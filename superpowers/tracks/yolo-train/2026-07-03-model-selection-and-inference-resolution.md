# YOLOv11 Model Selection & Inference Resolution — Findings

**Date:** 2026-07-03
**Branch:** `feature/yolo-train`
**Task:** Of the YOLOv11 models trained on this branch, which is the most cost-effective, and what is the best camera / inference resolution?
**Eval environment:** conda `py311_katago` — ultralytics 8.4.34, torch 2.11.0, device **MPS** (Apple Silicon dev machine, *not* the target NPU).

---

## TL;DR

- **Most cost-effective model → `yolo11s`** (safe pick, cross-game generalization *proven* equal to `yolo11x`), with **`yolo11n`** as an even-cheaper candidate that needs one clean cross-game confirmation before shipping.
- **Resolution → capture at `1920×1080`, run inference at `imgsz 640`.** These are two different resolutions in a three-stage pipeline (capture → perspective-warp → model input), not a single downsample.
- **Why bigger models don't help:** `mAP50` is saturated (~0.99) across every model size. The only metric that keeps climbing with size is `mAP50-95` (tight-box IoU) — which the deployment **discards**, because `board_state.detections_to_board` snaps on the **box center** to the nearest grid intersection (the "two-step" recognition design). You pay 3–30× the NPU compute for accuracy the pipeline throws away.
- **Blur augmentation (`led-safe-blur`) — direction confirmed, effect small (§3).** A 2-arm × 3-seed A/B (yolo11s) shows blur training raises **far-side (perspective-blurred) stone confidence +3.3%** and shrinks the near→far confidence gap ~18%, at unchanged near-side confidence — the intended "harden the soft far region" effect, consistent across seeds. But on this clean 1080p held-out it did **not** raise recall (already saturated at 1.0), so the gain is *confidence margin / stability*, **not** detection rate.

---

## 1. Model cost-effectiveness

### 1a. Same-board temporal val — relative ranking across all four sizes

Dataset: `data/go4_3game` val split (111 imgs; temporal split of `kifu_24138 + kifu_24168 + kifu_24171`). Shares board/camera/light with train → **absolute numbers are optimistic**, but the split is identical for all sizes so the **ranking is valid**.

| size | params | GFLOPs @640 / @1024 | weight | mAP50 @1024 | mAP50-95 @1024 | Recall @1024 | MPS inf ms @640 / @1024 |
|------|-------:|---------------------|-------:|------------:|---------------:|-------------:|-------------------------|
| **n** | 2.59M  | 6.3 / 16.5   | 5.6 MB   | 0.990 | 0.751 | 0.980 | 25.4 / 34.0 |
| **s** | 9.43M  | 21.3 / 55.2  | 19.3 MB  | 0.990 | 0.769 | 0.978 | 29.1 / 26.0 |
| **m** | 20.06M | 67.7 / 174.6 | 40.6 MB  | 0.989 | 0.789 | 0.984 | 36.8 / 55.9 |
| **x** | 56.88M | 194.4 / 500.4| 114.5 MB | 0.990 | 0.759 | 0.984 | 59.8 / 167.4 |

> `mAP50` is flat at ~0.99 from n to x. Only `mAP50-95` climbs (n 0.751 → m 0.789) — i.e. tighter box regression, which the center-snap deployment ignores. MPS ms are dev-machine numbers and noisy for small models (postprocess-dominated); on the SBC the real cost proxy is **GFLOPs**.

### 1b. Clean cross-game held-out — the honest test (s vs x)

Dataset: `data/go4_eval_24138` (`kifu_24138`, 205 frames, **never in these two models' training**), `imgsz 1024`.

| model | size | params | mAP50 | mAP50-95 | black R | white P/R | led_red R | led_green R |
|-------|-----:|-------:|------:|---------:|--------:|-----------|----------:|------------:|
| `go4_s_ab_blur_s0.pt`  | **s** | 9.43M  | **0.986** | 0.660 | 0.984 | 1.000 / 1.000 | 0.948 | 0.980 |
| `go4_x_2game_1080p.pt` | **x** | 56.88M | 0.983 | 0.741 | 0.978 | 0.998 / 0.996 | 0.946 | 0.971 |

> **`s` ties/beats `x` on cross-game `mAP50` (0.986 vs 0.983) at 1/6 the parameters and 1/9 the compute.** `x`'s only advantage is `mAP50-95` (tight box) — discarded by center-snap. `led_red` recall is the weakest class for both (~0.95; LEDs are ~100 instances/game vs ~10k stones) and is essentially tied.
>
> Caveat: `s` trained on 3 games (`24167+24168+24171`), `x` on 2 (`24168+24171`) — not perfectly controlled, but both are honest evals on the **same** held-out game.

### 1c. Recommendation (deployment target: RK3562 / RK3576 / RK3588 NPU, INT8 RKNN)

| Model | Verdict |
|-------|---------|
| **`yolo11s`** | ✅ **Recommended.** Cross-game generalization *proven* equal to `x`; 9.4M params / 21 GFLOPs@640 / 19 MB. Safe on all three SBC tiers. |
| **`yolo11n`** | 🔬 **Cheapest candidate.** Temporal-val `mAP50` 0.990 matches every larger model; 6.3 GFLOPs@640, 5.6 MB (~30× cheaper than `x`). **Gap:** no clean cross-game eval — `n`'s `go4_3game` training leaked `kifu_24138`. Confirm before shipping (see below), then prefer `n` for the weak RK3562. |
| **`yolo11m` / `yolo11x`** | ❌ **Not justified.** 3–30× the NPU compute for zero deployable accuracy gain. `x` is also overfit-prone on this small dataset. |

**To promote `yolo11n`:** train `n` on a set that excludes `kifu_24138` (`go4_2game` or `go4_ab`), then `val` on `data/go4_eval_24138` at `imgsz 1024`. If cross-game `mAP50 ≳ 0.98`, ship `n`.

---

## 2. Recommended inference method & resolution

### 2a. The three-stage pixel flow (not a single downsample)

```
①  Camera frame           1920 × 1080   full scene (board + table + hands)
        │  perspective warp — cv2.warpPerspective(M)
        │  samples the tilted board quadrilateral out of the 1080p pixels
        ▼
②  Rectified board square  1056 × 1056   out_size 950 + 1-cell margin each side
        │                                 bird's-eye; the board fills the frame
        │  YOLO backend letterbox/resize (internal)
        ▼
③  Model input            640 × 640      → yolo11s / yolo11n inference
```

- ① → ② is `warp_with_margin(frame, M, out_size=950, margin_cells=1.0)` (`worker_inprocess.py:98`). A **crop + de-skew**, not a whole-frame resize. `pad = round(1.0·949/18) = 53`, so the square is `950 + 2·53 = 1056` px (≈ 52.8 px/cell).
- ② → ③ is the plain resize to `imgsz`, done inside the ONNX / RKNN / Ultralytics backend.

### 2b. Capture resolution: **1920×1080** (native) — not negotiable

The sharpness of the 1056 px warped board (stage ②) depends on how many real source pixels the board occupied in stage ①:

| Capture | Board region in raw frame | Warp to 1056 px is… | Result |
|---------|---------------------------|---------------------|--------|
| **1080p** | ~1370 × 760 px | a **downsample** (real detail → 1056) | sharp board, clean stones/LEDs |
| **720p**  | ~913 × 509 px  | an **upsample** (too few pixels → 1056) | soft/blurry board |

A 720p capture (`kifu_24165`) **upsamples** to 1056 → the warp is blurry *before* the 640 resize, which collapsed cross-game **white recall to 0.66**. Re-recording at 1080p took it to **0.999**. Feed a soft intermediate into the 640 resize and the model can't recover the lost detail.

➡️ Always start the Mac capture server with `--capture-resolution 1920x1080` (the `server.py` default is `1280x720`, intended for the SBC). Geometry locks self-describe `source_width/height`; `warp.adjust_M_for_resolution` reconciles a live frame to the lock's calibration resolution.

### 2c. Inference `imgsz`: **640**

- `mAP50` is saturated at 640 for every size (n 0.989 / s 0.990 / m 0.989 / x 0.991).
- 640 is **RKNN-validated** and what the ONNX/RKNN export ships.
- 640 is **cleaner**: the `probe_imgsz` experiment showed small models emit more borderline / near-duplicate boxes at 1024 on dense frames.
- Going to 1024/960 only adds `mAP50-95` (tight box) that the center-snap pipeline ignores.

**Rule of thumb:** capture as high as the camera allows (1080p) so the ~1000 px warped board is downsampled-**sharp**; keep the model at `imgsz 640` because that's all the detail the center-snap task needs, and it's the cheapest / RKNN-validated size.

### 2d. ⚠️ Implementation inconsistency to fix

Runtime `imgsz` is not aligned across backends:

| Backend | Default `imgsz` | Path |
|---------|-----------------|------|
| Ultralytics (dev) | **960** | `stone_detector.py:47`, `inference/ultralytics_backend.py:25` |
| ONNX | **640** (from `meta.json`) | `inference/onnx_backend.py:128` |
| RKNN (SBC) | **640** (from `meta.json`) | `inference/rknn_backend.py:140` |

Align the dev/Ultralytics path to **640** so validation matches the deployed SBC path.

---

## 3. Blur augmentation A/B — robustness of the far-side (perspective-blur) region

**Question:** does training on *degraded* (blurred/low-res) crops make the detector more robust?

### 3a. Design (controlled, 2 arms × 3 seeds = 6 runs)

Identical everything except the augmentation and seed — yolo11s, imgsz 640, epochs 200, single-GPU (`train_ab.sh`):

| arm | augmentation | train pool | held-out test |
|-----|--------------|-----------|---------------|
| baseline | `led-safe` (hsv_s/v only, hsv_h=0) | `go4_ab` = kifu_24167+24168+24171 | `kifu_24138` (205 frames) |
| **blur** | `led-safe-blur` = led-safe **+** `_BlurDownscale` | same | same |

`_BlurDownscale` (`katrain/vision/tools/train_model.py:53`) applies **hue-safe** degradation to each train image: random down-then-up resample (p=0.20), Gaussian blur k∈{3,5} (p=0.15), JPEG q30–70 (p=0.10). No ToGray/CLAHE/channel ops, so `led_red` vs `led_green` stay separable. Rationale: the geometry warp upsamples the far board region (few source pixels) to near-region size → far-side stones are soft and score lower; blur aug simulates that so the model learns to trust them. (Note: installed in-process by `cmd_train`, so these runs are **single-GPU** — DDP worker subprocesses would silently skip the aug.)

Evaluation (`eval_ab_one.py`) reports overall held-out metrics **plus** far(left 1/3) vs near(right 1/3) stone recall & mean confidence @ deploy conf 0.25 — the far third is exactly where blur should help.

### 3b. Results — held-out `kifu_24138`, per-arm mean of 3 seeds

(6925 far stones, 6410 near stones; raw per-model JSON: `2026-07-03-blur-ab-eval-heldout-24138.jsonl`)

| metric | baseline `led-safe` | blur `led-safe-blur` | Δ |
|--------|--------------------:|---------------------:|---:|
| mAP50 | 0.9847 | 0.9843 | −0.0003 |
| **mAP50-95** | 0.6853 | **0.6953** | **+0.0100** |
| Recall | 0.984 | 0.985 | +0.001 |
| far-side recall @conf0.25 | **1.000** | **1.000** | 0 (both saturated) |
| **far-side mean confidence** | 0.694 ±0.025 | **0.717 ±0.008** | **+0.023 (+3.3%)** |
| near-side mean confidence | 0.862 | 0.855 | −0.007 |
| **near→far confidence gap** | **+0.168** | **+0.138** | **−18%** |

### 3c. Honest reading

- ✅ **Direction confirmed, consistent across 3 seeds:** far-side (blurred) confidence ↑3.3% while near-side is flat → the aug specifically hardens the soft far region. The near→far penalty shrinks ~18%, blur's far-conf variance is *lower* (0.008 vs 0.025 → more stable), and mAP50-95 gains +1 pt (tighter boxes).
- ⚠️ **But no recall/mAP50 gain:** this held-out is clean 1080p, so baseline far-side recall is already **1.0** — no headroom. The benefit is **confidence margin & stability, not detection rate**.
- ⚠️ **Scope:** the held-out doesn't cover the harsh conditions (motion blur, low-end camera, steeper angle) that would actually stress recall. So this is evidence blur is *safe and directionally helpful*, not proof it lifts field accuracy.
- 🔎 This is why `go4_s_ab_blur_s0.pt` (blur arm, seed 0) was the one pulled to the repo root and used as the cross-game `s` representative in §1b — blur wins on margin at equal detection rate.

**Next step to actually pressure-test robustness:** build a *degraded* held-out (synthetic motion blur / downscale / JPEG on `kifu_24138`, or a genuinely lower-quality capture) and re-run the same A/B — that's where a recall gap, if real, would show.

---

## Appendix — reproduce

Model-size sweep (temporal val, both imgsz), one model per fresh process to avoid MPS state leak:

```bash
PY=/opt/miniconda3/envs/py311_katago/bin/python
# eval_size.py: YOLO(go4_<sz>_3game.pt).val(data=go4_3game/data.yaml, imgsz∈{1024,640}, device=mps)
for sz in n s m x; do "$PY" eval_size.py "$sz"; done
```

Clean cross-game held-out (kifu_24138):

```bash
# eval_crossgame.py: .val(data=go4_eval_24138/data.yaml, imgsz=1024, device=mps)
#   s -> go4_s_ab_blur_s0.pt   (trained 24167+24168+24171)
#   x -> go4_x_2game_1080p.pt  (trained 24168+24171)
for t in s x; do "$PY" eval_crossgame.py "$t"; done
```

Blur A/B (§3) — 6 runs on the remote GPU box (`fan@home-ubuntu`), then held-out eval per model:

```bash
# train_ab.sh: 2 arms × 3 seeds, yolo11s imgsz 640, --device 0 (single-GPU keeps blur aug active)
#   --augment led-safe       -> go4_s_ab_ledsafe_s{0,1,2}
#   --augment led-safe-blur  -> go4_s_ab_blur_s{0,1,2}   (train pool go4_ab, held-out kifu_24138)
# eval_ab_one.py: overall + far/near stone recall & mean-conf @ conf 0.25 on go4_ab_heldout
for n in go4_s_ab_ledsafe_s{0,1,2} go4_s_ab_blur_s{0,1,2}; do python eval_ab_one.py "$n"; done
```

Dataset game composition (verify no leakage before trusting a cross-game number):

```
go4_2game      train/val: kifu_24168, kifu_24171
go4_3game      train/val: kifu_24138, kifu_24168, kifu_24171   # ← 24138 leaks; not held-out for these
go4_ab         train/val: kifu_24167, kifu_24168, kifu_24171
go4_eval_24138 val only : kifu_24138 (205 frames)              # ← clean held-out for _2game / _ab models
```
