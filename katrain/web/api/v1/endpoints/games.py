from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from datetime import datetime
from katrain.web.models import User
from katrain.web.api.v1.endpoints.auth import get_current_user

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
    manager = request.app.state.session_manager
    user_repo = request.app.state.user_repo
    sessions = manager.list_active_multiplayer_sessions()

    all_users = user_repo.list_users()
    users_by_id = {u["id"]: u["username"] for u in all_users}

    results = []
    for s in sessions:
        state = s.last_state or s.katrain.get_state()
        results.append(
            {
                "session_id": s.session_id,
                "player_b": users_by_id.get(s.player_b_id, "Unknown"),
                "player_w": users_by_id.get(s.player_w_id, "Unknown"),
                "spectator_count": len(s.sockets) - 2 if len(s.sockets) > 2 else 0,
                "move_count": len(state.get("history", [])),
            }
        )
    return results
