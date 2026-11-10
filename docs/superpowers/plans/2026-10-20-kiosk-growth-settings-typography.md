# Kiosk Growth, Settings, and Typography Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the approved Go kiosk design for page 22, pages 26–28, Chinese typography, and report move alignment into the real application while preserving real data and device behavior.

**Architecture:** Keep the existing React routes, API responses, and 1024×600 shell. Add one shared Chinese typography preference, sourced from persistent storage and applied at the kiosk root; keep existing Latin, numeric, mono, and brand faces fixed. Adapt growth and settings presentation to the approved design and sync the calibration UI with the deployed five-anchor backend contract. Do not add production fixtures or redesign the four course pages being handled elsewhere.

**Tech Stack:** React 19, TypeScript, Vite, CSS, Vitest, Playwright, FastAPI/Python only where durable preference storage or geometry contract needs it.

**Design source:** `docs/design/kiosk-current-based-redesign-2026-10-14.html` sections `#growth`, `#calib`, `#settings`, `#settings-board`, `#settings-typography`, `#report-recommend` and their `docs/design/kiosk-unified/` assets. The CJK-only font and fixed-position candidate corrections passed independent Astra Max review on 2026-10-20 at 1024×600.

**Boundaries:** Existing reports, growth statistics, account status, camera/LED readiness, and calibration results remain server-authoritative. The design artifact's macOS `local()` fonts are previews only; actual RK3562 choices require loadable licensed assets. Preserve unrelated dirty worktree changes. User authorized proceeding from approved design to development, including necessary backend work. Deploy and merge are outside this plan.

---

## Chunk 1: Shared typography and report alignment

### Task 1: Align report candidate stones and coordinates

**Files:**
- Modify: `katrain/web/ui/src/kiosk/components/report/reportRail.css`
- Test: `katrain/web/ui/src/kiosk/pages/ReportDetailPage.test.tsx`
- Inspect analogous candidate rows in `katrain/web/ui/src/kiosk/components/` and `katrain/web/ui/src/kiosk-shell/`; change only rows with the same centering fault.

- [ ] Replace `justify-content:center` in `.report-analysis-rail__candidate > span:first-child` with a fixed stone column and coordinate column, preserving the other three data columns and 44px row height. Keep actual-move marker after the coordinate without shifting the stone.
- [ ] Run `rg -n 'kifu-record__stone|candidate.*justify-content|move.*justify-content' katrain/web/ui/src/kiosk katrain/web/ui/src/kiosk-shell` and record any analogous live row needing the same fix.
- [ ] Run `cd katrain/web/ui && npx vitest run src/kiosk/pages/ReportDetailPage.test.tsx`; expect PASS.
- [ ] In a real 1024×600 report, measure stone and coordinate x coordinates across `R12`, `R10`, `N9`, and `S11`; both columns must be constant, including the expanded rail. Compare to the reviewed artifact.

### Task 2: Use real CJK-only font faces

**Files:**
- Modify: `katrain/web/ui/src/kiosk-shell/fonts.css` only through its generating source if generated; locate source with `rg -n 'SmartBox Kai|fonts.css' katrain/web/ui/scripts katrain/web/ui/src/kiosk-shell`.
- Modify: `katrain/web/ui/src/kiosk-shell/tokens.css`
- Modify: `katrain/web/ui/src/kiosk-shell/golaxy-spectator.css` (existing hardcoded CJK font stack only)
- Modify: `katrain/web/ui/src/kiosk/pages/trainingReviewed.css` (existing hardcoded CJK font stack only)
- Modify: `katrain/web/ui/src/kiosk/theme.ts`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`
- Create: `katrain/web/ui/src/kiosk/typography/` for a small preference type, storage client, and root typography application.
- Test: focused `katrain/web/ui/src/kiosk/__tests__/SettingsPage.test.tsx` plus one browser font-routing check.

- [ ] Use actual licensed, loadable Regular assets, not the artifact's macOS-only `local()` faces: existing WenKai; official CNS11643 TW-Kai for 楷体; original, unmodified official `AlimamaDaoLiTi-Regular.woff2` for 隶书 (publisher file at `https://fonts.alibabadesign.com/AlimamaDaoLiTi/AlimamaDaoLiTi-Regular/AlimamaDaoLiTi-Regular.woff2`); repository Noto Sans CJK SC for 黑体. The publisher's [DaoLi legal statement](https://www.yuque.com/alimama_ai-font/vfse9w/ynqpf9pt8wops4sl) expressly permits embedded use and bars conversion/splitting, so bundle the publisher's prebuilt WOFF2 unchanged, with attribution. Do not add a font dependency or expose a dead option.
- [ ] Keep Latin/ASCII and digits in the current fixed faces: the dynamic face(s) should cover Chinese ideographs and Chinese punctuation only (`unicode-range` or equivalent), while `SmartBox Fondamento`, `SmartBox Brand LongCang`, and mono/coordinates keep their current routing.
- [ ] Add three size levels: default, 2px smaller, and 4px smaller, with a 12px minimum, matching the approved artifact. The kiosk has 700+ fixed `font-size: ...px` CSS declarations and fixed MUI `fontSize`, so changing only `html`/theme cannot work. Integrate a single bounded typography applicator at `KioskApp.tsx`: on initial render and preference change, measure each text element's unscaled computed size once and assign its base-size CSS variable; a kiosk-scoped rule applies `max(12px, calc(var(--base-size) - var(--size-step)))`. Observe added nodes only for route changes and MUI portals, scheduling one batch per frame; disable sizing while measuring, disconnect on unmount, exclude launcher, canvas/SVG, brand, board coordinates, and icon glyphs. Keep control dimensions and 44px touch targets fixed. Do not use whole-page zoom/transform. Use one shared state instead of per-page toggles.
- [ ] Change MUI's font stack and the `KIOSK_*` exports to consume the same live CJK CSS variable, leaving the Latin-first faces fixed. Apply the variable to the kiosk root and its own MUI portal layer; never write a global font rule for Galaxy.
- [ ] Audit direct `SmartBox Kai` font declarations across kiosk and kiosk-shell CSS/TSX, including `trainingReviewed.css` and `golaxy-spectator.css`; route CJK text through the shared live variable while preserving Latin-first and brand stacks.
- [ ] Verify with browser `document.fonts`/CDP that Chinese glyphs change across four choices while `StellaBox`, `AI`, `R12`, digits, coordinates, and brand glyphs keep their intended families; inspect one representative 1024×600 settings page and one report page at each size, plus a training or spectator page for the hardcoded-stack regression.

### Task 3: Persist the typography preference across RK3562 restart

**Files:**
- Frontend: `katrain/web/ui/src/context/SettingsContext.tsx` or the small typography context from Task 2, plus its API client/tests.
- Backend: create `katrain/web/api/v1/endpoints/kiosk_preferences.py`, `katrain/web/core/kiosk_preferences.py`, register the router in `katrain/web/api/v1/api.py`, and add focused tests in `tests/web_ui/` or the nearest existing API test location.

- [ ] Fix the contract at `GET/PUT /api/v1/kiosk-preferences/typography`: JSON `{font: "wenkai" | "kaiti" | "lishu" | "heiti", size: "large" | "medium" | "small"}`; defaults `{font:"wenkai",size:"large"}`. This is device-scoped for guest and signed-in users on one RK3562. The SmartBox production browser runs `--incognito`, so `localStorage` is not durable. The deployed KaTrain service bind-mounts `/root/.katrain` to persistent `/mnt/data/weiqi/dot-katrain`; store the versioned JSON at `/root/.katrain/kiosk-typography.json` with atomic replace. Do not use the randomly generated fallback `settings.DEVICE_ID` as an identity key.
- [ ] Fetch before the kiosk shell renders (or show a neutral loading shell) so the stored choice restores without a flash. Track a local edit generation: a late initial GET may apply only if the user has not changed a choice. Serialize rapid PUTs so the final font/size pair is last on disk; the server serializes its atomic writes. On save failure, show unsaved/retry honestly, without reverting the immediate visual selection. No separate English setting.
- [ ] Test default GET, rejected invalid enum, durable PUT/reload, quick consecutive edits preserving the final pair, and late GET not overwriting a user's new choice. Browser-check a fresh incognito profile against the same backend preference.

## Chunk 2: Growth page 22

### Task 4: Match the approved three-tab Growth design

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/GrowthPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/growth/ActivityCalendar.tsx`
- Modify: `katrain/web/ui/src/kiosk-shell/go-screens.css` (growth selectors only)
- Test: `katrain/web/ui/src/kiosk/__tests__/GrowthPage.test.tsx`

- [ ] Retain existing live summary, ladder, diagnosis, activity requests and their distinct loading/error/empty states. Add tabs `概览`, `能力诊断`, `对手` to the right rail; show one panel at a time with the approved button material and touch behavior.
- [ ] Expand the 53-week activity matrix within the 680px rail, distribute month markers consistently above the matching week columns, and preserve day/date semantics. Use the approved 1024×600 `#growth` composition; do not rasterize real data into a design screenshot.
- [ ] Make ability/opponent tabs use existing API fields, with honest missing-data copy. Verify switching tabs, 53×7 placement, current-day position, and one failure state in focused Vitest and browser checks.
- [ ] Capture a real 1024×600 implementation screenshot and compare side by side with the approved artifact; resolve material differences in geometry, typography, button depth, and state copy.

## Chunk 3: Settings and physical board

### Task 5: Match approved settings navigation and board status

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx`
- Modify: `katrain/web/ui/src/kiosk-shell/go-screens.css` (settings selectors only)
- Test: `katrain/web/ui/src/kiosk/__tests__/SettingsPage.test.tsx`

- [ ] Remove the `账号与平台` group from this settings page and set `实体棋盘` as the first group. Keep backend account/platform endpoints and unrelated flows intact; this is a navigation/content change, not an account-data deletion.
- [ ] Show camera, geometry, and LED states in one horizontal row above `重新标定棋盘`. States must distinguish loading, unknown, connected, and disconnected. The calibration action requires both camera and LED ready; if either is absent, show the specific reason and do not enter calibration. Geometry uncalibrated is the valid reason to use the action.
- [ ] Add the `字体与字号` group above `关于`: four Chinese font choices and three size choices. On selection the whole Go settings page changes immediately; remove the redundant preview widget. In non-Chinese UI, keep an appropriate fixed language font while size still works, and restore the chosen CJK font when returning to Chinese.
- [ ] Check nav scrolling, 1024×600 visual alignment, default and missing-device statuses, disabled/action message, four font options, and two smaller sizes.

### Task 6: Sync calibration screen with the actual deployed five-point flow

**Files:**
- Modify: `katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationScreen.tsx`
- Test: `katrain/web/ui/src/kiosk/__tests__/GeometryCalibrationScreen.test.tsx`
- Backend and contract: selectively integrate from `origin/develop` at `2d769d5df` (including post-`cc17d4596` fixes) in `katrain/vision/{calibration_stability.py,led_geometry_calibrator.py,motion_filter.py,worker.py,worker_inprocess.py}`, `katrain/web/core/geometry_calibration_service.py`, `katrain/web/api/v1/endpoints/geometry.py`, `katrain/web/ui/src/api/geometryApi.ts`, `katrain/web/ui/src/kiosk/context/GeometryContext.tsx`, `katrain/web/ui/src/kiosk/components/vision/{GeometryCalibrationScreen.tsx,GeometryVideoPanel.tsx}`, and affected hooks/routes. Merge `katrain/web/ui/src/kiosk-shell/go-screens.css` hunks manually with existing local changes. Focus tests: `tests/test_geometry_api.py`, `tests/test_geometry_calibration_service.py`, `tests/test_led_geometry_calibrator.py` and existing UI geometry specs.

- [ ] Confirm source diff and preserve local changes. Adopt deployed four steps: wait for a stable empty board, confirm/lock exposure, locate four corners plus center as five anchors, generate empty-board baseline. The live phases include `waiting_stable`, `obstructed`, `lighting_paused`, and `lighting_rechecking`, with `pause_reason` and `/recheck-lighting`. Map these to truthful paused/active UI; do not merely relabel a 13-anchor backend.
- [ ] Preserve existing `preflight`, `completeRecalibration`, nullable LED readiness, `stopped_phase`, typed metrics, failure/retry/cancel/relocation and guard return while integrating newer flow. Focus tests on progress `0…5`, five measured anchors, each phase-to-step mapping, pause → recheck → resume, and cancel. `CALIBRATION_ANCHORS` remains a 13-point legacy constant on develop; runtime defaults to `FivePointLedGeometryCalibrator` and `FIVE_POINT_ANCHORS`.
- [ ] Compare 1024×600 implementation to approved `#calib`, including readiness and failure states. No device action or deployment is implied; report what cannot be verified without the running RK3562 service.

## Chunk 4: Integration and independent review

### Task 7: Focused integrated verification

**Files:**
- Test: existing focused Vitest/Playwright specs for report, growth, settings, and calibration. Add only behavior assertions missing for this work.
- Evidence: `docs/previews/` or existing visual track directory, using original links where page screenshots are replaced.

- [ ] Run affected Vitest tests, `cd katrain/web/ui && npm run build:kiosk-2d`, and focused Playwright at 1024×600. Run Python tests only for backend code that changed.
- [ ] For each changed page, compare reference, implementation, side-by-side, and overlay/diff at the same viewport. Check selected/unselected tabs, button depth, clip/overflow, CJK-only font behavior, persisted choice, and report coordinate alignment.
- [ ] Delete any temporary production fixtures used for previews. Record actual API states and unresolved device-only validation separately; do not mark unverified hardware as passed.
- [ ] Send the code and visual evidence to an independent Astra Max agent for adversarial review; fix findings and re-review until pass. Report changed files, tests, screenshots, and any physical-device limit to the user in this session.

## Execution order and ownership

1. Complete plan review with independent Astra Max, revise at most twice.
2. Use `superpowers:subagent-driven-development`: parallelize only disjoint Task 1 (report) and Task 4 (growth). Task 2/3 (typography foundation) must complete before Task 5 (settings). Task 6 (calibration) runs separately because it and Growth/Settings touch `go-screens.css`; the coordinator owns final stylesheet hunk integration. Give every worker exact file ownership and no license to edit others' work.
3. Review each implemented task for spec compliance then code quality, with the final independent Astra Max visual/code review in Task 7. Do not merge/deploy as part of this plan.
