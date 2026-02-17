"""
Live camera demo: run the full detection pipeline and visualize results.

Usage:
    python -m katrain.vision.tools.live_demo --model best.pt --camera 0

Controls:  Q = quit | C = toggle CLAHE | P = print board state
"""

import argparse

import cv2
import numpy as np

from katrain.vision.board_state import BoardStateExtractor, BLACK, WHITE
from katrain.vision.pipeline import DetectionPipeline


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
    )

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"Error: cannot open camera {args.camera}")
        return

    print("Q = quit | C = toggle CLAHE | P = print board")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        result = pipeline.process_frame(frame)

        if result is not None:
            display = draw_overlay(result.warped, result.board, pipeline.config)
            if result.confirmed_move:
                move_text = f"Move: {result.confirmed_move.gtp()} ({result.confirmed_move.player})"
                cv2.putText(display, move_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                print(f"Confirmed move: {result.confirmed_move}")
            cv2.imshow("Go Board Detection", display)
        else:
            cv2.imshow("Go Board Detection", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("c"):
            pipeline.use_clahe = not pipeline.use_clahe
            print(f"CLAHE: {'ON' if pipeline.use_clahe else 'OFF'}")
        elif key == ord("p") and result is not None:
            print(BoardStateExtractor.board_to_string(result.board))

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
