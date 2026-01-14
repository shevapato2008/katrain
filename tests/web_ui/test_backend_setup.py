import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from katrain.web.server import create_app

@pytest_asyncio.fixture
async def client():
    app = create_app(enable_engine=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac

@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "engines" in data

@pytest.mark.asyncio
async def test_versioned_health_check(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "engines" in data
    assert "local" in data["engines"]
    assert "cloud" in data["engines"]

def test_settings_override(monkeypatch):
    monkeypatch.setenv("KATRAIN_PORT", "9000")
    # We need to reload the module to see the change if it's evaluated at import time
    # Or we can test if we can create a new Settings instance
    from katrain.web.core.config import Settings
    new_settings = Settings()
    assert new_settings.KATRAIN_PORT == 9000

@pytest.mark.asyncio
async def test_static_mounts(client):
    # Check routes in app
    from fastapi import FastAPI
    app = create_app(enable_engine=False)
    routes = [route.path for route in app.routes]
    assert "/assets/img" in routes
    assert "/assets/fonts" in routes
    assert "/assets/sounds" in routes
