"""Engine-move failure recovery state machine (Task 7, review B5/M1/M4/m2).

Pure logic, no asyncio/I/O — fully unit-testable in isolation from the vision
poller. Consumed by `katrain/web/server.py`'s `_vision_move_poller` (via a small
extracted handler) to close gap G3: a camera-confirmed stone whose engine-tunnel
move keeps failing (genmove timeout, tunnel error, etc.) used to be re-armed and
retried forever while the physical stone sat on the board. This module tracks a
bounded-retry "episode" per (game_id, coords) and tells the caller when to stop
retrying and hand off to the physical-play orchestrator's `engine_error` pause
state + a `physical_engine_error` broadcast.

Reason -> behavior (the brief's transition table):
  engine_error / position_changed  -> counted; below threshold: re-arm; at
                                       threshold: stop re-arming, trip a
                                       recovery_token, caller enters engine_error.
  pending                          -> not counted, episode untouched, re-arm.
  illegal_move                     -> not counted, episode untouched, re-arm
                                       (physical mismatch flow handles this, not
                                       the tunnel).
  game_ended                       -> episode cleared, do NOT re-arm.
  anything else (e.g. the plain-platform default "move_rejected")
                                    -> passthrough, same as pending/illegal_move.
Episode semantics (review m2): the episode key is (game_id, coords) — a coordinate
or game_id change starts a fresh episode (the old one is simply discarded, not
"failed"); success/game_ended/session-missing/unbind all clear the episode.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional, Tuple

Coords = Tuple[int, int]
EpisodeKey = Tuple[str, Coords]

# Reasons that increment the episode's failure count and can trip the threshold.
COUNTED_REASONS = frozenset({"engine_error", "position_changed"})
# Reasons that clear the episode outright and tell the caller NOT to re-arm
# (the game is over; lamps clear via the terminal game_update, not a retry).
TERMINAL_REASONS = frozenset({"game_ended"})
# Everything else (pending, illegal_move, the plain-platform default
# "move_rejected", and any future/unrecognized reason) passes through: not
# counted, episode untouched, caller re-arms -- this is the pre-Task-7 behavior,
# preserved for reasons this task's episode/threshold machinery doesn't own.


@dataclass
class EngineRecoveryConfig:
    """Minimal, standalone config (review m1: NOT a PhysicalPlayConfig field —
    this is poller/retry policy, not LED planning)."""

    engine_move_max_attempts: int = 3


@dataclass
class RecoveryEpisode:
    """At most one ACTIVE episode per tracker (== per bound session, since the
    kiosk vision service binds a single session at a time)."""

    episode_key: EpisodeKey
    game_id: str
    coords: Coords
    count: int = 0
    detail: str = ""
    recovery_token: Optional[str] = None


@dataclass
class Outcome:
    """What the caller (the poller) should do after classifying one failure."""

    rearm: bool
    episode: Optional[RecoveryEpisode]
    enter_engine_error: bool = False  # True exactly once, at the threshold crossing


class EngineRecoveryTracker:
    """Owns the single active `RecoveryEpisode`, if any. `token_factory` is
    injectable for deterministic tests; defaults to `uuid.uuid4()` (fine for
    runtime state -- this is not workflow-replay code, per the brief)."""

    def __init__(
        self,
        config: Optional[EngineRecoveryConfig] = None,
        token_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
    ):
        self.config = config or EngineRecoveryConfig()
        self._token_factory = token_factory
        self._episode: Optional[RecoveryEpisode] = None

    @property
    def active_episode(self) -> Optional[RecoveryEpisode]:
        return self._episode

    def clear(self) -> None:
        """Drop the active episode unconditionally: success, game session missing,
        unbind, or session end all route here."""
        self._episode = None

    def on_success(self) -> None:
        self.clear()

    def on_failure(self, *, game_id: str, coords: Coords, reason: str, detail: str = "") -> Outcome:
        key: EpisodeKey = (game_id, coords)

        if reason in TERMINAL_REASONS:
            self.clear()
            return Outcome(rearm=False, episode=None)

        if reason not in COUNTED_REASONS:
            # pending / illegal_move / move_rejected / unknown: passthrough.
            return Outcome(rearm=True, episode=self._episode)

        if self._episode is None or self._episode.episode_key != key:
            # New coords (or game_id) -> new episode; the old one is discarded,
            # not "resolved" (review m2).
            self._episode = RecoveryEpisode(episode_key=key, game_id=game_id, coords=coords)

        episode = self._episode
        if episode.recovery_token is not None:
            # Already tripped -- detection should be paused so this shouldn't be
            # reachable in practice, but stay defensive rather than re-trip.
            return Outcome(rearm=False, episode=episode, enter_engine_error=False)

        episode.count += 1
        episode.detail = detail
        if episode.count >= self.config.engine_move_max_attempts:
            episode.recovery_token = self._token_factory()
            return Outcome(rearm=False, episode=episode, enter_engine_error=True)
        return Outcome(rearm=True, episode=episode)
