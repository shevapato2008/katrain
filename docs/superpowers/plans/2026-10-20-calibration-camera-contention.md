# Calibration Camera Contention Repair Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Follow the focused test-first steps below.

**Goal:** Finish five-point Go calibration reliably on RK3562 while retaining fresh-frame, hand-occlusion, and ordinary-shadow requirements.

**Architecture:** Fix the confirmed contention failure at the shared CameraHub boundary. Fresh capture waits within one total timeout for lifecycle access and a new frame; preview reads remain nonblocking. Keep all calibration freshness, geometry, and lighting criteria unchanged. Diagnose the separate reported shadow stall using a real user-provided scene before changing any image criteria.

**Tech Stack:** Python, threading, OpenCV, pytest, existing RK3562 systemd deployment.

## Evidence and boundaries

- Deployed KaTrain `2d769d5dfacd75f112ccc056388d99d72eed7503`; five anchors succeeded at 17:52, then baseline failed with 3/8, 0/8, 0/8 trusted frames in the same second.
- A deterministic real CameraHub + FivePoint + concurrent preview reproduces that exact sequence, exhausting three sets in 0.227 ms. CameraHub returns `(None,0,0)` immediately when another consumer holds its lifecycle lock.
- The precise competing device thread has not been identified. No camera disconnect or LED localization failure was recorded.
- Current unobstructed device snapshot passes grid and lighting checks. Historical logs do not identify the reported shadow stall; a new real shadow scene has been requested.
- Do not alter the original dirty workspace, restart an active user calibration, loosen trusted-frame checks, or synthesize a successful lock.

## Chunk 1: Shared capture repair

### Task 1: Fix bounded camera access and reproduce the complete failure

**Files:**
- Modify: `katrain/web/core/camera_hub.py`
- Test: `tests/test_camera_hub.py`
- Test: `tests/test_led_geometry_calibrator.py` or existing real-chain tests in `tests/test_geometry_calibration_service.py`

- [x] Add a deterministic regression using the real Hub and FivePoint, an injected frame source, real concurrency events, and preview contention after baseline sample 3. It must reach the actual baseline loop and require eight trusted samples without reflashing anchors. Stub expensive downstream lock construction only if necessary.
- [x] Add focused tests for a held lifecycle lock, the shared timeout budget, and hub stop during the wait. Existing camera fakes should accept the CameraManager timeout contract where needed.
- [x] Run new tests and observe the expected contention failure before implementation.
- [x] Change only `CameraHub.grab_fresh`: use a default 2.0-second total budget when timeout is omitted, acquire lifecycle lock with a bounded wait, return the existing absent-frame tuple on timeout/stopped hub, and pass only remaining positive time to `CameraManager.grab_fresh`. Always release the acquired lock. Preserve lifecycle exclusion and all other access methods.
- [x] Run the new tests plus camera-hub, LED calibration, geometry service, and stability tests. Preserve all duplicate-seq, stale-ts, settle, cancellation, hand, shadow, and incomplete-baseline rejection checks.
- [ ] Independently review spec compliance, then have Astra Max review actual code. Fix findings until Approved. Plan review is limited to two rounds per user instruction.

### Task 1 implementation evidence

- RED: seven focused cases produced six expected failures and one passing preview compatibility case. The real Hub + FivePoint regression logged `3/8 → 0/8 → 0/8` and returned `baseline_frames_missing` before any product edit.
- GREEN: the same seven cases pass, including complete eight-frame baseline construction through the real `_build_lock` and exactly one flash at each of the five anchors. Default and explicit timeout cases verify that lifecycle wait time is deducted from the camera budget; exhausted budgets never call the camera. The close-in-progress case returns the absent-frame tuple without reading the closed camera.
- Focused suite: `PYTHONPATH=. /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/test_camera_hub.py tests/test_led_geometry_calibrator.py tests/test_geometry_calibration_service.py tests/test_vision/test_calibration_stability.py` — **244 passed**.
- Review follow-up: `tests/test_capture_service.py` initially produced **6 failed, 3 passed** in 0.34s. Its camera fake omitted the manager's `timeout` parameter; the first `TypeError` prevented test cleanup and caused subsequent lease failures. Added `timeout=2.0` only to `FakeCam.grab_fresh` and the no-frame lambda. Independent rerun of `PYTHONPATH=. /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/test_capture_service.py` — **9 passed** in 0.31s. No product changes or repeat of the 244-case suite were needed.
- Self-review: production edits are confined to `CameraHub.grab_fresh`. Preview reads, stop/recovery exclusion, calibration sequence/timestamp/settle checks, eight-frame requirement, cancellation and image criteria are unchanged. No device access or release action was performed. Independent reviews remain pending.

## Chunk 2: Real-device diagnosis and delivery

### Task 2: Verify the actual device and shadow scene

**Files:** No speculative image-algorithm changes in this plan.

- [ ] Preserve journal, failure status and actual camera snapshot. Replay requested real shadow scene through unchanged grid, exposure and motion checks, correlating with device phase/logs.
- [ ] If shadow remains an independent reproducible product failure, document its actual failing predicate and extend this plan with the smallest evidence-backed correction before implementation/review.
- [ ] After reviews and focused tests pass, publish the corrective branch, integrate into `develop`, and update/publish the SmartBox submodule pointer using the previously authorized workflow. Preserve unrelated files.
- [ ] When no calibration is active, back up changed device files, deploy only changed runtime files to RK3562, compile and restart Go service once. Do not sync the whole repository or rebuild unchanged frontend.
- [ ] Verify health and runtime file hashes, then run one representative real five-point calibration and inspect resulting status, baseline result and timing. If physical scene needs user placement, request it without falsely claiming acceptance.
- [ ] Report actual fix, published revisions, observed device results and any remaining physical acceptance requirement. Ordinary shadows must pass when grid remains visible; actual hands must pause and resume current point after removal.
