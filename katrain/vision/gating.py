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

from katrain.vision.ipc import ConfirmedMove


def should_feed_sync(bound: bool, monitor: bool, paused: bool) -> bool:
    return (bound or monitor) and not paused


def should_detect_moves(bound: bool, monitor: bool, paused: bool, move_armed: bool, sync_state: str) -> bool:
    if paused:
        return False
    if bound:
        return True
    return monitor and move_armed and sync_state == "synced"


def move_event(bound: bool, row: int, col: int, color: int):
    if bound:
        return ConfirmedMove(col=col, row=row, color=color)
    return {"type": "move_confirmed", "data": {"row": row, "col": col, "color": color}}
