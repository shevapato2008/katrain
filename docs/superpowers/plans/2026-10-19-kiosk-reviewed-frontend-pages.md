# Reviewed Kiosk Frontend Pages Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the user-reviewed 06–09, 11–14, 15/16/professional report, 19 and 20 Kiosk designs using existing real data and interactions.

**Architecture:** Deliver one journey through visual verification at a time. Keep existing routes, hooks and API contracts; use page-local CSS for changed surfaces. Parallel workers may prepare independent frontend slices with disjoint ownership; finish and obtain user visual confirmation for each slice before any required backend work. Production pages must never import fixture data.

**Tech Stack:** Existing React/TypeScript/Vite frontend, Vitest/Testing Library and Playwright; current kiosk shell and board components.

---

## Chunk 1: Scope, evidence and ownership

Required references: `docs/design/KIOSK-UNIFIED-REDESIGN-RULES-2026-10-14.md` and `docs/design/kiosk-current-based-redesign-2026-10-14.html` (1024×600 proposed stage, not the surrounding comparison page). User follow-up criteria below supersede older source comments. Exclude AI 01/02/03/05, local 04/05a in its separate worktree, courses, growth, settings, calibration, and backend changes. Do not redesign shared boards or introduce new APIs.

### Existing implementation inventory

All paths below are relative to `katrain/web/ui/src/`.

| Journey | Routes under `/kiosk/` | Existing capability | Remaining frontend work |
|---|---|---|---|
| 06–09 platforms | `play/pvp/lobby`; `play/cross-platform/login/:platform`; `play/cross-platform/ogs`; `play/cross-platform/golaxy`; `play/cross-platform/golaxy/setup/:mode`; `play/cross-platform/engine/:platform` | `LobbyPage`, `PlatformLoginPage`, `PlatformLobbyPage`, `GolaxyHomePage`, `GolaxyPregameSetupPage`, `PlatformEngineSetupPage`: connection/login, SMS/password, room/challenge/resume, engine choice and setup already exist. Legacy `play/cross-platform` redirects to play. | Compact action buttons and raised connected tabs; left-aligned 07b/08 inputs; engine selector raised surface and chevron. Verify existing handlers rather than rebuild platform logic. |
| 11–14 training | `tsumego`; `tsumego/:level`; `tsumego/:level/:category`; `tsumego/:level/:category/:unit`; `tsumego/:level/:category/wrong`; `tsumego/problem/:problemId` | `TsumegoPage` fetches actual levels/category counts but renders a flat list and old mirrored-shell layout. Category/unit routes, preview selection, wrong filtering and stored wrong sequence, `?set=wrong`/`?set=all`, progress and problem controls already exist. | Real carousel drag/depth/pie; consistent category buttons; same-surface 单元/错题 tabs; larger problem cards and attempts/last duration; remove redundant resume CTA and 综合训练 jump in specified screens; 实体盘 wording/icon. |
| 15/16 archive | `kifu`; `kifu/:kifuId/replay`; `kifu/:kifuId` | `KifuPage` already uses `PAGE_SIZE=20` and analysis/replay routing, but cards currently navigate directly; it lacks the approved selected-card final-board preview. `KioskLayout` currently supplies an unrelated `GoConsoleRail`. `KifuDetailPage` handles replay. `KifuReportDetailPage` already shares `ReportAnalysisRail` with personal reports. | Compare current list against approved card geometry and final-board selection; left 查看棋谱/查看分析 availability; reuse existing numeric page jump. Preserve distinct unanalysed replay and analysed report. |
| 19 personal games | `report` (not `research`) | `ReportsPage` already fetches user games, selected SGF preview, report states/polling, normal/deep creation, delete confirmation and deletion API, search/filter/paging. Current `PAGE_SIZE=12`. `ResearchPage` is the research destination, not history owner. | 20/page plus page jump, aligned cards, final-board preview, left 查看棋谱 and tiered 分析报告 menu (500/2000 generate/view). Preserve loading/errors and truthful status. |
| 20 report tabs | `report/:taskId` and archive report above | `ReportDetailPage`, `ReportAnalysisRail`, `MoveGradePanel`: six analysis panels, filters, recommendations, charts, trial moves, metadata, toggles and playback already exist. | Single horizontal swipeable tab strip with selected tab visible. Share fix with archive report; do not reimplement stats or analysis. |

CSS ownership: existing shell `kiosk-shell/go-screens.css`, `shell-redesign.css`, `setup-redesign.css` and `KioskLayout.tsx` are shared and must have one integration owner. Existing page-local files include `kiosk/pages/LobbyPage.css`, `kifuLibrary.css`, `kiosk-shell/ogs-home.css`, `golaxy-home.css`; report styling is `kiosk/components/report/reportRail.css` and `reportWorkspace.css`.

### Task 1: Establish minimal shared setup (integration owner only)

- [ ] Read `ui-ux-pro-max`, both required design references and current tokens. Integrator owns shared font/numeric markup: SmartBox Kai Chinese, IBM Plex Mono newly drawn Arabic digits, formal text only 18/22/28 px, and raised soft keys with depressed pressed states. Keep each page’s full approved stage composition; do not restrict work to isolated requested controls. No new design-system exercise.
- [ ] Record current git status and preserve unrelated changes. Read this plan against the latest approved artifact and user criteria before touching code.
- [ ] Capture one baseline per journey at 1024×600 using existing Playwright fixtures/helpers. Use stable recorded payloads only in tests; use real API pages for final interaction checks when available.
- [ ] Remove the training home mirror only for the exact `/kiosk/tsumego` route in `kiosk/components/layout/KioskLayout.tsx`; preserve nested training boards and other L1 routes. Implement corresponding narrowly scoped shell class/CSS. Also migrate exact `/kiosk/kifu` from the shell-provided `GoConsoleRail` to a page-owned two-column layout. Integrator owns shell routing/layout/CSS; archive worker owns the page final-board preview, selected cards and replay/report actions. Agree the page wrapper contract before parallel edits.
- [ ] Register any new page-local stylesheet imports from their owning pages. Avoid concurrent edits to `KioskApp.tsx`, shared shell files, `src/api.ts`, translation infrastructure, and common icons. Integrator owns shared `kiosk/components/PhysicalBoardButton.tsx`, shared fonts and translated 实体盘 labels; coordinate its call sites with AI/local owners so their completed flows do not regress. Rename 实体棋盘→实体盘 across reviewed pages, including `GolaxyHomePage`, and use a consistent distinct physical-board icon.

Existing fourup specs are historical and may have stale routes, selectors and references: each worker must first update only its touched specs to current routes/selectors and extract the full approved proposal stage at 1024×600. Do not blindly treat old screenshot references as acceptance. Browser checks must use this worktree’s live Vite source: `KATRAIN_PW_VISUAL_PORT=5279 npx playwright test --config=playwright.visual.config.ts <targeted-specs>` (choose another dedicated free port for parallel worktrees). If using a static server instead, run the current build before serving it. Never validate stale `katrain/web/static` output.

Worker boundaries: platform owns Task 2 files; training owns Task 3 files; archive/history/report owns Tasks 4–6 in order. The integration owner handles shared shell and any genuinely required icon registration after workers specify it. No simultaneous workers edit `ReportsPage`, report components, or shared CSS. Parallel preparation does not authorize skipping per-slice user confirmation.

## Chunk 2: User journeys

### Task 2: Platform entry → login → lobby/setup (06–09)

**Modify:** `kiosk/pages/LobbyPage.tsx`, `LobbyPage.css`, `PlatformLoginPage.tsx`, `PlatformLobbyPage.tsx`, `PlatformEngineSetupPage.tsx`, `GolaxyHomePage.tsx`, `GolaxyPregameSetupPage.tsx`, `kiosk-shell/ogs-home.css`, `golaxy-home.css`; create `kiosk/pages/platformReviewed.css` for scoped overrides only if needed.

- [ ] Compare the approved lobby/login/engine stages with current markup. Change action dimensions and connected-pill relief without changing connection state meanings.
- [ ] Left-align labels, input text and placeholders for reviewed login variants; retain validation, SMS cooldown, keyboard and submit behavior.
- [ ] Add a visible dropdown chevron and raised selectable engine card; preserve actual 39-tier options, selected value, rules and start handler. Missing/error data must not display a fabricated opponent.
- [ ] Run `npm test -- src/kiosk/pages/LobbyPage.test.tsx src/kiosk/pages/PlatformLoginPage.test.tsx src/kiosk/pages/PlatformLobbyPage.test.tsx src/kiosk/pages/PlatformEngineSetupPage.test.tsx src/kiosk/pages/GolaxyHomePage.test.tsx src/kiosk/pages/GolaxyPregameSetupPage.test.tsx` from `katrain/web/ui`. Add tests only for changed behavior, not decorative CSS.
- [ ] Preview compact lobby, one left-aligned login variant and engine dropdown at 1024×600; reuse `tests/kiosk-screen-06-lobby.fourup.spec.ts`, `kiosk-screen-07-09-platform.fourup.spec.ts`, `kiosk-screen-09-setup.fourup.spec.ts` fixtures. Check other login variants with a focused DOM assertion rather than full recapture.
- [ ] Complete the visual/user confirmation gate below before backend work for this journey.

### Task 3: Level → category → units/wrong → problem (11–14)

**Modify:** `kiosk/pages/TsumegoPage.tsx`, `TsumegoCategoriesPage.tsx`, `TsumegoUnitsPage.tsx`, `TsumegoUnitListPage.tsx`, `TsumegoProblemPage.tsx`; create `kiosk/pages/trainingReviewed.css`; retain existing `tsumegoUnits.ts`, progress context and hooks unless a demonstrated frontend defect requires a small change.

- [ ] Replace level rows with the approved four-group carousel. Use actual API levels/counts, pointer drag with pointer capture, drag threshold preventing accidental navigation, bounded selection and release snap; support tap/keyboard selection. Use minimal local state, no carousel library.
- [ ] Render depth and category pie from available real counts. The artifact's captured 15级 percentages are reference data, not production constants. Missing counts show unavailable state; grouping must retain access to every returned level.
- [ ] Make 11a category buttons equal-sized. Remove the redundant last-question banner from units; retain resume elsewhere only where approved.
- [ ] Show 单元/错题 tabs on the units/browser surface. Wrong-book filters current level and category to attempted, still-unsolved problems using existing progress semantics. Unknown progress remains an error/unknown state, not zero mistakes.
- [ ] On 13 remove the 综合训练 jump; wrong tab filters problem cards rather than introducing a new global set. Enlarge cards and show `TsumegoProgressContext` actual `attempts` and existing `lastDuration`; absent duration displays `—`. Do not add a backend field before visual confirmation.
- [ ] Preserve wrong-sequence snapshot and query through previous/next, correct-answer advance and return. Make page 14 controls uniform in size within each operation group; rename physical controls 实体盘 with the shared distinct physical-board icon; preserve calibration/disconnected gates and physical behavior.
- [ ] Add focused Vitest coverage for carousel drag-versus-tap and tab filtering only where existing tests do not cover it. Run `npm test -- src/kiosk/KioskApp.routes.test.tsx` plus any changed page/hook tests.
- [ ] Run focused browser flows `KATRAIN_PW_VISUAL_PORT=5279 npx playwright test --config=playwright.visual.config.ts tests/kiosk-tsumego-list-preview.spec.ts tests/kiosk-tsumego-wrong.spec.ts` against this worktree’s Vite source. Use existing 11/12/13/14 fourup fixtures for representative 1024×600 captures, adding only the new carousel and filtered wrong-book cases.
- [ ] Complete the visual/user confirmation gate; verify actual attempts/duration display and preserve missing-value states; no backend work is required for these existing fields.

### Task 4: Professional archive → selected final board → replay/report (15/16)

**Modify:** `kiosk/pages/KifuPage.tsx`, `kifuLibrary.css`, `KifuDetailPage.tsx`; only adjust `KifuReportDetailPage.tsx` if archive-specific presentation requires it. Shared report styling belongs to Task 6.

- [ ] After integrator supplies the page-owned two-column shell, replace current direct-navigation card clicks with selection. Retain existing 20-record server pagination. Selecting a card previews the final SGF position; selected card stays selected until selection/data changes. Keep loading/malformed SGF behavior honest.
- [ ] Implement page-owned selected-card/final-board preview and align card geometry with approved artifact; place 查看棋谱/查看分析 in left panel. Disable unavailable actions based on actual SGF/analysis availability, and route unanalysed games to replay versus analysed games to report.
- [ ] Reuse existing `CompactPagination`, which already supplies numeric page jump. Verify bounds, page changes and selection reset; do not create a duplicate jump control or fetch all records locally.
- [ ] Run `npm test -- src/kiosk/pages/KifuReportDetailPage.test.tsx` and relevant existing archive tests; add only selection/action/page-jump behavior coverage where absent.
- [ ] Capture list with selection and one unanalysed replay using `tests/kiosk-screen-15-kifu.fourup.spec.ts` and `kiosk-screen-16-kifu-detail.fourup.spec.ts`. Verify analysed report after Task 6 with the shared report change.
- [ ] Complete the visual/user confirmation gate.

### Task 5: Personal games → final board → tiered report/view/delete (19)

**Modify:** `kiosk/pages/ReportsPage.tsx`; create `kiosk/pages/personalGamesReviewed.css` if current shared selectors cannot be scoped safely. Preserve feature report hooks and existing API methods.

- [ ] Change `PAGE_SIZE` from 12 to 20. Keep query/source/page server filters and independent list scroll. Reuse `CompactPagination` numeric page jump rather than create another control; last-page deletion uses existing page correction.
- [ ] Align cards and final-board selected preview with archive presentation without extracting a generic library abstraction unless both actually need it.
- [ ] Put 查看棋谱 and 分析报告 menu on the left; standard 500/deep 2000 each derive generate/view/working availability from real task tier/status. Preserve in-place generation, polling and retry; do not treat a normal report as a completed deep report.
- [ ] Reuse existing delete confirmation/API path; validate game and report state disappear after successful deletion and remain on failure. If API deletion semantics do not guarantee report removal, record the contract gap and stop at truthful frontend behavior pending visual confirmation.
- [ ] Run `npm test -- src/kiosk/pages/ReportsPage.test.tsx src/kiosk/pages/ReportsPage.polling.test.tsx src/kiosk/pages/ResearchPage.userGame.test.tsx`. Extend existing tests only for 20/page, page jump and tier-menu dispatch where missing.
- [ ] Capture selected final-board layout and open tier menu at 1024×600 using `tests/kiosk-screen-19-review.fourup.spec.ts`; verify one real navigation/generation path where connected data is available.
- [ ] Complete the visual/user confirmation gate.

### Task 6: Personal/professional report tabs (20)

**Modify:** `kiosk/components/report/MoveGradePanel.tsx`, `reportWorkspace.css`, `reportRail.css` if needed; page files only if props demonstrably require change.

- [ ] Keep all six current panels and filters. Make tabs one nonwrapping horizontal row with touch scrolling; keep expand/help controls usable and selected tab visible on selection/keyboard navigation. Use a container-scoped scroll operation; do not scroll the entire kiosk viewport.
- [ ] Preserve playback, board geometry, metadata modal, variation/trial moves and no-analysis states. Apply the shared strip to both personal and professional report.
- [ ] Add a focused tab-selection/visibility test if absent; run `npm test -- src/kiosk/pages/ReportDetailPage.test.tsx src/kiosk/pages/KifuReportDetailPage.test.tsx` plus existing MoveGradePanel tests.
- [ ] Capture initial and far-right tab at 1024×600 with existing `tests/kiosk-screen-20-report.fourup.spec.ts`; inspect one professional report with same strip. Validate other panels through existing interaction tests, without six redundant full visual reviews.
- [ ] Complete the visual/user confirmation gate.

## Chunk 3: Gates and delivery

### Visual/user confirmation gate (each journey)

- [ ] Check full-stage parity for every changed page, including shared fonts/digits, all visible text, raised controls, shell, board and content composition. Produce matching 1024×600 approved-reference and implementation captures, side-by-side plus overlay/difference, using the existing screenshot workflow. Record only actual differences: composition, spacing, hierarchy, font/color/material, icons, copy and state semantics.
- [ ] Request one Astra visual/code review of the completed frontend slice, scoped to its changed files and approved reference. Fix material findings; do not expand low-risk styling into security/tooling audits.
- [ ] Present the visible running frontend to the user for confirmation. Existing artifact approval authorizes frontend implementation; it does not replace the requested implementation visual acceptance before backend work.
- [ ] Keep a short field/authority/loading/error/retry/privacy/resource note for the slice. Any test fixture remains isolated in Playwright/Vitest; production keeps real APIs. Remove temporary preview entry points when acceptance finishes.

### Final integration

- [ ] Plan reviews are limited to at most two Astra reviews total; combine related plan findings and avoid review loops. Implementation reviews follow the user-requested Astra visual/code review, proportionate to risk.
- [ ] Read relevant Context7 docs only if implementation needs library-specific syntax or behavior; repository inventory alone needs no docs lookup.
- [ ] Integrate confirmed frontend slices serially, preserve local-game worktree changes, and run `npm run build` once after integration. Existing build output under `katrain/web/static` must be handled according to repository policy; do not stage generated output automatically.
- [ ] Stop after focused checks and representative previews establish acceptance. Report implemented routes, verification, remaining contract gaps and user confirmation status. Do not claim backend integration, deployment or release; implementation may create focused commits after verification; deployment/push remains outside this plan unless requested.
