"""REST API endpoints for the live broadcasting module."""

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from katrain.web.live.models import MatchStatus
from katrain.web.live.translator import get_translator
from katrain.web.api.v1.endpoints.auth import get_current_user, get_current_user_optional
from katrain.web.models import User

router = APIRouter()


class MatchSummary(BaseModel):
    """Summary response for match listing."""
    id: str
    source: str
    tournament: str
    round_name: Optional[str]
    date: str
    player_black: str
    player_white: str
    black_rank: Optional[str]
    white_rank: Optional[str]
    status: str
    result: Optional[str]
    move_count: int
    current_winrate: float
    current_score: float
    last_updated: str
    # Game rules
    board_size: int = 19
    komi: float = 7.5
    rules: str = "chinese"


class MatchDetail(MatchSummary):
    """Detailed match response."""
    sgf: Optional[str]
    moves: list[str]


class MatchListResponse(BaseModel):
    """Response for match list endpoint."""
    matches: list[MatchSummary]
    total: int
    live_count: int


class UpcomingMatchResponse(BaseModel):
    """Response for upcoming match."""
    id: str
    tournament: str
    round_name: Optional[str]
    scheduled_time: str
    player_black: Optional[str]
    player_white: Optional[str]
    source_url: Optional[str]


class UpcomingListResponse(BaseModel):
    """Response for upcoming matches list."""
    matches: list[UpcomingMatchResponse]


class CacheStatsResponse(BaseModel):
    """Response for cache statistics."""
    live_count: int
    finished_count: int
    upcoming_count: int
    featured_id: Optional[str]
    last_list_update: Optional[str]
    last_cleanup: Optional[str]


class CommentResponse(BaseModel):
    """Response for a single comment."""
    id: int
    match_id: str
    user_id: int
    username: str
    content: str
    created_at: str


class CommentListResponse(BaseModel):
    """Response for comment list."""
    comments: list[CommentResponse]
    total: int


class CreateCommentRequest(BaseModel):
    """Request to create a comment."""
    content: str


class LiveTranslationsResponse(BaseModel):
    """Response for live translations."""
    lang: str
    players: dict[str, str]
    tournaments: dict[str, str]
    rounds: dict[str, str]
    rules: dict[str, str]


class PlayerTranslationResponse(BaseModel):
    """Response for a single player translation."""
    original: str
    translated: str
    lang: str
    info: Optional[dict] = None


def get_live_service(request: Request):
    """Dependency to get the live service from app state."""
    live_service = getattr(request.app.state, "live_service", None)
    if not live_service:
        raise HTTPException(status_code=503, detail="Live service not initialized")
    return live_service


@router.get("/matches", response_model=MatchListResponse)
async def get_matches(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status: live, finished"),
    source: Optional[str] = Query(None, description="Filter by source: xingzhen, weiqi_org"),
    lang: Optional[str] = Query(None, description="Target language for translations: en, jp, ko, cn, tw"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of matches to return"),
    live_service=Depends(get_live_service),
):
    """Get list of matches (live and recent finished).

    Returns matches sorted with live matches first, then finished by date.
    Optionally translates player and tournament names to the specified language.
    """
    cache = live_service.cache
    translator = get_translator() if lang else None

    if status == "live":
        matches = await cache.get_live_matches()
    elif status == "finished":
        matches = await cache.get_finished_matches(limit=limit)
    else:
        matches = await cache.get_all_matches(limit=limit)

    # Filter by source if specified
    if source:
        matches = [m for m in matches if m.source.value == source]

    # Convert to response format
    summaries = []
    for m in matches[:limit]:
        # Apply translations if language specified
        player_black = m.player_black
        player_white = m.player_white
        tournament = m.tournament
        round_name = m.round_name

        if translator and lang:
            player_black = translator.translate_player(m.player_black, lang)
            player_white = translator.translate_player(m.player_white, lang)
            tournament = translator.translate_tournament(m.tournament, lang)
            if m.round_name:
                round_name = translator.translate_round(m.round_name, lang)

        summaries.append(MatchSummary(
            id=m.id,
            source=m.source.value,
            tournament=tournament,
            round_name=round_name,
            date=m.date.isoformat(),
            player_black=player_black,
            player_white=player_white,
            black_rank=m.black_rank,
            white_rank=m.white_rank,
            status=m.status.value,
            result=m.result,
            move_count=m.move_count,
            current_winrate=m.current_winrate,
            current_score=m.current_score,
            last_updated=m.last_updated.isoformat(),
            board_size=getattr(m, 'board_size', 19) or 19,
            komi=getattr(m, 'komi', 7.5) or 7.5,
            rules=getattr(m, 'rules', 'chinese') or 'chinese',
        ))

    live_matches = await cache.get_live_matches()
    return MatchListResponse(
        matches=summaries,
        total=len(summaries),
        live_count=len(live_matches),
    )


@router.get("/matches/featured")
async def get_featured_match(
    request: Request,
    lang: Optional[str] = Query(None, description="Target language for translations: en, jp, ko, cn, tw"),
    live_service=Depends(get_live_service),
):
    """Get the current featured match (most important live match or latest finished).

    Optionally translates player and tournament names to the specified language.
    """
    cache = live_service.cache
    translator = get_translator() if lang else None
    match = await cache.get_featured_match()

    if not match:
        return {"match": None}

    # Apply translations if language specified
    player_black = match.player_black
    player_white = match.player_white
    tournament = match.tournament
    round_name = match.round_name

    if translator and lang:
        player_black = translator.translate_player(match.player_black, lang)
        player_white = translator.translate_player(match.player_white, lang)
        tournament = translator.translate_tournament(match.tournament, lang)
        if match.round_name:
            round_name = translator.translate_round(match.round_name, lang)

    return {
        "match": MatchSummary(
            id=match.id,
            source=match.source.value,
            tournament=tournament,
            round_name=round_name,
            date=match.date.isoformat(),
            player_black=player_black,
            player_white=player_white,
            black_rank=match.black_rank,
            white_rank=match.white_rank,
            status=match.status.value,
            result=match.result,
            move_count=match.move_count,
            current_winrate=match.current_winrate,
            current_score=match.current_score,
            last_updated=match.last_updated.isoformat(),
            board_size=getattr(match, 'board_size', 19) or 19,
            komi=getattr(match, 'komi', 7.5) or 7.5,
            rules=getattr(match, 'rules', 'chinese') or 'chinese',
        )
    }


@router.get("/matches/{match_id}", response_model=MatchDetail)
async def get_match(
    match_id: str,
    request: Request,
    fetch_detail: bool = Query(False, description="Fetch latest data from source"),
    live_service=Depends(get_live_service),
):
    """Get detailed information for a specific match.

    Set fetch_detail=true to fetch the latest data from the source API.
    """
    if fetch_detail:
        match = await live_service.poller.fetch_match_detail(match_id)
    else:
        match = await live_service.cache.get_match(match_id)

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    return MatchDetail(
        id=match.id,
        source=match.source.value,
        tournament=match.tournament,
        round_name=match.round_name,
        date=match.date.isoformat(),
        player_black=match.player_black,
        player_white=match.player_white,
        black_rank=match.black_rank,
        white_rank=match.white_rank,
        status=match.status.value,
        result=match.result,
        move_count=match.move_count,
        current_winrate=match.current_winrate,
        current_score=match.current_score,
        last_updated=match.last_updated.isoformat(),
        sgf=match.sgf,
        moves=match.moves,
        board_size=getattr(match, 'board_size', 19) or 19,
        komi=getattr(match, 'komi', 7.5) or 7.5,
        rules=getattr(match, 'rules', 'chinese') or 'chinese',
    )


@router.get("/matches/{match_id}/analysis")
async def get_match_analysis(
    match_id: str,
    request: Request,
    move_number: Optional[int] = Query(None, description="Get analysis for specific move"),
    live_service=Depends(get_live_service),
):
    """Get KataGo analysis data for a match.

    Returns analysis for all moves, or a specific move if move_number is provided.
    Analysis data is retrieved from the database.
    """
    match = await live_service.cache.get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    # Get analysis from database via service
    analysis = await live_service.get_match_analysis(match_id)

    if move_number is not None:
        if move_number not in analysis:
            raise HTTPException(status_code=404, detail=f"Analysis for move {move_number} not found")
        return {"move_number": move_number, "analysis": analysis[move_number].model_dump()}

    return {
        "match_id": match_id,
        "analyzed_moves": list(analysis.keys()),
        "analysis": {k: v.model_dump() for k, v in analysis.items()},
    }


@router.get("/matches/{match_id}/analysis/preload")
async def preload_match_analysis(
    match_id: str,
    request: Request,
    live_service=Depends(get_live_service),
):
    """Preload analysis for a match when user enters the page.

    This retrieves all available analysis and boosts priority for pending analysis.
    Recommended to call when user navigates to the match detail page.
    """
    match = await live_service.cache.get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    # Preload analysis (also boosts priority for pending tasks)
    analysis = await live_service.preload_analysis(match_id)

    return {
        "match_id": match_id,
        "analyzed_moves": list(analysis.keys()),
        "total_moves": match.move_count,
        "analysis": {k: v.model_dump() for k, v in analysis.items()},
    }


@router.post("/matches/{match_id}/analyze")
async def request_match_analysis(
    match_id: str,
    request: Request,
    start_move: int = Query(0, ge=0, description="First move to analyze"),
    end_move: Optional[int] = Query(None, ge=0, description="Last move to analyze"),
    live_service=Depends(get_live_service),
):
    """Request KataGo analysis for a match.

    Queues analysis for the specified move range (or full game if not specified).
    Analysis runs in the background and results are available via GET /analysis.
    """
    match = await live_service.cache.get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    if not live_service.analyzer:
        raise HTTPException(status_code=503, detail="Analysis service not enabled")

    # Default end_move to current move count
    if end_move is None:
        end_move = match.move_count

    await live_service.request_analysis(match_id, (start_move, end_move))

    return {
        "status": "queued",
        "match_id": match_id,
        "start_move": start_move,
        "end_move": end_move,
        "queue_size": await live_service.analyzer.get_queue_size(),
    }


@router.get("/upcoming", response_model=UpcomingListResponse)
async def get_upcoming_matches(
    request: Request,
    lang: Optional[str] = Query(None, description="Target language for translations: en, jp, ko, cn, tw"),
    limit: int = Query(20, ge=1, le=100),
    live_service=Depends(get_live_service),
):
    """Get list of upcoming matches.

    Optionally translates player and tournament names to the specified language.
    """
    cache = live_service.cache
    translator = get_translator() if lang else None
    upcoming = await cache.get_upcoming()

    matches = []
    for m in upcoming[:limit]:
        # Apply translations if language specified
        tournament = m.tournament
        round_name = m.round_name
        player_black = m.player_black
        player_white = m.player_white

        if translator and lang:
            tournament = translator.translate_tournament(m.tournament, lang)
            if m.round_name:
                round_name = translator.translate_round(m.round_name, lang)
            if m.player_black:
                player_black = translator.translate_player(m.player_black, lang)
            if m.player_white:
                player_white = translator.translate_player(m.player_white, lang)

        matches.append(UpcomingMatchResponse(
            id=m.id,
            tournament=tournament,
            round_name=round_name,
            scheduled_time=m.scheduled_time.isoformat(),
            player_black=player_black,
            player_white=player_white,
            source_url=m.source_url,
        ))

    return UpcomingListResponse(matches=matches)


@router.get("/stats", response_model=CacheStatsResponse)
async def get_live_stats(
    request: Request,
    live_service=Depends(get_live_service),
):
    """Get live service statistics."""
    stats = await live_service.cache.get_stats()
    return CacheStatsResponse(**stats)


@router.post("/refresh")
async def refresh_matches(
    request: Request,
    live_service=Depends(get_live_service),
):
    """Force refresh match data from all sources.

    This is an admin endpoint that should be rate-limited in production.
    """
    await live_service.poller.force_refresh()
    stats = await live_service.cache.get_stats()
    return {"status": "ok", "stats": stats}


@router.get("/analysis/stats")
async def get_analysis_stats(
    request: Request,
    live_service=Depends(get_live_service),
):
    """Get analysis queue statistics.

    Returns counts by status: pending, running, success, failed.
    """
    from katrain.web.core.db import SessionLocal
    from katrain.web.live.analysis_repo import LiveAnalysisRepo

    with SessionLocal() as db:
        repo = LiveAnalysisRepo(db)
        stats = repo.get_analysis_stats()

    return {
        "stats": stats,
        "total": sum(stats.values()),
    }


@router.post("/cleanup")
async def cleanup_stale_data(
    request: Request,
    delete_invalid: bool = Query(False, description="Delete invalid matches (empty ID or missing players)"),
    live_service=Depends(get_live_service),
):
    """Clean up stale data from the database.

    This is an admin endpoint that:
    - Removes failed analyses for matches without moves data
    - Optionally deletes invalid matches (e.g., 'xingzhen_' with empty source_id)
    """
    from katrain.web.core.db import SessionLocal
    from katrain.web.live.analysis_repo import LiveAnalysisRepo
    from katrain.web.core.models_db import LiveMatchDB

    results = {}

    with SessionLocal() as db:
        repo = LiveAnalysisRepo(db)

        # Clean up failed analyses
        failed_deleted = repo.cleanup_failed_analyses()
        results["failed_analyses_deleted"] = failed_deleted

        if delete_invalid:
            # Find and delete invalid matches (empty source_id)
            invalid_matches = db.query(LiveMatchDB).filter(
                LiveMatchDB.source_id == ""
            ).all()

            deleted_matches = 0
            for match in invalid_matches:
                if repo.delete_invalid_match(match.match_id):
                    deleted_matches += 1

            results["invalid_matches_deleted"] = deleted_matches

    return {"status": "ok", "results": results}


@router.post("/matches/{match_id}/recover")
async def recover_match_moves(
    match_id: str,
    request: Request,
    live_service=Depends(get_live_service),
):
    """Recover moves data for a match and reset failed analyses.

    This is an admin endpoint that:
    1. Fetches the latest match detail from the source API
    2. Updates the database with the moves data
    3. Resets any failed analyses to pending so they can be retried

    Use this to fix matches that have empty moves[] in the database.
    """
    result = await live_service.recover_match_moves(match_id)

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return {"status": "ok", **result}


@router.get("/admin/stats")
async def get_admin_stats(
    request: Request,
    live_service=Depends(get_live_service),
):
    """Get comprehensive statistics for admin monitoring.

    Returns:
    - Analysis queue size and status counts
    - Number of matches without moves data
    - Cache statistics
    """
    analysis_stats = await live_service.get_analysis_stats()
    cache_stats = await live_service.cache.get_stats()

    return {
        "analysis": analysis_stats,
        "cache": cache_stats,
    }


@router.post("/admin/recover-all")
async def recover_all_matches(
    request: Request,
    live_service=Depends(get_live_service),
):
    """Recover moves for all matches that have empty moves in the database.

    This is an admin endpoint that triggers the recovery process for all
    matches without moves data. It runs asynchronously - use GET /admin/stats
    to monitor progress.
    """
    from katrain.web.core.db import SessionLocal
    from katrain.web.live.analysis_repo import LiveAnalysisRepo

    with SessionLocal() as db:
        repo = LiveAnalysisRepo(db)
        matches_without_moves = repo.get_matches_without_moves()
        count = len(matches_without_moves)

    if count == 0:
        return {"status": "ok", "message": "No matches need recovery"}

    # Trigger recovery in background (don't await)
    import asyncio
    asyncio.create_task(live_service._recover_matches_without_moves())

    return {
        "status": "started",
        "matches_to_recover": count,
        "message": f"Recovery started for {count} matches. Use GET /admin/stats to monitor progress.",
    }


# ==================== Translation Endpoints ====================


@router.get("/translations", response_model=LiveTranslationsResponse)
async def get_live_translations(
    lang: str = Query("en", description="Target language code (en, cn, tw, jp, ko)"),
):
    """Get all live-specific translations for frontend caching.

    Returns player names, tournament names, round names, and rules
    translated to the specified language.
    """
    translator = get_translator()
    translations = translator.get_all_translations(lang)

    return LiveTranslationsResponse(
        lang=lang,
        players={k: v for k, v in translations["players"].items() if v is not None},
        tournaments={k: v for k, v in translations["tournaments"].items() if v is not None},
        rounds={k: v for k, v in translations["rounds"].items() if v is not None},
        rules={k: v for k, v in translations["rules"].items() if v is not None},
    )


@router.get("/translate/player", response_model=PlayerTranslationResponse)
async def translate_player_name(
    name: str = Query(..., description="Player name to translate"),
    lang: str = Query("en", description="Target language code"),
):
    """Translate a single player name.

    Useful for debugging and testing translations.
    Returns the translated name and full player info if available.
    """
    translator = get_translator()
    translated = translator.translate_player(name, lang)
    info = translator.get_player_info(name)

    return PlayerTranslationResponse(
        original=name,
        translated=translated,
        lang=lang,
        info=info,
    )


@router.get("/translate/tournament")
async def translate_tournament_name(
    name: str = Query(..., description="Tournament name to translate"),
    lang: str = Query("en", description="Target language code"),
):
    """Translate a tournament name.

    Useful for debugging and testing translations.
    """
    translator = get_translator()
    translated = translator.translate_tournament(name, lang)

    return {
        "original": name,
        "translated": translated,
        "lang": lang,
    }


@router.get("/translate/round")
async def translate_round_name(
    name: str = Query(..., description="Round name to translate"),
    lang: str = Query("en", description="Target language code"),
):
    """Translate a round name (Final, Semi-final, etc.).

    Useful for debugging and testing translations.
    """
    translator = get_translator()
    translated = translator.translate_round(name, lang)

    return {
        "original": name,
        "translated": translated,
        "lang": lang,
    }


# ==================== Comment Endpoints ====================


@router.get("/matches/{match_id}/comments", response_model=CommentListResponse)
async def get_comments(
    match_id: str,
    request: Request,
    limit: int = Query(50, ge=1, le=200, description="Maximum number of comments"),
    offset: int = Query(0, ge=0, description="Number of comments to skip"),
    live_service=Depends(get_live_service),
):
    """Get comments for a match.

    Returns comments ordered by creation time (oldest first).
    """
    from katrain.web.core.db import SessionLocal
    from katrain.web.live.comment_repo import LiveCommentRepo

    # Verify match exists
    match = await live_service.cache.get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    with SessionLocal() as db:
        repo = LiveCommentRepo(db)
        comments = repo.get_comments(match_id, limit=limit, offset=offset)
        total = repo.get_comment_count(match_id)

        # Build response with username
        comment_responses = []
        for c in comments:
            comment_responses.append(CommentResponse(
                id=c.id,
                match_id=c.match_id,
                user_id=c.user_id,
                username=c.user.username if c.user else "Unknown",
                content=c.content,
                created_at=c.created_at.isoformat() if c.created_at else "",
            ))

    return CommentListResponse(comments=comment_responses, total=total)


@router.post("/matches/{match_id}/comments", response_model=CommentResponse)
async def create_comment(
    match_id: str,
    request: Request,
    comment_data: CreateCommentRequest,
    current_user: User = Depends(get_current_user),
    live_service=Depends(get_live_service),
):
    """Create a new comment on a match.

    Requires authentication. Only works for live matches.
    """
    from katrain.web.core.db import SessionLocal
    from katrain.web.live.comment_repo import LiveCommentRepo

    # Verify match exists
    match = await live_service.cache.get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    # Only allow comments on live matches
    if match.status.value != "live":
        raise HTTPException(status_code=400, detail="Comments are only allowed on live matches")

    # Validate content
    content = comment_data.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Comment content cannot be empty")
    if len(content) > 500:
        raise HTTPException(status_code=400, detail="Comment content too long (max 500 characters)")

    with SessionLocal() as db:
        repo = LiveCommentRepo(db)
        comment = repo.create_comment(
            match_id=match_id,
            user_id=current_user.id,
            content=content,
        )

        return CommentResponse(
            id=comment.id,
            match_id=comment.match_id,
            user_id=comment.user_id,
            username=current_user.username,
            content=comment.content,
            created_at=comment.created_at.isoformat() if comment.created_at else "",
        )


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Delete a comment.

    Only the comment owner can delete their own comments.
    """
    from katrain.web.core.db import SessionLocal
    from katrain.web.live.comment_repo import LiveCommentRepo

    with SessionLocal() as db:
        repo = LiveCommentRepo(db)
        success = repo.delete_comment(comment_id, current_user.id)

        if not success:
            raise HTTPException(
                status_code=404,
                detail="Comment not found or you don't have permission to delete it"
            )

    return {"status": "ok", "message": "Comment deleted"}


@router.get("/matches/{match_id}/comments/poll")
async def poll_comments(
    match_id: str,
    request: Request,
    since_id: int = Query(0, ge=0, description="Only return comments with ID greater than this"),
    live_service=Depends(get_live_service),
):
    """Poll for new comments since a given ID.

    Use this for live updates - pass the ID of the last received comment.
    """
    from katrain.web.core.db import SessionLocal
    from katrain.web.live.comment_repo import LiveCommentRepo

    # Verify match exists
    match = await live_service.cache.get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    with SessionLocal() as db:
        repo = LiveCommentRepo(db)
        comments = repo.get_recent_comments(match_id, since_id=since_id)

        comment_responses = []
        for c in comments:
            comment_responses.append(CommentResponse(
                id=c.id,
                match_id=c.match_id,
                user_id=c.user_id,
                username=c.user.username if c.user else "Unknown",
                content=c.content,
                created_at=c.created_at.isoformat() if c.created_at else "",
            ))

    return {"comments": comment_responses, "count": len(comment_responses)}


# ============== Translation Learning API ==============


class TranslationRequest(BaseModel):
    """Request body for learning a translation."""
    name: str
    name_type: str  # "player" or "tournament"
    translations: dict  # {"en": "...", "jp": "...", etc.}
    country: Optional[str] = None  # For players: CN, JP, KR, TW
    source: str = "manual"


class MissingTranslationsResponse(BaseModel):
    """Response for missing translations query."""
    missing_players: list[str]
    missing_tournaments: list[str]


@router.post("/translations/learn")
async def learn_translation(
    request: TranslationRequest,
    user: User = Depends(get_current_user),
):
    """Store a new translation in the database.

    Requires authentication. Used to manually add or correct translations.
    """
    translator = get_translator()

    if request.name_type == "player":
        success = translator.store_player(
            name=request.name,
            translations=request.translations,
            country=request.country,
            source=request.source,
        )
    elif request.name_type == "tournament":
        success = translator.store_tournament(
            name=request.name,
            translations=request.translations,
            source=request.source,
        )
    else:
        raise HTTPException(status_code=400, detail="name_type must be 'player' or 'tournament'")

    if not success:
        raise HTTPException(status_code=500, detail="Failed to store translation")

    return {"status": "ok", "name": request.name, "type": request.name_type}


@router.get("/translations/missing", response_model=MissingTranslationsResponse)
async def get_missing_translations(
    lang: str = Query("en", description="Target language to check"),
    live_service=Depends(get_live_service),
):
    """Get list of names that don't have translations yet.

    Useful for bulk translation work - returns all player and tournament
    names from current/recent matches that lack translations.
    """
    translator = get_translator()

    # Get all unique names from current matches
    all_players = set()
    all_tournaments = set()

    # From live/finished matches
    matches = await live_service.cache.get_all_matches()
    for match in matches:
        all_players.add(match.player_black)
        all_players.add(match.player_white)
        all_tournaments.add(match.tournament)

    # From upcoming matches
    upcoming = await live_service.cache.get_upcoming()
    for match in upcoming:
        all_tournaments.add(match.tournament)
        if match.player_black:
            all_players.add(match.player_black)
        if match.player_white:
            all_players.add(match.player_white)

    # Find missing translations
    missing_players = translator.get_missing_translations(list(all_players), "player", lang)
    missing_tournaments = translator.get_missing_translations(list(all_tournaments), "tournament", lang)

    return MissingTranslationsResponse(
        missing_players=sorted(missing_players),
        missing_tournaments=sorted(missing_tournaments),
    )
