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
async def test_cookie_takes_precedence_over_header(app):
    """Box-SSO F3: the shared sb_token cookie is the AUTHORITATIVE box identity and
    wins over a (stale/other) Authorization header. On switch-user the launcher writes
    user B's fresh cookie while katrain's localStorage may still hold user A's stale
    Bearer; cookie-first stops A from being recorded for B's play (cross-account bug)."""
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

    # Stale/other user's Bearer header present, but the authoritative box cookie is cke_user.
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies={"sb_token": cke_tok}
    ) as ac:
        response = await ac.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {hdr_tok}"})

    assert response.status_code == 200
    assert response.json()["username"] == "cke_user"  # cookie wins (F3 authoritative)


def _make_probe_app(repo, dep):
    """A fresh app (NO SPA catch-all) exposing one route behind `dep`, sharing the test
    repo. katrain's real app mounts StaticFiles at '/' (server.py), which shadows any
    route appended post-construction, so a dependency probe needs its own bare app.
    `dep` resolves `request.app.state.user_repo` — set here to the shared test repo."""
    from fastapi import FastAPI, Depends

    probe = FastAPI()
    probe.state.user_repo = repo

    @probe.get("/probe")
    async def _probe(u=Depends(dep)):
        return {"username": getattr(u, "username", None) if u is not None else None}

    return probe


async def _login_token(app, username: str) -> str:
    repo = app.state.user_repo
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    try:
        repo.create_user(username, pwd_context.hash("testpassword"))
    except ValueError:
        pass
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return (
            await ac.post("/api/v1/auth/login", json={"username": username, "password": "testpassword"})
        ).json()["access_token"]


# ---- F1 mitigation: broadcast sb_token cookie must NEVER reach a privileged endpoint ----
@pytest.mark.asyncio
async def test_admin_dep_rejects_cookie_only(app):
    """F1: get_current_admin_user is strict header-only. A cookie-only request (no
    Authorization header) — even with a perfectly valid token — 401s at dependency
    resolution, so the 127.0.0.1-broadcast cookie can never grant admin."""
    from katrain.web.api.v1.endpoints.auth import get_current_admin_user

    tok = await _login_token(app, "admin_probe_user")
    probe = _make_probe_app(app.state.user_repo, get_current_admin_user)

    # Only the cookie, NO Authorization header → strict header-only dep 401s.
    async with AsyncClient(
        transport=ASGITransport(app=probe), base_url="http://test", cookies={"sb_token": tok}
    ) as ac:
        r = await ac.get("/probe")

    assert r.status_code == 401  # cookie can't reach admin, even with a valid token


@pytest.mark.asyncio
async def test_optional_dep_identifies_user_from_cookie(app):
    """get_current_user_optional also honors the cookie: no creds → 200/None;
    cookie present → identifies the user (same _resolve_token as get_current_user)."""
    from katrain.web.api.v1.endpoints.auth import get_current_user_optional

    tok = await _login_token(app, "opt_user")
    probe = _make_probe_app(app.state.user_repo, get_current_user_optional)

    async with AsyncClient(transport=ASGITransport(app=probe), base_url="http://test") as ac:
        anon = await ac.get("/probe")
    async with AsyncClient(
        transport=ASGITransport(app=probe), base_url="http://test", cookies={"sb_token": tok}
    ) as ac:
        withck = await ac.get("/probe")

    assert anon.status_code == 200 and anon.json()["username"] is None
    assert withck.status_code == 200 and withck.json()["username"] == "opt_user"


# ---- F5: 401 contract characterization (the shared-dep rewrite must not silently drift) ----
@pytest.mark.asyncio
async def test_get_me_missing_creds_401_contract(app):
    """No creds → 401 + WWW-Authenticate: Bearer + detail 'Not authenticated'
    (the manually-raised 401 must match the old auto_error behavior)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/v1/auth/me")
    assert r.status_code == 401
    assert r.headers.get("www-authenticate") == "Bearer"
    assert r.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_get_me_non_bearer_header_401(app):
    """A non-Bearer Authorization (auto_error=False treats it as no token) → 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/v1/auth/me", headers={"Authorization": "Basic Zm9vOmJhcg=="})
    assert r.status_code == 401
    assert r.headers.get("www-authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_get_me_garbage_cookie_401(app):
    """An invalid sb_token cookie → get_user_from_token can't decode → 401."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies={"sb_token": "not-a-jwt"}
    ) as ac:
        r = await ac.get("/api/v1/auth/me")
    assert r.status_code == 401
