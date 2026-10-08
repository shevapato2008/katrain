from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from datetime import datetime
from katrain.web.models import User
from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.core.pvp_lobby_bots import human_ladder_rungs, playable_rungs

router = APIRouter()


@router.get("/active/multiplayer")
async def list_active_multiplayer_games(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """进行中的联机对局列表。

    ⚠️ **必须鉴权。** 这里原来是完全裸的 —— 而它吐的是 `session_id`。
    记忆里那条利用链的另一半(陌生人判负他人对局)上游已经用
    `guard_session_terminator` 封了,但「不鉴权的 session_id 列表」这一半
    一直留着:任何人都能枚举出正在进行的对局、双方用户名和会话号。
    `get_current_user` 本文件早就 import 了,只是没挂上。
    """
    from katrain.web.core.box_sso import strict_box_sso_enabled

    bridge = getattr(request.app.state, "pvp_box_bridge", None)
    if strict_box_sso_enabled() and bridge is not None:
        from katrain.web.core.pvp_box_bridge import PvpBoxAuthError, PvpBoxRemoteError

        generation = request.app.state.box_sso.active_generation
        try:
            central_user_id = (await bridge.identity(generation, current_user.id))["user_id"]
            rows = await bridge.get_json(generation, current_user.id, "/api/v1/games/active/multiplayer")
            return bridge.rewrite_active_games(generation, current_user.id, central_user_id, rows)
        except PvpBoxAuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except PvpBoxRemoteError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    manager = request.app.state.session_manager
    user_repo = request.app.state.user_repo
    sessions = manager.list_active_multiplayer_sessions()

    all_users = user_repo.list_users()
    users_by_id = {u["id"]: u["username"] for u in all_users}
    ids = {user_id for s in sessions for user_id in (s.player_b_id, s.player_w_id)
           if user_id is not None and user_id > 0}
    ranks = human_ladder_rungs(request.app.state.session_factory, ids)
    labels = {level.rung: level.rank_label for level in playable_rungs()}
    runtime = getattr(request.app.state, "pvp_lobby_bots", None)
    bots_by_id = {row["id"]: row for row in runtime.public_online_rows()} if runtime is not None else {}

    results = []
    for s in sessions:
        if s.game_ended or getattr(s, "game_type", "free") == "pvp_online":
            continue
        state = s.last_state or s.katrain.get_state()
        black_bot = bots_by_id.get(s.player_b_id, {})
        white_bot = bots_by_id.get(s.player_w_id, {})
        black_rung = black_bot.get("ladder_rung", ranks.get(s.player_b_id))
        white_rung = white_bot.get("ladder_rung", ranks.get(s.player_w_id))
        results.append(
            {
                "session_id": s.session_id,
                "player_b": users_by_id.get(s.player_b_id, black_bot.get("username", "Unknown")),
                "player_w": users_by_id.get(s.player_w_id, white_bot.get("username", "Unknown")),
                "player_b_id": s.player_b_id,
                "player_w_id": s.player_w_id,
                "player_b_rung": black_rung,
                "player_w_rung": white_rung,
                "player_b_rank_label": labels.get(black_rung),
                "player_w_rank_label": labels.get(white_rung),
                "spectator_count": len(s.sockets) - 2 if len(s.sockets) > 2 else 0,
                "move_count": len(state.get("history", [])),
                "degraded": bool(getattr(s, "bot_degraded", False) or getattr(s, "multiplayer_degraded", False)),
            }
        )
    return results
