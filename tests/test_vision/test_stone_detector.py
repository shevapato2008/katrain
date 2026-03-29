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


class TestStoneDetectorWithMockBackend:
    """Test StoneDetector delegates to InferenceBackend correctly."""

    def test_detect_delegates_to_backend(self):
        expected_detections = [
            Detection(x_center=20.0, y_center=30.0, class_id=0, confidence=0.95, bbox=(10.0, 20.0, 30.0, 40.0))
        ]
        mock_backend = MagicMock()
        mock_backend.detect.return_value = expected_detections

        with patch("katrain.vision.inference.create_backend", return_value=mock_backend):
            det = StoneDetector("dummy.pt", backend="onnx", confidence_threshold=0.5)
            img = np.zeros((400, 400, 3), dtype=np.uint8)
            results = det.detect(img)

        mock_backend.load.assert_called_once_with("dummy.pt")
        mock_backend.detect.assert_called_once_with(img, 0.5)
        assert results == expected_detections

    def test_backend_factory_called_with_name(self):
        mock_backend = MagicMock()

        with patch("katrain.vision.inference.create_backend", return_value=mock_backend) as mock_factory:
            StoneDetector("dummy.pt", backend="ultralytics")
            mock_factory.assert_called_once_with("ultralytics")

        with patch("katrain.vision.inference.create_backend", return_value=mock_backend) as mock_factory:
            StoneDetector("dummy.onnx", backend="onnx")
            mock_factory.assert_called_once_with("onnx")
