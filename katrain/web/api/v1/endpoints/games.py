from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from datetime import datetime
from katrain.web.models import User
from katrain.web.api.v1.endpoints.auth import get_current_user

router = APIRouter()


@router.get("/active/multiplayer")
async def list_active_multiplayer_games(request: Request):
    manager = request.app.state.session_manager
    user_repo = request.app.state.user_repo
    sessions = manager.list_active_multiplayer_sessions()

    all_users = user_repo.list_users()
    users_by_id = {u["id"]: u["username"] for u in all_users}

    results = []
    for s in sessions:
        state = s.last_state or s.katrain.get_state()
        results.append({
            "session_id": s.session_id,
            "player_b": users_by_id.get(s.player_b_id, "Unknown"),
            "player_w": users_by_id.get(s.player_w_id, "Unknown"),
            "spectator_count": len(s.sockets) - 2 if len(s.sockets) > 2 else 0,
            "move_count": len(state.get("history", []))
        })
    return results
