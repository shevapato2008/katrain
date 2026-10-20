from fastapi import FastAPI
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints import kiosk_preferences


def test_typography_preference_persists_across_store_reload(tmp_path, monkeypatch):
    monkeypatch.setattr(kiosk_preferences, "TYPOGRAPHY_PATH", tmp_path / "kiosk-typography.json")
    app = FastAPI()
    app.include_router(kiosk_preferences.router, prefix="/api/v1/kiosk-preferences")
    client = TestClient(app)

    url = "/api/v1/kiosk-preferences/typography"
    assert client.get(url).json() == {"font": "wenkai", "size": "large"}
    assert client.put(url, json={"font": "lishu", "size": "medium"}).json() == {
        "font": "lishu",
        "size": "medium",
    }
    kiosk_preferences._store = None
    assert client.get(url).json() == {"font": "lishu", "size": "medium"}
    assert client.put(url, json={"font": "heiti", "size": "small"}).status_code == 200
    kiosk_preferences._store = None
    assert client.get(url).json() == {"font": "heiti", "size": "small"}


def test_typography_preference_rejects_unknown_choices(tmp_path, monkeypatch):
    monkeypatch.setattr(kiosk_preferences, "TYPOGRAPHY_PATH", tmp_path / "kiosk-typography.json")
    app = FastAPI()
    app.include_router(kiosk_preferences.router, prefix="/api/v1/kiosk-preferences")
    client = TestClient(app)

    url = "/api/v1/kiosk-preferences/typography"
    assert client.put(url, json={"font": "unknown", "size": "large"}).status_code == 422
    assert client.put(url, json={"font": "wenkai", "size": "huge"}).status_code == 422
    assert client.get(url).json() == {"font": "wenkai", "size": "large"}
