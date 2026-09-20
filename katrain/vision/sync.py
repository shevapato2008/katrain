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
        missing_hold_seconds: float = 7.0,
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
        self._prev_expected_board: np.ndarray | None = None
        self._expected_node_id: int | None = None
        self._pending_expected_node_id: int | None = None
        self._target_board: np.ndarray | None = None

        # Mismatch tracking
        self._mismatch_board: np.ndarray | None = None
        self._mismatch_count: int = 0

        # A live stone vision cannot see is held back until it has been continuously
        # invisible for BOTH missing_hold_seconds of real time AND illegal_change_frames
        # of actually-observed frames. Wall-clock alone is not enough: gating.py's
        # should_feed_sync_frame stops feeding frames while the scene moves, so a 3-second
        # occlusion arrives here as two frames 3 seconds apart. The old gate was the frame
        # counter alone, which at the board's 6-15 fps is 0.3-0.8s — an arm passing over.
        self._missing_hold_seconds = missing_hold_seconds
        self._missing_since: dict[tuple[int, int], list] = {}  # (row,col) -> [first_seen_ts, frames]

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

    def set_expected_board(self, board: np.ndarray, *, expected_node_id: int | None = None) -> None:
        """Set the expected board (from game engine).

        Keeps the previous distinct expected board so ``_compare_boards`` can tell
        "digital stone the player hasn't placed yet" from "stone that must come
        off". Repeating the same matrix does not advance that baseline. A new node
        revision is tracked independently and acknowledged once vision observes an
        exact physical match.
        """
        if not np.array_equal(board, self._expected_board):
            self._prev_expected_board = self._expected_board.copy()
            self._expected_board = board.copy()
            if self._state == SyncState.CAPTURE_PENDING:
                self._pending_captures = [
                    (r, c, color) for r, c, color in self._pending_captures if int(board[r, c]) != color
                ]
                if not self._pending_captures:
                    self._state = SyncState.SYNCED

        if expected_node_id != self._expected_node_id:
            self._expected_node_id = expected_node_id
            self._pending_expected_node_id = expected_node_id

    def enter_setup_mode(self, target_board: np.ndarray) -> None:
        """Enter tsumego setup mode with a target position."""
        self._target_board = target_board.copy()
        self._state = SyncState.SETUP_IN_PROGRESS
        # A fresh setup must not inherit a stale degraded countdown: otherwise an
        # already-empty board (mean_conf reported as 0.0) re-enters DEGRADED on the
        # very next frame and starves _check_setup, so "clear board" never completes.
        self._degraded_timer_start = None
        self._degraded_recovery_start = None

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

        was_board_lost = self._state == SyncState.BOARD_LOST
        if was_board_lost and self._target_board is not None:
            # A transient loss during setup (a hand occluding a corner while placing
            # stones) must NOT abandon setup: resume it so subsequently placed stones
            # keep reporting as SETUP_PROGRESS instead of dropping to compare mode and
            # being flagged as ILLEGAL_CHANGE.
            self._state = SyncState.SETUP_IN_PROGRESS

        # 2. Degraded-mode hysteresis
        was_degraded = self._state == SyncState.DEGRADED
        degraded_events = self._check_degraded(mean_confidence, now)
        events.extend(degraded_events)
        if self._state == SyncState.DEGRADED:
            return events
        if was_degraded:
            return events

        # 3. Setup mode
        if self._state == SyncState.SETUP_IN_PROGRESS and self._target_board is not None:
            setup_events = self._check_setup(observed_board)
            events.extend(setup_events)
        else:
            # 4. Compare with expected board before declaring recovery: a visible
            # frame can still contain the same displacement that caused BOARD_LOST.
            events.extend(self._compare_boards(observed_board, now))

        if was_board_lost and self._state != SyncState.BOARD_LOST:
            events.insert(0, SyncEvent(SyncEventType.BOARD_REACQUIRED))

        return events

    def reset(self, observed_board: np.ndarray | None = None) -> None:
        """Reset sync state. If *observed_board* given, use as new expected."""
        if observed_board is not None:
            self._expected_board = observed_board.copy()
        else:
            self._expected_board = np.zeros((self._board_size, self._board_size), dtype=int)
        self._prev_expected_board = None
        self._expected_node_id = None
        self._pending_expected_node_id = None
        self._target_board = None
        self._mismatch_board = None
        self._mismatch_count = 0
        self._missing_since = {}
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
        """Compare observed board against the tsumego target board.

        missing = target points whose observed content differs (empty OR wrong color).
        extra   = observed stones that differ from target (on empty target points OR
                  wrong color on a target point — such points appear in BOTH lists).
        SETUP_COMPLETE requires exact equality: missing AND extra both empty.
        """
        assert self._target_board is not None
        events: list[SyncEvent] = []

        total = int(np.count_nonzero(self._target_board != EMPTY))
        missing = [
            [int(r), int(c)]
            for r, c in zip(*np.where((self._target_board != EMPTY) & (observed_board != self._target_board)))
        ]
        extra = [
            [int(r), int(c), int(observed_board[r, c])]
            for r, c in zip(*np.where((observed_board != EMPTY) & (observed_board != self._target_board)))
        ]
        matched = total - len(missing)

        events.append(
            SyncEvent(
                SyncEventType.SETUP_PROGRESS,
                data={"matched": matched, "total": total, "missing": missing, "extra": extra},
            )
        )

        if not missing and not extra:
            events.append(SyncEvent(SyncEventType.SETUP_COMPLETE))
            self._target_board = None
            self._expected_board = observed_board.copy()
            self._prev_expected_board = None
            self._expected_node_id = None
            self._pending_expected_node_id = None
            self._state = SyncState.SYNCED

        return events

    def _compare_boards(self, observed_board: np.ndarray, now: float) -> list[SyncEvent]:
        """Compare observed board with expected board and emit sync events."""
        events: list[SyncEvent] = []
        diff_mask = observed_board != self._expected_board

        diff_positions = list(zip(*np.where(diff_mask)))
        diff_count = len(diff_positions)

        # 4a. Classify against the previous expected board (digital authority).
        #     Newly-expected stone the player hasn't placed yet is NOT an anomaly;
        #     a live stone that vanished physically IS one (review Codex B2) — it must
        #     ride the debounced mismatch flow, never the instantly-self-clearing
        #     capture flow. removal_needed only holds points where a stone is still
        #     physically present, so the sticky still_pending check stays meaningful.
        prev = self._prev_expected_board
        removal_needed: list[tuple[int, int, int]] = []  # physical stone must come OFF
        placement_pending: list[tuple[int, int, int]] = []  # digital stone awaiting placement
        missing_anomaly: list[tuple[int, int, int]] = []  # live stone vanished physically
        unexpected: list[tuple[int, int, int]] = []

        for r, c in diff_positions:
            r, c = int(r), int(
                c
            )  # np.where yields numpy.int64 → cast so event payloads are JSON-serializable (/ws/vision)
            expected_val = int(self._expected_board[r, c])
            observed_val = int(observed_board[r, c])
            if expected_val != EMPTY and observed_val == EMPTY:
                if prev is not None and int(prev[r, c]) == EMPTY:
                    placement_pending.append((r, c, expected_val))  # e.g. AI move lamp lit
                else:
                    missing_anomaly.append(
                        (r, c, expected_val)
                    )  # stolen live stone (or pre-injection capture transient)
            elif expected_val == EMPTY and observed_val != EMPTY:
                if prev is not None and int(prev[r, c]) == observed_val:
                    removal_needed.append((r, c, observed_val))  # digital capture/undo pending removal
                else:
                    unexpected.append((r, c, observed_val))
            elif expected_val != EMPTY and observed_val != EMPTY and expected_val != observed_val:
                # Color changed — treat as unexpected
                unexpected.append((r, c, observed_val))

        # 4a-bis. Hold back a missing stone until it has been continuously invisible for
        # both a real elapsed period and a minimum number of observed frames — see
        # `_missing_hold_seconds`. `missing_anomaly` itself is left intact because the
        # board-lost check below must still react immediately: a displaced board produces
        # many missing points at once and is not something to wait out.
        held_missing: list[tuple[int, int, int]] = []
        ripe_missing: list[tuple[int, int, int]] = []
        seen_missing: set[tuple[int, int]] = set()
        for r, c, clr in missing_anomaly:
            cell = (r, c)
            seen_missing.add(cell)
            entry = self._missing_since.get(cell)
            if entry is None:
                entry = [now, 0]
                self._missing_since[cell] = entry
            entry[1] += 1
            # entry[1] >= self._illegal_change_frames (D5's second condition) is defence
            # in depth: it is CURRENTLY structurally redundant with the pre-existing
            # _mismatch_count stability debounce below (4d), because both are gated at
            # the same self._illegal_change_frames threshold and both accumulate over the
            # same event stream — frames where this cell is in missing_anomaly. By the
            # time _mismatch_count could reach that threshold and fire, this cell has by
            # construction already been observed that many times, so this clause cannot
            # currently change WHETHER ILLEGAL_CHANGE eventually fires — only, in the rare
            # case where wall-clock alone would have gone ripe earlier (a long occlusion
            # gap followed by fast frames), WHEN the debounce starts counting, delaying the
            # fire. Every test but one in this class cannot tell "this clause present" from
            # "this clause deleted" — a green suite there is not evidence it is unnecessary,
            # only that today's debounce already implies it for the ordinary case. See
            # test_frame_count_condition_delays_ripening_after_a_long_gap in
            # test_sync.py::TestMissingStoneHold for the one ordering that DOES distinguish
            # them. Keep this clause — it makes D5's intent explicit in code and it is what
            # protects the missing path if the debounce is ever loosened or removed
            # independently.
            if now - entry[0] >= self._missing_hold_seconds and entry[1] >= self._illegal_change_frames:
                ripe_missing.append((r, c, clr))
            else:
                held_missing.append((r, c, clr))
        for cell in list(self._missing_since):
            if cell not in seen_missing:
                del self._missing_since[cell]

        # 4b. Many unexplained changes → board displaced / lost. Captures and
        # digitally requested placements are known changes, even for large groups.
        if len(unexpected) + len(missing_anomaly) >= self._board_lost_threshold:
            if self._state != SyncState.BOARD_LOST:
                events.append(SyncEvent(SyncEventType.BOARD_LOST, data={"diff_count": diff_count}))
            self._state = SyncState.BOARD_LOST
            self._mismatch_board = None
            self._mismatch_count = 0
            return events

        # 4c. Capture-pending logic (sticky)
        if removal_needed and self._state != SyncState.CAPTURE_PENDING:
            self._pending_captures = removal_needed
            self._state = SyncState.CAPTURE_PENDING
            events.append(
                SyncEvent(
                    SyncEventType.CAPTURE_PENDING,
                    data={"positions": [(r, c, clr) for r, c, clr in removal_needed]},
                )
            )
            return events

        if self._state == SyncState.CAPTURE_PENDING:
            # Check if captures have been cleared
            still_pending = [(r, c, clr) for r, c, clr in self._pending_captures if int(observed_board[r, c]) != EMPTY]
            if not still_pending:
                self._pending_captures = []
                self._state = SyncState.SYNCED
                events.append(SyncEvent(SyncEventType.CAPTURES_CLEARED))
                # Fall through to check for remaining differences.
            else:
                self._pending_captures = still_pending
                return events

        # 4d. Anomaly tracking: unexpected extras AND ripe missing live stones both count.
        if unexpected or ripe_missing:
            # Build a fingerprint of current anomalous positions for stability check.
            current_mismatch = np.zeros_like(self._expected_board)
            for r, c, clr in unexpected:
                current_mismatch[r, c] = clr
            for r, c, clr in ripe_missing:
                current_mismatch[r, c] = clr + 2  # distinct fingerprint values (3/4)

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
                        data={
                            "positions": [(r, c, clr) for r, c, clr in unexpected],
                            "missing": [(r, c, clr) for r, c, clr in ripe_missing + placement_pending],
                        },
                    )
                )
                self._mismatch_board = None
                self._mismatch_count = 0
            elif self._state != SyncState.MISMATCH_WARNING:
                self._state = SyncState.MISMATCH_WARNING

            return events

        if held_missing:
            # Still waiting out the hold. Not an anomaly yet, but definitely not a clean
            # frame either: falling through to 4e would acknowledge the versioned expected
            # board while a stone the game believes in is not visible.
            self._mismatch_board = None
            self._mismatch_count = 0
            return events

        # 4e. No anomalies — exact matches and placement-pending-only frames are
        # both legacy-SYNCED, but only exact physical equality acknowledges a
        # versioned expected-board command.
        self._mismatch_board = None
        self._mismatch_count = 0
        was_synced = self._state == SyncState.SYNCED
        self._state = SyncState.SYNCED
        synced_event: SyncEvent | None = None

        if diff_count == 0:
            self._prev_expected_board = self._expected_board.copy()
            if self._pending_expected_node_id is not None:
                synced_event = SyncEvent(
                    SyncEventType.SYNCED,
                    data={"expected_node_id": self._pending_expected_node_id},
                )
                self._pending_expected_node_id = None

        if synced_event is None and not was_synced:
            synced_event = SyncEvent(SyncEventType.SYNCED)
        if synced_event is not None:
            events.append(synced_event)

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
