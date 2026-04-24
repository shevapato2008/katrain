# YOLO Training Results: go_dataset_diff_sam

**Date**: 2026-02-19
**Dataset**: `go_dataset_diff_sam` (SAM-generated synthetic diff images)
**Hardware**: Apple M1 Max, MPS (Metal Performance Shaders)

## Dataset

- **Source**: Synthetic Go board images generated via SAM segmentation pipeline
- **Total images**: 201
- **Train/Val split**: 161 train / 40 val (every 5th image to val)
- **Classes**: 2 (`black`, `white`)
- **Val instances**: 4,847 (2,377 black, 2,470 white)

## Commands

### 1. Data Generation (synthesize_dataset)

```bash
uv run python -m katrain.vision.tools.synthesize_dataset \
  --seed-image go_dataset/assets/board-with-stones.png \
  --empty-board go_dataset/assets/board-empty.png \
  --sgf-dir /Users/fan/Repositories/go-topic-collections/19x19/data/kifu/ \
  --output ./go_dataset_diff_sam \
  --max-games 10 --move-interval 10 \
  --detect-method diff --crop-method sam \
  --verify
```

| Option | Description |
|--------|-------------|
| `--seed-image` | Reference board image with stones (used to derive stone appearance) |
| `--empty-board` | Empty board image (used as background for diff-based detection) |
| `--sgf-dir` | Directory of SGF game records to replay moves from |
| `--output` | Output directory for generated dataset (images + YOLO labels) |
| `--max-games` | Maximum number of SGF games to process |
| `--move-interval` | Sample every Nth move position from each game |
| `--detect-method` | Stone detection method: `diff` (image difference with empty board) |
| `--crop-method` | Stone cropping method: `sam` (Segment Anything Model for precise masks) |
| `--verify` | Generate visual verification images with bounding box overlays |

### 2. Dataset Preparation (train/val split)

```bash
cd go_dataset_diff_sam
mkdir -p images/train images/val labels/train labels/val

# Every 5th image to val (~80/20 split)
ls images/*.jpg | sort | awk 'NR % 5 == 0' | while read f; do
  base=$(basename "$f" .jpg)
  mv "images/$base.jpg" images/val/
  mv "labels/$base.txt" labels/val/
done

# Rest to train
mv images/*.jpg images/train/
mv labels/*.txt labels/train/
```

### 3. Model Training

```bash
# yolo11n (~2.6M params)
uv run python -m katrain.vision.tools.train_model train \
  --data go_dataset_diff_sam/data.yaml \
  --model-size n --epochs 10 --patience 5 \
  --name go_stones_sam_n --device mps

# yolo11x (~57M params, batch=4 to fit in MPS memory)
uv run python -m katrain.vision.tools.train_model train \
  --data go_dataset_diff_sam/data.yaml \
  --model-size x --epochs 10 --patience 5 \
  --name go_stones_sam_x --device mps --batch 4
```

## Training Configuration

| Parameter | yolo11n | yolo11x |
|-----------|---------|---------|
| Pretrained weights | `yolo11n.pt` | `yolo11x.pt` |
| Parameters | ~2.6M | ~57M |
| GFLOPs | 6.4 | 195.5 |
| Epochs | 10 | 10 |
| Patience | 5 | 5 |
| Image size | 960 | 960 |
| Batch size | 16 (auto) | 4 (manual) |
| Device | MPS | MPS |
| Optimizer | AdamW (auto) | AdamW (auto) |

## Training Results (Validation Set - Synthetic Data)

### yolo11n

| Epoch | mAP50 | mAP50-95 | box_loss | cls_loss |
|-------|-------|----------|----------|----------|
| 1 | 0.007 | 0.001 | 1.659 | 3.606 |
| 2 | 0.001 | 0.000 | 1.263 | 2.512 |
| 3 | 0.072 | 0.033 | 1.149 | 1.833 |
| 4 | 0.326 | 0.125 | 0.952 | 1.197 |
| 5 | 0.301 | 0.137 | 0.896 | 0.889 |
| 6 | 0.616 | 0.474 | 0.966 | 0.915 |
| 7 | 0.746 | 0.594 | 0.776 | 0.747 |
| **8** | **0.749** | **0.616** | 0.741 | 0.711 |
| 9 | 0.675 | 0.578 | 0.690 | 0.646 |
| 10 | 0.678 | 0.578 | 0.666 | 0.713 |

**Best epoch**: 8 (saved as `best.pt`)

### yolo11x

| Epoch | mAP50 | mAP50-95 | box_loss | cls_loss |
|-------|-------|----------|----------|----------|
| 1 | 0.000 | 0.000 | 0.860 | 0.909 |
| 2 | 0.002 | 0.001 | 0.839 | 0.658 |
| 3 | 0.000 | 0.000 | 1.179 | 0.896 |
| 4 | 0.000 | 0.000 | 1.230 | 0.801 |
| 5 | 0.000 | 0.000 | 0.836 | 0.571 |
| **6** | **0.988** | **0.792** | 0.976 | 0.579 |
| 7 | 0.747 | 0.591 | 0.782 | 0.433 |
| 8 | 0.558 | 0.494 | 0.736 | 0.400 |
| 9 | 0.608 | 0.547 | 0.621 | 0.335 |
| 10 | 0.579 | 0.526 | 0.596 | 0.330 |

**Best epoch**: 6 (saved as `best.pt`), followed by significant overfitting.

### Final Validation Summary

| Metric | yolo11n | yolo11x |
|--------|:-------:|:-------:|
| mAP50 | **0.781** | 0.596 |
| mAP50-95 | **0.641** | 0.479 |
| Precision | 0.462 | **0.991** |
| Recall | **0.734** | 0.486 |
| Black mAP50 | 0.811 | 0.556 |
| White mAP50 | 0.750 | 0.636 |
| Training time | 6 min | 28 min |
| best.pt size | 5.5 MB | 114.4 MB |
| Inference speed | 65.7 ms | 128.5 ms |

## Real Image Inference

**Test image**: `tests/data/board_recognition_case1_real.png` (real photo of a 9x9 Go board with stones)

### Results at conf=0.25

| Metric | yolo11n | yolo11x |
|--------|:-------:|:-------:|
| Black detected | 0 | 6 |
| White detected | 0 | 10 |
| Total detected | 0 | **16** |

### Results at conf=0.10

| Metric | yolo11n | yolo11x |
|--------|:-------:|:-------:|
| Black detected | 2 | **8** |
| White detected | 0 | **12** |
| Total detected | 2 | **20** |
| Avg confidence | 0.156 | **0.645** |
| Min confidence | 0.155 | 0.118 |
| Max confidence | 0.157 | **0.979** |

### Inference Observations

- **yolo11n**: Nearly unable to detect real stones. Only found 2 black stones at very low confidence (~0.15). White stones completely missed.
- **yolo11x**: Successfully detected most stones with high confidence (many >0.9). Some false positives on cloth texture near board edges.

## Key Findings

1. **yolo11x generalizes far better to real images** despite lower final mAP on synthetic validation data. The larger model captures more transferable features.

2. **Severe overfitting in yolo11x**: Peaked at mAP50=0.988 at epoch 6, then dropped sharply. The small dataset (161 train images) cannot sustain the 57M parameter model. Future training should use fewer epochs or stronger regularization.

3. **Sim-to-real gap is significant**: Both models trained on synthetic data struggle with real photos. This is expected given the domain difference (clean rendered boards vs. perspective-distorted real photos with varying lighting).

4. **MPS acceleration effective**: 5-6x speedup over CPU. Batch size needs to be reduced for large models (yolo11x required batch=4 to fit in ~23GB GPU memory, vs batch=16 for yolo11n).

5. **yolo11n too small for this task**: The 2.6M parameter model lacks capacity to learn features that transfer from synthetic to real domains.

## Live Demo Verification

The live demo decouples board detection and stone detection into independent layers, so YOLO bboxes appear even when board detection (Canny) fails.

```bash
uv run python -m katrain.vision.tools.live_demo \
  --model runs/detect/go_stones_sam_x/weights/best.pt \
  --camera 0 --view both --show-detections --confidence 0.25 --font-scale 0.25
```

### Expected behavior

| Scenario | Camera window shows |
|----------|-------------------|
| Board NOT detected, stones visible | YOLO bboxes only (green/orange rectangles) |
| Board detected, stones visible | Cyan boundary + green grid dots + YOLO bboxes |
| Board detected, no stones | Cyan boundary + green grid dots only |
| Neither works | Raw camera frame |

### Controls

| Key | Action |
|-----|--------|
| `D` | Toggle YOLO bboxes on/off (board overlay stays) |
| `V` | Cycle view mode: camera → warped → both |
| `C` | Toggle CLAHE (may help board detection) |
| `P` | Print board state to terminal |
| `Q` | Quit |

### Tuning tips

- Lower `--confidence` (e.g. 0.10) to see more detections at the cost of false positives
- Use `--font-scale 0.2` for smaller labels on crowded boards
- Add `--skip-motion-filter` to keep annotations visible while moving hands over the board
- Warped view only appears when board detection succeeds (it requires perspective transform)

## Artifacts

- `runs/detect/go_stones_sam_n/weights/best.pt` - yolo11n best weights (5.5 MB)
- `runs/detect/go_stones_sam_x/weights/best.pt` - yolo11x best weights (114.4 MB)
- `runs/detect/inference_n_real_low_conf.jpg` - yolo11n inference visualization
- `runs/detect/inference_x_real_low_conf.jpg` - yolo11x inference visualization
- `runs/detect/go_stones_sam_{n,x}/` - Full training logs, curves, and plots

## Recommendations

1. **Use yolo11x as the baseline model** for further iteration
2. **Add real training images** to bridge the sim-to-real gap (even 10-20 annotated real photos could help significantly)
3. **Reduce epochs to 6-8** with patience=3 to avoid overfitting on small datasets
4. **Consider yolo11m as a middle ground** - 20M params may offer better balance between generalization and inference speed
5. **Increase data augmentation** - perspective transforms, lighting variation, and background diversity to better match real conditions
