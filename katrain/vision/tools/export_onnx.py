"""Export YOLO .pt model to ONNX format with model.meta.json sidecar.

Usage:
    python -m katrain.vision.tools.export_onnx --model best.pt --imgsz 960

Requires: ultralytics, onnx, onnxslim (dev machine only).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def export_onnx(model_path: str, imgsz: int = 960, output_dir: str | None = None, simplify: bool = True) -> Path:
    """Export a YOLO .pt model to ONNX with a metadata sidecar.

    Args:
        model_path: Path to .pt weights file.
        imgsz: Input image size for the model.
        output_dir: Directory for output files. Defaults to same directory as model.
        simplify: Whether to simplify the ONNX graph.

    Returns:
        Path to the exported .onnx file.
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        print("Error: ultralytics is required for export. Install with: pip install ultralytics")
        sys.exit(1)

    model_path = Path(model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    if output_dir:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = model_path.parent

    # Load and export
    model = YOLO(str(model_path))
    onnx_path = model.export(format="onnx", imgsz=imgsz, simplify=simplify)
    onnx_path = Path(onnx_path)

    # Move to output dir if needed
    final_onnx = out_dir / onnx_path.name
    if onnx_path != final_onnx:
        onnx_path.rename(final_onnx)
        onnx_path = final_onnx

    # Extract model info for metadata
    class_names = model.names  # e.g. {0: "black", 1: "white"}
    num_classes = len(class_names)

    # YOLO v8/v11 raw output: (1, num_classes + 4, num_detections)
    # 4 = xywh bounding box coords, num_detections depends on imgsz
    # For imgsz=960: 8400 detections (80x80 + 40x40 + 20x20 grid cells)
    # For imgsz=640: 8400 detections
    num_detections = _estimate_num_detections(imgsz)
    output_shape = [1, num_classes + 4, num_detections]

    # Determine source model name from the .pt filename or model info
    source_name = model_path.stem
    if hasattr(model, "cfg") and model.cfg:
        source_name = Path(model.cfg).stem

    meta = {
        "format": "onnx",
        "source": source_name,
        "imgsz": imgsz,
        "input_name": "images",
        "input_shape": [1, 3, imgsz, imgsz],
        "input_normalize": "0-1",
        "input_channel_order": "RGB",
        "output_name": "output0",
        "output_shape": output_shape,
        "output_format": "yolo_v8_raw",
        "classes": list(class_names.values()),
        "includes_nms": False,
        "bbox_format": "xywh_center_normalized",
    }

    meta_path = onnx_path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    print(f"Exported ONNX model: {onnx_path}")
    print(f"Exported metadata:   {meta_path}")
    print(f"  Classes: {meta['classes']}")
    print(f"  Input:   {meta['input_shape']}")
    print(f"  Output:  {meta['output_shape']}")

    return onnx_path


def _estimate_num_detections(imgsz: int) -> int:
    """Estimate number of YOLO detection anchors for a given image size.

    YOLO v8/v11 uses 3 detection heads at strides 8, 16, 32.
    Each head produces (imgsz/stride)^2 anchors.
    """
    total = 0
    for stride in (8, 16, 32):
        grid = imgsz // stride
        total += grid * grid
    return total


def main():
    parser = argparse.ArgumentParser(description="Export YOLO .pt to ONNX with metadata sidecar")
    parser.add_argument("--model", required=True, help="Path to .pt weights")
    parser.add_argument("--imgsz", type=int, default=960, help="Input image size (default: 960)")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: same as model)")
    parser.add_argument("--no-simplify", action="store_true", help="Skip ONNX graph simplification")
    args = parser.parse_args()

    export_onnx(args.model, args.imgsz, args.output_dir, simplify=not args.no_simplify)


if __name__ == "__main__":
    main()
