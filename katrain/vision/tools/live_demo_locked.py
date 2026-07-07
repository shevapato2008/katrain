"""Live geometry-locked 4-class detection preview.

Warps each camera frame with a geometry lock + 1-cell margin **exactly matching the training warp**
(baipu_autolabel / worker_inprocess), runs the detector, and draws the predicted boxes. This is the
train/serve-consistent way to preview the model on a live camera — unlike live_demo.py, which warps
via BoardFinder (board-edge basis, no margin) and so feeds the model a different geometry than it was
trained on.

The camera is opened through the production CameraManager at the resolution the lock was calibrated
at (stored in the lock as source_width/source_height; falls back to --capture-resolution for old
locks). Each frame is reconciled to that resolution via adjust_M_for_resolution, so the warp is
correct even if the camera can't deliver the requested size.

Usage:
    python -m katrain.vision.tools.live_demo_locked \
        --model go4_x_best.pt \
        --geometry data/baipu_captures/<game>/geometry.npz \
        --camera 0 --imgsz 1024 --conf 0.4

Controls: Q = quit

NOTE: the geometry lock must match the CURRENT board/camera pose (e.g. right after 摆谱 that game,
board unmoved). If the board moved since the lock was frozen, the boxes won't align — re-capture/
recalibrate to get a fresh geometry.npz.
"""

import argparse

import cv2

from katrain.vision.camera import CameraManager
from katrain.vision.config import DEFAULT_MARGIN_CELLS
from katrain.vision.geometry_lock import load_geometry_lock
from katrain.vision.motion_filter import MotionFilter
from katrain.vision.stone_detector import StoneDetector
from katrain.vision.warp import adjust_M_for_resolution, warp_with_margin

# BGR per class id: black, white, led_red, led_green
_COLOR = {0: (0, 0, 255), 1: (0, 255, 0), 2: (0, 140, 255), 3: (255, 200, 0)}


def main():
    ap = argparse.ArgumentParser(description="Live geometry-locked 4-class detection preview")
    ap.add_argument("--model", required=True, help="Path to trained YOLO weights (.pt/.onnx)")
    ap.add_argument("--geometry", required=True, help="geometry.npz from a capture (provides M + out_size)")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="Confidence threshold. 0.25 default: far-side (perspective-blurred) stones score lower, "
        "and occupancy-aware assignment + board priors filter spurious low-conf boxes downstream.",
    )
    ap.add_argument("--imgsz", type=int, default=1024, help="Detector input size (640 = faster, less accurate)")
    ap.add_argument(
        "--iou",
        type=float,
        default=0.5,
        help="Agnostic-NMS IoU threshold. 0.5 default merges size-variant duplicate boxes on "
        "blurry far-side stones (their mutual IoU ~0.69 survives the ultralytics 0.7 default).",
    )
    ap.add_argument("--margin-cells", type=float, default=DEFAULT_MARGIN_CELLS)
    ap.add_argument("--backend", default="ultralytics", choices=["ultralytics", "onnx", "rknn"])
    ap.add_argument(
        "--no-motion-gate",
        action="store_true",
        help="Detect on EVERY frame (default: only on motion-stable frames, like the production "
        "worker). Detecting on blurred/moving frames produces flickering duplicate boxes.",
    )
    ap.add_argument(
        "--capture-resolution",
        default="1280x720",
        help="Camera resolution to request when the lock has no source_width/height (old locks).",
    )
    args = ap.parse_args()

    lock = load_geometry_lock(args.geometry)
    out_size = int(lock.out_size)
    src_wh = (lock.source_width, lock.source_height)

    # Prefer the lock's calibration resolution; else the CLI fallback.
    if lock.source_width and lock.source_height:
        req_w, req_h = int(lock.source_width), int(lock.source_height)
        print(f"camera resolution from lock: {req_w}x{req_h}")
    else:
        req_w, req_h = (int(x) for x in args.capture_resolution.split("x"))
        print(f"lock has no source resolution; requesting {req_w}x{req_h} (--capture-resolution)")

    detector = StoneDetector(
        args.model, backend=args.backend, confidence_threshold=args.conf, imgsz=args.imgsz, iou_threshold=args.iou
    )

    camera = CameraManager(device_id=args.camera, width=req_w, height=req_h)
    if not camera.open():
        print(f"Error: cannot open camera {args.camera}")
        return
    print("Q = quit")
    motion = None if args.no_motion_gate else MotionFilter()
    try:
        warned = False
        dets = []
        while True:
            frame = camera.read_frame()
            if frame is None:
                continue
            frame_wh = (frame.shape[1], frame.shape[0])
            if not warned and src_wh[0] and tuple(int(v) for v in src_wh) != frame_wh:
                print(f"WARNING: camera delivered {frame_wh}, lock calibrated at {tuple(src_wh)} — rescaling M")
                warned = True
            M = adjust_M_for_resolution(lock.M, src_wh, frame_wh)
            warped = warp_with_margin(frame, M, out_size, margin_cells=args.margin_cells)
            # Only run detection on motion-STABLE frames — matches the production worker
            # (worker_inprocess gates on MotionFilter.is_stable). Detecting on blurred/moving
            # frames is what makes one stone flicker between several offset boxes. On unstable
            # frames we keep the last stable detections instead of re-running the model.
            stable = motion.is_stable(frame) if motion is not None else True
            if stable:
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
            if motion is not None:
                cv2.putText(
                    warped,
                    "STABLE" if stable else "MOVING - hold still (boxes frozen)",
                    (10, 56),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0) if stable else (0, 165, 255),
                    2,
                )
            cv2.imshow("Live geometry-locked detection (Q=quit)", warped)
            if (cv2.waitKey(1) & 0xFF) == ord("q"):
                break
    finally:
        camera.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
