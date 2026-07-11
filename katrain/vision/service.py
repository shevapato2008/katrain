"""Vision service — main-process controller for the vision worker.

This is a thin proxy that manages the worker lifecycle, relays commands,
and polls for events/moves. It does NOT run inference directly.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any, Callable

import numpy as np

from katrain.vision.config_service import VisionServiceConfig
from katrain.vision.ipc import CommandType, ConfirmedMove, WorkerCommand, WorkerStatus
from katrain.vision.sync import game_state_stones_to_board

logger = logging.getLogger(__name__)


class VisionService:
    """Main-process controller for the vision worker."""

    def __init__(self, config: VisionServiceConfig, frame_source=None):
        self._config = config
        self._frame_source = frame_source
        self._worker = None  # VisionWorkerProcess | InProcessAdapter
        self._bound_session_id: str | None = None
        self._event_callbacks: list[Callable] = []
        self._latest_status: WorkerStatus = WorkerStatus()
        self._pending_events: deque = deque()
        self._pending_moves: deque = deque()

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        """Spawn the vision worker (subprocess or in-process thread)."""
        worker_config = self._config.to_worker_config()

        if self._config.process_mode == "inprocess" or self._frame_source is not None:
            from katrain.vision.worker_inprocess import InProcessAdapter

            self._worker = InProcessAdapter(worker_config, camera=self._frame_source)
        else:
            from katrain.vision.worker import VisionWorkerProcess

            self._worker = VisionWorkerProcess(worker_config)

        self._worker.start()
        logger.info("VisionService started (mode=%s)", self._config.process_mode)

    def stop(self) -> None:
        """Stop the vision worker."""
        if self._worker:
            self._worker.stop()
            self._worker = None
        logger.info("VisionService stopped")

    # -- status --------------------------------------------------------------

    @property
    def camera_status(self) -> str:
        return self._latest_status.camera_status

    @property
    def pose_lock_status(self) -> str:
        return self._latest_status.pose_lock_status

    @property
    def sync_state(self) -> str:
        return self._latest_status.sync_state

    @property
    def bound_session_id(self) -> str | None:
        return self._bound_session_id

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def refresh_status(self) -> None:
        """Pull latest status from worker."""
        if self._worker:
            status = self._worker.get_status()
            if status is not None:
                self._latest_status = status

    # -- commands ------------------------------------------------------------

    def confirm_pose_lock(self) -> bool:
        """Send confirm pose lock command to worker."""
        if not self._worker:
            return False
        self._worker.send_command(WorkerCommand(action=CommandType.CONFIRM_POSE_LOCK))
        return True

    def set_expected_board(self, board: np.ndarray) -> None:
        """Update expected board for sync comparison."""
        if self._worker:
            self._worker.send_command(
                WorkerCommand(action=CommandType.SET_EXPECTED_BOARD, data={"board": board.tolist()})
            )

    def set_expected_from_stones(self, stones: list[list], board_size: int = 19) -> None:
        """Convert GameState.stones to board matrix and set as expected."""
        board = game_state_stones_to_board(stones, board_size)
        self.set_expected_board(board)

    def enter_setup_mode(self, target_board: np.ndarray) -> None:
        """Enter tsumego setup mode with target position."""
        if self._worker:
            self._worker.send_command(
                WorkerCommand(action=CommandType.ENTER_SETUP_MODE, data={"target_board": target_board.tolist()})
            )

    def reset_sync(self, expected: np.ndarray | None = None) -> None:
        """Reset sync. With `expected` (digital board) = trust-digital recovery: sync
        re-baselines to the digital board and the move detector to the digital∪physical
        UNION (so a still-present leftover / glare-washed stone doesn't re-fire as a move).
        Without it = legacy physical-adopt (ambiguous-ignore / research reset)."""
        if self._worker:
            data = {"expected": expected.tolist()} if expected is not None else None
            self._worker.send_command(WorkerCommand(action=CommandType.RESET_SYNC, data=data))

    def bind_session(self, session_id: str) -> None:
        """Bind vision to a game session.

        Clears any pending ConfirmedMove left over from BEFORE this bind (review
        M1): a stale camera confirmation for whatever was bound previously (or
        never unbound, e.g. a server-restart edge case) must never be injected
        into the newly-bound session's game."""
        self._bound_session_id = session_id
        self._pending_moves.clear()
        if self._worker:
            self._worker.send_command(WorkerCommand(action=CommandType.BIND))

    def unbind_session(self) -> None:
        """Unbind from current session. Clears pending ConfirmedMove (review M1) so
        a move confirmed just before unbind can't leak into whatever session binds
        next."""
        self._bound_session_id = None
        self._pending_moves.clear()
        if self._worker:
            self._worker.send_command(WorkerCommand(action=CommandType.UNBIND))

    def set_monitor(self, active: bool) -> None:
        """Enable/disable monitor mode (tsumego physical board — no game session)."""
        if self._worker:
            self._worker.send_command(WorkerCommand(action=CommandType.SET_MONITOR, data={"active": active}))

    def set_paused(self, paused: bool) -> None:
        """Pause/resume recognition (hint display, try mode). Single-owner aggregate bool."""
        if self._worker:
            self._worker.send_command(WorkerCommand(action=CommandType.SET_PAUSED, data={"paused": paused}))

    def set_move_armed(self, armed: bool) -> None:
        """Arm/disarm monitor-mode move detection (frontend arms only in the 'ready' phase)."""
        if self._worker:
            self._worker.send_command(WorkerCommand(action=CommandType.SET_MOVE_ARMED, data={"armed": armed}))

    def set_viewer_active(self, active: bool) -> None:
        """Tell worker whether MJPEG viewers are connected."""
        if self._worker:
            self._worker.send_command(WorkerCommand(action=CommandType.SET_VIEWER_ACTIVE, data={"active": active}))

    def set_geometry(self, geometry) -> None:
        if self._worker:
            self._worker.send_command(WorkerCommand(action=CommandType.SET_GEOMETRY, data={"geometry": geometry}))

    def pause_detection(self) -> None:
        """Suspend MoveDetector move confirmation only (hint display; PRD R4.3).

        Narrowed scope after review: SyncStateMachine.update keeps running while paused —
        capture_pending/illegal_change flows must stay live during a catch-up wait (guide
        stone removal, report anomalies). During an LED hint, lit-and-expected-empty
        intersections are protected from feeding sync via set_lit_points() masking instead.
        """
        if self._worker:
            self._worker.send_command(WorkerCommand(action=CommandType.PAUSE_DETECTION))

    def resume_detection(self) -> None:
        if self._worker:
            self._worker.send_command(WorkerCommand(action=CommandType.RESUME_DETECTION))

    def set_lit_points(self, points: list[tuple[int, int]]) -> None:
        """Intersections currently lit by the LED board (R7.1 masking)."""
        if self._worker:
            self._worker.send_command(
                WorkerCommand(action=CommandType.SET_LIT_POINTS, data={"points": [[r, c] for r, c in points]})
            )

    # -- data retrieval ------------------------------------------------------

    def get_detected_board(self) -> list[list[int]] | None:
        """Return the latest detected board state (19x19 grid)."""
        return self._latest_status.detected_board

    def get_preview_jpeg(self) -> bytes | None:
        """Get latest JPEG preview frame from worker."""
        if self._worker:
            return self._worker.get_preview_jpeg()
        return None

    def _drain_worker(self) -> None:
        """Single drain point: route ConfirmedMove and dict events to separate queues
        so the /ws/vision loop and the move poller no longer race on one queue."""
        if not self._worker:
            return
        while True:
            evt = self._worker.get_event()
            if evt is None:
                break
            if isinstance(evt, ConfirmedMove):
                self._pending_moves.append(evt)
            else:
                self._pending_events.append(evt)

    def poll_events(self) -> list[Any]:
        """Read all pending dict events from worker (never consumes moves)."""
        self._drain_worker()
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    def get_confirmed_move(self) -> ConfirmedMove | None:
        """Read and consume the OLDEST pending confirmed move (FIFO — a stalled
        poller no longer silently drops intermediate moves)."""
        self._drain_worker()
        if self._pending_moves:
            return self._pending_moves.popleft()
        return None

    @property
    def is_alive(self) -> bool:
        return self._worker is not None and self._worker.is_alive
