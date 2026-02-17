"""
Data collection tool: capture perspective-corrected board images for YOLO training.

Usage:
    python -m katrain.vision.tools.collect_data --output ./go_dataset/images --camera 0

Controls:
    SPACE = save current frame
    Q     = quit
"""

import argparse
import time
from pathlib import Path

import cv2

from katrain.vision.board_finder import BoardFinder


def main():
    parser = argparse.ArgumentParser(description="Capture board images for training data")
    parser.add_argument("--output", type=str, default="./go_dataset/images/train", help="Output directory")
    parser.add_argument("--camera", type=int, default=0, help="Camera device index")
    parser.add_argument("--min-threshold", type=int, default=20, help="Canny min threshold")
    parser.add_argument("--use-clahe", action="store_true", help="Enable CLAHE preprocessing")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    finder = BoardFinder()
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"Error: cannot open camera {args.camera}")
        return

    count = 0
    print(f"Saving to {output_dir}/")
    print("SPACE = save | Q = quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        warped, found = finder.find_focus(frame, min_threshold=args.min_threshold, use_clahe=args.use_clahe)

        if found and warped is not None:
            cv2.imshow("Board (corrected)", warped)
        cv2.imshow("Camera (raw)", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord(" ") and found and warped is not None:
            timestamp = int(time.time() * 1000)
            filename = output_dir / f"board_{timestamp}.jpg"
            cv2.imwrite(str(filename), warped)
            count += 1
            print(f"Saved: {filename} ({count} total)")

    cap.release()
    cv2.destroyAllWindows()
    print(f"Total images saved: {count}")


if __name__ == "__main__":
    main()
