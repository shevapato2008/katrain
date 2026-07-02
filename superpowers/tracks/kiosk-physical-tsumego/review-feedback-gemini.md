# Review Feedback: Kiosk Tsumego Physical Integration (Gemini)

- **审查员**: Gemini
- **日期**: 2026-07-02
- **对象**: `prd.md`, `plan.md`

This review assesses the pre-implementation plan for the "Kiosk Physical Tsumego" feature. The plan is comprehensive, but several design weaknesses, particularly in the frontend state machine, pose significant risks of race conditions, state corruption, and poor user experience. The following feedback aims to address these issues before implementation begins.

---

## Overall Assessment

The plan correctly identifies the major technical components and provides a detailed, step-by-step implementation guide. The backend changes are mostly well-reasoned. However, the frontend orchestration (Task 8) is the weakest link, containing several race conditions and brittle design choices that must be addressed. The lack of planned unit testing for this complex state machine is a major process flaw.

Below are detailed findings and actionable recommendations, categorized as requested.

---

## A. Frontend Orchestration State Machine (`usePhysicalTsumego`, Task 8)

### 1. Event Consumption Model
- **[Blocker]** `plan.md Task 8 Step 1`
- **Issue**: The plan to use a single `latestEvent` state for consuming WebSocket events is inherently unsafe. If two events arrive between React renders, the first event will be overwritten and lost. Losing a `setup_complete` or `move_confirmed` event will stall the state machine and break the user flow.
- **Recommendation**: Modify the plan **before implementation**. The hook must use a queue-based event processing model.
  - Implement an `events` state variable as an array: `const [events, setEvents] = useState<VisionEvent[]>([]);`.
  - Use a `useEffect` to process events from the queue. Keep track of the last processed event ID using a `useRef` to prevent reprocessing.
  - This ensures that every event is processed exactly once, in order.

### 2. `replying` Phase Race Condition
- **[Major]** `plan.md Task 8, Risk #2`
- **Issue**: There's a race condition if the user physically places a stone before the AI's reply renders on screen. The vision system will detect this as an `extra` stone, which will block the `SETUP_COMPLETE` event from firing (as it requires zero `extra` stones), stalling the process.
- **Recommendation**: Make the `replying` phase more explicit and robust.
  1. When entering the `replying` phase, immediately call `POST /vision/pause` to prevent the vision system from detecting new moves.
  2. After the AI's reply is detected (via the `stones` prop changing), post the new board state as the `expected-board`.
  3. Only after successfully setting the new target board, call `POST /vision/unpause`.
  This creates a safe window where user input is explicitly ignored.

### 3. Incorrect Move with Captures
- **[Major]** `plan.md Task 8, Risk #5`
- **Issue**: The v1 plan to only show the `extra` stone (the wrong move) to be removed is insufficient when the wrong move also captured opponent stones. The user will not know they need to replace the captured stones, leading to confusion.
- **Recommendation**: The `removing` (or "revert") phase must fully guide the user.
  1. The target board for the setup operation should be the state *before* the user's incorrect move (which `useTsumegoProblem`'s `undo` provides).
  2. The `BoardSetupGuide` and voice feedback must be enhanced. Instead of a generic message, they should guide the user through both removing their incorrect stone (`extra`) and replacing the captured stones (`missing`). The UI should visually distinguish between these two actions if possible.

### 4. `solved` Phase Celebration Abort
- **[Minor]** `plan.md Task 8, Risk #4`
- **Issue**: The `celebrate()` function is a fire-and-forget `async` function. If the user navigates to the next problem while the LED celebration is happening, the old celebration loop will continue to run and conflict with the `ledClear()` call for the new problem.
- **Recommendation**: The `celebrate` function must be made abortable.
  - The `useEffect` that calls it should create an `AbortController`.
  - Pass the `signal` from the controller to the `celebrate` function.
  - The `useEffect`'s cleanup function must call `controller.abort()`.
  - Inside the `celebrate` function's loop, check for `signal.aborted` and exit the loop if true.

### 5. `restartKey` Complexity
- **[Minor]** `plan.md Task 9 Step 3(g)`
- **Issue**: The `physicalCycle` state and `restartKey` prop are an indirect and overly complex way to signal a new problem.
- **Recommendation**: Simplify the hook's API. Pass the problem ID `problem.id` directly as a prop to `usePhysicalTsumego`. The hook's main `useEffect` should include `problem.id` in its dependency array. This will naturally and cleanly trigger cleanup and re-initialization when the problem changes, making the `restartKey` pattern unnecessary.

---

## B. Backend Vision Changes

### 8. Event Routing Brittleness
- **[Major]** `plan.md Task 3`
- **Issue**: The plan relies on an implicit, undocumented behavior of the WebSocket handler (single-consumer queue). This is extremely brittle and likely to break in the future if any other component starts listening to `/ws/vision`.
- **Recommendation**: Harden the eventing mechanism. The best solution is a proper pub/sub model where clients subscribe to topics. A simpler, minimal-change solution is to change the backend to **broadcast** vision monitor events to all connected `/ws/vision` clients. The frontend hook can then filter events by a session ID or problem ID if needed. At the absolute minimum, a large, prominent comment must be added to the backend code explaining this fragile single-consumer assumption.

### 9. Global Pause State
- **[Major]** `plan.md Task 4`
- **Issue**: The global boolean `pause` flag is not robust. While the UI currently combines `showHint || isTryMode`, this will break if a third reason to pause is introduced. The first component to unpause will incorrectly unpause for all components.
- **Recommendation**: Implement a more robust locking mechanism. A reference-counted pause or a named lock system (`POST /vision/pause {"lock_id": "try_mode"}`) is the proper engineering solution. This ensures the system remains paused until all locks are released. If this is out of scope for v1, the current approach should be marked as significant technical debt in the code.

---

## C. Plan Quality and Omissions

### 10. `matched` Calculation Error
- **[Blocker]** `plan.md Task 9 Step 3(e)`
- **Issue**: The formula provided in the plan for calculating `matched` is logically incorrect and will produce wrong numbers. It mixes total problem stones with per-stage missing stones.
- **Recommendation**: Do not perform this calculation in the `TsumegoProblemPage`. The `useVisionSync` hook (via the backend `/ws/vision` event) already provides the correct `matched` and `total` numbers for the current setup stage. The `BoardSetupGuide` component should be modified to accept these values directly from the `physical` object: `matched={physical.matched}` and `total={physical.total}`.

### 11. Lack of Unit Tests
- **[Major]** `plan.md` (overall structure)
- **Issue**: The plan omits unit tests for `usePhysicalTsumego`, the most complex and state-sensitive part of the entire feature. Relying solely on e2e or manual testing for a state machine is inefficient and will lead to a buggy and hard-to-maintain component.
- **Recommendation**: The plan must be amended to include a task to set up `vitest` and `@testing-library/react`. At least one other task should be dedicated to writing unit tests for `usePhysicalTsumego`, covering all major state transitions, event handling (including the queue), and edge cases like the `replying` and `removing` phases.

### 13. Screen/Physical Dual Input Handling
- **[Blocker]** PRD TR1
- **Issue**: The plan has a critical omission: it does not handle the case where a user makes a move on the screen while in physical mode. This will cause the physical board to become out-of-sync with the game state, confusing the user and the vision system.
- **Recommendation**: A re-sync mechanism is required.
  - In `TsumegoProblemPage.tsx`, add a `useEffect` that depends on `stones`.
  - Inside this effect, if `physical.enabled` is true, detect if the change to `stones` was caused by a screen-only interaction.
  - If it was, the hook must immediately treat the new `stones` array as a new setup target. This can be done by calling a new function on the `usePhysicalTsumego` hook, like `resync(newStones)`, which would internally post a new `expected-board` to the vision service and transition its state machine to `clearing` or `setup`. This ensures the physical board is always guided back to match the screen's source of truth.
