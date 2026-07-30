import threading
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.models import User
from katrain.web.server import create_app
from katrain.web.session import SessionManager, WebSession


def _make_session(session_id="test-session"):
    katrain = MagicMock()
    katrain.get_state.return_value = {"end_result": None, "history": []}
    return WebSession(session_id=session_id, katrain=katrain, lock=threading.Lock())


def test_session_game_ended_defaults_to_false():
    assert _make_session().game_ended is False


def test_terminal_state_latches_game_ended_until_explicit_reset():
    manager = SessionManager(enable_engine=False)
    session = _make_session()
    manager._sessions[session.session_id] = session
    manager._schedule_broadcast = MagicMock()

    manager._on_state(session.session_id, {"end_result": "B+R"})
    assert session.game_ended is True

    manager._on_state(session.session_id, {"end_result": None})
    assert session.game_ended is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/new-game", {"session_id": "test-session"}),
        (
            "/api/game/setup",
            {"session_id": "test-session", "mode": "newgame", "settings": {"size": 19}},
        ),
    ],
)
async def test_starting_game_resets_game_ended(path, payload):
    app = create_app(enable_engine=False)
    session = _make_session()
    session.game_ended = True
    app.state.session_manager._sessions[session.session_id] = session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(path, json=payload)

    assert response.status_code == 200
    assert session.game_ended is False


@pytest.mark.asyncio
async def test_multiplayer_count_completion_latches_game_ended():
    app = create_app(enable_engine=False)
    session = _make_session()
    session.player_b_id = 1
    session.player_w_id = 2
    session.pending_count_request = 1
    session.pending_count_timestamp = 123.0
    session.katrain.game.current_node.score = 5.5
    session.katrain.get_sgf.return_value = "(;FF[4]SZ[19])"
    session.katrain.get_state.return_value = {"end_result": "B+5.5", "history": [{}] * 100}
    app.state.session_manager._sessions[session.session_id] = session
    app.state.session_manager._schedule_broadcast = MagicMock()
    app.state.game_repo = MagicMock()
    app.dependency_overrides[get_current_user] = lambda: User(id=2, username="white")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/count/respond",
            json={"session_id": session.session_id, "accept": True},
        )

    assert response.status_code == 200
    assert session.game_ended is True
