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
        mock_backend.detect.assert_called_once_with(img, 0.5, None)  # iou_threshold defaults to None
        assert results == expected_detections

    def test_backend_factory_called_with_name(self):
        mock_backend = MagicMock()

        with patch("katrain.vision.inference.create_backend", return_value=mock_backend) as mock_factory:
            StoneDetector("dummy.pt", backend="ultralytics")
            mock_factory.assert_called_once_with("ultralytics")

        with patch("katrain.vision.inference.create_backend", return_value=mock_backend) as mock_factory:
            StoneDetector("dummy.onnx", backend="onnx")
            mock_factory.assert_called_once_with("onnx")


def _boxed(x, y, class_id, conf, side=30.0):
    return Detection(
        x_center=x,
        y_center=y,
        class_id=class_id,
        confidence=conf,
        bbox=(x - side / 2, y - side / 2, x + side / 2, y + side / 2),
    )


class TestDedupDetections:
    """Same-object duplicate suppression after NMS (size-variant boxes on one stone can
    have mutual IoU below the NMS threshold, so NMS alone leaves several boxes/stone)."""

    def test_nested_boxes_on_one_stone_keep_highest_confidence(self):
        from katrain.vision.stone_detector import dedup_detections

        dets = [
            _boxed(100, 100, 0, 0.55, side=40),
            _boxed(103, 102, 0, 0.75, side=28),
            _boxed(98, 99, 0, 0.30, side=34),
        ]
        out = dedup_detections(dets)
        assert len(out) == 1
        assert out[0].confidence == 0.75

    def test_color_confused_duplicate_collapses_to_stronger(self):
        # One stone read as both black and white: the weaker box must not survive to
        # spill onto a neighbouring empty point and manufacture a phantom stone.
        from katrain.vision.stone_detector import dedup_detections

        dets = [_boxed(100, 100, 0, 0.8), _boxed(102, 101, 1, 0.65)]
        out = dedup_detections(dets)
        assert len(out) == 1
        assert out[0].class_id == 0

    def test_adjacent_stones_are_not_merged(self):
        from katrain.vision.stone_detector import dedup_detections

        # Neighbouring intersections sit ~one box-width apart — well past the dedup radius.
        dets = [_boxed(100, 100, 0, 0.9), _boxed(132, 100, 1, 0.85)]
        assert len(dedup_detections(dets)) == 2

    def test_led_halo_never_suppresses_the_stone_under_it(self):
        from katrain.vision.stone_detector import dedup_detections

        dets = [_boxed(100, 100, 2, 0.9), _boxed(101, 101, 0, 0.6)]  # led_red over black
        assert len(dedup_detections(dets)) == 2

    def test_detections_without_bbox_are_never_deduped(self):
        from katrain.vision.stone_detector import dedup_detections

        dets = [
            Detection(x_center=100, y_center=100, class_id=0, confidence=0.9),
            Detection(x_center=100, y_center=100, class_id=0, confidence=0.5),
        ]
        assert len(dedup_detections(dets)) == 2

    def test_stone_detector_detect_applies_dedup(self):
        backend_out = [_boxed(100, 100, 0, 0.8), _boxed(102, 101, 0, 0.6)]
        mock_backend = MagicMock()
        mock_backend.detect.return_value = backend_out

        with patch("katrain.vision.inference.create_backend", return_value=mock_backend):
            det = StoneDetector("dummy.pt", backend="onnx", confidence_threshold=0.5)
            results = det.detect(np.zeros((400, 400, 3), dtype=np.uint8))

        assert len(results) == 1
        assert results[0].confidence == 0.8
