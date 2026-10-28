"""REST API endpoints for the kifu album (tournament game records) module."""

from typing import Annotated, Optional, List
import hashlib
from time import perf_counter

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, false, func, or_
from sqlalchemy.orm import Session, defer, load_only
from starlette.concurrency import run_in_threadpool
from katrain.core.sgf_parser import SGF
from katrain.cron.kifu_parameters import ParameterError, resolve_parameters, validate_parameters
from katrain.kifu_ingest.ranks import display_rank_for_game_slot

from katrain.web.core.db import SessionLocal, get_db
from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumEventSelection,
    KifuAnalysisJob,
    KifuAnalysisMove,
    KifuEvent,
)
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
from katrain.web.kifu.name_parse import parse_event, parse_player
from katrain.web.kifu.player_ranks import lookup_album_rank_snapshots
from katrain.web.kifu.round_names import display_round_name
from katrain.web.kifu.library import report_availability
from katrain.web.kifu.library_search import HISTORICAL_PLAYER_ALIASES, public_player_id, unique_exact_player_id
from katrain.web.kifu.prepared_read import (
    PreparedSearchNotReady,
    begin_read_snapshot,
    current_policy_signature,
    read_displays,
    read_state,
    require_ready,
    search_filter,
)

router = APIRouter()
KIFU_MODEL_SHA256 = "93bdb63a3bfae4a70db0cb5265287495ecfc10b1ba1cc6814feeba1cdf055871"
KIFU_VISITS = 2000

_HISTORICAL_PLAYER_ALIASES = HISTORICAL_PLAYER_ALIASES


def _obscured_program_event_ids_loaded(db: Session, albums: list, selected_events: dict) -> set[int]:
    """Use SGF content already loaded for the list preview and analysis status."""
    candidates = [album for album in albums if album.event == "GNUGo3.8" and album.id not in selected_events]
    if not candidates:
        return set()
    obscured = {
        album_id
        for (album_id,) in db.query(KifuAlbumEventSelection.album_id).filter(
            KifuAlbumEventSelection.album_id.in_([album.id for album in candidates])
        )
    }
    for album in candidates:
        try:
            names = SGF.parse_sgf(album.sgf_content).get_list_property("GN") or []
        except Exception:
            obscured.add(album.id)
            continue
        if (
            names
            and names[0] == "GNUGo3.8"
            and any(
                name
                and name != names[0]
                and parse_event(name, None).category not in {"program_source_label", "corrupt_data"}
                for name in names[1:]
            )
        ):
            obscured.add(album.id)
    return obscured


def _cloud_prepared_not_ready(exc):
    if not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code != 503:
        return False
    try:
        payload = exc.response.json()
    except ValueError:
        return False
    detail = payload.get("detail") if isinstance(payload, dict) else None
    return isinstance(detail, dict) and detail.get("code") == PreparedSearchNotReady.code


async def _from_dispatcher(call, not_found_detail: str):
    """Board proxy: distinguish cloud HTTP failure from an unreachable cloud."""
    try:
        return await call()
    except RemoteServiceUnavailableError as exc:
        if _cloud_prepared_not_ready(exc.__cause__):
            raise _not_ready(PreparedSearchNotReady("cloud")) from exc
        code = "kifu_cloud_error" if isinstance(exc.__cause__, httpx.HTTPStatusError) else "kifu_cloud_unreachable"
        raise HTTPException(status_code=503, detail={"code": code, "message": str(exc)}) from exc
    except httpx.HTTPStatusError as exc:
        if _cloud_prepared_not_ready(exc):
            raise _not_ready(PreparedSearchNotReady("cloud")) from exc
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
    black_rank_origin: str = "unknown"
    white_rank_origin: str = "unknown"
    black_rank_source: Optional[dict] = None
    white_rank_source: Optional[dict] = None
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


_PREPARED_ALBUM_COLUMNS = (
    KifuAlbum.id,
    KifuAlbum.player_black,
    KifuAlbum.player_white,
    KifuAlbum.black_rank,
    KifuAlbum.white_rank,
    KifuAlbum.event,
    KifuAlbum.result,
    KifuAlbum.rules,
    KifuAlbum.date_played,
    KifuAlbum.komi,
    KifuAlbum.handicap,
    KifuAlbum.board_size,
    KifuAlbum.round_name,
    KifuAlbum.move_count,
    KifuAlbum.place,
    KifuAlbum.source,
    KifuAlbum.sgf_content,
    KifuAlbum.source_path,
    KifuAlbum.duplicate_of_id,
)


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


def get_kifu_session_factory():
    """Inject a factory, never a Session created on a dependency worker thread."""
    return SessionLocal


@router.get("/search-ready")
def kifu_search_ready(session_factory=Depends(get_kifu_session_factory)):
    """Expose this web process's policy hash independently of generic health."""
    with session_factory() as db:
        begin_read_snapshot(db)
        runtime_signature = current_policy_signature()
        value, ready, unavailable = None, False, False
        try:
            value = read_state(db)
            ready = require_ready(db) is not None
        except PreparedSearchNotReady:
            unavailable = True
        return JSONResponse(
            status_code=503 if unavailable else 200,
            content={
                "kifu_search_ready": ready,
                "runtime_policy_signature": runtime_signature,
                "policy_signature": value["policy_signature"] if value else None,
                "enabled": bool(value and value["enabled"]),
                "ready": bool(value and value["ready"]),
                "initial_coverage_complete": bool(value and value["initial_coverage_complete"]),
                "phase": value["phase"] if value else "unmigrated",
            },
        )


def read_in_owned_session(session_factory, *, submitted_at, timings, **params):
    """Construct, read and close each local Session on the same bounded pool worker."""
    started = perf_counter()
    timings["kifu_queue"] = (started - submitted_at) * 1000
    try:
        with session_factory() as db:
            return read_album_page(db, timings=timings, **params)
    finally:
        timings["kifu_worker"] = (perf_counter() - started) * 1000


@router.get("/albums", response_model=KifuAlbumListResponse)
async def list_kifu_albums(
    request: Request,
    response: Response = None,
    q: Optional[str] = Query(None, description="Search query (fuzzy match on player names, event, date)"),
    player_id: Annotated[int | None, Query(ge=1, description="Filter a public player identity")] = None,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    lang: str = "cn",
    session_factory=Depends(get_kifu_session_factory),
):
    """List records; local synchronous database work stays off the event loop."""
    started = perf_counter()
    _validate_list_params(q, player_id, lang)
    dispatcher = getattr(request.app.state, "repository_dispatcher", None)
    if dispatcher is not None:
        params = {"q": q, "page": page, "page_size": page_size, "lang": lang}
        if player_id is not None:
            params["player_id"] = player_id
        return await _from_dispatcher(lambda: dispatcher.kifu_list_albums(**params), "Kifu albums not found")
    timings = {}
    result = await run_in_threadpool(
        read_in_owned_session,
        session_factory,
        submitted_at=perf_counter(),
        timings=timings,
        q=q,
        player_id=player_id,
        page=page,
        page_size=page_size,
        lang=lang,
    )
    # Handler ends before FastAPI serialization/ASGI sending. These explicit names
    # must not be presented as complete HTTP or browser request measurements.
    timings["kifu_handler"] = (perf_counter() - started) * 1000
    if response is not None:
        response.headers["Server-Timing"] = ", ".join(
            f"{name};dur={duration:.3f}" for name, duration in timings.items()
        )
    return result


def _validate_list_params(q, player_id, lang):
    if lang not in LANGUAGES:
        raise HTTPException(status_code=422, detail="Unsupported language")
    if player_id is not None and (player_id < 1 or q is not None):
        raise HTTPException(status_code=422, detail="player_id must be positive and cannot be combined with q")


def _not_ready(exc):
    return HTTPException(status_code=503, detail={"code": exc.code, "message": "Kifu search is not ready"})


def read_album_page(db, *, q=None, player_id=None, page=1, page_size=20, lang="cn", timings=None):
    """Read prepared names and the complete page in the worker's one snapshot."""
    _validate_list_params(q, player_id, lang)
    begin_read_snapshot(db)
    try:
        if require_ready(db) is None:
            return read_album_page_legacy(
                db, q=q, player_id=player_id, page=page, page_size=page_size, lang=lang, timings=timings
            )
        return _read_prepared_album_page(
            db, q=q, player_id=player_id, page=page, page_size=page_size, lang=lang, timings=timings
        )
    except PreparedSearchNotReady as exc:
        raise _not_ready(exc) from exc


def _read_prepared_album_page(db, *, q=None, player_id=None, page=1, page_size=20, lang="cn", timings=None):
    """Forced prepared read after the caller verifies its snapshot's ready gate.

    The explicit CLI comparison may use this while enabled is still false; it
    checks coverage/policy/dirty in the same snapshot before calling this helper.
    """
    timings = {} if timings is None else timings
    started = perf_counter()
    predicate, priority = search_filter(
        db, query=q, player_id=player_id, lang=name_display_language(lang), strict=strict_names_enabled()
    )
    timings["kifu_candidate"] = (perf_counter() - started) * 1000
    visible = (KifuAlbum.duplicate_of_id.is_(None), KifuAlbum.list_hidden_reason.is_(None))
    query = db.query(KifuAlbum).options(load_only(*_PREPARED_ALBUM_COLUMNS)).filter(*visible)
    count_query = db.query(func.count(KifuAlbum.id)).filter(*visible)
    if predicate is not None:
        query = query.filter(predicate)
        count_query = count_query.filter(predicate)
    if priority is not None:
        query = query.order_by(case((priority, 0), else_=1))
    query = query.order_by(KifuAlbum.date_sort.desc().nulls_last(), KifuAlbum.id.desc())
    started = perf_counter()
    total = count_query.scalar() or 0
    timings["kifu_count"] = (perf_counter() - started) * 1000
    started = perf_counter()
    # Current report/rank identity checks require every page row's SGF. Keep the
    # bounded page read rather than weakening those checks to load only preview.
    records = query.offset((page - 1) * page_size).limit(page_size).all()
    timings["kifu_page"] = (perf_counter() - started) * 1000
    started = perf_counter()
    displays = read_displays(db, [record.id for record in records], name_display_language(lang))
    timings["kifu_display"] = (perf_counter() - started) * 1000
    started = perf_counter()
    availability = report_availability(db, records, KIFU_MODEL_SHA256, KIFU_VISITS)
    timings["kifu_report"] = (perf_counter() - started) * 1000
    started = perf_counter()
    ranks = lookup_album_rank_snapshots(db.connection(), [record.id for record in records])
    timings["kifu_rank"] = (perf_counter() - started) * 1000
    items = []
    for record in records:
        display = displays[record.id]
        items.append(
            _summary(
                record,
                (display["player_black"], display["player_white"], display["event"]),
                display["strict_outputs"]["sources"],
                lang,
                rank_snapshots=ranks,
            ).model_copy(update={"has_analysis": availability[record.id]})
        )
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
    return KifuAlbumListResponse(items=items, total=total, page=page, page_size=page_size, preview=preview)


def read_album_page_legacy(db, *, q=None, player_id=None, page=1, page_size=20, lang="cn", timings=None):
    """Synchronous local list core, retaining the existing page and preview contract."""
    _validate_list_params(q, player_id, lang)
    begin_read_snapshot(db)
    timings = {} if timings is None else timings
    requested_lang = lang
    lang = name_display_language(lang)
    orthographic_batch_contexts = {}

    query = db.query(KifuAlbum).options(defer(KifuAlbum.search_text))
    visible = (KifuAlbum.duplicate_of_id.is_(None), KifuAlbum.list_hidden_reason.is_(None))
    query = query.filter(*visible)
    count_query = db.query(func.count(KifuAlbum.id)).filter(*visible)

    candidate_started = perf_counter()
    exact_id = (
        unique_exact_player_id(
            db, q, strict=strict_names_enabled(), orthographic_batch_contexts=orthographic_batch_contexts
        )
        if q
        else None
    )
    if player_id is not None or exact_id is not None:
        identity_id = player_id if player_id is not None else exact_id
        approved = exact_id is not None or public_player_id(
            db, identity_id, orthographic_batch_contexts=orthographic_batch_contexts
        )
        needle = (
            or_(KifuAlbum.black_player_id == identity_id, KifuAlbum.white_player_id == identity_id)
            if approved
            else false()
        )
        query = query.filter(needle)
        count_query = count_query.filter(needle)
    elif q:
        strict = strict_names_enabled()
        raw_name_rows = []
        player_ids, event_ids, raw_players, raw_event_name_ids = strict_matching_names(
            db, q, raw_name_rows=raw_name_rows, orthographic_batch_contexts=orthographic_batch_contexts
        )
        shared_player_ids = set(player_ids) if len(player_ids) > 1 else set()
        selected_event_ids = strict_selected_event_search_ids(db, q, raw_event_name_ids, event_ids)
        if not strict:
            legacy_players, legacy_events = matching_entity_ids(
                db, q, exact=True, orthographic_batch_contexts=orthographic_batch_contexts
            )
            player_ids |= legacy_players
            event_ids |= legacy_events
        exact_raw_event = bool(raw_event_name_ids) and not player_ids and not event_ids and not raw_players
        exact_player = len(player_ids) == 1 and not event_ids and not raw_players and not raw_event_name_ids
        exact_player_with_raw = (
            len(player_ids) == 1
            and bool(raw_players)
            and not event_ids
            and not raw_event_name_ids
            and not selected_event_ids
        )
        player_only_search = (exact_player or exact_player_with_raw) and not selected_event_ids
        shared_players = bool(shared_player_ids) and not event_ids and not raw_event_name_ids
        if exact_player:
            player_id = next(iter(player_ids))
            needle = or_(KifuAlbum.black_player_id == player_id, KifuAlbum.white_player_id == player_id)
        elif exact_player_with_raw:
            player_id = next(iter(player_ids))
            needle = or_(
                KifuAlbum.black_player_id == player_id,
                KifuAlbum.white_player_id == player_id,
                strict_raw_player_search_clause(db, raw_players, q, names=raw_name_rows),
            )
        elif shared_players:
            needle = or_(
                KifuAlbum.black_player_id.in_(shared_player_ids), KifuAlbum.white_player_id.in_(shared_player_ids)
            )
            if raw_players:
                needle = or_(needle, strict_raw_player_search_clause(db, raw_players, q, names=raw_name_rows))
        elif len(event_ids) == 1 and not player_ids and not raw_players and not raw_event_name_ids:
            needle = KifuAlbum.event_id == next(iter(event_ids))
        elif exact_raw_event:
            needle = strict_raw_event_search_clause(db, raw_event_name_ids)
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
        if selected_event_ids and not shared_players:
            needle = or_(needle, KifuAlbum.id.in_(selected_event_ids))
        if not strict and lang == "cn" and not exact_raw_event and not shared_players and not player_only_search:
            from katrain.web.kifu.first_pass_cn import search_raw_names, valid_override_search_ids

            provisional_players, provisional_events, provisional_albums = search_raw_names(q)
            if provisional_players:
                needle = or_(
                    needle,
                    KifuAlbum.player_black.in_(provisional_players),
                    KifuAlbum.player_white.in_(provisional_players),
                )
            if provisional_events and not exact_player:
                no_selection = ~KifuAlbum.id.in_(db.query(KifuAlbumEventSelection.album_id))
                unlinked_raws = {raw for raw, canonical in provisional_events if canonical is None}
                if unlinked_raws:
                    needle = or_(
                        needle, KifuAlbum.event_id.is_(None) & KifuAlbum.event.in_(unlinked_raws) & no_selection
                    )
                for canonical in {canonical for _, canonical in provisional_events if canonical is not None}:
                    raws = {raw for raw, name in provisional_events if name == canonical}
                    matching_ids = db.query(KifuEvent.id).filter(KifuEvent.canonical_name == canonical)
                    needle = or_(
                        needle, KifuAlbum.event.in_(raws) & KifuAlbum.event_id.in_(matching_ids) & no_selection
                    )
            if provisional_albums and not exact_player:
                verified_albums = valid_override_search_ids(db, provisional_albums)
                if verified_albums:
                    needle = or_(needle, KifuAlbum.id.in_(verified_albums))
        query = query.filter(needle)
        count_query = count_query.filter(needle)

    timings["kifu_candidate"] = (perf_counter() - candidate_started) * 1000

    # Sort by normalized date descending (nulls last), then by id for deterministic pagination
    query = query.order_by(KifuAlbum.date_sort.desc().nulls_last(), KifuAlbum.id.desc())

    # `Query.count()` wraps the *ordered* query in a subquery, so the ORDER BY survives
    # into a COUNT that cannot possibly need it. On the 151k-row production table that
    # cost an external merge sort on disk: 557ms, versus 27ms for a bare COUNT
    # (measured 2026-08-24 with EXPLAIN ANALYZE). Count from a separate unordered query.
    segment_started = perf_counter()
    total = count_query.scalar() or 0
    timings["kifu_count"] = (perf_counter() - segment_started) * 1000
    segment_started = perf_counter()
    records = query.offset((page - 1) * page_size).limit(page_size).all()

    timings["kifu_page"] = (perf_counter() - segment_started) * 1000
    segment_started = perf_counter()
    selected_events = live_event_selections(db, records)
    strict = strict_names_enabled()
    fallback_maps = None if strict else display_maps(db, records, lang, selected_events=selected_events)
    obscured_event_ids = _obscured_program_event_ids_loaded(db, records, selected_events)
    players, events, event_canonical_names, sources, raw_players, raw_events = strict_display_maps(
        db, records, lang, selected_events=selected_events, orthographic_batch_contexts=orthographic_batch_contexts
    )
    timings["kifu_display"] = (perf_counter() - segment_started) * 1000
    segment_started = perf_counter()
    availability = report_availability(db, records, KIFU_MODEL_SHA256, KIFU_VISITS)
    timings["kifu_report"] = (perf_counter() - segment_started) * 1000
    segment_started = perf_counter()
    rank_snapshots = lookup_album_rank_snapshots(db.connection(), [record.id for record in records])
    timings["kifu_rank"] = (perf_counter() - segment_started) * 1000
    items = [
        _summary_legacy(
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
            rank_snapshots=rank_snapshots,
        ).model_copy(update={"has_analysis": availability[r.id]})
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


def _direct_kifu_db():
    """Production receives a factory; explicit Sessions remain a direct-call seam."""
    return None


@router.get("/albums/{album_id}", response_model=KifuAlbumDetail)
async def get_kifu_album(
    request: Request,
    album_id: int,
    lang: str = "cn",
    db: Session = Depends(_direct_kifu_db),
    session_factory=Depends(get_kifu_session_factory),
):
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
    if isinstance(db, Session):
        return read_album_detail(db, album_id, lang=lang)
    factory = session_factory if callable(session_factory) else get_kifu_session_factory()
    return await run_in_threadpool(read_detail_in_owned_session, factory, album_id, lang=lang)


def read_detail_in_owned_session(session_factory, album_id, *, lang="cn"):
    with session_factory() as db:
        return read_album_detail(db, album_id, lang=lang)


def read_album_detail(db, album_id, *, lang="cn"):
    if lang not in LANGUAGES:
        raise HTTPException(status_code=422, detail="Unsupported language")
    begin_read_snapshot(db)
    record = db.query(KifuAlbum).filter(KifuAlbum.id == album_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail=f"Kifu album {album_id} not found")
    try:
        if require_ready(db) is None:
            return read_album_detail_legacy(db, album_id, lang=lang, _record=record)
        display = read_displays(db, [record.id], name_display_language(lang))[record.id]
        values = _summary(
            record,
            (display["player_black"], display["player_white"], display["event"]),
            display["strict_outputs"]["sources"],
            lang,
            rank_snapshots=lookup_album_rank_snapshots(db.connection(), [record.id]),
        ).model_dump()
        values["has_analysis"] = report_availability(db, [record], KIFU_MODEL_SHA256, KIFU_VISITS)[record.id]
        return KifuAlbumDetail.model_validate(
            {
                **values,
                "place": record.place,
                "source": record.source,
                "sgf_content": record.sgf_content,
            }
        )
    except PreparedSearchNotReady as exc:
        raise _not_ready(exc) from exc


def read_album_detail_legacy(db, album_id, *, lang="cn", _record=None):
    """Explicit original proof reader, also usable for same-snapshot comparison."""
    if lang not in LANGUAGES:
        raise HTTPException(status_code=422, detail="Unsupported language")
    begin_read_snapshot(db)
    requested_lang = lang
    lang = name_display_language(lang)

    record = _record if _record is not None else db.query(KifuAlbum).filter(KifuAlbum.id == album_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"Kifu album {album_id} not found")

    selected_events = live_event_selections(db, [record])
    strict = strict_names_enabled()
    fallback_maps = None if strict else display_maps(db, [record], lang, selected_events=selected_events)
    obscured_event_ids = obscured_program_event_ids(db, [record], selected_events=selected_events)
    players, events, event_canonical_names, sources, raw_players, raw_events = strict_display_maps(
        db, [record], lang, selected_events=selected_events
    )
    values = _summary_legacy(
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
        rank_snapshots=lookup_album_rank_snapshots(db.connection(), [record.id]),
    ).model_dump()
    values["has_analysis"] = report_availability(db, [record], KIFU_MODEL_SHA256, KIFU_VISITS)[record.id]
    return KifuAlbumDetail.model_validate(
        {**values, "place": record.place, "source": record.source, "sgf_content": record.sgf_content}
    )


def _summary_legacy(
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
    rank_snapshots: dict | None = None,
) -> KifuAlbumSummary:
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
                record.event,
                linked_canonical if lang == "cn" else None,
                lang,
                linked_canonical_name=linked_canonical,
            )
        fallback_names = (
            fallback_players.get(record.black_player_id) or black_raw_hint or black.name,
            fallback_players.get(record.white_player_id) or white_raw_hint or white.name,
            fallback_event,
        )
    if strict:
        black_name, white_name, displayed_event = resolve_strict_display(
            record,
            lang,
            players,
            events,
            event_canonical_names,
            raw_players,
            raw_events,
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
    return _summary(
        record,
        (black_name, white_name, displayed_event),
        sources.get(record.id, []),
        round_lang or lang,
        rank_snapshots=rank_snapshots,
    )


def _summary(record, names, sources, round_lang, *, rank_snapshots=None):
    """Assemble approved names with current game scalars and bounded rank data."""
    summary = KifuAlbumSummary.model_validate(record)
    black = parse_player(record.player_black, record.black_rank)
    white = parse_player(record.player_white, record.white_rank)
    return summary.model_copy(
        update={
            "display_player_black": names[0],
            "display_player_white": names[1],
            **_rank_displays(record, black, white, rank_snapshots or {}),
            "display_event": names[2],
            "display_round_name": display_round_name(record.round_name, round_lang),
            "sources": sources,
        }
    )


def _rank_displays(record, black, white, snapshots):
    """Render only exact-bound frozen overlays; malformed rows keep raw display."""
    values = {}
    sgf_sha256 = None
    for side, parsed in (("black", black), ("white", white)):
        raw = getattr(record, f"{side}_rank")
        rendered = display_rank_for_game_slot(None, parsed.display_rank)
        if raw:
            rendered["rank_origin"] = "source"
        row = snapshots.get((record.id, side))
        if row is not None:
            try:
                snapshot = row["snapshot"]
                ref = snapshot["source_ref"]
                if sgf_sha256 is None:
                    sgf_sha256 = hashlib.sha256(record.sgf_content.encode("utf-8")).hexdigest()
                if (
                    row["album_id"] == record.id
                    and row["side"] == side
                    and row["snapshot_sha256"] == snapshot["content_sha256"]
                    and ref["slot"] == side
                    and ref["sgf_sha256"] == sgf_sha256
                    and record.source_path == f"data/kifu-album/{ref['source_key']}/{ref['source_item_id']}.sgf"
                    and snapshot["raw_rank"] == (raw or parsed.display_rank or "")
                ):
                    rendered = display_rank_for_game_slot(snapshot, parsed.display_rank)
            except (ValueError, TypeError, KeyError, AttributeError):
                pass
        values.update(
            {
                f"display_{side}_rank": rendered["rank"],
                f"{side}_rank_origin": rendered["rank_origin"],
                f"{side}_rank_source": rendered["rank_source"],
            }
        )
    return values
