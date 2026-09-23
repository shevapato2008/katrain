# 去影子（board-state shadow step）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 侧光下「棋子 + 它的影子」被再框一次的影子框，在去重复框之后、分置信档之前被单独去掉，从源头消掉 H5 自我维持的假黑子和 D7 低置信疑似落子卡片；两颗贴在一起的真子（第一版的失败）一颗都不许丢。

**Architecture:** 撤回第一版（`dedup_detections` 里的重叠条款），`stone_detector.py` 回到 `98b1a67a` 逐字不变。新增 `BoardStateExtractor.drop_shadow_boxes`：一个棋子框离最近交叉点 ≥ 0.35 格（视差校正后），且与一个离交叉点更近、分数不低于它、大小相近的棋子框交叠 ≥ 0.27（除以较小框），就是影子框。`worker_inprocess.py` 在 `self._detector.detect(warped)` 之后立刻调用它。

**Tech Stack:** Python 3.11、numpy、pytest（`uv run`）。

**Spec:** `superpowers/tracks/vision-optimizations/shadow-dedup/design.md`（第二版；§0 讲第一版为什么撤回，§2 是全部实测数，§3 是规则）。第一版计划 `docs/superpowers/plans/2026-09-23-vision-shadow-dedup.md` 与它的 FAIL 记录 `shadow-dedup/validation.md` 保留作历史。

## Global Constraints

- 常量名字和值固定，定义在 `katrain/vision/board_state.py` 模块级：`SHADOW_OVERLAP_MIN = 0.27`、`SHADOW_MAX_SIDE_RATIO = 2.0`、`SHADOW_MIN_OFFSET = 0.35`。
- `katrain/vision/stone_detector.py` 与 `tests/test_vision/test_stone_detector.py` 必须与 `98b1a67a` **逐字相同**（`git diff 98b1a67a -- <两个文件>` 为空）。五子棋 session 钉着 `dedup_detections` 的签名和行为。
- `drop_shadow_boxes` **只删不加、不改顺序**：LED 框、没有面积的框、框心非有限数的框原样通过；永远不删一对里分数高的那个；结果与输入顺序无关。
- 调用点只有一个：`worker_inprocess.py` 里 `_infer_ms = ...` 那行之后、分置信档（`detections = [d for d in all_detections if ...]`）之前。`worker.py`（子进程版）板上不用，**不改**。
- Python 用 Black，120 列：`uv run black -l 120 <file>`。测试命令一律带 `--color=no -p no:cacheprovider`。
- 变异检查要把常量改成等长的值再还原；同一秒内还原会让 Python 继续用变异版的 `.pyc`。所以变异检查开始前删掉 `__pycache__`，全程带 `PYTHONDONTWRITEBYTECODE=1`。
- 子代理不 ssh 任何机器，不碰 RK3562。
- 共用工作树：Task 1 独占工作树，自己提交（只 `git add -- <列出的路径>`）。Task 2 与 Task 3 并行，**都不提交、不 `git checkout`/`stash`/`reset`/`add`**，由主会话按路径提交。Task 2 与 Task 3 都不许改 `katrain/` 下的任何文件（对方正在用它）。

## Review Focus

1. **两颗贴着的真子**（第一版的失败）：`kifu_24171` frame 098 的两个白框互压 0.38，都在点上 —— 两个都留。Task 1 `test_two_touching_real_stones_are_both_kept`。
2. **五子棋连珠**：五颗同色子一颗挨一颗（相距 0.95 格、框互压 0.30），一颗都不删；只删行尾的影子。Task 1 `test_a_row_of_five_touching_same_colour_stones_is_kept`、`test_the_shadow_at_the_end_of_a_row_is_dropped_and_the_row_kept`。
3. **真子被推向自己的影子**：子偏 0.4 格、影子落在下一个点上 —— 几何会把真子当影子，置信度条件保住它。Task 1 `test_a_stone_pushed_off_its_point_toward_its_shadow_is_kept`。
4. **三个门槛都钉在精确值上**（0.35、0.27、2.0），`>=`/`<=` 写成 `>`/`<` 会红。Task 1 三条 `*_boundary`。
5. **生产接线**：worker 真的在分档之前调用这一步（替身只替换检测器，循环是真的）。Task 1 `test_the_worker_drops_a_shadow_before_the_board_sees_it`。
6. **H5 已经成形的假子能被放掉**（不只是「不产生」）：第 2 帧从带着 H5 假子的盘面开始。Task 2 `test_the_shadow_step_breaks_the_h5_chain`。
7. **D7 那条路**：低于落子门槛的影子框不再是 `cell_top` 的候选。Task 2 `test_sub_threshold_shadow_no_longer_reaches_an_empty_point`。
8. **不伤真子由标注集证明**（209 张、这一步删 0 个框），**拦得住影子由 09-23 那局证明**（12 帧删 36 个、全是影子）。Task 3。

---

## 并行关系

- **Task 1**（撤回第一版 + 实现 + 单元测试）先做，独占工作树，自己提交。
- Task 1 审过之后：**Task 2**（端到端回归）与 **Task 3**（标注集验证闸）并行，互不改对方的文件，都不提交。
- **Task 4**（文档）在 Task 3 为 `PASS` 且 Task 2 通过后做。Task 3 不是 `PASS` 时停在 Task 4 之前，把数报给 Fan。

---

### Task 1: 撤回第一版，实现去影子一步并接进 worker

**Files:**
- Revert: `katrain/vision/stone_detector.py`、`tests/test_vision/test_stone_detector.py`（回到 `98b1a67a`），删除 `tests/test_vision/test_shadow_phantom.py`（Task 2 重写）
- Modify: `katrain/vision/board_state.py`（常量、`_overlap_of_smaller`、`BoardStateExtractor.drop_shadow_boxes`）
- Modify: `katrain/vision/worker_inprocess.py`（一处调用，三行）
- Create: `tests/test_vision/test_board_state_shadow.py`

**Interfaces:**
- Consumes: `BoardStateExtractor._positions(det, img_w, img_h) -> (fx_raw, fy_raw, fx, fy, on_board)`（视差校正只在这里做一次）；`STONE_CLASS_IDS`；测试用 `tests.test_vision.board_state_corpus.grid_to_px(cfg, col, row)` 与 `tests.test_vision.test_sustain_threshold._run(config, script)`（真 worker 循环，只替换检测器）。
- Produces（Task 2/3 用）: `katrain.vision.board_state.SHADOW_MIN_OFFSET` 等三个常量、`_overlap_of_smaller(a, b) -> float`、`BoardStateExtractor.drop_shadow_boxes(detections, img_w, img_h) -> list[Detection]`。

- [ ] **Step 1: 撤回第一版**

```bash
git revert --no-commit 90e439db acb174cd e110b141
git diff --cached --stat
git diff 98b1a67a -- katrain/vision/stone_detector.py tests/test_vision/test_stone_detector.py   # 必须为空
test ! -e tests/test_vision/test_shadow_phantom.py && echo "phantom test removed"
git commit -m "revert(vision): take the shadow clause back out of dedup_detections

The labelled-set gate failed: two touching real stones overlap as much as a stone and its
shadow. Shadow handling moves to a separate board-state step after dedup.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
CI=true uv run pytest tests/test_vision -q --color=no -p no:cacheprovider 2>&1 | tail -1
```

Expected: revert 无冲突；`--stat` 列出三个文件；`git diff 98b1a67a` 空；打印 `phantom test removed`；最后一行 **840 passed**。

- [ ] **Step 2: 写失败的测试**

创建 `tests/test_vision/test_board_state_shadow.py`：

```python
"""drop_shadow_boxes: a stone's shadow boxed a second time (side light) is removed after dedup; real stones,
however tightly packed, are not. Geometry from the RK3562 daylight game (2026-09-23) and the labelled set
(kifu_24171); see superpowers/tracks/vision-optimizations/shadow-dedup/design.md."""

import random

from katrain.vision.board_state import (
    BLACK,
    SHADOW_MIN_OFFSET,
    WHITE,
    BoardStateExtractor,
    _overlap_of_smaller,
)
from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig
from katrain.vision.parallax import ParallaxParams
from katrain.vision.stone_detector import Detection
from tests.test_vision.board_state_corpus import IMG, grid_to_px

CFG = BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS)
DAYLIGHT_PARALLAX = ParallaxParams(nadir_fx=19.612, nadir_fy=9.0, k=0.989689)  # the 09-23 board's lock
CELL = 949 / 18  # px per cell in the 1056 px warp


def _box(x, y, cls, conf, w, h=None):
    h = w if h is None else h
    return Detection(
        x_center=x, y_center=y, class_id=cls, confidence=conf, bbox=(x - w / 2, y - h / 2, x + w / 2, y + h / 2)
    )


def _at(row, col, cls, conf, cells=1.1):
    x, y = grid_to_px(CFG, col, row)
    return _box(x, y, cls, conf, cells * CELL)


def _drop(dets, parallax=None):
    return BoardStateExtractor(CFG, parallax=parallax).drop_shadow_boxes(dets, IMG, IMG)


def _stubbed(positions):
    """An extractor whose grid positions are given exactly: {id(detection): (row, col)}."""
    ex = BoardStateExtractor(CFG)
    ex._positions = lambda d, w, h: (positions[id(d)][1], positions[id(d)][0]) * 2 + (True,)
    return ex


# G5 black stone in frame warped_09 and its shadow box at the two positions the live log recorded
G5 = Detection(x_center=360.33, y_center=792.29, class_id=0, confidence=0.50, bbox=(332.6, 761.8, 388.0, 822.8))
SHADOW_POSITIONS = ((388.82, 775.63), (387.02, 776.69))  # corrected column 6.501 / 6.467: 0.62 / 0.58 off a point


def _g5_shadow(x, y, conf=0.45):
    return _box(x, y, 0, conf, 49.9, 51.1)


def test_a_stones_shadow_box_is_dropped_and_the_stone_kept():
    for x, y in SHADOW_POSITIONS:
        assert _drop([G5, _g5_shadow(x, y)], DAYLIGHT_PARALLAX) == [G5]


def test_a_box_that_outscores_its_partner_is_never_dropped():
    """A shadow that outscores its stone (never seen live: 0 of 36) is left alone, exactly as before this step
    existed -- the step never deletes the higher-scoring box of a pair."""
    stone = Detection(G5.x_center, G5.y_center, 0, 0.45, G5.bbox)
    for x, y in SHADOW_POSITIONS:
        shadow = _g5_shadow(x, y, conf=0.50)
        assert _drop([stone, shadow], DAYLIGHT_PARALLAX) == [stone, shadow]


def test_two_touching_real_stones_are_both_kept():
    """kifu_24171 frame 098 (labelled set), deployed model's own boxes: two white stones pushed together.
    Their boxes overlap by 0.38 -- as much as a shadow -- but both sit on a point. The first version of this
    fix merged one of them away (gate FAIL, 45 frames)."""
    left = Detection(
        315.4741413116455,
        895.2108535766602,
        1,
        0.3651,
        (287.62708053588864, 866.7678405761718, 343.32120208740236, 923.6538665771484),
    )
    right = Detection(
        354.6771755218506,
        897.7171234130859,
        1,
        0.4284,
        (322.0275512695312, 867.1066223144531, 387.3267997741699, 928.3276245117187),
    )
    assert _overlap_of_smaller(left.bbox, right.bbox) >= 0.27  # precondition: overlap alone would drop one
    assert _drop([left, right]) == [left, right]


def test_a_row_of_five_touching_same_colour_stones_is_kept():
    """Five-in-a-row stress case: every stone touches the next (0.95 cells apart) and the boxes are wide
    enough to overlap their neighbours by 0.30. The row drifts off the grid by 0.05 cells per stone."""
    row = [_at(9, 3 + 0.95 * k, WHITE - 1, 0.7, cells=1.35) for k in range(5)]
    assert all(_overlap_of_smaller(a.bbox, b.bbox) >= 0.27 for a, b in zip(row, row[1:]))  # precondition
    assert _drop(row) == row


def test_the_shadow_at_the_end_of_a_row_is_dropped_and_the_row_kept():
    row = [_at(9, 3 + 0.95 * k, WHITE - 1, 0.7, cells=1.35) for k in range(5)]
    shadow = _at(9, 3 + 0.95 * 4 + 0.6, BLACK - 1, 0.45, cells=1.0)
    assert _drop([*row, shadow]) == row


def test_a_stone_pushed_off_its_point_toward_its_shadow_is_kept():
    """A stone 0.4 cells off its point, its shadow box 0.6 further out -- landing on the next point. Geometry
    alone would call the STONE the shadow (it is the one between points); it scored higher, so it stays."""
    stone = _at(9, 5.4, BLACK - 1, 0.7, cells=1.1)
    shadow = _at(9, 6.0, BLACK - 1, 0.45, cells=1.0)
    assert _overlap_of_smaller(stone.bbox, shadow.bbox) >= 0.27  # precondition: the pair qualifies on overlap
    assert _drop([stone, shadow]) == [stone, shadow]


def test_a_box_is_only_a_shadow_of_a_box_nearer_a_point():
    """Two overlapping boxes both between points: the one nearer a point is not the other one's shadow, even
    when it scored lower."""
    nearer = _at(9, 5.38, BLACK - 1, 0.40, cells=1.1)
    farther = _at(9, 5.55, BLACK - 1, 0.60, cells=1.1)
    assert _overlap_of_smaller(nearer.bbox, farther.bbox) >= 0.27  # precondition
    assert _drop([nearer, farther]) == [nearer, farther]


def test_overlap_threshold_boundary():
    # Two 50 px squares dx apart: overlap = (50 - dx) / 50; dx = 36.5 gives exactly the double 0.27.
    near, far_at, far_below = _box(100, 100, 0, 0.9, 50), _box(136.5, 100, 0, 0.8, 50), _box(137, 100, 0, 0.8, 50)
    ex = _stubbed({id(near): (0.0, 0.0), id(far_at): (0.0, 0.5), id(far_below): (0.0, 0.5)})
    assert ex.drop_shadow_boxes([near, far_at], IMG, IMG) == [near]
    assert ex.drop_shadow_boxes([near, far_below], IMG, IMG) == [near, far_below]


def test_offset_threshold_boundary():
    near, far = _box(100, 100, 0, 0.9, 50), _box(120, 100, 0, 0.8, 50)
    assert SHADOW_MIN_OFFSET == 0.35
    at = _stubbed({id(near): (0.0, 0.0), id(far): (0.0, 0.35)})  # exactly 0.35 (0.35 - round(0.35) == 0.35)
    below = _stubbed({id(near): (0.0, 0.0), id(far): (0.0, 0.34)})
    assert at.drop_shadow_boxes([near, far], IMG, IMG) == [near]
    assert below.drop_shadow_boxes([near, far], IMG, IMG) == [near, far]


def test_side_ratio_boundary():
    big_at, big_above, small = _box(100, 100, 0, 0.9, 100), _box(100, 100, 0, 0.9, 105), _box(150, 100, 0, 0.8, 50)
    ex = _stubbed({id(big_at): (0.0, 0.0), id(big_above): (0.0, 0.0), id(small): (0.0, 0.5)})
    assert ex.drop_shadow_boxes([big_at, small], IMG, IMG) == [big_at]  # side ratio exactly 2.0
    assert ex.drop_shadow_boxes([big_above, small], IMG, IMG) == [big_above, small]  # 2.1


def test_a_big_box_does_not_make_the_stones_under_it_shadows():
    """A hand read as one big box (3x a stone) sitting on a point, scoring higher than everything under it. A stone
    under it pushed 0.4 cells off its point is fully inside the hand box (overlap 1.0), nearer-a-point and
    confidence both point at the stone -- only the side-ratio guard keeps it."""
    hand = _at(9, 9, BLACK - 1, 0.9, cells=3.0)
    stones = [_at(9, 8.6, WHITE - 1, 0.6), _at(9, 10, BLACK - 1, 0.7), _at(10, 9, WHITE - 1, 0.8)]
    assert _overlap_of_smaller(stones[0].bbox, hand.bbox) == 1.0  # precondition
    assert _drop([hand, *stones]) == [hand, *stones]


def test_led_boxes_are_never_dropped():
    stone, lamp = _at(9, 9, BLACK - 1, 0.8), _at(9, 9.5, 2, 0.7)  # led_red, half a cell off, overlapping
    assert _drop([stone, lamp]) == [stone, lamp]


def test_boxes_without_area_or_finite_position_pass_through():
    stone = _at(9, 9, BLACK - 1, 0.8)
    x, y = grid_to_px(CFG, 9.5, 9)
    flat = Detection(x, y, 0, 0.7, (x - 25, y, x + 25, y))
    no_x = Detection(float("nan"), y, 0, 0.7, (x - 25, y - 25, x + 25, y + 25))
    no_y = Detection(x, float("nan"), 0, 0.7, (x - 25, y - 25, x + 25, y + 25))
    far = Detection(float("inf"), y, 0, 0.7, (x - 25, y - 25, x + 25, y + 25))
    dets = [stone, flat, no_x, no_y, far]
    assert _drop(dets) == dets


def test_the_result_does_not_depend_on_input_order():
    row = [_at(9, 3 + 0.95 * k, WHITE - 1, 0.7, cells=1.35) for k in range(5)]
    dets = [*row, _at(9, 3 + 0.95 * 4 + 0.6, BLACK - 1, 0.45, cells=1.0), G5, _g5_shadow(*SHADOW_POSITIONS[0])]
    want = {id(d) for d in _drop(dets, DAYLIGHT_PARALLAX)}
    rng = random.Random(7)
    for _ in range(20):
        shuffled = dets[:]
        rng.shuffle(shuffled)
        assert {id(d) for d in _drop(shuffled, DAYLIGHT_PARALLAX)} == want


def test_the_worker_drops_a_shadow_before_the_board_sees_it():
    """Production wiring: the in-process worker applies the step to what the detector returns. Without it,
    the shadow (0.45, above the 0.40 add threshold) becomes a black stone on the empty point beside the
    stone; the test harness replaces only the detector, so this runs the real loop."""
    from tests.test_vision.test_sustain_threshold import _run

    stone = _at(10, 10, BLACK - 1, 0.8, cells=1.05)
    shadow = _at(10, 10.6, BLACK - 1, 0.45, cells=1.0)
    plain = BoardStateExtractor(CFG).detections_to_board(
        [stone, shadow], img_w=IMG, img_h=IMG, occupancy_aware=True, add_threshold=0.40
    )
    assert plain[10][11] == BLACK  # precondition: without the step the shadow lands on (10, 11)
    board, _ = _run({"confidence_threshold": 0.40, "confidence_keep": 0.30}, [[stone, shadow]] * 6)
    assert int(board[10][10]) == BLACK and int(board[10][11]) == 0
```

- [ ] **Step 3: 跑测试，确认失败**

Run: `CI=true uv run pytest tests/test_vision/test_board_state_shadow.py -q --color=no -p no:cacheprovider`
Expected: 收集阶段报 `ImportError: cannot import name 'SHADOW_MIN_OFFSET' from 'katrain.vision.board_state'`（整个文件 1 error）。

- [ ] **Step 4: 实现**

`katrain/vision/board_state.py`：

(a) 在 `COLOR_FLIP_RELEASE_FRAMES = 15` 那一行之后插入（前面空一行）：

```python
# Shadow boxes (RK3562 daylight game, 2026-09-23): side light makes the model box a stone together with its
# shadow a second time, centred 0.56-0.75 cells off the stone. dedup_detections leaves it alone (it only merges
# boxes whose centres are within half a box side), and it then became a phantom on the neighbouring point
# (H5: 16 prompts in one game). drop_shadow_boxes removes a stone box that overlaps a box sitting closer to an
# intersection (by >= SHADOW_OVERLAP_MIN of the smaller box, similar size) AND sits between intersections
# itself. Overlap alone cannot tell a shadow from a touching neighbour: two real white stones pushed together
# overlapped by 0.38 in kifu_24171 -- but each sat on its own point (0.04-0.08 cells off). Measured, without
# parallax correction: real boxes on 209 labelled images sit <= 0.38 cells from their point at p99.9, and
# dropping a real stone starts between 0.25 and 0.30; every shadow box in the daylight game sat >= 0.45.
# See superpowers/tracks/vision-optimizations/shadow-dedup/design.md.
SHADOW_OVERLAP_MIN = 0.27
SHADOW_MAX_SIDE_RATIO = 2.0
SHADOW_MIN_OFFSET = 0.35
```

(b) 在 `def _nearest_empty_cell(` 之前插入（后面空两行）：

```python
def _overlap_of_smaller(a: tuple, b: tuple) -> float:
    """Intersection area of two (x1, y1, x2, y2) boxes over the smaller box's area; 0.0 when either has none."""
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    smaller = area_a if area_a < area_b else area_b
    if not smaller > 0:
        return 0.0
    w = min(a[2], b[2]) - max(a[0], b[0])
    if not w > 0:
        return 0.0
    h = min(a[3], b[3]) - max(a[1], b[1])
    if not h > 0:
        return 0.0
    return w * h / smaller
```

(c) 在 `BoardStateExtractor` 里、`def detections_to_board(` 之前插入（后面空一行）：

```python
    def drop_shadow_boxes(self, detections: list[Detection], img_w: int, img_h: int) -> list[Detection]:
        """Remove stone boxes that are a stone's shadow boxed a second time; every other detection passes
        through unchanged and in its original order (LED boxes, boxes without area and boxes whose centre is
        not finite are never touched).

        A stone box is dropped when it sits at least SHADOW_MIN_OFFSET cells from its nearest intersection
        (parallax-corrected) AND overlaps, by at least SHADOW_OVERLAP_MIN of the smaller box, another stone box
        that is similar in size (larger mean side <= SHADOW_MAX_SIDE_RATIO x smaller), sits closer to an
        intersection, and scored at least as high. The last condition keeps the step from ever deleting the
        higher-scoring box of a pair: when a real stone is itself pushed off its point toward its shadow, or a
        shadow outscores its stone (never seen: 0 of 36), both boxes stay, exactly as before this step existed.
        Decided over the whole input at once, so the result does not depend on input order.

        Cost: one position per stone box, then a scan for the few boxes that sit between points -- 0.2 ms on
        a Mac for a 117-box frame; 1.2 ms if every box sits between points (geometry off by half a cell)."""
        stones = [
            i
            for i, d in enumerate(detections)
            if d.class_id in STONE_CLASS_IDS
            and math.isfinite(d.x_center)
            and math.isfinite(d.y_center)
            and d.bbox[2] - d.bbox[0] > 0
            and d.bbox[3] - d.bbox[1] > 0
        ]
        offset: dict[int, float] = {}
        side: dict[int, float] = {}
        for i in stones:
            d = detections[i]
            _, _, fx, fy, _ = self._positions(d, img_w, img_h)
            offset[i] = math.hypot(fy - round(fy), fx - round(fx))
            side[i] = (d.bbox[2] - d.bbox[0] + d.bbox[3] - d.bbox[1]) / 2.0
        shadows = set()
        for i in stones:
            if offset[i] < SHADOW_MIN_OFFSET:
                continue
            box, conf = detections[i].bbox, detections[i].confidence
            for j in stones:
                if j == i or offset[j] >= offset[i] or detections[j].confidence < conf:
                    continue
                other = detections[j].bbox
                if other[0] >= box[2] or box[0] >= other[2] or other[1] >= box[3] or box[1] >= other[3]:
                    continue  # no intersection: skip the ratio and the division
                smaller, larger = (side[i], side[j]) if side[i] < side[j] else (side[j], side[i])
                if larger <= SHADOW_MAX_SIDE_RATIO * smaller and _overlap_of_smaller(box, other) >= SHADOW_OVERLAP_MIN:
                    shadows.add(i)
                    break
        return [d for i, d in enumerate(detections) if i not in shadows]
```

`katrain/vision/worker_inprocess.py`：把

```python
                    _infer_ms = (time.monotonic() - _t_inf) * 1000
```

替换为

```python
                    _infer_ms = (time.monotonic() - _t_inf) * 1000
                    # A stone's shadow boxed a second time (side light) is dropped before the keep/sustain split,
                    # so no consumer -- board assignment, the sustain tier, the ambiguous-move promoter -- sees it.
                    all_detections = self._active_extractor().drop_shadow_boxes(all_detections, w, h)
```

（`w`、`h` 在这段之前已由 `h, w = warped.shape[:2]` 定义；`_active_extractor()` 总是返回一个提取器。）

- [ ] **Step 5: 跑测试，确认通过；全量；格式**

```bash
uv run black -l 120 katrain/vision/board_state.py katrain/vision/worker_inprocess.py tests/test_vision/test_board_state_shadow.py
CI=true uv run pytest tests/test_vision/test_board_state_shadow.py -q --color=no -p no:cacheprovider 2>&1 | tail -1
CI=true uv run pytest tests/test_vision -q --color=no -p no:cacheprovider 2>&1 | tail -1
```

Expected: **15 passed**；全量 **855 passed**（840 + 15），0 failed。任何原有用例变红都要报告，不许改原有断言。

- [ ] **Step 6: 提交**

```bash
git add -- katrain/vision/board_state.py katrain/vision/worker_inprocess.py tests/test_vision/test_board_state_shadow.py
git commit -m "feat(vision): drop a stone's shadow box after dedup, in the board state

A stone box between intersections (>= 0.35 cells, parallax-corrected) that overlaps a
similar-sized box nearer a point which scored at least as high is a shadow boxed a second
time. The worker applies it right after detection, before the confidence tiers.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 7: 变异检查（每一条新测试都要能红）**

```bash
find katrain tests -name __pycache__ -type d -prune -exec rm -rf {} +
# 每次改动之后：
CI=true PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_vision/test_board_state_shadow.py -q --color=no -p no:cacheprovider 2>&1 | grep -E "^FAILED|^ERROR|passed|failed"
# 每次读完：
git checkout -- katrain/vision/board_state.py katrain/vision/worker_inprocess.py
```

| 改动（`board_state.py`，最后一行是 `worker_inprocess.py`） | 必须变红的测试（修计划时在原型上实测） |
|---|---|
| `SHADOW_MIN_OFFSET = 0.0` | `test_a_row_of_five_touching_same_colour_stones_is_kept`、`test_offset_threshold_boundary`、`test_the_shadow_at_the_end_of_a_row_is_dropped_and_the_row_kept` |
| `SHADOW_MIN_OFFSET = 0.60` | `test_a_stones_shadow_box_is_dropped_and_the_stone_kept`、`test_offset_threshold_boundary`、`test_overlap_threshold_boundary`、`test_side_ratio_boundary`、`test_the_shadow_at_the_end_of_a_row_is_dropped_and_the_row_kept`、`test_the_worker_drops_a_shadow_before_the_board_sees_it` |
| `SHADOW_MIN_OFFSET = 0.36` | `test_offset_threshold_boundary` |
| `if offset[i] < SHADOW_MIN_OFFSET:` 改成 `<=` | `test_offset_threshold_boundary` |
| `SHADOW_OVERLAP_MIN = 1.01` | 与 `SHADOW_MIN_OFFSET = 0.60` 那一行相同的六条 |
| `SHADOW_OVERLAP_MIN = 0.25` | `test_overlap_threshold_boundary` |
| `>= SHADOW_OVERLAP_MIN` 改成 `>` | `test_overlap_threshold_boundary` |
| `SHADOW_MAX_SIDE_RATIO = 10.0` | `test_a_big_box_does_not_make_the_stones_under_it_shadows`、`test_side_ratio_boundary` |
| `larger <= SHADOW_MAX_SIDE_RATIO` 改成 `<` | `test_side_ratio_boundary` |
| `if d.class_id in STONE_CLASS_IDS` 改成 `if True` | `test_led_boxes_are_never_dropped` |
| 删掉 ` or detections[j].confidence < conf`（置信度条件） | `test_a_box_is_only_a_shadow_of_a_box_nearer_a_point`、`test_a_box_that_outscores_its_partner_is_never_dropped`、`test_a_stone_pushed_off_its_point_toward_its_shadow_is_kept` |
| 删掉 ` offset[j] >= offset[i] or`（离点更近的条件） | `test_a_box_is_only_a_shadow_of_a_box_nearer_a_point` |
| 删掉两行 `and math.isfinite(...)` | `test_boxes_without_area_or_finite_position_pass_through` |
| `return [d for i, d in enumerate(detections) if i not in shadows]` 改成 `return list(detections)` | 与 `SHADOW_MIN_OFFSET = 0.60` 那一行相同的六条 |
| 删掉 worker 里 `all_detections = self._active_extractor().drop_shadow_boxes(...)` 那一行 | `test_the_worker_drops_a_shadow_before_the_board_sees_it` |

把「改动 → 变红的测试名」原样写进报告。任何一行没有按表变红，就是测试没有守住它声称守住的东西，要修测试而不是修表。全部还原后 `git status --short` 对这两个文件为空，再跑一遍全量，必须回到 **855 passed**。

---

### Task 2: 端到端回归 —— 09-23 那局的真实框走完整条线（与 Task 3 并行）

**Files:**
- Create: `tests/test_vision/test_shadow_phantom.py`（Task 1 删掉了第一版；这是按新顺序重写的）
- 已存在（不改）：`tests/test_vision/data/shadow_dedup_20260923.json`

**Interfaces:**
- Consumes: Task 1 的 `BoardStateExtractor.drop_shadow_boxes`；`dedup_detections`（原样）；`BoardStateExtractor(config, parallax=...)`、`.detections_to_board(...)`、`.cell_top(...)`、`.parallax_points(...)`。
- Produces: 无（纯测试）。

本任务**不提交**，不改 `katrain/` 下任何文件（Task 3 正在用它），由主会话审过后提交。

- [ ] **Step 1: 写测试**

```python
"""End-to-end: shadow boxes from the RK3562 daylight game (2026-09-23) must not reach the board.

Geometry is the deployed go4_s.rknn's own output on that board, run through the live order -- dedup_detections,
then drop_shadow_boxes, then the board-state path (parallax on, occupancy-aware assignment, sticky). See
superpowers/tracks/vision-optimizations/shadow-dedup/design.md §1 for how H5 became a self-sustaining phantom
and D7 a sub-threshold prompt.
"""

import dataclasses
import json
from pathlib import Path

import numpy as np
import pytest

from katrain.vision.board_state import BoardStateExtractor
from katrain.vision.classes import STONE_CLASS_IDS
from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig
from katrain.vision.parallax import ParallaxParams
from katrain.vision.stone_detector import Detection, dedup_detections

IMG = 1056
FIXTURE = json.loads((Path(__file__).parent / "data" / "shadow_dedup_20260923.json").read_text())
TRUTH = np.array(FIXTURE["truth_board"])
G5, H5 = (14, 6), (14, 7)

# G5 black stone (frame warped_09) and its shadow box at the two positions the live log recorded:
#   frame 1: raw (13.69, 6.364) -> corrected column 6.5006 -> rounds into the EMPTY H5
#   frame 2: raw (13.71, 6.33)  -> corrected column 6.467  -> held on H5 by sticky assignment (0.58 < 0.65)
G5_STONE = Detection(x_center=360.33, y_center=792.29, class_id=0, confidence=0.50, bbox=(332.6, 761.8, 388.0, 822.8))


def _shadow(x, y, conf=0.45):
    return Detection(
        x_center=x, y_center=y, class_id=0, confidence=conf, bbox=(x - 24.95, y - 25.55, x + 24.95, y + 25.55)
    )


FRAME1_SHADOW = _shadow(388.82, 775.63)
FRAME2_SHADOW = _shadow(387.02, 776.69)


def _extractor():
    return BoardStateExtractor(
        BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS), parallax=ParallaxParams(**FIXTURE["parallax"])
    )


def _live(ex, raw):
    """What the worker hands on: dedup inside StoneDetector.detect, then the shadow step."""
    return ex.drop_shadow_boxes(dedup_detections(raw), IMG, IMG)


def _board(ex, dets, prev=None):
    return ex.detections_to_board(
        dets, img_w=IMG, img_h=IMG, occupancy_aware=True, add_threshold=0.40, prev_board=prev, sticky_board=prev
    )


def _frame(name):
    return [Detection(d["x"], d["y"], d["cls"], d["conf"], tuple(d["bbox"])) for d in FIXTURE["frames"][name]]


def _empty_points_hit(ex, dets):
    """Truth-EMPTY intersections that some stone box rounds onto (parallax-corrected)."""
    hits = set()
    for _, _, fy, fx, cls, _ in ex.parallax_points([d for d in dets if d.class_id in STONE_CLASS_IDS], IMG, IMG):
        r, c = int(round(fy)), int(round(fx))
        if 0 <= r < 19 and 0 <= c < 19 and TRUTH[r][c] == 0:
            hits.add((r, c))
    return hits


def test_the_h5_chain_reproduces_without_the_shadow_step():
    """Precondition: the fixture really drives the live phantom path, dedup included. If this goes red, the
    assignment code changed and the tests below no longer prove anything about shadows."""
    ex = _extractor()
    b1 = _board(ex, dedup_detections([G5_STONE, FRAME1_SHADOW]))
    b2 = _board(ex, dedup_detections([G5_STONE, FRAME2_SHADOW]), prev=b1)
    assert b1[H5] == 1 and b2[H5] == 1
    assert b1[G5] == 1 and b2[G5] == 1


def test_the_shadow_step_breaks_the_h5_chain():
    ex = _extractor()
    b1 = _board(ex, _live(ex, [G5_STONE, FRAME1_SHADOW]))
    assert b1[H5] == 0 and b1[G5] == 1
    # Frame 2 starting from a board where the phantom is ALREADY established (sticky would hold it): the
    # shadow step must release it, not merely avoid creating it.
    phantom = _board(ex, dedup_detections([G5_STONE, FRAME1_SHADOW]))
    assert phantom[H5] == 1  # precondition
    b2 = _board(ex, _live(ex, [G5_STONE, FRAME2_SHADOW]), prev=phantom)
    assert b2[H5] == 0 and b2[G5] == 1


def test_sub_threshold_shadow_no_longer_reaches_an_empty_point():
    """The D7 path: a shadow box below the add threshold (0.32, as logged for D7) that rounds onto an EMPTY
    point is a cell_top candidate for the ambiguous-move prompt. In warped_09 the box beside C8 does this."""
    ex = _extractor()
    raw = _frame("warped_09.jpg")
    hits = _empty_points_hit(ex, dedup_detections(raw))
    assert hits == {(10, 2)}  # precondition: C9, and only C9, after dedup alone
    shadow = next(
        d
        for d in raw
        if d.class_id in STONE_CLASS_IDS
        and (int(round(ex.parallax_points([d], IMG, IMG)[0][2])), int(round(ex.parallax_points([d], IMG, IMG)[0][3])))
        == (10, 2)
    )
    raw = [dataclasses.replace(d, confidence=0.32) if d is shadow else d for d in raw]
    keep_tier = [d for d in dedup_detections(raw) if d.confidence >= 0.30]
    assert (10, 2) in ex.cell_top(keep_tier, IMG, IMG)  # precondition: the prompt path would see it
    kept = [d for d in _live(ex, raw) if d.confidence >= 0.30]
    assert (10, 2) not in ex.cell_top(kept, IMG, IMG)


@pytest.mark.parametrize("name, missed", [("warped_06.jpg", set()), ("warped_09.jpg", {(5, 2)})])
def test_real_frames_lose_no_stone_and_reach_no_empty_point(name, missed):
    """Whole frames: after dedup and the shadow step, the board equals the truth except the one stone the
    detector itself missed in warped_09 (C14), and no stone box rounds onto an empty point."""
    ex = _extractor()
    kept = _live(ex, _frame(name))
    assert _empty_points_hit(ex, kept) == set()
    board = _board(ex, [d for d in kept if d.confidence >= 0.30])
    diff = {(r, c) for r in range(19) for c in range(19) if board[r][c] != TRUTH[r][c]}
    assert diff == missed
```

- [ ] **Step 2: 跑测试**

Run: `CI=true uv run pytest tests/test_vision/test_shadow_phantom.py -q --color=no -p no:cacheprovider`
Expected: **5 passed**。

- [ ] **Step 3: 确认它们会为对的理由变红（在临时 worktree 里，不碰共用工作树）**

把去影子这一步换成「原样返回」，只有断言影子被去掉的三条该红：

```bash
git worktree add /tmp/shadow-e2e HEAD
cp tests/test_vision/test_shadow_phantom.py /tmp/shadow-e2e/tests/test_vision/
cd /tmp/shadow-e2e
python3 - <<'EOF'
p = "katrain/vision/board_state.py"
s = open(p).read()
old = "        return [d for i, d in enumerate(detections) if i not in shadows]"
assert s.count(old) == 1
open(p, "w").write(s.replace(old, "        return list(detections)"))
EOF
CI=true PYTHONDONTWRITEBYTECODE=1 /Users/fan/Repositories/katrain-vision-stone-parallax/.venv/bin/python -m pytest tests/test_vision/test_shadow_phantom.py -q --color=no -p no:cacheprovider 2>&1 | grep -E "^FAILED|passed|failed"
cd /Users/fan/Repositories/katrain-vision-stone-parallax
git worktree remove --force /tmp/shadow-e2e
```

（用主工作树的 venv 跑 `python -m pytest`：它把临时 worktree 放在 `sys.path` 最前面，导入的是改过的代码；`uv run` 在新 worktree 里会另建环境。）

Expected: `test_the_shadow_step_breaks_the_h5_chain`、`test_sub_threshold_shadow_no_longer_reaches_an_empty_point`、`test_real_frames_lose_no_stone_and_reach_no_empty_point[warped_09.jpg-missed1]` FAIL；`test_the_h5_chain_reproduces_without_the_shadow_step` 与 `[warped_06.jpg-missed0]` PASS（**3 failed, 2 passed**，修计划时实测如此）。0 failed 说明导入的是共用工作树里的代码，停下报告。

- [ ] **Step 4: 全量 + 格式**

```bash
uv run black -l 120 tests/test_vision/test_shadow_phantom.py
CI=true uv run pytest tests/test_vision -q --color=no -p no:cacheprovider 2>&1 | tail -1
```

Expected: **860 passed**（Task 1 后的 855 + 本任务 5 条），0 failed。报告「可以提交」。

---

### Task 3: 标注集验证闸（与 Task 2 并行）

**Files:**
- Create: `superpowers/tracks/vision-optimizations/shadow-dedup/measure_shadow_step.py`
- Modify: `superpowers/tracks/vision-optimizations/shadow-dedup/validation.md`（在文末追加第二版一节；第一版的 FAIL 记录原样保留）
- 复用（不改）：同目录的 `measure_labelled.py`（借它的 `labels_for`、`match`、`where`）

**Interfaces:**
- Consumes: 主会话给的 `$SCR`（含板上导出的 `dets_labelled.json` —— 209 张图去重前的原始框 —— 与 `labels/`）；Task 1 已提交的代码；`superpowers/tracks/vision-optimizations/evidence-2026-09-23-daylight-game/` 下的 `truth_board.json` 与 `board_detections_12_frames.json.gz`。
- Produces: `validation.md` 第二版一节里一行 `VERDICT: PASS`、`FAIL` 或 `INVALID`，以及真子框偏离量分布、这一步删掉的框数、代价与颜色两项。

本任务**不提交**，不改 `katrain/` 与 `tests/` 下的任何文件（Task 2 正在用它们）。

- [ ] **Step 1: 写测量脚本**

`superpowers/tracks/vision-optimizations/shadow-dedup/measure_shadow_step.py`：

```python
"""Acceptance gate for the board-state shadow step (design.md §5) on the labelled set.

"Old" is the live order without the step: dedup_detections. "New" adds BoardStateExtractor.drop_shadow_boxes
after it -- both taken from the working tree on PYTHONPATH, i.e. the code being landed. The step only ever
removes boxes, so the new output is a subset of the old one, and old coverage minus new coverage is exactly
what the step costs. Coverage is a maximum one-to-one matching of boxes to YOLO labels (measure_labelled.match),
colour-agnostic and colour-aware.

Usage (repo root):
  PYTHONPATH=. python measure_shadow_step.py <dets.json> <labels_root> --expect-images N [--parallax FX,FY,K]
"""

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from measure_labelled import labels_for, match, where  # noqa: E402

from katrain.vision.board_state import SHADOW_MIN_OFFSET, BoardStateExtractor  # noqa: E402
from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig  # noqa: E402
from katrain.vision.parallax import ParallaxParams  # noqa: E402
from katrain.vision.stone_detector import Detection, dedup_detections  # noqa: E402

IMG = 1056
STONE = (0, 1)
GATE_MIN_RECALL = 0.95


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dets")
    ap.add_argument("labels_root", type=Path)
    ap.add_argument("--expect-images", type=int, required=True)
    ap.add_argument("--parallax", help="nadir_fx,nadir_fy,k of the board the images came from (default: none)")
    args = ap.parse_args()
    parallax = ParallaxParams(*map(float, args.parallax.split(","))) if args.parallax else None
    ex = BoardStateExtractor(BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS), parallax=parallax)
    dets = json.load(open(args.dets))

    n_labels = seen_old = n_dropped = 0
    lost, recoloured, dropped_on_labels, real_offsets = [], [], [], []
    for name, fr in sorted(dets.items()):
        raw = [Detection(d["x"], d["y"], d["cls"], d["conf"], tuple(d["bbox"])) for d in fr["raw"]]
        labels = labels_for(args.labels_root, name)
        n_labels += len(labels)
        old = dedup_detections(raw)
        new = ex.drop_shadow_boxes(old, IMG, IMG)
        kept_old = [d for d in old if d.class_id in STONE]
        kept_new = [d for d in new if d.class_id in STONE]
        new_ids = {id(d) for d in kept_new}
        m_old = match(kept_old, labels)
        seen_old += len(m_old)
        for li, bi in m_old.items():
            _, _, fx, fy, _ = ex._positions(kept_old[bi], IMG, IMG)
            real_offsets.append(math.hypot(fy - round(fy), fx - round(fx)))
            if id(kept_old[bi]) not in new_ids:
                dropped_on_labels.append((name, where(labels[li])))
        n_dropped += len(kept_old) - len(kept_new)
        m_new = match(kept_new, labels)
        if len(m_new) < len(m_old):
            lost.append((name, len(m_old) - len(m_new), [where(labels[li]) for li in sorted(set(m_old) - set(m_new))]))
        c_old, c_new = match(kept_old, labels, True), match(kept_new, labels, True)
        if len(c_new) < len(c_old):
            recoloured.append(
                (name, len(c_old) - len(c_new), [where(labels[li]) for li in sorted(set(c_old) - set(c_new))])
            )

    real_offsets.sort()
    n = len(real_offsets)
    q = lambda p: real_offsets[min(n - 1, int(p * n))] if n else float("nan")  # noqa: E731
    recall = seen_old / n_labels if n_labels else 0.0
    print(f"images {len(dets)} (expected {args.expect_images})  labelled stones {n_labels}  recall(old) {recall:.4f}")
    print(f"parallax {'on ' + args.parallax if args.parallax else 'off'}  SHADOW_MIN_OFFSET {SHADOW_MIN_OFFSET}")
    print(
        f"label-matched boxes, cells from their point: p50 {q(0.5):.2f} p90 {q(0.9):.2f} p99 {q(0.99):.2f} "
        f"p99.9 {q(0.999):.2f} max {q(1.0):.2f}  (at or above the threshold: {sum(o >= SHADOW_MIN_OFFSET for o in real_offsets)})"
    )
    print(
        f"boxes the shadow step dropped: {n_dropped}, of which label-matched before: {len(dropped_on_labels)} {dropped_on_labels[:20]}"
    )
    print(f"labels the shadow step costs: {sum(k for _, k, _ in lost)} {lost[:20]}")
    print(f"labels that lose their correct-colour box: {sum(k for _, k, _ in recoloured)} {recoloured[:20]}")
    valid = len(dets) == args.expect_images and recall >= GATE_MIN_RECALL
    ok = valid and not lost and not recoloured
    verdict = "PASS" if ok else ("FAIL" if valid else "INVALID")
    print(
        f"VERDICT: {verdict}  (valid: images == expected and recall >= {GATE_MIN_RECALL}; "
        f"pass: no label lost or recoloured by the shadow step)"
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 自检 —— 09-23 那局的 12 帧（已知答案，视差校正开）**

```bash
EV=superpowers/tracks/vision-optimizations/evidence-2026-09-23-daylight-game
M=superpowers/tracks/vision-optimizations/shadow-dedup/measure_shadow_step.py
python3 - "$EV" "$SCR" <<'PY'
import json, gzip, sys, os
ev, scr = sys.argv[1], sys.argv[2]
T = json.load(open(f"{ev}/truth_board.json"))["board"]
D = json.load(gzip.open(f"{ev}/board_detections_12_frames.json.gz", "rt"))
os.makedirs(f"{scr}/labels12", exist_ok=True)
pad, cell = 53, 949 / 18
for name in D:
    with open(f"{scr}/labels12/{name[:-4]}.txt", "w") as f:
        for r in range(19):
            for c in range(19):
                if T[r][c]:
                    f.write(f"{T[r][c]-1} {(pad + c*cell)/1056:.6f} {(pad + r*cell)/1056:.6f} {cell/1056:.6f} {cell/1056:.6f}\n")
json.dump(D, open(f"{scr}/dets12.json", "w"))
PY
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 uv run python $M $SCR/dets12.json $SCR/labels12 --expect-images 12 --parallax 19.612,9.0,0.989689
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 uv run python $M $SCR/dets12.json $SCR/labels12 --expect-images 13 --parallax 19.612,9.0,0.989689 | tail -1
```

期望（修计划时原型实测）：第一次 `images 12 (expected 12)  labelled stones 1296  recall(old) 1.0000`、`p50 0.12 p90 0.23 p99 0.34 p99.9 0.35 max 0.36`、`boxes the shadow step dropped: 36, of which label-matched before: 0`、代价 `0`、颜色 `0`、`VERDICT: PASS`；第二次最后一行 `VERDICT: INVALID`。对不上就停下报告 NEEDS_CONTEXT，不许改脚本去凑。

- [ ] **Step 3: 跑标注集**

```bash
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 uv run python $M $SCR/dets_labelled.json $SCR/labels --expect-images 209 | tee $SCR/report2.txt
```

修计划时原型读数：`images 209 ... recall(old) 0.9997`、`p50 0.18 p90 0.28 p99 0.35 p99.9 0.38 max 0.46`、`boxes the shadow step dropped: 0`、代价 `0`、颜色 `0`、`VERDICT: PASS`。结果不管是什么都照实写，不许改门槛或脚本。

- [ ] **Step 4: 在 `validation.md` 文末追加「## 第二版：去影子一步（YYYY-MM-DD）」一节**

内容：数据来源（同第一版：`$SCR/dets_labelled.json` 是板上 `go4_s.rknn` 导出的 209 张图原始框）、「旧」与「新」各是什么（`dedup_detections` / 再加 `drop_shadow_boxes`，工作树 HEAD 的 sha）、Step 2 两次运行的输出、Step 3 的完整输出（原样贴进代码块）、`VERDICT` 行原样照抄。不是 PASS 时再写哪一条没过、涉及的图片名与位置，**不给修改建议**。

- [ ] **Step 5: 报告**

不删 `$SCR`（主会话保留到收尾）。报告「可以提交」，附 `VERDICT` 行。

---

### Task 4: 文档收口

**Files:**
- Modify: `superpowers/tracks/vision-optimizations/README.md`（「一帧怎么走」表 5b 行；「历次优化」表追加一行）
- Modify: `superpowers/tracks/vision-optimizations/shadow-dedup/design.md`（标题下加状态行）

- [ ] **Step 1: README 5b 行**

把以 `| 5b | 去影子（**规划中**）` 开头的那一行改为：

```markdown
| 5b | 去影子：侧光下「子 + 影子」被再框一次的那个框 | `board_state.drop_shadow_boxes` | 离交叉点 ≥ 0.35 格，且与一个离点更近、分数不低于它、大小相近的框互压 ≥ 0.27 |
```

- [ ] **Step 2: 「历次优化」表追加一行**（放在表最后一行之后，格式照抄上面几行）

```markdown
| 2026-09-23 | 去重复框之后新增「去影子」一步 | 侧光下「子 + 影子」被再框一次，偏出半格，逃过去重，经视差 + 粘滞在邻点（H5）自我维持成假子；低于门槛的则升级成疑似落子卡片（D7）。第一版并进去重，会吞掉贴在一起的真子，已撤回 | 待上板 | [shadow-dedup/design.md](shadow-dedup/design.md)、[validation.md](shadow-dedup/validation.md) |
```

- [ ] **Step 3: design.md 状态行**

在标题下一行插入：`状态：第二版已实现（Task 1/2），标注集验证 <照抄 validation.md 第二版一节的 VERDICT>，待 RK3562 侧光局复测。`

- [ ] **Step 4: 报告「可以提交」**

---

## 完成后的动作（不在任务内，由主会话执行）

1. opus 按 code-review 技能审整个分支（从 `98b1a67a` 到 HEAD），改到通过。
2. 流程图：`recognition-pipeline.architecture.json` 里「去影子」去掉「规划中」，加源码出处（`board_state.drop_shadow_boxes`）；`meta.repository.revision` 改成当时的 HEAD 并重核所有出处行号；用 archify 重新生成，showcase 必须 9/9、0 错 0 警告。
3. **上板前征得 Fan 同意**。部署两个运行时文件：`katrain/vision/board_state.py`、`katrain/vision/worker_inprocess.py`（`stone_detector.py` 与板上一致，不动）；按 `reference_rk3562_katrain_deploy_recipe` 备份 → rsync → `systemctl restart smartbox-katrain`，前端不用重建。
4. 侧光时段下一盘：`evidence-2026-09-23-daylight-game/summarize.py` 统计疑似落子卡片（上一局 111 手 19 次）；vtrace 看 `detect − pre − npu − post`（上一局框数 ≥ 100 的帧中位 3 ms、p95 6 ms，整帧中位 504 ms；预计中位 5–6 ms）。中位超过 9 ms 或出现 > 60 ms 的帧，停下报数。
5. 通知五子棋 session：已落地，`dedup_detections` 未变，新增 `BoardStateExtractor.drop_shadow_boxes` 与三个常量。
6. 合 develop、push，bump smartbox `vendor/katrain`（只 `git add -- vendor/katrain`）。

## 明确不做（本轮）

见 spec §6：弹窗改造与「不是落子」、参照帧三处缺口、孤立假框（A15 类）、§3 的两种罕见情形（保持原行为）。
