"""Authenticated, read-only public hall snapshots for the kiosk spectator."""

import re
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Request

from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.core.box_sso import strict_box_sso_enabled
from katrain.web.core.pvp_box_bridge import PvpBoxAuthError, PvpBoxRemoteError
from katrain.web.core.pvp_lobby_bots import human_ladder_rungs, playable_rungs
from katrain.web.models import User


_SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")


def create_pvp_spectator_router(guard_session_viewer: Callable, session_state_for_read: Callable) -> APIRouter:
    """Reuse the application's viewer and authoritative state reader closures."""
    router = APIRouter()

    @router.get("/api/pvp/spectate/{session_id}")
    async def spectate(session_id: str, request: Request, current_user: User = Depends(get_current_user)):
        if not _SESSION_ID.fullmatch(session_id):
            raise HTTPException(status_code=404, detail="Public hall game not found")
        app = request.app
        if strict_box_sso_enabled():
            bridge = getattr(app.state, "pvp_box_bridge", None)
            if bridge is None:
                raise HTTPException(status_code=503, detail="Central lobby unavailable")
            try:
                response = await bridge.request(
                    app.state.box_sso.active_generation, current_user.id, "GET", f"/api/pvp/spectate/{session_id}"
                )
            except PvpBoxAuthError as exc:
                raise HTTPException(status_code=401, detail=str(exc)) from exc
            except PvpBoxRemoteError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Public hall game not found or finished")
            if not response.is_success:
                raise HTTPException(status_code=503, detail="Central spectator unavailable")
            try:
                data = response.json()
            except ValueError as exc:
                raise HTTPException(status_code=503, detail="Invalid central spectator snapshot") from exc
            if (
                not isinstance(data, dict)
                or data.get("session_id") != session_id
                or data.get("public_lobby") is not True
                or not isinstance(data.get("state"), dict)
            ):
                raise HTTPException(status_code=503, detail="Invalid central spectator snapshot")
            return data

        try:
            session = app.state.session_manager.get_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Public hall game not found or finished") from exc
        # This endpoint exposes only the hall, including to an owner of a private AI game.
        if getattr(session, "game_type", None) not in ("free", "pvp_lobby") or not all(
            type(seat) is int for seat in (session.player_b_id, session.player_w_id)
        ):
            raise HTTPException(status_code=404, detail="Public hall game not found")
        guard_session_viewer(session, current_user, "public hall spectator")
        state = session_state_for_read(session)
        spectator_count = app.state.session_manager.touch_http_spectator(session, current_user.id)
        state = {**state, "spectator_count": spectator_count}
        users_by_id = {user["id"]: user["username"] for user in app.state.user_repo.list_users()}
        ids = {seat for seat in (session.player_b_id, session.player_w_id) if seat > 0}
        ranks = human_ladder_rungs(app.state.session_factory, ids)
        labels = {level.rung: level.rank_label for level in playable_rungs()}
        runtime = getattr(app.state, "pvp_lobby_bots", None)
        bots = {row["id"]: row for row in runtime.public_online_rows()} if runtime is not None else {}
        players = {}
        for color, user_id in (("b", session.player_b_id), ("w", session.player_w_id)):
            bot = bots.get(user_id, {})
            rung = bot.get("ladder_rung", ranks.get(user_id))
            players[f"player_{color}"] = users_by_id.get(user_id, bot.get("username", "Unknown"))
            players[f"player_{color}_id"] = user_id
            players[f"player_{color}_rank_label"] = labels.get(rung)
        return {
            "session_id": session_id,
            "public_lobby": True,
            "game_ended": bool(session.game_ended),
            "spectator_count": spectator_count,
            "state": state,
            **players,
        }

    return router
