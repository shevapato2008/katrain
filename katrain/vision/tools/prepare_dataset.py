"""
Prepare a YOLO dataset: split into train/val, create data.yaml, merge datasets.

Usage:
    python -m katrain.vision.tools.prepare_dataset --images ./collected --labels ./labels --output ./dataset --split 0.8 --validate
    python -m katrain.vision.tools.prepare_dataset --merge-base ./synthetic --merge-extra ./real --output ./combined
"""

import argparse
import random
import shutil
from pathlib import Path


def split_dataset(
    image_dir: Path,
    label_dir: Path,
    output_dir: Path,
    train_ratio: float = 0.8,
    seed: int = 42,
) -> dict:
    """Split images and labels into train/val sets.

    Args:
        image_dir: Directory with images.
        label_dir: Directory with matching YOLO .txt labels.
        output_dir: Root of output dataset (creates images/train, images/val, etc).
        train_ratio: Fraction of data for training.
        seed: Random seed for reproducible splits.

    Returns:
        Stats dict with train/val counts.
    """
    image_dir = Path(image_dir)
    label_dir = Path(label_dir)
    output_dir = Path(output_dir)

    img_extensions = {".jpg", ".jpeg", ".png", ".bmp"}
    images = sorted(f for f in image_dir.iterdir() if f.suffix.lower() in img_extensions)

    rng = random.Random(seed)
    rng.shuffle(images)

    split_idx = int(len(images) * train_ratio)
    train_images = images[:split_idx]
    val_images = images[split_idx:]

    stats = {"train": 0, "val": 0, "missing_labels": 0}

    for split_name, split_images in [("train", train_images), ("val", val_images)]:
        img_out = output_dir / "images" / split_name
        lbl_out = output_dir / "labels" / split_name
        img_out.mkdir(parents=True, exist_ok=True)
        lbl_out.mkdir(parents=True, exist_ok=True)

        for img_path in split_images:
            shutil.copy2(img_path, img_out / img_path.name)
            label_path = label_dir / (img_path.stem + ".txt")
            if label_path.exists():
                shutil.copy2(label_path, lbl_out / label_path.name)
            else:
                stats["missing_labels"] += 1
            stats[split_name] += 1

    return stats


def write_data_yaml(output_dir: Path) -> None:
    """Write YOLO data.yaml for the dataset."""
    output_dir = Path(output_dir)
    yaml_content = (
        f"path: {output_dir.resolve()}\ntrain: images/train\nval: images/val\n\nnc: 2\nnames: ['black', 'white']\n"
    )
    (output_dir / "data.yaml").write_text(yaml_content)


def merge_datasets(base_dir: Path, merge_dir: Path, output_dir: Path) -> dict:
    """Merge two YOLO datasets into one.

    Copies all images and labels from both datasets into output.
    Handles filename collisions by prefixing merge_dir files with 'merge_'.

    Returns:
        Stats dict with counts from each source.
    """
    base_dir = Path(base_dir)
    merge_dir = Path(merge_dir)
    output_dir = Path(output_dir)

    stats = {"base": 0, "merged": 0}

    for split in ("train", "val"):
        out_img = output_dir / "images" / split
        out_lbl = output_dir / "labels" / split
        out_img.mkdir(parents=True, exist_ok=True)
        out_lbl.mkdir(parents=True, exist_ok=True)

        # Copy base
        base_img = base_dir / "images" / split
        base_lbl = base_dir / "labels" / split
        if base_img.exists():
            for f in base_img.iterdir():
                shutil.copy2(f, out_img / f.name)
                stats["base"] += 1
            if base_lbl.exists():
                for f in base_lbl.iterdir():
                    shutil.copy2(f, out_lbl / f.name)

        # Copy merge (prefix to avoid collisions)
        merge_img = merge_dir / "images" / split
        merge_lbl = merge_dir / "labels" / split
        if merge_img.exists():
            for f in merge_img.iterdir():
                dest_name = f"merge_{f.name}" if (out_img / f.name).exists() else f.name
                shutil.copy2(f, out_img / dest_name)
                stats["merged"] += 1
                lbl_file = merge_lbl / (f.stem + ".txt")
                if merge_lbl.exists() and lbl_file.exists():
                    lbl_dest = f"merge_{lbl_file.name}" if dest_name.startswith("merge_") else lbl_file.name
                    shutil.copy2(lbl_file, out_lbl / lbl_dest)

    write_data_yaml(output_dir)
    return stats


def validate_dataset(dataset_dir: Path) -> dict:
    """Validate a YOLO dataset structure.

    Returns:
        Dict with counts and any issues found.
    """
    dataset_dir = Path(dataset_dir)
    result = {"valid": True, "issues": [], "train_images": 0, "val_images": 0, "train_labels": 0, "val_labels": 0}

    yaml_path = dataset_dir / "data.yaml"
    if not yaml_path.exists():
        result["valid"] = False
        result["issues"].append("Missing data.yaml")

    img_extensions = {".jpg", ".jpeg", ".png", ".bmp"}

    for split in ("train", "val"):
        img_dir = dataset_dir / "images" / split
        lbl_dir = dataset_dir / "labels" / split

        if not img_dir.exists():
            result["issues"].append(f"Missing images/{split}/")
            result["valid"] = False
            continue

        images = [f for f in img_dir.iterdir() if f.suffix.lower() in img_extensions]
        labels = list(lbl_dir.iterdir()) if lbl_dir.exists() else []
        label_stems = {f.stem for f in labels}

        result[f"{split}_images"] = len(images)
        result[f"{split}_labels"] = len(labels)

        # Check for orphan images (no matching label)
        orphans = [f.name for f in images if f.stem not in label_stems]
        if orphans:
            result["issues"].append(f"{split}: {len(orphans)} images without labels")

        # Check for orphan labels (no matching image)
        image_stems = {f.stem for f in images}
        orphan_labels = [f.name for f in labels if f.stem not in image_stems]
        if orphan_labels:
            result["issues"].append(f"{split}: {len(orphan_labels)} labels without images")

    return result


def main():
    parser = argparse.ArgumentParser(description="Prepare YOLO dataset for Go stone training")
    parser.add_argument("--images", type=str, help="Input image directory")
    parser.add_argument("--labels", type=str, help="Input label directory")
    parser.add_argument("--output", type=str, required=True, help="Output dataset directory")
    parser.add_argument("--split", type=float, default=0.8, help="Train/val split ratio")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for split")
    parser.add_argument("--validate", action="store_true", help="Validate dataset after creation")
    parser.add_argument("--merge-base", type=str, help="Base dataset directory for merging")
    parser.add_argument("--merge-extra", type=str, help="Extra dataset directory to merge in")
    args = parser.parse_args()

    output_dir = Path(args.output)

    if args.merge_base and args.merge_extra:
        print(f"Merging: {args.merge_base} + {args.merge_extra} -> {args.output}")
        stats = merge_datasets(Path(args.merge_base), Path(args.merge_extra), output_dir)
        print(f"Done. Base: {stats['base']} images, Merged: {stats['merged']} images")
    elif args.images and args.labels:
        print(f"Splitting: {args.images} -> {args.output} (ratio={args.split})")
        stats = split_dataset(Path(args.images), Path(args.labels), output_dir, args.split, args.seed)
        write_data_yaml(output_dir)
        print(f"Done. Train: {stats['train']}, Val: {stats['val']}, Missing labels: {stats['missing_labels']}")
    else:
        parser.error("Provide either --images/--labels or --merge-base/--merge-extra")

    if args.validate:
        result = validate_dataset(output_dir)
        print(f"\nValidation: {'PASS' if result['valid'] else 'FAIL'}")
        print(f"  Train: {result['train_images']} images, {result['train_labels']} labels")
        print(f"  Val: {result['val_images']} images, {result['val_labels']} labels")
        for issue in result["issues"]:
            print(f"  Issue: {issue}")


if __name__ == "__main__":
    main()
