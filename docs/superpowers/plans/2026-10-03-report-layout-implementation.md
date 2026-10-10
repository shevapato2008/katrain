# Shared analysis report layout implementation plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Bring the Galaxy professional and personal report pages and the 1024×600 kiosk report pages into line with the approved HTML preview while preserving their existing analysis data and interactions.

**Architecture:** Keep the existing data hooks and board renderers. Update the shared Galaxy `ReportAnalysisLayout`, `ReportMetaPanel`, `AiAnalysis`, and report controls used by both report routes. Update the shared kiosk `ReportAnalysisRail` and its CSS used by both kiosk routes. Keep professional and personal actions distinct.

**Tech Stack:** React, TypeScript, MUI, kiosk CSS, Vitest, Playwright.

---

## Chunk 1: Galaxy reports

### Task 1: Fixed rail and compact recommendations

**Files:** `katrain/web/ui/src/galaxy/components/report/ReportAnalysisLayout.tsx`, `katrain/web/ui/src/components/live/AiAnalysis.tsx`, `katrain/web/ui/src/galaxy/pages/KifuReportDetailPage.tsx`, `katrain/web/ui/src/galaxy/pages/report/ReportDetailPage.tsx`.

- [x] Make professional layout omit the redundant entry action row; retain personal research/recompute actions.
- [x] Set report rail rows to the approved 154px identity, 250px recommendations, flexible analysis, compact controls, and 58px playback.
- [x] Bound candidate rows to four visible 36px rows with a local scrollbar for a fifth candidate; retain all five in the DOM and on the board.
- [x] Replace analysis expand text with an accessible icon, and ensure the fixed analysis card stays in place when changing moves or tabs.
- [x] Preserve status, actual-move information, error/retry behavior and all other existing analysis fields.

### Task 2: Identity and controls

**Files:** `katrain/web/ui/src/galaxy/components/report/ReportMetaPanel.tsx`, `katrain/web/ui/src/galaxy/pages/live/LiveMatchDisplayControls.tsx`.

- [x] Keep event/date in the identity card; size player names like nearby text and retain scores, result, rules and komi.
- [x] Align report controls with the approved two-row layout: action buttons first; move numbers and coordinates as switches second.
- [x] Keep advice, territory, try-move and clear interactions and accessible names.

## Chunk 2: Kiosk reports

### Task 3: Shared 7-inch rail

**Files:** `katrain/web/ui/src/kiosk/components/report/ReportAnalysisRail.tsx`, `katrain/web/ui/src/kiosk-shell/go-screens.css`, `katrain/web/ui/src/kiosk/pages/KifuReportDetailPage.tsx`, `katrain/web/ui/src/kiosk/pages/ReportDetailPage.tsx`.

- [x] Keep the 516px board and 460px rail at 1024×600 and apply the approved report spacing, typography and touch targets to both routes.
- [x] Keep five recommendations, the bounded analysis/details modal, and compact navigation visible without scrolling the completed rail.
- [x] Preserve distinct professional replay and personal research/recompute actions and honest pending/running/error states.

## Chunk 3: Verification

### Task 4: Focused tests and target-size previews

**Files:** Existing report page tests and `docs/design/analysis-report-review.md`.

- [x] Add or adjust focused assertions for the new report controls, five candidates, and professional/personal actions.
- [x] Run targeted Vitest tests and the TypeScript build.
- [x] Capture one real Galaxy screenshot at 2048×1080 and one real kiosk screenshot at 1024×600, comparing each to its approved HTML preview at the same viewport.
- [x] Record any remaining design difference and remove temporary browser fixtures after verification.
