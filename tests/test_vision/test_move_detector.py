import numpy as np
import pytest
from katrain.vision.move_detector import (
    AmbiguousPromoter,
    MoveDetector,
    PendingConfidencePeak,
    SUSPECT_CONFIDENCE_BONUS,
    SUSPICION_THRESHOLD,
)
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

    def test_an_unrelated_cell_no_longer_destroys_a_real_candidate(self):
        """Premise changed by L1. This test used to assert that a diff at ANOTHER cell
        restarts the real stone's count — that was the starvation bug: on RK3562
        2026-09-20 a real stone never entered its game at all because a phantom
        elsewhere kept resetting the shared counter. Each cell now counts for itself,
        and an absent frame is merely a miss (within miss_grace)."""
        detector = MoveDetector(consistency_frames=3, miss_grace=2)
        empty = np.zeros((19, 19), dtype=int)
        detector.detect_new_move(empty)

        with_stone = empty.copy()
        with_stone[3][3] = BLACK

        detector.detect_new_move(with_stone)  # (3,3) count=1
        detector.detect_new_move(with_stone)  # (3,3) count=2
        different = empty.copy()
        different[5][5] = WHITE
        detector.detect_new_move(different)  # (3,3) absent once — graced, not reset
        assert detector.detect_new_move(with_stone) == (3, 3, BLACK)  # count=3 -> confirms

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

    def test_clear_stone_can_use_shorter_required_frames(self):
        detector = MoveDetector(consistency_frames=5)
        empty = np.zeros((19, 19), dtype=int)
        detector.detect_new_move(empty)

        with_stone = empty.copy()
        with_stone[3][3] = BLACK
        assert detector.detect_new_move(with_stone, required_frames=3) is None
        assert detector.detect_new_move(with_stone, required_frames=3) is None
        assert detector.detect_new_move(with_stone, required_frames=3) == (3, 3, BLACK)

    def test_unknown_confidence_keeps_slow_confirmation_path(self):
        detector = MoveDetector(consistency_frames=5)
        empty = np.zeros((19, 19), dtype=int)
        detector.detect_new_move(empty)

        with_stone = empty.copy()
        with_stone[3][3] = BLACK
        for _ in range(4):
            assert detector.detect_new_move(with_stone, required_frames=None) is None
        assert detector.detect_new_move(with_stone, required_frames=None) == (3, 3, BLACK)

    def test_service_config_carries_move_confirm_frames(self):
        from katrain.vision.config_service import VisionServiceConfig

        cfg = VisionServiceConfig(move_confirm_frames=7)
        assert cfg.to_worker_config()["move_confirm_frames"] == 7
        assert VisionServiceConfig().to_worker_config()["move_confirm_frames"] == 5  # raised default
        assert VisionServiceConfig().to_worker_config()["move_confirm_fast_frames"] == 3
        assert VisionServiceConfig().to_worker_config()["move_confirm_fast_confidence"] == 0.70


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

    def test_two_cell_change_no_longer_hard_resets(self):
        """Premise changed by L1. Two diffs is the common phantom-beside-a-real-stone
        case, not scene disruption — the real stone must still be able to confirm."""
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty, with_stone = self._boards()
        two = with_stone.copy()
        two[5][5] = WHITE
        d.detect_new_move(empty)
        d.detect_new_move(with_stone)  # (3,3) count=1
        d.detect_new_move(with_stone)  # (3,3) count=2
        assert d.detect_new_move(two) == (3, 3, BLACK)  # count=3 -> confirms despite (5,5)

    def test_scene_disruption_still_hard_resets(self):
        """Four or more simultaneous diffs IS scene disruption (a hand sweeping across
        the board, the board being moved) — everything is abandoned, as before."""
        d = MoveDetector(consistency_frames=3, miss_grace=2, disruption_threshold=4)
        empty, with_stone = self._boards()
        many = with_stone.copy()
        many[5][5] = WHITE
        many[6][6] = BLACK
        many[7][7] = WHITE
        d.detect_new_move(empty)
        d.detect_new_move(with_stone)  # count=1
        d.detect_new_move(with_stone)  # count=2
        d.detect_new_move(many)  # 4 diffs -> hard reset
        assert d.detect_new_move(with_stone) is None  # count=1 again
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


class TestPerCellCandidates:
    """L1: the criterion for "does this move count" must be the candidate cell's own
    evidence, not the whole board's. Measured on RK3562 2026-09-20: a persistent
    phantom on one edge point kept every real move from ever accumulating enough
    consecutive whole-board-clean frames — one real stone never entered its game."""

    def _empty(self):
        return np.zeros((19, 19), dtype=int)

    def test_a_second_changed_cell_no_longer_blocks_a_real_stone(self):
        """THE regression. Under the old `len(diff_positions) > 1` rule, frames 2 and 3
        below each hard-reset everything, so the real stone could never reach 3."""
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty = self._empty()
        d.force_sync(empty)

        real = empty.copy()
        real[2][10] = WHITE  # the user's stone
        both = real.copy()
        both[18][13] = WHITE  # a phantom lights up on the far edge mid-window

        d.detect_new_move(real)  # real=1
        d.detect_new_move(both)  # real=2, phantom=1
        assert d.detect_new_move(both) == (2, 10, WHITE)  # real=3 confirms; phantom only at 2

    def test_flickering_phantom_loses_its_streak_while_a_real_stone_keeps_its_own(self):
        d = MoveDetector(consistency_frames=3, miss_grace=0)
        empty = self._empty()
        d.force_sync(empty)

        real = empty.copy()
        real[2][10] = WHITE
        both = real.copy()
        both[18][13] = WHITE

        d.detect_new_move(both)  # real=1, phantom=1
        d.detect_new_move(real)  # real=2, phantom absent past grace 0 -> dropped
        assert d.detect_new_move(both) == (2, 10, WHITE)  # real=3 confirms; phantom back at 1

    def test_exact_tie_confirms_nothing(self):
        """Two stones appearing on the SAME frame and advancing in lockstep is genuine
        ambiguity, not a phantom beside a real stone — emit nothing (unchanged)."""
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty = self._empty()
        d.detect_new_move(empty)
        two = empty.copy()
        two[3][3] = BLACK
        two[4][4] = WHITE
        for _ in range(5):
            assert d.detect_new_move(two) is None

    def test_the_older_candidate_wins_a_streak_tie(self):
        """Equal streaks, different first-seen frames -> the one that has been waiting
        longer goes first (FIFO), so a real stone placed before a phantom appeared is
        never queued behind it. The real stone blinks once (graced), which is what lets
        the two streaks draw level in the first place."""
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty = self._empty()
        d.force_sync(empty)

        real_only = empty.copy()
        real_only[2][10] = WHITE  # seen first
        phantom_only = empty.copy()
        phantom_only[18][13] = WHITE  # seen one frame later
        both = real_only.copy()
        both[18][13] = WHITE

        d.detect_new_move(real_only)  # real=1 first_seen=1
        d.detect_new_move(phantom_only)  # real absent (miss 1, graced); phantom=1 first_seen=2
        d.detect_new_move(both)  # real=2, phantom=2
        # real=3, phantom=3 -> counts tie, first_seen breaks it in the real stone's favour
        assert d.detect_new_move(both) == (2, 10, WHITE)

    def test_fast_path_not_lent_to_a_miss_graced_leaders_neighbor(self):
        """D8: `required_frames` is evidence about ONE stone — the workers measure
        `peak_for(pending_move)` on whichever cell is leading, then pass it in as
        `required_frames`. `ready` is built only from `current` (this frame's diffs),
        but `fast_cell` is taken from ALL candidates, including ones absent this frame
        but still inside miss_grace. So a leader that is absent on this exact frame is
        not in `ready` at all — leaving a second candidate alone in it, eligible for a
        fast-path allowance that was measured on a *different* stone. Confirming N here
        is not a delayed move, it is the WRONG STONE committed — irreversible on a
        cross-platform game.

        Four calls, consistency_frames=5, miss_grace=2, fast required_frames=3:
            f1 {L}      -> L=1
            f2 {L, N}   -> L=2, N=1
            f3 {L, N}   -> L=3, N=2
            f4 {N} only -> L absent (miss 1, still graced) so fast_cell=L; current={N}
                           -> N=3

        With D8, N is not `fast_cell`, so it needs consistency_frames=5, not 3 -> frame
        4 returns None (this test's assertion). Without D8 (delete the
        `needed = fast_needed if key == fast_cell else self.consistency_frames`
        restriction and always use `fast_needed`), N's count of 3 clears 3 and N wrongly
        confirms on frame 4 — proven in a disposable worktree per the task brief."""
        d = MoveDetector(consistency_frames=5, miss_grace=2)
        empty = self._empty()
        d.force_sync(empty)

        L = (2, 10, WHITE)  # the measured cell (leader)
        N = (18, 13, WHITE)  # asymmetric neighbor — never the measured cell

        only_l = empty.copy()
        only_l[L[0]][L[1]] = L[2]
        both = only_l.copy()
        both[N[0]][N[1]] = N[2]
        only_n = empty.copy()
        only_n[N[0]][N[1]] = N[2]

        d.detect_new_move(only_l)  # f1: L=1
        d.detect_new_move(both)  # f2: L=2, N=1
        d.detect_new_move(both)  # f3: L=3, N=2
        # f4: L absent (graced), fast_cell captured as L before N's count is bumped
        assert d.detect_new_move(only_n, required_frames=3) is None  # N=3, not the fast_cell

    def test_pending_move_and_count_report_the_leading_candidate(self):
        """The workers read these two properties every frame (confidence-peak tracking
        and the 'confirming' chip). They must keep working."""
        d = MoveDetector(consistency_frames=5, miss_grace=2)
        empty = self._empty()
        d.force_sync(empty)
        assert d.pending_move is None
        assert d.count == 0

        board = empty.copy()
        board[2][10] = WHITE
        d.detect_new_move(board)
        d.detect_new_move(board)
        assert d.pending_move == (2, 10, WHITE)
        assert d.count == 2

        d.force_sync(board)
        assert d.pending_move is None
        assert d.count == 0

    def test_ignore_cells_still_excluded_from_candidates(self):
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty = self._empty()
        d.force_sync(empty)
        leftover = empty.copy()
        leftover[3][3] = BLACK
        for _ in range(8):
            assert d.detect_new_move(leftover, ignore_cells={(3, 3)}) is None


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


class TestIgnoreCells:
    """A removal-lit / cleanup cell (the system is asking the user to REMOVE a stone, not
    place one) must never become a 'new move' — even after the streaming SET_EXPECTED_BOARD
    force-syncs the baseline back to the bare digital board (leftover cell EMPTY).

    Regression for the resync leftover re-injection (workflow wzceinjdc, lens C/A): FIX C's
    RESET_SYNC union baseline was transient — it lived only in ``prev_board`` and the next
    ~0.25s analysis-stream push clobbered it, so the un-lifted physical stone re-confirmed
    as a phantom move onto the just-captured point. ``ignore_cells`` (fed the frame's
    removal-lit ∩ expected-empty mask) closes that window durably: it is re-derived every
    frame, so no baseline overwrite can defeat it."""

    def _empty(self):
        return np.zeros((19, 19), dtype=int)

    def test_ignored_cell_never_confirms_even_with_empty_baseline(self):
        d = MoveDetector(consistency_frames=3)
        empty = self._empty()
        d.force_sync(empty)  # baseline empty at (3,3) — the post-clobber state
        leftover = empty.copy()
        leftover[3][3] = BLACK  # physical stone still on the captured / removal-lit point
        for _ in range(8):
            assert d.detect_new_move(leftover, ignore_cells={(3, 3)}) is None

    def test_control_without_ignore_reinjects(self):
        # Proves the defect is real: the SAME clobbered baseline WITHOUT the mask re-fires.
        d = MoveDetector(consistency_frames=3)
        empty = self._empty()
        d.force_sync(empty)
        leftover = empty.copy()
        leftover[3][3] = BLACK
        d.detect_new_move(leftover)
        d.detect_new_move(leftover)
        assert d.detect_new_move(leftover) == (3, 3, BLACK)  # re-injection

    def test_ignore_does_not_suppress_a_real_move_elsewhere(self):
        # A genuine new move at an UNlit cell still confirms while a leftover cell is ignored.
        # (Skipping the leftover also rescues the real move from the multi-stone hard-reset.)
        d = MoveDetector(consistency_frames=3)
        empty = self._empty()
        d.force_sync(empty)
        b = empty.copy()
        b[3][3] = BLACK  # ignored leftover
        b[9][9] = WHITE  # real new move
        assert d.detect_new_move(b, ignore_cells={(3, 3)}) is None  # count 1 (only 9,9 diffs)
        assert d.detect_new_move(b, ignore_cells={(3, 3)}) is None  # count 2
        assert d.detect_new_move(b, ignore_cells={(3, 3)}) == (9, 9, WHITE)

    def test_none_ignore_is_backward_compatible(self):
        d = MoveDetector(consistency_frames=2)
        empty = self._empty()
        d.detect_new_move(empty)
        s = empty.copy()
        s[3][3] = BLACK
        d.detect_new_move(s)
        assert d.detect_new_move(s) == (3, 3, BLACK)  # ignore_cells default (None) unchanged


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

    def test_peak_for_only_returns_the_matching_pending_cell(self):
        p = self._peak()
        pending = (15, 3, BLACK)
        p.observe(pending, {(15, 3): 0.47})
        assert p.peak_for(pending) == pytest.approx(0.47)
        assert p.peak_for((4, 4, WHITE)) is None
        assert p.peak_for(None) is None

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


class TestCellReputation:
    """L2: a cell that repeatedly produces candidates which never become real moves
    must clear a higher bar. Measured on RK3562 2026-09-20: vision (18,13) flashed 69
    times across 3 processes (405s lit) and was auto-confirmed twice at 0.50-0.57,
    while the global add gate was 0.40. Raising the global gate would also have blocked
    the weak real stones it exists for — so the penalty is per-cell."""

    def _boards(self):
        empty = np.zeros((19, 19), dtype=int)
        flashed = empty.copy()
        flashed[18][13] = WHITE
        return empty, flashed

    def _flash_once(self, d, empty, flashed, miss_grace):
        """One appear-then-vanish cycle: seen once, then absent past the grace."""
        d.detect_new_move(flashed)
        for _ in range(miss_grace + 1):
            d.detect_new_move(empty)

    def test_abandoned_candidate_accrues_suspicion(self):
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty, flashed = self._boards()
        d.detect_new_move(empty)
        assert d.suspicion_of(18, 13) == 0

        self._flash_once(d, empty, flashed, miss_grace=2)
        assert d.suspicion_of(18, 13) == 1

    def test_repeated_flashing_makes_the_cell_suspect(self):
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty, flashed = self._boards()
        d.detect_new_move(empty)
        for _ in range(SUSPICION_THRESHOLD):
            self._flash_once(d, empty, flashed, miss_grace=2)
        assert d.is_suspect(18, 13)

    def test_suspect_cell_still_confirms_at_the_normal_frame_count(self):
        """Fix round 1: a suspect cell's extra bar is the workers' ambiguous routing
        gate ONLY, never the confirmation frame count. An earlier version doubled
        required_frames here; that gated detect_new_move's return value, which sits
        upstream of BOTH auto-play and the ambiguous confirmation card (the stuck-stone
        promoter only runs when no candidate is pending at all). A suspect cell that
        could never assemble the doubled count therefore confirmed nowhere, ever —
        silent, permanent loss, which is F2 (a real stone that never entered its game),
        manufactured by the very fix meant to stop F1. Being suspect must never take the
        card itself off the table — it only changes what happens after this returns."""
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty, flashed = self._boards()
        d.detect_new_move(empty)
        for _ in range(SUSPICION_THRESHOLD):
            self._flash_once(d, empty, flashed, miss_grace=2)
        assert d.is_suspect(18, 13)

        # Same consistency_frames as an honest cell (see test_an_honest_cell_is_never_penalised).
        assert d.detect_new_move(flashed) is None
        assert d.detect_new_move(flashed) is None
        assert d.detect_new_move(flashed) == (18, 13, WHITE)

    def test_suspect_confidence_bonus_covers_the_measured_phantom(self):
        """L2's sole F1 mechanism, post fix-round-1, is this routing gate — the frame
        count no longer discriminates suspect cells at all. Device flags measured on
        RK3562 2026-09-20: --vision-ambiguous-confidence 0.42. Vision (18,13) auto-
        confirmed at 0.50 (10:43:19) and 0.57 (peak, the O1 event) — both below the
        raised gate, so once suspect it can only reach the user via the confirmation
        card, never auto-play. Real confirmed moves on this box peak at p25=0.72
        (config_service.py move_confirm_fast_confidence comment), comfortably above the
        raised gate, so the large majority of real moves are unaffected even if flagged
        suspect."""
        raised_gate = min(0.95, 0.42 + SUSPECT_CONFIDENCE_BONUS)
        assert raised_gate == pytest.approx(0.67)
        assert raised_gate > 0.57  # the O1 auto-confirm peak
        assert raised_gate > 0.50  # the 10:43:19 auto-confirm
        assert raised_gate < 0.72  # real-move peak p25 — suspicion must not cost real play

    def test_an_honest_cell_is_never_penalised(self):
        """A real stone appears and confirms — it never appears-then-vanishes."""
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty = np.zeros((19, 19), dtype=int)
        stone = empty.copy()
        stone[3][3] = BLACK
        d.detect_new_move(empty)
        d.detect_new_move(stone)
        d.detect_new_move(stone)
        assert d.detect_new_move(stone) == (3, 3, BLACK)
        assert d.suspicion_of(3, 3) == 0
        assert not d.is_suspect(3, 3)

    def test_an_unactioned_confirmation_is_never_penalised_for_re_firing(self):
        """The caller-owned-baseline contract makes an unactioned confirmation re-fire on
        purpose (a weak real stone waiting on the user's confirmation card). Charging
        those repeats would run the score away and block the stone permanently."""
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty, flashed = self._boards()
        d.detect_new_move(empty)
        for _ in range(6):  # two full confirmation windows, nothing actioned in between
            d.detect_new_move(flashed)
        assert d.suspicion_of(18, 13) == 0
        assert not d.is_suspect(18, 13)

    def test_reset_suspicion_clears_everything(self):
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty, flashed = self._boards()
        d.detect_new_move(empty)
        for _ in range(SUSPICION_THRESHOLD):
            self._flash_once(d, empty, flashed, miss_grace=2)
        assert d.is_suspect(18, 13)

        d.reset_suspicion()
        assert d.suspicion_of(18, 13) == 0

    def test_force_sync_does_not_clear_suspicion(self):
        """force_sync runs on every expected-board push (several times a second).
        Clearing there would mean the counter never accumulates."""
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty, flashed = self._boards()
        d.detect_new_move(empty)
        for _ in range(SUSPICION_THRESHOLD):
            self._flash_once(d, empty, flashed, miss_grace=2)
        d.force_sync(empty)
        assert d.is_suspect(18, 13)
