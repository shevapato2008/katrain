"""PhysicalPlayOrchestrator — drives the physical LED board from authoritative game state.

Design (PRD R2 / feasibility §4.1):
- Backend-owned: LEDs are physical-device state; the frontend may refresh or disconnect.
- Reconciliation, not events: each tick diffs the digital board (latest game_update)
  against the observed board (vision) and writes the LED batch. One loop covers AI-move
  lamps, capture lamps, undo restore, handicap guidance and leftover-stone cleanup.
- Event-source abstraction (PRD R8.1 / Q5): the ONLY input is the game_update state dict.
  A remote opponent (phase 2) or a second human produces identical updates — zero changes.
- Threading: on_game_state may be called from the AI thread (wrapped update_state_callback).
  It only stores the dict and pushes the expected board (queue put, thread-safe). All
  planner mutations happen on the event loop inside _tick_once.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from katrain.vision.sync import game_state_stones_to_board
from katrain.web.core.physical_play import LedPlanner, PhysicalPlayConfig

logger = logging.getLogger("katrain_web.physical_play")


class PhysicalPlayOrchestrator:
    def __init__(
        self,
        *,
        config: PhysicalPlayConfig,
        led,  # LedService | None (None => plan/gate only, no serial writes)
        vision,  # VisionService
        session_manager,
        touch_led_activity: Callable[[], None] = lambda: None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.config = config
        self._led = led
        self._vision = vision
        self._manager = session_manager
        self._touch = touch_led_activity
        self._clock = clock

        self._planner = LedPlanner(config)
        self._session_id: Optional[str] = None
        self._session = None
        self._orig_callback = None
        self._latest_state: Optional[Dict] = None
        self._task: Optional[asyncio.Task] = None
        self._last_points: Optional[List[Dict]] = None
        self._caught_up = True
        self._suspended = False
        self._hint_active = False
        self._paused_sent: Optional[bool] = None  # last pause state sent to the worker
        self._hint_task: Optional[asyncio.Task] = None
        self._behind_since: Optional[float] = None
        self._reminded = False
        self._escalated = False
        self._last_assert_ts: Optional[float] = None  # last actual LED write (review A)

    # -- lifecycle -----------------------------------------------------------

    def on_bind(self, session_id: str, session) -> None:
        """Attach to a session: wrap its (single-slot) state callback, seed state,
        start the tick loop. Called from the vision bind endpoint (Task 6).
        Idempotent for the same session (the frontend double-binds today, review M1)."""
        if session_id == self._session_id and session is self._session:
            return
        self.on_unbind()
        self._session_id = session_id
        self._session = session
        self._planner.reset()
        self._orig_callback = session.katrain.update_state_callback
        orig = self._orig_callback

        def wrapped(state, _orig=orig):
            if _orig:
                _orig(state)
            self.on_game_state(state)

        session.katrain.update_state_callback = wrapped
        self.on_game_state(session.katrain.get_state())
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(self._run())

    def on_unbind(self) -> None:
        """Detach: restore callback, cancel hint, blank the lamps (R2.5)."""
        self.dismiss_hint()
        if self._session is not None:
            self._session.katrain.update_state_callback = self._orig_callback
        self._session = None
        self._session_id = None
        self._orig_callback = None
        self._latest_state = None
        self._caught_up = True
        self._behind_since = None
        self._reminded = False
        self._escalated = False
        self._sync_pause_state()  # resume detection if we had it paused
        self._apply_points([])

    async def shutdown(self) -> None:
        self.on_unbind()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    # -- inputs ----------------------------------------------------------------

    def on_game_state(self, state: Dict) -> None:
        """Authoritative game_update. Pushing the expected board here re-baselines
        MoveDetector on EVERY digital change (AI move, undo, nav) — closing the gap
        where placing the AI's stone was itself detected as a new move."""
        if self._session_id is None:
            return
        self._latest_state = state
        try:
            self._vision.set_expected_from_stones(state["stones"], state["board_size"][0])
        except Exception as e:  # never break the broadcast chain
            logger.debug("expected-board push failed: %s", e)

    @property
    def board_caught_up(self) -> bool:
        """False while the physical board still owes a placement/removal (Q4 gate)."""
        return self._caught_up

    def _sync_pause_state(self) -> None:
        """Single owner of the worker's move-detection pause (Q4 redesign + hint).
        While paused, the worker produces NO ConfirmedMove — this replaces the unsound
        'hold a confirmed move' design (MoveDetector advances its baseline at confirm
        time, so held moves could go stale/corrupt — review Blocker 1). A premature
        user stone simply stays unconfirmed and is picked up naturally after resume,
        against the baseline force-synced by the expected-board push."""
        desired = self._hint_active or not self._caught_up
        if desired == self._paused_sent:
            return
        self._paused_sent = desired
        if hasattr(self._vision, "pause_detection"):  # lands in Task 7
            if desired:
                self._vision.pause_detection()
            else:
                self._vision.resume_detection()

    # -- tick loop ---------------------------------------------------------------

    async def _run(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.config.tick_interval_s)
                if self._session_id is None or self._suspended:
                    continue
                try:
                    self._tick_once()
                except Exception as e:  # defensive: LED problems must not kill the loop
                    logger.warning("physical-play tick error: %s", e)
        except asyncio.CancelledError:
            pass

    def _tick_once(self) -> None:
        state = self._latest_state
        if not state:
            return
        observed = self._vision.get_detected_board()
        if observed is None:
            return  # board not visible: keep current lamps (PRD §3.4 BOARD_LOST row)
        if state.get("end_result"):
            self._caught_up = True
            self._sync_pause_state()
            self._apply_points([])
            return
        board_size = state["board_size"][0]
        expected = np.asarray(game_state_stones_to_board(state["stones"], board_size))
        self._planner.on_expected(expected)
        plan = self._planner.tick(expected, np.asarray(observed))
        self._caught_up = plan.caught_up
        self._sync_pause_state()
        # Review A: periodically re-send a non-empty lamp state so the 300s LED idle
        # failsafe — and manual clears / serial reconnects — can't strand a dark lamp
        # while the plan is unchanged (the dedupe below would otherwise never re-send).
        if (
            self._last_points
            and self._last_assert_ts is not None
            and self._clock() - self._last_assert_ts > self.config.led_reassert_interval_s
        ):
            self._last_points = None
        self._apply_points(plan.points)
        self._maybe_remind(plan)

    def _apply_points(self, points: List[Dict]) -> None:
        if points == self._last_points:
            return
        self._last_points = points
        if self._led is not None:
            if points:
                self._led.set_points(points, strict=False)
            else:
                self._led.clear(strict=False)
            self._touch()
            self._last_assert_ts = self._clock()
        # R7.1: tell vision which intersections are lit so lamp glare on empty points
        # can't be misread as stones (VisionService method lands in Task 7 — guarded).
        if hasattr(self._vision, "set_lit_points"):
            self._vision.set_lit_points([(p["row"], p["col"]) for p in points])

    def _maybe_remind(self, plan) -> None:
        """Two escalation tiers (review B escape hatch): a gentle toast at
        reminder_after_s, then a blocking dialog at escalate_after_s offering
        retry / restored / switch-to-screen-play. Each fires once per lag episode."""
        if plan.caught_up:
            self._behind_since = None
            self._reminded = False
            self._escalated = False
            return
        now = self._clock()
        if self._behind_since is None:
            self._behind_since = now
            return
        behind_for = now - self._behind_since
        kind = None
        if not self._escalated and behind_for > self.config.escalate_after_s:
            self._escalated = True
            kind = "escalation"
        elif not self._reminded and behind_for > self.config.reminder_after_s:
            self._reminded = True
            kind = "reminder"
        if kind:
            self._manager.broadcast_to_session(
                self._session_id,
                {
                    "type": "physical_reminder",
                    "data": {
                        "kind": kind,
                        "to_place": [list(p) for p in sorted(plan.to_place)],
                        "to_remove": [list(p) for p in sorted(plan.to_remove)],
                    },
                },
            )

    # -- hint (Task 8 wires the endpoint) ----------------------------------------

    def show_hint(self, points: List[Tuple[int, int]]) -> None:
        """Blink white lamps on the top-N points. Suspends reconciliation AND move
        detection (R4.3) for the duration; auto-restores on timeout or dismiss."""
        self.dismiss_hint()
        self._suspended = True
        self._hint_active = True
        self._sync_pause_state()
        if hasattr(self._vision, "set_lit_points"):
            self._vision.set_lit_points(list(points))
        self._hint_task = asyncio.get_running_loop().create_task(self._blink(points))

    def dismiss_hint(self) -> None:
        if self._hint_task is not None and not self._hint_task.done():
            self._hint_task.cancel()
        self._hint_task = None
        self._end_hint()

    def _end_hint(self) -> None:
        if not self._suspended:
            return
        self._suspended = False
        self._hint_active = False
        self._sync_pause_state()  # stays paused if the board is still lagging
        self._last_points = None  # force the game lamp state to re-send next tick

    async def _blink(self, points: List[Tuple[int, int]]) -> None:
        half = self.config.hint_blink_period_s / 2
        deadline = self._clock() + self.config.hint_timeout_s
        on = True
        try:
            while self._clock() < deadline:
                if self._led is not None:
                    if on:
                        self._led.set_rgb_points(
                            [{"row": r, "col": c, "rgb": (255, 255, 255)} for r, c in points], strict=False
                        )
                    else:
                        self._led.clear(strict=False)
                    self._touch()
                on = not on
                await asyncio.sleep(half)
        except asyncio.CancelledError:
            raise
        finally:
            self._end_hint()
