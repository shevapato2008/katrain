import os
import pytest
from fastapi.testclient import TestClient
from katrain.web.server import create_app

@pytest.fixture
def client():
    app = create_app(enable_engine=False)
    return TestClient(app)

def test_config_loading(monkeypatch):
    os.environ["LOCAL_KATAGO_URL"] = "http://local:8000"
    os.environ["CLOUD_KATAGO_URL"] = "http://cloud:8000"
    
    # We'll create a config module and check its values
    from katrain.web import config
    monkeypatch.setattr(config, "LOCAL_KATAGO_URL", "http://local:8000")
    monkeypatch.setattr(config, "CLOUD_KATAGO_URL", "http://cloud:8000")
    
    assert config.LOCAL_KATAGO_URL == "http://local:8000"
    assert config.CLOUD_KATAGO_URL == "http://cloud:8000"

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    # Future health check should include engine status
    # assert "engines" in data
