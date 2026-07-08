"""PAUSE/RESUME/SET_LIT_POINTS must be handled by BOTH dispatchers (SET_GEOMETRY 前车之鉴)."""

import queue
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from katrain.vision.board_state import BLACK, EMPTY
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


# ---------------------------------------------------------------------------
# Resync leftover re-injection — must NOT re-fire on BOTH dispatchers (wzceinjdc lens C/A)
# ---------------------------------------------------------------------------


def _post_resync_reinjection_guard(w):
    """After a trust-digital resync, a physical stone still sitting on a just-captured /
    removal-lit point must NOT re-confirm as a move — even though the streaming
    SET_EXPECTED_BOARD force-syncs the detector baseline back to the bare digital board.

    Drives the REAL RESET_SYNC(expected) + SET_EXPECTED_BOARD handlers so the assertions
    pin the actual mechanism: (1) the union baseline holds the leftover at reset, (2) the
    next analysis-stream push clobbers it back to digital-empty (the trap FIX C's transient
    union could not survive), (3) with the removal-lit mask fed to detect_new_move the
    leftover is inert regardless. Regression for the resync re-injection on the SBC path."""
    digital = np.zeros((19, 19), dtype=int)  # (3,3) was just captured -> digital empty
    leftover = digital.copy()
    leftover[3][3] = BLACK  # human's stone not lifted; camera still reads it
    w._last_stable_board = leftover.copy()
    w._lit_points = {(3, 3)}  # blue "remove" lamp burning at the captured point

    # (1) trust-digital resync: sync -> digital, detector -> union(digital, leftover)
    w._cmd_queue.put(WorkerCommand(action=CommandType.RESET_SYNC, data={"expected": digital.tolist()}))
    w._drain_or_process()
    assert w._move_detector.prev_board[3][3] == BLACK  # union kept the leftover at reset

    # (2) streaming analysis re-pushes the (unchanged) digital board ~0.25s later
    w._cmd_queue.put(WorkerCommand(action=CommandType.SET_EXPECTED_BOARD, data={"board": digital.tolist()}))
    w._drain_or_process()
    assert w._move_detector.prev_board[3][3] == EMPTY  # baseline clobbered back to digital (the trap)

    # (3) detection resumes; the loop feeds the leftover board + the removal-lit mask.
    exp = w._expected_np
    masked = {p for p in w._lit_points if exp is None or int(exp[p[0]][p[1]]) == EMPTY}
    for _ in range(8):
        assert w._move_detector.detect_new_move(w._last_stable_board, ignore_cells=masked) is None


class TestResyncReinjectionGuard:
    def test_inprocess_leftover_does_not_reinject(self):
        from katrain.vision.worker_inprocess import InProcessAdapter

        with patch("katrain.vision.worker_inprocess.StoneDetector"):
            w = InProcessAdapter({"board_size": 19}, camera=None)
        w._drain_or_process = w._drain_commands
        _post_resync_reinjection_guard(w)

    def test_subprocess_leftover_does_not_reinject(self):
        from katrain.vision.move_detector import MoveDetector
        from katrain.vision.sync import SyncStateMachine
        from katrain.vision.worker import _VisionWorkerLoop

        w = _VisionWorkerLoop.__new__(_VisionWorkerLoop)  # 跳过重 __init__，只驱动分发器 + 检测器
        w._cmd_queue = queue.Queue()
        w._running = True
        w._board_locked = False
        w._board_finder = MagicMock()
        w._sync = SyncStateMachine()
        w._move_detector = MoveDetector(consistency_frames=3)
        w._expected_np = None
        w._prev_conf_map = {}
        w._ambig_last_emit = {}
        w._averager = MagicMock()
        w._promoter = MagicMock()
        w._lit_points = set()
        w._drain_or_process = w._process_commands
        _post_resync_reinjection_guard(w)
