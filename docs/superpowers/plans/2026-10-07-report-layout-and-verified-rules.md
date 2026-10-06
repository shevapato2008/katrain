# Report Layout and Verified Analysis Rules Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development for independent scopes. Keep tests and review proportional; production data and analysis parameters require explicit integrity checks.

**Goal:** Deliver the requested Galaxy/kiosk report corrections, restore move audio, eliminate unsupported rule defaults in professional analysis, rerun verified existing reports on home-ubuntu and sync results to production.

**Architecture:** Reuse existing report, candidate and chart components. Resolve analysis rules and komi from explicit evidence before admitting professional jobs; retain raw SGF provenance and distinguish missing metadata from verified parameters. Persist effective parameters with each job and verify them during execution and transfer.

**Tech Stack:** React/MUI, HTML design artifact, FastAPI/SQLAlchemy/PostgreSQL, KataGo JSON analysis, dual RTX3090 workers.

## Authorization and evidence

- User explicitly authorized overnight implementation, max-effort gpt-6-astra visual/technical decisions, tests, code review, deployment to both servers and reanalysis/sync. A reviewer can approve the design on the user's behalf.
- Prototype: `docs/design/analysis-report-v2.html`; source CSS/JS isolated in this directory. Original artifact remains intact. Never import prototype fixtures into product code.
- 24171 SGF contains KM[6.5], no RU. API rules=null. Both professional UI and cron parser currently default to Chinese, producing an unsupported rule assertion. Komi alone cannot identify the rule set.
- Rule ambiguity is a data integrity issue independent of visual work; backend investigation and evidence collection can proceed while prototype review runs.

## Task 1 — Design and visual gate

Files: `docs/design/analysis-report-v2.html`, `report-v2-preview.css`, `report-v2-preview.js`, review notes and screenshots.

- [ ] Preserve existing theme fonts, materials, board/sidebar/rail geometry, labels and chart statistics.
- [ ] Four equal action columns; board display row uses the same width/height, three buttons Galaxy, no 3D kiosk.
- [ ] Top five candidates; append actual move as sixth row when outside five. Use actual candidate metrics if available, otherwise honest em dashes. Remove the separate actual-move footer.
- [ ] Vertical left subtab/filter groups, responsive plots filling remaining width and height, smaller independent chart labels.
- [ ] Help beside chart tabs: delayed hover and click; touch click; outside/Escape close; full explanations/count limitations retained in popover.
- [ ] Inspect five tabs plus match distribution, actual-sixth row, help and detail popup at 2048x1080, 1440x900 and kiosk1024x600. No whole-rail scroll.
- [ ] Run ui-ux-pro-max after initial Claude Design HTML; fix concrete contrast/interaction findings.
- [ ] Independent gpt-6-astra max visually reviews rendered screenshots, revises until approved. Record approval.

## Task 2 — Verify rules and make parameter admission honest

Files: `katrain/cron/sgf.py`, `katrain/cron/jobs/kifu_analyze.py`, `katrain/web/kifu/provenance.py`, `identity.py`, relevant DB models/migration, `scripts/backfill_kifu_analysis.py`, `scripts/kifu_batch_transfer.py`, `scripts/sync_kifu_analysis.py`, `katrain/web/api/v1/endpoints/kifu.py`, focused pytest files.

- [ ] Audit already analyzed professional albums, raw RU/KM, duplicate records, current effective parameters and source evidence. Do not infer Japan/Korea from6.5 or China from7.5.
- [ ] Define minimal resolver: supported explicit SGF rule + finite explicit komi, or verified exact-game/event policy with recorded evidence. Unknown/unsupported/conflicting metadata is unresolved, not an implicit Chinese default.
- [ ] Preserve raw metadata; store effective rules/komi and verification provenance with jobs. Workers and import/export validate the same immutable parameters; changing parameters cannot reuse earlier position rows.
- [ ] Existing unverified results are not advertised as verified reports. Admission/execution rejects unresolved parameters with actionable status; personal/live explicit choices keep existing behavior.
- [ ] Write focused failing regression tests for missingRU, unsupportedRU, explicit valid pairs, zero komi, evidence override conflicts, worker guard and transfer parameter mismatch; implement and run targeted tests.
- [ ] Verify formal competition evidence when possible. If actual parameters cannot be established, keep that game unresolved and report the limitation; an agent decision is not a substitute for evidence.

## Task 3 — Product presentation and sound

Files: `galaxy/components/report/ReportAnalysisLayout.tsx`, `ReportMetaPanel.tsx`, `galaxy/components/board/BoardDisplayControls.tsx`, `components/live/AiAnalysis.tsx`, `TrendChart.tsx`, `kiosk/components/report/ReportAnalysisRail.tsx`, `MoveGradePanel.tsx`, `kiosk-shell/go-screens.css`, report detail pages/hooks, localization.

- [ ] After visual approval, implement artifact geometry using existing components; share icons/labels/dimensions with game/live/report.
- [ ] Replace forced18px SVG text override with appropriate12–14px chart text; measure chart area across all tabs.
- [ ] Render actual sixth row and no redundant footer without inventing winrate/score/prior.
- [ ] Restore sound through existing audio utility after tracing regression. Do not play on initial asynchronous report load, same-position updates, missing/pass coordinates, or theme/filter changes; respect sound preference/browser unlocking. Preserve existing try/replay behavior.
- [ ] Detail dialog explicitly consumes current theme font; known/unknown rule labels agree with backend verification status.
- [ ] Focused frontend behavior regressions, typecheck and standard/kiosk2D builds; kiosk build must exclude3D. Runtime sound test after user gesture and screenshot all affected charts.

## Task 4 — Review and deployment

- [ ] Independent gpt-6-astra code review focuses actual-move semantics, audio triggers, rule provenance, worker/transfer integrity and deployment risks. Fix concrete defects.
- [ ] Preserve deployed concurrent title/search patches and environment settings. Do not restart Postgres/MinIO/KataGo or unrelated services.
- [ ] Deploy web/cron changed code and frontend assets to home first, verify API and visual runtime including kiosk. Deploy same reviewed changes to ucloud and visually verify public URLs.
- [ ] Backup affected existing job/move rows before marking for reanalysis; do not overwrite rawSGF or unverified source parameters.
- [ ] On home use isolated workers on both3090, correct pinned b11c768 model and2000visits. No production GPU batch work. Rerun existing reports whose rules/komi are verified; keep unresolved games withheld with reasons.
- [ ] Track per-game timing/completion, verify contiguous root+move positions and >=2000rootvisits, effective parameter/model metadata. Sync to ucloud transactionally with parameter validation.
- [ ] Verify report/list availability and same metrics on both servers; document completed/unresolved counts, timing, source evidence, deployment image/asset hashes and screenshots. Remove all temporary product fixtures.
