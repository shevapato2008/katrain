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
    # as AsyncClient/ASGITransport doesn't trigger lifespan automatically
    from katrain.web.core.auth import SQLiteUserRepository
    repo = SQLiteUserRepository("test_auth_api.db")
    repo.init_db()
    app.state.user_repo = repo
    
    return app

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
        pass # Already exists

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/auth/login", json={
            "username": "testuser",
            "password": "testpassword"
        })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_failure(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/auth/login", json={
            "username": "testuser",
            "password": "wrongpassword"
        })
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
        login_resp = await ac.post("/api/v1/auth/login", json={
            "username": "me_user",
            "password": "testpassword"
        })
        token = login_resp.json()["access_token"]

        # Test /me
        response = await ac.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
    
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "me_user"

@pytest.mark.asyncio
async def test_get_me_unauthorized(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/auth/me")
    assert response.status_code == 401
