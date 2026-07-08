"""Frame-feeding / move-detection gates + move-event routing, shared by both vision workers.

bound      = game-session BIND (对弈路径，行为保持不变)
monitor    = tsumego/physical monitor mode (无 session)
paused     = 提示白灯/试下期间挂起一切识别
move_armed = 前端相位显式 arm（仅"轮到用户落子"时 true——SYNCED 只是必要条件，
             清盘/摆放/应手完成后都会短暂 SYNCED，不能据此推断轮到用户）

Routing contract (LOCKED BY TESTS): bound moves -> ConfirmedMove dataclass consumed by
the game poller; monitor moves -> dict event fanned out over /ws/vision (Task 5 pump).
"""

from __future__ import annotations

from typing import Sequence

from katrain.vision.ipc import ConfirmedMove


def mean_detection_confidence(detections: Sequence) -> float:
    """Confidence of a board reading, shared by both vision workers.

    Zero detections on an already-located board (corners found) is a *confident
    empty* reading — return 1.0, NOT 0.0. Scoring empty as 0.0 makes an empty
    board (the tsumego "clear board" step) look permanently low-confidence, which
    slides SyncStateMachine into DEGRADED after ~10s; DEGRADED skips the setup
    check, so clearing never completes. Only genuine low-confidence *detections*
    should drive DEGRADED.
    """
    if not detections:
        return 1.0
    return sum(d.confidence for d in detections) / len(detections)


def should_feed_sync(bound: bool, monitor: bool, paused: bool) -> bool:
    return (bound or monitor) and not paused


def should_detect_moves(bound: bool, monitor: bool, paused: bool, move_armed: bool, sync_state: str) -> bool:
    if paused:
        return False
    if bound:
        return True
    # move_armed already means "轮到用户落子", so the MoveDetector (which only reacts to a stone
    # ADDED vs its setup baseline) is the authority. A placed stone flips sync synced ->
    # mismatch_warning, and a noisy reading (a real-board stone flickering as "missing") drops it
    # into capture_pending; gating strictly on "synced" starves the MoveDetector before it confirms
    # (the move then never fires — surfacing as illegal_change/capture_pending instead). Keep
    # detecting across those readable states; only board_lost/degraded/setup (unusable, or not the
    # user's turn) stay blocked.
    return monitor and move_armed and sync_state in ("synced", "mismatch_warning", "capture_pending")


def move_event(bound: bool, row: int, col: int, color: int):
    if bound:
        return ConfirmedMove(col=col, row=row, color=color)
    return {"type": "move_confirmed", "data": {"row": row, "col": col, "color": color}}
