import json

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
    """Test 7: Capture pending -> cleared -> SYNCED.

    Migrated to the digital-authority pattern (Codex Blocker 2 / Task 5): under the
    new four-way diff, "expected stone the player hasn't placed yet" is
    placement_pending, not capture_pending (see TestDigitalAuthorityDiff). Now
    CAPTURE_PENDING is reserved for an actual digital capture — expected goes from
    "has stone" to EMPTY while the physical stone is still on the board
    (prev == observed). This test drives that sequence explicitly instead of relying
    on a single set_expected_board() call.
    """

    def test_capture_pending_and_cleared(self):
        sm = SyncStateMachine(board_size=19)
        sm.bind()
        sm.confirm_pose_lock()

        # Stone at (5, 5) is placed both digitally and physically -> synced.
        with_stone = board_with({(5, 5): BLACK})
        sm.set_expected_board(with_stone)
        sm.update(with_stone.copy(), mean_confidence=0.9, timestamp=999.0)
        assert sm.state == SyncState.SYNCED

        # Digital side captures the stone (engine says it's gone), but the physical
        # stone is still sitting on the board -> CAPTURE_PENDING.
        without_stone = empty_board()
        sm.set_expected_board(without_stone)
        events = sm.update(with_stone.copy(), mean_confidence=0.9, timestamp=1000.0)

        assert sm.state == SyncState.CAPTURE_PENDING
        capture_events = [e for e in events if e.type == SyncEventType.CAPTURE_PENDING]
        assert len(capture_events) == 1
        assert capture_events[0].data["positions"] == [(5, 5, BLACK)]

        # Now the stone is physically removed (observed matches the new expected).
        events2 = sm.update(without_stone.copy(), mean_confidence=0.9, timestamp=1001.0)
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
    """Test 14: CAPTURE_PENDING persists until stones are physically removed.

    Migrated to the digital-authority pattern (Codex Blocker 2 / Task 5) — see the
    docstring on TestSyncStateMachineCaptureFlow. Both stones are placed digitally
    and physically first, then digitally captured, so the physical stones remain
    and removal_needed classifies them as CAPTURE_PENDING (prev == observed at both
    points), exercising the same sticky still_pending behavior as before.
    """

    def test_capture_pending_persists_across_frames(self):
        sm = SyncStateMachine(board_size=19)
        sm.bind()
        sm.confirm_pose_lock()

        # Both stones placed digitally and physically -> synced.
        with_stones = board_with({(5, 5): BLACK, (5, 6): BLACK})
        sm.set_expected_board(with_stones)
        sm.update(with_stones.copy(), mean_confidence=0.9, timestamp=999.0)
        assert sm.state == SyncState.SYNCED

        # Digital side captures both stones; physically they're still on the board.
        without_stones = empty_board()
        sm.set_expected_board(without_stones)
        events = sm.update(with_stones.copy(), mean_confidence=0.9, timestamp=1000.0)
        assert sm.state == SyncState.CAPTURE_PENDING

        # One stone physically removed, but the other still on the board.
        # pending_captures = [(5, 5, BLACK), (5, 6, BLACK)] from the initial pass.
        # On this frame: observed[5,5]=EMPTY (not still pending), observed[5,6]=BLACK (still pending).
        observed_one_remaining = board_with({(5, 6): BLACK})
        events = sm.update(observed_one_remaining, mean_confidence=0.9, timestamp=1001.0)
        assert sm.state == SyncState.CAPTURE_PENDING

        # Both stones now physically absent -> matches new expected -> cleared.
        events = sm.update(without_stones.copy(), mean_confidence=0.9, timestamp=1002.0)
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


class TestDigitalAuthorityDiff:
    """After the orchestrator pushes expected on every game_update (digital authority)."""

    def _synced_machine(self, expected):
        sm = SyncStateMachine()
        sm.bind()
        sm.confirm_pose_lock()
        sm.set_expected_board(expected)
        return sm

    def test_newly_expected_stone_is_placement_pending_not_capture(self):
        sm = self._synced_machine(empty_board())
        with_ai = board_with({(3, 3): 1})
        sm.set_expected_board(with_ai)  # AI 数字落子
        events = sm.update(observed_board=empty_board())  # 用户还没摆
        types = [e.type for e in events]
        assert SyncEventType.CAPTURE_PENDING not in types
        assert SyncEventType.ILLEGAL_CHANGE not in types
        assert sm.state == SyncState.SYNCED  # 待摆放不是异常

    def test_digital_capture_emits_capture_pending_until_removed(self):
        before = board_with({(5, 5): 2, (3, 3): 1})
        sm = self._synced_machine(before)
        sm.update(observed_board=before)
        after = board_with({(3, 3): 1})  # 数字盘提掉 (5,5)
        sm.set_expected_board(after)
        events = sm.update(observed_board=before)  # 物理盘白子还在
        pend = [e for e in events if e.type == SyncEventType.CAPTURE_PENDING]
        assert pend and (5, 5, 2) in [tuple(p) for p in pend[0].data["positions"]]
        events = sm.update(observed_board=after)  # 拿掉
        assert SyncEventType.CAPTURES_CLEARED in [e.type for e in events]

    def test_truly_unexpected_stone_still_illegal_change_with_missing(self):
        # 场景刻意不含「待拿除」差异（removal 会先走 sticky CAPTURE_PENDING 分支）：
        # 期望新增 (9,9) 白（待摆放），观测却在 (15,15) 乱放一子。
        sm = self._synced_machine(empty_board())
        sm.set_expected_board(board_with({(9, 9): 2}))
        bad = board_with({(15, 15): 1})
        events = []
        for _ in range(5):  # illegal_change_frames 默认 5
            events = sm.update(observed_board=bad)
        illegal = [e for e in events if e.type == SyncEventType.ILLEGAL_CHANGE]
        assert illegal
        assert (15, 15, 1) in [tuple(p) for p in illegal[0].data["positions"]]
        # missing = 待摆放清单（供恢复对话框），且它自己不构成异常
        assert (9, 9, 2) in [tuple(p) for p in illegal[0].data["missing"]]

    def test_stolen_live_stone_is_anomaly_not_capture(self):
        # 评审 Codex Blocker 2 回归：盘上活子被误拿走（数字盘没提它）——绝不能走
        # CAPTURE_PENDING→秒清除把异常吞掉；必须进 mismatch 防抖流并列入 missing。
        live = board_with({(3, 3): 1, (5, 5): 2})
        sm = self._synced_machine(live)
        sm.update(observed_board=live)
        sm.set_expected_board(live)  # prev = live（无数字侧变化）
        gone = board_with({(3, 3): 1})  # (5,5) 白子被拿走
        all_events = []
        for _ in range(5):  # illegal_change_frames 默认 5
            all_events += sm.update(observed_board=gone)
        types = [e.type for e in all_events]
        assert SyncEventType.CAPTURE_PENDING not in types
        illegal = [e for e in all_events if e.type == SyncEventType.ILLEGAL_CHANGE]
        assert illegal
        assert (5, 5, 2) in [tuple(p) for p in illegal[0].data["missing"]]

    def test_setup_complete_resets_prev_so_vanished_stone_is_anomaly(self):
        # Regression: SETUP_COMPLETE must reset prev-expected, else an orphaned prev
        # can silently swallow a vanished live stone into placement_pending.
        sm = SyncStateMachine(board_size=19)
        sm.bind()
        sm.confirm_pose_lock()
        # Prior digital-authority play leaves an orphaned prev, EMPTY at the tsumego spots.
        sm.set_expected_board(board_with({(0, 0): 1}))
        sm.set_expected_board(board_with({(0, 0): 1}))  # prev now = {(0,0):BLACK}
        # Enter and complete a tsumego at different locations.
        target = board_with({(5, 5): 1, (5, 6): 2})
        sm.enter_setup_mode(target)
        sm.update(observed_board=target.copy())  # -> SETUP_COMPLETE, state SYNCED
        # A live stone now vanishes before any new set_expected_board push.
        gone = board_with({(5, 5): 1})  # (5,6) white removed
        all_events = []
        for _ in range(5):  # illegal_change_frames default 5
            all_events += sm.update(observed_board=gone)
        # With prev reset (None), (5,6) -> missing_anomaly -> illegal_change. Without the fix,
        # stale prev[(5,6)]==EMPTY would (wrongly) make it placement_pending (silent).
        illegal = [e for e in all_events if e.type == SyncEventType.ILLEGAL_CHANGE]
        assert illegal, "vanished live stone after SETUP_COMPLETE must raise an anomaly, not be swallowed"
        assert (5, 6, 2) in [tuple(p) for p in illegal[0].data["missing"]]


class TestEventPayloadsAreJsonSerializable:
    """Regression: sync events flow to the frontend via websocket.send_json (/ws/vision),
    which uses json.dumps — numpy.int64 positions from np.where would crash the socket and
    silently kill the on-screen confirmation UX. Positions/missing must be plain python ints."""

    def _synced(self, expected):
        sm = SyncStateMachine(board_size=19)
        sm.bind()
        sm.confirm_pose_lock()
        sm.set_expected_board(expected)
        return sm

    def test_capture_pending_positions_json_serializable(self):
        before = board_with({(5, 5): WHITE, (3, 3): BLACK})
        sm = self._synced(before)
        sm.update(observed_board=before)
        sm.set_expected_board(board_with({(3, 3): BLACK}))  # digital capture of (5,5)
        events = sm.update(observed_board=before)  # physical stone still there
        pend = [e for e in events if e.type == SyncEventType.CAPTURE_PENDING]
        assert pend
        for r, c, clr in pend[0].data["positions"]:
            assert type(r) is int and type(c) is int  # not numpy.int64
        json.dumps({"type": pend[0].type.value, "data": pend[0].data})  # must not raise

    def test_illegal_change_positions_and_missing_json_serializable(self):
        sm = self._synced(empty_board())
        sm.set_expected_board(board_with({(9, 9): WHITE}))  # placement_pending target
        bad = board_with({(15, 15): BLACK})  # unexpected extra
        events = []
        for _ in range(5):
            events = sm.update(observed_board=bad)
        illegal = [e for e in events if e.type == SyncEventType.ILLEGAL_CHANGE]
        assert illegal
        for r, c, clr in illegal[0].data["positions"] + illegal[0].data["missing"]:
            assert type(r) is int and type(c) is int
        json.dumps({"type": illegal[0].type.value, "data": illegal[0].data})  # must not raise

    def test_setup_progress_missing_json_serializable(self):
        sm = SyncStateMachine(board_size=19)
        sm.bind()
        sm.confirm_pose_lock()
        sm.enter_setup_mode(board_with({(3, 3): BLACK, (5, 5): WHITE}))
        events = sm.update(observed_board=board_with({(3, 3): BLACK}))  # partial → SETUP_PROGRESS
        prog = [e for e in events if e.type == SyncEventType.SETUP_PROGRESS]
        assert prog
        for r, c in prog[0].data["missing"]:
            assert type(r) is int and type(c) is int
        json.dumps({"type": prog[0].type.value, "data": prog[0].data})  # must not raise
