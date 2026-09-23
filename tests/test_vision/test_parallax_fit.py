"""Calibration fit (prd P1-2 acceptance 1-3; acceptance 2 as rewritten 2026-09-22)."""

import numpy as np
import pytest

from katrain.vision.coordinates import apply_parallax
from katrain.vision.parallax import ParallaxParams, fit_parallax
from tests.test_vision.parallax_synth import (
    H_MM,
    H_STONE_MM,
    K_TRUE,
    NADIR_GRID,
    detected_grid,
    grid_to_mm,
    mm_to_grid,
)

PATTERN_9 = [(0, 0), (18, 0), (0, 18), (18, 18), (9, 9), (3, 3), (15, 3), (3, 15), (15, 15)]  # (col, row)


def _detected(pattern, rng=None, sigma_mm=0.0):
    out = []
    for c, r in pattern:
        x, y = grid_to_mm(*detected_grid(c, r))
        if rng is not None:
            x, y = x + rng.normal(0, sigma_mm), y + rng.normal(0, sigma_mm)
        out.append(mm_to_grid(x, y))
    return out


def _worst_correction_error_mm(params):
    worst = 0.0
    for r in range(19):
        for c in range(19):
            fx, fy = apply_parallax(*detected_grid(c, r), params.nadir, params.k)
            (ex, ey), (tx, ty) = grid_to_mm(fx, fy), grid_to_mm(c, r)
            worst = max(worst, float(np.hypot(ex - tx, ey - ty)))
    return worst


def test_noiseless_fit_recovers_the_truth():
    fit = fit_parallax(PATTERN_9, _detected(PATTERN_9), H_MM)
    assert abs(fit.k - K_TRUE) < 1e-6
    assert abs(fit.nadir_fx - NADIR_GRID[0]) < 1e-6 and abs(fit.nadir_fy - NADIR_GRID[1]) < 1e-6
    assert fit.rms_cells < 1e-9
    assert fit.h_implied_mm == pytest.approx(H_STONE_MM, abs=1e-6)
    assert fit.n == 9
    assert fit.params == ParallaxParams(fit.nadir_fx, fit.nadir_fy, fit.k)


def test_noisy_fit_is_accurate_where_it_matters():
    """Measured on h_implied and on the corrected positions -- never on k (k = 1, i.e. no correction
    at all, scores a 1.04% k error) nor on the nadir (ill-conditioned: ~29 mm p95 at this noise)."""
    rng = np.random.default_rng(20260922)
    h_err, corr_err = [], []
    for _ in range(200):
        fit = fit_parallax(PATTERN_9, _detected(PATTERN_9, rng, 0.3), H_MM)
        h_err.append(abs(fit.h_implied_mm - H_STONE_MM) / H_STONE_MM)
        corr_err.append(_worst_correction_error_mm(fit.params))
    assert np.percentile(h_err, 95) < 0.20  # 0.083 at design time
    assert np.percentile(corr_err, 95) < 1.0  # 0.395 mm at design time


def test_the_accuracy_gate_rejects_no_correction():
    # The gate above must be one that "no correction" fails, or it certifies nothing.
    assert _worst_correction_error_mm(ParallaxParams(*NADIR_GRID, 1.0)) > 1.0


@pytest.mark.parametrize("pattern", [[(0, 0)], [(0, 0), (18, 18)]])
def test_fewer_than_three_samples_raise(pattern):
    with pytest.raises(ValueError, match="at least 3"):
        fit_parallax(pattern, _detected(pattern), H_MM)


def test_collinear_samples_raise():
    row = [(c, 0) for c in range(0, 19, 3)]
    with pytest.raises(ValueError, match="collinear"):
        fit_parallax(row, _detected(row), H_MM)


def test_coincident_samples_raise():
    same = [(9, 9)] * 5
    with pytest.raises(ValueError, match="collinear"):
        fit_parallax(same, _detected(same), H_MM)


def test_no_parallax_raises():
    with pytest.raises(ValueError, match="no measurable parallax"):
        fit_parallax(PATTERN_9, [(float(c), float(r)) for c, r in PATTERN_9], H_MM)


def test_shape_mismatch_raises():
    with pytest.raises(ValueError, match=r"\(n, 2\)"):
        fit_parallax(PATTERN_9, _detected(PATTERN_9)[:-1], H_MM)
