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
from katrain.web.core.physical_play import BLACK, EMPTY, WHITE, LedPlanner, PhysicalPlayConfig

logger = logging.getLogger("katrain_web.physical_play")


class PhysicalPlayOrchestrator:
    # Pause-reason constants (M2 refactor). Task 8 adds "awaiting_removal" the same
    # way — a single _add_pause_reason(...) call, no change needed here or in
    # _sync_pause_state.
    PAUSE_REASON_LAG = "lag"
    PAUSE_REASON_HINT = "hint"
    PAUSE_REASON_ENGINE_ERROR = "engine_error"  # Task 7 (B5/M1/M4)
    PAUSE_REASON_AWAITING_REMOVAL = "awaiting_removal"  # Task 8 (B4/M5/D8)

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
        self._pause_reasons: set[str] = set()  # {"lag", "hint", ...} -- see _sync_pause_state
        self._suspended = False  # cached: tick body suspended (derived from _pause_reasons)
        self._paused_sent: Optional[bool] = None  # last pause state sent to the worker
        self._hint_task: Optional[asyncio.Task] = None
        self._behind_since: Optional[float] = None
        self._reminded = False
        self._escalated = False
        self._last_assert_ts: Optional[float] = None  # last actual LED write (review A)
        self._engine_error_context: Optional[dict] = None  # {"coords", "recovery_token"} (Task 8 consumes)
        self._awaiting_removal_context: Optional[dict] = None  # {"coords", "stable_count", "last_remind_ts"}

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
        self._pause_reasons.clear()  # unbind drops EVERY reason (hint/lag/future ones)
        self._behind_since = None
        self._reminded = False
        self._escalated = False
        self._engine_error_context = None
        self._awaiting_removal_context = None
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

    def resync(self) -> None:
        """User-triggered recovery from a stuck removal / mismatch_warning (kiosk
        "重置识别", escalation "已按指示恢复"). Re-baselines vision to the CURRENT
        digital board — discarding a camera phantom that latched a missing_anomaly /
        MISMATCH_WARNING — and drops the planner's stuck removal so an un-clearable
        removal stops gating move injection. Detection resumes immediately, with no
        30s/120s escalation wait.

        Safe without a bound session (research mode): degrades to a plain sync reset."""
        state = self._latest_state
        if state is None:
            # No bound game yet: degrade to a plain physical-adopt reset.
            try:
                self._vision.reset_sync()
            except Exception as e:  # never let a recovery tap raise
                logger.debug("resync: reset_sync failed: %s", e)
            return

        board_size = state["board_size"][0]
        expected = np.asarray(game_state_stones_to_board(state["stones"], board_size))
        try:
            # ONE atomic command: sync re-baselines to the digital board (mismatch clears
            # against digital) while the MoveDetector baselines to the digital∪physical
            # UNION — so a still-present leftover / glare-washed stone is not re-injected as
            # a move when detection resumes. (A separate expected-push would re-baseline the
            # detector to bare digital and re-inject the leftover.)
            self._vision.reset_sync(expected=expected)
        except Exception as e:
            logger.debug("resync: reset_sync failed: %s", e)

        # Drop the planner's stuck removal so an un-clearable removal stops gating moves;
        # a still-present stone re-surfaces as a non-gating blue cleanup lamp next tick.
        self._planner.reconcile(expected)

        # Release the move-detection pause NOW and reset the lag timers so the
        # reminder/escalation flow re-arms cleanly on the next genuine lag.
        self._set_caught_up(True)
        self._behind_since = None
        self._reminded = False
        self._escalated = False

        # Force the next tick to re-emit lamps (the dedupe would otherwise suppress the
        # now-changed plan) so a stale blue lamp clears.
        self._last_points = None

    def enter_engine_error(self, coords: Tuple[int, int], recovery_token: str) -> None:
        """Task 7 hand-off: the poller's engine_recovery episode tripped its
        attempts threshold. Suspends the tick AND pauses move detection (same
        aggregation as hint/lag, via _add_pause_reason) so the physical stone that
        triggered the failing tunnel call stops being re-confirmed and retried.
        Stores `coords`/`recovery_token` for Task 8/9's dismiss-dialog endpoint."""
        self._engine_error_context = {"coords": coords, "recovery_token": recovery_token}
        self._add_pause_reason(self.PAUSE_REASON_ENGINE_ERROR)

    def clear_engine_error(self) -> None:
        """Counterpart of enter_engine_error: resumes detection (unless another
        reason is still active) once the recovery dialog is dismissed/resolved."""
        self._engine_error_context = None
        self._remove_pause_reason(self.PAUSE_REASON_ENGINE_ERROR)

    def enter_awaiting_removal(self, coords: Tuple[int, int]) -> None:
        """Task 8 (B4/M5/D8): the recovery dialog's "cancel" hand-off. `coords` are
        GTP/board space (col, row0=bottom) — same convention as `enter_engine_error`
        and the `physical_engine_error` broadcast; converted to vision-grid
        (row0=top) internally by `_tick_awaiting_removal`.

        Replaces the engine_error pause reason with awaiting_removal (add-then-remove
        order keeps the aggregate non-empty throughout, so _sync_pause_state never
        fires a spurious resume+re-pause blip) — the failure record is gone (the
        caller already consumed it via the tracker's CAS), so there's no more retry
        story, only "wait for the physical stone to come off"."""
        self._awaiting_removal_context = {
            "coords": coords,
            "stable_count": 0,
            "last_remind_ts": self._clock(),
        }
        self._add_pause_reason(self.PAUSE_REASON_AWAITING_REMOVAL)
        self._remove_pause_reason(self.PAUSE_REASON_ENGINE_ERROR)
        self._engine_error_context = None

    def clear_awaiting_removal(self) -> None:
        """Counterpart of enter_awaiting_removal: resumes detection (unless another
        reason is still active) once the stability gate resolves or the session
        unbinds."""
        self._awaiting_removal_context = None
        self._remove_pause_reason(self.PAUSE_REASON_AWAITING_REMOVAL)

    def _add_pause_reason(self, reason: str) -> None:
        """Add a suspension reason (M2). Idempotent: a reason already present is a
        no-op, so re-adding it never re-triggers _sync_pause_state or its IPC call."""
        if reason in self._pause_reasons:
            return
        self._pause_reasons.add(reason)
        self._sync_pause_state()

    def _remove_pause_reason(self, reason: str) -> None:
        """Remove a suspension reason (M2). Idempotent counterpart of _add_pause_reason
        — removing an absent reason is a no-op. Other reasons still in the set keep
        the tick/detection paused (this is the fix for review M2: a shared boolean
        used to let one reason's dismissal wrongly resume everything)."""
        if reason not in self._pause_reasons:
            return
        self._pause_reasons.discard(reason)
        self._sync_pause_state()

    def _set_caught_up(self, caught_up: bool) -> None:
        """Translate the board catch-up flag into the "lag" pause reason. Kept as a
        single call site so every _caught_up assignment stays in sync with the set."""
        self._caught_up = caught_up
        if caught_up:
            self._remove_pause_reason(self.PAUSE_REASON_LAG)
        else:
            self._add_pause_reason(self.PAUSE_REASON_LAG)

    def _sync_pause_state(self) -> None:
        """Single aggregation point (M2) for BOTH suspension effects, derived from
        self._pause_reasons:
          (a) self._suspended — gates the tick body (_run/_tick_once). Any reason
              OTHER than pure lag suspends the tick (hint does; Task 7's engine_error
              will too). Lag ALONE never suspends the tick — the tick itself is what
              re-evaluates catch-up and clears the lag reason, so stopping it would
              make lag un-recoverable.
          (b) the worker's move-detection pause (Q4 redesign + hint) — paused while
              ANY reason is active. While paused, the worker produces NO ConfirmedMove
              — this replaces the unsound 'hold a confirmed move' design (MoveDetector
              advances its baseline at confirm time, so held moves could go
              stale/corrupt — review Blocker 1). A premature user stone simply stays
              unconfirmed and is picked up naturally after resume, against the
              baseline force-synced by the expected-board push.
        The IPC call to vision is only made when the boolean actually changes
        (self._paused_sent), so combining/dropping reasons that don't flip the
        aggregate never re-sends a duplicate pause/resume."""
        self._suspended = bool(self._pause_reasons - {self.PAUSE_REASON_LAG})
        desired = bool(self._pause_reasons)
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
                if self._session_id is None:
                    continue
                # Task 8: awaiting_removal is a member of _pause_reasons (so
                # detection stays paused and _suspended is True, like engine_error/
                # hint), but the tick loop must keep running a NARROW board-equality
                # check instead of either the full reconciliation OR nothing —
                # dispatch here, before the _suspended gate below.
                if self.PAUSE_REASON_AWAITING_REMOVAL in self._pause_reasons:
                    try:
                        self._tick_awaiting_removal()
                    except Exception as e:  # defensive: LED problems must not kill the loop
                        logger.warning("physical-play awaiting-removal tick error: %s", e)
                    continue
                if self._suspended:
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
            self._set_caught_up(True)
            self._apply_points([])
            return
        board_size = state["board_size"][0]
        expected = np.asarray(game_state_stones_to_board(state["stones"], board_size))
        self._planner.set_context(
            guided_colors=self._guided_colors_from_state(state),
            setup_cells=self._setup_cells_from_state(state, board_size),
        )
        self._planner.on_expected(expected)
        plan = self._planner.tick(expected, np.asarray(observed))
        self._set_caught_up(plan.caught_up)
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

    def _tick_awaiting_removal(self) -> None:
        """Task 8's narrow tick (dispatched by `_run` instead of `_tick_once` while
        PAUSE_REASON_AWAITING_REMOVAL is active). Resolution gate: the observed board
        equals the digital board (which implies the target cell is empty — the failed
        move never landed digitally) for `awaiting_removal_stable_ticks` CONSECUTIVE
        ticks. A wrong-cell removal, a replace-after-remove, or the target simply
        staying occupied are all covered by the SAME equality check (any of them
        breaks the equality, resetting the counter to 0) — no separate branches
        needed for the review's three non-resolving scenarios.

        Guidance: a blue 'remove' lamp on the target cell while it's still occupied
        (reuses `_apply_points`, same as the main tick); cleared once removed. A
        reminder re-broadcasts every `awaiting_removal_remind_interval_s` while still
        waiting, for the frontend to re-prompt the user."""
        ctx = self._awaiting_removal_context
        if ctx is None:
            return
        state = self._latest_state
        if not state:
            return
        observed = self._vision.get_detected_board()
        if observed is None:
            return  # board not visible: hold current state, try again next tick
        board_size = state["board_size"][0]
        expected = np.asarray(game_state_stones_to_board(state["stones"], board_size))
        observed_arr = np.asarray(observed)
        col, gtp_row = ctx["coords"]
        vr, vc = board_size - 1 - int(gtp_row), int(col)
        target_clear = bool(observed_arr[vr, vc] == EMPTY)
        board_matches = bool(np.array_equal(observed_arr, expected))
        stable = target_clear and board_matches
        ctx["stable_count"] = ctx["stable_count"] + 1 if stable else 0

        self._apply_points([] if target_clear else [{"row": vr, "col": vc, "color": "remove"}])

        if ctx["stable_count"] >= self.config.awaiting_removal_stable_ticks:
            self._complete_awaiting_removal()
            return

        now = self._clock()
        if now - ctx["last_remind_ts"] >= self.config.awaiting_removal_remind_interval_s:
            ctx["last_remind_ts"] = now
            self._manager.broadcast_to_session(
                self._session_id,
                {
                    "type": "physical_awaiting_removal_reminder",
                    "data": {"row": vr, "col": vc},
                },
            )

    def _complete_awaiting_removal(self) -> None:
        """Stability gate satisfied: re-baseline vision to the (already-matching)
        digital board via the existing `resync()` — reusing it rather than a bespoke
        reset keeps the removal-pending/planner state consistent with every other
        recovery path — then drop the reason (resumes detection) and tell the
        frontend to close the waiting UI."""
        self.resync()
        self.clear_awaiting_removal()
        self._manager.broadcast_to_session(
            self._session_id,
            {"type": "physical_engine_error_resolved"},
        )

    @staticmethod
    def _guided_colors_from_state(state: Dict) -> Optional[set]:
        """Colors whose stones need placement lamps = the AI-played colors. Human moves
        need no LED (vision observing them IS the move source). None (no players_info)
        keeps the legacy guide-everything behavior.

        A remote Golaxy engine-play seat marks BOTH players_info entries "human" (the
        physical board mediates for both), so player_type alone can't see it. Task 1's
        `platform_engine_color` state field ("B"/"W"/None) names the color the remote
        engine plays; that color is guided exactly like a local player:ai would be. Read
        as a plain dict field only (no import from katrain/web/platforms — see the SBC
        build-boundary contract in CLAUDE.md)."""
        players = state.get("players_info")
        if not players:
            return None
        engine_color = state.get("platform_engine_color")
        return {
            color
            for bw, color in (("B", BLACK), ("W", WHITE))
            if (players.get(bw) or {}).get("player_type") == "player:ai" or bw == engine_color
        }

    @staticmethod
    def _setup_cells_from_state(state: Dict, board_size: int) -> set:
        """Root-setup (handicap / AB) stones: entries with no move number. Guided
        regardless of color — the '开局 N 红灯全亮' handicap flow. Same coordinate
        flip as game_state_stones_to_board (gtp_row 0 = bottom -> vision row 0 = top)."""
        cells = set()
        for entry in state.get("stones") or []:
            # [player, [col, gtp_row] | None, score_loss, move_number]
            if len(entry) >= 4 and entry[3] is None and entry[1]:
                col, gtp_row = entry[1]
                cells.add((board_size - 1 - int(gtp_row), int(col)))
        return cells

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
        # can't be misread as stones. The mask blocks ADDITIONS only (board_state checks
        # the last stable board): an established stone at a lit cell keeps being
        # recognized — masking it used to blind vision to the very stone a "remove" lamp
        # pointed at (lamp/recognition oscillation that made moves unregistrable) and to
        # force-clear _removal_pending while the stone was still on the board.
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
        self._add_pause_reason(self.PAUSE_REASON_HINT)
        if hasattr(self._vision, "set_lit_points"):
            self._vision.set_lit_points(list(points))
        self._hint_task = asyncio.get_running_loop().create_task(self._blink(points))

    def dismiss_hint(self) -> None:
        if self._hint_task is not None and not self._hint_task.done():
            self._hint_task.cancel()
        self._hint_task = None
        self._end_hint()

    def _end_hint(self) -> None:
        if self.PAUSE_REASON_HINT not in self._pause_reasons:
            return
        self._remove_pause_reason(self.PAUSE_REASON_HINT)  # stays paused if another reason remains
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
