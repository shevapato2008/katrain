# Kiosk Pre-Growth Integration Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development for independent tasks. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Finish the user-approved Kiosk redesign before page 22 成长, including real frontend behavior and any backend change that a verified contract gap requires.

**Architecture:** Treat `docs/design/kiosk-current-based-redesign-2026-10-14.html` and the user's later corrections as the visual authority for pages 01–21 and their supplements. Keep existing API, persistence, and engine paths as the data authority. Repair concrete remaining behavior defects, then verify representative real journeys at 1024×600. Do not implement new Golaxy/OGS platform capabilities solely because the artifact shows a disabled or unavailable state; the artifact expressly preserves those truthful states. OGS tutorial integration and page 22 onward are outside this plan.

**Tech Stack:** React/TypeScript/Vite, existing FastAPI/SQLAlchemy APIs, Vitest, Pytest, Playwright.

---

## Scope and current evidence

| Pages | Current implementation | Remaining verified work |
|---|---|---|
| 01–05 and local variants | AI and local play React screens implemented; real local FastAPI + KataGo start/move and screen-input local turn switches were exercised; Astra visual checks passed. | Preserve; physical RK3562 input still requires device acceptance, not a new backend API. |
| 06–10 and platform supplements | Reviewed presentation, login, engine setup and existing lobby/game bridges implemented. Some Golaxy quick-match/room/invite actions are deliberately unavailable, matching the artifact's no-fabricated-flow rule. | Local spectator `#pvp-spectate` still uses the older compact card styling; align this approved screen. No speculative upstream protocol or backend endpoint work. |
| 11–14 | Carousel, category/unit/wrong-book, account progress, problem actions and duration persistence implemented. | Correct per-problem attempt totals and untouched/wrong labels; distinguish wrong-book loading from empty. |
| 15–17 and professional report | Selected archive terminal board, 20/page, replay/report split, baipu restore/try/hint/manual paths and calibration gate exist. | Same-size visual check of 17 calibration gate and one real replay/selection path; repair only concrete parity gaps. |
| 19–21 and failure states | Personal-game search/selection/report tiers/delete, report tabs and research actions exist. Normal/deep creation is server-authoritative at 500/2000 visits; game deletion cascades reports. | Completed-report 重算 currently calls failed-only retry; research can show stale recommendations and position identity omits colors. Verify 21 visually. |

Existing reviewed-frontend plan: `docs/superpowers/plans/2026-10-19-kiosk-reviewed-frontend-pages.md`. Existing AI/local plans record their real-API and visual results. Preserve unrelated untracked design files and previews. No deployment or merge is authorized by this plan.

## Task 1: Training progress integrity, 11–14

**Files:** `katrain/web/ui/src/hooks/useTsumegoProblem.ts`, `katrain/web/ui/src/hooks/useTsumegoProblem.test.ts`, `katrain/web/ui/src/context/TsumegoProgressContext.tsx`, its existing tests, `katrain/web/ui/src/kiosk/pages/TsumegoUnitListPage.tsx`, `katrain/web/ui/src/kiosk/pages/TsumegoUnitsPage.tsx`, and their existing tests.

- [x] Add a focused hook test: record a wrong attempt on problem A, navigate in the same hook instance to B, and confirm B starts from its own persisted count; reopen A and confirm new failures increase the saved cumulative count. Also cover server history arriving after problem data; the next failure must exceed the authoritative prior count. Reuse existing mocked progress provider/API rather than a new test harness.
- [x] Fix initialization/flush so problem identity and cumulative attempts cannot leak across navigation. The server's `max(existing, incoming)` merge expects an absolute cumulative value, not a per-mount delta. Do not count try-mode exploration as a failed attempt.
- [x] In the problem list, show `—` for untouched attempts and use an attempted/wrong state for unresolved entries with positive attempts. Expose the minimum loading/loaded distinction from `TsumegoProgressContext`; both unit entry and wrong-book list must wait for account progress before saying `0 道错题`, disabling entry, or presenting a false empty list. Preserve the current level/category filter and existing failure/retry state.
- [x] Run focused hook/context/unit page tests and one representative 1024×600 wrong-book/problem preview. Check persisted values against existing `GET/POST /api/v1/tsumego/progress`.

## Task 2: Completed report recompute, 20

**Files:** `katrain/web/ui/src/kiosk/pages/ReportDetailPage.tsx`, `katrain/web/ui/src/kiosk/pages/ReportDetailPage.test.tsx`. Read `katrain/web/ui/src/api/reportApi.ts`, `katrain/web/api/v1/endpoints/reports.py`, `tests/web_ui/test_reports_api.py`.

- [x] Add tests for a completed report's visible 重算 and a failed report's retry. Completed must create a new task with `{user_game_id, report_type, force:true}` and navigate to its returned task; failed must call the existing `/retry` endpoint. Preserve loading, identity and error guards.
- [x] Implement that dispatch with existing `ReportsAPI.create`/`ReportsAPI.retry`. Do not change the server's failed-only retry boundary or 500/2000 visit authority. Keep reauthorization/charging errors visible; do not silently reuse the old completed task.
- [x] Run the focused frontend tests and existing report API tests. Preview the report details dialog at 1024×600 with a representative completed task. Do not actually queue a costly report just to capture a screenshot.

## Task 3: Research position integrity, 21

**Files:** `katrain/web/ui/src/kiosk/pages/ResearchPage.tsx`, `katrain/web/ui/src/kiosk/__tests__/ResearchPage.test.tsx`.

- [x] Add focused tests for moving from position A to B while A's quick result or error is shown/pending; B must show pending/no recommendation/error until its own result arrives. Add same-coordinate/different-stone-color case. During full scan, local board navigation preceding asynchronous session navigation must also never expose a previous-node recommendation.
- [x] Include the truncated stone-color sequence in the position identity and key quick rows/errors by the position that produced them. Keep the existing ownership key and late-response guard; preserve 400 ms debounce and real API payloads. Give scan recommendations precedence only when the session node corresponds to the current local position.
- [x] Run focused tests and compare one 1024×600 real ResearchPage state with `#research`. Repair only concrete layout/material differences; do not redesign the existing tools or board.

## Task 4: Local spectator visual alignment, approved supplement

**Files:** `katrain/web/ui/src/kiosk/pages/PvpSpectatorPage.tsx`, `katrain/web/ui/src/kiosk-shell/golaxy-spectator.css`, `katrain/web/ui/src/kiosk/pages/PvpSpectatorPage.test.tsx`.

- [x] Compare the actual page with `#pvp-spectate` at 1024×600. Replace the old rectangular, small-type player cards with the approved separated trapezoid cards and 18/22/28 hierarchy. Keep active/waiting contrast and the working read-only info control.
- [x] Preserve existing room snapshot polling, board, move/status/participant data, retry, accessibility labels and truthful unavailability. Reuse current tests for behavior; add a test only if a changed interaction needs coverage.
- [x] Capture one representative real-browser 1024×600 screenshot and fix concrete geometry/clipping differences. No backend change is indicated.

## Task 5: Integrate and verify the pre-growth boundary

**Files:** Existing tests and page styles only for demonstrated mismatches; no new infrastructure.

- [x] Recheck 17 calibration-gated Baipu screen at 1024×600 against `#baipu` and confirm camera/LED/marking states remain truthful. The artifact's 5-point/4-step copy is older than the real 13-point/5-step calibration; retain the actual workflow and record this reference mismatch rather than regressing it. Check one archive selected-card → unanalysed replay navigation with real API data, or document an unavailable local service.
- [x] Recheck 19 card search/result alignment and 20 report tabs after Tasks 1–3 with one current screenshot per affected journey. Use a same-size reference/implementation comparison and inspect geometry, text, icons, disabled states and raised controls.
- [x] Run focused frontend tests, one production UI build, and existing relevant backend API tests. Confirm `REPORT_VISITS` normal/deep and deletion cascade from code/tests; do not build a redundant backend layer when the contract already covers the user journey.
- [x] Request independent Astra Max visual/code review of final changed pages and actual screenshots. Fix material findings. Record which journeys were exercised with real backend, which require physical device, and which unavailable platform states are inherited.
- [ ] Present the real screenshots and evidence to the user for final visual acceptance. No fixture business data in production code.

New backend edits are permitted only for an observed contract defect and after the current slice's real runtime visual confirmation. Existing backend calls and read-only contract checks may proceed now. No known gap requires a new backend endpoint.

## Review and execution

- [x] Ask Astra Max to review this plan independently, revise once if needed, and stop after at most two plan reviews as previously requested.
- [x] Execute independent Tasks 1–4 with `superpowers:subagent-driven-development`; coordinate shared index and commit exact task files only. Review task behavior and code, then run Task 5 serially.

## Final verification record (2026-10-19)

- Astra Max reviewed the plan twice and approved it. Independent final code and visual review returned **APPROVE** after its five findings were fixed: research setup-stone node offset, late training history rebasing and persistence, spectator header type, research table type, and research action icons.
- Frontend focused run: **177/177** tests in six suites. Production UI build passed. Backend report and cascade run: **6/6** tests. Kiosk asset manifest and `git diff --check` passed.
- Real Chromium at 1024×600: reviewed the training wrong-book entry, professional archive selection, personal games, report and report details, research rail (reference beside implementation and overlay), and local spectator. The report dialog and local spectator focused visual specs passed; archive unanalysed replay and 17 calibration gate checks also passed. Screenshots live in `docs/previews/reviewed-pre-growth-2026-10-19/`.
- Existing production APIs already provide cumulative tsumego progress, report `force` creation, normal/deep 500/2000 visits, game-deletion cascade, session research, and lobby spectator snapshots. The only backend file change is a test that verifies report-task and move-row deletion with a game. No new endpoint or schema was needed.
- Physical RK3562 input, camera, LED, and KataGo execution remain device acceptance work; this local visual and contract pass does not claim a production deployment. The artifact's older 5-point/4-step calibration copy was not adopted over the real 13-point/5-step flow. Unavailable platform actions remain visibly unavailable.
