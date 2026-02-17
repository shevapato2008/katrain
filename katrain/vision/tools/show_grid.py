"""
Show the 19x19 grid overlay on a live camera feed to verify board detection + coordinate mapping.

Usage:
    python -m katrain.vision.tools.show_grid --camera 0

No YOLO model needed — this only tests BoardFinder + coordinate mapping.

Controls:  Q = quit | C = toggle CLAHE | S = save screenshot
"""

import argparse

import cv2
import numpy as np

from katrain.vision.board_finder import BoardFinder
from katrain.vision.config import BoardConfig
from katrain.vision.coordinates import grid_to_pixel


def draw_grid(image: np.ndarray, config: BoardConfig) -> np.ndarray:
    """Draw all 361 intersection points and grid lines on the warped board image."""
    display = image.copy()
    h, w = display.shape[:2]
    gs = config.grid_size

    # Draw grid lines
    for i in range(gs):
        # Horizontal lines
        x0, y = grid_to_pixel(0, i, w, h, config)
        x1, _ = grid_to_pixel(gs - 1, i, w, h, config)
        cv2.line(display, (x0, y), (x1, y), (0, 0, 255), 1)
        # Vertical lines
        x, y0 = grid_to_pixel(i, 0, w, h, config)
        _, y1 = grid_to_pixel(i, gs - 1, w, h, config)
        cv2.line(display, (x, y0), (x, y1), (0, 0, 255), 1)

    # Draw intersection dots
    for row in range(gs):
        for col in range(gs):
            px, py = grid_to_pixel(col, row, w, h, config)
            cv2.circle(display, (px, py), 3, (0, 255, 0), -1)

    # Highlight star points (for 19x19)
    if gs == 19:
        for r in (3, 9, 15):
            for c in (3, 9, 15):
                px, py = grid_to_pixel(c, r, w, h, config)
                cv2.circle(display, (px, py), 5, (0, 255, 255), -1)

    # Label corners
    for col, row, label in [(0, 0, "A19"), (18, 0, "T19"), (0, 18, "A1"), (18, 18, "T1"), (9, 9, "K10")]:
        px, py = grid_to_pixel(col, row, w, h, config)
        cv2.putText(display, label, (px + 6, py - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)

    return display


def main():
    parser = argparse.ArgumentParser(description="Show 19x19 grid overlay on detected board")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--use-clahe", action="store_true")
    parser.add_argument("--canny-min", type=int, default=20)
    parser.add_argument("--calibration", type=str, default=None)
    args = parser.parse_args()

    camera_config = None
    if args.calibration:
        from katrain.vision.config import CameraConfig

        data = np.load(args.calibration)
        camera_config = CameraConfig(camera_matrix=data["camera_matrix"], dist_coeffs=data["dist_coeffs"])

    config = BoardConfig()
    finder = BoardFinder(camera_config=camera_config)
    use_clahe = args.use_clahe

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"Error: cannot open camera {args.camera}")
        return

    print("Q = quit | C = toggle CLAHE | S = save screenshot")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        warped, found = finder.find_focus(frame, min_threshold=args.canny_min, use_clahe=use_clahe)

        if found and warped is not None:
            grid_img = draw_grid(warped, config)
            h, w = grid_img.shape[:2]
            cv2.putText(grid_img, f"{w}x{h}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow("Grid Overlay", grid_img)
        else:
            cv2.putText(frame, "Board not detected", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        cv2.imshow("Camera", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("c"):
            use_clahe = not use_clahe
            print(f"CLAHE: {'ON' if use_clahe else 'OFF'}")
        elif key == ord("s") and found and warped is not None:
            cv2.imwrite("grid_screenshot.jpg", draw_grid(warped, config))
            print("Saved grid_screenshot.jpg")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
