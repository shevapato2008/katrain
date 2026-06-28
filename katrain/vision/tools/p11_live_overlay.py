"""P11 live overlay — watch board-drift detection + LED fiducial re-lock in real time.

Opens a live camera window with the current geometry's grid drawn on the board and a
drift HUD. Slide/bump the board: the grid drifts off the printed lines and the HUD shift
climbs (RED = over threshold). Press 'r' to light LED fiducials and re-solve this frame's
homography M_f — the grid snaps back onto the board. Press 'w' to toggle the rectified
(warped) view. Press 'q' to quit (LEDs cleared on exit).

Reuses: geometry_lock (M_0), geometry_drift.GeometryDriftMonitor (P5, translation detect),
fiducial_recalibrate (P11: select/detect/solve), led_service, camera_hub.

Run (from the repo root so it uses THIS worktree's code):
    PYTHONPATH=$PWD /opt/miniconda3/envs/py311_katago/bin/python -m katrain.vision.tools.p11_live_overlay \
        --camera 0 --resolution 1920x1080 --led-serial-port /dev/cu.usbmodem2101
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from katrain.web.core.camera_hub import CameraHub, CameraHubConfig
from katrain.web.core.led_service import LedService, LedServiceConfig
from katrain.vision.geometry_lock import load_geometry_lock
from katrain.vision.geometry_drift import GeometryDriftMonitor
from katrain.vision.fiducial_recalibrate import (
    select_fiducials,
    detect_led_centroids,
    solve_frame_homography,
    drift_from_homography,
)
from katrain.vision.calibration_strategy import CalibrationContext, Scenario
from katrain.vision.calibration_strategies import OuterCornerStrategy


def decide_scenario(trigger: str) -> Scenario:
    """Map a relock trigger to a calibration Scenario (and thus allow_led). The automatic
    drift path is RUNTIME (no LED); only the user's 'r' key is a MANUAL_FALLBACK (LED OK)."""
    return Scenario.MANUAL_FALLBACK if trigger == "manual-r" else Scenario.RUNTIME_RECALIBRATION


FIDUCIAL_RGB = (0, 255, 0)  # full green, detected on channel 1 (raised from 96 — wood cover attenuates)
FIDUCIAL_CHANNEL = 1
SEARCH_FACTOR = 1.3  # ROI radius in cell-spacings; >1 tolerates stale-lock offset
LED_MAX_BRIGHT = 160  # global LED brightness for relock (clamped by firmware MAX_BRIGHT)
AUTO_STREAK = 8  # consecutive over-threshold frames before an auto re-lock (debounce transient motion)
AUTO_COOLDOWN_S = 3.0  # min seconds between auto re-locks (don't spam LEDs on persistent failure)


def _raw_cell_spacing(points: np.ndarray) -> float:
    """Mean adjacent-intersection distance in CAMERA space (px)."""
    dx = np.linalg.norm(np.diff(points, axis=1), axis=2).mean()
    dy = np.linalg.norm(np.diff(points, axis=0), axis=2).mean()
    return float((dx + dy) / 2.0)


def _expected_from_M(coords, M, xs, ys):
    """Predicted camera-space position of each (row,col) under homography M (camera->canonical)."""
    Minv = np.linalg.inv(np.asarray(M, np.float64))
    canon = np.array([[[float(xs[c]), float(ys[r])]] for (r, c) in coords], np.float64)
    cam = cv2.perspectiveTransform(canon, Minv).reshape(-1, 2)
    return {coords[i]: (float(cam[i][0]), float(cam[i][1])) for i in range(len(coords))}


def _draw_grid(frame, M, xs, ys, color):
    Minv = np.linalg.inv(np.asarray(M, np.float64))
    vis = frame.copy()
    canon = np.array([[float(xs[c]), float(ys[r])] for r in range(19) for c in range(19)], np.float64).reshape(-1, 1, 2)
    cam = cv2.perspectiveTransform(canon, Minv).reshape(19, 19, 2)
    for i in range(19):
        cv2.polylines(vis, [cam[i].astype(np.int32)], False, color, 1)
        cv2.polylines(vis, [cam[:, i].astype(np.int32)], False, color, 1)
    return vis


def _dump_relock_debug(debug_dir, tag, dark, lit, expected, det, search_px):
    """Write dark/lit/diff frames + an ROI overlay so a failed relock can be inspected."""
    import os

    os.makedirs(debug_dir, exist_ok=True)
    d = np.asarray(dark)
    l = np.asarray(lit)
    cv2.imwrite(os.path.join(debug_dir, f"{tag}_dark.png"), d)
    cv2.imwrite(os.path.join(debug_dir, f"{tag}_lit.png"), l)
    # green-channel diff (what detection keys on), amplified so dim LEDs are visible
    diff = cv2.absdiff(l, d)
    cv2.imwrite(os.path.join(debug_dir, f"{tag}_diff_x4.png"), cv2.convertScaleAbs(diff, alpha=4.0))
    ann = l.copy()
    peaks = []
    for coord, (x, y) in expected.items():
        r = det.get(coord)
        good = bool(r and r.ok)
        col = (0, 255, 0) if good else (0, 0, 255)
        cv2.circle(ann, (int(x), int(y)), int(search_px), col, 2)
        pk = getattr(r, "peak", None)
        if pk is not None:
            peaks.append(pk)
        label = f"{coord}" + (f" p={pk:.0f}" if pk is not None else "")
        if r and not r.ok:
            label += f" {r.reason}"
        cv2.putText(ann, label, (int(x) - 45, int(y) - int(search_px) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1)
        if good and r.centroid is not None:
            cv2.drawMarker(ann, (int(r.centroid[0]), int(r.centroid[1])), (0, 255, 255), cv2.MARKER_CROSS, 14, 2)
    cv2.imwrite(os.path.join(debug_dir, f"{tag}_annotated.png"), ann)
    pk_str = f"max={max(peaks):.0f} min={min(peaks):.0f}" if peaks else "n/a"
    print(f"  [debug] {debug_dir}/{tag}_*.png  (peaks {pk_str}; frame {l.shape[1]}x{l.shape[0]})")


def relock(led, frame_dark, frame_lit_grabber, geo, M_cur, raw_spacing, debug_dir=None, tag="relock"):
    """Light empty corners+star fiducials, detect on dark/lit diff, solve M_f. Returns (M_f, info)."""
    board = [[None] * 19 for _ in range(19)]  # demo assumes an empty board
    F = select_fiducials(board, None, target=13, min_count=8)
    expected = _expected_from_M(F, M_cur, geo.xs, geo.ys)
    led.clear(strict=True)
    dark = frame_dark()
    show = led.set_rgb_points([{"row": r, "col": c, "rgb": list(FIDUCIAL_RGB)} for (r, c) in F], strict=True)
    lit = frame_lit_grabber(show.get("shown_at"))
    led.clear(strict=True)
    det = detect_led_centroids(dark, lit, expected, channel=FIDUCIAL_CHANNEL, search_px=SEARCH_FACTOR * raw_spacing)
    if debug_dir:
        _dump_relock_debug(debug_dir, tag, dark, lit, expected, det, SEARCH_FACTOR * raw_spacing)
    ok = [(coord, r.centroid) for coord, r in det.items() if r.ok]
    if len(ok) < 8:
        return None, f"relock FAILED: only {len(ok)}/{len(F)} fiducials detected"
    fit = solve_frame_homography(ok, out_size=int(geo.out_size), min_inliers=6)
    if not fit.ok:
        return None, f"relock FAILED: solve {fit.reason} (inliers={fit.inlier_count})"
    return np.asarray(fit.M, np.float64), f"relock OK: {len(ok)} fiducials, residual {fit.rms_residual / raw_spacing:.3f}px-cells, inliers {fit.inlier_count}"


def main():
    ap = argparse.ArgumentParser(description="P11 live drift + LED re-lock overlay")
    ap.add_argument("--camera", default="0")
    ap.add_argument("--resolution", default="1920x1080")
    ap.add_argument("--led-serial-port", default="/dev/cu.usbmodem2101")
    ap.add_argument("--geometry", default="~/.katrain/geometry_lock.npz")
    ap.add_argument("--threshold-cells", type=float, default=0.15)
    ap.add_argument("--debug-dir", default="/tmp/p11_relock_debug", help="dump dark/lit/diff/annotated on each relock")
    ap.add_argument("--no-auto", action="store_true", help="disable automatic re-lock on sustained drift (manual r only)")
    args = ap.parse_args()

    geo = load_geometry_lock(Path(args.geometry).expanduser())
    raw_spacing = _raw_cell_spacing(np.asarray(geo.points))
    M0 = np.asarray(geo.M, np.float64)
    M_cur = M0.copy()
    print(f"geometry out_size={geo.out_size}, raw cell spacing ~{raw_spacing:.1f}px")

    led = LedService(LedServiceConfig(enabled=True, serial_port=args.led_serial_port, baud_rate=115200, max_bright=LED_MAX_BRIGHT))
    led.start()
    connected = any(led.clear(strict=True).get("ok") or time.sleep(0.4) for _ in range(12))
    print(f"LED connected: {connected}")

    dev = int(args.camera) if str(args.camera).isdigit() else args.camera
    w, h = (int(x) for x in args.resolution.split("x"))
    hub = CameraHub(CameraHubConfig(device_id=dev, width=w, height=h, lock_exposure=True))
    hub.start()

    def grab():
        f = hub.read_frame()
        return f[0] if isinstance(f, tuple) else f

    def grab_blocking(timeout=5.0):
        # read_frame() returns the latest buffered frame, which is None until the threaded
        # reader fills it — spin briefly so the reference/relock grabs never see None.
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            f = grab()
            if f is not None:
                return f
            time.sleep(0.02)
        raise RuntimeError(f"camera produced no frame within {timeout:.0f}s")

    monitor = GeometryDriftMonitor(grab_blocking(), cell_spacing_px=raw_spacing, threshold_cells=args.threshold_cells, consecutive_frames=1)
    show_warp = False
    auto = not args.no_auto
    relock_count = 0
    over_streak = 0
    last_auto_t = 0.0

    def do_relock(reason):
        nonlocal M_cur, monitor, relock_count
        relock_count += 1
        scenario = decide_scenario(reason)
        print(f"[relock #{relock_count}] trigger={reason} scenario={scenario.name} allow_led={scenario.allows_led()}")
        if scenario.allows_led():
            # user-initiated → LED fiducial (sub-pixel)
            M_new, info = relock(
                led,
                lambda: grab(),
                lambda show_at: (time.sleep(0.15), grab())[1],
                geo, M_cur, raw_spacing,
                debug_dir=args.debug_dir, tag=f"relock{relock_count:02d}",
            )
        else:
            # automatic → no-LED outer-corner (product-consistent; never lights an LED)
            out = OuterCornerStrategy().calibrate(
                CalibrationContext(frames=[grab_blocking()], board=None, geometry=geo, led=None, out_size=int(geo.out_size)),
                allow_led=False,
            )
            M_new = np.asarray(out.M, np.float64) if out.ok else None
            info = f"outer_corner OK conf {out.confidence:.2f}" if out.ok else f"outer_corner FAILED: {out.reason}"
        print(" ", info)
        if M_new is not None:
            M_cur = M_new
            monitor = GeometryDriftMonitor(grab_blocking(), cell_spacing_px=raw_spacing,
                                           threshold_cells=args.threshold_cells, consecutive_frames=1)
            drift = drift_from_homography(M_cur, M0, out_size=int(geo.out_size))
            print(f"  drift vs M_0: {drift.median_px / raw_spacing:.2f} cells, rot {drift.deg:.2f}deg")
            return True
        return False

    msg = "r=re-lock  a=toggle auto  w=warped  q=quit"
    print(f"{msg}   (auto={'ON' if auto else 'off'}; auto fires after {AUTO_STREAK} drift frames, {AUTO_COOLDOWN_S:.0f}s cooldown)")
    try:
        while True:
            frame = grab()
            if frame is None:
                continue
            now = time.monotonic()
            d = monitor.update(frame)
            over = d.shift_cells > args.threshold_cells
            over_streak = over_streak + 1 if over else 0
            color = (0, 0, 255) if over else (0, 220, 0)
            vis = _draw_grid(frame, M_cur, geo.xs, geo.ys, color)
            status = "DRIFT" if over else "OK"
            cv2.rectangle(vis, (0, 0), (vis.shape[1], 70), (0, 0, 0), -1)
            cv2.putText(vis, f"{status}  shift={d.shift_px:5.1f}px  {d.shift_cells:4.2f}cells  (thr {args.threshold_cells})  auto={'ON' if auto else 'off'}",
                        (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            cv2.putText(vis, msg, (12, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
            cv2.imshow("P11 live overlay", cv2.resize(vis, (1280, 720)))
            if show_warp:
                cv2.imshow("warped (M_cur)", cv2.warpPerspective(frame, M_cur, (int(geo.out_size), int(geo.out_size))))

            # Auto re-lock: drift sustained over threshold past the streak, respecting cooldown.
            if auto and over_streak >= AUTO_STREAK and (now - last_auto_t) >= AUTO_COOLDOWN_S:
                last_auto_t = now
                over_streak = 0
                do_relock("auto-drift")

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("a"):
                auto = not auto
                print(f"auto-relock {'ON' if auto else 'off'}")
            if key == ord("w"):
                show_warp = not show_warp
                if not show_warp:
                    cv2.destroyWindow("warped (M_cur)")
            if key == ord("r"):
                over_streak = 0
                do_relock("manual-r")
    finally:
        led.clear(strict=True)
        led.stop()
        hub.stop()
        cv2.destroyAllWindows()
    print("done")


if __name__ == "__main__":
    main()
