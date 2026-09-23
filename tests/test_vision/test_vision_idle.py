"""没人用摄像头时,识别、漂移检测、摄像头解码都该停下来。

2026-09-21 RK3562:kiosk 停在启动器、没在下棋时 katrain 仍持续 ~170% CPU(4×A53 共 400%),
py-spy 按线程:识别 35% / 摄像头解码 33% / 漂移检测 31%。三条都是常驻全速 ⇒ 整个界面的按钮都慢。
「有人用」= 实体对局绑定、做题/摆谱监视、摆棋准备、有人开着识别预览、有人在取画面(标定/推流/摆谱)。
"""

import time
from unittest.mock import MagicMock, patch

import numpy as np

from katrain.vision.camera import CameraManager
from katrain.vision.ipc import CommandType, WorkerCommand
from katrain.vision.worker_inprocess import InProcessAdapter


def _wait_until(pred, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(0.02)
    return False


def test_worker_reads_no_frames_while_nobody_needs_them_but_still_reports_status():
    camera = MagicMock()
    camera.is_connected = True
    camera.read_frame.return_value = np.zeros((32, 48, 3), np.uint8)
    with patch("katrain.vision.worker_inprocess.StoneDetector"):
        adapter = InProcessAdapter({"model_path": "dummy.onnx", "capture_fps": 50}, camera=camera)
    adapter.start()
    try:
        # 状态照常上报:左栏的「摄像头已连接」不能因为空闲就变成未连接。
        assert _wait_until(lambda: adapter._status.camera_ready)
        time.sleep(0.4)
        assert camera.read_frame.call_count == 0
        assert adapter.needs_frames() is False

        adapter.send_command(WorkerCommand(action=CommandType.BIND))
        assert _wait_until(lambda: camera.read_frame.call_count > 0)
        assert adapter.needs_frames() is True
    finally:
        adapter.stop()


class _FakeCap:
    def __init__(self):
        self.reads = 0
        self.grabs = 0

    def read(self):
        self.reads += 1
        time.sleep(0.005)
        return True, np.zeros((4, 4, 3), np.uint8)

    def grab(self):
        self.grabs += 1
        time.sleep(0.005)
        return True


def test_camera_stops_decoding_when_nobody_asked_for_frames_and_resumes_on_demand():
    cam = CameraManager(device_id=0)
    cap = _FakeCap()
    cam._cap = cap
    cam._connected = True
    cam._last_demand = time.monotonic() - 60  # 很久没人要画面
    import threading

    reader = threading.Thread(target=cam._reader_loop, daemon=True)
    reader.start()
    try:
        time.sleep(0.5)
        # 空闲:缓冲照常清(grab 不解码),解码每秒只剩 1 帧上下 —— 不是按摄像头帧率。
        assert cap.grabs > 20
        assert cap.reads <= 2
        reads_before = cap.reads
        cam.read_frame()  # 有人要画面了
        assert _wait_until(lambda: cap.reads > reads_before + 10)
    finally:
        cam._stop_event.set()
        reader.join(timeout=2)
