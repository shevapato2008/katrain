"""
Board sync state machine for Go board visual recognition.

Compares the observed board (from camera/YOLO) with the expected board
(from the game engine) and emits events when they diverge or re-converge.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from katrain.vision.board_state import BLACK, EMPTY, WHITE


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class SyncEventType(Enum):
    MOVE_CONFIRMED = "move_confirmed"  # MoveDetector confirmed a new stone
    CAPTURE_PENDING = "capture_pending"  # Stones need physical removal
    CAPTURES_CLEARED = "captures_cleared"  # User removed captured stones
    ILLEGAL_CHANGE = "illegal_change"  # Stable unexpected board change
    SETUP_PROGRESS = "setup_progress"  # N/M stones matched during tsumego setup
    SETUP_COMPLETE = "setup_complete"  # All target stones placed
    AMBIGUOUS_STONE = "ambiguous_stone"  # Stone between intersections
    BOARD_LOST = "board_lost"  # Board corners not detected
    BOARD_REACQUIRED = "board_reacquired"  # Board detected again after loss
    DEGRADED = "degraded"  # Low confidence, stop syncing
    SYNCED = "synced"  # Everything matches


@dataclass
class SyncEvent:
    type: SyncEventType
    data: dict = field(default_factory=dict)  # type-specific payload


# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------


class SyncState(Enum):
    UNBOUND = "unbound"
    CALIBRATING = "calibrating"
    SYNCED = "synced"
    CAPTURE_PENDING = "capture_pending"
    MISMATCH_WARNING = "mismatch_warning"
    BOARD_LOST = "board_lost"
    SETUP_IN_PROGRESS = "setup_in_progress"
    DEGRADED = "degraded"


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


class SyncStateMachine:
    """Compares observed board (from vision) with expected board (from game engine).

    Design principles:
    1. New stone confirmation stays in MoveDetector. SyncStateMachine trusts its output.
    2. ILLEGAL_CHANGE requires N consecutive frames (default 5) of stable mismatch.
    3. CAPTURE_PENDING is sticky — stays until stones are physically removed.
    4. Board displacement (many positions change simultaneously) triggers BOARD_LOST.
    5. Degraded mode: mean_confidence < 0.35 for 10 consecutive seconds → DEGRADED.
       Exit: mean_confidence > 0.45 for 5 seconds (hysteresis).
    """

    def __init__(
        self,
        board_size: int = 19,
        illegal_change_frames: int = 5,
        board_lost_threshold: int = 10,
        degraded_confidence: float = 0.35,
        degraded_recovery: float = 0.45,
        degraded_enter_seconds: float = 10.0,
        degraded_exit_seconds: float = 5.0,
    ):
        self._board_size = board_size
        self._illegal_change_frames = illegal_change_frames
        self._board_lost_threshold = board_lost_threshold
        self._degraded_confidence = degraded_confidence
        self._degraded_recovery = degraded_recovery
        self._degraded_enter_seconds = degraded_enter_seconds
        self._degraded_exit_seconds = degraded_exit_seconds

        # Board state
        self._expected_board: np.ndarray = np.zeros((board_size, board_size), dtype=int)
        self._target_board: np.ndarray | None = None

        # Mismatch tracking
        self._mismatch_board: np.ndarray | None = None
        self._mismatch_count: int = 0

        # Machine state
        self._state: SyncState = SyncState.UNBOUND
        self._pending_captures: list[tuple[int, int, int]] = []  # (row, col, color)

        # Degraded-mode timers
        self._degraded_timer_start: float | None = None
        self._degraded_recovery_start: float | None = None

    # -- properties ----------------------------------------------------------

    @property
    def state(self) -> SyncState:
        return self._state

    # -- public API ----------------------------------------------------------

    def set_expected_board(self, board: np.ndarray) -> None:
        """Set the expected board (from game engine)."""
        self._expected_board = board.copy()

    def enter_setup_mode(self, target_board: np.ndarray) -> None:
        """Enter tsumego setup mode with a target position."""
        self._target_board = target_board.copy()
        self._state = SyncState.SETUP_IN_PROGRESS

    def update(
        self,
        observed_board: np.ndarray | None,
        mean_confidence: float = 1.0,
        board_detected: bool = True,
        timestamp: float | None = None,
    ) -> list[SyncEvent]:
        """Process one frame and return events.

        Args:
            observed_board: (board_size, board_size) matrix, or None if board not detected.
            mean_confidence: average confidence of all detections in this frame.
            board_detected: whether board corners were found (False → BOARD_LOST).
            timestamp: frame timestamp (defaults to time.time()).

        Returns:
            List of SyncEvent generated by this frame.
        """
        if self._state == SyncState.UNBOUND:
            return []

        now = timestamp if timestamp is not None else time.time()
        events: list[SyncEvent] = []

        # 1. Board detection check
        if not board_detected or observed_board is None:
            if self._state != SyncState.BOARD_LOST:
                self._state = SyncState.BOARD_LOST
                events.append(SyncEvent(SyncEventType.BOARD_LOST))
            return events

        if self._state == SyncState.BOARD_LOST:
            self._state = SyncState.SYNCED
            events.append(SyncEvent(SyncEventType.BOARD_REACQUIRED))
            # Fall through to remaining checks with the new frame.

        # 2. Degraded-mode hysteresis
        degraded_events = self._check_degraded(mean_confidence, now)
        events.extend(degraded_events)
        if self._state == SyncState.DEGRADED:
            return events

        # 3. Setup mode
        if self._state == SyncState.SETUP_IN_PROGRESS and self._target_board is not None:
            setup_events = self._check_setup(observed_board)
            events.extend(setup_events)
            return events

        # 4. Compare with expected board
        compare_events = self._compare_boards(observed_board)
        events.extend(compare_events)

        return events

    def reset(self, observed_board: np.ndarray | None = None) -> None:
        """Reset sync state. If *observed_board* given, use as new expected."""
        if observed_board is not None:
            self._expected_board = observed_board.copy()
        else:
            self._expected_board = np.zeros((self._board_size, self._board_size), dtype=int)
        self._target_board = None
        self._mismatch_board = None
        self._mismatch_count = 0
        self._pending_captures = []
        self._degraded_timer_start = None
        self._degraded_recovery_start = None
        self._state = SyncState.SYNCED

    def bind(self) -> None:
        """Transition from UNBOUND to CALIBRATING."""
        self._state = SyncState.CALIBRATING

    def confirm_pose_lock(self) -> None:
        """Transition from CALIBRATING to SYNCED."""
        self._state = SyncState.SYNCED

    # -- internal helpers ----------------------------------------------------

    def _check_degraded(self, mean_confidence: float, now: float) -> list[SyncEvent]:
        """Evaluate degraded-mode entry/exit with hysteresis."""
        events: list[SyncEvent] = []

        if self._state == SyncState.DEGRADED:
            # Check recovery
            if mean_confidence > self._degraded_recovery:
                if self._degraded_recovery_start is None:
                    self._degraded_recovery_start = now
                elif now - self._degraded_recovery_start >= self._degraded_exit_seconds:
                    self._state = SyncState.SYNCED
                    events.append(SyncEvent(SyncEventType.SYNCED))
                    self._degraded_recovery_start = None
                    self._degraded_timer_start = None
            else:
                self._degraded_recovery_start = None
        else:
            # Check entry
            if mean_confidence < self._degraded_confidence:
                if self._degraded_timer_start is None:
                    self._degraded_timer_start = now
                elif now - self._degraded_timer_start >= self._degraded_enter_seconds:
                    self._state = SyncState.DEGRADED
                    events.append(SyncEvent(SyncEventType.DEGRADED))
                    self._degraded_recovery_start = None
            else:
                self._degraded_timer_start = None

        return events

    def _check_setup(self, observed_board: np.ndarray) -> list[SyncEvent]:
        """Compare observed board against the tsumego target board."""
        assert self._target_board is not None
        events: list[SyncEvent] = []

        target_positions = list(zip(*np.where(self._target_board != EMPTY)))
        total = len(target_positions)
        matched = 0
        missing: list[list[int]] = []

        for r, c in target_positions:
            if observed_board[r, c] == self._target_board[r, c]:
                matched += 1
            else:
                missing.append([r, c])

        events.append(
            SyncEvent(
                SyncEventType.SETUP_PROGRESS,
                data={"matched": matched, "total": total, "missing": missing},
            )
        )

        if matched == total:
            events.append(SyncEvent(SyncEventType.SETUP_COMPLETE))
            self._target_board = None
            self._expected_board = observed_board.copy()
            self._state = SyncState.SYNCED

        return events

    def _compare_boards(self, observed_board: np.ndarray) -> list[SyncEvent]:
        """Compare observed board with expected board and emit sync events."""
        events: list[SyncEvent] = []
        diff_mask = observed_board != self._expected_board

        diff_positions = list(zip(*np.where(diff_mask)))
        diff_count = len(diff_positions)

        # 4a. Many simultaneous changes → board displaced / lost
        if diff_count >= self._board_lost_threshold:
            self._state = SyncState.BOARD_LOST
            events.append(SyncEvent(SyncEventType.BOARD_LOST, data={"diff_count": diff_count}))
            self._mismatch_board = None
            self._mismatch_count = 0
            return events

        # 4b. Check captures: stones expected but not observed
        captures: list[tuple[int, int, int]] = []
        unexpected: list[tuple[int, int, int]] = []

        for r, c in diff_positions:
            expected_val = int(self._expected_board[r, c])
            observed_val = int(observed_board[r, c])
            if expected_val != EMPTY and observed_val == EMPTY:
                # Stone expected but missing → capture candidate
                captures.append((r, c, expected_val))
            elif expected_val == EMPTY and observed_val != EMPTY:
                # Stone present but not expected → unexpected placement
                unexpected.append((r, c, observed_val))
            elif expected_val != EMPTY and observed_val != EMPTY and expected_val != observed_val:
                # Color changed — treat as unexpected
                unexpected.append((r, c, observed_val))

        # 4c. Capture-pending logic (sticky)
        if captures and self._state != SyncState.CAPTURE_PENDING:
            self._pending_captures = captures
            self._state = SyncState.CAPTURE_PENDING
            events.append(
                SyncEvent(
                    SyncEventType.CAPTURE_PENDING,
                    data={"positions": [(r, c, clr) for r, c, clr in captures]},
                )
            )
            return events

        if self._state == SyncState.CAPTURE_PENDING:
            # Check if captures have been cleared
            still_pending = [
                (r, c, clr)
                for r, c, clr in self._pending_captures
                if int(observed_board[r, c]) != EMPTY
            ]
            if not still_pending:
                self._pending_captures = []
                self._state = SyncState.SYNCED
                events.append(SyncEvent(SyncEventType.CAPTURES_CLEARED))
                # Fall through to check for remaining differences.
            else:
                self._pending_captures = still_pending
                return events

        # 4d. Unexpected changes → stable mismatch tracking
        if unexpected:
            # Build a fingerprint of current unexpected positions for stability check
            current_mismatch = np.zeros_like(self._expected_board)
            for r, c, clr in unexpected:
                current_mismatch[r, c] = clr

            if self._mismatch_board is not None and np.array_equal(current_mismatch, self._mismatch_board):
                self._mismatch_count += 1
            else:
                self._mismatch_board = current_mismatch
                self._mismatch_count = 1

            if self._mismatch_count >= self._illegal_change_frames:
                self._state = SyncState.MISMATCH_WARNING
                events.append(
                    SyncEvent(
                        SyncEventType.ILLEGAL_CHANGE,
                        data={"positions": [(r, c, clr) for r, c, clr in unexpected]},
                    )
                )
                self._mismatch_board = None
                self._mismatch_count = 0
            elif self._state != SyncState.MISMATCH_WARNING:
                self._state = SyncState.MISMATCH_WARNING

            return events

        # 4e. No differences — everything matches
        self._mismatch_board = None
        self._mismatch_count = 0
        if self._state != SyncState.SYNCED:
            self._state = SyncState.SYNCED
            events.append(SyncEvent(SyncEventType.SYNCED))

        return events


# ---------------------------------------------------------------------------
# Conversion helper
# ---------------------------------------------------------------------------


def game_state_stones_to_board(
    stones: list[list],
    board_size: int = 19,
) -> np.ndarray:
    """Convert GameState.stones tuple array to vision board matrix.

    Each entry in *stones* is ``[player, [col, gtp_row]|null, scoreLoss, moveNum]``
    where *player* is ``"B"`` or ``"W"`` and *gtp_row* 0 = bottom.

    The vision board uses ``board[row][col]`` where row 0 = top, so:
        vision_row = board_size - 1 - gtp_row
    """
    board = np.zeros((board_size, board_size), dtype=int)

    for entry in stones:
        player = entry[0]
        coords = entry[1]
        if coords is None:
            continue  # pass move
        col, gtp_row = coords[0], coords[1]
        vision_row = board_size - 1 - gtp_row
        board[vision_row, col] = BLACK if player == "B" else WHITE

    return board
