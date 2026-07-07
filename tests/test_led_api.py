"""HTTP-layer tests for the LED endpoints (web env). No serial/board required."""

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints import led


class FakeLed:
    def __init__(self, connected=True):
        self._connected = connected
        self.calls = []

    def set_points(self, points, *, strict=False):
        self.calls.append(("set_points", points, strict))
        return {"ok": True, "connected": self._connected, "shown_at": None, "errors": []}

    def clear(self, *, strict=False):
        self.calls.append(("clear", strict))
        return {"ok": True, "connected": self._connected, "shown_at": None, "errors": []}

    def is_connected(self):
        return self._connected


def _client(led_obj):
    app = FastAPI()
    app.include_router(led.router, prefix="/led")
    if led_obj is not None:
        app.state.led = led_obj
    return TestClient(app)


class TestLedEndpoints:
    def test_point(self):
        fake = FakeLed()
        c = _client(fake)
        r = c.post("/led/point", json={"row": 3, "col": 3, "color": "black"})
        assert r.status_code == 200 and r.json()["ok"] is True
        assert fake.calls[0] == ("set_points", [{"row": 3, "col": 3, "color": "black"}], False)

    def test_points(self):
        fake = FakeLed()
        c = _client(fake)
        r = c.post("/led/points", json={"points": [{"row": 0, "col": 0, "color": "remove"}]})
        assert r.status_code == 200
        assert fake.calls[0][2] is False  # UI path is non-strict

    def test_clear_and_status(self):
        fake = FakeLed()
        c = _client(fake)
        assert c.post("/led/clear").status_code == 200
        assert c.get("/led/status").json() == {"connected": True}

    def test_404_when_not_enabled(self):
        c = _client(None)
        assert c.post("/led/clear").status_code == 404

    def test_422_out_of_range(self):
        c = _client(FakeLed())
        assert c.post("/led/point", json={"row": 19, "col": 0, "color": "black"}).status_code == 422
