"""Parallax correction inside BoardStateExtractor (prd P1-1 acceptance 2, 3; design §2.3)."""

import math

import numpy as np
import pytest

from katrain.vision.board_state import EMPTY, STICKY_RADIUS, SUSTAIN_RADIUS, BoardStateExtractor
from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig
from katrain.vision.coordinates import apply_parallax
from katrain.vision.parallax import ParallaxParams
from katrain.vision.stone_detector import Detection
from tests.test_vision.board_state_corpus import IMG, grid_to_px
from tests.test_vision.parallax_synth import K_TRUE, NADIR_GRID, detected_grid

CFG = BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS)
ON = ParallaxParams(NADIR_GRID[0], NADIR_GRID[1], K_TRUE)


def _det(fx, fy, cls=0, conf=0.9):
    x, y = grid_to_px(CFG, fx, fy)
    return Detection(x_center=x, y_center=y, class_id=cls, confidence=conf)


def _placed(parallax, det, occupancy):
    board = BoardStateExtractor(CFG, parallax=parallax).detections_to_board([det], IMG, IMG, occupancy_aware=occupancy)
    cells = list(zip(*np.nonzero(board)))
    return tuple(int(v) for v in cells[0]) if cells else None


class TestSanity361:
    def test_forward_model_positions_land_home_with_and_without_correction(self):
        # Sanity only: the largest offset is 0.204 cell (< half a cell), so this passes WITHOUT
        # the correction too -- it cannot show the correction works. TestFarRowsDisplacedOutward can.
        for parallax in (None, ON):
            ex = BoardStateExtractor(CFG, parallax=parallax)
            wrong = [
                (r, c)
                for r in range(19)
                for c in range(19)
                if ex._grid_cell(_det(*detected_grid(c, r)), IMG, IMG) != (r, c)
            ]
            assert wrong == [], (parallax, wrong)


class TestFarRowsDisplacedOutward:
    """The discriminating form of prd P1-1 acceptance 2: stones in rows 1-5 (the far side, next to the
    outermost row), each placed 0.35 cell further away from the camera. Without the correction they land
    on the neighbouring intersection (63 of 95 at design time); with it, none do. Both halves run every
    time, so this test proves on its own that the correction is what makes the difference.

    Row 0 is excluded on purpose: there the outward stone's RAW position rounds off-board, and the
    margin-DROP rule (either raw or corrected off-board -> drop) keeps dropping it -- the known cost
    pinned by test_outermost_row_keeps_todays_tolerance."""

    ROWS = range(1, 6)

    def _wrong(self, parallax, occupancy):
        return [
            (r, c)
            for r in self.ROWS
            for c in range(19)
            if _placed(parallax, _det(*detected_grid(c, r, outward_cells=0.35)), occupancy) != (r, c)
        ]

    @pytest.mark.parametrize("occupancy", [False, True])
    def test_without_correction_they_land_on_a_neighbour(self, occupancy):
        assert len(self._wrong(None, occupancy)) >= 30  # 63 of 95 at design time

    @pytest.mark.parametrize("occupancy", [False, True])
    def test_with_correction_all_land_home(self, occupancy):
        assert self._wrong(ON, occupancy) == []

    def test_outermost_row_keeps_todays_tolerance(self):
        # Known cost of the margin-DROP rule (design §7.1): a row-0 stone placed 0.3 cell outward has its
        # raw position past the drop line, so it is dropped with and without the correction alike.
        for parallax in (None, ON):
            assert _placed(parallax, _det(*detected_grid(9, 0, outward_cells=0.30)), occupancy=False) is None


# Points just outside the far edge / side edges that are dropped today and that the correction alone
# would pull back on-board (design §2.3, prd P1-1 acceptance 3 revision).
BAND = (
    [(fx, -0.6) for fx in (0.0, 4.0, 9.0, 14.0, 18.0)]
    + [(-0.55, fy) for fy in (2.0, 9.0, 16.0)]
    + [(18.55, fy) for fy in (2.0, 9.0, 16.0)]
)


class TestMarginDropSurvivesCorrection:
    @pytest.mark.parametrize("fx,fy", BAND)
    def test_band_point_is_still_dropped(self, fx, fy):
        cfx, cfy = apply_parallax(fx, fy, ON.nadir, ON.k)
        # Precondition: the correction by itself WOULD round this on-board; otherwise the test certifies nothing.
        assert 0 <= round(cfx) <= 18 and 0 <= round(cfy) <= 18
        ex = BoardStateExtractor(CFG, parallax=ON)
        assert ex._grid_cell(_det(fx, fy), IMG, IMG) is None
        for occupancy in (False, True):
            assert _placed(ON, _det(fx, fy), occupancy) is None

    def test_point_pushed_off_board_by_the_correction_is_dropped(self):
        # The other half of "either": on the camera side the correction pushes outward (toward a nadir beyond row 18).
        fx, fy = 9.0, 18.495
        assert round(fy) == 18
        assert round(apply_parallax(fx, fy, ON.nadir, ON.k)[1]) == 19
        assert BoardStateExtractor(CFG, parallax=ON)._grid_cell(_det(fx, fy), IMG, IMG) is None


class TestOffBoardDetectionsBehaveAsUncorrected:
    """codex adversarial review 2026-09-22 [high]: a margin object that the correction would pull within
    reach of an edge stone must not keep that stone alive after the user removes it -- neither through
    presence sustain (any class) nor through sticky assignment (same colour). Baseline drops the stone at
    once; so must the corrected extractor, over many frames."""

    RAW = (9.0, -0.8)  # just outside the far edge, beside an edge stone at (0, 9)

    def _after_removal(self, parallax, cls, frames=20):
        ex = BoardStateExtractor(CFG, parallax=parallax)
        prev = np.zeros((19, 19), dtype=int)
        prev[0][9] = 1  # a black edge stone; the user has just removed it, only the margin object remains
        for _ in range(frames):
            prev = ex.detections_to_board(
                [_det(*self.RAW, cls=cls)], IMG, IMG, occupancy_aware=True, prev_board=prev, sticky_board=prev
            )
        return int(prev[0][9])

    def test_precondition_the_correction_alone_would_reach_the_stone(self):
        cfx, cfy = apply_parallax(*self.RAW, ON.nadir, ON.k)
        corrected, raw = math.hypot(cfx - 9, cfy), math.hypot(self.RAW[0] - 9, self.RAW[1])
        assert corrected <= SUSTAIN_RADIUS < raw
        assert corrected <= STICKY_RADIUS < raw

    @pytest.mark.parametrize("cls", [0, 2], ids=["black-stone-sticky", "led-class-sustain"])
    def test_removed_edge_stone_is_not_kept_alive(self, cls):
        for parallax in (None, ON):
            assert self._after_removal(parallax, cls) == EMPTY, parallax


class TestSingleApplication:
    def test_detection_points_are_corrected_exactly_once(self):
        fx_raw, fy_raw = detected_grid(3, 1)
        ((fy, fx, _, _),) = BoardStateExtractor(CFG, parallax=ON).detection_points([_det(fx_raw, fy_raw)], IMG, IMG)
        once = apply_parallax(fx_raw, fy_raw, ON.nadir, ON.k)
        twice = apply_parallax(*once, ON.nadir, ON.k)
        assert (fx, fy) == pytest.approx(once, abs=1e-9)
        assert (fx, fy) != pytest.approx(twice, abs=1e-6)

    def test_parallax_points_carry_raw_and_corrected(self):
        fx_raw, fy_raw = detected_grid(3, 1)
        ex = BoardStateExtractor(CFG, parallax=ON)
        ((pfy_raw, pfx_raw, pfy, pfx, cls, conf),) = ex.parallax_points([_det(fx_raw, fy_raw, 1, 0.7)], IMG, IMG)
        assert (pfx_raw, pfy_raw) == pytest.approx((fx_raw, fy_raw), abs=1e-9)
        assert (pfx, pfy) == pytest.approx((3, 1), abs=1e-9)
        assert (cls, conf) == (1, 0.7)

    def test_parallax_points_raw_equals_corrected_when_off(self):
        ((fy_raw, fx_raw, fy, fx, _, _),) = BoardStateExtractor(CFG).parallax_points([_det(3.2, 1.1)], IMG, IMG)
        assert (fx_raw, fy_raw) == (fx, fy)
