# Analysis Report Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Give professional kifu and personal review reports one consistent, readable, fixed-position analysis layout on Galaxy desktop and the 1024×600 RK3562 kiosk, with five AI recommendations and no whole-rail scrolling.

**Architecture:** Keep the existing report data hooks, `LiveBoard`, grade calculation, charts, and navigation. Compose the same report sections for personal and professional entry points within each platform. Move long explanations and the full kiosk analysis into bounded dialogs. Preserve all existing report data and failure/progress states. The HTML artifact at `docs/design/analysis-report-preview.html` is the visual target, with the independent Astra review decisions recorded below.

**Tech Stack:** React, TypeScript, MUI (Galaxy), kiosk CSS, Vitest, Playwright.

---

## Design decisions and data contract

- Desktop target viewport: 2048×1080. Kiosk target: 1024×600. The board remains the existing textured `LiveBoard`; the right sections use fixed positions and no whole-rail scroll.
- One identity line gives the event/title and date, one player line gives black/white names and a clearly attributed score lead, one win line gives both labeled rates, and one detail line gives result/rules/komi. A detail dialog retains round, ranks, source, report type, task status, visits and other metadata. Remove repeated `A vs B` title and status chips from the visible rail.
- Exactly five candidate slots, with disabled dashes when the engine supplied fewer. Keep all stored candidates for grade and match calculations. The actual played move remains independently available outside the five-row grid (Galaxy) or in game details (kiosk), with missing evaluation stated explicitly. Recommendation percent uses PSV over **all stored candidates**, falling back to visits over all stored candidates; the actual-move comparison never changes this denominator. Both tables and board markers convert stored black-perspective lead/win rate to the SGF-derived mover; the identity bar remains explicitly black/white. Resolve the mover from the SGF move color at the current board cursor (or opposite the last move at game end), rather than turn parity, for handicap and white-to-play games.
- Desktop analysis keeps the existing five tabs in a fixed panel and expands that same mounted panel in place to read long seven-grade distributions, filters, explanatory text and match denominators without losing the selected tab. Kiosk gives five always visible candidates and opens the existing `MoveGradePanel`/plot in a fixed analysis dialog; preserve its tabs, filters, chart click-to-move and details.
- Tools and navigation are fixed. Galaxy uses `试下／领地／手数` and `支招／坐标` in two rows. Kiosk puts `领地／手数／支招／坐标` together as four pressed-state toggles beneath entry actions, giving all controls at least 44px. The coordinate toggle controls ruler visibility while reserving ruler space to prevent board geometry jumps. Preserve clear variation, playback, research/recompute, kifu route, loading, error and retry.
- Backend check: the current personal and professional offline report path both call `katrain/cron/report_position.py::position_snapshot`, which stores up to ten candidate moves including PSV. `katrain/web/interface.py` is a separate legacy path and does not define the report contract. No database migration is needed; five limits only presentation, never the stored top-ten data or match statistics.

## File map

- `docs/design/analysis-report-preview.html`: reviewed HTML target and local interactive states.
- `katrain/web/ui/src/components/live/LiveBoard.tsx`: remove report marker cap by configurable limit, default three for other consumers.
- `katrain/web/ui/src/components/live/AiAnalysis.tsx`: compact five-row report variant, fixed denominator, SGF-derived mover and separate actual-move comparison; preserve default behavior elsewhere.
- `katrain/web/ui/src/galaxy/components/report/ReportMetaPanel.tsx`: compact report identity and detail dialog.
- `katrain/web/ui/src/galaxy/components/report/ReportAnalysisLayout.tsx`: reusable fixed Galaxy rail composition and in-place analysis expansion for personal and professional reports.
- `katrain/web/ui/src/galaxy/pages/report/ReportDetailPage.tsx`, `katrain/web/ui/src/galaxy/pages/KifuReportDetailPage.tsx`: wire shared layout, five markers/rows and entry-specific actions/states.
- `katrain/web/ui/src/kiosk/components/report/ReportAnalysisRail.tsx`: reusable kiosk fixed layout, five rows, detail/analysis dialog, tool rows and playback slots.
- `katrain/web/ui/src/kiosk/pages/ReportDetailPage.tsx`, `katrain/web/ui/src/kiosk/pages/KifuReportDetailPage.tsx`: keep data/behavior owners, use the shared kiosk rail.
- `katrain/web/ui/src/kiosk-shell/go-screens.css`: target-size geometry, type and contrast for kiosk report only.
- Focused tests beside touched components and one representative Playwright screenshot per target viewport.

## Chunk 1: Shared behavior and desktop

### Task 1: Five recommendations and board markers

- [x] Add a report-scoped marker limit prop to `LiveBoard`, defaulting to the existing three. Pass five from the four report pages; do not change live/research defaults.
- [x] Pass `topN={5}` to Galaxy `AiAnalysis`; calculate report percentages from all candidates, keep an actual-move comparison outside five rows and show missing values honestly. Pass SGF-derived mover and compact row heights with a scoped prop/class.
- [x] Test the marker limit and five-row rendering with a six-candidate fixture. Run `npm test -- --run src/components/live/LiveBoard.test.tsx src/components/live/AiAnalysis.test.tsx` from `katrain/web/ui`.
- [x] Include the behavior change in the feature commit.

### Task 2: Fixed Galaxy report composition

- [x] Refactor `ReportMetaPanel` to a compact four-line identity/win block and an accessible detail dialog containing all removed metadata. Preserve translated result/rules, ranks, status and source.
- [x] Add `ReportAnalysisLayout` as a report-only rail grid with identity, five-row recommendations, existing five-tab `TrendChart`, display/action rows and playback fixed in place. Do not change `BoardPageShell` for unrelated board pages.
- [x] Wire the professional and personal Galaxy report pages to the same composition. Preserve task progress/errors, try/territory/numbers/advice/coordinates, personal research and retry, professional kifu navigation, and move navigation.
- [x] Run focused existing report tests and TypeScript build; inspect the desktop page at 2048×1080 against the artifact. Correct clipping/scrolling and contrast found there.
- [x] Include Galaxy changes in the feature commit.

## Chunk 2: RK3562 report

### Task 3: Fixed kiosk rail and complete analysis dialog

- [x] Add a reusable `ReportAnalysisRail` with an 80–84px identity, five 44px candidate rows, fixed action/toggle/navigation rows. Include a details dialog and a bounded analysis dialog containing the existing complete `MoveGradePanel` and `ReviewWinratePlot`.
- [x] Wire personal and professional kiosk report pages to this rail. Keep their existing hooks, errors, retry, route actions, variation selection and chart click-to-jump. Make five rows and board markers agree; use PSV-first percent. Show actual played move separately when outside five.
- [x] Put `领地／手数／支招／坐标` in one kiosk toggle row. Reserve ruler dimensions when coordinates are hidden. Keep every touch control at least 44px at 1024×600.
- [x] Run focused kiosk report tests and TypeScript build. Capture 1024×600 viewport and compare to the artifact; verify no right-rail scroll and open dialog tab/filter/close interactions.
- [x] Include kiosk changes in the feature commit.

## Chunk 3: Integration verification

### Task 4: Cross-entry regression

- [x] Run targeted unit tests for both Galaxy and kiosk personal/professional report paths, the board and analysis components.
- [x] Run representative browser previews at 2048×1080 and 1024×600 for completed, missing position, running and failed reports where existing fixtures support those states. Check board, fonts, five recommendations, details, tab content, playback, and no clipped controls.
- [x] Confirm no production fixture data or debug preview controls entered runtime components. Record any remaining gaps and the exact commands/results.
- [x] Include documentation and review screenshots in the feature commit; leave generated Playwright artifacts untracked.

## Review checkpoints

- Independent `gpt-6-astra max` visual review on 2026-10-03 rejected the initial simplified kiosk miniature chart and confirmed the five-row + analysis-dialog arrangement, two-level type, preserved metadata, and separate toggles. The revised artifact is `docs/design/analysis-report-preview.html`; generated `analysis-report-desktop-v2.png` and `analysis-report-kiosk-v3.png` show the target viewports.
- After Chunk 1 and Chunk 2, request plan/code review scoped to the changed files. Resolve correctness and data contract issues; avoid broad unrelated redesign.
- Second and final independent Astra review identified clipped desktop chart labels, controls overlap, untranslated raw metadata, black/white perspective mismatch between table and board, and missing SGF actual-move fallback. These were fixed in the implementation and checked with focused browser and unit tests. The running/failed report notices may extend the kiosk rail and permit scrolling in those exceptional states; completed reports fit without scrolling at 1024×600.
