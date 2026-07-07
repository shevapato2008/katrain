import numpy as np

from katrain.web.core.camera_hub import CameraHub, CameraHubConfig


class FakeCamera:
    def __init__(self):
        self.open_calls = 0
        self.close_calls = 0
        self.is_connected = False
        self.frame = np.zeros((4, 6, 3), np.uint8)

    def open(self):
        self.open_calls += 1
        self.is_connected = True
        return True

    def close(self):
        self.close_calls += 1
        self.is_connected = False

    def read_frame(self):
        return self.frame.copy()

    def grab_fresh(self, after_ts=None, settle_ms=150.0):
        return self.frame.copy(), 7, 123.0


def test_camera_hub_owns_one_camera_lifecycle():
    camera = FakeCamera()
    hub = CameraHub(CameraHubConfig(device_id=0, width=1920, height=1080), camera=camera)

    hub.start()
    hub.start()
    assert camera.open_calls == 1
    assert hub.is_connected() is True

    frame = hub.read_frame()
    fresh, seq, ts = hub.grab_fresh(after_ts=100.0, settle_ms=10)
    assert frame.shape == (4, 6, 3)
    assert fresh.shape == frame.shape and seq == 7 and ts == 123.0

    hub.stop()
    hub.stop()
    assert camera.close_calls == 1


def test_camera_hub_grab_burst_uses_shared_frame_source():
    camera = FakeCamera()
    hub = CameraHub(CameraHubConfig(), camera=camera)
    hub.start()

    frames = hub.grab_burst(n=3, interval=0)

    assert len(frames) == 3
    assert all(frame.shape == (4, 6, 3) for frame in frames)
