"""
Generate printable ArUco markers for Go board corner detection.

Print the output image and cut out the 4 markers. Place them at the board corners:
  - Marker 0 (default) → top-left corner
  - Marker 1 (default) → top-right corner
  - Marker 2 (default) → bottom-right corner
  - Marker 3 (default) → bottom-left corner

Usage:
    python -m katrain.vision.tools.generate_markers --ids 0 1 2 3 --size 100 --output markers.png
"""

import argparse

import cv2
import numpy as np


def generate_marker_sheet(ids: list[int], size: int = 100, margin: int = 20) -> np.ndarray:
    """Generate a 2x2 grid of ArUco markers with labels."""
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

    labels = ["Top-Left", "Top-Right", "Bottom-Right", "Bottom-Left"]
    label_height = 30
    cell_w = size + 2 * margin
    cell_h = size + 2 * margin + label_height

    sheet = np.ones((cell_h * 2, cell_w * 2), dtype=np.uint8) * 255

    positions = [(0, 0), (1, 0), (1, 1), (0, 1)]  # 2x2 grid: TL, TR, BR, BL

    for i, mid in enumerate(ids):
        marker = cv2.aruco.generateImageMarker(aruco_dict, mid, size)
        col, row = positions[i]
        x = col * cell_w + margin
        y = row * cell_h + margin
        sheet[y : y + size, x : x + size] = marker

        # Label
        label = f"ID={mid} ({labels[i]})"
        ty = y + size + margin + 5
        cv2.putText(sheet, label, (x, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.4, 0, 1)

    return sheet


def main():
    parser = argparse.ArgumentParser(description="Generate printable ArUco markers for board detection")
    parser.add_argument("--ids", type=int, nargs=4, default=[0, 1, 2, 3], help="4 marker IDs (TL TR BR BL)")
    parser.add_argument("--size", type=int, default=100, help="Marker size in pixels")
    parser.add_argument("--output", type=str, default="markers.png", help="Output file path")
    args = parser.parse_args()

    sheet = generate_marker_sheet(args.ids, args.size)
    cv2.imwrite(args.output, sheet)
    print(f"Saved {args.output} ({sheet.shape[1]}x{sheet.shape[0]} px)")
    print(f"Marker IDs: {args.ids}")
    print("Print, cut, and place at board corners: TL, TR, BR, BL")


if __name__ == "__main__":
    main()
