import pytest

from katrain.vision.gating import (
    mean_detection_confidence,
    move_event,
    should_detect_moves,
    should_feed_sync,
)
from katrain.vision.ipc import ConfirmedMove


class _Det:
    """Minimal stub: mean_detection_confidence only reads .confidence."""

    def __init__(self, confidence: float):
        self.confidence = confidence


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

    def test_monitor_detects_freshly_placed_move_during_mismatch(self):
        # 答题时落子会让 SyncStateMachine 立刻从 synced 变 mismatch_warning。走子检测必须
        # 继续（armed = 轮到用户），否则 MoveDetector 在攒够确认帧前就被门控饿死，那颗子被
        # 误判成 illegal_change 而非 move_confirmed（物理死活答题不同步的根因）。
        assert should_detect_moves(False, True, False, True, "mismatch_warning")
        # 噪声读数会把 sync 打到 capture_pending(真实子闪断成"缺失"),此时也要继续检测
        assert should_detect_moves(False, True, False, True, "capture_pending")
        # 板面读数不可用时仍然拦截
        assert not should_detect_moves(False, True, False, True, "board_lost")
        assert not should_detect_moves(False, True, False, True, "degraded")

    def test_paused_blocks(self):
        assert not should_detect_moves(True, True, True, True, "synced")


class TestMoveEvent:
    def test_bound_yields_dataclass_for_game_poller(self):
        evt = move_event(bound=True, row=3, col=4, color=1)
        assert isinstance(evt, ConfirmedMove) and (evt.row, evt.col, evt.color) == (3, 4, 1)

    def test_monitor_yields_dict_for_ws(self):
        evt = move_event(bound=False, row=3, col=4, color=2)
        assert evt == {"type": "move_confirmed", "data": {"row": 3, "col": 4, "color": 2}}


class TestMeanDetectionConfidence:
    """空盘(0 检测)是*干净空盘*=高置信读数(1.0)，不是低置信(0.0)。

    否则死活「清盘」步骤 mean_conf 恒为 0.0 -> SyncStateMachine 10s 后滑入 DEGRADED
    -> 跳过 _check_setup -> setup_complete 永不触发 -> 清盘永远卡住。
    """

    def test_empty_board_is_confident(self):
        assert mean_detection_confidence([]) == 1.0

    def test_nonempty_returns_average(self):
        assert mean_detection_confidence([_Det(0.8), _Det(0.6)]) == pytest.approx(0.7)

    def test_single_detection(self):
        assert mean_detection_confidence([_Det(0.42)]) == pytest.approx(0.42)
