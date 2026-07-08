"""Regressions for the physical-tsumego "已匹配 0/17" / mid-setup LED-death bug.

Root cause chain (confirmed from live board DIAG logs, 2026-07-08):
  1. ILLEGAL_CHANGE / CAPTURE_PENDING event `positions` were built straight from
     ``np.where`` → numpy ``int64``. The /ws/vision send loop does ``json.dumps``,
     which rejects numpy scalars → the socket handler raised and the WebSocket
     died. Every later vision event went to 0 clients, so the kiosk froze at
     "已匹配 0/17" and the LEDs (cleared on WS drop) never came back.
  2. A single-frame BOARD_LOST during setup (a hand occluding a corner while
     placing stones) exited SETUP_IN_PROGRESS on reacquire, so subsequently
     placed stones were reported as ILLEGAL_CHANGE instead of SETUP_PROGRESS.
"""

import json

import numpy as np

from katrain.vision.board_state import BLACK, WHITE
from katrain.vision.sync import SyncEventType, SyncState, SyncStateMachine


def empty_board(size: int = 19) -> np.ndarray:
    return np.zeros((size, size), dtype=int)


def board_with(stones: dict, size: int = 19) -> np.ndarray:
    board = empty_board(size)
    for (r, c), color in stones.items():
        board[r, c] = color
    return board


def _synced_machine(**kwargs) -> SyncStateMachine:
    m = SyncStateMachine(**kwargs)
    m.bind()
    m.confirm_pose_lock()  # → SYNCED, expected board = empty
    return m


def _all_ints(positions) -> bool:
    return all(isinstance(v, int) and not isinstance(v, np.generic) for pos in positions for v in pos)


class TestVisionEventJsonSafety:
    def test_illegal_change_positions_are_json_serializable(self):
        m = _synced_machine(illegal_change_frames=3)
        observed = board_with({(6, 17): BLACK})  # unexpected stone (col 17 = a np.int64 in the log)
        events = []
        for _ in range(3):
            events = m.update(observed)
        illegal = [e for e in events if e.type == SyncEventType.ILLEGAL_CHANGE]
        assert illegal, "expected ILLEGAL_CHANGE after a stable unexpected stone"
        # THE regression: numpy int64 in positions crashes json.dumps → kills /ws/vision.
        json.dumps(illegal[0].data)
        assert _all_ints(illegal[0].data["positions"])

    def test_capture_pending_positions_are_json_serializable(self):
        # Digital-authority semantics (post-develop merge): CAPTURE_PENDING is an ACTUAL
        # digital capture — a synced stone that the engine removes while the physical
        # stone is still on the board. (A newly-expected-but-unplaced stone is
        # placement_pending, not capture.) col 17 is the np.int64 that crashed json.dumps.
        m = _synced_machine()
        with_stone = board_with({(6, 17): BLACK})
        m.set_expected_board(with_stone)
        m.update(with_stone.copy())  # placed digitally + physically → SYNCED
        m.set_expected_board(empty_board())  # engine captures it…
        events = m.update(with_stone.copy())  # …but the physical stone lingers → capture
        captures = [e for e in events if e.type == SyncEventType.CAPTURE_PENDING]
        assert captures, "expected CAPTURE_PENDING when a synced stone is digitally captured"
        # THE regression: numpy int64 in positions crashes json.dumps → kills /ws/vision.
        json.dumps(captures[0].data)
        assert _all_ints(captures[0].data["positions"])


class TestSetupSurvivesBoardLost:
    def test_board_lost_then_reacquired_resumes_setup(self):
        target = board_with({(6, 17): BLACK, (5, 5): WHITE})
        m = _synced_machine()
        m.enter_setup_mode(target)
        assert m.state == SyncState.SETUP_IN_PROGRESS

        # Hand reaches over the board to place a stone → a corner is briefly lost.
        m.update(None, board_detected=False)
        assert m.state == SyncState.BOARD_LOST

        # Board reacquired with one target stone placed: must resume setup, NOT
        # drop to compare mode (which reports placed stones as ILLEGAL_CHANGE).
        events = m.update(board_with({(6, 17): BLACK}), board_detected=True)
        assert m.state == SyncState.SETUP_IN_PROGRESS
        types = {e.type for e in events}
        assert SyncEventType.SETUP_PROGRESS in types
        assert SyncEventType.ILLEGAL_CHANGE not in types
