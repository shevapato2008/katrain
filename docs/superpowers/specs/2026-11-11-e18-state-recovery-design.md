# E18 restoration and authoritative game state

Status: ready for the parent-coordinated independent Astra Max review (at most two rounds); implementation has not started.

## Goal and scope

When White E18 is already move 16 in the game, replacing that physical stone restores move 16. The electronic board, history and turn must show move 16 / Black to play; the next legal Black move (move 17) must work. Restoration never submits another White move. Recovery must show pending, success or a retryable error honestly and must not repeatedly reopen an identical stale dialog.

This is task A only. Task B remains a separate investigation. Do not modify reference capture/adoption, veto rules, averaging, model thresholds, calibration, camera geometry or training. In particular, do not merge/cherry-pick diagnostic commits `13a58e39`, `92e3930ad` or `4097`.

Implementation base: clean `origin/develop` `97f4b49e1ff31c66a2b4c6c1c7de1d569e7f4cb2`, branch `fix/e18-state-recovery-20261111`, worktree `/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/e18-state-recovery-20261111`. Base 97 already locks `get_state`; the incident's deployed interface did not. That base improvement alone does not serialize snapshot capture plus callback publication.

## Evidence and remaining uncertainty

The separate report is `/Users/fan/Repositories/katrain-kiosk-debug/output/diagnostics/reference-trace-20261111/mismatch-live/independent-e18-recovery-findings.json`. Trace event 40 expected White E18 at node 16; events 41/42 confirmed Black C16 while E18 was White. Recorded server logs rejected Black because cached turn was White. At 19:18 the UI still showed history 15 and missing White E18. At 19:32:13, after the user replaced E18, `e18-replaced-20261111-193213/status.json`, `screen.png` and `warped.jpg` prove physical E18 White, 16 detected stones, vision synced, no popup, yet UI history 15 / White thinking. Current live in-memory cursor was not directly inspected at that later moment.

Two controlled reproductions independently established reachable faults: (1) a node-15 snapshot callback can publish after node 16; (2) GET sanitization can capture cache 15, observe a concurrent publication 16, then write sanitized 15 back. Neither reproduction proves which precise interleaving happened in the incident. Both must be closed.

## Minimal design

### Serialize local snapshot publication; do not order by node depth

Extend the existing runtime `ai_ladder_commit_lock` across `_broadcast_current_state`'s fresh `get_state()` and synchronous state callback/scheduling. Release it before post-broadcast hooks and before any socket I/O. A snapshot cannot be captured at 15, allow the commit/publication of 16, and then publish 15. Legitimate undo, redo and navigation remain valid because there is no depth comparator or new state-version framework.

Keep the existing throttle lock limited to throttle bookkeeping; release it before acquiring the commit lock. The callback chain `_on_state → _schedule_broadcast` schedules asynchronous sends without awaiting; the physical-play wrapper schedules to its loop when necessary. Do not add acquisition of `session.lock` in this callback. Existing mutation order is `session.lock → ai_ladder_commit_lock`; service metadata is acquired after commit and must never acquire game/session locks in reverse. Audit `on_session_state` hooks and existing post-broadcast move-sound callbacks before landing. Test serialized publication with real barriers and bounded joins, including a contending legitimate navigation.

`session_state_for_read` returns a fresh runtime snapshot for local sessions, and uses the central mirror for `pvp_lobby`. Construct a response copy, preserve the existing `legacy_analysis_allowed` / `strip_private_analysis` rules and response metadata, and never write that projection back to `session.last_state`. Preserve timer freshness and privacy/billing restrictions. No request-specific filtering belongs in the canonical cache.

### Use current authority for the normal vision turn check

Replace the ordinary/non-ranked cached `last_state.player_to_move` precheck with a live local next-player read under the existing commit lock; use the central mirror for `pvp_lobby`. Recheck the captured binding/session/game generation before acting. Keep the final guarded play and its live turn/AI/endgame checks. A stale cache saying W cannot reject B17 after live W16. Do not bypass human-seat guards or allow physical White input on the AI seat.

### A scoped restoration operation, preserving legacy reset semantics

Extend the existing `/api/v1/vision/sync/reset` request with optional `session_id` and `game_id`. The mismatch UI supplies both; this opts into a bound-game restoration path. Existing unscoped digital reset and `adopt=physical` retain their behavior, including RESET_SYNC's digital∪physical detector baseline. Do not alter that baseline or reference invalidation policy in task A.

The scoped restoration path deliberately uses the existing `SET_EXPECTED_BOARD(force_rearm=True)` publication, not RESET_SYNC. Its purpose is to reconcile the currently authoritative board, not to adopt observed extras or invalidate references. This prevents a legal, already-present B17 from being silently absorbed into a reset union. The existing detection path owns any new move; restoration itself never calls `play`.

Under the commit lock: validate the captured vision binding source, runtime game object and requested game ID; obtain fresh authority; synchronously publish the same snapshot to the canonical/UI callback; reconcile the planner to that snapshot and remove only the existing lag/removal recovery gate appropriate to this path. Do not clear game-over, hint, USB, geometry, engine-error or remote-disconnect gates. Enqueue fresh expected via the existing source/generation guards. Release all thread locks before waiting.

One active scoped restoration per bound game is sufficient. Generate an opaque `recovery_id` and register its waiter before enqueueing. Carry it on SET_EXPECTED_BOARD and on the sync state's pending exact-match acknowledgment. Normal expected publications during this same recovery carry the same ID with their current node/revision, so a legitimate B17 can advance normally and the waiter follows the current same-game position. Emit acknowledgment only from a processed exact-equality frame, not from status=`synced`, reset, legacy unversioned events or a stale queued event. This adds acknowledgment metadata only; stone classification and confirmation rules do not change.

Observe acknowledgments in `VisionService._drain_worker` without stealing them from the normal vision pump. Match recovery ID, binding epoch, expected revision and node. One waiter/future, cleaned on success, failure, unbind, replacement or timeout, is enough; do not add a general recovery framework. Bound the whole operation to eight seconds using one original deadline. Revalidate the same binding/game and current node/revision after acknowledgment before success; a newer same-game expected position continues within that deadline. Rebind/replacement or conflicting request is HTTP 409; unavailable worker is 503; timeout is 504. No false `{ok:true}`.

Success returns `{ok:true,recovery_id,session_id,game_id,current_node_id}`. The UI refreshes state through existing `API.getState(sessionId, token)` / session state setter so privacy filtering stays on the normal route. A game that advanced legitimately is accepted at its new current node; there is no expectation that the stale UI node ID equal the recovery target.

### Existing UI, honest feedback

Reuse BoardMismatchDialog, its buttons and caption/error text. While a scoped restoration and state refresh are pending, keep one dialog visible, disable repeated taps and show “正在核对盘面…”. A network error, timeout or wrong-game response leaves a retry action and explicit error; it must not claim success or suppress all future actionable differences. Coalesce identical incoming mismatch events into that visible operation. On success apply fresh state before clearing the dialog. Ignore responses after session/game changes.

Automatic physical restoration without a tap also matters: when a genuine `synced` event resolves an active mismatch, refresh the current game through the same parent callback. Clear the stale checklist after successful refresh; retry/error feedback remains available if refresh fails. A late unversioned event must not complete an active scoped request before its matched acknowledgment.

Use refreshed `player_to_move` for the existing single-extra adopt button: one extra Black stone is adoptable only when it is actually Black's human turn; missing E18 never offers adopt. Do not silently adopt or deny a physical stone. Existing captures, pending platform moves, phantom-denial and local-confirmation ownership remain intact.

## Acceptance and proportional verification

1. Deterministic barriers prove both original corruption schedules fail after the fix; legitimate undo/redo still publishes.
2. Cache W / live B after White E18 accepts legal Black move 17 exactly once, while AI-turn and wrong-game input remain rejected.
3. Physical E18 restoration reconciles node16 without calling play. Success requires current exact observation plus coherent refreshed UI; stale ack, bind/game change, absent worker and timeout cannot return success.
4. A pending next Black stone is neither lost in a union baseline nor committed by restoration; ordinary confirmation submits it once and recovery follows the resulting current position.
5. Focused existing privacy, post-broadcast sound, routing, capture/phantom, binding and recovery tests pass. No full GPU test or broad new infrastructure is required.
6. One 1024×600 preview using existing dialog style covers pending and retry/error, plus the final electronic node16/B-turn state; focused Vitest assertions cover the remaining concurrency states.

The parent coordinates one fresh independent Astra Max plan review (maximum two rounds), then SDD implementation and final independent Astra Max code approval. No implementation begins before that approval. Release requires a separate freshly reviewed guarded device plan and an idle device; no device action is authorized by this document alone.
