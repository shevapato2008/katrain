# RK3562 Hardware Vision State Design

## Goal

Make camera exposure, board geometry, and the calibration LED policy deterministic across ordinary deployments and reproducible in provisioned/golden images without treating device calibration as user data.

## Ownership boundary

| Data | Owner | Location |
| --- | --- | --- |
| KaTrain code, calibration algorithm, LED sequence/color policy | software image | repository and `/opt/smartbox` |
| Camera exposure chosen by a successful calibration | this physical device | active generation under eMMC `/var/lib/smartbox/hardware/vision/generations/` |
| Camera-to-board geometry | this physical device | the same active eMMC generation |
| SGF, accounts, preferences, user databases | user/TF card | `/mnt/data/...` |

`/var/lib/smartbox/hardware/vision` is never part of source deployment rsync. The KaTrain systemd sandbox explicitly grants only this eMMC directory for hardware-state writes.

## Runtime behavior

At startup KaTrain loads a camera profile only when its schema, camera device, and resolution match. A valid profile starts the camera in native V4L2 manual mode with the saved exposure. With no valid profile, the camera remains in native hardware-AE mode so a newly provisioned machine can acquire a usable image; continuous software AE is disabled.

When geometry calibration starts, `GeometryCalibrationService` snapshots the active camera mode/exposure, drives native hardware AE until the measured frame enters the accepted band, switches to native manual mode, verifies the driver readback, and performs the LED lit/dark measurements at fixed exposure. Only after geometry calibration succeeds does it commit a new eMMC generation containing `geometry_lock.npz`, its existing `geometry_lock.json` diagnostics sidecar, `camera-profile.json`, and a checksum manifest.

The store writes and validates every file in a temporary generation directory, renames that directory into `generations/<generation-id>`, then atomically replaces a small `current.json` pointer. The old generation and pointer remain active until the final pointer replacement. A crash or injected failure at any earlier step therefore leaves the previous complete generation loadable; startup never assembles a state from files belonging to different generations.

A failed or cancelled run restores the snapshotted runtime mode/exposure in `finally` and never replaces the last known-good files. `CameraManager` retains the configured persisted controls and reapplies them after camera reconnect/reopen.

Legacy TF geometry has no matching exposure profile and therefore must not be promoted as a complete active generation. A privileged provisioning helper validates the legacy `geometry_lock.npz` plus optional `geometry_lock.json`, copies them into eMMC `legacy-import/`, reloads the copied geometry, and only then removes the TF originals. A failed copy or validation removes only temporary/invalid destination files and preserves the legacy source. KaTrain does not load `legacy-import`; the first successful recalibration creates the first complete active generation. This keeps TF clean without silently pairing old geometry/baseline with a newly acquired exposure.

## Calibration LED contract

The software contract is exact and version-controlled:

1. Four corners in this order: `(0,0)`, `(0,18)`, `(18,18)`, `(18,0)`.
2. Nine star points in row-major order: `(3,3)`, `(3,9)`, `(3,15)`, `(9,3)`, `(9,9)`, `(9,15)`, `(15,3)`, `(15,9)`, `(15,15)`.
3. Every position uses green only. Weak green signal may retry at a higher green intensity; red and blue are never calibration fallbacks.
4. Each lit frame is preceded by a strict LED clear and followed by a strict final clear.

KaTrain unit tests assert the complete ordered list and green-only attempts. Smartbox provisioning tests and `golden-preflight` import the deployed constants and reject an image whose calibration policy differs.

## Provisioning and golden-image behavior

`provision.sh --section katrain/systemd` creates root-owned mode-0755 `/var/lib/smartbox/hardware/vision`, runs the bounded legacy-import helper as root, installs the systemd arguments and eMMC writable-path rule, and disables software AE. The runtime service needs no permission to delete TF files. `smartbox-firstboot.sh` idempotently recreates the eMMC directory on a newly flashed machine.

`golden-preflight` verifies the directory, systemd arguments, writable-path contract, and exact LED calibration policy. `image-prep` removes `current.json`, all generation/legacy-import directories, and temporary vision-state files before `dd`, then fails unless the hardware-vision directory is empty. A clone must acquire its own exposure and geometry rather than inherit the golden board's physical alignment. The algorithm and green-only policy remain in the image and therefore apply on first boot.

## Failure handling

- Invalid or mismatched camera profiles are ignored with a warning and hardware AE is used until calibration succeeds.
- A new generation becomes visible only through an atomic `current.json` pointer switch; an injected failure before that switch leaves the previous generation loadable.
- Calibration failure restores the pre-run camera controls, including after cancellation.
- Camera reconnect reapplies the last configured persisted controls.
- Legacy geometry is archived, not activated, and removed from TF only after the eMMC archive reloads successfully.
- Missing eMMC directory or a wrong calibration policy is fatal in golden-image preflight.
- Any device-specific vision state remaining after `image-prep` is fatal, preventing it from entering the cloned image.

## Verification

- KaTrain: focused tests for state migration/profile persistence, camera-control forwarding, successful-calibration atomic save, failed-calibration preservation, and exact green-only order.
- Smartbox: provisioning contract tests for eMMC directory creation, systemd flags/sandbox, firstboot behavior, image-prep cleanup, and golden-preflight policy gate.
- RK3562: observe hardware AE convergence, successful manual lock/profile save, service restart restoring the same exposure, green-only 13-point calibration, and unchanged state across a code deployment.
