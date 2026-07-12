"""Export a YOLO .pt model to an RKNN-friendly *split-head* ONNX + meta sidecar.

Usage:
    python -m katrain.vision.tools.export_onnx_split --pt best.pt --imgsz 640 \
        --out rknn_build_split/best_split.onnx

Why split-head: the standard ultralytics export concatenates box pixel coords
(0-640) and class scores (0-1) into one output tensor.  Per-tensor INT8
quantization then scales the whole tensor by the box range, rounding every
class score to 0 — the NPU returns zero detections.  This exporter patches
``Detect.forward`` to emit the raw per-scale conv tensors (box-DFL logits +
class logits) *before* DFL decode / anchor add / sigmoid / concat, so each
tensor has a single value range and quantizes cleanly.  The decode moves to the
host (:func:`katrain.vision.inference.split_decode.decode_split_heads`).

See ``superpowers/tracks/yolo-rknn-deploy/`` for the full write-up.

Requires: ultralytics, torch, onnx (dev machine only).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from katrain.vision.classes import CLASS_NAMES


def _patch_detect_forward() -> None:
    """Replace ``Detect.forward`` to emit raw per-scale conv tensors.

    Per detection level ``i`` this yields two tensors:
      * ``cv2[i](x[i])`` -> ``(1, 4*reg_max, H, W)`` box-DFL logits
      * ``cv3[i](x[i])`` -> ``(1, nc, H, W)`` class logits
    in emission order stride 8, 16, 32 (box then class within each stride).
    """
    from ultralytics.nn.modules import Detect

    def forward_split(self, x):
        outs = []
        for i in range(self.nl):
            outs.append(self.cv2[i](x[i]))
            outs.append(self.cv3[i](x[i]))
        return tuple(outs)

    Detect.forward = forward_split


def export_onnx_split(pt_path: str, imgsz: int = 640, out: str | None = None) -> Path:
    """Export ``pt_path`` to a split-head ONNX with a ``.meta.json`` sidecar.

    Returns the path to the exported ``.onnx`` file.
    """
    try:
        import torch
        from ultralytics import YOLO
    except ImportError:
        print("Error: ultralytics + torch are required for split-head export.")
        sys.exit(1)

    pt = Path(pt_path)
    if not pt.is_file():
        raise FileNotFoundError(f"Model not found: {pt}")

    out_path = Path(out) if out else pt.with_name(f"{pt.stem}_split.onnx")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    yolo = YOLO(str(pt))
    detect = yolo.model.model[-1]
    nc, reg_max, nl = int(detect.nc), int(detect.reg_max), int(detect.nl)
    strides = [int(s) for s in detect.stride.tolist()]

    _patch_detect_forward()
    model = yolo.model.eval()
    for p in model.parameters():
        p.requires_grad = False

    # Output names box_s{stride}/cls_s{stride} in emission order.
    output_names: list[str] = []
    for s in strides:
        output_names += [f"box_s{s}", f"cls_s{s}"]

    dummy = torch.zeros(1, 3, imgsz, imgsz)
    torch.onnx.export(
        model,
        dummy,
        str(out_path),
        input_names=["images"],
        output_names=output_names,
        opset_version=19,  # rknn-toolkit2 2.3.2 supports <= 19
        do_constant_folding=True,
        dynamo=False,
    )

    meta = {
        "format": "onnx_split",
        "source": pt.stem,
        "imgsz": imgsz,
        "input_name": "images",
        "input_shape": [1, 3, imgsz, imgsz],
        "input_normalize": "0-1",
        "input_channel_order": "RGB",
        "nc": nc,
        "reg_max": reg_max,
        "nl": nl,
        "strides": strides,
        "output_names": output_names,
        "classes": list(CLASS_NAMES),
        "decode": "host_dfl_anchor_sigmoid_nms",
    }
    meta_path = out_path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    print(f"Exported split-head ONNX: {out_path}")
    print(f"Exported metadata:        {meta_path}")
    print(f"  nc={nc} reg_max={reg_max} strides={strides}")
    print(f"  outputs (emit order): {output_names}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Export YOLO .pt to split-head ONNX for RKNN INT8")
    parser.add_argument("--pt", required=True, help="Path to .pt weights")
    parser.add_argument("--imgsz", type=int, default=640, help="Input image size (default: 640)")
    parser.add_argument("--out", default=None, help="Output .onnx path (default: {stem}_split.onnx next to .pt)")
    args = parser.parse_args()

    export_onnx_split(args.pt, args.imgsz, args.out)


if __name__ == "__main__":
    main()
