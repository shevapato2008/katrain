# Codex Review - `plan.md`

## Summary

The overall backend-owned reconciliation loop is the right architecture. It keeps LED state tied to authoritative game state instead of frontend lifetime, and it is a better fit than a purely event-driven design for physical hardware.

That said, the plan has several correctness problems that should be fixed before implementation. The biggest issue is the Q4 "hold confirmed user move" design: with the current `MoveDetector`, holding a move after confirmation mutates the detector baseline and can create stale or corrupt future move events. Task 5's sync rewrite also has a concrete misclassification bug.

## Findings

### [Blocker] Q4 hold-gate is not sound with the current `MoveDetector`

Anchors: `plan.md:1249-1270`, `katrain/vision/move_detector.py:53-56`, `katrain/vision/worker.py:256-260`, `katrain/vision/worker_inprocess.py:171-175`

Task 6 holds a `ConfirmedMove` while `board_caught_up == False`. But `MoveDetector.detect_new_move()` commits `prev_board = board.copy()` at the moment it emits the confirmed move. If the user prematurely places their own next stone while the AI stone is still missing, the detector baseline becomes the physical board that includes the premature user stone and still lacks the AI stone. When the user then places the AI stone, the worker can emit a second `ConfirmedMove` for that AI stone. Because the poller does not drain new worker moves while `held` exists, that stale event can be submitted after the held move is injected.

This can produce duplicate/illegal move attempts at best, and a wrong move if the old AI point becomes empty again after captures.

Fix: do not "hold" confirmed moves with the current detector semantics. While the physical board is behind, either pause/drain-and-discard move injection and show an explicit `awaiting_physical_sync` UI state, or redesign the worker to support tentative move detection that does not advance `MoveDetector.prev_board` until the backend accepts the move. If holding remains a hard requirement, add a separate move-baseline command/versioning mechanism so stale detections from the behind period are dropped.

Add a regression test for: AI stone pending -> user prematurely places own move -> user places AI stone -> only the premature move is handled according to policy, and the AI placement is never later injected as a fresh move.

### [Blocker] Task 5 reclassifies real missing stones as captures

Anchors: `plan.md:1072-1102`, `katrain/vision/sync.py:283-343`

The proposed `_compare_boards` rewrite treats `expected != EMPTY and observed == EMPTY` as `removal_needed` unless the previous expected board was empty. That is wrong for an existing stone physically removed by mistake. It will go through `CAPTURE_PENDING` and then immediately `CAPTURES_CLEARED` because the observed point is already empty, hiding a real board mismatch.

Fix the classification:

- `expected != EMPTY and observed == EMPTY` with `prev == EMPTY`: placement pending, not an anomaly.
- `expected != EMPTY and observed == EMPTY` with `prev != EMPTY`: missing physical stone, an anomaly after debounce; include it in `missing`.
- `expected == EMPTY and observed != EMPTY` with `prev == observed`: digital capture/undo pending physical removal, blue lamp / capture flow.
- `expected == EMPTY and observed != EMPTY` otherwise: unexpected extra stone.

Add tests for a player removing an existing live stone without any digital capture. It should produce an `illegal_change`/restore flow, not `capture_pending`.

### [Blocker] LED idle-failsafe bug is real

Anchors: `plan.md:879-891`, `katrain/web/server.py:1782-1803`

`_apply_points()` returns early when `points == self._last_points`, and activity is only touched after an LED write. A long pending placement can therefore be cleared by `_led_failsafe_loop`, while `_last_points` still says the LED state is current, so the guidance lamp never comes back.

Fix: track `last_led_asserted_at` separately from `_last_points` and periodically reassert non-empty desired LED state before the 300s failsafe window, then touch `led_last_activity` only after the reassert/write succeeds. This is better than only stamping activity, because it also recovers from manual clears or reconnects.

Task 15 should add a specific acceptance case: AI stone pending for more than 5 minutes still has guidance, or is reasserted without needing a new game state.

### [Important] Placement-target glare is still unhandled

Anchors: `plan.md:1502-1507`, `plan.md:2760`

The mask only drops lit points that are expected-empty. A placement target is expected-non-empty, so it remains unmasked exactly when the user places a stone on a lit LED. That is the highest-risk glare case.

Fix: when vision first observes any stone on a pending placement target, temporarily extinguish or suppress that target lamp for the confirmation window, while keeping the desired plan state so it can relight if the candidate disappears or is wrong. The new `move_pending` event can drive this, but the orchestrator also needs a target-suppression state and tests for "lamp off during confirmation, relights on failed confirmation."

### [Important] Hint payload reconstruction is incomplete for real SGF trees

Anchors: `plan.md:1814-1835`, `katrain/core/engine.py:123-188`

`_build_payload_from_game()` walks `current_node.parent` and reads only `game.root.placements`. KaTrain's own engine query builder uses `analysis_node.nodes_from_root`, collects placements from every node in the path, handles `clear_placements` by refusing unsupported positions, includes `initialPlayer`, and normalizes rules through engine logic.

Fix: reuse or mirror `BaseEngine.build_analysis_query()` semantics, then route the resulting payload through `RequestRouter`. At minimum, include placements from all nodes in `current_node.nodes_from_root`, handle `clear_placements`, include `initialPlayer`, and test handicap/setup stones after undo/navigation.

### [Important] The plan needs a real recovery state for physical desync

Anchors: `plan.md:30`, `plan.md:674-680`, `plan.md:1266-1269`

The 30s reminder is not enough. If the user cannot make the board catch up because vision is degraded, the game can stall forever. This is distinct from the detector-baseline blocker above.

Fix: expose an explicit backend state such as `awaiting_physical_sync` with `to_place` / `to_remove`, and after a timeout show actions like retry detection, reset sync after manual restore, or temporarily fall back to screen confirmation. Do not rely on the generic `illegal_change` path to explain "place the AI stone first."

### [Important] `PoseLostBanner` calls the geometry API incorrectly

Anchors: `plan.md:2625-2647`, `katrain/web/ui/src/api/geometryApi.ts:85-89`

`GeometryAPI.calibrate` requires a trigger argument, but Task 14 calls `GeometryAPI.calibrate()` with no argument. This will fail TypeScript. It also obscures the D2 hard rule.

Fix: call `GeometryAPI.calibrate('manual')` from the button and assert that render does not call it. Keep the explicit manual trigger in code and tests.

### [Minor] Vision bind/unbind is already duplicated in `GamePage`

Anchors: `katrain/web/ui/src/kiosk/pages/GamePage.tsx:42-48`, `katrain/web/ui/src/kiosk/hooks/useVisionSync.ts:72-112`, `plan.md:1164-1175`

`GamePage` calls `API.visionBind()` directly, and `useVisionSync()` also binds before opening `/ws/vision`. Once bind/unbind starts clearing LEDs and wrapping the state callback, duplicate calls become visible and make lifecycle bugs harder to reason about.

Fix: choose one owner. Prefer `useVisionSync` owning bind/ws/unbind, and remove the direct bind effect from `GamePage`, or make the backend bind hook idempotent for the same session.

## Things I checked that are okay

- `game_type` and `analysis_allowed` are already emitted by `WebKaTrain.get_state()` (`katrain/web/interface.py:464-465`). Task 9 only needs the TypeScript fields; no backend `get_state()` change is needed.
- Task 2's internal deque split is race-free for the current FastAPI usage: `poll_events()` and `get_confirmed_move()` run on the same asyncio loop, and the proposed drain has no awaits.
- `RequestRouter.route()` already implements the planned cloud-preferred behavior: `payload["is_analysis"]` uses cloud only if `cloud_client` exists, and board mode falls back to local (`katrain/web/core/router.py:10-19`).

## Suggested task-order changes

1. Redesign Q4 input blocking before Tasks 4/6/7. The current hold approach should not be implemented as written.
2. Fix Task 5 classification before wiring the orchestrator into bind.
3. Add the LED reassert/failsafe fix in Task 4, not Task 15.
4. Fold placement-target lamp suppression into Task 7, because masking alone is insufficient.
5. Fix `GeometryAPI.calibrate('manual')` in Task 14 before writing tests.
