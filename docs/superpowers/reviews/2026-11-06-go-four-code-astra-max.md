# Four Go fixes — independent code review

Reviewer: independent Astra max reviewer, separate from the plan and implementation authors.

Initial reviewed range: `fb916f12516dd510080fb736a48a825dc206bc37..d7fce01102802f347b921f7f2e654099d75991da`.

Final reviewed product HEAD: `ae7adaf4fe7fb1bd358fddd8064bd6682b16e85d`.

**Final verdict: Approved.** Both substantive findings below were corrected and independently rechecked. No important or blocking finding remains in the four requested changes.

## Round 1 — ChangesRequired

Two substantive findings require narrow corrections. The other reviewed behavior has no additional blocking finding.

### V1 — Important: a confirmation from the previous game can enter a replacement game in the same session

- Location at the initial HEAD: `katrain/vision/service.py:148–160,171–176`; `katrain/web/server.py:5301`.
- Trigger: bind session S/game G1 and generate a stamped confirmation; `/api/new-game`, `/api/game/setup`, or SGF loading replaces `session.katrain.game` with G2 before the confirmation is consumed, without a vision bind.
- `capture_binding_source()` captures G2 with G1's still-current epoch. `source_is_current()` compares the captured identity only with the session's current identity; it never checks the identity saved by the actual bind. The handler therefore accepts the old epoch/revision token under a newly captured G2 source. Meanwhile the orchestrator's original G1 callback correctly fails its identity check, leaving physical updates permanently attached to an obsolete source until another bind.
- Independent reproduction: execute only the actual `_handle_confirmed_move` AST definition, with a recording submission stub, real `VisionService`, and no app/server/lifespan. Bind G1 → publish revision 1 → create `(epoch=1, revision=1, observation=5)` → replace game with G2 → call handler. Observed `old_game_confirmed_move_reached_submit_for_new_game=True`, `old_epoch_used=True`. A separate service harness observes `old_source_current=False` but `newly_recaptured_source_current=True` despite a different `_bound_game_identity`.
- Required correction: validate sources against both the bind's saved identity and the current authority; invalidate or explicitly rebind through the actual game-replacement lifecycle, including safe cleanup of the old physical wrapper/state. Ordinary confirmation/fetch must not renew an obsolete binding. Retain the existing current-source check within the actual submission boundary. A focused same-session replacement regression is sufficient.

### T1 — Important: an opened view remains loading after an existing remote territory request settles

- Location at the initial HEAD: `katrain/web/ui/src/features/aiLadder/useRankedTerritory.ts:46,68–70,103–104`.
- Trigger: remount/re-enter while the server reports an earlier request as `in_flight`; activate territory; the next quota poll reports completion. The activation writes `view.phase='loading'`, but successful polling updates only quota. The returned phase prioritizes that persistent view phase over the now-false remote flag.
- Independent reproduction: a single temporary Vitest hook test, using a minimal config without environment loading and fully mocked API calls, supplies `{remaining:1,in_flight:true}` → activate → advance 2 seconds → `{remaining:0,in_flight:false}`. `remaining` becomes 0 and no analysis POST occurs, but the assertion that phase leaves `loading` fails. At zero quota the button remains enabled by that phase while activation returns without a result or an honest exhausted/error state. Temporary harness files were removed immediately.
- Required correction: when the remote-only work settles, leave loading if there is no current local request or cached answer, preserving the user's dismiss intent. Do not automatically issue another paid request or introduce receipt persistence. Cover this one state transition, including zero remaining uses.

## Reviewed behavior without further blocking findings

- Both workers establish the exact confirmed point before the same frame's sync comparison; raw mismatch evidence and genuine other extra/missing points remain active. The finally path flushes changed digital authority before token release, and uncertain platform sends retain their existing gateway reconciliation context. The persistent room receive/catch-up boundary remains limited to the same room/session/game/auth identity.
- Ranked and Star territory cache and visibility are separate; close removes the Canvas overlay, delayed closed results stay hidden, and same-position cached review bypasses zero-quota request guards. Ranked `score_lead` comes from the same explicitly BLACK-perspective KataGo response and is finite numeric data or null; old receipts may omit it. Ownership counts remain labeled as points, not a score.
- The shared side-dialog class uses the existing transparent backdrop and right-side scrim. Its real-browser tests assert the 1024×600 board/dialog separation, and ROOT supplied a fresh two-scenario pass. This review does not substitute another design approval or a new visual pass.
- New ranked/rated setup defaults change only the two UI initial values. Countdown playback records success only after the media promise resolves; singleton ownership prevents old cancellation from stopping a new owner; current window/visibility/mute/generation guards and offset seeking use the existing sound asset and preferences.
- The review-home change is limited to the scoped 22px heading, 30px row, and 46px pagination area; existing layout and 44px pagination controls remain intact.

## Evidence and limits

Read the focused changed production paths and their regression assertions. ROOT's fresh integrated logs show 336 vision/backend tests, 34 selected territory/time API tests, 324 UI tests, strict smartbox 2D/SSO build checks, and two territory browser scenarios passing. These suites were not redundantly rerun by this reviewer; the two independent targeted reproductions above expose gaps not covered by those passing checks.

No product source was edited by this reviewer. No real application lifespan, hardware/audio/LED/game action, paid analysis, cloud data action, deployment, credential/environment read, prohibited data directory access, or full-tree status was performed. Original-image reference-veto and four-stone/approximately-15-second disappearance causes remain unresolved; RK speaker listening and native tab lifecycle were not independently verified here.

## Round 2 — Approved

### V1 closed — integrated commit `656e3a4a8b5b14c17c1e15f4928cba0c706116d4`

- Source capture is anchored to the bind's saved game identity; both `source_is_current` and expected-board publication require that identity to remain the current authority. Recapturing from an ordinary confirmation can no longer grant a replacement game the old epoch.
- The three existing game-replacement endpoints use a narrow lifecycle context. Actual object replacement invalidates the old epoch immediately, with source/epoch-checked loop cleanup for the old orchestrator and recovery state. Late cleanup cannot unbind a newer game. Unchanged-game operations keep their binding.
- `_do_new_game` now holds the existing game commit lock during replacement, in the same AI-lock → commit-lock order already used by the AI path. Submission guards recheck their original source inside the relevant existing commit boundary.
- `GamePage` passes the authoritative `game_id` to `useVisionSync`. A same-session replacement enters preparing and performs the normal bind/onBound sequence again, preserving the existing socket. A pending old-game response cannot mark the new game ready; its completion queues the new game's bind. This closes the otherwise permanent unbound-page regression.
- Independent fresh verification on the integrated commit: **8 backend cases passed** covering source recapture, the real handler/gateway, replacement while waiting for the local commit lock, normal rebind before/after delayed cleanup, and actual replacement locking; **7 binding hook cases passed**. The new wrapper publishes subsequent moves, while the old wrapper has no physical effect. The scoped diff check passed.

### T1 closed — integrated commit `ae7adaf4fe7fb1bd358fddd8064bd6682b16e85d`

- The successful quota poll now moves a remote-only loading view to idle when no request for the current quota scope or cached result owns that view. It preserves visibility intent, leaves normal local pending/result handling intact, and issues no analysis request.
- The implementation adds the single dismissal/zero-quota regression requested in Round 1. Independently reran the original failing open-view harness on the final integrated HEAD: **1 case passed**; remote completion leaves loading, zero remaining disables a new request, the still-open view remains open, and no analysis POST occurs. Evidence: `/tmp/go-four-code-review-t1-20261106.log`. Temporary harness files were removed.

Only the two corrections and their adjacent regression paths were rechecked; no redundant full-suite, visual redesign, device run, or release operation was added. The original-image and device-audio limitations above remain unchanged by this code approval.


## ROOT integrated verification after both corrections

Product code remains exactly the independently approved `ae7adaf4fe7fb1bd358fddd8064bd6682b16e85d`; the closing commit adds review records only.

- Vision/backend affected range: 344 passed (`/tmp/go-four-final-vision-20261106.log`).
- Exact territory and time-snapshot API nodes: 29 passed, existing datetime deprecation warnings only (`/tmp/go-four-final-territory-time-20261106.log`). Tests use synthetic SQLite/ASGI fixtures without the production lifespan.
- Main affected frontend selection: 326 passed in 12 files (`/tmp/go-four-final-ui-20261106.log`). The binding-specific selection also covers both `.test.ts` and `.test.tsx`: 7 passed in 2 files (`/tmp/go-four-final-binding-ui-20261106.log`); this overlaps the main selection and is not an additional disjoint total.
- `npm run build:smartbox-kiosk-2d`: passed TypeScript, Vite and strict Box SSO/2D boundary checks (`/tmp/go-four-final-smartbox-build-20261106.log`).
- Final merged-source territory preview: 2 passed using an exclusive Vite port and fully mocked API/WS (`/tmp/go-four-final-territory-preview-20261106.log`). Geometry/backdrop checks preserve the left board.
- Focused source working-tree diff is clean. Review/plan records are retained on `fix/go-kiosk-four-issues-20261105` in `/tmp/katrain-go-four-fixes-20261105`.

This request's work is implemented and independently reviewed, but has not been pushed, merged to develop, deployed to servers, or installed on RK3562. Device speaker listening and the two original-image-dependent missing-stone investigations remain as stated above. No tests were expanded into a full application startup, production database change or hardware action.
