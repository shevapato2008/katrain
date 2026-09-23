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


def _rect(x, y, class_id, conf, w, h):
    return Detection(
        x_center=x, y_center=y, class_id=class_id, confidence=conf, bbox=(x - w / 2, y - h / 2, x + w / 2, y + h / 2)
    )


class TestShadowDuplicateDedup:
    """Side light makes the model box a stone together with its shadow a second time, ~half a cell off
    (RK3562 daylight game 2026-09-23). Real box geometry below comes from the deployed go4_s.rknn on that
    board; see superpowers/tracks/vision-optimizations/shadow-dedup/design.md."""

    # G5 black stone (frame warped_09) and its shadow box at the two positions the live log recorded
    G5 = Detection(x_center=360.33, y_center=792.29, class_id=0, confidence=0.50, bbox=(332.6, 761.8, 388.0, 822.8))

    @staticmethod
    def _g5_shadow(x, y, conf=0.45):
        return _rect(x, y, 0, conf, 49.9, 51.1)

    def test_shadow_box_of_a_stone_is_merged_into_it(self):
        from katrain.vision.stone_detector import dedup_detections

        for x, y in ((388.82, 775.63), (387.02, 776.69)):  # IoMin 0.373 / 0.411; centre dist > 0.5 * side
            out = dedup_detections([self.G5, self._g5_shadow(x, y)])
            assert out == [self.G5]

    def test_black_shadow_beside_a_white_stone_is_merged(self):
        from katrain.vision.stone_detector import dedup_detections

        c8 = Detection(
            x_center=141.32248363494872,
            y_center=627.0086608886718,
            class_id=1,
            confidence=0.6349,
            bbox=(110.30381927490234, 595.2922851562499, 172.3411479949951, 658.7250366210938),
        )
        shadow = Detection(
            x_center=173.78701915740965,
            y_center=609.3615966796875,
            class_id=0,
            confidence=0.2157,
            bbox=(151.50497589111328, 588.0772109985352, 196.06906242370604, 630.6459823608399),
        )  # IoMin 0.388, side ratio 1.44
        assert dedup_detections([c8, shadow]) == [c8]

    def test_the_closest_real_neighbours_on_the_board_are_kept(self):
        from katrain.vision.stone_detector import dedup_detections

        j2 = Detection(
            x_center=473.5685806274414,
            y_center=939.0665222167969,
            class_id=0,
            confidence=0.7155,
            bbox=(441.18038177490234, 907.70302734375, 505.95677947998047, 970.4300170898438),
        )
        j3 = Detection(
            x_center=463.5263305664062,
            y_center=893.9533630371093,
            class_id=0,
            confidence=0.6765,
            bbox=(433.25148925781247, 864.3791473388671, 493.80117187499997, 923.5275787353515),
        )  # IoMin 0.2325 — the highest overlap between two REAL stones in 2762 labelled pairs
        assert len(dedup_detections([j2, j3])) == 2

    def test_overlap_threshold_boundary(self):
        from katrain.vision.stone_detector import dedup_detections

        # Two 50 px squares dx apart: IoMin = (50 - dx) / 50, and dx > 25 keeps the centre rule out. dx = 36.5
        # gives 13.5 * 50 / 2500, which is exactly the double 0.27 -- so `>=` vs `>` is pinned, not approximated.
        at = dedup_detections([_rect(100, 100, 0, 0.9, 50, 50), _rect(136.5, 100, 0, 0.8, 50, 50)])
        below = dedup_detections([_rect(100, 100, 0, 0.9, 50, 50), _rect(137, 100, 0, 0.8, 50, 50)])  # 0.26
        assert len(at) == 1 and at[0].confidence == 0.9
        assert len(below) == 2

    def test_side_ratio_boundary(self):
        from katrain.vision.stone_detector import dedup_detections

        small = _rect(150, 100, 0, 0.8, 50, 50)  # centre 50 px from the big box's: the centre rule never fires
        at = dedup_detections([_rect(100, 100, 0, 0.9, 100, 100), small])  # side ratio exactly 2.0, IoMin 0.5
        above = dedup_detections([_rect(100, 100, 0, 0.9, 105, 105), small])  # 2.1, IoMin 0.55
        assert len(at) == 1
        assert len(above) == 2

    def test_big_box_does_not_swallow_neighbouring_stones_by_overlap(self):
        from katrain.vision.stone_detector import dedup_detections

        # A hand read as one big black box, 3.2x a stone, overlapping each stone by 100% of the stone. The stones
        # sit 30-40 px from its centre, outside the centre rule's 25 px (which is unchanged and still merges
        # anything closer); only the side-ratio guard keeps the overlap clause off them.
        hand = _rect(200, 200, 0, 0.9, 160, 160)
        stones = [_rect(170, 200, 1, 0.8, 50, 50), _rect(230, 200, 0, 0.7, 50, 50), _rect(200, 160, 1, 0.6, 50, 50)]
        assert len(dedup_detections([hand, *stones])) == 4

    def test_led_boxes_keep_the_centre_distance_rule(self):
        from katrain.vision.stone_detector import dedup_detections

        leds = [_rect(100, 100, 2, 0.9, 50, 50), _rect(136, 100, 2, 0.8, 50, 50)]  # IoMin 0.28, centre dist 36 > 25
        stones = [_rect(100, 100, 0, 0.9, 50, 50), _rect(136, 100, 0, 0.8, 50, 50)]  # identical geometry
        assert len(dedup_detections(leds)) == 2
        assert len(dedup_detections(stones)) == 1

    def test_overlapping_pair_two_grid_cells_apart_is_found(self):
        from katrain.vision.stone_detector import dedup_detections

        # dx = 32: IoMin 0.36. With the old grid cell (0.5 * 50 = 25 px) x=99 and x=131 fall in buckets
        # 3 and 5 — outside the 3x3 scan — so a cell that was not widened silently misses this pair.
        out = dedup_detections([_rect(99, 100, 0, 0.9, 50, 50), _rect(131, 100, 0, 0.8, 50, 50)])
        assert len(out) == 1

    def test_zero_area_box_never_merges_by_overlap(self):
        from katrain.vision.stone_detector import dedup_detections

        # Zero height, so no overlap ratio. Its mean side is still 25, so it DOES take part in the centre rule
        # (radius 12.5 px, unchanged): the partner sits 20 px away to keep that rule out of this test.
        flat = Detection(x_center=120, y_center=100, class_id=0, confidence=0.9, bbox=(95.0, 100.0, 145.0, 100.0))
        assert len(dedup_detections([flat, _rect(140, 100, 0, 0.8, 50, 50)])) == 2


class TestDedupVectorisationIsEquivalent:
    """dedup_detections' clash test runs over a spatial grid; this pins it against a scalar O(k^2) reference.

    The rewrite is an optimisation, so it is pinned by a differential test against the
    original scalar implementation over randomised inputs — including the cases that
    make the grouping rules load-bearing (LED vs stone, LED vs other LED, bbox-less
    detections, and equal confidences, where the stable sort decides who wins).
    """

    @staticmethod
    def _reference_dedup(detections):
        """Scalar reference of the CURRENT rule (centre distance, plus the stone-only overlap clause),
        written independently of the module's helpers."""
        import math

        from katrain.vision.classes import STONE_CLASS_IDS
        from katrain.vision.stone_detector import DEDUP_MAX_SIDE_RATIO, DEDUP_OVERLAP_MIN

        def overlap_of_smaller(a, b):
            area_a = (a[2] - a[0]) * (a[3] - a[1])
            area_b = (b[2] - b[0]) * (b[3] - b[1])
            if min(area_a, area_b) <= 0:
                return 0.0
            w = min(a[2], b[2]) - max(a[0], b[0])
            h = min(a[3], b[3]) - max(a[1], b[1])
            return max(0.0, w) * max(0.0, h) / min(area_a, area_b)

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
                if (
                    det.class_id in STONE_CLASS_IDS
                    and max(d_side, o_side) <= DEDUP_MAX_SIDE_RATIO * min_side
                    and overlap_of_smaller(det.bbox, other.bbox) >= DEDUP_OVERLAP_MIN
                ):
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

    @pytest.mark.parametrize("off_centre", [0, 40])
    def test_overlap_clause_across_grid_cells_matches_reference(self, off_centre):
        """Pairs 26-36 px apart with ~50 px boxes: only the overlap clause can merge them (the centre-distance
        radius is ~25 px), and with a grid cell sized for that radius many land two cells apart -- outside the
        3x3 scan. off_centre moves x_center/y_center up to 40 px away from the bbox midpoint (every backend
        emits the midpoint, but Detection does not enforce it): the grid must stay exact regardless."""
        from katrain.vision.stone_detector import dedup_detections

        rng = np.random.default_rng(11)
        dets = []
        for _ in range(40):
            x = float(rng.integers(0, 600))
            y = float(rng.integers(0, 600))
            for dx, dy in ((0.0, 0.0), (float(rng.integers(26, 37)), float(rng.integers(-4, 5)))):
                side = float(rng.integers(46, 55))
                mx, my = x + dx, y + dy  # bbox midpoint
                ox = float(rng.integers(-off_centre, off_centre + 1))
                oy = float(rng.integers(-off_centre, off_centre + 1))
                dets.append(
                    Detection(
                        x_center=mx + ox,
                        y_center=my + oy,
                        class_id=int(rng.integers(0, 2)),
                        confidence=float(rng.integers(1, 9)) / 10.0,
                        bbox=(mx - side / 2, my - side / 2, mx + side / 2, my + side / 2),
                    )
                )
        assert [id(d) for d in dedup_detections(dets)] == [id(d) for d in self._reference_dedup(dets)]

    def test_outliers_and_non_finite_centres_match_reference(self):
        """Boxes that stay out of the grid and are checked linearly: a hand read as one big box with a stone
        under it (inside the centre radius), a second hand box overlapping another, a 1056 x 20 bar, and
        centres at inf / NaN (a backend overflow must not raise). The result must equal the scalar scan."""
        from katrain.vision.stone_detector import dedup_detections

        rng = np.random.default_rng(12)
        dets = []
        for _ in range(60):
            x, y = float(rng.integers(0, 1000)), float(rng.integers(0, 1000))
            side = float(rng.integers(46, 60))
            dets.append(_rect(x, y, int(rng.integers(0, 2)), float(rng.integers(1, 9)) / 10.0, side, side))
        for hx, hy in ((200.0, 200.0), (600.0, 500.0)):
            dets.append(_rect(hx, hy, 0, 0.95, 160, 160))
            dets.append(_rect(hx + 8, hy - 6, 1, 0.5, 50, 50))
        dets.append(_rect(612.0, 520.0, 0, 0.9, 170, 150))
        dets.append(_rect(528.0, 800.0, 0, 0.97, 1056, 20))
        dets.append(Detection(float("inf"), 300.0, 0, 0.6, (280.0, 280.0, 330.0, 330.0)))
        dets.append(Detection(float("nan"), 700.0, 1, 0.6, (680.0, 680.0, 730.0, 730.0)))
        dets.append(Detection(300.0, float("nan"), 1, 0.6, (280.0, 280.0, 330.0, 330.0)))
        assert [id(d) for d in dedup_detections(dets)] == [id(d) for d in self._reference_dedup(dets)]

    def test_one_huge_box_does_not_widen_the_grid_for_everyone(self, monkeypatch):
        """The grid exists for speed (the O(k^2) scan took 86 ms at 213 stones on the RK3562). One oversized
        box must not size it for every other box: count overlap evaluations with and without a 1056 x 20 bar."""
        import katrain.vision.stone_detector as sd

        rng = np.random.default_rng(3)
        stones = [
            _rect(53 + c * 52.72, 53 + r * 52.72, int(rng.integers(0, 2)), float(rng.uniform(0.3, 0.9)), 56, 56)
            for r in range(19)
            for c in range(19)
            if rng.random() < 0.6
        ]
        calls = []
        real = sd._overlap_of_smaller
        monkeypatch.setattr(sd, "_overlap_of_smaller", lambda a, b: calls.append(1) or real(a, b))
        sd.dedup_detections(stones)
        without_bar = len(calls)
        calls.clear()
        sd.dedup_detections(stones + [_rect(528.0, 528.0, 0, 0.99, 1056, 20)])
        # the bar itself is checked against every stone once; everything else must stay local
        assert len(calls) <= without_bar + len(stones)

    def test_input_list_is_not_mutated(self):
        from katrain.vision.stone_detector import dedup_detections

        rng = np.random.default_rng(3)
        dets = self._random_detections(rng, 20)
        snapshot = list(dets)
        dedup_detections(dets)
        assert dets == snapshot
