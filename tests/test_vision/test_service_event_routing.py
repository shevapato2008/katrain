"""poll_events must never swallow ConfirmedMove; get_confirmed_move must be FIFO."""

from katrain.vision.ipc import ConfirmedMove
from katrain.vision.service import VisionService
from katrain.vision.config_service import VisionServiceConfig


class FakeWorker:
    def __init__(self, events):
        self._events = list(events)

    def get_event(self):
        return self._events.pop(0) if self._events else None


def _service(events):
    svc = VisionService(VisionServiceConfig(enabled=True))
    svc._worker = FakeWorker(events)
    return svc


class TestEventRouting:
    def test_poll_events_preserves_moves_for_move_consumer(self):
        move = ConfirmedMove(col=3, row=4, color=1)
        svc = _service([{"type": "synced", "data": {}}, move])
        events = svc.poll_events()
        assert events == [{"type": "synced", "data": {}}]  # dict 事件正常返回
        assert svc.get_confirmed_move() == move  # 落子没有被 poll_events 吞掉

    def test_get_confirmed_move_is_fifo_and_requeues_nothing(self):
        m1 = ConfirmedMove(col=1, row=1, color=1)
        m2 = ConfirmedMove(col=2, row=2, color=2)
        svc = _service([m1, {"type": "degraded", "data": {}}, m2])
        assert svc.get_confirmed_move() == m1
        assert svc.get_confirmed_move() == m2
        assert svc.get_confirmed_move() is None
        assert svc.poll_events() == [{"type": "degraded", "data": {}}]


class TestQueueHygieneOnBindUnbind:
    """Review M1: a ConfirmedMove that arrived for the OLD bound session must never
    leak into a session bound afterwards. bind_session/unbind_session both clear
    the pending-moves deque so a stale camera confirmation from session A can't
    get injected once session B is bound. No worker attached (worker=None) so
    bind/unbind's send_command calls are no-ops -- these tests are about the
    main-process deque, not the IPC command."""

    def _service_no_worker(self):
        return VisionService(VisionServiceConfig(enabled=True))

    def test_unbind_clears_pending_moves(self):
        svc = self._service_no_worker()
        svc.bind_session("s1")
        svc._pending_moves.append(ConfirmedMove(col=3, row=3, color=1))
        svc.unbind_session()
        assert svc.get_confirmed_move() is None

    def test_cross_session_move_not_injected_after_rebind(self):
        svc = self._service_no_worker()
        svc.bind_session("s1")
        svc._pending_moves.append(ConfirmedMove(col=3, row=3, color=1))  # stale move for s1
        svc.unbind_session()
        svc.bind_session("s2")
        assert svc.get_confirmed_move() is None  # must NOT surface under s2

    def test_bind_also_clears_any_leftover_pending_moves(self):
        # Defensive: even if unbind was skipped (server crash/restart edge case),
        # a fresh bind must not inherit a stale queue either.
        svc = self._service_no_worker()
        svc._pending_moves.append(ConfirmedMove(col=5, row=5, color=2))
        svc.bind_session("s2")
        assert svc.get_confirmed_move() is None


def test_bound_authority_is_versioned_deduplicated_and_source_checked():
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    svc = _service([])
    svc._worker = MagicMock()
    a = SimpleNamespace(katrain=SimpleNamespace(game=object()))
    b = SimpleNamespace(katrain=SimpleNamespace(game=object()))
    svc.bind_session("a", session=a)
    source_a = svc.capture_binding_source("a", a)
    assert svc.publish_expected_from_stones(source_a, [], expected_node_id=1)
    revision_a = svc.expected_revision
    assert not svc.publish_expected_from_stones(source_a, [], expected_node_id=1)
    assert svc.expected_revision == revision_a
    assert svc.publish_expected_from_stones(source_a, [], expected_node_id=2)
    svc.bind_session("b", session=b)
    source_b = svc.capture_binding_source("b", b)
    assert source_b.binding_epoch != source_a.binding_epoch
    assert not svc.publish_expected_from_stones(source_a, [["B", [3, 15], None, 1]], expected_node_id=3)
    assert svc.expected_revision == 0
    assert svc.publish_expected_from_stones(source_b, [], expected_node_id=1)
    assert svc._worker.send_command.call_args.args[0].data["binding_epoch"] == source_b.binding_epoch


def test_old_stamped_ipc_cannot_cross_binding_or_authority_revision():
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    svc = VisionService(VisionServiceConfig())
    worker = FakeWorker([])
    worker.send_command = MagicMock()
    svc._worker = worker
    a = SimpleNamespace(katrain=SimpleNamespace(game=object()))
    b = SimpleNamespace(katrain=SimpleNamespace(game=object()))
    svc.bind_session("a", session=a)
    source = svc.capture_binding_source("a", a)
    svc.publish_expected_from_stones(source, [], expected_node_id=1)
    old = ConfirmedMove(3, 3, 1, 8, svc.binding_epoch, svc.expected_revision)
    worker._events = [old]
    svc.poll_events()  # split deque populated before the authority changes
    svc.publish_expected_from_stones(source, [], expected_node_id=2)
    assert svc.get_confirmed_move() is None
    svc.bind_session("b", session=b)
    worker._events = [
        {"type": "illegal_change", "binding_epoch": old.binding_epoch, "data": {"positions": [[3, 3, 1]]}},
        old,
    ]
    assert svc.poll_events() == []
    assert svc.get_confirmed_move() is None


def test_recapturing_source_cannot_upgrade_replaced_game_under_old_binding():
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    svc = VisionService(VisionServiceConfig())
    svc._worker = MagicMock()
    session = SimpleNamespace(katrain=SimpleNamespace(game=object()))
    svc.bind_session("s", session=session)
    old_source = svc.capture_binding_source("s", session)
    svc.publish_expected_from_stones(old_source, [], expected_node_id=1)
    revision = svc.expected_revision
    session.katrain.game = object()
    recaptured = svc.capture_binding_source("s", session)
    assert not svc.source_is_current(old_source)
    assert not svc.source_is_current(recaptured)
    assert not svc.publish_expected_from_stones(recaptured, [["B", [3, 15], None, 1]], expected_node_id=2)
    assert svc.expected_revision == revision


def _reference_service():
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    svc = VisionService(VisionServiceConfig())
    svc._worker = MagicMock()
    svc._worker.get_event.return_value = None
    session = SimpleNamespace(katrain=SimpleNamespace(game=object(), game_type="play_ai"))
    svc.bind_session("s", session=session)
    source = svc.capture_binding_source("s", session)
    svc.publish_expected_from_stones(source, [], expected_node_id=16)
    move = ConfirmedMove(3, 3, 1, 8, svc.binding_epoch, svc.expected_revision)
    return svc, session, source, move


def test_reference_source_survives_only_redundant_bind_and_keeps_epoch_fence():
    from katrain.vision.ipc import CommandType

    svc, session, source, move = _reference_service()
    initial = svc.capture_reference_baseline(source, move)
    svc._pending_moves.append(move)
    svc.bind_session("s", session=session)
    bind = svc._worker.send_command.call_args.args[0]
    assert bind.action == CommandType.BIND
    assert bind.data["source_nonce"] == initial.source_nonce
    assert bind.data["worker_generation"] == initial.worker_generation
    assert bind.data["preserve_reference"] is True
    assert svc.binding_epoch != move.binding_epoch
    assert svc.get_confirmed_move() is None
    assert svc.capture_reference_baseline(source, move) is None
    sid = "s"
    for change in ("game", "session", "session_id", "mode", "worker"):
        old = bind.data["source_nonce"]
        if change == "game":
            session.katrain.game = object()
        elif change == "session":
            from types import SimpleNamespace

            session = SimpleNamespace(katrain=session.katrain)
        elif change == "session_id":
            sid = "other"
        elif change == "mode":
            session.katrain.game_type = "pvp_local"
        elif change == "worker":
            from unittest.mock import MagicMock

            svc._worker = MagicMock()
        svc.bind_session(sid, session=session)
        bind = svc._worker.send_command.call_args.args[0]
        assert bind.data["source_nonce"] != old
        assert bind.data["preserve_reference"] is False


def test_accepted_reference_publishes_exact_target_then_receipt_and_rejects_stale():
    import hashlib
    import numpy as np
    from dataclasses import replace
    from katrain.vision.ipc import CommandType

    svc, session, source, move = _reference_service()
    baseline = svc.capture_reference_baseline(source, move)
    board = [[0] * 19 for _ in range(19)]
    board[3][3] = 1
    assert not svc.publish_accepted_reference(source, move, baseline, 17, 999, board)
    assert not svc.publish_accepted_reference(source, move, replace(baseline, board_digest="wrong"), 17, 16, board)
    svc._worker.send_command.reset_mock()
    assert svc.publish_accepted_reference(source, move, baseline, 17, 16, board)
    commands = [c.args[0] for c in svc._worker.send_command.call_args_list]
    assert [c.action for c in commands] == [CommandType.SET_EXPECTED_BOARD, CommandType.ACCEPT_REFERENCE_CANDIDATE]
    expected, receipt = commands
    assert receipt.data["move_token"] == move.token
    assert receipt.data["baseline_target"] == baseline
    assert receipt.data["accepted_target"].expected_node_id == 17
    assert receipt.data["accepted_target"].expected_revision == expected.data["expected_revision"]
    assert expected.data["board_digest"] == hashlib.sha256(np.asarray(board, dtype=np.int8).tobytes()).hexdigest()
    assert receipt.data["accepted_board"] == board
    board[0][0] = 2
    assert receipt.data["accepted_board"][0][0] == 0
    # A newer AI target is authoritative even if no photograph exists for it yet.
    svc.publish_expected_from_stones(source, [["B", [3, 15]], ["W", [4, 14]]], expected_node_id=18)
    before = svc._worker.send_command.call_count
    assert not svc.publish_accepted_reference(source, move, baseline, 17, 16, board)
    assert svc._worker.send_command.call_count == before
    session.katrain.game = object()
    assert not svc.publish_accepted_reference(source, move, baseline, 17, 16, board)


def test_reference_worker_start_rotates_generation_and_forwards_lighting(monkeypatch):
    from unittest.mock import MagicMock
    import katrain.vision.worker_inprocess as worker_module

    owner = object()
    factory = MagicMock()
    monkeypatch.setattr(worker_module, "InProcessAdapter", factory)
    svc = VisionService(VisionServiceConfig(process_mode="inprocess"), lighting_owner=owner, lighting_disabled=False)
    svc.start()
    first = svc._worker_generation
    svc.stop()
    svc.start()
    assert svc._worker_generation != first
    assert factory.call_args.kwargs["lighting_owner"] is owner
    assert factory.call_args.kwargs["lighting_disabled"] is False


def test_reference_receipt_reuses_exact_already_published_target_only():
    from katrain.vision.ipc import CommandType

    svc, session, source, move = _reference_service()
    baseline = svc.capture_reference_baseline(source, move)
    board = [[0] * 19 for _ in range(19)]
    board[3][3] = 1
    svc.publish_expected_from_stones(source, [["B", [3, 15]]], expected_node_id=17)
    revision = svc.expected_revision
    svc._worker.send_command.reset_mock()
    assert svc.publish_accepted_reference(source, move, baseline, 17, 16, board)
    assert svc.expected_revision == revision
    assert svc._worker.send_command.call_count == 1
    assert svc._worker.send_command.call_args.args[0].action == CommandType.ACCEPT_REFERENCE_CANDIDATE


def test_reference_mode_change_rotates_nonce_and_force_rearm_keeps_target():
    svc, session, source, move = _reference_service()
    baseline = svc.capture_reference_baseline(source, move)
    assert svc.capture_reference_baseline(source, ConfirmedMove(3, 3, 1, 8, move.binding_epoch, 999)) is None
    assert not svc.publish_expected_from_stones(source, [], expected_node_id=16, force_rearm=True)
    assert svc.capture_reference_baseline(source, move) == baseline
    svc._worker.supports_local_confirmation = True
    svc.set_local_confirmation_mode(True, session_id="s", game_id="g")
    assert svc._source_nonce != baseline.source_nonce
    assert svc.capture_reference_baseline(source, move) is None
    svc.set_local_confirmation_mode(False, session_id="s", game_id="g")
    assert svc.publish_expected_from_stones(source, [], expected_node_id=16)
    fresh = ConfirmedMove(3, 3, 1, 9, svc.binding_epoch, svc.expected_revision)
    assert svc.capture_reference_baseline(source, fresh).source_nonce != baseline.source_nonce
    # Undo revisits a lower/earlier node through a new revision, without node ordering.
    revision = svc.expected_revision
    svc.publish_expected_from_stones(source, [], expected_node_id=1)
    assert svc.expected_revision > revision


def test_local_mode_command_carries_current_reference_source_identity():
    from katrain.vision.ipc import CommandType

    svc, session, source, move = _reference_service()
    svc._worker.supports_local_confirmation = True
    old_nonce = svc._source_nonce
    assert svc.set_local_confirmation_mode(True, session_id="s", game_id="g")
    command = svc._worker.send_command.call_args.args[0]
    assert command.action == CommandType.SET_LOCAL_CONFIRMATION_MODE
    assert command.data["source_nonce"] == svc._source_nonce != old_nonce
    assert command.data["worker_generation"] == svc._worker_generation
    assert svc.set_local_confirmation_mode(False, session_id="s", game_id="g")
    nonce = svc._source_nonce
    assert svc.set_local_confirmation_mode(False, session_id="s", game_id="other")
    assert svc._worker.send_command.call_args.args[0].data["source_nonce"] == nonce


def test_local_completion_publishes_exact_target_before_complete_and_fences_replaced_source(monkeypatch):
    import time
    import numpy as np
    from katrain.vision.ipc import CommandType

    svc, session, source, move = _reference_service()
    svc._worker.supports_local_confirmation = True
    assert svc.set_local_confirmation_mode(True, session_id="s", game_id="g")
    svc.publish_expected_from_stones(source, [], expected_node_id=16)
    monkeypatch.setattr(VisionService, "local_confirmation_ready", property(lambda self: True))
    board = np.zeros((19, 19), dtype=np.int8)
    assert svc.open_local_window(
        "window", board, expected_node_id=16, expected_color=1, deadline_monotonic=time.monotonic() + 10
    )
    board[3, 3] = 1
    svc._worker.send_command.reset_mock()
    assert svc.complete_local_window("window", board, expected_node_id=17)
    commands = [call.args[0] for call in svc._worker.send_command.call_args_list]
    assert [command.action for command in commands] == [
        CommandType.SET_EXPECTED_BOARD,
        CommandType.COMPLETE_LOCAL_WINDOW,
    ]
    expected, complete = commands
    assert complete.data["accepted_target"] == svc._reference_target
    assert complete.data["accepted_target"].expected_node_id == 17
    assert complete.data["accepted_target"].expected_revision == expected.data["expected_revision"]
    assert complete.data["source_nonce"] == expected.data["source_nonce"] == svc._source_nonce
    assert complete.data["worker_generation"] == svc._worker_generation
    assert complete.data["accepted_board"] == board.tolist()
    assert not svc.complete_local_window("window", board, expected_node_id=17)
    assert svc.open_local_window(
        "stale", board, expected_node_id=17, expected_color=2, deadline_monotonic=time.monotonic() + 10
    )
    session.katrain.game = object()
    before = svc._worker.send_command.call_count
    assert not svc.complete_local_window("stale", board, expected_node_id=18)
    assert svc._worker.send_command.call_count == before
