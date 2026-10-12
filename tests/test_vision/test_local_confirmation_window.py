"""Local confirmation uses the production pipeline, with one isolated observation window."""

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from katrain.vision.board_state import BoardStateExtractor
from katrain.vision.config import BoardConfig, DEFAULT_MARGIN_CELLS
from katrain.vision.config_service import VisionServiceConfig
from katrain.vision.ipc import CommandType, ConfirmedMove, WorkerCommand
from katrain.vision.service import VisionService
from katrain.vision.stone_detector import Detection
from katrain.vision.worker_inprocess import InProcessAdapter


CONFIG = BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS)


class Camera:
    is_connected = True

    def __init__(self):
        self.worker = None
        self.script = []
        self.reads = 0

    def read_frame_identified(self):
        self.reads += 1
        seq, ts, frame = self.script.pop(0)
        if not self.script:
            self.worker._running = False
        return frame, seq, ts

    def read_frame(self):
        raise AssertionError("local mode must read the camera identity")


def board(stones=()):
    result = np.zeros((19, 19), dtype=int)
    for row, col, color in stones:
        result[row, col] = color
    return result


def frame():
    return np.random.default_rng(7).integers(80, 200, (240, 240, 3), dtype=np.uint8)


def detection(row=3, col=3, color=1, confidence=0.9):
    x = (CONFIG.border_width_mm + col * CONFIG.grid_spacing_w) / CONFIG.total_width * 240
    y = (CONFIG.border_length_mm + row * CONFIG.grid_spacing_l) / CONFIG.total_length * 240
    return Detection(
        x_center=x, y_center=y, class_id=color - 1, confidence=confidence, bbox=(x - 5, y - 5, x + 5, y + 5)
    )


def worker(*, pose_locked=True):
    camera = Camera()
    with patch("katrain.vision.worker_inprocess.StoneDetector"):
        result = InProcessAdapter(
            {"enhance": "off", "auto_exposure": "off", "reference_check": "on", "capture_fps": 100000},
            camera=camera,
        )
    camera.worker = result
    result._bound = True
    result._geometry = SimpleNamespace(points=None)
    result._expected_np = board()
    result._move_detector.force_sync(board())
    result._sync.bind()
    if pose_locked:
        result._sync.confirm_pose_lock()
    result._warp_frame = lambda image: (image, True)
    result._motion_is_stable = MagicMock(return_value=True)
    result._maybe_send_preview = MagicMock()
    result._active_extractor = lambda: BoardStateExtractor(CONFIG)
    result._detector.detect.return_value = []
    return result, camera


def command(result, name, **data):
    result.send_command(WorkerCommand(action=getattr(CommandType, name), data=data))
    result._drain_commands()


def run(result, camera, *, n=1, image=None, identities=None):
    image = frame() if image is None else image
    now = time.monotonic()
    camera.script = identities or [(100 + camera.reads + i, now + 0.001 * i, image) for i in range(n)]
    result._running = True
    result._loop()


def prepare(result, camera):
    command(result, "SET_LOCAL_CONFIRMATION_MODE", enabled=True, session_id="session")
    run(result, camera)
    assert result.get_status().local_confirmation_ready
    result._detector.reset_mock()


def open_window(result, token="turn", *, opened=None):
    command(
        result,
        "OPEN_LOCAL_WINDOW",
        token=token,
        expected_board=board().tolist(),
        expected_node_id=12,
        expected_color=1,
        opened_monotonic=time.monotonic() if opened is None else opened,
        deadline_monotonic=time.monotonic() + 10,
    )


def events(result):
    output = []
    while (event := result.get_event()) is not None:
        output.append(event)
    return output


def test_bootstrap_stops_inference_when_reference_is_ready_and_emits_no_move_or_sync_events():
    result, camera = worker()
    command(result, "SET_LOCAL_CONFIRMATION_MODE", enabled=True, session_id="session")
    run(result, camera, n=4)
    assert result._reference is not None
    assert result._detector.detect.call_count == 1
    assert result.get_status().local_confirmation_ready
    assert events(result) == []
    assert camera.reads == 4


def test_open_and_cancel_preserve_reference_denials_and_suspicion_but_reset_window_accumulators():
    result, camera = worker()
    prepare(result, camera)
    reference = result._reference
    denial = np.ones(10)
    result._denied[(4, 4)] = denial
    result._move_detector.charge_carded_confirmation(3, 3)
    result._conf_peak.observe((3, 3, 1), {(3, 3): 0.95})
    result._averager.add(frame())
    open_window(result)
    assert result._reference is reference
    assert result._denied[(4, 4)] is denial
    assert result._move_detector.suspicion_of(3, 3) == 1
    assert result._move_detector.pending_move is None
    assert result._conf_peak.peak_for((3, 3, 1)) is None
    assert len(result._averager._frames) == 0
    command(result, "CANCEL_LOCAL_WINDOW", token="stale")
    assert result._local_window is not None
    command(result, "CANCEL_LOCAL_WINDOW", token="turn")
    assert result._local_window is None
    assert result._reference is reference


def test_reference_veto_is_applied_inside_local_window_even_when_free_play_is_paused():
    result, camera = worker()
    prepare(result, camera)
    result._paused = True
    result._detector.detect.return_value = [detection()]
    open_window(result)
    run(result, camera, n=6)
    local = events(result)
    assert len(local) == 6
    assert all(event.token == "turn" and event.candidate is None for event in local)
    assert all(event.board == board().tolist() for event in local)
    assert result._detector.detect.call_count == 6


def test_window_uses_multiframe_confidence_candidate_and_never_emits_a_normal_confirmed_move():
    result, camera = worker()
    prepare(result, camera)
    result._detector.detect.return_value = [detection()]
    # Actual occupancy changes the pixels, so the reference must not veto it.
    changed = frame().copy()
    changed[35:65, 35:65] = 15
    open_window(result)
    run(result, camera, n=5, image=changed)
    local = events(result)
    assert len(local) == 5
    assert all(not isinstance(event, ConfirmedMove) for event in local)
    assert local[0].candidate is None and local[1].candidate is None
    assert local[2].candidate == ConfirmedMove(col=3, row=3, color=1, observation_seq=4)
    assert local[-1].candidate == local[2].candidate
    assert local[-1].board == board([(3, 3, 1)]).tolist()
    assert local[-1].camera_seq == 105


def test_click_prefers_new_camera_frames_and_duplicate_camera_ids_never_count_as_observations():
    result, camera = worker()
    prepare(result, camera)
    opened = time.monotonic()
    open_window(result, opened=opened)
    before = result._observation_seq
    run(
        result,
        camera,
        identities=[
            (101, opened - 0.01, frame()),
            (102, opened + 0.01, frame()),
            (102, opened + 0.01, frame()),
            (103, opened + 0.03, frame()),
        ],
    )
    local = events(result)
    assert [event.camera_seq for event in local] == [102, 103]
    assert result._observation_seq == before + 2
    assert result._detector.detect.call_count == 2


def test_complete_refreshes_reference_using_the_last_raw_window_frame_and_no_new_inference():
    result, camera = worker()
    prepare(result, camera)
    result._detector.detect.return_value = [detection()]
    changed = frame().copy()
    changed[35:65, 35:65] = 15
    open_window(result)
    run(result, camera, n=3, image=changed)
    expected = board([(3, 3, 1)])
    reads, inferences = camera.reads, result._detector.detect.call_count
    command(result, "COMPLETE_LOCAL_WINDOW", token="turn", accepted_board=expected.tolist(), expected_node_id=13)
    assert result._local_window is None
    assert np.array_equal(result._expected_np, expected)
    assert np.array_equal(result._reference.board, expected)
    assert camera.reads == reads and result._detector.detect.call_count == inferences


def test_repeated_mode_command_does_not_restart_bootstrap_or_destroy_reference():
    result, camera = worker()
    prepare(result, camera)
    reference = result._reference
    command(result, "SET_LOCAL_CONFIRMATION_MODE", enabled=True, session_id="session")
    run(result, camera, n=2)
    assert result._reference is reference
    result._detector.detect.assert_not_called()


def test_expired_bootstrap_stops_inference_and_reports_unavailable():
    result, camera = worker()
    command(result, "SET_LOCAL_CONFIRMATION_MODE", enabled=True, session_id="session")
    result._local_bootstrap_deadline = time.monotonic() - 1
    run(result, camera)
    result._detector.detect.assert_not_called()
    assert not result.get_status().local_confirmation_ready
    assert result.get_status().local_confirmation_bootstrap_state == "unavailable"


def test_shadow_reference_mode_cannot_claim_physical_confirmation_capability():
    result, camera = worker()
    result._ref_mode = "shadow"
    assert result.supports_local_confirmation is False
    command(result, "SET_LOCAL_CONFIRMATION_MODE", enabled=True, session_id="s")
    run(result, camera)
    result._detector.detect.assert_not_called()
    assert result.get_status().local_confirmation_bootstrap_state == "unavailable"


def test_sub_add_real_stone_is_pending_before_ambiguous_promotion_and_cannot_become_a_candidate():
    result, camera = worker()
    prepare(result, camera)
    result._detector.detect.return_value = [detection(confidence=0.4)]
    changed = frame().copy()
    changed[35:65, 35:65] = 15
    open_window(result)
    run(result, camera, n=4, image=changed)
    local = events(result)
    assert all(event.candidate is None and event.pending for event in local)
    assert all(event.board == board().tolist() for event in local)


def test_complete_does_not_capture_a_raw_disagreement_corrected_only_by_the_reference():
    result, camera = worker()
    prepare(result, camera)
    original = result._reference
    result._detector.detect.return_value = [detection()]
    open_window(result)
    run(result, camera, n=3)
    result._ref_taken_at = time.monotonic() - 61
    command(result, "COMPLETE_LOCAL_WINDOW", token="turn", accepted_board=board().tolist(), expected_node_id=13)
    assert result._reference is original


def test_expired_window_stops_inference_and_old_cancel_cannot_close_the_next_one():
    result, camera = worker()
    prepare(result, camera)
    open_window(result, token="one")
    result._local_window.deadline_monotonic = time.monotonic() - 1
    run(result, camera)
    assert result._local_window is None
    result._detector.detect.assert_not_called()
    open_window(result, token="two")
    command(result, "CANCEL_LOCAL_WINDOW", token="one")
    assert result._local_window.token == "two"


def test_complete_cannot_capture_a_frame_that_was_lit_even_if_the_lamps_are_now_off():
    result, camera = worker()
    prepare(result, camera)
    original = result._reference
    result._detector.detect.return_value = [detection()]
    changed = frame().copy()
    changed[35:65, 35:65] = 15
    open_window(result)
    result._lit_points = {(0, 0)}
    run(result, camera, n=3, image=changed)
    result._lit_points.clear()
    command(
        result, "COMPLETE_LOCAL_WINDOW", token="turn", accepted_board=board([(3, 3, 1)]).tolist(), expected_node_id=13
    )
    assert result._reference is original


def test_service_routes_only_the_current_local_window_and_rejects_unsupported_workers():
    from katrain.vision.ipc import LocalWindowObservation

    service = VisionService(VisionServiceConfig(enabled=True))
    service._worker = SimpleNamespace(supports_local_confirmation=False)
    assert service.set_local_confirmation_mode(True, session_id="s") is False
    assert (
        service.open_local_window(
            "a", board(), expected_node_id=1, expected_color=1, deadline_monotonic=time.monotonic() + 10
        )
        is False
    )
    result, camera = worker()
    prepare(result, camera)
    service._worker = result
    assert service.set_local_confirmation_mode(True, session_id="s") is True
    result._drain_commands()
    run(result, camera)
    assert service.open_local_window(
        "b", board(), expected_node_id=1, expected_color=1, deadline_monotonic=time.monotonic() + 10
    )
    stale = LocalWindowObservation(token="a", board=board().tolist(), observation_seq=1, camera_seq=1, camera_ts=1)
    fresh = LocalWindowObservation(
        token="b",
        board=board().tolist(),
        observation_seq=2,
        camera_seq=2,
        camera_ts=time.monotonic() + 1,
        session_id="s",
    )
    result._event_queue.put(stale)
    result._event_queue.put(ConfirmedMove(3, 3, 1))
    result._event_queue.put(fresh)
    assert service.poll_events() == []
    assert service.get_confirmed_move() is None
    assert service.get_local_window_observation("b") == fresh
    assert service.get_local_window_observation("b") is None


def test_service_cannot_treat_another_sessions_ready_status_as_its_bootstrap_result():
    result, camera = worker()
    prepare(result, camera)
    service = VisionService(VisionServiceConfig(enabled=True))
    service._worker = result
    service.set_local_confirmation_mode(True, session_id="new-session")
    assert service.local_confirmation_ready is False


def test_duplicate_camera_frame_does_not_advance_the_motion_stability_accumulator():
    result, camera = worker()
    prepare(result, camera)
    opened = time.monotonic()
    open_window(result, opened=opened)
    result._motion_is_stable.reset_mock()
    image = frame()
    run(result, camera, identities=[(101, opened + 0.01, image), (101, opened + 0.01, image)])
    assert result._motion_is_stable.call_count == 1


def test_cancel_removes_the_stale_confirmation_that_would_keep_idle_exposure_muted():
    result, camera = worker()
    prepare(result, camera)
    open_window(result)
    result._move_detector.detect_new_move(board([(3, 3, 1)]))
    result._move_detector.detect_new_move(board([(3, 3, 1)]))
    assert result._move_detector.about_to_confirm
    command(result, "CANCEL_LOCAL_WINDOW", token="turn")
    assert not result._move_detector.about_to_confirm


def test_a_disconnected_camera_cannot_reuse_reference_readiness():
    result, camera = worker()
    prepare(result, camera)
    camera.is_connected = False
    result._publish_status(None)
    assert result.get_status().camera_ready is False
    assert result.get_status().local_confirmation_ready is False


def test_same_session_new_game_rebuilds_reference_and_same_game_reconnect_preserves_it():
    result, camera = worker()
    service = VisionService(VisionServiceConfig(enabled=True))
    service._worker = result
    service.set_local_confirmation_mode(True, session_id="session", game_id="game-one")
    result._drain_commands()
    run(result, camera)
    assert service.local_confirmation_ready
    reference = result._reference

    service.set_local_confirmation_mode(True, session_id="session", game_id="game-one")
    result._drain_commands()
    assert result._reference is reference and service.local_confirmation_ready

    service.set_local_confirmation_mode(True, session_id="session", game_id="game-two")
    assert not service.local_confirmation_ready
    assert service.local_confirmation_bootstrap_state == "bootstrap"
    result._drain_commands()
    assert result._reference is None
    assert not service.local_confirmation_ready
    run(result, camera)
    assert service.local_confirmation_ready and result._reference is not reference


def test_explicit_bootstrap_retry_waits_for_the_new_attempt_instead_of_old_unavailable_status():
    result, camera = worker()
    service = VisionService(VisionServiceConfig(enabled=True))
    service._worker = result
    service.set_local_confirmation_mode(True, session_id="session")
    result._drain_commands()
    result._local_bootstrap_deadline = time.monotonic() - 1
    run(result, camera)
    assert service.local_confirmation_bootstrap_state == "unavailable"

    service.set_local_confirmation_mode(False, session_id="session")
    service.set_local_confirmation_mode(True, session_id="session")
    assert service.local_confirmation_bootstrap_state == "bootstrap"
    assert not service.local_confirmation_ready
    result._drain_commands()
    assert service.local_confirmation_bootstrap_state == "bootstrap"
    run(result, camera)
    assert service.local_confirmation_ready


def bound_local(result, session_id="session", game_id="game"):
    service = VisionService(VisionServiceConfig(enabled=True))
    service._worker = result
    service.bind_session(session_id)
    service.set_expected_from_stones([], expected_node_id=12)
    service.set_local_confirmation_mode(True, session_id=session_id, game_id=game_id)
    result._drain_commands()
    return service


def test_real_bind_bootstrap_locks_pose_then_first_confirmation_closes_without_idle_inference():
    result, camera = worker(pose_locked=False)
    service = bound_local(result)
    assert result._sync.state.value == "calibrating"
    run(result, camera, n=4)
    assert result._reference is not None and service.local_confirmation_ready
    assert result.get_status().pose_lock_status == "locked"
    assert result.get_status().sync_state == "synced"
    assert result._detector.detect.call_count == 1 and events(result) == []

    opened = time.monotonic()
    assert service.open_local_window(
        "first", board(), expected_node_id=12, expected_color=1, deadline_monotonic=opened + 8
    )
    result._drain_commands()
    result._detector.detect.return_value = [detection()]
    changed = frame().copy()
    changed[35:65, 35:65] = 15
    run(result, camera, n=3, image=changed)
    observation = service.get_local_window_observation("first")
    assert observation.candidate is not None
    service.complete_local_window("first", board([(3, 3, 1)]), expected_node_id=13)
    result._drain_commands()
    assert result._local_window is None
    inferences = result._detector.detect.call_count
    run(result, camera, n=3, image=changed)
    assert result._detector.detect.call_count == inferences and events(result) == []


def test_early_first_stone_rejects_reference_then_explicit_retry_prepares_real_empty_reference():
    result, camera = worker(pose_locked=False)
    service = bound_local(result)
    result._detector.detect.return_value = [detection()]
    run(result, camera, n=2)
    assert result._reference is None and not service.local_confirmation_ready
    result._local_bootstrap_deadline = time.monotonic() - 1
    run(result, camera)
    assert service.local_confirmation_bootstrap_state == "unavailable"
    assert result.get_status().pose_lock_status == "unlocked"
    result._detector.detect.return_value = []
    service.set_local_confirmation_mode(False, session_id="session", game_id="game")
    service.set_local_confirmation_mode(True, session_id="session", game_id="game")
    result._drain_commands()
    run(result, camera, n=3)
    assert service.local_confirmation_ready and np.array_equal(result._reference.board, board())
    assert result.get_status().pose_lock_status == "locked"
    assert result.get_status().sync_state == "synced" and events(result) == []


@pytest.mark.parametrize("value,reason", [(255, "frame_overexposed"), (10, "frame_underexposed")])
def test_severe_raw_window_frames_emit_honest_lighting_evidence_and_clear_candidate_immediately(value, reason):
    result, camera = worker()
    prepare(result, camera)
    opened = time.monotonic()
    open_window(result, opened=opened)
    result._local_window.candidate = ConfirmedMove(col=3, row=3, color=1)
    severe = np.full_like(frame(), value)
    run(result, camera, identities=[(101 + i, opened + t, severe) for i, t in enumerate((0.01, 0.2, 0.4, 1.02))])
    local = events(result)
    assert len(local) == 4
    assert all(event.candidate is None and event.board == [] for event in local)
    assert [event.exposure["confirmed"] for event in local] == [False, False, False, True]
    assert local[-1].exposure["reason"] == reason
    assert local[-1].exposure["bad_frames"] == 4
    assert local[-1].exposure["span_ms"] >= 1000
    result._detector.detect.assert_not_called()


@pytest.mark.parametrize("interrupt", ["normal", "motion", "missing", "duplicate", "late", "direction", "controls"])
def test_lighting_continuity_is_reset_by_raw_worker_interruptions(interrupt):
    result, camera = worker()
    prepare(result, camera)
    opened = time.monotonic()
    open_window(result, opened=opened)
    severe = np.full_like(frame(), 255)
    run(result, camera, identities=[(101, opened + 0.01, severe), (102, opened + 0.2, severe)])
    events(result)
    image, seq, ts = severe, 103, opened + 0.4
    if interrupt == "normal":
        image = frame()
    elif interrupt == "motion":
        result._motion_is_stable.return_value = False
    elif interrupt == "missing":
        image = None
    elif interrupt == "duplicate":
        seq, ts = 102, opened + 0.2
    elif interrupt == "late":
        ts = opened - 0.1
    elif interrupt == "direction":
        image = np.full_like(frame(), 10)
    elif interrupt == "controls":
        camera.controls_effective = None
        camera.request_controls = MagicMock()
    run(result, camera, identities=[(seq, ts, image)])
    events(result)
    result._motion_is_stable.return_value = True
    camera.controls_effective = True
    run(result, camera, identities=[(104, opened + 1.5, severe), (105, opened + 2, severe)])
    local = events(result)
    assert local[-1].exposure["bad_frames"] == 2
    assert local[-1].exposure["confirmed"] is False


@pytest.mark.parametrize("value", [100, 190])
def test_mild_exposure_outside_ae_target_preserves_the_normal_board_pipeline(value):
    result, camera = worker()
    prepare(result, camera)
    open_window(result)
    run(result, camera, image=np.full_like(frame(), value))
    local = events(result)
    assert len(local) == 1 and local[0].exposure["reason"] is None
    assert local[0].board == board().tolist()
    result._detector.detect.assert_called_once()


def test_lighting_uses_raw_board_warp_before_average_and_enhancement():
    result, camera = worker()
    prepare(result, camera)
    open_window(result)
    severe = np.full_like(frame(), 255)
    result._warp_frame = lambda image: (severe, True)
    with patch("katrain.vision.worker_inprocess.enhance_for_inference", return_value=frame()) as enhance:
        run(result, camera, image=frame())
    local = events(result)
    assert local[0].exposure["reason"] == "frame_overexposed"
    assert local[0].exposure["median"] == 255
    enhance.assert_not_called()


def test_old_mode_generation_and_geometry_loss_cannot_publish_local_pose_ready():
    result, camera = worker(pose_locked=False)
    service = bound_local(result)
    run(result, camera)
    generation = result._local_mode_generation
    service.set_local_confirmation_mode(True, session_id="session", game_id="new-game")
    result._drain_commands()
    command(
        result,
        "SET_LOCAL_CONFIRMATION_MODE",
        enabled=True,
        session_id="session",
        game_id="game",
        mode_generation=generation,
    )
    assert not service.local_confirmation_ready and result._reference is None
    assert result.get_status().pose_lock_status == "unlocked"
    run(result, camera)
    assert service.local_confirmation_ready
    result.set_geometry(None)
    result._publish_status(None)
    assert not service.local_confirmation_ready
    assert result.get_status().pose_lock_status == "unlocked"


def test_lighting_metadata_is_optional_and_survives_ipc_pickle_roundtrip():
    import pickle
    from katrain.vision.ipc import LocalWindowObservation

    observation = LocalWindowObservation(token="turn", board=[], observation_seq=1, camera_seq=1, camera_ts=1)
    assert observation.exposure is None
    observation.exposure = {"reason": "frame_overexposed", "bad_frames": 3, "span_ms": 1000, "confirmed": True}
    assert pickle.loads(pickle.dumps(observation)).exposure == observation.exposure
