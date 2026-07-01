"""
Train or validate a YOLO11 model for Go stone detection.

Train (default extra-large):
    python -m katrain.vision.tools.train_model train --data ./data.yaml

Train (specific size):
    python -m katrain.vision.tools.train_model train --data ./data.yaml --model-size m

Validate:
    python -m katrain.vision.tools.train_model val --data ./data.yaml --model runs/detect/go_stones/weights/best.pt
"""

import argparse
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "models"

MODEL_SIZES = {
    "n": ("yolo11n.pt", "~2.6M params, fastest"),
    "s": ("yolo11s.pt", "~9.4M params"),
    "m": ("yolo11m.pt", "~20M params, balanced"),
    "l": ("yolo11l.pt", "~25M params"),
    "x": ("yolo11x.pt", "~57M params, most accurate"),
}

DEFAULT_MODEL = "yolo11x.pt"

# LED-safe augmentation for the 4-class baipu model. hsv_h=0 is load-bearing:
# hue separates led_red from led_green, so jittering it corrupts the label.
# copy_paste is pinned to 0.0 ON PURPOSE: Ultralytics CopyPaste no-ops on bbox-only
# labels (it needs segmentation polygons) and is class-agnostic anyway, so it cannot
# oversample the LED class. hsv_s/hsv_v give mild illumination robustness; hsv_h stays 0.
LED_SAFE_AUG = {
    "hsv_h": 0.0,
    "hsv_s": 0.2,
    "hsv_v": 0.4,
    "degrees": 0.0,
    "shear": 0.0,
    "perspective": 0.0,
    "flipud": 0.0,
    "fliplr": 0.5,
    "translate": 0.1,
    "scale": 0.5,
    "mosaic": 1.0,
    "close_mosaic": 15,
    "mixup": 0.0,
    "copy_paste": 0.0,
    "erasing": 0.0,
}


class _BlurDownscale:
    """Hue-safe blur / low-res / JPEG degradation on the composed TRAIN image.

    Hardens the model against the far-side perspective-blur gradient: the geometry warp
    upsamples the far board region (few source pixels) to the same size as the near region,
    so far-side stones are soft/low-detail and score lower. We simulate that by randomly
    down-then-up resampling, Gaussian-blurring, and JPEG-degrading training crops. All ops
    preserve hue (no ToGray/CLAHE/channel ops) so led_red vs led_green stay separable.
    """

    def __init__(self, p_downscale=0.20, p_blur=0.15, p_jpeg=0.10, seed=0):
        import random

        self._rand = random.Random(seed)  # deterministic but varies across calls
        self.p_downscale, self.p_blur, self.p_jpeg = p_downscale, p_blur, p_jpeg

    def __call__(self, labels):
        import cv2

        img = labels.get("img") if isinstance(labels, dict) else None
        if img is None or img.ndim != 3:
            return labels
        r = self._rand
        h, w = img.shape[:2]
        if r.random() < self.p_downscale:  # low-res far-side simulation
            f = r.uniform(0.3, 0.7)
            small = cv2.resize(img, (max(1, int(w * f)), max(1, int(h * f))), interpolation=cv2.INTER_AREA)
            img = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
        if r.random() < self.p_blur:
            k = r.choice([3, 5])
            img = cv2.GaussianBlur(img, (k, k), 0)
        if r.random() < self.p_jpeg:
            ok, enc = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), r.randint(30, 70)])
            if ok:
                img = cv2.imdecode(enc, cv2.IMREAD_COLOR)
        labels["img"] = img
        return labels


def _install_blur_downscale_aug() -> None:
    """Monkeypatch YOLODataset.build_transforms to inject _BlurDownscale into the TRAIN
    pipeline (right before Format). albumentations isn't installed in our envs, so this is
    the dependency-free way to add blur/low-res aug. Raises if the insertion point can't be
    found — a requested blur run must never silently train without it."""
    from ultralytics.data import dataset as _ds

    orig = _ds.YOLODataset.build_transforms

    def patched(self, hyp=None):
        compose = orig(self, hyp)
        if getattr(self, "augment", False):  # train split only (val has augment=False)
            tlist = getattr(compose, "transforms", None)
            if not isinstance(tlist, list) or not tlist:
                raise RuntimeError("led-safe-blur: unexpected Compose structure; cannot insert transform")
            tlist.insert(len(tlist) - 1, _BlurDownscale())  # before Format (the last transform)
            print("[led-safe-blur] BlurDownscale augmentation INSTALLED in train pipeline")
        return compose

    _ds.YOLODataset.build_transforms = patched


def build_train_kwargs(args) -> dict:
    """Assemble the model.train() kwargs, injecting LED_SAFE_AUG for the led-safe variants."""
    kwargs = dict(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        name=args.name,
        patience=args.patience,
        device=args.device,
        seed=getattr(args, "seed", 0),
        save=True,
        plots=True,
        cache=getattr(args, "cache", False),
    )
    if getattr(args, "augment", "default") in ("led-safe", "led-safe-blur"):
        kwargs.update(LED_SAFE_AUG)
    return kwargs


def resolve_model(args) -> str:
    """Resolve the model path from --model and --model-size arguments.

    --model takes precedence when explicitly changed from the default.
    --model-size provides a convenient shortcut for standard YOLO11 sizes.
    """
    if args.model != DEFAULT_MODEL and args.model_size:
        # --model was explicitly set, it takes precedence
        pt = args.model
    elif args.model_size:
        if args.model_size not in MODEL_SIZES:
            raise SystemExit(f"Unknown model size '{args.model_size}'. Choose from: {', '.join(MODEL_SIZES)}")
        pt, desc = MODEL_SIZES[args.model_size]
        print(f"Model: {pt} ({desc})")
    else:
        pt = args.model

    # Check local models/ directory first
    local = MODEL_DIR / Path(pt).name
    if local.exists():
        print(f"Using local model: {local}")
        return str(local)
    return pt


def cmd_train(args):
    from ultralytics import YOLO

    if getattr(args, "augment", "default") == "led-safe-blur":
        _install_blur_downscale_aug()
    model_path = resolve_model(args)
    print(f"Loading model: {model_path}")
    model = YOLO(model_path)
    model.train(**build_train_kwargs(args))
    print(f"\nTraining complete. Best weights: runs/detect/{args.name}/weights/best.pt")


def cmd_val(args):
    from ultralytics import YOLO

    model_path = resolve_model(args)
    print(f"Loading model: {model_path}")
    model = YOLO(model_path)
    results = model.val(data=args.data, imgsz=args.imgsz)
    print(f"\nmAP50: {results.box.map50:.4f}")
    print(f"mAP50-95: {results.box.map:.4f}")


def main():
    parser = argparse.ArgumentParser(description="YOLO11 training/validation for Go stone detection")
    sub = parser.add_subparsers(dest="command", required=True)

    train_p = sub.add_parser("train", help="Train a model")
    train_p.add_argument("--data", type=str, required=True)
    train_p.add_argument(
        "--model", type=str, default=DEFAULT_MODEL, help=f"Model path or pretrained weights (default: {DEFAULT_MODEL})"
    )
    train_p.add_argument(
        "--model-size",
        type=str,
        choices=list(MODEL_SIZES.keys()),
        default=None,
        help="Shortcut: n(2.6M) s(9.4M) m(20M) l(25M) x(57M). Overrides --model if set",
    )
    train_p.add_argument("--epochs", type=int, default=100)
    train_p.add_argument("--imgsz", type=int, default=960)
    train_p.add_argument("--batch", type=int, default=-1, help="Batch size (-1 for auto-batch based on GPU memory)")
    train_p.add_argument("--name", type=str, default="go_stones")
    train_p.add_argument("--patience", type=int, default=20)
    train_p.add_argument("--seed", type=int, default=0, help="RNG seed (weight init, shuffle, aug) for reproducible/multi-seed runs")
    train_p.add_argument("--device", type=str, default="mps", help="Device: mps (Mac GPU), cpu, 0 (CUDA GPU 0)")
    train_p.add_argument(
        "--augment",
        choices=["default", "led-safe", "led-safe-blur"],
        default="default",
        help="led-safe: hsv_h=0 + LED-friendly aug. led-safe-blur: same + cv2 blur/downscale/jpeg "
        "degradation to harden against the far-side perspective-blur gradient.",
    )
    train_p.add_argument("--cache", action="store_true", help="cache images in RAM (small datasets)")

    val_p = sub.add_parser("val", help="Validate a trained model")
    val_p.add_argument("--data", type=str, required=True)
    val_p.add_argument("--model", type=str, required=True, help="Path to best.pt")
    val_p.add_argument(
        "--model-size",
        type=str,
        choices=list(MODEL_SIZES.keys()),
        default=None,
        help="Shortcut: n(2.6M) s(9.4M) m(20M) l(25M) x(57M). Overrides --model if set",
    )
    val_p.add_argument("--imgsz", type=int, default=960)

    args = parser.parse_args()
    if args.command == "train":
        cmd_train(args)
    elif args.command == "val":
        cmd_val(args)


if __name__ == "__main__":
    main()
