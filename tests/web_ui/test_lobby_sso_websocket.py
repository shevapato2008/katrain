from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from katrain.web.core.auth import SQLAlchemyUserRepository, create_access_token
from katrain.web.core import models_db
from katrain.web.server import create_app
from katrain.web.session import LobbyManager, Matchmaker


@asynccontextmanager
async def no_lifespan(app):
    """Exercise websocket routing without the external-service startup lifecycle."""
    yield


@pytest.fixture
def lobby_app(tmp_path):
    app = create_app(enable_engine=False)
    app.router.lifespan_context = no_lifespan

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{tmp_path / 'lobby_sso.db'}", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    app.state.user_repo = SQLAlchemyUserRepository(sessionmaker(bind=engine))
    app.state.lobby_manager = LobbyManager()
    app.state.matchmaker = Matchmaker()

    yield app

    engine.dispose()


def create_token(app, username):
    user = app.state.user_repo.create_user(username, "unused-password-hash")
    return create_access_token(data={"sub": username}), user["id"]


def test_lobby_query_token_authenticates_without_origin(lobby_app):
    token, user_id = create_token(lobby_app, "query_user")

    with TestClient(lobby_app) as client:
        with client.websocket_connect(f"/ws/lobby?token={token}") as websocket:
            assert websocket.receive_json()["type"] == "lobby_update"
            assert user_id in lobby_app.state.lobby_manager.get_online_user_ids()


def test_lobby_same_origin_cookie_authenticates(lobby_app):
    token, user_id = create_token(lobby_app, "cookie_user")

    with TestClient(lobby_app) as client:
        client.cookies.set("sb_token", token)
        with client.websocket_connect("/ws/lobby", headers={"Origin": "http://testserver"}) as websocket:
            assert websocket.receive_json()["type"] == "lobby_update"
            assert user_id in lobby_app.state.lobby_manager.get_online_user_ids()


@pytest.mark.parametrize("origin", [None, "https://attacker.example"])
def test_lobby_cookie_rejects_missing_or_untrusted_origin(lobby_app, origin):
    token, _ = create_token(lobby_app, "cookie_attacker")
    headers = {} if origin is None else {"Origin": origin}

    with TestClient(lobby_app) as client:
        client.cookies.set("sb_token", token)
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws/lobby", headers=headers) as websocket:
                websocket.receive_json()

    assert exc_info.value.code == 1008


def test_lobby_query_token_wins_over_cookie(lobby_app):
    query_token, query_user_id = create_token(lobby_app, "query_user")
    cookie_token, cookie_user_id = create_token(lobby_app, "cookie_user")

    with TestClient(lobby_app) as client:
        client.cookies.set("sb_token", cookie_token)
        with client.websocket_connect(f"/ws/lobby?token={query_token}") as websocket:
            assert websocket.receive_json()["type"] == "lobby_update"
            online_user_ids = lobby_app.state.lobby_manager.get_online_user_ids()
            assert query_user_id in online_user_ids
            assert cookie_user_id not in online_user_ids
