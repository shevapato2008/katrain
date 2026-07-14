import pytest
from fastapi import Depends, FastAPI
from httpx import AsyncClient, ASGITransport
from katrain.web.server import create_app
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
async def test_get_me_missing_creds_401_contract(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_get_me_non_bearer_header_401(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/auth/me", headers={"Authorization": "Basic abc123"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_get_me_garbage_cookie_401(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies={"sb_token": "not-a-jwt"}
    ) as ac:
        response = await ac.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


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
async def test_cookie_authoritative_over_header(app):
    """The shared SSO cookie wins over a stale Authorization header."""
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

    # User B is signed in through the shared Box SSO cookie, while a stale client
    # Authorization header still names user A.
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies={"sb_token": cke_tok}
    ) as ac:
        response = await ac.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {hdr_tok}"})

    assert response.status_code == 200
    assert response.json()["username"] == "cke_user"


@pytest.mark.asyncio
async def test_admin_dep_rejects_cookie_only(app):
    """Admin dependencies must not accept the ambient Box SSO cookie."""
    from katrain.web.api.v1.endpoints.auth import get_current_admin_user

    probe_app = FastAPI()
    probe_app.state.user_repo = app.state.user_repo

    @probe_app.get("/admin-probe")
    async def admin_probe(current_user=Depends(get_current_admin_user)):
        return {"username": current_user.username}

    repo = app.state.user_repo
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = pwd_context.hash("testpassword")
    repo.create_user("cookie_admin", hashed)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (
            await ac.post("/api/v1/auth/login", json={"username": "cookie_admin", "password": "testpassword"})
        ).json()["access_token"]

    async with AsyncClient(
        transport=ASGITransport(app=probe_app), base_url="http://test", cookies={"sb_token": token}
    ) as ac:
        response = await ac.get("/admin-probe")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_optional_dep_identifies_user_from_cookie(app):
    from katrain.web.api.v1.endpoints.auth import get_current_user_optional

    probe_app = FastAPI()
    probe_app.state.user_repo = app.state.user_repo

    @probe_app.get("/optional-auth")
    async def optional_auth_probe(current_user=Depends(get_current_user_optional)):
        return {"username": current_user.username if current_user else None}

    repo = app.state.user_repo
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = pwd_context.hash("testpassword")
    repo.create_user("optional_cookie_user", hashed)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (
            await ac.post(
                "/api/v1/auth/login", json={"username": "optional_cookie_user", "password": "testpassword"}
            )
        ).json()["access_token"]

    async with AsyncClient(
        transport=ASGITransport(app=probe_app), base_url="http://test", cookies={"sb_token": token}
    ) as ac:
        response = await ac.get("/optional-auth")

    assert response.status_code == 200
    assert response.json() == {"username": "optional_cookie_user"}


@pytest.mark.asyncio
async def test_optional_dep_returns_none_without_credentials(app):
    from katrain.web.api.v1.endpoints.auth import get_current_user_optional

    probe_app = FastAPI()
    probe_app.state.user_repo = app.state.user_repo

    @probe_app.get("/optional-auth")
    async def optional_auth_probe(current_user=Depends(get_current_user_optional)):
        return {"username": current_user.username if current_user else None}

    async with AsyncClient(transport=ASGITransport(app=probe_app), base_url="http://test") as ac:
        response = await ac.get("/optional-auth")

    assert response.status_code == 200
    assert response.json() == {"username": None}
