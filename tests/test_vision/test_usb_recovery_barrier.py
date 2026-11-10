"""USB recovery is a loop-boundary barrier, independent of UI/hint pauses."""

import threading
import time
from unittest.mock import Mock

import numpy as np

from katrain.vision.config_service import VisionServiceConfig
from katrain.vision.ipc import ConfirmedMove
from katrain.vision.service import VisionService
from tests.test_vision.test_local_confirmation_window import worker, prepare, open_window, frame


def test_service_rejects_old_business_from_request_until_ack():
    service = VisionService(VisionServiceConfig())
    entered, finish = threading.Event(), threading.Event()

    def begin(timeout=2):
        entered.set()
        return finish.wait(timeout)

    service._worker = Mock(begin_usb_recovery=begin)
    service._pending_moves.append(ConfirmedMove(col=1, row=2, color=1))
    service._pending_events.append({"type": "synced"})
    result = []
    thread = threading.Thread(target=lambda: result.append(service.begin_usb_recovery()))
    thread.start()
    assert entered.wait(1)
    try:
        assert service.get_confirmed_move() is None
        assert service.poll_events() == []
        assert service.get_local_window_observation("old") is None
        assert not service.open_local_window(
            "new", np.zeros((19, 19)), expected_node_id=1, expected_color=1, deadline_monotonic=time.monotonic() + 5
        )
    finally:
        finish.set()
        thread.join(2)
    assert result == [True]
    assert not service._pending_moves and not service._pending_events


def test_worker_ack_waits_for_inference_then_discards_queues_and_window():
    result, camera = worker()
    prepare(result, camera)
    reference, expected = result._reference, result._expected_np.copy()
    open_window(result, "old")
    result._paused = True
    entered, finish = threading.Event(), threading.Event()

    def slow_detect(*args, **kwargs):
        entered.set()
        assert finish.wait(2)
        return []

    result._detector.detect.side_effect = slow_detect
    image = frame()
    camera.read_frame_identified = lambda: (image, 999, time.monotonic())
    result.start()
    assert entered.wait(1)
    ack = []
    pause = threading.Thread(target=lambda: ack.append(result.begin_usb_recovery(timeout=2)))
    pause.start()
    try:
        time.sleep(0.03)
        assert ack == []
        finish.set()
        pause.join(2)
        assert ack == [True]
        assert result._local_window is None
        assert result.get_event() is None
        calls = result._detector.detect.call_count
        time.sleep(0.03)
        assert result._detector.detect.call_count == calls
        assert result._paused is True
        assert result._reference is reference
        assert np.array_equal(result._expected_np, expected)
        assert result.get_status().camera_ready is True
        assert result.get_status().recognition_ready is False
    finally:
        finish.set()
        result.end_usb_recovery()
        result.stop()


def test_worker_timeout_does_not_leave_late_usb_pause():
    result, _ = worker()
    assert result.begin_usb_recovery(timeout=0.001) is False
    assert not result._usb_requested.is_set()


def test_service_without_ack_support_refuses_recovery():
    service = VisionService(VisionServiceConfig())
    service._worker = object()
    assert service.begin_usb_recovery(timeout=0) is False


def test_service_failed_ack_callback_unwinds_its_usb_request():
    service = VisionService(VisionServiceConfig())
    service._worker = Mock(begin_usb_recovery=Mock(return_value=True))
    service.set_usb_recovery_callback(lambda timeout: (_ for _ in ()).throw(RuntimeError("loop closed")))
    assert service.begin_usb_recovery() is False
    assert not service.usb_business_blocked
    service._worker.end_usb_recovery.assert_called_once()


def test_camera_status_is_real_while_business_waits_for_other_transport():
    from katrain.vision.hardware_recovery_gate import HardwareRecoveryGate
    from katrain.vision.ipc import WorkerStatus

    gate = HardwareRecoveryGate()
    service = VisionService(VisionServiceConfig(), recovery_gate=gate)
    service._worker = Mock(
        get_status=lambda: WorkerStatus(
            camera_status="connected", camera_ready=True, recognition_ready=True, local_confirmation_ready=True
        )
    )
    with gate.try_recovery():
        service.refresh_status()
        assert service.camera_status == "connected"
        assert service._latest_status.camera_ready is True
        assert service._latest_status.recognition_ready is False
    service.refresh_status()
    assert service._latest_status.recognition_ready is True


def test_queued_window_cannot_resurrect_after_ack_and_new_window_uses_fresh_frame():
    from tests.test_vision.test_local_confirmation_window import run

    result, camera = worker()
    prepare(result, camera)
    # This command was accepted immediately before the pause request, but had
    # not yet reached the worker. The boundary must consume and then retire it.
    from katrain.vision.ipc import CommandType, WorkerCommand

    result.send_command(
        WorkerCommand(
            CommandType.OPEN_LOCAL_WINDOW,
            {
                "token": "old",
                "expected_board": result._expected_np.tolist(),
                "expected_node_id": 1,
                "expected_color": 1,
                "opened_monotonic": time.monotonic(),
                "deadline_monotonic": time.monotonic() + 5,
            },
        )
    )
    result._usb_requested.set()
    assert result._usb_boundary() is True
    assert result._local_window is None
    assert result._cmd_queue.empty()
    result.end_usb_recovery()
    assert result.get_status().recognition_ready is False
    run(result, camera)
    assert result.get_status().local_confirmation_ready is True
    open_window(result, "fresh")
    assert result._local_window.token == "fresh"


def test_usb_ack_resets_old_sync_votes_without_replacing_authority_or_setup():
    result, camera = worker()
    prepare(result, camera)
    expected = result._sync._expected_board.copy()
    target = np.ones((19, 19), dtype=int)
    result._local_confirmation_mode = False
    result._sync.enter_setup_mode(target, setup_id="setup")
    result._sync._mismatch_count = 4
    result._sync._mismatch_board = target
    result._sync._missing_since[(1, 2)] = [0.0, 4]
    result._sync._degraded_timer_start = 0.0
    result._usb_requested.set()
    assert result._usb_boundary()
    assert result._sync._mismatch_count == 0
    assert result._sync._missing_since == {}
    assert result._sync._degraded_timer_start is None
    assert np.array_equal(result._sync._expected_board, expected)
    assert np.array_equal(result._sync._target_board, target)
    assert result._sync.state.value == "setup_in_progress"
