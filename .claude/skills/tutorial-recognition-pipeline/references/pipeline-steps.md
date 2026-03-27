# Pipeline Steps Detail

## S0: Bounding Box Detection

Detect individual diagram regions on a multi-diagram page.

**VLLM approach** (primary): Send full page image, ask for `{"figures": {"图1": [x1,y1,x2,y2], ...}}`
**CV fallback**: Detect diagram vertical ranges via row-wise dark pixel density, then find horizontal extent.

Output: bbox dict mapping figure_label → pixel coordinates.

## S1: Region Calibration

Determine which portion of the 19x19 board is shown (most diagrams show a corner).

**CV hint** (`calibrate_region()`):
- Detect thick border lines (left/right/top/bottom edges)
- Match star points (hoshi at positions 3,9,15 on each axis)
- Score multiple hypotheses, pick best confidence

**VLLM refinement**: Send crop image with grid line counts, ask for `{"col_start": N, "row_start": N}`.

Rules:
- Thick left border → `col_start = 0`
- Thick right border → `col_start = 19 - num_v_lines`
- Star points at known positions constrain the solution

## S2: OpenCV Grid Detection (`cv_detect_grid()`)

Morphological line detection for precise grid positions.

1. Threshold to binary (< 160)
2. Horizontal kernel (`min_line_len × 1`) → morphological open → horizontal lines
3. Vertical kernel (`1 × min_line_len`) → morphological open → vertical lines
4. Project to 1D (sum along axis)
5. Peak detection with minimum distance constraint
6. Gap filling: if gap between adjacent lines > 1.6× spacing, interpolate missing lines

Returns: `(h_positions[], v_positions[], spacing)` — exact pixel coordinates.

## S3: Occupied Intersection Detection (`cv_detect_occupied()`)

Multi-feature anomaly detection at every intersection.

**Features per intersection:**
- `dark_ratio`: fraction of pixels < 100 (black stone signature)
- `edge_ratio`: Canny edge density (stone border signature)
- `std_val`: pixel standard deviation (texture vs. flat background)
- `circ_contrast`: mean(outside) - mean(inside) circular mask (white stone signature)

**Occupied if ANY of:**
- `dark_ratio > median + 2σ`
- `edge_ratio > median + 2σ`
- `std_val > median + 2σ`
- `circ_contrast < -15` (white stone)
- `dark_ratio > 0.28` (absolute threshold for numbered stones)

**Letter detection (second pass):** For unoccupied non-border intersections, mask out the grid cross pattern, count remaining dark pixels. `outside_ratio > 0.12` → letter candidate.

**CV pre-classification** (`cv_preclass_confident()`):
- `dark_ratio > 0.55 && mean < 80` → "black" (confident)
- `mean > 180 && dark_ratio < 0.05` → "white" (confident)
- Else → ambiguous (needs VLLM)

## S4: VLLM Few-Shot Classification

Two images sent to VLLM:
1. **Fewshot sheet** (`build_fewshot_sheet()`): top row = 6 labeled example patches, bottom rows = target patches with letter labels A, B, C...
2. **Annotated crop** (`build_annotated_crop()`): full board crop with magenta letter labels at occupied positions

**Few-shot examples** (from `data/training_patches/examples/`):
- `black_plain.png` → "black"
- `black_numbered.png` → "black+N"
- `white_plain.png` → "white"
- `white_numbered.png` → "white+N"
- `letter.png` → "letter_A"
- `empty.png` → "empty"

**Categories:**
- `"black"` / `"white"`: plain stones
- `"black+N"` / `"white+N"`: stones with move number N
- `"triangle_black"` / `"triangle_white"` etc.: shape-marked stones
- `"letter_X"`: letter annotation on empty intersection
- `"empty"`: false detection

**Merging:** VLLM results override CV pre-classifications. CV-confident results are used as fallback when VLLM fails.

## S5: Payload Construction (`classification_to_payload()`)

Convert classification results + label_map + region offsets → `BoardPayload` JSON.

Maps each classified position:
- `"black"/"black+N"` → `stones.B` + optional `labels`
- `"white"/"white+N"` → `stones.W` + optional `labels`
- `"letter_X"` → `letters`
- `"triangle_*"` etc. → `shapes`

Viewport computed server-side via `compute_viewport()`.
