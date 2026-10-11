"""IPC protocol between main process and vision worker.

Uses multiprocessing.Queue for commands (main→worker) and
multiprocessing.Queue for events (worker→main). Preview frames
are passed via a shared bytes buffer (overwrite semantics).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CommandType(Enum):
    """Commands sent from main process to vision worker."""

    SET_EXPECTED_BOARD = "set_expected_board"
    CONFIRM_POSE_LOCK = "confirm_pose_lock"
    RESET_SYNC = "reset_sync"
    ENTER_SETUP_MODE = "enter_setup_mode"
    BIND = "bind"
    UNBIND = "unbind"
    SET_VIEWER_ACTIVE = "set_viewer_active"
    SET_GEOMETRY = "set_geometry"
    SET_MONITOR = "set_monitor"
    SET_PAUSED = "set_paused"
    SET_MOVE_ARMED = "set_move_armed"
    SET_LOCAL_CONFIRMATION_MODE = "set_local_confirmation_mode"
    OPEN_LOCAL_WINDOW = "open_local_window"
    CANCEL_LOCAL_WINDOW = "cancel_local_window"
    COMPLETE_LOCAL_WINDOW = "complete_local_window"
    PAUSE_DETECTION = "pause_detection"
    RESUME_DETECTION = "resume_detection"
    SET_LIT_POINTS = "set_lit_points"
    DENY_STONE = "deny_stone"  # 用户在弹窗上按了「不是落子」
    SHUTDOWN = "shutdown"


@dataclass
class WorkerCommand:
    """Command sent by main process to worker."""

    action: CommandType
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkerStatus:
    """Periodically published by worker to main process."""

    camera_status: str = "disconnected"  # "disconnected" | "connected"
    pose_lock_status: str = "unlocked"  # "unlocked" | "locked"
    sync_state: str = "unbound"  # SyncState value
    mean_confidence: float = 0.0
    detected_board: list[list[int]] | None = None  # 19x19 grid (0=empty, 1=black, 2=white)
    camera_ready: bool = False
    geometry_ready: bool = False
    model_ready: bool = False
    recognition_ready: bool = False
    last_motion_at: float | None = None  # monotonic; lets hint lamps yield when a hand enters
    # Which board observation `detected_board` came from. Consumers compare it against a
    # ConfirmedMove's own observation_seq to tell "a genuinely newer look at the board"
    # from "the last thing this worker happened to publish" — worker.py publishes at 1 Hz,
    # so the newest published board can easily predate a move confirmed since.
    observation_seq: int = 0
    local_confirmation_mode: bool = False
    local_confirmation_session_id: str | None = None
    local_confirmation_game_id: str | None = None
    local_confirmation_mode_generation: int = 0
    local_confirmation_ready: bool = False
    local_confirmation_bootstrap_state: str = "idle"


@dataclass
class ConfirmedMove:
    """A confirmed move detected by the vision worker."""

    col: int
    row: int
    color: int  # BLACK=1, WHITE=2
    observation_seq: int = 0  # the observation this confirmation was made on


@dataclass
class LocalWindowObservation:
    """One complete postprocessed board, isolated from the automatic move consumer."""

    token: str
    board: list[list[int]]
    observation_seq: int
    camera_seq: int
    camera_ts: float
    candidate: ConfirmedMove | None = None
    pending: bool = False
    ambiguous_points: list[list[int]] = field(default_factory=list)
    session_id: str | None = None
