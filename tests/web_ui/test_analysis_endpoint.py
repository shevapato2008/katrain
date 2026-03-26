import pytest
import respx
from httpx import AsyncClient, ASGITransport, Response
from katrain.web.server import create_app
from katrain.web.core.config import settings
import os

@pytest.fixture
def app():
    # Use a test database
    os.environ["KATRAIN_DATABASE_PATH"] = "test_analysis.db"
    if os.path.exists("test_analysis.db"):
        os.remove("test_analysis.db")
    
    # Configure mock URLs
    settings.LOCAL_KATAGO_URL = "http://local-engine:8000"
    settings.CLOUD_KATAGO_URL = "http://cloud-engine:8000"
    
    app = create_app(enable_engine=False)
    
    # Manually trigger the repo initialization for tests
    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.core import models_db
    from sqlalchemy import create_engine as _create_engine
    from sqlalchemy.orm import sessionmaker
    test_engine = _create_engine("sqlite:///test_analysis.db", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(bind=test_engine)
    repo = SQLAlchemyUserRepository(TestSessionLocal)
    app.state.user_repo = repo

    # Initialize Router
    from katrain.web.core.engine_client import KataGoClient
    from katrain.web.core.router import RequestRouter
    local_client = KataGoClient(url=settings.LOCAL_KATAGO_URL)
    cloud_client = KataGoClient(url=settings.CLOUD_KATAGO_URL)
    app.state.router = RequestRouter(local_client=local_client, cloud_client=cloud_client)

    return app

@pytest.mark.asyncio
@respx.mock
async def test_analyze_routing_integration(app):
    # Setup: ensure a user exists and get token
    from katrain.web.core.auth import get_password_hash
    repo = app.state.user_repo
    repo.create_user("testuser", get_password_hash("testpassword"))

    # Create a session to test against
    manager = app.state.session_manager
    session = manager.create_session()
    sid = session.session_id

    # Mock both engines
    respx.post("http://local-engine:8000/analyze").mock(return_value=Response(200, json={"engine": "local"}))
    respx.post("http://cloud-engine:8000/analyze").mock(return_value=Response(200, json={"engine": "cloud"}))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Login
        login_resp = await ac.post("/api/v1/auth/login", json={
            "username": "testuser",
            "password": "testpassword"
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Test Play Request (routes to local)
        resp_play = await ac.post("/api/v1/analysis/analyze", 
                                 json={"session_id": sid, "payload": {"is_analysis": False, "id": "play"}}, 
                                 headers=headers)
        assert resp_play.status_code == 200
        assert resp_play.json()["engine"] == "local"
        assert session.katrain.last_engine == "local"

        # Test Analysis Request (routes to cloud)
        resp_analysis = await ac.post("/api/v1/analysis/analyze", 
                                     json={"session_id": sid, "payload": {"is_analysis": True, "id": "analysis"}}, 
                                     headers=headers)
        assert resp_analysis.status_code == 200
        assert resp_analysis.json()["engine"] == "cloud"
        assert session.katrain.last_engine == "cloud"

@pytest.mark.asyncio
async def test_analyze_unauthorized(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/analysis/analyze", json={})
    assert response.status_code == 401
