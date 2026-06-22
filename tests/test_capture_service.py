"""Tests for CaptureService (mock camera) and CameraManager's grab_fresh gate.

No real camera is opened. Real capture (exposure lock, LED-lit frames) is verified
on hardware day.
"""

import threading
import time

import numpy as np
import pytest

from katrain.web.core.capture_service import CaptureService, CaptureServiceConfig


class FakeCam:
    def __init__(self):
        self.opened = False
        self.closed = False
        self.is_connected = False
        self._frame = np.zeros((8, 8, 3), np.uint8)

    def open(self):
        self.opened = True
        self.is_connected = True
        return True

    def close(self):
        self.closed = True
        self.is_connected = False

    def grab_fresh(self, after_ts=None, settle_ms=150.0):
        return self._frame.copy(), 7, 123.0

    def read_frame(self):
        return self._frame.copy()


def _svc(camera):
    return CaptureService(CaptureServiceConfig(enabled=True, camera_device=0, out_dir="/tmp/baipu_test"), camera=camera)


class TestCaptureService:
    def test_shared_hub_is_not_opened_or_closed_by_capture_service(self):
        hub = FakeCam()
        hub.is_started = True
        svc = CaptureService(
            CaptureServiceConfig(enabled=True, camera_device=0, out_dir="/tmp/baipu_test"), hub=hub
        )

        svc.start()
        svc.stop()

        assert hub.opened is False
        assert hub.closed is False

    def test_lifecycle(self):
        cam = FakeCam()
        svc = _svc(cam)
        svc.start()
        assert cam.opened and svc.is_connected() is True
        svc.stop()
        assert cam.closed and svc.is_connected() is False

    def test_grab_fresh_delegates(self):
        cam = FakeCam()
        svc = _svc(cam)
        svc.start()
        frame, seq, ts = svc.grab_fresh(after_ts=100.0, settle_ms=10)
        assert frame.shape == (8, 8, 3) and seq == 7 and ts == 123.0

    def test_read_frame_delegates_for_preview(self):
        cam = FakeCam()
        svc = _svc(cam)
        svc.start()
        assert svc.read_frame().shape == (8, 8, 3)

    def test_capture_to_writes_file(self, tmp_path):
        cam = FakeCam()
        svc = _svc(cam)
        svc.start()
        out = tmp_path / "game1" / "frame_000.jpg"
        path, seq, ts = svc.capture_to(str(out))
        assert out.exists() and seq == 7
        # parent dir was created; no leftover tmp file
        assert not (tmp_path / "game1" / ".frame_000.tmp.jpg").exists()

    def test_capture_to_raises_without_frame(self, tmp_path):
        cam = FakeCam()
        cam.grab_fresh = lambda after_ts=None, settle_ms=150.0: (None, 0, 0.0)
        svc = _svc(cam)
        svc.start()
        with pytest.raises(RuntimeError):
            svc.capture_to(str(tmp_path / "x.jpg"))

    def test_grab_burst(self):
        cam = FakeCam()
        svc = _svc(cam)
        svc.start()
        frames = svc.grab_burst(n=3, interval=0)
        assert len(frames) == 3


class TestCameraGrabFreshGate:
    def test_returns_only_post_after_ts_frame(self):
        from katrain.vision.camera import CameraManager

        cam = CameraManager(device_id=0)
        # Seed a stale frame.
        with cam._frame_lock:
            cam._latest_frame = np.zeros((4, 4, 3), np.uint8)
            cam._frame_ts = time.monotonic()
            cam._frame_seq = 1
        t0 = time.monotonic()

        def push_new():
            time.sleep(0.08)
            with cam._frame_lock:
                cam._latest_frame = np.ones((4, 4, 3), np.uint8)
                cam._frame_ts = time.monotonic()
                cam._frame_seq = 2

        threading.Thread(target=push_new).start()
        frame, seq, ts = cam.grab_fresh(after_ts=t0, settle_ms=0, timeout=2.0)
        assert seq == 2 and ts > t0  # never the stale pre-after_ts frame
