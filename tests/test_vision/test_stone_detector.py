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


class TestDedupVectorisationIsEquivalent:
    """dedup_detections' inner clash test is vectorised; the greedy scan is not.

    The rewrite is an optimisation, so it is pinned by a differential test against the
    original scalar implementation over randomised inputs — including the cases that
    make the grouping rules load-bearing (LED vs stone, LED vs other LED, bbox-less
    detections, and equal confidences, where the stable sort decides who wins).
    """

    @staticmethod
    def _reference_dedup(detections):
        """The pre-optimisation implementation, verbatim."""
        import math

        from katrain.vision.classes import STONE_CLASS_IDS

        kept = []
        for det in sorted(detections, key=lambda d: -d.confidence):
            d_side = (det.bbox[2] - det.bbox[0] + det.bbox[3] - det.bbox[1]) / 2.0
            is_dup = False
            for other in kept:
                if (det.class_id in STONE_CLASS_IDS) != (other.class_id in STONE_CLASS_IDS):
                    continue
                if det.class_id not in STONE_CLASS_IDS and det.class_id != other.class_id:
                    continue
                o_side = (other.bbox[2] - other.bbox[0] + other.bbox[3] - other.bbox[1]) / 2.0
                min_side = min(d_side, o_side)
                if min_side <= 0:
                    continue
                if math.hypot(det.x_center - other.x_center, det.y_center - other.y_center) < 0.5 * min_side:
                    is_dup = True
                    break
            if not is_dup:
                kept.append(det)
        return kept

    @staticmethod
    def _random_detections(rng, n):
        dets = []
        for _ in range(n):
            x = float(rng.integers(0, 400))
            y = float(rng.integers(0, 400))
            cls = int(rng.integers(0, 4))
            # Coarse confidence grid so ties happen often — that exercises sort stability.
            conf = float(rng.integers(1, 8)) / 10.0
            if rng.random() < 0.12:
                bbox = (0.0, 0.0, 0.0, 0.0)  # bbox-less: must never dedup
            else:
                side = float(rng.integers(10, 60))
                bbox = (x - side / 2, y - side / 2, x + side / 2, y + side / 2)
            dets.append(Detection(x_center=x, y_center=y, class_id=cls, confidence=conf, bbox=bbox))
        return dets

    @pytest.mark.parametrize("seed", range(40))
    def test_matches_reference_on_random_inputs(self, seed):
        from katrain.vision.stone_detector import dedup_detections

        rng = np.random.default_rng(seed)
        dets = self._random_detections(rng, int(rng.integers(0, 60)))

        got = dedup_detections(dets)
        want = self._reference_dedup(dets)

        # Identity comparison: the same Detection objects, in the same order.
        assert [id(d) for d in got] == [id(d) for d in want]

    @pytest.mark.parametrize("n", [0, 1, 2])
    def test_degenerate_sizes_match_reference(self, n):
        from katrain.vision.stone_detector import dedup_detections

        rng = np.random.default_rng(99)
        dets = self._random_detections(rng, n)
        assert [id(d) for d in dedup_detections(dets)] == [id(d) for d in self._reference_dedup(dets)]

    def test_clustered_stones_match_reference(self):
        """Random points are mostly far apart; this packs many detections into a few
        spots so the dedup radius actually fires and chains of suppression form."""
        from katrain.vision.stone_detector import dedup_detections

        rng = np.random.default_rng(5)
        dets = []
        for cx, cy in [(100, 100), (108, 104), (300, 300), (305, 298), (302, 306)]:
            for _ in range(8):
                x = cx + float(rng.integers(-6, 7))
                y = cy + float(rng.integers(-6, 7))
                side = float(rng.integers(20, 50))
                dets.append(
                    Detection(
                        x_center=x,
                        y_center=y,
                        class_id=int(rng.integers(0, 4)),
                        confidence=float(rng.integers(1, 6)) / 10.0,
                        bbox=(x - side / 2, y - side / 2, x + side / 2, y + side / 2),
                    )
                )
        assert [id(d) for d in dedup_detections(dets)] == [id(d) for d in self._reference_dedup(dets)]

    def test_input_list_is_not_mutated(self):
        from katrain.vision.stone_detector import dedup_detections

        rng = np.random.default_rng(3)
        dets = self._random_detections(rng, 20)
        snapshot = list(dets)
        dedup_detections(dets)
        assert dets == snapshot
