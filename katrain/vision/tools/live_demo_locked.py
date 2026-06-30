"""Live geometry-locked 4-class detection preview.

Warps each camera frame with a geometry lock + 1-cell margin **exactly matching the training warp**
(baipu_autolabel / worker_inprocess), runs the detector, and draws the predicted boxes. This is the
train/serve-consistent way to preview the model on a live camera — unlike live_demo.py, which warps
via BoardFinder (board-edge basis, no margin) and so feeds the model a different geometry than it was
trained on.

Usage:
    python -m katrain.vision.tools.live_demo_locked \
        --model go4_x_best.pt \
        --geometry data/baipu_captures/kifu_24165/geometry.npz \
        --camera 0 --imgsz 1024 --conf 0.4

Controls: Q = quit

NOTE: the geometry lock must match the CURRENT board/camera pose (e.g. right after 摆谱 that game,
board unmoved). If the board moved since the lock was frozen, the boxes won't align — re-capture/
recalibrate to get a fresh geometry.npz.
"""

import argparse

import cv2
import numpy as np

from katrain.vision.config import DEFAULT_MARGIN_CELLS
from katrain.vision.stone_detector import StoneDetector
from katrain.vision.warp import warp_with_margin

# BGR per class id: black, white, led_red, led_green
_COLOR = {0: (0, 0, 255), 1: (0, 255, 0), 2: (0, 140, 255), 3: (255, 200, 0)}


def main():
    ap = argparse.ArgumentParser(description="Live geometry-locked 4-class detection preview")
    ap.add_argument("--model", required=True, help="Path to trained YOLO weights (.pt/.onnx)")
    ap.add_argument("--geometry", required=True, help="geometry.npz from a capture (provides M + out_size)")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--conf", type=float, default=0.4)
    ap.add_argument("--imgsz", type=int, default=1024, help="Detector input size (640 = faster, less accurate)")
    ap.add_argument("--margin-cells", type=float, default=DEFAULT_MARGIN_CELLS)
    ap.add_argument("--backend", default="ultralytics", choices=["ultralytics", "onnx", "rknn"])
    args = ap.parse_args()

    geo = np.load(args.geometry, allow_pickle=True)
    M = np.asarray(geo["M"], np.float64)
    out_size = int(geo["out_size"])
    detector = StoneDetector(args.model, backend=args.backend, confidence_threshold=args.conf, imgsz=args.imgsz)

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"Error: cannot open camera {args.camera}")
        return
    print("Q = quit")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        warped = warp_with_margin(frame, M, out_size, margin_cells=args.margin_cells)
        dets = detector.detect(warped)
        counts = {0: 0, 1: 0, 2: 0, 3: 0}
        for d in dets:
            counts[d.class_id] = counts.get(d.class_id, 0) + 1
            x1, y1, x2, y2 = (int(v) for v in d.bbox)
            color = _COLOR.get(d.class_id, (200, 200, 200))
            cv2.rectangle(warped, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                warped,
                f"{d.class_name} {d.confidence:.2f}",
                (x1, max(0, y1 - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                color,
                1,
            )
        cv2.putText(
            warped,
            f"B:{counts[0]} W:{counts[1]} R:{counts[2]} G:{counts[3]}",
            (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (255, 255, 255),
            2,
        )
        cv2.imshow("Live geometry-locked detection (Q=quit)", warped)
        if (cv2.waitKey(1) & 0xFF) == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
