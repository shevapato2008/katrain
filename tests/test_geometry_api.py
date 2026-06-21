"""HTTP-layer tests for the geometry lock endpoint (web env). No camera/board."""

import numpy as np
import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints import geometry
from katrain.vision.geometry_lock import GeometryLock


class FakeCapture:
    def __init__(self, frames):
        self._frames = frames

    def grab_burst(self, n=8, interval=0.1):
        return list(self._frames)


class FakeLed:
    def __init__(self):
        self.cleared = False

    def clear(self, *, strict=False):
        self.cleared = True
        return {"ok": True, "connected": True, "shown_at": None, "errors": []}


def _client(capture=None, led=None):
    app = FastAPI()
    app.include_router(geometry.router, prefix="/geometry")
    if capture is not None:
        app.state.capture = capture
    if led is not None:
        app.state.led = led
    return app, TestClient(app)


def _ok_lock():
    return GeometryLock(
        corners=np.zeros((4, 2), np.float32),
        points=np.zeros((19, 19, 2), np.float32),
        xs=np.zeros(19, np.float32),
        ys=np.zeros(19, np.float32),
        M=np.eye(3),
        Minv=np.eye(3),
        out_size=950,
        baseline=np.zeros((19, 19, 3), np.float32),
        confidence=0.9,
        nmatch=18,
        empty_black=0,
        empty_white=0,
    )


class TestGeometryEndpoint:
    def test_404_without_capture(self):
        _, c = _client()
        assert c.post("/geometry/lock").status_code == 404

    def test_status_unlocked(self):
        _, c = _client(capture=FakeCapture([]))
        assert c.get("/geometry/status").json() == {"locked": False}

    def test_no_frames(self):
        _, c = _client(capture=FakeCapture([]), led=FakeLed())
        body = c.post("/geometry/lock").json()
        assert body["ok"] is False and body["reason"] == "no_frames"

    def test_success_path_clears_led_and_sets_state(self, monkeypatch):
        led = FakeLed()
        app, c = _client(capture=FakeCapture([np.zeros((4, 4, 3), np.uint8)]), led=led)
        monkeypatch.setattr("katrain.vision.geometry_lock.lock_geometry_from_frames", lambda frames: _ok_lock())
        monkeypatch.setattr("katrain.vision.geometry_lock.save_geometry_lock", lambda lock, path: None)
        body = c.post("/geometry/lock").json()
        assert body["ok"] is True and body["confidence"] == 0.9
        assert led.cleared is True
        assert getattr(app.state, "geometry", None) is not None

    def test_non_empty_baseline_rejected(self, monkeypatch):
        lock = _ok_lock()
        lock.empty_black = 5  # board not actually empty
        app, c = _client(capture=FakeCapture([np.zeros((4, 4, 3), np.uint8)]), led=FakeLed())
        monkeypatch.setattr("katrain.vision.geometry_lock.lock_geometry_from_frames", lambda frames: lock)
        body = c.post("/geometry/lock").json()
        assert body["ok"] is False and body["reason"] == "non_empty_baseline"

    def test_low_confidence_does_not_replace_existing_lock(self, monkeypatch):
        lock = _ok_lock()
        lock.confidence = 0.4
        saved = False

        def record_save(_lock, _path):
            nonlocal saved
            saved = True

        app, c = _client(capture=FakeCapture([np.zeros((4, 4, 3), np.uint8)]), led=FakeLed())
        monkeypatch.setattr("katrain.vision.geometry_lock.lock_geometry_from_frames", lambda frames: lock)
        monkeypatch.setattr("katrain.vision.geometry_lock.save_geometry_lock", record_save)

        body = c.post("/geometry/lock").json()

        assert body["ok"] is False and body["reason"] == "low_confidence"
        assert saved is False
        assert getattr(app.state, "geometry", None) is None
