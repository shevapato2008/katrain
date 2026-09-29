import asyncio

from katrain.vision.ipc import ConfirmedMove
from katrain.web.core.vision_pump import route_vision_event, route_vision_attention


def _drain(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


class TestRouteVisionEvent:
    def test_dict_event_broadcast_to_all_clients(self):
        q1, q2, moves = asyncio.Queue(), asyncio.Queue(), asyncio.Queue()
        evt = {"type": "setup_complete", "data": {}}
        route_vision_event(evt, [q1, q2], moves, bound=False)
        assert _drain(q1) == [evt] and _drain(q2) == [evt]
        assert moves.empty()

    def test_confirmed_move_routed_to_move_queue_when_bound(self):
        q1, moves = asyncio.Queue(), asyncio.Queue()
        mv = ConfirmedMove(col=3, row=4, color=1)
        route_vision_event(mv, [q1], moves, bound=True)
        assert _drain(moves) == [mv]
        assert q1.empty()

    def test_confirmed_move_dropped_when_not_bound(self):
        q1, moves = asyncio.Queue(), asyncio.Queue()
        route_vision_event(ConfirmedMove(col=3, row=4, color=1), [q1], moves, bound=False)
        assert moves.empty() and q1.empty()


def test_illegal_change_routes_vision_row_col_points_to_attention_once_bound():
    class Attention:
        def __init__(self):
            self.shown = []
            self.cleared = []

        def show_attention(self, points, source):
            self.shown.append((points, source))

        def clear_attention(self, source):
            self.cleared.append(source)

    attention = Attention()
    evt = {"type": "illegal_change", "data": {"positions": [[18, 4, 1]], "missing": [[0, 5, 2]]}}
    route_vision_attention(evt, attention, bound=False)
    assert attention.shown == []
    route_vision_attention(evt, attention, bound=True)
    assert attention.shown == [([(18, 4), (0, 5)], "vision")]
    route_vision_attention({"type": "synced"}, attention, bound=True)
    assert attention.cleared == ["vision"]
