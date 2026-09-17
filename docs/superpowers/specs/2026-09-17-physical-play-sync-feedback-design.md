# Physical Play Synchronization and Feedback Design

**Date:** 2026-09-17  
**Status:** Approved design, pending implementation plan

## Problem and evidence

The 2026-09-16 free-play game `game_2026-09-16_17-18-32_44659d86` exposed four related defects:

1. The stone sound can be delivered before the updated game state, so the sound is heard before the digital stone is painted.
2. The persistent “AI played” banner is absolutely positioned over the bottom of the board and is only cleared by an on-screen move, not by physical-board synchronization.
3. Off-centre stones can be reported together with `illegal_change`. The generic mismatch dialog and the off-centre card then compete, and the dialog can cover the lower-z-index card. A confidently detected stone on an adjacent intersection may only produce `illegal_change`, so it never reaches the existing `confidence == 0` off-centre path.
4. The reported 40–60 second late-game delays were dominated by unresolved board mismatches, not neural-network runtime. The recorded enhancement-plus-inference averages were about 331 ms before 60 stones and 384 ms from 120 stones onward, while moves 127, 149, and 153 remained in `illegal_change` for approximately 40, 47, and 60 seconds.

The box serves `katrain/web/static-kiosk-2d`, not `katrain/web/static`. A runtime `npm not found` warning alone does not prove the kiosk bundle is stale: `build_frontend()` currently checks for npm before checking whether the matching prebuilt bundle already exists. Deployment must nevertheless verify the actual kiosk bundle rather than silently accepting an unknown version.

## Goals

- Paint the digital move before its sound is played.
- Show the AI placement coordinate outside the board and keep it visible until the physical board is synchronized.
- Give one clear recovery instruction for an off-centre stone, without stacking it behind the generic mismatch dialog.
- Prevent an otherwise legal pending move from being presented simultaneously as a generic board mismatch.
- Validate late-game recognition by measuring synchronization latency separately from inference runtime.
- Make kiosk frontend deployment verifiable without requiring npm on the RK3562.

## Non-goals

- Rewriting the complete vision worker or board-state protocol.
- Adding another inference optimization before the synchronization defects are measured with the already-deployed board ROI motion gate.
- Automatically resolving arbitrary multi-stone board corruption.
- Changing desktop KaTrain audio behavior.

## Chosen approach

Apply a focused vertical fix across the existing web interface, kiosk UI, vision presentation layer, and board deployment script. Preserve existing event types where possible, add only the node identity needed to associate a sound with a painted position, and make the vision UI select one recovery surface by priority.

Frontend-only timing delays or z-index increases are rejected because they do not solve adjacent-intersection mismatches or guarantee that a sound belongs to the position already painted. A complete vision state-machine rewrite is also rejected as disproportionate.

## 1. Move sound synchronization

### Backend contract

Each web `sound` message for a played move will include the identity of the resulting node:

```json
{
  "type": "sound",
  "data": {
    "sound": "stone3",
    "after_node_id": 123456789
  }
}
```

`after_node_id` uses the same `id(current_node)` value already exposed as `game_state.current_node_id`. Existing clients remain compatible because the new field is additive.

For an AI move, the web interface will broadcast the resulting game state before emitting its sound. The web implementation will no longer emit the AI sound from inside `_do_ai_move`; `_do_ai_move_and_broadcast` will determine whether a move was committed, call `update_state()`, and then emit the sound for the resulting node. Desktop code remains unchanged.

### Frontend behavior

`useGameSession` will keep node-associated sounds in a FIFO. A sound is removed from the FIFO only when the committed `gameState.current_node_id` equals its `after_node_id`. Playback then uses two nested `requestAnimationFrame` callbacks: the first observes the React commit and the second runs after at least one paint containing that commit. This prevents back-to-back WebSocket handlers or React batching from making reordered messages audible before the board is visible.

If the sound arrives after the matching state is already committed, it follows the same post-paint scheduling path immediately. Messages without `after_node_id` retain the current immediate-play behavior for backward compatibility. The FIFO and scheduled animation-frame callbacks are cancelled when the session changes, `game_id` changes, or the connection closes, so no sound can leak into a later game.

## 2. AI placement status

The absolute bottom banner in `GamePage` will be removed. The same localized coordinate instruction will be passed to `GameControlPanel` as a transient physical-play status and rendered in the right rail's existing `.ghint` status slot.

Status priority in that slot is:

1. hardware fault;
2. pending AI physical-placement instruction;
3. login requirement;
4. minimum-move counting explanation.

When an AI move makes it the human's turn, `GamePage` stores:

- the formatted coordinate and stone color;
- the current AI node identity.

The node identity is also carried with the expected-board command sent to vision as `expected_node_id`. `VisionService`, both worker implementations, and `SyncStateMachine` preserve the identity that belongs to the expected board. This is the causal contract between the game and vision WebSockets: frontend receipt order is not used as proof that a physical synchronization belongs to a game node.

`expected_node_id` is updated on every expected-board command even when the stone matrix is unchanged (for example, a pass). The worker may still coalesce the expensive board/baseline reset for an unchanged matrix, but it must not coalesce away the revision update.

Each new `expected_node_id` arms one exact-match acknowledgement. On a later usable frame, `SyncStateMachine` compares `observed_board` with the expected matrix for that revision. If and only if the matrices are exactly equal, it emits one `synced` event containing that `expected_node_id` and marks the revision acknowledged. It emits this acknowledgement even when the state enum was already `SYNCED`; repeated expected-board commands for the same node do not re-arm it. Board loss, low-confidence degraded recovery, or a merely empty `placement_pending` classification cannot acknowledge the revision. Reset, unbind, and a different revision cancel the previous unacknowledged revision.

The hint is cleared only by `synced` whose `expected_node_id` equals the stored AI node identity. A stale event, an event for an earlier node, or an unversioned legacy event cannot clear it. The hint is also cleared on a new session, `game_id` change, game end, or leaving physical-play mode. It has no timer because the instruction remains relevant until the physical stone has actually been placed.

## 3. One vision recovery surface

`VisionSyncOverlay` will derive one `activeRecovery` value and present at most one blocking recovery surface. The priority order is:

1. capture handling;
2. off-centre stone correction;
3. generic board mismatch;
4. persistent board loss.

### Event rules and lifecycle

- `move_pending` records `(row, col, color)` and starts a four-second presentation deadline. A later candidate replaces it. It is cleared by a game-node advance, `ambiguous_stone`, `capture_pending`, `board_lost`, `synced`, or deadline expiry.
- While that deadline is active, `illegal_change` is suppressed only when `positions` contains exactly the pending `(row, col, color)` and `missing` is empty. Any additional position or missing stone is a real mismatch and is not suppressed.
- `capture_pending` clears pending, ambiguous, and mismatch presentation state and owns the surface. `captures_cleared` removes capture ownership; any remaining difference must arrive as a later event in the same or a later worker update before another surface opens.
- `ambiguous_stone` clears pending and mismatch state and owns the surface. With `unbacked=true` it shows the off-centre correction wording. With `unbacked=false` it retains the existing low-confidence confirm/ignore wording; weak confidence is not described as a physically off-centre stone.
- `illegal_change` is first tested for the conservative adjacent-relocation rule below. If it matches, relocation owns the surface; otherwise it becomes the generic mismatch only when capture or ambiguous recovery is not active.
- `board_lost` starts the existing persistence timer but is visible only when no higher-priority recovery owns the surface.
- `synced` clears pending, capture, ambiguous/relocation, mismatch, and board-loss presentation state. The AI placement hint has the stricter matching-node rule defined in Section 2.

Rendering follows `activeRecovery` rather than independent `open` flags. The off-centre and low-confidence prompts use the Material UI modal layer, so they cannot sit underneath `BoardMismatchDialog`.

### Adjacent-intersection relocation

The presentation layer will classify a simple mismatch as an off-centre relocation when all of the following are true:

- there is exactly one unpaired extra stone and one unpaired missing stone of the same color;
- their Chebyshev distance is one intersection;
- neither point is part of a pending capture.

The instruction names both positions, for example: “White stone is off-centre; move it from E1 to F1.” Once the user moves it, the normal `synced` event dismisses the prompt.

Any mismatch with multiple possible pairings, different colors, or a distance greater than one remains the generic board mismatch flow. This conservative rule avoids guessing during captures or genuine multi-stone corruption. The classifier is a pure frontend helper over `positions` and `missing`, independently unit-testable from modal state.

## 4. Late-game performance verification

No additional inference optimization is included in this change. The board ROI motion gate and the previously deployed split-decode, detection deduplication, CLAHE caching, and adaptive confirmation remain in place.

Diagnostics will report and evaluate independent measurements:

- frame cost: enhancement and inference duration;
- candidate confirmation latency: first `move_pending` for a coordinate to `Vision move submitted` or `ambiguous_stone`;
- board recovery latency: first targeted off-centre prompt to matching `synced` during the controlled device test.

The event pump log records the event timestamps, and the existing accepted-move log supplies the auto-accept endpoint. Human stone-placement time is not inferred from `set_expected_board`; the controlled device test records when the prompted correction is physically made.

Acceptance on an RK3562 with a representative board containing at least 120 stones:

- a single legal high-confidence move confirms within 1.2 seconds in the representative run;
- an unknown/low-confidence move retains the five-frame slow path;
- a clearly off-centre stone produces a targeted instruction within 3 seconds;
- motion outside the calibrated board does not postpone confirmation;
- enhancement plus inference averages approximately 410 ms or less, with p95 and individual spikes recorded separately;
- no move waits tens of seconds when the only physical difference is the legal new stone.

If these fail, diagnosis follows the event trace first (`move_pending`, `illegal_change`, `ambiguous_stone`, `synced`) rather than treating every delay as inference slowness.

## 5. Kiosk bundle deployment

Production ownership belongs to the existing `smartbox-software/provisioning/provision.sh --section katrain` path. KaTrain's legacy `scripts/board_upgrade.sh` is not a production SmartBox entry point and is not changed by this work.

Before the SmartBox tree is copied to the RK3562, the deployment host builds the strict board bundle inside the vendored KaTrain checkout:

```text
cd smartbox-software/vendor/katrain/katrain/web/ui
npm run build:smartbox-kiosk-2d
```

The existing strict `.smartbox-build.json` contract remains authoritative. For this deployment, “valid prebuilt bundle” means all of the following:

- `static-kiosk-2d/index.html` exists;
- `.smartbox-build.json` is exactly the schema-1 strict payload already required by `validate_smartbox_kiosk_build`;
- every entry asset referenced by `index.html` exists;
- after checksum-mode copy, SHA-256 for `index.html`, the manifest, and every referenced entry asset matches between the deployment host and RK3562.

The host copies the updated SmartBox tree and complete `static-kiosk-2d` directory, then the RK3562 runs `provisioning/provision.sh --section katrain`, which invokes the existing strict validation before installing/restarting anything. After validation, deployment restarts `smartbox-katrain` and `smartbox-kiosk`, performs an HTTP health check, forces Chromium to reload without cache, and verifies the loaded entry-asset filename against the deployed `index.html`. Failure of any step fails deployment.

On the RK3562, npm is optional when this valid prebuilt kiosk bundle is present. KaTrain runtime frontend checks will be reordered to check the correct bundle before checking for npm, removing the misleading warning without weakening the SmartBox strict manifest gate.

## Error handling

- A sound whose target node never arrives is discarded on connection close or session change; queued animation-frame callbacks are cancelled at the same boundary.
- A stale or reconnected vision event cannot clear a newly created AI placement hint unless its `expected_node_id` exactly matches that hint's node.
- An unresolved `move_pending` releases its narrow mismatch suppression after four seconds, preventing a stale candidate from hiding a genuine mismatch indefinitely.
- Ambiguous adjacent-stone pairings fall back to the existing generic mismatch dialog.
- A failed kiosk build, copy, checksum comparison, service restart, or reload is a failed deployment and is reported before device acceptance begins.

## Focused verification

### Backend

- Verify AI move messages broadcast the matching game state before the node-associated sound.
- Verify capture and ordinary stone sounds include the resulting node identity.
- Verify each expected-board revision emits exactly one node-associated `synced` acknowledgement only after exact observed/expected equality, including an unchanged-board revision update; degraded recovery alone must not acknowledge it.
- Preserve existing direct `_do_ai_move` behavior tests without changing desktop behavior.

### Frontend

- Verify a node-associated sound waits for the matching `game_update` and browser paint.
- Verify the AI placement instruction is in the right-rail status area, not over the board.
- Verify only `synced` carrying the matching `expected_node_id` clears the instruction; stale, unversioned, and different-node events do not.
- Verify hardware faults override the placement instruction.
- Verify capture, ambiguous/off-centre, mismatch, and board-loss transitions render exactly one recovery surface.
- Verify `unbacked=true` and weak-but-backed ambiguous events retain their distinct wording.
- Verify pending-candidate mismatch suppression uses the exact payload rule and expires after four seconds.
- Verify a one-intersection same-color extra/missing pair produces a relocation instruction, while ambiguous multi-stone differences retain the generic mismatch dialog.

### Device

- Reproduce an AI move and confirm board paint precedes sound.
- Confirm the right-rail coordinate remains until the matching physical stone is placed.
- Place one stone between adjacent intersections and confirm the targeted correction appears and automatically clears after correction.
- Repeat several moves on a 120-plus-stone position and record frame and interaction timings.

Only the focused Python and frontend tests for these behaviors, the real TypeScript build gate (`npx tsc -b`), the kiosk bundle build, and the representative device run are required. Existing unrelated full-suite failures are not part of acceptance.
