"""REST API endpoints for the kifu album (tournament game records) module."""

from typing import Optional, List

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session, defer

from katrain.web.core.db import get_db
from katrain.web.core.models_db import KifuAlbum, KifuAlbumEventSelection, KifuEvent
from katrain.web.core.repository import RemoteServiceUnavailableError
from katrain.web.kifu.identity import (
    LANGUAGES,
    name_display_language,
    display_event_name,
    display_maps,
    live_event_selections,
    matching_entity_ids,
    obscured_program_event_ids,
    resolve_strict_display,
    strict_display_maps,
    strict_matching_names,
    strict_raw_player_search_clause,
    strict_raw_event_search_clause,
    strict_names_enabled,
    strict_selected_event_search_ids,
)
from katrain.web.kifu.name_parse import parse_player
from katrain.web.kifu.round_names import display_round_name

router = APIRouter()

# The archive uses Japanese romanizations while many kiosk users search in Chinese.
_HISTORICAL_PLAYER_ALIASES = {
    "吴清源": ("go seigen",),
    "吳清源": ("吴清源", "go seigen"),
    "道策": ("honinbo dosaku",),
    "丈和": ("honinbo jowa", "kadono jowa", "kadono matsunosuke", "todani matsunosuke"),
    "秀策": ("shusaku", "yasuda eisai"),
    "木谷实": ("kitani minoru",),
    "木谷實": ("木谷实", "kitani minoru"),
}


async def _from_dispatcher(call, not_found_detail: str):
    """board 模式走云端。**连不上是 503,不是空库**(见 `RepositoryDispatcher.kifu_list_albums` 那段注释)。"""
    try:
        return await call()
    except RemoteServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        detail = not_found_detail if status == 404 else f"Remote kifu request failed ({status})"
        raise HTTPException(status_code=status, detail=detail) from exc


class KifuAlbumSummary(BaseModel):
    """Summary response for kifu album listing (excludes sgf_content)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    player_black: str
    player_white: str
    black_rank: Optional[str]
    white_rank: Optional[str]
    event: Optional[str]
    result: Optional[str]
    rules: Optional[str]
    date_played: Optional[str]
    komi: Optional[float]
    handicap: int
    board_size: int
    round_name: Optional[str]
    move_count: int
    display_player_black: str = ""
    display_player_white: str = ""
    display_black_rank: Optional[str] = None
    display_white_rank: Optional[str] = None
    display_event: Optional[str] = None
    display_round_name: Optional[str] = None
    sources: List[str] = Field(default_factory=list)


class KifuAlbumDetail(KifuAlbumSummary):
    """Full response including SGF content."""

    place: Optional[str]
    rules: Optional[str]
    source: Optional[str]
    sgf_content: str


class KifuAlbumListResponse(BaseModel):
    """Paginated list response."""

    items: List[KifuAlbumSummary]
    total: int
    page: int
    page_size: int


@router.get("/albums", response_model=KifuAlbumListResponse)
async def list_kifu_albums(
    request: Request,
    q: Optional[str] = Query(None, description="Search query (fuzzy match on player names, event, date)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    lang: str = "cn",
    db: Session = Depends(get_db),
):
    """List tournament game records with optional search and pagination."""
    if lang not in LANGUAGES:
        raise HTTPException(status_code=422, detail="Unsupported language")
    # Board mode: delegate to repository dispatcher
    dispatcher = getattr(request.app.state, "repository_dispatcher", None)
    if dispatcher is not None:
        return await _from_dispatcher(
            lambda: dispatcher.kifu_list_albums(q, page, page_size, lang), "Kifu albums not found"
        )
    requested_lang = lang
    lang = name_display_language(lang)

    query = db.query(KifuAlbum).options(defer(KifuAlbum.sgf_content), defer(KifuAlbum.search_text))
    visible = (KifuAlbum.duplicate_of_id.is_(None), KifuAlbum.list_hidden_reason.is_(None))
    query = query.filter(*visible)
    count_query = db.query(func.count(KifuAlbum.id)).filter(*visible)

    if q:
        strict = strict_names_enabled()
        raw_name_rows = []
        player_ids, event_ids, raw_players, raw_event_name_ids = strict_matching_names(
            db, q, raw_name_rows=raw_name_rows
        )
        selected_event_ids = strict_selected_event_search_ids(db, q, raw_event_name_ids, event_ids)
        if not strict:
            legacy_players, legacy_events = matching_entity_ids(db, q, exact=True)
            player_ids |= legacy_players
            event_ids |= legacy_events
        if len(player_ids) == 1 and not event_ids and not raw_players and not raw_event_name_ids:
            player_id = next(iter(player_ids))
            needle = or_(KifuAlbum.black_player_id == player_id, KifuAlbum.white_player_id == player_id)
        elif len(event_ids) == 1 and not player_ids and not raw_players and not raw_event_name_ids:
            needle = KifuAlbum.event_id == next(iter(event_ids))
        else:
            partial_players, partial_events = (set(), set()) if strict else matching_entity_ids(db, q, exact=False)
            terms = (
                (q.lower(),) if strict else (q.lower(), *_HISTORICAL_PLAYER_ALIASES.get(q.removeprefix("本因坊"), ()))
            )
            player_match = or_(
                *(
                    func.lower(field).contains(term, autoescape=True)
                    for field in (KifuAlbum.player_black, KifuAlbum.player_white)
                    for term in terms
                )
            )
            clauses = [KifuAlbum.search_text.contains(q.lower(), autoescape=True), player_match]
            if partial_players:
                clauses.extend(
                    (KifuAlbum.black_player_id.in_(partial_players), KifuAlbum.white_player_id.in_(partial_players))
                )
            if partial_events:
                clauses.append(KifuAlbum.event_id.in_(partial_events))
            if strict or raw_players or raw_event_name_ids:
                if player_ids:
                    clauses.extend(
                        (KifuAlbum.black_player_id.in_(player_ids), KifuAlbum.white_player_id.in_(player_ids))
                    )
                if event_ids:
                    clauses.append(KifuAlbum.event_id.in_(event_ids))
                if raw_players:
                    clauses.append(strict_raw_player_search_clause(db, raw_players, q, names=raw_name_rows))
                if raw_event_name_ids:
                    clauses.append(strict_raw_event_search_clause(db, raw_event_name_ids))
            needle = or_(*clauses)
            query = query.order_by(case((player_match, 0), else_=1))
        if selected_event_ids:
            needle = or_(needle, KifuAlbum.id.in_(selected_event_ids))
        if not strict and lang == "cn":
            from katrain.web.kifu.first_pass_cn import search_raw_names, valid_override_search_ids

            provisional_players, provisional_events, provisional_albums = search_raw_names(q)
            if provisional_players:
                needle = or_(needle, KifuAlbum.player_black.in_(provisional_players),
                             KifuAlbum.player_white.in_(provisional_players))
            if provisional_events:
                no_selection = ~KifuAlbum.id.in_(db.query(KifuAlbumEventSelection.album_id))
                unlinked_raws = {raw for raw, canonical in provisional_events if canonical is None}
                if unlinked_raws:
                    needle = or_(needle, KifuAlbum.event_id.is_(None) & KifuAlbum.event.in_(unlinked_raws)
                                 & no_selection)
                for canonical in {canonical for _, canonical in provisional_events if canonical is not None}:
                    raws = {raw for raw, name in provisional_events if name == canonical}
                    matching_ids = db.query(KifuEvent.id).filter(KifuEvent.canonical_name == canonical)
                    needle = or_(needle, KifuAlbum.event.in_(raws) & KifuAlbum.event_id.in_(matching_ids)
                                 & no_selection)
            if provisional_albums:
                verified_albums = valid_override_search_ids(db, provisional_albums)
                if verified_albums:
                    needle = or_(needle, KifuAlbum.id.in_(verified_albums))
        query = query.filter(needle)
        count_query = count_query.filter(needle)

    # Sort by normalized date descending (nulls last), then by id for deterministic pagination
    query = query.order_by(KifuAlbum.date_sort.desc().nulls_last(), KifuAlbum.id.desc())

    # `Query.count()` wraps the *ordered* query in a subquery, so the ORDER BY survives
    # into a COUNT that cannot possibly need it. On the 151k-row production table that
    # cost an external merge sort on disk: 557ms, versus 27ms for a bare COUNT
    # (measured 2026-08-24 with EXPLAIN ANALYZE). Count from a separate unordered query.
    total = count_query.scalar() or 0
    records = query.offset((page - 1) * page_size).limit(page_size).all()

    selected_events = live_event_selections(db, records)
    strict = strict_names_enabled()
    fallback_maps = None if strict else display_maps(db, records, lang, selected_events=selected_events)
    obscured_event_ids = obscured_program_event_ids(db, records, selected_events=selected_events)
    players, events, event_canonical_names, sources, raw_players, raw_events = strict_display_maps(
        db, records, lang, selected_events=selected_events
    )
    return KifuAlbumListResponse(
        items=[
            _summary(
                r,
                players,
                events,
                event_canonical_names,
                sources,
                lang,
                round_lang=requested_lang,
                raw_players=raw_players,
                raw_events=raw_events,
                obscured_event_ids=obscured_event_ids,
                selected_events=selected_events,
                fallback_maps=fallback_maps,
            )
            for r in records
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/albums/{album_id}", response_model=KifuAlbumDetail)
async def get_kifu_album(request: Request, album_id: int, lang: str = "cn", db: Session = Depends(get_db)):
    """Get a single kifu album record with full SGF content."""
    if lang not in LANGUAGES:
        raise HTTPException(status_code=422, detail="Unsupported language")
    # Board mode: delegate to repository dispatcher
    dispatcher = getattr(request.app.state, "repository_dispatcher", None)
    if dispatcher is not None:
        result = await _from_dispatcher(
            lambda: dispatcher.kifu_get_album(album_id, lang), f"Kifu album {album_id} not found"
        )
        if not result:
            raise HTTPException(status_code=404, detail=f"Kifu album {album_id} not found")
        return result
    requested_lang = lang
    lang = name_display_language(lang)

    record = db.query(KifuAlbum).filter(KifuAlbum.id == album_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"Kifu album {album_id} not found")

    selected_events = live_event_selections(db, [record])
    strict = strict_names_enabled()
    fallback_maps = None if strict else display_maps(db, [record], lang, selected_events=selected_events)
    obscured_event_ids = obscured_program_event_ids(db, [record], selected_events=selected_events)
    players, events, event_canonical_names, sources, raw_players, raw_events = strict_display_maps(
        db, [record], lang, selected_events=selected_events
    )
    values = _summary(
        record,
        players,
        events,
        event_canonical_names,
        sources,
        lang,
        round_lang=requested_lang,
        raw_players=raw_players,
        raw_events=raw_events,
        obscured_event_ids=obscured_event_ids,
        selected_events=selected_events,
        fallback_maps=fallback_maps,
    ).model_dump()
    return KifuAlbumDetail.model_validate(
        {**values, "place": record.place, "source": record.source, "sgf_content": record.sgf_content}
    )


def _summary(
    record: KifuAlbum,
    players: dict[int, str],
    events: dict[int, str],
    event_canonical_names: dict[int, str],
    sources: dict[int, list[str]],
    lang: str,
    *,
    round_lang: str | None = None,
    raw_players: dict[str, str] | None = None,
    raw_events: dict[str, str] | None = None,
    obscured_event_ids: set[int] | None = None,
    selected_events: dict[int, tuple[str, int | None]] | None = None,
    fallback_maps: tuple | None = None,
) -> KifuAlbumSummary:
    summary = KifuAlbumSummary.model_validate(record)
    black = parse_player(record.player_black, record.black_rank)
    white = parse_player(record.player_white, record.white_rank)
    strict = raw_players is not None and raw_events is not None
    fallback_names = None
    if fallback_maps is not None:
        fallback_players, fallback_events, fallback_canonical, _, event_hints = fallback_maps
        if lang == "cn":
            from katrain.web.kifu.first_pass_cn import player_name

            black_raw_hint = player_name(record.player_black)
            white_raw_hint = player_name(record.player_white)
        else:
            black_raw_hint = white_raw_hint = None
        linked_canonical = fallback_canonical.get(record.event_id)
        if record.event_id in fallback_events:
            fallback_event = display_event_name(
                record.event, fallback_events[record.event_id], lang, linked_canonical_name=linked_canonical
            )
        else:
            fallback_event = event_hints.get(record.id) or display_event_name(
                record.event, linked_canonical if lang == "cn" else None, lang,
                linked_canonical_name=linked_canonical,
            )
        fallback_names = (
            fallback_players.get(record.black_player_id) or black_raw_hint or black.name,
            fallback_players.get(record.white_player_id) or white_raw_hint or white.name,
            fallback_event,
        )
    if strict:
        black_name, white_name, displayed_event = resolve_strict_display(
            record, lang, players, events, event_canonical_names, raw_players, raw_events,
            obscured_event_ids=obscured_event_ids,
            selected_events=selected_events,
            fallback_names=fallback_names,
        )
    else:
        black_name = players.get(record.black_player_id, black.name)
        white_name = players.get(record.white_player_id, white.name)
        displayed_event = display_event_name(
            record.event,
            events.get(record.event_id),
            lang,
            linked_canonical_name=event_canonical_names.get(record.event_id),
        )
    return summary.model_copy(
        update={
            "display_player_black": black_name,
            "display_player_white": white_name,
            "display_black_rank": black.display_rank,
            "display_white_rank": white.display_rank,
            "display_event": displayed_event,
            "display_round_name": display_round_name(record.round_name, round_lang or lang),
            "sources": sources.get(record.id, []),
        }
    )
