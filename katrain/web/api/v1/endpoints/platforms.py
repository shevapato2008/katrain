"""REST API endpoints for cross-platform online play."""

from __future__ import annotations

import logging
import random
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, field_validator

from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.models import User

logger = logging.getLogger("katrain_web")

router = APIRouter()


# --- Request/Response models ---


class PlatformLoginRequest(BaseModel):
    username: str
    password: str = ""  # optional — the SMS path does not use it
    sms_code: str = ""


class SmsRequest(BaseModel):
    phone: str


_VALID_HANDICAP = {-1, 0, 2, 3, 4, 5, 6, 7, 8, 9}  # 让子值 (handicap); no 1


def _komi_for_handicap(h: int) -> float:
    """Derive komi from handicap, matching Golaxy 自由对弈 conventions (chinese rules)."""
    if h == 0:
        return 7.5  # 分先 (even game)
    if h == -1:
        return 0.0  # 让先 (reverse komi, no stones)
    return float(h)  # 让N子 (N-stone handicap) -> komi N


def _handicap_stone_count(h: int) -> int:
    """Derive the genmove handicap (stone count) param. 分先/让先 place no stones."""
    return h if h >= 2 else 0


def _resolve_color(c: str) -> str:
    """Resolve the human's color, rolling nigiri (coin flip) if requested."""
    return random.choice(["B", "W"]) if c == "nigiri" else c


class EngineStartRequest(BaseModel):
    """Human-vs-AI engine game request.

    Client sends exactly `level` + `human_color` + `handicap`; everything else
    (rule, board_size, komi) is derived/fixed server-side. `extra="forbid"`
    means any other field is a 422 — this is how the "no non-default game
    config" constraint is enforced at the API boundary.

    - `human_color`: "B" | "W" | "nigiri" (nigiri = server coin-flips B/W at
      request time; the resolved color is returned in the response).
    - `handicap` (让子值): `0` = 分先 (even, komi 7.5), `-1` = 让先 (reverse
      komi 0.0, no stones placed), `2..9` = 让N子 (N-stone handicap, komi N).
      `1` is not a valid handicap value.
    - `rule` is always "chinese", `board_size` is always `19`.
    """

    model_config = {"extra": "forbid"}
    level: int
    human_color: str = "B"
    handicap: int = 0

    @field_validator("human_color")
    @classmethod
    def _color(cls, v):
        if v not in ("B", "W", "nigiri"):
            raise ValueError("human_color must be 'B', 'W', or 'nigiri'")
        return v

    @field_validator("handicap")
    @classmethod
    def _handicap(cls, v):
        if v not in _VALID_HANDICAP:
            raise ValueError(f"handicap must be one of {sorted(_VALID_HANDICAP)}")
        return v


class PlatformChallengeRequest(BaseModel):
    user_id: str
    board_size: int = 19
    time_control: dict = {}
    rules: str = "chinese"
    ranked: bool = True
    handicap: int = 0
    komi: Optional[float] = None


class AcceptChallengeRequest(BaseModel):
    challenge_id: str


class DeclineChallengeRequest(BaseModel):
    challenge_id: str


class AutomatchRequest(BaseModel):
    board_size: int = 19
    time_control: dict = {}
    rank_range: Optional[list[int]] = None


class EngineAnalysisRequest(BaseModel):
    """Request to run one analysis tunnel (area/options/judge/variation) against
    an existing engine game, resolved from `session_id` (see PlatformManager.
    engine_analysis). `judge` is whitelisted here even though the kiosk UI only
    wires 3 buttons (plan §13 line 473) — do not drop it."""

    session_id: str
    kind: Literal["area", "options", "judge", "variation"]


def _hint_position_token(app_state, session_id: str) -> Optional[int]:
    """Task 10 (G5/M7/M8): if `session_id` is currently bound to the vision-driven
    physical board AND an orchestrator is present, return the game's current_node
    identity as a position token — the caller re-checks this after the (slow)
    analysis await so a stale 支招 result can never blink LEDs on a position the
    board has since moved past. Returns None when there is no physical board
    tie-in to gate against (no orchestrator, no vision, or a different/no session
    bound), which the caller treats as "never show a hint"."""
    orchestrator = getattr(app_state, "physical_play", None)
    vision = getattr(app_state, "vision", None)
    if orchestrator is None or vision is None or vision.bound_session_id != session_id:
        return None
    manager = app_state.session_manager
    try:
        session = manager.get_session(session_id)
    except KeyError:
        return None
    with session.lock:
        return id(session.katrain.game.current_node)


def _maybe_show_hint(app_state, session_id: str, position_token: Optional[int], result) -> None:
    """Blink the physical board's white 支招 hint LEDs on a successful `options`
    result, gated on the position token captured before the analysis await.
    Re-resolves orchestrator/vision/session fresh (rather than reusing captured
    references) so a rebind during the await is caught too. LED/IPC failures are
    swallowed — the paid analysis result must still reach the tablet."""
    if position_token is None:
        return
    orchestrator = getattr(app_state, "physical_play", None)
    vision = getattr(app_state, "vision", None)
    if orchestrator is None or vision is None or vision.bound_session_id != session_id:
        logger.debug("支招 hint dropped: session %s no longer bound", session_id)
        return
    manager = app_state.session_manager
    try:
        session = manager.get_session(session_id)
    except KeyError:
        return
    try:
        with session.lock:
            if id(session.katrain.game.current_node) != position_token:
                logger.debug("支招 hint dropped: position changed for session %s", session_id)
                return
        # `Candidate.row`/`.col` are already top-anchored KaTrain (col, row) --
        # golaxy_to_katrain's row=0 is TOP, same frame vision/show_hint expects
        # (see katrain/web/platforms/golaxy/coords.py docstring). No flip.
        points = [(c.row, c.col) for c in result.candidates]
        if points:
            orchestrator.show_hint(points)
    except Exception:
        logger.exception("show_hint failed for session %s (LED/IPC error ignored)", session_id)


# --- Credential management ---


@router.post("/{platform}/login")
async def platform_login(
    platform: str, req: PlatformLoginRequest, request: Request, user: User = Depends(get_current_user)
):
    """Login to a Go platform. Tries saved JWT first, then password."""
    from katrain.web.platforms.models import PlatformCredentials

    pm = request.app.state.platform_manager
    adapter = pm.get_adapter(platform)
    if adapter is None:
        raise HTTPException(status_code=404, detail=f"Unknown platform: {platform}")

    # Try saved credentials (JWT token) first to avoid OGS rate-limiting
    saved = pm._credential_store.load_credentials(user.id, platform)
    if saved and saved.auth_data.get("user_jwt"):
        saved.auth_data["password"] = req.password  # Keep password as fallback
        success = await pm.connect_platform(platform, saved, user.id)
        if success:
            return {"status": "connected", "platform": platform, "username": saved.username}

    # Fresh login: SMS code (Golaxy) or password (OGS/Fox/KGS).
    if req.sms_code:
        auth_data = {"sms_code": req.sms_code}
    else:
        auth_data = {"password": req.password}
    credentials = PlatformCredentials(platform=platform, username=req.username, auth_data=auth_data)
    success = await pm.connect_platform(platform, credentials, user.id)
    if not success:
        raise HTTPException(status_code=401, detail="Login failed")

    return {"status": "connected", "platform": platform, "username": req.username}


@router.delete("/{platform}/logout")
async def platform_logout(platform: str, request: Request, user: User = Depends(get_current_user)):
    """Logout from a platform and delete saved credentials."""
    pm = request.app.state.platform_manager
    await pm.disconnect_platform(platform)
    pm._credential_store.delete_credentials(user.id, platform)
    return {"status": "disconnected", "platform": platform}


@router.get("/status")
async def platform_status(request: Request, user: User = Depends(get_current_user)):
    """List all platforms and their connection/credential status."""
    pm = request.app.state.platform_manager
    platforms = pm.list_platforms()
    saved = {p["platform"]: p["username"] for p in pm._credential_store.list_platforms(user.id)}
    for p in platforms:
        p["saved_username"] = saved.get(p["platform"])
    return {"platforms": platforms}


# --- SMS login (Golaxy: phone + verification code) ---


@router.post("/{platform}/sms/request")
async def request_sms(platform: str, req: SmsRequest, request: Request, user: User = Depends(get_current_user)):
    """Request an SMS verification code for phone-based login (Golaxy)."""
    pm = request.app.state.platform_manager
    adapter = pm.get_adapter(platform)
    if adapter is None:
        raise HTTPException(status_code=404, detail=f"Unknown platform: {platform}")
    fn = getattr(adapter, "request_sms_code", None)
    if fn is None:
        raise HTTPException(status_code=400, detail=f"{platform} does not support SMS login")
    ok = await fn(req.phone)
    if not ok:
        raise HTTPException(status_code=502, detail="SMS request failed")
    return {"status": "sent"}


# --- Engine play (human-vs-AI) ---


@router.post("/{platform}/engine/start")
async def start_engine(
    platform: str, req: EngineStartRequest, request: Request, user: User = Depends(get_current_user)
):
    """Start a human-vs-AI engine game. Client sends level + human_color +
    handicap; komi/rule/board_size are derived/fixed server-side (see
    EngineStartRequest)."""
    pm = request.app.state.platform_manager
    adapter = pm.get_adapter(platform)
    if adapter is None or not adapter.is_connected:
        raise HTTPException(status_code=400, detail=f"Not connected to {platform}")
    if not getattr(adapter, "supports_engine_play", False):
        raise HTTPException(status_code=400, detail=f"{platform} does not support engine play")
    # Validate the requested level against the adapter's level table.
    levels = adapter.get_engine_levels()
    if not any(l["elo_score"] == req.level for l in levels):
        raise HTTPException(status_code=422, detail=f"Unknown level {req.level}")
    from katrain.web.platforms.golaxy.adapter import EngineGameConfig

    color = _resolve_color(req.human_color)  # rolls nigiri if requested
    config = EngineGameConfig(
        level=req.level,
        human_color=color,
        komi=_komi_for_handicap(req.handicap),
        rule="chinese",
        handicap=_handicap_stone_count(req.handicap),
        board_size=19,
    )
    session_id = await pm.start_engine_game(platform, config, user.id)
    return {"session_id": session_id, "human_color": color}


@router.post("/{platform}/engine/analysis")
async def engine_analysis(
    platform: str, req: EngineAnalysisRequest, request: Request, user: User = Depends(get_current_user)
):
    """Run one analysis tunnel (area/options/judge/variation) for the engine
    game behind `req.session_id`. Insufficient quota is a normal, expected
    outcome (not a server error) — it comes back as `{ok:false}` at HTTP 200,
    not a 5xx. Genuine failures (AuthExpired/Retryable/Fatal) are not caught
    here and surface as 5xx, same as other routes."""
    pm = request.app.state.platform_manager
    adapter = pm.get_adapter(platform)
    if adapter is None or not adapter.is_connected:
        raise HTTPException(status_code=400, detail=f"Not connected to {platform}")
    if not getattr(adapter, "supports_engine_play", False):
        raise HTTPException(status_code=400, detail=f"{platform} does not support engine play")
    from katrain.web.platforms.golaxy.engine_client import QuotaExhausted

    # Task 10 (G5/M7/M8): capture the position token BEFORE the (slow) analysis
    # tunnel call so a concurrent move/undo/rebind during the await can be
    # detected afterward. Only "options" ever shows a hint, so skip the lock
    # acquisition for the other kinds.
    position_token = _hint_position_token(request.app.state, req.session_id) if req.kind == "options" else None

    try:
        result = await pm.engine_analysis(platform, req.session_id, req.kind)
    except QuotaExhausted:
        return {"ok": False, "reason": "insufficient", "kind": req.kind}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No engine game for session {req.session_id}")

    if req.kind == "options":
        _maybe_show_hint(request.app.state, req.session_id, position_token, result)

    import dataclasses

    return {"ok": True, "kind": req.kind, "data": dataclasses.asdict(result)}


@router.get("/{platform}/engine/levels")
async def engine_levels(platform: str, request: Request, user: User = Depends(get_current_user)):
    """Return the AI level table for an engine-play platform."""
    pm = request.app.state.platform_manager
    adapter = pm.get_adapter(platform)
    if adapter is None:
        raise HTTPException(status_code=404, detail=f"Unknown platform: {platform}")
    if not getattr(adapter, "supports_engine_play", False):
        raise HTTPException(status_code=400, detail=f"{platform} does not support engine play")
    return {"levels": adapter.get_engine_levels()}


@router.get("/{platform}/engine/items")
async def engine_items(platform: str, request: Request, user: User = Depends(get_current_user)):
    """Remaining metered-道具 counts (领地/支招/变化图) for the connected
    engine-play account — powers the analysis-button badges. Account-level, not
    per-game. Each count is an int, or `null` when the platform didn't report
    it (surface as "unknown", never as 0). Genuine wire failures
    (AuthExpired/Retryable/Fatal) surface as 5xx, same as the other routes."""
    pm = request.app.state.platform_manager
    adapter = pm.get_adapter(platform)
    if adapter is None or not adapter.is_connected:
        raise HTTPException(status_code=400, detail=f"Not connected to {platform}")
    if not getattr(adapter, "supports_engine_play", False):
        raise HTTPException(status_code=400, detail=f"{platform} does not support engine play")
    import dataclasses

    result = await adapter.fetch_item_counts()
    return dataclasses.asdict(result)  # {"area": int|null, "options": int|null, "variation": int|null}


# --- Lobby ---


@router.get("/{platform}/users")
async def platform_users(
    platform: str,
    q: Optional[str] = None,
    room: Optional[str] = None,
    request: Request = None,
    user: User = Depends(get_current_user),
):
    """List online users on a platform.

    Without `q`: returns seek graph / open challenge users (actively looking for games).
    With `q`: searches players by username prefix.
    """
    pm = request.app.state.platform_manager
    adapter = pm.get_adapter(platform)
    if adapter is None or not adapter.is_connected:
        raise HTTPException(status_code=400, detail=f"Not connected to {platform}")

    if q:
        # Specific player search
        users = await adapter.get_online_users(room=q)
    else:
        # Default: show seek graph users (one entry per open challenge)
        challenges = await adapter.get_open_challenges()
        seen = set()
        users = []
        for c in challenges:
            # Deduplicate by username (not user_id which may be empty)
            key = c.from_user.username
            if key not in seen:
                seen.add(key)
                c.from_user.status = "seeking"
                users.append(c.from_user)
    return {
        "users": [{"user_id": u.user_id, "username": u.username, "rank": u.rank, "status": u.status} for u in users]
    }


@router.get("/{platform}/rooms")
async def platform_rooms(platform: str, request: Request, user: User = Depends(get_current_user)):
    """List rooms/channels on a platform (Fox, KGS)."""
    pm = request.app.state.platform_manager
    adapter = pm.get_adapter(platform)
    if adapter is None or not adapter.is_connected:
        raise HTTPException(status_code=400, detail=f"Not connected to {platform}")
    if not adapter.supports_rooms:
        raise HTTPException(status_code=400, detail=f"{platform} does not support rooms")
    rooms = await adapter.get_rooms()
    return {"rooms": rooms}


@router.get("/{platform}/challenges")
async def platform_challenges(platform: str, request: Request, user: User = Depends(get_current_user)):
    """List open challenges on a platform (OGS seek graph)."""
    pm = request.app.state.platform_manager
    adapter = pm.get_adapter(platform)
    if adapter is None or not adapter.is_connected:
        raise HTTPException(status_code=400, detail=f"Not connected to {platform}")
    challenges = await adapter.get_open_challenges()
    return {"challenges": challenges}


# --- Challenge flow ---


@router.post("/{platform}/challenge")
async def send_challenge(
    platform: str, req: PlatformChallengeRequest, request: Request, user: User = Depends(get_current_user)
):
    """Send a challenge to a user on a platform."""
    pm = request.app.state.platform_manager
    adapter = pm.get_adapter(platform)
    if adapter is None or not adapter.is_connected:
        raise HTTPException(status_code=400, detail=f"Not connected to {platform}")
    challenge_id = await adapter.send_challenge(req.user_id, req.model_dump())
    return {"challenge_id": challenge_id}


@router.post("/{platform}/challenge/accept")
async def accept_challenge(
    platform: str, req: AcceptChallengeRequest, request: Request, user: User = Depends(get_current_user)
):
    """Accept an incoming challenge."""
    pm = request.app.state.platform_manager
    adapter = pm.get_adapter(platform)
    if adapter is None or not adapter.is_connected:
        raise HTTPException(status_code=400, detail=f"Not connected to {platform}")
    game_session = await adapter.accept_challenge(req.challenge_id)
    session_id = await pm.start_platform_game(platform, game_session, user.id)
    return {"session_id": session_id, "game": game_session.__dict__}


@router.post("/{platform}/challenge/decline")
async def decline_challenge(
    platform: str, req: DeclineChallengeRequest, request: Request, user: User = Depends(get_current_user)
):
    """Decline an incoming challenge."""
    pm = request.app.state.platform_manager
    adapter = pm.get_adapter(platform)
    if adapter is None or not adapter.is_connected:
        raise HTTPException(status_code=400, detail=f"Not connected to {platform}")
    await adapter.decline_challenge(req.challenge_id)
    return {"status": "declined"}


# --- Automatch ---


@router.post("/{platform}/automatch/start")
async def start_automatch(
    platform: str, req: AutomatchRequest, request: Request, user: User = Depends(get_current_user)
):
    """Start automatch on a platform."""
    pm = request.app.state.platform_manager
    adapter = pm.get_adapter(platform)
    if adapter is None or not adapter.is_connected:
        raise HTTPException(status_code=400, detail=f"Not connected to {platform}")
    if not adapter.supports_automatch:
        raise HTTPException(status_code=400, detail=f"{platform} does not support automatch")
    await adapter.start_automatch(req.model_dump())
    return {"status": "searching"}


@router.post("/{platform}/automatch/cancel")
async def cancel_automatch(platform: str, request: Request, user: User = Depends(get_current_user)):
    """Cancel automatch on a platform."""
    pm = request.app.state.platform_manager
    adapter = pm.get_adapter(platform)
    if adapter is None or not adapter.is_connected:
        raise HTTPException(status_code=400, detail=f"Not connected to {platform}")
    await adapter.cancel_automatch()
    return {"status": "cancelled"}
