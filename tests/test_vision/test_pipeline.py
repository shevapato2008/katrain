import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from katrain.vision.pipeline import DetectionPipeline
from katrain.vision.config import BoardConfig
from katrain.vision.stone_detector import Detection
from katrain.vision.board_state import BLACK


class TestDetectionPipeline:
    def test_init(self):
        with patch("katrain.vision.pipeline.StoneDetector"):
            pipeline = DetectionPipeline(model_path="dummy.pt")
            assert pipeline.config.grid_size == 19

    def test_process_frame_motion_rejected_before_board_detection(self):
        """Motion filter runs on raw frame — BoardFinder should NOT be called."""
        with patch("katrain.vision.pipeline.StoneDetector"):
            pipeline = DetectionPipeline(model_path="dummy.pt")
            pipeline.motion_filter = MagicMock()
            pipeline.motion_filter.is_stable.return_value = False
            pipeline.board_finder = MagicMock()

            result = pipeline.process_frame(np.zeros((480, 640, 3), dtype=np.uint8))
            assert result is None
            pipeline.board_finder.find_focus.assert_not_called()  # Key assertion

    def test_process_frame_no_board(self):
        with patch("katrain.vision.pipeline.StoneDetector"):
            pipeline = DetectionPipeline(model_path="dummy.pt")
            pipeline.motion_filter = MagicMock()
            pipeline.motion_filter.is_stable.return_value = True
            pipeline.board_finder = MagicMock()
            pipeline.board_finder.find_focus.return_value = (None, False)

            result = pipeline.process_frame(np.zeros((480, 640, 3), dtype=np.uint8))
            assert result is None

    def test_process_frame_returns_board_and_move(self):
        with patch("katrain.vision.pipeline.StoneDetector") as mock_cls:
            cfg = BoardConfig()
            mock_detector = MagicMock()
            x_px = (cfg.border_width_mm + cfg.board_width_mm / 2) / cfg.total_width * 400
            y_px = (cfg.border_length_mm + cfg.board_length_mm / 2) / cfg.total_length * 400
            mock_detector.detect.return_value = [Detection(x_center=x_px, y_center=y_px, class_id=0, confidence=0.95)]
            mock_cls.return_value = mock_detector

            pipeline = DetectionPipeline(model_path="dummy.pt")
            pipeline.motion_filter = MagicMock()
            pipeline.motion_filter.is_stable.return_value = True
            pipeline.board_finder = MagicMock()
            fake_warped = np.zeros((400, 400, 3), dtype=np.uint8)
            pipeline.board_finder.find_focus.return_value = (fake_warped, True)

            result = pipeline.process_frame(np.zeros((480, 640, 3), dtype=np.uint8))
            assert result is not None
            assert result.board.shape == (19, 19)
            assert result.board[9][9] == BLACK
            assert result.warped is not None
            # confirmed_move is None until consistency check passes
