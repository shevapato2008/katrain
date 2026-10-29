# Calibration Grid Advisory Implementation Plan

> Execute in the dedicated `fix/calibration-grid-advisory-20261029` worktree. The user has approved implementation and the four-step RK3562 release; no further design approval is needed. Keep review and testing proportional to this calibration fix.

**Goal:** An unobstructed, stable board must reach LED calibration even when printed-grid detection fails. Grid visibility becomes an advisory, while LED measurements decide whether calibration succeeds.

**Architecture:** Keep frame freshness, motion, exposure, four-corner geometry, independent center validation and baseline quality checks. Allow a missing grid to use full-frame LED dark/lit differencing rather than waiting forever or requiring a grid-derived ROI. Use confirmed LED geometry to protect the baseline against board displacement when passive grid detection is unavailable. Surface one nonblocking message in the existing calibration note.

**Scope:** Do not repair cancellation, change the in-game drift algorithm, lower calibration quality thresholds, or deploy other games. This session's deployment target is RK3562 as explicitly requested. Preserve concurrent work and any active deployment transaction.

## 1. Reproduce and specify behavior

- [x] Save the retained real reflection frame from the October 29 investigation as a regression fixture.
- [x] Run the existing focused calibration tests as a baseline.
- [x] Add failing tests: stable missing-grid frames advance after the normal motion sequence; movement still pauses; a real five-point chain succeeds with grid detection unavailable; missing LED signals fail within existing retry bounds; the UI displays the advisory without showing an obstruction pause.
- [x] Cover displacement after confirmed LED points with grid detection unavailable, preserving the existing publication boundary.

## 2. Implement the smallest coherent change

Files: `katrain/vision/calibration_stability.py`, `katrain/vision/led_geometry_calibrator.py`, `katrain/web/core/geometry_calibration_service.py`, `katrain/web/ui/src/api/geometryApi.ts`, and `katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationScreen.tsx`.

- [x] Make grid visibility observational; do not return `board_occluded` solely because grid localization failed. Keep the existing motion thresholds and consecutive-frame requirement.
- [x] Permit `anchor_roi=None` in the five-point path and reuse existing full-frame centroid detection with its existing quality thresholds and retry bounds.
- [x] Retain displacement protection using confirmed LED positions when passive grid localization is unavailable; reuse existing displacement measurement rather than adding another detector.
- [x] Add optional `grid_warning: 'grid_not_visible' | null` to status, reset it on a new run/success, and show `网格暂未识别，将通过 LED 定位棋盘` in the existing note while active. Skip board-only lighting checks when no trusted grid is available; retain whole-frame exposure checks and final quality checks.
- [x] Update only tests whose old expectation intentionally required a static missing grid to block LEDs. Keep motion, shadow, freshness, cancellation, geometry and baseline coverage.

## 3. Verify

- [x] Run `PYTHONPATH=. /Users/fan/Repositories/katrain/.venv/bin/python -m pytest -q tests/test_vision/test_calibration_stability.py tests/test_led_geometry_calibrator.py tests/test_geometry_calibration_service.py tests/test_geometry_drift.py tests/test_geometry_api.py`.
- [x] Run the existing GeometryCalibrationScreen Vitest file and the frontend TypeScript/build checks needed for the deployed kiosk bundle.
- [ ] Check one 1024×600 advisory preview on the deployed RK renderer. Local full-app preview fixtures did not reach the screen; the existing component suite verifies the message. Do not expand preview-tool debugging.
- [x] Review the diff for unchanged cancellation and in-game drift behavior; preserve quality thresholds and bounded LED retries.

## 4. Publish and deploy in the user's requested order

- [ ] Commit the fix on the new branch. Fetch the latest `origin/develop`, merge it, resolve conflicts and verify the combined result. Push the feature branch.
- [ ] Merge into the latest `develop` and push without force; retry integration if another session advances it.
- [ ] In an isolated SmartBox checkout based on current `origin/main`, advance only `vendor/katrain` to the published develop commit, commit and push main. Preserve the primary checkout and unrelated submodules.
- [ ] Read RK3562 identity, current services, hardware state and deployment transaction. Do not overwrite another release or restart an active game. Once safe, back up only the affected runtime files and static indexes, ship only the changed Python files plus the same-source full/strict kiosk assets, retain old hashed assets, then restart the Go service only as required.
- [ ] Verify actual served assets, service health, camera readiness and runtime hashes. Do not manufacture hardware calibration success. Notify the user of published revisions and RK deployment, leaving the actual board interaction for their requested frontend acceptance.

## Execution evidence

- Plan written before product or test edits. Starting revision: `fd62f743c`.

- Baseline: 223 existing focused tests passed. RED: five new regressions reproduced grid occlusion waiting and the missing-ROI infinite retry; the UI advisory test also failed before implementation.
- Focused correction: two additional RED regressions demonstrated slow cumulative baseline movement and board-only movement hidden by stationary surroundings. The LED-derived crop is now checked on each actual captured frame.
- GREEN: 263 Python cases (stability, LED, calibration service, drift, geometry API), 55 GeometryCalibrationScreen Vitest cases, and `npm run build` passed. Existing build chunk-size warnings remain.
- Plan review found only the baseline movement gap above; the correction and regression tests address it. Static grid loss is intentionally no longer a hand detector: a stationary covering present from the start may allow LEDs to light, and invisible LED signals fail after the existing two attempts. Motion/lighting and final geometry checks remain.
- RK read-only preflight: `gzpeite`, Go backend inactive, another release `voice-hermes-20261029-08849f5d-cd544a84-03` is in phase `push` with an active C++ compiler. Do not seize that transaction or activate Go while it is in progress.
