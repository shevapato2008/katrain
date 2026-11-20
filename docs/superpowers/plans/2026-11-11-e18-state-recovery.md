# E18 State Recovery Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore White E18 as the existing move 16, synchronize electronic state and turn, and accept the next legal Black move with honest bounded recovery feedback.

**Architecture:** Serialize local snapshot capture and callback publication with the existing commit lock; keep GET response filtering out of canonical cache writes. Restore from a current bound-game snapshot and existing expected-board publisher, with one finite exact-frame acknowledgment and the existing UI. Legacy RESET_SYNC union/reference behavior stays unchanged.

**Tech Stack:** Existing Python runtime/FastAPI/vision command queue, pytest, React/TypeScript/MUI/Vitest; existing Playwright preview harness only.

---

## Chunk 1: Task A only — authoritative publication and restoration

Read `../specs/2026-11-11-e18-state-recovery-design.md` first. This chunk is below 1000 lines. Do not touch reference capture/adoption/veto/averaging/model rules. No source from diagnostic branches is a dependency.

Review status: all round-1 R1–R3 findings are incorporated together; the next independent plan review is round 2/final. No further plan review loop or implementation is authorized before its result.

### Ownership and dependency order

Task 1 owns `interface.py`, session scheduling/send serialization in `session.py`, the GET helper in `server.py`, and publication/privacy tests. Task 2 owns only `_submit_confirmed_move` in `server.py` and its poller tests; run after task 1 because they share a file. Task 3 owns service/sync/worker acknowledgment metadata, orchestrator and endpoint, and related Python tests. Task 4 owns frontend API/dialog/overlay/GamePage and the `useGameSession` receive-generation fence/tests. Tasks 3 and 4 may run in parallel only after their request/result and callback contracts below are fixed; each gets a fresh bounded implementer. Parent controls one final integration and review, with no extra reviewer loops beyond the authorized workflow.

### Task 1: Prevent both publication/cache regressions

**Modify:** `katrain/web/interface.py:_broadcast_current_state`; `katrain/web/session.py:WebSession/_schedule_broadcast/_broadcast_payload`; `katrain/web/server.py:session_state_for_read`.
**Tests:** extend `tests/web_ui/test_move_sound_order.py`; create `tests/web_ui/test_state_publication_order.py`; extend `tests/web_ui/test_paid_analysis_guards.py` only as needed for the response/canonical distinction.

- [ ] Add a real-runtime test with an old broadcaster paused after snapshot capture; start a thread attempting W16 commit/new publication. In the fixed behavior it cannot overtake the old callback; release old, join both with a two-second failure bound, and assert callback order `[15,16]`, canonical16 and scheduled UI16. Do not assert scheduler timing using sleeps. Test navigation/undo after16 publishes15 legitimately and post-broadcast sound remains after its matching state.
- [ ] Add the reviewer's actual asyncio scheduling regression: background old15 calls the real `_schedule_broadcast`, then the currently running loop callback publishes16 before yielding; assert callback order and fake-socket receive order `[15,16]`. Use Events/loop turns, not timing sleeps. Repeat with two fake sockets, a yielding first send, and a matching sound payload; each socket must see ordered states before that sound.
- [ ] Add a GET test which blocks `strip_private_analysis` after capturing15, publishes16 through the real manager callback, resumes the GET, and asserts canonical remains16 even if response reflects its captured snapshot. Also assert a subsequent local GET reads current16, and that sanitizing response metadata/analysis never mutates or replaces canonical. Preserve `pvp_lobby` mirror selection and existing clock behavior.
- [ ] Run `CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/web_ui/test_state_publication_order.py`; expect the corruption assertions to fail on the baseline.
- [ ] Implement the critical section exactly at snapshot+callback scheduling, using the existing RLock:

```python
with self.ai_ladder_commit_lock:
    callback = self.update_state_callback
    if callback is None:
        return
    state = self.get_state()
    callback(state)
self._run_post_broadcast(post_broadcast, state)
```

Do not hold `_broadcast_lock` or perform socket I/O here. Audit callback hooks for `session.lock` inversion; maintain `session.lock → commit → metadata`. Existing manager lock use must remain nonblocking beyond lookups/scheduling; do not wait on futures inside the callback. Make `_schedule_broadcast` use `loop.call_soon_threadsafe` to create the send task for both on-loop and off-loop callers, retaining error reporting. Add one per-session async send lock around `_broadcast_payload` socket iteration so yielding/multi-socket sends preserve enqueue order. Never await this lock while holding the commit lock; creation callbacks only schedule tasks. Keep state and post-broadcast sound on this same queue path.

- [ ] In the GET helper obtain fresh runtime state for local authority (central mirror for `pvp_lobby`), build an independent response projection, apply existing privacy filter and response metadata, and delete sanitization's `session.last_state = state`. Do not broaden analysis eligibility or billing behavior.
- [ ] Run `CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/web_ui/test_state_publication_order.py tests/web_ui/test_move_sound_order.py tests/web_ui/test_paid_analysis_guards.py tests/web_ui/test_session_broadcast_surface.py`; expect all pass. Inspect failures for assumptions about barriers now inside the commit lock; update test scheduling without weakening sound-order assertions.
- [ ] Commit only these owned source/test paths: `git commit --only <explicit-paths> -m 'serialize game state publication and isolate read projections'`.

### Task 2: Check vision turns against current authority

**Modify:** `katrain/web/server.py:_submit_confirmed_move` normal non-ranked cached-turn precheck only (the outer dispatcher is `_handle_confirmed_move`).
**Tests:** `tests/test_vision_move_poller.py`; reuse existing binding/generation and live-guard fixtures.

- [ ] Add cases with cached node15/W but live node16/B (White E18 already recorded). Confirmed Black move17 reaches guarded play exactly once; no White play is issued. Add live W/AI and stale binding/game cases which remain rejected, and central `pvp_lobby` authority selection.
- [ ] Run `CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/test_vision_move_poller.py -k 'stale or turn or generation or binding'`; expect new stale-cache acceptance case to fail initially.
- [ ] Read live next player inside `ai_ladder_commit_lock` for local game, recheck `current()` there, and retain final session/commit guarded play. Do not use a cached-color rejection before that live read. Preserve rejection rearming and throttle behavior.
- [ ] Run `CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/test_vision_move_poller.py`; expect pass. If combined imports contaminate `WebKaTrain`, run the affected class in a separate pytest process, as baseline evidence requires; do not modify production logic for a mocked import failure.
- [ ] Commit only `server.py` and its owned poller tests with `git commit --only ... -m 'check physical moves against the live turn'`.

### Task 3: Scoped bound-game restoration with exact-frame acknowledgment

**Modify:** `katrain/web/api/v1/endpoints/vision.py:ResetSyncRequest/reset_sync`; `katrain/web/core/physical_play_orchestrator.py` restoration method alongside legacy `resync`; `katrain/vision/service.py:publish_expected_from_stones/_drain_worker`; `katrain/vision/sync.py:set_expected_board` and exact-equality acknowledgment; `katrain/vision/worker.py` and `worker_inprocess.py` SET_EXPECTED_BOARD argument/event metadata only.
**Tests:** `tests/test_physical_play_recovery.py`, `tests/test_physical_play_orchestrator.py`, `tests/test_vision_api.py`, `tests/test_vision/test_worker_commands.py`, `tests/test_vision/test_sync.py`, `tests/test_vision_bind_state.py`.

**Frozen contract:** Scoped body `{adopt:'digital',session_id:string,game_id:string}`; legacy bodies remain supported. `session_id` and `game_id` are required together: partial scoped input fails 400/422 rather than using legacy fallback. Success `{ok:true,recovery_id:string,session_id:string,game_id:string,current_node_id:number}`. Failures use 409 source/game change or in-flight conflict, 503 worker unavailable, 504 eight-second timeout. State remains on ordinary authenticated `getState`. Neither request nor response requires the obsolete UI current node to equal live authority.

- [ ] Add endpoint/orchestrator tests for cache15/live16, physical restored16, no play calls; wrong bound session/game; worker absent; stale/bare ack; timeout; rebind/replaced game during wait; duplicate request; partial identity body; observation success. Assert no thread lock is held over await and no success precedes exact processed observation.
- [ ] Add a pending legal B17 case: restore does not RESET_SYNC or adopt/deny/play that stone; normal confirmation advances to17 once; current expected publication carries recovery identity and success follows the exact observed current17. Add captured leftover/phantom baseline regression assertions to existing legacy reset tests.
- [ ] Run `CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/test_physical_play_recovery.py tests/test_vision_api.py`; expect scoped success/guard/ack tests to fail initially.
- [ ] Implement one scoped restoration operation. Capture source/game and register a single `recovery_id` waiter before enqueue. Under commit lock reread authority, publish it via runtime callback, reconcile only the relevant existing lag/removal gate, and call source-guarded `publish_expected_from_stones(..., force_rearm=True)`. Do not call legacy `resync`/RESET_SYNC in this scoped path. Leave legacy digital/physical reset untouched.
- [ ] Add optional recovery ID metadata to SET_EXPECTED_BOARD and sync pending acknowledgment. Normal publications for the active same-game restoration retain that ID. Existing epoch/revision validation still runs first in both worker paths. Exact equality emits `{expected_node_id,recovery_id}` with event epoch/revision; placement-only, reset/status synced and stale events cannot fulfill it. Do not change classification or confirmation branches.
- [ ] In service drain, observe the matching event before retaining it for the pump. Resolve one bounded waiter on its captured loop safely; preserve normal event delivery and do not consume moves. Clear waiter on unbind/replacement/failure/timeout. Use an original eight-second deadline; after ack reread current source/node/revision under commit lock and continue for a newer same-game expectation within that deadline. Retain/recheck a matching newer acknowledgment that already arrived before target advancement; do not wait for it a second time. Never acquire commit/session locks from inside service metadata lock.
- [ ] Return success only for matched current expectation. Publish/refresh canonical UI state from the same current authority before success; propagate queue/worker failure rather than swallowing it. Preserve privacy by returning only identity, followed by existing filtered GET.
- [ ] Run, in separate processes if baseline import contamination appears:

```bash
CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/test_physical_play_recovery.py tests/test_physical_play_orchestrator.py
CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/test_vision_api.py tests/test_vision_bind_state.py
CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/test_vision/test_worker_commands.py tests/test_vision/test_sync.py tests/test_vision/test_sync_regressions.py
```

Expected: pass including existing capture/union/reset/generation tests. No model/camera test or new benchmark is needed.

- [ ] Commit only task 3 owned paths with `git commit --only ... -m 'verify scoped physical board restoration against current game'`.

### Task 4: Pending/error/success in the existing dialog

**Modify:** `katrain/web/ui/src/hooks/useGameSession.ts`; `katrain/web/ui/src/api.ts`; `katrain/web/ui/src/kiosk/components/vision/VisionSyncOverlay.tsx`; `.../physical/BoardMismatchDialog.tsx`; `.../vision/visionRecovery.ts`; `.../pages/GamePage.tsx`; localized user-visible strings in the existing locale files used by these components if keys need registration.
**Tests:** `.../vision/VisionSyncOverlay.test.tsx`; `.../vision/visionRecovery.test.ts`; `.../kiosk/__tests__/BoardMismatchDialog.test.tsx`; `.../pages/GamePage.test.tsx`; extend `katrain/web/ui/src/hooks/useGameSession.test.ts` and reuse `useGameSession.navigation.test.tsx` for navigation assertions.

- [ ] Add Vitest cases: restore waits for HTTP and fresh state; keeps dialog pending and disables duplicates; failures remain visible/retryable; identical mismatch events coalesce; late bare synced cannot falsely finish pending scoped recovery; bare/stale/placement-only synced starts the same scoped verifier and cannot clear through GET alone; exact-frame auto verification completes without tapping even after the old node acknowledgment was consumed; changed session/game ignores old completion. Confirm missing E18 never calls play/adopt, while refreshed B turn makes the existing single-extra B adopt action eligible. Preserve platform pending-stone behavior. Add deferred GET16 → received WebSocket17 → resolve GET16 and legitimate undo17→16 cases: old GET never applies, and a response superseded by a different verified node cannot count as completion. Test the sufficient-current-state case separately. Existing BoardMismatchDialog baseline assertions drift from rendered “多出 黑 Q4” and “确实落在这里？采纳为我的落子”; adjust semantic matchers in these owned tests, not product copy.
- [ ] Run `npm test -- src/kiosk/components/vision/VisionSyncOverlay.test.tsx src/kiosk/components/vision/visionRecovery.test.ts src/kiosk/__tests__/BoardMismatchDialog.test.tsx` in `katrain/web/ui`; expect new assertions to fail initially.
- [ ] Type the scoped recovery request/result in `api.ts`, preserving existing callers. Add `gameId` and a parent `onRefreshState(verifiedIdentity)` callback returning the hook’s applied/already-current/superseded result to overlay. Expose a small `refreshStateForRecovery(verifiedIdentity)` method from `useGameSession`; GamePage delegates to it. The hook owns GET and captures a receive-generation before starting, incremented synchronously at authoritative state acceptance and session/game replacement. Do not use an effect-only counter that can lag a message callback. Superseded GET never applies; return applied, already-current (only same game/node as exact verified result), or superseded. A different current node yields one visible retryable changed-position error, never false completion. Bound refresh to two seconds and reject late completion. No depth comparator; legitimate undo/navigation increments the same local generation. Reuse current button/caption/error typography for pending/retry. Await scoped response, then state refresh, then clear; do not catch-and-ignore failures. Treat auto synced only as a trigger for this identical scoped verifier, then fenced refresh. Prevent the reducer from eagerly clearing an active mismatch on bare synced, coalesce all identical pending triggers, and do not automatically retry a failed operation forever. Keep reducer ownership and existing pending stone state; no new global state framework.
- [ ] Run `npm test -- src/kiosk/components/vision/VisionSyncOverlay.test.tsx src/kiosk/components/vision/visionRecovery.test.ts src/kiosk/__tests__/BoardMismatchDialog.test.tsx src/kiosk/pages/GamePage.test.tsx src/hooks/useGameSession.test.ts`; expect pass. Reuse the existing node_modules link; do not run npm install. Run `npm run build:smartbox-kiosk-2d`; expect TypeScript/build/verification pass.
- [ ] Use the existing local preview harness at 1024×600 for one representative pending/error composition and recovered node16/B-turn. Capture one sheet or screenshot pair, inspect touch targets/text/no duplicate modals, and reuse existing styles. Do not expand to all game states or change visual design. No current device navigation.
- [ ] Commit only task 4 owned paths with `git commit --only ... -m 'show verified board restoration progress and retry'`.

### Task 5: Integration and independent final approval

- [ ] Run the task 1, task 2, task 3 focused commands above in independent pytest invocations, and task 4 Vitest/build once after final integration. Existing baseline is 109 pass plus three `TestLiveTurnAccessor` MockTypeError failures when mixed imports are combined; those three pass alone. Treat that as known test-isolation contamination, not a new product failure.
- [ ] Exercise one deterministic end-to-end test using real game/session publication plus fake worker observations: W E18 committed16, stale cache/UI15 injected, physical E18 restored, scoped recovery publishes16 and receives exact ack, UI refreshes16/B, next confirmed legal B17 accepted once. Add to `tests/test_physical_play_recovery.py`; no hardware/model fixture.
- [ ] Inspect `git diff --stat` and `git diff --check`. Confirm no changes to reference/model/averaging rules and no diagnostic commits or unrelated dirty files included.
- [ ] Parent obtains final independent Astra Max code approval covering the two corruption schedules, actual socket send order, same-game GET/WS fence, verified automatic recovery, lock order, stale-turn acceptance, request identity/ack timeout, privacy and preserved legacy reset/pending-stone semantics. Resolve required findings within authorized review limits. Do not self-approve or ask user to reauthorize execution.

### Task 6: Guarded release handoff (parent owned; no live changes now)

- [ ] Prepare and independently review a fresh concrete RK3562 deploy plan before touching the active device. Reuse existing reviewed runtime/operator primitives; do not build a deploy framework. Device must be normally idle. First stop the owned temporary trace, collect its evidence, and restore the three owned trace source changes, verifying exact backups/hashes and no other changes. Preserve authentication/billing, new calibration, DB, USB, voice and kiosk residents. The active incident game must not be changed or silently restarted.
- [ ] Fetch and merge current `origin/develop` into the fix branch, resolve conflicts and rerun affected focused checks, then commit/push feature branch. Never cherry-pick/merge the temporary diagnostic branch.
- [ ] Merge the approved feature into `develop` and push. Update `smartbox-software/vendor/katrain` to that published develop commit and commit/push only that gitlink on parent main, preserving unrelated dirty lobby work.
- [ ] Deploy that integrated release to RK3562 only (latest explicit user scope overrides repository cloud defaults) with the freshly reviewed guarded plan. Verify deployed source/build commit, healthy resident services, actual representative kiosk page and the restoration/B17 acceptance journey when a user-safe idle test is available. Report any unperformed device acceptance honestly; do not label a feature-branch deployment as develop integration.
- [ ] Report feature, develop and parent gitlink commits plus device version and focused verification. Task B stays separate and unimplemented.
