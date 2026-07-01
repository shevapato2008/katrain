"""Task 9 (P12): the crowded-board accuracy GATE logic (deterministic, injected detectors).

The synthetic-render → real-detector measurement is a benchmark (run via __main__ / hardware);
here we lock the GATE's measurement + thresholding so it can't silently mis-pass.
"""
import numpy as np

from katrain.vision.tools.outer_corner_accuracy import (
    corner_error_cells,
    dense_stones,
    gate,
    measure,
    render_board,
)

QUAD = np.array([[260, 150], [1010, 170], [1040, 690], [240, 660]], np.float64)


def test_dense_stones_fill_fraction():
    rng = np.random.default_rng(0)
    assert len(dense_stones(0.0, rng)) == 0
    assert len(dense_stones(0.8, rng)) == round(0.8 * 361)
    assert len(dense_stones(1.0, rng)) == 361


def test_corner_error_zero_for_identical_quad():
    assert corner_error_cells(QUAD, QUAD) < 1e-6


def test_corner_error_scales_with_displacement():
    noisy = QUAD + np.array([6, 0])  # shift all corners 6px
    err = corner_error_cells(noisy, QUAD)
    assert err > 0.0
    # 6px on a ~40px camera cell ≈ 0.15 cells — sanity bound
    assert 0.05 < err < 0.5


def test_measure_perfect_detector_passes_gate():
    res = measure(detect_fn=lambda frame: QUAD.copy(), fills=(0.0, 0.8), rotations=(0.0,), base_quad=QUAD)
    assert all(e is not None and e < 1e-6 for e in res.values())
    assert gate(res, max_error_cells=0.12) is True


def test_measure_noisy_detector_fails_gate():
    res = measure(detect_fn=lambda frame: QUAD + np.array([20, 0]), fills=(0.0,), rotations=(0.0,), base_quad=QUAD)
    assert gate(res, max_error_cells=0.12) is False


def test_render_board_produces_frame():
    f = render_board(QUAD, fill_pct=0.5, frame_size=(1280, 720))
    assert f.shape == (720, 1280, 3) and int(f.max()) > 0


def test_gate_false_when_no_detections():
    assert gate({(0.0, 0.0): None}, max_error_cells=0.12) is False
