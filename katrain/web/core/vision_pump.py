"""Single-consumer fan-out for vision worker events.

The worker event queue is DESTRUCTIVE (each event can be read once). Exactly ONE
pump task drains it and routes by type:
  - dict events (sync/setup/monitor move_confirmed) -> broadcast to every /ws/vision
    client via its per-connection asyncio.Queue (each WS handler owns its socket writes);
  - ConfirmedMove dataclasses (bound game path) -> app-level move queue consumed by
    _vision_move_poller. Dropped when no session is bound (stale moves must not leak
    into a later bind).
Nothing else may call VisionService.poll_events().
"""

from __future__ import annotations

import asyncio
from typing import Iterable

from katrain.vision.ipc import ConfirmedMove
from katrain.vision.sync import game_state_stones_to_board


def is_stale_illegal_change(evt: dict, game_state: dict | None) -> bool:
    """Discard a worker mismatch if every reported extra is already in the game.

    The game can commit a camera-confirmed stone before the worker consumes its
    new expected board. A mismatch calculated against the old board may then
    arrive late. Only an exact match with the authoritative board is stale;
    missing stones and different colours remain actionable.
    """
    if evt.get("type") != "illegal_change" or not game_state:
        return False
    data = evt.get("data") or {}
    positions = data.get("positions") or []
    if not positions or data.get("missing"):
        return False
    try:
        board_size = int(game_state["board_size"][0])
        board = game_state_stones_to_board(game_state["stones"], board_size)
        return all(
            0 <= int(row) < board_size
            and 0 <= int(col) < board_size
            and int(board[int(row), int(col)]) == int(color)
            for row, col, color in positions
        )
    except (KeyError, IndexError, TypeError, ValueError):
        return False


def route_vision_event(
    evt,
    client_queues: Iterable[asyncio.Queue],
    move_queue: asyncio.Queue,
    bound: bool,
) -> None:
    if isinstance(evt, ConfirmedMove):
        if bound:
            move_queue.put_nowait(evt)
        return
    if isinstance(evt, dict):
        for q in client_queues:
            q.put_nowait(evt)


def route_vision_attention(evt, orchestrator, *, bound: bool) -> None:
    """Route authoritative mismatch points to the physical LED owner.

    Sync payloads already use the vision/LED grid: row 0 is the top edge.
    """
    if not bound or orchestrator is None or not isinstance(evt, dict):
        return
    if evt.get("type") == "illegal_change":
        data = evt.get("data") or {}
        points = [(int(row), int(col)) for row, col, *_ in data.get("positions", []) + data.get("missing", [])]
        if points:
            orchestrator.show_attention(points, source="vision")
    elif evt.get("type") == "synced":
        orchestrator.clear_attention("vision")
