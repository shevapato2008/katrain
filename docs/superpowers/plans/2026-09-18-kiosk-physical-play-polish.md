# Kiosk Physical Play Polish Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix transient board-reacquired notifications, make kiosk move sounds wait for the visible Canvas, add final-five-second countdown audio, and make the vision reset action understandable and visually centered.

**Architecture:** Correct the false board-loss input at the shared worker gate, while preserving true camera/pose failures in both worker implementations. Add an opt-in kiosk-only paint acknowledgement to the shared game-session sound queue, reuse the existing sound preference path for countdown audio, and extend the shared pagebar action with an optional visible label without changing other icon-only actions.

**Tech Stack:** Python 3, pytest, React 18, TypeScript, Vitest/Testing Library, Vite CSS.

---

## Chunk 1: Vision event correctness

### Task 1: Do not report motion-gated frames as board loss

**Files:**
- Modify: `katrain/vision/gating.py`
- Modify: `katrain/vision/worker.py`
- Modify: `katrain/vision/worker_inprocess.py`
- Test: `tests/test_vision/test_gating.py`

- [ ] **Step 1: Write the failing gate tests**

Add tests for a small shared predicate that decides whether the current capture cycle may feed the sync state machine:

```python
def test_unstable_camera_frame_is_skipped():
    assert not should_feed_sync_frame(frame_present=True, motion_stable=False)

def test_camera_dropout_and_stable_frame_are_observations():
    assert should_feed_sync_frame(frame_present=False, motion_stable=False)
    assert should_feed_sync_frame(frame_present=True, motion_stable=True)
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `uv run pytest tests/test_vision/test_gating.py -q`

Expected: FAIL because `should_feed_sync_frame` does not exist.

- [ ] **Step 3: Implement the shared predicate and wire both workers**

Add the predicate to `gating.py`. In each worker, evaluate motion stability once per frame and call `SyncStateMachine.update` only when the session/monitor gate is open and the frame predicate permits it. A missing frame and a stable frame with failed board transform must still call the state machine with `board_detected=False`; a present but motion-unstable frame must not call it. Keep the copied worker loops behaviorally identical.

- [ ] **Step 4: Run focused vision tests and verify GREEN**

Inspect both worker call sites in the focused worker test: a present, motion-unstable frame must bypass
`SyncStateMachine.update`, while a missing frame and a stable transform failure must still be forwarded as loss
observations. The shared predicate has exhaustive truth-table coverage; do not duplicate the full capture loop in a
test fixture.

Run: `uv run pytest tests/test_vision/test_gating.py tests/test_vision/test_sync.py tests/test_vision/test_sync_regressions.py tests/test_vision/test_worker_commands.py -q`

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add katrain/vision/gating.py katrain/vision/worker.py katrain/vision/worker_inprocess.py tests/test_vision/test_gating.py
git commit -m "ignore motion frames in vision sync"
```

## Chunk 2: Audio follows the visible board

### Task 2: Add kiosk-only Canvas paint acknowledgement for move sounds

**Files:**
- Modify: `katrain/web/ui/src/hooks/useGameSession.ts`
- Modify: `katrain/web/ui/src/hooks/useGameSession.sound.test.tsx`
- Modify: `katrain/web/ui/src/components/Board.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`
- Test: `katrain/web/ui/src/components/Board.endResultOverlay.test.tsx`
- Test: `katrain/web/ui/src/kiosk/pages/GamePage.test.tsx`

- [ ] **Step 1: Write failing sound-queue tests**

Extend the hook harness so it can opt into `deferMoveSoundUntilPaint`. Add both event orders:

```text
sound -> game state -> no playback -> acknowledge matching painted node -> paint-frame delay -> playback
game state -> acknowledge painted node -> sound -> paint-frame delay -> playback
```

Also assert that a mismatched paint acknowledgement does not release the sound, and that session/game/socket cleanup clears both queued sounds and paint acknowledgement state. Existing default-mode and legacy sound tests must remain unchanged.
Assert strict mode drops a stale queued sound when the committed/painted node advances, and that a matching
acknowledgement schedules playback on the next animation frame. Keep the existing default mode's two-frame behavior.

- [ ] **Step 2: Run the sound tests and verify RED**

Run: `cd katrain/web/ui && npm test -- --run src/hooks/useGameSession.sound.test.tsx`

Expected: FAIL because the option and acknowledgement API do not exist.

- [ ] **Step 3: Implement the opt-in hook contract**

Add `deferMoveSoundUntilPaint?: boolean` to `UseGameSessionOptions`, defaulting false. Return a stable `acknowledgePaintedNode(nodeId)` callback. In strict mode, `flushQueuedSounds` requires both committed-node and painted-node equality before scheduling playback; default mode retains existing behavior. Clear paint state anywhere queued sound state is cleared and when the game changes. Preserve legacy sounds without `after_node_id`.

- [ ] **Step 4: Write and run a failing Board callback test**

Add an optional `onNodePainted` prop and test that the callback is not yet available/used. Run the focused Board test and confirm RED.

- [ ] **Step 5: Implement Board and kiosk wiring**

After the 2D Canvas finishes drawing a `gameState`, invoke `onNodePainted(gameState.current_node_id)` when the ID is numeric. Kiosk `GamePage` enables strict sound deferral and passes the hook acknowledgement callback to its single visible 2D Board. Do not wire Galaxy, Board3D, ZenMode, or hidden renderers.
Add a `GamePage` wiring assertion for the strict option and callback. In the Board test, spy on the Canvas draw path so
the acknowledgement is observed only after the matching node render completes.

- [ ] **Step 6: Run focused frontend tests and verify GREEN**

Run:

```bash
cd katrain/web/ui
npm test -- --run src/hooks/useGameSession.sound.test.tsx src/components/Board.endResultOverlay.test.tsx src/kiosk/pages/GamePage.test.tsx
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```bash
git add katrain/web/ui/src/hooks/useGameSession.ts katrain/web/ui/src/hooks/useGameSession.sound.test.tsx katrain/web/ui/src/components/Board.tsx katrain/web/ui/src/components/Board.endResultOverlay.test.tsx katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/pages/GamePage.test.tsx
git commit -m "sync kiosk move sounds with board paint"
```

## Chunk 3: Countdown audio

### Task 3: Play the existing countdown sound during kiosk byoyomi

**Files:**
- Modify: `katrain/web/ui/src/hooks/useSound.ts`
- Modify: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.playAi.test.tsx`

- [ ] **Step 1: Write failing countdown behavior tests**

Mock `useSound` at the component boundary and drive fake time through a non-local timed game. Assert one playback for each remaining second 5, 4, 3, 2, 1; no duplicates during sub-second renders; reset after the timer leaves the countdown zone; and no playback when `timer.settings.sound` is false, the seat is inactive, the timer is paused, or the clock is not in byoyomi.
Drive the clock into a second byoyomi period and verify 5 can be announced again. Reuse the existing `useSound` and
`audioPrefs` unit coverage for the device-level SFX preference rather than duplicating that hook test here.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `cd katrain/web/ui && npm test -- --run src/kiosk/components/game/GameControlPanel.playAi.test.tsx`

Expected: FAIL because kiosk has no countdown playback.

- [ ] **Step 3: Register and play the existing audio asset**

Add `countdownbeep` to `SoundName` and `SOUND_FILES`. In `SeatRow`, use `useSound` and an effect keyed by the active byoyomi second. Require `timer.settings.sound === true`; `useSound` supplies the device-level `sfx` gate. Reset the per-seat last-second ref outside the 5-to-1 window so a new period can announce again. Do not alter the local-PvP `PlayerRow` path.

- [ ] **Step 4: Run focused clock/audio tests and verify GREEN**

Run:

```bash
cd katrain/web/ui
npm test -- --run src/kiosk/components/game/GameControlPanel.playAi.test.tsx src/kiosk/components/game/GameControlPanel.clock.test.tsx src/utils/audioPrefs.test.ts
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add katrain/web/ui/src/hooks/useSound.ts katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx katrain/web/ui/src/kiosk/components/game/GameControlPanel.playAi.test.tsx
git commit -m "add kiosk byoyomi countdown sound"
```

## Chunk 4: Clear resync action

### Task 4: Add a visible and correctly centered “重置识别” label

**Files:**
- Modify: `katrain/web/ui/src/kiosk/shell/KioskPagebar.tsx`
- Modify: `katrain/web/ui/src/kiosk/shell/KioskPagebar.test.tsx`
- Modify: `katrain/web/ui/src/kiosk-shell/tokens.css`
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.test.tsx`

- [ ] **Step 1: Write failing pagebar tests**

Add a test showing an action can opt into visible text while retaining its accessible name, and that actions without `visibleLabel` stay icon-only. Add a GamePage assertion that physical mode renders a button named “重置识别” with visible text and screen mode omits it.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
cd katrain/web/ui
npm test -- --run src/kiosk/shell/KioskPagebar.test.tsx src/kiosk/pages/GamePage.test.tsx
```

Expected: FAIL because `visibleLabel` is not supported and GamePage still emits an icon-only action.

- [ ] **Step 3: Implement the optional labeled action**

Add `visibleLabel?: ReactNode` to the pagebar action contract, render it only when supplied, and add a modifier class. For the modifier, use a 44px touch height, automatic width, horizontal padding, gap, `line-height: 1`, and centered inline-flex layout; explicitly set `padding: 0`/`line-height: 0` for the unchanged icon-only variant. In GamePage, display `重置识别` and correct the accessible description to say the screen/digital position is authoritative.

- [ ] **Step 4: Run focused UI tests and verify GREEN**

Run the same two test files. Expected: pass.

- [ ] **Step 5: Run a representative 1024×600 browser preview**

Use the existing kiosk game Playwright fixture or local runtime to capture one 1024×600 physical-play game screenshot. Confirm the back button, long game title/subtitle, and labeled resync button fit without overlap; record any inability to run the real preview as a device-verification item rather than expanding tooling work.
This is a low-risk local layout change, so the single representative preview is the proportional geometry gate; do
not add a new Playwright suite solely for pixel bounds.

- [ ] **Step 6: Commit**

```bash
git add katrain/web/ui/src/kiosk/shell/KioskPagebar.tsx katrain/web/ui/src/kiosk/shell/KioskPagebar.test.tsx katrain/web/ui/src/kiosk-shell/tokens.css katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/pages/GamePage.test.tsx
git commit -m "clarify kiosk vision resync action"
```

## Chunk 5: Integration verification

### Task 5: Run proportional regression gates

**Files:**
- No production changes expected

- [ ] **Step 1: Run the full vision regression gate**

Run: `uv run pytest tests/test_vision -q`

Expected: 0 failures.

- [ ] **Step 2: Run the full frontend test gate**

Run: `cd katrain/web/ui && npm test -- --run`

Expected: 0 failures.

- [ ] **Step 3: Run the real TypeScript build gate**

Run: `cd katrain/web/ui && npx tsc -b`

Expected: exit 0. Do not substitute `tsc --noEmit`, which is a no-op in this repository.

- [ ] **Step 4: Review scope and device handoff**

Confirm white move 88 LED remains untouched, both worker copies carry the same motion-gate behavior, and no deployment was attempted while RK3562 is offline. Record the exact commits and tomorrow’s device checks: no reacquired toast during normal moves, visible-before-audio ordering, LED behavior logging, 5-to-1 countdown, and resync-button geometry/action.
