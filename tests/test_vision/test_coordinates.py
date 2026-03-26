import pytest
from katrain.vision.config import BoardConfig
from katrain.vision.coordinates import pixel_to_physical, physical_to_grid, grid_to_physical


@pytest.fixture
def cfg():
    return BoardConfig()


class TestPixelToPhysical:
    def test_origin(self, cfg):
        x_mm, y_mm = pixel_to_physical(0, 0, img_w=640, img_h=480, config=cfg)
        assert x_mm == 0.0
        assert y_mm == 0.0

    def test_center(self, cfg):
        x_mm, y_mm = pixel_to_physical(320, 240, img_w=640, img_h=480, config=cfg)
        assert abs(x_mm - cfg.total_width / 2) < 0.01
        assert abs(y_mm - cfg.total_length / 2) < 0.01

    def test_bottom_right(self, cfg):
        x_mm, y_mm = pixel_to_physical(640, 480, img_w=640, img_h=480, config=cfg)
        assert abs(x_mm - cfg.total_width) < 0.01
        assert abs(y_mm - cfg.total_length) < 0.01


class TestPhysicalToGrid:
    def test_top_left_intersection(self, cfg):
        pos_x, pos_y = physical_to_grid(cfg.border_width_mm, cfg.border_length_mm, config=cfg)
        assert pos_x == 0
        assert pos_y == 0

    def test_bottom_right_intersection(self, cfg):
        x = cfg.border_width_mm + cfg.board_width_mm
        y = cfg.border_length_mm + cfg.board_length_mm
        pos_x, pos_y = physical_to_grid(x, y, config=cfg)
        assert pos_x == 18
        assert pos_y == 18

    def test_center_intersection(self, cfg):
        x = cfg.border_width_mm + cfg.board_width_mm / 2
        y = cfg.border_length_mm + cfg.board_length_mm / 2
        pos_x, pos_y = physical_to_grid(x, y, config=cfg)
        assert pos_x == 9
        assert pos_y == 9

    def test_clamps_to_bounds(self, cfg):
        pos_x, pos_y = physical_to_grid(0, 0, config=cfg)
        assert pos_x == 0
        assert pos_y == 0
        pos_x, pos_y = physical_to_grid(9999, 9999, config=cfg)
        assert pos_x == 18
        assert pos_y == 18


class TestGridToPhysical:
    def test_origin(self, cfg):
        x_mm, y_mm = grid_to_physical(0, 0, config=cfg)
        assert abs(x_mm - cfg.border_width_mm) < 0.01
        assert abs(y_mm - cfg.border_length_mm) < 0.01

    def test_last(self, cfg):
        x_mm, y_mm = grid_to_physical(18, 18, config=cfg)
        expected_x = cfg.border_width_mm + cfg.board_width_mm
        expected_y = cfg.border_length_mm + cfg.board_length_mm
        assert abs(x_mm - expected_x) < 0.01
        assert abs(y_mm - expected_y) < 0.01

    def test_roundtrip(self, cfg):
        """physical_to_grid(grid_to_physical(x,y)) == (x,y) for all grid positions."""
        for gx in range(19):
            for gy in range(19):
                x_mm, y_mm = grid_to_physical(gx, gy, config=cfg)
                rx, ry = physical_to_grid(x_mm, y_mm, config=cfg)
                assert rx == gx
                assert ry == gy
