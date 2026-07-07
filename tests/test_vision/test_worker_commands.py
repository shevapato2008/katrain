"""PAUSE/RESUME/SET_LIT_POINTS must be handled by BOTH dispatchers (SET_GEOMETRY 前车之鉴)."""

import queue
from unittest.mock import patch

import pytest

from katrain.vision.ipc import CommandType, WorkerCommand


def _drain_with(worker_obj):
    worker_obj._cmd_queue.put(WorkerCommand(action=CommandType.PAUSE_DETECTION))
    worker_obj._drain_or_process()
    assert worker_obj._paused is True
    worker_obj._cmd_queue.put(WorkerCommand(action=CommandType.SET_LIT_POINTS, data={"points": [[3, 3], [5, 5]]}))
    worker_obj._drain_or_process()
    assert worker_obj._lit_points == {(3, 3), (5, 5)}
    worker_obj._cmd_queue.put(WorkerCommand(action=CommandType.RESUME_DETECTION))
    worker_obj._drain_or_process()
    assert worker_obj._paused is False


class TestInProcessDispatcher:
    def test_pause_lit_resume(self):
        from katrain.vision.worker_inprocess import InProcessAdapter

        # StoneDetector.__init__ eagerly loads a model (ultralytics/onnx backend); patch it out
        # so construction doesn't require the ultralytics package or a real model file — same
        # pattern as tests/test_vision/test_shared_camera.py.
        with patch("katrain.vision.worker_inprocess.StoneDetector"):
            w = InProcessAdapter({"board_size": 19}, camera=None)
        w._drain_or_process = w._drain_commands
        _drain_with(w)


class TestSubprocessDispatcher:
    def test_pause_lit_resume(self):
        # NOTE: the brief calls this class "VisionWorker", but the actual class
        # in worker.py that owns _process_commands/__init__ is `_VisionWorkerLoop`
        # (VisionWorkerProcess is only the main-process-side proxy with send_command).
        from katrain.vision.worker import _VisionWorkerLoop

        w = _VisionWorkerLoop.__new__(_VisionWorkerLoop)  # 跳过重 __init__（相机/模型），只测分发器
        w._cmd_queue = queue.Queue()
        w._paused = False
        w._lit_points = set()
        w._running = True
        w._drain_or_process = w._process_commands
        _drain_with(w)
