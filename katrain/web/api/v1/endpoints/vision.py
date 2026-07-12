"""Vision REST API endpoints — thin proxies to VisionService."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


# -- Request models ----------------------------------------------------------


class BindRequest(BaseModel):
    session_id: str


class SetupModeRequest(BaseModel):
    target_board: list[list[int]]  # (board_size x board_size) matrix


class ResetSyncRequest(BaseModel):
    # "digital" = trust-digital recovery (kiosk 重置识别 / escalation restored): re-baseline
    # to the game, clear the stuck removal/pause. "physical" = accept the camera board as-is
    # (ambiguous-stone 忽略): keep the ignored stone in the detector baseline so it doesn't
    # re-fire.
    adopt: str = "digital"


# -- Helpers -----------------------------------------------------------------


def _get_vision(request: Request):
    """Get VisionService from app state, raise 404 if not enabled."""
    vision = getattr(request.app.state, "vision", None)
    if vision is None:
        raise HTTPException(status_code=404, detail="Vision service not enabled")
    return vision


def _drain_stale_move_queue(request: Request) -> None:
    """Review M1: app.state.vision_move_queue is the queue route_vision_event feeds
    ConfirmedMove events into; drain it on every bind/unbind so a move queued for
    the OLD session (or before any session was ever bound) can't cross into
    whatever session (re)binds next. VisionService.bind_session/unbind_session
    separately clear the service-side pending-moves deque -- this covers the
    app-level queue, which may not exist at all in tests / vision-disabled apps."""
    queue = getattr(request.app.state, "vision_move_queue", None)
    if queue is None:
        return
    while not queue.empty():
        try:
            queue.get_nowait()
        except Exception:
            break


def _consume_recovery_episode(request: Request, body: "EngineMoveRecoveryRequest"):
    """Task 8 (B4/M5/D8) shared guard for both engine-move/retry and .../cancel:
    validate that an active recovery episode exists for `body.session_id`, that
    vision is currently bound to that same session, and that `body.recovery_token`
    matches -- THEN atomically detach it (CAS via tracker.consume()) so a concurrent
    second call (double-click, or a retry racing a cancel) can never also succeed.

    Auth level matches M5: bound-session+token is the primary check (no separate
    user/session-cookie auth here, consistent with the rest of this file's vision
    endpoints -- they're all trusted-kiosk-LAN, session_id-scoped)."""
    vision = _get_vision(request)
    tracker = getattr(request.app.state, "engine_recovery", None)
    if tracker is None or vision.bound_session_id != body.session_id:
        raise HTTPException(status_code=409, detail="No active engine-move recovery for this session")
    episode = tracker.consume(body.recovery_token)
    if episode is None:
        raise HTTPException(status_code=409, detail="Recovery token is stale or already consumed")
    return episode


# -- Endpoints ---------------------------------------------------------------


@router.get("/status")
async def vision_status(request: Request):
    """Return vision service status."""
    vision = getattr(request.app.state, "vision", None)
    if vision is None:
        return {
            "enabled": False,
            "camera_connected": False,
            "pose_locked": False,
            "sync_state": "idle",
            "bound_session_id": None,
            "camera_ready": False,
            "geometry_ready": False,
            "model_ready": False,
            "recognition_ready": False,
            "led_connected": bool(getattr(request.app.state, "led", None)) and request.app.state.led.is_connected(),
        }

    vision.refresh_status()
    return {
        "enabled": vision.enabled,
        "camera_connected": vision.camera_status == "connected",
        "pose_locked": vision.pose_lock_status == "locked",
        "sync_state": vision.sync_state,
        "bound_session_id": vision.bound_session_id,
        "camera_ready": vision._latest_status.camera_ready,
        "geometry_ready": vision._latest_status.geometry_ready,
        "model_ready": vision._latest_status.model_ready,
        "recognition_ready": vision._latest_status.recognition_ready,
        "led_connected": bool(getattr(request.app.state, "led", None)) and request.app.state.led.is_connected(),
    }


@router.get("/stream")
async def vision_stream(request: Request):
    """MJPEG video stream of the camera preview (2-3 fps, backpressure-aware)."""
    vision = _get_vision(request)
    vision.set_viewer_active(True)

    async def generate():
        try:
            while True:
                jpeg = vision.get_preview_jpeg()
                if jpeg:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n"
                    )
                await asyncio.sleep(0.05)  # ~20 fps polling
        finally:
            vision.set_viewer_active(False)

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace;boundary=frame")


@router.get("/detected-board")
async def get_detected_board(request: Request):
    """Return the latest detected board state as a 19x19 matrix."""
    vision = _get_vision(request)
    vision.refresh_status()
    board = vision.get_detected_board()
    return {"board": board}


@router.post("/pose-lock/confirm")
async def confirm_pose_lock(request: Request):
    """Confirm board pose lock after calibration."""
    vision = _get_vision(request)
    ok = vision.confirm_pose_lock()
    return {"ok": ok}


@router.post("/bind")
async def bind_session(request: Request, body: BindRequest):
    """Bind vision to a game session."""
    vision = _get_vision(request)
    manager = request.app.state.session_manager
    try:
        session = manager.get_session(body.session_id)
    except KeyError:
        # A stale tab re-binding a session lost to a server restart must get a clean
        # 404, not a KeyError 500 (SessionManager.get_session raises, not returns None).
        session = None
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {body.session_id} not found")

    vision.bind_session(body.session_id)
    _drain_stale_move_queue(request)

    # Set expected board from current game state
    game_state = session.katrain.get_state()
    if game_state and "stones" in game_state:
        vision.set_expected_from_stones(game_state["stones"])

    orchestrator = getattr(request.app.state, "physical_play", None)
    if orchestrator is not None:
        orchestrator.on_bind(body.session_id, session)

    return {"ok": True, "session_id": body.session_id}


@router.post("/unbind")
async def unbind_session(request: Request):
    """Unbind from current session."""
    vision = _get_vision(request)
    orchestrator = getattr(request.app.state, "physical_play", None)
    if orchestrator is not None:
        orchestrator.on_unbind()
    vision.unbind_session()
    _drain_stale_move_queue(request)
    recovery = getattr(request.app.state, "engine_recovery", None)
    if recovery is not None:
        recovery.clear()  # Task 7: an in-flight recovery episode belongs to the unbound game
    return {"ok": True}


@router.post("/sync/reset")
async def reset_sync(request: Request, body: ResetSyncRequest | None = None):
    """Reset vision sync. adopt='digital' (default; kiosk 重置识别 / escalation '已按指示恢复')
    delegates to the physical-play orchestrator — re-baseline to the DIGITAL game, discard
    camera phantoms, and release any stuck removal/pause so play continues. adopt='physical'
    (ambiguous-stone 忽略) accepts the current camera board as baseline so the ignored stone
    doesn't re-fire. Falls back to a plain physical-adopt reset with no orchestrator
    (research mode)."""
    vision = _get_vision(request)
    orchestrator = getattr(request.app.state, "physical_play", None)
    adopt = body.adopt if body else "digital"
    if orchestrator is not None and adopt != "physical":
        orchestrator.resync()
    else:
        vision.reset_sync()
    return {"ok": True}


@router.post("/setup-mode")
async def enter_setup_mode(request: Request, body: SetupModeRequest):
    """Enter tsumego setup mode with a target board position."""
    vision = _get_vision(request)
    import numpy as np

    target = np.array(body.target_board, dtype=int)
    vision.enter_setup_mode(target)
    return {"ok": True}


class MonitorRequest(BaseModel):
    active: bool


class PauseRequest(BaseModel):
    paused: bool


class MoveDetectionRequest(BaseModel):
    armed: bool


class ExpectedBoardRequest(BaseModel):
    board: list[list[int]]  # vision coords, row 0 = top


class EngineMoveRecoveryRequest(BaseModel):
    session_id: str
    recovery_token: str


@router.post("/monitor")
async def set_monitor(request: Request, body: MonitorRequest):
    """Enable/disable sessionless monitor mode (physical tsumego)."""
    vision = _get_vision(request)
    vision.set_monitor(body.active)
    return {"ok": True, "active": body.active}


@router.post("/pause")
async def set_paused(request: Request, body: PauseRequest):
    """Pause/resume recognition (hint display, try mode).

    Single-owner aggregate boolean: the one page owning monitor mode sends
    `showHint || isTryMode` — do NOT add independent callers (no ref-counting in v1).
    """
    vision = _get_vision(request)
    vision.set_paused(body.paused)
    return {"ok": True, "paused": body.paused}


@router.post("/move-detection")
async def set_move_detection(request: Request, body: MoveDetectionRequest):
    """Arm/disarm monitor-mode move detection (frontend arms only in 'ready' phase)."""
    vision = _get_vision(request)
    vision.set_move_armed(body.armed)
    return {"ok": True, "armed": body.armed}


@router.post("/expected-board")
async def set_expected_board(request: Request, body: ExpectedBoardRequest):
    """Set expected board + rebase move detector (SET_EXPECTED_BOARD does force_sync)."""
    vision = _get_vision(request)
    import numpy as np

    vision.set_expected_board(np.array(body.board, dtype=int))
    return {"ok": True}


@router.post("/engine-move/retry")
async def retry_engine_move(request: Request, body: EngineMoveRecoveryRequest):
    """Task 8 (B4/M5/D8): resubmit a stuck engine-tunnel move after Task 7's
    bounded-retry threshold tripped and the recovery dialog came up.

    Token CAS: `_consume_recovery_episode` detaches the episode BEFORE this
    resubmit's `await gateway.play_move(...)` — a concurrent double-click (same
    token) always finds the episode already gone on its second call and gets a
    409; exactly one submission ever reaches the gateway.

    - success -> clear the orchestrator's engine_error reason (resumes detection
      via the pause-reasons mechanism) and {"ok": true}.
    - failure again -> `tracker.trip_now(...)` re-trips a FRESH token immediately
      (no bounded-attempts count for an explicit user retry — see engine_recovery.py),
      re-arms the orchestrator's engine_error context with it (detection stays
      paused throughout — never resumed mid-retry), HTTP 200 {"ok": false, "detail",
      "recovery_token": <new>}.
    """
    episode = _consume_recovery_episode(request, body)
    tracker = request.app.state.engine_recovery
    orchestrator = getattr(request.app.state, "physical_play", None)
    gateway = getattr(request.app.state, "platform_gateway", None)
    col, row = episode.coords

    try:
        if gateway is None:
            raise RuntimeError("Platform gateway not available")
        await gateway.play_move(body.session_id, col, row, user_id=0)
    except Exception as e:
        new_episode = tracker.trip_now(game_id=episode.game_id, coords=episode.coords, detail=str(e))
        if orchestrator is not None:
            orchestrator.enter_engine_error(episode.coords, new_episode.recovery_token)
        return {"ok": False, "detail": str(e), "recovery_token": new_episode.recovery_token}

    tracker.on_success()
    if orchestrator is not None:
        orchestrator.clear_engine_error()
    return {"ok": True}


@router.post("/engine-move/cancel")
async def cancel_engine_move(request: Request, body: EngineMoveRecoveryRequest):
    """Task 8: give up retrying the stuck move and wait for the PHYSICAL stone at
    its coords to be removed instead (awaiting_removal). Detection stays paused
    throughout; the orchestrator's tick loop keeps running a narrow board-equality
    check each tick (see PhysicalPlayOrchestrator._tick_awaiting_removal /
    `_run`'s dispatch) rather than a full LED reconciliation or nothing at all.

    Returns immediately — resolution (stone removed + board matches digital for N
    stable ticks) is asynchronous, signaled later via a `physical_engine_error_resolved`
    broadcast that the frontend uses to close the waiting UI."""
    episode = _consume_recovery_episode(request, body)
    orchestrator = getattr(request.app.state, "physical_play", None)
    if orchestrator is not None:
        orchestrator.enter_awaiting_removal(episode.coords)
    return {"ok": True, "awaiting_removal": True}
