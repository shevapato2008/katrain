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
    from katrain.web.core.auth import SQLiteUserRepository
    repo = SQLiteUserRepository("test_analysis.db")
    repo.init_db()
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
                                 json={"is_analysis": False, "id": "play"}, 
                                 headers=headers)
        assert resp_play.status_code == 200
        assert resp_play.json()["engine"] == "local"

        # Test Analysis Request (routes to cloud)
        resp_analysis = await ac.post("/api/v1/analysis/analyze", 
                                     json={"is_analysis": True, "id": "analysis"}, 
                                     headers=headers)
        assert resp_analysis.status_code == 200
        assert resp_analysis.json()["engine"] == "cloud"

@pytest.mark.asyncio
async def test_analyze_unauthorized(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/analysis/analyze", json={})
    assert response.status_code == 401
