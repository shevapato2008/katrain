# 参照图对比（reference-frame check）实施计划 v3

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 白天强光/光照不均下，用「上一次盘面与棋谱一致时的画面」按格比对，减少识别的假阴性（子被光吃掉）和假阳性（亮斑被当成子）；本轮只交付到影子模式（算并记日志，不改识别结果），用板上白天数据定阈值后再决定是否打开。

**Architecture:** 每格取一小块灰度图（warp 后、8 帧平均前、CLAHE 前），与参照图同格做 ZNCC。相关度高只作为**有界证据**：它只影响「交给下游的盘面」，不回写识别自己的历史状态；保护棋谱已知的子力度大，压制凭空多出的子力度小且有帧数上限，到点放行并作废参照。参照图只在棋谱推进且当前无任何否决、无待确认落子时更新，只存在内存里。

**Tech Stack:** Python 3.11、numpy、OpenCV（仅 `cvtColor`）、pytest。板子是 RK3562（ARM Cortex-A53 级，2 GB，服务内存上限 1700 MB），识别每帧 380–600 ms。

**Spec:** `superpowers/tracks/vision-optimizations/reference-frame/design.md`（v2；相邻问题 `docs/known-issue-overexposure.md` 明确不在本轮范围）

**审核记录：** v1 由 Codex 审出 8 条 P1、4 条 P2；v2 又被审出 8 条 P1、2 条 P2（本文是 v3）。其中「板上跑的是子进程 worker」一条经实测驳回
（板子 journal 有 16035 行 `katrain.vision.worker_inprocess`；`service.py:42` 在 `frame_source` 非空时
强制走 in-process，板上单元带 `--capture-camera 0`）。其余全部采纳，spec 与本计划据此重写，
被推翻的旧判据列在 spec §10。

## Global Constraints

- **不改动现有识别阈值与结构**：0.40 新增 / 0.30 保持 / 0.20 维持三档滞回、两帧投票、MoveDetector 的 3/5 帧确认、`masked` 亮灯遮罩，一律不动。
- **否决不回写识别历史**：`_last_stable_board`、`_prev_observed_board` 永远是未经否决的投票结果；否决只产出 `observed_board`（下游用）。
- **默认 `shadow`**，本轮板上只跑 shadow。改默认需要板上白天数据，不在本计划内。
- **参照只在内存里一份**：不写任何文件。
- **每帧计算整体向量化**；构建索引表的那一次循环（每几何锁一次）不受此限。
- **比对帧 = warp 后、8 帧平均前、CLAHE 前**。
- 代码注释、提交信息用英文；文档用中文。格式化 `uv run black -l 120`。
- 测试 `uv run pytest`；`tests/web_ui/` 与根级测试分开跑。
- 提交信息结尾带 `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`。

## 文件结构

| 文件 | 职责 |
|---|---|
| `katrain/vision/reference_frame.py`（新建） | 纯计算：取样几何 `CellSampler`、参照图 `ReferenceFrame`（ZNCC + 「测不了」判据）。 |
| `katrain/vision/worker_inprocess.py`（改） | 状态、参照生命周期、按格有界否决、vtrace 计时段。 |
| `katrain/vision/config_service.py`（改） | `reference_check` 配置项。 |
| `katrain/web/server.py`（改） | `--vision-reference-check {off,shadow,on}`。 |
| `tests/test_vision/test_reference_frame.py`（新建） | 纯计算 + worker 集成。 |

## 已知陷阱（v1 踩过或被审出，务必避免）

1. **取样块中心算错半格**：`x0` 已是「中心减半宽」的左上角，偏移数组必须是 `arange(...)`，不能再减 half。
2. **不能用 CLAHE 后的图**（自适应，会造出不存在的差异）。
3. **不能用 8 帧平均后的图**：新子要几帧才显形，过渡期会被误判成「没变」。
4. **`SET_EXPECTED_BOARD` 不能无条件作废参照**（每手都来），但**必须**在非落子形状的跳变（悔棋/跳转/新局）时作废。
5. **参照自我中毒**：拍参照必须用未经否决的盘面，且要求无待确认落子、当前无任何否决；不做「盘面没变也定期重拍」。

---

### Task 1: 纯计算模块 `reference_frame.py`

**Files:**
- Create: `katrain/vision/reference_frame.py`
- Test: `tests/test_vision/test_reference_frame.py`

**Interfaces:**
- Consumes: `katrain.vision.config.BoardConfig`、`katrain.vision.coordinates.grid_to_physical`、`ParallaxParams`（只读 `.nadir` / `.k`）。
- Produces:
  - 常量 `MIN_PATCH_STD = 3.0`、`CLIP_LEVEL = 250`、`MAX_CLIPPED_FRACTION = 0.25`、`PATCH_RADIUS_CELLS = 0.45`、`SAMPLE_STEP = 2`
  - `to_gray(warped) -> np.ndarray`
  - `CellSampler`（frozen dataclass：`img_w, img_h, grid_size, points, flat_index`；`sample(gray) -> (cells, points) float32`）
  - `build_sampler(img_w, img_h, config=None, parallax=None, radius_cells=PATCH_RADIUS_CELLS, step=SAMPLE_STEP) -> CellSampler`
  - `ReferenceFrame(sampler, gray, board)`：属性 `board`；方法 `similarity(gray) -> (grid, grid) float32`（NaN = 测不了）、`unchanged(gray, threshold) -> (mask, similarity)`

- [ ] **Step 1: 写失败的测试**

新建 `tests/test_vision/test_reference_frame.py`：

```python
"""Reference-frame check (2026-09-23): per-cell ZNCC against the last frame whose board matched the
game record, as bounded evidence against daylight false negatives/positives.
Design: superpowers/tracks/vision-optimizations/reference-frame/design.md
"""

import numpy as np
import pytest

from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig
from katrain.vision.reference_frame import ReferenceFrame, build_sampler, to_gray

BLACK, WHITE = 1, 2
SIZE = 1056
CONFIG = BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS)
ZNCC = 0.90


def _sampler(parallax=None):
    return build_sampler(SIZE, SIZE, CONFIG, parallax)


def _cell_centre(row, col):
    x_mm = CONFIG.border_width_mm + col * CONFIG.grid_spacing_w
    y_mm = CONFIG.border_length_mm + row * CONFIG.grid_spacing_l
    return int(round(x_mm / CONFIG.total_width * SIZE)), int(round(y_mm / CONFIG.total_length * SIZE))


def _board_frame(stones=(), seed=0):
    """A textured board (wood grain + grid lines) with discs on the given intersections."""
    rng = np.random.default_rng(seed)
    frame = np.full((SIZE, SIZE, 3), 150, np.uint8)
    frame[..., 0] = 120
    frame = np.clip(frame.astype(np.int16) + rng.integers(0, 25, frame.shape), 0, 255).astype(np.uint8)
    for i in range(19):
        x, y = _cell_centre(i, i)
        frame[max(0, y - 1) : y + 1, :] = 90
        frame[:, max(0, x - 1) : x + 1] = 90
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    for row, col, colour, *offset in stones:
        x, y = _cell_centre(row, col)
        dx, dy = (offset + [0, 0])[:2] if offset else (0, 0)
        frame[(xx - x - dx) ** 2 + (yy - y - dy) ** 2 <= 24**2] = 235 if colour == WHITE else 25
    return frame


def _empty_board():
    return np.zeros((19, 19), dtype=int)


def test_the_patch_of_every_cell_is_centred_on_its_intersection_and_inside_the_frame():
    sampler = _sampler()
    assert sampler.flat_index.min() >= 0 and sampler.flat_index.max() < SIZE * SIZE
    for row, col in ((0, 0), (0, 18), (18, 0), (18, 18), (0, 9), (9, 0), (18, 9), (9, 18), (2, 2), (9, 9)):
        ys, xs = np.divmod(sampler.flat_index[row * 19 + col], SIZE)
        x, y = _cell_centre(row, col)
        assert abs((xs.min() + xs.max()) / 2 - x) <= 2 and abs((ys.min() + ys.max()) / 2 - y) <= 2


def test_the_patch_follows_the_mount_parallax_outward():
    """A stone is imaged away from the nadir, so with parallax the patch shifts outward, not inward."""
    parallax = type("P", (), {"nadir": (19.612, 9.0), "k": 0.989689})()
    shifted = build_sampler(SIZE, SIZE, CONFIG, parallax)
    plain = _sampler()
    ys_p, xs_p = np.divmod(plain.flat_index[0 * 19 + 0], SIZE)
    ys_s, xs_s = np.divmod(shifted.flat_index[0 * 19 + 0], SIZE)
    assert xs_s.mean() < xs_p.mean()  # (0,0) is on the far side of the nadir: imaged further out


def test_the_same_scene_is_unchanged_everywhere():
    frame = _board_frame([(4, 4, BLACK)])
    board = _empty_board()
    board[4][4] = BLACK
    reference = ReferenceFrame(_sampler(), to_gray(frame), board)
    mask, sim = reference.unchanged(to_gray(frame), ZNCC)
    assert mask.all() and np.nanmin(sim) > 0.99


def test_a_brightness_change_is_still_unchanged_where_a_pixel_diff_would_scream():
    frame = _board_frame([(4, 4, BLACK)])
    brighter = np.clip(frame.astype(np.float32) * 1.3 + 40, 0, 250).astype(np.uint8)
    reference = ReferenceFrame(_sampler(), to_gray(frame), _empty_board())
    mask, _ = reference.unchanged(to_gray(brighter), ZNCC)
    assert mask.all()
    assert np.abs(to_gray(brighter).astype(int) - to_gray(frame).astype(int)).mean() > 40


@pytest.mark.parametrize(
    "before,after,cell",
    [
        ((), ((9, 9, WHITE),), (9, 9)),  # a stone placed
        (((9, 9, WHITE),), (), (9, 9)),  # a stone taken off (capture)
        (((9, 9, BLACK),), ((9, 9, WHITE),), (9, 9)),  # colour replaced
        (((9, 9, WHITE),), ((9, 9, WHITE, 26, 0),), (9, 9)),  # nudged half a cell
    ],
)
def test_every_real_board_change_breaks_the_correlation(before, after, cell):
    reference = ReferenceFrame(_sampler(), to_gray(_board_frame(before)), _empty_board())
    mask, sim = reference.unchanged(to_gray(_board_frame(after)), ZNCC)
    assert not mask[cell[0]][cell[1]], f"zncc={sim[cell[0]][cell[1]]}"


def test_a_stone_at_one_eighth_weight_still_reads_as_unchanged():
    """Why the comparison must never be fed the frame averager's output: at 1/8 weight -- the first
    frame of a new stone inside an 8-frame average -- the cell still correlates about 0.93, above any
    usable threshold, so a veto there would erase a move while it is appearing. The production path
    avoids this by comparing the pre-average frame (see to_gray, and the loop test in Task 2)."""
    empty = _board_frame().astype(np.float32)
    stone = _board_frame([(9, 9, BLACK)]).astype(np.float32)
    blended = (empty * 7 / 8 + stone / 8).astype(np.uint8)
    reference = ReferenceFrame(_sampler(), to_gray(_board_frame()), _empty_board())
    _, sim = reference.unchanged(to_gray(blended), ZNCC)
    assert sim[9][9] > ZNCC  # the hazard, recorded on purpose
    _, raw_sim = reference.unchanged(to_gray(_board_frame([(9, 9, BLACK)])), ZNCC)
    assert raw_sim[9][9] < ZNCC  # the frame production actually compares


def test_a_blown_out_cell_cannot_be_compared():
    before = _board_frame([(2, 2, WHITE)])
    after = before.copy()
    x, y = _cell_centre(2, 2)
    after[y - 30 : y + 30, x - 30 : x + 30] = 255
    reference = ReferenceFrame(_sampler(), to_gray(before), _empty_board())
    mask, sim = reference.unchanged(to_gray(after), ZNCC)
    assert np.isnan(sim[2][2]) and not mask[2][2]


def test_a_mostly_clipped_cell_with_one_grid_line_left_is_also_cannot_tell():
    """std alone passes here (the surviving line carries variance) -- the clipped-fraction test is
    what catches it."""
    before = _board_frame([(2, 2, WHITE)])
    after = before.copy()
    x, y = _cell_centre(2, 2)
    after[y - 30 : y + 30, x - 30 : x + 30] = 255
    after[y - 30 : y + 30, x - 2 : x + 2] = 60  # one dark grid line survives the glare
    reference = ReferenceFrame(_sampler(), to_gray(before), _empty_board())
    mask, sim = reference.unchanged(to_gray(after), ZNCC)
    assert np.isnan(sim[2][2]) and not mask[2][2]


def test_a_frame_of_the_wrong_size_is_refused():
    reference = ReferenceFrame(_sampler(), to_gray(_board_frame()), _empty_board())
    with pytest.raises(ValueError):
        reference.similarity(np.zeros((640, 640), np.uint8))
```

- [ ] **Step 2: 运行，确认失败**

Run: `uv run pytest tests/test_vision/test_reference_frame.py -q`
Expected: FAIL，`ModuleNotFoundError: No module named 'katrain.vision.reference_frame'`

- [ ] **Step 3: 实现模块**

新建 `katrain/vision/reference_frame.py`：

```python
"""Per-cell comparison against the last frame whose board matched the game record (2026-09-23).

Daylight glare and uneven window light make the detector drop stones it already saw (false negative)
and invent stones on bright patches (false positive). Both are model failures on a board that did not
physically change, so the cheapest evidence is the picture itself.

The comparison is a zero-mean normalised cross-correlation (ZNCC) per cell, not a pixel difference:
a cell that simply got brighter, darker or crossed by a soft shadow edge still correlates ~1, while a
stone appearing, disappearing, changing colour or shifting half a cell destroys the correlation. That
invariance is the whole point -- plain differencing reports "changed" for exactly the lighting events
this is meant to survive.

High correlation is EVIDENCE, not proof (a review of the first draft was right to insist): clipping,
blur and partially averaged transitions can all correlate. The caller therefore bounds how long it may
act on it and never writes the result back into recognition's own history. See the spec.

A cell that cannot be compared -- flat (blown out or pitch black) or mostly clipped -- comes back NaN,
and the caller falls back to the detector. See docs/known-issue-overexposure.md.

Design: superpowers/tracks/vision-optimizations/reference-frame/design.md
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from katrain.vision.config import BoardConfig
from katrain.vision.coordinates import grid_to_physical

# Gray levels. Below this std the patch has no structure to correlate.
MIN_PATCH_STD = 3.0
# A pixel at or above this is clipped; a patch with more than MAX_CLIPPED_FRACTION of them carries no
# usable structure even when a surviving grid line keeps its std up.
CLIP_LEVEL = 250
MAX_CLIPPED_FRACTION = 0.25
# Patch radius as a fraction of one cell. Larger leaks the neighbours' changes in (which only makes
# the rule stay silent, the safe direction); smaller stops covering the stone.
PATCH_RADIUS_CELLS = 0.45
# Sample every Nth pixel of that footprint: a stone-vs-wood-grain difference is far coarser than one
# pixel, and this cuts the per-frame gather, the statistics and the index table by step**2.
SAMPLE_STEP = 2


@dataclass(frozen=True)
class CellSampler:
    """Which pixels of a warped frame belong to each intersection.

    Built once per (geometry lock, frame size): the warp puts the board on a regular grid, so a
    cell's pixel block never moves until the lock changes.
    """

    img_w: int
    img_h: int
    grid_size: int
    points: int  # samples per cell
    flat_index: np.ndarray  # (grid_size**2, points) int32, into a flattened gray frame

    def sample(self, gray: np.ndarray) -> np.ndarray:
        """(cells, points) float32 blocks, row-major by (row, col)."""
        if gray.shape[:2] != (self.img_h, self.img_w):
            raise ValueError(f"frame {gray.shape[:2]} does not match the sampler {(self.img_h, self.img_w)}")
        return gray.reshape(-1)[self.flat_index].astype(np.float32)


def to_gray(warped: np.ndarray) -> np.ndarray:
    """The image the comparison runs on: warped, but BEFORE the frame averager and BEFORE CLAHE.

    CLAHE is adaptive, so the same cell renders differently when something elsewhere on the board
    changes. The averager shows a new stone at partial weight for several frames, which is exactly the
    window where a veto would erase a move mid-appearance.
    """
    return cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if warped.ndim == 3 else warped


def build_sampler(
    img_w: int,
    img_h: int,
    config: BoardConfig | None = None,
    parallax=None,
    radius_cells: float = PATCH_RADIUS_CELLS,
    step: int = SAMPLE_STEP,
) -> CellSampler:
    """Patch centres sit where a stone on that intersection is *imaged*, not on the intersection.

    A stone's centre is above the board, so the camera pushes it outward from the nadir by 1/k --
    the shift `apply_parallax` undoes for detections. Here we go the other way, to aim the patch at
    the stone. Without parallax params the intersection itself is used.
    """
    config = config or BoardConfig()
    grid = config.grid_size
    cell_px = min(
        config.grid_spacing_w / config.total_width * img_w,
        config.grid_spacing_l / config.total_length * img_h,
    )
    patch = min(2 * max(4, int(round(radius_cells * cell_px))), img_w, img_h)
    half = patch // 2
    offsets = np.arange(0, patch, step, dtype=np.int32)  # from the block's top-left corner, NOT its centre

    nadir_x = nadir_y = None
    k = getattr(parallax, "k", None)
    if parallax is not None and k:
        nadir_x, nadir_y = parallax.nadir

    index = np.empty((grid * grid, offsets.size * offsets.size), dtype=np.int32)
    for row in range(grid):
        for col in range(grid):
            fx, fy = float(col), float(row)
            if nadir_x is not None:
                # inverse of apply_parallax: where a stone on this intersection appears
                fx = nadir_x + (fx - nadir_x) / k
                fy = nadir_y + (fy - nadir_y) / k
            x_mm, y_mm = grid_to_physical(fx, fy, config)
            px = x_mm / config.total_width * img_w
            py = y_mm / config.total_length * img_h
            x0 = min(max(int(round(px)) - half, 0), img_w - patch)
            y0 = min(max(int(round(py)) - half, 0), img_h - patch)
            index[row * grid + col] = ((y0 + offsets)[:, None] * img_w + (x0 + offsets)[None, :]).reshape(-1)
    return CellSampler(img_w=img_w, img_h=img_h, grid_size=grid, points=index.shape[1], flat_index=index)


def _usable(patches: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(std, usable): a patch is usable when it has structure and is not mostly clipped."""
    std = patches.std(axis=1)
    clipped = (patches >= CLIP_LEVEL).mean(axis=1)
    return std, (std >= MIN_PATCH_STD) & (clipped <= MAX_CLIPPED_FRACTION)


class ReferenceFrame:
    """One reference: the normalised cell patches of a frame plus the board it is known to show."""

    def __init__(self, sampler: CellSampler, gray: np.ndarray, board: np.ndarray):
        patches = sampler.sample(gray)
        std, usable = _usable(patches)
        self.sampler = sampler
        self.board = np.array(board, dtype=int, copy=True)
        self.usable = usable
        self.normalised = (patches - patches.mean(axis=1, keepdims=True)) / np.where(usable, std, 1.0)[:, None]

    def similarity(self, gray: np.ndarray) -> np.ndarray:
        """(grid, grid) float32 ZNCC in [-1, 1]; NaN where either frame's patch cannot be compared."""
        patches = self.sampler.sample(gray)
        std, usable = _usable(patches)
        usable &= self.usable
        normalised = (patches - patches.mean(axis=1, keepdims=True)) / np.where(usable, std, 1.0)[:, None]
        zncc = (self.normalised * normalised).sum(axis=1) / normalised.shape[1]
        return np.where(usable, zncc, np.nan).astype(np.float32).reshape(self.sampler.grid_size, -1)

    def unchanged(self, gray: np.ndarray, threshold: float) -> tuple[np.ndarray, np.ndarray]:
        """(mask, similarity): mask is True where the cell is structurally the same as the reference.
        Evidence that its occupancy is still `self.board` -- see the module docstring on how far the
        caller may act on it."""
        sim = self.similarity(gray)
        return np.nan_to_num(sim, nan=-1.0) >= threshold, sim
```

- [ ] **Step 4: 运行，确认通过**

Run: `uv run pytest tests/test_vision/test_reference_frame.py -q`
Expected: 11 passed（含 4 个参数化用例）

若 `test_a_stone_fading_in_through_the_frame_averager_is_not_called_unchanged` 失败（1/8 权重的过渡态
相关度仍 ≥ 0.90），**不要调低阈值来凑**：记录实测 ZNCC 值，把它写进 spec §7，并在 Task 2 的
`REFERENCE_HOLD_SUPPRESS` 注释里说明这正是需要短上限的原因。

- [ ] **Step 5: 格式化并提交**

```bash
uv run black -l 120 katrain/vision/reference_frame.py tests/test_vision/test_reference_frame.py
git add katrain/vision/reference_frame.py tests/test_vision/test_reference_frame.py
git commit -m "feat(vision): per-cell ZNCC against a reference frame

Daylight glare makes the detector drop stones it already saw and invent stones on bright patches,
both on a board that did not physically change. A zero-mean normalised cross-correlation per cell
survives a cell getting brighter or crossed by a shadow (where a pixel difference would scream) and
collapses when a stone appears, disappears, changes colour or shifts half a cell. Patches that are
flat or mostly clipped come back NaN -- nothing to compare, the detector is on its own there.

Pure computation, no worker wiring yet.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: 接进 worker —— 有界证据，不回写历史

**Files:**
- Modify: `katrain/vision/worker_inprocess.py`
- Test: `tests/test_vision/test_reference_frame.py`（追加集成部分）

**Interfaces:**
- Consumes: Task 1 的 `CellSampler` / `ReferenceFrame` / `build_sampler` / `to_gray`。
- Produces：
  - 常量 `REFERENCE_ZNCC = 0.90`、`REFERENCE_HOLD_KEEP = 150`、`REFERENCE_HOLD_SUPPRESS = 10`
  - `InProcessAdapter._ref_mode: str`（`config["reference_check"]`，默认 `"shadow"`）
  - `InProcessAdapter._reference_check(board, gray) -> np.ndarray`（返回下游用的 effective board；shadow/无参照时返回入参对象本身）
  - `InProcessAdapter._maybe_capture_reference(board, observed, gray, motion_stable) -> None`
  - `InProcessAdapter._invalidate_reference(reason: str) -> None`

- [ ] **Step 1: 写失败的集成测试**

追加到 `tests/test_vision/test_reference_frame.py`：

```python
from types import SimpleNamespace
from unittest.mock import patch as mock_patch

from katrain.vision.board_state import EMPTY
from katrain.vision.ipc import CommandType, WorkerCommand
from katrain.vision.worker_inprocess import (
    REFERENCE_HOLD_KEEP,
    REFERENCE_HOLD_SUPPRESS,
    REFERENCE_ZNCC,
    InProcessAdapter,
)


def _adapter(mode="on"):
    with mock_patch("katrain.vision.worker_inprocess.StoneDetector"):
        adapter = InProcessAdapter({"board_size": 19, "reference_check": mode}, camera=None)
    adapter._geometry = SimpleNamespace(points=None)
    adapter._bound = True
    return adapter


def _with_reference(mode, ref_frame, ref_board):
    adapter = _adapter(mode)
    adapter._ref_sampler = _sampler()
    adapter._reference = ReferenceFrame(adapter._ref_sampler, to_gray(ref_frame), ref_board)
    return adapter


def test_the_threshold_the_worker_uses_is_the_one_the_unit_tests_assert():
    assert REFERENCE_ZNCC == ZNCC


def test_a_stone_the_game_knows_survives_a_detector_that_lost_it():
    truth = _empty_board()
    truth[4][4] = BLACK
    frame = _board_frame([(4, 4, BLACK)])
    adapter = _with_reference("on", frame, truth)
    detector_says = truth.copy()
    detector_says[4][4] = EMPTY  # glare ate the stone
    effective = adapter._reference_check(detector_says, to_gray(frame))
    assert effective[4][4] == BLACK
    assert detector_says[4][4] == EMPTY  # the caller's array is never mutated


def test_an_invented_stone_is_suppressed_but_only_for_a_few_frames():
    frame = _board_frame()
    adapter = _with_reference("on", frame, _empty_board())
    detector_says = _empty_board()
    detector_says[12][3] = WHITE
    for _ in range(REFERENCE_HOLD_SUPPRESS):
        assert adapter._reference_check(detector_says, to_gray(frame))[12][3] == EMPTY
    # the detector keeps insisting: the reference loses, and drops itself so a real stone can land
    assert adapter._reference_check(detector_says, to_gray(frame))[12][3] == WHITE
    assert adapter._reference is None


def test_a_missing_stone_is_held_far_longer_than_an_invented_one():
    assert REFERENCE_HOLD_KEEP > 5 * REFERENCE_HOLD_SUPPRESS
    truth = _empty_board()
    truth[4][4] = BLACK
    frame = _board_frame([(4, 4, BLACK)])
    adapter = _with_reference("on", frame, truth)
    detector_says = truth.copy()
    detector_says[4][4] = EMPTY
    for _ in range(REFERENCE_HOLD_SUPPRESS + 5):
        assert adapter._reference_check(detector_says, to_gray(frame))[4][4] == BLACK
    assert adapter._reference is not None


def test_a_colour_disagreement_gets_the_short_hold_not_the_long_one():
    """board_state.py:316 releases a wrong colour after 15 raw frames by design; the reference must
    not re-block that for half a minute."""
    truth = _empty_board()
    truth[4][4] = BLACK
    frame = _board_frame([(4, 4, BLACK)])
    adapter = _with_reference("on", frame, truth)
    detector_says = truth.copy()
    detector_says[4][4] = WHITE
    for _ in range(REFERENCE_HOLD_SUPPRESS):
        assert adapter._reference_check(detector_says, to_gray(frame))[4][4] == BLACK
    assert adapter._reference_check(detector_says, to_gray(frame))[4][4] == WHITE


def test_the_hold_budget_is_cumulative_so_a_flapping_detector_cannot_reset_it():
    """A detector that sees the stone only every other frame would never exhaust a *consecutive*
    counter, and the suppression would be permanent."""
    frame = _board_frame()
    adapter = _with_reference("on", frame, _empty_board())
    invented, agreeing = _empty_board(), _empty_board()
    invented[12][3] = WHITE
    for _ in range(REFERENCE_HOLD_SUPPRESS):
        adapter._reference_check(invented, to_gray(frame))
        adapter._reference_check(agreeing, to_gray(frame))  # a frame where the detector agrees again
    assert adapter._reference_check(invented, to_gray(frame))[12][3] == WHITE


def test_a_real_change_is_left_alone_so_the_move_still_lands():
    adapter = _with_reference("on", _board_frame(), _empty_board())
    detector_says = _empty_board()
    detector_says[9][9] = WHITE
    out = adapter._reference_check(detector_says, to_gray(_board_frame([(9, 9, WHITE)])))
    assert out[9][9] == WHITE and adapter._ref_hold[9][9] == 0


def test_shadow_mode_reports_but_returns_the_board_untouched(caplog):
    frame = _board_frame()
    adapter = _with_reference("shadow", frame, _empty_board())
    detector_says = _empty_board()
    detector_says[12][3] = WHITE
    with caplog.at_level("INFO"):
        out = adapter._reference_check(detector_says, to_gray(frame))
    assert out is detector_says  # identical object: nothing downstream can diverge
    assert "would keep" in caplog.text and "(12,3)" in caplog.text


def test_a_lit_lamp_cell_is_left_to_the_detector():
    frame = _board_frame()
    adapter = _with_reference("on", frame, _empty_board())
    adapter._lit_points = {(12, 3)}
    detector_says = _empty_board()
    detector_says[12][3] = WHITE
    assert adapter._reference_check(detector_says, to_gray(frame))[12][3] == WHITE


def test_the_reference_is_taken_only_when_nothing_can_be_hiding_in_it():
    adapter = _adapter("on")
    frame = _board_frame([(4, 4, BLACK)])
    gray = to_gray(frame)
    board = _empty_board()
    board[4][4] = BLACK
    adapter._expected_np = board

    adapter._maybe_capture_reference(_empty_board(), _empty_board(), gray, motion_stable=True)  # camera disagrees
    assert adapter._reference is None
    adapter._maybe_capture_reference(board, board, gray, motion_stable=False)  # something is moving
    assert adapter._reference is None
    adapter._lit_points = {(3, 3)}
    adapter._maybe_capture_reference(board, board, gray, motion_stable=True)  # a lamp is lit
    assert adapter._reference is None
    adapter._lit_points = set()
    adapter._paused = True
    adapter._maybe_capture_reference(board, board, gray, motion_stable=True)  # recognition is paused
    assert adapter._reference is None
    adapter._paused = False
    real_detector, adapter._move_detector = adapter._move_detector, SimpleNamespace(pending_move=(4, 4, BLACK))
    adapter._maybe_capture_reference(board, board, gray, motion_stable=True)  # a move is being confirmed
    assert adapter._reference is None
    adapter._move_detector = real_detector
    adapter._ref_hold[7][7] = 1
    adapter._maybe_capture_reference(board, board, gray, motion_stable=True)  # a cell is under veto
    assert adapter._reference is None
    adapter._ref_hold[:] = 0
    stale = board.copy()
    stale[4][4] = EMPTY  # this frame's own observation has not caught up with the vote
    adapter._maybe_capture_reference(board, stale, gray, motion_stable=True)
    assert adapter._reference is None

    adapter._maybe_capture_reference(board, board, gray, motion_stable=True)
    assert adapter._reference is not None and adapter._reference.board[4][4] == BLACK


def test_the_same_expected_board_is_never_re_captured():
    """v1 re-took the reference every 2 s while the board was unchanged, which fixated a poisoned one."""
    adapter = _adapter("on")
    board = _empty_board()
    adapter._expected_np = board
    adapter._maybe_capture_reference(board, board, to_gray(_board_frame()), motion_stable=True)
    first = adapter._reference
    adapter._maybe_capture_reference(board, board, to_gray(_board_frame(seed=1)), motion_stable=True)
    assert adapter._reference is first

    board = board.copy()
    board[4][4] = BLACK
    adapter._expected_np = board
    adapter._maybe_capture_reference(board, board, to_gray(_board_frame([(4, 4, BLACK)])), motion_stable=True)
    assert adapter._reference is not first and adapter._reference.board[4][4] == BLACK


def test_the_reference_is_dropped_by_every_discontinuity():
    for command in (
        WorkerCommand(action=CommandType.UNBIND),
        WorkerCommand(action=CommandType.BIND),
        WorkerCommand(action=CommandType.RESET_SYNC),
        WorkerCommand(action=CommandType.ENTER_SETUP_MODE, data={"target_board": _empty_board().tolist()}),
        WorkerCommand(action=CommandType.SET_PAUSED, data={"paused": True}),
    ):
        adapter = _with_reference("on", _board_frame(), _empty_board())
        adapter._cmd_queue.put(command)
        adapter._drain_commands()
        assert adapter._reference is None, command.action

    adapter = _with_reference("on", _board_frame(), _empty_board())
    adapter.set_geometry(None)
    assert adapter._reference is None and adapter._ref_sampler is None


def test_a_move_keeps_the_reference_but_an_undo_or_a_jump_drops_it():
    ref_board = _empty_board()
    ref_board[4][4] = BLACK
    one_more = ref_board.copy()
    one_more[5][5] = WHITE
    undone = _empty_board()
    jumped = ref_board.copy()
    jumped[5][5] = WHITE
    jumped[6][6] = BLACK

    # the orchestrator re-sends the same board off game state, which must not count as a jump
    for board, kept in ((ref_board, True), (one_more, True), (undone, False), (jumped, False)):
        adapter = _with_reference("on", _board_frame([(4, 4, BLACK)]), ref_board)
        adapter._cmd_queue.put(WorkerCommand(action=CommandType.SET_EXPECTED_BOARD, data={"board": board.tolist()}))
        adapter._drain_commands()
        assert (adapter._reference is not None) is kept


def test_off_mode_never_takes_a_reference():
    adapter = _adapter("off")
    board = _empty_board()
    adapter._expected_np = board
    adapter._maybe_capture_reference(board, board, to_gray(_board_frame()), motion_stable=True)
    assert adapter._reference is None


# ---- through the real loop -------------------------------------------------------------------
# Helper-level tests cannot prove where the loop puts the two boards. These drive `_loop()` the way
# tests/test_vision/test_sustain_threshold.py does, with a scripted camera, scripted detections and
# scripted warped frames.

from unittest.mock import MagicMock  # noqa: E402

from katrain.vision.board_state import BoardStateExtractor  # noqa: E402
from katrain.vision.stone_detector import Detection  # noqa: E402
from tests.test_vision.board_state_corpus import grid_to_px  # noqa: E402


class _ScriptedDetector:
    instance = None

    def __init__(self, model_path, backend="ultralytics", confidence_threshold=0.5, **kwargs):
        self.confidence_threshold = confidence_threshold
        self.script = []
        _ScriptedDetector.instance = self

    def detect(self, image):
        return list(self.script.pop(0)) if self.script else []


class _ScriptedCamera:
    is_connected = True

    def __init__(self, frames, drop_reference_at=None):
        self.frames = frames
        self.drop_reference_at = drop_reference_at
        self.worker = None

    def read_frame(self):
        self.frames -= 1
        if self.frames == self.drop_reference_at:
            # a pause / resync / re-lock landing mid-placement, which is what opens the window
            self.worker._invalidate_reference("test")
        if self.frames <= 0:
            self.worker._running = False
        return np.zeros((10, 10, 3), dtype=np.uint8)


def _det(row, col, cls, conf=0.9):
    x, y = grid_to_px(CONFIG, float(col), float(row))
    return Detection(x_center=x, y_center=y, class_id=cls, confidence=conf, bbox=(x - 20, y - 20, x + 20, y + 20))


def _run_loop(mode, warped_frames, detection_script, game, averager=None, drop_reference_at=None):
    """Drive the real loop. `warped_frames` is one BGR frame per processed frame (the last repeats),
    `detection_script` one detection list per frame, `game` the expected board."""
    camera = _ScriptedCamera(len(detection_script), drop_reference_at)
    with mock_patch("katrain.vision.worker_inprocess.StoneDetector", _ScriptedDetector):
        worker = InProcessAdapter(
            {"board_size": 19, "enhance": "off", "auto_exposure": "off", "reference_check": mode}, camera=camera
        )
    camera.worker = worker
    worker.needs_frames = lambda: True
    worker._bound = True
    worker._geometry = SimpleNamespace(points=None)
    worker._expected_np = game
    worker._running = True
    worker._config["capture_fps"] = 100000
    worker._motion_is_stable = MagicMock(return_value=True)
    frames = list(warped_frames)
    worker._warp_frame = lambda frame: (frames.pop(0) if len(frames) > 1 else frames[0], True)
    worker._averager = MagicMock()
    worker._averager.add.side_effect = averager or (lambda frame: frame)
    extractor = BoardStateExtractor(CONFIG)
    worker._active_extractor = lambda: extractor
    worker._maybe_send_preview = MagicMock()
    worker._ref_sampler = _sampler()
    _ScriptedDetector.instance.script = [list(frame) for frame in detection_script]
    worker._loop()
    return worker


def _invented_stone_script(n=6):
    """The board is empty and the game agrees; from frame 3 the detector invents a white stone."""
    empty_frame = _board_frame()
    game = _empty_board()
    script = [[]] * 2 + [[_det(12, 3, 1)]] * n
    return [empty_frame], script, game


def test_on_mode_hides_the_invented_stone_downstream_but_keeps_recognition_history_raw():
    frames, script, game = _invented_stone_script()
    worker = _run_loop("on", frames, script, game)
    assert worker._reference is not None  # the first two frames agreed with the game: reference taken
    assert int(worker._last_stable_board[12][3]) == WHITE  # history stays raw, so the detector is visible
    assert int(worker.get_status().detected_board[12][3]) == EMPTY  # downstream got the corrected board


def test_shadow_mode_is_behaviour_identical_to_off():
    frames, script, game = _invented_stone_script()
    shadow = _run_loop("shadow", frames, script, game)
    off = _run_loop("off", frames, script, game)
    assert np.array_equal(shadow._last_stable_board, off._last_stable_board)
    assert np.array_equal(shadow.get_status().detected_board, off.get_status().detected_board)
    assert shadow.get_status().sync_state == off.get_status().sync_state


def test_the_check_runs_on_the_pre_average_frame():
    """If the comparison ever moved behind the frame averager, this fails: the averager here returns a
    flat frame, which has no structure to correlate, so nothing could be vetoed."""
    frames, script, game = _invented_stone_script()
    flat = _run_loop("on", frames, script, game, averager=lambda frame: np.full_like(frame, 128))
    assert int(flat.get_status().detected_board[12][3]) == EMPTY


def test_the_first_frame_of_a_real_stone_is_never_captured_as_a_reference():
    """The poisoning sequence: something drops the reference (pause, resync, re-lock) just as a stone
    is going down. On the first frame that shows it, the two-frame vote still says empty and
    MoveDetector has no pending move yet, so a capture there would photograph the stone and label its
    cell empty -- and then erase that stone for as long as the reference lives."""
    game = _empty_board()
    script = [[]] * 2 + [[_det(9, 9, 1)]] * 4
    frames = [_board_frame(), _board_frame(), _board_frame([(9, 9, WHITE)])]
    worker = _run_loop("on", frames, script, game, drop_reference_at=3)
    assert worker._reference is None or int(worker._reference.board[9][9]) == EMPTY
    if worker._reference is not None:  # a later frame may legitimately re-take it
        _, sim = worker._reference.unchanged(to_gray(_board_frame([(9, 9, WHITE)])), REFERENCE_ZNCC)
        assert sim[9][9] < REFERENCE_ZNCC, "the reference contains the stone it calls empty"
```

- [ ] **Step 2: 运行，确认失败**

Run: `uv run pytest tests/test_vision/test_reference_frame.py -q`
Expected: FAIL，`ImportError: cannot import name 'REFERENCE_ZNCC'`

- [ ] **Step 3: 实现 worker 改动**

3a. 导入（放在 `from katrain.vision.parallax import ...` 之后）：

```python
from katrain.vision.reference_frame import CellSampler, ReferenceFrame, build_sampler, to_gray
```

3b. 模块常量（放在 `GLOW_SETTLE_FRAMES = 2` 之后）：

```python
# Reference-frame check (2026-09-23). A cell whose ZNCC against the reference is at least this counts
# as structurally unchanged -- evidence, not proof, so every veto is bounded:
REFERENCE_ZNCC = 0.90
# ... a stone the game record knows but the detector now reads as EMPTY may be held through a long
# glare (far-side white stones were measured below the keep threshold for up to 45 s). If the hold is
# wrong (the player really took that stone off), the board surfaces it after this many frames plus
# Sync's own 7 s missing hold, so keep it well under a minute.
REFERENCE_HOLD_KEEP = 90  # frames, ~36 s at 2.3 fps
# ... while everything else is held only briefly: a stone on a point the game thinks is empty (the
# reference may be the wrong one -- captured with that stone already on the board and unnoticed), and
# a colour disagreement, which board_state.py:316 already releases on its own after 15 raw frames and
# must not be re-blocked for longer than that.
REFERENCE_HOLD_SUPPRESS = 10  # frames, ~4 s at 2.3 fps
```

3c. `__init__` 状态（紧跟 `self._glow_ref` 那一组之后）：

```python
        # Reference-frame check: the last frame whose *raw* board matched the game record, kept as
        # normalised per-cell patches in memory only -- never a file, one reference at a time.
        self._ref_mode = str(config.get("reference_check", "shadow"))
        self._ref_sampler: CellSampler | None = None
        self._reference: ReferenceFrame | None = None
        self._ref_hold = np.zeros((board_config.grid_size, board_config.grid_size), dtype=int)
        self._ref_log_frame = -1
```

3d. `set_geometry` 开头，紧跟 `self._motion_filter.reset()`：

```python
        self._ref_sampler = None
        self._invalidate_reference("geometry")  # patches are tied to this warp
```

3e. `_drain_commands`：`BIND`、`UNBIND`、`RESET_SYNC`、`ENTER_SETUP_MODE` 各加一行
`self._invalidate_reference("<command>")`；`SET_PAUSED` 分支在设置 `self._paused` 之后加：

```python
                if self._paused:
                    self._invalidate_reference("paused")
```

`PAUSE_DETECTION` 分支同样加 `self._invalidate_reference("paused")`。

`SET_EXPECTED_BOARD` 分支，在 `board` 解析出来之后（`self._expected_np` 赋值附近）加：

```python
                if self._reference is not None and not np.array_equal(board, self._reference.board):
                    # The reference stays valid only while the game moved FORWARD from the position it
                    # shows: every stone it holds is still there in the same colour, and at most one
                    # new stone appeared. Undo, navigation to a sibling, a new game and an undone
                    # capture all take a stone away from that position, so they drop it. The equality
                    # guard above matters on its own: the orchestrator re-sends the same expected
                    # board off game state (physical_play_orchestrator.py:160), not off a change
                    # event, and a re-send would otherwise read as "zero stones added" and drop the
                    # reference at game-update frequency.
                    # Known and accepted: a setup edit that only adds one stone looks like a move
                    # here. The capture guards and REFERENCE_HOLD_SUPPRESS bound that case.
                    ref_board = self._reference.board
                    kept = bool(np.all((ref_board == EMPTY) | (board == ref_board)))
                    added = int(((ref_board == EMPTY) & (board != EMPTY)).sum())
                    if not kept or added > 1:
                        self._invalidate_reference("expected board is no longer a move ahead")
```

3f. 三个新方法（放在 `_measure_pending_glow` 之前）：

```python
    def _invalidate_reference(self, reason: str) -> None:
        if self._reference is not None:
            logger.info("refcheck reference dropped: %s", reason)
        self._reference = None
        self._ref_hold[:] = 0

    def _reference_check(self, board: np.ndarray, gray: np.ndarray | None) -> np.ndarray:
        """The board to hand downstream: cells that still look exactly as they did when the board last
        matched the game record keep that value, for a bounded number of frames.

        The caller's array is the recognition pipeline's own history and is never modified: a veto
        must not feed back into hysteresis, the sustain tier or the colour-flip release, or a wrong
        veto would have no way out (it would keep re-asserting itself through the state it corrupted).
        """
        reference = self._reference
        if reference is None or gray is None:
            return board
        try:
            unchanged, sim = reference.unchanged(gray, REFERENCE_ZNCC)
        except ValueError:  # frame size changed under us; the next capture rebuilds the sampler
            self._ref_sampler = None
            self._invalidate_reference("frame size")
            return board
        for row, col in self._lit_points:
            unchanged[row][col] = False  # a lit lamp changes the cell's look on its own
        disagree = unchanged & (board != reference.board)
        if not disagree.any():
            return board
        # Counted over this reference's whole life, never reset on an agreeing frame: a detector that
        # sees the stone only every other frame would never exhaust a consecutive counter, and the
        # veto would become permanent -- exactly the failure the limit exists to prevent. A new
        # reference zeroes them.
        self._ref_hold[disagree] += 1
        # Only "the game knows a stone here and the detector now sees nothing" earns the long hold.
        # A colour disagreement gets the short one: board_state.py:316 releases a wrong colour after
        # 15 raw frames by design, and this must not quietly re-block that for half a minute.
        missing = (reference.board != EMPTY) & (board == EMPTY)
        limit = np.where(missing, REFERENCE_HOLD_KEEP, REFERENCE_HOLD_SUPPRESS)
        if (disagree & (self._ref_hold > limit)).any():
            # The detector has insisted for too long. It wins, and the reference goes: if it was the
            # poisoned one (a stone already on the board when it was taken), this is the only exit.
            self._invalidate_reference("the detector kept disagreeing")
            return board
        rows, cols = np.nonzero(disagree)
        if self._frame_count != self._ref_log_frame:
            self._ref_log_frame = self._frame_count
            shown = ", ".join(
                f"({r},{c}) board={board[r][c]} ref={reference.board[r][c]} zncc={sim[r][c]:.2f} "
                f"held={self._ref_hold[r][c]}/{limit[r][c]}"
                for r, c in list(zip(rows.tolist(), cols.tolist()))[:4]
            )
            logger.info(
                "refcheck %s %d cell(s): %s%s",
                "keeps" if self._ref_mode == "on" else "would keep",
                len(rows),
                shown,
                " ..." if len(rows) > 4 else "",
            )
        if self._ref_mode != "on":
            return board  # shadow: the same object, so nothing downstream can diverge
        effective = board.copy()
        effective[disagree] = reference.board[disagree]
        return effective

    def _maybe_capture_reference(
        self, board: np.ndarray, observed: np.ndarray, gray: np.ndarray | None, motion_stable: bool
    ) -> None:
        """Take a new reference only when nothing can be hiding in the picture.

        `board` is the RAW voted board and `observed` this frame's pre-vote observation; both must
        equal the game record. Requiring only the voted one is not enough: the two-frame vote holds
        the previous value on the first frame a cell changes, so the very frame a new stone appears
        still votes "empty" while `pending_move` is not set yet (MoveDetector runs later in the loop).
        That frame would photograph the stone and label its cell empty. The pre-vote board sees the
        stone immediately, so demanding both closes that window.

        Never pass the reference-corrected board here: a corrected board would let a wrong veto
        authorise its own replacement reference. Even with all of this, board == game record is
        agreement between two fallible matrices, not proof of the pixels -- REFERENCE_HOLD_SUPPRESS is
        the last line.
        """
        expected = self._expected_np
        if (
            self._ref_mode == "off"
            or gray is None
            or not self._bound
            or self._paused
            or not motion_stable
            or self._lit_points
            or expected is None
            or self._geometry is None
            or self._move_detector.pending_move is not None
            or bool(self._ref_hold.any())
            or not np.array_equal(board, expected)
            or not np.array_equal(observed, expected)
        ):
            return
        if self._reference is not None and np.array_equal(self._reference.board, board):
            return  # nothing new to record
        h, w = gray.shape[:2]
        if self._ref_sampler is None or (self._ref_sampler.img_w, self._ref_sampler.img_h) != (w, h):
            extractor = self._active_extractor()
            self._ref_sampler = build_sampler(w, h, extractor.config, extractor.parallax)
        self._reference = ReferenceFrame(self._ref_sampler, gray, board)
        self._ref_hold[:] = 0
```

3g. 主循环：在 `_warp_frame` 之后、`self._averager.add(warped)` 之前取灰度图：

```python
                    # Reference-frame check runs on the warped frame BEFORE the averager and BEFORE
                    # CLAHE -- see to_gray's docstring for why either one would break it.
                    ref_gray = to_gray(warped) if self._ref_mode != "off" else None
```

3h. 主循环：把两帧投票之后那一段改成（`_log_board_delta` 和两处历史赋值保持 raw，不要动）：

```python
                    raw_observation = observed_board  # pre-vote, needed by the capture guard
                    self._prev_observed_board = observed_board
                    self._last_stable_board = stable_board
                    if tr:
                        tr.mark("assign")
                    observed_board = self._reference_check(stable_board, ref_gray)
                    self._maybe_capture_reference(stable_board, raw_observation, ref_gray, motion_stable=True)
                    if tr:
                        tr.mark("refchk")
                    self._observation_seq += 1
```

（顺序是先检查后拍照：检查会在到达上限时作废参照，而拍照要求「当前无任何否决」。）

- [ ] **Step 4: 运行，确认通过**

Run: `uv run pytest tests/test_vision/test_reference_frame.py -q`
Expected: 31 passed

- [ ] **Step 5: 跑整套视觉测试，确认没有回归**

Run: `uv run pytest tests/test_vision -q`
Expected: 全部通过（基线 799 passed + 本计划新增）

- [ ] **Step 6: 格式化并提交**

```bash
uv run black -l 120 katrain/vision/worker_inprocess.py tests/test_vision/test_reference_frame.py
git add katrain/vision/worker_inprocess.py tests/test_vision/test_reference_frame.py
git commit -m "feat(vision): reference-frame evidence for the board handed downstream, shadow by default

The worker keeps one reference: the last still frame, no lamp lit, no move pending, whose RAW voted
board equalled the game record. Cells that still correlate with it keep the reference's occupancy in
the board handed to move detection, sync and status -- which is where the daylight false negatives and
false positives die.

Three bounds keep a wrong reference from becoming a stuck board: recognition's own history
(_last_stable_board, _prev_observed_board, hysteresis, the sustain tier, the colour-flip release) stays
raw, so the detector's disagreement stays visible; a stone the game knows is held at most
REFERENCE_HOLD_KEEP frames and a stone it does not know is suppressed at most REFERENCE_HOLD_SUPPRESS;
and the reference is dropped by bind, unbind, resync, setup, pause, re-lock and any expected-board jump
that is not a single added stone.

Default mode is shadow: it computes and logs what it would keep and returns the caller's own array.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: 配置项与命令行开关

**Files:**
- Modify: `katrain/vision/config_service.py`
- Modify: `katrain/web/server.py`
- Test: `tests/test_vision/test_reference_frame.py`（末尾追加）

**Interfaces:**
- Produces: `VisionServiceConfig.reference_check: str = "shadow"`；`to_worker_config()["reference_check"]`；`--vision-reference-check {off,shadow,on}`。

- [ ] **Step 1: 写失败的测试**

```python
def test_the_worker_config_carries_the_reference_check_mode():
    from katrain.vision.config_service import VisionServiceConfig

    assert VisionServiceConfig().to_worker_config()["reference_check"] == "shadow"
    assert VisionServiceConfig(reference_check="on").to_worker_config()["reference_check"] == "on"
```

- [ ] **Step 2: 运行，确认失败**

Run: `uv run pytest tests/test_vision/test_reference_frame.py -q -k reference_check_mode`
Expected: FAIL，`KeyError: 'reference_check'`

- [ ] **Step 3: 实现**

`config_service.py`，`ae_target` 字段之后：

```python
    # Reference-frame check ("off" | "shadow" | "on", 2026-09-23): compare each cell against the last
    # frame whose raw board matched the game record and keep the occupancy of cells that look
    # unchanged, bounded per cell. "shadow" computes and logs it without touching recognition — the
    # default until board data in daylight sets the threshold and the two hold limits.
    # See superpowers/tracks/vision-optimizations/reference-frame/design.md.
    reference_check: str = "shadow"
```

`to_worker_config()` 的字典里，`"parallax_auto": self.parallax_enabled,` 之后：

```python
            "reference_check": self.reference_check,
```

`server.py`，`--vision-auto-exposure` 的 `add_argument` 之前：

```python
    parser.add_argument(
        "--vision-reference-check",
        choices=["off", "shadow", "on"],
        default=None,
        help="Per-cell comparison against the last frame whose board matched the game: 'on' keeps the "
        "occupancy of cells that look structurally unchanged (bounded per cell), 'shadow' only logs "
        "what it would do (default), 'off' disables it.",
    )
```

参数装配处，`auto_exposure` 那两行之后：

```python
        if args.vision_reference_check is not None:
            vision_kwargs["reference_check"] = args.vision_reference_check
```

- [ ] **Step 4: 运行，确认通过**

Run: `uv run pytest tests/test_vision -q`
Expected: 全部通过

- [ ] **Step 5: 格式化并提交**

```bash
uv run black -l 120 katrain/vision/config_service.py katrain/web/server.py
git add katrain/vision/config_service.py katrain/web/server.py tests/test_vision/test_reference_frame.py
git commit -m "feat(vision): --vision-reference-check {off,shadow,on}

The box takes the mode from its systemd drop-in like every other vision knob; the default stays
shadow, so deploying this changes no recognition until the daylight data is in.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: 成本核实与文档收口

**Files:**
- Modify: `superpowers/tracks/vision-optimizations/reference-frame/design.md`（§11、§12 补实测数字）

- [ ] **Step 1: 本机量一次每帧成本与内存**

```bash
uv run python -c "
import time, tracemalloc, numpy as np
from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig
from katrain.vision.reference_frame import ReferenceFrame, build_sampler
cfg = BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS)
s = build_sampler(1056, 1056, cfg)
g = np.random.default_rng(0).integers(0, 255, (1056, 1056), dtype=np.uint8)
r = ReferenceFrame(s, g, np.zeros((19,19), int))
tracemalloc.start()
t = time.monotonic()
for _ in range(50): r.similarity(g)
ms = (time.monotonic()-t)/50*1000
cur, peak = tracemalloc.get_traced_memory()
print(f'per frame {ms:.1f} ms, peak transient {peak/2**20:.1f} MiB, index {s.flat_index.nbytes/2**20:.1f} MiB, ref {r.normalised.nbytes/2**20:.1f} MiB')
"
```

Expected: 本机每帧 < 10 ms。板子约为本机的 5–10 倍；真值等部署后在板上用 vtrace 的 refchk 段量。

- [ ] **Step 2: 把数字与「板上待答问题」写进 spec §11、§12**

要写清：本机每帧毫秒数与内存；板上 shadow 要收集的四项（会纠正的假阴性数、会纠正的假阳性数、
会挡住真落子的次数、未变格子的 ZNCC 分布）；以及三个待定值 `REFERENCE_ZNCC`、
`REFERENCE_HOLD_KEEP`、`REFERENCE_HOLD_SUPPRESS`。

- [ ] **Step 3: 提交**

```bash
git add superpowers/tracks/vision-optimizations/reference-frame/design.md
git commit -m "docs(vision): reference-frame cost on this machine and what the board run must answer

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## 完成后的动作（不在任务内，由本会话执行）

1. Codex 第二轮审核（本计划 v2）。
2. `/code-review` 技能审这一串改动（Fan 2026-09-23 要求）。
3. 部署到 RK3562（rsync 四个文件 + 重启），白天开一局，`vtrace` 里看 `refchk` 耗时，日志里收 `refcheck` 数据。
4. 据数据定三个常量，再决定是否把 `on` 交给板子。

## 明确不做（本轮）

- 不改曝光控制、不动 `--vision-auto-exposure off`（见 `docs/known-issue-overexposure.md`）。
- 不做「变化形状是否像棋子」的第二条判据。
- 不把参照图写进文件。
- 不因本功能调整任何既有阈值。
- 不改 `katrain/vision/worker.py`（子进程 worker）：板上跑的是 in-process 适配器，实测有据；
  子进程 worker 在板上不参与，本轮不做双实现（若将来板上改走子进程，这条要连同测试一起补）。
