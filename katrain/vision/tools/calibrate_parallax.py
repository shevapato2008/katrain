"""Stone-parallax calibration for the geometry-locked board (vision-stone-parallax track).

Run ON THE BOARD with the katrain service stopped (it owns the camera):

    sudo systemctl stop smartbox-katrain
    /opt/smartbox/venv-katrain/bin/python -m katrain.vision.tools.calibrate_parallax \\
        --hardware-vision-dir /var/lib/smartbox/hardware/vision \\
        --model /opt/smartbox/share/katrain-vision/go4_s.rknn --backend rknn \\
        --camera 0 --resolution 1920x1080 --enhance clahe --conf 0.30 --stone-set ver9-22x7
    sudo systemctl start smartbox-katrain

Start with the board EMPTY and exactly where it was when the geometry was locked (do not touch it after
stopping the service). The tool first checks that the printed grid lines sit where the saved geometry
expects them; then place one stone on each of the 17 printed points (alternate black and white), press
Enter, keep hands out of view; then remove all stones for the closing grid check. The tool warps each
frame exactly like the service, reads the RAW (uncorrected) grid positions, takes the per-point median over
--frames frames, fits k and the nadir, and writes <hardware-vision-dir>/parallax/go-19x19.json ONLY if every
check passes, both grid checks included. Recalibrate after moving the camera arm, changing the board or the
stones, or aligning the board (prd §5).
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from katrain.vision.classes import NAME_TO_ID, STONE_CLASS_IDS
from katrain.vision.config import DEFAULT_MARGIN_CELLS
from katrain.vision.parallax import FitResult, fit_parallax
from katrain.vision.parallax_store import (
    BOARD_GO_19,
    H_IMPLIED_WINDOW_MM,
    ParallaxCalibration,
    parallax_path,
    save_parallax,
)
from katrain.vision.warp import adjust_M_for_resolution, margin_px_for, warp_with_margin

# (row, col) in the geometry-lock grid: 9 star points, 4 corners, 4 edge midpoints. 17 rather than 9:
# with ~1.5 mm of placement error, 9 points get falsely refused by the 2-8 mm window 2.5% of the time,
# 17 points 0.4% (design D5).
PATTERN_17: tuple[tuple[int, int], ...] = (
    (3, 3), (3, 9), (3, 15), (9, 3), (9, 9), (9, 15), (15, 3), (15, 9), (15, 15),
    (0, 0), (0, 18), (18, 0), (18, 18),
    (0, 9), (9, 0), (9, 18), (18, 9),
)  # fmt: skip
MIN_PRESENCE = 0.8  # a point must hold exactly one stone detection in at least this share of frames
MAX_EXTRA = 0.2  # an off-pattern intersection holding a stone in this share of frames is a real stray stone
# 0.30 cell (~6.9 mm), not tighter: at ~1.5 mm placement error one of 17 points exceeds 0.15 cell
# about 70% of the time, 0.30 cell about 0.05%.
MAX_RESID_CELLS = 0.30
# Lens height above the board for the ver9 mount (geometry.md §3: lens_mm z 348.942 - board z 9.5).
# Only used for the h_implied diagnostic and its 2-8 mm gate; the correction itself never uses it.
DEFAULT_CAMERA_HEIGHT_MM = 339.44
# Printed-grid check (codex round 2 [high]). The fit absorbs a warp translation t into the nadir with zero
# residual, and once the runtime geometry is re-locked t becomes a permanent error of k*t ~ t. The printed lines
# (h = 0) move with the board, so their offset from where the warp expects them IS that t. 0.10 cell is the
# GeometryDriftMonitor threshold: a warp the service would call "board moved" is never calibrated on.
MAX_GRID_SHIFT_CELLS = 0.10
MIN_GRID_LINES = 15  # of 19 per axis must agree with the median offset, or the grid was not seen
EMPTY_FRAMES = 5  # empty-board frames per grid check (per-pixel median)
_LINE_TOL_CELLS = 0.15
_BLACK = NAME_TO_ID["black"]


@dataclass(frozen=True)
class GridOffset:
    dx_cells: float  # printed grid minus where the saved geometry puts it, in cells
    dy_cells: float
    lines_x: int  # lines within _LINE_TOL_CELLS of the median offset, of 19
    lines_y: int

    @property
    def shift_cells(self) -> float:
        return math.hypot(self.dx_cells, self.dy_cells)


def _axis_offset(profile, expected, pitch):
    """Offset (cells) of the 19 line peaks in ``profile`` from ``expected``, and how many lines agree with it.
    A comb search over [-0.5, 0.5) cell finds the grid as a whole; each line is then refined to a sub-pixel peak."""
    xs = np.arange(len(profile), dtype=np.float64)
    deltas = np.arange(-50, 50) / 100.0
    scores = [np.interp(expected + d * pitch, xs, profile).sum() for d in deltas]
    d0 = float(deltas[int(np.argmax(scores))])
    half = int(0.4 * pitch)
    offsets = []
    for e in expected:
        c = int(round(e + d0 * pitch))
        lo, hi = max(c - half, 1), min(c + half, len(profile) - 2)
        i = lo + int(np.argmax(profile[lo : hi + 1]))
        a, b, cc = profile[i - 1], profile[i], profile[i + 1]
        den = a - 2 * b + cc
        sub = 0.5 * (a - cc) / den if den < 0 else 0.0
        offsets.append((i + sub - e) / pitch)
    offsets = np.array(offsets)
    t = float(np.median(offsets))
    return t, int(np.sum(np.abs(offsets - t) <= _LINE_TOL_CELLS))


def grid_offset(warped_bgr, out_size: int, margin_cells: float = DEFAULT_MARGIN_CELLS) -> GridOffset:
    """Where the printed grid lines of an EMPTY warped board sit relative to where the geometry lock puts them
    (line i at pad + i*(out_size-1)/18, the warp's own geometry, not BoardConfig's mm mapping)."""
    pad = margin_px_for(out_size, margin_cells)
    pitch = (out_size - 1) / 18
    expected = pad + np.arange(19) * pitch
    grey = cv2.cvtColor(warped_bgr, cv2.COLOR_BGR2GRAY) if warped_bgr.ndim == 3 else warped_bgr
    grey = cv2.GaussianBlur(grey, (3, 3), 0)
    # black-hat keeps thin dark marks (lines, star points) and drops lighting gradients and large blobs
    lines = cv2.morphologyEx(grey, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15)))
    lines = lines.astype(np.float64)
    inside = slice(pad, pad + out_size)
    dx, nx = _axis_offset(lines[inside, :].mean(axis=0), expected, pitch)
    dy, ny = _axis_offset(lines[:, inside].mean(axis=1), expected, pitch)
    return GridOffset(dx, dy, nx, ny)


def grid_check_reasons(off: GridOffset, when: str) -> list[str]:
    if min(off.lines_x, off.lines_y) < MIN_GRID_LINES:
        return [
            f"{when}: printed grid lines not found (x {off.lines_x}/19, y {off.lines_y}/19): is the board empty and lit?"
        ]
    if off.shift_cells > MAX_GRID_SHIFT_CELLS:
        return [
            f"{when}: the saved geometry is {off.shift_cells:.2f} cells off the printed grid "
            f"(dx {off.dx_cells:+.2f}, dy {off.dy_cells:+.2f}): the board moved since the geometry was locked. "
            "Start the service, re-lock the geometry on the empty board, stop it, and calibrate again."
        ]
    return []


@dataclass
class Verdict:
    ok: bool
    reasons: list[str]
    fit: FitResult | None = None
    medians: dict = field(default_factory=dict)  # (row, col) -> (fx_raw, fy_raw)
    n_black: int = 0
    n_white: int = 0


def evaluate(frames, camera_height_mm: float, pattern=PATTERN_17) -> Verdict:
    """Judge a capture. ``frames``: per captured frame, the RAW detections as [(fy_raw, fx_raw, class_id)]."""
    total = len(frames)
    if total == 0:
        return Verdict(False, ["no frames captured"])
    wanted = set(pattern)
    seen = {cell: [] for cell in pattern}
    extra = Counter()
    for dets in frames:
        per_cell = defaultdict(list)
        for fy, fx, cls in dets:
            if cls not in STONE_CLASS_IDS:
                continue  # LED classes are not stones
            cell = (int(round(fy)), int(round(fx)))
            if not (0 <= cell[0] < 19 and 0 <= cell[1] < 19):
                continue  # warp-margin objects are not stones
            per_cell[cell].append((fx, fy, cls))
        for cell, hits in per_cell.items():
            if cell in wanted:
                if len(hits) == 1:
                    seen[cell].append(hits[0])
            else:
                extra[cell] += 1
    reasons = []
    for cell in pattern:
        if len(seen[cell]) < MIN_PRESENCE * total:
            reasons.append(
                f"point {cell}: exactly one stone in only {len(seen[cell])}/{total} frames "
                "(missing, doubled, or not detected)"
            )
    for cell, n in sorted(extra.items()):
        if n >= MAX_EXTRA * total:
            reasons.append(
                f"unexpected stone at {cell} in {n}/{total} frames (only the calibration points may hold stones)"
            )
    if reasons:
        return Verdict(False, reasons)
    medians = {
        cell: (float(np.median([h[0] for h in seen[cell]])), float(np.median([h[1] for h in seen[cell]])))
        for cell in pattern
    }
    colours = [Counter(h[2] for h in seen[cell]).most_common(1)[0][0] for cell in pattern]
    n_black = sum(1 for c in colours if c == _BLACK)
    n_white = len(pattern) - n_black
    try:
        fit = fit_parallax([(c, r) for r, c in pattern], [medians[cell] for cell in pattern], camera_height_mm)
    except ValueError as exc:
        return Verdict(False, [f"fit failed: {exc}"], None, medians, n_black, n_white)
    lo, hi = H_IMPLIED_WINDOW_MM
    if not lo <= fit.h_implied_mm <= hi:
        reasons.append(f"h_implied {fit.h_implied_mm:.2f} mm is outside [{lo}, {hi}]: the warp or the pairing is wrong")
    if fit.max_resid_cells > MAX_RESID_CELLS:
        reasons.append(
            f"point {pattern[fit.worst_index]} is {fit.max_resid_cells:.2f} cells off the fit "
            f"(> {MAX_RESID_CELLS}): re-seat that stone on its intersection"
        )
    return Verdict(not reasons, reasons, fit, medians, n_black, n_white)


def decide_and_write(
    frames,
    *,
    grid_offsets: dict,
    out_path,
    stone_set: str,
    camera_height_mm: float,
    geometry_generation,
    fitted_at: str,
    dry_run: bool,
):
    """Grid checks + evaluate(); on success build the calibration and (unless dry_run) save it. Nothing is written
    on failure. ``grid_offsets``: {"start": GridOffset, "end": GridOffset} measured on the empty board."""
    grid_reasons = [] if grid_offsets else ["no geometry check: the printed grid was not measured on the empty board"]
    for when, off in grid_offsets.items():
        grid_reasons += grid_check_reasons(off, when)
    verdict = evaluate(frames, camera_height_mm)
    if grid_reasons:
        verdict = replace(verdict, ok=False, reasons=grid_reasons + verdict.reasons)
    if not verdict.ok:
        return verdict, None
    fit = verdict.fit
    calib = ParallaxCalibration(
        board=BOARD_GO_19,
        stone_set=stone_set,
        nadir_fx=fit.nadir_fx,
        nadir_fy=fit.nadir_fy,
        k=fit.k,
        m=fit.m,
        h_implied_mm=fit.h_implied_mm,
        camera_height_mm=camera_height_mm,
        rms_cells=fit.rms_cells,
        max_resid_cells=fit.max_resid_cells,
        n_samples=fit.n,
        n_black=verdict.n_black,
        n_white=verdict.n_white,
        frames=len(frames),
        geometry_generation=geometry_generation,
        fitted_at=fitted_at,
    )
    if not dry_run:
        save_parallax(out_path, calib)
    return verdict, calib


def render_pattern(pattern=PATTERN_17) -> str:
    """ASCII board, far side (row 0) at the top as the camera sees it; X = put a stone here."""
    rows = []
    for r in range(19):
        rows.append(f"{r:2d} " + " ".join("X" if (r, c) in pattern else "." for c in range(19)))
    return "   " + " ".join(str(c % 10) for c in range(19)) + "\n" + "\n".join(rows)


def camera_settings(profile) -> dict:
    """CameraManager exposure / white-balance arguments that reproduce the service's capture for this
    geometry generation (server.py: a persisted hardware_auto_then_lock profile -> lock_exposure with
    exposure=None; AWB stays unlocked). Calibrating under different exposure would bake an
    exposure-dependent detector bias into k and the nadir (codex review 2026-09-22)."""
    from katrain.web.core.hardware_vision_state import CAMERA_STRATEGY_HARDWARE_AUTO_THEN_LOCK

    return {
        "lock_exposure": profile.strategy == CAMERA_STRATEGY_HARDWARE_AUTO_THEN_LOCK,
        "exposure": None,
        "lock_awb": False,
    }


def _warp(frame, lock):
    """The service's warp (worker_inprocess): lock homography, resolution-adjusted, 1-cell margin."""
    M = adjust_M_for_resolution(lock.M, (lock.source_width, lock.source_height), (frame.shape[1], frame.shape[0]))
    return warp_with_margin(frame, M, int(lock.out_size), margin_cells=DEFAULT_MARGIN_CELLS)


def _read_frames(camera, n_frames: int, timeout_s: float, settle_s: float = 0.5):
    """``n_frames`` distinct frames captured after this call (plus ``settle_s``), never a frame the camera
    already had queued. ``CameraManager.read_frame()`` returns whatever is latest immediately, which while
    this generator is blocked on an operator's ``input()`` is a frame from up to ~1s before Enter (the idle
    reader decodes at 1 fps after CAMERA_IDLE_AFTER_S) and can carry the operator's hand into frame; gate on
    the reader thread's own timestamps via ``grab_fresh`` instead."""
    deadline = time.monotonic() + timeout_s
    after = time.monotonic() + settle_s
    while n_frames > 0:
        if time.monotonic() > deadline:
            raise RuntimeError(f"camera stopped delivering frames ({n_frames} still wanted after {timeout_s:.0f}s)")
        frame, _seq, ts = camera.grab_fresh(after_ts=after, settle_ms=0.0, timeout=1.0)
        if frame is None or ts <= after:  # grab_fresh returns the latest (possibly stale) frame on timeout
            continue
        after = ts
        n_frames -= 1
        yield frame


def empty_board_offset(camera, lock, n_frames: int = EMPTY_FRAMES, timeout_s: float = 30.0) -> GridOffset:
    """Printed-grid check on the empty board: per-pixel median of ``n_frames`` distinct, freshly-captured
    warped frames (no enhancement)."""
    warped = [_warp(frame, lock) for frame in _read_frames(camera, n_frames, timeout_s)]
    return grid_offset(np.median(np.stack(warped), axis=0).astype(np.uint8), int(lock.out_size))


def capture_frames(camera, lock, detector, extractor, enhance: str, n_frames: int, timeout_s: float = 120.0):
    """Warp + enhance + detect exactly like worker_inprocess, keeping RAW grid positions of stone detections.
    Frames are distinct and captured after the call (see ``_read_frames``), not a stale frame that predates
    Enter or one still catching an operator's hand."""
    from katrain.vision.enhance import enhance_for_inference

    frames = []
    for frame in _read_frames(camera, n_frames, timeout_s):
        warped = enhance_for_inference(_warp(frame, lock), enhance)
        h, w = warped.shape[:2]
        pts = extractor.parallax_points(detector.detect(warped), img_w=w, img_h=h)
        frames.append([(fy_raw, fx_raw, cls) for fy_raw, fx_raw, _fy, _fx, cls, _conf in pts])
    return frames


def _fmt(off: GridOffset) -> str:
    return f"dx {off.dx_cells:+.3f} dy {off.dy_cells:+.3f} cells (|{off.shift_cells:.3f}|), lines {off.lines_x}/{off.lines_y}"


def _report_and_write(verdict: Verdict, calib, out_path, dry_run: bool) -> int:
    """Print the verdict (fit numbers BEFORE any write, so a write failure never hides them), then write
    the calibration unless ``dry_run``. A ``save_parallax`` failure (e.g. an empty --stone-set, or a
    permission error) is reported plainly, no traceback."""
    if not verdict.ok:
        print("CALIBRATION FAILED, nothing written:")
        for reason in verdict.reasons:
            print(f"  - {reason}")
        return 1
    fit = verdict.fit
    print(f"k={fit.k:.6f} m={fit.m:.6f} nadir=({fit.nadir_fx:.3f}, {fit.nadir_fy:.3f})")
    # BoardConfig's mm mapping scales the warp grid by 0.99853, which reads h ~0.5 mm low (harmless to the fix)
    print(f"h_implied={fit.h_implied_mm:.2f} mm (~3.0 = detector reports the mid-plane, ~6.5 = the top face)")
    print(
        f"rms={fit.rms_cells:.3f} cells (~{fit.rms_cells * 22.85:.1f} mm), worst {PATTERN_17[fit.worst_index]} "
        f"{fit.max_resid_cells:.3f} cells; stones {verdict.n_black} black / {verdict.n_white} white"
    )
    if dry_run:
        print(f"dry run: not written to {out_path}")
        return 0
    try:
        save_parallax(out_path, calib)
    except Exception as exc:
        print(f"not written: {exc}")
        return 1
    print(f"wrote {out_path}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Calibrate the stone-parallax correction (run on the board, service stopped)"
    )
    ap.add_argument("--hardware-vision-dir", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--backend", default="rknn", choices=["ultralytics", "onnx", "rknn"])
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--resolution", default="1920x1080")
    ap.add_argument("--enhance", default="clahe", choices=["clahe", "off"])
    ap.add_argument("--conf", type=float, default=0.30, help="detector threshold; the board service keeps at 0.30")
    ap.add_argument("--frames", type=int, default=30)
    ap.add_argument("--stone-set", required=True, help='which stones were used, e.g. "ver9-22x7"')
    ap.add_argument("--camera-height-mm", type=float, default=DEFAULT_CAMERA_HEIGHT_MM)
    ap.add_argument("--dry-run", action="store_true", help="report only; never write the calibration file")
    args = ap.parse_args(argv)

    from katrain.vision.board_state import BoardStateExtractor
    from katrain.vision.camera import CameraManager
    from katrain.vision.config import BoardConfig
    from katrain.vision.stone_detector import StoneDetector
    from katrain.web.core.hardware_vision_state import HardwareVisionStateStore

    width, height = (int(v) for v in args.resolution.lower().split("x"))
    try:
        state = HardwareVisionStateStore(Path(args.hardware_vision_dir).expanduser()).load_current(
            args.camera, width, height
        )
    except (OSError, ValueError) as exc:
        print(f"cannot read the current geometry: {exc}")
        return 2
    if state is None:
        print("no current geometry for this camera/resolution: lock the board geometry first")
        return 2

    detector = StoneDetector(args.model, backend=args.backend, confidence_threshold=args.conf)
    extractor = BoardStateExtractor(BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS))  # no parallax: RAW positions
    settings = camera_settings(state.profile)
    camera = CameraManager(device_id=args.camera, width=width, height=height, **settings)
    if not camera.open():
        print(f"cannot open camera {args.camera} (is the katrain service still running?)")
        return 2
    if settings["lock_exposure"] and camera.controls_effective is not True:
        camera.close()
        print("camera exposure could not be locked the way the service locks it: refusing to calibrate")
        return 2
    try:
        input("The board must be EMPTY and untouched since the geometry was locked. Press Enter. ")
        start = empty_board_offset(camera, state.geometry)
        print(f"printed grid vs saved geometry, start: {_fmt(start)}")
        reasons = grid_check_reasons(start, "start")
        if reasons:
            print("CALIBRATION REFUSED, nothing written:")
            for reason in reasons:
                print(f"  - {reason}")
            return 1
        print(render_pattern())
        input(f"Place one stone on each X ({len(PATTERN_17)} points, alternate black/white), then press Enter. ")
        frames = capture_frames(camera, state.geometry, detector, extractor, args.enhance, args.frames)
        input("Remove ALL stones without moving the board, then press Enter. ")
        end = empty_board_offset(camera, state.geometry)
        print(f"printed grid vs saved geometry, end:   {_fmt(end)}")
    finally:
        camera.close()

    out_path = parallax_path(args.hardware_vision_dir)
    verdict, calib = decide_and_write(
        frames,
        grid_offsets={"start": start, "end": end},
        out_path=out_path,
        stone_set=args.stone_set,
        camera_height_mm=args.camera_height_mm,
        geometry_generation=state.generation,
        fitted_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        dry_run=True,  # evaluate + build the calibration first, print the fit, write for real below
    )
    return _report_and_write(verdict, calib, out_path, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
