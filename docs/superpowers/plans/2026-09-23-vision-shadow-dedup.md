# 影子重复框去重 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `dedup_detections` 把「棋子 + 它的影子」这种偏出半格的重复框认作同一颗子，从源头消掉侧光下的假子（H5 自我维持的假黑子、D7 低置信疑似落子卡片）。

**Architecture:** 在现有「中心距 < 0.5 × 较小边长」规则之外，对两个棋子类框追加一条「交叠面积 ÷ 较小框面积 ≥ 0.27，且两框边长比 ≤ 2」的合并条款；只加不减，LED 框不受影响。网格加速结构的格边长随之放大到「最大框宽/高 + 2 × 框心偏离 bbox 中点的最大值」，并由对比 O(k²) 参考实现的差分测试保证逐对象一致。落地（合 develop、上板）前用 209 张带真值的标注图复核门槛：板上用部署模型导出去重前的框，本机用**分支上的真代码**与基线代码对比。

**Tech Stack:** Python 3.11、numpy、OpenCV、pytest（`uv run`）；RK3562 上的 RKNN 推理（`go4_s.rknn`）；ssh 到 `rk3562-direct` 与 `home-ubuntu`。

**Spec:** `superpowers/tracks/vision-optimizations/shadow-dedup/design.md`（必读；数字、根因、复现坐标都在里面）

## Global Constraints

- 阈值常量，名字和值都固定：`DEDUP_OVERLAP_MIN = 0.27`、`DEDUP_MAX_SIDE_RATIO = 2.0`，定义在 `katrain/vision/stone_detector.py` 模块级。
- 新条款**只作用于两个棋子类框**（`STONE_CLASS_IDS`，黑白之间也算）；LED 类（`led_red` / `led_green`）只按旧的中心距规则、只在同类内去重。
- 判定条件是旧规则的**超集**：旧规则的判定代码原样保留，新条款只在它之后追加。但贪心扫描的**输出**不单调：旧规则下被 B 吞掉的 C，在 B 自己被新条款并进 A 之后会重新活下来（spec §3 有例子）。代码和注释里不许写「不会让被合并的框复活」；真实数据上的复活数由 Task 1B 的闸统计。
- `dedup_detections(detections: list[Detection]) -> list[Detection]` 与 `Detection` 数据类的签名、字段**不许改**（五子棋 session 钉了这两个）。
- 输出必须与同语义的 O(k²) 标量参考实现**逐对象、逐顺序一致**（`id()` 比较），网格只是加速。
- 旧规则下「没有 bbox（全 0）或平均边长 ≤ 0」的检测永不参与去重 —— 新条款同样不许让它们参与。面积为 0 但平均边长 > 0 的框（例如高为 0）照旧参与中心距规则，只是不参与新条款（没有面积就没有重叠比例）。
- Python 用 Black，120 列：`uv run black -l 120 <file>`。
- 测试命令一律带 `--color=no`（变异检查要解析输出；带颜色时 `startswith("FAILED")` 匹配不到任何东西）。
- 板子（RK3562，2 GB 内存）只由主会话操作，子代理不 ssh 板子。板上一次只跑一件事：动板子之前 `pgrep -af "board_detect_dump|pytest"` 必须为空。
- 共用工作树：**并行的任务不许 `git commit`，也不许 `git checkout`/`git stash`**，除非任务里明确写了；提交由执行本计划的主会话在每个任务审过之后统一做，且只用 `git add -- <该任务列出的路径>`，不许 `git add -A` / `commit -a`（并行任务的未提交文件就在同一棵树里）。
- 变异检查要把常量改成等长的值（`0.27`→`0.25`）再还原。若还原与改动落在同一秒，源文件的 mtime 和大小都与变异版相同，Python 会继续用变异版的 `.pyc`：源码写着 0.27，跑的却是 0.25，结果全错且看不出来（修订本计划时在原型上实际踩到过：整帧测试因此丢了 J2/J3）。所以变异检查开始前删掉 `__pycache__`，整个过程都带 `PYTHONDONTWRITEBYTECODE=1`。

## Review Focus

1. **一只手搭在盘上被读成一个大框**（边长是棋子的 3 倍、置信度更高）：新条款不许吞掉它下面的真子（离大框中心不到 0.5 × 较小边长的，仍由旧的中心距规则合并，行为不变）—— Task 2 `test_big_box_does_not_swallow_neighbouring_stones_by_overlap`。
2. **两颗相邻真子放得歪、框互压得比 J2/J3（0.233）还多**：只要 IoMin < 0.27 就都保留。门槛正好 0.27、边长比正好 2.0 这两点都有用例（把 `>=`/`<=` 写成 `>`/`<` 会变红）—— Task 2 `test_overlap_threshold_boundary`、`test_side_ratio_boundary`；真实分布由 Task 1B 的标注集闸复核。
3. **两盏相邻的 LED 同时亮**：LED 框互压到 0.28 也不许合并 —— Task 2 `test_led_boxes_keep_the_centre_distance_rule`。
4. **影子框的置信度反超真子**（实测从未发生：会成假子的影子框没有一个比它的子分高）：在第 2 帧位置（校正后第 6.467 列），保留下来的影子框仍落在 G5；在第 1 帧位置（6.5006 列），子会被挪到 H5。后者是已知限制（spec §6），用 `xfail(strict=True)` 钉住：将来谁修好了它，这条会变红，提醒去掉标记 —— Task 3 `test_shadow_outscoring_its_stone_still_lands_on_the_stone[frame2|frame1]`。
5. **低于落子门槛的影子框（D7 那条路）**：去重后 `cell_top` 在空点上不再有候选，疑似落子卡片无从升级 —— Task 3 `test_sub_threshold_shadow_no_longer_reaches_an_empty_point`。
6. **闸量的是不是真代码**：Task 1B 里的「新」是分支上的 `dedup_detections`，「旧」是基线提交里的同一个函数，不是脚本自带的规则副本；标签与框一对一匹配，逐个标注比，不比总数。PASS / FAIL / INVALID / 复活这四条分支，修计划时都实际触发过。
7. **框心不在 bbox 中点**：四个后端都输出中点，但 `Detection` 不强制这一点；网格边长加上了偏离量，差分测试 `[40]` 那一格专门守这件事。

---

## 并行关系

- **Task 1A**（主会话：拉标注集，在板上导出去重前的原始框）与 **Task 2**（子代理：改规则 + 单元测试）**同时开工**，互不依赖。
- Task 2 审过、主会话提交之后：**Task 1B**（测量闸，测的是分支上的真代码）与 **Task 3**（端到端回归）并行，两者不碰同一个文件。
- **Task 4** 在 1B 为 `PASS` 且 Task 3 通过后做。1B 为 `FAIL` 或 `INVALID` 时停在 Task 4 之前：不合 develop、不上板，把数报给 Fan；Task 2/3 的提交留在特性分支上等他定（特性分支上的提交不算落地）。

---

### Task 1A: 导出标注集的原始框（主会话做，要动板子）

**不派子代理**：要 ssh 两台机器，其中板子只有 2 GB 内存，上面还跑着服务。

**Interfaces:**
- Consumes: 板上 `/opt/smartbox/share/katrain-vision/go4_s.rknn`、`/opt/smartbox/venv-katrain/bin/python`、`/root/smartbox-software/vendor/katrain`（板上代码，只借它的推理后端）；home-ubuntu 的 `/home/fan/Repositories/katrain/data/go4_split/{images,labels}/{train,val}/`（1056×1056 JPEG，YOLO 归一化标签 `cls cx cy w h`，类 0=black 1=white 2=led_red 3=led_green）。
- Produces: `$SCR/dets_labelled.json`（209 个键）与 `$SCR/labels/`；把 `$SCR` 的路径交给 Task 1B。

- [ ] **Step 1: 拉数据到本机临时目录**

```bash
SCR=$(mktemp -d /tmp/shadow-labelled.XXXX); echo $SCR
rsync -az -e "ssh -o BatchMode=yes" home-ubuntu:/home/fan/Repositories/katrain/data/go4_split/images/ $SCR/images/
rsync -az -e "ssh -o BatchMode=yes" home-ubuntu:/home/fan/Repositories/katrain/data/go4_split/labels/ $SCR/labels/
find $SCR/images -name '*.jpg' | wc -l      # 期望 209
find $SCR/labels -name '*.txt' | wc -l      # 期望 209
```

- [ ] **Step 2: 在板上跑部署模型（导出去重前的全部框）**

先查板子：

```bash
ssh rk3562-direct 'pgrep -af "board_detect_dump|pytest"; free -m | sed -n 2p; df -m /root | tail -1'
```

第一行必须为空（有别的会话在板上跑测试就等它跑完）；`available` ≥ 400；`/root` 所在分区可用 ≥ 500 MB。任一条不满足就停。

```bash
R=$(ssh rk3562-direct 'mktemp -d /root/shadow-probe.XXXXXX'); echo "$R"   # 必须形如 /root/shadow-probe.ab12cd，否则停
mkdir -p $SCR/flat && find $SCR/images -name '*.jpg' -exec cp {} $SCR/flat/ \;
ls $SCR/flat | wc -l      # 期望 209（train/val 文件名不重名；不是 209 就停）
rsync -a $SCR/flat/ rk3562-direct:$R/frames/
scp superpowers/tracks/vision-optimizations/evidence-2026-09-23-daylight-game/board_detect_dump.py rk3562-direct:$R/
ssh rk3562-direct "cd /root/smartbox-software/vendor/katrain && PYTHONPATH=/root/smartbox-software/vendor/katrain \
  /opt/smartbox/venv-katrain/bin/python $R/board_detect_dump.py $R/frames $R/dets_labelled.json 2>&1 | grep -vc '^[IW] RKNN'"
scp rk3562-direct:$R/dets_labelled.json $SCR/
ssh rk3562-direct "rm -rf $R"
ssh rk3562-direct 'ls -d /root/shadow-probe.* 2>/dev/null; echo end'   # 只应打印 end
```

期望：倒数第四条命令打印 209（每张图一行）。`dets_labelled.json` 的键是图片文件名，值里的 `raw` 是去重前的框列表，每个框 `{"x","y","cls","conf","bbox":[x1,y1,x2,y2]}`（同时导出的 `dedup` 是板上旧代码的去重结果，本计划不用）。中途任何一步失败，先 `ssh rk3562-direct "rm -rf $R"` 再查原因。

---

### Task 1B: 标注集验证闸（测分支上的真代码）

在 Task 2 提交之后做，与 Task 3 并行。

**Files:**
- Create: `superpowers/tracks/vision-optimizations/shadow-dedup/measure_labelled.py`
- Create: `superpowers/tracks/vision-optimizations/shadow-dedup/validation.md`

**Interfaces:**
- Consumes: 主会话给的 `$SCR`（含 `dets_labelled.json` 与 `labels/`）；工作树里已提交的 Task 2 代码（「新」）；基线提交 `98b1a67a` 里的 `katrain/vision/stone_detector.py`（「旧」，与 Task 2 之前的版本逐字相同）。
- Produces: `validation.md` 里一行 `VERDICT: PASS`、`VERDICT: FAIL` 或 `VERDICT: INVALID`，以及下列数：真子框互压 IoMin 最大值与前 10 对、新规则比旧规则多丢的标注、新规则复活的框、重复框 IoMin 直方图、最大的原始棋子框边长。

本任务**不提交**，也**不改 `katrain/` 与 `tests/` 下的任何文件**（Task 3 同时在跑）；由主会话审过后提交。

- [ ] **Step 1: 写测量脚本**

`superpowers/tracks/vision-optimizations/shadow-dedup/measure_labelled.py`：

```python
"""Shadow-dedup acceptance gate on the labelled set (design.md §5).

Measures the REAL code, not a copy of the rule: "new" is dedup_detections from the working tree on
PYTHONPATH, "old" is the same function as it was at --base. Truth stones come from the YOLO labels only.

Usage (repo root): PYTHONPATH=. python measure_labelled.py <dets.json> <labels_root> --base <sha> --expect-images N
"""
import argparse
import json
import math
import subprocess
from collections import Counter
from pathlib import Path

from katrain.vision.stone_detector import Detection, dedup_detections

IMG = 1056
PAD, CELL = 53, 949 / 18
STONE = (0, 1)
GATE_REAL_MAX = 0.25
GATE_MIN_RECALL = 0.95


def load_old(base: str):
    src = subprocess.run(
        ["git", "show", f"{base}:katrain/vision/stone_detector.py"], capture_output=True, text=True, check=True
    ).stdout
    ns = {"__name__": "stone_detector_at_base"}
    exec(compile(src, f"{base}:stone_detector.py", "exec"), ns)
    return ns["dedup_detections"]


def iomin(a, b):
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    small = min(area_a, area_b)
    if small <= 0:
        return 0.0
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h) / small


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


def match(boxes, labels):
    """One-to-one, colour-agnostic (black/white are one dedup group): nearest pairs first, each label and each
    box used at most once, only within half a label side. Returns {label index: box index}."""
    pairs = []
    for li, lab in enumerate(labels):
        for bi, d in enumerate(boxes):
            dist = math.hypot(d.x_center - lab["x"], d.y_center - lab["y"])
            if dist <= 0.5 * lab["side"]:
                pairs.append((dist, li, bi))
    out, used = {}, set()
    for _, li, bi in sorted(pairs):
        if li not in out and bi not in used:
            out[li] = bi
            used.add(bi)
    return out


def where(lab):
    return f"r{round((lab['y'] - PAD) / CELL)}c{round((lab['x'] - PAD) / CELL)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dets")
    ap.add_argument("labels_root", type=Path)
    ap.add_argument("--base", required=True)
    ap.add_argument("--expect-images", type=int, required=True)
    args = ap.parse_args()
    old_dedup = load_old(args.base)
    dets = json.load(open(args.dets))

    real_pairs, extra_best, newly_lost, revived_extra = [], [], [], []
    n_labels = seen_old = n_revived = 0
    max_extent = 0.0
    for name, fr in sorted(dets.items()):
        raw = [Detection(d["x"], d["y"], d["cls"], d["conf"], tuple(d["bbox"])) for d in fr["raw"]]
        labels = labels_for(args.labels_root, name)
        n_labels += len(labels)
        stones = [d for d in raw if d.class_id in STONE]
        for d in stones:
            max_extent = max(max_extent, d.bbox[2] - d.bbox[0], d.bbox[3] - d.bbox[1])

        own = match(stones, labels)  # label -> its real box in the raw output
        real = {bi: li for li, bi in own.items()}
        ids = sorted(real)
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                v = iomin(stones[ids[x]].bbox, stones[ids[y]].bbox)
                if v > 0:
                    real_pairs.append((v, name, where(labels[real[ids[x]]]), where(labels[real[ids[y]]])))
        for e, d in enumerate(stones):
            if e not in real:
                extra_best.append(max((iomin(d.bbox, stones[r].bbox) for r in real), default=0.0))

        kept_old = [d for d in old_dedup(raw) if d.class_id in STONE]
        kept_new = [d for d in dedup_detections(raw) if d.class_id in STONE]
        m_old, m_new = match(kept_old, labels), match(kept_new, labels)
        seen_old += len(m_old)
        newly_lost += [(name, where(labels[li])) for li in sorted(set(m_old) - set(m_new))]
        old_ids = {id(d) for d in kept_old}
        matched_new = {id(kept_new[bi]) for bi in m_new.values()}
        for d in kept_new:
            if id(d) not in old_ids:  # greedy suppression is not monotone: see design.md §3
                n_revived += 1
                if id(d) not in matched_new:
                    revived_extra.append((name, round(d.x_center), round(d.y_center), d.confidence))

    real_pairs.sort(reverse=True)
    real_max = real_pairs[0][0] if real_pairs else 0.0
    recall = seen_old / n_labels if n_labels else 0.0
    print(f"images {len(dets)} (expected {args.expect_images})  labelled stones {n_labels}  recall(old) {recall:.4f}")
    print(f"largest raw stone box side {max_extent:.1f} px")
    print(f"real-vs-real overlapping pairs {len(real_pairs)}  IoMin max {real_max:.3f}  above 0.20: "
          f"{sum(v > 0.20 for v, *_ in real_pairs)}")
    for v, name, a, b in real_pairs[:10]:
        print(f"  {v:.3f}  {name}  {a} {b}")
    bins = [0, 0.1, 0.2, 0.27, 0.3, 0.4, 0.5, 0.7, 1.01]
    hist = Counter(next(k for k in range(len(bins) - 1) if bins[k] <= v < bins[k + 1]) for v in extra_best)
    print("extra boxes, best IoMin with a real box:", {f"{bins[k]}-{bins[k+1]}": hist.get(k, 0) for k in range(len(bins) - 1)})
    print(f"labels the old rule sees but the new rule loses: {len(newly_lost)} {newly_lost[:20]}")
    print(f"boxes the new rule keeps but the old one dropped: {n_revived}, of which on no label: {len(revived_extra)} "
          f"{revived_extra[:20]}")
    valid = len(dets) == args.expect_images and recall >= GATE_MIN_RECALL
    ok = valid and real_max <= GATE_REAL_MAX and not newly_lost and not revived_extra
    verdict = "PASS" if ok else ("FAIL" if valid else "INVALID")
    print(f"VERDICT: {verdict}  (valid: images == expected and recall >= {GATE_MIN_RECALL}; pass: real max <= "
          f"{GATE_REAL_MAX}, no newly lost label, no revived box on an empty point)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 先拿板上这局的 12 帧跑一遍，确认脚本读数与 spec 一致**

这一步用的是已知答案的数据，用来发现脚本本身的错。12 帧没有 YOLO 标签，真值从 `truth_board.json` 生成临时标签（放在交叉点上、边长一格）：

```bash
EV=superpowers/tracks/vision-optimizations/evidence-2026-09-23-daylight-game
M=superpowers/tracks/vision-optimizations/shadow-dedup/measure_labelled.py
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
PYTHONPATH=. uv run python $M $SCR/dets12.json $SCR/labels12 --base 98b1a67a --expect-images 12
PYTHONPATH=. uv run python $M $SCR/dets12.json $SCR/labels12 --base 98b1a67a --expect-images 13 | tail -1
```

期望（修订计划时在原型上实际跑出来的读数）：第一次运行打印 `images 12 (expected 12)  labelled stones 1296  recall(old) 1.0000`、`largest raw stone box side 82.0 px`、`IoMin max 0.233`（前几对都是 `r17c8 r16c8`，即 J2/J3）、多丢的标注 `0`、复活的框 `0`、`VERDICT: PASS`；第二次（故意报错图数）最后一行是 `VERDICT: INVALID`。读数对不上就先修脚本，不许进 Step 3。
（另外两个分支修计划时也实际触发过，本任务不重做，因为要改源码：把 `DEDUP_OVERLAP_MIN` 改成 0.20，12 帧里多丢 12 个 J2/J3 标注、判 `FAIL`；三个 50 px 框排在 x = 100/130/150、只在 100 处有标注，复活 1 个且不在标注上、判 `FAIL`。）

- [ ] **Step 3: 跑标注集**

```bash
PYTHONPATH=. uv run python $M $SCR/dets_labelled.json $SCR/labels --base 98b1a67a --expect-images 209 | tee $SCR/report.txt
```

- [ ] **Step 4: 写 `validation.md`**

内容：日期、数据来源（home-ubuntu 路径、209 张、板上 `go4_s.rknn` sha1 `f0ece24d3659d75fa282fda099b1cecf3cbb74e4`）、「新」「旧」各是哪个提交、Step 2 的自检读数、Step 3 的完整输出（原样贴进代码块）、`VERDICT` 行原样照抄。不是 PASS 时再加一段：哪一条没过、涉及的图片名与位置，**不给修改建议**（门槛是 Fan 的决定）。

- [ ] **Step 5: 清理，报告**

```bash
rm -rf $SCR
```

报告「可以提交」，附 `VERDICT` 行。

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

        # Two 50 px squares dx apart: IoMin = (50 - dx) / 50, and dx > 25 keeps the centre rule out. dx = 36.5
        # gives 13.5 * 50 / 2500, which is exactly the double 0.27 -- so `>=` vs `>` is pinned, not approximated.
        at = dedup_detections([_rect(100, 100, 0, 0.9, 50, 50), _rect(136.5, 100, 0, 0.8, 50, 50)])
        below = dedup_detections([_rect(100, 100, 0, 0.9, 50, 50), _rect(137, 100, 0, 0.8, 50, 50)])  # 0.26
        assert len(at) == 1 and at[0].confidence == 0.9
        assert len(below) == 2

    def test_side_ratio_boundary(self):
        from katrain.vision.stone_detector import dedup_detections

        small = _rect(150, 100, 0, 0.8, 50, 50)  # centre 50 px from the big box's: the centre rule never fires
        at = dedup_detections([_rect(100, 100, 0, 0.9, 100, 100), small])  # side ratio exactly 2.0, IoMin 0.5
        above = dedup_detections([_rect(100, 100, 0, 0.9, 105, 105), small])  # 2.1, IoMin 0.55
        assert len(at) == 1
        assert len(above) == 2

    def test_big_box_does_not_swallow_neighbouring_stones_by_overlap(self):
        from katrain.vision.stone_detector import dedup_detections

        # A hand read as one big black box, 3.2x a stone, overlapping each stone by 100% of the stone. The stones
        # sit 30-40 px from its centre, outside the centre rule's 25 px (which is unchanged and still merges
        # anything closer); only the side-ratio guard keeps the overlap clause off them.
        hand = _rect(200, 200, 0, 0.9, 160, 160)
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

    def test_zero_area_box_never_merges_by_overlap(self):
        from katrain.vision.stone_detector import dedup_detections

        # Zero height, so no overlap ratio. Its mean side is still 25, so it DOES take part in the centre rule
        # (radius 12.5 px, unchanged): the partner sits 20 px away to keep that rule out of this test.
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

最后在 `test_clustered_stones_match_reference` 之后追加一个专门让新条款在网格边界上起作用的差分用例（`off_centre=40` 那一格让框心偏离 bbox 中点，守的是网格边长里的偏离量）：

```python
    @pytest.mark.parametrize("off_centre", [0, 40])
    def test_overlap_clause_across_grid_cells_matches_reference(self, off_centre):
        """Pairs 26-36 px apart with ~50 px boxes: only the overlap clause can merge them (the centre-distance
        radius is ~25 px), and with a grid cell sized for that radius many land two cells apart -- outside the
        3x3 scan. off_centre moves x_center/y_center up to 40 px away from the bbox midpoint (every backend
        emits the midpoint, but Detection does not enforce it): the grid must stay exact regardless."""
        from katrain.vision.stone_detector import dedup_detections

        rng = np.random.default_rng(11)
        dets = []
        for _ in range(40):
            x = float(rng.integers(0, 600))
            y = float(rng.integers(0, 600))
            for dx, dy in ((0.0, 0.0), (float(rng.integers(26, 37)), float(rng.integers(-4, 5)))):
                side = float(rng.integers(46, 55))
                mx, my = x + dx, y + dy  # bbox midpoint
                ox = float(rng.integers(-off_centre, off_centre + 1))
                oy = float(rng.integers(-off_centre, off_centre + 1))
                dets.append(
                    Detection(
                        x_center=mx + ox,
                        y_center=my + oy,
                        class_id=int(rng.integers(0, 2)),
                        confidence=float(rng.integers(1, 9)) / 10.0,
                        bbox=(mx - side / 2, my - side / 2, mx + side / 2, my + side / 2),
                    )
                )
        assert [id(d) for d in dedup_detections(dets)] == [id(d) for d in self._reference_dedup(dets)]
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `CI=true uv run pytest tests/test_vision/test_stone_detector.py -q --color=no`
Expected: FAIL —— `TestDedupVectorisationIsEquivalent` 的各条在运行时报 `ImportError: cannot import name 'DEDUP_MAX_SIDE_RATIO'`（参考实现在函数体内 import 常量）；`TestShadowDuplicateDedup` 里 `test_shadow_box_of_a_stone_is_merged_into_it`、`test_black_shadow_beside_a_white_stone_is_merged`、`test_overlap_threshold_boundary`（正好 0.27 那对）、`test_side_ratio_boundary`（正好 2.0 那对）、`test_led_boxes_keep_the_centre_distance_rule`（stones 那半）、`test_overlapping_pair_two_grid_cells_apart_is_found` 失败。`test_the_closest_real_neighbours_on_the_board_are_kept`、`test_big_box_does_not_swallow_neighbouring_stones_by_overlap`、`test_zero_area_box_never_merges_by_overlap` 在旧代码上就通过（它们守的是「不许多合并」）。

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
    width/height plus twice the largest centre-to-bbox-midpoint offset (two boxes can only intersect
    while their bbox midpoints are closer than the larger extent; every backend emits the midpoint as the
    centre, but Detection does not enforce it). So every pair either rule can merge lands in the same or
    an adjacent cell, the 3x3 scan never misses one, and the result is identical to the scalar O(k^2)
    scan. One oversized box widens the cell for the whole batch (``0.5 * max_side`` already did);
    accepted because detection only runs on motion-still frames.

    The overlap clause only ever ADDS merges, but the greedy output is not monotone: a box that the
    centre rule alone drops because B was kept survives once B itself is merged into A by the overlap
    clause.
    """
```

函数体里把：

```python
    cell = 0.5 * max_side
```

替换为：

```python
    boxed = [d for d, s in zip(dets, sides) if s > 0]
    max_extent = max(max(d.bbox[2] - d.bbox[0], d.bbox[3] - d.bbox[1]) for d in boxed)
    off_centre = max(
        max(abs(d.x_center - (d.bbox[0] + d.bbox[2]) / 2.0), abs(d.y_center - (d.bbox[1] + d.bbox[3]) / 2.0))
        for d in boxed
    )
    cell = max(0.5 * max_side, max_extent + 2.0 * off_centre)
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

Expected: 基线 840 passed；现在应为 **851 passed**（本任务新增 11 条：`TestShadowDuplicateDedup` 9 条 + 差分用例 2 格），0 failed。任何原有用例变红都要报告，不许改原有断言让它变绿。

- [ ] **Step 6: 变异检查（每一条新测试都要能红）**

先由主会话提交本任务（见 Global Constraints：本任务的提交由主会话做；实现者在这一步之前停下，报告「可以提交」）。提交之后先清掉字节码缓存，再逐条做下列改动、跑、记录，最后用 `git checkout -- katrain/vision/stone_detector.py` 还原（此时文件已提交，还原不会丢工作）。**整个过程都带 `PYTHONDONTWRITEBYTECODE=1`**，理由见 Global Constraints 最后一条：

```bash
find katrain tests -name __pycache__ -type d -prune -exec rm -rf {} +
# 每次改动之后：
CI=true PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_vision/test_stone_detector.py -q --color=no -p no:cacheprovider 2>&1 | grep -E "^FAILED|passed|failed"
```

| 改动 | 必须变红的测试（修订计划时在原型上实测的结果） |
|---|---|
| `DEDUP_OVERLAP_MIN = 1.01` | `test_shadow_box_of_a_stone_is_merged_into_it`、`test_black_shadow_beside_a_white_stone_is_merged`、`test_overlap_threshold_boundary`、`test_side_ratio_boundary`、`test_led_boxes_keep_the_centre_distance_rule`、`test_overlapping_pair_two_grid_cells_apart_is_found` |
| `DEDUP_OVERLAP_MIN = 0.25` | `test_overlap_threshold_boundary`（0.26 那对会被合并） |
| `DEDUP_OVERLAP_MIN = 0.22` | `test_overlap_threshold_boundary`、`test_the_closest_real_neighbours_on_the_board_are_kept` |
| `DEDUP_MAX_SIDE_RATIO = 10.0` | `test_big_box_does_not_swallow_neighbouring_stones_by_overlap`、`test_side_ratio_boundary` |
| 新条款里 `>= DEDUP_OVERLAP_MIN` 改成 `>` | `test_overlap_threshold_boundary` |
| 新条款里 `<= DEDUP_MAX_SIDE_RATIO * min_side` 改成 `<` | `test_side_ratio_boundary` |
| 删掉 `if det_is_stone:` 这一层（新条款对 LED 也生效） | `test_led_boxes_keep_the_centre_distance_rule`，以及 `test_clustered_stones_match_reference` 和一批 `test_matches_reference_on_random_inputs[...]` |
| `cell = 0.5 * max_side` | `test_overlapping_pair_two_grid_cells_apart_is_found`、`test_overlap_clause_across_grid_cells_matches_reference[0]` 与 `[40]` |
| `cell = max(0.5 * max_side, max_extent)`（去掉偏离量） | `test_overlap_clause_across_grid_cells_matches_reference[40]` |

把「改动 → 变红的测试名」原样写进报告。任何一行没有按表变红，就是测试没有守住它声称守住的东西，要修测试而不是修表。还原之后再跑一遍 Step 5，必须回到 851 passed。

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


@pytest.mark.parametrize(
    "shadow",
    [
        pytest.param(FRAME2_SHADOW, id="frame2"),
        pytest.param(
            FRAME1_SHADOW,
            id="frame1",
            marks=pytest.mark.xfail(
                strict=True,
                reason="known limitation (design.md §6): the kept shadow box is corrected past column 6.5, so the "
                "stone moves to H5. Never observed live: no phantom-capable shadow box outscored its stone.",
            ),
        ),
    ],
)
def test_shadow_outscoring_its_stone_still_lands_on_the_stone(shadow):
    ex = _extractor()
    stone = dataclasses.replace(G5_STONE, confidence=0.45)
    shadow = dataclasses.replace(shadow, confidence=0.50)
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

Run: `CI=true uv run pytest tests/test_vision/test_shadow_phantom.py -q --color=no -rxX`
Expected: `6 passed, 1 xfailed`（Task 2 已提交）；xfail 的是 `[frame1]`，原因行照 spec §6。

- [ ] **Step 3: 在 Task 2 之前的代码上确认它们会红**

`<BASE>` = `98b1a67a`（`katrain/vision/stone_detector.py` 在它与 Task 2 之前的提交里逐字相同）。用临时 worktree，**不许**在共用工作树上 checkout：

```bash
git worktree add /tmp/shadow-base <BASE>
cp tests/test_vision/test_shadow_phantom.py /tmp/shadow-base/tests/test_vision/
(cd /tmp/shadow-base && CI=true uv run pytest tests/test_vision/test_shadow_phantom.py -q --color=no 2>&1 | grep -E "^FAILED|passed|failed")
git worktree remove --force /tmp/shadow-base
```

Expected: `test_the_h5_chain_reproduces_without_dedup` 与 `test_real_frames_lose_no_stone_and_reach_no_empty_point[warped_06.jpg-...]` PASS；`test_dedup_breaks_the_h5_chain`、`test_shadow_outscoring_its_stone_still_lands_on_the_stone[frame2]`、`test_sub_threshold_shadow_no_longer_reaches_an_empty_point`、`test_real_frames_lose_no_stone_and_reach_no_empty_point[warped_09.jpg-...]` FAIL；`[frame1]` xfailed（4 failed, 2 passed, 1 xfailed，修计划时实测如此）。把这段输出原样写进报告。若 worktree 里 `uv run` 缺依赖（fastapi 等），先 `uv sync --extra web` 再跑。

- [ ] **Step 4: 全量视觉测试 + 格式**

```bash
uv run black -l 120 tests/test_vision/test_shadow_phantom.py
CI=true uv run pytest tests/test_vision -q --color=no -p no:cacheprovider 2>&1 | tail -3
```

Expected: **857 passed, 1 xfailed**（Task 2 后的 851 + 本任务 6 条 + 1 条 xfail），0 failed。

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
3. 侧光时段下一盘：用 `evidence-2026-09-23-daylight-game/summarize.py` 统计疑似落子卡片数（对照：上一局 111 手 19 次），并打开 vtrace 看去重耗时。注意 `det[pre= npu= post=]` 是后端自己的三段，**不含**去重（去重在 `StoneDetector.detect` 里、后端返回之后），去重耗时要算 `detect − pre − npu − post`。上一局基线（2323 帧）：框数 ≥ 100 的帧中位 3 ms、p95 6 ms，整帧 `total` 中位 504 ms。本机实测新代码在真实帧上是旧代码的 3 倍（0.15 → 0.45 ms），按板子慢约 11 倍折算，预计中位 5–6 ms。中位超过 9 ms，或者出现 > 60 ms 的帧，就停下来报数。
4. 通知五子棋 session（`smartbox-software-gomoku-features-d4`）：规则已落地、常量名与值。
5. 合 develop、push，bump smartbox `vendor/katrain`（只 `git add -- vendor/katrain`）。

## 明确不做（本轮）

见 spec §6：弹窗改造与「不是落子」、参照帧三处缺口、孤立假框（A15 类）、影子框反超且越界的已知限制。
