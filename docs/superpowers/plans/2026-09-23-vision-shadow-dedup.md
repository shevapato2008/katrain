# 影子重复框去重 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `dedup_detections` 把「棋子 + 它的影子」这种偏出半格的重复框认作同一颗子，从源头消掉侧光下的假子（H5 自我维持的假黑子、D7 低置信疑似落子卡片）。

**Architecture:** 在现有「中心距 < 0.5 × 较小边长」规则之外，对两个棋子类框追加一条「交叠面积 ÷ 较小框面积 ≥ 0.27，且两框边长比 ≤ 2」的合并条款；只加不减，LED 框不受影响。网格加速结构的格边长随之放大到「最大框宽/高」，并由对比 O(k²) 参考实现的差分测试保证逐位等价。落地前用 209 张带真值的标注图在板上用部署模型复核门槛。

**Tech Stack:** Python 3.11、numpy、OpenCV、pytest（`uv run`）；RK3562 上的 RKNN 推理（`go4_s.rknn`）；ssh 到 `rk3562-direct` 与 `home-ubuntu`。

**Spec:** `superpowers/tracks/vision-optimizations/shadow-dedup/design.md`（必读；数字、根因、复现坐标都在里面）

## Global Constraints

- 阈值常量，名字和值都固定：`DEDUP_OVERLAP_MIN = 0.27`、`DEDUP_MAX_SIDE_RATIO = 2.0`，定义在 `katrain/vision/stone_detector.py` 模块级。
- 新条款**只作用于两个棋子类框**（`STONE_CLASS_IDS`，黑白之间也算）；LED 类（`led_red` / `led_green`）只按旧的中心距规则、只在同类内去重。
- 新规则是旧规则的**超集**：旧规则的判定代码原样保留，新条款只在它之后追加。
- `dedup_detections(detections: list[Detection]) -> list[Detection]` 与 `Detection` 数据类的签名、字段**不许改**（五子棋 session 钉了这两个）。
- 输出必须与同语义的 O(k²) 标量参考实现**逐对象、逐顺序一致**（`id()` 比较），网格只是加速。
- 旧规则下「没有 bbox（全 0）或平均边长 ≤ 0」的检测永不参与去重 —— 新条款同样不许让它们参与。
- Python 用 Black，120 列：`uv run black -l 120 <file>`。
- 测试命令一律带 `--color=no`（变异检查要解析输出；带颜色时 `startswith("FAILED")` 匹配不到任何东西）。
- 板子（RK3562，2 GB 内存）上一次只跑一件事：动板子之前 `pgrep -af "board_detect_dump|pytest"` 必须为空。
- 共用工作树：**并行的任务不许 `git commit`，也不许 `git checkout`/`git stash`**，除非任务里明确写了；提交由执行本计划的主会话在每个任务审过之后统一做。

## Review Focus

1. **一只手搭在盘上被读成一个大框**（边长是棋子的 3 倍、置信度更高）：大框下面的每颗真子都必须保留 —— Task 2 `test_big_box_does_not_swallow_the_stones_under_it`。
2. **两颗相邻真子放得歪、框互压得比 J2/J3（0.233）还多**：只要 IoMin < 0.27 就都保留，且门槛两侧逐点钉死 —— Task 2 `test_overlap_threshold_boundary`；真实分布由 Task 1 的标注集闸复核。
3. **两盏相邻的 LED 同时亮**：LED 框互压到 0.28 也不许合并 —— Task 2 `test_led_boxes_keep_the_centre_distance_rule`。
4. **影子框的置信度反超真子**：保留下来的影子框仍须落在真子那一格，邻点不得出子 —— Task 3 `test_shadow_outscoring_its_stone_still_lands_on_the_stone`。
5. **低于落子门槛的影子框（D7 那条路）**：去重后 `cell_top` 在空点上不再有候选，疑似落子卡片无从升级 —— Task 3 `test_sub_threshold_shadow_no_longer_reaches_an_empty_point`。

---

## 并行关系

- **Task 1**（标注集验证闸）与 **Task 2**（改规则 + 单元测试）**同时开工**，互不依赖：Task 1 自带一份规则的独立实现，不 import 仓里的 `dedup_detections`。
- **Task 3** 依赖 Task 2 的实现。
- **Task 4** 在 1–3 都通过后做。Task 1 结论为 FAIL 时，停在 Task 4 之前，把数报给 Fan。

---

### Task 1: 标注集验证闸（板上部署模型 × 209 张真值图）

**Files:**
- Create: `superpowers/tracks/vision-optimizations/shadow-dedup/measure_labelled.py`
- Create: `superpowers/tracks/vision-optimizations/shadow-dedup/validation.md`
- 复用（不改）：`superpowers/tracks/vision-optimizations/evidence-2026-09-23-daylight-game/board_detect_dump.py`

**Interfaces:**
- Consumes: 板上 `/opt/smartbox/share/katrain-vision/go4_s.rknn`、`/opt/smartbox/venv-katrain/bin/python`、`/root/smartbox-software/vendor/katrain`（板上代码）；home-ubuntu 的 `/home/fan/Repositories/katrain/data/go4_split/{images,labels}/{train,val}/`（1056×1056 JPEG，YOLO 归一化标签 `cls cx cy w h`，类 0=black 1=white 2=led_red 3=led_green）。
- Produces: `validation.md` 里一行明确的 `VERDICT: PASS` 或 `VERDICT: FAIL`，以及下列数：真子框互压 IoMin 最大值与前 5 对、旧/新规则各自丢失的标注棋子数、重复框 IoMin 直方图。

本任务**不提交**，只产出文件；由主会话审过后提交。

- [ ] **Step 1: 拉数据到本机临时目录**

```bash
SCR=$(mktemp -d /tmp/shadow-labelled.XXXX); echo $SCR
rsync -az -e "ssh -o BatchMode=yes" home-ubuntu:/home/fan/Repositories/katrain/data/go4_split/images/ $SCR/images/
rsync -az -e "ssh -o BatchMode=yes" home-ubuntu:/home/fan/Repositories/katrain/data/go4_split/labels/ $SCR/labels/
find $SCR/images -name '*.jpg' | wc -l      # 期望 209
find $SCR/labels -name '*.txt' | wc -l      # 期望 209
```

- [ ] **Step 2: 在板上跑部署模型（去重前的全部框）**

```bash
ssh rk3562-direct 'pgrep -af "board_detect_dump|pytest" ; free -m | sed -n 2p'   # 第一行必须为空；available 应 > 400
ssh rk3562-direct 'rm -rf /root/shadow-probe/labelled && mkdir -p /root/shadow-probe/labelled'
mkdir -p $SCR/flat && find $SCR/images -name '*.jpg' -exec cp {} $SCR/flat/ \;
ls $SCR/flat | wc -l      # 期望 209（train/val 文件名不重名；不是 209 就停）
rsync -a $SCR/flat/ rk3562-direct:/root/shadow-probe/labelled/
scp superpowers/tracks/vision-optimizations/evidence-2026-09-23-daylight-game/board_detect_dump.py rk3562-direct:/root/shadow-probe/
ssh rk3562-direct 'cd /root/smartbox-software/vendor/katrain && PYTHONPATH=/root/smartbox-software/vendor/katrain \
  /opt/smartbox/venv-katrain/bin/python /root/shadow-probe/board_detect_dump.py /root/shadow-probe/labelled /root/shadow-probe/dets_labelled.json 2>&1 | grep -vc "^[IW] RKNN"'
scp rk3562-direct:/root/shadow-probe/dets_labelled.json $SCR/
ssh rk3562-direct 'rm -rf /root/shadow-probe/labelled /root/shadow-probe/dets_labelled.json'   # 板上磁盘只剩 2 GB，用完即删
```

期望：倒数第三条命令打印 209（每张图一行）。`dets_labelled.json` 的键是图片文件名，值含 `raw`（去重前）与 `dedup`（板上现行规则）两个框列表，每个框 `{"x","y","cls","conf","bbox":[x1,y1,x2,y2]}`。

- [ ] **Step 3: 写测量脚本**

`superpowers/tracks/vision-optimizations/shadow-dedup/measure_labelled.py`：

```python
"""Shadow-dedup acceptance gate on the labelled set (design.md §5).

Inputs: the board's raw (pre-dedup) boxes per image (board_detect_dump.py output) and the YOLO
labels derived from the game record. Truth stones come from the labels only.

Usage: python measure_labelled.py <dets_labelled.json> <labels_root> > report.txt
"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

IMG = 1056
STONE = (0, 1)
OVERLAP_MIN = 0.27  # design.md §2 — this script carries its OWN copy of the rule on purpose
MAX_SIDE_RATIO = 2.0
GATE_REAL_MAX = 0.25


def side(b):
    return ((b[2] - b[0]) + (b[3] - b[1])) / 2.0


def area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def iomin(a, b):
    small = min(area(a), area(b))
    if small <= 0:
        return 0.0
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h) / small


def dedup(dets, new_rule):
    """Scalar reference of dedup_detections: old rule, plus the new clause when new_rule."""
    kept = []
    for d in sorted(dets, key=lambda d: -d["conf"]):
        ds = side(d["bbox"])
        dup = False
        for o in kept:
            d_stone, o_stone = d["cls"] in STONE, o["cls"] in STONE
            if d_stone != o_stone or (not d_stone and d["cls"] != o["cls"]):
                continue
            os_ = side(o["bbox"])
            ms = min(ds, os_)
            if ms <= 0:
                continue
            if math.hypot(d["x"] - o["x"], d["y"] - o["y"]) < 0.5 * ms:
                dup = True
                break
            if new_rule and d_stone and max(ds, os_) <= MAX_SIDE_RATIO * ms and iomin(d["bbox"], o["bbox"]) >= OVERLAP_MIN:
                dup = True
                break
        if not dup:
            kept.append(d)
    return kept


def labels_for(labels_root: Path, image_name: str):
    hits = list(labels_root.rglob(Path(image_name).stem + ".txt"))
    if len(hits) != 1:
        raise SystemExit(f"label for {image_name}: expected 1 file, found {len(hits)}")
    out = []
    for line in hits[0].read_text().split("\n"):
        parts = line.split()
        if len(parts) == 5 and int(parts[0]) in STONE:
            c, cx, cy, w, h = int(parts[0]), *map(float, parts[1:])
            out.append({"cls": c, "x": cx * IMG, "y": cy * IMG, "side": (w + h) / 2 * IMG})
    return out


def owners(stones, labels):
    """label index -> index (into stones) of the highest-confidence box within half a label side."""
    own = {}
    for li, lab in enumerate(labels):
        cand = [i for i, d in enumerate(stones) if math.hypot(d["x"] - lab["x"], d["y"] - lab["y"]) <= 0.5 * lab["side"]]
        if cand:
            own[li] = max(cand, key=lambda i: stones[i]["conf"])
    return own


def seen(kept, labels):
    ks = [d for d in kept if d["cls"] in STONE]
    return {li for li, lab in enumerate(labels) if any(math.hypot(d["x"] - lab["x"], d["y"] - lab["y"]) <= 0.5 * lab["side"] for d in ks)}


def main():
    dets = json.load(open(sys.argv[1]))
    labels_root = Path(sys.argv[2])
    real_pairs, extra_best, lost_old, lost_new, n_labels = [], [], 0, 0, 0
    for name, fr in sorted(dets.items()):
        raw = fr["raw"]
        labels = labels_for(labels_root, name)
        n_labels += len(labels)
        stones = [d for d in raw if d["cls"] in STONE]
        own = owners(stones, labels)
        real_idx = set(own.values())
        idx_label = {v: k for k, v in own.items()}
        for i in real_idx:
            for j in real_idx:
                if i < j:
                    v = iomin(stones[i]["bbox"], stones[j]["bbox"])
                    if v > 0:
                        real_pairs.append((v, name, idx_label[i], idx_label[j]))
        for e in range(len(stones)):
            if e in real_idx:
                continue
            best = max((iomin(stones[e]["bbox"], stones[r]["bbox"]) for r in real_idx), default=0.0)
            extra_best.append(best)
        base = seen(raw, labels)
        lost_old += len(base - seen(dedup(raw, False), labels))
        lost_new += len(base - seen(dedup(raw, True), labels))
    real_pairs.sort(reverse=True)
    real_max = real_pairs[0][0] if real_pairs else 0.0
    print(f"images {len(dets)}  labelled stones {n_labels}")
    print(f"real-vs-real overlapping pairs {len(real_pairs)}  IoMin max {real_max:.3f}")
    for v, name, a, b in real_pairs[:5]:
        print(f"  {v:.3f}  {name}  labels #{a} #{b}")
    bins = [0, 0.1, 0.2, 0.27, 0.3, 0.4, 0.5, 0.7, 1.01]
    hist = Counter(next(k for k in range(len(bins) - 1) if bins[k] <= v < bins[k + 1]) for v in extra_best)
    print("extra boxes, best IoMin with a real box:", {f"{bins[k]}-{bins[k+1]}": hist.get(k, 0) for k in range(len(bins) - 1)})
    print(f"labelled stones lost: old rule {lost_old}  new rule {lost_new}")
    ok = real_max <= GATE_REAL_MAX and lost_new == lost_old
    print(f"VERDICT: {'PASS' if ok else 'FAIL'}  (gate: real max <= {GATE_REAL_MAX} and lost_new == lost_old)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 先拿板上这局的 12 帧跑一遍，确认脚本读数与 spec 一致**

这一步用的是已知答案的数据，用来发现脚本本身的错。12 帧没有 YOLO 标签，所以只核「旧规则丢子数 = 新规则丢子数」与真子互压最大值；真值从 `truth_board.json` 生成临时标签：

```bash
EV=superpowers/tracks/vision-optimizations/evidence-2026-09-23-daylight-game
python3 - "$EV" "$SCR" <<'EOF'
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
EOF
python3 superpowers/tracks/vision-optimizations/shadow-dedup/measure_labelled.py $SCR/dets12.json $SCR/labels12
```

期望：`real-vs-real ... IoMin max 0.233`（±0.005，J2/J3；这里真值未做视差修正，最大值应与 spec 表中 0.233 相同或极接近），`lost: old rule N  new rule N`（两数相等）。读数对不上就先修脚本，不许进 Step 5。

- [ ] **Step 5: 跑标注集**

```bash
python3 superpowers/tracks/vision-optimizations/shadow-dedup/measure_labelled.py $SCR/dets_labelled.json $SCR/labels | tee $SCR/report.txt
```

- [ ] **Step 6: 写 `validation.md`**

内容：日期、数据来源（home-ubuntu 路径、209 张、板上 `go4_s.rknn` sha1 `f0ece24d3659d75fa282fda099b1cecf3cbb74e4`）、Step 4 的自检读数、Step 5 的完整输出（原样贴进代码块）、`VERDICT` 行原样照抄。FAIL 时再加一段：哪一条没过、前 5 对真子互压的图片名，**不给修改建议**（门槛是 Fan 的决定）。

- [ ] **Step 7: 清理**

```bash
rm -rf $SCR
ssh rk3562-direct 'ls /root/shadow-probe/'   # 只应剩 board_detect_dump.py、frames/、dets.json（09-23 那局的）
```

---

### Task 2: 规则本体 —— `dedup_detections` 追加重叠条款

**Files:**
- Modify: `katrain/vision/stone_detector.py:32-106`（`dedup_detections` 及其上方新增常量与辅助函数）
- Test: `tests/test_vision/test_stone_detector.py`（新增 `TestShadowDuplicateDedup`；改 `TestDedupVectorisationIsEquivalent._reference_dedup`）

**Interfaces:**
- Consumes: `katrain.vision.classes.STONE_CLASS_IDS`；`Detection(x_center, y_center, class_id, confidence, bbox=(x1, y1, x2, y2))`。
- Produces（Task 3 用）: 模块级 `DEDUP_OVERLAP_MIN: float = 0.27`、`DEDUP_MAX_SIDE_RATIO: float = 2.0`、`_overlap_of_smaller(a: tuple, b: tuple) -> float`；`dedup_detections` 签名不变。

- [ ] **Step 1: 写失败的测试**

在 `tests/test_vision/test_stone_detector.py` 的 `TestDedupDetections` 类之后、`TestDedupVectorisationIsEquivalent` 之前插入：

```python
def _rect(x, y, class_id, conf, w, h):
    return Detection(x_center=x, y_center=y, class_id=class_id, confidence=conf, bbox=(x - w / 2, y - h / 2, x + w / 2, y + h / 2))


class TestShadowDuplicateDedup:
    """Side light makes the model box a stone together with its shadow a second time, ~half a cell off
    (RK3562 daylight game 2026-09-23). Real box geometry below comes from the deployed go4_s.rknn on that
    board; see superpowers/tracks/vision-optimizations/shadow-dedup/design.md."""

    # G5 black stone (frame warped_09) and its shadow box at the two positions the live log recorded
    G5 = Detection(x_center=360.33, y_center=792.29, class_id=0, confidence=0.50, bbox=(332.6, 761.8, 388.0, 822.8))

    @staticmethod
    def _g5_shadow(x, y, conf=0.45):
        return _rect(x, y, 0, conf, 49.9, 51.1)

    def test_shadow_box_of_a_stone_is_merged_into_it(self):
        from katrain.vision.stone_detector import dedup_detections

        for x, y in ((388.82, 775.63), (387.02, 776.69)):  # IoMin 0.373 / 0.411; centre dist > 0.5 * side
            out = dedup_detections([self.G5, self._g5_shadow(x, y)])
            assert out == [self.G5]

    def test_black_shadow_beside_a_white_stone_is_merged(self):
        from katrain.vision.stone_detector import dedup_detections

        c8 = Detection(
            x_center=141.32248363494872,
            y_center=627.0086608886718,
            class_id=1,
            confidence=0.6349,
            bbox=(110.30381927490234, 595.2922851562499, 172.3411479949951, 658.7250366210938),
        )
        shadow = Detection(
            x_center=173.78701915740965,
            y_center=609.3615966796875,
            class_id=0,
            confidence=0.2157,
            bbox=(151.50497589111328, 588.0772109985352, 196.06906242370604, 630.6459823608399),
        )  # IoMin 0.388, side ratio 1.44
        assert dedup_detections([c8, shadow]) == [c8]

    def test_the_closest_real_neighbours_on_the_board_are_kept(self):
        from katrain.vision.stone_detector import dedup_detections

        j2 = Detection(
            x_center=473.5685806274414,
            y_center=939.0665222167969,
            class_id=0,
            confidence=0.7155,
            bbox=(441.18038177490234, 907.70302734375, 505.95677947998047, 970.4300170898438),
        )
        j3 = Detection(
            x_center=463.5263305664062,
            y_center=893.9533630371093,
            class_id=0,
            confidence=0.6765,
            bbox=(433.25148925781247, 864.3791473388671, 493.80117187499997, 923.5275787353515),
        )  # IoMin 0.2325 — the highest overlap between two REAL stones in 2762 labelled pairs
        assert len(dedup_detections([j2, j3])) == 2

    def test_overlap_threshold_boundary(self):
        from katrain.vision.stone_detector import dedup_detections

        # Two 50 px squares offset horizontally by dx: IoMin = (50 - dx) / 50; dx > 25 keeps the old rule out.
        merged = dedup_detections([_rect(100, 100, 0, 0.9, 50, 50), _rect(136, 100, 0, 0.8, 50, 50)])  # 0.28
        kept = dedup_detections([_rect(100, 100, 0, 0.9, 50, 50), _rect(137, 100, 0, 0.8, 50, 50)])  # 0.26
        assert len(merged) == 1 and merged[0].confidence == 0.9
        assert len(kept) == 2

    def test_side_ratio_boundary(self):
        from katrain.vision.stone_detector import dedup_detections

        small = _rect(150, 100, 0, 0.8, 50, 50)  # centre 50 px from the big box's: the old rule never fires
        ratio_19 = dedup_detections([_rect(100, 100, 0, 0.9, 95, 95), small])  # IoMin 0.45
        ratio_21 = dedup_detections([_rect(100, 100, 0, 0.9, 105, 105), small])  # IoMin 0.55
        assert len(ratio_19) == 1
        assert len(ratio_21) == 2

    def test_big_box_does_not_swallow_the_stones_under_it(self):
        from katrain.vision.stone_detector import dedup_detections

        hand = _rect(200, 200, 0, 0.9, 160, 160)  # 3.2x a stone: a hand read as one big black box
        stones = [_rect(170, 200, 1, 0.8, 50, 50), _rect(230, 200, 0, 0.7, 50, 50), _rect(200, 160, 1, 0.6, 50, 50)]
        assert len(dedup_detections([hand, *stones])) == 4

    def test_led_boxes_keep_the_centre_distance_rule(self):
        from katrain.vision.stone_detector import dedup_detections

        leds = [_rect(100, 100, 2, 0.9, 50, 50), _rect(136, 100, 2, 0.8, 50, 50)]  # IoMin 0.28, centre dist 36 > 25
        stones = [_rect(100, 100, 0, 0.9, 50, 50), _rect(136, 100, 0, 0.8, 50, 50)]  # identical geometry
        assert len(dedup_detections(leds)) == 2
        assert len(dedup_detections(stones)) == 1

    def test_overlapping_pair_two_grid_cells_apart_is_found(self):
        from katrain.vision.stone_detector import dedup_detections

        # dx = 32: IoMin 0.36. With the old grid cell (0.5 * 50 = 25 px) x=99 and x=131 fall in buckets
        # 3 and 5 — outside the 3x3 scan — so a cell that was not widened silently misses this pair.
        out = dedup_detections([_rect(99, 100, 0, 0.9, 50, 50), _rect(131, 100, 0, 0.8, 50, 50)])
        assert len(out) == 1

    def test_zero_area_box_never_takes_part(self):
        from katrain.vision.stone_detector import dedup_detections

        # Zero height: mean side is still 25, so keep the partner beyond the old radius (0.5 * 25 = 12.5 px).
        flat = Detection(x_center=120, y_center=100, class_id=0, confidence=0.9, bbox=(95.0, 100.0, 145.0, 100.0))
        assert len(dedup_detections([flat, _rect(140, 100, 0, 0.8, 50, 50)])) == 2
```

再把 `TestDedupVectorisationIsEquivalent` 的类文档字符串第一句改为 `"""dedup_detections' clash test runs over a spatial grid; this pins it against a scalar O(k^2) reference."""`（其余段落保留），并把 `_reference_dedup` 整个替换成：

```python
    @staticmethod
    def _reference_dedup(detections):
        """Scalar reference of the CURRENT rule (centre distance, plus the stone-only overlap clause),
        written independently of the module's helpers."""
        import math

        from katrain.vision.classes import STONE_CLASS_IDS
        from katrain.vision.stone_detector import DEDUP_MAX_SIDE_RATIO, DEDUP_OVERLAP_MIN

        def overlap_of_smaller(a, b):
            area_a = (a[2] - a[0]) * (a[3] - a[1])
            area_b = (b[2] - b[0]) * (b[3] - b[1])
            if min(area_a, area_b) <= 0:
                return 0.0
            w = min(a[2], b[2]) - max(a[0], b[0])
            h = min(a[3], b[3]) - max(a[1], b[1])
            return max(0.0, w) * max(0.0, h) / min(area_a, area_b)

        kept = []
        for det in sorted(detections, key=lambda d: -d.confidence):
            d_side = (det.bbox[2] - det.bbox[0] + det.bbox[3] - det.bbox[1]) / 2.0
            is_dup = False
            for other in kept:
                if (det.class_id in STONE_CLASS_IDS) != (other.class_id in STONE_CLASS_IDS):
                    continue
                if det.class_id not in STONE_CLASS_IDS and det.class_id != other.class_id:
                    continue
                o_side = (other.bbox[2] - other.bbox[0] + other.bbox[3] - other.bbox[1]) / 2.0
                min_side = min(d_side, o_side)
                if min_side <= 0:
                    continue
                if math.hypot(det.x_center - other.x_center, det.y_center - other.y_center) < 0.5 * min_side:
                    is_dup = True
                    break
                if (
                    det.class_id in STONE_CLASS_IDS
                    and max(d_side, o_side) <= DEDUP_MAX_SIDE_RATIO * min_side
                    and overlap_of_smaller(det.bbox, other.bbox) >= DEDUP_OVERLAP_MIN
                ):
                    is_dup = True
                    break
            if not is_dup:
                kept.append(det)
        return kept
```

最后在 `test_clustered_stones_match_reference` 之后追加一个专门让新条款在网格边界上起作用的差分用例：

```python
    def test_overlap_clause_across_grid_cells_matches_reference(self):
        """Pairs 26-36 px apart with ~50 px boxes: only the overlap clause can merge them (the centre-distance
        radius is ~25 px), and with a grid cell sized for that radius about a fifth of them land two cells
        apart -- outside the 3x3 scan. This is what a grid cell that was not widened gets wrong."""
        from katrain.vision.stone_detector import dedup_detections

        rng = np.random.default_rng(11)
        dets = []
        for _ in range(40):
            x = float(rng.integers(0, 600))
            y = float(rng.integers(0, 600))
            for dx, dy in ((0.0, 0.0), (float(rng.integers(26, 37)), float(rng.integers(-4, 5)))):
                side = float(rng.integers(46, 55))
                dets.append(
                    Detection(
                        x_center=x + dx,
                        y_center=y + dy,
                        class_id=int(rng.integers(0, 2)),
                        confidence=float(rng.integers(1, 9)) / 10.0,
                        bbox=(x + dx - side / 2, y + dy - side / 2, x + dx + side / 2, y + dy + side / 2),
                    )
                )
        assert [id(d) for d in dedup_detections(dets)] == [id(d) for d in self._reference_dedup(dets)]
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `CI=true uv run pytest tests/test_vision/test_stone_detector.py -q --color=no`
Expected: FAIL —— `TestDedupVectorisationIsEquivalent` 的各条在运行时报 `ImportError: cannot import name 'DEDUP_MAX_SIDE_RATIO'`（参考实现在函数体内 import 常量）；`TestShadowDuplicateDedup` 里 `test_shadow_box_of_a_stone_is_merged_into_it`、`test_black_shadow_beside_a_white_stone_is_merged`、`test_overlap_threshold_boundary`、`test_side_ratio_boundary`、`test_led_boxes_keep_the_centre_distance_rule`（stones 那半）、`test_overlapping_pair_two_grid_cells_apart_is_found` 失败。`test_the_closest_real_neighbours_on_the_board_are_kept`、`test_big_box_does_not_swallow_the_stones_under_it`、`test_zero_area_box_never_takes_part` 在旧代码上就通过（它们守的是「不许多合并」）。

- [ ] **Step 3: 实现**

在 `katrain/vision/stone_detector.py` 中 `def dedup_detections` 之前插入：

```python
# Shadow duplicates (RK3562 daylight game, 2026-09-23): side light makes the model box a stone together
# with its shadow a second time, centred 0.56-0.75 cells off the stone -- outside the centre-distance
# radius used below -- and that box then became a phantom on the neighbouring point (H5: 16 prompts in
# one game). Labelled against the game record on 12 board frames, two REAL stones' boxes overlap at
# most 0.233 of the smaller box (J2+J3; boxes are ~1.1 cells wide), while every shadow box that could
# become a phantom overlaps its stone by >= 0.326. See
# superpowers/tracks/vision-optimizations/shadow-dedup/design.md.
DEDUP_OVERLAP_MIN = 0.27
# ...but only between boxes of similar size: the overlap is measured against the SMALLER box, so a hand
# misread as one big box would otherwise swallow every stone under it. Measured: shadow pairs <= 1.58,
# neighbouring real stones <= 1.21.
DEDUP_MAX_SIDE_RATIO = 2.0


def _overlap_of_smaller(a: tuple, b: tuple) -> float:
    """Intersection area of two (x1, y1, x2, y2) boxes over the smaller box's area; 0.0 when either has none."""
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    smaller = area_a if area_a < area_b else area_b
    if smaller <= 0:
        return 0.0
    w = min(a[2], b[2]) - max(a[0], b[0])
    if w <= 0:
        return 0.0
    h = min(a[3], b[3]) - max(a[1], b[1])
    if h <= 0:
        return 0.0
    return w * h / smaller
```

把 `dedup_detections` 的文档字符串第一段改为：

```python
    """Suppress duplicate boxes that NMS misses. Two detections are the same object when their centres
    are closer than half the smaller box's mean side (size-variant boxes on one stone -- a tight box
    nested in a loose one -- can have mutual IoU below the NMS threshold), or, for two STONE boxes of
    similar size (larger mean side <= DEDUP_MAX_SIDE_RATIO x smaller), when they overlap by at least
    DEDUP_OVERLAP_MIN of the smaller box (a stone boxed a second time together with its shadow).
    Keep the higher confidence.
```

其后几段（Grouping / bbox-less / greedy scan 的说明）保留；把讲网格边长的那一段替换为：

```python
    Grid cell = the larger of ``0.5 * max_side`` (the centre-distance radius bound) and the largest box
    width/height in the batch (two boxes can only intersect while their centres are closer than that),
    so every pair either rule can merge lands in the same or an adjacent cell and the 3x3 scan never
    misses one. The result is identical to the scalar O(k^2) scan, not merely equivalent.
    """
```

函数体里把：

```python
    cell = 0.5 * max_side
```

替换为：

```python
    max_extent = max(
        max(d.bbox[2] - d.bbox[0], d.bbox[3] - d.bbox[1]) for d, s in zip(dets, sides) if s > 0
    )
    cell = max(0.5 * max_side, max_extent)
```

把内层判定：

```python
                    if math.hypot(det.x_center - other.x_center, det.y_center - other.y_center) < 0.5 * min_side:
                        is_dup = True
                        break
```

替换为：

```python
                    if math.hypot(det.x_center - other.x_center, det.y_center - other.y_center) < 0.5 * min_side:
                        is_dup = True
                        break
                    if det_is_stone:
                        max_pair_side = d_side if d_side > sides[j] else sides[j]
                        if (
                            max_pair_side <= DEDUP_MAX_SIDE_RATIO * min_side
                            and _overlap_of_smaller(det.bbox, other.bbox) >= DEDUP_OVERLAP_MIN
                        ):
                            is_dup = True
                            break
```

（`det_is_stone` 已在循环上方定义；走到这里时 `other` 与 `det` 同组，所以 `det_is_stone` 为真即两个都是棋子类。）

- [ ] **Step 4: 跑测试，确认通过**

Run: `CI=true uv run pytest tests/test_vision/test_stone_detector.py -q --color=no`
Expected: 全部 PASS。

- [ ] **Step 5: 全量视觉测试 + 格式**

```bash
uv run black -l 120 katrain/vision/stone_detector.py tests/test_vision/test_stone_detector.py
CI=true uv run pytest tests/test_vision -q --color=no -p no:cacheprovider 2>&1 | tail -3
```

Expected: 基线 840 passed；现在应为 **850 passed**（本任务新增 10 条），0 failed。任何原有用例变红都要报告，不许改原有断言让它变绿。

- [ ] **Step 6: 变异检查（每一条新测试都要能红）**

先由主会话提交本任务（见 Global Constraints：本任务的提交由主会话做；实现者在这一步之前停下，报告「可以提交」）。提交之后逐条做下列改动、跑、记录、用 `git checkout -- katrain/vision/stone_detector.py` 还原（此时文件已提交，还原不会丢工作）：

| 改动 | 必须变红的测试 |
|---|---|
| `DEDUP_OVERLAP_MIN = 1.01` | `test_shadow_box_of_a_stone_is_merged_into_it`、`test_black_shadow_beside_a_white_stone_is_merged`、`test_overlap_threshold_boundary` |
| `DEDUP_OVERLAP_MIN = 0.25` | `test_overlap_threshold_boundary`（dx=37 那对会被合并） |
| `DEDUP_OVERLAP_MIN = 0.22` | `test_the_closest_real_neighbours_on_the_board_are_kept` |
| `DEDUP_MAX_SIDE_RATIO = 10.0` | `test_big_box_does_not_swallow_the_stones_under_it`、`test_side_ratio_boundary` |
| 删掉 `if det_is_stone:` 这一层（新条款对 LED 也生效） | `test_led_boxes_keep_the_centre_distance_rule` |
| `cell = 0.5 * max_side` | `test_overlapping_pair_two_grid_cells_apart_is_found`、`test_overlap_clause_across_grid_cells_matches_reference` |

每次用 `CI=true uv run pytest tests/test_vision/test_stone_detector.py -q --color=no 2>&1 | grep -E "^FAILED|passed|failed"` 读结果，把「改动 → 变红的测试名」原样写进报告。任何一行没有按表变红，就是测试没有守住它声称守住的东西，要修测试而不是修表。

---

### Task 3: 端到端回归 —— 从真实框到盘面

**Files:**
- Create: `tests/test_vision/test_shadow_phantom.py`
- 已存在（主会话在 spec 提交里放好，不改）：`tests/test_vision/data/shadow_dedup_20260923.json`（两帧 warped_06 / warped_09 的去重前原始框、真值盘面、视差参数）

**Interfaces:**
- Consumes: Task 2 改过的 `dedup_detections`；`BoardStateExtractor(config, parallax=...)`、`.detections_to_board(dets, img_w, img_h, occupancy_aware=True, add_threshold=0.40, prev_board=..., sticky_board=...)`、`.cell_top(dets, img_w, img_h) -> {(row, col): (conf, class_id)}`、`.parallax_points(dets, img_w, img_h) -> [(fy_raw, fx_raw, fy, fx, cls, conf)]`；`ParallaxParams(nadir_fx, nadir_fy, k)`；`BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS)`。
- Produces: 无（纯测试）。

- [ ] **Step 1: 写测试**

```python
"""End-to-end: shadow duplicate boxes from the RK3562 daylight game (2026-09-23) must not reach the board.

Geometry is the deployed go4_s.rknn's own output on that board, run through the live board-state path
(parallax on, occupancy-aware assignment, sticky). See
superpowers/tracks/vision-optimizations/shadow-dedup/design.md §1 for how H5 became a self-sustaining
phantom and D7 a sub-threshold prompt.
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
    return Detection(x_center=x, y_center=y, class_id=0, confidence=conf, bbox=(x - 24.95, y - 25.55, x + 24.95, y + 25.55))


FRAME1_SHADOW = _shadow(388.82, 775.63)
FRAME2_SHADOW = _shadow(387.02, 776.69)


def _extractor():
    return BoardStateExtractor(BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS), parallax=ParallaxParams(**FIXTURE["parallax"]))


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


def test_the_h5_chain_reproduces_without_dedup():
    """Precondition: the fixture really drives the live phantom path. If this goes red, the assignment code
    changed and the tests below no longer prove anything about shadows."""
    ex = _extractor()
    b1 = _board(ex, [G5_STONE, FRAME1_SHADOW])
    b2 = _board(ex, [G5_STONE, FRAME2_SHADOW], prev=b1)
    assert b1[H5] == 1 and b2[H5] == 1
    assert b1[G5] == 1 and b2[G5] == 1


def test_dedup_breaks_the_h5_chain():
    ex = _extractor()
    b1 = _board(ex, dedup_detections([G5_STONE, FRAME1_SHADOW]))
    b2 = _board(ex, dedup_detections([G5_STONE, FRAME2_SHADOW]), prev=b1)
    assert b1[H5] == 0 and b2[H5] == 0
    assert b1[G5] == 1 and b2[G5] == 1


def test_shadow_outscoring_its_stone_still_lands_on_the_stone():
    ex = _extractor()
    stone = dataclasses.replace(G5_STONE, confidence=0.45)
    shadow = dataclasses.replace(FRAME2_SHADOW, confidence=0.50)
    kept = dedup_detections([stone, shadow])
    assert kept == [shadow]  # the higher confidence wins, as before
    b = _board(ex, kept)
    assert b[G5] == 1 and b[H5] == 0


def test_sub_threshold_shadow_no_longer_reaches_an_empty_point():
    """The D7 path: a shadow box below the add threshold (0.32, as logged for D7) that rounds onto an EMPTY
    point is a cell_top candidate for the ambiguous-move prompt. In warped_09 the box beside C8 does this."""
    ex = _extractor()
    raw = _frame("warped_09.jpg")
    hits = _empty_points_hit(ex, raw)
    assert hits == {(10, 2)}  # precondition: C9, and only C9, before dedup
    shadow = next(
        d
        for d in raw
        if d.class_id in STONE_CLASS_IDS
        and (int(round(ex.parallax_points([d], IMG, IMG)[0][2])), int(round(ex.parallax_points([d], IMG, IMG)[0][3])))
        == (10, 2)
    )
    raw = [dataclasses.replace(d, confidence=0.32) if d is shadow else d for d in raw]
    keep_tier = [d for d in raw if d.confidence >= 0.30]
    assert (10, 2) in ex.cell_top(keep_tier, IMG, IMG)  # precondition: the prompt path would see it
    kept = [d for d in dedup_detections(raw) if d.confidence >= 0.30]
    assert (10, 2) not in ex.cell_top(kept, IMG, IMG)


@pytest.mark.parametrize("name, missed", [("warped_06.jpg", set()), ("warped_09.jpg", {(5, 2)})])
def test_real_frames_lose_no_stone_and_reach_no_empty_point(name, missed):
    """Whole frames: after dedup, the board equals the truth except the one stone the detector itself missed
    in warped_09 (C14), and no stone box rounds onto an empty point."""
    ex = _extractor()
    kept = dedup_detections(_frame(name))
    assert _empty_points_hit(ex, kept) == set()
    board = _board(ex, [d for d in kept if d.confidence >= 0.30])
    diff = {(r, c) for r in range(19) for c in range(19) if board[r][c] != TRUTH[r][c]}
    assert diff == missed
```

- [ ] **Step 2: 跑测试**

Run: `CI=true uv run pytest tests/test_vision/test_shadow_phantom.py -q --color=no`
Expected: 全部 PASS（Task 2 已合入）。

- [ ] **Step 3: 在 Task 2 之前的代码上确认它们会红**

主会话提供 Task 2 之前的提交号 `<BASE>`（即本计划 spec 提交）。用临时 worktree，**不许**在共用工作树上 checkout：

```bash
git worktree add /tmp/shadow-base <BASE>
cp tests/test_vision/test_shadow_phantom.py /tmp/shadow-base/tests/test_vision/
(cd /tmp/shadow-base && CI=true uv run pytest tests/test_vision/test_shadow_phantom.py -q --color=no 2>&1 | grep -E "^FAILED|passed|failed")
git worktree remove --force /tmp/shadow-base
```

Expected: `test_the_h5_chain_reproduces_without_dedup` 与 `test_real_frames_lose_no_stone_and_reach_no_empty_point[warped_06.jpg-...]` PASS；`test_dedup_breaks_the_h5_chain`、`test_shadow_outscoring_its_stone_still_lands_on_the_stone`、`test_sub_threshold_shadow_no_longer_reaches_an_empty_point`、`test_real_frames_lose_no_stone_and_reach_no_empty_point[warped_09.jpg-...]` FAIL（4 failed, 2 passed）。把这段输出原样写进报告。若 worktree 里 `uv run` 缺依赖（fastapi 等），先 `uv sync --extra web` 再跑。

- [ ] **Step 4: 全量视觉测试 + 格式**

```bash
uv run black -l 120 tests/test_vision/test_shadow_phantom.py
CI=true uv run pytest tests/test_vision -q --color=no -p no:cacheprovider 2>&1 | tail -3
```

Expected: **856 passed**（Task 2 后的 850 + 本任务 6 条），0 failed。

报告「可以提交」，由主会话提交。

---

### Task 4: 文档收口

**Files:**
- Modify: `superpowers/tracks/vision-optimizations/README.md`（「一帧怎么走」表第 5 行；「历次优化」表追加一行）
- Modify: `superpowers/tracks/vision-optimizations/shadow-dedup/design.md`（文首加状态行）

**Interfaces:** 无代码。

- [ ] **Step 1: README 第 5 行**

把 `| 5 | YOLO（RKNN）检测 | \`stone_detector.py\` | 黑 / 白 / 红灯 / 绿灯 |` 改为：

```markdown
| 5 | YOLO（RKNN）检测 + 去重（中心距 < 半个边长，或棋子框互压 ≥ 0.27 且大小相近） | `stone_detector.py` | 黑 / 白 / 红灯 / 绿灯；IoMin 0.27、边长比 ≤ 2 |
```

- [ ] **Step 2: 「历次优化」表追加一行**（放在表的最后一行之后，格式照抄上面几行）

```markdown
| 2026-09-23 | 去重追加「棋子框互压 ≥ 0.27（交叠 ÷ 较小框）」 | 侧光下「子 + 影子」被再框一次，偏出半格，逃过旧的中心距去重，经视差 + 粘滞在邻点（H5）自我维持成假子；低于门槛的则升级成疑似落子卡片（D7） | 待上板 | [shadow-dedup/design.md](shadow-dedup/design.md)、[validation.md](shadow-dedup/validation.md) |
```

- [ ] **Step 3: design.md 文首状态行**

在标题下一行插入：`状态：已实现（Task 2/3），标注集验证 <PASS|FAIL，照抄 validation.md 的 VERDICT>，待 RK3562 侧光局复测。`

- [ ] **Step 4: 报告「可以提交」**

---

## 完成后的动作（不在任务内，由主会话执行）

1. opus 按 code-review 技能审整个分支，改到通过。
2. **上板前征得 Fan 同意**（katrain 此刻是停着的，板上在跑象棋；切回围棋是他的操作）。部署只动一个运行时文件：`katrain/vision/stone_detector.py`（按 `reference_rk3562_katrain_deploy_recipe` 备份 → rsync → `systemctl restart smartbox-katrain`），前端不用重建。
3. 侧光时段下一盘：用 `evidence-2026-09-23-daylight-game/summarize.py` 统计疑似落子卡片数（对照：上一局 111 手 19 次），并打开 vtrace 看 `det[... post=]` 的中位数不比上一局（8–9 ms）高出 3 ms 以上。
4. 通知五子棋 session（`smartbox-software-gomoku-features-d4`）：规则已落地、常量名与值。
5. 合 develop、push，bump smartbox `vendor/katrain`（只 `git add -- vendor/katrain`）。

## 明确不做（本轮）

见 spec §6：弹窗改造与「不是落子」、参照帧三处缺口、孤立假框（A15 类）、影子框反超且越界的已知限制。
