# Kiosk AI Play Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the approved Kiosk play home, AI setup, and AI game design into the real React app, then verify its existing backend journey without claiming fixture tests are full integration.

**Architecture:** The 1024 × 600 approved HTML artifact is the visual reference. Keep existing React routes, session APIs, engine readiness, ranked lifecycle, and game state as the authority; make scoped presentation changes in the page components and page-specific CSS. Verify the real app at the target viewport with the existing backend contract, and change the backend only if a concrete contract mismatch prevents the journey.

**Tech Stack:** React, TypeScript, Vite, existing Kiosk CSS, Vitest, Playwright, FastAPI.

---

## Scope and acceptance

This plan covers `/kiosk/play` (01), `/kiosk/play/ai/setup/free` (02), `/kiosk/play/ai/setup/ranked` (03), and `/kiosk/play/ai/game/:sessionId` for free/ranked AI play (05). The user accepted the **design artifact** for these screens before moving to cross-platform work; the React runtime has not yet received same-size visual approval. The reference is `docs/design/kiosk-current-based-redesign-2026-10-14.html` with renderable hashes `#play`, `#setup-free`, `#setup-ranked`, and `#game`. The artifact's `#game-ranked` has no captured current screenshot and is not renderable; derive ranked presentation from the approved game style while retaining the true ranked restrictions. Read `docs/design/kiosk-unified/{core,play,setup,game,tactile}.css`, the corresponding `.js`, and the artifact's numeral treatment. Other screens, including 15/19, are separate slices. No fixture business data may enter production.

At 1024 × 600, the play home keeps the existing information order and platform identity marks, uses smaller equal-sized raised mode buttons, and omits explanatory icons on its own non-platform mode buttons. Setup uses dropdowns for editable enumerated choices, including free opponent strength; fixed/read-only fields remain distinct, explanatory prose moves into working info dialogs, and ranked fields follow the approved grouping without hardcoding sample data. The AI game **creates** two separate four-corner rounded trapezoid player cards with a compact gap equal to the adjacent vertical gap, gives the win-rate chart more space, and keeps action buttons equal-sized with icon/text spacing and distinct icons and the label `支招`. Starting a free or ranked game and receiving state must continue to use the real APIs and truthful readiness/auth/error states.

The prior artifact approval authorizes frontend implementation. Per `AGENTS.md`, after the real 1024 × 600 React comparison, obtain the user's visual confirmation **before any newly necessary backend modification**. Read-only contract verification and use of existing backend endpoints may proceed. If runtime backend is unavailable, explicitly leave integrated acceptance pending; a stub preview is only visual evidence. Do not deploy or merge as part of this plan unless separately requested.

## File ownership for parallel work

Implementation runs in the clean isolated worktree `/Users/fan/.config/superpowers/worktrees/katrain-kiosk-ui-redesign/ai-play-20261019` on `feature/kiosk-ai-play-slice-20261019`. The coordinator commits the already visually reviewed Galaxy/Kiosk Fondamento change as one coherent commit in the original workspace (including real font asset and license), then cherry-picks it into the worktree. The artifact remains read-only at its absolute path in the original workspace; do not copy the large evidence tree. The coordinator then owns shared presentation: `KioskFrame.tsx`/`KioskLayout.tsx` for a route-scoped class or data attribute, `KioskConsoleRail.tsx`/`GoConsoleRail.tsx` for the play console's help control, `shell-redesign.css` for page header, dock and console typography, plus `KioskApp.tsx` for stylesheet imports. The shell must match `core.css` and `tactile.css` without changing other page behavior. Workers share a Git index, so **only the coordinator stages and commits**, after each worker has stopped. Workers own disjoint production files:

| Task | Exclusive production files | Focused existing tests |
| --- | --- | --- |
| 1 Play | `katrain/web/ui/src/kiosk/pages/PlayPage.tsx`, `katrain/web/ui/src/kiosk-shell/play-redesign.css` | `katrain/web/ui/src/kiosk/pages/PlayPage.test.tsx` |
| 2 Setup | `katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx`, `katrain/web/ui/src/kiosk-shell/setup-redesign.css` | `katrain/web/ui/src/kiosk/pages/AiSetupPage.test.tsx`, `katrain/web/ui/tests/kiosk-setup-r2-geometry.spec.ts` |
| 3 Game | `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx`, `katrain/web/ui/src/kiosk-shell/game-redesign.css` | `katrain/web/ui/src/kiosk/__tests__/GamePage.test.tsx` |

`katrain/web/ui/src/kiosk/shell/KioskCard.tsx` and shared `tokens.css` are left alone unless a worker demonstrates a concrete blocker and coordinates a central shared-file edit. Task 1 may use a local card variant to omit the tile. Task 2 owns the required JSX regrouping, strength selector, and real help dialog while retaining existing state and server-derived values. Task 3 owns the required JSX paired-card layout in `GameControlPanel.tsx` and AI-scoped styles; any needed `GamePage.tsx` edit is coordinated first. Shared local/online controls must keep their behavior.

## Chunk 1: Prepare the shared entry point

### Task 0: Brand and scoped shared shell

**Files:**
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`
- Modify: `katrain/web/ui/src/kiosk/shell/KioskFrame.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/layout/KioskLayout.tsx`
- Modify: `katrain/web/ui/src/kiosk/shell/KioskConsoleRail.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/layout/GoConsoleRail.tsx`
- Create: `katrain/web/ui/src/kiosk-shell/shell-redesign.css`
- Create: `katrain/web/ui/src/kiosk-shell/play-redesign.css`
- Create: `katrain/web/ui/src/kiosk-shell/setup-redesign.css`
- Create: `katrain/web/ui/src/kiosk-shell/game-redesign.css`

- [ ] In the original workspace, stage **only** the reviewed Fondamento files: `GalaxyApp.tsx`, `GalaxyTopBar.tsx`, `LoginPage.tsx`, `KioskApp.tsx`, `tokens.css`, `brand-font.css`, and `fonts/{fondamento-latin-regular.woff2,OFL-Fondamento.txt}`. Verify `git diff --cached --check`, commit them together, then cherry-pick into the worktree. Do not stage design artifacts.
- [ ] Read `KioskApp.tsx`, `KioskFrame.tsx`, `KioskLayout.tsx`, console components and `AGENTS.md`. Add one stable AI-journey route attribute/class on the shell for /kiosk/play, free/ranked setup and free/ranked game, keeping all other routes unchanged.
- [ ] Add the play console help control with accessible name and working help content; preserve camera/calibration/LED status truth. Scope 18 px console readings, 22 px dock labels, header sizing and raised presentation to the AI journey in `shell-redesign.css`; use the real Fondamento font already cherry-picked. Check the 1024 × 600 canvas for clipping.
- [ ] Add the four new stylesheet imports immediately after `go-screens.css` in `KioskApp.tsx`. Leave the three worker-owned stylesheet bodies empty initially.
- [ ] Run `git diff --check` and a TypeScript/Vite build smoke check (`npm run build` from `katrain/web/ui`); expect no import errors.
- [ ] Commit the coordinator-owned shared shell in the worktree with an exact-file add, then dispatch Tasks 1–3 in parallel. Do not let workers commit concurrently.

## Chunk 2: Parallel screen implementation

### Task 1: Play home, screen 01

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/PlayPage.tsx`
- Modify: `katrain/web/ui/src/kiosk-shell/play-redesign.css`
- Test: `katrain/web/ui/src/kiosk/pages/PlayPage.test.tsx`

- [ ] Add one focused assertion that the four primary mode choices preserve their route/disabled behavior while rendering without explanatory icon tiles; retain branded platform marks.
- [ ] Run `npm test -- --run src/kiosk/pages/PlayPage.test.tsx`; verify the new assertion fails for the old presentation.
- [ ] Implement a PlayPage-only class/markup variant and scoped CSS: compact equal geometry, matched button/background radii, raised border/highlight/shadow, legible text and spacing, existing section order and truthful platform states. Do not remove meaningful status text or alter navigation.
- [ ] Re-run the focused test; expect pass. Check the PlayPage at 1024 × 600 against `#play` with one real-browser screenshot.
- [ ] Return owned-file changes and visual findings to the coordinator; the coordinator commits after review.

### Task 2: AI setup, screens 02/03

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx` for grouping, strength selector, and help dialog
- Modify: `katrain/web/ui/src/kiosk-shell/setup-redesign.css`
- Test: `katrain/web/ui/src/kiosk/pages/AiSetupPage.test.tsx`
- Test: `katrain/web/ui/tests/kiosk-setup-r2-geometry.spec.ts` (replace superseded stepper geometry assertions)

- [ ] Add focused interaction assertions: all editable enum fields, including opponent strength, expose options; choosing strength updates the actual value later sent by `handleStart`; fixed ranked fields do not open; info dialogs expose their explanations.
- [ ] Run `npm test -- src/kiosk/pages/AiSetupPage.test.tsx` from `katrain/web/ui`; verify new assertions fail on the old presentation.
- [ ] Replace the 29-rung `SetupStepper` with `SetupSelect` (same `rank` state and `rankOptions` mapping), regroup free/ranked rows as in `setup.js`, and move long `su-hint` prose into accessible help dialogs. Keep status/error/blocking flows and all API payload values intact. Style actual selectors with the approved raised treatment; preserve `aria-haspopup`, `aria-expanded`, disabled options and read-only semantics.
- [ ] Update the old Playwright geometry assertion that requires the removed ± stepper to instead verify the strength dropdown's 1024 × 600 bounds and open menu. Re-run focused Vitest; expect pass.
- [ ] Check free/ranked unscaled 1024 × 600 screenshots, including one open menu and lower start action. Return changes to the coordinator for commit.

### Task 3: Live AI game, screen 05

**Files:**
- Modify: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx` only for a needed AI-specific class/markup or label
- Modify: `katrain/web/ui/src/kiosk-shell/game-redesign.css`
- Test: `katrain/web/ui/src/kiosk/__tests__/GamePage.test.tsx`
- Optional only if truly necessary and coordinated: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`

- [ ] Identify the player-card, win-rate chart, and action-grid DOM/classes in `GameControlPanel.tsx`; note which selectors are shared with local/online modes.
- [ ] Add a focused assertion for the user-visible `支招` label, distinct coordinate/territory/digit icons if rendered by this panel, and action availability; do not mirror CSS internals in tests.
- [ ] Run the focused test to observe the baseline/new assertion, then implement paired player-card markup for free AI (currently stacked rows). Use a clipped or otherwise slanted shape that retains four rounded corners and keeps a small, even gap; avoid making the diagonal overlap or narrowing names. Reclaim height for the win-rate plot; keep action buttons equal-sized and icon/text spacing consistent.
- [ ] Re-run the focused test; expect pass. Inspect free and ranked game screenshots at 1024 × 600 and verify no clipped content or action change.
- [ ] Return changes to the coordinator for commit and report any backend contract issue.

## Chunk 3: Integrate and verify the real journey

### Task 4: Contract and viewport acceptance

**Files:**
- Read: `katrain/web/ui/src/api.ts`, `katrain/web/ui/src/features/aiLadder/api.ts`, `katrain/web/server.py`, `katrain/web/api/v1/endpoints/ai_ladder.py`
- Read: `katrain/web/ui/tests/kiosk-screen-05-game.spec.ts`, `katrain/web/ui/tests/kiosk-setup-r2-geometry.spec.ts`
- Modify an existing focused test only for a concrete uncovered regression.

- [ ] Compare the actual calls from `AiSetupPage` (`API.createSession` then `API.gameSetup` for free; `startAiLadderGame` for ranked) with `server.py` and `ai_ladder.py`. Record request/response fields and state/error handling. Do not modify backend before the runtime screenshot receives user approval if a gap is found.
- [ ] Run `npm test -- src/kiosk/pages/PlayPage.test.tsx src/kiosk/pages/AiSetupPage.test.tsx src/kiosk/__tests__/GamePage.test.tsx` and `npm run build` from `katrain/web/ui`. Build **before** any default-config Playwright run so FastAPI does not serve stale static assets.
- [ ] Run the relevant existing Playwright specs after updating obsolete visual assertions, recognizing their routed API fixtures prove layout/interaction only. Separately perform one free and one ranked **non-intercepted** start request, returned session-ID navigation, state fetch, and move/state update against an actual running backend. If credentials/engine/service are unavailable, mark the corresponding journey pending and do not claim backend integration passed; reuse existing backend route tests for contract evidence.
- [ ] Capture the artifact's **unscaled stage only** and the real app at identical 1024 × 600. Produce reference, implementation, side-by-side, and overlay/diff images; compare geometry, labels, icon semantics, and active/disabled states. Update old Playwright expectations (pagebar/knobs/stepper) only where the approved artifact supersedes them; preserve behavioral checks.
- [ ] Run `git diff --check`. Request an independent Astra Max visual/code review with screenshots and exact diff; fix actionable findings and repeat code review until approved. Obtain user runtime visual confirmation before any newly necessary backend edit.
- [ ] Record the screenshot paths, focused test results, backend contract conclusion, commit hashes, and remaining risk. Keep 15/19 design changes separate from this slice.
