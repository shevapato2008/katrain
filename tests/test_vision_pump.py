import asyncio
import pytest
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

    app = SimpleNamespace(
        state=SimpleNamespace(
            vision=Vision(),
            session_manager=SimpleNamespace(get_session=lambda _id: SimpleNamespace(last_state=state)),
            vision_ws_clients={"client": client},
            vision_move_queue=asyncio.Queue(),
            physical_play=SimpleNamespace(show_attention=lambda *args, **kwargs: shown.append((args, kwargs))),
        )
    )

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


@pytest.mark.parametrize("rejected", [False, True])
def test_slow_confirmation_pump_before_poller_and_authority_flush_before_release(rejected):
    import logging
    from unittest.mock import AsyncMock
    from tests.platforms.test_gateway import bound_vision_gateway
    from tests.test_vision.test_worker_commands import _run_real_detector_confirmation
    from katrain.vision.ipc import CommandType
    from katrain.web.server import _handle_confirmed_move, _vision_event_pump

    async def run():
        app, session, vision, orch, pm, adapter, ctx = bound_vision_gateway()
        worker = _run_real_detector_confirmation(
            "inprocess",
            0.68,
            5,
            binding_epoch=vision.binding_epoch,
            expected_revision=vision.expected_revision,
        )
        # A corner occlusion does not convert the owned point into a mismatch on reacquire.
        lost = worker._sync.update(None, board_detected=False)
        recovered = worker._sync.update(worker._last_stable_board)
        assert [event.type.value for event in lost + recovered] == ["board_lost", "board_reacquired"]
        for event in lost + recovered:
            worker._event_queue.put({"type": event.type.value, "data": event.data})
        vision._worker = worker
        if rejected:
            adapter.submit_move = AsyncMock(return_value=False)
        client = asyncio.Queue()
        shown = []
        orch.show_attention = lambda *args, **kwargs: shown.append((args, kwargs))
        app.state.vision = vision
        app.state.vision_ws_clients = {"client": client}
        app.state.vision_move_queue = asyncio.Queue()
        polled = asyncio.Event()
        poll = vision.poll_events

        def poll_and_signal():
            events = poll()
            polled.set()
            return events

        vision.poll_events = poll_and_signal
        pump = asyncio.create_task(_vision_event_pump(app))
        await polled.wait()  # force the independently scheduled pump to consume dicts first
        pump.cancel()
        try:
            await pump
        except asyncio.CancelledError:
            pass
        assert not [event for event in list(client._queue) if event["type"] == "illegal_change"]
        assert shown == []
        move = vision.get_confirmed_move()
        assert move is not None
        await _handle_confirmed_move(app, vision, "s", move, logging.getLogger(__name__))
        commands = list(worker._cmd_queue.queue)
        assert [cmd.action for cmd in commands][-2:] == [
            CommandType.SET_EXPECTED_BOARD,
            CommandType.RELEASE_CONFIRMED_MOVE,
        ]
        worker._drain_commands()
        assert not worker._sync.has_confirmed_move
        matched = worker._last_stable_board
        events = worker._sync.update(matched)
        if rejected:
            assert len(events) == 1 and events[0].type.value == "illegal_change"
            assert events[0].data["actionable"] is True
            assert session.katrain.game.current_node.depth == 0
            worker._event_queue.put({"type": events[0].type.value, "data": events[0].data})
            polled.clear()
            pump = asyncio.create_task(_vision_event_pump(app))
            await polled.wait()
            pump.cancel()
            try:
                await pump
            except asyncio.CancelledError:
                pass
            mismatch = [event for event in list(client._queue) if event["type"] == "illegal_change"]
            assert len(mismatch) == 1
            assert mismatch[0]["data"]["positions"] == [(3, 3, 1)]
            assert shown == [(([(3, 3)],), {"source": "vision"})]
        else:
            assert any(event.type.value == "synced" for event in events)
            assert not any(event.type.value == "illegal_change" for event in events)
            assert session.katrain.game.current_node.depth == 1
        await orch.shutdown()

    asyncio.run(run())
