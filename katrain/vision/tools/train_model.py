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

MODEL_SIZES = {
    "n": ("yolo11n.pt", "~2.6M params, fastest"),
    "s": ("yolo11s.pt", "~9.4M params"),
    "m": ("yolo11m.pt", "~20M params, balanced"),
    "l": ("yolo11l.pt", "~25M params"),
    "x": ("yolo11x.pt", "~57M params, most accurate"),
}

DEFAULT_MODEL = "yolo11x.pt"


def resolve_model(args) -> str:
    """Resolve the model path from --model and --model-size arguments.

    --model takes precedence when explicitly changed from the default.
    --model-size provides a convenient shortcut for standard YOLO11 sizes.
    """
    if args.model != DEFAULT_MODEL and args.model_size:
        # --model was explicitly set, it takes precedence
        return args.model
    if args.model_size:
        if args.model_size not in MODEL_SIZES:
            raise SystemExit(f"Unknown model size '{args.model_size}'. Choose from: {', '.join(MODEL_SIZES)}")
        pt, desc = MODEL_SIZES[args.model_size]
        print(f"Model: {pt} ({desc})")
        return pt
    return args.model


def cmd_train(args):
    from ultralytics import YOLO

    model_path = resolve_model(args)
    print(f"Loading model: {model_path}")
    model = YOLO(model_path)
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        name=args.name,
        patience=args.patience,
        save=True,
        plots=True,
    )
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
