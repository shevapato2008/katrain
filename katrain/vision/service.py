"""Vision service — main-process controller for the vision worker.

This is a thin proxy that manages the worker lifecycle, relays commands,
and polls for events/moves. It does NOT run inference directly.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, replace
from threading import RLock
from typing import Any, Callable

import numpy as np

from katrain.vision.config_service import VisionServiceConfig
from katrain.vision.ipc import (
    CommandType,
    ConfirmedMove,
    LocalWindowObservation,
    ReferenceTargetKey,
    WorkerCommand,
    WorkerStatus,
)
from katrain.vision.sync import game_state_stones_to_board

logger = logging.getLogger(__name__)


def binding_game_identity(session):
    if getattr(session, "game_type", None) == "pvp_lobby":
        state = getattr(session, "last_state", None) or {}
        return ("room", state.get("game_id"), state.get("central_session_id"))
    game = getattr(session.katrain, "game", None)
    return ("local", game if game is not None else session.katrain)


@dataclass(frozen=True)
class VisionBindingSource:
    session_id: str
    session: Any
    game_identity: tuple
    binding_epoch: int


@dataclass
class ExpectedRecovery:
    source: VisionBindingSource
    recovery_id: str
    loop: Any
    wake: asyncio.Event
    ack: tuple | None = None  # binding epoch, expected revision, expected node
    invalidated: bool = False


class VisionService:
    """Main-process controller for the vision worker."""

    def __init__(
        self,
        config: VisionServiceConfig,
        frame_source=None,
        *,
        recovery_gate=None,
        lighting_owner=None,
        lighting_disabled=False,
    ):
        self._config = config
        self._frame_source = frame_source
        self._lighting_owner = lighting_owner
        self._lighting_disabled = lighting_disabled
        self._worker_generation = uuid.uuid4().hex
        self._source_nonce = uuid.uuid4().hex
        self._bound_worker = None
        self._bound_mode = None
        self._reference_candidate_enabled = False
        self._reference_target: ReferenceTargetKey | None = None
        self._previous_reference_target: ReferenceTargetKey | None = None
        self._worker = None  # VisionWorkerProcess | InProcessAdapter
        self._game_over = False
        self._bound_event_game_id = None
        self._bound_session_id: str | None = None
        self._bound_session = None
        self._bound_game_identity = None
        self._binding_epoch = 0
        self._expected_revision = 0
        self._published_expected = None
        self._expected_recovery: ExpectedRecovery | None = None
        self._metadata_lock = RLock()
        self._event_callbacks: list[Callable] = []
        self._latest_status: WorkerStatus = WorkerStatus()
        self._pending_events: deque = deque()
        self._pending_moves: deque = deque()
        self._pending_local_observations: deque = deque(maxlen=1)
        self._local_confirmation_mode = False
        self._local_confirmation_session_id: str | None = None
        self._local_confirmation_game_id: str | None = None
        self._local_mode_generation = 0
        self._local_window_token: str | None = None
        self._local_window_source: tuple[VisionBindingSource, str, str] | None = None
        self._local_window_deadline = 0.0
        self.recovery_gate = recovery_gate
        self._usb_requested = False
        self._usb_recovery_callback = None

    @property
    def usb_business_blocked(self) -> bool:
        return self._usb_requested or bool(self.recovery_gate is not None and self.recovery_gate.active)

    def set_usb_recovery_callback(self, callback) -> None:
        """Install the board loop's bounded WS queue retirement callback."""
        self._usb_recovery_callback = callback

    def begin_usb_recovery(self, timeout=2.0) -> bool:
        begin = getattr(self._worker, "begin_usb_recovery", None)
        if not callable(begin):
            return False
        started = time.monotonic()
        with self._metadata_lock:
            self._usb_requested = True
        acknowledged = False
        try:
            if begin(timeout=timeout) is not True:
                return False
            with self._metadata_lock:
                self._pending_moves.clear()
                self._pending_events.clear()
                self._pending_local_observations.clear()
                self._local_window_token = None
                self._local_window_source = None
            if self._usb_recovery_callback is not None:
                remaining = max(0.0, timeout - (time.monotonic() - started))
                if self._usb_recovery_callback(remaining) is not True:
                    return False
            acknowledged = True
            return True
        except Exception:
            logger.exception("Vision USB quiescence could not be acknowledged")
            return False
        finally:
            if not acknowledged:
                self.end_usb_recovery()

    def end_usb_recovery(self) -> None:
        end = getattr(self._worker, "end_usb_recovery", None)
        try:
            if callable(end):
                end()
        finally:
            self._usb_requested = False

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        """Spawn the vision worker (subprocess or in-process thread)."""
        worker_config = self._config.to_worker_config()
        with self._metadata_lock:
            self._worker_generation = uuid.uuid4().hex
            self._source_nonce = uuid.uuid4().hex
            self._reference_target = self._previous_reference_target = None

        if self._config.process_mode == "inprocess" or self._frame_source is not None:
            from katrain.vision.worker_inprocess import InProcessAdapter

            self._worker = InProcessAdapter(
                worker_config,
                camera=self._frame_source,
                lighting_owner=self._lighting_owner,
                lighting_disabled=self._lighting_disabled,
            )
        else:
            from katrain.vision.worker import VisionWorkerProcess

            self._worker = VisionWorkerProcess(worker_config)

        self._worker.start()
        logger.info("VisionService started (mode=%s)", self._config.process_mode)

    def stop(self) -> None:
        """Stop the vision worker."""
        with self._metadata_lock:
            self._invalidate_expected_recovery()
        if self._worker:
            self._worker.stop()
            self._worker = None
        self._local_confirmation_mode = False
        self._local_window_token = None
        self._local_window_source = None
        self._pending_local_observations.clear()
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
        if self.usb_business_blocked:
            self._latest_status = replace(self._latest_status, recognition_ready=False, local_confirmation_ready=False)

    @property
    def last_motion_at(self) -> float | None:
        """Latest camera motion, also available while move detection is paused."""
        self.refresh_status()
        return self._latest_status.last_motion_at

    # -- commands ------------------------------------------------------------

    def confirm_pose_lock(self) -> bool:
        """Send confirm pose lock command to worker."""
        if not self._worker:
            return False
        self._worker.send_command(WorkerCommand(action=CommandType.CONFIRM_POSE_LOCK))
        return True

    @property
    def binding_epoch(self) -> int:
        return self._binding_epoch

    @property
    def expected_revision(self) -> int:
        return self._expected_revision

    def capture_binding_source(self, session_id: str, session) -> VisionBindingSource:
        identity = binding_game_identity(session)
        with self._metadata_lock:
            if session_id == self._bound_session_id and session is self._bound_session:
                identity = self._bound_game_identity
            return VisionBindingSource(session_id, session, identity, self._binding_epoch)

    def _binding_mode(self, session):
        katrain = getattr(session, "katrain", None)
        return (
            getattr(session, "game_type", "free"),
            getattr(katrain, "game_type", "free"),
            self._local_confirmation_mode,
            self._reference_candidate_enabled,
        )

    def _source_is_current_locked(self, source, identity) -> bool:
        return (
            source.binding_epoch == self._binding_epoch
            and source.session_id == self._bound_session_id
            and (self._bound_session is None or source.session is self._bound_session)
            and source.game_identity == self._bound_game_identity == identity
            and self._bound_worker is self._worker
            and self._bound_mode == self._binding_mode(source.session)
        )

    def source_is_current(self, source: VisionBindingSource) -> bool:
        identity = binding_game_identity(source.session)
        with self._metadata_lock:
            return self._source_is_current_locked(source, identity)

    @staticmethod
    def _wake_expected_recovery(recovery: ExpectedRecovery) -> None:
        if not recovery.loop.is_closed():
            try:
                recovery.loop.call_soon_threadsafe(recovery.wake.set)
            except RuntimeError:
                # The request's loop may close between the check and a worker-thread wake.
                pass

    def _invalidate_expected_recovery(self) -> None:
        recovery = self._expected_recovery
        self._expected_recovery = None
        if recovery is not None:
            recovery.invalidated = True
            self._wake_expected_recovery(recovery)

    def begin_expected_recovery(self, source: VisionBindingSource) -> ExpectedRecovery:
        """Register before publishing; callers already hold the authority commit lock."""
        with self._metadata_lock:
            if self._expected_recovery is not None:
                raise ValueError("A vision recovery is already active")
            recovery = ExpectedRecovery(source, uuid.uuid4().hex, asyncio.get_running_loop(), asyncio.Event())
            self._expected_recovery = recovery
            return recovery

    def finish_expected_recovery(self, recovery: ExpectedRecovery) -> None:
        with self._metadata_lock:
            if self._expected_recovery is recovery:
                self._expected_recovery = None

    def recovery_acknowledged(self, recovery: ExpectedRecovery, expected_node_id) -> bool:
        with self._metadata_lock:
            return (
                self._expected_recovery is recovery
                and not recovery.invalidated
                and recovery.ack == (self._binding_epoch, self._expected_revision, expected_node_id)
            )

    def publish_expected_from_stones(
        self, source: VisionBindingSource, stones, board_size=19, *, expected_node_id=None, force_rearm=False
    ) -> bool:
        # Callers hold the game's commit lock from snapshot read until queue insertion.
        # This lock only protects service metadata: never acquire a game lock inside it.
        board = game_state_stones_to_board(stones, board_size)
        identity = binding_game_identity(source.session)
        with self._metadata_lock:
            if not self._source_is_current_locked(source, identity):
                return False
            return self._publish_expected_locked(source, board, expected_node_id, force_rearm=force_rearm)

    def _publish_expected_locked(self, source, board, expected_node_id, *, force_rearm=False) -> bool:
        board = np.asarray(board, dtype=np.int8, order="C")
        key = (expected_node_id, board.shape, board.tobytes())
        changed = key != self._published_expected
        if not changed and not force_rearm:
            return False
        if changed:
            self._expected_revision += 1
            self._published_expected = key
            self._previous_reference_target = self._reference_target
            self._reference_target = ReferenceTargetKey(
                self._source_nonce,
                self._worker_generation,
                source.binding_epoch,
                self._expected_revision,
                expected_node_id,
                hashlib.sha256(board.tobytes()).hexdigest(),
            )
        recovery = self._expected_recovery
        recovery_data = {}
        if recovery is not None and recovery.source == source:
            recovery_data["recovery_id"] = recovery.recovery_id
            self._wake_expected_recovery(recovery)
        if force_rearm:
            recovery_data["force_rearm"] = True
        if self._worker:
            self._worker.send_command(
                WorkerCommand(
                    CommandType.SET_EXPECTED_BOARD,
                    {
                        "board": board.tolist(),
                        "expected_node_id": expected_node_id,
                        "binding_epoch": source.binding_epoch,
                        "expected_revision": self._expected_revision,
                        "source_nonce": self._source_nonce,
                        "worker_generation": self._worker_generation,
                        "mode_generation": self._local_mode_generation,
                        "board_digest": self._reference_target.board_digest,
                        **recovery_data,
                    },
                )
            )
        return changed

    def capture_reference_baseline(self, source: VisionBindingSource, move: ConfirmedMove) -> ReferenceTargetKey | None:
        identity = binding_game_identity(source.session)
        with self._metadata_lock:
            target = self._reference_target
            if (
                self._source_is_current_locked(source, identity)
                and target is not None
                and (move.binding_epoch, move.expected_revision) == (target.binding_epoch, target.expected_revision)
            ):
                return target
            return None

    def publish_accepted_reference(
        self,
        source: VisionBindingSource,
        move: ConfirmedMove,
        baseline: ReferenceTargetKey,
        accepted_node_id,
        accepted_parent_node_id,
        accepted_board,
    ) -> bool:
        """Queue the real commit before callbacks can publish a later AI position.

        Caller holds the game commit lock; the metadata lock preserves SET→ACCEPT FIFO.
        Only the current target or its immediately preceding baseline may participate.
        """
        board = np.array(accepted_board, dtype=np.int8, order="C", copy=True)
        if board.shape != (19, 19) or not np.isin(board, (0, 1, 2)).all():
            return False
        identity = binding_game_identity(source.session)
        with self._metadata_lock:
            target = self._reference_target
            if (
                baseline is None
                or not self._worker
                or not self._source_is_current_locked(source, identity)
                or (move.binding_epoch, move.expected_revision) != (baseline.binding_epoch, baseline.expected_revision)
                or baseline.source_nonce != self._source_nonce
                or baseline.worker_generation != self._worker_generation
                or baseline.expected_node_id != accepted_parent_node_id
            ):
                return False
            accepted_key = (accepted_node_id, board.shape, board.tobytes())
            already_published = accepted_key == self._published_expected
            if baseline != target and not (already_published and baseline == self._previous_reference_target):
                return False
            self._publish_expected_locked(source, board, accepted_node_id)
            self._worker.send_command(
                WorkerCommand(
                    CommandType.ACCEPT_REFERENCE_CANDIDATE,
                    {
                        "move_token": move.token,
                        "baseline_target": baseline,
                        "accepted_target": self._reference_target,
                        "accepted_parent_node_id": accepted_parent_node_id,
                        "accepted_board": board.tolist(),
                    },
                )
            )
            return True

    def invalidate_replaced_game(self, source: VisionBindingSource) -> int | None:
        """Retire only the binding whose anchored game was actually replaced."""
        identity = binding_game_identity(source.session)
        with self._metadata_lock:
            if (
                source.binding_epoch != self._binding_epoch
                or source.session_id != self._bound_session_id
                or source.session is not self._bound_session
                or source.game_identity != self._bound_game_identity
                or identity == self._bound_game_identity
            ):
                return None
            self.unbind_session()
            return self._binding_epoch

    def release_confirmed_move(self, move: ConfirmedMove) -> None:
        # Token only. In particular this cannot clear platform pending or write expected.
        with self._metadata_lock:
            if move.binding_epoch and move.binding_epoch != self._binding_epoch:
                return
            if self._worker:
                self._worker.send_command(WorkerCommand(CommandType.RELEASE_CONFIRMED_MOVE, {"token": move.token}))

    def set_expected_board(self, board: np.ndarray, *, expected_node_id: int | None = None) -> None:
        """Update expected board for sync comparison."""
        if self._bound_session is not None:
            return
        if self._worker:
            data = {"board": board.tolist()}
            if expected_node_id is not None:
                data["expected_node_id"] = expected_node_id
            self._worker.send_command(WorkerCommand(action=CommandType.SET_EXPECTED_BOARD, data=data))

    def set_expected_from_stones(
        self, stones: list[list], board_size: int = 19, *, expected_node_id: int | None = None
    ) -> None:
        """Convert GameState.stones to board matrix and set as expected."""
        board = game_state_stones_to_board(stones, board_size)
        self.set_expected_board(board, expected_node_id=expected_node_id)

    def enter_setup_mode(self, target_board: np.ndarray, setup_id: str | None = None) -> None:
        """Enter tsumego setup mode with target position."""
        if self._worker:
            self._worker.send_command(
                WorkerCommand(
                    action=CommandType.ENTER_SETUP_MODE,
                    data={
                        "target_board": target_board.tolist(),
                        **({"setup_id": setup_id} if setup_id is not None else {}),
                    },
                )
            )

    def reset_sync(self, expected: np.ndarray | None = None) -> None:
        """Reset sync. With `expected` (digital board) = trust-digital recovery: sync
        re-baselines to the digital board and the move detector to the digital∪physical
        UNION (so a still-present leftover / glare-washed stone doesn't re-fire as a move).
        Without it = legacy physical-adopt (ambiguous-ignore / research reset)."""
        if self._worker:
            data = {"expected": expected.tolist()} if expected is not None else None
            self._worker.send_command(WorkerCommand(action=CommandType.RESET_SYNC, data=data))

    def deny_stone(self, row: int, col: int) -> None:
        """用户在疑似落子弹窗上按了「不是落子」。

        存下那一格**此刻**的像素当作否认样本:只要它还长成那样,这一格就不再被当成子。
        与旧的「忽略」(adopt='physical')相反 —— 那条路把假阳性收进基线当成现实,还顺手
        销毁了参考帧;这条只记下用户说的那句「这儿没有子」,并且在像素变了的那一刻自动失效。
        """
        if self._worker:
            self._worker.send_command(WorkerCommand(action=CommandType.DENY_STONE, data={"row": row, "col": col}))

    def bind_session(self, session_id: str, *, session=None, reference_candidate_enabled=False) -> None:
        """Bind vision to a game session.

        Clears any pending ConfirmedMove left over from BEFORE this bind (review
        M1): a stale camera confirmation for whatever was bound previously (or
        never unbound, e.g. a server-restart edge case) must never be injected
        into the newly-bound session's game."""
        identity = binding_game_identity(session) if session is not None else None
        if (
            self._local_confirmation_mode
            and session_id == self._bound_session_id
            and session is self._bound_session
            and identity == self._bound_game_identity
            and self._worker is self._bound_worker
            and self._binding_mode(session) == self._bound_mode
            and self._reference_candidate_enabled is (reference_candidate_enabled is True)
        ):
            return
        with self._metadata_lock:
            self._reference_candidate_enabled = reference_candidate_enabled is True
            mode = self._binding_mode(session)
            preserve = (
                session_id == self._bound_session_id
                and session is self._bound_session
                and identity == self._bound_game_identity
                and mode == self._bound_mode
                and self._worker is self._bound_worker
            )
            if not preserve:
                self._source_nonce = uuid.uuid4().hex
            self._bound_worker = self._worker
            self._bound_mode = mode
            self._invalidate_expected_recovery()
            self._binding_epoch += 1
            self._expected_revision = 0
            self._published_expected = None
            self._reference_target = self._previous_reference_target = None
            self._game_over = False
            game = getattr(getattr(session, "katrain", None), "game", None)
            self._bound_event_game_id = (
                (getattr(session, "last_state", None) or {}).get("game_id")
                if getattr(session, "game_type", None) == "pvp_lobby"
                else getattr(game, "game_id", None)
            )
            self._bound_session_id = session_id
            self._bound_session = session
            self._bound_game_identity = identity
            self._pending_moves.clear()
            self._pending_events.clear()
            self._pending_local_observations.clear()
            if self._worker:
                self._worker.send_command(
                    WorkerCommand(
                        CommandType.BIND,
                        {
                            "binding_epoch": self._binding_epoch,
                            "source_nonce": self._source_nonce,
                            "worker_generation": self._worker_generation,
                            "mode_generation": self._local_mode_generation,
                            "preserve_reference": preserve,
                            "reference_candidate_enabled": self._reference_candidate_enabled
                            and not self._local_confirmation_mode,
                        },
                    )
                )

    def unbind_session(self) -> None:
        """Unbind from current session. Clears pending ConfirmedMove (review M1) so
        a move confirmed just before unbind can't leak into whatever session binds
        next."""
        with self._metadata_lock:
            self._invalidate_expected_recovery()
            self._binding_epoch += 1
            self._expected_revision = 0
            self._published_expected = None
            self._source_nonce = uuid.uuid4().hex
            self._reference_target = self._previous_reference_target = None
            self._bound_worker = self._bound_mode = None
            self._reference_candidate_enabled = False
            self._game_over = False
            self._bound_event_game_id = None
            self._bound_session_id = None
            self._bound_session = None
            self._bound_game_identity = None
        self._pending_moves.clear()
        self._pending_events.clear()
        self._pending_local_observations.clear()
        self._local_confirmation_mode = False
        self._local_confirmation_session_id = None
        self._local_confirmation_game_id = None
        self._local_window_token = None
        self._local_window_source = None
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

    @property
    def supports_local_confirmation(self) -> bool:
        return getattr(self._worker, "supports_local_confirmation", False) is True

    @property
    def local_confirmation_frames(self) -> int:
        return max(1, int(self._config.move_confirm_frames))

    @property
    def local_confirmation_ready(self) -> bool:
        if self.usb_business_blocked or not self.supports_local_confirmation:
            return False
        self.refresh_status()
        return bool(
            self.supports_local_confirmation
            and self._local_confirmation_mode
            and self._latest_status.local_confirmation_session_id == self._local_confirmation_session_id
            and self._latest_status.local_confirmation_game_id == self._local_confirmation_game_id
            and self._latest_status.local_confirmation_mode_generation == self._local_mode_generation
            and self._latest_status.local_confirmation_ready
        )

    @property
    def local_confirmation_bootstrap_state(self) -> str:
        self.refresh_status()
        if self._latest_status.local_confirmation_mode_generation != self._local_mode_generation:
            return "bootstrap" if self._local_confirmation_mode else "idle"
        return self._latest_status.local_confirmation_bootstrap_state

    def set_local_confirmation_mode(
        self, enabled: bool, *, session_id: str | None = None, game_id: str | None = None
    ) -> bool:
        with self._metadata_lock:
            if not self.supports_local_confirmation:
                return False
            if (enabled, session_id, game_id) == (
                self._local_confirmation_mode,
                self._local_confirmation_session_id,
                self._local_confirmation_game_id,
            ):
                return True
            session = self._bound_session
            katrain = getattr(session, "katrain", None)
            game = getattr(katrain, "game", None)
            if (
                enabled is True
                and self._lighting_owner is not None
                and not self._lighting_disabled
                and session is not None
                and session_id == self._bound_session_id
                and self._worker is self._bound_worker
                and self._bound_mode == self._binding_mode(session)
                and binding_game_identity(session) == self._bound_game_identity
                and getattr(katrain, "game_type", None) == "pvp_local"
                and game is not None
                and getattr(game, "game_id", None) == game_id
            ):
                # Startup's handshake has no reference receipt. Let an ordinary
                # queued dark SHOW establish one before local bootstrap starts.
                try:
                    self._lighting_owner.clear(strict=False)
                except Exception:
                    logger.warning("local confirmation bootstrap LED clear failed", exc_info=True)
            mode_changed = (
                self._bound_mode != self._binding_mode(self._bound_session)
                or enabled != self._local_confirmation_mode
                or (
                    enabled
                    and (
                        session_id != self._local_confirmation_session_id or game_id != self._local_confirmation_game_id
                    )
                )
            )
            if mode_changed:
                self._source_nonce = uuid.uuid4().hex
                self._reference_target = self._previous_reference_target = None
                self._published_expected = None
            self._local_mode_generation += 1
            self._local_confirmation_mode = enabled
            self._local_confirmation_session_id = session_id
            self._local_confirmation_game_id = game_id
            self._bound_mode = self._binding_mode(self._bound_session)
            self._local_window_token = None
            self._local_window_source = None
            self._pending_local_observations.clear()
            self._pending_moves.clear()
            self._worker.send_command(
                WorkerCommand(
                    action=CommandType.SET_LOCAL_CONFIRMATION_MODE,
                    data={
                        "enabled": enabled,
                        "session_id": session_id,
                        "game_id": game_id,
                        "mode_generation": self._local_mode_generation,
                        "source_nonce": self._source_nonce,
                        "worker_generation": self._worker_generation,
                        "reference_candidate_enabled": self._reference_candidate_enabled and not enabled,
                    },
                )
            )
            return True

    def open_local_window(
        self,
        token: str,
        expected_board: np.ndarray,
        *,
        expected_node_id: int | None,
        expected_color: int,
        deadline_monotonic: float,
    ) -> bool:
        with self._metadata_lock:
            opened = time.monotonic()
            if self.usb_business_blocked or not self.local_confirmation_ready or deadline_monotonic <= opened:
                return False
            self._local_window_token = token
            self._local_window_source = None
            if self._bound_session is not None:
                source = self.capture_binding_source(self._bound_session_id, self._bound_session)
                if self._source_is_current_locked(source, binding_game_identity(source.session)):
                    self._local_window_source = (source, self._source_nonce, self._worker_generation)
            self._local_window_deadline = deadline_monotonic
            self._pending_local_observations.clear()
            self._worker.send_command(
                WorkerCommand(
                    action=CommandType.OPEN_LOCAL_WINDOW,
                    data={
                        "token": token,
                        "expected_board": expected_board.tolist(),
                        "expected_node_id": expected_node_id,
                        "expected_color": expected_color,
                        "opened_monotonic": opened,
                        "deadline_monotonic": deadline_monotonic,
                    },
                )
            )
            return True

    def cancel_local_window(self, token: str) -> bool:
        if not self.supports_local_confirmation or token != self._local_window_token:
            return False
        self._local_window_token = None
        self._local_window_source = None
        self._pending_local_observations.clear()
        self._worker.send_command(WorkerCommand(action=CommandType.CANCEL_LOCAL_WINDOW, data={"token": token}))
        return True

    def complete_local_window(self, token: str, accepted_board: np.ndarray, *, expected_node_id: int | None) -> bool:
        """Publish the controller's true accepted board, then finish its scoped window.

        The local controller holds session.lock and the actual game's commit lock
        from its successful commit through this call. Never reread later game state.
        """
        board = np.array(accepted_board, dtype=np.int8, order="C", copy=True)
        with self._metadata_lock:
            scope = self._local_window_source
            if (
                not self.supports_local_confirmation
                or not self._local_confirmation_mode
                or token != self._local_window_token
                or scope is None
            ):
                return False
            source, source_nonce, worker_generation = scope
            if (
                source_nonce != self._source_nonce
                or worker_generation != self._worker_generation
                or not self._source_is_current_locked(source, binding_game_identity(source.session))
            ):
                return False
            self._publish_expected_locked(source, board, expected_node_id)
            self._worker.send_command(
                WorkerCommand(
                    action=CommandType.COMPLETE_LOCAL_WINDOW,
                    data={
                        "token": token,
                        "accepted_board": board.tolist(),
                        "expected_node_id": expected_node_id,
                        "accepted_target": self._reference_target,
                        "source_nonce": self._source_nonce,
                        "worker_generation": self._worker_generation,
                    },
                )
            )
            self._local_window_token = None
            self._local_window_source = None
            self._pending_local_observations.clear()
            return True

    def set_move_armed(self, armed: bool) -> None:
        """Arm/disarm monitor-mode move detection (frontend arms only in the 'ready' phase)."""
        if self._worker:
            self._worker.send_command(WorkerCommand(action=CommandType.SET_MOVE_ARMED, data={"armed": armed}))

    def set_game_over(self, ended: bool, *, source=None) -> None:
        """Retire only this binding's processing demand, not the shared camera."""
        with self._metadata_lock:
            if source is not None and not self._source_is_current_locked(source, binding_game_identity(source.session)):
                return
            if self._game_over == bool(ended):
                return
            if self._game_over:
                # Discard late worker output before reopening this binding (legacy undo).
                self._drain_worker()
            self._game_over = bool(ended)
            self._pending_moves.clear()
            self._pending_events.clear()
            self._pending_local_observations.clear()
            self._local_window_token = self._local_window_source = None
            if self._worker:
                self._worker.send_command(
                    WorkerCommand(
                        CommandType.SET_GAME_OVER, {"ended": bool(ended), "binding_epoch": self._binding_epoch}
                    )
                )

    def needs_frames(self) -> bool:
        """此刻有没有人要看棋盘(实体对局 / 监视 / 摆棋准备 / 识别预览)。子进程沿最新需帧状态，尚未上报时保守答「要」。"""
        needs = getattr(self._worker, "needs_frames", None)
        if callable(needs):
            return bool(needs())
        self.refresh_status()
        demand = self._latest_status.frame_demand
        return bool(demand) if demand is not None else self._worker is not None

    def set_viewer_active(self, active: bool) -> None:
        """Tell worker whether MJPEG viewers are connected."""
        if self._worker:
            self._worker.send_command(WorkerCommand(action=CommandType.SET_VIEWER_ACTIVE, data={"active": active}))

    def set_geometry(self, geometry) -> None:
        if self._worker:
            self._worker.send_command(WorkerCommand(action=CommandType.SET_GEOMETRY, data={"geometry": geometry}))

    def pause_detection(self) -> None:
        """Suspend the whole compare pipeline: move confirmation AND SyncStateMachine.

        ⚠️ This docstring used to claim SyncStateMachine.update keeps running while
        paused. It does not, and has not: `should_feed_sync(bound, monitor, paused)`
        (gating.py:34-35) returns False when paused, and both workers gate
        `self._sync.update()` on it — so capture_pending / illegal_change / move
        confirmation all stop together. Anyone reasoning from the old sentence would
        pick the wrong mechanism (PAUSE_REASON_GAME_OVER relies on the real one).

        Callers: LED hint display (PRD R4.3), and game-over (see
        PhysicalPlayOrchestrator.PAUSE_REASON_GAME_OVER). During an LED hint,
        lit-and-expected-empty intersections are additionally protected from feeding
        sync via set_lit_points() masking.
        """
        if self._worker:
            self._worker.send_command(WorkerCommand(action=CommandType.PAUSE_DETECTION))

    def resume_detection(self) -> None:
        if self._worker:
            self._worker.send_command(WorkerCommand(action=CommandType.RESUME_DETECTION))

    def set_lit_points(
        self, points: list[tuple[int, int]], *, mask_points: list[tuple[int, int]] | None = None
    ) -> None:
        """Report lit cells for glow measurement; mask only cells that cannot receive a new stone."""
        if self._worker:
            self._worker.send_command(
                WorkerCommand(
                    action=CommandType.SET_LIT_POINTS,
                    data={
                        "points": [[r, c] for r, c in points],
                        "mask_points": [[r, c] for r, c in (points if mask_points is None else mask_points)],
                    },
                )
            )

    # -- data retrieval ------------------------------------------------------

    def get_detected_board(self) -> list[list[int]] | None:
        """Return the latest detected board state (19x19 grid).

        Pulls fresh status first. The cached `_latest_status` is only refreshed by
        whoever last touched another status property, so it can be arbitrarily old.
        """
        if self.usb_business_blocked:
            return None
        self.refresh_status()
        return self._latest_status.detected_board

    def get_board_observation(self) -> tuple[list[list[int]] | None, int]:
        """The latest board reading together with the observation it came from.

        The sequence number is what makes a presence check sound: `worker.py` publishes
        status at 1 Hz, so "the newest board we have" can easily predate a move confirmed
        since. Callers must require a sequence strictly greater than the one stamped on
        the ConfirmedMove before treating an empty cell as a disappearance.
        """
        if self.usb_business_blocked:
            return None, 0
        self.refresh_status()
        return self._latest_status.detected_board, int(self._latest_status.observation_seq)

    def get_preview_jpeg(self) -> bytes | None:
        """Get latest JPEG preview frame from worker."""
        if self.usb_business_blocked:
            return None
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
            if self._game_over and (
                isinstance(evt, (ConfirmedMove, LocalWindowObservation))
                or (
                    isinstance(evt, dict)
                    and not evt.get("sessionless")
                    and evt.get("type")
                    in {"move_pending", "capture_pending", "illegal_change", "ambiguous_stone", "missing_stone"}
                )
            ):
                continue
            if isinstance(evt, LocalWindowObservation):
                if (
                    self._local_confirmation_mode
                    and evt.token == self._local_window_token
                    and evt.session_id == self._local_confirmation_session_id
                ):
                    self._pending_local_observations.append(evt)
            elif isinstance(evt, ConfirmedMove):
                if not self._local_confirmation_mode and (
                    not evt.binding_epoch
                    or (evt.binding_epoch == self._binding_epoch and evt.expected_revision == self._expected_revision)
                ):
                    self._pending_moves.append(evt)
            else:
                epoch = evt.get("binding_epoch", 0) if isinstance(evt, dict) else 0
                if epoch and epoch != self._binding_epoch:
                    continue
                if (
                    isinstance(evt, dict)
                    and self._bound_session_id
                    and not epoch
                    and not evt.get("sessionless")
                    and evt.get("type")
                    in {"move_pending", "capture_pending", "illegal_change", "ambiguous_stone", "missing_stone"}
                ):
                    continue
                if isinstance(evt, dict) and epoch and self._bound_session_id:
                    evt = {**evt, "session_id": self._bound_session_id, "game_id": self._bound_event_game_id}
                recovery = self._expected_recovery
                if recovery is not None and isinstance(evt, dict) and evt.get("type") == "synced":
                    data = evt.get("data") or {}
                    revision = evt.get("expected_revision")
                    if (
                        epoch == recovery.source.binding_epoch
                        and data.get("recovery_id") == recovery.recovery_id
                        and data.get("expected_node_id") is not None
                        and isinstance(revision, int)
                        and revision == self._expected_revision
                        and (recovery.ack is None or revision >= recovery.ack[1])
                    ):
                        recovery.ack = (epoch, revision, data["expected_node_id"])
                        self._wake_expected_recovery(recovery)
                if not epoch or epoch == self._binding_epoch:
                    self._pending_events.append(evt)

    def poll_events(self) -> list[Any]:
        """Read all pending dict events from worker (never consumes moves)."""
        with self._metadata_lock:
            if self.usb_business_blocked:
                return []
            self._drain_worker()
            events = list(self._pending_events)
            self._pending_events.clear()
            return events

    def get_confirmed_move(self) -> ConfirmedMove | None:
        """Read and consume the OLDEST pending confirmed move (FIFO — a stalled
        poller no longer silently drops intermediate moves)."""
        with self._metadata_lock:
            if self.usb_business_blocked:
                return None
            self._drain_worker()
            while self._pending_moves:
                move = self._pending_moves.popleft()
                if not move.binding_epoch or (
                    move.binding_epoch == self._binding_epoch and move.expected_revision == self._expected_revision
                ):
                    return move
            return None

    def get_local_window_observation(self, token: str | None = None) -> LocalWindowObservation | None:
        with self._metadata_lock:
            if self.usb_business_blocked:
                return None
            self._drain_worker()
            if token is not None and token != self._local_window_token:
                return None
            if time.monotonic() >= self._local_window_deadline:
                self._pending_local_observations.clear()
                return None
            if self._pending_local_observations:
                return self._pending_local_observations.pop()
            return None

    @property
    def is_alive(self) -> bool:
        return self._worker is not None and self._worker.is_alive
