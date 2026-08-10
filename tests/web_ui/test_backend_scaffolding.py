import pytest
from fastapi.testclient import TestClient
from katrain.web.core.config import Settings
from katrain.web.server import create_app


@pytest.fixture
def client():
    app = create_app(enable_engine=False)
    return TestClient(app)


def test_engine_urls_come_from_the_environment(monkeypatch):
    """Settings reads the engine URLs from the environment in its own __init__.

    Construct a fresh Settings rather than poking at the module-level singleton: patching
    the singleton's attributes would pass even if the env plumbing were deleted outright.
    """
    monkeypatch.setenv("LOCAL_KATAGO_URL", "http://local:8000")
    monkeypatch.setenv("CLOUD_KATAGO_URL", "http://cloud:8000")

    loaded = Settings()

    assert loaded.LOCAL_KATAGO_URL == "http://local:8000"
    assert loaded.CLOUD_KATAGO_URL == "http://cloud:8000"


def test_health_check(client):
    """The unversioned /health must answer exactly like /api/v1/health.

    It is a thin alias, but the two drifted once already: the v1 handler grew a `request`
    parameter and this alias kept calling it bare, so /health 500'd in production while
    /api/v1/health stayed 200. Asserting on the body -- not just the status -- is what
    makes that drift visible here instead of on a deployed box.
    """
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "engines" in data

    versioned = client.get("/api/v1/health")
    assert versioned.status_code == 200
    assert set(versioned.json()) == set(data)
