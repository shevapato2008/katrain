"""
Live camera demo: run the full detection pipeline and visualize results.

Usage:
    python -m katrain.vision.tools.live_demo --model best.pt --camera 0
    python -m katrain.vision.tools.live_demo --model best.pt --camera 0 --view camera
    python -m katrain.vision.tools.live_demo --model best.pt --camera 0 --view both --font-scale 0.25
    python -m katrain.vision.tools.live_demo --model best.pt --camera 0 --view warped --show-detections

Controls:  Q = quit | C = toggle CLAHE | P = print board state | D = toggle detections overlay | V = toggle view mode
"""

import argparse

import cv2
import numpy as np

from katrain.vision.board_state import BoardStateExtractor, BLACK, WHITE
from katrain.vision.pipeline import DetectionPipeline
from katrain.vision.tools.show_grid import draw_detection_overlay, draw_detections_overlay

VIEW_MODES = ["camera", "warped", "both"]


def draw_overlay(image: np.ndarray, board: np.ndarray, config) -> np.ndarray:
    display = image.copy()
    black_count = int(np.sum(board == BLACK))
    white_count = int(np.sum(board == WHITE))
    cv2.putText(display, f"B:{black_count} W:{white_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    return display


def main():
    parser = argparse.ArgumentParser(description="Live Go board detection demo")
    parser.add_argument("--model", type=str, required=True, help="Path to trained YOLO model")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--confidence", type=float, default=0.5)
    parser.add_argument("--use-clahe", action="store_true")
    parser.add_argument("--canny-min", type=int, default=20)
    parser.add_argument("--calibration", type=str, default=None, help="Path to camera_calibration.npz")
    parser.add_argument("--show-detections", action="store_true", help="Show YOLO bbox + label + confidence overlay")
    parser.add_argument(
        "--view", choices=VIEW_MODES, default="camera", help="Display mode: camera, warped, or both (default: camera)"
    )
    parser.add_argument("--font-scale", type=float, default=0.3, help="Font size for labels (default: 0.3)")
    parser.add_argument(
        "--skip-motion-filter",
        action="store_true",
        help="Disable motion rejection (annotations persist during hand movement)",
    )
    args = parser.parse_args()

    camera_config = None
    if args.calibration:
        from katrain.vision.config import CameraConfig

        data = np.load(args.calibration)
        camera_config = CameraConfig(camera_matrix=data["camera_matrix"], dist_coeffs=data["dist_coeffs"])

    pipeline = DetectionPipeline(
        model_path=args.model,
        camera_config=camera_config,
        confidence_threshold=args.confidence,
        use_clahe=args.use_clahe,
        canny_min=args.canny_min,
        skip_motion_filter=args.skip_motion_filter,
    )

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"Error: cannot open camera {args.camera}")
        return

    view_mode = args.view
    show_detections = args.show_detections
    font_scale = args.font_scale
    last_result = None  # cache last successful FrameResult for persistent camera overlay
    last_warped_display = None  # cache last warped display for persistent warped view

    print("Q = quit | C = toggle CLAHE | P = print board | D = toggle detections overlay | V = toggle view mode")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        result = pipeline.process_frame(frame)

        # Cache last successful result
        if result is not None and result.corners is not None:
            last_result = result

        # Use current result or fall back to cached result
        active_result = result if result is not None else last_result

        # Run YOLO on raw frame for camera-view bboxes (independent of board detection)
        if show_detections and view_mode in ("camera", "both"):
            raw_detections = pipeline.detector.detect(frame)
        else:
            raw_detections = []

        # --- Camera view ---
        if view_mode in ("camera", "both"):
            cam_display = frame.copy()

            # Layer 1: Board boundary + grid (when board was ever detected)
            if active_result is not None and active_result.corners is not None:
                cam_display = draw_detection_overlay(
                    cam_display,
                    active_result.corners,
                    active_result.transform_matrix,
                    active_result.warp_size,
                    pipeline.config,
                )

            # Layer 2: YOLO bboxes directly on camera frame
            if raw_detections:
                cam_display = draw_detections_overlay(cam_display, raw_detections, pipeline.config, font_scale=font_scale)

            if active_result is not None and active_result.confirmed_move:
                move_text = f"Move: {active_result.confirmed_move.gtp()} ({active_result.confirmed_move.player})"
                cv2.putText(cam_display, move_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            cv2.imshow("Camera", cam_display)

        # --- Warped view ---
        if view_mode in ("warped", "both"):
            if result is not None:
                if show_detections:
                    warped_display = draw_detections_overlay(
                        result.warped, result.detections, pipeline.config, font_scale=font_scale
                    )
                    black_count = int(np.sum(result.board == BLACK))
                    white_count = int(np.sum(result.board == WHITE))
                    cv2.putText(
                        warped_display,
                        f"B:{black_count} W:{white_count}",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0, 255, 0),
                        2,
                    )
                else:
                    warped_display = draw_overlay(result.warped, result.board, pipeline.config)

                if result.confirmed_move:
                    move_text = f"Move: {result.confirmed_move.gtp()} ({result.confirmed_move.player})"
                    cv2.putText(warped_display, move_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                    print(f"Confirmed move: {result.confirmed_move}")

                last_warped_display = warped_display
                cv2.imshow("Warped Board", warped_display)
            elif last_warped_display is not None:
                cv2.imshow("Warped Board", last_warped_display)
            elif view_mode == "warped":
                cv2.imshow("Warped Board", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("c"):
            pipeline.use_clahe = not pipeline.use_clahe
            print(f"CLAHE: {'ON' if pipeline.use_clahe else 'OFF'}")
        elif key == ord("d"):
            show_detections = not show_detections
            print(f"Detections overlay: {'ON' if show_detections else 'OFF'}")
        elif key == ord("v"):
            idx = VIEW_MODES.index(view_mode)
            old_mode = view_mode
            view_mode = VIEW_MODES[(idx + 1) % len(VIEW_MODES)]
            print(f"View mode: {view_mode}")
            # Close windows that are no longer needed
            if old_mode == "both" and view_mode != "both":
                if view_mode == "camera":
                    cv2.destroyWindow("Warped Board")
                else:
                    cv2.destroyWindow("Camera")
            elif old_mode == "camera" and view_mode == "warped":
                cv2.destroyWindow("Camera")
            elif old_mode == "warped" and view_mode == "camera":
                cv2.destroyWindow("Warped Board")
        elif key == ord("p") and result is not None:
            print(BoardStateExtractor.board_to_string(result.board))

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
