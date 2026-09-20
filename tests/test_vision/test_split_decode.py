"""Deterministic tests for the split-head host decode (no board / NPU needed).

Constructs synthetic raw conv tensors with a single known-active anchor and
asserts the decoded box / class / confidence.  Also checks robustness to RKNN
output reordering and the backend meta-routing.
"""

import numpy as np
import pytest

from katrain.vision.inference.split_decode import decode_split_heads, is_split_meta

NC = 4
REG_MAX = 16
STRIDES = [8, 16, 32]
IMGSZ = 64  # grids: stride8 -> 8x8, stride16 -> 4x4, stride32 -> 2x2


def _blank_outputs():
    """Six raw tensors with no active anchor (class logits all strongly negative)."""
    outs = []
    for s in STRIDES:
        g = IMGSZ // s
        box = np.zeros((1, 4 * REG_MAX, g, g), dtype=np.float32)  # uniform DFL
        cls = np.full((1, NC, g, g), -10.0, dtype=np.float32)  # sigmoid(-10) ~ 4.5e-5
        outs.append(box)
        outs.append(cls)
    return outs  # order: box_s8, cls_s8, box_s16, cls_s16, box_s32, cls_s32


def _activate(outs, level_idx, gy, gx, class_id, dist_bin=1):
    """Make one anchor a strong detection with ltrb distance ~= dist_bin (grid units)."""
    box = outs[level_idx * 2]
    cls = outs[level_idx * 2 + 1]
    # DFL: put softmax mass on `dist_bin` for all 4 sides -> distance ~= dist_bin.
    for side in range(4):
        box[0, side * REG_MAX + dist_bin, gy, gx] = 10.0
    cls[0, class_id, gy, gx] = 10.0  # sigmoid(10) ~ 0.99995


def test_single_detection_decodes_to_expected_box():
    outs = _blank_outputs()
    # stride-8 level (idx 0), grid cell (gy=2, gx=3), class 0 (black), dist ~1 grid unit.
    _activate(outs, level_idx=0, gy=2, gx=3, class_id=0, dist_bin=1)

    dets = decode_split_heads(
        outs,
        nc=NC,
        reg_max=REG_MAX,
        strides=STRIDES,
        confidence_threshold=0.25,
        iou_threshold=0.5,
        scale=1.0,
        x_off=0,
        y_off=0,  # identity letterbox -> model space == image space
    )

    assert len(dets) == 1
    d = dets[0]
    assert d.class_id == 0
    assert d.confidence > 0.99
    # anchor centre = (gx+0.5, gy+0.5)*stride = (3.5,2.5)*8 = (28, 20); dist ~1 grid = 8px each side
    assert d.x_center == pytest.approx(28.0, abs=1.0)
    assert d.y_center == pytest.approx(20.0, abs=1.0)
    x1, y1, x2, y2 = d.bbox
    assert x1 == pytest.approx(20.0, abs=1.0)
    assert y1 == pytest.approx(12.0, abs=1.0)
    assert x2 == pytest.approx(36.0, abs=1.0)
    assert y2 == pytest.approx(28.0, abs=1.0)


def test_class_id_and_stride_level_are_honoured():
    # stride-32 level (idx 2), cell (1,0), class 2 (led_red).
    outs = _blank_outputs()
    _activate(outs, level_idx=2, gy=1, gx=0, class_id=2, dist_bin=1)
    dets = decode_split_heads(
        outs,
        nc=NC,
        reg_max=REG_MAX,
        strides=STRIDES,
        confidence_threshold=0.25,
        iou_threshold=0.5,
        scale=1.0,
        x_off=0,
        y_off=0,
    )
    assert len(dets) == 1
    assert dets[0].class_id == 2
    # anchor centre = (0.5, 1.5)*32 = (16, 48)
    assert dets[0].x_center == pytest.approx(16.0, abs=2.0)
    assert dets[0].y_center == pytest.approx(48.0, abs=2.0)


def test_decode_is_robust_to_output_reordering():
    outs = _blank_outputs()
    _activate(outs, level_idx=0, gy=2, gx=3, class_id=1, dist_bin=1)
    shuffled = [outs[4], outs[1], outs[5], outs[0], outs[3], outs[2]]  # arbitrary permutation
    dets = decode_split_heads(
        shuffled,
        nc=NC,
        reg_max=REG_MAX,
        strides=STRIDES,
        confidence_threshold=0.25,
        iou_threshold=0.5,
        scale=1.0,
        x_off=0,
        y_off=0,
    )
    assert len(dets) == 1
    assert dets[0].class_id == 1
    assert dets[0].x_center == pytest.approx(28.0, abs=1.0)


def test_letterbox_inverse_maps_to_original_space():
    outs = _blank_outputs()
    _activate(outs, level_idx=0, gy=2, gx=3, class_id=0, dist_bin=1)
    # scale 0.5 with a 4px x-offset: orig = (model - off) / scale
    dets = decode_split_heads(
        outs,
        nc=NC,
        reg_max=REG_MAX,
        strides=STRIDES,
        confidence_threshold=0.25,
        iou_threshold=0.5,
        scale=0.5,
        x_off=4,
        y_off=0,
    )
    assert len(dets) == 1
    # model centre (28,20) -> ((28-4)/0.5, (20-0)/0.5) = (48, 40)
    assert dets[0].x_center == pytest.approx(48.0, abs=2.0)
    assert dets[0].y_center == pytest.approx(40.0, abs=2.0)


def test_no_active_anchor_returns_empty():
    dets = decode_split_heads(
        _blank_outputs(),
        nc=NC,
        reg_max=REG_MAX,
        strides=STRIDES,
        confidence_threshold=0.25,
        iou_threshold=0.5,
        scale=1.0,
        x_off=0,
        y_off=0,
    )
    assert dets == []


def test_missing_class_tensor_raises():
    outs = _blank_outputs()
    outs = outs[:1]  # only one box tensor, no matching class tensor
    with pytest.raises(ValueError):
        decode_split_heads(
            outs,
            nc=NC,
            reg_max=REG_MAX,
            strides=STRIDES,
            confidence_threshold=0.25,
            iou_threshold=0.5,
            scale=1.0,
            x_off=0,
            y_off=0,
        )


class TestIsSplitMeta:
    def test_onnx_split_format(self):
        assert is_split_meta({"format": "onnx_split"})

    def test_rknn_split_format(self):
        assert is_split_meta({"format": "rknn_split"})

    def test_decode_field(self):
        assert is_split_meta({"decode": "host_dfl_anchor_sigmoid_nms"})

    def test_legacy_single_output_is_not_split(self):
        assert not is_split_meta({"format": "rknn", "output_format": "yolo_v8_raw"})
        assert not is_split_meta({"format": "onnx"})


class TestRknnBackendRoutesSplit:
    """RknnBackend.detect must route split-meta models through the host decode."""

    def test_detect_uses_split_decode(self):
        from unittest.mock import MagicMock

        from katrain.vision.inference.rknn_backend import RknnBackend

        outs = _blank_outputs()
        _activate(outs, level_idx=0, gy=2, gx=3, class_id=0, dist_bin=1)

        backend = RknnBackend()
        backend._meta = {
            "format": "rknn_split",
            "imgsz": IMGSZ,
            "nc": NC,
            "reg_max": REG_MAX,
            "strides": STRIDES,
            "classes": ["black", "white", "led_red", "led_green"],
            "input_channel_order": "RGB",
        }
        backend._rknn = MagicMock()
        backend._rknn.inference.return_value = outs  # canned NPU outputs

        img = np.zeros((IMGSZ, IMGSZ, 3), dtype=np.uint8)  # identity letterbox
        dets = backend.detect(img, confidence_threshold=0.25)

        assert len(dets) == 1
        assert dets[0].class_id == 0
        assert dets[0].x_center == pytest.approx(28.0, abs=1.0)


class TestMaskBeforeDflIsEquivalent:
    """The decode thresholds BEFORE running DFL so it only decodes surviving anchors.

    That reorder is an optimisation, not a behaviour change, so it is pinned by a
    differential test against a reference that keeps the original order (decode every
    anchor, then mask).  If the two ever disagree the optimisation has changed results.

    NOT bit-identical, and deliberately not asserted as such: class ids and confidences
    match exactly, but box coordinates differ by ~1e-5 relative because numpy's pairwise
    summation blocks differently over an (A,4,16) array than over the masked (K,4,16)
    subset.  The tolerance below is 1e-3 px — four orders of magnitude tighter than any
    real regression (detection centres are rounded onto a ~55px grid downstream) and
    still far above the observed float32 noise.
    """

    COORD_TOL = 1e-3  # px

    @staticmethod
    def _reference_decode(outputs, *, nc, reg_max, strides, confidence_threshold, iou_threshold, scale, x_off, y_off):
        """The pre-optimisation order: DFL over ALL anchors, mask afterwards."""
        import cv2

        from katrain.vision.inference.split_decode import _identify, _make_anchors, _sigmoid, _softmax
        from katrain.vision.stone_detector import Detection

        grids, box_logits, cls_logits = _identify(outputs, nc, reg_max)
        anchors, stride_vec = _make_anchors(grids, sorted(strides))
        num_anchors = box_logits.shape[0]

        reg = box_logits.reshape(num_anchors, 4, reg_max).astype(np.float32)
        reg = _softmax(reg, axis=2)
        dist = (reg * np.arange(reg_max, dtype=np.float32)).sum(axis=2)

        s = stride_vec[:, 0]
        x1 = (anchors[:, 0] - dist[:, 0]) * s
        y1 = (anchors[:, 1] - dist[:, 1]) * s
        x2 = (anchors[:, 0] + dist[:, 2]) * s
        y2 = (anchors[:, 1] + dist[:, 3]) * s

        scores = _sigmoid(cls_logits.astype(np.float32))
        class_ids = scores.argmax(axis=1)
        confidences = scores.max(axis=1)

        mask = confidences >= confidence_threshold
        x1, y1, x2, y2 = x1[mask], y1[mask], x2[mask], y2[mask]
        class_ids, confidences = class_ids[mask], confidences[mask]
        if len(class_ids) == 0:
            return []

        tl_boxes = np.stack([x1, y1, x2 - x1, y2 - y1], axis=1)
        indices = cv2.dnn.NMSBoxes(
            bboxes=tl_boxes.tolist(),
            scores=confidences.tolist(),
            score_threshold=confidence_threshold,
            nms_threshold=iou_threshold,
        )
        if len(indices) == 0:
            return []
        out = []
        for idx in np.asarray(indices).flatten():
            ox1 = float((x1[idx] - x_off) / scale)
            oy1 = float((y1[idx] - y_off) / scale)
            ox2 = float((x2[idx] - x_off) / scale)
            oy2 = float((y2[idx] - y_off) / scale)
            out.append(
                Detection(
                    x_center=(ox1 + ox2) / 2.0,
                    y_center=(oy1 + oy2) / 2.0,
                    class_id=int(class_ids[idx]),
                    confidence=float(confidences[idx]),
                    bbox=(ox1, oy1, ox2, oy2),
                )
            )
        return out

    @pytest.mark.parametrize("seed", range(12))
    def test_matches_reference_on_random_logits(self, seed):
        rng = np.random.default_rng(seed)
        # Random logits across all three levels; the class bias keeps the survivor count
        # realistic (a handful out of ~340 anchors at imgsz 64) instead of "everything".
        outs = []
        for s in STRIDES:
            g = IMGSZ // s
            outs.append(rng.standard_normal((1, 4 * REG_MAX, g, g)).astype(np.float32) * 3.0)
            outs.append((rng.standard_normal((1, NC, g, g)).astype(np.float32) * 3.0 - 2.0))

        kwargs = dict(
            nc=NC,
            reg_max=REG_MAX,
            strides=STRIDES,
            confidence_threshold=0.35,
            iou_threshold=0.5,
            scale=0.6,
            x_off=7,
            y_off=3,
        )
        got = decode_split_heads(outs, **kwargs)
        want = self._reference_decode(outs, **kwargs)

        # Same detections, same order, same classes/confidences — exactly.
        assert len(got) == len(want)
        assert [d.class_id for d in got] == [d.class_id for d in want]
        assert [d.confidence for d in got] == [d.confidence for d in want]
        # Geometry to within float32 reduction noise (see class docstring).
        for g, w in zip(got, want):
            assert abs(g.x_center - w.x_center) < self.COORD_TOL
            assert abs(g.y_center - w.y_center) < self.COORD_TOL
            for got_edge, want_edge in zip(g.bbox, w.bbox):
                assert abs(got_edge - want_edge) < self.COORD_TOL


class TestAnchorCache:
    def test_repeated_calls_return_the_same_arrays(self):
        from katrain.vision.inference.split_decode import _make_anchors

        a1, s1 = _make_anchors([(8, 8), (4, 4), (2, 2)], [8, 16, 32])
        a2, s2 = _make_anchors([(8, 8), (4, 4), (2, 2)], [8, 16, 32])
        assert a1 is a2 and s1 is s2

    def test_cached_arrays_are_read_only(self):
        """Callers index (which copies); writing through the shared view would corrupt
        every later frame's decode."""
        from katrain.vision.inference.split_decode import _make_anchors

        anchors, stride_vec = _make_anchors([(4, 4)], [8])
        with pytest.raises(ValueError):
            anchors[0, 0] = 999.0
        with pytest.raises(ValueError):
            stride_vec[0, 0] = 999.0

    def test_different_geometry_gets_its_own_entry(self):
        from katrain.vision.inference.split_decode import _make_anchors

        a_small, _ = _make_anchors([(4, 4)], [8])
        a_big, _ = _make_anchors([(8, 8)], [8])
        assert a_small.shape == (16, 2)
        assert a_big.shape == (64, 2)
