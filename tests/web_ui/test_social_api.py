import pytest
import os

# Set environment variable BEFORE importing anything that might use it
os.environ["KATRAIN_DATABASE_URL"] = "sqlite:///test_social_api.db"

from httpx import AsyncClient, ASGITransport
from katrain.web.server import create_app
from katrain.web.core.config import settings

@pytest.fixture
def app():
    # Use a single test database for the whole file
    db_file = "test_social_api.db"
    if os.path.exists(db_file):
        os.remove(db_file)
    
    # Reload modules to ensure they use the correct DB
    import importlib
    from katrain.web.core import config, db, auth
    importlib.reload(config)
    importlib.reload(db)
    importlib.reload(auth)
    
    from katrain.web.core.db import SessionLocal, engine
    from katrain.web.core.models_db import Base
    
    # Ensure tables are created
    Base.metadata.create_all(bind=engine)
    
    app = create_app(enable_engine=False)
    
    # Manually initialize repository for tests
    from katrain.web.core.auth import SQLAlchemyUserRepository
    repo = SQLAlchemyUserRepository(SessionLocal)
    app.state.user_repo = repo
    
    return app

@pytest.mark.asyncio
async def test_follow_unfollow(app):
    # Setup: 2 users
    repo = app.state.user_repo
    from katrain.web.core.auth import get_password_hash
    repo.create_user("user1", get_password_hash("pass1"))
    repo.create_user("user2", get_password_hash("pass2"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Login as user1
        login_resp = await ac.post("/api/v1/auth/login", json={
            "username": "user1",
            "password": "pass1"
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Follow user2
        response = await ac.post("/api/v1/users/follow/user2", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "followed"

        # Check following list
        response = await ac.get("/api/v1/users/following", headers=headers)
        assert response.status_code == 200
        following = response.json()
        assert any(u["username"] == "user2" for u in following)

        # Unfollow user2
        response = await ac.delete("/api/v1/users/follow/user2", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "unfollowed"

        # Check following list again
        response = await ac.get("/api/v1/users/following", headers=headers)
        assert response.status_code == 200
        following = response.json()
        assert not any(u["username"] == "user2" for u in following)

@pytest.mark.asyncio
async def test_followers_list(app):
    # Setup: 2 users
    repo = app.state.user_repo
    from katrain.web.core.auth import get_password_hash
    repo.create_user("follower", get_password_hash("pass1"))
    repo.create_user("target", get_password_hash("pass2"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Login as follower
        login_resp = await ac.post("/api/v1/auth/login", json={
            "username": "follower",
            "password": "pass1"
        })
        token1 = login_resp.json()["access_token"]
        
        # Login as target
        login_resp = await ac.post("/api/v1/auth/login", json={
            "username": "target",
            "password": "pass2"
        })
        token2 = login_resp.json()["access_token"]

        # Follow target
        await ac.post("/api/v1/users/follow/target", headers={"Authorization": f"Bearer {token1}"})

        # Check target's followers
        response = await ac.get("/api/v1/users/followers", headers={"Authorization": f"Bearer {token2}"})
        assert response.status_code == 200
        followers = response.json()
        assert any(u["username"] == "follower" for u in followers)
