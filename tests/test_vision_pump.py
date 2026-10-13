import asyncio
from types import SimpleNamespace

from katrain.vision.ipc import ConfirmedMove
from katrain.web.core.vision_pump import is_stale_illegal_change, route_vision_event, route_vision_attention


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


def test_accepted_first_stone_does_not_become_a_late_mismatch():
    # The Golaxy tunnel has accepted Q4 (core 15,3), while vision still compares
    # its (top-origin) frame against the old empty board for one more frame.
    state = {"board_size": [19, 19], "stones": [["B", [15, 3], None, 1]]}
    event = {"type": "illegal_change", "data": {"positions": [(15, 15, 1)], "missing": []}}
    assert is_stale_illegal_change(event, state)


def test_real_vision_mismatches_are_not_suppressed():
    state = {"board_size": [19, 19], "stones": [["B", [15, 3], None, 1]]}
    for event in (
        {"type": "illegal_change", "data": {"positions": [(15, 15, 2)], "missing": []}},
        {"type": "illegal_change", "data": {"positions": [(15, 14, 1)], "missing": []}},
        {"type": "illegal_change", "data": {"positions": [(15, 15, 1)], "missing": [(3, 3, 2)]}},
    ):
        assert not is_stale_illegal_change(event, state)


def test_late_first_stone_mismatch_reaches_neither_popup_nor_led():
    from katrain.web.server import _vision_event_pump

    event = {"type": "illegal_change", "data": {"positions": [(15, 15, 1)], "missing": []}}
    state = {"board_size": [19, 19], "stones": [["B", [15, 3], None, 1]]}
    client = asyncio.Queue()
    shown = []
    polled = asyncio.Event()

    class Vision:
        bound_session_id = "game-1"
        events = [event]

        def poll_events(self):
            events, self.events = self.events, []
            polled.set()
            return events

    app = SimpleNamespace(state=SimpleNamespace(
        vision=Vision(),
        session_manager=SimpleNamespace(get_session=lambda _id: SimpleNamespace(last_state=state)),
        vision_ws_clients={"client": client},
        vision_move_queue=asyncio.Queue(),
        physical_play=SimpleNamespace(show_attention=lambda *args, **kwargs: shown.append((args, kwargs))),
    ))

    async def run_once():
        task = asyncio.create_task(_vision_event_pump(app))
        await asyncio.wait_for(polled.wait(), timeout=1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(run_once())
    assert client.empty()
    assert shown == []
