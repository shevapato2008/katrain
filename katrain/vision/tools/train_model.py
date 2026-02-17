"""
Train or validate a YOLO11 model for Go stone detection.

Train:    python -m katrain.vision.tools.train_model train --data ./go_dataset/data.yaml
Validate: python -m katrain.vision.tools.train_model val --data ./go_dataset/data.yaml --model runs/detect/go_stones/weights/best.pt
"""

import argparse


def cmd_train(args):
    from ultralytics import YOLO

    model = YOLO(args.model)
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

    model = YOLO(args.model)
    results = model.val(data=args.data, imgsz=args.imgsz)
    print(f"\nmAP50: {results.box.map50:.4f}")
    print(f"mAP50-95: {results.box.map:.4f}")


def main():
    parser = argparse.ArgumentParser(description="YOLO11 training/validation for Go stone detection")
    sub = parser.add_subparsers(dest="command", required=True)

    train_p = sub.add_parser("train", help="Train a model")
    train_p.add_argument("--data", type=str, required=True)
    train_p.add_argument("--model", type=str, default="yolo11n.pt")
    train_p.add_argument("--epochs", type=int, default=100)
    train_p.add_argument("--imgsz", type=int, default=960)
    train_p.add_argument("--batch", type=int, default=16)
    train_p.add_argument("--name", type=str, default="go_stones")
    train_p.add_argument("--patience", type=int, default=20)

    val_p = sub.add_parser("val", help="Validate a trained model")
    val_p.add_argument("--data", type=str, required=True)
    val_p.add_argument("--model", type=str, required=True, help="Path to best.pt")
    val_p.add_argument("--imgsz", type=int, default=960)

    args = parser.parse_args()
    if args.command == "train":
        cmd_train(args)
    elif args.command == "val":
        cmd_val(args)


if __name__ == "__main__":
    main()
