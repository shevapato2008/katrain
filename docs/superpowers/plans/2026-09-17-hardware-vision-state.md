# RK3562 Hardware Vision State Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist RK3562 camera exposure and board geometry in eMMC, enforce a green-only 13-point calibration sequence, and make provisioning/golden images reproduce the policy safely.

**Architecture:** KaTrain owns a small atomic hardware-state adapter and the runtime calibration behavior. Smartbox provisioning creates and exposes the eMMC directory, disables continuous software AE, validates the deployed policy, and sanitizes per-device results before golden-image capture.

**Tech Stack:** Python, OpenCV/V4L2, FastAPI runtime wiring, systemd, Bash provisioning, pytest.

---

## Chunk 1: KaTrain runtime contract

### Task 1: Green-only calibration policy

**Files:**
- Modify: `katrain/vision/led_geometry_calibrator.py`
- Modify: `tests/test_led_geometry_calibrator.py`

- [ ] Write a failing test that asserts every retry for all 13 ordered anchors is green and that a missing green signal never emits red or blue.
- [ ] Run the focused test and confirm it fails because `COLOR_CHANNELS` contains red and blue.
- [ ] Restrict `COLOR_CHANNELS` to green while retaining the two green intensity levels.
- [ ] Run the focused calibrator tests and confirm they pass.

### Task 2: Camera-control forwarding and exposure readback

**Files:**
- Modify: `katrain/vision/camera.py`
- Modify: `katrain/web/core/camera_hub.py`
- Modify: `katrain/web/core/capture_service.py`
- Modify: `tests/test_vision/test_auto_exposure.py`
- Modify: `tests/test_capture_service.py`

- [ ] Write failing tests for current mode/exposure readback, reconnect reapplication, and `CaptureService` forwarding `request_controls`, `controls_effective`, `initial_exposure`, `current_auto_exposure`, and `current_exposure`.
- [ ] Run them and confirm the forwarding/readback assertions fail.
- [ ] Store the reader-thread exposure readback and forward the four control members through both wrappers.
- [ ] Run the focused tests and confirm they pass.

### Task 3: Atomic eMMC hardware-state generations

**Files:**
- Create: `katrain/web/core/hardware_vision_state.py`
- Create: `tests/test_hardware_vision_state.py`

- [ ] Write failing tests for schema/device/resolution validation, a complete generation commit, atomic `current.json` switching, and failure injection before the pointer switch proving the previous generation still loads.
- [ ] Run the new test module and confirm it fails because the module is absent.
- [ ] Implement the minimal generation store with checksum manifest and atomic current pointer.
- [ ] Run the new tests and confirm they pass.

### Task 4: Runtime startup and successful-calibration persistence

**Files:**
- Modify: `katrain/web/server.py`
- Modify: `katrain/web/core/geometry_calibration_service.py`
- Modify: `tests/test_geometry_calibration_service.py`
- Modify: `tests/web_ui/test_board_lifespan_camera_degraded.py`

- [ ] Write failing tests that a valid active generation selects manual startup, no generation leaves hardware AE enabled, success commits profile plus geometry together, and failure/cancellation restores the prior runtime controls and preserves the active generation.
- [ ] Run the focused tests and confirm the new behavior fails.
- [ ] Add `--hardware-vision-dir`, load only the `current.json` active eMMC generation before camera startup, and commit exposure plus geometry only after successful calibration; runtime code must not read, migrate, or delete TF legacy state.
- [ ] Run the focused tests and confirm they pass.

## Chunk 2: Provisioning and golden image

### Task 5: Provision the eMMC state directory and stable runtime flags

**Files:**
- Modify: `/Users/fan/Repositories/smartbox-software/provisioning/provision.sh`
- Modify: `/Users/fan/Repositories/smartbox-software/provisioning/systemd/smartbox-katrain.service.d/10-dataoffload.conf`
- Modify: `/Users/fan/Repositories/smartbox-software/provisioning/systemd/smartbox-katrain.service.d/20-vision-led.conf`
- Modify: `/Users/fan/Repositories/smartbox-software/provisioning/apps/smartbox-firstboot.sh`
- Create: `/Users/fan/Repositories/smartbox-software/provisioning/apps/smartbox-vision-state-migrate.py`
- Modify: `/Users/fan/Repositories/smartbox-software/provisioning/tests/test_vision_led_provisioning.py`
- Modify: `/Users/fan/Repositories/smartbox-software/provisioning/tests/test_firstboot_behavior.py`
- Create: `/Users/fan/Repositories/smartbox-software/provisioning/tests/test_vision_state_migrate.py`

- [ ] Write failing provisioning tests for root-owned directory creation, `ReadWritePaths`, `--hardware-vision-dir`, `--vision-auto-exposure off`, and a root-run legacy helper that validates/copies/reloads before deleting the exact TF legacy files.
- [ ] Run the focused tests and confirm they fail.
- [ ] Implement the bounded root-only helper, invoke it from provisioning after the eMMC directory exists, and add idempotent provision/firstboot directory creation plus systemd wiring; do not grant the runtime service additional TF write access.
- [ ] Run the focused tests and confirm they pass.

### Task 6: Golden-image gates and sanitization

**Files:**
- Modify: `/Users/fan/Repositories/smartbox-software/provisioning/provision.sh`
- Modify: `/Users/fan/Repositories/smartbox-software/provisioning/tests/test_image_prep_contract.py`
- Modify: `/Users/fan/Repositories/smartbox-software/provisioning/tests/test_vision_led_provisioning.py`
- Modify: `/Users/fan/Repositories/smartbox-software/docs/rk3562-golden-image-runbook.md`

- [ ] Write failing tests that `golden-preflight` verifies the eMMC/systemd/green-only policy contract and `image-prep` empties only the hardware-vision state directory then fails if any entry remains.
- [ ] Run the focused tests and confirm they fail.
- [ ] Implement the preflight import checks and image sanitization; document that clones calibrate their own physical geometry.
- [ ] Run the focused tests and confirm they pass.

## Chunk 3: Integration and device acceptance

### Task 7: Cross-repository verification

- [ ] Run the focused KaTrain suite for camera, capture, geometry calibration, and LED calibrator.
- [ ] Run the focused smartbox provisioning suite and `bash -n provisioning/provision.sh`.
- [ ] Inspect both diffs for unintended changes, preserving the existing modified `vendor/hermes-agent` worktree.

### Task 8: RK3562 acceptance

- [ ] Deploy the two repository changes through the existing controlled path.
- [ ] Run provisioning sections required to install the updated service/drop-ins and execute golden preflight.
- [ ] Recover the current camera with hardware AE, run one calibration, and verify 13 positions emit green only.
- [ ] Verify `/var/lib/smartbox/hardware/vision/current.json` selects a complete generation containing the camera profile, geometry, sidecar, and manifest, and the legacy TF geometry file is gone or safely archived.
- [ ] Restart KaTrain and verify the saved manual exposure and usable brightness are restored.
- [ ] Perform a code-only redeploy and verify the `current.json` pointer and active generation hashes remain unchanged.
