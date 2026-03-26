import pytest
from httpx import AsyncClient, ASGITransport
from katrain.web.server import create_app
from katrain.web.core.config import settings
from katrain.web.core.db import Base
from katrain.web.core.models_db import User, UserGame
import os

# Override setting for test
settings.DATABASE_URL = "sqlite:///./test_user_data.db"

@pytest.fixture
def app():
    # Setup test DB
    if os.path.exists("./test_user_data.db"):
        os.remove("./test_user_data.db")

    from sqlalchemy import create_engine
    test_engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)

    app = create_app(enable_engine=False)

    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.core.game_repo import GameRepository
    from katrain.web.core.user_game_repo import UserGameRepository, UserGameAnalysisRepository
    from sqlalchemy.orm import sessionmaker
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    repo = SQLAlchemyUserRepository(TestSessionLocal)
    game_repo = GameRepository(TestSessionLocal)
    user_game_repo = UserGameRepository(TestSessionLocal)
    user_game_analysis_repo = UserGameAnalysisRepository(TestSessionLocal)
    app.state.user_repo = repo
    app.state.game_repo = game_repo
    app.state.user_game_repo = user_game_repo
    app.state.user_game_analysis_repo = user_game_analysis_repo

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
async def test_user_games_crud(app):
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

        # 2. List User Games (Empty)
        resp = await ac.get("/api/v1/user-games/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

        # 3. Create User Game
        resp = await ac.post("/api/v1/user-games/", headers=headers, json={
            "sgf_content": "(;GM[1]FF[4]CA[UTF-8]AP[KaTrain:1.17.1];B[dp];W[pd])",
            "source": "research",
            "title": "Test Research Game",
            "player_black": "Alice",
            "player_white": "Bob",
            "move_count": 2,
        })
        assert resp.status_code == 200
        game = resp.json()
        assert game["title"] == "Test Research Game"
        assert game["id"] is not None
        game_id = game["id"]

        # 4. List User Games (1 item)
        resp = await ac.get("/api/v1/user-games/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

        # 5. Get Game Detail
        resp = await ac.get(f"/api/v1/user-games/{game_id}", headers=headers)
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["sgf_content"] == "(;GM[1]FF[4]CA[UTF-8]AP[KaTrain:1.17.1];B[dp];W[pd])"

        # 6. Update Game
        resp = await ac.put(f"/api/v1/user-games/{game_id}", headers=headers, json={
            "title": "Updated Title",
        })
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

        # 7. Delete Game
        resp = await ac.delete(f"/api/v1/user-games/{game_id}", headers=headers)
        assert resp.status_code == 200

        # 8. Verify deletion
        resp = await ac.get(f"/api/v1/user-games/{game_id}", headers=headers)
        assert resp.status_code == 404

@pytest.mark.asyncio
async def test_user_game_analysis_api(app):
    """Test analysis data endpoints."""
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

        # Create a game
        resp = await ac.post("/api/v1/user-games/", headers=headers, json={
            "sgf_content": "(;FF[4]SZ[19];B[pd];W[dp])",
            "source": "research",
        })
        game_id = resp.json()["id"]

        # Insert analysis data directly via repo
        analysis_repo = app.state.user_game_analysis_repo
        analysis_repo.upsert(game_id=game_id, move_number=0, winrate=0.5, score_lead=0.0, visits=500)
        analysis_repo.upsert(game_id=game_id, move_number=1, winrate=0.52, score_lead=1.2, visits=500, move="Q16", actual_player="B")

        # Get all analysis
        resp = await ac.get(f"/api/v1/user-games/{game_id}/analysis", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["move_number"] == 0
        assert data[1]["move_number"] == 1

        # Get single move analysis
        resp = await ac.get(f"/api/v1/user-games/{game_id}/analysis/1", headers=headers)
        assert resp.status_code == 200
        move = resp.json()
        assert move["move"] == "Q16"
        assert move["actual_player"] == "B"

        # Get nonexistent move
        resp = await ac.get(f"/api/v1/user-games/{game_id}/analysis/99", headers=headers)
        assert resp.status_code == 404
