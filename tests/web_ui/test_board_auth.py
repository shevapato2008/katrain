"""Tests for board-mode auth forwarding (design sections 5.1-5.4).

Covers:
- Login: remote forwarding, shadow user creation, local token issuance
- Login: shadow user reuse on repeat login
- Register: forwarding to remote
- Refresh: local token refresh + remote best-effort
- Logout: remote tokens cleared + credentials deleted
- Error cases: remote 401, remote unreachable (503)
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.api.v1.endpoints.auth import SHADOW_USER_NO_LOCAL_AUTH
from katrain.web.core import models_db
from katrain.web.core.auth import SQLAlchemyUserRepository, create_access_token, create_refresh_token
from katrain.web.core.config import settings
from katrain.web.server import create_app
from katrain.web.session import LobbyManager, Matchmaker, SessionManager


@pytest.fixture
def board_app():
    """Create a board-mode test app with a mocked RemoteAPIClient."""
    db_path = "test_board_auth.db"
    os.environ["KATRAIN_DATABASE_PATH"] = db_path
    if os.path.exists(db_path):
        os.remove(db_path)

    app = create_app(enable_engine=False)

    # Set up local SQLite with user repo
    test_engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(bind=test_engine)
    repo = SQLAlchemyUserRepository(TestSessionLocal)
    app.state.user_repo = repo

    # Mock RemoteAPIClient (marks this as board mode)
    mock_client = MagicMock()
    mock_client.login = AsyncMock()
    mock_client.register = AsyncMock()
    mock_client._refresh_access_token = AsyncMock(return_value=True)
    mock_client.clear_tokens = MagicMock()
    mock_client._access_token = "remote_access_token"
    mock_client._refresh_token = "remote_refresh_token"
    app.state.remote_client = mock_client

    # Session management (needed for logout)
    app.state.lobby_manager = LobbyManager()
    app.state.matchmaker = Matchmaker()
    app.state.session_manager = SessionManager()
    app.state.game_repo = None

    yield app

    if os.path.exists(db_path):
        os.remove(db_path)


# ── Login Tests ──


@pytest.mark.asyncio
async def test_board_login_creates_shadow_user(board_app):
    """Board-mode login: forward to remote, create shadow user, return local tokens."""
    board_app.state.remote_client.login.return_value = {
        "access_token": "remote_at",
        "refresh_token": "remote_rt",
        "token_type": "bearer",
    }

    with patch("katrain.web.core.credentials.save_refresh_token") as mock_save:
        async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as ac:
            resp = await ac.post("/api/v1/auth/login", json={"username": "alice", "password": "pass123"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert "access_token" in data
    assert "refresh_token" in data

    # Verify remote_client.login was called
    board_app.state.remote_client.login.assert_called_once_with("alice", "pass123")

    # Verify remote refresh_token was persisted
    mock_save.assert_called_once_with(settings.DEVICE_ID, "remote_rt")

    # Verify local token is signed with local SECRET_KEY
    payload = jwt.decode(data["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "alice"
    assert payload["type"] == "access"

    # Verify shadow user was created in local DB
    shadow = board_app.state.user_repo.get_user_by_username("alice")
    assert shadow is not None
    assert shadow["hashed_password"] == SHADOW_USER_NO_LOCAL_AUTH


@pytest.mark.asyncio
async def test_board_login_reuses_shadow_user(board_app):
    """Repeat login reuses existing shadow user, not duplicates."""
    board_app.state.remote_client.login.return_value = {
        "access_token": "remote_at",
        "refresh_token": "remote_rt",
        "token_type": "bearer",
    }

    with patch("katrain.web.core.credentials.save_refresh_token"):
        async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as ac:
            await ac.post("/api/v1/auth/login", json={"username": "bob", "password": "pass"})
            resp2 = await ac.post("/api/v1/auth/login", json={"username": "bob", "password": "pass"})

    assert resp2.status_code == 200
    # Should still be one user, not two
    users = board_app.state.user_repo.list_users()
    bob_users = [u for u in users if u["username"] == "bob"]
    assert len(bob_users) == 1


@pytest.mark.asyncio
async def test_board_login_remote_401(board_app):
    """Remote returns 401 → local 401."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    board_app.state.remote_client.login.side_effect = httpx.HTTPStatusError(
        "401 Unauthorized", request=MagicMock(), response=mock_resp
    )

    async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/auth/login", json={"username": "bad", "password": "wrong"})

    assert resp.status_code == 401

    # No shadow user should be created
    assert board_app.state.user_repo.get_user_by_username("bad") is None


@pytest.mark.asyncio
async def test_board_login_remote_unreachable(board_app):
    """Remote unreachable → 503 Service Unavailable."""
    board_app.state.remote_client.login.side_effect = httpx.ConnectError("Connection refused")

    async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/auth/login", json={"username": "alice", "password": "pass"})

    assert resp.status_code == 503
    assert "Cannot connect to remote server" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_board_login_remote_timeout(board_app):
    """Remote timeout → 503 Service Unavailable."""
    board_app.state.remote_client.login.side_effect = httpx.TimeoutException("Timeout")

    async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/auth/login", json={"username": "alice", "password": "pass"})

    assert resp.status_code == 503


# ── Register Tests ──


@pytest.mark.asyncio
async def test_board_register_forwards_to_remote(board_app):
    """Board-mode register: forward to remote, return remote user."""
    board_app.state.remote_client.register.return_value = {
        "id": 42,
        "uuid": "abc123",
        "username": "newuser",
        "rank": "20k",
        "credits": 10000.0,
    }

    async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/auth/register", json={"username": "newuser", "password": "pass"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "newuser"
    board_app.state.remote_client.register.assert_called_once_with("newuser", "pass")


@pytest.mark.asyncio
async def test_board_register_remote_error(board_app):
    """Remote register error → forwarded status code."""
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"detail": "User already exists"}
    board_app.state.remote_client.register.side_effect = httpx.HTTPStatusError(
        "400 Bad Request", request=MagicMock(), response=mock_resp
    )

    async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/auth/register", json={"username": "dup", "password": "pass"})

    assert resp.status_code == 400
    assert "User already exists" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_board_register_remote_unreachable(board_app):
    """Remote unreachable during register → 503."""
    board_app.state.remote_client.register.side_effect = httpx.ConnectError("Connection refused")

    async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/auth/register", json={"username": "u", "password": "p"})

    assert resp.status_code == 503


# ── Refresh Tests ──


@pytest.mark.asyncio
async def test_board_refresh_issues_local_token(board_app):
    """Board-mode refresh: validate local refresh_token, issue new local access_token."""
    # Create shadow user first
    repo = board_app.state.user_repo
    repo.create_user(username="charlie", hashed_password=SHADOW_USER_NO_LOCAL_AUTH)

    # Create a local refresh_token
    local_refresh = create_refresh_token(data={"sub": "charlie"})

    async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/auth/refresh", json={"refresh_token": local_refresh})

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data

    # Verify new local access_token
    payload = jwt.decode(data["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "charlie"
    assert payload["type"] == "access"

    # Verify remote refresh was attempted (best-effort)
    board_app.state.remote_client._refresh_access_token.assert_called_once()


@pytest.mark.asyncio
async def test_board_refresh_remote_failure_still_succeeds(board_app):
    """Remote refresh failure doesn't block local token issuance."""
    repo = board_app.state.user_repo
    repo.create_user(username="dave", hashed_password=SHADOW_USER_NO_LOCAL_AUTH)
    local_refresh = create_refresh_token(data={"sub": "dave"})

    # Remote refresh fails
    board_app.state.remote_client._refresh_access_token.side_effect = Exception("Network error")

    async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/auth/refresh", json={"refresh_token": local_refresh})

    # Should still succeed with new local token
    assert resp.status_code == 200
    assert "access_token" in resp.json()


# ── Logout Tests ──


@pytest.mark.asyncio
async def test_board_logout_clears_remote_tokens(board_app):
    """Board-mode logout: clear remote tokens + delete credentials."""
    # Create shadow user and get a local token
    repo = board_app.state.user_repo
    repo.create_user(username="eve", hashed_password=SHADOW_USER_NO_LOCAL_AUTH)
    local_token = create_access_token(data={"sub": "eve"})

    with patch("katrain.web.core.credentials.delete_credentials") as mock_delete:
        async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as ac:
            resp = await ac.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {local_token}"})

    assert resp.status_code == 200
    board_app.state.remote_client.clear_tokens.assert_called_once()
    mock_delete.assert_called_once_with(settings.DEVICE_ID)


# ── get_current_user works with shadow user ──


@pytest.mark.asyncio
async def test_board_me_works_with_shadow_user(board_app):
    """get_current_user resolves shadow user from local token."""
    repo = board_app.state.user_repo
    repo.create_user(username="frank", hashed_password=SHADOW_USER_NO_LOCAL_AUTH)
    local_token = create_access_token(data={"sub": "frank"})

    async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {local_token}"})

    assert resp.status_code == 200
    assert resp.json()["username"] == "frank"
