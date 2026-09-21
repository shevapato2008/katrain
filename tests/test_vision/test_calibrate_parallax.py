"""Calibration tool, judgment half (prd P1-2 acceptance 4): nothing is written unless every check passes."""

import numpy as np
import pytest

from katrain.vision.config import DEFAULT_MARGIN_CELLS
from katrain.vision.parallax_store import load_parallax, parallax_path
from katrain.vision.tools.calibrate_parallax import (
    MAX_GRID_SHIFT_CELLS,
    PATTERN_17,
    GridOffset,
    decide_and_write,
    evaluate,
    grid_check_reasons,
    grid_offset,
)
from katrain.vision.warp import margin_px_for
from tests.test_vision.parallax_synth import H_MM, H_STONE_MM, K_TRUE, detected_grid

ALIGNED = GridOffset(0.0, 0.0, 19, 19)
OUT = 950  # geometry-lock warp size; with the 1-cell margin the warped canvas is 1056
PAD = margin_px_for(OUT, DEFAULT_MARGIN_CELLS)
CANVAS = OUT + 2 * PAD
PITCH = (OUT - 1) / 18


def _frames(k=K_TRUE, n=30, jitter=0.02, shift=None, seed=1):
    """Raw detections as the tool sees them: one stone per calibration point, black/white alternating."""
    rng = np.random.default_rng(seed)
    frames = []
    for _ in range(n):
        dets = []
        for i, (r, c) in enumerate(PATTERN_17):
            fx, fy = detected_grid(c, r, k=k)
            if shift is not None and (r, c) == shift[0]:
                fx += shift[1]
            dets.append((fy + rng.normal(0, jitter), fx + rng.normal(0, jitter), i % 2))
        frames.append(dets)
    return frames


def _coverage(pos, centre, half_width=1.0):
    """Share of each pixel [p-0.5, p+0.5] covered by the band [centre-half_width, centre+half_width]."""
    return np.clip(np.minimum(pos + 0.5, centre + half_width) - np.maximum(pos - 0.5, centre - half_width), 0, 1)


def _board_image(dx=0.0, dy=0.0, jitter=0.0, lines=True, seed=0):
    """A warped EMPTY board: wood, a lighting gradient, sensor noise and (optionally) the printed grid, drawn
    (dx, dy) cells away from where the saved geometry expects it; ``jitter`` = per-line print/warp error in cells."""
    rng = np.random.default_rng(seed)
    pos = np.arange(CANVAS, dtype=np.float64)
    ink = np.zeros((CANVAS, CANVAS))
    if lines:
        xl = PAD + (np.arange(19) + dx + rng.normal(0, jitter, 19)) * PITCH
        yl = PAD + (np.arange(19) + dy + rng.normal(0, jitter, 19)) * PITCH
        span_x = _coverage(pos, (xl[0] + xl[-1]) / 2, (xl[-1] - xl[0]) / 2 + 1)
        span_y = _coverage(pos, (yl[0] + yl[-1]) / 2, (yl[-1] - yl[0]) / 2 + 1)
        for x in xl:
            ink = np.maximum(ink, np.outer(span_y, _coverage(pos, x)))
        for y in yl:
            ink = np.maximum(ink, np.outer(_coverage(pos, y), span_x))
        yy, xx = np.mgrid[0:CANVAS, 0:CANVAS]
        for r in (3, 9, 15):
            for c in (3, 9, 15):
                ink[(xx - xl[c]) ** 2 + (yy - yl[r]) ** 2 <= 16] = 1.0  # star points
    wood = np.array([95.0, 165.0, 215.0])  # BGR
    light = 0.75 + 0.35 * pos[None, :] / CANVAS + 0.1 * pos[:, None] / CANVAS
    img = wood[None, None, :] * light[:, :, None] * (1 - 0.7 * ink[:, :, None])
    img += rng.normal(0, 6, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def _grain_image(seed):
    """No grid at all: wood with 40 random dark grain streaks, the lighting gradient and noise."""
    rng = np.random.default_rng(seed)
    img = _board_image(lines=False, seed=seed).astype(np.float64)
    for _ in range(40):
        at = int(rng.uniform(1, CANVAS - 1))
        if rng.random() < 0.5:
            img[:, at - 1 : at + 1] *= rng.uniform(0.6, 0.9)
        else:
            img[at - 1 : at + 1, :] *= rng.uniform(0.6, 0.9)
    return np.clip(img, 0, 255).astype(np.uint8)


def _run(tmp_path, frames, dry_run=False, grid_offsets=None):
    return decide_and_write(
        frames,
        grid_offsets={"start": ALIGNED, "end": ALIGNED} if grid_offsets is None else grid_offsets,
        out_path=parallax_path(tmp_path),
        stone_set="ver9-22x7",
        camera_height_mm=H_MM,
        geometry_generation="gen-1",
        fitted_at="2026-09-22T10:00:00+08:00",
        dry_run=dry_run,
    )


def test_pattern_is_17_distinct_on_board_points_spanning_both_axes():
    assert len(set(PATTERN_17)) == 17
    assert all(0 <= r < 19 and 0 <= c < 19 for r, c in PATTERN_17)
    pts = np.array(PATTERN_17, dtype=float)
    assert np.linalg.matrix_rank(pts - pts.mean(axis=0)) == 2


def test_clean_capture_passes_and_writes_the_file(tmp_path):
    verdict, calib = _run(tmp_path, _frames())
    assert verdict.ok, verdict.reasons
    assert abs(verdict.fit.k - K_TRUE) < 5e-4
    assert verdict.fit.h_implied_mm == pytest.approx(H_STONE_MM, abs=0.3)
    assert (verdict.n_black, verdict.n_white) == (9, 8)
    loaded, reason = load_parallax(parallax_path(tmp_path))
    assert reason == "ok" and loaded == calib
    assert (loaded.stone_set, loaded.geometry_generation, loaded.frames, loaded.n_samples) == (
        "ver9-22x7",
        "gen-1",
        30,
        17,
    )


def test_dry_run_writes_nothing(tmp_path):
    verdict, _ = _run(tmp_path, _frames(), dry_run=True)
    assert verdict.ok and not parallax_path(tmp_path).exists()


def _drop(frames, cell, first_n=None):
    for i, dets in enumerate(frames):
        if first_n is None or i < first_n:
            dets[:] = [d for d in dets if (int(round(d[0])), int(round(d[1]))) != cell]
    return frames


def _append(frames, det, first_n=None):
    for i, dets in enumerate(frames):
        if first_n is None or i < first_n:
            dets.append(det)
    return frames


FAILURES = {
    "point missing": (lambda: _drop(_frames(), (9, 9)), "(9, 9)"),
    "point missing in 8 of 30 frames": (lambda: _drop(_frames(), (9, 9), first_n=8), "(9, 9)"),
    "two stones on one point": (lambda: _append(_frames(), (9.02, 9.01, 0)), "(9, 9)"),
    "stone off the pattern": (lambda: _append(_frames(), (5.0, 5.0, 0)), "(5, 5)"),
    "stone 0.45 cell off its point": (lambda: _frames(shift=((9, 9), 0.45)), "(9, 9)"),
    "implied height below the window": (lambda: _frames(k=(H_MM - 1.0) / H_MM), "h_implied"),
    "implied height far above the window": (lambda: _frames(k=(H_MM - 12.0) / H_MM), ""),
    "no frames": (lambda: [], "no frames"),
}


@pytest.mark.parametrize("name", sorted(FAILURES))
def test_failures_write_nothing_and_keep_the_old_file(tmp_path, name):
    make, needle = FAILURES[name]
    path = parallax_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"previous calibration")
    verdict, calib = _run(tmp_path, make())
    assert not verdict.ok and calib is None
    assert needle in " | ".join(verdict.reasons)
    assert path.read_bytes() == b"previous calibration"


def test_a_transient_extra_detection_is_tolerated(tmp_path):
    verdict, _ = _run(tmp_path, _append(_frames(), (5.0, 5.0, 0), first_n=2), dry_run=True)
    assert verdict.ok, verdict.reasons


def test_led_classes_and_margin_objects_are_not_stones(tmp_path):
    frames = _append(_append(_frames(), (9.0, 9.0, 2)), (-0.8, 4.0, 0))
    verdict, _ = _run(tmp_path, frames, dry_run=True)
    assert verdict.ok, verdict.reasons


def test_camera_settings_reproduce_the_service_capture():
    from types import SimpleNamespace

    from katrain.vision.tools.calibrate_parallax import camera_settings

    locked = camera_settings(SimpleNamespace(strategy="hardware_auto_then_lock"))
    assert locked == {"lock_exposure": True, "exposure": None, "lock_awb": False}
    assert camera_settings(SimpleNamespace(strategy="something_else"))["lock_exposure"] is False


def test_main_refuses_when_exposure_cannot_be_locked(tmp_path, monkeypatch):
    """codex review 2026-09-22: never calibrate under an exposure the service would not run with."""
    from types import SimpleNamespace

    import katrain.vision.camera as camera_mod
    import katrain.vision.stone_detector as detector_mod
    import katrain.web.core.hardware_vision_state as hvs
    from katrain.vision.tools import calibrate_parallax as tool

    state = SimpleNamespace(
        generation="gen-1",
        geometry=object(),
        profile=SimpleNamespace(strategy=hvs.CAMERA_STRATEGY_HARDWARE_AUTO_THEN_LOCK),
    )
    monkeypatch.setattr(hvs, "HardwareVisionStateStore", lambda root: SimpleNamespace(load_current=lambda *a: state))
    monkeypatch.setattr(detector_mod, "StoneDetector", lambda *a, **k: object())

    class FakeCamera:
        controls_effective = False  # the lock did not take

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.closed = False
            FakeCamera.last = self

        def open(self):
            return True

        def close(self):
            self.closed = True

    monkeypatch.setattr(camera_mod, "CameraManager", FakeCamera)
    rc = tool.main(["--hardware-vision-dir", str(tmp_path), "--model", "m.rknn", "--stone-set", "ver9-22x7"])
    assert rc == 2
    assert FakeCamera.last.kwargs["lock_exposure"] is True and FakeCamera.last.closed
    assert not parallax_path(tmp_path).exists()


# --- printed-grid check (codex round 2 [high]; Opus ruling 2026-09-22) ---


def test_aligned_grid_reads_zero_and_passes():
    off = grid_offset(_board_image(), OUT)
    assert abs(off.dx_cells) <= 0.02 and abs(off.dy_cells) <= 0.02
    assert (off.lines_x, off.lines_y) == (19, 19)
    assert grid_check_reasons(off, "start") == []


def test_a_quarter_cell_stale_geometry_is_measured_and_refused():
    off = grid_offset(_board_image(dy=0.25), OUT)
    assert off.dy_cells == pytest.approx(0.25, abs=0.02)
    reasons = grid_check_reasons(off, "start")
    assert reasons and "re-lock" in reasons[0]


@pytest.mark.parametrize("dx, dy, refused", [(-0.12, 0.07, True), (0.06, 0.05, False)])
def test_the_grid_threshold_is_pinned_from_both_sides(dx, dy, refused):
    off = grid_offset(_board_image(dx=dx, dy=dy), OUT)
    assert (off.shift_cells > MAX_GRID_SHIFT_CELLS) == refused
    assert bool(grid_check_reasons(off, "end")) == refused


@pytest.mark.parametrize("axis", ["dx", "dy"])
@pytest.mark.parametrize("shift", [0.45, -0.45])
def test_large_sub_cell_shifts_are_recovered_and_refused(axis, shift):
    off = grid_offset(_board_image(**{axis: shift}), OUT)
    assert getattr(off, f"{axis}_cells") == pytest.approx(shift, abs=0.03)
    assert grid_check_reasons(off, "start")


def test_per_line_print_error_is_tolerated_but_a_shift_is_not():
    assert grid_check_reasons(grid_offset(_board_image(jitter=0.06, seed=3), OUT), "start") == []
    assert grid_check_reasons(grid_offset(_board_image(dy=0.25, jitter=0.06, seed=3), OUT), "start")


@pytest.mark.parametrize("seed", range(10))
def test_a_frame_without_a_grid_is_refused_as_not_found(seed):
    reasons = grid_check_reasons(grid_offset(_grain_image(seed), OUT), "start")
    assert reasons and "not found" in reasons[0]


def test_stale_geometry_is_refused_although_the_fit_itself_is_perfect(tmp_path):
    """codex round 2 [high]: a warp translation is absorbed into the nadir with zero residual and a plausible h, so
    only the printed-grid check can refuse it. Red if decide_and_write ignores grid_offsets."""
    frames = [[(fy + 0.25, fx, cls) for fy, fx, cls in dets] for dets in _frames(jitter=0.0)]
    alone = evaluate(frames, H_MM)
    assert alone.ok and alone.fit.max_resid_cells < 1e-9  # the fit cannot see it
    assert alone.fit.h_implied_mm == pytest.approx(H_STONE_MM, abs=0.3)
    stale = grid_offset(_board_image(dy=0.25), OUT)
    path = parallax_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"previous calibration")
    for offsets in ({"start": stale, "end": stale}, {"start": ALIGNED, "end": stale}):  # stale before / bumped during
        verdict, calib = _run(tmp_path, frames, grid_offsets=offsets)
        assert not verdict.ok and calib is None
        assert "re-lock" in " | ".join(verdict.reasons)
        assert path.read_bytes() == b"previous calibration"


def test_a_whole_cell_shift_that_the_grid_check_aliases_to_zero_is_refused_by_pairing(tmp_path):
    frames = [[(fy, fx + 1.0, cls) for fy, fx, cls in dets] for dets in _frames()]
    verdict, calib = _run(tmp_path, frames)
    assert not verdict.ok and calib is None


def test_no_grid_measurement_means_no_calibration(tmp_path):
    verdict, calib = _run(tmp_path, _frames(), grid_offsets={})
    assert not verdict.ok and calib is None
    assert "no geometry check" in " | ".join(verdict.reasons)
