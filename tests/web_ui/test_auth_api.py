import pytest
from httpx import AsyncClient, ASGITransport
from katrain.web.server import create_app
from katrain.web.core.config import settings
import os


@pytest.fixture
def app():
    # Use a test database
    os.environ["KATRAIN_DATABASE_PATH"] = "test_auth_api.db"
    # Ensure any existing test DB is removed
    if os.path.exists("test_auth_api.db"):
        os.remove("test_auth_api.db")

    app = create_app(enable_engine=False)

    # Manually trigger the repo initialization for tests
    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.core import models_db
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    test_engine = create_engine("sqlite:///test_auth_api.db", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(bind=test_engine)
    repo = SQLAlchemyUserRepository(TestSessionLocal)
    app.state.user_repo = repo

    yield app

    if os.path.exists("test_auth_api.db"):
        os.remove("test_auth_api.db")


@pytest.mark.asyncio
async def test_login_success(app):
    # Setup: ensure a user exists
    repo = app.state.user_repo
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = pwd_context.hash("testpassword")
    try:
        repo.create_user("testuser", hashed)
    except ValueError:
        pass  # Already exists

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/auth/login", json={"username": "testuser", "password": "testpassword"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_failure(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/auth/login", json={"username": "testuser", "password": "wrongpassword"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me(app):
    # Setup: get a token
    repo = app.state.user_repo
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = pwd_context.hash("testpassword")
    try:
        repo.create_user("me_user", hashed)
    except ValueError:
        pass

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Login first
        login_resp = await ac.post("/api/v1/auth/login", json={"username": "me_user", "password": "testpassword"})
        token = login_resp.json()["access_token"]

        # Test /me
        response = await ac.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "me_user"


@pytest.mark.asyncio
async def test_get_me_unauthorized(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_sso_cookie(app):
    """Box SSO: /me authenticates from the shared `sb_token` cookie when no
    Authorization header is present (launcher sets this 127.0.0.1 cookie)."""
    repo = app.state.user_repo
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = pwd_context.hash("testpassword")
    try:
        repo.create_user("cookie_user", hashed)
    except ValueError:
        pass

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (
            await ac.post("/api/v1/auth/login", json={"username": "cookie_user", "password": "testpassword"})
        ).json()["access_token"]

    # No Authorization header — token only in the shared SSO cookie (client-level).
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies={"sb_token": token}
    ) as ac:
        response = await ac.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["username"] == "cookie_user"


@pytest.mark.asyncio
async def test_bearer_header_takes_precedence_over_cookie(app):
    """A valid Authorization header wins over any (stale/other) shared cookie."""
    repo = app.state.user_repo
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = pwd_context.hash("testpassword")
    for u in ("hdr_user", "cke_user"):
        try:
            repo.create_user(u, hashed)
        except ValueError:
            pass

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        hdr_tok = (
            await ac.post("/api/v1/auth/login", json={"username": "hdr_user", "password": "testpassword"})
        ).json()["access_token"]
        cke_tok = (
            await ac.post("/api/v1/auth/login", json={"username": "cke_user", "password": "testpassword"})
        ).json()["access_token"]

    # Stale/other user's token in the shared cookie, but a valid Bearer header present.
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies={"sb_token": cke_tok}
    ) as ac:
        response = await ac.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {hdr_tok}"})

    assert response.status_code == 200
    assert response.json()["username"] == "hdr_user"
