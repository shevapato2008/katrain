import pytest
from fastapi.testclient import TestClient
from katrain.web.api.v1.endpoints import health as health_endpoint
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


@pytest.mark.parametrize(
    ("katago_status", "expected_local"),
    [(200, "reachable"), (503, "error_503")],
)
def test_versioned_health_maps_local_katago_http_status(client, monkeypatch, katago_status, expected_local):
    class StubResponse:
        status_code = katago_status

    class StubAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, _url):
            return StubResponse()

    monkeypatch.setattr(health_endpoint.httpx, "AsyncClient", lambda **_kwargs: StubAsyncClient())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["engines"]["local"] == expected_local
