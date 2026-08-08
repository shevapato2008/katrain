"""Authenticated status and server-authoritative start API for ranked AI play."""

from __future__ import annotations

import uuid
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.core import models_db
from katrain.web.core.ai_ladder_catalog import (
    AiLadderSessionSnapshot,
    build_opponent_snapshot,
    catalog_entry,
    catalog_projection,
    frozen_recipe_from_snapshot,
    result_for_user,
    session_snapshot_from_pending,
)
from katrain.web.core.ai_ladder_ranked import (
    AI_LADDER_GAME_TYPE,
    PLACEMENT_GAMES,
    AiLadderBlockingGame,
    AiLadderLifecycleConflict,
    AiLadderLifecycleNotFound,
    AiLadderLifecycleReceipt,
    AiLadderOpponentSnapshot,
    InvalidReservationKey,
    initial_placement_window,
)
from katrain.web.models import User

router = APIRouter()


#: The board every rung was measured on. Fixed here rather than taken from the
#: request, for the same reason the rung is: a rung's rank name describes its
#: strength in a 19x19 Chinese-rules 7.5-komi even game and nothing else (every
#: calibration campaign ran exactly that -- see
#: superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py), so a
#: client that could ask for 9x9, or for 6.5 komi, would be seating an opponent
#: whose measured strength no longer describes the game being played -- and then
#: banking the result. The player still chooses their seat and their clock.
LADDER_BOARD_SIZE = 19
LADDER_RULES = "chinese"
LADDER_KOMI = 7.5
LADDER_HANDICAP = 0


class AiLadderStartRequest(BaseModel):
    """Seat and clock only. Strength, board conditions, result and configuration
    are all server-owned; `extra="forbid"` means a client that still sends
    board_size/rules/komi/handicap is told so rather than silently ignored."""

    model_config = ConfigDict(extra="forbid")

    color: Literal["black", "white"] = "black"
    time_enabled: bool = False
    main_time: int = Field(default=0, ge=0, le=86400)
    byo_length: int = Field(default=30, ge=0, le=3600)
    byo_periods: int = Field(default=3, ge=0, le=100)


class AiLadderReserveRequest(AiLadderStartRequest):
    game_id: str = Field(min_length=1, max_length=32)


class AiLadderReservationKeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservation_key: str = Field(min_length=1, max_length=128)


class AiLadderActivateRequest(AiLadderReservationKeyRequest):
    session_id: str = Field(min_length=1, max_length=128)


class AiLadderEndRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Literal["user_resigned"]


def _require_authority(request: Request) -> None:
    if not getattr(request.app.state, "ai_ladder_authoritative", False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ranked AI ladder authority is unavailable on this node",
        )


def _pending_settlement(request: Request, user_id: int) -> bool:
    lifecycle = request.app.state.ai_ladder_repo.get_blocking_game(user_id)
    if lifecycle is not None:
        return lifecycle.state == "pending_settlement"
    return request.app.state.ai_ladder_repo.get_pending_game(user_id) is not None


def _device_id(request: Request, *, required: bool = True) -> str:
    value = request.headers.get("X-StellaBox-Device-ID")
    normalized = value.strip() if isinstance(value, str) else ""
    if len(normalized) > 64 or (required and not normalized):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="X-StellaBox-Device-ID must be a non-empty label of at most 64 characters",
        )
    return normalized or "cloud-local"


def _blocking_payload(request: Request, game: AiLadderBlockingGame, device_id: str) -> dict[str, object]:
    payload: dict[str, object] = {
        "game_id": game.game_id,
        # A reservation already occupies the account and therefore has the same
        # product meaning as an active game, even before its board session is bound.
        "state": "pending_settlement" if game.state == "pending_settlement" else "active",
        "ownership": "current_device" if game.origin_device_id == device_id else "other_device",
        "user_color": game.user_color,
        "opponent_rank_name": game.opponent.rank_name,
    }
    if (
        game.state == "active"
        and game.origin_device_id == device_id
        and game.origin_session_id
        and _active_session(request, game.origin_session_id)
    ):
        payload["session_id"] = game.origin_session_id
    return payload


def _lifecycle_payload(receipt: AiLadderLifecycleReceipt) -> dict[str, object]:
    return {
        "state": "settled",
        "game_id": receipt.game_id,
        "receipt": {"counted": receipt.counted, "reason": receipt.reason},
    }


def _lifecycle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AiLadderLifecycleNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ranked game not found")
    if isinstance(exc, (AiLadderLifecycleConflict, InvalidReservationKey)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


def _active_session(request: Request, session_id: str) -> bool:
    manager = request.app.state.session_manager
    lock = getattr(manager, "_lock", None)
    if lock is None:
        session = getattr(manager, "_sessions", {}).get(session_id)
    else:
        with lock:
            session = manager._sessions.get(session_id)
    return session is not None


def _recover_pending(request: Request, user_id: int) -> None:
    repo = request.app.state.ai_ladder_repo
    pending = repo.get_pending_game(user_id)
    if pending is None:
        return
    lifecycle = repo.get_blocking_game(user_id)
    try:
        game = request.app.state.user_game_repo.get_authoritative_ai_ladder_ranked(pending["game_id"], user_id)
        if lifecycle is not None:
            # Account occupancy is cloud-authoritative. Never abandon it merely
            # because this process lost its session. A fully saved origin result may
            # still complete the same credentialed terminal transaction after restart.
            if game is None or not pending.get("reservation_key"):
                return
            snapshot = session_snapshot_from_pending(pending)
            repo.mark_pending_game_saved(user_id=user_id, game_id=snapshot.game_id, result=game["result"])
            repo.finalize_reserved_game(
                user_id=user_id,
                game_id=snapshot.game_id,
                terminal_source="recovery",
                result=result_for_user(game["result"], snapshot.user_color),
                deciding_device_id=lifecycle.origin_device_id,
                reservation_key=pending["reservation_key"],
                game_record=game,
            )
            repo.clear_pending_game(user_id=user_id, game_id=snapshot.game_id)
            return
        if game is None:
            if not _active_session(request, pending["session_id"]):
                repo.clear_pending_game(user_id=user_id, game_id=pending["game_id"])
            return
        snapshot = session_snapshot_from_pending(pending)
        repo.mark_pending_game_saved(user_id=user_id, game_id=snapshot.game_id, result=game["result"])
        repo.settle_game(
            user_id=user_id,
            game_id=snapshot.game_id,
            user_color=snapshot.user_color,
            result=result_for_user(game["result"], snapshot.user_color),
            game_type=snapshot.game_type,
            opponent=snapshot.opponent,
        )
        repo.clear_pending_game(user_id=user_id, game_id=snapshot.game_id)
    except Exception as exc:
        logging.getLogger("katrain_web").error("Failed to recover ranked AI settlement: %s", exc)


def _status_payload(request: Request, current_user: User, *, device_id: Optional[str] = None) -> dict[str, object]:
    _recover_pending(request, current_user.id)
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
    current_opponent = dict(opponent)
    if opponent["certification_status"] == "certified" and opponent["availability"] == "available":
        current_opponent["counting_eligibility"] = "eligible"
    else:
        current_opponent["counting_eligibility"] = "ineligible"
        current_opponent["counting_reason"] = "opponent_not_eligible"
    placement_state: dict[str, object]
    if rung is None:
        placement_state = {"phase": "placement", "completed_games": completed, "total_games": PLACEMENT_GAMES}
    else:
        placement_state = {"phase": "placed", "rung": opponent}

    from katrain.core import ladder

    blocking = repo.get_blocking_game(current_user.id)
    return {
        "view_state": "ready",
        "placement_state": placement_state,
        "current_opponent": current_opponent,
        "recent_ranked_results": repo.recent_counted_results(current_user.id, limit=5),
        "net_score": net_score,
        "pending_settlement": _pending_settlement(request, current_user.id),
        "blocking_game": _blocking_payload(request, blocking, device_id or "cloud-local") if blocking else None,
        # Whether THIS node will seat an uncertified rung. The rung's own
        # certification_status/availability keep telling the truth about the rung; this
        # says what the server will do about it, so the client can stop guessing why a
        # start request would be refused (or, here, accepted).
        "provisional_play_allowed": ladder.provisional_play_allowed(),
    }


@router.get("/catalog")
def get_catalog(current_user: User = Depends(get_current_user)):
    return catalog_projection()


@router.get("/status")
def get_status(request: Request, current_user: User = Depends(get_current_user)):
    _require_authority(request)
    return _status_payload(request, current_user, device_id=_device_id(request, required=False))


def _reserve(
    *, body: AiLadderReserveRequest, request: Request, current_user: User, device_id: str
):
    status_payload = _status_payload(request, current_user, device_id=device_id)
    opponent_entry = status_payload["current_opponent"]
    assert isinstance(opponent_entry, dict)
    try:
        opponent, execution_identity = build_opponent_snapshot(int(opponent_entry["rung"]))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    try:
        return request.app.state.ai_ladder_repo.reserve_game(
            user_id=current_user.id,
            game_id=body.game_id,
            user_color="B" if body.color == "black" else "W",
            opponent=opponent,
            origin_device_id=device_id,
            ai_subtype="ai:ladder",
            execution_identity=execution_identity,
            rules_snapshot={
                "board_size": LADDER_BOARD_SIZE,
                "rules": LADDER_RULES,
                "komi": LADDER_KOMI,
                "handicap": LADDER_HANDICAP,
            },
            time_control_snapshot={
                "time_enabled": body.time_enabled,
                "main_time": body.main_time,
                "byo_length": body.byo_length,
                "byo_periods": body.byo_periods,
            },
        )
    except (ValueError, AiLadderLifecycleConflict) as exc:
        raise _lifecycle_error(exc) from exc


@router.post("/games/reserve", status_code=status.HTTP_201_CREATED)
def reserve_ranked_game(
    body: AiLadderReserveRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    _require_authority(request)
    device_id = _device_id(request)
    try:
        reserved = _reserve(body=body, request=request, current_user=current_user, device_id=device_id)
    except HTTPException as exc:
        blocking = request.app.state.ai_ladder_repo.get_blocking_game(current_user.id)
        if exc.status_code == status.HTTP_409_CONFLICT and blocking is not None:
            exc.detail = {"message": str(exc.detail), "blocking_game": _blocking_payload(request, blocking, device_id)}
        raise
    if not reserved.created or reserved.reservation_key is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Reservation already exists; its credential cannot be replayed",
                "blocking_game": _blocking_payload(request, reserved.game, device_id),
            },
        )
    return {
        "game_id": reserved.game.game_id,
        "reservation_key": reserved.reservation_key,
        "blocking_game": _blocking_payload(request, reserved.game, device_id),
    }


@router.post("/games/{game_id}/activate")
def activate_ranked_game(
    game_id: str,
    body: AiLadderActivateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    _require_authority(request)
    try:
        game = request.app.state.ai_ladder_repo.activate_reservation(
            user_id=current_user.id,
            game_id=game_id,
            reservation_key=body.reservation_key,
            origin_device_id=_device_id(request),
            origin_session_id=body.session_id,
        )
    except ValueError as exc:
        raise _lifecycle_error(exc) from exc
    return {"state": "active", "game_id": game.game_id}


@router.post("/games/{game_id}/pending-settlement")
def mark_ranked_game_pending(
    game_id: str,
    body: AiLadderReservationKeyRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    _require_authority(request)
    try:
        game = request.app.state.ai_ladder_repo.mark_pending_settlement(
            user_id=current_user.id,
            game_id=game_id,
            reservation_key=body.reservation_key,
            origin_device_id=_device_id(request),
        )
    except ValueError as exc:
        raise _lifecycle_error(exc) from exc
    return {"state": "pending_settlement", "game_id": game.game_id}


@router.delete("/games/{game_id}/reservation")
def cancel_ranked_game_reservation(
    game_id: str,
    body: AiLadderReservationKeyRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    _require_authority(request)
    try:
        result = request.app.state.ai_ladder_repo.cancel_reservation(
            user_id=current_user.id,
            game_id=game_id,
            reservation_key=body.reservation_key,
            origin_device_id=_device_id(request),
        )
    except ValueError as exc:
        raise _lifecycle_error(exc) from exc
    if result.receipt is not None:
        return _lifecycle_payload(result.receipt)
    return {"state": "cancelled", "game_id": game_id}


@router.get("/games/{game_id}/status")
def get_ranked_game_status(
    game_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    _require_authority(request)
    lifecycle = request.app.state.ai_ladder_repo.get_game_lifecycle(user_id=current_user.id, game_id=game_id)
    if lifecycle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ranked game not found")
    if isinstance(lifecycle, AiLadderLifecycleReceipt):
        return _lifecycle_payload(lifecycle)
    return {
        "state": "pending_settlement" if lifecycle.state == "pending_settlement" else "active",
        "game_id": lifecycle.game_id,
    }


@router.post("/games/{game_id}/end")
def end_ranked_game(
    game_id: str,
    body: AiLadderEndRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    _require_authority(request)
    try:
        receipt = request.app.state.ai_ladder_repo.finalize_reserved_game(
            user_id=current_user.id,
            game_id=game_id,
            terminal_source="remote_resign",
            result="loss",
            deciding_device_id=_device_id(request, required=False),
        )
    except ValueError as exc:
        raise _lifecycle_error(exc) from exc
    return _lifecycle_payload(receipt)


@router.post("/start", status_code=status.HTTP_201_CREATED)
def start_ranked_game(
    body: AiLadderStartRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    _require_authority(request)
    device_id = _device_id(request, required=False)
    status_payload = _status_payload(request, current_user, device_id=device_id)
    if status_payload["pending_settlement"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Previous ranked game settlement is pending")
    game_id = uuid.uuid4().hex
    reservation = _reserve(
        body=AiLadderReserveRequest(game_id=game_id, **body.model_dump()),
        request=request,
        current_user=current_user,
        device_id=device_id,
    )
    assert reservation.reservation_key is not None
    reservation_key = reservation.reservation_key
    opponent = reservation.game.opponent
    execution_identity = reservation.game.execution_identity

    manager = request.app.state.session_manager
    activity = getattr(request.app.state, "ranked_analysis_activity", None)

    def analysis_is_active(session_id: str, kinds: dict[str, int]) -> bool:
        if any(kind.startswith(("quick-analysis", "platform:")) for kind in kinds):
            return True
        try:
            analysis_session = manager.get_session(session_id)
        except KeyError:
            return False
        if set(kinds) == {"continuous"}:
            return bool(getattr(analysis_session.katrain, "pondering", False))
        # One-shot and tree-wide analysis can outlive the initiating HTTP call and
        # may touch nodes other than current_node. Conservatively keep the lease
        # until the session is reset/deleted; this is safer than guessing completion.
        return True

    if activity is not None and not activity.reserve_ranked_start(current_user.id, analysis_is_active):
        request.app.state.ai_ladder_repo.cancel_reservation(
            user_id=current_user.id,
            game_id=game_id,
            reservation_key=reservation_key,
            origin_device_id=device_id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stop active analysis before starting a ranked AI game",
        )

    try:
        session = manager.create_session(
            katago_uuid=current_user.uuid,
            user_id=current_user.id,
            initial_game_type=AI_LADDER_GAME_TYPE,
            skip_initial_analysis=True,
        )
    except Exception as exc:
        if activity is not None:
            activity.release_ranked_start(current_user.id)
        request.app.state.ai_ladder_repo.cancel_reservation(
            user_id=current_user.id,
            game_id=game_id,
            reservation_key=reservation_key,
            origin_device_id=device_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not create game session"
        ) from exc

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
    frozen_recipe = frozen_recipe_from_snapshot(opponent)

    try:
        request.app.state.ai_ladder_repo.create_pending_game(snapshot, reservation_key=reservation_key)
        if activity is not None:
            activity.release_ranked_start(current_user.id)
        with session.lock:
            session.user_id = current_user.id
            session.game_type = AI_LADDER_GAME_TYPE
            session.ai_ladder_snapshot = snapshot
            session.ai_ladder_runtime_identity = execution_identity
            session.ai_ladder_ai_subtype = "ai:ladder"
            session.ai_ladder_settlement_pending = False
            session.ai_ladder_reservation_key = reservation_key
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
                size=LADDER_BOARD_SIZE,
                handicap=LADDER_HANDICAP,
                komi=LADDER_KOMI,
                rules=LADDER_RULES,
                game_type=AI_LADDER_GAME_TYPE,
                ladder_rung=opponent.rung,
                frozen_ladder_recipe=frozen_recipe,
                skip_initial_analysis=True,
            )
            session.katrain.game_type = AI_LADDER_GAME_TYPE
            session.last_state = session.katrain.get_state()
        request.app.state.ai_ladder_repo.activate_reservation(
            user_id=current_user.id,
            game_id=game_id,
            reservation_key=reservation_key,
            origin_device_id=device_id,
            origin_session_id=session.session_id,
        )
    except Exception as exc:
        if activity is not None:
            activity.release_ranked_start(current_user.id)
        try:
            request.app.state.ai_ladder_repo.clear_pending_game(user_id=current_user.id, game_id=game_id)
        except Exception:
            pass
        try:
            request.app.state.ai_ladder_repo.cancel_reservation(
                user_id=current_user.id,
                game_id=game_id,
                reservation_key=reservation_key,
                origin_device_id=device_id,
            )
        except Exception:
            pass
        try:
            manager.remove_session(session.session_id)
        except Exception:
            pass
        code = status.HTTP_409_CONFLICT if isinstance(exc, ValueError) else status.HTTP_503_SERVICE_UNAVAILABLE
        raise HTTPException(status_code=code, detail="Could not configure ranked game") from exc

    return {
        "session_id": session.session_id,
        "game_id": game_id,
        "opponent": catalog_entry(opponent.rung),
        "status": _status_payload(request, current_user, device_id=device_id),
    }


class AiLadderOpponentPayload(BaseModel):
    """The opponent exactly as the board froze it when the game started."""

    model_config = ConfigDict(extra="forbid")

    rung: int = Field(ge=1, le=41)
    rank_name: str = Field(min_length=1)
    config_snapshot: dict
    certification_status: str = Field(min_length=1)
    availability: str = Field(min_length=1)
    route: Literal["local", "server"]


class AiLadderGameRecordPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sgf_content: str = Field(min_length=1)
    result: str = Field(min_length=1)
    board_size: int
    rules: str = Field(min_length=1)
    komi: float
    move_count: int = Field(ge=0)
    player_black: str = Field(min_length=1)
    player_white: str = Field(min_length=1)
    source: Literal["play_ai"]
    category: Literal["game"]
    game_type: Literal["ai_ladder_ranked"]
    black_rank: Optional[str] = None
    white_rank: Optional[str] = None
    title: Optional[str] = None
    event: Optional[str] = None
    round_name: Optional[str] = None
    game_date: Optional[str] = None


class AiLadderSettlementSubmission(BaseModel):
    """One settled game, forwarded by the board that played it.

    The board is the authority for what happened at its own table (which game, which
    seat, which result, against which frozen rung). It is NOT the authority for the
    account's rank: this endpoint re-runs the same settlement against the cloud's own
    profile, so the cloud stays the single place ranks are decided across devices.
    """

    model_config = ConfigDict(extra="forbid")

    game_id: str = Field(min_length=1, max_length=64)
    user_color: Literal["B", "W"]
    result: Literal["win", "loss", "inconclusive"]
    game_type: str = Field(min_length=1)
    opponent: Optional[AiLadderOpponentPayload] = None
    engine_stalled: bool = False
    device_id: Optional[str] = Field(default=None, max_length=64)
    reservation_key: Optional[str] = Field(default=None, min_length=1, max_length=128)
    game_record: Optional[AiLadderGameRecordPayload] = None


@router.post("/settlements")
def submit_settlement(
    body: AiLadderSettlementSubmission,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Accept a settled ranked game from a board and apply it to the cloud profile.

    Idempotent by `game_id`: `settle_game` replays the first decision it recorded for a
    game rather than settling it twice, so a board that retries after a timeout (or
    after being unsure whether its POST landed) cannot move the rank twice.
    """
    _require_authority(request)
    opponent = None
    if body.opponent is not None:
        try:
            opponent = AiLadderOpponentSnapshot(**body.opponent.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    try:
        lifecycle = request.app.state.ai_ladder_repo.get_game_lifecycle(
            user_id=current_user.id, game_id=body.game_id
        )
        if isinstance(lifecycle, AiLadderBlockingGame):
            receipt = request.app.state.ai_ladder_repo.finalize_reserved_game(
                user_id=current_user.id,
                game_id=body.game_id,
                terminal_source="played_result",
                result=body.result,
                deciding_device_id=_device_id(request),
                reservation_key=body.reservation_key,
                game_record=body.game_record.model_dump() if body.game_record is not None else None,
                engine_stalled=body.engine_stalled,
            )
            outcome = receipt
        elif isinstance(lifecycle, AiLadderLifecycleReceipt):
            outcome = lifecycle
            receipt = lifecycle
        else:
            receipt = None
            outcome = request.app.state.ai_ladder_repo.settle_game(
                user_id=current_user.id,
                game_id=body.game_id,
                user_color=body.user_color,
                result=body.result,
                game_type=body.game_type,
                opponent=opponent,
                engine_stalled=body.engine_stalled,
            )
    except ValueError as exc:
        raise _lifecycle_error(exc) from exc

    logging.getLogger("katrain_web").info(
        "ai-ladder settlement from device %s: game=%s counted=%s reason=%s",
        body.device_id or "unknown",
        body.game_id,
        outcome.counted,
        outcome.reason,
    )
    response = {
        "game_id": body.game_id,
        "counted": outcome.counted,
        "replayed": outcome.replayed,
        "reason": outcome.reason,
        # The cloud's answer for this account, which is the one that counts across
        # devices. A board that disagrees is looking at a stale local profile.
        "profile": {
            "ai_ladder_rung": outcome.ai_ladder_rung,
            "placement_lo": outcome.placement_lo,
            "placement_hi": outcome.placement_hi,
            "placement_completed": outcome.placement_completed,
            "net_score": outcome.net_score,
        },
    }
    if receipt is not None:
        response["lifecycle"] = _lifecycle_payload(receipt)
    return response


@router.get("/settlements/{game_id}")
def get_settlement_receipt(
    game_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    _require_authority(request)
    lifecycle = request.app.state.ai_ladder_repo.get_game_lifecycle(user_id=current_user.id, game_id=game_id)
    if isinstance(lifecycle, AiLadderBlockingGame):
        return {"state": "pending"}
    receipt = request.app.state.ai_ladder_repo.get_settlement_receipt(
        user_id=current_user.id,
        game_id=game_id,
    )
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ranked game not found")
    return receipt
