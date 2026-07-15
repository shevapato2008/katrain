from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.auth import SQLAlchemyUserRepository, create_access_token
from katrain.web.core.box_sso import BoxSSOState
from katrain.web.core.config import settings
from katrain.web.server import create_app
from katrain.web.session import LobbyManager, Matchmaker, SessionManager


BRIDGE_HEADER = {"X-SmartBox-Bridge-Key": "bridge-test-secret"}


@asynccontextmanager
async def no_lifespan(app):
    yield


@pytest.fixture
def strict_app(tmp_path, monkeypatch):
    key_path = tmp_path / "bridge.key"
    key_path.write_text("bridge-test-secret\n", encoding="utf-8")
    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", True)
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO_BRIDGE_KEY_PATH", str(key_path))

    app = create_app(enable_engine=False)
    app.router.lifespan_context = no_lifespan
    engine = create_engine(
        f"sqlite:///{tmp_path / 'box_sso.db'}", connect_args={"check_same_thread": False}
    )
    models_db.Base.metadata.create_all(bind=engine)
    app.state.user_repo = SQLAlchemyUserRepository(sessionmaker(bind=engine))
    app.state.remote_client = MagicMock()
    app.state.remote_client.set_tokens = MagicMock()
    app.state.remote_client.clear_tokens = MagicMock()
    app.state.lobby_manager = LobbyManager()
    app.state.matchmaker = Matchmaker()
    app.state.session_manager = SessionManager(enable_engine=False)
    app.state.game_repo = None
    yield app
    engine.dispose()


async def bootstrap(client, *, generation=1, username="alice", headers=None):
    return await client.post(
        "/api/v1/auth/box-sso/bootstrap",
        headers=headers or BRIDGE_HEADER,
        json={
            "username": username,
            "generation": generation,
            "remote_access_token": "remote-access",
            "remote_refresh_token": "remote-refresh",
        },
    )


@pytest.mark.asyncio
async def test_strict_bridge_bootstrap_returns_generation_bound_local_token(strict_app):
    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        response = await bootstrap(client, generation=7)

    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    token = response.json()["access_token"]
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "alice"
    assert payload["box_generation"] == 7
    strict_app.state.remote_client.set_tokens.assert_called_once_with(
        "remote-access", "remote-refresh"
    )


@pytest.mark.asyncio
async def test_strict_mode_rejects_bad_bridge_secret_and_non_loopback(strict_app):
    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        bad_secret = await bootstrap(
            client, headers={"X-SmartBox-Bridge-Key": "wrong"}
        )
    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://board.example"
    ) as client:
        remote_host = await bootstrap(client)

    assert bad_secret.status_code == 403
    assert remote_host.status_code == 403
    strict_app.state.remote_client.set_tokens.assert_not_called()


@pytest.mark.asyncio
async def test_strict_browser_accepts_only_go_cookie_and_current_generation(strict_app):
    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        first = await bootstrap(client, generation=3)
        old_token = first.json()["access_token"]
        direct_bearer = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"}
        )
        retired_cookie = await client.get(
            "/api/v1/auth/me", cookies={"sb_token": old_token}
        )
        current_cookie = await client.get(
            "/api/v1/auth/me", cookies={"sb_go_token": old_token}
        )
        await bootstrap(client, generation=4)
        stale_cookie = await client.get(
            "/api/v1/auth/me", cookies={"sb_go_token": old_token}
        )

    assert direct_bearer.status_code == 401
    assert retired_cookie.status_code == 401
    assert current_cookie.status_code == 200
    assert stale_cookie.status_code == 401


@pytest.mark.asyncio
async def test_strict_mode_disables_direct_login_register_and_refresh(strict_app):
    refresh_token = create_access_token({"sub": "legacy"})
    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        login = await client.post(
            "/api/v1/auth/login", json={"username": "alice", "password": "pw"}
        )
        register = await client.post(
            "/api/v1/auth/register", json={"username": "alice", "password": "pw"}
        )
        refresh = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
        )

    assert login.status_code == 403
    assert register.status_code == 403
    assert refresh.status_code == 403


@pytest.mark.asyncio
async def test_bridge_clear_invalidates_generation_and_closes_registered_sockets(strict_app):
    socket = MagicMock()
    socket.close = AsyncMock()
    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        boot = await bootstrap(client, generation=9)
        token = boot.json()["access_token"]
        strict_app.state.box_sso.register_socket(socket)
        cleared = await client.post(
            "/api/v1/auth/box-sso/clear",
            headers=BRIDGE_HEADER,
            json={"generation": 9},
        )
        me = await client.get(
            "/api/v1/auth/me", cookies={"sb_go_token": token}
        )

    assert cleared.status_code == 200
    assert me.status_code == 401
    strict_app.state.remote_client.clear_tokens.assert_called_once_with()
    socket.close.assert_awaited_once()


def test_strict_lobby_rejects_query_token_but_accepts_same_origin_go_cookie(strict_app):
    with TestClient(strict_app) as client:
        boot = client.post(
            "/api/v1/auth/box-sso/bootstrap",
            headers=BRIDGE_HEADER,
            json={
                "username": "socket-user",
                "generation": 11,
                "remote_access_token": "remote-access",
                "remote_refresh_token": "remote-refresh",
            },
        )
        token = boot.json()["access_token"]
        with pytest.raises(Exception):
            with client.websocket_connect(f"/ws/lobby?token={token}") as websocket:
                websocket.receive_json()

        client.cookies.set("sb_go_token", token)
        with client.websocket_connect(
            "/ws/lobby", headers={"Origin": "http://testserver"}
        ) as websocket:
            assert websocket.receive_json()["type"] == "lobby_update"
