"""星阵人机局终局端点契约测试。"""

import threading
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from katrain.web.api.v1.endpoints.auth import get_current_user_optional
from katrain.web.models import User
from katrain.web.platforms.gateway import PlatformMoveRejectedError
from katrain.web.server import create_app
from katrain.web.session import WebSession

HUMAN = User(id=7, username="小明")


def _engine_session(end_result=None, human_color="B", engine=True):
    """构造星阵人机会话；engine=False 时构造同座位形状的 OGS 真人局。"""
    katrain = MagicMock()
    katrain.game_type = "free"
    katrain.analysis_allowed = True
    katrain.get_state.return_value = {"end_result": end_result, "player_to_move": human_color, "history": []}
    katrain.game.end_result = end_result
    if engine:
        katrain.platform_engine_color = "W" if human_color == "B" else "B"
    session = WebSession(session_id="eng-1", katrain=katrain, lock=threading.Lock())
    session.user_id = HUMAN.id
    session.player_b_id = HUMAN.id if human_color == "B" else -1
    session.player_w_id = HUMAN.id if human_color == "W" else -1
    return session


def _gateway(is_engine=True):
    gw = MagicMock()
    gw.is_platform_game.return_value = True
    gw.is_engine_game.return_value = is_engine
    gw.play_move = AsyncMock()
    gw.pass_move = AsyncMock()
    gw.resign = AsyncMock(return_value={"status": "ok"})
    return gw


def _app(session, gateway):
    app = create_app(enable_engine=False)
    app.state.session_manager._sessions[session.session_id] = session
    app.state.session_manager._schedule_broadcast = MagicMock()
    app.state.platform_gateway = gateway
    app.state.game_repo = MagicMock()
    app.dependency_overrides[get_current_user_optional] = lambda: HUMAN
    return app


def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestMoveWhenTheEngineEndsTheGame:
    async def test_game_ended_returns_the_ended_state_not_409(self):
        session = _engine_session(end_result="Void")
        gw = _gateway()
        gw.play_move.side_effect = PlatformMoveRejectedError("AI returned non-move coord 361", reason="game_ended")
        app = _app(session, gw)

        async with _client(app) as ac:
            response = await ac.post("/api/move", json={"session_id": session.session_id, "coords": [3, 3]})

        assert response.status_code == 200, response.text
        assert response.json()["state"]["end_result"] == "Void"
        assert session.last_state["end_result"] == "Void"

    async def test_other_rejections_are_still_409(self):
        session = _engine_session()
        gw = _gateway()
        gw.play_move.side_effect = PlatformMoveRejectedError("tunnel down", reason="engine_error")
        app = _app(session, gw)

        async with _client(app) as ac:
            response = await ac.post("/api/move", json={"session_id": session.session_id, "coords": [3, 3]})

        assert response.status_code == 409
        assert response.json()["detail"] == "tunnel down"
