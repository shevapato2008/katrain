"""
Auto-label warped board images for YOLO training by HSV color classification.

Samples HSV color at each of 361 grid intersections, classifies black/white/empty,
outputs YOLO-format .txt label files.

Usage:
    python -m katrain.vision.tools.auto_label --images ./images --labels ./labels
    python -m katrain.vision.tools.auto_label --images ./images --labels ./labels --verify --verify-dir ./verify
"""

import argparse
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

import cv2
import numpy as np

from katrain.vision.config import BoardConfig
from katrain.vision.coordinates import grid_to_pixel

# Normalized stone bounding box (22mm stone on 424.2 x 454.5 mm board)
STONE_BBOX_W = 22.0 / 424.2  # ~0.052
STONE_BBOX_H = 22.0 / 454.5  # ~0.048


class StoneColor(IntEnum):
    BLACK = 0
    WHITE = 1
    EMPTY = -1


@dataclass
class LabeledStone:
    grid_x: int
    grid_y: int
    color: StoneColor
    pixel_x: int
    pixel_y: int


def classify_intersection(
    hsv_image: np.ndarray,
    px: int,
    py: int,
    half_patch: int,
    black_v_max: int = 80,
    white_s_max: int = 50,
    white_v_min: int = 160,
) -> StoneColor:
    """Classify a grid intersection as black, white, or empty using HSV thresholds.

    Samples a small patch centered at (px, py) and uses median V and S channels.
    """
    h, w = hsv_image.shape[:2]
    y1 = max(0, py - half_patch)
    y2 = min(h, py + half_patch + 1)
    x1 = max(0, px - half_patch)
    x2 = min(w, px + half_patch + 1)
    patch = hsv_image[y1:y2, x1:x2]
    if patch.size == 0:
        return StoneColor.EMPTY

    median_v = int(np.median(patch[:, :, 2]))
    median_s = int(np.median(patch[:, :, 1]))

    if median_v < black_v_max:
        return StoneColor.BLACK
    if median_s < white_s_max and median_v > white_v_min:
        return StoneColor.WHITE
    return StoneColor.EMPTY


def label_board_image(
    image: np.ndarray,
    config: BoardConfig | None = None,
    black_v_max: int = 80,
    white_s_max: int = 50,
    white_v_min: int = 160,
) -> list[LabeledStone]:
    """Label all stones on a warped board image.

    Args:
        image: BGR warped board image.
        config: Board dimensions. Defaults to standard 19x19.

    Returns:
        List of LabeledStone for detected black/white intersections (empty excluded).
    """
    if config is None:
        config = BoardConfig()

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    img_h, img_w = image.shape[:2]
    half_patch = int(0.015 * img_w)

    labels = []
    for gy in range(config.grid_size):
        for gx in range(config.grid_size):
            px, py = grid_to_pixel(gx, gy, img_w, img_h, config)
            color = classify_intersection(
                hsv, px, py, half_patch, black_v_max=black_v_max, white_s_max=white_s_max, white_v_min=white_v_min
            )
            if color != StoneColor.EMPTY:
                labels.append(LabeledStone(grid_x=gx, grid_y=gy, color=color, pixel_x=px, pixel_y=py))
    return labels


def write_yolo_labels(labels: list[LabeledStone], output_path: Path, img_w: int, img_h: int) -> None:
    """Write YOLO-format label file.

    Format: class_id x_center y_center width height (all normalized 0-1).
    """
    output_path = Path(output_path)
    lines = []
    for label in labels:
        class_id = int(label.color)
        x_center = label.pixel_x / img_w
        y_center = label.pixel_y / img_h
        lines.append(f"{class_id} {x_center:.6f} {y_center:.6f} {STONE_BBOX_W:.6f} {STONE_BBOX_H:.6f}")
    output_path.write_text("\n".join(lines) + "\n" if lines else "")


def draw_verification(image: np.ndarray, labels: list[LabeledStone]) -> np.ndarray:
    """Draw labeled bounding boxes on the image for visual validation."""
    vis = image.copy()
    img_h, img_w = vis.shape[:2]
    box_w = int(STONE_BBOX_W * img_w)
    box_h = int(STONE_BBOX_H * img_h)

    for label in labels:
        color = (0, 0, 255) if label.color == StoneColor.BLACK else (255, 255, 255)
        x1 = label.pixel_x - box_w // 2
        y1 = label.pixel_y - box_h // 2
        x2 = label.pixel_x + box_w // 2
        y2 = label.pixel_y + box_h // 2
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
        text = "B" if label.color == StoneColor.BLACK else "W"
        cv2.putText(vis, text, (x1, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
    return vis


def label_directory(
    image_dir: Path,
    label_dir: Path,
    config: BoardConfig | None = None,
    verify: bool = False,
    verify_dir: Path | None = None,
    black_v_max: int = 80,
    white_s_max: int = 50,
    white_v_min: int = 160,
) -> dict:
    """Batch-label all images in a directory.

    Returns:
        dict with counts: total, labeled, black_stones, white_stones.
    """
    image_dir = Path(image_dir)
    label_dir = Path(label_dir)
    label_dir.mkdir(parents=True, exist_ok=True)

    if verify and verify_dir:
        verify_dir = Path(verify_dir)
        verify_dir.mkdir(parents=True, exist_ok=True)

    if config is None:
        config = BoardConfig()

    extensions = {".jpg", ".jpeg", ".png", ".bmp"}
    image_files = sorted(f for f in image_dir.iterdir() if f.suffix.lower() in extensions)

    stats = {"total": len(image_files), "labeled": 0, "black_stones": 0, "white_stones": 0}

    for img_path in image_files:
        image = cv2.imread(str(img_path))
        if image is None:
            print(f"  Skip (unreadable): {img_path.name}")
            continue

        labels = label_board_image(
            image, config=config, black_v_max=black_v_max, white_s_max=white_s_max, white_v_min=white_v_min
        )

        img_h, img_w = image.shape[:2]
        label_path = label_dir / (img_path.stem + ".txt")
        write_yolo_labels(labels, label_path, img_w, img_h)

        n_black = sum(1 for l in labels if l.color == StoneColor.BLACK)
        n_white = sum(1 for l in labels if l.color == StoneColor.WHITE)
        stats["labeled"] += 1
        stats["black_stones"] += n_black
        stats["white_stones"] += n_white

        print(f"  {img_path.name}: {n_black}B + {n_white}W = {len(labels)} stones")

        if verify and verify_dir:
            vis = draw_verification(image, labels)
            cv2.imwrite(str(verify_dir / img_path.name), vis)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Auto-label warped board images for YOLO training")
    parser.add_argument("--images", type=str, required=True, help="Directory of warped board images")
    parser.add_argument("--labels", type=str, required=True, help="Output directory for YOLO label files")
    parser.add_argument("--verify", action="store_true", help="Generate verification images")
    parser.add_argument("--verify-dir", type=str, default=None, help="Directory for verification images")
    parser.add_argument("--black-v-max", type=int, default=80, help="V threshold for black stones")
    parser.add_argument("--white-s-max", type=int, default=50, help="S threshold for white stones")
    parser.add_argument("--white-v-min", type=int, default=160, help="V threshold for white stones")
    args = parser.parse_args()

    verify_dir = args.verify_dir or (args.labels + "_verify" if args.verify else None)

    print(f"Auto-labeling images from: {args.images}")
    print(f"Writing labels to: {args.labels}")
    print(f"Thresholds: black_v_max={args.black_v_max}, white_s_max={args.white_s_max}, white_v_min={args.white_v_min}")

    stats = label_directory(
        image_dir=Path(args.images),
        label_dir=Path(args.labels),
        verify=args.verify,
        verify_dir=Path(verify_dir) if verify_dir else None,
        black_v_max=args.black_v_max,
        white_s_max=args.white_s_max,
        white_v_min=args.white_v_min,
    )

    print(f"\nDone. {stats['labeled']}/{stats['total']} images labeled.")
    print(f"Total: {stats['black_stones']} black + {stats['white_stones']} white stones")


if __name__ == "__main__":
    main()
