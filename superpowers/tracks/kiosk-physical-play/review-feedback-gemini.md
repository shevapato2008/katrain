# Gemini's Review of Kiosk Physical Play Implementation Plan

**To:** fan (via Claude)
**From:** Gemini
**Date:** 2026-07-02
**Subject:** Critical Review of `plan.md` for Kiosk Physical Play

This document contains my technical review of the implementation plan. I have verified the plan's claims against the codebase (`feature/kiosk-physical-play` branch) and analyzed the high-risk areas and specific questions you raised.

Overall, the plan is incredibly thorough and well-researched. The task decomposition is logical, and the TDD approach is excellent. My findings are focused on the high-risk areas you correctly identified, several of which I classify as blockers or important design issues that need to be addressed before execution.

---

## Executive Summary of Findings

*   **Blockers (2):** An LED idle-failsafe bug that will break the user experience, and a dependency on backend data (`game_type`, `analysis_allowed`) that is not actually being sent to the frontend.
*   **Important (4):** A potential permanent game stall, a risk of incorrect state due to missed events in the vision sync logic, an under-specified engine routing mechanism for hints, and insufficient glare-masking for placement targets.
*   **Minor (1):** A suboptimal UX flow for handling out-of-turn moves.

The core architecture (reconciliation loop, `PhysicalPlayOrchestrator`) is sound. The issues found are all fixable within the proposed framework.

---

## Detailed Findings & Recommendations

Here is a detailed breakdown, cross-referenced with the high-risk areas (A-G) from your review request.

### [Blocker] A. LED Idle-Failsafe Will Cause Game to Stall

Your analysis of the idle-failsafe bug is **correct**. My review of `katrain/web/server.py` and the plan's `_apply_points` logic confirms that if a user waits more than 5 minutes to place an AI stone, the guidance lamp will turn off and *will not* turn back on, effectively stalling the game.

-   **Finding:** The `if points == self._last_points: return` check in `_apply_points` (Task 4) prevents the activity timer from being stamped, leading the `_led_failsafe_loop` to incorrectly clear the board after `LED_IDLE_TIMEOUT_S`.
-   **Recommendation:** Modify the orchestrator's `_tick` method (Task 4, Step 5). Add a line to call `self._touch_led_activity()` on every tick *if the board is not caught up*. This is the cleanest fix as it localizes the solution to the component that bypasses the standard LED activity-stamping mechanism.

    ```python
    # In PhysicalPlayOrchestrator._tick()
    async def _tick(self):
        # ... logic to calculate points ...
        if not self.board_caught_up:
            self._touch_led_activity() # <-- ADD THIS LINE

        await self._apply_points(points)
        self._maybe_remind(points)
    ```

### [Blocker] G. Frontend `mode` Plumbing Rests on a False Assumption

Your suspicion was correct. I have verified the code in `katrain/web/interface.py`, and the `get_state()` method **does not** include `game_type` or `analysis_allowed` in its returned payload.

-   **Finding:** The frontend logic in Tasks 9, 12, and 13, which relies on these properties to conditionally render UI elements like the hint and undo buttons, will fail. This breaks core functionality for ranked vs. free play.
-   **Recommendation:** Amend the plan to include a backend change. The `get_state` method in `katrain/web/interface.py` must be modified to add `self.game_type` and `self.analysis_allowed` to the returned state dictionary. This change should be a prerequisite for the frontend tasks that depend on it.

### [Important] B. Q4 Hold-Gate Can Lead to Permanent Game Stall

The plan's "block until placed" logic for AI moves is sound in principle but lacks a necessary escape hatch.

-   **Finding:** As designed in Task 6, if `board_caught_up` never becomes true (e.g., user walks away, vision fails), the `_vision_move_poller` will hold the user's next move indefinitely, deadlocking the game. The "30s nag" is insufficient.
-   **Recommendation:** The plan must include an escape hatch. After a longer timeout (e.g., 2-3 minutes of nagging), the UI should present a modal dialog forcing a user decision: options could include "Retry Detection", "Enter Edit Mode to Fix Board", or even "Forfeit AI's Move". This prevents a permanent stall.

*(Note: The UX for handling an out-of-turn placement is a **[Minor]** issue. Re-using the generic `MISMATCH_WARNING` is functional, but a more specific state like `AWAITING_AI_PLACEMENT` would provide a clearer user message.)*

### [Important] C. Digital-Authority Sync Rewrite is Not Resilient to Missed Events

The new `_compare_boards` logic in Task 5 is a good refactoring but introduces a new failure mode.

-   **Finding:** The three-way diff (`current`, `expected`, `prev_expected`) is entirely dependent on the orchestrator receiving every single `game_update` event to keep `prev_expected_board` perfectly in sync. Given that the update callback runs in a separate thread, a missed event is a plausible risk, which would lead to incorrect diffs and state machine errors.
-   **Recommendation:** Make the `vision.set_expected_from_stones` call more robust. It should accept not just the board state but also a sequence number or a hash of the game state. The vision service can then track this identifier to detect if an update was missed and, if so, fall back to the safer, simple two-way diff (`current` vs `expected`) for that cycle.

### [Important] E. Masking Logic is Insufficient for Placement Targets

Your analysis of the masking logic is spot-on. The current plan fails to account for glare at the most critical moment.

-   **Finding:** The proposed masking logic in Task 7 correctly ignores glare on *expected-empty* points. However, it explicitly *does not* mask a placement-target lamp, as the point is expected-non-empty. This means the vision system will see both LED glare and a physical stone, risking a misclassification.
-   **Recommendation:** The orchestrator should extinguish a placement lamp as soon as the vision system reports an *unconfirmed* detection at that spot. The plan already adds a `move_pending` event (Task 7) for the UI's "确认中" chip. This same event should be used by the orchestrator to turn off the lamp, allowing the subsequent 2-3 frames for confirmation to get a clean, glare-free view of the physical stone.

### [Important] F. Hint Engine Routing is Under-Specified

The plan for the hint feature (Task 8) successfully reconstructs the game payload but hand-waves the critical step of engine selection.

-   **Finding:** The plan relies on an "Imagined API" (`get_engine(force_strong=True)`). This is a significant gap. In board mode, the default engine is a weak local one, and no existing mechanism is described for selecting a different, stronger engine for analysis on-demand.
-   **Recommendation:** The plan for Task 8 must be expanded to include the design and implementation of this engine routing logic within the `KataGoEnginePool` or a similar service. It needs to concretely solve how to request and utilize a non-default (and potentially remote) engine for analysis calls.

---

## Answers to Specific Questions

1.  **Reconciliation-loop model?** Yes, it is the right model. It's robust, simpler to implement correctly than an event-driven model, and resilient to the kinds of transient failures one can expect with physical hardware.
2.  **Task 2 queue fix race-free?** Yes. Given asyncio's single-threaded nature and the atomicity of `deque` operations, the proposed single-producer, multiple-consumer pattern using separate deques is race-free. No lock is needed.
3.  **Idle-failsafe bug (§A) real?** Yes, it's real and a **[Blocker]**. My recommendation is in the detailed findings above.
4.  **Q4 hold-gate (§B) sound?** Mostly, but it needs an escape hatch for the permanent stall case, which is an **[Important]** issue.
5.  **Task 5 sync rewrite (§C) risk?** Yes, it risks breaking on missed events. This is an **[Important]** issue that needs a resiliency mechanism (like a sequence number).
6.  **Task ordering / dependency problems?** The ordering seems fine. Using `hasattr` as a guard between Tasks 4 and 7 is an acceptable development seam.
7.  **Over-builds or under-specifies?** The plan is not over-built. It does under-specify the hint engine routing and the hold-gate escape hatch, as noted above.

This is a complex but exciting feature. The plan is very close to being solid. I'm available for any follow-up questions.
