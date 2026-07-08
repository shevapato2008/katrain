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
