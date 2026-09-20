# Tsumego Galaxy Journey Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make kiosk tsumego follow the approved Galaxy journey: difficulty → category → 20-problem unit, including mixed training.

**Architecture:** Keep the existing kiosk shell, APIs, account-scoped pointers, progress provider, and unit/problem screens. Replace the level hub’s category-first content with a continuous level ladder, redraw the category screen with kiosk-native components, and treat `all` as a pseudo-category whose paginated level problems are flattened into the same unit sequence contract. Extend the problem screen’s existing set-aware navigation so `?set=all` stays inside the mixed sequence.

**Tech Stack:** React 19, React Router 6, TypeScript, kiosk-shell CSS/components, Vitest/Testing Library, Playwright.

---

## Chunk 1: Level-first and category screens

### Task 1: Replace the category-first hub with the Galaxy level ladder

**Files:**
- Modify: `katrain/web/ui/src/kiosk/__tests__/TsumegoPage.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoPage.tsx`
- Modify: `katrain/web/ui/src/kiosk-shell/go-screens.css`

- [x] **Step 1: Write failing level-first tests**

  Remove expectations for category cards on `/kiosk/tsumego`; assert one ordered level row per API level, current-level highlighting, the kyu/dan seam, and navigation to `/kiosk/tsumego/:level`.

- [x] **Step 2: Run the focused test and verify RED**

  Run: `NODE_OPTIONS=--no-experimental-webstorage npx vitest run src/kiosk/__tests__/TsumegoPage.test.tsx`

  Expected: FAIL because the hub still renders category cards and ring cards.

- [x] **Step 3: Implement the level ladder**

  Keep greeting, account-scoped resume, loading/error/empty states, and the existing `/levels` contract. Render `button.tsumego-level-row` items with level, total count, category distribution, current marker, and a seam between the last kyu and first dan.

- [x] **Step 4: Run the focused test and verify GREEN**

  Run the Step 2 command; expect all `TsumegoPage` tests to pass.

### Task 2: Redraw the category page with kiosk-native components

**Files:**
- Modify: `katrain/web/ui/src/kiosk/__tests__/TsumegoCategoriesPage.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoCategoriesPage.tsx`
- Modify: `katrain/web/ui/src/kiosk-shell/go-screens.css`

- [x] **Step 1: Write failing shell/category tests**

  Assert the page uses `kiosk-layout-b`, labels its back action “难度”, orders real categories with `categoryRank`, shows completed/total when available, and renders a “综合训练” entry that navigates to `/kiosk/tsumego/:level/all`.

- [x] **Step 2: Run the focused test and verify RED**

  Run: `NODE_OPTIONS=--no-experimental-webstorage npx vitest run src/kiosk/__tests__/TsumegoCategoriesPage.test.tsx`

  Expected: FAIL because the page is still the old MUI grid and says “全部题目”.

- [x] **Step 3: Implement the kiosk-native category screen**

  Reuse `KioskPagebar`, `KioskScrollZone`, `KioskSecLabel`, `KioskCard`, `CATEGORY_META`, and the existing best-effort progress fetch. Remove page-local MUI cards/icons and keep the retry behavior.

- [x] **Step 4: Run the focused test and verify GREEN**

  Run the Step 2 command; expect all category-page tests to pass.

## Chunk 2: Mixed training through units and problems

### Task 3: Make `all` use the same unit sequence contract

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/tsumegoUnits.ts`
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoUnitsPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoUnitListPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/TsumegoUnitsPage.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/TsumegoUnitListPage.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/KioskApp.test.tsx`

- [x] **Step 1: Write failing mixed-unit tests**

  Assert `/15k/all` loads every page of `/levels/15k/problems?page=N&page_size=200`, stores `sequenceKey('15k', 'all')`, groups it into 20-problem units, returns to the category screen, and opens problem cells with `?set=all`.

- [x] **Step 2: Run the focused tests and verify RED**

  Run: `NODE_OPTIONS=--no-experimental-webstorage npx vitest run src/kiosk/__tests__/TsumegoUnitsPage.test.tsx src/kiosk/__tests__/TsumegoUnitListPage.test.tsx src/kiosk/__tests__/KioskApp.test.tsx`

  Expected: FAIL because `/all` still renders `TsumegoLevelPage` and unit loaders only know category endpoints.

- [x] **Step 3: Add one sequence loader and route `all` through units**

  Add `fetchTsumegoSequence(level, category, signal)`: category mode performs the existing `?limit=1000` request; `all` mode drains the paginated level endpoint. Use it in both unit pages, name the pseudo-category “综合训练”, omit self-referential “整级/错题” alternatives for it, and remove the static `TsumegoLevelPage` route so the dynamic category route owns `all`.

- [x] **Step 4: Run the focused tests and verify GREEN**

  Run the Step 2 command; expect all focused tests to pass.

### Task 4: Preserve mixed navigation inside the problem screen

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/TsumegoProblemPage.test.tsx`

- [x] **Step 1: Write failing `?set=all` tests**

  Seed `sequenceKey(level, 'all')`, open a problem with `?set=all`, then assert previous/next preserve the query, pagebar/resume say “综合训练”, and back/last-problem actions return to `/kiosk/tsumego/:level/all/:unit` or `/all` as appropriate.

- [x] **Step 2: Run the focused test and verify RED**

  Run: `NODE_OPTIONS=--no-experimental-webstorage npx vitest run src/kiosk/__tests__/TsumegoProblemPage.test.tsx`

  Expected: FAIL because the screen only recognizes `?set=wrong`.

- [x] **Step 3: Implement all-set navigation**

  Resolve the active sequence in priority order: valid wrong snapshot, valid mixed sequence, category sequence. Keep the real problem category tag, while using “综合训练” for the journey label, resume pointer, sequence navigation, and return targets.

- [x] **Step 4: Run the focused test and verify GREEN**

  Run the Step 2 command; expect all problem-page tests to pass.

## Chunk 3: Integration and target viewport

### Task 5: Verify behavior and the approved 1024×600 composition

**Evidence:** focused Vitest suite, production build, and temporary Playwright CLI screenshots inspected at the target `1024×600` viewport.

- [x] **Step 1: Exercise the journey in a real browser**

  Stub the real API shapes with Playwright CLI, verify difficulty → category → mixed unit navigation, and capture representative 1024×600 screenshots for difficulty, category, and unit screens. Per the repository proportionality rule, keep this as one focused preview rather than adding a permanent browser test that duplicates component coverage.

- [x] **Step 2: Run type/build and focused behavior checks**

  Run:

  ```bash
  NODE_OPTIONS=--no-experimental-webstorage npx vitest run \
    src/kiosk/__tests__/TsumegoPage.test.tsx \
    src/kiosk/__tests__/TsumegoCategoriesPage.test.tsx \
    src/kiosk/__tests__/TsumegoUnitsPage.test.tsx \
    src/kiosk/__tests__/TsumegoUnitListPage.test.tsx \
    src/kiosk/__tests__/TsumegoProblemPage.test.tsx
  npm run build
  ```

  Expected: all focused tests pass; TypeScript and kiosk build exit 0.

- [x] **Step 3: Run the target viewport preview and inspect one representative screenshot per screen**

  Run the Playwright CLI journey at `1024×600`. Confirm touch targets, row/card hierarchy, readable counts, scrolling, and that no content overlaps the fixed shell.
