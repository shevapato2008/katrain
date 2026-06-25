# Baipu→YOLO 4-Class Auto-Label & Retrain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retrain the KaTrain board-recognition YOLO11 model from 2 classes (black, white) to 4 classes (black, white, led_red, led_green), using zero-manual-annotation labels auto-generated from baipu capture ground truth (SGF + per-frame LED metadata + frozen board geometry).

**Architecture:** A new labeler warps each captured raw frame to the deployment's rectified 950×950 board space (the same space `worker.py` feeds the detector), reconstructs the exact board state from the SGF via existing `katrain.core.baipu` (capture-aware), looks up each stone/LED at its calibrated grid intersection, corrects a per-frame global board-drift translation, and writes 4-class YOLO boxes. Existing `prepare_dataset`/`train_model`/`export_onnx`/`export_rknn` are reused; the export+inference chain is already class-count-generic, so the only code changes are the data.yaml writers, a single class-name source of truth, and one runtime guard.

**Tech Stack:** Python 3.11, OpenCV (cv2), NumPy, Ultralytics YOLO11, pytest. Deployment target RK3588 NPU (ONNX→RKNN).

## Global Constraints

- **Class scheme (verbatim, fixed order):** `['black', 'white', 'led_red', 'led_green']` → ids `black=0, white=1, led_red=2, led_green=3`.
- **LED color → class:** manifest `led_point.color == "black"` (next move is black) → **`led_red` (2)**; `led_point.color == "white"` → **`led_green` (3)**. (Red guides Black, green guides White.)
- **Label coordinate space:** rectified **950×950** warped board (`out_size` from `geometry.npz`), matching `worker.py:199` which runs `detector.detect(warped)`. **Do NOT label raw frames.**
- **Grid convention:** canonical `row=0` top, `col=0` left ("seated_human"). `geometry.npz["points"][row][col]` and `xs[col]/ys[row]` use this convention directly — **no transpose, no row flip** (empirically confirmed: direct mapping median LED error 17.6 px vs 31.7 px for any flip; and `BoardConfig.border_*_mm == 0`, so warped intersection `(r,c)` = `(xs[col], ys[row]) ≈ (col/18·950, row/18·950)`, which is the exact inverse of deployment `detections_to_board`).
- **Prerequisite — install the `vision` extra (REQUIRED before Tasks 3–6):** OpenCV (`cv2`) lives in `[project.optional-dependencies].vision`, not the base deps, so a plain `uv sync` omits it and even existing vision tests fail to collect. Run **`uv sync --extra vision`** once. (Task 8/9 also want `--extra vision-train` for ultralytics.)
- **Black formatting:** `black -l 120 katrain tests`.
- **Tests:** `CI=true uv run pytest tests/test_vision` must pass (no GPU/engine needed for the labeler tasks; the train/export step is a runbook, not a unit test).
- **i18n `.mo` — scoped prerequisite (real-data / SGF-parse tests only):** `katrain.core.baipu` → `katrain.core.game` → `katrain.core.lang` raises `FileNotFoundError: [Errno 2] No translation file found for domain: 'katrain'` at **import time** if the compiled translations are absent (verified: the existing `tests/test_baipu_*.py` error this way on a fresh checkout). **Task 3 imports `core.baipu` lazily — inside `load_capture`/`reconstruct_board`, not at module top** — so importing `baipu_autolabel` does NOT trigger this, and the **pure-CV unit tests run in CI with no `.mo` and no capture fixture**. The `.mo` build is required only for the tests/CLI that actually parse the SGF (the `@requires_capture` real-data tests and `process_game`): run **`uv run python i18n.py`** once to compile `katrain/i18n/locales/*/LC_MESSAGES/katrain.mo` before those. (Tasks 1, 2, 7, 8 do not import `core.game` at all.)
- **Single source of truth:** the 4 class names live in exactly one place (`katrain/vision/classes.py`) and are imported everywhere (data.yaml writers, `stone_detector.CLASS_NAMES`, export fallbacks).

---

## Key Findings That Shaped This Plan (from parallel investigation)

1. **Deployment runs YOLO on the warped board, not raw frames** (`katrain/vision/worker.py:194-199`: `warpPerspective` → `detect(warped)` → `detections_to_board` via `pixel_to_physical`/`physical_to_grid`). ⟹ train in warped space to avoid train/serve skew.
2. **The dominant per-frame label error is NOT stone-height parallax — it is a global board-drift translation** between the frozen `geometry.npz` grid and the actual board, which jumps ~16 px once mid-game (the board was bumped/re-seated around move ~85). Stones and LEDs drift together (corr 0.97). A radial "shift toward image center by k·spacing" model is rejected by the data (R²≈0). ⟹ compensate with a **per-frame global translation** estimated from that frame's anchors (the always-present guide LED + isolated stones); on a zero-anchor frame, carry forward the previous frame's shift (never silently fall back to `(0,0)` mid-game). The small residual (<0.2·spacing) is absorbed by a modest box margin (Task 5 sizes stone boxes ≈1.05·spacing, LED boxes tight ≈0.45·spacing).
3. **The export/inference chain is already class-count-generic.** `export_onnx` derives `classes` from `model.names` into a `<model>.meta.json` sidecar; `export_rknn` and the onnx/rknn backends size the class slice dynamically from that sidecar. ⟹ **no code change** there; correctness depends entirely on `data.yaml` being `nc: 4` at train time.
4. **Runtime board-state writer would corrupt state on LED detections** (`board_state.py:33` `board[...] = det.class_id + 1` maps led_red→3, led_green→4). ⟹ one guard line.
5. **Training a tiny, single-board, single-light dataset (212 frames, 1 game)** needs: COCO-pretrained `yolo11n`, `imgsz=640`, `hsv_h=0.0` (hue is the LED class signal — jittering it corrupts the label), and a **temporal (not random) train/val split** so near-duplicate consecutive frames don't leak across the split.
   - **On LED class balance (corrected — do NOT use `copy_paste`):** per-OBJECT the LED is ~1:80 vs stones, but it appears in **211 of 212 frames**, so per-IMAGE it is **not** rare — every training image already teaches the LED class and ~211 instances is adequate coverage for this single-game smoke-test model. Ultralytics `copy_paste` is a **no-op here**: its `CopyPaste` early-returns when `instances.segments` is empty (verified in `ultralytics/data/augment.py`), and our labels are bbox-only (no polygons), so it would silently do nothing — and it is class-agnostic regardless. If LED recall is weak, oversample **offline** (duplicate LED-bearing images / paste LED ROIs onto warp backgrounds) or bump `imgsz`/model size (Task 9), not via the `copy_paste` hyperparameter.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `katrain/vision/classes.py` | **Create** | Single source of truth: ordered class-name list, id↔name maps, `STONE_CLASS_IDS`, `LED_COLOR_TO_CLASS`. |
| `katrain/vision/stone_detector.py` | Modify | `CLASS_NAMES` imports from `classes.py` (adds led_red/led_green). |
| `katrain/vision/board_state.py` | Modify | Guard: skip detections whose `class_id` is not a stone. |
| `katrain/vision/config.py` | Modify | Add `LedAnchorConfig` (HSV thresholds for the LED drift-anchor, so they aren't hardcoded in the labeler). |
| `katrain/vision/tools/baipu_autolabel.py` | **Create** | Warp + reconstruct + drift-correct + 4-class YOLO label writer + verification overlays + CLI. Imports `core.baipu` **lazily** so pure-CV tests need no `.mo`. |
| `katrain/vision/tools/train_model.py` | Modify | Add a `led-safe` augmentation preset (`hsv_h=0` etc.) wired into `cmd_train`. |
| `katrain/vision/tools/prepare_dataset.py` | Modify | `write_data_yaml` uses `classes.py`; add `temporal_split_dataset`. |
| `katrain/vision/tools/download_dataset.py` | Modify | `write_data_yaml` uses `classes.py`. |
| `katrain/vision/tools/data_template.yaml` | Modify | `nc: 4` + 4 names. |
| `katrain/vision/README.md` | Modify | Document 4 classes + the baipu-labeling + training runbook. |
| `tests/test_vision/test_classes.py` | **Create** | Lock class order/ids. |
| `tests/test_vision/test_board_state.py` | **Modify (append)** | LED-detection guard (file already exists — append a new test class, do NOT overwrite). |
| `tests/test_vision/test_prepare_dataset.py` | **Modify** | Update stale `nc: 2` assertion → `nc: 4`; append temporal-split test (file already exists). |
| `tests/test_vision/test_download_dataset.py` | **Modify** | Update stale `nc: 2` assertion → `nc: 4` (file already exists). |
| `tests/test_vision/test_train_model.py` | **Create** | Lock the `led-safe` augmentation kwargs (esp. `hsv_h == 0.0`). |
| `tests/test_vision/test_baipu_autolabel.py` | **Create** | **CI-runnable pure-CV unit tests** (grid math, box sizing/clipping, YOLO format, LED-centroid + shift recovery/carry-forward on synthetic in-memory images) **plus** `@requires_capture` real-data integration tests (load/reconstruct/process_game against `kifu_24171`). |

---

## Task 1: Single source of truth for the 4 classes

**Files:**
- Create: `katrain/vision/classes.py`
- Test: `tests/test_vision/test_classes.py`
- Modify: `katrain/vision/stone_detector.py:12`

**Interfaces:**
- Produces: `CLASS_NAMES: list[str]` (ordered), `NAME_TO_ID: dict[str,int]`, `ID_TO_NAME: dict[int,str]`, `STONE_CLASS_IDS: frozenset[int]` = `{0,1}`, `LED_COLOR_TO_CLASS: dict[str,int]` = `{"black":2,"white":3}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vision/test_classes.py
from katrain.vision.classes import (
    CLASS_NAMES, NAME_TO_ID, ID_TO_NAME, STONE_CLASS_IDS, LED_COLOR_TO_CLASS,
)


def test_class_order_is_fixed():
    assert CLASS_NAMES == ["black", "white", "led_red", "led_green"]


def test_id_maps_round_trip():
    assert NAME_TO_ID == {"black": 0, "white": 1, "led_red": 2, "led_green": 3}
    assert ID_TO_NAME == {0: "black", 1: "white", 2: "led_red", 3: "led_green"}


def test_stone_ids_exclude_leds():
    assert STONE_CLASS_IDS == frozenset({0, 1})


def test_led_color_maps_black_to_red_white_to_green():
    # red guides the next BLACK move, green guides the next WHITE move
    assert LED_COLOR_TO_CLASS == {"black": 2, "white": 3}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `CI=true uv run pytest tests/test_vision/test_classes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'katrain.vision.classes'`

- [ ] **Step 3: Create `katrain/vision/classes.py`**

```python
"""Single source of truth for YOLO detection classes.

Order is load-bearing: it IS the YOLO class-id order. black=0, white=1,
led_red=2, led_green=3. Red LED guides the next BLACK move; green LED guides
the next WHITE move (see manifest led_point.color).
"""

CLASS_NAMES: list[str] = ["black", "white", "led_red", "led_green"]

NAME_TO_ID: dict[str, int] = {name: i for i, name in enumerate(CLASS_NAMES)}
ID_TO_NAME: dict[int, str] = {i: name for i, name in enumerate(CLASS_NAMES)}

# Board-stone classes (everything else is guidance, not a stone on the board).
STONE_CLASS_IDS: frozenset[int] = frozenset({NAME_TO_ID["black"], NAME_TO_ID["white"]})

# manifest led_point.color (the color about to be played) -> LED class id.
LED_COLOR_TO_CLASS: dict[str, int] = {
    "black": NAME_TO_ID["led_red"],
    "white": NAME_TO_ID["led_green"],
}
```

- [ ] **Step 4: Update `stone_detector.py` to use the shared constant**

Replace `CLASS_NAMES = {0: "black", 1: "white"}` (line 12) with:

```python
from katrain.vision.classes import ID_TO_NAME as CLASS_NAMES  # {0:'black',1:'white',2:'led_red',3:'led_green'}
```

(Keep the existing `Detection.class_name` lookup — it now resolves all four ids; the `unknown_{id}` fallback stays for safety.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `CI=true uv run pytest tests/test_vision/test_classes.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add katrain/vision/classes.py katrain/vision/stone_detector.py tests/test_vision/test_classes.py
git commit -m "feat(vision): add 4-class single source of truth (black/white/led_red/led_green)"
```

---

## Task 2: Runtime guard — LED detections must not corrupt board state

**Files:**
- Modify: `katrain/vision/board_state.py:23-35`
- Test: `tests/test_vision/test_board_state.py` — **this file already exists** (`TestBoardStateConstants`, `TestDetectionsToBoard`, `TestBoardToString`). **APPEND** the new test class below; do NOT overwrite.

**Interfaces:**
- Consumes: `katrain.vision.classes.STONE_CLASS_IDS`, `katrain.vision.stone_detector.Detection`.
- Note: `Detection` fields are `(x_center, y_center, class_id, confidence, bbox=(x1,y1,x2,y2))` — there is **no** `width`/`height` kwarg (verified at `stone_detector.py:15-23`). Construct it exactly as the existing tests do.
- Produces: `BoardStateExtractor.detections_to_board` ignores any detection whose `class_id ∉ STONE_CLASS_IDS`.

- [ ] **Step 1: Append the failing test class to the existing file**

```python
# APPEND to tests/test_vision/test_board_state.py (existing imports already cover np/BLACK/WHITE/Detection)


class TestLedGuard:
    def _det(self, x, y, class_id, conf=0.9):
        return Detection(x_center=x, y_center=y, class_id=class_id, confidence=conf)

    def test_led_detections_are_ignored(self):
        ex = BoardStateExtractor()
        img = 950
        # a black stone at grid (0,0) -> pixel ~ (0,0); a red LED (class 2) at grid (1,1)
        dets = [self._det(2, 2, 0), self._det(int(1 / 18 * img), int(1 / 18 * img), 2)]
        board = ex.detections_to_board(dets, img_w=img, img_h=img)
        assert board[0][0] == BLACK
        # LED (class_id=2) must NOT have written anything (would have been 3 with the +1 bug)
        assert set(int(v) for v in np.unique(board)) <= {0, BLACK, WHITE}
        assert board[1][1] == 0

    def test_white_still_maps_to_white(self):
        ex = BoardStateExtractor()
        board = ex.detections_to_board([self._det(2, 2, 1)], img_w=950, img_h=950)
        assert board[0][0] == WHITE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `CI=true uv run pytest tests/test_vision/test_board_state.py -v`
Expected: FAIL — `test_led_detections_are_ignored` asserts `board[1][1]==0` but current code writes `2+1=3` there.

- [ ] **Step 3: Add the guard in `detections_to_board`**

In `katrain/vision/board_state.py`, add the import at top:

```python
from katrain.vision.classes import STONE_CLASS_IDS
```

and inside the `for det in detections:` loop (before the `pixel_to_physical` call) add:

```python
            if det.class_id not in STONE_CLASS_IDS:
                continue  # LED guidance classes (led_red/led_green) are not board stones
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `CI=true uv run pytest tests/test_vision/test_board_state.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add katrain/vision/board_state.py tests/test_vision/test_board_state.py
git commit -m "fix(vision): ignore LED detections in board-state extraction so they don't write phantom stones"
```

---

## Task 3: Capture loader + warped grid + board reconstruction

**Files:**
- Create: `katrain/vision/tools/baipu_autolabel.py` (start the module)
- Test: `tests/test_vision/test_baipu_autolabel.py`

**Interfaces:**
- Consumes: `katrain.core.baipu.build_steps_from_sgf`, `expected_board_from_steps` (**imported lazily inside `load_capture`/`reconstruct_board`, NOT at module top** — keeps `import baipu_autolabel` free of the `core.lang`/i18n chain so pure-CV tests run with no `.mo`); `numpy`, `cv2`.
- Produces:
  - `@dataclass Capture` with: `game_dir: Path`, `manifest: dict`, `steps: list[dict]`, `M: np.ndarray (3x3)`, `out_size: int`, `xs: np.ndarray (19,)`, `ys: np.ndarray (19,)`.
  - `load_capture(game_dir: Path) -> Capture`
  - `warp_frame(frame_bgr: np.ndarray, M: np.ndarray, out_size: int) -> np.ndarray`
  - `grid_point(row: int, col: int, xs, ys) -> tuple[float, float]` → warped `(x, y)`
  - `reconstruct_board(steps, applied_move_index: int) -> list[list[str | None]]` (19×19 of `'B'`/`'W'`/`None`)
  - `mean_grid_spacing(xs, ys) -> float`

- [ ] **Step 1: Write the failing tests (CI-runnable synthetic + `@requires_capture` real-data)**

The pure-CV tests use a synthetic grid faithful to the real capture (`np.linspace(0, 949, 19)` matches `kifu_24171`'s `xs`/`ys` to <1e-4) and **do not touch `load_capture`/`reconstruct_board`**, so they run in CI with no fixture and no `.mo`. Only the `@requires_capture` tests (which parse the SGF) need the real game + the i18n build.

```python
# tests/test_vision/test_baipu_autolabel.py
from pathlib import Path
import os
import numpy as np
import pytest
import cv2

from katrain.vision.tools import baipu_autolabel as bal

GAME = Path(os.path.expanduser("~/.katrain/baipu_captures/kifu_24171"))
# Decorate ONLY the SGF-parse / real-data tests with this — NOT a module-level pytestmark,
# so the synthetic pure-CV tests below always run in CI.
requires_capture = pytest.mark.skipif(not GAME.exists(), reason="baipu capture fixture not present (real-data integration)")

# Synthetic grid — faithful to kifu_24171 (out_size 950, spacing ~52.72).
SYNTH_XS = np.linspace(0.0, 949.0, 19)
SYNTH_YS = np.linspace(0.0, 949.0, 19)


# ---------- pure-CV unit tests (CI: no fixture, no .mo) ----------

def test_grid_point_corner_and_topright():
    x0, y0 = bal.grid_point(0, 0, SYNTH_XS, SYNTH_YS)
    assert (round(x0), round(y0)) == (0, 0)
    x, y = bal.grid_point(0, 18, SYNTH_XS, SYNTH_YS)
    assert round(x) == 949 and round(y) == 0  # row=0 top, col=18 right


def test_mean_grid_spacing():
    assert abs(bal.mean_grid_spacing(SYNTH_XS, SYNTH_YS) - 52.72) < 0.5


# ---------- real-data integration tests (skip without fixture; need .mo) ----------

@requires_capture
def test_load_capture_shapes():
    cap = bal.load_capture(GAME)
    assert cap.out_size == 950
    assert cap.xs.shape == (19,) and cap.ys.shape == (19,)
    assert cap.M.shape == (3, 3)
    assert cap.manifest["board_size"] == 19
    assert len(cap.steps) >= cap.manifest["total_moves"]


@requires_capture
def test_reconstruct_board_matches_move_index_minus_captures():
    cap = bal.load_capture(GAME)
    # frame_040: applied_move_index=39 -> 40 placements minus captures.
    board = bal.reconstruct_board(cap.steps, 39)
    n_black = sum(c == "B" for row in board for c in row)
    n_white = sum(c == "W" for row in board for c in row)
    assert (n_black, n_white) == (20, 20)  # 40 moves, no captures yet at move 40


@requires_capture
def test_reconstruct_board_handles_captures_by_final_move():
    cap = bal.load_capture(GAME)
    board = bal.reconstruct_board(cap.steps, 210)  # final position of a 211-move game
    total = sum(c is not None for row in board for c in row)
    assert total == 205  # 211 placements - 6 captured (verified)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `CI=true uv run pytest tests/test_vision/test_baipu_autolabel.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'katrain.vision.tools.baipu_autolabel'` (the module is created in Step 3; once it exists but a function is missing you'll instead see `AttributeError`). Because of the lazy import (Step 3), the **pure-CV tests need no `.mo`**. The `@requires_capture` tests will additionally **SKIP** unless `~/.katrain/baipu_captures/kifu_24171` exists; to run them, build the i18n catalog once first (they parse the SGF → `core.baipu`):
```bash
uv run python i18n.py   # one-time; compiles katrain/i18n/locales/*/LC_MESSAGES/katrain.mo
```

- [ ] **Step 3: Create the module with the loader/reconstruction**

```python
"""Auto-label baipu capture frames for 4-class YOLO training.

Unlike auto_label.py (HSV-guess on warped images, 2 classes), this uses the
SGF GROUND TRUTH + frozen board geometry to place exact 4-class boxes
(black, white, led_red, led_green) in the rectified 950x950 board space that
worker.py feeds the detector. See
superpowers/tracks/yolo-train/2026-06-23-yolo-4class-autolabel-train-plan.md
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

# load_capture/reconstruct_board lazily import katrain.core.baipu, which pulls in Kivy.
# Kivy parses sys.argv on import and would hijack the Task 6 CLI's --game-dir/--out-* flags;
# KIVY_NO_ARGS=1 disables that (same pattern as katrain/__main__.py).
os.environ.setdefault("KIVY_NO_ARGS", "1")

import cv2
import numpy as np

# NOTE: katrain.core.baipu is imported LAZILY inside load_capture / reconstruct_board.
# Importing it at module top would pull in katrain.core.game -> katrain.core.lang, which
# instantiates gettext at import and raises FileNotFoundError when the i18n .mo files are
# absent — breaking the pure-CV unit tests that never parse an SGF. Keep it lazy.


@dataclass
class Capture:
    game_dir: Path
    manifest: dict
    steps: list[dict]
    M: np.ndarray
    out_size: int
    xs: np.ndarray
    ys: np.ndarray


def load_capture(game_dir: Path) -> Capture:
    from katrain.core.baipu import build_steps_from_sgf  # lazy: avoids i18n import at module load

    game_dir = Path(game_dir)
    manifest = json.loads((game_dir / "manifest.json").read_text())
    sgf = (game_dir / (manifest.get("sgf_path") or "game.sgf")).read_text()
    steps = build_steps_from_sgf(sgf)["steps"]
    geo = np.load(game_dir / (manifest.get("geometry_path") or "geometry.npz"), allow_pickle=True)
    return Capture(
        game_dir=game_dir,
        manifest=manifest,
        steps=steps,
        M=np.asarray(geo["M"], dtype=np.float64),
        out_size=int(geo["out_size"]),
        xs=np.asarray(geo["xs"], dtype=np.float64),
        ys=np.asarray(geo["ys"], dtype=np.float64),
    )


def warp_frame(frame_bgr: np.ndarray, M: np.ndarray, out_size: int) -> np.ndarray:
    """Rectify a raw camera frame to the out_size square board (deployment space)."""
    return cv2.warpPerspective(frame_bgr, M, (out_size, out_size))


def grid_point(row: int, col: int, xs: np.ndarray, ys: np.ndarray) -> tuple[float, float]:
    """Warped-image (x, y) of canonical intersection (row, col). Direct, no flip."""
    return float(xs[col]), float(ys[row])


def reconstruct_board(steps: list[dict], applied_move_index: int) -> list[list[str | None]]:
    """19x19 of 'B'/'W'/None after applying steps[0..applied_move_index] (capture-aware)."""
    from katrain.core.baipu import expected_board_from_steps  # lazy: avoids i18n import at module load

    return expected_board_from_steps(steps, applied_move_index, 19)


def mean_grid_spacing(xs: np.ndarray, ys: np.ndarray) -> float:
    return float(np.mean([np.mean(np.diff(xs)), np.mean(np.diff(ys))]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `CI=true uv run pytest tests/test_vision/test_baipu_autolabel.py -v`
Expected: the 2 pure-CV tests PASS (in CI, no fixture/`.mo`); the 3 `@requires_capture` tests PASS locally where `~/.katrain/baipu_captures/kifu_24171` exists **and** the `.mo` files are built, otherwise SKIP. Net: `2 passed, 3 skipped` on a bare runner; `5 passed` locally.

- [ ] **Step 5: Commit**

```bash
git add katrain/vision/tools/baipu_autolabel.py tests/test_vision/test_baipu_autolabel.py
git commit -m "feat(vision): baipu capture loader + capture-aware board reconstruction in warped space"
```

---

## Task 4: Per-frame global board-drift compensation

**Files:**
- Modify: `katrain/vision/config.py` (add `LedAnchorConfig` — HSV thresholds, not hardcoded in the labeler)
- Modify: `katrain/vision/tools/baipu_autolabel.py`
- Test: `tests/test_vision/test_baipu_autolabel.py` (append)

**Interfaces:**
- Consumes: `Capture`, `grid_point`, `mean_grid_spacing`, `reconstruct_board`, `katrain.vision.config.LedAnchorConfig`.
- Produces:
  - `@dataclass LedAnchorConfig` (in `config.py`): `red_hue_hi=12, red_hue_lo=168, green_hue_lo=40, green_hue_hi=90, s_min=80, v_min=120` — the HSV thresholds the LED drift-anchor uses, so light/camera changes are a config edit, not a code edit.
  - `detect_led_centroid(warped_bgr, gx, gy, search_px, color: str, cfg: LedAnchorConfig | None = None) -> tuple[float,float] | None` — brightest red/green blob near `(gx,gy)`; thresholds come from `cfg` (defaults to `LedAnchorConfig()`).
  - `detect_isolated_stone_centroids(warped_bgr, board, xs, ys, spacing) -> list[tuple[grid_pt, centroid]]` — Hough-circle centroid for stones with no occupied 4-neighbor.
  - `@dataclass ShiftReport(dx, dy, anchor_count: int, led_found: bool, residual_px: float, fallback_used: bool)`.
  - `estimate_global_shift(warped_bgr, board, led_point, xs, ys, spacing, prev_shift=(0.0,0.0), cfg=None) -> ShiftReport` — robust median of `(centroid − grid_point)` over the LED + isolated stones, clamped to `|shift| ≤ 0.6·spacing`. **On zero anchors it carries forward `prev_shift`** (NOT unconditional `(0,0)`) and sets `fallback_used=True`; `residual_px` is the MAD of anchor deltas about the median.

> **Why carry-forward, not `(0,0)`:** the LED HSV detection here feeds **only the drift anchor** — the LED's *class and position* come from manifest ground truth (Task 5), so HSV failure never mislabels the LED, it just loses one anchor. Drift is empirically piecewise-constant (one ~16 px jump at move ~85). The single post-jump frame that can have zero anchors is the full-board final frame (no LED, no isolated stones); `(0,0)` there would misalign every box by ~16 px, whereas carrying forward the previous frame's shift inherits the correct offset. `(0,0)` is correct only for the pre-drift first frame, which is exactly `prev_shift`'s default. A position-dependent/parallax model was measured and rejected (no correlation with image position). HSV thresholds are parameterized (`LedAnchorConfig`) so a second board/light is a config change; this is a Major robustness hardening, not a Blocker (HSV never touches labels).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_vision/test_baipu_autolabel.py

# ---------- pure-CV unit tests (CI: no fixture, no .mo) ----------

def test_detect_led_centroid_finds_green_blob():
    spacing = bal.mean_grid_spacing(SYNTH_XS, SYNTH_YS)
    img = np.zeros((950, 950, 3), dtype=np.uint8)
    gx, gy = bal.grid_point(9, 9, SYNTH_XS, SYNTH_YS)
    cv2.circle(img, (int(gx) + 4, int(gy) - 3), 6, (0, 255, 0), -1)  # green (BGR) blob
    c = bal.detect_led_centroid(img, gx, gy, int(0.7 * spacing), "white")  # white move -> green LED
    assert c is not None
    assert abs(c[0] - (gx + 4)) < 3 and abs(c[1] - (gy - 3)) < 3


def test_estimate_global_shift_recovers_known_translation():
    # LED-only anchor: deterministic (HSV centroid), no Hough flakiness.
    spacing = bal.mean_grid_spacing(SYNTH_XS, SYNTH_YS)
    img = np.zeros((950, 950, 3), dtype=np.uint8)
    led = {"row": 9, "col": 9, "color": "white"}  # green LED
    gx, gy = bal.grid_point(9, 9, SYNTH_XS, SYNTH_YS)
    tx, ty = 8.0, -5.0
    cv2.circle(img, (int(gx + tx), int(gy + ty)), 6, (0, 255, 0), -1)
    empty = [[None] * 19 for _ in range(19)]
    rep = bal.estimate_global_shift(img, empty, led, SYNTH_XS, SYNTH_YS, spacing)
    assert abs(rep.dx - tx) < 0.1 * spacing and abs(rep.dy - ty) < 0.1 * spacing
    assert rep.led_found and rep.anchor_count >= 1 and not rep.fallback_used


def test_estimate_global_shift_carry_forward_on_no_anchor():
    spacing = bal.mean_grid_spacing(SYNTH_XS, SYNTH_YS)
    blank = np.zeros((950, 950, 3), dtype=np.uint8)
    empty = [[None] * 19 for _ in range(19)]
    rep = bal.estimate_global_shift(blank, empty, None, SYNTH_XS, SYNTH_YS, spacing, prev_shift=(5.0, -3.0))
    assert (rep.dx, rep.dy) == (5.0, -3.0) and rep.fallback_used and rep.anchor_count == 0
    rep0 = bal.estimate_global_shift(blank, empty, None, SYNTH_XS, SYNTH_YS, spacing)
    assert (rep0.dx, rep0.dy) == (0.0, 0.0)  # first frame: default prev_shift


# ---------- real-data integration test (skip without fixture; need .mo) ----------

@requires_capture
def test_estimate_global_shift_is_small_and_clamped():
    cap = bal.load_capture(GAME)
    spacing = bal.mean_grid_spacing(cap.xs, cap.ys)
    fr = next(f for f in cap.manifest["frames"] if f["file"] == "frame_040.jpg")
    img = cv2.imread(str(GAME / fr["file"]))
    warped = bal.warp_frame(img, cap.M, cap.out_size)
    board = bal.reconstruct_board(cap.steps, fr["applied_move_index"])
    rep = bal.estimate_global_shift(warped, board, fr["led_point"], cap.xs, cap.ys, spacing)
    assert abs(rep.dx) <= 0.6 * spacing and abs(rep.dy) <= 0.6 * spacing
    assert rep.anchor_count >= 1  # frame_040 has the guide LED + isolated stones
```

- [ ] **Step 2: Run test to verify it fails**

Run: `CI=true uv run pytest tests/test_vision/test_baipu_autolabel.py -k "shift or centroid" -v`
Expected: FAIL — `AttributeError: ... has no attribute 'estimate_global_shift'` (or `detect_led_centroid`). These pure-CV tests need no `.mo` and no fixture.

- [ ] **Step 3a: Add `LedAnchorConfig` to `katrain/vision/config.py`**

Append a dataclass next to the existing `BoardConfig`/`CameraConfig` (match the file's `@dataclass` style):

```python
@dataclass
class LedAnchorConfig:
    """HSV thresholds for locating the guide LED as a drift anchor (NOT for labeling —
    the LED's class/position come from manifest ground truth). Parameterized so a new
    board/light is a config edit, not a code change. Red hue wraps 0/180."""

    red_hue_hi: int = 12
    red_hue_lo: int = 168
    green_hue_lo: int = 40
    green_hue_hi: int = 90
    s_min: int = 80
    v_min: int = 120
```

- [ ] **Step 3b: Implement the detectors + shift estimator (with `ShiftReport` + carry-forward)**

```python
# add to katrain/vision/tools/baipu_autolabel.py
from katrain.vision.config import LedAnchorConfig


def detect_led_centroid(warped_bgr, gx, gy, search_px, color, cfg: LedAnchorConfig | None = None):
    """Brightest saturated red/green blob within search_px of (gx,gy). None if not found.

    Thresholds come from cfg (parameterized so a new light/camera is a config edit).
    """
    cfg = cfg or LedAnchorConfig()
    h, w = warped_bgr.shape[:2]
    x0, y0 = max(0, int(gx - search_px)), max(0, int(gy - search_px))
    x1, y1 = min(w, int(gx + search_px)), min(h, int(gy + search_px))
    roi = warped_bgr[y0:y1, x0:x1]
    if roi.size == 0:
        return None
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    s, v = hsv[:, :, 1], hsv[:, :, 2]
    hue = hsv[:, :, 0]
    bright = (s > cfg.s_min) & (v > cfg.v_min)
    if color == "black":  # red LED: hue wraps around 0/180
        mask = bright & ((hue < cfg.red_hue_hi) | (hue > cfg.red_hue_lo))
    else:                 # white move -> green LED
        mask = bright & (hue > cfg.green_hue_lo) & (hue < cfg.green_hue_hi)
    if mask.sum() < 4:
        return None
    ys_, xs_ = np.nonzero(mask)
    weights = v[ys_, xs_].astype(np.float64)
    cx = float(np.average(xs_, weights=weights)) + x0
    cy = float(np.average(ys_, weights=weights)) + y0
    return cx, cy


def _has_occupied_neighbor(board, r, c):
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        rr, cc = r + dr, c + dc
        if 0 <= rr < 19 and 0 <= cc < 19 and board[rr][cc] is not None:
            return True
    return False


def detect_isolated_stone_centroids(warped_bgr, board, xs, ys, spacing):
    """Hough-circle centroid for stones with no occupied 4-neighbor (avoids cluster drag)."""
    gray = cv2.cvtColor(warped_bgr, cv2.COLOR_BGR2GRAY)
    r = max(6, int(0.45 * spacing))
    out = []
    half = int(0.7 * spacing)
    for rr in range(19):
        for cc in range(19):
            if board[rr][cc] is None or _has_occupied_neighbor(board, rr, cc):
                continue
            gx, gy = grid_point(rr, cc, xs, ys)
            x0, y0 = max(0, int(gx - half)), max(0, int(gy - half))
            x1, y1 = min(gray.shape[1], int(gx + half)), min(gray.shape[0], int(gy + half))
            patch = gray[y0:y1, x0:x1]
            if patch.size == 0:
                continue
            circles = cv2.HoughCircles(
                patch, cv2.HOUGH_GRADIENT, dp=1.2, minDist=2 * r,
                param1=120, param2=18, minRadius=int(0.6 * r), maxRadius=int(1.4 * r),
            )
            if circles is None:
                continue
            c0 = circles[0][0]
            out.append(((gx, gy), (float(c0[0]) + x0, float(c0[1]) + y0)))
    return out


@dataclass
class ShiftReport:
    dx: float
    dy: float
    anchor_count: int
    led_found: bool
    residual_px: float   # MAD of anchor deltas about the median (anchor agreement)
    fallback_used: bool  # True when no anchors -> prev_shift was carried forward


def estimate_global_shift(warped_bgr, board, led_point, xs, ys, spacing, prev_shift=(0.0, 0.0), cfg=None):
    """Robust per-frame drift = median(detected_centroid - grid_point) over anchors.

    On zero anchors, carry forward prev_shift (NOT (0,0)) so a single anchor-less frame
    mid-game (e.g. the full-board final frame) inherits the correct ~16px offset instead
    of snapping back to the un-drifted grid. Returns a ShiftReport.
    """
    deltas = []
    led_found = False
    if led_point is not None:
        gx, gy = grid_point(led_point["row"], led_point["col"], xs, ys)
        led = detect_led_centroid(warped_bgr, gx, gy, int(0.7 * spacing), led_point["color"], cfg)
        if led is not None:
            deltas.append((led[0] - gx, led[1] - gy))
            led_found = True
    for (gx, gy), (cx, cy) in detect_isolated_stone_centroids(warped_bgr, board, xs, ys, spacing):
        deltas.append((cx - gx, cy - gy))
    if not deltas:
        return ShiftReport(float(prev_shift[0]), float(prev_shift[1]), 0, led_found, 0.0, True)
    arr = np.asarray(deltas, dtype=np.float64)
    dx, dy = float(np.median(arr[:, 0])), float(np.median(arr[:, 1]))
    residual = float(np.median(np.abs(arr - np.array([dx, dy]))))  # MAD
    lim = 0.6 * spacing
    dx, dy = float(np.clip(dx, -lim, lim)), float(np.clip(dy, -lim, lim))
    return ShiftReport(dx, dy, len(deltas), led_found, residual, False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `CI=true uv run pytest tests/test_vision/test_baipu_autolabel.py -k "shift or centroid" -v`
Expected: the 3 pure-CV tests PASS in CI (no fixture/`.mo`); the `@requires_capture` clamp test SKIPs without the game. Locally with the fixture + `.mo`: all pass.

- [ ] **Step 5: Commit**

```bash
git add katrain/vision/config.py katrain/vision/tools/baipu_autolabel.py tests/test_vision/test_baipu_autolabel.py
git commit -m "feat(vision): per-frame board-drift compensation (ShiftReport, carry-forward, configurable LED-anchor HSV)"
```

---

## Task 5: 4-class box generation + YOLO label writing + verification overlays

**Files:**
- Modify: `katrain/vision/tools/baipu_autolabel.py`
- Test: `tests/test_vision/test_baipu_autolabel.py` (append)

**Interfaces:**
- Consumes: `Capture`, `grid_point`, `estimate_global_shift`, `mean_grid_spacing`, `katrain.vision.classes` (`LED_COLOR_TO_CLASS`, `NAME_TO_ID`).
- Produces:
  - `@dataclass Box(class_id:int, cx:float, cy:float, w:float, h:float)` — pixel units.
  - `frame_boxes(board, led_point, xs, ys, shift, spacing, stone_frac=1.05, led_frac=0.45, img_w=950, img_h=950) -> list[Box]` — one box per stone (class 0/1) sized `clip(stone_frac*spacing, 40, 70)` px (~55) + one **tight** box for the LED (class 2/3) sized `clip(led_frac*spacing, 16, 36)` px (~24) if `led_point` is not None; centered on `grid_point + shift`; **each box clipped to `[0,img_w]×[0,img_h]`** (corner stones at `(0,0)`/`(949,949)` get a half-size in-frame box, not one hanging off-image).
  - `boxes_to_yolo_lines(boxes, img_w, img_h) -> list[str]` — `class cx cy w h` normalized 0–1, 6dp.
  - `draw_overlay(warped_bgr, boxes) -> np.ndarray` — colored boxes for human spot-check.

> **Why separate, tighter, clipped boxes (was a uniform ~90 px box):** deployment snaps on the box **center only** (`board_state.detections_to_board` → `pixel_to_physical` → `physical_to_grid`; `det.bbox` is never read for board state), so an oversized *stone* box doesn't corrupt deploy — but it does degrade training localization and overlaps neighbors (~0.26 IoU at 90 px vs ~0.05 at 1.1·spacing). For the **LED** (the whole point of this retrain, and the small-target success metric) a 90 px box is ~92 % board texture, sabotaging recall — so the LED box is tight. The old "absorb drift with generous boxes" rationale is moot now that Task 4 drives residual <0.2·spacing. Corner clipping fixes malformed off-image labels.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_vision/test_baipu_autolabel.py
from katrain.vision.classes import NAME_TO_ID

# ---------- pure-CV unit tests (CI: no fixture, no .mo) ----------

def test_frame_boxes_stone_and_led_sizes():
    spacing = bal.mean_grid_spacing(SYNTH_XS, SYNTH_YS)
    board = [[None] * 19 for _ in range(19)]
    board[9][9] = "W"
    led = {"row": 3, "col": 3, "color": "black"}  # -> led_red
    boxes = bal.frame_boxes(board, led, SYNTH_XS, SYNTH_YS, (0.0, 0.0), spacing)
    stone = next(b for b in boxes if b.class_id in (0, 1))
    led_box = next(b for b in boxes if b.class_id in (2, 3))
    assert 40 <= stone.w <= 70 and stone.class_id == NAME_TO_ID["white"]
    assert led_box.class_id == NAME_TO_ID["led_red"]
    assert led_box.w <= 36 and led_box.w < stone.w  # LED box is tight, smaller than a stone


def test_corner_box_is_clipped_into_image():
    spacing = bal.mean_grid_spacing(SYNTH_XS, SYNTH_YS)
    board = [[None] * 19 for _ in range(19)]
    board[0][0] = "B"  # grid (0,0) -> pixel (0,0); an unclipped box would hang off-frame
    boxes = bal.frame_boxes(board, None, SYNTH_XS, SYNTH_YS, (0.0, 0.0), spacing)
    b = boxes[0]
    assert b.cx - b.w / 2 >= -0.01 and b.cy - b.h / 2 >= -0.01  # fully inside image
    stone_side = min(max(1.05 * spacing, 40.0), 70.0)
    assert abs(b.w - stone_side / 2) < 1.0  # exactly the off-image half was clipped


def test_boxes_to_yolo_lines_format_and_range():
    boxes = [bal.Box(class_id=3, cx=475.0, cy=475.0, w=90.0, h=90.0)]
    lines = bal.boxes_to_yolo_lines(boxes, 950, 950)
    assert lines == ["3 0.500000 0.500000 0.094737 0.094737"]


# ---------- real-data integration tests (skip without fixture; need .mo) ----------

@requires_capture
def test_frame_boxes_counts_and_led_class():
    cap = bal.load_capture(GAME)
    spacing = bal.mean_grid_spacing(cap.xs, cap.ys)
    fr = next(f for f in cap.manifest["frames"] if f["file"] == "frame_040.jpg")
    board = bal.reconstruct_board(cap.steps, fr["applied_move_index"])
    boxes = bal.frame_boxes(board, fr["led_point"], cap.xs, cap.ys, (0.0, 0.0), spacing)
    stones = [b for b in boxes if b.class_id in (0, 1)]
    leds = [b for b in boxes if b.class_id in (2, 3)]
    assert len(stones) == 40
    # frame_040 led_point.color == "black" -> led_red (2)
    assert len(leds) == 1 and leds[0].class_id == NAME_TO_ID["led_red"]


@requires_capture
def test_final_frame_has_no_led_box():
    cap = bal.load_capture(GAME)
    spacing = bal.mean_grid_spacing(cap.xs, cap.ys)
    fr = next(f for f in cap.manifest["frames"] if f["file"] == "frame_211.jpg")
    board = bal.reconstruct_board(cap.steps, fr["applied_move_index"])
    boxes = bal.frame_boxes(board, fr["led_point"], cap.xs, cap.ys, (0.0, 0.0), spacing)
    assert all(b.class_id in (0, 1) for b in boxes)  # final_no_led frame
```

- [ ] **Step 2: Run test to verify it fails**

Run: `CI=true uv run pytest tests/test_vision/test_baipu_autolabel.py -k "frame_boxes or corner or yolo_lines" -v`
Expected: FAIL — `frame_boxes`/`Box` not defined. These pure-CV tests need no `.mo`/fixture.

- [ ] **Step 3: Implement box generation, YOLO writer, overlay**

```python
# add to katrain/vision/tools/baipu_autolabel.py
from katrain.vision.classes import ID_TO_NAME, LED_COLOR_TO_CLASS, NAME_TO_ID  # ID_TO_NAME used by process_game stats (Task 6)

_DRAW = {0: (0, 0, 255), 1: (0, 255, 0), 2: (0, 140, 255), 3: (255, 200, 0)}


@dataclass
class Box:
    class_id: int
    cx: float
    cy: float
    w: float
    h: float


def _clip_box(cx, cy, w, h, img_w, img_h):
    """Clip a center box to [0,img_w]x[0,img_h] and return the re-centered (cx,cy,w,h).

    Both endpoints are clamped into bounds, so a box that drifts entirely off an edge
    collapses to zero width/height (caller drops it) rather than producing negative coords.
    """
    x1 = min(max(0.0, cx - w / 2), float(img_w))
    x2 = min(max(0.0, cx + w / 2), float(img_w))
    y1 = min(max(0.0, cy - h / 2), float(img_h))
    y2 = min(max(0.0, cy + h / 2), float(img_h))
    return (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1


def frame_boxes(board, led_point, xs, ys, shift, spacing,
                stone_frac: float = 1.05, led_frac: float = 0.45, img_w: int = 950, img_h: int = 950):
    # Stones ~object-tight (deploy snaps on center; box extent is training-localization only).
    # LEDs tight: a background-dominated box destroys small-target recall (the success metric).
    stone_side = float(np.clip(stone_frac * spacing, 40.0, 70.0))
    led_side = float(np.clip(led_frac * spacing, 16.0, 36.0))
    dx, dy = shift
    boxes: list[Box] = []
    for r in range(19):
        for c in range(19):
            v = board[r][c]
            if v is None:
                continue
            gx, gy = grid_point(r, c, xs, ys)
            cid = NAME_TO_ID["black"] if v == "B" else NAME_TO_ID["white"]
            cx, cy, w, h = _clip_box(gx + dx, gy + dy, stone_side, stone_side, img_w, img_h)
            if w > 0 and h > 0:  # drop stones that drifted entirely off-frame (not visible -> no label)
                boxes.append(Box(cid, cx, cy, w, h))
    if led_point is not None:
        gx, gy = grid_point(led_point["row"], led_point["col"], xs, ys)
        cx, cy, w, h = _clip_box(gx + dx, gy + dy, led_side, led_side, img_w, img_h)
        if w > 0 and h > 0:
            boxes.append(Box(LED_COLOR_TO_CLASS[led_point["color"]], cx, cy, w, h))
    return boxes


def boxes_to_yolo_lines(boxes, img_w, img_h):
    lines = []
    for b in boxes:
        lines.append(
            f"{b.class_id} {b.cx / img_w:.6f} {b.cy / img_h:.6f} {b.w / img_w:.6f} {b.h / img_h:.6f}"
        )
    return lines


def draw_overlay(warped_bgr, boxes):
    vis = warped_bgr.copy()
    for b in boxes:
        x1, y1 = int(b.cx - b.w / 2), int(b.cy - b.h / 2)
        x2, y2 = int(b.cx + b.w / 2), int(b.cy + b.h / 2)
        cv2.rectangle(vis, (x1, y1), (x2, y2), _DRAW[b.class_id], 2)
    return vis
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `CI=true uv run pytest tests/test_vision/test_baipu_autolabel.py -k "frame_boxes or corner or yolo_lines" -v`
Expected: the 3 pure-CV box tests PASS in CI (no fixture/`.mo`); the 2 `@requires_capture` box tests SKIP without the game (pass locally).

- [ ] **Step 5: Commit**

```bash
git add katrain/vision/tools/baipu_autolabel.py tests/test_vision/test_baipu_autolabel.py
git commit -m "feat(vision): 4-class box generation, YOLO label writer, and verification overlays"
```

---

## Task 6: CLI driver — emit images/ + labels/ + verify/ for a game

**Files:**
- Modify: `katrain/vision/tools/baipu_autolabel.py` (add `process_game` + `main`)
- Test: `tests/test_vision/test_baipu_autolabel.py` (append integration test)

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `process_game(game_dir, out_images, out_labels, verify_dir=None, dedup_per_move=True, stone_frac=1.05, led_frac=0.45) -> dict` stats `{frames, written, black, white, led_red, led_green, skipped, shift_fallback}`. Threads each frame's estimated shift into the next call as `prev_shift` (carry-forward, Task 4); counts `shift_fallback` when a frame had zero anchors; when `verify_dir` is set, also writes `verify_dir/shifts.csv` (`frame,dx,dy,anchor_count,led_found,residual_px,fallback_used`) for the QA gate. Writes warped `<game>_<frame>.jpg` to `out_images`, matching `.txt` to `out_labels`, optional overlay to `verify_dir`. `dedup_per_move=True` keeps only one frame per distinct `applied_move_index` (one frame per board state; drops any near-duplicate retakes). **Note on `kifu_24171` specifically:** all 212 frames already have distinct `applied_move_index` (the only retakes — frames 097/098 — were repaired pre-capture; see `manifest.json.bak-before-frame-097-098-repair`), so on this game dedup drops 0 and `written == frames == 212`, `skipped == 0`. The flag is still correct/needed for future multi-retake captures; it's just a no-op here.
  - **Initial frame edge case:** `frame_000.jpg` has `applied_move_index == -1` (empty board) and `frame_kind == "initial_led"` with a `led_point` for the very first move. `reconstruct_board(steps, -1)` returns the empty board (per `expected_board_from_steps` docstring: `k == -1` → empty), so this frame yields **0 stone boxes + 1 LED box** — a valid training sample, not an error. The final frame `frame_211.jpg` is the mirror case (`frame_kind == "final_no_led"`, `led_point is None`) → stones only, no LED box.
  - CLI: `python -m katrain.vision.tools.baipu_autolabel --game-dir DIR [--game-dir DIR ...] --out-images D --out-labels D [--verify-dir D] [--no-dedup] [--stone-frac 1.05] [--led-frac 0.45]`

- [ ] **Step 1: Write the failing integration test**

```python
# append to tests/test_vision/test_baipu_autolabel.py (real-data integration; needs fixture + .mo)
@requires_capture
def test_process_game_writes_matching_labels(tmp_path):
    imgs = tmp_path / "images"
    lbls = tmp_path / "labels"
    verify = tmp_path / "verify"
    stats = bal.process_game(GAME, imgs, lbls, verify_dir=verify, dedup_per_move=True)
    assert stats["written"] == 212  # all frames distinct applied_move_index -> dedup is a no-op here
    # every image has a label file
    img_stems = {p.stem for p in imgs.glob("*.jpg")}
    lbl_stems = {p.stem for p in lbls.glob("*.txt")}
    assert img_stems == lbl_stems
    # 211 frames carry a guide LED, but frame_143's LED is on row 0 and the board drifted ~25px
    # off the top edge, so that LED is genuinely outside the rectified image and is correctly
    # dropped. 210-211 tolerates the sub-pixel boundary. (Verified during execution: 210.)
    assert 210 <= stats["led_red"] + stats["led_green"] <= 211
    assert (verify / "shifts.csv").exists()  # per-frame drift diagnostics for the QA gate
    # every label line is well-formed with class in 0..3
    for txt in lbls.glob("*.txt"):
        for line in txt.read_text().splitlines():
            parts = line.split()
            assert len(parts) == 5 and 0 <= int(parts[0]) <= 3
            assert all(0.0 <= float(x) <= 1.0 for x in parts[1:])
```

- [ ] **Step 2: Run test to verify it fails**

Run (locally, with the fixture + `.mo` built): `CI=true uv run pytest tests/test_vision/test_baipu_autolabel.py -k process_game -v`
Expected: FAIL — `process_game` not defined. This is the one `@requires_capture` test that also parses the SGF, so it needs both the `kifu_24171` fixture and `uv run python i18n.py`; on a bare runner it SKIPs.

- [ ] **Step 3: Implement `process_game` + `main`**

```python
# add to katrain/vision/tools/baipu_autolabel.py
import argparse


def process_game(game_dir, out_images, out_labels, verify_dir=None, dedup_per_move=True,
                 stone_frac=1.05, led_frac=0.45):
    game_dir = Path(game_dir)
    out_images, out_labels = Path(out_images), Path(out_labels)
    out_images.mkdir(parents=True, exist_ok=True)
    out_labels.mkdir(parents=True, exist_ok=True)
    csv_rows = []
    if verify_dir:
        verify_dir = Path(verify_dir)
        verify_dir.mkdir(parents=True, exist_ok=True)

    cap = load_capture(game_dir)
    spacing = mean_grid_spacing(cap.xs, cap.ys)
    stats = {"frames": 0, "written": 0, "black": 0, "white": 0, "led_red": 0,
             "led_green": 0, "skipped": 0, "shift_fallback": 0}
    seen_move_idx = set()
    gid = cap.manifest.get("game_id", game_dir.name)
    last_shift = (0.0, 0.0)  # carry-forward seed: (0,0) is correct for the pre-drift first frame

    for fr in cap.manifest["frames"]:
        stats["frames"] += 1
        ami = fr["applied_move_index"]
        if dedup_per_move and ami in seen_move_idx:
            stats["skipped"] += 1
            continue
        seen_move_idx.add(ami)
        img = cv2.imread(str(game_dir / fr["file"]))
        if img is None:
            stats["skipped"] += 1
            continue
        warped = warp_frame(img, cap.M, cap.out_size)
        board = reconstruct_board(cap.steps, ami)
        rep = estimate_global_shift(warped, board, fr.get("led_point"), cap.xs, cap.ys, spacing,
                                    prev_shift=last_shift)
        last_shift = (rep.dx, rep.dy)  # next frame inherits this if it has no anchors
        if rep.fallback_used:
            stats["shift_fallback"] += 1
        boxes = frame_boxes(board, fr.get("led_point"), cap.xs, cap.ys, (rep.dx, rep.dy), spacing,
                            stone_frac=stone_frac, led_frac=led_frac, img_w=cap.out_size, img_h=cap.out_size)

        stem = f"{gid}_{Path(fr['file']).stem}"
        cv2.imwrite(str(out_images / f"{stem}.jpg"), warped)
        lines = boxes_to_yolo_lines(boxes, cap.out_size, cap.out_size)
        (out_labels / f"{stem}.txt").write_text("\n".join(lines) + ("\n" if lines else ""))
        if verify_dir:
            cv2.imwrite(str(verify_dir / f"{stem}.jpg"), draw_overlay(warped, boxes))
            csv_rows.append(f"{fr['file']},{rep.dx:.2f},{rep.dy:.2f},{rep.anchor_count},"
                            f"{int(rep.led_found)},{rep.residual_px:.2f},{int(rep.fallback_used)}")

        for b in boxes:
            stats[ID_TO_NAME[b.class_id]] += 1
        stats["written"] += 1

    if verify_dir:
        header = "frame,dx,dy,anchor_count,led_found,residual_px,fallback_used"
        (verify_dir / "shifts.csv").write_text(header + "\n" + "\n".join(csv_rows) + "\n")
    return stats


def main():
    ap = argparse.ArgumentParser(description="Auto-label baipu captures for 4-class YOLO (warped space)")
    ap.add_argument("--game-dir", action="append", required=True, help="baipu capture dir (repeatable)")
    ap.add_argument("--out-images", required=True)
    ap.add_argument("--out-labels", required=True)
    ap.add_argument("--verify-dir", default=None)
    ap.add_argument("--no-dedup", action="store_true", help="keep all frames (default: one per move)")
    ap.add_argument("--stone-frac", type=float, default=1.05, help="stone box side as a fraction of grid spacing")
    ap.add_argument("--led-frac", type=float, default=0.45, help="LED box side as a fraction of grid spacing (tight)")
    args = ap.parse_args()
    total = {}
    for gd in args.game_dir:
        s = process_game(gd, args.out_images, args.out_labels, args.verify_dir,
                         dedup_per_move=not args.no_dedup, stone_frac=args.stone_frac, led_frac=args.led_frac)
        print(f"{gd}: {s}")
        for k, v in s.items():
            total[k] = total.get(k, 0) + v
    print(f"TOTAL: {total}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run (locally): `CI=true uv run pytest tests/test_vision/test_baipu_autolabel.py -k process_game -v`
Expected: PASS (1 passed) locally; SKIP on a bare runner.

- [ ] **Step 5: Generate the real dataset and eyeball the overlays (manual gate)**

Run:
```bash
uv run python -m katrain.vision.tools.baipu_autolabel \
  --game-dir ~/.katrain/baipu_captures/kifu_24171 \
  --out-images /tmp/go4/images_raw --out-labels /tmp/go4/labels_raw \
  --verify-dir /tmp/go4/verify
```
Expected: prints `TOTAL: {...written: 212...}` with `shift_fallback: 0` (every frame has an anchor on this game). **Open 8–10 images in `/tmp/go4/verify/` spanning early/mid/late/final frames** and confirm boxes sit on stones and the LED. Pay special attention to frames after move ~85 (the drift jump) — boxes must still cover the stones thanks to per-frame shift correction. **Also inspect `/tmp/go4/verify/shifts.csv`**: confirm `dx/dy` jump ~16 px around move ~85 and stay small/stable elsewhere, `residual_px` is small (anchors agree), and `fallback_used` is 0 (or, if any, that the carried-forward shift was still correct).

- [ ] **Step 6: Commit**

```bash
git add katrain/vision/tools/baipu_autolabel.py tests/test_vision/test_baipu_autolabel.py
git commit -m "feat(vision): baipu_autolabel CLI — emit warped images + 4-class labels + verify overlays"
```

---

## Task 7: Temporal (leakage-free) train/val split + 4-class data.yaml

**Files:**
- Modify: `katrain/vision/tools/prepare_dataset.py` (use `classes.py`; add `temporal_split_dataset` + `--split-mode`/`--gap` CLI)
- Modify: `katrain/vision/tools/download_dataset.py:130` (use `classes.py`)
- Modify: `katrain/vision/tools/data_template.yaml`
- Modify: `tests/test_vision/test_prepare_dataset.py` — **already exists**; update the stale `nc: 2` assertion and APPEND the temporal-split test.
- Modify: `tests/test_vision/test_download_dataset.py` — **already exists**; update its stale `nc: 2` assertion (line ~80).

**Interfaces:**
- Consumes: `katrain.vision.classes.CLASS_NAMES`.
- Produces:
  - `write_data_yaml(output_dir)` now emits `nc: {len(CLASS_NAMES)}` and `names: {CLASS_NAMES}`.
  - `temporal_split_dataset(image_dir, label_dir, output_dir, train_ratio=0.8, gap=3) -> dict` — sorts images by filename (frame order), assigns the **first** `train_ratio` contiguous block to train and the **tail** to val, **dropping `gap` frames at the boundary** so no near-duplicate straddles the split.

> **Why not the existing random `split_dataset`?** All frames come from one continuous game; consecutive frames are near-identical. A random split puts frame N in train and N+1 in val → memorized val → meaningless mAP. A contiguous temporal holdout with a discarded boundary gap fixes this. (Even so, val still shares one board/camera/light — treat val mAP as optimistic until a second capture session exists.)

- [ ] **Step 1: Update the two stale `nc: 2` assertions in existing tests**

In `tests/test_vision/test_prepare_dataset.py`, the existing `test_writes_yaml` (≈ line 137-140) asserts `assert "nc: 2" in content`. Change it to:

```python
    def test_writes_yaml(self, tmp_path):
        write_data_yaml(tmp_path)
        content = (tmp_path / "data.yaml").read_text()
        assert "nc: 4" in content
        assert "led_red" in content and "led_green" in content
```

In `tests/test_vision/test_download_dataset.py`, the `test_data_yaml_created` test (≈ line 80) likewise asserts `"nc: 2"` — change that assertion to `assert "nc: 4" in content`.

- [ ] **Step 2: Append the temporal-split test to the existing `test_prepare_dataset.py`**

```python
# APPEND to tests/test_vision/test_prepare_dataset.py
from katrain.vision.tools.prepare_dataset import temporal_split_dataset


def _make_frames(tmp, n):
    img_dir, lbl_dir = tmp / "img", tmp / "lbl"
    img_dir.mkdir(); lbl_dir.mkdir()
    for i in range(n):
        (img_dir / f"f_{i:03d}.jpg").write_bytes(b"\xff\xd8\xff\xd9")
        (lbl_dir / f"f_{i:03d}.txt").write_text("0 0.5 0.5 0.1 0.1\n")
    return img_dir, lbl_dir


def test_temporal_split_has_no_boundary_leak(tmp_path):
    img_dir, lbl_dir = _make_frames(tmp_path, 100)
    out = tmp_path / "ds"
    stats = temporal_split_dataset(img_dir, lbl_dir, out, train_ratio=0.8, gap=3)
    train = sorted(p.stem for p in (out / "images" / "train").iterdir())
    val = sorted(p.stem for p in (out / "images" / "val").iterdir())
    max_train = max(int(s.split("_")[1]) for s in train)
    min_val = min(int(s.split("_")[1]) for s in val)
    assert min_val - max_train > 3  # boundary gap discarded → no near-duplicate straddles split
    assert stats["train"] + stats["val"] + stats["dropped_gap"] == 100
```

- [ ] **Step 3: Run tests to verify they fail (red)**

Run: `CI=true uv run pytest tests/test_vision/test_prepare_dataset.py tests/test_vision/test_download_dataset.py -v`
Expected: FAIL — `write_data_yaml` still emits `nc: 2` (so the updated `nc: 4` assertions fail) and `temporal_split_dataset` is not yet defined (ImportError).

- [ ] **Step 4: Update `write_data_yaml` (both files) and add `temporal_split_dataset`**

In `katrain/vision/tools/prepare_dataset.py`, add import and rewrite `write_data_yaml`:

```python
from katrain.vision.classes import CLASS_NAMES


def write_data_yaml(output_dir: Path) -> None:
    """Write YOLO data.yaml for the dataset (class list from the single source of truth)."""
    output_dir = Path(output_dir)
    names = ", ".join(f"'{n}'" for n in CLASS_NAMES)
    yaml_content = (
        f"path: {output_dir.resolve()}\ntrain: images/train\nval: images/val\n\n"
        f"nc: {len(CLASS_NAMES)}\nnames: [{names}]\n"
    )
    (output_dir / "data.yaml").write_text(yaml_content)


def temporal_split_dataset(image_dir, label_dir, output_dir, train_ratio: float = 0.8, gap: int = 3) -> dict:
    """Contiguous temporal split (NOT random) with a discarded boundary gap to prevent
    near-duplicate consecutive frames leaking across train/val."""
    import shutil

    image_dir, label_dir, output_dir = Path(image_dir), Path(label_dir), Path(output_dir)
    exts = {".jpg", ".jpeg", ".png", ".bmp"}
    images = sorted(f for f in image_dir.iterdir() if f.suffix.lower() in exts)
    n = len(images)
    split = int(n * train_ratio)
    train_imgs = images[: max(0, split - gap)]
    val_imgs = images[split:]
    stats = {"train": 0, "val": 0, "dropped_gap": n - len(train_imgs) - len(val_imgs), "missing_labels": 0}
    for name, group in (("train", train_imgs), ("val", val_imgs)):
        img_out = output_dir / "images" / name
        lbl_out = output_dir / "labels" / name
        img_out.mkdir(parents=True, exist_ok=True)
        lbl_out.mkdir(parents=True, exist_ok=True)
        for ip in group:
            shutil.copy2(ip, img_out / ip.name)
            lp = label_dir / (ip.stem + ".txt")
            if lp.exists():
                shutil.copy2(lp, lbl_out / lp.name)
            else:
                stats["missing_labels"] += 1
            stats[name] += 1
    write_data_yaml(output_dir)
    return stats
```

In `katrain/vision/tools/download_dataset.py`, replace its duplicate `write_data_yaml` body with the same `CLASS_NAMES`-derived string (add `from katrain.vision.classes import CLASS_NAMES`), and update any "2-class" docstring/print.

In `katrain/vision/tools/data_template.yaml`, change the last two lines to:
```yaml
nc: 4
names: ['black', 'white', 'led_red', 'led_green']
```

**Also wire the temporal split into the CLI** (so the baipu runbook uses a flag, not a here-doc, and a future implementer can't silently reach for the leaky random split). In `prepare_dataset.py`'s `main()`, add `--split-mode {random,temporal}` (default `random` — preserves existing behavior for other datasets) and `--gap` (default `3`), and dispatch on it in the `--images/--labels` branch:

```python
    parser.add_argument("--split-mode", choices=["random", "temporal"], default="random",
                        help="temporal: contiguous holdout with a boundary gap (REQUIRED for continuous baipu frames)")
    parser.add_argument("--gap", type=int, default=3, help="frames dropped at the temporal split boundary")
    # ... in the --images/--labels branch, replace the unconditional split_dataset(...) call with:
    if args.split_mode == "temporal":
        stats = temporal_split_dataset(Path(args.images), Path(args.labels), output_dir, args.split, args.gap)
    else:
        stats = split_dataset(Path(args.images), Path(args.labels), output_dir, args.split, args.seed)
        write_data_yaml(output_dir)  # temporal_split_dataset writes its own data.yaml
```

Add a one-line warning to `split_dataset`'s docstring: *"Random split — do NOT use for continuous baipu game frames (consecutive frames are near-duplicates → val leakage). Use temporal_split_dataset."*

- [ ] **Step 5: Run tests to verify they pass (green)**

Run: `CI=true uv run pytest tests/test_vision/test_prepare_dataset.py tests/test_vision/test_download_dataset.py -v`
Expected: PASS (all green, including the updated `nc: 4` assertions and the new temporal-split test).

- [ ] **Step 6: Assemble the real dataset**

Run:
```bash
uv run python -m katrain.vision.tools.prepare_dataset \
  --images /tmp/go4/images_raw --labels /tmp/go4/labels_raw --output /tmp/go4/dataset \
  --split 0.8 --split-mode temporal --gap 3 --validate
cat /tmp/go4/dataset/data.yaml   # verify nc: 4 + 4 names
```
Expected: prints train/val/dropped_gap counts; `data.yaml` shows `nc: 4`. **`--split-mode temporal` is mandatory here** — the default `random` would leak near-duplicate consecutive frames into val.

- [ ] **Step 7: Commit**

```bash
git add katrain/vision/tools/prepare_dataset.py katrain/vision/tools/download_dataset.py \
        katrain/vision/tools/data_template.yaml \
        tests/test_vision/test_prepare_dataset.py tests/test_vision/test_download_dataset.py
git commit -m "feat(vision): 4-class data.yaml + temporal (leakage-free) train/val split"
```

---

## Task 8: LED-safe augmentation preset in `train_model.py`

**Files:**
- Modify: `katrain/vision/tools/train_model.py` (add `LED_SAFE_AUG`, `build_train_kwargs`, `--augment`/`--cache` flags; wire into `cmd_train`)
- Test: `tests/test_vision/test_train_model.py` (create)

**Interfaces:**
- Produces: `LED_SAFE_AUG: dict`, `build_train_kwargs(args) -> dict`. `cmd_train` calls `model.train(**build_train_kwargs(args))`.
- Consumed by: Task 9 runbook (`train ... --augment led-safe --cache`).

> **Why this is a code task, not a CLI aside:** `cmd_train` (current `train_model.py:55-71`) passes a fixed kwarg set to `model.train()` with **no augmentation passthrough**. Running the train command without this change uses Ultralytics' default `hsv_h=0.015`, which jitters hue — and **hue is the exact signal that distinguishes led_red from led_green**, so the default would corrupt the labels this whole plan exists to produce. `hsv_h=0.0` is mandatory.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vision/test_train_model.py
from types import SimpleNamespace
from katrain.vision.tools.train_model import build_train_kwargs, LED_SAFE_AUG


def _args(**over):
    base = dict(data="d.yaml", epochs=1, imgsz=640, batch=8, name="n",
                patience=10, device="cpu", cache=True, augment="led-safe")
    base.update(over)
    return SimpleNamespace(**base)


def test_led_safe_zeroes_hue_and_sets_key_aug():
    kw = build_train_kwargs(_args())
    assert kw["hsv_h"] == 0.0           # hue is the LED class signal — never jitter
    assert kw["copy_paste"] == 0.0      # no-op on bbox labels (needs segments) — must NOT be relied on
    assert kw["close_mosaic"] == 15
    assert kw["mixup"] == 0.0 and kw["degrees"] == 0.0 and kw["flipud"] == 0.0
    assert kw["fliplr"] == 0.5
    assert kw["data"] == "d.yaml" and kw["imgsz"] == 640 and kw["cache"] is True


def test_default_augment_leaves_ultralytics_defaults():
    kw = build_train_kwargs(_args(augment="default"))
    assert "hsv_h" not in kw            # no override → ultralytics defaults apply
    assert kw["data"] == "d.yaml"


def test_led_safe_aug_constant_is_hue_locked():
    assert LED_SAFE_AUG["hsv_h"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `CI=true uv run pytest tests/test_vision/test_train_model.py -v`
Expected: FAIL — `build_train_kwargs`/`LED_SAFE_AUG` not defined (ImportError).

- [ ] **Step 3: Add the preset + helper and wire into `cmd_train`**

In `katrain/vision/tools/train_model.py`, add near the top (after `DEFAULT_MODEL`):

```python
# LED-safe augmentation for the 4-class baipu model. hsv_h=0 is load-bearing:
# hue separates led_red from led_green, so jittering it corrupts the label.
# copy_paste is pinned to 0.0 ON PURPOSE: Ultralytics CopyPaste no-ops on bbox-only
# labels (it needs segmentation polygons) and is class-agnostic anyway, so it cannot
# oversample the LED class. hsv_s/hsv_v give mild illumination robustness; hsv_h stays 0.
LED_SAFE_AUG = {
    "hsv_h": 0.0, "hsv_s": 0.2, "hsv_v": 0.4,
    "degrees": 0.0, "shear": 0.0, "perspective": 0.0,
    "flipud": 0.0, "fliplr": 0.5, "translate": 0.1, "scale": 0.5,
    "mosaic": 1.0, "close_mosaic": 15, "mixup": 0.0, "copy_paste": 0.0, "erasing": 0.0,
}


def build_train_kwargs(args) -> dict:
    """Assemble the model.train() kwargs, injecting LED_SAFE_AUG when --augment led-safe."""
    kwargs = dict(
        data=args.data, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
        name=args.name, patience=args.patience, device=args.device,
        save=True, plots=True, cache=getattr(args, "cache", False),
    )
    if getattr(args, "augment", "default") == "led-safe":
        kwargs.update(LED_SAFE_AUG)
    return kwargs
```

Rewrite `cmd_train` to use it:

```python
def cmd_train(args):
    from ultralytics import YOLO

    model_path = resolve_model(args)
    print(f"Loading model: {model_path}")
    model = YOLO(model_path)
    model.train(**build_train_kwargs(args))
    print(f"\nTraining complete. Best weights: runs/detect/{args.name}/weights/best.pt")
```

Add the two flags to the `train` subparser argparse (alongside `--epochs`/`--imgsz`/etc.):

```python
    train_p.add_argument("--augment", choices=["default", "led-safe"], default="default",
                         help="led-safe: hsv_h=0 + LED-friendly aug for the 4-class model")
    train_p.add_argument("--cache", action="store_true", help="cache images in RAM (small datasets)")
```
(Use whatever the existing train subparser variable is named; match the file's argparse style.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `CI=true uv run pytest tests/test_vision/test_train_model.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add katrain/vision/tools/train_model.py tests/test_vision/test_train_model.py
git commit -m "feat(vision): led-safe augmentation preset (hsv_h=0; copy_paste pinned 0 — no-op on bbox labels)"
```

---

## Task 9: Train, validate, export (runbook — not a unit test)

**Files:** none changed (uses `train_model.py` from Task 8 + existing `export_onnx.py` / `export_rknn.py`, all class-count-generic).

**Interfaces:**
- Consumes: `/tmp/go4/dataset/data.yaml` (nc:4), `models/yolo11n.pt`.
- Produces: `runs/detect/go4_n/weights/best.pt`, `best.onnx` + `best.meta.json` (classes=4), and `best_rk3588.rknn` + **`best_rk3588.meta.json`** (RKNN sidecar is named `{onnx_stem}_{target}.meta.json`, NOT `best.meta.json` — see `export_rknn.py`).

> Pure runbook — keep the exact flags; they encode the investigation's findings for a tiny, single-board, LED-imbalanced dataset.

- [ ] **Step 1: Train (yolo11n, COCO-pretrained, LED-safe augmentation from Task 8)**

```bash
uv run python -m katrain.vision.tools.train_model train \
  --data /tmp/go4/dataset/data.yaml --model-size n \
  --imgsz 640 --epochs 200 --patience 40 --batch 16 --name go4_n \
  --augment led-safe --cache
```
`--augment led-safe` (Task 8) applies `hsv_h=0.0` + the LED-friendly augmentation set; do not omit it — the default hue jitter corrupts LED labels. **Device:** `train_model.py` defaults to `--device mps` (Mac GPU). On a CUDA box add `--device 0`; CPU-only add `--device cpu`.
Expected: training completes; `runs/detect/go4_n/weights/best.pt` written; watch **val LED recall**, not just overall mAP (stones dominate mAP).

- [ ] **Step 2: Validate on the temporal-holdout val split**

```bash
uv run python -m katrain.vision.tools.train_model val \
  --data /tmp/go4/dataset/data.yaml \
  --model runs/detect/go4_n/weights/best.pt \
  --imgsz 640
```
**`--imgsz 640` is required** — `train_model.py val` defaults to `imgsz=960`; validating at a different size than training/export (640) gives non-comparable per-class recall. Expected: per-class P/R/mAP for all 4 classes.

**Two-tier gate (do not over-read a single game):**
- **Smoke gate (this game, temporal val):** `led_red`/`led_green` recall ≥ ~0.9 AND no `led→stone` confusion in the per-class confusion matrix. This proves the pipeline learns the 4 classes — it is **not** a generalization claim (val shares one board/camera/light/stone-set with train). If recall is low: bump `imgsz` to 960, then `--model-size s`, then **offline LED oversampling** (duplicate LED-bearing images / paste LED ROIs) — **not** `copy_paste` (a no-op on bbox labels, Task 8).
- **Production gate (before field trust):** a **second capture session** (different board/light), validated by **session holdout** (train on game A, validate on game B), reporting LED recall, stone precision, and LED-as-stone false-positive rate. (Multi-game holdout needs session-aware splitting — see the note in Task 7; `temporal_split_dataset`'s filename sort is single-game only.)

Record both tiers' numbers in the README metrics table (Task 10). **Note on val-vs-deploy:** even at `imgsz=640`, deployment runs the detector on the 950×950 warped frame letterboxed to the model's `imgsz`; val mAP is an upper bound on field accuracy. Keep `imgsz` identical across train/val/export so only the letterbox differs.

- [ ] **Step 3: Export ONNX (embeds the 4-class list into the sidecar)**

```bash
uv run python -m katrain.vision.tools.export_onnx \
  --model runs/detect/go4_n/weights/best.pt --imgsz 640
cat runs/detect/go4_n/weights/best.meta.json   # confirm "classes": ["black","white","led_red","led_green"]
```
Expected: `best.onnx` + `best.meta.json` with `nc=4`, static shape.

- [ ] **Step 4: Export RKNN for RK3588 (static shape, same imgsz)**

```bash
uv run python -m katrain.vision.tools.export_rknn \
  --onnx runs/detect/go4_n/weights/best.onnx --target rk3588
cat runs/detect/go4_n/weights/best_rk3588.meta.json   # RKNN sidecar (NOT best.meta.json — that's the ONNX one)
```
Expected: `best_rk3588.rknn` + `best_rk3588.meta.json` (classes=4). The RKNN file/sidecar are named `{onnx_stem}_{target}.*` by `export_rknn.py` — deploy them as a matched pair. No code change was needed in either exporter (confirmed generic).

- [ ] **Step 5: Smoke-test inference on held-out frames (no commit; sanity only)**

`live_demo.py` only reads a live camera (`--camera`, no image-dir mode), so use the Ultralytics predict CLI on the val images instead:

```bash
uv run yolo predict model=runs/detect/go4_n/weights/best.pt \
  source=/tmp/go4/dataset/images/val save=True project=/tmp/go4 name=pred
```
Expected: annotated images in `/tmp/go4/pred/` with black/white/led_red/led_green boxes; LEDs detected as their own class (not as stones). Open a few to confirm. (The runtime guard from Task 2 separately ensures any led_red/led_green detection is never written into board state.)

---

## Task 10: Documentation

**Files:**
- Modify: `katrain/vision/README.md`

- [ ] **Step 1: Update the class count + add the baipu-labeling + training runbook**

Update README:
- Change "**Classes**: 2 (`black`, `white`)" → "4 (`black`, `white`, `led_red`, `led_green`)".
- Add a section "Auto-labeling baipu captures" documenting `baipu_autolabel.py` (warped space, SGF ground truth, per-frame drift correction with carry-forward, configurable LED-anchor HSV, separate stone/LED box sizing + corner clipping, `red→black move`, `green→white move`).
- Paste the Task 9 commands and the recorded val per-class metrics. Add an **experiment table** (one row per run): `imgsz`, `model-size`, `stone_frac`/`led_frac`, per-class P/R/mAP, and **LED-as-stone false-positive rate** — so future `640/n → 960/s` tuning is evidence-based, not vibes.
- Link the QA artifacts produced during labeling: the `verify/` overlays and `verify/shifts.csv` (per-frame drift diagnostics) from Task 6.
- **Data caveats (state plainly):** trained on **one game / one board / one light** → val is optimistic; the model is **specific to this board+lighting** and a different device/environment **requires re-collecting data and retraining** (Production gate, Task 9). On class balance: the LED is per-image ubiquitous (211/212 frames) but per-object rare; `copy_paste` is **not** used (it's a no-op on bbox labels) — if LED recall is weak, oversample offline.

- [ ] **Step 2: Format + commit**

> **Do NOT run `black -l 120 katrain tests`** — that reformats ~120 pre-existing repo files unrelated
> to this feature (a huge accidental diff). Black only the files THIS feature created/modified
> (already done per-task); the README is Markdown and needs no formatting.

```bash
# only this feature's python files (no-op if already formatted per-task):
uv run black -l 120 \
  katrain/vision/classes.py katrain/vision/board_state.py katrain/vision/config.py \
  katrain/vision/stone_detector.py katrain/vision/tools/baipu_autolabel.py \
  katrain/vision/tools/train_model.py katrain/vision/tools/prepare_dataset.py \
  katrain/vision/tools/download_dataset.py tests/test_vision/test_classes.py \
  tests/test_vision/test_board_state.py tests/test_vision/test_baipu_autolabel.py \
  tests/test_vision/test_train_model.py tests/test_vision/test_prepare_dataset.py \
  tests/test_vision/test_download_dataset.py
git add katrain/vision/README.md
git commit -m "docs(vision): document 4-class model, baipu auto-labeling, and training runbook"
```

---

## Self-Review

**Spec coverage:**
- (1) "Does the codebase have YOLO11 training code?" → answered in findings; reused in Tasks 8–9. ✓
- (2) "How to process baipu images for training (no boxes drawn, SGF has positions/colors, red=next black, green=next white)?" → Tasks 3–6 generate exact 4-class labels from SGF + LED metadata + geometry; LED color→class mapping locked in Global Constraints + Task 1/5. ✓
- 4-class everywhere (data.yaml, model, export, inference): Task 1 + Task 7, with the audit confirming export/inference are already generic. ✓
- Drift/parallax handling: Task 4. ✓
- Runtime safety (no phantom stones): Task 2. ✓
- LED-safe training (hsv_h=0; `copy_paste` pinned 0 — a no-op on bbox labels): Task 8. Best-practices (yolo11n, imgsz 640, temporal split): Tasks 7–9. ✓
- CI test coverage of core CV logic (no fixture/`.mo`): synthetic pure-CV tests in Tasks 3–6. ✓

**Placeholder scan:** No TBD/“handle edge cases”/“similar to Task N”. Every code step shows full code. ✓

**Type consistency:** `Box`, `Capture`, `ShiftReport`, `LedAnchorConfig`, `grid_point`, `estimate_global_shift`, `detect_led_centroid`, `frame_boxes`, `boxes_to_yolo_lines`, `process_game`, `temporal_split_dataset`, `write_data_yaml`, `build_train_kwargs`, `LED_SAFE_AUG`, `CLASS_NAMES/NAME_TO_ID/ID_TO_NAME/STONE_CLASS_IDS/LED_COLOR_TO_CLASS` used with consistent signatures across tasks. **`estimate_global_shift` now returns a `ShiftReport`** (not a tuple): Task 4 tests read `rep.dx/.dy/...`, and Task 6 `process_game` calls `frame_boxes(..., (rep.dx, rep.dy), ...)` — `frame_boxes`/`draw_overlay` still take a plain `(dx,dy)` tuple, so the change is contained. **`ID_TO_NAME` is imported in Task 5's class import** (`ID_TO_NAME, LED_COLOR_TO_CLASS, NAME_TO_ID`) and consumed by `process_game` stats in Task 6 (fixes the original missing-import `NameError`). `frame_boxes` signature is `(board, led_point, xs, ys, shift, spacing, stone_frac=1.05, led_frac=0.45, img_w=950, img_h=950)` everywhere it's called. `Detection` constructed as `(x_center, y_center, class_id, confidence)` (no width/height) per `stone_detector.py:15-23`. ✓

**Adversarial-review fixes applied:** `Detection` signature corrected (no width/height); existing `test_board_state.py`/`test_prepare_dataset.py`/`test_download_dataset.py` are appended/edited (not clobbered) and their stale `nc: 2` assertions updated to `nc: 4`; `live_demo --source` (nonexistent) replaced with `yolo predict`; LED-safe augmentation made a real code task (Task 8) instead of a CLI aside; **i18n `.mo` prerequisite added to Global Constraints** (Tasks 3–6 import `core.baipu`→`core.game`→`core.lang`, which errors at pytest collection with the `katrain` `FileNotFoundError` until `uv run python i18n.py` is run — verified against a fresh checkout); dedup `Why` qualified for `kifu_24171` (0 dups, no-op) and the `frame_000` (`applied_move_index=-1`, empty board + LED) / `frame_211` (`final_no_led`) edge cases documented.

**Codex + Gemini review round (adopted / rejected — verified against the codebase before deciding):**

- **Adopted (Blocker/Major):** import `ID_TO_NAME` (Task 5/6 `NameError`); CI-runnable synthetic pure-CV tests + lazy `core.baipu` import so the labeler's logic is tested without fixture/`.mo` (Tasks 3–6); drift `ShiftReport` + **carry-forward** of the previous shift instead of unconditional `(0,0)`, plus a synthetic known-translation accuracy test (Task 4); parameterized LED-anchor HSV via `LedAnchorConfig` (Task 4); **separate, tighter, image-clipped** stone (~1.05·spacing) vs LED (~0.45·spacing) boxes (Task 5); `copy_paste` removed — verified no-op on bbox labels in Ultralytics source (Task 8); `--split-mode temporal` CLI so the runbook can't reach the leaky random split (Task 7); `val --imgsz 640` (Task 9); RKNN sidecar renamed `best_rk3588.meta.json` (Task 9); two-tier gate = single-game *smoke* vs second-session *production* (Task 9); board/light-specific + QA-artifact docs (Task 10).
- **Rejected / down-weighted (with reason):** Gemini's *"add `transforms.ColorJitter`/`GaussianBlur`/`GaussNoise` to `LED_SAFE_AUG`"* — those are **torchvision** transforms, **not** Ultralytics `model.train()` kwargs; the valid equivalents (`hsv_s`, `hsv_v`) are already in the preset (`hsv_h` stays 0). Gemini's *"derive expected values from SGF"* for reconstruction tests — **circular** (`reconstruct_board` *is* the SGF replay); applied only where it's an independent oracle (box-count == non-empty board cells). Both reviewers' *pass/handicap/clear edge-case tests* — down-weighted: `katrain.core.baipu` already handles these (`NON_PLACEMENT_KINDS`, `clear` steps, AB/AW setup; `kifu_24171` has none) and the labeler inherits that behavior; left as optional synthetic coverage, not a blocker. Codex's *runtime LED-grid stone-suppression* — kept as a **documented residual risk** below, not added: the lit LED marks the **next** move's (empty) intersection, ONNX/RKNN NMS is class-agnostic, and active suppression could drop a real stone.

**Live-data verification (prior review):** schema + magic numbers checked against the real capture `~/.katrain/baipu_captures/kifu_24171` — manifest keys (`frames[].{file,applied_move_index,led_point.{row,col,color}}`, `board_size`, `total_moves`, `sgf_path`, `geometry_path`, `game_id`) ✓; `geometry.npz` keys (`M`, `out_size=950`, `xs`/`ys` spacing≈52.72) ✓; `build_steps_from_sgf` → 211 steps (all `move`) ✓; `expected_board_from_steps(steps,39)` → (20 B, 20 W) ✓; `(steps,210)` → 205 stones (211−6 captured) ✓; `frame_211.jpg` `frame_kind=="final_no_led"`, `led_point is None` ✓.

**Robustness note (handicap/setup games):** `manifest.applied_move_index` is the index into `steps[]` (set as `move_index` in `baipu_capture.py:193`, which iterates the full step list including any AB/AW setup), so `expected_board_from_steps(steps, applied_move_index, 19)` is correct even for handicap games — `applied_move_index` is NOT a move-only counter. No extra guard needed; stated here so an implementer doesn't "fix" it.

**Known residual risks (flagged, not blocking):**

- Train/serve warp source differs slightly (frozen geometry.npz M vs live `board_finder` corners). Mitigated by `translate/scale` augmentation + the round-trip-consistent labeling; revisit if val-vs-live gap appears.
- Single game → val optimistic. Plan recommends a second capture session before production trust (out of this plan's scope: "first game runs through end-to-end").
- **Runtime LED/stone co-location (defense-in-depth, not implemented):** the Task 2 guard drops `led_red`/`led_green` detections so they never write phantom stones, which is sufficient for the stated goal. A *separate* failure — the model emitting a spurious `black`/`white` box at the lit LED's intersection — is mitigated by the 4-class training itself (the model learns LEDs are their own class), by class-agnostic NMS collapsing co-located boxes, and by the fact that the lit LED sits on the **next** move's currently-**empty** intersection. Active "suppress stones near an LED grid point" logic was deliberately **not** added: it risks dropping a genuine stone if a future capture ever lights an LED adjacent to a played stone. Revisit only if field data shows phantom stones at LED sites.
- **Multi-game splitting:** `temporal_split_dataset` sorts by filename and is **single-game only**; pooling several games needs session-aware holdout (train on game A, val on game B) — flagged in Task 7/Task 9, not built here.
