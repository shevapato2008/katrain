# SBC Kiosk Report Parity Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver complete Galaxy Report feature parity as a touch-first 1024×600 kiosk client while keeping report analysis exclusively on the server.

**Architecture:** Move Report/user-game contracts and UI-independent Report state into shared frontend modules, keep Galaxy visuals intact, and build kiosk-specific list/detail components from existing kiosk/live primitives. The kiosk calls the existing authenticated APIs; the database, KataGo analysis, and `katrain-cron` lifecycle remain server-only.

**Tech Stack:** React 19, TypeScript 5.9, React Router 6, MUI 7, Vitest/Testing Library, Playwright, Vite, FastAPI/pytest regression tests.

**Implementation skills:** Use @superpowers:test-driven-development for every behavior change, @superpowers:systematic-debugging for unexpected failures, and @superpowers:verification-before-completion before claiming completion.

**Working directory:** Frontend commands run from `katrain/web/ui`; backend commands run from the repository root.

---

## File map

### Shared frontend

- Create `katrain/web/ui/src/api/reportApi.ts`: authenticated Report API and public Report contracts.
- Create `katrain/web/ui/src/api/userGamesApi.ts`: shared user-game API and contracts.
- Modify `katrain/web/ui/src/galaxy/api/reportApi.ts`: compatibility re-export only.
- Modify `katrain/web/ui/src/galaxy/api/userGamesApi.ts`: compatibility re-export only.
- Create `katrain/web/ui/src/features/report/reportModel.ts`: pure task/import/analysis derivations.
- Create `katrain/web/ui/src/features/report/useReportTasks.ts`: active-only list/summary polling and mutations.
- Create `katrain/web/ui/src/features/report/useReportDetail.ts`: progressive report loading and cursor policy.
- Create matching tests beside each shared file.

### Galaxy regression integration

- Modify `katrain/web/ui/src/galaxy/pages/report/ReportsPage.tsx`: consume shared headless behavior.
- Modify `katrain/web/ui/src/galaxy/pages/report/ReportDetailPage.tsx`: consume shared detail behavior.
- Modify Galaxy Report components only for shared type import paths.
- Modify the two existing Galaxy page tests to mock shared modules and retain feature assertions.

### Kiosk list UI

- Create `katrain/web/ui/src/kiosk/pages/ReportsPage.tsx` and test.
- Create `katrain/web/ui/src/kiosk/components/report/ReportGameCard.tsx` and test.
- Create `katrain/web/ui/src/kiosk/components/report/ReportImportMenu.tsx`.
- Create `katrain/web/ui/src/kiosk/components/report/ReportLocalImportDialog.tsx` and test.
- Create `katrain/web/ui/src/kiosk/components/report/ReportLibraryImportDialog.tsx` and test.

### Kiosk detail UI

- Create `katrain/web/ui/src/kiosk/pages/ReportDetailPage.tsx` and test.
- Create `katrain/web/ui/src/kiosk/components/report/ReportMetaPanel.tsx` and test.

### Navigation and verification

- Modify `katrain/web/ui/src/kiosk/KioskApp.tsx`.
- Modify `katrain/web/ui/src/kiosk/components/layout/navTabs.tsx`, `Dock.tsx`, and `Header.tsx` plus their tests.
- Modify `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx` only if needed to provide a secondary-page back affordance.
- Create `katrain/web/ui/tests/report-kiosk.spec.ts`.
- Do not modify `docker-compose.yml`, `Dockerfile.cron`, `katrain/cron/**`, SBC service definitions, or SBC packaging to add local Report analysis.

---

## Chunk 1: Shared contracts and headless Report behavior

### Task 1: Share the API contracts without breaking Galaxy

**Files:**
- Create: `katrain/web/ui/src/api/reportApi.ts`
- Create: `katrain/web/ui/src/api/reportApi.test.ts`
- Create: `katrain/web/ui/src/api/userGamesApi.ts`
- Modify: `katrain/web/ui/src/api/userGamesApi.test.ts`
- Modify: `katrain/web/ui/src/galaxy/api/reportApi.ts`
- Modify: `katrain/web/ui/src/galaxy/api/userGamesApi.ts`

- [ ] **Step 1: Write failing shared API request tests**

For Reports, cover list, summary, get, create normal/deep, retry, and getMoves. For user games, retain list/get coverage and add create, update, delete, and analysis request coverage. Assert bearer auth, JSON bodies, exact paths, and surfaced non-2xx response text for both clients.

```ts
it('creates a deep report through the existing server endpoint', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okJson(task)));
  await ReportsAPI.create('token', { user_game_id: 'game-1', report_type: 'deep' });
  expect(fetch).toHaveBeenCalledWith('/api/v1/reports/', expect.objectContaining({
    method: 'POST',
    body: JSON.stringify({ user_game_id: 'game-1', report_type: 'deep' }),
  }));
});
```

- [ ] **Step 2: Run the test and verify the shared module is missing**

Run: `npm run test -- src/api/reportApi.test.ts src/api/userGamesApi.test.ts`  
Expected: FAIL because the new shared implementations do not exist.

- [ ] **Step 3: Move the existing API implementations and contracts into shared files**

Keep endpoint behavior byte-for-byte compatible. Export these exact contracts:

```ts
export type ReportType = 'normal' | 'deep';
export type KnownReportStatus = 'pending' | 'running' | 'completed' | 'failed';
export type ReportStatus = KnownReportStatus | (string & Record<never, never>);
export const isActiveReportStatus = (status: string): status is 'pending' | 'running' =>
  status === 'pending' || status === 'running';
export const isTerminalReportStatus = (status: string): status is 'completed' | 'failed' =>
  status === 'completed' || status === 'failed';
```

Use `ReportType` and `ReportStatus` in `ReportTaskSummary`; unknown server strings remain renderable as an unknown status while helpers narrow known behavior.

- [ ] **Step 4: Replace old Galaxy modules with compatibility exports**

```ts
export * from '../../api/reportApi';
```

Use the equivalent export for `userGamesApi.ts`. This prevents unrelated Galaxy pages from being migrated in the same change.

- [ ] **Step 5: Run API tests, Galaxy consumers, and the TypeScript compiler**

Run: `npm run test -- src/api/reportApi.test.ts src/api/userGamesApi.test.ts`  
Expected: PASS, including all pre-existing user-game API tests.

Run: `npm run test -- src/galaxy/pages/report`  
Expected: PASS through the compatibility exports.

Run: `npx tsc -b --pretty false`  
Expected: exit 0 with compatibility imports type-correct.

- [ ] **Step 6: Commit the shared API boundary**

```bash
git add katrain/web/ui/src/api katrain/web/ui/src/galaxy/api/reportApi.ts katrain/web/ui/src/galaxy/api/userGamesApi.ts
git commit -m "share report client APIs"
```

### Task 2: Extract pure Report state derivation

**Files:**
- Create: `katrain/web/ui/src/features/report/reportModel.ts`
- Create: `katrain/web/ui/src/features/report/reportModel.test.ts`

- [ ] **Step 1: Write failing table-driven tests**

Test these exported functions:

```ts
isActiveReportTask(task)
createOptimisticReportTask(gameId, reportType, moveCount, optimisticId)
reconcileReportTasks(serverTasks, optimisticTasks)
buildReportStatesByGame(tasks)
toLocalUserGameParams(payload)
toLibraryUserGameParams(album, sgfContent)
toMoveAnalysisMap(reportMoves, userGameId)
nextReportCursor(previousCursor, previousFrontier, nextFrontier)
```

Required cases include newest task winning per type/state, optimistic tasks disappearing when the real task for the same game/type arrives, zero-total progress safety, normal/deep independence, null analysis rows, and historical cursor preservation.

```ts
expect(nextReportCursor(12, 20, 24)).toBe(12);
expect(nextReportCursor(20, 20, 24)).toBe(24);
expect(nextReportCursor(30, 30, 12)).toBe(12);
expect(nextReportCursor(30, 40, 12)).toBe(12);
expect(nextReportCursor(4, 4, 0)).toBe(0);
```

- [ ] **Step 2: Run the model test and verify it fails**

Run: `npm run test -- src/features/report/reportModel.test.ts`  
Expected: FAIL because the model module is absent.

- [ ] **Step 3: Define UI-independent input and state types**

Define these in `reportModel.ts`, with imports only from shared `src/api/**`, `src/types/**`, and `src/utils/**` modules:

```ts
export interface LocalReportImportPayload {
  title?: string; sgfContent: string; boardSize: number; rules: string;
  komi: number; moveCount: number; playerBlack?: string; playerWhite?: string;
  blackRank?: string; whiteRank?: string;
}
export interface ReportGameStatus {
  activeNormal?: ReportTaskSummary; activeDeep?: ReportTaskSummary;
  completedNormal?: ReportTaskSummary; completedDeep?: ReportTaskSummary;
  failedNormal?: ReportTaskSummary; failedDeep?: ReportTaskSummary;
}
export type ReportStatesByGame = Record<string, ReportGameStatus>;
```

- [ ] **Step 4: Implement deterministic pure functions**

Do not read clocks or call APIs inside the model. Pass the optimistic ID from the caller. Preserve `delta_score`/`delta_winrate` zeroes with `??`, not `||`.

- [ ] **Step 5: Run the model test**

Run: `npm run test -- src/features/report/reportModel.test.ts`  
Expected: PASS.

- [ ] **Step 6: Commit the model**

```bash
git add katrain/web/ui/src/features/report
git commit -m "extract report state model"
```

### Task 3: Add active-only task polling and mutations

**Files:**
- Create: `katrain/web/ui/src/features/report/useReportTasks.ts`
- Create: `katrain/web/ui/src/features/report/useReportTasks.test.tsx`

- [ ] **Step 1: Write hook tests with fake timers**

Assert initial parallel list/summary load, two-second polling only with pending/running tasks, polling stop after terminal response, optimistic insertion before POST resolves, reconciliation, retry refresh, and error recovery.

- [ ] **Step 2: Run the hook tests and verify failure**

Run: `npm run test -- src/features/report/useReportTasks.test.tsx`  
Expected: FAIL because the hook is absent.

- [ ] **Step 3: Implement the hook with injected token and translation fallback**

Return data and actions, not MUI elements:

```ts
{
  tasks, queueSummary, reportStatesByGame, loading, error,
  refresh, createReport, retryReport
}
```

Use a stable `refresh`, clear intervals on unmount/token change, and retain previous data during transient refresh failures.

- [ ] **Step 4: Run hook/model/API tests**

Run: `npm run test -- src/features/report src/api/reportApi.test.ts`  
Expected: PASS with no fake-timer leakage.

- [ ] **Step 5: Commit task orchestration**

```bash
git add katrain/web/ui/src/features/report
git commit -m "add report task polling hook"
```

### Task 4: Add progressive detail loading

**Files:**
- Create: `katrain/web/ui/src/features/report/useReportDetail.ts`
- Create: `katrain/web/ui/src/features/report/useReportDetail.test.tsx`

- [ ] **Step 1: Write failing progressive-load tests**

Test initial parallel move/game fetch after task lookup, pending/running polling, terminal stop, failed task exposure, cleanup, malformed task ID, refresh error without blanking prior data, and cursor rules.

- [ ] **Step 2: Run the hook test and verify failure**

Run: `npm run test -- src/features/report/useReportDetail.test.tsx`  
Expected: FAIL because the hook is absent.

- [ ] **Step 3: Implement the headless detail hook**

Return `task`, `game`, raw moves, `analysisByMove`, `currentMove`, `setCurrentMove`, `loading`, `error`, and `refresh`. Poll at 2000 ms only for active states. Use `nextReportCursor` so a historical user selection is not forced forward.

- [ ] **Step 4: Run all shared Report tests**

Run: `npm run test -- src/features/report src/api/reportApi.test.ts`  
Expected: PASS.

- [ ] **Step 5: Commit the detail hook**

```bash
git add katrain/web/ui/src/features/report
git commit -m "add progressive report detail hook"
```

## Chunk 2: Preserve Galaxy and prepare Settings navigation

### Task 5: Migrate Galaxy Report pages to the shared behavior

**Files:**
- Modify: `katrain/web/ui/src/galaxy/pages/report/ReportsPage.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/report/ReportsPage.test.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/report/ReportDetailPage.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/report/ReportDetailPage.test.tsx`
- Modify: `katrain/web/ui/src/galaxy/components/report/ReportGameCard.tsx`
- Modify: `katrain/web/ui/src/galaxy/components/report/ReportMetaPanel.tsx`

- [ ] **Step 1: Run existing Galaxy Report tests as a green characterization baseline**

Run: `npm run test -- src/galaxy/pages/report`  
Expected: PASS before the refactor.

- [ ] **Step 2: Add missing behavior-level characterization tests**

Keep mocks at the current ReportsAPI/UserGamesAPI boundary. Add behavior-level assertions for URL search/pagination, normal and deep creation arguments, optimistic reconciliation display, delete rejection, progressive detail refresh, historical cursor pinning, and `/galaxy/research` navigation. These are preservation tests, so they must pass against current behavior before migration.

Run: `npm run test -- src/galaxy/pages/report`  
Expected: PASS with the new characterization coverage.

- [ ] **Step 3: Replace duplicated page state with shared hooks/model**

Keep all Galaxy component markup and `/galaxy/...` navigation unchanged. Remove only duplicated API polling, task derivation, import conversion, move mapping, and cursor logic.

- [ ] **Step 4: Adapt page tests to the new headless boundary**

Replace API orchestration mocks with explicit shared-hook fixtures and spies for `createReport`, `retryReport`, task `refresh`, `setCurrentMove`, and detail `refresh`. Assert the same user-visible behavior plus correct adapter arguments; do not assert hook internals.

- [ ] **Step 5: Point Galaxy presentational components at shared types**

Change `ReportGameCard.tsx` to import `ReportGameStatus` from `features/report/reportModel`, and change both `ReportGameCard.tsx` and `ReportMetaPanel.tsx` to import task/user-game contracts from shared `src/api/**`. Do not move or restyle Galaxy components.

- [ ] **Step 6: Run Galaxy and shared tests**

Run: `npm run test -- src/galaxy/pages/report src/features/report src/api/reportApi.test.ts`  
Expected: PASS with unchanged Galaxy-visible behavior.

Run: `npx tsc -b --pretty false`  
Expected: exit 0 before committing the shared-hook adapter and type-import refactor.

- [ ] **Step 7: Commit Galaxy migration**

```bash
git add katrain/web/ui/src/galaxy katrain/web/ui/src/features/report
git commit -m "reuse shared report behavior in galaxy"
```

### Task 6: Add touch-safe Settings access in the header

**Files:**
- Modify: `katrain/web/ui/src/kiosk/components/layout/Header.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/SettingsPage.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/Header.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/navigation.integration.test.tsx`

- [ ] **Step 1: Write failing Header/Settings navigation tests**

Assert a translated 48×48 header Settings button and navigation to `/kiosk/settings` with the current internal route stored in location state. Assert Settings has its own translated 48×48 back `IconButton`, returns to the validated stored route, and falls back to `/kiosk/play` for absent/external state, `/kiosk/settings` with query/hash, or any `/kiosk/settings/...` descendant. The Dock remains unchanged in this task so no destination is broken before the real Report page exists.

- [ ] **Step 2: Run navigation tests and verify failure**

Run: `npm run test -- src/kiosk/__tests__/Header.test.tsx src/kiosk/__tests__/SettingsPage.test.tsx src/kiosk/__tests__/navigation.integration.test.tsx`  
Expected: FAIL because header Settings navigation/state and the page-owned return action do not exist.

- [ ] **Step 3: Implement translated Header navigation state**

Use router navigation rather than a raw page reload for the header Settings button; pass `{ from: location.pathname + location.search }` in route state. Use `useTranslation` with a Simplified Chinese fallback for its visible/accessibility label and set explicit `minWidth`, `width`, `minHeight`, and `height` to 48.

- [ ] **Step 4: Add a dedicated Settings return control**

Add a page-owned 48×48 `IconButton` rather than relying on the existing 40 px `SubPageBar`. Parse `location.state.from` against the current origin, require an internal `/kiosk/` pathname, and reject pathnames equal to `/kiosk/settings` or beginning `/kiosk/settings/` regardless of query/hash; otherwise return to `/kiosk/play`. Keep existing Settings content and Dock behavior unchanged until the atomic Dock swap in Task 9.

- [ ] **Step 5: Run navigation tests**

Run: `npm run test -- src/kiosk/__tests__/Header.test.tsx src/kiosk/__tests__/SettingsPage.test.tsx src/kiosk/__tests__/navigation.integration.test.tsx`  
Expected: PASS.

- [ ] **Step 6: Type-check the navigation refactor**

Run: `npx tsc -b --pretty false`  
Expected: exit 0.

- [ ] **Step 7: Commit navigation**

```bash
git add katrain/web/ui/src/kiosk
git commit -m "add kiosk header settings access"
```

## Chunk 3: Kiosk Report list and import flows

### Task 7: Build the touch Report game card

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/report/ReportGameCard.tsx`
- Create: `katrain/web/ui/src/kiosk/components/report/ReportGameCard.test.tsx`

- [ ] **Step 1: Write state/action tests**

Cover selected styling; title/event/source fallback; date; move count; player names/ranks; result; truncation; translated status/action text and accessible names; normal/deep generate actions; active progress; completed open actions; failed retry; delete event isolation; and all action targets at least 48 px. Use a table covering simultaneous normal/deep combinations: completed-normal + active-deep, active-normal + completed-deep, failed-normal + completed-deep, and active superseding failed/completed for the same type without hiding the other type.

- [ ] **Step 2: Run the card test and verify failure**

Run: `npm run test -- src/kiosk/components/report/ReportGameCard.test.tsx`  
Expected: FAIL because the component is absent.

- [ ] **Step 3: Implement the card using kiosk conventions**

Follow `KifuPage` card visuals and use `KioskResultBadge`. Do not copy the Galaxy card CSS. Put infrequent actions in a touch menu without hiding current report status. Every user-facing string and accessibility label uses `useTranslation` with a Simplified Chinese fallback.

- [ ] **Step 4: Run the card test**

Run: `npm run test -- src/kiosk/components/report/ReportGameCard.test.tsx`  
Expected: PASS.

- [ ] **Step 5: Commit the card**

```bash
git add katrain/web/ui/src/kiosk/components/report
git commit -m "add kiosk report cards"
```

### Task 8: Build touch-first import flows

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/report/ReportImportMenu.tsx`
- Create: `katrain/web/ui/src/kiosk/components/report/ReportImportMenu.test.tsx`
- Create: `katrain/web/ui/src/kiosk/components/report/ReportLocalImportDialog.tsx`
- Create: `katrain/web/ui/src/kiosk/components/report/ReportLocalImportDialog.test.tsx`
- Create: `katrain/web/ui/src/kiosk/components/report/ReportLibraryImportDialog.tsx`
- Create: `katrain/web/ui/src/kiosk/components/report/ReportLibraryImportDialog.test.tsx`

- [ ] **Step 1: Write failing dialog tests**

Menu tests: both choices open the correct flow, choosing/closing clears the menu, clicks do not trigger parent card selection, and trigger/menu rows are at least 48 px. Local tests: file/paste parsing, invalid or missing SGF disablement, parsed 9/13/19 metadata, import-only/normal/deep payloads, loading lock, and fixed actions. Library tests: open-triggered fetch, search, pagination, selection reset when results change, fetch failure/retry, and the same three submit modes. At a mocked 1024×600 viewport, assert dialog paper fits the viewport, content has independent vertical scrolling, actions remain visible, document/dialog has no horizontal overflow, labels wrap deliberately, and every critical target is at least 48×48.

- [ ] **Step 2: Run dialog tests and verify failure**

Run: `npm run test -- src/kiosk/components/report/ReportImportMenu.test.tsx src/kiosk/components/report/ReportLocalImportDialog.test.tsx src/kiosk/components/report/ReportLibraryImportDialog.test.tsx`  
Expected: FAIL because the kiosk dialogs are absent.

- [ ] **Step 3: Implement near-full-screen dialogs**

Use a bounded paper height below 600 px, scroll only `DialogContent`, keep `DialogActions` fixed, wrap action labels deliberately, and use 48 px controls. Reuse `sgfToMoves`, `KifuAPI`, and shared import payload types/functions. Every new label and error uses `useTranslation` with a Simplified Chinese fallback.

- [ ] **Step 4: Run dialog tests**

Run: `npm run test -- src/kiosk/components/report/ReportImportMenu.test.tsx src/kiosk/components/report/ReportLocalImportDialog.test.tsx src/kiosk/components/report/ReportLibraryImportDialog.test.tsx`  
Expected: PASS.

- [ ] **Step 5: Commit import flows**

```bash
git add katrain/web/ui/src/kiosk/components/report
git commit -m "add kiosk report imports"
```

### Task 9: Assemble the level-one Report page

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/ReportsPage.tsx`
- Create: `katrain/web/ui/src/kiosk/pages/ReportsPage.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/layout/navTabs.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/layout/Dock.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/Dock.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/KioskApp.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/KioskLayout.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/layout/KioskLayout.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/navigation.integration.test.tsx`

- [ ] **Step 1: Write page tests for the complete list flow**

Mock shared APIs/hooks and assert first-game selection; selection preservation when still present; reset after search, page, delete, or import removes the selection; URL search/page state; queue-summary counts; both import-menu choices; import-only refresh; import+normal/deep; optimistic task display and server reconciliation; retry; delete confirmation/rejection; completed-report navigation; active-only two-second polling/progress updates; terminal polling stop; visible polling errors; and no physical-board calls.

For preview, assert 9×9, 13×13, and 19×19 propagation; first/previous/autoplay/next/last/slider behavior through `PlaybackBar`; missing SGF; malformed SGF; game-detail fetch failure with retry; card switching; and final-move initialization.

In the same red test set, assert the atomic navigation result: exactly eight translated Dock items, **复盘** opens the real `/kiosk/report` page, **设置** is absent from the Dock, `/kiosk/report` shows Header and Dock, and `/kiosk/settings` shows Header but no Dock while retaining the Task 6 return control. Update both KioskLayout suites that previously expected Settings in the Dock.

- [ ] **Step 2: Run the page test and verify failure**

Run: `npm run test -- src/kiosk/pages/ReportsPage.test.tsx src/kiosk/__tests__/Dock.test.tsx src/kiosk/__tests__/KioskApp.test.tsx src/kiosk/__tests__/KioskLayout.test.tsx src/kiosk/components/layout/KioskLayout.test.tsx src/kiosk/__tests__/navigation.integration.test.tsx`  
Expected: FAIL because the real page, route, and atomic Dock swap do not exist.

- [ ] **Step 3: Implement list/query/selection state**

Load games with `UserGamesAPI.list`, synchronize `q` and `page` query parameters, preserve a valid selection, select the first current-page item otherwise, and render translated loading/empty/network states. In the same step, register the real `ReportsPage` as `report` in `KioskApp.tsx`, replace Settings with Report in the eight-item Dock, include `/kiosk/report` and exclude `/kiosk/settings` in `L1_PATHS`, and render Dock labels through `useTranslation` with Chinese fallbacks. The Dock destination and route become live in one commit; no stub or broken destination is introduced.

- [ ] **Step 4: Implement the 1024×600 preview and playback shell**

Left: reuse `LiveBoard` and `PlaybackBar`, initialize at final move, propagate SGF board size, and show bounded missing/malformed/load-error states with retry. Right: `minWidth: 0`, fixed header/search/import, independently scrolling cards, fixed pagination, and no horizontal overflow. Every new string uses `useTranslation` with a Simplified Chinese fallback.

- [ ] **Step 5: Wire import flows and selection reconciliation**

Use `UserGamesAPI.create` and `KifuAPI.getAlbum`; support import-only/normal/deep, close only after success, show failures without discarding dialog input, refresh the game list, and select the imported game when present on the current page.

- [ ] **Step 6: Wire Report tasks, queue summary, and polling feedback**

Use `useReportTasks` for normal/deep creation, retry, optimistic state, queue summary, active progress, and polling errors. Render queue counts and pass the complete simultaneous normal/deep state to each card.

- [ ] **Step 7: Wire deletion and recovery**

Confirm before `UserGamesAPI.delete`, preserve the page on server rejection, and after success refresh games/tasks and reconcile the selection/current page. Keep all API failures visible with retry or repeatable action paths.

- [ ] **Step 8: Run list, import, navigation, and shared tests**

Run: `npm run test -- src/kiosk/pages/ReportsPage.test.tsx src/kiosk/components/report src/kiosk/__tests__/Dock.test.tsx src/kiosk/__tests__/KioskApp.test.tsx src/kiosk/__tests__/KioskLayout.test.tsx src/kiosk/components/layout/KioskLayout.test.tsx src/kiosk/__tests__/navigation.integration.test.tsx src/features/report`  
Expected: PASS.

- [ ] **Step 9: Commit the level-one page**

```bash
git add katrain/web/ui/src/kiosk katrain/web/ui/src/features/report
git commit -m "add kiosk report list"
```

## Chunk 4: Kiosk Report detail and final verification

### Task 10: Build compact Report metadata

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/report/ReportMetaPanel.tsx`
- Create: `katrain/web/ui/src/kiosk/components/report/ReportMetaPanel.test.tsx`

- [ ] **Step 1: Write metadata tests**

Cover pending/running/completed/failed labels, normal/deep, players/ranks/result/source, rules/komi, current win rate/score lead, analyzed/total progress, missing analysis, and long-title ellipsis.

- [ ] **Step 2: Run the test and verify failure**

Run: `npm run test -- src/kiosk/components/report/ReportMetaPanel.test.tsx`  
Expected: FAIL because the panel is absent.

- [ ] **Step 3: Implement a compact touch-safe panel**

Keep the component presentational. Use shared types and kiosk tokens; do not import Galaxy's `ReportMetaPanel`.

- [ ] **Step 4: Run the test**

Run: `npm run test -- src/kiosk/components/report/ReportMetaPanel.test.tsx`  
Expected: PASS.

- [ ] **Step 5: Commit metadata UI**

```bash
git add katrain/web/ui/src/kiosk/components/report
git commit -m "add kiosk report metadata"
```

### Task 11: Assemble the immersive detail page

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/ReportDetailPage.tsx`
- Create: `katrain/web/ui/src/kiosk/pages/ReportDetailPage.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/layout/SubPageBar.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/layout/SubPageBar.test.tsx`

- [ ] **Step 1: Write complete interaction tests**

Assert immersive lifecycle, square `LiveBoard`, 9/13/19 support, pending/running progressive display, historical cursor pinning, terminal polling stop, PV tap/clear, try moves/clear, territory disablement without ownership, numbers, AI markers, trend navigation, playback, and stone sound.

Assert the back bar contains a 48×48 back control, ellipsized game title, report status/type, and a 48 px-high **在研究中打开** action that uses `user_game_id`. Cover unauthenticated access, failed task retry, missing SGF with back/reload recovery, not-found/network errors with a `refresh` retry, and a retry failure that remains visible instead of blanking prior data.

- [ ] **Step 2: Run the detail test and verify failure**

Run: `npm run test -- src/kiosk/pages/ReportDetailPage.test.tsx`  
Expected: FAIL because the page is absent or still a route stub.

- [ ] **Step 3: Implement the immersive split layout**

Mirror the structural behavior of `LiveMatchPage`: full-height square board left; `minWidth: 0` right column with `SubPageBar`, compact metadata, four persistent touch toggles, `AiAnalysis`, `TrendChart`, and fixed `PlaybackBar`. Raise the shared `SubPageBar` back target from 40 to 48 px and update its focused test so live and Report secondary pages retain the larger touch target.

Build the right side of the Report back bar as a non-shrinking action group containing status/type and **在研究中打开**. Give the title container `minWidth: 0` and ellipsis; do not allow the action group to overlap or leave the viewport.

- [ ] **Step 4: Wire board interactions and Research navigation**

Use `useReportDetail`; derive PV from the tapped recommendation; reset PV on move changes; keep try moves local; navigate to `/kiosk/research?user_game_id=${game.id}`. Never invoke vision, LED, local KataGo, or cron code.

Render explicit recovery actions: `refresh` for load/network failures, shared retry API followed by `refresh` for failed tasks, and a back action for unauthenticated/missing-SGF states. Keep previously loaded board/analysis visible during a transient refresh error.

- [ ] **Step 5: Run detail and live regression tests**

Run: `npm run test -- src/kiosk/pages/ReportDetailPage.test.tsx src/kiosk/__tests__/LiveMatchPage.test.tsx src/components/live`  
Expected: PASS.

- [ ] **Step 6: Commit detail page**

```bash
git add katrain/web/ui/src/kiosk
git commit -m "add kiosk report detail"
```

### Task 12: Add exact-viewport browser coverage

**Files:**
- Create: `katrain/web/ui/tests/report-kiosk.spec.ts`
- Modify: `katrain/web/ui/playwright.config.ts` only if an existing 1024×600 project cannot be selected without affecting other suites.

- [ ] **Step 1: Add deterministic API fixtures in the Playwright spec**

Intercept auth, user games, kifu library, Report list/summary/detail/moves, and mutation requests. Provide fixtures for no-report, queued, running, normal/deep completed, failed, and long metadata.

- [ ] **Step 2: Write 1024×600 interaction and fit assertions**

Set viewport to exactly `{ width: 1024, height: 600 }`. Exercise list selection, generation, import dialogs, completed-detail entry, toggles, and Research. For every critical control—including Dock/Header actions, import actions, detail back/Research, four toggles, recommendation rows, retry, and playback controls—assert its bounding box is fully inside the viewport and has width and height of at least 48 px. Assert `document.documentElement.scrollWidth <= 1024`.

- [ ] **Step 3: Run Playwright and inspect failure/screenshots**

Run: `npx playwright test tests/report-kiosk.spec.ts --project=chromium`  
Expected: PASS if unit-tested layout is already correct. If it fails, Playwright records the exact failing assertion plus trace/screenshot; use those artifacts only to drive Step 4.

- [ ] **Step 4: Fix only verified layout/interaction issues**

Apply `minWidth: 0`, fixed action flex-shrink, ellipsis/wrapping, bounded dialog content, or explicit responsive sizing where the failing bounding box proves it is needed.

- [ ] **Step 5: Re-run Playwright**

Run: `npx playwright test tests/report-kiosk.spec.ts --project=chromium`  
Expected: PASS at 1024×600 with no horizontal document overflow and no clipped critical actions.

- [ ] **Step 6: Commit browser coverage**

```bash
git add katrain/web/ui/tests/report-kiosk.spec.ts katrain/web/ui/playwright.config.ts katrain/web/ui/src/kiosk
git commit -m "test kiosk report viewport"
```

### Task 13: Run full regression and enforce the server-only cron boundary

**Files:**
- Verify: `katrain/web/ui/scripts/verify-kiosk.sh`
- Verify: `docker-compose.yml`
- Verify: `Dockerfile.cron`
- Verify: `katrain/cron/**`
- Verify: `docs/sbc-setup/RK3588_deployment.md`
- Modify: only files required to fix a demonstrated frontend regression; do not add SBC cron configuration.

- [ ] **Step 1: Run frontend lint and unit tests**

Run: `npm run lint`  
Expected: exit 0.

Run: `npm run test`  
Expected: all Vitest suites PASS.

- [ ] **Step 2: Run both production builds**

Run: `npm run build`  
Expected: TypeScript and Vite build exit 0.

Run: `npm run build:kiosk-2d`  
Expected: build and `verify:kiosk-2d` exit 0; no kiosk import from `src/galaxy/**`, Board3D, or recorder-only code.

- [ ] **Step 3: Run backend Report regressions without requiring an SBC engine**

Run: `CI=true .venv/bin/python -m pytest tests/web_ui/test_reports_api.py tests/web_ui/test_reports_db.py tests/web_ui/test_report_analyzer.py -v`  
Expected: PASS, or environment-dependent engine cases explicitly SKIP under CI; no new backend behavior failure.

- [ ] **Step 4: Discover deployment artifacts and audit cron ownership**

Run: `rg --files -g '*.service' -g '*sbc*' -g '*deploy*' -g '*package*' -g 'Dockerfile*' -g '*compose*.yml'`  
Expected: inventory includes the existing server Docker/cron files and `docs/sbc-setup/RK3588_deployment.md`; inspect every SBC/service/package result, not only Docker files.

Run: `rg -n "katrain-cron|report_analyze" katrain/web/ui/src/kiosk katrain/web/ui/scripts/verify-kiosk.sh docs/sbc-setup/RK3588_deployment.md`  
Expected: no matches. Report kiosk code and SBC deployment documentation contain no local cron/analyzer wiring.

Run: `git diff --name-only origin/develop...HEAD -- docker-compose.yml Dockerfile.cron katrain/cron docs/sbc-setup/RK3588_deployment.md`  
Expected: no output. `origin/develop` is the recorded base of `feature/sbc-report-parity`; this base-to-HEAD audit includes already committed work and proves the feature has not changed server cron ownership or SBC deployment artifacts. If the branch is deliberately rebased before execution, update this recorded base in the plan/PR before running the audit.

Run: `rg -n "katrain-cron|report_analyze" docker-compose.yml Dockerfile.cron katrain/cron`  
Expected: existing matches are confined to server services/jobs and remain unchanged by the preceding diff check.

- [ ] **Step 5: Review the final diff for scope and translation coverage**

Run: `git diff --check`  
Expected: no whitespace errors.

Run: `git status --short`  
Expected: only intended Report/navigation/test/documentation changes are present.

- [ ] **Step 6: Perform 7-inch SBC acceptance**

On the deployed kiosk, verify touch use at native 1024×600: Dock Report entry, header Settings access, local/library import, normal/deep generation, server cron progress, completed analysis interactions, Research handoff, and absence of clipping. Confirm no `katrain-cron` unit/container/process is installed on the SBC.

- [ ] **Step 7: Commit final verified fixes and record results**

```bash
git add katrain/web/ui/src katrain/web/ui/tests katrain/web/ui/playwright.config.ts
git commit -m "finish kiosk report parity"
```

Record exact command results, skipped tests, browser screenshots, SBC model/OS, and manual acceptance findings in the eventual PR description.

## Out of scope / future track

After this plan is implemented and tested, create a separate design track to evaluate optional local free review using a smaller B18 model. Do not pre-build that abstraction here, and do not deploy `katrain-cron` to the SBC in that future exploration.
