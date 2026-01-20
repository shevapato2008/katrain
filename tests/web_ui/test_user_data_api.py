import pytest
from httpx import AsyncClient, ASGITransport
from katrain.web.server import create_app
from katrain.web.core.config import settings
from katrain.web.core.db import SessionLocal, Base, engine
from katrain.web.core.models_db import User, Game
import os

# Override setting for test
settings.DATABASE_URL = "sqlite:///./test_user_data.db"

@pytest.fixture
def app():
    # Setup test DB
    if os.path.exists("./test_user_data.db"):
        os.remove("./test_user_data.db")
    
    # Re-bind engine to new test DB url if needed (though SQLAlchemy engine is usually global)
    # Ideally we'd use a session override, but for simple integration test:
    from sqlalchemy import create_engine
    test_engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    
    app = create_app(enable_engine=False)
    
    # Inject the repo that uses this engine
    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.core.game_repo import GameRepository
    from sqlalchemy.orm import sessionmaker
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    
    repo = SQLAlchemyUserRepository(TestSessionLocal)
    game_repo = GameRepository(TestSessionLocal)
    app.state.user_repo = repo
    app.state.game_repo = game_repo
    
    yield app
    
    # Teardown
    if os.path.exists("./test_user_data.db"):
        os.remove("./test_user_data.db")

@pytest.mark.asyncio
async def test_user_profile_data(app):
    # 1. Create User
    repo = app.state.user_repo
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = pwd_context.hash("password")
    repo.create_user("testplayer", hashed)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 2. Login
        login_resp = await ac.post("/api/v1/auth/login", json={
            "username": "testplayer",
            "password": "password"
        })
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Get Me (Check defaults)
        resp = await ac.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testplayer"
        assert data["rank"] == "20k"
        assert data["credits"] == 10000.0

@pytest.mark.asyncio
async def test_cloud_games_crud(app):
    # 1. Create User
    repo = app.state.user_repo
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = pwd_context.hash("password")
    repo.create_user("testplayer", hashed)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        login_resp = await ac.post("/api/v1/auth/login", json={
            "username": "testplayer",
            "password": "password"
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. List Games (Empty)
        resp = await ac.get("/api/v1/games/", headers=headers)
        assert resp.status_code == 200
        games = resp.json()
        assert len(games) == 0

        # 3. Save Game
        resp = await ac.post("/api/v1/games/", headers=headers, json={
            "sgf_content": "(;GM[1]FF[4]CA[UTF-8]AP[KaTrain:1.17.1];B[dp];W[pd])",
            "result": "B+R",
            "game_type": "free"
        })
        assert resp.status_code == 200
        game = resp.json()
        assert game["result"] == "B+R"
        assert game["id"] is not None
        
        # 4. List Games (1 item)
        resp = await ac.get("/api/v1/games/", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1
