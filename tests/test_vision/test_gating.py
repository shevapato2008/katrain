from katrain.vision.gating import move_event, should_detect_moves, should_feed_sync
from katrain.vision.ipc import ConfirmedMove


class TestShouldFeedSync:
    def test_bound_feeds(self):
        assert should_feed_sync(bound=True, monitor=False, paused=False)

    def test_monitor_feeds_without_bind(self):
        assert should_feed_sync(bound=False, monitor=True, paused=False)

    def test_paused_blocks_everything(self):
        assert not should_feed_sync(bound=True, monitor=True, paused=True)

    def test_neither_no_feed(self):
        assert not should_feed_sync(bound=False, monitor=False, paused=False)


class TestShouldDetectMoves:
    def test_bound_detects_regardless_of_state(self):
        # 保持既有对弈行为：bound 时不看 sync_state 也不看 move_armed
        assert should_detect_moves(True, False, False, False, "capture_pending")

    def test_monitor_requires_armed_and_synced(self):
        assert should_detect_moves(False, True, False, True, "synced")
        assert not should_detect_moves(False, True, False, False, "synced")  # 未 arm
        assert not should_detect_moves(False, True, False, True, "setup_in_progress")  # 摆放中

    def test_paused_blocks(self):
        assert not should_detect_moves(True, True, True, True, "synced")


class TestMoveEvent:
    def test_bound_yields_dataclass_for_game_poller(self):
        evt = move_event(bound=True, row=3, col=4, color=1)
        assert isinstance(evt, ConfirmedMove) and (evt.row, evt.col, evt.color) == (3, 4, 1)

    def test_monitor_yields_dict_for_ws(self):
        evt = move_event(bound=False, row=3, col=4, color=2)
        assert evt == {"type": "move_confirmed", "data": {"row": 3, "col": 4, "color": 2}}
