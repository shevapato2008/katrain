"""
Download and convert Roboflow "Go Positions" dataset for YOLO training.

Remaps 3 classes (blackStone=0, whiteStone=1, grid=2) to 2 classes (black=0, white=1),
dropping the grid class entirely.

Usage:
    python -m katrain.vision.tools.download_dataset --source ~/Downloads/Go-Positions-1 --output ./synthetic_dataset
"""

import argparse
import shutil
from pathlib import Path

# Roboflow "Go Positions" class mapping: original_id -> our_id (None = drop)
ROBOFLOW_CLASS_MAP = {
    0: 0,  # blackStone -> black
    1: 1,  # whiteStone -> white
    2: None,  # grid -> drop
}


def remap_label_line(line: str, class_mapping: dict[int, int | None] = None) -> str | None:
    """Remap a single YOLO label line to new class IDs.

    Args:
        line: YOLO label line "class_id x y w h".
        class_mapping: Dict mapping old class_id to new class_id (None = drop).

    Returns:
        Remapped line, or None if the class should be dropped.
    """
    if class_mapping is None:
        class_mapping = ROBOFLOW_CLASS_MAP

    parts = line.strip().split()
    if len(parts) < 5:
        return None

    old_class = int(parts[0])
    new_class = class_mapping.get(old_class)
    if new_class is None:
        return None

    return f"{new_class} {' '.join(parts[1:])}"


def convert_labels(source_dir: Path, output_dir: Path, class_mapping: dict[int, int | None] = None) -> dict:
    """Convert a Roboflow YOLO dataset to our 2-class format.

    Copies images and remaps label files. Handles train/valid/test splits if present.

    Args:
        source_dir: Root of the downloaded Roboflow dataset.
        output_dir: Root of the output dataset.
        class_mapping: Class remapping dict.

    Returns:
        Stats dict with file counts.
    """
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)

    if class_mapping is None:
        class_mapping = ROBOFLOW_CLASS_MAP

    stats = {"images": 0, "labels": 0, "lines_kept": 0, "lines_dropped": 0}

    # Roboflow exports have splits like train/, valid/, test/
    # Each split has images/ and labels/ subdirs
    splits = [d for d in source_dir.iterdir() if d.is_dir() and d.name in ("train", "valid", "test")]

    if not splits:
        # Flat structure: images and labels at top level
        splits = [source_dir]

    for split_dir in splits:
        split_name = split_dir.name if split_dir != source_dir else ""
        # Roboflow uses "valid" but YOLO wants "val"
        out_split = "val" if split_name == "valid" else split_name

        src_images = split_dir / "images"
        src_labels = split_dir / "labels"

        if not src_images.exists():
            src_images = split_dir
        if not src_labels.exists():
            src_labels = split_dir

        out_images = output_dir / "images" / out_split if out_split else output_dir / "images"
        out_labels = output_dir / "labels" / out_split if out_split else output_dir / "labels"
        out_images.mkdir(parents=True, exist_ok=True)
        out_labels.mkdir(parents=True, exist_ok=True)

        img_extensions = {".jpg", ".jpeg", ".png", ".bmp"}
        for img_path in sorted(src_images.iterdir()):
            if img_path.suffix.lower() not in img_extensions:
                continue

            shutil.copy2(img_path, out_images / img_path.name)
            stats["images"] += 1

            label_path = src_labels / (img_path.stem + ".txt")
            if label_path.exists():
                new_lines = []
                for line in label_path.read_text().strip().split("\n"):
                    if not line.strip():
                        continue
                    remapped = remap_label_line(line, class_mapping)
                    if remapped is not None:
                        new_lines.append(remapped)
                        stats["lines_kept"] += 1
                    else:
                        stats["lines_dropped"] += 1

                out_label_path = out_labels / label_path.name
                out_label_path.write_text("\n".join(new_lines) + "\n" if new_lines else "")
                stats["labels"] += 1

    # Write data.yaml
    write_data_yaml(output_dir)

    return stats


def write_data_yaml(output_dir: Path) -> None:
    """Write YOLO data.yaml for the converted dataset."""
    output_dir = Path(output_dir)
    yaml_content = (
        f"path: {output_dir.resolve()}\ntrain: images/train\nval: images/val\n\nnc: 2\nnames: ['black', 'white']\n"
    )
    (output_dir / "data.yaml").write_text(yaml_content)


def main():
    parser = argparse.ArgumentParser(description="Convert Roboflow Go Positions dataset to 2-class YOLO format")
    parser.add_argument("--source", type=str, required=True, help="Path to downloaded Roboflow dataset")
    parser.add_argument("--output", type=str, required=True, help="Output directory for converted dataset")
    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        print(f"Source directory not found: {source}")
        print()
        print("To download the dataset:")
        print("  1. Go to https://universe.roboflow.com/synthetic-data-3ol2y/go-positions")
        print("  2. Click 'Download Dataset' -> YOLO11 format")
        print("  3. Extract the zip and pass the path with --source")
        return

    print(f"Converting: {args.source} -> {args.output}")
    print(f"Class mapping: blackStone(0)->black(0), whiteStone(1)->white(1), grid(2)->dropped")

    stats = convert_labels(source, Path(args.output))

    print(f"\nDone. {stats['images']} images, {stats['labels']} label files converted.")
    print(f"Labels: {stats['lines_kept']} kept, {stats['lines_dropped']} dropped (grid class)")
    print(f"data.yaml written to {Path(args.output) / 'data.yaml'}")


if __name__ == "__main__":
    main()
