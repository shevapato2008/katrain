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
