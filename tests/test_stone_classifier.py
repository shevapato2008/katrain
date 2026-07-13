"""Equivalence + refactor-guard tests for the classical stone classifier.

The SBC (RK3562) spends ~10s finalizing LED geometry calibration; ~7.5s of that
is `sample_grid` (a 361-point Python loop of `np.median`) invoked 16x by
`_build_lock`. These tests pin the EXACT current behaviour so the vectorization
(sample_grid) and the sample-reuse refactor (build_baseline_from_samples /
classify_from_sample) cannot change a single classification.
"""

import cv2
import numpy as np

from katrain.vision import stone_classifier as sc


def _reference_sample_grid(warp, xs, ys, patch_ratio=sc.PATCH_RATIO):
    """The original, un-vectorized implementation — an independent oracle.

    Kept verbatim in the test so the production `sample_grid` is checked against
    a copy that never changes, including the clipped patches at board borders.
    """
    hsv = cv2.cvtColor(warp, cv2.COLOR_BGR2HSV)
    h, w = hsv.shape[:2]
    spacing = float(np.median(np.diff(xs)))
    r = max(3.0, spacing * patch_ratio)
    out = np.zeros((sc.GRID_SIZE, sc.GRID_SIZE, 3), np.float32)
    for ri in range(sc.GRID_SIZE):
        for ci in range(sc.GRID_SIZE):
            cx, cy = xs[ci], ys[ri]
            x0, x1 = max(0, int(cx - r)), min(w, int(cx + r) + 1)
            y0, y1 = max(0, int(cy - r)), min(h, int(cy + r) + 1)
            patch = hsv[y0:y1, x0:x1].reshape(-1, 3)
            if patch.size == 0:
                out[ri, ci] = np.array([0.0, 0.0, 0.0], np.float32)
            else:
                out[ri, ci] = np.median(patch, axis=0).astype(np.float32)
    return out


def _board_grid(size=950):
    xs = np.linspace(0, size - 1, sc.GRID_SIZE).astype(np.float32)
    return xs, xs.copy()


def test_sample_grid_matches_reference_on_random_board_including_borders():
    # linspace(0, size-1) puts anchors exactly on the edges (0 and size-1), so
    # the four corners and all edge points exercise the clipped-patch path.
    xs, ys = _board_grid(950)
    warp = np.random.default_rng(7).integers(0, 255, (950, 950, 3), dtype=np.uint8)

    got = sc.sample_grid(warp, xs, ys)
    ref = _reference_sample_grid(warp, xs, ys)

    np.testing.assert_array_equal(got, ref)


def test_sample_grid_matches_reference_on_nonsquare_frame_with_stones():
    # Non-square frame + real stone-like patches: the clipping uses image h and w
    # independently, and a mistaken axis would surface here.
    xs, ys = _board_grid(720)
    warp = np.full((720, 900, 3), 90, np.uint8)
    cv2.circle(warp, (0, 0), 30, (20, 20, 20), -1)  # dark stone straddling the corner
    cv2.circle(warp, (360, 360), 30, (240, 240, 240), -1)  # bright stone mid-board
    cv2.circle(warp, (899, 719), 30, (240, 20, 20), -1)  # far corner

    got = sc.sample_grid(warp, xs, ys)
    ref = _reference_sample_grid(warp, xs, ys)

    np.testing.assert_array_equal(got, ref)


def test_build_baseline_from_samples_equals_build_baseline():
    xs, ys = _board_grid(950)
    rng = np.random.default_rng(1)
    warps = [rng.integers(0, 255, (950, 950, 3), dtype=np.uint8) for _ in range(4)]

    samples = [sc.sample_grid(w, xs, ys) for w in warps]
    got = sc.build_baseline_from_samples(samples)
    ref = sc.build_baseline(warps, xs, ys)

    np.testing.assert_array_equal(got, ref)


def test_classify_from_sample_equals_classify():
    xs, ys = _board_grid(950)
    rng = np.random.default_rng(2)
    baseline = sc.build_baseline([rng.integers(0, 255, (950, 950, 3), dtype=np.uint8)], xs, ys)
    target = rng.integers(0, 255, (950, 950, 3), dtype=np.uint8)

    ref_state, _ref_cur = sc.classify(target, xs, ys, baseline)
    cur = sc.sample_grid(target, xs, ys)
    got_state = sc.classify_from_sample(cur, baseline)

    np.testing.assert_array_equal(got_state, ref_state)
