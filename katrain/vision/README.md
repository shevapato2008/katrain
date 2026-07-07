# Physical Board LED-Anchor Calibration

Board mode uses a single `CameraHub` for capture, geometry calibration, and optional live recognition. A geometry lock is valid for an interactive session only after the 13 LED anchors (four corners and nine star points) have been detected on an empty board. A previous lock remains on disk as rollback data, but does not bypass session calibration.

Start the MacBook hardware service:

```bash
KATRAIN_MODE=board python -m katrain --ui web --host 127.0.0.1 --port 8001 \
  --disable-engine --led-serial-port /dev/cu.usbmodem2101 \
  --led-lut-path ~/.katrain/led_lut.json \
  --capture-camera 0 --capture-resolution 1920x1080 \
  --capture-dir ~/.katrain/baipu_captures
```

Verify capabilities and start a manual calibration after clearing the board:

```bash
curl http://127.0.0.1:8001/api/v1/geometry/status
curl -X POST http://127.0.0.1:8001/api/v1/geometry/calibrate \
  -H 'Content-Type: application/json' \
  -d '{"trigger":"manual","empty_confirmed":true}'
```

The kiosk guard invokes the same endpoint with `trigger=auto` after the operator confirms the board is empty. During calibration, poll `/api/v1/geometry/status`; success is `phase=ready`, `session_calibrated=true`, and `capabilities.geometry_ready=true`. `recognition_ready` additionally requires a loaded stone-recognition model. The settings page and geometry status icon open the manual recalibration screen.

## Kiosk calibration workflow

1. Log in, open **Settings**, then choose **Recalibrate board**. The grid icon in the top status bar opens the same `/kiosk/vision/setup` page.
2. Clear all stones from the physical board. The page shows the raw HBV camera stream and the square perspective-corrected stream side by side on a wide display, or stacked on a narrow display.
3. Confirm the empty board to start calibration. The four corners and nine star points are flashed in sequence; detected anchors appear on the raw stream as progress advances from 0/13 to 13/13.
4. A successful calibration shows four corner labels, 38 grid lines, and 361 intersections in green on both streams. The page also reports the RMS and maximum fit residual.
5. Selecting **Recalibrate** from a ready state only opens the empty-board warning. LEDs do not flash until **Empty board, start automatic calibration** is selected.
6. If camera or board drift invalidates the geometry, physical-board modules pause and show the stale grid in red. Clear the board and confirm recalibration to restore the ready state.

Stone recognition is optional for the baipu capture workflow: geometry can be ready while `model_ready` and `recognition_ready` remain false. AI play, tsumego, and research flows that require recognition remain blocked until a model is loaded.

Coordinates are always seated-human coordinates: `(row=0,col=0)` is upper-left and `(row=0,col=18)` is upper-right. Camera orientation is learned from the LED anchors and must not be manually rotated in the capture path. Geometry files are atomically stored at `~/.katrain/geometry_lock.npz` and `.json`; each baipu game also freezes its geometry beside the captured frames.

# 4-Class Detector (black / white / led_red / led_green)

The current board-recognition model detects **4 classes**: `black=0, white=1, led_red=2, led_green=3`.
The two LED classes let the detector recognise the guidance LED as its own object (so it is never
misread as a stone — see the `board_state` guard) and enable future LED-aware features. The class
list is a single source of truth in `katrain/vision/classes.py`; `data.yaml` writers, the detector,
and the exporters all derive from it.

**LED colour → class:** the manifest's `led_point.color` is the colour *about to be played* —
`"black"` (Black's move next) → **`led_red`**, `"white"` → **`led_green`**. Red guides Black, green guides White.

## Auto-labeling baipu captures (zero manual annotation)

`katrain/vision/tools/baipu_autolabel.py` generates exact 4-class YOLO labels from baipu capture
ground truth — **no hand-drawn boxes**. For each captured frame it:

1. Warps the raw frame to the deployment's rectified **950×950** board space using the frozen
   `geometry.npz` homography (the same space `worker.py` feeds the detector — avoids train/serve skew).
2. Reconstructs the exact board state from the SGF via `katrain.core.baipu` (capture-aware: handles
   captures, setup stones, passes).
3. Looks up each stone/LED at its calibrated grid intersection.
4. Corrects a **per-frame global board-drift translation** (the frozen grid drifts from the real board
   — in `kifu_24171` it jumps ~16–25 px once mid-game when the board was bumped). The shift is the
   robust median of `(detected centroid − grid point)` over the guide LED + isolated stones, clamped to
   `0.6·spacing`; on an anchor-less frame it **carries forward** the previous frame's shift rather than
   snapping back to the un-drifted grid. LED-anchor HSV thresholds live in `config.LedAnchorConfig`
   (a config edit for a new light/camera, not a code change).
5. Writes 4-class YOLO boxes: stones ≈`1.05·spacing` (object-tight; deployment snaps on box centre),
   LEDs a tight ≈`0.45·spacing` (a background-dominated box wrecks small-target recall). Boxes are
   clipped to the image; a stone/LED that drifts entirely off-frame is dropped (not visible → no label).

Per-frame drift diagnostics are written to `verify/shifts.csv`
(`frame,dx,dy,anchor_count,led_found,residual_px,fallback_used`) and colour overlays to `verify/`.

## Runbook

```bash
# 0. one-time setup
uv sync --extra vision --extra vision-train     # opencv + ultralytics/torch
uv run python i18n.py                           # compile .mo (core.baipu needs it for the SGF parse)

# 1. auto-label one or more capture dirs -> warped images + 4-class labels + verify overlays
uv run python -m katrain.vision.tools.baipu_autolabel \
  --game-dir ~/.katrain/baipu_captures/kifu_24171 \
  --out-images /tmp/go4/images_raw --out-labels /tmp/go4/labels_raw --verify-dir /tmp/go4/verify
# eyeball 8-10 overlays in /tmp/go4/verify/ and check /tmp/go4/verify/shifts.csv

# 2. temporal (leakage-free) train/val split + 4-class data.yaml  (NOT random — consecutive frames are near-dupes)
uv run python -m katrain.vision.tools.prepare_dataset \
  --images /tmp/go4/images_raw --labels /tmp/go4/labels_raw --output /tmp/go4/dataset \
  --split 0.8 --split-mode temporal --gap 3 --validate

# 3. train yolo11n, COCO-pretrained, LED-safe augmentation (hsv_h=0)
uv run python -m katrain.vision.tools.train_model train \
  --data /tmp/go4/dataset/data.yaml --model-size n --imgsz 640 --epochs 200 \
  --patience 40 --batch 16 --name go4_n --augment led-safe --cache --device mps

# 4. validate AT THE SAME imgsz (val defaults to 960 -> non-comparable otherwise)
uv run python -m katrain.vision.tools.train_model val \
  --data /tmp/go4/dataset/data.yaml --model <runs_dir>/detect/go4_n/weights/best.pt --imgsz 640

# 5. export (class-generic; meta.json carries the 4-class list)
uv run python -m katrain.vision.tools.export_onnx --model <runs_dir>/detect/go4_n/weights/best.pt --imgsz 640
uv run python -m katrain.vision.tools.export_rknn --onnx <runs_dir>/detect/go4_n/weights/best.onnx --target rk3588
# RKNN export is x86-only (rknn-toolkit2) — run it off the Mac. Deploy best_rk3588.rknn + best_rk3588.meta.json as a pair.
```

> `<runs_dir>` is Ultralytics' configured `runs_dir` (see `yolo settings`); on this machine it is
> `~/Repositories/katrain-visual-recognition/runs`, not `./runs`.

## Experiment log (4-class baipu model)

Dataset `kifu_24171`: 212 frames → 166 train / 43 val (temporal split, gap 3). Black/white ≈ 21k box
instances; LEDs are per-object rare (~210 instances) but appear in 211/212 frames.

**Run `go4_n`** (yolo11n, COCO-pretrained, imgsz 640, `--augment led-safe`, batch 16, MPS; early-stopped
at epoch 47, best epoch 7). Val (imgsz 640):

| class | P | R | mAP50 | mAP50-95 | val instances |
|---|---|---|---|---|---|
| black | 0.607 | 0.175 | 0.418 | 0.240 | 3924 |
| white | 0.544 | 0.173 | 0.381 | 0.212 | 4004 |
| led_red | 0.0 | 0.0 | 0.0 | 0.0 | 21 |
| led_green | 0.0 | 0.0 | 0.0 | 0.0 | 21 |

**Interpreting these numbers (this is a single-game smoke run — pipeline validation, not a production model):**

- **LEDs at 0** is expected here: ~21k stone instances vs ~165 LED instances (≈127:1 per-object imbalance),
  and `mosaic=1.0` shrinks the 16 px LED to ~8 px during the early epochs that drove early-stopping. The LED
  is bright and distinctive (verified in the overlays) — the blocker is purely instance imbalance. Fix by
  adding LED-rich capture sessions and/or offline LED-ROI oversampling, then retrain.
- **Modest black/white recall (~0.17)** is mostly a **temporal-split distribution gap**, not under-training
  (val mAP plateaued by epoch 7; 40 more epochs gave nothing). The leakage-free split trains on the *sparse
  early* board and validates on the *dense late* board (~185 stones/frame) — frames the model rarely saw.
  Annotation quality is good (overlays track stones through the mid-game ~16–25 px drift jump); the levers
  are more games (density variety), larger `imgsz`, and lighter mosaic — collected/validated via the
  multi-session production gate above.

## Data caveats

- **One game, one board, one light.** Val is optimistic (train/val share board + camera + lighting +
  stone set). The model is **specific to this board+lighting**; a different device/environment requires
  **re-collecting data and retraining**. Validate generalisation with a *second capture session*
  (session holdout: train game A, validate game B) before field trust.
- **LED class balance:** the LED is ubiquitous per-image (211/212 frames) but rare per-object. Ultralytics
  `copy_paste` is **not** used — it no-ops on bbox-only labels (needs segmentation polygons) and is
  class-agnostic. If LED recall is weak, oversample **offline** (duplicate LED-bearing images / paste LED
  ROIs onto warp backgrounds) or bump `imgsz`/model size.

# YOLO Training Results: go_dataset_diff_sam (historical, 2-class synthetic)

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

## Two-step recognition: true-position detection → occupancy-aware assignment

The detector reports each stone's **true visible position** (boxes hug the real stone, via
`baipu_autolabel --refine-boxes`, on by default). Deployment then maps detections to the board
in a **separate** step: `BoardStateExtractor.detections_to_board(..., occupancy_aware=True)`
assigns each detection to the nearest **empty** intersection by sub-cell distance, reassigning a
collided detection to its nearest empty neighbour instead of silently dropping it. The temporal
"one new stone, on a previously-empty point" rule lives in `MoveDetector.detect_new_move`.

**Train/serve margin caveat (reconcile before production training):** `baipu_autolabel` warps
training images with a 1-cell margin (`--margin-cells 1.0`), but `BoardConfig.border_*_mm == 0`
and the live warp currently uses no margin. The CNN detects the stone wherever it appears, so this
is not fatal, but for best train/serve match keep the live warp's margin and `border_*_mm`
consistent with the training margin. Tracked as a residual risk, not fixed in this addendum.
