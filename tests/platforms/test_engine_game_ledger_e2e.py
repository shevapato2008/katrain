"""Engine-game terminal paths reach the real user-games recording stack.

Only the Golaxy network call and final repository boundary are replaced.
"""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from katrain.vision.ipc import ConfirmedMove
from katrain.web.api.v1.endpoints.auth import get_current_user_optional
from katrain.web.models import User
from katrain.web.platforms.gateway import PlatformCommandGateway
from katrain.web.platforms.golaxy.adapter import EngineGameConfig, GolaxyAdapter
from katrain.web.platforms.golaxy.coords import katrain_to_golaxy
from katrain.web.platforms.golaxy.engine_client import GenmoveResult
from katrain.web.platforms.manager import PlatformManager
from katrain.web.server import _handle_confirmed_move, create_app

HUMAN = User(id=7, username="小明")
AI_SPECIAL = GenmoveResult(coord=361, prob=0.0)


async def _real_engine_game(genmove, human_color="B"):
    app = create_app(enable_engine=False)
    session_manager = app.state.session_manager
    platform_manager = PlatformManager(session_manager)
    gateway = PlatformCommandGateway(platform_manager, session_manager)
    adapter = GolaxyAdapter()
    platform_manager.register_adapter(adapter)
    adapter._rest.set_tokens("tok", "refresh")
    adapter._rest.engine_genmove = AsyncMock(return_value=genmove)
    platform_manager._setup_callbacks(adapter)
    app.state.platform_gateway = gateway
    app.state.game_repo = None
    app.state.repository_dispatcher = MagicMock()
    app.state.repository_dispatcher.user_games_create = AsyncMock(return_value={"id": "g1"})
    app.dependency_overrides[get_current_user_optional] = lambda: HUMAN
    session_id = await platform_manager.start_engine_game(
        "golaxy", EngineGameConfig(level=1100, human_color=human_color), user_id=HUMAN.id
    )
    return app, session_manager.get_session(session_id), gateway


def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _the_one_row(app):
    create = app.state.repository_dispatcher.user_games_create
    assert create.await_count == 1, f"星阵人机局终局应写 1 行 user_games,实际 {create.await_count} 行"
    kwargs = create.await_args.kwargs
    assert kwargs["user_id"] == HUMAN.id
    return kwargs["data"]


async def test_ai_ending_the_game_over_http_writes_one_row():
    app, session, gateway = await _real_engine_game(AI_SPECIAL)

    async with _client(app) as ac:
        response = await ac.post("/api/move", json={"session_id": session.session_id, "coords": [3, 3]})

    assert response.status_code == 200, response.text
    assert not gateway.is_engine_game(session.session_id)
    data = _the_one_row(app)
    assert (data["source"], data["result"]) == ("play_ai", "Void")
    assert data["player_black"] == "小明" and data["player_white"].startswith("[golaxy] ")


async def test_resigning_over_http_writes_one_row_and_resigning_again_writes_none():
    move = GenmoveResult(coord=katrain_to_golaxy(15, 3, 19), prob=0.5)
    app, session, gateway = await _real_engine_game(move, "W")

    async with _client(app) as ac:
        first = await ac.post("/api/resign", json={"session_id": session.session_id})
        again = await ac.post("/api/resign", json={"session_id": session.session_id})

    assert (first.status_code, again.status_code) == (200, 200), (first.text, again.text)
    assert not gateway.is_engine_game(session.session_id)
    data = _the_one_row(app)
    assert (data["source"], data["result"]) == ("play_ai", "B+R")
    assert data["player_white"] == "小明" and data["player_black"].startswith("[golaxy] ")
    assert again.json()["state"]["end_result"] == "B+R"


async def test_ai_ending_the_game_on_the_physical_board_writes_one_row_for_the_owner():
    app, session, gateway = await _real_engine_game(AI_SPECIAL)
    app.state.user_repo = SimpleNamespace(
        get_user_by_id=lambda uid: {"id": uid, "username": "小明"} if uid == HUMAN.id else None
    )
    vision = SimpleNamespace(set_expected_from_stones=lambda *args, **kwargs: None)

    await _handle_confirmed_move(
        app, vision, session.session_id, ConfirmedMove(col=3, row=3, color=1), logging.getLogger("e2e")
    )

    assert not gateway.is_engine_game(session.session_id)
    data = _the_one_row(app)
    assert (data["source"], data["result"], data["player_black"]) == ("play_ai", "Void", "小明")
