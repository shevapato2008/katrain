# 棋子成像视差修正 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 geometry-lock 识别链的「像素 → 连续网格坐标」之后、「取整到交点」之前补上棋子视差修正,
并提供现场标定工具与可对照的诊断,修正关着时行为与今天逐位相同。

**Architecture:** 纯函数 `coordinates.apply_parallax` 做一次位似;`BoardStateExtractor` 用一个私有方法
`_positions` 统一产出「原始 / 修正后」坐标,所有下游都从它取;参数来自板上独立文件
`<hardware-vision-dir>/parallax/go-19x19.json`,由 server 启动时读进 `VisionServiceConfig.parallax`,
经 worker config 只交给 geometry-lock 那个 extractor;板上命令行工具拟合并写这个文件。

**Tech Stack:** Python 3.12、numpy、pytest;OpenCV / RKNN 只在标定工具的采帧部分用到。

**Spec:** `superpowers/tracks/vision-stone-parallax/design.md`(设计)与同目录 `prd.md`(需求,含 2026-09-22 修订)。
执行者两份都要读;本计划的每条验收都能在 prd.md §3 里找到出处(见文末「验收对照」)。

## Global Constraints

来自 kickoff §1 与 prd.md,**每个任务都隐含包括这些**:

1. 偏移 = 以 nadir 为中心、系数 k = (H−h)/H 的一次位似,反向是精确解,不迭代。
2. k 在仿射变换下不变 ⇒ 修正直接做在连续网格坐标 (fx, fy) 上,k 不换算,nadir 表示成同一坐标系里的一对数。
3. **nadir 必须现场标定,不许把 CAD 值写进生产代码**。CAD 值只允许出现在测试的合成数据里,且标明是合成数据。
4. **`physical_to_grid` 与 `continuous_grid_pos` 一字不动**;修正只插在 `board_state.py` 里。
5. **边距 DROP 行为不许回归**:原始坐标或修正后坐标任一取整出界就 DROP。
6. **未标定(parallax 为 None)时整条修正是恒等映射,行为与今天逐位相同**;`k == 1.0` 同样逐位相同。
7. 不碰 YOLO 权重 / 推理后端 / warp / board_finder / geometry_lock / 四角检测 / `worker.py`。
8. `apply_parallax` **不是幂等的**(两次 = k²):每个检测只修正一次,只在 `BoardStateExtractor._positions` 里调用。
9. `detection_points` 返回值形状不变(4 元组);`ambiguous_stone` 事件结构不变。
10. Python 代码 Black 120 列;注释与 docstring 用英文,和周边代码一致。

**环境(所有任务通用)**

- 工作目录:`/Users/fan/Repositories/katrain-vision-stone-parallax`(worktree,分支 `feature/vision-stone-parallax`)。
- Python:`PY=/Users/fan/Repositories/katrain-vision-stone-parallax/.venv/bin/python`。这个 venv 已用
  `uv sync --extra web --extra vision --extra board` 装好;**只给 `--extra web` 会缺 cv2,`tests/test_vision` 会整片
  收集失败,看起来像你的改动弄红的**。所有 `pytest` 一律 `"$PY" -m pytest ... -p no:cacheprovider`。
- 参考脚本 `superpowers/tracks/vision-stone-parallax/parallax_correct.py` 可以用 `"$PY"` 或 `/opt/homebrew/bin/python3`
  跑(系统 `python3` 没有 numpy)。**仓库里的测试不许 import 这些参考脚本。**
- 基线:`tests/test_vision` 在 develop `34e9c7b6` 上 651 passed。

**共用工作树的纪律(并行执行时必须遵守)**

- 只用 `git add -- <本任务列出的路径>`;**禁止** `git add -A`、`git commit -a`、`git commit --amend`、`git stash`、
  `git checkout/restore/reset` 任何不是自己刚改的文件。`index.lock` 冲突就等几秒重试。
- **变异检查一律在一次性 worktree 里做**(命令在各任务里写全),绝不在共享工作树里改源码再还原。
- 执行者如果认为需要改上面第 1–9 条、或要动 YOLO / warp / `physical_to_grid`:**不许自己批准**。停下报告;
  控制者派独立 Opus agent 裁决替代方案,裁决与理由记进 ledger,留给 Fan 复核。

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `katrain/vision/coordinates.py` | 改 | 新增 `apply_parallax` |
| `katrain/vision/parallax.py` | 新建 | `ParallaxParams`、`FitResult`、`fit_parallax`(纯 numpy) |
| `katrain/vision/parallax_store.py` | 新建 | `ParallaxCalibration`、`parallax_path`、`load_parallax`、`save_parallax`、`H_IMPLIED_WINDOW_MM`、`attach_parallax` |
| `katrain/vision/board_state.py` | 改 | 构造参数 `parallax`、`_positions`、`_on_board`、D7 规则、`parallax_points` |
| `katrain/vision/config_service.py` | 改 | `VisionServiceConfig.parallax` 与 `to_worker_config` |
| `katrain/vision/worker_inprocess.py` | 改 | locked extractor 接参数;`_log_board_delta` 诊断 |
| `katrain/web/server.py` | 改 | 启动时 `attach_parallax` + 一行日志 |
| `katrain/vision/tools/calibrate_parallax.py` | 新建 | 板上标定工具:判定(纯)+ 采帧 + CLI |
| `tests/test_vision/board_state_corpus.py` | 新建 | 确定性检测语料 + 金样生成器 |
| `tests/test_vision/data/board_state_golden.json` | 新建 | 修正前代码产出的金样 |
| `tests/test_vision/parallax_synth.py` | 新建 | ver9 合成几何(测试专用) |
| `tests/test_vision/test_board_state_golden.py` | 新建 | 修正关着时逐位等于金样 |
| `tests/test_vision/test_parallax_apply.py` | 新建 | `apply_parallax` / `ParallaxParams` |
| `tests/test_vision/test_board_state_parallax.py` | 新建 | 361 健全、远端区分、边距带、单次修正、`parallax_points` |
| `tests/test_vision/test_parallax_fit.py` | 新建 | 拟合 |
| `tests/test_vision/test_parallax_store.py` | 新建 | 文件格式与读写 |
| `tests/test_vision/test_parallax_wiring.py` | 新建 | config / adapter / `attach_parallax` / 诊断日志 |
| `tests/test_vision/test_calibrate_parallax.py` | 新建 | 标定工具判定与写文件 |
| `superpowers/tracks/vision-stone-parallax/handoff.md` | 新建 | 上板步骤与待填的对照数据 |

## 依赖与并行

| 批次 | 任务 | 前置 | 改动的文件互不重叠 |
|---|---|---|---|
| W1 | Task 1、Task 2 | — | 是 |
| W2 | Task 3、Task 4、Task 5 | T3 需要 T1+T2;T4、T5 需要 T2 | 是(T4 只追加 `parallax.py` 末尾,T2 已提交) |
| W3 | Task 6、Task 8 | T6 需要 T3+T5;T8 需要 T3+T4+T5 | 是 |
| W4 | Task 7 | T3、T6(同改 `worker_inprocess.py`,必须在 T6 之后) | — |
| W5 | Task 9 | 全部 | — |
| 明天 | Task 10(上板) | Task 9 + Fan 在场、RK3562 已连上 | — |

---

### Task 1: 修正前行为的金样

在动 `board_state.py` 之前,把今天的输出冻成金样。之后「修正关着时逐位相同」(prd P1-1 验收 1)就拿它比。

**Files:**
- Create: `tests/test_vision/board_state_corpus.py`
- Create: `tests/test_vision/data/board_state_golden.json`(由脚本生成)
- Test: `tests/test_vision/test_board_state_golden.py`

**Interfaces:**
- Consumes: 现有 `BoardStateExtractor(config)`、`_grid_cell`、`detection_points`、`detections_to_board`、`cell_top`、`cell_confidences`。
- Produces(后续任务用):`IMG: int = 1056`、`grid_to_px(cfg, fx, fy, img=IMG) -> (x, y)`、`GOLDEN_PATH`、
  `run_all(make_extractor: Callable[[BoardConfig], BoardStateExtractor]) -> dict`。

**约束(从 Global 摘):** 第 6 条;不许改任何生产代码。

- [ ] **Step 1: 写语料与生成器**

`tests/test_vision/board_state_corpus.py`:

```python
"""Deterministic detection corpus that characterizes BoardStateExtractor (vision-stone-parallax track).

The golden file was produced by the pre-parallax extractor. With parallax off, the extractor must
reproduce it bit-for-bit (prd P1-1 acceptance 1). The corpus covers every path the parallax change
touches: on-grid stones with jitter, cell-boundary straddlers (sticky / spill), same-point
collisions, warp-margin objects on both sides of the drop line, LED classes, lit-cell masks,
hysteresis, presence sustain and colour flips carried across frames.

Regenerate ONLY from a commit whose board_state.py predates the parallax change:
    .venv/bin/python -m tests.test_vision.board_state_corpus --write
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from katrain.vision.board_state import BoardStateExtractor
from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig
from katrain.vision.stone_detector import Detection

GOLDEN_PATH = Path(__file__).parent / "data" / "board_state_golden.json"
IMG = 1056  # 950 + 2 * 53: the geometry-lock warp canvas with its 1-cell margin
FRAMES = 24
SEED = 20260922
CONFIGS = {
    "margin": lambda: BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS),
    "plain": lambda: BoardConfig(),
}


def grid_to_px(cfg, fx, fy, img=IMG):
    """Inverse of pixel_to_physical + continuous_grid_pos: continuous grid (fx, fy) -> warped pixel."""
    gs = cfg.grid_size - 1
    x_mm = cfg.border_width_mm + fx * cfg.board_width_mm / gs
    y_mm = cfg.border_length_mm + fy * cfg.board_length_mm / gs
    return x_mm * img / cfg.total_width, y_mm * img / cfg.total_length


def build_frames(cfg, seed=SEED):
    rng = np.random.default_rng(seed)
    scene = {}
    frames = []

    def det(fx, fy, cls, conf):
        x, y = grid_to_px(cfg, fx, fy)
        return Detection(x_center=float(x), y_center=float(y), class_id=int(cls), confidence=float(conf))

    for t in range(FRAMES):
        for _ in range(2):
            r, c = (int(v) for v in rng.integers(0, 19, 2))
            scene[(r, c)] = int(rng.integers(0, 2))
        keys = sorted(scene)
        if keys and rng.random() < 0.3:
            del scene[keys[int(rng.integers(0, len(keys)))]]
        keys = sorted(scene)
        if keys and rng.random() < 0.3:
            k = keys[int(rng.integers(0, len(keys)))]
            scene[k] = 1 - scene[k]
        dets = []
        for (r, c), cls in sorted(scene.items()):
            jx, jy = rng.normal(0, 0.15, 2)
            dets.append(det(c + jx, r + jy, cls, rng.uniform(0.3, 0.95)))
        for _ in range(3):  # cell-boundary straddlers (sticky / spill)
            r, c = (int(v) for v in rng.integers(0, 19, 2))
            off = float(rng.choice([-0.5, 0.5]) + rng.normal(0, 0.05))
            fx, fy = (c + off, r) if rng.random() < 0.5 else (c, r + off)
            dets.append(det(fx, fy, rng.integers(0, 2), rng.uniform(0.3, 0.95)))
        for _ in range(2):  # same-point collisions
            if scene:
                r, c = sorted(scene)[int(rng.integers(0, len(scene)))]
                jx, jy = rng.normal(0, 0.1, 2)
                dets.append(det(c + jx, r + jy, rng.integers(0, 2), rng.uniform(0.3, 0.95)))
        for _ in range(4):  # warp-margin objects on all four sides, both sides of the drop line
            u, v = float(rng.uniform(-0.95, -0.3)), float(rng.uniform(0, 18))
            fx, fy = [(u, v), (18 - u, v), (v, u), (v, 18 - u)][int(rng.integers(0, 4))]
            dets.append(det(fx, fy, rng.integers(0, 4), rng.uniform(0.3, 0.95)))
        for _ in range(2):  # LED-class detections on the grid
            r, c = (int(v) for v in rng.integers(0, 19, 2))
            dets.append(det(c, r, rng.integers(2, 4), rng.uniform(0.3, 0.95)))
        masked = {tuple(int(v) for v in rng.integers(0, 19, 2)) for _ in range(3)}
        add_threshold = None if t % 3 == 0 else 0.5
        frames.append((dets, masked, add_threshold))
    return frames


def _board_str(board):
    return "".join(str(int(v)) for v in np.asarray(board).ravel())


def run(extractor, frames):
    """Every BoardStateExtractor output the parallax change can reach, frame by frame, on ONE
    extractor instance (the colour-flip streak is instance state carried across frames)."""
    out = []
    prev_stable = None
    prev_raw = None
    for dets, masked, add_threshold in frames:
        cells = [extractor._grid_cell(d, IMG, IMG) for d in dets]
        legacy = extractor.detections_to_board(
            dets, IMG, IMG, occupancy_aware=False, masked_cells=masked, prev_board=prev_stable, add_threshold=add_threshold
        )
        occ = extractor.detections_to_board(
            dets,
            IMG,
            IMG,
            occupancy_aware=True,
            masked_cells=masked,
            prev_board=prev_stable,
            add_threshold=add_threshold,
            sticky_board=prev_raw,
        )
        out.append(
            {
                "grid_cell": [None if g is None else [int(g[0]), int(g[1])] for g in cells],
                "points": [
                    [float(fy), float(fx), int(cls), float(conf)]
                    for fy, fx, cls, conf in extractor.detection_points(dets, IMG, IMG)
                ],
                "legacy": _board_str(legacy),
                "occupancy": _board_str(occ),
                "cell_top": sorted(
                    [int(r), int(c), float(conf), int(cls)]
                    for (r, c), (conf, cls) in extractor.cell_top(dets, IMG, IMG).items()
                ),
                "cell_conf": sorted(
                    [int(r), int(c), float(v)] for (r, c), v in extractor.cell_confidences(dets, IMG, IMG).items()
                ),
            }
        )
        prev_raw = occ
        prev_stable = occ.copy()
    return out


def run_all(make_extractor):
    """make_extractor(config) -> BoardStateExtractor; returns {config name: [per-frame outputs]}."""
    return {name: run(make_extractor(factory()), build_frames(factory())) for name, factory in CONFIGS.items()}


def _write_golden():
    import katrain.vision.board_state as board_state

    if "parallax" in Path(board_state.__file__).read_text():
        sys.exit("refusing: board_state.py already knows about parallax; the golden must come from pre-parallax code")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    payload = {"generated_at_commit": commit, "outputs": run_all(BoardStateExtractor)}
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    print(f"wrote {GOLDEN_PATH} ({GOLDEN_PATH.stat().st_size} bytes) from {commit}")


if __name__ == "__main__":
    if sys.argv[1:] != ["--write"]:
        sys.exit("usage: python -m tests.test_vision.board_state_corpus --write")
    _write_golden()
```

- [ ] **Step 2: 生成金样**

Run: `cd /Users/fan/Repositories/katrain-vision-stone-parallax && "$PY" -m tests.test_vision.board_state_corpus --write`
Expected: `wrote .../board_state_golden.json (约 185000 bytes) from 34e9c7b6...`(或 develop 之上本分支的某个
提交;只要 `board_state.py` 还没改就行)。

- [ ] **Step 3: 写测试**

`tests/test_vision/test_board_state_golden.py`:

```python
"""With parallax off, BoardStateExtractor must reproduce the pre-parallax outputs bit-for-bit
(prd P1-1 acceptance 1). The golden file names the commit it was generated on; see
board_state_corpus.py for what the corpus covers and how to regenerate it."""

import json

from katrain.vision.board_state import BoardStateExtractor
from tests.test_vision.board_state_corpus import GOLDEN_PATH, run_all


def _golden():
    return json.loads(GOLDEN_PATH.read_text())


def _first_difference(got, want):
    for name in want:
        for i, (g, w) in enumerate(zip(got[name], want[name])):
            for key in w:
                if g[key] != w[key]:
                    return f"config={name} frame={i} key={key}"
    return None


def test_golden_records_its_source_commit():
    assert len(_golden()["generated_at_commit"]) == 40


def test_extractor_reproduces_golden():
    want = _golden()["outputs"]
    got = json.loads(json.dumps(run_all(BoardStateExtractor)))
    assert _first_difference(got, want) is None, _first_difference(got, want)
    assert got == want
```

- [ ] **Step 4: 跑测试**

Run: `"$PY" -m pytest tests/test_vision/test_board_state_golden.py -q -p no:cacheprovider`
Expected: `2 passed`

- [ ] **Step 5: 提交**

```bash
git add -- tests/test_vision/board_state_corpus.py tests/test_vision/data/board_state_golden.json tests/test_vision/test_board_state_golden.py
git commit -m "test(vision): freeze pre-parallax BoardStateExtractor outputs as a golden

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 6: 变异检查(一次性 worktree)—— 证明金样闸会红**

```bash
MUT=$(mktemp -d)/wt && git worktree add --detach "$MUT" HEAD
"$PY" - "$MUT/katrain/vision/board_state.py" <<'EOF'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); s = p.read_text()
old = "        if 0 <= cy < gs and 0 <= cx < gs:\n            return cy, cx\n        return None\n"
assert s.count(old) == 1
p.write_text(s.replace(old, "        return min(gs - 1, max(0, cy)), min(gs - 1, max(0, cx))\n"))
EOF
(cd "$MUT" && "$PY" -c 'import katrain.vision.board_state as m; print(m.__file__)')
(cd "$MUT" && "$PY" -m pytest tests/test_vision/test_board_state_golden.py -q -p no:cacheprovider)
git worktree remove --force "$MUT"
```
Expected:第一条打印的路径在 `$MUT` 下面;pytest `1 failed, 1 passed`(DROP 改成 clamp 被抓到)。
设计阶段已在进程内验过这套语料对 7 种变异都会红:clamp、`STICKY_RADIUS`、`SUSTAIN_RADIUS`、
`SPILL_MIN_CONFIDENCE`(0 与 1.1)、`COLOR_FLIP_RELEASE_FRAMES`、「所有坐标往 nadir 收缩」。

**验收:** 金样文件已提交且记录了源提交;测试在当前代码上 2 passed;clamp 变异下变红。

---

### Task 2: `apply_parallax` 与 `ParallaxParams`

**Files:**
- Modify: `katrain/vision/coordinates.py`(文件末尾追加)
- Create: `katrain/vision/parallax.py`
- Create: `tests/test_vision/parallax_synth.py`
- Test: `tests/test_vision/test_parallax_apply.py`

**Interfaces:**
- Produces:
  - `apply_parallax(fx: float, fy: float, nadir: tuple[float, float] | None, k: float | None) -> tuple[float, float]`
  - `ParallaxParams(nadir_fx: float, nadir_fy: float, k: float)`(frozen),`.nadir -> tuple[float, float]`,`.to_dict() -> dict`
  - 测试辅助 `tests.test_vision.parallax_synth`:`K_TRUE`、`NADIR_GRID`、`H_MM`、`H_STONE_MM`、
    `grid_to_mm(fx, fy)`、`mm_to_grid(x, y)`、`detected_grid(col, row, k=K_TRUE, outward_cells=0.0) -> (fx, fy)`

**约束:** 第 3、4、6、8 条。`coordinates.py` 里现有函数一字不动,只在末尾追加。

- [ ] **Step 1: 写合成几何辅助**

`tests/test_vision/parallax_synth.py`:

```python
"""Synthetic ver9 stone-parallax geometry for tests ONLY.

Constants are the CAD-derived values of superpowers/tracks/vision-stone-parallax/geometry.md §3.
Production never uses them: the nadir must be calibrated on site (prd P1-2). Grid convention matches
the geometry-lock warp: fx = column, fy = row, row 0 is the far side (away from the camera), and the
nadir lies beyond row 18 on the camera side.
"""

import math

CAM_MM = (0.0, -70.545)  # lens projection centre dropped onto the board plane
H_MM = 339.4424  # lens height above the board surface
H_STONE_MM = 3.5  # detected stone centre height = half the 7 mm thickness
K_TRUE = (H_MM - H_STONE_MM) / H_MM
X0_MM, Y0_MM = -213.3, -502.0  # grid line 0 (column A / far row)
PX_MM, PY_MM = 23.7, 22.0  # column / row pitch
NADIR_GRID = ((CAM_MM[0] - X0_MM) / PX_MM, (CAM_MM[1] - Y0_MM) / PY_MM)  # (9.0, 19.6116)


def grid_to_mm(fx, fy):
    return X0_MM + fx * PX_MM, Y0_MM + fy * PY_MM


def mm_to_grid(x, y):
    return (x - X0_MM) / PX_MM, (y - Y0_MM) / PY_MM


def _forward_mm(x, y, k):
    return CAM_MM[0] + (x - CAM_MM[0]) / k, CAM_MM[1] + (y - CAM_MM[1]) / k


def detected_grid(col, row, k=K_TRUE, outward_cells=0.0):
    """Where the detector would report a stone whose contact point is (col, row), optionally displaced
    ``outward_cells`` further away from the camera (radially from the nadir, measured in grid cells).
    The forward model runs in millimetres, so the anisotropic 23.7 x 22.0 pitch is real, not assumed away."""
    fx, fy = float(col), float(row)
    if outward_cells:
        ux, uy = fx - NADIR_GRID[0], fy - NADIR_GRID[1]
        n = math.hypot(ux, uy)
        fx, fy = fx + outward_cells * ux / n, fy + outward_cells * uy / n
    return mm_to_grid(*_forward_mm(*grid_to_mm(fx, fy), k))
```

- [ ] **Step 2: 写失败测试**

`tests/test_vision/test_parallax_apply.py`:

```python
import math

import pytest

from katrain.vision.coordinates import apply_parallax
from katrain.vision.parallax import ParallaxParams
from tests.test_vision.parallax_synth import K_TRUE, NADIR_GRID, detected_grid


class TestApplyParallax:
    @pytest.mark.parametrize("nadir,k", [(None, 0.99), ((9.0, 19.6), None), (None, None)])
    def test_uncalibrated_is_identity(self, nadir, k):
        assert apply_parallax(3.1, 17.7, nadir, k) == (3.1, 17.7)

    def test_k_one_returns_inputs_bit_for_bit(self):
        # nadir + (fx - nadir) * 1.0 is not always fx in floating point, so k == 1.0 must
        # short-circuit for "off" to be bit-identical (prd P1-1 acceptance 1).
        assert 9.0 + (0.1 - 9.0) != 0.1
        assert apply_parallax(0.1, 0.1, (9.0, 19.6), 1.0) == (0.1, 0.1)

    def test_nadir_is_a_fixed_point(self):
        assert apply_parallax(*NADIR_GRID, NADIR_GRID, K_TRUE) == pytest.approx(NADIR_GRID, abs=1e-12)

    def test_inverts_the_forward_model_at_every_intersection(self):
        # Forward model in mm, correction in grid coordinates: this is the affine-invariance claim.
        for row in range(19):
            for col in range(19):
                assert apply_parallax(*detected_grid(col, row), NADIR_GRID, K_TRUE) == pytest.approx((col, row), abs=1e-9)

    def test_moves_points_toward_the_nadir(self):
        fx, fy = apply_parallax(0.0, 0.0, NADIR_GRID, K_TRUE)
        assert math.hypot(fx - NADIR_GRID[0], fy - NADIR_GRID[1]) < math.hypot(*NADIR_GRID)

    def test_is_not_idempotent(self):
        once = apply_parallax(0.0, 0.0, NADIR_GRID, K_TRUE)
        assert apply_parallax(*once, NADIR_GRID, K_TRUE) != pytest.approx(once, abs=1e-6)


class TestParallaxParams:
    def test_round_trips_through_dict(self):
        p = ParallaxParams(9.0, 19.6, 0.99)
        assert ParallaxParams(**p.to_dict()) == p
        assert p.nadir == (9.0, 19.6)
```

- [ ] **Step 3: 跑测试确认失败**

Run: `"$PY" -m pytest tests/test_vision/test_parallax_apply.py -q -p no:cacheprovider`
Expected: 收集阶段 `ImportError: cannot import name 'apply_parallax'`

- [ ] **Step 4: 实现**

`katrain/vision/coordinates.py` 末尾追加:

```python
def apply_parallax(
    fx: float, fy: float, nadir: tuple[float, float] | None, k: float | None
) -> tuple[float, float]:
    """Undo stone-thickness parallax on a continuous grid position (vision-stone-parallax track).

    A stone's detected centre sits above the board, so the camera sees it pushed outward from the
    nadir (the lens centre dropped onto the board plane) by a homothety of factor 1/k; the contact
    point is ``nadir + (detected - nadir) * k``. The factor survives the affine pixel -> mm -> grid
    chain unchanged, so this runs directly on (fx, fy) with ``nadir`` in the same grid coordinates.

    NOT idempotent (applying twice contracts by k**2): call it exactly once per detection.
    Identity when uncalibrated (``nadir`` or ``k`` is None), and returns the inputs untouched when
    ``k == 1.0`` -- ``nadir + (fx - nadir) * 1.0`` is not always ``fx`` in floating point, and
    "parallax off" must be bit-identical to not calling this at all.
    """
    if nadir is None or k is None or k == 1.0:
        return fx, fy
    return nadir[0] + (fx - nadir[0]) * k, nadir[1] + (fy - nadir[1]) * k
```

`katrain/vision/parallax.py`:

```python
"""Stone-parallax correction parameters and calibration fit -- pure math, no I/O.

Derivation and measured inputs: superpowers/tracks/vision-stone-parallax/geometry.md.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParallaxParams:
    """What BoardStateExtractor needs: the camera nadir in the geometry-lock warp's continuous grid
    coordinates (fx = column, fy = row) and the contraction factor k = (H - h) / H."""

    nadir_fx: float
    nadir_fy: float
    k: float

    @property
    def nadir(self) -> tuple[float, float]:
        return (self.nadir_fx, self.nadir_fy)

    def to_dict(self) -> dict:
        return {"nadir_fx": self.nadir_fx, "nadir_fy": self.nadir_fy, "k": self.k}
```

- [ ] **Step 5: 跑测试确认通过**

Run: `"$PY" -m pytest tests/test_vision/test_parallax_apply.py tests/test_vision/test_coordinates.py tests/test_vision/test_warp_consistency.py -q -p no:cacheprovider`
Expected: 全部 passed(新文件 9 条 + 既有两文件原样通过)

- [ ] **Step 6: 提交**

```bash
git add -- katrain/vision/coordinates.py katrain/vision/parallax.py tests/test_vision/parallax_synth.py tests/test_vision/test_parallax_apply.py
git commit -m "feat(vision): apply_parallax and ParallaxParams

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**验收:** prd P1-1 验收 1 的前半(None / k=1 恒等,k=1 逐位)、验收 4(nadir 不动点);非幂等有测试钉住。

---

### Task 3: `BoardStateExtractor` 接上修正

**Files:**
- Modify: `katrain/vision/board_state.py`(import 行 :19;`__init__` :80-98;`_grid_cell` :100-114;`detection_points` :126-134;`_assign_occupancy_aware` :209-241)
- Modify: `tests/test_vision/test_board_state_golden.py`(参数化)
- Test: `tests/test_vision/test_board_state_parallax.py`

**Interfaces:**
- Consumes: `apply_parallax`、`ParallaxParams`(Task 2);`IMG`、`grid_to_px`、`run_all`(Task 1);`parallax_synth`(Task 2)。
- Produces:
  - `BoardStateExtractor(config: BoardConfig | None = None, parallax: ParallaxParams | None = None)`,属性 `.parallax`
  - `BoardStateExtractor.parallax_points(detections, img_w, img_h) -> list[tuple[fy_raw, fx_raw, fy, fx, class_id, confidence]]`
  - `detection_points` 形状不变,内容是修正后坐标

**约束:** 第 4、5、6、8、9 条。**不许改** `pixel_to_physical` / `continuous_grid_pos` / `physical_to_grid`。

- [ ] **Step 1: 写失败测试**

`tests/test_vision/test_board_state_parallax.py`:

```python
"""Parallax correction inside BoardStateExtractor (prd P1-1 acceptance 2, 3; design §2.3)."""

import math

import numpy as np
import pytest

from katrain.vision.board_state import EMPTY, STICKY_RADIUS, SUSTAIN_RADIUS, BoardStateExtractor
from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig
from katrain.vision.coordinates import apply_parallax
from katrain.vision.parallax import ParallaxParams
from katrain.vision.stone_detector import Detection
from tests.test_vision.board_state_corpus import IMG, grid_to_px
from tests.test_vision.parallax_synth import K_TRUE, NADIR_GRID, detected_grid

CFG = BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS)
ON = ParallaxParams(NADIR_GRID[0], NADIR_GRID[1], K_TRUE)


def _det(fx, fy, cls=0, conf=0.9):
    x, y = grid_to_px(CFG, fx, fy)
    return Detection(x_center=x, y_center=y, class_id=cls, confidence=conf)


def _placed(parallax, det, occupancy):
    board = BoardStateExtractor(CFG, parallax=parallax).detections_to_board([det], IMG, IMG, occupancy_aware=occupancy)
    cells = list(zip(*np.nonzero(board)))
    return tuple(int(v) for v in cells[0]) if cells else None


class TestSanity361:
    def test_forward_model_positions_land_home_with_and_without_correction(self):
        # Sanity only: the largest offset is 0.204 cell (< half a cell), so this passes WITHOUT
        # the correction too -- it cannot show the correction works. TestFarRowsDisplacedOutward can.
        for parallax in (None, ON):
            ex = BoardStateExtractor(CFG, parallax=parallax)
            wrong = [
                (r, c) for r in range(19) for c in range(19) if ex._grid_cell(_det(*detected_grid(c, r)), IMG, IMG) != (r, c)
            ]
            assert wrong == [], (parallax, wrong)


class TestFarRowsDisplacedOutward:
    """The discriminating form of prd P1-1 acceptance 2: stones in rows 1-5 (the far side, next to the
    outermost row), each placed 0.35 cell further away from the camera. Without the correction they land
    on the neighbouring intersection (63 of 95 at design time); with it, none do. Both halves run every
    time, so this test proves on its own that the correction is what makes the difference.

    Row 0 is excluded on purpose: there the outward stone's RAW position rounds off-board, and the
    margin-DROP rule (either raw or corrected off-board -> drop) keeps dropping it -- the known cost
    pinned by test_outermost_row_keeps_todays_tolerance."""

    ROWS = range(1, 6)

    def _wrong(self, parallax, occupancy):
        return [
            (r, c)
            for r in self.ROWS
            for c in range(19)
            if _placed(parallax, _det(*detected_grid(c, r, outward_cells=0.35)), occupancy) != (r, c)
        ]

    @pytest.mark.parametrize("occupancy", [False, True])
    def test_without_correction_they_land_on_a_neighbour(self, occupancy):
        assert len(self._wrong(None, occupancy)) >= 30  # 63 of 95 at design time

    @pytest.mark.parametrize("occupancy", [False, True])
    def test_with_correction_all_land_home(self, occupancy):
        assert self._wrong(ON, occupancy) == []

    def test_outermost_row_keeps_todays_tolerance(self):
        # Known cost of the margin-DROP rule (design §7.1): a row-0 stone placed 0.3 cell outward has its
        # raw position past the drop line, so it is dropped with and without the correction alike.
        for parallax in (None, ON):
            assert _placed(parallax, _det(*detected_grid(9, 0, outward_cells=0.30)), occupancy=False) is None


# Points just outside the far edge / side edges that are dropped today and that the correction alone
# would pull back on-board (design §2.3, prd P1-1 acceptance 3 revision).
BAND = (
    [(fx, -0.6) for fx in (0.0, 4.0, 9.0, 14.0, 18.0)]
    + [(-0.55, fy) for fy in (2.0, 9.0, 16.0)]
    + [(18.55, fy) for fy in (2.0, 9.0, 16.0)]
)


class TestMarginDropSurvivesCorrection:
    @pytest.mark.parametrize("fx,fy", BAND)
    def test_band_point_is_still_dropped(self, fx, fy):
        cfx, cfy = apply_parallax(fx, fy, ON.nadir, ON.k)
        # Precondition: the correction by itself WOULD round this on-board; otherwise the test certifies nothing.
        assert 0 <= round(cfx) <= 18 and 0 <= round(cfy) <= 18
        ex = BoardStateExtractor(CFG, parallax=ON)
        assert ex._grid_cell(_det(fx, fy), IMG, IMG) is None
        for occupancy in (False, True):
            assert _placed(ON, _det(fx, fy), occupancy) is None

    def test_point_pushed_off_board_by_the_correction_is_dropped(self):
        # The other half of "either": on the camera side the correction pushes outward (toward a nadir beyond row 18).
        fx, fy = 9.0, 18.495
        assert round(fy) == 18
        assert round(apply_parallax(fx, fy, ON.nadir, ON.k)[1]) == 19
        assert BoardStateExtractor(CFG, parallax=ON)._grid_cell(_det(fx, fy), IMG, IMG) is None


class TestOffBoardDetectionsBehaveAsUncorrected:
    """codex adversarial review 2026-09-22 [high]: a margin object that the correction would pull within
    reach of an edge stone must not keep that stone alive after the user removes it -- neither through
    presence sustain (any class) nor through sticky assignment (same colour). Baseline drops the stone at
    once; so must the corrected extractor, over many frames."""

    RAW = (9.0, -0.8)  # just outside the far edge, beside an edge stone at (0, 9)

    def _after_removal(self, parallax, cls, frames=20):
        ex = BoardStateExtractor(CFG, parallax=parallax)
        prev = np.zeros((19, 19), dtype=int)
        prev[0][9] = 1  # a black edge stone; the user has just removed it, only the margin object remains
        for _ in range(frames):
            prev = ex.detections_to_board(
                [_det(*self.RAW, cls=cls)], IMG, IMG, occupancy_aware=True, prev_board=prev, sticky_board=prev
            )
        return int(prev[0][9])

    def test_precondition_the_correction_alone_would_reach_the_stone(self):
        cfx, cfy = apply_parallax(*self.RAW, ON.nadir, ON.k)
        corrected, raw = math.hypot(cfx - 9, cfy), math.hypot(self.RAW[0] - 9, self.RAW[1])
        assert corrected <= SUSTAIN_RADIUS < raw
        assert corrected <= STICKY_RADIUS < raw

    @pytest.mark.parametrize("cls", [0, 2], ids=["black-stone-sticky", "led-class-sustain"])
    def test_removed_edge_stone_is_not_kept_alive(self, cls):
        for parallax in (None, ON):
            assert self._after_removal(parallax, cls) == EMPTY, parallax


class TestSingleApplication:
    def test_detection_points_are_corrected_exactly_once(self):
        fx_raw, fy_raw = detected_grid(3, 1)
        ((fy, fx, _, _),) = BoardStateExtractor(CFG, parallax=ON).detection_points([_det(fx_raw, fy_raw)], IMG, IMG)
        once = apply_parallax(fx_raw, fy_raw, ON.nadir, ON.k)
        twice = apply_parallax(*once, ON.nadir, ON.k)
        assert (fx, fy) == pytest.approx(once, abs=1e-9)
        assert (fx, fy) != pytest.approx(twice, abs=1e-6)

    def test_parallax_points_carry_raw_and_corrected(self):
        fx_raw, fy_raw = detected_grid(3, 1)
        ex = BoardStateExtractor(CFG, parallax=ON)
        ((pfy_raw, pfx_raw, pfy, pfx, cls, conf),) = ex.parallax_points([_det(fx_raw, fy_raw, 1, 0.7)], IMG, IMG)
        assert (pfx_raw, pfy_raw) == pytest.approx((fx_raw, fy_raw), abs=1e-9)
        assert (pfx, pfy) == pytest.approx((3, 1), abs=1e-9)
        assert (cls, conf) == (1, 0.7)

    def test_parallax_points_raw_equals_corrected_when_off(self):
        ((fy_raw, fx_raw, fy, fx, _, _),) = BoardStateExtractor(CFG).parallax_points([_det(3.2, 1.1)], IMG, IMG)
        assert (fx_raw, fy_raw) == (fx, fy)
```

把 `tests/test_vision/test_board_state_golden.py` 的 `test_extractor_reproduces_golden` 换成参数化版本
(文件其余不变,import 里加 `pytest` 与 `ParallaxParams`):

```python
import json

import pytest

from katrain.vision.board_state import BoardStateExtractor
from katrain.vision.parallax import ParallaxParams
from tests.test_vision.board_state_corpus import GOLDEN_PATH, run_all
```

```python
@pytest.mark.parametrize(
    "make_extractor",
    [
        pytest.param(BoardStateExtractor, id="default"),
        pytest.param(lambda cfg: BoardStateExtractor(cfg, parallax=None), id="parallax-none"),
        pytest.param(lambda cfg: BoardStateExtractor(cfg, parallax=ParallaxParams(9.0, 19.6, 1.0)), id="parallax-k1"),
    ],
)
def test_extractor_reproduces_golden(make_extractor):
    want = _golden()["outputs"]
    got = json.loads(json.dumps(run_all(make_extractor)))
    assert _first_difference(got, want) is None, _first_difference(got, want)
    assert got == want
```

- [ ] **Step 2: 跑测试确认失败**

Run: `"$PY" -m pytest tests/test_vision/test_board_state_parallax.py tests/test_vision/test_board_state_golden.py -q -p no:cacheprovider`
Expected: 失败,`TypeError: BoardStateExtractor.__init__() got an unexpected keyword argument 'parallax'`;
golden 的 `default` 那一条仍然通过。

- [ ] **Step 3: 实现**

`katrain/vision/board_state.py`:

import 区(:19 附近)改为:

```python
from katrain.vision.coordinates import apply_parallax, continuous_grid_pos, pixel_to_physical
from katrain.vision.parallax import ParallaxParams
```

`__init__` 签名与开头:

```python
    def __init__(self, config: BoardConfig | None = None, parallax: ParallaxParams | None = None):
        self.config = config or BoardConfig()
        # Stone-parallax correction (vision-stone-parallax track). Only the geometry-lock extractor
        # ever gets one: the nadir is calibrated in that warp's grid, and the BoardFinder warp uses a
        # different basis. None = off, bit-identical to the pre-parallax behaviour.
        self.parallax = parallax
```

(`self._color_flip_streak` 等后续行保持不变。)

`_grid_cell` 之前新增两个方法,并替换 `_grid_cell` 的实现(docstring 追加最后一段):

```python
    def _positions(self, det, img_w: int, img_h: int) -> tuple[float, float, float, float, bool]:
        """(fx_raw, fy_raw, fx, fy, on_board) for a detection. The ONLY caller of apply_parallax -- it is
        not idempotent, so every consumer must take its (fx, fy) from here, corrected exactly once.

        on_board is False when EITHER the raw or the corrected position rounds off the grid, and an
        off-board detection keeps its RAW position as (fx, fy). The correction pulls points toward the
        nadir; letting it move a warp-margin object would let that object reach cells it cannot reach
        today -- not only as a new stone, but through sticky assignment and presence sustain, where it
        kept a just-removed edge stone alive in review. Off-board detections therefore behave exactly
        as they do without the correction."""
        x_mm, y_mm = pixel_to_physical(det.x_center, det.y_center, img_w, img_h, self.config)
        fx_raw, fy_raw = continuous_grid_pos(x_mm, y_mm, self.config)
        if self.parallax is None:
            return fx_raw, fy_raw, fx_raw, fy_raw, self._on_board(fx_raw, fy_raw)
        fx, fy = apply_parallax(fx_raw, fy_raw, self.parallax.nadir, self.parallax.k)
        if self._on_board(fx_raw, fy_raw) and self._on_board(fx, fy):
            return fx_raw, fy_raw, fx, fy, True
        return fx_raw, fy_raw, fx_raw, fy_raw, False

    def _on_board(self, fx: float, fy: float) -> bool:
        gs = self.config.grid_size
        return 0 <= int(round(fy)) < gs and 0 <= int(round(fx)) < gs

    def _grid_cell(self, det, img_w: int, img_h: int) -> tuple[int, int] | None:
        """Nearest intersection (row, col) for a detection, or None when it is off-board.

        The geometry-lock warp includes a 1-cell blank margin; an object sitting in that
        margin (cable, marker, glare) must be DROPPED, not clamped to the nearest border
        intersection — clamping once turned a red object beside the top-right corner into
        a phantom T19 move. Up to half a cell of overshoot still rounds onto the edge row,
        so sloppily placed border stones keep working.

        With parallax on, off-board means EITHER the raw or the corrected position rounds off the
        grid (see _positions): otherwise the correction would drag a margin object in a ~0.2-cell band
        outside the far/side edges back onto the board."""
        _, _, fx, fy, on_board = self._positions(det, img_w, img_h)
        return (int(round(fy)), int(round(fx))) if on_board else None
```

`detection_points` 替换,并在其后新增 `parallax_points`:

```python
    def detection_points(self, detections: list[Detection], img_w: int, img_h: int) -> list:
        """Continuous grid positions of ALL detections (any class, off-board included), parallax-
        corrected: [(fy, fx, class_id, confidence)]. Used by presence sustain and delta diagnostics."""
        pts = []
        for det in detections:
            _, _, fx, fy, _ = self._positions(det, img_w, img_h)
            pts.append((fy, fx, det.class_id, det.confidence))
        return pts

    def parallax_points(self, detections: list[Detection], img_w: int, img_h: int) -> list:
        """detection_points with the raw position kept alongside, for diagnostics only:
        [(fy_raw, fx_raw, fy, fx, class_id, confidence)]."""
        pts = []
        for det in detections:
            fx_raw, fy_raw, fx, fy, _ = self._positions(det, img_w, img_h)
            pts.append((fy_raw, fx_raw, fy, fx, det.class_id, det.confidence))
        return pts
```

`_assign_occupancy_aware` 开头到 off-board 判定(:220-241)替换为:

```python
        gs = board.shape[0]
        positions = [self._positions(det, img_w, img_h) for det in detections]
        # any class, for sustain -- same content as detection_points(), without recomputing it
        all_points = [(fy, fx, det.class_id, det.confidence) for det, (_, _, fx, fy, _) in zip(detections, positions)]
        items = []
        for det, (_, _, fx, fy, on_board) in zip(detections, positions):
            if det.class_id not in STONE_CLASS_IDS:
                continue
            residual = math.hypot(fx - round(fx), fy - round(fy))
            items.append((residual, det, fx, fy, on_board))
        # Highest confidence claims its intersection first (matches the legacy "highest-confidence
        # wins" semantics); residual only breaks ties between equally confident detections. A
        # lower-confidence detection that then lands on an occupied point is either a sloppily
        # placed real stone (spill it to the nearest empty neighbour) or a duplicate/false positive
        # (drop it) — decided by SPILL_MIN_CONFIDENCE, so a weak FP can't spawn a phantom.
        items.sort(key=lambda t: (-t[1].confidence, t[0]))
        for _, det, fx, fy, on_board in items:
            sticky = self._sticky_cell(sticky_board, board, fy, fx, det.class_id + 1)
            if sticky is not None:
                cy, cx = sticky  # boundary-straddling stone stays on its established cell
            else:
                if not on_board:
                    continue  # off-board detection (warp-margin object) — never clamp onto a border point
                cy, cx = int(round(fy)), int(round(fx))
```

(从 `# Lit-cell mask blocks ADDITIONS only` 往下全部保持原样;sustain 循环里的 `all_points` 现在就是上面这份。
粘滞与存在维持用的 (fx, fy) 对盘外检测是原始坐标 —— 由 `_positions` 保证,这里不需要再判。)

- [ ] **Step 4: 跑测试确认通过**

Run: `"$PY" -m pytest tests/test_vision/test_board_state_parallax.py tests/test_vision/test_board_state_golden.py tests/test_vision/test_board_state.py tests/test_vision/test_warp_consistency.py -q -p no:cacheprovider`
Expected: 全部 passed(金样 1+3 条参数化都过)

- [ ] **Step 5: 跑整个视觉测试目录**

Run: `"$PY" -m pytest tests/test_vision -q -p no:cacheprovider`
Expected: `651 + 本任务与之前任务新增的条数` 全部 passed,0 failed

- [ ] **Step 6: 提交**

```bash
git add -- katrain/vision/board_state.py tests/test_vision/test_board_state_parallax.py tests/test_vision/test_board_state_golden.py
git commit -m "feat(vision): BoardStateExtractor applies stone-parallax correction once per detection

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 7: 三个变异检查(一次性 worktree,每个单独开一棵)**

变异 A —— 出界只看修正后坐标:

```bash
MUT=$(mktemp -d)/wt && git worktree add --detach "$MUT" HEAD
"$PY" - "$MUT/katrain/vision/board_state.py" <<'EOF'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); s = p.read_text()
old = "        if self._on_board(fx_raw, fy_raw) and self._on_board(fx, fy):\n"
assert s.count(old) == 1
p.write_text(s.replace(old, "        if self._on_board(fx, fy):\n"))
EOF
(cd "$MUT" && "$PY" -m pytest tests/test_vision/test_board_state_parallax.py -q -p no:cacheprovider -k Margin)
git worktree remove --force "$MUT"
```
Expected: `TestMarginDropSurvivesCorrection::test_band_point_is_still_dropped` 失败(band 点被拉回盘内)。

变异 D —— 出界判定对,但盘外检测仍带修正后坐标进入粘滞 / 存在维持(codex 复现的那条):

```bash
MUT=$(mktemp -d)/wt && git worktree add --detach "$MUT" HEAD
"$PY" - "$MUT/katrain/vision/board_state.py" <<'EOF'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); s = p.read_text()
old = "        return fx_raw, fy_raw, fx_raw, fy_raw, False\n"
assert s.count(old) == 1
p.write_text(s.replace(old, "        return fx_raw, fy_raw, fx, fy, False\n"))
EOF
(cd "$MUT" && "$PY" -m pytest tests/test_vision/test_board_state_parallax.py -q -p no:cacheprovider -k "OffBoard or Margin")
git worktree remove --force "$MUT"
```
Expected: `TestOffBoardDetectionsBehaveAsUncorrected::test_removed_edge_stone_is_not_kept_alive` 两个参数都失败;
`TestMarginDropSurvivesCorrection` 仍通过(说明两条测试守的是两件不同的事)。

变异 B —— 修正做两次:

```bash
MUT=$(mktemp -d)/wt && git worktree add --detach "$MUT" HEAD
"$PY" - "$MUT/katrain/vision/board_state.py" <<'EOF'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); s = p.read_text()
old = "        fx, fy = apply_parallax(fx_raw, fy_raw, self.parallax.nadir, self.parallax.k)\n"
assert s.count(old) == 1
p.write_text(s.replace(old, old + "        fx, fy = apply_parallax(fx, fy, self.parallax.nadir, self.parallax.k)\n"))
EOF
(cd "$MUT" && "$PY" -m pytest tests/test_vision/test_board_state_parallax.py -q -p no:cacheprovider -k SingleApplication)
git worktree remove --force "$MUT"
```
Expected: `test_detection_points_are_corrected_exactly_once` 失败。

变异 C —— `apply_parallax` 去掉 `k == 1.0` 短路:

```bash
MUT=$(mktemp -d)/wt && git worktree add --detach "$MUT" HEAD
"$PY" - "$MUT/katrain/vision/coordinates.py" <<'EOF'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); s = p.read_text()
old = "    if nadir is None or k is None or k == 1.0:\n"
assert s.count(old) == 1
p.write_text(s.replace(old, "    if nadir is None or k is None:\n"))
EOF
(cd "$MUT" && "$PY" -m pytest tests/test_vision/test_board_state_golden.py -q -p no:cacheprovider)
git worktree remove --force "$MUT"
```
Expected: `test_extractor_reproduces_golden[parallax-k1]` 失败(浮点末位不同)。

**验收:** prd P1-1 验收 1(关着逐位,金样三种构造)、验收 2(健全性 + 区分版,两半都在同一测试里跑)、
验收 3(边距带 + 反方向);三个变异各自变红。

---

### Task 4: 拟合 `fit_parallax`

**Files:**
- Modify: `katrain/vision/parallax.py`(末尾追加;顶部 import 加 numpy)
- Test: `tests/test_vision/test_parallax_fit.py`

**Interfaces:**
- Consumes: `ParallaxParams`(Task 2)、`parallax_synth`、`apply_parallax`。
- Produces:
  - `FitResult(k, nadir_fx, nadir_fy, m, rms_cells, max_resid_cells, worst_index, h_implied_mm, n)`(frozen),`.params -> ParallaxParams`
  - `fit_parallax(points, detected, camera_height_mm: float) -> FitResult`;`points` 是 `(col, row)`,`detected` 是 `(fx_raw, fy_raw)`

**约束:** 第 1、2、3 条;不对 nadir 做合理性检查;不用 k 的相对误差当验收。

- [ ] **Step 1: 写失败测试**

`tests/test_vision/test_parallax_fit.py`:

```python
"""Calibration fit (prd P1-2 acceptance 1-3; acceptance 2 as rewritten 2026-09-22)."""

import numpy as np
import pytest

from katrain.vision.coordinates import apply_parallax
from katrain.vision.parallax import ParallaxParams, fit_parallax
from tests.test_vision.parallax_synth import (
    H_MM,
    H_STONE_MM,
    K_TRUE,
    NADIR_GRID,
    detected_grid,
    grid_to_mm,
    mm_to_grid,
)

PATTERN_9 = [(0, 0), (18, 0), (0, 18), (18, 18), (9, 9), (3, 3), (15, 3), (3, 15), (15, 15)]  # (col, row)


def _detected(pattern, rng=None, sigma_mm=0.0):
    out = []
    for c, r in pattern:
        x, y = grid_to_mm(*detected_grid(c, r))
        if rng is not None:
            x, y = x + rng.normal(0, sigma_mm), y + rng.normal(0, sigma_mm)
        out.append(mm_to_grid(x, y))
    return out


def _worst_correction_error_mm(params):
    worst = 0.0
    for r in range(19):
        for c in range(19):
            fx, fy = apply_parallax(*detected_grid(c, r), params.nadir, params.k)
            (ex, ey), (tx, ty) = grid_to_mm(fx, fy), grid_to_mm(c, r)
            worst = max(worst, float(np.hypot(ex - tx, ey - ty)))
    return worst


def test_noiseless_fit_recovers_the_truth():
    fit = fit_parallax(PATTERN_9, _detected(PATTERN_9), H_MM)
    assert abs(fit.k - K_TRUE) < 1e-6
    assert abs(fit.nadir_fx - NADIR_GRID[0]) < 1e-6 and abs(fit.nadir_fy - NADIR_GRID[1]) < 1e-6
    assert fit.rms_cells < 1e-9
    assert fit.h_implied_mm == pytest.approx(H_STONE_MM, abs=1e-6)
    assert fit.n == 9
    assert fit.params == ParallaxParams(fit.nadir_fx, fit.nadir_fy, fit.k)


def test_noisy_fit_is_accurate_where_it_matters():
    """Measured on h_implied and on the corrected positions -- never on k (k = 1, i.e. no correction
    at all, scores a 1.04% k error) nor on the nadir (ill-conditioned: ~29 mm p95 at this noise)."""
    rng = np.random.default_rng(20260922)
    h_err, corr_err = [], []
    for _ in range(200):
        fit = fit_parallax(PATTERN_9, _detected(PATTERN_9, rng, 0.3), H_MM)
        h_err.append(abs(fit.h_implied_mm - H_STONE_MM) / H_STONE_MM)
        corr_err.append(_worst_correction_error_mm(fit.params))
    assert np.percentile(h_err, 95) < 0.20  # 0.083 at design time
    assert np.percentile(corr_err, 95) < 1.0  # 0.395 mm at design time


def test_the_accuracy_gate_rejects_no_correction():
    # The gate above must be one that "no correction" fails, or it certifies nothing.
    assert _worst_correction_error_mm(ParallaxParams(*NADIR_GRID, 1.0)) > 1.0


@pytest.mark.parametrize("pattern", [[(0, 0)], [(0, 0), (18, 18)]])
def test_fewer_than_three_samples_raise(pattern):
    with pytest.raises(ValueError, match="at least 3"):
        fit_parallax(pattern, _detected(pattern), H_MM)


def test_collinear_samples_raise():
    row = [(c, 0) for c in range(0, 19, 3)]
    with pytest.raises(ValueError, match="collinear"):
        fit_parallax(row, _detected(row), H_MM)


def test_coincident_samples_raise():
    same = [(9, 9)] * 5
    with pytest.raises(ValueError, match="collinear"):
        fit_parallax(same, _detected(same), H_MM)


def test_no_parallax_raises():
    with pytest.raises(ValueError, match="no measurable parallax"):
        fit_parallax(PATTERN_9, [(float(c), float(r)) for c, r in PATTERN_9], H_MM)


def test_shape_mismatch_raises():
    with pytest.raises(ValueError, match=r"\(n, 2\)"):
        fit_parallax(PATTERN_9, _detected(PATTERN_9)[:-1], H_MM)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `"$PY" -m pytest tests/test_vision/test_parallax_fit.py -q -p no:cacheprovider`
Expected: `ImportError: cannot import name 'fit_parallax'`

- [ ] **Step 3: 实现**

`katrain/vision/parallax.py`:`from dataclasses import dataclass` 下面加 `import numpy as np`,文件末尾追加:

```python
@dataclass(frozen=True)
class FitResult:
    k: float
    nadir_fx: float
    nadir_fy: float
    m: float
    rms_cells: float
    max_resid_cells: float
    worst_index: int
    h_implied_mm: float
    n: int

    @property
    def params(self) -> ParallaxParams:
        return ParallaxParams(self.nadir_fx, self.nadir_fy, self.k)


def fit_parallax(points, detected, camera_height_mm: float) -> FitResult:
    """Least-squares fit of the forward model D = m*P + (1 - m)*C, linear in (m, b = (1 - m)*C).

    ``points``: (n, 2) true intersections as (col, row) -- the geometry-lock grid's (fx, fy).
    ``detected``: (n, 2) matching RAW (uncorrected) detected positions in the same coordinates.
    ``camera_height_mm`` (H) only feeds ``h_implied_mm = H * (1 - k)``, a diagnostic telling which
    stone height the detector reports (3.5 = mid-plane, 7.0 = top face); the correction never uses H.

    Raises ValueError rather than return an ill-posed fit: fewer than 3 samples; samples that do not
    span both board axes (collinear or coincident -- the model is not degenerate on a line, but a
    calibration that never varied one axis is a misuse, prd P1-2 acceptance 3); or m == 1 (no
    measurable parallax, so the nadir b / (1 - m) is undefined).

    Never sanity-check the fitted nadir: b's error is amplified by 1 / (1 - m) (~100x; 0.3 mm of
    noise gives ~29 mm p95), yet the nadir enters the correction multiplied by (1 - k) ~ 0.01, so the
    corrected positions stay accurate (~0.4 mm p95).
    """
    P = np.asarray(points, dtype=float)
    D = np.asarray(detected, dtype=float)
    if P.ndim != 2 or P.shape[1:] != (2,) or P.shape != D.shape:
        raise ValueError(f"points and detected must both be (n, 2); got {P.shape} and {D.shape}")
    n = len(P)
    if n < 3:
        raise ValueError(f"need at least 3 samples, got {n}")
    if np.linalg.matrix_rank(P - P.mean(axis=0)) < 2:
        raise ValueError("samples are collinear: calibration stones must span both board axes")
    A = np.zeros((2 * n, 3))
    b = np.zeros(2 * n)
    A[0::2, 0] = P[:, 0]
    A[0::2, 1] = 1.0
    b[0::2] = D[:, 0]
    A[1::2, 0] = P[:, 1]
    A[1::2, 2] = 1.0
    b[1::2] = D[:, 1]
    m, bx, by = (float(v) for v in np.linalg.lstsq(A, b, rcond=None)[0])
    if abs(1.0 - m) < 1e-9:
        raise ValueError("fitted m == 1: no measurable parallax, the nadir is undefined")
    resid = np.hypot(*(A @ np.array([m, bx, by]) - b).reshape(n, 2).T)
    k = 1.0 / m
    return FitResult(
        k=k,
        nadir_fx=bx / (1.0 - m),
        nadir_fy=by / (1.0 - m),
        m=m,
        rms_cells=float(np.sqrt(np.mean(resid**2))),
        max_resid_cells=float(resid.max()),
        worst_index=int(resid.argmax()),
        h_implied_mm=float(camera_height_mm) * (1.0 - k),
        n=n,
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `"$PY" -m pytest tests/test_vision/test_parallax_fit.py tests/test_vision/test_parallax_apply.py -q -p no:cacheprovider`
Expected: 全部 passed

- [ ] **Step 5: 提交**

```bash
git add -- katrain/vision/parallax.py tests/test_vision/test_parallax_fit.py
git commit -m "feat(vision): fit_parallax recovers k and nadir from stones on known points

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 6: 变异检查 —— 精度闸对「拟合被写坏」会红**

```bash
MUT=$(mktemp -d)/wt && git worktree add --detach "$MUT" HEAD
"$PY" - "$MUT/katrain/vision/parallax.py" <<'EOF'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); s = p.read_text()
old = "    k = 1.0 / m\n"
assert s.count(old) == 1
p.write_text(s.replace(old, "    k = 1.0 / m ** 2\n"))
EOF
(cd "$MUT" && "$PY" -m pytest tests/test_vision/test_parallax_fit.py -q -p no:cacheprovider -k "noisy or noiseless")
git worktree remove --force "$MUT"
```
Expected: 两条都失败。

**验收:** prd P1-2 验收 1(无噪 1e-6 / rms 1e-9)、验收 2(改写版:h p95 < 20%、修正残差 p95 < 1 mm,
且同一闸对「不修正」必红)、验收 3(少于 3 点 / 共线 / 重合 / m=1 报错)。

---

### Task 5: 标定文件 `parallax_store`

**Files:**
- Create: `katrain/vision/parallax_store.py`
- Test: `tests/test_vision/test_parallax_store.py`

**Interfaces:**
- Consumes: `ParallaxParams`(Task 2)。
- Produces(Task 6、8 用):
  - `SCHEMA = 1`、`BOARD_GO_19 = "go-19x19"`、`H_IMPLIED_WINDOW_MM = (2.0, 8.0)`
  - `ParallaxCalibration(board, stone_set, nadir_fx, nadir_fy, k, m, h_implied_mm, camera_height_mm, rms_cells,
    max_resid_cells, n_samples, n_black, n_white, frames, geometry_generation, fitted_at, schema=1)`(frozen),
    `.params`、`.to_json_dict()`、`ParallaxCalibration.from_json_dict(data, board=BOARD_GO_19)`(非法抛 ValueError)
  - `parallax_path(hardware_vision_dir, board=BOARD_GO_19) -> Path`
  - `load_parallax(path, board=BOARD_GO_19) -> tuple[ParallaxCalibration | None, str]`(从不抛)
  - `save_parallax(path, calib) -> None`(先校验,原子写)

**约束:** 不碰 `hardware_vision_state.py` 与它管的 `generations/`、`current.json`;文件放在 `<dir>/parallax/` 子目录。

- [ ] **Step 1: 写失败测试**

`tests/test_vision/test_parallax_store.py`:

```python
import json
import math

import pytest

from katrain.vision.parallax import ParallaxParams
from katrain.vision.parallax_store import (
    BOARD_GO_19,
    ParallaxCalibration,
    load_parallax,
    parallax_path,
    save_parallax,
)


def _calib(**overrides):
    values = dict(
        board=BOARD_GO_19,
        stone_set="ver9-22x7",
        nadir_fx=9.02,
        nadir_fy=19.58,
        k=0.98969,
        m=1 / 0.98969,
        h_implied_mm=339.44 * (1 - 0.98969),  # must equal camera_height_mm * (1 - k)
        camera_height_mm=339.44,
        rms_cells=0.031,
        max_resid_cells=0.07,
        n_samples=17,
        n_black=9,
        n_white=8,
        frames=30,
        geometry_generation="gen-1",
        fitted_at="2026-09-22T10:00:00+08:00",
    )
    values.update(overrides)
    return ParallaxCalibration(**values)


def test_path_is_one_file_per_board_under_the_vision_dir(tmp_path):
    assert parallax_path(tmp_path) == tmp_path / "parallax" / "go-19x19.json"


def test_save_then_load_round_trips(tmp_path):
    path = parallax_path(tmp_path)
    save_parallax(path, _calib())
    calib, reason = load_parallax(path)
    assert reason == "ok"
    assert calib == _calib()
    assert calib.params == ParallaxParams(9.02, 19.58, 0.98969)


def test_missing_file_means_not_calibrated(tmp_path):
    calib, reason = load_parallax(parallax_path(tmp_path))
    assert calib is None and reason.startswith("not calibrated")


def _write(tmp_path, data):
    path = parallax_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data))
    return path


@pytest.mark.parametrize(
    "mutate,needle",
    [
        (lambda d: d.update(schema=2), "schema"),
        (lambda d: d.update(board="xiangqi-9x10"), "board"),
        (lambda d: d.pop("k"), "missing"),
        (lambda d: d.update(extra=1), "unexpected"),
        (lambda d: d.update(k=math.nan), "finite"),
        (lambda d: d.update(k=True), "finite"),
        (lambda d: d.update(k=1.0), "(0, 1)"),
        (lambda d: d.update(k=1.2), "(0, 1)"),
        (lambda d: d.update(h_implied_mm=1.5), "h_implied_mm"),
        (lambda d: d.update(h_implied_mm=8.5), "h_implied_mm"),
        # k damaged alone: the stale h_implied_mm must not vouch for it
        (lambda d: d.update(k=0.5), "1/k"),
        (lambda d: d.update(k=0.985, m=1 / 0.985), "does not match"),
        # internally consistent, but the height itself is out of the window
        (lambda d: d.update(k=1 - 9 / 339.44, m=1 / (1 - 9 / 339.44), h_implied_mm=339.44 * (9 / 339.44)), "outside"),
        (lambda d: d.update(camera_height_mm=0.0), "camera_height_mm"),
        (lambda d: d.update(n_samples=-1), "n_samples"),
        (lambda d: d.update(stone_set=""), "stone_set"),
        (lambda d: d.update(geometry_generation=3), "geometry_generation"),
    ],
)
def test_invalid_file_is_refused_with_a_reason(tmp_path, mutate, needle):
    data = _calib().to_json_dict()
    mutate(data)
    calib, reason = load_parallax(_write(tmp_path, data))
    assert calib is None
    assert reason.startswith("invalid calibration file") and needle in reason


def test_unparseable_json_is_refused(tmp_path):
    calib, reason = load_parallax(_write(tmp_path, "{not json"))
    assert calib is None and reason.startswith("invalid calibration file")


def test_save_refuses_an_invalid_calibration_and_keeps_the_old_file(tmp_path):
    path = parallax_path(tmp_path)
    save_parallax(path, _calib())
    before = path.read_bytes()
    with pytest.raises(ValueError, match="h_implied_mm"):
        save_parallax(path, _calib(h_implied_mm=12.0))
    assert path.read_bytes() == before
    assert sorted(p.name for p in path.parent.iterdir()) == ["go-19x19.json"]  # no temp file left behind


def test_save_replaces_an_existing_file(tmp_path):
    path = parallax_path(tmp_path)
    save_parallax(path, _calib())
    save_parallax(path, _calib(k=0.985, m=1 / 0.985, h_implied_mm=339.44 * (1 - 0.985)))
    assert load_parallax(path)[0].k == 0.985
```

- [ ] **Step 2: 跑测试确认失败**

Run: `"$PY" -m pytest tests/test_vision/test_parallax_store.py -q -p no:cacheprovider`
Expected: `ModuleNotFoundError: No module named 'katrain.vision.parallax_store'`

- [ ] **Step 3: 实现**

`katrain/vision/parallax_store.py`:

```python
"""On-disk stone-parallax calibration: one JSON file per board under the hardware-vision dir.

It lives beside, never inside, HardwareVisionStateStore's generations: geometry is re-committed on
every drift recalibration, while parallax stays valid until the camera mount, the board or the stone
set changes (vision-stone-parallax design.md §0 D1). The generation it was fitted against is only
recorded for the startup log, never used as a switch.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from katrain.vision.parallax import ParallaxParams

SCHEMA = 1
BOARD_GO_19 = "go-19x19"
# The stones are 7 mm thick: an implied detected-centre height outside this window means the warp or
# the stone-to-intersection pairing was wrong, so the calibration is refused (prd P1-2 acceptance 4).
H_IMPLIED_WINDOW_MM = (2.0, 8.0)

_FLOAT_FIELDS = ("nadir_fx", "nadir_fy", "k", "m", "h_implied_mm", "camera_height_mm", "rms_cells", "max_resid_cells")
_COUNT_FIELDS = ("n_samples", "n_black", "n_white", "frames")


@dataclass(frozen=True)
class ParallaxCalibration:
    board: str
    stone_set: str
    nadir_fx: float
    nadir_fy: float
    k: float
    m: float
    h_implied_mm: float
    camera_height_mm: float
    rms_cells: float
    max_resid_cells: float
    n_samples: int
    n_black: int
    n_white: int
    frames: int
    geometry_generation: str | None
    fitted_at: str
    schema: int = SCHEMA

    @property
    def params(self) -> ParallaxParams:
        return ParallaxParams(self.nadir_fx, self.nadir_fy, self.k)

    def to_json_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json_dict(cls, data, board: str = BOARD_GO_19) -> ParallaxCalibration:
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")
        expected = {f.name for f in fields(cls)}
        missing = sorted(expected - set(data))
        if missing:
            raise ValueError(f"missing fields {missing}")
        unexpected = sorted(set(data) - expected)
        if unexpected:
            raise ValueError(f"unexpected fields {unexpected}")
        if data["schema"] != SCHEMA:
            raise ValueError(f"schema {data['schema']!r} is not {SCHEMA}")
        if data["board"] != board:
            raise ValueError(f"calibrated for board {data['board']!r}, not {board!r}")
        for name in ("stone_set", "fitted_at"):
            if not isinstance(data[name], str) or not data[name]:
                raise ValueError(f"{name} must be a non-empty string")
        if data["geometry_generation"] is not None and not isinstance(data["geometry_generation"], str):
            raise ValueError("geometry_generation must be a string or null")
        for name in _FLOAT_FIELDS:
            value = data[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number, got {value!r}")
        for name in _COUNT_FIELDS:
            if type(data[name]) is not int or data[name] < 0:
                raise ValueError(f"{name} must be a non-negative integer, got {data[name]!r}")
        if not 0.0 < data["k"] < 1.0:
            raise ValueError(f"k={data['k']} is outside (0, 1): parallax always contracts toward the nadir")
        # The height gate must constrain the k that is actually applied, not a free-standing field: a
        # file whose k alone was damaged would otherwise pass on its stale h_implied_mm (codex review).
        if data["camera_height_mm"] <= 0:
            raise ValueError(f"camera_height_mm={data['camera_height_mm']} must be positive")
        if abs(data["m"] * data["k"] - 1.0) > 1e-9:
            raise ValueError(f"m={data['m']} is not 1/k (k={data['k']})")
        h_from_k = data["camera_height_mm"] * (1.0 - data["k"])
        if abs(h_from_k - data["h_implied_mm"]) > 1e-6:
            raise ValueError(
                f"h_implied_mm={data['h_implied_mm']} does not match camera_height_mm*(1-k)={h_from_k:.6f}"
            )
        lo, hi = H_IMPLIED_WINDOW_MM
        if not lo <= h_from_k <= hi:
            raise ValueError(f"h_implied_mm={h_from_k:.3f} (from k) is outside [{lo}, {hi}]")
        return cls(**{name: data[name] for name in expected})


def parallax_path(hardware_vision_dir, board: str = BOARD_GO_19) -> Path:
    return Path(hardware_vision_dir).expanduser() / "parallax" / f"{board}.json"


def load_parallax(path, board: str = BOARD_GO_19) -> tuple[ParallaxCalibration | None, str]:
    """(calibration, "ok") or (None, reason). Never raises for a bad file: a broken calibration
    turns the correction off, it must not take recognition down."""
    p = Path(path)
    if not p.exists():
        return None, f"not calibrated ({p} does not exist)"
    try:
        return ParallaxCalibration.from_json_dict(json.loads(p.read_text(encoding="utf-8")), board=board), "ok"
    except (OSError, ValueError, TypeError) as exc:  # json.JSONDecodeError is a ValueError
        return None, f"invalid calibration file {p}: {exc}"


def save_parallax(path, calib: ParallaxCalibration) -> None:
    """Validate, then write atomically (temp file in the same directory + os.replace), so a refused
    or interrupted write never replaces a good calibration."""
    ParallaxCalibration.from_json_dict(calib.to_json_dict(), board=calib.board)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{p.name}.", suffix=".tmp", dir=p.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(calib.to_json_dict(), f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
```

- [ ] **Step 4: 跑测试确认通过**

Run: `"$PY" -m pytest tests/test_vision/test_parallax_store.py -q -p no:cacheprovider`
Expected: 全部 passed

- [ ] **Step 5: 提交**

```bash
git add -- katrain/vision/parallax_store.py tests/test_vision/test_parallax_store.py
git commit -m "feat(vision): parallax calibration file, one per board beside the vision generations

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**验收:** design D1 / §3 / §4 的文件格式与拒收条件;prd P1-2 验收 4 的「不允许静默写入」在写入侧由 `save_parallax` 先校验保证。

---

### Task 6: 接线(config → adapter → server)

**Files:**
- Modify: `katrain/vision/config_service.py`(`VisionServiceConfig` 末尾字段 :125 `capture_fps` 之后;`to_worker_config` :133-152)
- Modify: `katrain/vision/parallax_store.py`(末尾追加 `attach_parallax`)
- Modify: `katrain/vision/worker_inprocess.py`(import 区 :20-43;`__init__` :115-122)
- Modify: `katrain/web/server.py`(:725-730,`VisionService(vision_config, ...)` 之前)
- Test: `tests/test_vision/test_parallax_wiring.py`

**Interfaces:**
- Consumes: `ParallaxParams`、`parallax_store`(Task 5)、`BoardStateExtractor(config, parallax=...)`(Task 3)。
- Produces:
  - `VisionServiceConfig.parallax: dict | None = None`;`to_worker_config()["parallax"]`
  - `attach_parallax(vision_config, hardware_vision_dir, current_generation) -> tuple[VisionServiceConfig, int, str]`
  - `InProcessAdapter._state_extractor_locked.parallax`(有参数时)/ `_state_extractor.parallax is None`(永远)

**约束:** 第 7 条(不改 `worker.py`);server 里不加除调用与一行日志以外的逻辑;不热加载。

- [ ] **Step 1: 写失败测试**

`tests/test_vision/test_parallax_wiring.py`:

```python
import logging
from unittest.mock import patch

from katrain.vision.config_service import VisionServiceConfig
from katrain.vision.parallax import ParallaxParams
from katrain.vision.parallax_store import BOARD_GO_19, ParallaxCalibration, attach_parallax, parallax_path, save_parallax

PARAMS = {"nadir_fx": 9.02, "nadir_fy": 19.58, "k": 0.98969}


def _calib():
    return ParallaxCalibration(
        board=BOARD_GO_19,
        stone_set="ver9-22x7",
        nadir_fx=9.02,
        nadir_fy=19.58,
        k=0.98969,
        m=1 / 0.98969,
        h_implied_mm=339.44 * (1 - 0.98969),  # must equal camera_height_mm * (1 - k)
        camera_height_mm=339.44,
        rms_cells=0.031,
        max_resid_cells=0.07,
        n_samples=17,
        n_black=9,
        n_white=8,
        frames=30,
        geometry_generation="gen-fit",
        fitted_at="2026-09-22T10:00:00+08:00",
    )


class TestVisionServiceConfig:
    def test_parallax_defaults_off_and_reaches_the_worker_config(self):
        assert VisionServiceConfig().to_worker_config()["parallax"] is None
        assert VisionServiceConfig(parallax=PARAMS).to_worker_config()["parallax"] == PARAMS


class TestInProcessAdapter:
    def _adapter(self, config):
        from katrain.vision.worker_inprocess import InProcessAdapter

        with patch("katrain.vision.worker_inprocess.StoneDetector"):
            return InProcessAdapter(config, camera=None)

    def test_only_the_geometry_lock_extractor_gets_parallax(self):
        a = self._adapter({"parallax": PARAMS})
        assert a._state_extractor_locked.parallax == ParallaxParams(**PARAMS)
        assert a._state_extractor.parallax is None  # BoardFinder warp: different grid basis

    def test_no_parallax_key_means_off(self):
        a = self._adapter({})
        assert a._state_extractor_locked.parallax is None and a._state_extractor.parallax is None


class TestAttachParallax:
    def test_without_hardware_vision_dir_it_is_off(self):
        cfg, level, msg = attach_parallax(VisionServiceConfig(parallax=PARAMS), None, None)
        assert cfg.parallax is None and level == logging.INFO and "parallax off" in msg

    def test_uncalibrated_dir_is_off_at_info(self, tmp_path):
        cfg, level, msg = attach_parallax(VisionServiceConfig(), tmp_path, "gen-now")
        assert cfg.parallax is None and level == logging.INFO and "not calibrated" in msg

    def test_broken_file_is_off_at_warning(self, tmp_path):
        path = parallax_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text("{broken")
        cfg, level, msg = attach_parallax(VisionServiceConfig(), tmp_path, "gen-now")
        assert cfg.parallax is None and level == logging.WARNING and "invalid calibration file" in msg

    def test_valid_file_turns_it_on_and_logs_provenance(self, tmp_path):
        save_parallax(parallax_path(tmp_path), _calib())
        cfg, level, msg = attach_parallax(VisionServiceConfig(), tmp_path, "gen-now")
        assert cfg.parallax == PARAMS and level == logging.INFO
        for needle in ("parallax on", "go-19x19", "ver9-22x7", "k=0.989690", "fit_generation=gen-fit", "current_generation=gen-now"):
            assert needle in msg, needle

    def test_it_returns_a_new_config_and_leaves_the_input_alone(self, tmp_path):
        original = VisionServiceConfig()
        save_parallax(parallax_path(tmp_path), _calib())
        cfg, _, _ = attach_parallax(original, tmp_path, None)
        assert original.parallax is None and cfg is not original
```

- [ ] **Step 2: 跑测试确认失败**

Run: `"$PY" -m pytest tests/test_vision/test_parallax_wiring.py -q -p no:cacheprovider`
Expected: `ImportError: cannot import name 'attach_parallax'`

- [ ] **Step 3: 实现**

`katrain/vision/config_service.py`:在 `capture_fps: int = 15` 之后加字段:

```python
    # Stone-parallax correction {"nadir_fx", "nadir_fy", "k"} for the geometry-lock extractor, or None
    # (off). Never set by hand: server.py fills it at startup from <hardware-vision-dir>/parallax/
    # go-19x19.json, written by katrain.vision.tools.calibrate_parallax.
    parallax: dict | None = None
```

`to_worker_config` 返回的字典里 `"capture_fps": self.capture_fps,` 之后加一行:

```python
            "parallax": self.parallax,
```

`katrain/vision/parallax_store.py`:顶部 import 加 `import dataclasses` 与 `import logging`,文件末尾追加:

```python
def attach_parallax(vision_config, hardware_vision_dir, current_generation: str | None):
    """Server startup: (vision_config with .parallax set or cleared, log level, log message).

    Returns a new config (dataclasses.replace) and never raises: a missing or broken calibration
    only turns the correction off. A missing file is the normal pre-calibration state (INFO); a
    present-but-invalid one is a fault worth noticing (WARNING)."""
    if not hardware_vision_dir:
        return (
            dataclasses.replace(vision_config, parallax=None),
            logging.INFO,
            "vision parallax off: no --hardware-vision-dir",
        )
    path = parallax_path(hardware_vision_dir)
    calib, reason = load_parallax(path)
    if calib is None:
        level = logging.INFO if not path.exists() else logging.WARNING
        return dataclasses.replace(vision_config, parallax=None), level, f"vision parallax off: {reason}"
    message = (
        f"vision parallax on: board={calib.board} stone_set={calib.stone_set} k={calib.k:.6f} "
        f"nadir=({calib.nadir_fx:.3f},{calib.nadir_fy:.3f}) h_implied={calib.h_implied_mm:.2f}mm "
        f"rms={calib.rms_cells:.3f}cells n={calib.n_samples} fitted_at={calib.fitted_at} "
        f"fit_generation={calib.geometry_generation} current_generation={current_generation}"
    )
    return dataclasses.replace(vision_config, parallax=calib.params.to_dict()), logging.INFO, message
```

`katrain/vision/worker_inprocess.py`:import 区加一行(按字母序放在 `motion_roi` 之后):

```python
from katrain.vision.parallax import ParallaxParams
```

`__init__` 里 `self._state_extractor_locked = BoardStateExtractor(...)` 整段替换为:

```python
        # Geometry-lock warps add a 1-cell margin (matching baipu_autolabel training images), so the
        # mapping for that path needs the matching border. BoardFinder fallback keeps border 0.
        # Stone parallax is calibrated in THIS warp's grid, so only this extractor may receive it.
        parallax_cfg = config.get("parallax")
        self._state_extractor_locked = BoardStateExtractor(
            BoardConfig(
                grid_size=board_config.grid_size,
                board_width_mm=board_config.board_width_mm,
                board_length_mm=board_config.board_length_mm,
                margin_cells=DEFAULT_MARGIN_CELLS,
            ),
            parallax=ParallaxParams(**parallax_cfg) if parallax_cfg else None,
        )
```

`katrain/web/server.py`:在 `if vision_config and vision_config.enabled and camera_hub is not None:` 块内,
`from katrain.vision.service import VisionService` 之后、`vision = VisionService(vision_config, frame_source=camera_hub)` 之前插入:

```python
        from katrain.vision.parallax_store import attach_parallax

        vision_config, parallax_level, parallax_message = attach_parallax(
            vision_config,
            hardware_vision_dir,
            hardware_vision_state.generation if hardware_vision_state is not None else None,
        )
        log.log(parallax_level, parallax_message)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `"$PY" -m pytest tests/test_vision/test_parallax_wiring.py tests/test_vision/test_config_service.py tests/test_vision/test_worker_commands.py tests/test_vision/test_warp_consistency.py -q -p no:cacheprovider`
Expected: 全部 passed

- [ ] **Step 5: server 能 import**

Run: `"$PY" -c "import katrain.web.server"`
Expected: 无输出、退出码 0

- [ ] **Step 6: 提交**

```bash
git add -- katrain/vision/config_service.py katrain/vision/parallax_store.py katrain/vision/worker_inprocess.py katrain/web/server.py tests/test_vision/test_parallax_wiring.py
git commit -m "feat(vision): load the board's parallax calibration at startup, geometry-lock extractor only

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**验收:** design D2 / D3 / §2.4;prd P1-1「依赖/卡点」:没标定前开关关着(INFO 一行);
文件坏了关着(WARNING 一行)。server 实际启动那一行在 Task 10 上板时看日志核。

---

### Task 7: board delta 诊断(P2)

**Files:**
- Modify: `katrain/vision/worker_inprocess.py`(`_log_board_delta` :223-247)
- Test: `tests/test_vision/test_parallax_wiring.py`(末尾追加一个类)

**Interfaces:**
- Consumes: `BoardStateExtractor.parallax_points`(Task 3)、Task 6 之后的 `worker_inprocess.py`。
- Produces: 日志格式 `board delta: +['(r,c)C~<cls><conf>@<d> pl<shift>[*]'] -['(r,c)C~...']`

**约束:** `(r,c)颜色` 前缀保持原样(vision-recognition-stability §7 按它 grep);`ambiguous_stone` 事件不动;`worker.py` 不动。

- [ ] **Step 1: 写失败测试**(追加到 `tests/test_vision/test_parallax_wiring.py` 末尾)

```python
class TestBoardDeltaDiagnostics:
    """P2 (narrowed 2026-09-22): each board change shows the nearby detection's parallax shift and a *
    when the correction moved it to a different intersection; 0.00 and no * when off."""

    def _log(self, parallax, caplog):
        import numpy as np

        from katrain.vision.board_state import BoardStateExtractor
        from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig
        from katrain.vision.stone_detector import Detection
        from katrain.vision.worker_inprocess import InProcessAdapter
        from tests.test_vision.board_state_corpus import IMG, grid_to_px
        from tests.test_vision.parallax_synth import K_TRUE, NADIR_GRID

        cfg = BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS)
        a = InProcessAdapter.__new__(InProcessAdapter)
        a._geometry = object()  # geometry-lock path -> _active_extractor() is the locked one
        a._state_extractor = BoardStateExtractor(BoardConfig())
        a._state_extractor_locked = BoardStateExtractor(
            cfg, parallax=ParallaxParams(*NADIR_GRID, K_TRUE) if parallax else None
        )
        before = np.zeros((19, 19), dtype=int)
        before[5][5] = 2
        after = np.zeros((19, 19), dtype=int)
        after[1][9] = 1
        x, y = grid_to_px(cfg, 9.0, 0.40)  # raw rounds to row 0; corrected (0.598) rounds to row 1
        with caplog.at_level(logging.INFO, logger="katrain.vision.worker_inprocess"):
            a._log_board_delta(before, after, [Detection(x_center=x, y_center=y, class_id=0, confidence=0.9)], IMG, IMG)
        (line,) = [r.getMessage() for r in caplog.records if r.getMessage().startswith("board delta:")]
        return line

    def test_on_shows_raw_to_corrected_shift_and_rescue_marker(self, caplog):
        line = self._log(True, caplog)
        assert "'(1,9)B~B0.90@0.40 pl0.20* (0.40,9.00)>(0.60,9.00)'" in line
        assert "'(5,5)W~none'" in line

    def test_off_shows_zero_shift_and_no_marker(self, caplog):
        line = self._log(False, caplog)
        assert "'(1,9)B~B0.90@0.60 pl0.00 (0.40,9.00)>(0.40,9.00)'" in line
        assert "*" not in line
```

- [ ] **Step 2: 跑测试确认失败**

Run: `"$PY" -m pytest tests/test_vision/test_parallax_wiring.py -q -p no:cacheprovider -k BoardDelta`
Expected: 2 failed(今天新增格不带 `~` 描述,也没有 `pl`)

- [ ] **Step 3: 实现** —— `_log_board_delta` 整个替换为:

```python
    def _log_board_delta(self, before, after, detections, w: int, h: int) -> None:
        """One INFO line per stable-board change: which cells appeared/vanished and what the
        detector actually saw nearby — turns 'why did my stone drop?' into reading a log line.

        Each cell carries its nearest detection as
        <class><conf>@<distance> pl<shift>[*] (<fy_raw>,<fx_raw>)>(<fy>,<fx>): shift is how far the
        parallax correction moved it (cells; 0.00 when off), a * means the correction changed which
        intersection it rounds to — "this move was rescued by parallax" — and the coordinate pair is the
        raw -> corrected continuous (row, col) position (prd P2). The leading (r,c)<colour> token is
        unchanged: vision-recognition-stability §7 greps it."""
        pts = self._active_extractor().parallax_points(detections, img_w=w, img_h=h)
        names = {0: "B", 1: "W", 2: "R", 3: "G"}

        def near(r, c):
            best = None
            for fy_raw, fx_raw, fy, fx, cls, conf in pts:
                d = ((fy - r) ** 2 + (fx - c) ** 2) ** 0.5
                if best is None or d < best[0]:
                    best = (d, cls, conf, fy_raw, fx_raw, fy, fx)
            if best is None or best[0] > 1.0:
                return "none"
            d, cls, conf, fy_raw, fx_raw, fy, fx = best
            shift = ((fy - fy_raw) ** 2 + (fx - fx_raw) ** 2) ** 0.5
            rescued = (int(round(fy_raw)), int(round(fx_raw))) != (int(round(fy)), int(round(fx)))
            return (
                f"{names.get(cls, '?')}{conf:.2f}@{d:.2f} pl{shift:.2f}{'*' if rescued else ''} "
                f"({fy_raw:.2f},{fx_raw:.2f})>({fy:.2f},{fx:.2f})"
            )

        sym = {1: "B", 2: "W"}
        added = [
            f"({r},{c}){sym.get(int(after[r][c]), '?')}~{near(int(r), int(c))}"
            for r, c in zip(*np.where((before != after) & (after != 0)))
        ]
        removed = [
            f"({r},{c}){sym.get(int(before[r][c]), '?')}~{near(int(r), int(c))}"
            for r, c in zip(*np.where((before != after) & (after == 0)))
        ]
        logger.info("board delta: +%s -%s", added or "[]", removed or "[]")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `"$PY" -m pytest tests/test_vision/test_parallax_wiring.py tests/test_vision/test_worker_commands.py -q -p no:cacheprovider`
Expected: 全部 passed

- [ ] **Step 5: 提交**

```bash
git add -- katrain/vision/worker_inprocess.py tests/test_vision/test_parallax_wiring.py
git commit -m "feat(vision): board delta log shows each move's parallax shift and rescue marker

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**验收:** prd P2(2026-09-22 收窄版):开着时每次棋盘变化可查 `pl` 与 `*`,关着时 `pl0.00`、无 `*`;
`ambiguous_stone` 事件结构不变(本任务不碰它;既有测试 `test_worker_commands.py` 照过)。

---

### Task 8: 板上标定工具 `calibrate_parallax`

**Files:**
- Create: `katrain/vision/tools/calibrate_parallax.py`
- Test: `tests/test_vision/test_calibrate_parallax.py`

**Interfaces:**
- Consumes: `BoardStateExtractor.parallax_points`(Task 3)、`FitResult` / `fit_parallax`(Task 4)、
  `ParallaxCalibration` / `save_parallax` / `parallax_path` / `H_IMPLIED_WINDOW_MM` / `BOARD_GO_19`(Task 5)。
- Produces:
  - `PATTERN_17: tuple[tuple[int, int], ...]`((row, col))、`MIN_PRESENCE = 0.8`、`MAX_EXTRA = 0.2`、`MAX_RESID_CELLS = 0.30`、
    `DEFAULT_CAMERA_HEIGHT_MM = 339.44`
  - `Verdict(ok, reasons, fit, medians, n_black, n_white)`
  - `evaluate(frames, camera_height_mm, pattern=PATTERN_17) -> Verdict`;`frames` 是每帧的原始棋子检测 `[(fy_raw, fx_raw, class_id)]`
  - `MAX_GRID_SHIFT_CELLS = 0.10`、`MIN_GRID_LINES = 15`、`EMPTY_FRAMES = 5`
  - `GridOffset(dx_cells, dy_cells, lines_x, lines_y)`(frozen,`.shift_cells`)、
    `grid_offset(warped_bgr, out_size, margin_cells=DEFAULT_MARGIN_CELLS) -> GridOffset`、
    `grid_check_reasons(off, when) -> list[str]`
  - `decide_and_write(frames, *, grid_offsets, out_path, stone_set, camera_height_mm, geometry_generation, fitted_at, dry_run) -> tuple[Verdict, ParallaxCalibration | None]`;
    `grid_offsets` 是 `{"start": GridOffset, "end": GridOffset}`,必填,空则拒绝
  - `camera_settings(profile) -> dict`(`lock_exposure` / `exposure` / `lock_awb`,照服务对这一代几何的采集方式)
  - CLI:`python -m katrain.vision.tools.calibrate_parallax --hardware-vision-dir D --model M --stone-set S [...]`

**约束:** 第 3 条(nadir 只来自拟合);只读几何(`HardwareVisionStateStore.load_current`),不写 generations;
`h_implied` 超窗口 / 漏摆 / 多摆 / 单点残差过大 / **印刷网格与保存的几何对不上**都**不写文件、旧文件原样保留**;
摄像头、检测器、`HardwareVisionStateStore` 一律在 `main()` 里延迟 import(判定那一半要能在没有摄像头的环境里单测)。

**为什么要查网格(codex 第 2 轮 [high],Opus 裁决 2026-09-22):** 拟合是 D = mP + b,warp 的平移 t 被 b 整个
吸收进 nadir,残差为零、h 照样落在窗口里 —— 拟合自己**看不见**一张过期的 warp。运行时几何一旦重新锁好,这个 t
就变成永久的 k·t ≈ t 的误差。能看见它的只有「印刷线在不在 warp 期望的地方」:线印在 h=0,跟棋盘一起动。所以在
空盘上、摆子**之前**和收子**之后**各量一次;任何一次偏 > 0.10 格(与 `GeometryDriftMonitor` 判「棋盘动了」同一个
阈值)就拒绝。不留绕过开关。偏移接近整格时会混叠成 ≈0(0.95 读成 −0.05),那种情况 17 点配对会失败,测试 8 钉住。

- [ ] **Step 1: 写失败测试**

`tests/test_vision/test_calibrate_parallax.py`:

```python
"""Calibration tool, judgment half (prd P1-2 acceptance 4): nothing is written unless every check passes."""

import numpy as np
import pytest

from katrain.vision.config import DEFAULT_MARGIN_CELLS
from katrain.vision.parallax_store import load_parallax, parallax_path
from katrain.vision.tools.calibrate_parallax import (
    MAX_GRID_SHIFT_CELLS,
    PATTERN_17,
    GridOffset,
    decide_and_write,
    evaluate,
    grid_check_reasons,
    grid_offset,
)
from katrain.vision.warp import margin_px_for
from tests.test_vision.parallax_synth import H_MM, H_STONE_MM, K_TRUE, detected_grid

ALIGNED = GridOffset(0.0, 0.0, 19, 19)
OUT = 950  # geometry-lock warp size; with the 1-cell margin the warped canvas is 1056
PAD = margin_px_for(OUT, DEFAULT_MARGIN_CELLS)
CANVAS = OUT + 2 * PAD
PITCH = (OUT - 1) / 18


def _frames(k=K_TRUE, n=30, jitter=0.02, shift=None, seed=1):
    """Raw detections as the tool sees them: one stone per calibration point, black/white alternating."""
    rng = np.random.default_rng(seed)
    frames = []
    for _ in range(n):
        dets = []
        for i, (r, c) in enumerate(PATTERN_17):
            fx, fy = detected_grid(c, r, k=k)
            if shift is not None and (r, c) == shift[0]:
                fx += shift[1]
            dets.append((fy + rng.normal(0, jitter), fx + rng.normal(0, jitter), i % 2))
        frames.append(dets)
    return frames


def _coverage(pos, centre, half_width=1.0):
    """Share of each pixel [p-0.5, p+0.5] covered by the band [centre-half_width, centre+half_width]."""
    return np.clip(np.minimum(pos + 0.5, centre + half_width) - np.maximum(pos - 0.5, centre - half_width), 0, 1)


def _board_image(dx=0.0, dy=0.0, jitter=0.0, lines=True, seed=0):
    """A warped EMPTY board: wood, a lighting gradient, sensor noise and (optionally) the printed grid, drawn
    (dx, dy) cells away from where the saved geometry expects it; ``jitter`` = per-line print/warp error in cells."""
    rng = np.random.default_rng(seed)
    pos = np.arange(CANVAS, dtype=np.float64)
    ink = np.zeros((CANVAS, CANVAS))
    if lines:
        xl = PAD + (np.arange(19) + dx + rng.normal(0, jitter, 19)) * PITCH
        yl = PAD + (np.arange(19) + dy + rng.normal(0, jitter, 19)) * PITCH
        span_x = _coverage(pos, (xl[0] + xl[-1]) / 2, (xl[-1] - xl[0]) / 2 + 1)
        span_y = _coverage(pos, (yl[0] + yl[-1]) / 2, (yl[-1] - yl[0]) / 2 + 1)
        for x in xl:
            ink = np.maximum(ink, np.outer(span_y, _coverage(pos, x)))
        for y in yl:
            ink = np.maximum(ink, np.outer(_coverage(pos, y), span_x))
        yy, xx = np.mgrid[0:CANVAS, 0:CANVAS]
        for r in (3, 9, 15):
            for c in (3, 9, 15):
                ink[(xx - xl[c]) ** 2 + (yy - yl[r]) ** 2 <= 16] = 1.0  # star points
    wood = np.array([95.0, 165.0, 215.0])  # BGR
    light = 0.75 + 0.35 * pos[None, :] / CANVAS + 0.1 * pos[:, None] / CANVAS
    img = wood[None, None, :] * light[:, :, None] * (1 - 0.7 * ink[:, :, None])
    img += rng.normal(0, 6, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def _grain_image(seed):
    """No grid at all: wood with 40 random dark grain streaks, the lighting gradient and noise."""
    rng = np.random.default_rng(seed)
    img = _board_image(lines=False, seed=seed).astype(np.float64)
    for _ in range(40):
        at = int(rng.uniform(1, CANVAS - 1))
        if rng.random() < 0.5:
            img[:, at - 1 : at + 1] *= rng.uniform(0.6, 0.9)
        else:
            img[at - 1 : at + 1, :] *= rng.uniform(0.6, 0.9)
    return np.clip(img, 0, 255).astype(np.uint8)


def _run(tmp_path, frames, dry_run=False, grid_offsets=None):
    return decide_and_write(
        frames,
        grid_offsets={"start": ALIGNED, "end": ALIGNED} if grid_offsets is None else grid_offsets,
        out_path=parallax_path(tmp_path),
        stone_set="ver9-22x7",
        camera_height_mm=H_MM,
        geometry_generation="gen-1",
        fitted_at="2026-09-22T10:00:00+08:00",
        dry_run=dry_run,
    )


def test_pattern_is_17_distinct_on_board_points_spanning_both_axes():
    assert len(set(PATTERN_17)) == 17
    assert all(0 <= r < 19 and 0 <= c < 19 for r, c in PATTERN_17)
    pts = np.array(PATTERN_17, dtype=float)
    assert np.linalg.matrix_rank(pts - pts.mean(axis=0)) == 2


def test_clean_capture_passes_and_writes_the_file(tmp_path):
    verdict, calib = _run(tmp_path, _frames())
    assert verdict.ok, verdict.reasons
    assert abs(verdict.fit.k - K_TRUE) < 5e-4
    assert verdict.fit.h_implied_mm == pytest.approx(H_STONE_MM, abs=0.3)
    assert (verdict.n_black, verdict.n_white) == (9, 8)
    loaded, reason = load_parallax(parallax_path(tmp_path))
    assert reason == "ok" and loaded == calib
    assert (loaded.stone_set, loaded.geometry_generation, loaded.frames, loaded.n_samples) == (
        "ver9-22x7",
        "gen-1",
        30,
        17,
    )


def test_dry_run_writes_nothing(tmp_path):
    verdict, _ = _run(tmp_path, _frames(), dry_run=True)
    assert verdict.ok and not parallax_path(tmp_path).exists()


def _drop(frames, cell, first_n=None):
    for i, dets in enumerate(frames):
        if first_n is None or i < first_n:
            dets[:] = [d for d in dets if (int(round(d[0])), int(round(d[1]))) != cell]
    return frames


def _append(frames, det, first_n=None):
    for i, dets in enumerate(frames):
        if first_n is None or i < first_n:
            dets.append(det)
    return frames


FAILURES = {
    "point missing": (lambda: _drop(_frames(), (9, 9)), "(9, 9)"),
    "point missing in 8 of 30 frames": (lambda: _drop(_frames(), (9, 9), first_n=8), "(9, 9)"),
    "two stones on one point": (lambda: _append(_frames(), (9.02, 9.01, 0)), "(9, 9)"),
    "stone off the pattern": (lambda: _append(_frames(), (5.0, 5.0, 0)), "(5, 5)"),
    "stone 0.45 cell off its point": (lambda: _frames(shift=((9, 9), 0.45)), "(9, 9)"),
    "implied height below the window": (lambda: _frames(k=(H_MM - 1.0) / H_MM), "h_implied"),
    "implied height far above the window": (lambda: _frames(k=(H_MM - 12.0) / H_MM), ""),
    "no frames": (lambda: [], "no frames"),
}


@pytest.mark.parametrize("name", sorted(FAILURES))
def test_failures_write_nothing_and_keep_the_old_file(tmp_path, name):
    make, needle = FAILURES[name]
    path = parallax_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"previous calibration")
    verdict, calib = _run(tmp_path, make())
    assert not verdict.ok and calib is None
    assert needle in " | ".join(verdict.reasons)
    assert path.read_bytes() == b"previous calibration"


def test_a_transient_extra_detection_is_tolerated(tmp_path):
    verdict, _ = _run(tmp_path, _append(_frames(), (5.0, 5.0, 0), first_n=2), dry_run=True)
    assert verdict.ok, verdict.reasons


def test_led_classes_and_margin_objects_are_not_stones(tmp_path):
    frames = _append(_append(_frames(), (9.0, 9.0, 2)), (-0.8, 4.0, 0))
    verdict, _ = _run(tmp_path, frames, dry_run=True)
    assert verdict.ok, verdict.reasons


def test_camera_settings_reproduce_the_service_capture():
    from types import SimpleNamespace

    from katrain.vision.tools.calibrate_parallax import camera_settings

    locked = camera_settings(SimpleNamespace(strategy="hardware_auto_then_lock"))
    assert locked == {"lock_exposure": True, "exposure": None, "lock_awb": False}
    assert camera_settings(SimpleNamespace(strategy="something_else"))["lock_exposure"] is False


def test_main_refuses_when_exposure_cannot_be_locked(tmp_path, monkeypatch):
    """codex review 2026-09-22: never calibrate under an exposure the service would not run with."""
    from types import SimpleNamespace

    import katrain.vision.camera as camera_mod
    import katrain.vision.stone_detector as detector_mod
    import katrain.web.core.hardware_vision_state as hvs
    from katrain.vision.tools import calibrate_parallax as tool

    state = SimpleNamespace(
        generation="gen-1",
        geometry=object(),
        profile=SimpleNamespace(strategy=hvs.CAMERA_STRATEGY_HARDWARE_AUTO_THEN_LOCK),
    )
    monkeypatch.setattr(hvs, "HardwareVisionStateStore", lambda root: SimpleNamespace(load_current=lambda *a: state))
    monkeypatch.setattr(detector_mod, "StoneDetector", lambda *a, **k: object())

    class FakeCamera:
        controls_effective = False  # the lock did not take

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.closed = False
            FakeCamera.last = self

        def open(self):
            return True

        def close(self):
            self.closed = True

    monkeypatch.setattr(camera_mod, "CameraManager", FakeCamera)
    rc = tool.main(["--hardware-vision-dir", str(tmp_path), "--model", "m.rknn", "--stone-set", "ver9-22x7"])
    assert rc == 2
    assert FakeCamera.last.kwargs["lock_exposure"] is True and FakeCamera.last.closed
    assert not parallax_path(tmp_path).exists()


# --- printed-grid check (codex round 2 [high]; Opus ruling 2026-09-22) ---


def test_aligned_grid_reads_zero_and_passes():
    off = grid_offset(_board_image(), OUT)
    assert abs(off.dx_cells) <= 0.02 and abs(off.dy_cells) <= 0.02
    assert (off.lines_x, off.lines_y) == (19, 19)
    assert grid_check_reasons(off, "start") == []


def test_a_quarter_cell_stale_geometry_is_measured_and_refused():
    off = grid_offset(_board_image(dy=0.25), OUT)
    assert off.dy_cells == pytest.approx(0.25, abs=0.02)
    reasons = grid_check_reasons(off, "start")
    assert reasons and "re-lock" in reasons[0]


@pytest.mark.parametrize("dx, dy, refused", [(-0.12, 0.07, True), (0.06, 0.05, False)])
def test_the_grid_threshold_is_pinned_from_both_sides(dx, dy, refused):
    off = grid_offset(_board_image(dx=dx, dy=dy), OUT)
    assert (off.shift_cells > MAX_GRID_SHIFT_CELLS) == refused
    assert bool(grid_check_reasons(off, "end")) == refused


@pytest.mark.parametrize("axis", ["dx", "dy"])
@pytest.mark.parametrize("shift", [0.45, -0.45])
def test_large_sub_cell_shifts_are_recovered_and_refused(axis, shift):
    off = grid_offset(_board_image(**{axis: shift}), OUT)
    assert getattr(off, f"{axis}_cells") == pytest.approx(shift, abs=0.03)
    assert grid_check_reasons(off, "start")


def test_per_line_print_error_is_tolerated_but_a_shift_is_not():
    assert grid_check_reasons(grid_offset(_board_image(jitter=0.06, seed=3), OUT), "start") == []
    assert grid_check_reasons(grid_offset(_board_image(dy=0.25, jitter=0.06, seed=3), OUT), "start")


@pytest.mark.parametrize("seed", range(10))
def test_a_frame_without_a_grid_is_refused_as_not_found(seed):
    reasons = grid_check_reasons(grid_offset(_grain_image(seed), OUT), "start")
    assert reasons and "not found" in reasons[0]


def test_stale_geometry_is_refused_although_the_fit_itself_is_perfect(tmp_path):
    """codex round 2 [high]: a warp translation is absorbed into the nadir with zero residual and a plausible h, so
    only the printed-grid check can refuse it. Red if decide_and_write ignores grid_offsets."""
    frames = [[(fy + 0.25, fx, cls) for fy, fx, cls in dets] for dets in _frames(jitter=0.0)]
    alone = evaluate(frames, H_MM)
    assert alone.ok and alone.fit.max_resid_cells < 1e-9  # the fit cannot see it
    assert alone.fit.h_implied_mm == pytest.approx(H_STONE_MM, abs=0.3)
    stale = grid_offset(_board_image(dy=0.25), OUT)
    path = parallax_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"previous calibration")
    for offsets in ({"start": stale, "end": stale}, {"start": ALIGNED, "end": stale}):  # stale before / bumped during
        verdict, calib = _run(tmp_path, frames, grid_offsets=offsets)
        assert not verdict.ok and calib is None
        assert "re-lock" in " | ".join(verdict.reasons)
        assert path.read_bytes() == b"previous calibration"


def test_a_whole_cell_shift_that_the_grid_check_aliases_to_zero_is_refused_by_pairing(tmp_path):
    frames = [[(fy, fx + 1.0, cls) for fy, fx, cls in dets] for dets in _frames()]
    verdict, calib = _run(tmp_path, frames)
    assert not verdict.ok and calib is None


def test_no_grid_measurement_means_no_calibration(tmp_path):
    verdict, calib = _run(tmp_path, _frames(), grid_offsets={})
    assert not verdict.ok and calib is None
    assert "no geometry check" in " | ".join(verdict.reasons)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `"$PY" -m pytest tests/test_vision/test_calibrate_parallax.py -q -p no:cacheprovider`
Expected: `ModuleNotFoundError: No module named 'katrain.vision.tools.calibrate_parallax'`

- [ ] **Step 3: 实现**

`katrain/vision/tools/calibrate_parallax.py`:

```python
"""Stone-parallax calibration for the geometry-locked board (vision-stone-parallax track).

Run ON THE BOARD with the katrain service stopped (it owns the camera):

    sudo systemctl stop smartbox-katrain
    /opt/smartbox/venv-katrain/bin/python -m katrain.vision.tools.calibrate_parallax \\
        --hardware-vision-dir /var/lib/smartbox/hardware/vision \\
        --model /opt/smartbox/share/katrain-vision/go4_s.rknn --backend rknn \\
        --camera 0 --resolution 1920x1080 --enhance clahe --conf 0.30 --stone-set ver9-22x7
    sudo systemctl start smartbox-katrain

Start with the board EMPTY and exactly where it was when the geometry was locked (do not touch it after
stopping the service). The tool first checks that the printed grid lines sit where the saved geometry
expects them; then place one stone on each of the 17 printed points (alternate black and white), press
Enter, keep hands out of view; then remove all stones for the closing grid check. The tool warps each
frame exactly like the service, reads the RAW (uncorrected) grid positions, takes the per-point median over
--frames frames, fits k and the nadir, and writes <hardware-vision-dir>/parallax/go-19x19.json ONLY if every
check passes, both grid checks included. Recalibrate after moving the camera arm, changing the board or the
stones, or aligning the board (prd §5).
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from katrain.vision.classes import NAME_TO_ID, STONE_CLASS_IDS
from katrain.vision.config import DEFAULT_MARGIN_CELLS
from katrain.vision.parallax import FitResult, fit_parallax
from katrain.vision.parallax_store import (
    BOARD_GO_19,
    H_IMPLIED_WINDOW_MM,
    ParallaxCalibration,
    parallax_path,
    save_parallax,
)
from katrain.vision.warp import adjust_M_for_resolution, margin_px_for, warp_with_margin

# (row, col) in the geometry-lock grid: 9 star points, 4 corners, 4 edge midpoints. 17 rather than 9:
# with ~1.5 mm of placement error, 9 points get falsely refused by the 2-8 mm window 2.5% of the time,
# 17 points 0.4% (design D5).
PATTERN_17: tuple[tuple[int, int], ...] = (
    (3, 3), (3, 9), (3, 15), (9, 3), (9, 9), (9, 15), (15, 3), (15, 9), (15, 15),
    (0, 0), (0, 18), (18, 0), (18, 18),
    (0, 9), (9, 0), (9, 18), (18, 9),
)  # fmt: skip
MIN_PRESENCE = 0.8  # a point must hold exactly one stone detection in at least this share of frames
MAX_EXTRA = 0.2  # an off-pattern intersection holding a stone in this share of frames is a real stray stone
# 0.30 cell (~6.9 mm), not tighter: at ~1.5 mm placement error one of 17 points exceeds 0.15 cell
# about 70% of the time, 0.30 cell about 0.05%.
MAX_RESID_CELLS = 0.30
# Lens height above the board for the ver9 mount (geometry.md §3: lens_mm z 348.942 - board z 9.5).
# Only used for the h_implied diagnostic and its 2-8 mm gate; the correction itself never uses it.
DEFAULT_CAMERA_HEIGHT_MM = 339.44
# Printed-grid check (codex round 2 [high]). The fit absorbs a warp translation t into the nadir with zero
# residual, and once the runtime geometry is re-locked t becomes a permanent error of k*t ~ t. The printed lines
# (h = 0) move with the board, so their offset from where the warp expects them IS that t. 0.10 cell is the
# GeometryDriftMonitor threshold: a warp the service would call "board moved" is never calibrated on.
MAX_GRID_SHIFT_CELLS = 0.10
MIN_GRID_LINES = 15  # of 19 per axis must agree with the median offset, or the grid was not seen
EMPTY_FRAMES = 5  # empty-board frames per grid check (per-pixel median)
_LINE_TOL_CELLS = 0.15
_BLACK = NAME_TO_ID["black"]


@dataclass(frozen=True)
class GridOffset:
    dx_cells: float  # printed grid minus where the saved geometry puts it, in cells
    dy_cells: float
    lines_x: int  # lines within _LINE_TOL_CELLS of the median offset, of 19
    lines_y: int

    @property
    def shift_cells(self) -> float:
        return math.hypot(self.dx_cells, self.dy_cells)


def _axis_offset(profile, expected, pitch):
    """Offset (cells) of the 19 line peaks in ``profile`` from ``expected``, and how many lines agree with it.
    A comb search over [-0.5, 0.5) cell finds the grid as a whole; each line is then refined to a sub-pixel peak."""
    xs = np.arange(len(profile), dtype=np.float64)
    deltas = np.arange(-50, 50) / 100.0
    scores = [np.interp(expected + d * pitch, xs, profile).sum() for d in deltas]
    d0 = float(deltas[int(np.argmax(scores))])
    half = int(0.4 * pitch)
    offsets = []
    for e in expected:
        c = int(round(e + d0 * pitch))
        lo, hi = max(c - half, 1), min(c + half, len(profile) - 2)
        i = lo + int(np.argmax(profile[lo : hi + 1]))
        a, b, cc = profile[i - 1], profile[i], profile[i + 1]
        den = a - 2 * b + cc
        sub = 0.5 * (a - cc) / den if den < 0 else 0.0
        offsets.append((i + sub - e) / pitch)
    offsets = np.array(offsets)
    t = float(np.median(offsets))
    return t, int(np.sum(np.abs(offsets - t) <= _LINE_TOL_CELLS))


def grid_offset(warped_bgr, out_size: int, margin_cells: float = DEFAULT_MARGIN_CELLS) -> GridOffset:
    """Where the printed grid lines of an EMPTY warped board sit relative to where the geometry lock puts them
    (line i at pad + i*(out_size-1)/18, the warp's own geometry, not BoardConfig's mm mapping)."""
    pad = margin_px_for(out_size, margin_cells)
    pitch = (out_size - 1) / 18
    expected = pad + np.arange(19) * pitch
    grey = cv2.cvtColor(warped_bgr, cv2.COLOR_BGR2GRAY) if warped_bgr.ndim == 3 else warped_bgr
    grey = cv2.GaussianBlur(grey, (3, 3), 0)
    # black-hat keeps thin dark marks (lines, star points) and drops lighting gradients and large blobs
    lines = cv2.morphologyEx(grey, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15)))
    lines = lines.astype(np.float64)
    inside = slice(pad, pad + out_size)
    dx, nx = _axis_offset(lines[inside, :].mean(axis=0), expected, pitch)
    dy, ny = _axis_offset(lines[:, inside].mean(axis=1), expected, pitch)
    return GridOffset(dx, dy, nx, ny)


def grid_check_reasons(off: GridOffset, when: str) -> list[str]:
    if min(off.lines_x, off.lines_y) < MIN_GRID_LINES:
        return [
            f"{when}: printed grid lines not found (x {off.lines_x}/19, y {off.lines_y}/19): is the board empty and lit?"
        ]
    if off.shift_cells > MAX_GRID_SHIFT_CELLS:
        return [
            f"{when}: the saved geometry is {off.shift_cells:.2f} cells off the printed grid "
            f"(dx {off.dx_cells:+.2f}, dy {off.dy_cells:+.2f}): the board moved since the geometry was locked. "
            "Start the service, re-lock the geometry on the empty board, stop it, and calibrate again."
        ]
    return []


@dataclass
class Verdict:
    ok: bool
    reasons: list[str]
    fit: FitResult | None = None
    medians: dict = field(default_factory=dict)  # (row, col) -> (fx_raw, fy_raw)
    n_black: int = 0
    n_white: int = 0


def evaluate(frames, camera_height_mm: float, pattern=PATTERN_17) -> Verdict:
    """Judge a capture. ``frames``: per captured frame, the RAW detections as [(fy_raw, fx_raw, class_id)]."""
    total = len(frames)
    if total == 0:
        return Verdict(False, ["no frames captured"])
    wanted = set(pattern)
    seen = {cell: [] for cell in pattern}
    extra = Counter()
    for dets in frames:
        per_cell = defaultdict(list)
        for fy, fx, cls in dets:
            if cls not in STONE_CLASS_IDS:
                continue  # LED classes are not stones
            cell = (int(round(fy)), int(round(fx)))
            if not (0 <= cell[0] < 19 and 0 <= cell[1] < 19):
                continue  # warp-margin objects are not stones
            per_cell[cell].append((fx, fy, cls))
        for cell, hits in per_cell.items():
            if cell in wanted:
                if len(hits) == 1:
                    seen[cell].append(hits[0])
            else:
                extra[cell] += 1
    reasons = []
    for cell in pattern:
        if len(seen[cell]) < MIN_PRESENCE * total:
            reasons.append(
                f"point {cell}: exactly one stone in only {len(seen[cell])}/{total} frames "
                "(missing, doubled, or not detected)"
            )
    for cell, n in sorted(extra.items()):
        if n >= MAX_EXTRA * total:
            reasons.append(
                f"unexpected stone at {cell} in {n}/{total} frames (only the calibration points may hold stones)"
            )
    if reasons:
        return Verdict(False, reasons)
    medians = {
        cell: (float(np.median([h[0] for h in seen[cell]])), float(np.median([h[1] for h in seen[cell]])))
        for cell in pattern
    }
    colours = [Counter(h[2] for h in seen[cell]).most_common(1)[0][0] for cell in pattern]
    n_black = sum(1 for c in colours if c == _BLACK)
    n_white = len(pattern) - n_black
    try:
        fit = fit_parallax([(c, r) for r, c in pattern], [medians[cell] for cell in pattern], camera_height_mm)
    except ValueError as exc:
        return Verdict(False, [f"fit failed: {exc}"], None, medians, n_black, n_white)
    lo, hi = H_IMPLIED_WINDOW_MM
    if not lo <= fit.h_implied_mm <= hi:
        reasons.append(f"h_implied {fit.h_implied_mm:.2f} mm is outside [{lo}, {hi}]: the warp or the pairing is wrong")
    if fit.max_resid_cells > MAX_RESID_CELLS:
        reasons.append(
            f"point {pattern[fit.worst_index]} is {fit.max_resid_cells:.2f} cells off the fit "
            f"(> {MAX_RESID_CELLS}): re-seat that stone on its intersection"
        )
    return Verdict(not reasons, reasons, fit, medians, n_black, n_white)


def decide_and_write(
    frames,
    *,
    grid_offsets: dict,
    out_path,
    stone_set: str,
    camera_height_mm: float,
    geometry_generation,
    fitted_at: str,
    dry_run: bool,
):
    """Grid checks + evaluate(); on success build the calibration and (unless dry_run) save it. Nothing is written
    on failure. ``grid_offsets``: {"start": GridOffset, "end": GridOffset} measured on the empty board."""
    grid_reasons = [] if grid_offsets else ["no geometry check: the printed grid was not measured on the empty board"]
    for when, off in grid_offsets.items():
        grid_reasons += grid_check_reasons(off, when)
    verdict = evaluate(frames, camera_height_mm)
    if grid_reasons:
        verdict = replace(verdict, ok=False, reasons=grid_reasons + verdict.reasons)
    if not verdict.ok:
        return verdict, None
    fit = verdict.fit
    calib = ParallaxCalibration(
        board=BOARD_GO_19,
        stone_set=stone_set,
        nadir_fx=fit.nadir_fx,
        nadir_fy=fit.nadir_fy,
        k=fit.k,
        m=fit.m,
        h_implied_mm=fit.h_implied_mm,
        camera_height_mm=camera_height_mm,
        rms_cells=fit.rms_cells,
        max_resid_cells=fit.max_resid_cells,
        n_samples=fit.n,
        n_black=verdict.n_black,
        n_white=verdict.n_white,
        frames=len(frames),
        geometry_generation=geometry_generation,
        fitted_at=fitted_at,
    )
    if not dry_run:
        save_parallax(out_path, calib)
    return verdict, calib


def render_pattern(pattern=PATTERN_17) -> str:
    """ASCII board, far side (row 0) at the top as the camera sees it; X = put a stone here."""
    rows = []
    for r in range(19):
        rows.append(f"{r:2d} " + " ".join("X" if (r, c) in pattern else "." for c in range(19)))
    return "   " + " ".join(str(c % 10) for c in range(19)) + "\n" + "\n".join(rows)


def camera_settings(profile) -> dict:
    """CameraManager exposure / white-balance arguments that reproduce the service's capture for this
    geometry generation (server.py: a persisted hardware_auto_then_lock profile -> lock_exposure with
    exposure=None; AWB stays unlocked). Calibrating under different exposure would bake an
    exposure-dependent detector bias into k and the nadir (codex review 2026-09-22)."""
    from katrain.web.core.hardware_vision_state import CAMERA_STRATEGY_HARDWARE_AUTO_THEN_LOCK

    return {
        "lock_exposure": profile.strategy == CAMERA_STRATEGY_HARDWARE_AUTO_THEN_LOCK,
        "exposure": None,
        "lock_awb": False,
    }


def _warp(frame, lock):
    """The service's warp (worker_inprocess): lock homography, resolution-adjusted, 1-cell margin."""
    M = adjust_M_for_resolution(lock.M, (lock.source_width, lock.source_height), (frame.shape[1], frame.shape[0]))
    return warp_with_margin(frame, M, int(lock.out_size), margin_cells=DEFAULT_MARGIN_CELLS)


def _read_frames(camera, n_frames: int, timeout_s: float):
    deadline = time.monotonic() + timeout_s
    while n_frames > 0:
        if time.monotonic() > deadline:
            raise RuntimeError(f"camera stopped delivering frames ({n_frames} still wanted after {timeout_s:.0f}s)")
        frame = camera.read_frame()
        if frame is None:
            time.sleep(0.02)
            continue
        n_frames -= 1
        yield frame


def empty_board_offset(camera, lock, n_frames: int = EMPTY_FRAMES, timeout_s: float = 30.0) -> GridOffset:
    """Printed-grid check on the empty board: per-pixel median of ``n_frames`` warped frames (no enhancement)."""
    warped = [_warp(frame, lock) for frame in _read_frames(camera, n_frames, timeout_s)]
    return grid_offset(np.median(np.stack(warped), axis=0).astype(np.uint8), int(lock.out_size))


def capture_frames(camera, lock, detector, extractor, enhance: str, n_frames: int, timeout_s: float = 120.0):
    """Warp + enhance + detect exactly like worker_inprocess, keeping RAW grid positions of stone detections."""
    from katrain.vision.enhance import enhance_for_inference

    frames = []
    for frame in _read_frames(camera, n_frames, timeout_s):
        warped = enhance_for_inference(_warp(frame, lock), enhance)
        h, w = warped.shape[:2]
        pts = extractor.parallax_points(detector.detect(warped), img_w=w, img_h=h)
        frames.append([(fy_raw, fx_raw, cls) for fy_raw, fx_raw, _fy, _fx, cls, _conf in pts])
    return frames


def _fmt(off: GridOffset) -> str:
    return f"dx {off.dx_cells:+.3f} dy {off.dy_cells:+.3f} cells (|{off.shift_cells:.3f}|), lines {off.lines_x}/{off.lines_y}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Calibrate the stone-parallax correction (run on the board, service stopped)"
    )
    ap.add_argument("--hardware-vision-dir", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--backend", default="rknn", choices=["ultralytics", "onnx", "rknn"])
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--resolution", default="1920x1080")
    ap.add_argument("--enhance", default="clahe", choices=["clahe", "off"])
    ap.add_argument("--conf", type=float, default=0.30, help="detector threshold; the board service keeps at 0.30")
    ap.add_argument("--frames", type=int, default=30)
    ap.add_argument("--stone-set", required=True, help='which stones were used, e.g. "ver9-22x7"')
    ap.add_argument("--camera-height-mm", type=float, default=DEFAULT_CAMERA_HEIGHT_MM)
    ap.add_argument("--dry-run", action="store_true", help="report only; never write the calibration file")
    args = ap.parse_args(argv)

    from katrain.vision.board_state import BoardStateExtractor
    from katrain.vision.camera import CameraManager
    from katrain.vision.config import BoardConfig
    from katrain.vision.stone_detector import StoneDetector
    from katrain.web.core.hardware_vision_state import HardwareVisionStateStore

    width, height = (int(v) for v in args.resolution.lower().split("x"))
    try:
        state = HardwareVisionStateStore(Path(args.hardware_vision_dir).expanduser()).load_current(
            args.camera, width, height
        )
    except (OSError, ValueError) as exc:
        print(f"cannot read the current geometry: {exc}")
        return 2
    if state is None:
        print("no current geometry for this camera/resolution: lock the board geometry first")
        return 2

    detector = StoneDetector(args.model, backend=args.backend, confidence_threshold=args.conf)
    extractor = BoardStateExtractor(BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS))  # no parallax: RAW positions
    settings = camera_settings(state.profile)
    camera = CameraManager(device_id=args.camera, width=width, height=height, **settings)
    if not camera.open():
        print(f"cannot open camera {args.camera} (is the katrain service still running?)")
        return 2
    if settings["lock_exposure"] and camera.controls_effective is not True:
        camera.close()
        print("camera exposure could not be locked the way the service locks it: refusing to calibrate")
        return 2
    try:
        input("The board must be EMPTY and untouched since the geometry was locked. Press Enter. ")
        start = empty_board_offset(camera, state.geometry)
        print(f"printed grid vs saved geometry, start: {_fmt(start)}")
        reasons = grid_check_reasons(start, "start")
        if reasons:
            print("CALIBRATION REFUSED, nothing written:")
            for reason in reasons:
                print(f"  - {reason}")
            return 1
        print(render_pattern())
        input(f"Place one stone on each X ({len(PATTERN_17)} points, alternate black/white), then press Enter. ")
        frames = capture_frames(camera, state.geometry, detector, extractor, args.enhance, args.frames)
        input("Remove ALL stones without moving the board, then press Enter. ")
        end = empty_board_offset(camera, state.geometry)
        print(f"printed grid vs saved geometry, end:   {_fmt(end)}")
    finally:
        camera.close()

    out_path = parallax_path(args.hardware_vision_dir)
    verdict, calib = decide_and_write(
        frames,
        grid_offsets={"start": start, "end": end},
        out_path=out_path,
        stone_set=args.stone_set,
        camera_height_mm=args.camera_height_mm,
        geometry_generation=state.generation,
        fitted_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        dry_run=args.dry_run,
    )
    if not verdict.ok:
        print("CALIBRATION FAILED, nothing written:")
        for reason in verdict.reasons:
            print(f"  - {reason}")
        return 1
    fit = verdict.fit
    print(f"k={fit.k:.6f} m={fit.m:.6f} nadir=({fit.nadir_fx:.3f}, {fit.nadir_fy:.3f})")
    # BoardConfig's mm mapping scales the warp grid by 0.99853, which reads h ~0.5 mm low (harmless to the fix)
    print(f"h_implied={fit.h_implied_mm:.2f} mm (~3.0 = detector reports the mid-plane, ~6.5 = the top face)")
    print(
        f"rms={fit.rms_cells:.3f} cells (~{fit.rms_cells * 22.85:.1f} mm), worst {PATTERN_17[fit.worst_index]} "
        f"{fit.max_resid_cells:.3f} cells; stones {verdict.n_black} black / {verdict.n_white} white"
    )
    print(f"dry run: not written to {out_path}" if args.dry_run else f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `"$PY" -m pytest tests/test_vision/test_calibrate_parallax.py -q -p no:cacheprovider`
Expected: 全部 passed

- [ ] **Step 5: CLI 冒烟(不需要摄像头)**

Run: `"$PY" -m katrain.vision.tools.calibrate_parallax --help`
Expected: 打印用法,退出码 0

- [ ] **Step 6: 变异检查(只在一次性 worktree 里做,见 Global Constraints)**

在 `git worktree add` 出来的临时目录里,把 `decide_and_write` 里的 `for when, off in grid_offsets.items(): ...`
两行删掉,跑 `test_stale_geometry_is_refused_although_the_fit_itself_is_perfect` → 必须变红;再把
`grid_check_reasons` 的 `> MAX_GRID_SHIFT_CELLS` 改成 `> 0.5` → `test_a_quarter_cell_stale_geometry_is_measured_and_refused`
和门限两侧那条必须变红。记录结果写进提交说明,删掉临时 worktree。

- [ ] **Step 7: 提交**

```bash
git add -- katrain/vision/tools/calibrate_parallax.py tests/test_vision/test_calibrate_parallax.py
git commit -m "feat(vision): on-board parallax calibration tool that refuses to write a bad fit

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**验收:** prd P1-2 实现 1–3、验收 4(h 超窗口不写入,另加漏摆 / 多摆 / 摆歪 / 无帧 / 几何过期);design D4、D5、§2.5。
注:h≈12 mm 这种大偏差在配对这一步就会失败(远端的子落到相邻交点),所以 h 窗口本身用 h=1 mm 的用例来测。
注:`BoardConfig` 的 mm 映射把第 i 线放在 0.0038 + 0.99853·i(不是 warp 的 i),这对修正无害(拟合自洽),
但会让 `h_implied` 读成 ≈3.0 mm 而不是 3.5 —— 明天读数时知道这件事。网格检查用的是 warp 自己的几何,不受影响。

---

### Task 9: 全量验证与文档

**Files:**
- Create: `superpowers/tracks/vision-stone-parallax/handoff.md`
- Modify: `superpowers/tracks/vision-stone-parallax/README.md`(文件表加 `design.md` / `plan.md` / `handoff.md`;「接进流水线的位置」改成指向 `_positions`)

**约束:** 新增失败只能靠**名字集合**的基线 diff 判定,不许按条数比。本分支没有前端改动 ⇒ 不需要 `npm run build`。

- [ ] **Step 1: Black**

Run: `"$PY" -m black -l 120 --check katrain/vision/coordinates.py katrain/vision/parallax.py katrain/vision/parallax_store.py katrain/vision/board_state.py katrain/vision/config_service.py katrain/vision/worker_inprocess.py katrain/web/server.py katrain/vision/tools/calibrate_parallax.py tests/test_vision/board_state_corpus.py tests/test_vision/parallax_synth.py tests/test_vision/test_board_state_golden.py tests/test_vision/test_parallax_apply.py tests/test_vision/test_board_state_parallax.py tests/test_vision/test_parallax_fit.py tests/test_vision/test_parallax_store.py tests/test_vision/test_parallax_wiring.py tests/test_vision/test_calibrate_parallax.py`
Expected: `All done!`。若报 would reformat:去掉 `--check` 跑一次,`git diff` 确认只是格式,单独提交 `style: black`。

- [ ] **Step 2: 基线全量(一次性 worktree,develop `34e9c7b6`)**

```bash
OUT=$(mktemp -d); BASE="$OUT/base-wt"
git worktree add --detach "$BASE" 34e9c7b6
(cd "$BASE" && CI=true "$PY" -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors -rfE 2>&1) > "$OUT/base.log"
grep -E '^(FAILED|ERROR) ' "$OUT/base.log" | sed -E 's/ - .*//' | sort -u > "$OUT/base.txt"
git worktree remove --force "$BASE"
echo "$OUT"; wc -l < "$OUT/base.txt"
```

- [ ] **Step 3: 本分支全量**

```bash
CI=true "$PY" -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors -rfE > "$OUT/head.log" 2>&1
grep -E '^(FAILED|ERROR) ' "$OUT/head.log" | sed -E 's/ - .*//' | sort -u > "$OUT/head.txt"
comm -13 "$OUT/base.txt" "$OUT/head.txt"
git status --short
```
Expected: `comm -13` 输出为空(没有新增失败);`git status --short` 只有预期的未跟踪文件。若 `katrain/config.json`
被测试改写(已知的测试副作用),`git diff katrain/config.json` 核对后用 `git checkout -- katrain/config.json` 还原。

- [ ] **Step 4: 写 `handoff.md`**

内容(全文,标题与小节照写):

```markdown
# vision-stone-parallax 上板交接

## 已完成(代码)
- 修正:`coordinates.apply_parallax` + `BoardStateExtractor._positions`(只在 geometry-lock extractor 上)
- 标定文件:`<hardware-vision-dir>/parallax/go-19x19.json`(`parallax_store.py`),server 启动读取并打一行日志
- 标定工具:`python -m katrain.vision.tools.calibrate_parallax`
- 诊断:board delta 行每格带 `pl<位移>` 与 `*`(被视差救回)

## 上板步骤(Fan 在场、RK3562 连上后)
1. 部署(照 memory `reference_rk3562_katrain_deploy_recipe`):先备份;源码 rsync 根层不加 `--delete`;本分支无前端改动,不需要重建 kiosk 包。
2. **两套固定摆位,恰好 20 手,顺序与颜色写死**(修正前后完全相同;棋盘坐标,19 路离镜头最远;
   15–18 路 × C、G、K、O、S 五列):

   | 手 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 |
   |---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
   | 点 | C18 | G18 | K18 | O18 | S18 | C17 | G17 | K17 | O17 | S17 | C16 | G16 | K16 | O16 | S16 | C15 | G15 | K15 | O15 | S15 |
   | 色 | 黑 | 白 | 黑 | 白 | 黑 | 白 | 黑 | 白 | 黑 | 白 | 黑 | 白 | 黑 | 白 | 黑 | 白 | 黑 | 白 | 黑 | 白 |

   - **A 复现故障**:每颗子**中心压在该交叉点往远离镜头方向 8 mm 处**(用尺量;8 mm ≈ 0.36 格,超过修正前远端
     剩余容差约 6.5–7 mm、小于修正后的 11 mm)。19 路不放:最外一排往外偏的容差本来就不恢复(prd §5 第 5 条)。
   - **B 不回归**:同样 20 手,正常摆正。
   - 每一轮在 kiosk 人人对弈(实体棋盘)新开一局 19 路;轮与轮之间清空棋盘。
   - **每手最多观察 15 秒**,按下面四类之一记一次,然后直接下下一手(**不悔棋**:错点只会往远离镜头方向错到 19 路,
     19 路不在清单里,不会和后面的手撞上):
     - **正确**:board delta 出现这一手的交叉点,kiosk 上子落在该点;
     - **错点**:落到了别的交叉点;
     - **卡片**:弹出确认卡片 —— 记一次,按「确认」让它落下;若卡片上的点不对,同时记一次错点;
     - **未确认**:15 秒内既没落下也没弹卡片 —— 记一次,子留在盘上。
   - 每一轮开始前、结束后各记一次时间,作为这一轮的日志窗口 `--since/--until`。
3. **修正前对照**(还没有标定文件):**先在 kiosk 上空盘重新锁定一次几何**(修正前修正后两组对照都要从新鲜的锁开始,
   过期的锁会把修正前的出错数撑高、显得修正效果更大)。确认启动日志有 `vision parallax off: not calibrated`。
   A、B 各跑一遍,每轮记录:四类计数;`journalctl -u smartbox-katrain --since <开始> --until <结束> | grep -c 'peak conf 0.00 <'`(unbacked 计数)。
4. **标定**(工具在空盘上先后两次核对印刷网格与保存的几何,任一次偏 > 0.10 格就拒绝、什么都不写 ——
   拟合本身看不见过期的几何,见 design §2.5):
   - 停服务前:棋盘清空、kiosk 显示几何已就绪。自上次锁定以来碰过棋盘(**包括清空修正前那几轮**),先在 kiosk 上
     空盘重新锁定一次几何。然后**不碰棋盘**,`sudo systemctl stop smartbox-katrain`。
   - 跑工具(命令见工具 docstring):空盘回车 → 按图摆 17 子回车 → 收掉全部子(不挪棋盘)回车。
   - 抄下两次打印的网格偏移(start / end)与 k / nadir / h_implied / rms / 最差点 → `sudo systemctl start smartbox-katrain`。
   - 失败按提示处理(重摆 / 重新锁定几何),**不要改阈值,没有绕过开关**。刚锁好的几何仍稳定偏 > 0.10 格(LED 与
     印刷线本身对不齐)⇒ 记下数字,这是一条要交给 Fan 判断的发现,不放宽闸。
   - `h_implied` 读数比真值低约 0.5 mm(`BoardConfig` 的 mm 映射比 warp 小 0.99853 倍,对修正无害):
     ≈3.0 mm 对应「检测器报的是子的中面」,≈6.5 mm 对应顶面。
5. 确认启动日志 `vision parallax on: ... current_generation=...`。
6. **修正后对照**:同一光照,A、B 各再跑一遍,记录同样两项;board delta 行里数 `*` 的条数。

## 判定(事先定死,不看结果再调)
- 一轮的「出错」= 错点 + 卡片 + 未确认 三类之和(同一手记了卡片又记错点,只算一次)。
- **基线必须复现故障**:修正前 A 至少 **5/20** 手出错。达不到 ⇒ 这次对照**证据不足**,
  不能标完成;回头检查摆位(是不是没往外偏够 8 mm)再做。
- **修正后通过**:A **20/20 正确**(0 错点、0 未确认),且 A 的 unbacked 计数 ≤ 修正前的一半
  (修正前为 0 时本条不适用,由上一条兜住)。
- **不回归**:B 修正前、修正后都是 **20/20 正确**。
- 任何一条不满足:不标完成,把数据填表后交 Fan 判断。

## 对照数据(上板后填)
| | 修正前 A | 修正后 A | 修正前 B | 修正后 B |
|---|---|---|---|---|
| 日志窗口(起–止) | | | | |
| 正确 / 20 | | | | |
| 错点 | | | | |
| 卡片 | | | | |
| 未确认 | | | | |
| unbacked 计数(journal) | | | | |
| board delta 中 `*` 条数 | — | | — | |

## 标定结果(上板后填,同时抄进 geometry.md 末尾)
k / nadir / m / h_implied / rms / 最差点 / 网格偏移 start、end / 棋子 / 几何代次 / 时间
```

- [ ] **Step 5: 更新 README 并提交**

```bash
git add -- superpowers/tracks/vision-stone-parallax/handoff.md superpowers/tracks/vision-stone-parallax/README.md
git commit -m "docs(vision-parallax): handoff for the on-board run; README points at the implementation

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**验收:** Black 干净;全量测试相对 develop 基线**没有新增失败(按名字)**;handoff 写清明天的上板步骤。

---

### Task 10: 上板验收(明天,Fan 在场;不在本次夜间执行范围)

前置:Task 9 完成、已合入 develop 并推送、smartbox-software 子模块已更新;RK3562 已连上,Fan 在场。

- [ ] 按 `handoff.md`「上板步骤」1–6 执行;按「判定」一节决定能否标完成(门槛事先定死,不看结果再调)。
- [ ] 把标定结果(k、nadir、rms、h_implied、哪副棋子、哪次标定、几何代次)写进 `geometry.md` 末尾新小节「现场标定」。
- [ ] 填 `handoff.md` 对照表。
- [ ] `prd.md`:每条需求标完成状态(P1-1 验收 5、P1-2 验收 4 的上板部分、P2 上板部分);§5 已排除的风险划掉
      (例如 §5 第 4 条:若 `h_implied` 读数落在 ≈3.0 附近就划掉 —— 工具读数比真值低约 0.5 mm,见 Task 8 注)。

**验收:** prd P1-1 验收 5、P1-2 验收 4(上板)、P2(上板)。

---

## 收尾(控制者执行,Task 9 之后、代码审核通过之后)

Fan 2026-09-22 指示的顺序:

1. **追上 develop,commit & push**:`git fetch origin develop` → `git merge origin/develop`(有冲突先读
   memory `reference_clean_merge_is_not_correct_merge`)→ 视觉测试目录重跑 → `git push -u origin feature/vision-stone-parallax`。
2. **合入 develop 并 push**:在 develop 上快进或合并本分支 → `git push origin develop`;推送前再核一次
   `git merge-base --is-ancestor` 与视觉测试。
3. **smartbox-software 的 `vendor/katrain` 更新到 katrain develop 最新提交**:只 `git add -- vendor/katrain`,
   不碰 `vendor/hermes-agent`;commit & push 到 smartbox-software 的 main。
4. 不部署板子(等明天)。

## 验收对照(prd.md §3 → 本计划)

| prd 条目 | 本计划 |
|---|---|
| P1-1 期望 1(`apply_parallax` 纯函数;2026-09-22:非幂等) | Task 2(含非幂等测试)、Task 3 变异 B |
| P1-1 期望 2(只在两处调用,`physical_to_grid` 不动) | Task 3(`_positions` 唯一调用点);Global 第 4 条 |
| P1-1 期望 3(未标定恒等、逐位相同) | Task 1 金样 + Task 3 参数化(None / k=1)+ 变异 C |
| P1-1 验收 1 | Task 2 `test_uncalibrated_is_identity` / `test_k_one_returns_inputs_bit_for_bit`;Task 3 金样三种构造 |
| P1-1 验收 2(361 点;2026-09-22 加区分版:第 1–5 排外偏 0.35 格) | Task 3 `TestSanity361` + `TestFarRowsDisplacedOutward`(两种分配模式;第 0 排代价单独钉住) |
| P1-1 验收 3(边距 DROP 不回归;either 规则) | Task 3 `TestMarginDropSurvivesCorrection` + 变异 A |
| P1-1 验收 4(nadir 不动点) | Task 2 `test_nadir_is_a_fixed_point` |
| P1-1 验收 5(上板远端 20 手) | Task 10 |
| P1-2 实现 1(标定工具在 `katrain/vision/tools/`) | Task 8 |
| P1-2 实现 2(落盘;2026-09-22:独立文件) | Task 5、Task 6 |
| P1-2 实现 3(`h_implied`) | Task 4(`FitResult.h_implied_mm`)、Task 8(打印与闸) |
| P1-2 验收 1(无噪 1e-6 / rms 1e-9) | Task 4 `test_noiseless_fit_recovers_the_truth` |
| P1-2 验收 2(2026-09-22 改写:h 与修正残差) | Task 4 `test_noisy_fit_is_accurate_where_it_matters` + `test_the_accuracy_gate_rejects_no_correction` + 变异 |
| P1-2 验收 3(共线 / 少于 3 点报错) | Task 4 四条 `raise` 测试 |
| P1-2 验收 4(h 2–8 之外失败,不静默写入;上板记报告) | Task 5 `save_parallax` 先校验;Task 8 失败不写文件;Task 10 上板记录 |
| P2 期望 / 验收(2026-09-22 收窄) | Task 3 `parallax_points`、Task 7 日志与测试 |
| prd §5 第 7 条(标定时几何过期;codex 第 2 轮 [high]) | Task 8 网格核对测试 + codex 反例 + Step 6 变异;Task 9 handoff 第 4 步 |
| design D1–D8 | D1 Task 5;D2/D3 Task 6;D4/D5 Task 8;D6 Task 3+7;D7 Task 3;D8 全局(不做多记录) |
