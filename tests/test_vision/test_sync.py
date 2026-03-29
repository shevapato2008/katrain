import numpy as np
import pytest

from katrain.vision.board_state import BLACK, EMPTY, WHITE
from katrain.vision.sync import (
    SyncEvent,
    SyncEventType,
    SyncState,
    SyncStateMachine,
    game_state_stones_to_board,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def empty_board(size: int = 19) -> np.ndarray:
    return np.zeros((size, size), dtype=int)


def board_with(stones: dict[tuple[int, int], int], size: int = 19) -> np.ndarray:
    """Build a board with specific stones.  stones = {(row, col): color}."""
    board = empty_board(size)
    for (r, c), color in stones.items():
        board[r, c] = color
    return board


# ---------------------------------------------------------------------------
# Tests: game_state_stones_to_board
# ---------------------------------------------------------------------------


class TestGameStateStonesToBoard:
    def test_empty_stones_list(self):
        board = game_state_stones_to_board([], board_size=19)
        assert board.shape == (19, 19)
        assert np.all(board == EMPTY)

    def test_single_black_stone(self):
        # col=3, gtp_row=15 => vision_row = 19-1-15 = 3
        stones = [["B", [3, 15], 0.0, 1]]
        board = game_state_stones_to_board(stones, board_size=19)
        assert board[3, 3] == BLACK

    def test_pass_moves_are_skipped(self):
        stones = [
            ["B", [3, 15], 0.0, 1],
            ["W", None, 0.0, 2],  # pass
            ["B", [4, 14], 0.0, 3],
        ]
        board = game_state_stones_to_board(stones, board_size=19)
        assert board[3, 3] == BLACK
        assert board[4, 4] == BLACK
        # No crash from None coords, and pass does not place a stone.
        non_empty = np.count_nonzero(board)
        assert non_empty == 2

    def test_mix_of_black_and_white_stones_with_y_flip(self):
        stones = [
            ["B", [0, 18], 0.0, 1],  # vision_row=0, col=0  (top-left)
            ["W", [18, 0], 0.0, 2],  # vision_row=18, col=18 (bottom-right)
        ]
        board = game_state_stones_to_board(stones, board_size=19)
        assert board[0, 0] == BLACK
        assert board[18, 18] == WHITE

    def test_9x9_board(self):
        # col=4, gtp_row=4 => vision_row = 9-1-4 = 4 (center of 9x9)
        stones = [["B", [4, 4], 0.0, 1]]
        board = game_state_stones_to_board(stones, board_size=9)
        assert board.shape == (9, 9)
        assert board[4, 4] == BLACK
        assert np.count_nonzero(board) == 1


# ---------------------------------------------------------------------------
# Tests: SyncStateMachine
# ---------------------------------------------------------------------------


class TestSyncStateMachineNormalPlayFlow:
    """Test 6: UNBOUND -> CALIBRATING -> SYNCED, then matching board stays SYNCED."""

    def test_normal_play_lifecycle(self):
        sm = SyncStateMachine(board_size=19)
        assert sm.state == SyncState.UNBOUND

        sm.bind()
        assert sm.state == SyncState.CALIBRATING

        sm.confirm_pose_lock()
        assert sm.state == SyncState.SYNCED

        expected = empty_board()
        sm.set_expected_board(expected)

        events = sm.update(expected.copy(), mean_confidence=0.9, timestamp=1000.0)
        assert sm.state == SyncState.SYNCED
        # No mismatch, so no events (or a SYNCED event if state changed, but it was already SYNCED).
        illegal_events = [e for e in events if e.type == SyncEventType.ILLEGAL_CHANGE]
        assert len(illegal_events) == 0


class TestSyncStateMachineCaptureFlow:
    """Test 7: Capture pending -> cleared -> SYNCED."""

    def test_capture_pending_and_cleared(self):
        sm = SyncStateMachine(board_size=19)
        sm.bind()
        sm.confirm_pose_lock()

        # Expected: stone at (5, 5)
        expected = board_with({(5, 5): BLACK})
        sm.set_expected_board(expected)

        # Observed: stone missing at (5, 5)
        observed_missing = empty_board()
        events = sm.update(observed_missing, mean_confidence=0.9, timestamp=1000.0)

        assert sm.state == SyncState.CAPTURE_PENDING
        capture_events = [e for e in events if e.type == SyncEventType.CAPTURE_PENDING]
        assert len(capture_events) == 1
        assert capture_events[0].data["positions"] == [(5, 5, BLACK)]

        # Now the stone is removed (observed is empty, which matches "captured" state).
        # The expected board still has the stone, but observed is empty => still pending
        # because the user hasn't physically removed it yet... Actually, the capture IS
        # that the stone is already gone. The pending captures check if observed[r,c] != EMPTY.
        # Since observed[5,5] == EMPTY, still_pending is empty => CAPTURES_CLEARED.
        events2 = sm.update(observed_missing, mean_confidence=0.9, timestamp=1001.0)
        cleared_events = [e for e in events2 if e.type == SyncEventType.CAPTURES_CLEARED]
        assert len(cleared_events) == 1
        assert sm.state == SyncState.SYNCED


class TestSyncStateMachineIllegalChange:
    """Test 8: Stable mismatch triggers ILLEGAL_CHANGE after N frames; single frame does not."""

    def test_illegal_change_after_n_frames(self):
        sm = SyncStateMachine(board_size=19, illegal_change_frames=5)
        sm.bind()
        sm.confirm_pose_lock()

        expected = empty_board()
        sm.set_expected_board(expected)

        observed_with_extra = board_with({(3, 3): BLACK})

        # Frames 1..4: no ILLEGAL_CHANGE yet
        for i in range(4):
            events = sm.update(observed_with_extra, mean_confidence=0.9, timestamp=1000.0 + i)
            illegal = [e for e in events if e.type == SyncEventType.ILLEGAL_CHANGE]
            assert len(illegal) == 0, f"Should not fire on frame {i + 1}"

        # Frame 5: triggers ILLEGAL_CHANGE
        events = sm.update(observed_with_extra, mean_confidence=0.9, timestamp=1004.0)
        illegal = [e for e in events if e.type == SyncEventType.ILLEGAL_CHANGE]
        assert len(illegal) == 1
        assert sm.state == SyncState.MISMATCH_WARNING

    def test_single_frame_flicker_does_not_trigger(self):
        """Test 15: Transient noise for 1 frame does not trigger ILLEGAL_CHANGE."""
        sm = SyncStateMachine(board_size=19, illegal_change_frames=5)
        sm.bind()
        sm.confirm_pose_lock()

        expected = empty_board()
        sm.set_expected_board(expected)

        observed_with_extra = board_with({(3, 3): BLACK})
        # One frame with unexpected stone
        events = sm.update(observed_with_extra, mean_confidence=0.9, timestamp=1000.0)
        illegal = [e for e in events if e.type == SyncEventType.ILLEGAL_CHANGE]
        assert len(illegal) == 0

        # Back to normal
        events = sm.update(expected.copy(), mean_confidence=0.9, timestamp=1001.0)
        assert sm.state == SyncState.SYNCED


class TestSyncStateMachineBoardLost:
    """Test 9: Many simultaneous differences trigger BOARD_LOST."""

    def test_board_displacement_triggers_board_lost(self):
        sm = SyncStateMachine(board_size=19, board_lost_threshold=10)
        sm.bind()
        sm.confirm_pose_lock()

        expected = empty_board()
        sm.set_expected_board(expected)

        # Place 12 stones at once -> exceeds threshold of 10
        stones = {}
        for i in range(12):
            stones[(i, 0)] = BLACK
        observed = board_with(stones)

        events = sm.update(observed, mean_confidence=0.9, timestamp=1000.0)
        assert sm.state == SyncState.BOARD_LOST
        lost_events = [e for e in events if e.type == SyncEventType.BOARD_LOST]
        assert len(lost_events) == 1


class TestSyncStateMachineBoardRecovery:
    """Test 10: BOARD_LOST recovery when board is detected again with matching state."""

    def test_board_lost_recovery(self):
        sm = SyncStateMachine(board_size=19)
        sm.bind()
        sm.confirm_pose_lock()

        expected = empty_board()
        sm.set_expected_board(expected)

        # Lose the board (board_detected=False)
        events = sm.update(None, mean_confidence=0.0, board_detected=False, timestamp=1000.0)
        assert sm.state == SyncState.BOARD_LOST
        lost_events = [e for e in events if e.type == SyncEventType.BOARD_LOST]
        assert len(lost_events) == 1

        # Re-acquire the board with matching state
        events = sm.update(expected.copy(), mean_confidence=0.9, board_detected=True, timestamp=1001.0)
        reacquired = [e for e in events if e.type == SyncEventType.BOARD_REACQUIRED]
        assert len(reacquired) == 1
        assert sm.state == SyncState.SYNCED


class TestSyncStateMachineTsumegoSetup:
    """Test 11 & 12: Setup mode for tsumego problems."""

    def test_setup_progress_and_complete(self):
        """Test 11: Partial match emits SETUP_PROGRESS, full match emits SETUP_COMPLETE."""
        sm = SyncStateMachine(board_size=19)
        sm.bind()
        sm.confirm_pose_lock()

        target = board_with({(3, 3): BLACK, (4, 4): WHITE, (5, 5): BLACK})
        sm.enter_setup_mode(target)
        assert sm.state == SyncState.SETUP_IN_PROGRESS

        # Partial match: only one stone placed
        observed_partial = board_with({(3, 3): BLACK})
        events = sm.update(observed_partial, mean_confidence=0.9, timestamp=1000.0)

        progress_events = [e for e in events if e.type == SyncEventType.SETUP_PROGRESS]
        assert len(progress_events) == 1
        assert progress_events[0].data["matched"] == 1
        assert progress_events[0].data["total"] == 3
        assert len(progress_events[0].data["missing"]) == 2
        assert sm.state == SyncState.SETUP_IN_PROGRESS

        # Full match: all stones placed
        events = sm.update(target.copy(), mean_confidence=0.9, timestamp=1001.0)

        progress_events = [e for e in events if e.type == SyncEventType.SETUP_PROGRESS]
        complete_events = [e for e in events if e.type == SyncEventType.SETUP_COMPLETE]
        assert len(progress_events) == 1
        assert progress_events[0].data["matched"] == 3
        assert len(complete_events) == 1
        assert sm.state == SyncState.SYNCED

    def test_setup_wrong_color_counts_as_missing(self):
        """Test 12: Target has BLACK at (3,3), observed has WHITE -> not matched."""
        sm = SyncStateMachine(board_size=19)
        sm.bind()
        sm.confirm_pose_lock()

        target = board_with({(3, 3): BLACK})
        sm.enter_setup_mode(target)

        # Wrong color at (3, 3)
        observed_wrong = board_with({(3, 3): WHITE})
        events = sm.update(observed_wrong, mean_confidence=0.9, timestamp=1000.0)

        progress_events = [e for e in events if e.type == SyncEventType.SETUP_PROGRESS]
        assert len(progress_events) == 1
        assert progress_events[0].data["matched"] == 0
        assert progress_events[0].data["total"] == 1
        assert progress_events[0].data["missing"] == [[3, 3]]
        assert sm.state == SyncState.SETUP_IN_PROGRESS


class TestSyncStateMachineDegradedMode:
    """Test 13: Low confidence triggers DEGRADED; recovery after sustained high confidence."""

    def test_degraded_entry_and_exit(self):
        sm = SyncStateMachine(
            board_size=19,
            degraded_confidence=0.35,
            degraded_recovery=0.45,
            degraded_enter_seconds=10.0,
            degraded_exit_seconds=5.0,
        )
        sm.bind()
        sm.confirm_pose_lock()

        expected = empty_board()
        sm.set_expected_board(expected)
        observed = expected.copy()

        t = 1000.0

        # Low confidence for 9 seconds: not yet degraded
        sm.update(observed, mean_confidence=0.30, timestamp=t)
        t += 9.0
        events = sm.update(observed, mean_confidence=0.30, timestamp=t)
        degraded = [e for e in events if e.type == SyncEventType.DEGRADED]
        assert len(degraded) == 0
        assert sm.state != SyncState.DEGRADED

        # Low confidence for >10 seconds total: enter degraded
        t += 1.5
        events = sm.update(observed, mean_confidence=0.30, timestamp=t)
        degraded = [e for e in events if e.type == SyncEventType.DEGRADED]
        assert len(degraded) == 1
        assert sm.state == SyncState.DEGRADED

        # While degraded, high confidence for 4 seconds: not yet recovered
        t += 0.1
        sm.update(observed, mean_confidence=0.50, timestamp=t)
        t += 4.0
        events = sm.update(observed, mean_confidence=0.50, timestamp=t)
        synced = [e for e in events if e.type == SyncEventType.SYNCED]
        assert len(synced) == 0
        assert sm.state == SyncState.DEGRADED

        # High confidence for >5 seconds total: recover
        t += 1.5
        events = sm.update(observed, mean_confidence=0.50, timestamp=t)
        synced = [e for e in events if e.type == SyncEventType.SYNCED]
        assert len(synced) == 1
        assert sm.state == SyncState.SYNCED


class TestSyncStateMachineCaptureStickyBehavior:
    """Test 14: CAPTURE_PENDING persists until stones are physically removed."""

    def test_capture_pending_persists_across_frames(self):
        sm = SyncStateMachine(board_size=19)
        sm.bind()
        sm.confirm_pose_lock()

        expected = board_with({(5, 5): BLACK, (5, 6): BLACK})
        sm.set_expected_board(expected)

        # Observed: both stones missing (captured by opponent)
        observed_empty = empty_board()
        events = sm.update(observed_empty, mean_confidence=0.9, timestamp=1000.0)
        assert sm.state == SyncState.CAPTURE_PENDING

        # One stone removed, but the other still on the board (expected has both, observed has one)
        observed_one_remaining = board_with({(5, 6): BLACK})
        events = sm.update(observed_one_remaining, mean_confidence=0.9, timestamp=1001.0)
        # Still pending because (5, 6) is present but should be gone to clear captures.
        # Wait -- the pending captures are stones where expected != EMPTY but observed == EMPTY.
        # (5,5) was expected=BLACK, observed=EMPTY => pending capture.
        # (5,6) was expected=BLACK, observed=BLACK => not a capture.
        # So pending_captures = [(5, 5, BLACK)].
        # still_pending checks if observed[5,5] != EMPTY -> observed[5,5] == EMPTY -> not pending.
        # Actually, the re-check: still_pending filters pending_captures where observed != EMPTY.
        # pending_captures = [(5, 5, BLACK), (5, 6, BLACK)] from initial pass.
        # On next frame with observed_one_remaining: observed[5,5]=EMPTY (not pending), observed[5,6]=BLACK (still pending).
        assert sm.state == SyncState.CAPTURE_PENDING

        # Both stones now absent
        events = sm.update(observed_empty, mean_confidence=0.9, timestamp=1002.0)
        cleared = [e for e in events if e.type == SyncEventType.CAPTURES_CLEARED]
        assert len(cleared) == 1
        assert sm.state == SyncState.SYNCED


class TestSyncStateMachineTransientNoise:
    """Test 15 (extra coverage): Multi-frame but changing noise does not trigger ILLEGAL_CHANGE."""

    def test_changing_noise_resets_mismatch_count(self):
        sm = SyncStateMachine(board_size=19, illegal_change_frames=5)
        sm.bind()
        sm.confirm_pose_lock()

        expected = empty_board()
        sm.set_expected_board(expected)

        # Alternate between two different unexpected patterns -- count should reset each time
        noise_a = board_with({(3, 3): BLACK})
        noise_b = board_with({(4, 4): WHITE})

        for i in range(10):
            noise = noise_a if i % 2 == 0 else noise_b
            events = sm.update(noise, mean_confidence=0.9, timestamp=1000.0 + i)
            illegal = [e for e in events if e.type == SyncEventType.ILLEGAL_CHANGE]
            assert len(illegal) == 0, f"Should not fire on frame {i}"


class TestSyncStateMachineUnbound:
    """Test 16: UNBOUND state ignores all updates."""

    def test_unbound_ignores_updates(self):
        sm = SyncStateMachine(board_size=19)
        assert sm.state == SyncState.UNBOUND

        observed = board_with({(0, 0): BLACK, (18, 18): WHITE})
        events = sm.update(observed, mean_confidence=0.9, timestamp=1000.0)
        assert events == []
        assert sm.state == SyncState.UNBOUND
