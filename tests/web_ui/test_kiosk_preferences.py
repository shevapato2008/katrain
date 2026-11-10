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


def test_device_preferences_project_only_canonical_appearance(tmp_path, monkeypatch):
    import json

    path = tmp_path / "settings.json"
    monkeypatch.setenv("SMARTBOX_SETTINGS_PATH", str(path))
    app = FastAPI()
    app.include_router(kiosk_preferences.router, prefix="/api/v1/kiosk-preferences")
    client = TestClient(app)
    url = "/api/v1/kiosk-preferences/device"
    assert client.get(url).json() == {"language": "zh", "font": "wenkai"}
    for language in ("zh", "zh-TW", "en", "ja", "ko"):
        for font in ("wenkai", "kai", "daoli", "hei"):
            path.write_text(json.dumps({"language": language, "font": font, "volume": 17, "secret": "hidden"}))
            response = client.get(url)
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            assert response.json() == {"language": language, "font": font}
    path.write_text('{"language":"old","font":null}')
    assert client.get(url).json() == {"language": "zh", "font": "wenkai"}
    path.write_text('{"language":"ko"}')
    assert client.get(url).json() == {"language": "ko", "font": "wenkai"}


def test_device_preferences_existing_unreadable_data_is_not_a_default(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setenv("SMARTBOX_SETTINGS_PATH", str(path))
    app = FastAPI()
    app.include_router(kiosk_preferences.router, prefix="/api/v1/kiosk-preferences")
    client = TestClient(app)
    for content in ("{broken", "[]", "\udcff"):
        path.write_bytes(content.encode("utf-8", errors="surrogatepass"))
        response = client.get("/api/v1/kiosk-preferences/device")
        assert response.status_code == 503
    path.unlink()
    path.mkdir()
    assert client.get("/api/v1/kiosk-preferences/device").status_code == 503
