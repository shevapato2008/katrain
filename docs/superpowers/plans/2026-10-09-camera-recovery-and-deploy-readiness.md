# RK3562 Camera Recovery and Deployment Readiness Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan sequentially. Steps use checkbox syntax for tracking. The user requested at most two plan reviews by `gpt-6-astra` with `max` reasoning; do not expand that into repeated design or implementation review cycles.

**Goal:** Recover automatically when the configured camera is absent at startup or reconnects while recognition is idle, and prevent camera-dependent deployments from passing on HTTP availability alone.

**Architecture:** Keep one shared `CameraHub` and initialize its existing consumers even when the camera is temporarily unavailable. The hub owns one low-frequency recovery thread, while camera reconnect operations are serialized with lifecycle operations. Use the existing HBV udev alias and check the real vision status after deployment; retain existing calibration checks and require calibration whenever compatibility cannot be proven.

**Tech Stack:** Python, threading, FastAPI board lifespan, existing pytest suites, systemd drop-ins, Bash deployment script. No frontend changes, new packages, general retry framework, or USB/power-management changes.

---

## Chunk 1: Focused camera recovery defenses

### Evidence and acceptance criteria

On 2026-10-09, the RK3562 kernel recorded USB disconnection/re-enumeration at 16:22. KaTrain restarts at 16:56 and 17:18 failed to open camera index 0 and discarded the shared camera hub and all consumers. USB reconnect at 18:11 did not restore them. A restart at 18:18 restored vision. Kernel logs do not prove why USB disconnected or what device number it had between reconnects.

`InProcessAdapter._loop()` deliberately skips frame acquisition while idle. Existing reconnect is triggered only by `CameraManager.read_frame()`, so an idle dropout has no automatic recovery trigger. `/kiosk` still returns HTTP 200 while vision is disabled; current deployment verification accepts that degraded state.

Acceptance:

- Board UI and LEDs remain usable with no camera; configured vision reports enabled but disconnected, and recognition readiness remains false.
- Connecting the configured camera after initial failure restores its shared consumers without restarting KaTrain, even with no viewer or physical game active.
- A later dropout/reconnect also recovers while recognition is idle.
- Only one physical camera is owned; simultaneous recovery/read requests cannot close/reopen it concurrently; shutdown cannot reopen it afterwards.
- Disconnection clears cached frames so capture cannot return a stale pre-dropout frame.
- Existing camera/profile/resolution and exposure verification gates remain enforced. Legacy index-based calibration can match a stable alias only if both currently refer to the same device node.
- Camera-dependent deployment verification requires booleans `enabled`, `camera_connected`, and `camera_ready` to be true; HTTP 200, malformed JSON, or false fields do not pass. Do not require operator geometry confirmation to deploy.
- Keep verification focused on these regressions. Do not unplug the user's hardware, change live calibration files, or restart an active game to test.

### Workspace and review protocol

KaTrain workspace: `/Users/fan/Repositories/katrain-kiosk-debug`, branch `fix/kiosk-ui-debug`, initially clean.
SmartBox owning workspace: `/Users/fan/Repositories/smartbox-software`. It has unrelated user changes in provisioning and Hermes. Modify only the clean drop-in, deployment script, and their focused tests; preserve all other changes. These are coordinated fixes across the existing two owning repositories, not a vendor-wide refactor.

- [x] Save this complete plan, then dispatch a fresh `gpt-6-astra`, `max`, `fork_turns=none` reviewer with this file and the relevant source/test paths.
- [x] Incorporate material findings. Dispatch a second review only if required to check revised decisions. Stop after two reviews and resolve any remaining material issue directly from source evidence.
- [x] Execute the revised plan without an additional approval gate; the user explicitly authorized implementation after review.

### Task 1: Single-owner camera recovery during idle and initial absence

**Files:**
- Modify: `katrain/web/core/camera_hub.py`
- Modify: `katrain/vision/camera.py`
- Test: `tests/test_camera_hub.py`
- Test: `tests/test_vision/test_camera_recovery.py` (new focused tests)

- [x] Write failing tests for a strict default `start()` failure, an opt-in start with camera absent followed by recovery without `read_frame()` consumers, idle dropout/reconnect, idempotent start/stop, and stopped hubs not reopening. Use controlled events/injected fake cameras; avoid timing-dependent long sleeps.
- [x] Add a controlled concurrent-open test and a cached-frame invalidation test to prove lifecycle correctness rather than merely assert thread existence.
- [x] Run `.venv/bin/python -m pytest tests/test_camera_hub.py tests/test_vision/test_camera_recovery.py -q`; expect new behavioral assertions to fail before implementation.
- [x] Extend `CameraHub.start` with a board-only opt-in:

```python
def start(self, *, allow_unavailable: bool = False) -> None:
    # Existing default remains strict for standalone CaptureService callers.
    # In tolerant mode, retain the CameraManager even when open() returns False.
    # _started means lifecycle started; is_connected() still means readable.
    # Start exactly one recovery thread for a started hub.
```

The thread uses `Event.wait(5.0)`, checks the camera connection, and calls the camera's existing reconnect path only while disconnected. It does no decoding/inference while connected. Log initial absence once, recovery on transition, and retain existing reconnect cooldown. No asyncio event-loop callback performs camera open/warmup.

- [x] Serialize `CameraManager.open()`, `close()`, and `_try_reconnect()` using one reentrant lifecycle lock. Nonblocking reconnect attempts return no frame if another owner is already reconnecting; after acquiring the lock, recheck connection and cooldown. Keep reader-thread locks separate; never hold a lock the reader needs while joining that reader.
- [x] Give each reader its own capture and stop event. A bounded join must not forget a surviving reader: defer capture release to its `finally`, retain its thread, and refuse replacement until it exits. Never clear/reuse an old reader's event, and prevent a stopped reader from publishing a late frame. Prove this with one controlled blocked-reader regression. Connection readiness requires a successfully captured current frame, not just an opened handle.
- [x] Shutdown signals the hub recovery event, marks the hub stopped, waits for an in-progress lifecycle operation, joins the recovery thread, and closes the camera. Frame access from stopped hubs returns no frame. Stop cannot race with monitor or consumer reconnect and leave an open handle.
- [x] Clear `_latest_frame` under the frame lock in `_mark_disconnected()`. Do not broaden fresh-frame timestamp semantics.
- [x] Resolve symlink paths before reading sysfs camera identity. Preserve a configured stable alias across retries rather than replacing it with a numbered path after a transient alias failure. Existing numeric-device fallback remains supported.
- [x] Run the same tests; expect PASS and no leaked test threads.

### Task 2: Preserve board services through initial camera absence

**Files:**
- Modify: `katrain/web/server.py` (shared camera acquisition block only)
- Test: `tests/web_ui/test_board_lifespan_camera_degraded.py`
- Existing coverage: `tests/test_vision/test_camera_status_is_honest.py`

- [x] Replace the old regression expectation that all camera consumers disappear with a behavior test: missing camera does not abort board startup, LEDs remain started, the same hub reaches VisionService and CaptureService, calibration/orchestration are available, camera/recognition readiness remain false until recovery.
- [x] Retain tests for mismatched vision/capture configuration being fatal and camera-only/vision-only configurations working. Extend minimal fakes only where needed for the new lifecycle parameter.
- [x] Run `.venv/bin/python -m pytest tests/web_ui/test_board_lifespan_camera_degraded.py -q`; expect the new missing-camera expectation to fail.
- [x] Replace the destructive missing-device exception handling with:

```python
camera_hub = CameraHub(hub_config)
camera_hub.start(allow_unavailable=True)
```

Existing initialization of VisionService, CaptureService, physical-play orchestration, and calibration then runs once, sharing this hub. Non-device configuration/construction exceptions remain errors. Keep normal shutdown order: stop camera consumers, then stop the hub. No second service graph, delayed service registry, or automatic game binding.

- [x] Keep current exposure verification: absent camera must never cause persisted geometry to be mounted without verified controls. After initial absence, the camera can reconnect using native AE, and operator calibration/confirmation remains required if no verified geometry is mounted. Existing healthy startup still replays and mounts validated hardware state.

Preserve, rather than extend, the existing runtime exposure behavior: a later reconnect does not currently invalidate mounted geometry on failed control verification. This plan does not claim a new runtime exposure gate or expand into that separate calibration-policy change.
- [x] Run `.venv/bin/python -m pytest tests/web_ui/test_board_lifespan_camera_degraded.py tests/test_camera_hub.py tests/test_vision/test_camera_status_is_honest.py tests/test_vision/test_shared_camera.py -q`; expect PASS.

### Task 3: Stable device alias without silently discarding compatible calibration

**Files:**
- Modify: `/Users/fan/Repositories/smartbox-software/provisioning/systemd/smartbox-katrain.service.d/20-vision-led.conf`
- Modify: `katrain/web/core/hardware_vision_state.py`
- Test: `tests/test_hardware_vision_state.py`
- Modify tests: `/Users/fan/Repositories/smartbox-software/provisioning/tests/test_vision_led_provisioning.py`

- [x] Add a profile-loading regression that persists a numbered camera path and then loads through a symlink to the same device; add mismatch/missing-alias coverage so two distinct nodes are never treated as the same camera. Test numeric index `0` mapping to `/dev/video0` with a controlled filesystem identity probe.
- [x] Run `.venv/bin/python -m pytest tests/test_hardware_vision_state.py -q`; expect new alias compatibility case to fail.
- [x] Compare profile device identifiers exactly first, then allow different identifiers only when `os.path.samefile` proves their current node identity. Convert all-digit IDs to `/dev/videoN` before comparison. Catch only filesystem lookup errors; retain checksum/schema/resolution validation. Do not mutate stored profile payloads or hashes and do not infer identity from a generic camera name.

```python
def _camera_devices_match(stored: str, requested: str) -> bool:
    if stored == requested:
        return True
    stored_path = f"/dev/video{stored}" if stored.isdigit() else stored
    requested_path = f"/dev/video{requested}" if requested.isdigit() else requested
    try:
        return os.path.samefile(stored_path, requested_path)
    except OSError:
        return False
```

- [x] Update the focused drop-in test first to require both `--vision-camera /dev/smartbox-cam` and `--capture-camera /dev/smartbox-cam`; then change those two flags and their explanatory comment. Keep resolution, model, exposure, LED, and other flags unchanged.
- [x] Run `.venv/bin/python -m pytest tests/test_hardware_vision_state.py -q` and run the owning provisioning tests using the same Python executable with the absolute test path; expect PASS.

### Task 4: Camera-aware deployment verification

**Files:**
- Modify: `/Users/fan/Repositories/smartbox-software/scripts/deploy-main-to-rk3562.sh`
- Test: `/Users/fan/Repositories/smartbox-software/provisioning/tests/test_katrain_deploy_camera_readiness.py` (new)

- [x] Add subprocess-based tests for the actual shell functions and `push` invocation sequence, using stub `ssh`, `systemctl`, `curl`, `sleep`, and installation executables. Stub external boundaries and unrelated build/copy steps; execute the real restart/readiness/mode-restoration decisions.
- [x] Cover: HTTP page ready but camera false fails; all required fields true passes; malformed/missing status fails; camera not configured preserves HTTP-only behavior; inactive service is not started; a previously active KaTrain must still be verified when restoring `smartbox-go.target` leaves it inactive. Bound stub loops without real waiting.
- [x] Run the new test file with the KaTrain Python executable; expect failing assertions before implementation.
- [x] In the existing bounded 60-attempt readiness loop, first check `/kiosk` and, when the effective systemd ExecStart enables vision, also fetch `/api/v1/vision/status`. Parse with the existing board venv Python and require exact JSON booleans for `enabled`, `camera_connected`, and `camera_ready`. A valid page with false status continues polling; timeout exits nonzero and prints the final status for diagnosis. Do not retry a full service restart or accept a disabled camera as success.
- [x] Install only the KaTrain vision drop-in from the deployed source tree into `/etc/systemd/system/smartbox-katrain.service.d/20-vision-led.conf`, then `daemon-reload`, including when the service is inactive. Preserve other installed overrides. Capture whether KaTrain was active before `restart_and_verify` changes targets; pass that fact to final KaTrain restart/readiness verification. A previously active service becoming inactive cannot be classified as an intentionally inactive deployment.
- [x] Do not require `pose_locked`/`geometry_ready`/`recognition_ready` for deployment: operator confirmation is a separate workflow. Non-camera deployments retain their existing check.
- [x] Run focused shell tests plus `bash -n scripts/deploy-main-to-rk3562.sh`; expect PASS. Verify the failure result propagates through the existing `set -e` deployment entry point.

### Task 5: Finish with sufficient evidence

- [x] Run the focused combined KaTrain suite:

```bash
.venv/bin/python -m pytest tests/test_camera_hub.py tests/test_vision/test_camera_recovery.py tests/test_vision/test_camera_status_is_honest.py tests/test_vision/test_shared_camera.py tests/test_vision/test_auto_exposure.py tests/test_vision/test_vision_idle.py tests/test_capture_service.py tests/test_hardware_vision_state.py tests/web_ui/test_board_lifespan_camera_degraded.py -q
```

- [x] Run the two modified/new provisioning test files and Bash syntax check. Do not add full engine/GPU, frontend build, or broad UI regression runs to a camera lifecycle change.
- [x] Inspect both diffs for unrelated changes, lock/join ordering, and truthfulness of disconnected status. Record review findings and validation outcomes in this plan.
- [x] Deliver local source/config/script changes with exact modified paths and test results. Do not deploy or restart the live device as part of this code task; current hardware has recovered and has a bound session. State that on-device rollout remains pending.

### Plan review record

Reviews requested: `gpt-6-astra`, reasoning `max`, maximum two rounds. Record actual findings and revisions here before implementation.

Round 1 — Issues Found. Incorporated all three material findings: retain blocked reader generations and defer their release; install the KaTrain drop-in in the normal push path; remember pre-deployment KaTrain activity so target-restoration failures cannot skip verification. Added existing auto-exposure/idle/capture tests to cover touched lifecycle behavior. Explicitly documented that runtime exposure/geometry policy is unchanged. Baseline before implementation: 69 KaTrain tests and 24 vision-provisioning tests passed.


Round 2 — Approved. The final `gpt-6-astra` / `max` review found no unresolved material issues and approved implementation. Exactly two plan-review rounds were used.

### Implementation and validation record

Implemented Tasks 1–4 in the listed owning files. The shared hub now retains consumers after initial absence and runs a five-second recovery monitor even during idle. Reader captures/events are per generation; unfinished readers prevent replacement and release their capture themselves. Current-frame readiness, disconnected-cache invalidation, alias identity, conservative profile compatibility, and deployment readiness checks are covered by focused regressions.

Red-phase evidence: new camera/profile tests produced nine expected failures; the board-lifespan regression reproduced discarded camera consumers; the updated drop-in and deployment tests produced eight expected failures, including the actual push path skipping a previously active KaTrain after failed target restoration. Green-phase evidence after implementation/formatting:

- KaTrain focused camera, exposure, idle, capture, shared-camera, hardware-state, and board-lifespan suite: **134 passed** (2026-10-09).
- SmartBox vision provisioning and deployment camera readiness suite: **32 passed** (2026-10-09).
- `bash -n scripts/deploy-main-to-rk3562.sh`: passed.
- Scoped `git diff --check` in both repositories: passed.

No live device restart, deployment, calibration mutation, or hardware disconnection was performed during implementation. Changes are local and uncommitted; rollout requires committing the coordinated changes and updating the SmartBox KaTrain submodule revision to the fixed version. Existing runtime exposure/geometry policy remains unchanged as documented above.

### Authorized rollout follow-up

The user subsequently requested implementation to proceed. The rollout will commit the focused changes, apply them to the current SmartBox KaTrain baseline (`9f28d43d`), and update only the camera source/configuration/deployment files on RK3562. The four deployed Python files exactly match that baseline; the kiosk is in the PvP lobby. Preserve newer device-lease and identified-frame APIs during integration, and run their existing focused regressions. Back up the replaced files before restarting KaTrain. Current USB enumeration has no camera, so connected-camera acceptance remains pending physical availability; do not declare camera readiness from HTTP 200 alone.

- [x] Integrate and commit coordinated changes while preserving unrelated local work.
- [ ] Back up and install only the reviewed camera-related files and drop-in.
- [ ] Verify deployed source/configuration, HTTP availability, and real vision readiness; record any hardware-dependent acceptance still pending.

Integration onto `9f28d43d` preserves its cross-process `DeviceLease`, occupied-device degradation, unstarted-reader cleanup, and identified-frame API. When bounded camera close leaves a reader alive, a shutdown waiter retains the lease until that reader releases its capture. Identified-frame access follows the same stopped/busy guard as other frame reads. Two focused integration regressions reproduced premature lease release and stopped identified reads, then passed. Existing capture/diagnostic tests now stop their hubs; startup fakes include the current PvP bridge dependencies. The integrated focused suite (including diagnostic observations and lease tests) passed **153 tests**. The SmartBox suites passed **32 tests**, and Bash syntax validation passed. User confirmed the camera is temporarily disconnected; real reconnection acceptance remains pending.
