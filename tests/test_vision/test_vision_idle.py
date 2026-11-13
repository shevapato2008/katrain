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
    camera = MagicMock(spec=["is_connected", "read_frame"])
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

    def release(self):
        pass


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
        # 空闲时只排空缓冲，不再周期解码。
        assert cap.grabs > 20
        assert cap.reads == 0
        reads_before = cap.reads
        assert cam.read_frame() is None  # 唤醒时先等新的帧，不把旧缓存当当前画面
        assert _wait_until(lambda: cap.reads > reads_before + 10)
    finally:
        cam._stop_event.set()
        reader.join(timeout=2)


def test_long_idle_wakeup_does_not_return_cached_frame():
    cam = CameraManager(device_id=0)
    cam._connected = True
    cam._latest_frame = np.full((4, 4, 3), 99, np.uint8)
    cam._frame_ts = time.monotonic() - 60
    cam._last_demand = time.monotonic() - 60
    assert cam.read_frame() is None
    assert cam.read_frame_identified()[0] is None
    assert cam.read_frame_with_metadata() == (None, None)
    cam._latest_frame = np.full((4, 4, 3), 7, np.uint8)
    cam._frame_ts = time.monotonic()
    assert np.all(cam.read_frame() == 7)


def test_grab_fresh_timeout_does_not_return_old_frame():
    cam = CameraManager(device_id=0)
    cam._connected = True
    cam._latest_frame = np.zeros((4, 4, 3), np.uint8)
    cam._frame_seq = 3
    cam._frame_ts = time.monotonic() - 60
    started = time.monotonic()
    frame, seq, ts = cam.grab_fresh(settle_ms=0, timeout=0.02)
    assert frame is None
    assert seq == 3
    assert ts < started
    assert time.monotonic() - started < 0.2


def test_terminal_binding_stops_actual_camera_processing_but_regular_pause_does_not():
    camera = MagicMock(spec=["is_connected", "read_frame"])
    camera.is_connected = True
    camera.read_frame.return_value = np.zeros((32, 48, 3), np.uint8)
    with patch("katrain.vision.worker_inprocess.StoneDetector"):
        adapter = InProcessAdapter({"model_path": "dummy.onnx", "capture_fps": 50}, camera=camera)
    adapter.send_command(WorkerCommand(CommandType.BIND, {"binding_epoch": 4}))
    adapter.send_command(WorkerCommand(CommandType.PAUSE_DETECTION))
    adapter._drain_commands()
    assert adapter.needs_frames() is True  # lag/hint/removal pauses still observe
    adapter.send_command(WorkerCommand(CommandType.SET_GAME_OVER, {"ended": True, "binding_epoch": 4}))
    adapter.start()
    try:
        assert _wait_until(lambda: not adapter.needs_frames())
        time.sleep(0.3)
        assert camera.read_frame.call_count == 0
        adapter._detector.detect.assert_not_called()
        adapter.send_command(WorkerCommand(CommandType.SET_GAME_OVER, {"ended": False, "binding_epoch": 3}))
        time.sleep(0.3)
        assert adapter.needs_frames() is False  # stale session cannot wake it
        adapter.send_command(WorkerCommand(CommandType.BIND, {"binding_epoch": 5}))
        assert _wait_until(lambda: camera.read_frame.call_count > 0)
    finally:
        adapter.stop()


def test_terminal_binding_preserves_independent_vision_consumers():
    camera = MagicMock(spec=["is_connected", "read_frame"])
    with patch("katrain.vision.worker_inprocess.StoneDetector"):
        adapter = InProcessAdapter({"model_path": "dummy.onnx"}, camera=camera)
    adapter.send_command(WorkerCommand(CommandType.BIND, {"binding_epoch": 4}))
    adapter.send_command(WorkerCommand(CommandType.SET_GAME_OVER, {"ended": True, "binding_epoch": 4}))
    adapter._drain_commands()
    assert adapter.needs_frames() is False
    for command, data in [
        (CommandType.SET_MONITOR, {"active": True}),
        (CommandType.SET_VIEWER_ACTIVE, {"active": True}),
    ]:
        adapter.send_command(WorkerCommand(command, data))
        adapter._drain_commands()
        assert adapter.needs_frames() is True
        adapter.send_command(WorkerCommand(command, {"active": False}))
        adapter._drain_commands()
        assert adapter.needs_frames() is False
    adapter.send_command(
        WorkerCommand(CommandType.ENTER_SETUP_MODE, {"target_board": np.zeros((19, 19), int).tolist()})
    )
    adapter._drain_commands()
    assert adapter.needs_frames() is True


def test_subprocess_terminal_command_uses_the_same_processing_idle_boundary():
    import queue
    from katrain.vision.worker import _VisionWorkerLoop

    worker = _VisionWorkerLoop(queue.Queue(), queue.Queue(), queue.Queue(), queue.Queue(), {})
    worker._camera = MagicMock()
    worker._board_finder = MagicMock()
    worker._detector = MagicMock()
    worker._cmd_queue.put(WorkerCommand(CommandType.BIND, {"binding_epoch": 4}))
    worker._cmd_queue.put(WorkerCommand(CommandType.SET_GAME_OVER, {"ended": True, "binding_epoch": 4}))
    worker._running = True
    worker._maybe_publish_status = lambda: setattr(worker, "_running", False)
    worker._processing_loop()
    worker._camera.read_frame.assert_not_called()
    worker._detector.detect.assert_not_called()
    assert worker.needs_frames() is False

    worker._cmd_queue.put(WorkerCommand(CommandType.SET_GAME_OVER, {"ended": False, "binding_epoch": 3}))
    worker._process_commands()
    assert worker.needs_frames() is False
    worker._cmd_queue.put(WorkerCommand(CommandType.BIND, {"binding_epoch": 5}))
    worker._cmd_queue.put(WorkerCommand(CommandType.PAUSE_DETECTION))
    worker._camera.read_frame.return_value = None
    worker._running = True
    worker._processing_loop()
    worker._camera.read_frame.assert_called_once()
    assert worker.needs_frames() is True


def test_terminal_service_drops_pending_and_late_game_events_without_closing_camera():
    from katrain.vision.config_service import VisionServiceConfig
    from katrain.vision.ipc import ConfirmedMove
    from katrain.vision.service import VisionService
    from tests.test_vision.test_service_event_routing import FakeWorker

    service = VisionService(VisionServiceConfig())
    service.bind_session("one")
    service._pending_moves.append(ConfirmedMove(1, 1, 1))
    service._pending_events.append({"type": "move_pending", "data": {}})
    service.set_game_over(True)
    service._worker = FakeWorker([ConfirmedMove(2, 2, 1), {"type": "capture_pending", "data": {}}])
    assert service.get_confirmed_move() is None
    assert service.poll_events() == []
    service._worker = None
    service.bind_session("two")
    assert service._game_over is False


def test_resume_does_not_replay_events_queued_during_the_terminal_pause():
    from katrain.vision.config_service import VisionServiceConfig
    from katrain.vision.ipc import ConfirmedMove
    from katrain.vision.service import VisionService
    from tests.test_vision.test_service_event_routing import FakeWorker

    service = VisionService(VisionServiceConfig())
    service.set_game_over(True)
    worker = FakeWorker([ConfirmedMove(2, 2, 1), {"type": "move_pending", "data": {}}])
    worker.send_command = lambda command: None
    service._worker = worker
    service.set_game_over(False)
    assert service.get_confirmed_move() is None
    assert service.poll_events() == []
