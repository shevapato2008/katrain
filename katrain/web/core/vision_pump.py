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
