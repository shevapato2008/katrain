# Review Feedback for Golaxy Engine Integration Plan

> To: Plan Author
> From: Gemini (Code Reviewer)
> Date: 2026-07-02
> Subject: Review of `plan.md` for Kiosk Golaxy Engine Integration

---

## Overall Assessment

This is an exceptionally well-structured and detailed plan. The bottom-up, test-driven approach with clear verification checkpoints at each phase is excellent. The core architectural decision to adapt the stateless tunnel into the existing event-based `PlatformAdapter` by making `submit_move` a synchronous request-response cycle is pragmatic and minimizes rework.

The feedback below focuses on strengthening the plan's robustness and addressing potential user experience and maintenance issues, as requested in `review-request.md`.

---

## 🔴 Blocking Issues

*These issues must be addressed in the plan before implementation begins to avoid significant rework or creating a fragile feature.*

**1. (Ref: A4, E15) Lack of State Persistence**

The plan currently does not account for persisting the game state (`moves` list and game configuration). Because the Golaxy tunnel is stateless, the KaTrain server holds the only source of truth.

-   **Problem**: A simple page refresh, browser crash, or server restart would completely lose the ongoing game. This is not an acceptable user experience for a feature that is otherwise treated like a local game session.
-   **Required Change**: The plan **must** be updated to include state persistence. A new task should be added to **Phase 2 or 3** to save the engine game context (at a minimum, the `moves` list, `game_id`, and configuration) to a persistent store (e.g., the existing `user_games` database table) on every move. The `start_engine_game` flow should also handle reconnecting to an existing, non-terminated game. The Definition of Done (plan.md §9) must be updated to include "Game state is persisted and survives a page refresh."

**2. (Ref: B5) Unsafe Retry Strategy on HTTP Timeout**

The plan mentions "handle ... timeout" but doesn't specify how. This is critical for a synchronous call that modifies state.

-   **Problem**: The `genmove` API call is not idempotent. If a request is sent, the Golaxy server processes it, but the response is lost due to a network timeout, a simple retry would send the *same* human move again. This would cause the AI to make a second, unwanted move, corrupting the game state (`[H1, A1, H1, A2]`).
-   **Required Change**: The plan must explicitly state that **`engine_genmove` calls MUST NOT be retried on timeout**. A mitigation strategy must be designed. I recommend:
    1.  Use a very long timeout (e.g., 3-5 minutes) to accommodate high-level bots.
    2.  On timeout, the game should be moved to a "stalled" or "error" state on the server.
    3.  The UI should inform the user of the connection issue and that the game state is uncertain. Automatic recovery is not safely possible. The best user experience might be to allow the user to abandon the game.

## 🟡 Important Suggestions

*These are strongly recommended changes that will improve maintainability and robustness. They can be addressed within the relevant implementation phase.*

**1. (Ref: A2) Use a Separate Method for Engine Moves**

-   **Suggestion**: Instead of overloading `submit_move` and dispatching internally based on `game_id` type, create a new, explicit method in the adapter, such as `submit_engine_move(...)`.
-   **Reasoning**: This makes the code more self-documenting and avoids context-dependent "magic" behavior in `submit_move`. It improves long-term maintainability and reduces the risk of breaking the existing (and future) player-vs-player `submit_move` logic.

**2. (Ref: A3) Make Opponent Move Lookup Explicit**

-   **Suggestion**: In Phase 2/3, modify the `PlatformMove` event object to carry the `game_id`, and update `PlatformManager._on_opponent_move` to use this `game_id` for a direct lookup instead of scanning all active games.
-   **Reasoning**: The current scanning approach is a latent bug waiting to happen in any multi-game scenario. This is a low-cost, high-impact change that improves the system's robustness immediately.

**3. (Ref: B8) Add Explicit Task for Token Refresh**

-   **Suggestion**: Add a specific task to Phase 2 to wrap `engine_genmove` calls with the existing token refresh logic. Add a unit test that mocks an expired token response (`401` or similar) and verifies that a token refresh is triggered before the call is successfully retried.
-   **Reasoning**: While noted as a risk, this is a core requirement for functionality. Making it an explicit, testable task ensures it's not overlooked.

**4. (Ref: D11) Use a Backend Endpoint for Level Data**

-   **Suggestion**: Create a backend endpoint like `GET /{platform}/engine/levels` to serve the 39-level bot list to the frontend, rather than hardcoding it in the frontend.
-   **Reasoning**: This decouples the frontend from platform-specific configuration, making future updates (if Golaxy changes its bot levels) much easier—only a backend change would be needed, with no new frontend release.

**5. (Ref: B6, B7) Defensive Handling of Errors and Unknown Coords**

-   **Suggestion**:
    -   (B6) In Phase 2, design the `engine_genmove` client to at least attempt to classify API errors. An expired token should trigger a refresh; other errors can be logged and treated as fatal to the game.
    -   (B7) In Phase 1, the `golaxy_to_katrain` coordinate decoder must handle unknown coordinates defensively. If the AI returns a special value for PASS or RESIGN, the function should not crash. It should return a special value (e.g., `None`) that the adapter can then interpret correctly (e.g., as a pass or game termination).
-   **Reasoning**: This makes the integration more resilient to unexpected responses from the Golaxy API, preventing crashes and providing a better user experience when things go wrong.

## 🟢 Minor / Nitpicks

**1. (Ref: C10) Enhance Coordinate Test Coverage**

-   **Suggestion**: In the Phase 1 unit tests for coordinate conversion, explicitly add the four corner points (A1, T1, A19, T19) and the center point (K10) to the test cases.
-   **Reasoning**: This provides stronger guarantees that edge and boundary cases are handled correctly.

## ❓ Questions

The `review-request.md` posed a comprehensive set of questions. My points above are intended to serve as direct answers to them. The plan is very clear, and with the "Blocking" and "Important" changes incorporated, I have no further questions.

---
This is a strong plan, and I'm confident that with these adjustments, the project will result in a robust and maintainable feature.
