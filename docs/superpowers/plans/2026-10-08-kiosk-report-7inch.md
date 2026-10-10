# Kiosk 7-inch library and shared report implementation

**Goal:** Implement the user-approved HTML at 1024×600 in both personal and professional kiosk reports, preserving the 516×516 board and real report interactions.

**Architecture:** Keep existing API, parsing, sound and grading logic. ReportAnalysisRail owns a fixed metadata/workspace/tools/playback layout. MoveGradePanel hosts recommendation plus five chart tabs in the same workspace and uses existing grade calculations/help content. Library keeps its existing paginated API and board preview. Design fixtures stay in docs only.

**Tech stack:** Existing React/TypeScript, scoped CSS, FastAPI/PostgreSQL APIs, Vitest and Playwright.

## Implementation checklist

- [x] Shared report workspace: adapt `src/kiosk/components/report/MoveGradePanel.tsx`, add scoped `reportWorkspace.css`. Optional recommendation node adds a sixth tab; existing callers remain compatible. Tab widths 56/56/56/56/84/88; grouped label and active circle-i gap 3px, centered. Filters 54×44, 4px gap, rail62px; plots resize using existing measurements. Expand view preserves active tab/filters. No permanent explanatory block.
- [x] Report rail and page integration: `ReportAnalysisRail.tsx`, scoped `reportRail.css`, `KifuReportDetailPage.tsx`, `ReportDetailPage.tsx`, `KioskReportPlayback.tsx`. Four rows 104/300/44/44, 8px gaps. Header combines back/title/details, players, winbar, result/rules/komi. Honest unavailable state. Top5 and actual sixth row, no duplicate footer; keep variation, trial, territory, advice, sound and navigation. Six tools with shared icons; no kiosk3D.
- [x] Library: `KifuPage.tsx` and scoped `kifuLibrary.css`: fixed search/count/pagination, bounded list. No source text; report only when has_analysis, otherwise replay. Preserve page size20, search, preview and pagination.
- [x] Backend contract: inspect kifu/report response serialization and relevant tests. Ensure candidate ordering, actual move, nullable metrics, availability/parameters and personal ownership are sufficient. Fix only concrete missing behavior; no new schema or reanalysis required.
- [x] Verification: targeted existing report/library Vitest tests and updated behavior coverage; typecheck/build; relevant backend tests. Browser screenshots of real responses at1024×600 for library, professional/personal reports and representative chart/help state. Compare runtime against approved HTML (side by side and overlay); independent gpt-6-astra max visual/code review, fix blockers.
- [ ] Delivery: follow previously authorized integration flow—catch up develop, commit/push branch, merge/push develop, update smartbox vendor/katrain, deploy home-ubuntu/ucloud-v100 and visually verify. Preserve unrelated work. If external connection is unavailable, report exact unfinished step without claiming release.

## Contract / boundaries

Existing report APIs remain authoritative. Never ship mock SGFs or docs fixtures in application code. Availability follows valid analysis status and parameters. Board geometry, engine parameters, rule policy and GPU batch assignment stay as already accepted. List sources may remain stored but are not presented on cards. Real private reports retain ownership checks.

## Targeted checks

`npm test -- <kiosk Kifu/Report tests and reportCandidates tests>`; `npm run build`; focused pytest kifu/report API contract tests. Use existing browser tooling and private auth storage; never output cookies. Keep review proportional: one focused plan review and final runtime/code review; repeat only to fix a concrete blocker.

## Verification results

- 2026-10-08: 101 targeted frontend tests passed; two Playwright personal/professional report flows passed. Full and kiosk-2d builds passed, including the no-three.js kiosk boundary check.
- Backend contract: 109 passed, one PostgreSQL-only planner test skipped. Existing report/list contracts need no schema or backend change.
- Real home-ubuntu API preview at 1024×600: board 516×516 at x16/y70; report rail 460×516 at x548/y70; tab widths 56/56/56/56/84/88; filters 54×44 in normal and expanded views. Twenty list records, no source labels. Navigation triggered the existing stone sound playback. Physical device audio remains a device check.
- Same-viewport reference, runtime, side-by-side and overlay inspected. Existing board renderer/material retained; right rail geometry, compact label/info grouping, tools and chart hierarchy match the approved design. Explanations retain the theme and are opaque after animation.
- Independent gpt-6-astra max plan, final code and visual reviews approved. Personal ownership and report availability remain authoritative. Design fixtures remain isolated in docs.
- Caught up to develop 90895fdf without conflicts; delivery below is still pending.
