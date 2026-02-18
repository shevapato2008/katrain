import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from katrain.vision.stone_detector import StoneDetector, Detection


class TestDetection:
    def test_detection_fields(self):
        d = Detection(x_center=100.0, y_center=200.0, class_id=0, confidence=0.95)
        assert d.x_center == 100.0
        assert d.class_id == 0

    def test_class_name(self):
        assert Detection(x_center=0, y_center=0, class_id=0, confidence=0.9).class_name == "black"
        assert Detection(x_center=0, y_center=0, class_id=1, confidence=0.9).class_name == "white"

    def test_bbox_default(self):
        d = Detection(x_center=0, y_center=0, class_id=0, confidence=0.9)
        assert d.bbox == (0.0, 0.0, 0.0, 0.0)

    def test_bbox_explicit(self):
        d = Detection(x_center=20.0, y_center=30.0, class_id=1, confidence=0.8, bbox=(10.0, 20.0, 30.0, 40.0))
        assert d.bbox == (10.0, 20.0, 30.0, 40.0)


class TestStoneDetectorDetect:
    """Test YOLO result parsing with a mock model (no real .pt file needed)."""

    def test_parses_yolo_results(self):
        with patch("katrain.vision.stone_detector.YOLO") as mock_yolo_cls:
            mock_box = MagicMock()
            mock_box.xyxy = [MagicMock(tolist=lambda: [10.0, 20.0, 30.0, 40.0])]
            mock_box.cls = [MagicMock(__int__=lambda s: 0, __index__=lambda s: 0)]
            mock_box.conf = [MagicMock(__float__=lambda s: 0.95)]
            mock_result = MagicMock()
            mock_result.boxes = [mock_box]
            mock_model = MagicMock()
            mock_model.return_value = [mock_result]
            mock_yolo_cls.return_value = mock_model

            det = StoneDetector("dummy.pt", confidence_threshold=0.5)
            img = np.zeros((400, 400, 3), dtype=np.uint8)
            results = det.detect(img)
            assert len(results) == 1
            assert results[0].x_center == 20.0  # (10+30)/2
            assert results[0].class_id == 0
            assert results[0].bbox == (10.0, 20.0, 30.0, 40.0)

    def test_filters_low_confidence(self):
        with patch("katrain.vision.stone_detector.YOLO") as mock_yolo_cls:
            mock_box = MagicMock()
            mock_box.xyxy = [MagicMock(tolist=lambda: [10.0, 20.0, 30.0, 40.0])]
            mock_box.cls = [MagicMock(__int__=lambda s: 0, __index__=lambda s: 0)]
            mock_box.conf = [MagicMock(__float__=lambda s: 0.3)]  # below threshold
            mock_result = MagicMock()
            mock_result.boxes = [mock_box]
            mock_model = MagicMock()
            mock_model.return_value = [mock_result]
            mock_yolo_cls.return_value = mock_model

            det = StoneDetector("dummy.pt", confidence_threshold=0.5)
            results = det.detect(np.zeros((400, 400, 3), dtype=np.uint8))
            assert len(results) == 0
