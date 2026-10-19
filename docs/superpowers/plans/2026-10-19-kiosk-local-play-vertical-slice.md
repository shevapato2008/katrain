# Kiosk Local Play Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the approved 04 local setup and 05a two-person local game design into the real 1024 × 600 Kiosk, while preserving its existing confirmation and clock rules.

**Architecture:** Keep `PvpLocalSetupPage`, `LocalConfirmGame`, their state owners, and `/api/local/ready` plus `/api/local/confirm` as the single behavior path. Align only the route-scoped presentation with the approved HTML artifact. Verify the real browser first; change backend code only for an observed contract defect and only after the user's same-size frontend approval.

**Tech Stack:** React, TypeScript, existing Kiosk CSS, Vitest, Playwright, FastAPI.

---

## Scope and source of truth

- Approved visual source: `docs/design/kiosk-current-based-redesign-2026-10-14.html#setup-local` and `#game-local`, with `docs/design/kiosk-unified/{setup,game,tactile}.css` and `.js`. The user explicitly approved the revised local game preview; do not restart visual exploration.
- Behavior source: `PvpLocalSetupPage.tsx`, `GamePage.tsx`, `LocalConfirmGame.tsx`, `api.ts`, `server.py`, and `docs/design/local-confirm-2026-10-12-v2/DESIGN.md`. Preserve board preflight, optional names, real terms, sound preference, two-phase move confirmation, frozen clocks, wrong-stone recovery, pass/count/resign, no-save exit, and truthful disabled states.
- The target screenshot is an **unscaled 1024 × 600 Kiosk stage**, not the surrounding design index. The existing artifact uses illustrative player names and board positions; never import those fixture values into production.
- One vertical slice only: `/kiosk/play/pvp/setup` and `/kiosk/play/pvp/local/game/:sessionId` with screen input. Real physical board input retains existing code and needs device acceptance later. Online lobby and other Kiosk modules are separate slices.
- The real AI-play runtime preview is awaiting user confirmation. This plan may be reviewed now; start implementation after that confirmation. If the user requests corrections, finish the AI-play slice first.

## Ownership and acceptance

Create an isolated worktree from the accepted feature branch for implementation. The coordinator owns shared shell changes and commits after workers stop. Assign disjoint files to workers:

| Task | Production files | Focused tests |
| --- | --- | --- |
| Shared shell | `katrain/web/ui/src/kiosk/components/layout/KioskLayout.tsx`, `katrain/web/ui/src/kiosk-shell/shell-redesign.css` | `katrain/web/ui/src/kiosk/__tests__/KioskLayout.test.tsx` |
| Setup | `katrain/web/ui/src/kiosk/pages/PvpLocalSetupPage.tsx`, new `katrain/web/ui/src/kiosk-shell/local-setup-redesign.css` | `katrain/web/ui/src/kiosk/pages/PvpLocalSetupPage.test.tsx` |
| Game | `katrain/web/ui/src/kiosk/components/game/LocalConfirmGame.tsx`, `katrain/web/ui/src/kiosk/components/game/LocalConfirmGame.css` | `katrain/web/ui/src/kiosk/components/game/LocalConfirmGame.test.tsx` |

The coordinator adds the new stylesheet import in `katrain/web/ui/src/kiosk/KioskApp.tsx` before dispatching workers. Do not have multiple workers stage or commit concurrently.

At 1024 × 600, setup must keep the 516 px board and 460 px rail, offer working raised selectors for editable choices, show distinct fixed/derived fields, and fit the start action. The game must keep the 512 px board and 224 px side panels, visibly brighten the active side and dim the waiting side, display distinct coordinate/number icons, arrange its five small actions in two equal columns and rows, and give confirmation substantially more height and emphasis. The real start, selection, confirmation, turn switch, and both clocks must remain correct.

## Chunk 1: Shared route scope

### Task 1: Shared entry point

**Files:** `katrain/web/ui/src/kiosk/components/layout/KioskLayout.tsx`, `katrain/web/ui/src/kiosk/KioskApp.tsx`, `katrain/web/ui/src/kiosk-shell/shell-redesign.css`, new `katrain/web/ui/src/kiosk-shell/local-setup-redesign.css`.

- [ ] Add a `local-play` journey only for the exact local setup route and local game route. Keep the current `ai-play` route predicate and other routes unchanged. In `shell-redesign.css`, share only the approved topbar treatment between the two journeys using a common selector; leave AI setup/game-specific styles scoped to AI.
- [ ] Import `local-setup-redesign.css` from `KioskApp.tsx` and create its empty body before dispatching workers. Run `npm run build` from `katrain/web/ui`; expect exit 0. Commit the shared entry point in the isolated worktree.

## Chunk 2: Parallel page alignment

### Task 2: Local setup, screen 04

**Files:** `katrain/web/ui/src/kiosk/pages/PvpLocalSetupPage.tsx`, `katrain/web/ui/src/kiosk-shell/local-setup-redesign.css`, `katrain/web/ui/src/kiosk/pages/PvpLocalSetupPage.test.tsx`.

- [ ] Reuse the existing setup tests first. Add a focused assertion only for an uncovered gap: board/rule/handicap/time and optional names reach `API.gameSetup`; screen/physical choice flows through `writePlayOnBoard`, the active session's `onBoard`, and `readyLocalGame`; sound updates the existing `audioPrefs.sfx` preference. All editable selectors must still expose their choices. Run `npx vitest run src/kiosk/pages/PvpLocalSetupPage.test.tsx`; expect any new assertion to expose a real gap.
- [ ] Add one local-setup root class and scoped CSS based on the approved `setup-local` stage: 44 px touch targets, consistent raised controls, open-menu chevrons, separate dashed derived komi, balanced two-name row, and visible start action. Reuse the existing `SetupSelect`, `SetupDerived`, and `SetupPopoverHost`; do not copy their logic or add new preferences.
- [ ] Replace any long always-visible setup hints only where they cause measured clipping with an accessible, working section-help control. Keep error banner and board-preflight message visible. Re-run the focused test and inspect one 1024 × 600 real-browser setup screenshot plus one open selector.

### Task 3: Local game, screen 05a

**Files:** `katrain/web/ui/src/kiosk/components/game/LocalConfirmGame.tsx`, `katrain/web/ui/src/kiosk/components/game/LocalConfirmGame.css`, `katrain/web/ui/src/kiosk/components/game/LocalConfirmGame.test.tsx`.

- [ ] Add a focused behavior assertion for synchronized `aria-pressed` coordinates/numbers controls, active-versus-waiting labels, active-only confirm/pass, and confirm click once a point is selected. Run `npx vitest run src/kiosk/components/game/LocalConfirmGame.test.tsx` to record the baseline.
- [ ] Keep the existing five actions and handlers. Put coordinates, numbers, pass, count, and resign in a two-column equal-size grid with 44 px or taller targets; make the large per-side confirm action the clear primary control below them. Use existing `grid-nine` and `list-numbers` icons and retain `开/关` state text.
- [ ] Tune the two side panels using the approved active/waiting contrast, clock hierarchy, material and spacing. Keep error and busy states distinct, both names readable, the board at 512 px, and no clipped action at y=586. Preserve keyboard focus and reduced-motion behavior. Re-run the focused test and inspect real-browser screenshots for black turn, white turn, selected point, and one representative disabled/error state only if reachable without artificial product data.

## Chunk 3: Real journey and review

### Task 4: Contract and visual acceptance

**Files to read:** `katrain/web/ui/src/api.ts`, `katrain/web/ui/src/kiosk/pages/GamePage.tsx`, `katrain/web/server.py`, `katrain/web/core/local_confirmation.py`, existing focused tests. Modify a test only for a concrete uncovered regression.

- [ ] Compare actual `createSession` → `gameSetup(pvp_local)` → `readyLocalGame(screen)` → `confirmLocalMove` payloads with server handlers. Use the existing local isolated test DB and backend; never write test games to production. If a contract defect is found, obtain the required visual confirmation before backend edits.
- [ ] In a real browser at 1024 × 600, choose a timed preset and screen input, then start a local game. Pick an empty point and verify Black's clock runs while White's does not; confirm Black and verify White becomes active with its clock running. Pick/confirm White, verify two stones and Black active again. Check the disabled waiting-side confirmation, the time/byoyomi copy, and the entire action area for clipping. Confirmation-time clock freeze can rely on its existing focused test; do not claim physical recognition was tested on this Mac.
- [ ] Capture same-size artifact reference and runtime images for setup and game. Produce side-by-side and overlay/diff evidence, then compare geometry, spacing, type, icon meaning, active/waiting/disabled states, and key copy. Fix concrete mismatches before review.
- [ ] Run focused Vitest for setup and local game, `npm run build`, and `git diff --check`. Ask Astra Max for an independent **visual** and code review of the exact screenshots and diff. Fix actionable findings and repeat until pass. Then show the real runtime screenshots to the user for visual confirmation before any new backend implementation.

## Completion record

Record focused test results, real API/turn-switch result, screenshot paths, Astra decision, commit hashes, and the physical-device limitation. Do not merge or deploy as part of this slice without a separate release request.

**2026-10-19 frontend result:** Setup and local game are implemented in the isolated worktree. The 35 focused Vitest cases, production UI build, and `git diff --check` passed. At 1024 × 600, the local API created a screen-input game with 5 minutes plus three 30-second periods; Black selected D16 and confirmed, White selected E16 and confirmed, with the active clock and disabled waiting-side confirmation switching correctly. Screenshots and right-rail overlays are under `output/playwright/kiosk-local-*`. Astra Max requested two corrections (raised game controls and accurate rule help); both were fixed and its targeted visual/code re-review passed. Physical-board recognition still needs device acceptance and was not simulated on this Mac.
