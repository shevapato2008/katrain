import numpy as np
import pytest
from katrain.vision.move_detector import MoveDetector
from katrain.vision.board_state import BLACK, WHITE, EMPTY


@pytest.fixture
def detector():
    return MoveDetector(consistency_frames=3)


class TestMoveDetector:
    def test_no_change_returns_none(self, detector):
        board = np.zeros((19, 19), dtype=int)
        for _ in range(5):
            assert detector.detect_new_move(board) is None

    def test_detects_new_black_stone_after_consistency(self, detector):
        empty = np.zeros((19, 19), dtype=int)
        detector.detect_new_move(empty)

        with_stone = empty.copy()
        with_stone[3][3] = BLACK

        assert detector.detect_new_move(with_stone) is None  # count=1
        assert detector.detect_new_move(with_stone) is None  # count=2
        result = detector.detect_new_move(with_stone)  # count=3
        assert result == (3, 3, BLACK)

    def test_resets_count_on_change(self, detector):
        empty = np.zeros((19, 19), dtype=int)
        detector.detect_new_move(empty)

        with_stone = empty.copy()
        with_stone[3][3] = BLACK

        detector.detect_new_move(with_stone)  # count=1
        detector.detect_new_move(with_stone)  # count=2
        different = empty.copy()
        different[5][5] = WHITE
        detector.detect_new_move(different)  # count reset
        assert detector.detect_new_move(with_stone) is None  # count=1 again

    def test_ignores_multiple_simultaneous_new_stones(self, detector):
        empty = np.zeros((19, 19), dtype=int)
        detector.detect_new_move(empty)

        two_stones = empty.copy()
        two_stones[3][3] = BLACK
        two_stones[4][4] = WHITE

        for _ in range(5):
            assert detector.detect_new_move(two_stones) is None

    def test_handles_captures(self, detector):
        """Placing a stone that removes opponent stones: only the new stone is detected."""
        board1 = np.zeros((19, 19), dtype=int)
        board1[3][3] = WHITE  # opponent stone
        detector.detect_new_move(board1)

        board2 = board1.copy()
        board2[3][3] = EMPTY  # captured
        board2[3][4] = BLACK  # new move

        assert detector.detect_new_move(board2) is None  # count=1
        assert detector.detect_new_move(board2) is None  # count=2
        result = detector.detect_new_move(board2)  # count=3
        assert result == (3, 4, BLACK)

    def test_force_sync(self, detector):
        board1 = np.zeros((19, 19), dtype=int)
        board1[3][3] = BLACK
        detector.detect_new_move(board1)

        board2 = np.zeros((19, 19), dtype=int)  # stone removed (undo)
        detector.force_sync(board2)
        assert np.array_equal(detector.prev_board, board2)


class TestConfigurableConsistencyFrames:
    def test_five_frame_confirmation(self):
        detector = MoveDetector(consistency_frames=5)
        empty = np.zeros((19, 19), dtype=int)
        detector.detect_new_move(empty)

        with_stone = empty.copy()
        with_stone[3][3] = BLACK
        for _ in range(4):
            assert detector.detect_new_move(with_stone) is None
        assert detector.detect_new_move(with_stone) == (3, 3, BLACK)

    def test_service_config_carries_move_confirm_frames(self):
        from katrain.vision.config_service import VisionServiceConfig

        cfg = VisionServiceConfig(move_confirm_frames=7)
        assert cfg.to_worker_config()["move_confirm_frames"] == 7
        assert VisionServiceConfig().to_worker_config()["move_confirm_frames"] == 5  # raised default


class TestAmbiguousPromoter:
    """Sub-add promotion: a persistent below-add-threshold stone becomes a user prompt."""

    def _promoter(self, frames=3, cooldown=10):
        from katrain.vision.move_detector import AmbiguousPromoter

        return AmbiguousPromoter(promote_frames=frames, cooldown_frames=cooldown)

    def test_fires_after_consecutive_frames(self):
        p = self._promoter(frames=3)
        cand = {(2, 3): (0.42, 0)}
        assert p.step(cand) is None
        assert p.step(cand) is None
        assert p.step(cand) == (2, 3, 0, 0.42)

    def test_brief_absence_keeps_streak(self):
        # miss grace: a marginal stone blinking out for 1-2 frames must not restart
        # the streak — the frozen count resumes when the detection reappears.
        p = self._promoter(frames=3)
        cand = {(2, 3): (0.42, 0)}
        p.step(cand)  # streak 1
        p.step(cand)  # streak 2
        assert p.step({}) is None  # blink (miss 1) — streak frozen, nothing fires
        assert p.step(cand) == (2, 3, 0, 0.42)  # streak 3 on reappearance

    def test_absent_cell_never_fires_while_graced(self):
        p = self._promoter(frames=2)
        cand = {(2, 3): (0.42, 0)}
        p.step(cand)
        p.step(cand)  # fires? streak 2 >= 2 -> yes, consume it
        p.reset()
        p.step(cand)
        p.step(cand)  # streak 2 -> fires
        # rebuild to streak just below, then go absent: absent frames must not fire
        p.reset()
        p.step(cand)
        assert p.step({}) is None  # graced absence, streak frozen at 1

    def test_sustained_absence_resets_streak(self):
        p = self._promoter(frames=3)
        cand = {(2, 3): (0.42, 0)}
        p.step(cand)
        p.step(cand)
        p.step({})  # miss 1 (frozen)
        p.step({})  # miss 2 (frozen)
        p.step({})  # miss 3 > grace 2 — streak dropped
        assert p.step(cand) is None  # restart: streak 1
        assert p.step(cand) is None
        assert p.step(cand) is not None

    def test_cooldown_blocks_refire(self):
        p = self._promoter(frames=2, cooldown=5)
        cand = {(2, 3): (0.42, 0)}
        p.step(cand)
        assert p.step(cand) is not None  # fired, cooldown starts
        for _ in range(4):
            assert p.step(cand) is None  # streak rebuilds but cooldown holds
        # cooldown expired after 5 steps; streak is already >= promote_frames
        assert p.step(cand) is not None

    def test_one_prompt_at_a_time_longest_streak_wins(self):
        p = self._promoter(frames=2)
        p.step({(2, 3): (0.42, 0)})
        hit = p.step({(2, 3): (0.42, 0), (5, 5): (0.44, 1)})
        assert hit == (2, 3, 0, 0.42)  # (5,5) only has streak 1

    def test_reset_clears_everything(self):
        p = self._promoter(frames=2, cooldown=100)
        cand = {(2, 3): (0.42, 0)}
        p.step(cand)
        assert p.step(cand) is not None
        p.reset()  # e.g. user tapped Ignore -> RESET_SYNC
        p.step(cand)
        assert p.step(cand) is not None  # cooldown gone too — fresh session semantics


class TestMoveDetectorMissGrace:
    """A pending move survives brief detection dropouts (marginal-confidence flicker)."""

    def _boards(self):
        empty = np.zeros((19, 19), dtype=int)
        with_stone = empty.copy()
        with_stone[3][3] = BLACK
        return empty, with_stone

    def test_blink_freezes_count_then_confirms(self):
        d = MoveDetector(consistency_frames=5, miss_grace=2)
        empty, with_stone = self._boards()
        d.detect_new_move(empty)
        for _ in range(3):
            assert d.detect_new_move(with_stone) is None  # count 1..3
        assert d.detect_new_move(empty) is None  # blink (miss 1) — count frozen
        assert d.detect_new_move(empty) is None  # blink (miss 2) — still within grace
        assert d.detect_new_move(with_stone) is None  # count 4
        assert d.detect_new_move(with_stone) == (3, 3, BLACK)  # count 5 -> confirmed

    def test_sustained_absence_abandons_pending(self):
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty, with_stone = self._boards()
        d.detect_new_move(empty)
        d.detect_new_move(with_stone)
        d.detect_new_move(with_stone)  # count 2
        for _ in range(3):  # 3 consecutive misses > grace 2 -> abandoned
            d.detect_new_move(empty)
        assert d.detect_new_move(with_stone) is None  # restarts at count 1
        assert d.detect_new_move(with_stone) is None
        assert d.detect_new_move(with_stone) == (3, 3, BLACK)

    def test_multi_stone_change_still_hard_resets(self):
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty, with_stone = self._boards()
        two = with_stone.copy()
        two[5][5] = WHITE
        d.detect_new_move(empty)
        d.detect_new_move(with_stone)
        d.detect_new_move(with_stone)  # count 2
        d.detect_new_move(two)  # scene disruption -> hard reset (no grace)
        assert d.detect_new_move(with_stone) is None  # count 1 again
        assert d.detect_new_move(with_stone) is None
        assert d.detect_new_move(with_stone) == (3, 3, BLACK)

    def test_zero_grace_matches_legacy_behavior(self):
        d = MoveDetector(consistency_frames=3, miss_grace=0)
        empty, with_stone = self._boards()
        d.detect_new_move(empty)
        d.detect_new_move(with_stone)
        d.detect_new_move(with_stone)
        d.detect_new_move(empty)  # single miss > grace 0 -> abandoned
        assert d.detect_new_move(with_stone) is None
        assert d.detect_new_move(with_stone) is None
        assert d.detect_new_move(with_stone) == (3, 3, BLACK)


class TestCallerOwnedBaseline:
    """回归（一次性沉默）：确认时不再推进基线——被下游丢弃的确认会重试，
    只有调用方 force_sync（真正被接受 / 采纳物理盘）才停。"""

    def _boards(self):
        empty = np.zeros((19, 19), dtype=int)
        with_stone = empty.copy()
        with_stone[3][3] = BLACK
        return empty, with_stone

    def test_unactioned_confirm_refires(self):
        d = MoveDetector(consistency_frames=3)
        empty, with_stone = self._boards()
        d.detect_new_move(empty)
        d.detect_new_move(with_stone)
        d.detect_new_move(with_stone)
        assert d.detect_new_move(with_stone) == (3, 3, BLACK)  # confirmed, NOT actioned
        # baseline untouched -> the same move confirms again after another window
        d.detect_new_move(with_stone)
        d.detect_new_move(with_stone)
        assert d.detect_new_move(with_stone) == (3, 3, BLACK)

    def test_force_sync_after_acceptance_stops_refire(self):
        d = MoveDetector(consistency_frames=3)
        empty, with_stone = self._boards()
        d.detect_new_move(empty)
        d.detect_new_move(with_stone)
        d.detect_new_move(with_stone)
        assert d.detect_new_move(with_stone) == (3, 3, BLACK)
        d.force_sync(with_stone)  # caller accepted the move
        for _ in range(6):
            assert d.detect_new_move(with_stone) is None


def test_worker_config_carries_ambiguous_confidence():
    from katrain.vision.config_service import VisionServiceConfig

    assert VisionServiceConfig().to_worker_config()["ambiguous_confidence"] == 0.55
    assert VisionServiceConfig(ambiguous_confidence=0.42).to_worker_config()["ambiguous_confidence"] == 0.42


class TestPendingConfidencePeak:
    """Ambiguous gate uses the confirmation-window PEAK confidence, not one frame.

    Far-side stones oscillate 0.32-0.53 instantaneous around the gate; the
    confirm-frame value alone made card-vs-autoplay a coin flip.
    """

    def _peak(self):
        from katrain.vision.move_detector import PendingConfidencePeak

        return PendingConfidencePeak()

    def test_peak_accumulates_over_window(self):
        p = self._peak()
        pending = (15, 3, BLACK)
        for conf in (0.38, 0.47, 0.36):  # oscillating around a 0.42 gate
            p.observe(pending, {(15, 3): conf})
        # Confirm-frame instant conf is 0.36 but the window peaked at 0.47.
        assert p.gate_confidence(15, 3, 0.36) == pytest.approx(0.47)

    def test_other_cell_gets_instant_conf_only(self):
        p = self._peak()
        p.observe((15, 3, BLACK), {(15, 3): 0.50})
        assert p.gate_confidence(2, 2, 0.30) == pytest.approx(0.30)

    def test_pending_change_resets_peak(self):
        p = self._peak()
        p.observe((15, 3, BLACK), {(15, 3): 0.50})
        p.observe((4, 4, WHITE), {(4, 4): 0.33})  # different cell goes pending
        assert p.gate_confidence(15, 3, 0.30) == pytest.approx(0.30)
        assert p.gate_confidence(4, 4, 0.30) == pytest.approx(0.33)

    def test_pending_cleared_resets_peak(self):
        p = self._peak()
        p.observe((15, 3, BLACK), {(15, 3): 0.50})
        p.observe(None, {})  # confirm/force_sync cleared pending — window over
        assert p.gate_confidence(15, 3, 0.30) == pytest.approx(0.30)

    def test_miss_grace_frame_preserves_peak(self):
        p = self._peak()
        pending = (15, 3, BLACK)
        p.observe(pending, {(15, 3): 0.47})
        p.observe(pending, {})  # detection blinked out; pending survives via miss_grace
        assert p.gate_confidence(15, 3, 0.30) == pytest.approx(0.47)

    def test_unbacked_cell_stays_zero(self):
        p = self._peak()
        pending = (15, 3, BLACK)
        for _ in range(5):
            p.observe(pending, {(9, 9): 0.9})  # conf_map never backs the pending cell
        assert p.gate_confidence(15, 3, 0.0) == pytest.approx(0.0)

    def test_instant_above_peak_wins(self):
        p = self._peak()
        pending = (15, 3, BLACK)
        p.observe(pending, {(15, 3): 0.40})
        assert p.gate_confidence(15, 3, 0.52) == pytest.approx(0.52)
