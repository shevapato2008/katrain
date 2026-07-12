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
