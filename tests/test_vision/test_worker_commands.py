"""PAUSE/RESUME/SET_LIT_POINTS must be handled by BOTH dispatchers (SET_GEOMETRY 前车之鉴)."""

import queue
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from katrain.vision.board_state import BLACK, EMPTY
from katrain.vision.config_service import VisionServiceConfig
from katrain.vision.ipc import CommandType, ConfirmedMove, WorkerCommand
from katrain.vision.service import VisionService


def test_vision_service_expected_board_command_carries_node_id():
    service = VisionService(VisionServiceConfig())
    service._worker = MagicMock()
    board = np.zeros((19, 19), dtype=int)

    service.set_expected_from_stones([], expected_node_id=77)

    command = service._worker.send_command.call_args.args[0]
    assert command.action == CommandType.SET_EXPECTED_BOARD
    assert command.data == {"board": board.tolist(), "expected_node_id": 77}


def _assert_unchanged_expected_board_still_forwards_node_id(worker):
    board = np.zeros((19, 19), dtype=int)
    worker._sync = MagicMock()
    worker._move_detector = MagicMock()
    worker._move_detector.prev_board = board.copy()
    worker._expected_np = board.copy()
    worker._cmd_queue.put(
        WorkerCommand(
            action=CommandType.SET_EXPECTED_BOARD,
            data={"board": board.tolist(), "expected_node_id": 77},
        )
    )

    worker._drain_or_process()

    worker._sync.set_expected_board.assert_called_once()
    forwarded_board = worker._sync.set_expected_board.call_args.args[0]
    assert np.array_equal(forwarded_board, board)
    assert worker._sync.set_expected_board.call_args.kwargs == {"expected_node_id": 77}
    worker._move_detector.force_sync.assert_not_called()


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

    def test_unchanged_board_still_forwards_expected_node_id(self):
        w = _inprocess_worker()
        w._drain_or_process = w._drain_commands

        _assert_unchanged_expected_board_still_forwards_node_id(w)


def _inprocess_worker(camera=None):
    from katrain.vision.worker_inprocess import InProcessAdapter

    with patch("katrain.vision.worker_inprocess.StoneDetector"):
        return InProcessAdapter({"board_size": 19}, camera=camera)


def _geometry(source_width=600, source_height=400):
    return SimpleNamespace(
        corners=[(120, 80), (480, 80), (480, 320), (120, 320)],
        source_width=source_width,
        source_height=source_height,
        M=np.eye(3),
        out_size=1000,
    )


class _OneFrameCamera:
    is_connected = True

    def __init__(self):
        self.worker = None

    def read_frame(self):
        self.worker._running = False
        return np.zeros((10, 10, 3), dtype=np.uint8)


def _configure_confirmation_probe(worker, *, peak, count):
    board = np.zeros((19, 19), dtype=int)
    board[3][3] = BLACK
    extractor = MagicMock()
    extractor.detections_to_board.return_value = board
    extractor.cell_confidences.return_value = {} if peak is None else {(3, 3): peak}
    worker._move_detector = MagicMock()
    worker._move_detector.pending_move = (3, 3, BLACK)
    worker._move_detector.count = count
    worker._move_detector.consistency_frames = 5
    worker._move_detector.detect_new_move.return_value = (3, 3, BLACK)
    # A bare MagicMock() is truthy, so an unset is_suspect(...) silently ran every
    # existing case through the SUSPECT branch (gate 0.55+0.25 here) instead of the
    # plain gate it claimed to test — fix round 1, see test_worker_commands.py review.
    worker._move_detector.is_suspect.return_value = False
    worker._conf_peak = MagicMock()
    worker._conf_peak.peak_for.return_value = peak
    worker._conf_peak.gate_confidence.return_value = 0.0 if peak is None else peak
    worker._fast_confirm_frames = 3
    worker._fast_confirm_confidence = 0.70
    worker._ambiguous_confidence = 0.55
    worker._prev_conf_map = {}
    worker._ambig_last_emit = {}
    worker._bound = True
    worker._monitor = False
    worker._paused = False
    worker._move_armed = False
    worker._lit_points = set()
    worker._expected_np = None
    worker._prev_observed_board = None
    worker._last_stable_board = None
    worker._event_queue = queue.Queue()
    worker._promoter = MagicMock()
    worker._sync = MagicMock()
    worker._sync.state = SimpleNamespace(value="synced")
    worker._sync.update.return_value = []
    return extractor


@pytest.mark.parametrize(
    ("peak", "count", "expected_required", "expected_log"),
    [
        (0.80, 2, 3, "required_frames=3 observed_frames=3"),
        # The gate value (0.55) is named here on purpose, not just the frame counts: it
        # pins _configure_confirmation_probe's `is_suspect.return_value = False` default.
        # A bare MagicMock() is truthy, so if that line is ever dropped this case would
        # silently start running the suspect branch (gate 0.55+0.25=0.80) instead — see
        # test_..._suspect_cell_routes_to_ambiguous_card_not_autoplay's docstring.
        (None, 4, None, "peak conf 0.00 < 0.55 — ambiguous prompt; required_frames=5 observed_frames=5"),
    ],
)
def test_inprocess_confirmation_diagnostic_reports_selected_path(peak, count, expected_required, expected_log, caplog):
    camera = _OneFrameCamera()
    worker = _inprocess_worker(camera)
    camera.worker = worker
    extractor = _configure_confirmation_probe(worker, peak=peak, count=count)
    worker._running = True
    worker._config["capture_fps"] = 100000
    worker._motion_is_stable = MagicMock(return_value=True)
    worker._warp_frame = MagicMock(return_value=(np.zeros((10, 10, 3), dtype=np.uint8), True))
    worker._averager = MagicMock()
    worker._averager.add.side_effect = lambda frame: frame
    worker._detector = MagicMock()
    worker._detector.detect.return_value = []
    worker._active_extractor = MagicMock(return_value=extractor)
    worker._maybe_send_preview = MagicMock()

    with caplog.at_level("INFO"):
        worker._loop()

    assert worker._move_detector.detect_new_move.call_args.kwargs["required_frames"] == expected_required
    assert any(expected_log in record.message for record in caplog.records)


@pytest.mark.parametrize(
    ("is_suspect", "expected_log_fragment", "expect_confirmed"),
    [
        # 0.42 (device gate) + 0.25 (SUSPECT_CONFIDENCE_BONUS) = 0.67 > peak 0.57 -> routed to card.
        (True, "peak conf 0.57 < 0.67", False),
        # Not suspect: the device gate alone (0.42) is below peak 0.57 -> auto-plays.
        (False, "move confirmed", True),
    ],
)
def test_inprocess_suspect_cell_routes_to_ambiguous_card_not_autoplay(
    is_suspect, expected_log_fragment, expect_confirmed, caplog
):
    """Fix round 1: is_suspect() must change ONLY the ambiguous routing gate, never the
    confirmation frame count. Regression harness for the bug this replaces: with
    is_suspect left as a bare MagicMock (truthy), both cases below would silently run
    the SUSPECT branch regardless of the parametrized value."""
    camera = _OneFrameCamera()
    worker = _inprocess_worker(camera)
    camera.worker = worker
    extractor = _configure_confirmation_probe(worker, peak=0.57, count=5)
    worker._ambiguous_confidence = 0.42
    worker._move_detector.is_suspect.return_value = is_suspect
    worker._running = True
    worker._config["capture_fps"] = 100000
    worker._motion_is_stable = MagicMock(return_value=True)
    worker._warp_frame = MagicMock(return_value=(np.zeros((10, 10, 3), dtype=np.uint8), True))
    worker._averager = MagicMock()
    worker._averager.add.side_effect = lambda frame: frame
    worker._detector = MagicMock()
    worker._detector.detect.return_value = []
    worker._active_extractor = MagicMock(return_value=extractor)
    worker._maybe_send_preview = MagicMock()

    with caplog.at_level("INFO"):
        worker._loop()

    assert any(expected_log_fragment in record.message for record in caplog.records)
    event = worker._event_queue.get_nowait()
    if expect_confirmed:
        assert isinstance(event, ConfirmedMove)
        assert (event.row, event.col, event.color) == (3, 3, BLACK)
    else:
        assert event["type"] == "ambiguous_stone"
        assert event["data"]["row"] == 3 and event["data"]["col"] == 3


class TestInProcessMotionGating:
    def test_motion_mask_without_geometry_is_none(self):
        w = _inprocess_worker()

        assert w._motion_mask(np.zeros((200, 300, 3), dtype=np.uint8)) is None

    def test_geometry_lock_builds_mask_from_lock_corners_and_source_size(self):
        w = _inprocess_worker()
        geometry = _geometry()
        w.set_geometry(geometry)
        w._motion_mask_cache = MagicMock()
        frame = np.zeros((200, 300, 3), dtype=np.uint8)

        w._motion_mask(frame)

        w._motion_mask_cache.get.assert_called_once_with(frame.shape, geometry.corners, (600, 400))

    def test_each_geometry_assignment_invalidates_roi_cache_and_motion_baseline(self):
        w = _inprocess_worker()
        w._motion_mask_cache = MagicMock()
        w._motion_filter = MagicMock()

        w.set_geometry(_geometry())
        w.set_geometry(None)

        assert w._geometry is None
        assert w._motion_mask_cache.invalidate.call_count == 2
        assert w._motion_filter.reset.call_count == 2

    def test_unbind_resets_motion_history(self):
        w = _inprocess_worker()
        w._motion_filter = MagicMock()
        w._cmd_queue.put(WorkerCommand(action=CommandType.UNBIND))

        w._drain_commands()

        w._motion_filter.reset.assert_called_once_with()

    def test_reset_sync_keeps_motion_history_and_roi_cache(self):
        w = _inprocess_worker()
        w._motion_filter = MagicMock()
        w._motion_mask_cache = MagicMock()
        w._cmd_queue.put(WorkerCommand(action=CommandType.RESET_SYNC))

        w._drain_commands()

        w._motion_filter.reset.assert_not_called()
        w._motion_mask_cache.invalidate.assert_not_called()

    def test_frame_size_change_rebuilds_mask_and_establishes_fresh_motion_baseline(self):
        w = _inprocess_worker()
        w.set_geometry(_geometry())
        small = np.zeros((200, 300, 3), dtype=np.uint8)
        large = np.ones((400, 600, 3), dtype=np.uint8) * 255

        first_mask = w._motion_mask(small)
        assert w._motion_is_stable(small) is True
        resized_mask = w._motion_mask(large)

        assert resized_mask is not first_mask
        assert w._motion_is_stable(large) is True
        assert w._last_motion_roi_ratio is None
        assert w._last_motion_full_ratio == 0.0

    def test_motion_gate_passes_generated_mask_to_region_filter(self):
        w = _inprocess_worker()
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        mask = np.ones((10, 10), dtype=bool)
        w._motion_mask = MagicMock(return_value=mask)
        w._motion_filter = MagicMock()
        w._motion_filter.is_stable_with_regions.return_value = (True, 0.01, 0.02)

        assert w._motion_is_stable(frame) is True

        w._motion_filter.is_stable_with_regions.assert_called_once_with(frame, mask)
        assert w._last_motion_roi_ratio == 0.01
        assert w._last_motion_full_ratio == 0.02

    def test_rejected_motion_resets_averager_and_returns_false(self):
        w = _inprocess_worker()
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        w._motion_mask = MagicMock(return_value=None)
        w._motion_filter = MagicMock()
        w._motion_filter.is_stable_with_regions.return_value = (False, None, 0.31)
        w._averager = MagicMock()

        assert w._motion_is_stable(frame) is False
        w._averager.reset.assert_called_once_with()

    def test_rejection_logs_immediately_then_at_most_once_per_five_seconds(self, monkeypatch, caplog):
        w = _inprocess_worker()
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        w._motion_mask = MagicMock(return_value=None)
        w._motion_filter = MagicMock()
        w._motion_filter.is_stable_with_regions.return_value = (False, None, 0.31)
        w._averager = MagicMock()
        clock = iter((100.0, 101.0, 106.0))
        monkeypatch.setattr("katrain.vision.worker_inprocess.time.monotonic", lambda: next(clock))

        with caplog.at_level("INFO"):
            w._motion_is_stable(frame)
            w._motion_is_stable(frame)
            w._motion_is_stable(frame)

        assert sum("motion rejected" in record.message for record in caplog.records) == 2

    def test_motion_diagnostic_formats_roi_and_full_or_full_fallback(self):
        w = _inprocess_worker()
        w._last_motion_roi_ratio = 0.125
        w._last_motion_full_ratio = 0.25
        assert w._motion_diagnostic() == "roi:0.125/full:0.250"

        w._last_motion_roi_ratio = None
        assert w._motion_diagnostic() == "full:N/A/full:0.250"

    def test_motion_rejection_skips_all_recognition_work_for_one_loop_iteration(self):
        frame = np.zeros((10, 10, 3), dtype=np.uint8)

        class OneFrameCamera:
            is_connected = True

            def __init__(self):
                self.worker = None

            def read_frame(self):
                self.worker._running = False
                return frame

        camera = OneFrameCamera()
        w = _inprocess_worker(camera)
        camera.worker = w
        w._running = True
        w._motion_filter = MagicMock()
        w._motion_filter.is_stable_with_regions.return_value = (False, None, 0.31)
        w._warp_frame = MagicMock()
        w._detector.detect = MagicMock()
        w._active_extractor = MagicMock()
        w._move_detector.detect_new_move = MagicMock()
        w._averager = MagicMock()
        w._bound = True
        w._sync = MagicMock()
        w._sync.state = SimpleNamespace(value="synced")

        w._loop()

        w._averager.reset.assert_called_once_with()
        w._warp_frame.assert_not_called()
        w._detector.detect.assert_not_called()
        w._active_extractor.assert_not_called()
        w._move_detector.detect_new_move.assert_not_called()
        w._sync.update.assert_not_called()

    def test_camera_dropout_resets_averager_once_without_recognition_work(self):
        class DropoutCamera:
            is_connected = True

            def __init__(self):
                self.worker = None

            def read_frame(self):
                self.worker._running = False
                return None

        camera = DropoutCamera()
        w = _inprocess_worker(camera)
        camera.worker = w
        w._running = True
        w._config["capture_fps"] = 100000
        w._warp_frame = MagicMock()
        w._detector.detect = MagicMock()
        w._active_extractor = MagicMock()
        w._move_detector.detect_new_move = MagicMock()
        w._averager = MagicMock()

        w._loop()

        w._averager.reset.assert_called_once_with()
        w._warp_frame.assert_not_called()
        w._detector.detect.assert_not_called()
        w._active_extractor.assert_not_called()
        w._move_detector.detect_new_move.assert_not_called()

    def test_periodic_stable_log_includes_motion_roi_and_full_ratios(self, caplog):
        frame = np.zeros((10, 10, 3), dtype=np.uint8)

        class OneFrameCamera:
            is_connected = True

            def __init__(self):
                self.worker = None

            def read_frame(self):
                self.worker._running = False
                return frame

        camera = OneFrameCamera()
        w = _inprocess_worker(camera)
        camera.worker = w
        w._running = True
        w._config["capture_fps"] = 100000
        w._frame_count = 29
        w._motion_filter = MagicMock()
        w._motion_filter.is_stable_with_regions.return_value = (True, 0.125, 0.25)
        w._warp_frame = MagicMock(return_value=(frame, True))
        w._averager = MagicMock()
        w._averager.add.return_value = frame
        w._detector.detect.return_value = []
        extractor = MagicMock()
        extractor.detections_to_board.return_value = np.zeros((19, 19), dtype=int)
        w._active_extractor = MagicMock(return_value=extractor)

        with caplog.at_level("INFO"):
            w._loop()

        assert any("motion=roi:0.125/full:0.250" in record.message for record in caplog.records)


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

    def test_unchanged_board_still_forwards_expected_node_id(self):
        from katrain.vision.worker import _VisionWorkerLoop

        w = _VisionWorkerLoop.__new__(_VisionWorkerLoop)
        w._cmd_queue = queue.Queue()
        w._running = True
        w._drain_or_process = w._process_commands

        _assert_unchanged_expected_board_still_forwards_node_id(w)


def _subprocess_motion_worker():
    from katrain.vision.worker import _VisionWorkerLoop

    w = _VisionWorkerLoop.__new__(_VisionWorkerLoop)
    w._board_locked = False
    w._board_finder = MagicMock()
    w._board_finder.camera_config = None
    w._board_finder.pre_corner_point = [(60, 40), (240, 40), (240, 160), (60, 160)]
    w._motion_mask_cache = MagicMock()
    w._motion_filter = MagicMock()
    w._averager = MagicMock()
    w._last_motion_log = None
    w._last_motion_roi_ratio = None
    w._last_motion_full_ratio = None
    w._observation_seq = 0
    return w


@pytest.mark.parametrize(
    ("peak", "count", "expected_required", "expected_log"),
    [
        (0.80, 2, 3, "required_frames=3 observed_frames=3"),
        # The gate value (0.55) is named here on purpose, not just the frame counts: it
        # pins _configure_confirmation_probe's `is_suspect.return_value = False` default.
        # A bare MagicMock() is truthy, so if that line is ever dropped this case would
        # silently start running the suspect branch (gate 0.55+0.25=0.80) instead — see
        # test_..._suspect_cell_routes_to_ambiguous_card_not_autoplay's docstring.
        (None, 4, None, "peak conf 0.00 < 0.55 — ambiguous prompt; required_frames=5 observed_frames=5"),
    ],
)
def test_subprocess_confirmation_diagnostic_reports_selected_path(peak, count, expected_required, expected_log, caplog):
    worker = _subprocess_motion_worker()
    camera = _OneFrameCamera()
    camera.worker = worker
    extractor = _configure_confirmation_probe(worker, peak=peak, count=count)
    worker._running = True
    worker._cmd_queue = queue.Queue()
    worker._camera = camera
    worker._frame_count = 0
    worker._motion_is_stable = MagicMock(return_value=True)
    worker._board_finder.find_focus.return_value = (np.zeros((10, 10, 3), dtype=np.uint8), True)
    worker._config = {"use_clahe": False, "enhance": "none"}
    worker._enhance_mode = "none"
    worker._add_threshold = 0.5
    worker._ae = None
    worker._averager.add.side_effect = lambda frame: frame
    worker._detector = MagicMock()
    worker._detector.detect.return_value = []
    worker._overlay_lock = MagicMock()
    worker._overlay = MagicMock()
    worker._state_extractor = extractor
    worker._last_detected_board = None
    worker._consecutive_failures = 0
    worker._maybe_publish_status = MagicMock()

    with caplog.at_level("INFO"):
        worker._processing_loop()

    assert worker._move_detector.detect_new_move.call_args.kwargs["required_frames"] == expected_required
    assert any(expected_log in record.message for record in caplog.records)


@pytest.mark.parametrize(
    ("is_suspect", "expected_log_fragment", "expect_confirmed"),
    [
        # 0.42 (device gate) + 0.25 (SUSPECT_CONFIDENCE_BONUS) = 0.67 > peak 0.57 -> routed to card.
        (True, "peak conf 0.57 < 0.67", False),
        # Not suspect: the device gate alone (0.42) is below peak 0.57 -> auto-plays.
        (False, "move confirmed", True),
    ],
)
def test_subprocess_suspect_cell_routes_to_ambiguous_card_not_autoplay(
    is_suspect, expected_log_fragment, expect_confirmed, caplog
):
    """Mirror of test_inprocess_suspect_cell_routes_to_ambiguous_card_not_autoplay for
    the SBC subprocess path (worker.py) — worker parity, fix round 1."""
    worker = _subprocess_motion_worker()
    camera = _OneFrameCamera()
    camera.worker = worker
    extractor = _configure_confirmation_probe(worker, peak=0.57, count=5)
    worker._ambiguous_confidence = 0.42
    worker._move_detector.is_suspect.return_value = is_suspect
    worker._running = True
    worker._cmd_queue = queue.Queue()
    worker._camera = camera
    worker._frame_count = 0
    worker._motion_is_stable = MagicMock(return_value=True)
    worker._board_finder.find_focus.return_value = (np.zeros((10, 10, 3), dtype=np.uint8), True)
    worker._config = {"use_clahe": False, "enhance": "none"}
    worker._enhance_mode = "none"
    worker._add_threshold = 0.5
    worker._ae = None
    worker._averager.add.side_effect = lambda frame: frame
    worker._detector = MagicMock()
    worker._detector.detect.return_value = []
    worker._overlay_lock = MagicMock()
    worker._overlay = MagicMock()
    worker._state_extractor = extractor
    worker._last_detected_board = None
    worker._consecutive_failures = 0
    worker._maybe_publish_status = MagicMock()

    with caplog.at_level("INFO"):
        worker._processing_loop()

    assert any(expected_log_fragment in record.message for record in caplog.records)
    event = worker._event_queue.get_nowait()
    if expect_confirmed:
        assert isinstance(event, ConfirmedMove)
        assert (event.row, event.col, event.color) == (3, 3, BLACK)
    else:
        assert event["type"] == "ambiguous_stone"
        assert event["data"]["row"] == 3 and event["data"]["col"] == 3


class TestSubprocessMotionGating:
    def test_unlocked_worker_uses_full_frame_fallback(self):
        w = _subprocess_motion_worker()
        frame = np.zeros((200, 300, 3), dtype=np.uint8)

        assert w._motion_mask(frame) is None
        w._motion_mask_cache.get.assert_not_called()

    def test_locked_uncalibrated_worker_builds_mask_from_raw_corners(self):
        w = _subprocess_motion_worker()
        w._board_locked = True
        frame = np.zeros((200, 300, 3), dtype=np.uint8)

        w._motion_mask(frame)

        w._motion_mask_cache.get.assert_called_once_with(frame.shape, w._board_finder.pre_corner_point, (None, None))

    def test_locked_calibrated_worker_uses_full_frame_fallback(self):
        w = _subprocess_motion_worker()
        w._board_locked = True
        w._board_finder.camera_config = SimpleNamespace(is_calibrated=True)
        frame = np.zeros((200, 300, 3), dtype=np.uint8)

        assert w._motion_mask(frame) is None
        w._motion_mask_cache.get.assert_not_called()

    def test_full_frame_fallback_is_passed_to_hybrid_filter(self):
        w = _subprocess_motion_worker()
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        w._motion_filter.is_stable_with_regions.return_value = (True, None, 0.02)

        assert w._motion_is_stable(frame) is True

        w._motion_filter.is_stable_with_regions.assert_called_once_with(frame, None)
        assert w._last_motion_roi_ratio is None
        assert w._last_motion_full_ratio == 0.02

    def test_motion_gate_passes_generated_mask_and_rejection_resets_average(self):
        w = _subprocess_motion_worker()
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        mask = np.ones((10, 10), dtype=bool)
        w._motion_mask = MagicMock(return_value=mask)
        w._motion_filter.is_stable_with_regions.return_value = (False, 0.06, 0.10)

        assert w._motion_is_stable(frame) is False

        w._motion_filter.is_stable_with_regions.assert_called_once_with(frame, mask)
        w._averager.reset.assert_called_once_with()
        assert w._last_motion_roi_ratio == 0.06
        assert w._last_motion_full_ratio == 0.10

    def test_rejection_logs_immediately_then_at_most_once_per_five_seconds(self, monkeypatch, caplog):
        w = _subprocess_motion_worker()
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        w._motion_filter.is_stable_with_regions.return_value = (False, None, 0.31)
        clock = iter((100.0, 101.0, 106.0))
        monkeypatch.setattr("katrain.vision.worker.time.monotonic", lambda: next(clock))

        with caplog.at_level("INFO"):
            w._motion_is_stable(frame)
            w._motion_is_stable(frame)
            w._motion_is_stable(frame)

        assert sum("motion rejected" in record.message for record in caplog.records) == 2

    def test_motion_diagnostic_formats_roi_and_full_or_full_fallback(self):
        w = _subprocess_motion_worker()
        w._last_motion_roi_ratio = 0.125
        w._last_motion_full_ratio = 0.25
        assert w._motion_diagnostic() == "roi:0.125/full:0.250"

        w._last_motion_roi_ratio = None
        assert w._motion_diagnostic() == "full:N/A/full:0.250"

    @pytest.mark.parametrize(
        ("action", "starts_locked", "ends_locked"),
        [
            (CommandType.CONFIRM_POSE_LOCK, False, True),
            (CommandType.RESET_SYNC, True, False),
            (CommandType.UNBIND, True, True),
        ],
    )
    def test_command_boundary_resets_motion_region(self, action, starts_locked, ends_locked):
        from katrain.vision.sync import SyncStateMachine

        w = _subprocess_motion_worker()
        w._cmd_queue = queue.Queue()
        w._running = True
        w._board_locked = starts_locked
        w._sync = SyncStateMachine()
        w._move_detector = MagicMock()
        w._last_stable_board = None
        w._prev_observed_board = None
        w._prev_conf_map = {}
        w._ambig_last_emit = {}
        w._promoter = MagicMock()
        w._cmd_queue.put(WorkerCommand(action=action))

        w._process_commands()

        assert w._board_locked is ends_locked
        w._motion_mask_cache.invalidate.assert_called_once_with()
        w._motion_filter.reset.assert_called_once_with()

    def test_auto_unlock_resets_motion_region(self):
        w = _subprocess_motion_worker()
        frame = np.zeros((10, 10, 3), dtype=np.uint8)

        class OneFrameCamera:
            is_connected = True

            def read_frame(self):
                w._running = False
                return frame

        w._running = True
        w._camera = OneFrameCamera()
        w._process_commands = MagicMock()
        w._motion_is_stable = MagicMock(return_value=True)
        w._frame_count = 0
        w._board_locked = True
        w._board_finder.last_transform_matrix = None
        w._board_finder.find_focus.return_value = (None, False)
        w._consecutive_failures = 9
        w._config = {"use_clahe": False}
        w._overlay_lock = MagicMock()
        w._overlay = MagicMock()
        w._bound = False
        w._monitor = False
        w._paused = False
        w._move_armed = False
        w._sync = MagicMock()
        w._maybe_publish_status = MagicMock()
        w._reset_motion_region = MagicMock()

        w._processing_loop()

        assert w._board_locked is False
        w._reset_motion_region.assert_called_once_with()
        w._averager.reset.assert_called_once_with()

    def test_motion_rejection_skips_all_recognition_work_for_one_loop_iteration(self):
        w = _subprocess_motion_worker()
        frame = np.zeros((10, 10, 3), dtype=np.uint8)

        class OneFrameCamera:
            is_connected = True

            def read_frame(self):
                w._running = False
                return frame

        w._running = True
        w._camera = OneFrameCamera()
        w._process_commands = MagicMock()
        w._frame_count = 0
        w._motion_is_stable = MagicMock(return_value=False)
        w._board_finder.find_focus = MagicMock()
        w._detector = MagicMock()
        w._state_extractor = MagicMock()
        w._move_detector = MagicMock()
        w._bound = True
        w._monitor = False
        w._paused = False
        w._sync = MagicMock()
        w._maybe_publish_status = MagicMock()

        w._processing_loop()

        w._board_finder.find_focus.assert_not_called()
        w._detector.detect.assert_not_called()
        w._state_extractor.detections_to_board.assert_not_called()
        w._move_detector.detect_new_move.assert_not_called()
        w._sync.update.assert_not_called()

    def test_periodic_stable_log_includes_motion_roi_and_full_ratios(self, caplog):
        w = _subprocess_motion_worker()
        frame = np.zeros((10, 10, 3), dtype=np.uint8)

        class OneFrameCamera:
            is_connected = True

            def read_frame(self):
                w._running = False
                return frame

        w._running = True
        w._camera = OneFrameCamera()
        w._process_commands = MagicMock()
        w._frame_count = 29
        w._motion_is_stable = MagicMock(return_value=True)
        w._last_motion_roi_ratio = 0.125
        w._last_motion_full_ratio = 0.25
        w._board_finder.find_focus.return_value = (frame, True)
        w._config = {"use_clahe": False, "enhance": "none"}
        w._enhance_mode = "none"
        w._add_threshold = 0.5
        w._ae = None
        w._last_bstats = None
        w._averager.add.return_value = frame
        w._detector = MagicMock()
        w._detector.detect.return_value = []
        w._overlay_lock = MagicMock()
        w._overlay = MagicMock()
        w._lit_points = set()
        w._expected_np = None
        w._state_extractor = MagicMock()
        w._state_extractor.detections_to_board.return_value = np.zeros((19, 19), dtype=int)
        w._prev_observed_board = None
        w._last_stable_board = None
        w._last_detected_board = None
        w._bound = False
        w._monitor = False
        w._paused = False
        w._move_armed = False
        w._sync = MagicMock()
        w._maybe_publish_status = MagicMock()
        w._consecutive_failures = 0

        with caplog.at_level("INFO"):
            w._processing_loop()

        assert any("motion=roi:0.125/full:0.250" in record.message for record in caplog.records)


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
        w._motion_mask_cache = MagicMock()
        w._motion_filter = MagicMock()
        w._averager = MagicMock()
        w._promoter = MagicMock()
        w._lit_points = set()
        w._drain_or_process = w._process_commands
        _post_resync_reinjection_guard(w)
