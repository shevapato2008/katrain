"""HTTP-layer tests for the geometry lock endpoint (web env). No camera/board."""

import cv2
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

    def read_frame(self):
        return self._frames[-1].copy() if self._frames else None


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


def _ok_lock(*, out_size=950, M=None, corners=None, points=None):
    return GeometryLock(
        corners=np.asarray(corners if corners is not None else np.zeros((4, 2)), np.float32),
        points=np.asarray(points if points is not None else np.zeros((19, 19, 2)), np.float32),
        xs=np.zeros(19, np.float32),
        ys=np.zeros(19, np.float32),
        M=np.asarray(M if M is not None else np.eye(3), np.float64),
        Minv=np.eye(3),
        out_size=out_size,
        baseline=np.zeros((19, 19, 3), np.float32),
        confidence=0.9,
        nmatch=18,
        empty_black=0,
        empty_white=0,
    )


class TestGeometryEndpoint:
    def test_async_calibration_start_and_status(self):
        class FakeCalibration:
            def __init__(self):
                self.started = None

            def start(self, *, trigger, empty_confirmed):
                self.started = (trigger, empty_confirmed)

            def status(self):
                return {"phase": "flashing_corners", "progress": {"current": 2, "total": 13}}

        app, c = _client(capture=FakeCapture([]), led=FakeLed())
        calibration = FakeCalibration()
        app.state.geometry_calibration = calibration

        response = c.post("/geometry/calibrate", json={"trigger": "auto", "empty_confirmed": True})

        assert response.status_code == 202
        assert calibration.started == ("auto", True)
        assert c.get("/geometry/status").json()["phase"] == "flashing_corners"

    def test_confirm_existing_geometry(self):
        class FakeCalibration:
            def __init__(self):
                self.confirmed = False

            def confirm_existing(self):
                self.confirmed = True
                return {"phase": "ready", "session_calibrated": True}

        app, c = _client()
        calibration = FakeCalibration()
        app.state.geometry_calibration = calibration

        response = c.post("/geometry/confirm-existing")

        assert response.status_code == 200
        assert response.json()["phase"] == "ready"
        assert calibration.confirmed is True

    def test_confirm_existing_returns_404_without_calibration_service(self):
        _, c = _client()

        response = c.post("/geometry/confirm-existing")

        assert response.status_code == 404

    def test_confirm_existing_maps_rejection_to_conflict(self):
        class RejectingCalibration:
            def confirm_existing(self):
                raise ValueError("existing geometry can only be confirmed after restart")

        app, c = _client()
        app.state.geometry_calibration = RejectingCalibration()

        response = c.post("/geometry/confirm-existing")

        assert response.status_code == 409
        assert response.json()["detail"] == "existing geometry can only be confirmed after restart"

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

    def test_layout_returns_human_oriented_grid(self):
        corners = np.array([[10, 20], [1900, 30], [1880, 1050], [15, 1040]], np.float32)
        points = np.arange(19 * 19 * 2, dtype=np.float32).reshape(19, 19, 2)
        lock = _ok_lock(corners=corners, points=points)

        class FakeCalibration:
            current_lock = lock

            def status(self):
                return {"phase": "ready", "geometry_revision": 1}

        app, c = _client(capture=FakeCapture([np.zeros((1080, 1920, 3), np.uint8)]))
        app.state.geometry_calibration = FakeCalibration()

        response = c.get("/geometry/layout")

        assert response.status_code == 200
        body = response.json()
        assert body["frame"] == {"width": 1920, "height": 1080}
        assert [corner["label"] for corner in body["corners"]] == ["左上", "右上", "右下", "左下"]
        assert body["corners"][0]["row"] == 0 and body["corners"][0]["col"] == 0
        assert body["corners"][1]["row"] == 0 and body["corners"][1]["col"] == 18
        assert len(body["points"]) == 19 and len(body["points"][0]) == 19
        assert body["points"][18][18] == points[18, 18].tolist()
        assert body["revision"] == 1
        assert body["stale"] is False

    def test_layout_retains_old_geometry_when_degraded(self):
        lock = _ok_lock()

        class FakeCalibration:
            current_lock = lock

            def status(self):
                return {"phase": "degraded", "geometry_revision": 4}

        app, c = _client(capture=FakeCapture([np.zeros((10, 20, 3), np.uint8)]))
        app.state.geometry_calibration = FakeCalibration()

        body = c.get("/geometry/layout").json()

        assert body["phase"] == "degraded"
        assert body["stale"] is True
        assert body["revision"] == 4

    def test_layout_returns_409_without_geometry(self):
        _, c = _client(capture=FakeCapture([np.zeros((10, 20, 3), np.uint8)]))

        response = c.get("/geometry/layout")

        assert response.status_code == 409
        assert response.json()["detail"] == "geometry_not_available"

    def test_encode_warped_frame_uses_lock_size(self):
        frame = np.zeros((72, 128, 3), np.uint8)
        lock = _ok_lock(out_size=64, M=np.eye(3))

        jpeg = geometry._encode_warped_frame(frame, lock)
        decoded = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)

        assert decoded.shape[:2] == (64, 64)

    def test_warped_stream_returns_409_without_geometry(self):
        _, c = _client(capture=FakeCapture([np.zeros((10, 20, 3), np.uint8)]))

        response = c.get("/geometry/warped-stream")

        assert response.status_code == 409
        assert response.json()["detail"] == "geometry_not_available"
