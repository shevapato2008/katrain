"""Host-side decode for the RKNN-friendly split-head YOLO v8/v11 export.

The standard ultralytics export concatenates box pixel coords (0-640) and class
scores (0-1) into one output tensor.  Per-tensor INT8 quantization then scales
the whole tensor by the box range (~638/127 ≈ 5/step), rounding every class
score ≤1 to exactly 0 — the NPU returns zero detections.  See
``superpowers/tracks/yolo-rknn-deploy/`` for the full write-up.

The split-head export (``export_onnx_split.py``) emits the raw per-scale conv
tensors *before* DFL decode / anchor add / sigmoid / concat: per stride a
box-DFL logits tensor ``(1, 4*reg_max, H, W)`` and a class-logits tensor
``(1, nc, H, W)``.  Each has a single value range, so INT8 quantizes each
cleanly.  This module performs the decode those raw tensors defer to the host:
DFL softmax -> ltrb distance -> anchor+stride -> xyxy -> sigmoid -> agnostic NMS,
then maps boxes back to the original image via the letterbox transform.

The decode is identical whether the raw tensors come from RKNN or ONNX Runtime,
so both backends share this one function.
"""

from __future__ import annotations

import cv2
import numpy as np

from katrain.vision.stone_detector import Detection


def _softmax(x: np.ndarray, axis: int) -> np.ndarray:
    x = x - x.max(axis=axis, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=axis, keepdims=True)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


def _make_anchors(grids: list[tuple[int, int]], strides_sorted: list[int]) -> tuple[np.ndarray, np.ndarray]:
    """Anchor-point centres (row-major y*W+x, +0.5 offset) and per-anchor stride."""
    points, stride_vec = [], []
    for (H, W), s in zip(grids, strides_sorted):
        gy, gx = np.meshgrid(np.arange(H), np.arange(W), indexing="ij")
        ax = (gx.ravel() + 0.5).astype(np.float32)
        ay = (gy.ravel() + 0.5).astype(np.float32)
        points.append(np.stack([ax, ay], axis=1))  # (H*W, 2)
        stride_vec.append(np.full((H * W, 1), s, dtype=np.float32))
    return np.concatenate(points, 0), np.concatenate(stride_vec, 0)


def _identify(outputs: list[np.ndarray], nc: int, reg_max: int) -> tuple[list, np.ndarray, np.ndarray]:
    """Group raw outputs by spatial size (robust to RKNN output reordering).

    Within a spatial size the box tensor has ``4*reg_max`` channels and the
    class tensor has ``nc`` channels.  Grids are ordered largest-first, which
    aligns with ascending stride (stride 8 -> 16 -> 32).

    Returns ``(grids, box_logits (A, 4*reg_max), class_logits (A, nc))``.
    """
    box_ch = 4 * reg_max
    by_hw: dict[tuple[int, int], dict[int, np.ndarray]] = {}
    for o in outputs:
        o = np.asarray(o)
        o = o[0] if o.ndim == 4 else o  # -> (C, H, W)
        C, H, W = o.shape
        by_hw.setdefault((H, W), {})[C] = o.reshape(C, H * W)

    order = sorted(by_hw.keys(), key=lambda hw: -hw[0] * hw[1])  # stride 8 first
    grids, boxes, classes = [], [], []
    for hw in order:
        d = by_hw[hw]
        if box_ch not in d or nc not in d:
            raise ValueError(
                f"split-head decode: grid {hw} missing box({box_ch}ch) or class({nc}ch) "
                f"tensor; got channels {sorted(d)}"
            )
        grids.append(hw)
        boxes.append(d[box_ch].T)  # (H*W, 4*reg_max)
        classes.append(d[nc].T)  # (H*W, nc)
    return grids, np.concatenate(boxes, 0), np.concatenate(classes, 0)


def decode_split_heads(
    outputs: list[np.ndarray],
    *,
    nc: int,
    reg_max: int,
    strides: list[int],
    confidence_threshold: float,
    iou_threshold: float,
    scale: float,
    x_off: int,
    y_off: int,
) -> list[Detection]:
    """Decode split-head raw conv tensors into :class:`Detection` objects.

    Args:
        outputs: The raw output tensors (any order).  Per stride: a box-DFL
            logits tensor ``(1, 4*reg_max, H, W)`` and a class-logits tensor
            ``(1, nc, H, W)``.
        nc: Number of classes.
        reg_max: DFL bins per box side (ultralytics default 16).
        strides: Detection-head strides, e.g. ``[8, 16, 32]``.
        confidence_threshold: Minimum class score to keep a detection.
        iou_threshold: Agnostic-NMS IoU threshold.
        scale, x_off, y_off: Letterbox transform (model space -> original image).

    Returns:
        Detections in the original image coordinate space.
    """
    grids, box_logits, cls_logits = _identify(outputs, nc, reg_max)
    strides_sorted = sorted(strides)  # ascending stride aligns with largest-grid-first
    anchors, stride_vec = _make_anchors(grids, strides_sorted)
    num_anchors = box_logits.shape[0]

    # DFL: (A, 4*reg_max) -> (A, 4, reg_max) -> softmax over bins -> expected distance
    reg = box_logits.reshape(num_anchors, 4, reg_max).astype(np.float32)
    reg = _softmax(reg, axis=2)
    bins = np.arange(reg_max, dtype=np.float32)
    dist = (reg * bins).sum(axis=2)  # (A, 4) ltrb in grid units

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

    # --- agnostic NMS via OpenCV (expects top-left x, y, w, h) ---
    tl_boxes = np.stack([x1, y1, x2 - x1, y2 - y1], axis=1)
    indices = cv2.dnn.NMSBoxes(
        bboxes=tl_boxes.tolist(),
        scores=confidences.tolist(),
        score_threshold=confidence_threshold,
        nms_threshold=iou_threshold,
    )
    if len(indices) == 0:
        return []
    indices = np.asarray(indices).flatten()

    detections: list[Detection] = []
    for idx in indices:
        # Map each corner from model space -> original image space via letterbox.
        ox1 = float((x1[idx] - x_off) / scale)
        oy1 = float((y1[idx] - y_off) / scale)
        ox2 = float((x2[idx] - x_off) / scale)
        oy2 = float((y2[idx] - y_off) / scale)
        detections.append(
            Detection(
                x_center=(ox1 + ox2) / 2.0,
                y_center=(oy1 + oy2) / 2.0,
                class_id=int(class_ids[idx]),
                confidence=float(confidences[idx]),
                bbox=(ox1, oy1, ox2, oy2),
            )
        )
    return detections


def is_split_meta(meta: dict) -> bool:
    """Whether a model metadata sidecar describes a split-head model."""
    if meta.get("format") in ("onnx_split", "rknn_split"):
        return True
    return meta.get("decode") == "host_dfl_anchor_sigmoid_nms"
