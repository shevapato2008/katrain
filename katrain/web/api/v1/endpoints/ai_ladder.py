"""Authenticated status and server-authoritative start API for ranked AI play."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.core import models_db
from katrain.web.core.ai_ladder_catalog import (
    AiLadderSessionSnapshot,
    build_opponent_snapshot,
    catalog_entry,
    catalog_projection,
)
from katrain.web.core.ai_ladder_ranked import AI_LADDER_GAME_TYPE, PLACEMENT_GAMES, initial_placement_window
from katrain.web.models import User

router = APIRouter()


class AiLadderStartRequest(BaseModel):
    """Game preferences only. Strength, result, and configuration are server-owned."""

    model_config = ConfigDict(extra="forbid")

    board_size: Literal[9, 13, 19] = 19
    rules: str = Field(default="chinese", min_length=1, max_length=64)
    komi: float = 7.5
    handicap: int = Field(default=0, ge=0, le=9)
    color: Literal["black", "white"] = "black"
    time_enabled: bool = False
    main_time: int = Field(default=0, ge=0, le=86400)
    byo_length: int = Field(default=30, ge=0, le=3600)
    byo_periods: int = Field(default=3, ge=0, le=100)


def _require_authority(request: Request) -> None:
    if not getattr(request.app.state, "ai_ladder_authoritative", False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ranked AI ladder authority is unavailable on this node",
        )


def _pending_settlement(request: Request, user_id: int) -> bool:
    manager = request.app.state.session_manager
    lock = getattr(manager, "_lock", None)
    if lock is None:
        sessions = list(getattr(manager, "_sessions", {}).values())
    else:
        with lock:
            sessions = list(manager._sessions.values())
    in_memory_pending = any(
        getattr(session, "user_id", None) == user_id
        and getattr(session, "game_type", None) == AI_LADDER_GAME_TYPE
        and bool(getattr(session, "ai_ladder_settlement_pending", False))
        for session in sessions
    )
    if in_memory_pending:
        return True

    repo = request.app.state.ai_ladder_repo
    db = repo.session_factory()
    try:
        return (
            db.query(models_db.UserGame.id)
            .outerjoin(
                models_db.AiLadderGameLedger,
                models_db.AiLadderGameLedger.game_id == models_db.UserGame.id,
            )
            .filter(
                models_db.UserGame.user_id == user_id,
                models_db.UserGame.game_type == AI_LADDER_GAME_TYPE,
                models_db.AiLadderGameLedger.id.is_(None),
            )
            .first()
            is not None
        )
    finally:
        db.close()


def _status_payload(request: Request, current_user: User) -> dict[str, object]:
    repo = request.app.state.ai_ladder_repo
    db = repo.session_factory()
    try:
        profile = db.get(models_db.AiLadderProfile, current_user.id)
        if profile is None:
            lo, hi = initial_placement_window(current_user.rank)
            completed = 0
            rung = None
            net_score = 0
        else:
            lo, hi = profile.placement_lo, profile.placement_hi
            completed = profile.placement_completed
            rung = profile.ai_ladder_rung
            net_score = profile.net_score
    finally:
        db.close()

    opponent_rung = rung if rung is not None else (lo + hi) // 2
    opponent = catalog_entry(opponent_rung)
    placement_state: dict[str, object]
    if rung is None:
        placement_state = {"phase": "placement", "completed_games": completed, "total_games": PLACEMENT_GAMES}
    else:
        placement_state = {"phase": "placed", "rung": opponent}

    return {
        "view_state": "ready",
        "placement_state": placement_state,
        "current_opponent": opponent,
        "recent_ranked_results": repo.recent_counted_results(current_user.id, limit=5),
        "net_score": net_score,
        "pending_settlement": _pending_settlement(request, current_user.id),
    }


@router.get("/catalog")
def get_catalog(current_user: User = Depends(get_current_user)):
    return catalog_projection()


@router.get("/status")
def get_status(request: Request, current_user: User = Depends(get_current_user)):
    _require_authority(request)
    return _status_payload(request, current_user)


@router.post("/start", status_code=status.HTTP_201_CREATED)
def start_ranked_game(
    body: AiLadderStartRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    _require_authority(request)
    status_payload = _status_payload(request, current_user)
    if status_payload["pending_settlement"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Previous ranked game settlement is pending")
    opponent_entry = status_payload["current_opponent"]
    assert isinstance(opponent_entry, dict)
    opponent_rung = opponent_entry["rung"]
    assert isinstance(opponent_rung, int)
    try:
        opponent, execution_identity = build_opponent_snapshot(opponent_rung)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    manager = request.app.state.session_manager
    try:
        session = manager.create_session(katago_uuid=current_user.uuid)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not create game session"
        ) from exc

    game_id = uuid.uuid4().hex
    user_color = "B" if body.color == "black" else "W"
    ai_color = "W" if user_color == "B" else "B"
    snapshot = AiLadderSessionSnapshot(
        game_id=game_id,
        session_id=session.session_id,
        user_id=current_user.id,
        user_color=user_color,
        game_type=AI_LADDER_GAME_TYPE,
        opponent=opponent,
        ai_subtype="ai:ladder",
        execution_identity=execution_identity,
    )

    try:
        with session.lock:
            session.user_id = current_user.id
            session.game_type = AI_LADDER_GAME_TYPE
            session.ai_ladder_snapshot = snapshot
            session.ai_ladder_runtime_identity = execution_identity
            session.ai_ladder_ai_subtype = "ai:ladder"
            session.ai_ladder_settlement_pending = False
            session._recorded = False
            session.katrain(
                "update_player",
                bw=user_color,
                player_type="player:human",
                player_subtype="player:human",
                name=current_user.username,
            )
            session.katrain(
                "update_player",
                bw=ai_color,
                player_type="player:ai",
                player_subtype="ai:ladder",
                name=opponent.rank_name,
            )
            if body.time_enabled:
                session.katrain.update_config("timer/main_time", body.main_time)
                session.katrain.update_config("timer/byo_length", body.byo_length)
                session.katrain.update_config("timer/byo_periods", body.byo_periods)
                session.katrain.update_config("timer/paused", False)
            else:
                session.katrain.update_config("timer/main_time", 0)
                session.katrain.update_config("timer/byo_length", 0)
                session.katrain.update_config("timer/paused", True)
            session.katrain(
                "new_game",
                size=body.board_size,
                handicap=body.handicap,
                komi=body.komi,
                rules=body.rules,
                game_type=AI_LADDER_GAME_TYPE,
                ladder_rung=opponent.rung,
            )
            session.katrain.game_type = AI_LADDER_GAME_TYPE
            session.last_state = session.katrain.get_state()
    except Exception as exc:
        try:
            manager.remove_session(session.session_id)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not configure ranked game"
        ) from exc

    return {
        "session_id": session.session_id,
        "game_id": game_id,
        "opponent": catalog_entry(opponent.rung),
        "status": status_payload,
    }
