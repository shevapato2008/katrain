import math

import pytest

from katrain.vision.coordinates import apply_parallax
from katrain.vision.parallax import ParallaxParams
from tests.test_vision.parallax_synth import K_TRUE, NADIR_GRID, detected_grid


class TestApplyParallax:
    @pytest.mark.parametrize("nadir,k", [(None, 0.99), ((9.0, 19.6), None), (None, None)])
    def test_uncalibrated_is_identity(self, nadir, k):
        assert apply_parallax(3.1, 17.7, nadir, k) == (3.1, 17.7)

    def test_k_one_returns_inputs_bit_for_bit(self):
        # nadir + (fx - nadir) * 1.0 is not always fx in floating point, so k == 1.0 must
        # short-circuit for "off" to be bit-identical (prd P1-1 acceptance 1).
        assert 9.0 + (0.1 - 9.0) != 0.1
        assert apply_parallax(0.1, 0.1, (9.0, 19.6), 1.0) == (0.1, 0.1)

    def test_nadir_is_a_fixed_point(self):
        assert apply_parallax(*NADIR_GRID, NADIR_GRID, K_TRUE) == pytest.approx(NADIR_GRID, abs=1e-12)

    def test_inverts_the_forward_model_at_every_intersection(self):
        # Forward model in mm, correction in grid coordinates: this is the affine-invariance claim.
        for row in range(19):
            for col in range(19):
                assert apply_parallax(*detected_grid(col, row), NADIR_GRID, K_TRUE) == pytest.approx(
                    (col, row), abs=1e-9
                )

    def test_moves_points_toward_the_nadir(self):
        fx, fy = apply_parallax(0.0, 0.0, NADIR_GRID, K_TRUE)
        assert math.hypot(fx - NADIR_GRID[0], fy - NADIR_GRID[1]) < math.hypot(*NADIR_GRID)

    def test_is_not_idempotent(self):
        once = apply_parallax(0.0, 0.0, NADIR_GRID, K_TRUE)
        assert apply_parallax(*once, NADIR_GRID, K_TRUE) != pytest.approx(once, abs=1e-6)


class TestParallaxParams:
    def test_round_trips_through_dict(self):
        p = ParallaxParams(9.0, 19.6, 0.99)
        assert ParallaxParams(**p.to_dict()) == p
        assert p.nadir == (9.0, 19.6)
