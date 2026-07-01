"""Train/serve geometry consistency: the geometry-lock inference warp must add the same 1-cell
margin the training labeler uses, and BoardConfig's border must match, so a stone warped at
intersection (r,c) maps back to (c,r)."""

import numpy as np

from katrain.vision.config import BoardConfig, DEFAULT_MARGIN_CELLS
from katrain.vision.coordinates import physical_to_grid, pixel_to_physical
from katrain.vision.warp import margin_px_for, warp_with_margin


class TestMarginConfig:
    def test_default_config_has_zero_border(self):
        cfg = BoardConfig()
        assert cfg.border_width_mm == 0.0 and cfg.border_length_mm == 0.0  # board_finder paths unchanged

    def test_margin_cells_derives_one_cell_border(self):
        cfg = BoardConfig(margin_cells=1.0)
        assert abs(cfg.border_width_mm - cfg.board_width_mm / 18) < 1e-9
        assert abs(cfg.border_length_mm - cfg.board_length_mm / 18) < 1e-9


class TestWarpHelper:
    def test_margin_px_for_one_cell(self):
        assert margin_px_for(950, 1.0, 19) == round(949 / 18)  # 53

    def test_zero_margin_returns_out_size(self):
        out = warp_with_margin(np.zeros((40, 40, 3), np.uint8), np.eye(3), out_size=40, margin_cells=0.0)
        assert out.shape[:2] == (40, 40)

    def test_one_cell_margin_grows_canvas(self):
        out = warp_with_margin(np.zeros((100, 100, 3), np.uint8), np.eye(3), out_size=90, margin_cells=1.0)
        pad = margin_px_for(90, 1.0, 19)
        assert out.shape[:2] == (90 + 2 * pad, 90 + 2 * pad)


class TestTrainServeConsistency:
    def test_margined_intersection_pixels_map_back_to_grid(self):
        out_size, grid = 950, 19
        pad = margin_px_for(out_size, DEFAULT_MARGIN_CELLS, grid)
        canvas = out_size + 2 * pad
        cfg = BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS)
        xs = np.linspace(0, out_size - 1, grid)
        for r, c in [(0, 0), (0, 18), (18, 0), (18, 18), (9, 9), (3, 15), (15, 3), (1, 17)]:
            px, py = xs[c] + pad, xs[r] + pad  # intersection (r,c) in the margined warp
            x_mm, y_mm = pixel_to_physical(px, py, canvas, canvas, cfg)
            assert physical_to_grid(x_mm, y_mm, cfg) == (c, r)


class TestWorkerInprocessWiring:
    def _adapter(self, geometry):
        # Bypass heavy __init__ (camera/detector/board_finder); exercise only warp + extractor logic.
        from katrain.vision.board_state import BoardStateExtractor
        from katrain.vision.worker_inprocess import InProcessAdapter

        a = InProcessAdapter.__new__(InProcessAdapter)
        a._geometry = geometry
        a._require_geometry = False
        a._config = {}
        a._board_finder = None
        a._state_extractor = BoardStateExtractor(BoardConfig())
        a._state_extractor_locked = BoardStateExtractor(BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS))
        return a

    def test_geometry_warp_is_margined(self):
        class Geo:
            M = np.eye(3)
            out_size = 90

        a = self._adapter(Geo())
        warped, found = a._warp_frame(np.zeros((120, 120, 3), np.uint8))
        pad = margin_px_for(90, DEFAULT_MARGIN_CELLS, 19)
        assert found and warped.shape[:2] == (90 + 2 * pad, 90 + 2 * pad)

    def test_active_extractor_uses_margin_when_locked(self):
        class Geo:
            M = np.eye(3)
            out_size = 90

        locked = self._adapter(Geo())
        assert locked._active_extractor().config.border_width_mm > 0
        unlocked = self._adapter(None)
        assert unlocked._active_extractor().config.border_width_mm == 0.0


from katrain.vision.warp import adjust_M_for_resolution


class TestAdjustMForResolution:
    def test_identity_when_source_none(self):
        M = np.array([[2.0, 0.0, 1.0], [0.0, 3.0, 4.0], [0.0, 0.0, 1.0]])
        assert np.allclose(adjust_M_for_resolution(M, None, (640, 480)), M)

    def test_identity_when_resolution_matches(self):
        M = np.array([[2.0, 0.0, 1.0], [0.0, 3.0, 4.0], [0.0, 0.0, 1.0]])
        assert np.allclose(adjust_M_for_resolution(M, (1280, 720), (1280, 720)), M)

    def test_scales_half_resolution_frame_to_same_canonical(self):
        # M calibrated at 1280x720; a live frame at 640x360 (half) — pixel (px,py) there
        # corresponds to source (2px,2py). M_eff(frame_pt) must equal M(source_pt).
        M = np.array([[1.3, 0.1, 5.0], [0.05, 1.2, 7.0], [0.0, 0.0, 1.0]])
        M_eff = adjust_M_for_resolution(M, (1280, 720), (640, 360))
        for px, py in [(0, 0), (100, 50), (639, 359)]:
            src = M @ np.array([2 * px, 2 * py, 1.0])
            frm = M_eff @ np.array([px, py, 1.0])
            assert np.allclose(src / src[2], frm / frm[2])
