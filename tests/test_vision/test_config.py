from katrain.vision.config import BoardConfig, CameraConfig


class TestBoardConfig:
    def test_default_board_config(self):
        cfg = BoardConfig()
        assert cfg.grid_size == 19
        assert cfg.board_width_mm == 424.2
        assert cfg.board_length_mm == 454.5
        assert cfg.border_width_mm == 15.0
        assert cfg.border_length_mm == 15.0

    def test_grid_spacing(self):
        cfg = BoardConfig()
        assert abs(cfg.grid_spacing_w - 23.567) < 0.01
        assert abs(cfg.grid_spacing_l - 25.25) < 0.01

    def test_total_dimensions(self):
        cfg = BoardConfig()
        assert abs(cfg.total_width - 454.2) < 0.01
        assert abs(cfg.total_length - 484.5) < 0.01

    def test_custom_board_config(self):
        cfg = BoardConfig(
            grid_size=13, board_width_mm=294.0, board_length_mm=290.0, border_width_mm=23.0, border_length_mm=21.0
        )
        assert cfg.grid_size == 13
        assert cfg.board_width_mm == 294.0


class TestCameraConfig:
    def test_defaults(self):
        cam = CameraConfig()
        assert cam.camera_matrix is None
        assert cam.dist_coeffs is None
        assert cam.calibration_file is None

    def test_is_calibrated(self):
        cam = CameraConfig()
        assert cam.is_calibrated is False
