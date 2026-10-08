"""REST API endpoints for the kifu album (tournament game records) module."""

from typing import Optional, List
import hashlib

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session, defer
from katrain.cron.kifu_parameters import ParameterError, resolve_parameters, validate_parameters

from katrain.web.core.db import get_db
from katrain.web.core.models_db import KifuAlbum, KifuAnalysisJob, KifuAnalysisMove
from katrain.web.core.repository import RemoteServiceUnavailableError
from katrain.web.kifu.identity import (
    LANGUAGES,
    display_event_name,
    display_maps,
    matching_entity_ids,
    split_player_rank,
)
from katrain.web.kifu.round_names import display_round_name
from katrain.web.kifu.library import report_availability

router = APIRouter()
KIFU_MODEL_SHA256 = "93bdb63a3bfae4a70db0cb5265287495ecfc10b1ba1cc6814feeba1cdf055871"
KIFU_VISITS = 2000

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
    has_analysis: bool = False


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
    preview: Optional[KifuAlbumDetail] = None


@router.get("/albums/{album_id}/analysis")
async def get_kifu_analysis(request: Request, album_id: int, db: Session = Depends(get_db)):
    """Read the current pinned analysis; exact duplicates share their canonical job.

    analysis_parameters is the validated stored engine-input snapshot, never the
    album's raw metadata. Invalid/missing proof returns rules_unresolved, an
    actionable parameter_error and no moves. Album/SGF reading remains available.
    """
    dispatcher = getattr(request.app.state, "repository_dispatcher", None)
    if dispatcher is not None:
        return await _from_dispatcher(
            lambda: dispatcher.kifu_get_analysis(album_id), f"Kifu album {album_id} not found"
        )

    album = db.query(KifuAlbum).filter(KifuAlbum.id == album_id).first()
    if album is None:
        raise HTTPException(status_code=404, detail=f"Kifu album {album_id} not found")
    canonical_id = album.duplicate_of_id or album.id
    canonical = album if canonical_id == album.id else db.query(KifuAlbum).filter(KifuAlbum.id == canonical_id).first()
    if canonical is None or canonical.duplicate_of_id is not None:
        raise HTTPException(status_code=409, detail="Canonical kifu album is invalid")
    sgf_sha256 = hashlib.sha256(canonical.sgf_content.encode("utf-8")).hexdigest()
    # A duplicate link is only valid while both SGF payloads remain byte-identical.
    if album.id != canonical_id and album.sgf_content != canonical.sgf_content:
        canonical_id = album.id
        canonical = album
        sgf_sha256 = hashlib.sha256(album.sgf_content.encode("utf-8")).hexdigest()
    job = (
        db.query(KifuAnalysisJob)
        .filter(
            KifuAnalysisJob.album_id == canonical_id,
            KifuAnalysisJob.sgf_sha256 == sgf_sha256,
            KifuAnalysisJob.model_sha256 == KIFU_MODEL_SHA256,
            KifuAnalysisJob.requested_visits == KIFU_VISITS,
        )
        .first()
    )
    parameters = None
    parameter_error = None
    try:
        if job is not None:
            parameters = validate_parameters(canonical.sgf_content, job.analysis_parameters)
        else:
            # Can explain missing metadata before admission, but only a stored
            # engine-input snapshot may be presented as report parameters.
            resolve_parameters(canonical.sgf_content)
    except ParameterError as exc:
        parameter_error = exc.as_dict()
    moves = (
        []
        if job is None or parameter_error
        else (
            db.query(KifuAnalysisMove)
            .filter(KifuAnalysisMove.job_id == job.id)
            .order_by(KifuAnalysisMove.move_number)
            .all()
        )
    )
    if parameters and any(row.parameter_sha256 != parameters["parameter_sha256"] for row in moves):
        parameter_error = {
            "code": "parameter_mismatch",
            "message": "Stored positions use stale or unverified parameters",
        }
        parameters = None
        moves = []
    complete = bool(
        job
        and len(moves) == job.total_moves + 1
        and all(row.move_number == number and row.root_visits >= KIFU_VISITS for number, row in enumerate(moves))
    )
    status = job.status if job else "unavailable"
    error_message = job.error_message if job else None
    if parameter_error:
        status = "rules_unresolved"
        error_message = parameter_error["message"]
    if status == "completed" and not complete:
        status = "failed"
        error_message = "Stored analysis is incomplete"
    fields = (
        "move_number",
        "actual_move",
        "actual_player",
        "winrate",
        "score_lead",
        "visits",
        "root_visits",
        "top_moves",
        "ownership",
        "delta_score",
        "delta_winrate",
        "grade",
        "points_lost",
        "points_lost_source",
        "is_top_move",
        "top_prior",
        "brilliance",
    )
    return {
        "album_id": album_id,
        "canonical_album_id": canonical_id,
        "sgf_sha256": sgf_sha256,
        "model_sha256": KIFU_MODEL_SHA256,
        "requested_visits": KIFU_VISITS,
        "status": status,
        "analysis_parameters": parameters,
        "parameters_valid": parameters is not None,
        "parameters_verified": bool(parameters and parameters["verified"]),
        "parameter_error": parameter_error,
        "total_moves": job.total_moves if job else canonical.move_count,
        "analyzed_moves": job.analyzed_moves if job and not parameter_error else 0,
        "error_message": error_message,
        "moves": [{field: getattr(row, field) for field in fields} for row in moves if row.root_visits >= KIFU_VISITS],
    }


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

    query = db.query(KifuAlbum).options(defer(KifuAlbum.search_text))
    query = query.filter(KifuAlbum.duplicate_of_id.is_(None))
    count_query = db.query(func.count(KifuAlbum.id)).filter(KifuAlbum.duplicate_of_id.is_(None))

    if q:
        player_ids, event_ids = matching_entity_ids(db, q, exact=True)
        if len(player_ids) == 1 and not event_ids:
            player_id = next(iter(player_ids))
            needle = or_(KifuAlbum.black_player_id == player_id, KifuAlbum.white_player_id == player_id)
        elif len(event_ids) == 1 and not player_ids:
            needle = KifuAlbum.event_id == next(iter(event_ids))
        else:
            partial_players, partial_events = matching_entity_ids(db, q, exact=False)
            terms = (q.lower(), *_HISTORICAL_PLAYER_ALIASES.get(q.removeprefix("本因坊"), ()))
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
            needle = or_(*clauses)
            query = query.order_by(case((player_match, 0), else_=1))
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

    players, events, sources = display_maps(db, records, lang)
    availability = report_availability(db, records, KIFU_MODEL_SHA256, KIFU_VISITS)
    items = [
        _summary(r, players, events, sources, lang).model_copy(update={"has_analysis": availability[r.id]})
        for r in records
    ]
    preview = (
        None
        if not records
        else KifuAlbumDetail.model_validate(
            {
                **items[0].model_dump(),
                "place": records[0].place,
                "source": records[0].source,
                "sgf_content": records[0].sgf_content,
            }
        )
    )
    return KifuAlbumListResponse(
        items=items,
        preview=preview,
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

    record = db.query(KifuAlbum).filter(KifuAlbum.id == album_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"Kifu album {album_id} not found")

    players, events, sources = display_maps(db, [record], lang)
    values = _summary(record, players, events, sources, lang).model_dump()
    values["has_analysis"] = report_availability(db, [record], KIFU_MODEL_SHA256, KIFU_VISITS)[record.id]
    return KifuAlbumDetail.model_validate(
        {**values, "place": record.place, "source": record.source, "sgf_content": record.sgf_content}
    )


def _summary(
    record: KifuAlbum, players: dict[int, str], events: dict[int, str], sources: dict[int, list[str]], lang: str
) -> KifuAlbumSummary:
    summary = KifuAlbumSummary.model_validate(record)
    black_name, embedded_black_rank = split_player_rank(record.player_black)
    white_name, embedded_white_rank = split_player_rank(record.player_white)
    return summary.model_copy(
        update={
            "display_player_black": players.get(record.black_player_id, black_name),
            "display_player_white": players.get(record.white_player_id, white_name),
            "display_black_rank": record.black_rank or embedded_black_rank,
            "display_white_rank": record.white_rank or embedded_white_rank,
            "display_event": display_event_name(record.event, events.get(record.event_id), lang),
            "display_round_name": display_round_name(record.round_name, lang),
            "sources": sources.get(record.id, []),
        }
    )
