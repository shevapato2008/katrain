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
