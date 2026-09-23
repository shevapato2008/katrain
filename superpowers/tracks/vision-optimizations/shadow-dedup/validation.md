# Shadow-dedup acceptance gate — labelled-set validation (Task 1B)

Date: 2026-09-23

## Data source

- Labels/images: `home-ubuntu:/home/fan/Repositories/katrain/data/go4_split/{images,labels}/{train,val}/` — 1056×1056 JPEG with YOLO-normalized labels (`cls cx cy w h`, class 0=black, 1=white, 2=led_red, 3=led_green). 209 images (train+val).
- Raw (pre-dedup) detection boxes: exported by running the deployed inference backend directly on board `rk3562-direct`, model `/opt/smartbox/share/katrain-vision/go4_s.rknn`, sha1 `f0ece24d3659d75fa282fda099b1cecf3cbb74e4`, via `board_detect_dump.py` against the 209 images copied onto the board (Task 1A). Result: `dets_labelled.json`, 209 keys, 22421 raw boxes total.
- "New" code (`dedup_detections` under test): working tree on branch `feature/vision-stone-parallax`, HEAD `acb174cd` (`fix(vision): keep a NaN y-centre out of the dedup grid`).
- "Old" code (baseline): `git show 98b1a67a:katrain/vision/stone_detector.py` — `docs(vision): shadow-dedup spec and plan, with the 2026-09-23 daylight-game evidence`, byte-identical to `dedup_detections` before Task 2's change.

## Step 2 self-check (12-frame known-answer set, `truth_board.json` fiducial labels)

Run 1 (`--expect-images 12`):

```
images 12 (expected 12)  labelled stones 1296  recall(old) 1.0000
largest raw stone box side 82.0 px
real-vs-real overlapping pairs 2758  IoMin max 0.233  above 0.20: 13
  0.233  warped_04.jpg  r17c8 r16c8
  0.229  warped_07.jpg  r17c8 r16c8
  0.225  warped_09.jpg  r17c8 r16c8
  0.225  warped_06.jpg  r16c8 r17c8
  0.222  warped_00.jpg  r16c8 r17c8
  0.215  warped_02.jpg  r17c8 r16c8
  0.215  warped_03.jpg  r17c8 r16c8
  0.213  warped_01.jpg  r17c8 r16c8
  0.213  warped_05.jpg  r17c8 r16c8
  0.212  warped_08.jpg  r15c6 r16c6
extra boxes, best IoMin with a real box: {'0-0.1': 51, '0.1-0.2': 0, '0.2-0.27': 0, '0.27-0.3': 1, '0.3-0.4': 11, '0.4-0.5': 20, '0.5-0.7': 65, '0.7-1.01': 6}
labels the new rule's merges cost: 0 []
labels that lose their correct-colour box: 0 []
boxes the new rule keeps but the old one dropped: 0, of which on no label: 0 []
VERDICT: PASS  (valid: images == expected and recall >= 0.95; pass: real max <= 0.25, no label lost or recoloured by the new merges, no revived box on an empty point)
```

Run 2 (deliberately wrong `--expect-images 13`, last line only):

```
VERDICT: INVALID  (valid: images == expected and recall >= 0.95; pass: real max <= 0.25, no label lost or recoloured by the new merges, no revived box on an empty point)
```

Both readings match the brief's expected values exactly (`images 12 ... recall(old) 1.0000`, `largest raw stone box side 82.0 px`, `IoMin max 0.233` with the top pairs at `r17c8 r16c8`, zero on merge-cost/recoloured/revived, `VERDICT: PASS`; second run `VERDICT: INVALID`). Proceeded to Step 3.

## Step 3: full 209-image labelled-set run

Command: `PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 uv run python superpowers/tracks/vision-optimizations/shadow-dedup/measure_labelled.py $SCR/dets_labelled.json $SCR/labels --base 98b1a67a --expect-images 209`

```
images 209 (expected 209)  labelled stones 21178  recall(old) 0.9997
largest raw stone box side 78.8 px
real-vs-real overlapping pairs 37079  IoMin max 0.675  above 0.20: 462
  0.675  kifu_24171_frame_146.jpg  r15c1 r15c2
  0.376  kifu_24171_frame_151.jpg  r16c6 r16c5
  0.369  kifu_24171_frame_098.jpg  r16c6 r16c5
  0.362  kifu_24171_frame_104.jpg  r16c6 r16c5
  0.355  kifu_24171_frame_136.jpg  r16c5 r16c6
  0.353  kifu_24171_frame_123.jpg  r16c6 r16c5
  0.350  kifu_24171_frame_112.jpg  r16c5 r16c6
  0.349  kifu_24171_frame_161.jpg  r16c6 r16c5
  0.349  kifu_24171_frame_149.jpg  r16c6 r16c5
  0.346  kifu_24171_frame_134.jpg  r16c6 r16c5
extra boxes, best IoMin with a real box: {'0-0.1': 84, '0.1-0.2': 5, '0.2-0.27': 0, '0.27-0.3': 0, '0.3-0.4': 0, '0.4-0.5': 0, '0.5-0.7': 834, '0.7-1.01': 111}
labels the new rule's merges cost: 45 [('kifu_24171_frame_091.jpg', 1, ['r16c5']), ('kifu_24171_frame_092.jpg', 1, ['r16c5']), ('kifu_24171_frame_093.jpg', 1, ['r16c5']), ('kifu_24171_frame_095.jpg', 1, ['r16c5']), ('kifu_24171_frame_096.jpg', 1, ['r16c5']), ('kifu_24171_frame_097.jpg', 1, ['r16c6']), ('kifu_24171_frame_098.jpg', 1, ['r16c5']), ('kifu_24171_frame_099.jpg', 1, ['r16c6']), ('kifu_24171_frame_101.jpg', 1, ['r16c5']), ('kifu_24171_frame_104.jpg', 1, ['r16c5']), ('kifu_24171_frame_106.jpg', 1, ['r16c5']), ('kifu_24171_frame_108.jpg', 1, ['r16c5']), ('kifu_24171_frame_109.jpg', 1, ['r16c5']), ('kifu_24171_frame_111.jpg', 1, ['r16c5']), ('kifu_24171_frame_112.jpg', 1, ['r16c6']), ('kifu_24171_frame_113.jpg', 1, ['r16c5']), ('kifu_24171_frame_116.jpg', 1, ['r16c5']), ('kifu_24171_frame_119.jpg', 1, ['r16c5']), ('kifu_24171_frame_121.jpg', 1, ['r16c5']), ('kifu_24171_frame_122.jpg', 1, ['r16c6'])]
labels that lose their correct-colour box: 45 [('kifu_24171_frame_091.jpg', 1, ['r16c5']), ('kifu_24171_frame_092.jpg', 1, ['r16c5']), ('kifu_24171_frame_093.jpg', 1, ['r16c5']), ('kifu_24171_frame_095.jpg', 1, ['r16c5']), ('kifu_24171_frame_096.jpg', 1, ['r16c5']), ('kifu_24171_frame_097.jpg', 1, ['r16c6']), ('kifu_24171_frame_098.jpg', 1, ['r16c5']), ('kifu_24171_frame_099.jpg', 1, ['r16c6']), ('kifu_24171_frame_101.jpg', 1, ['r16c5']), ('kifu_24171_frame_104.jpg', 1, ['r16c5']), ('kifu_24171_frame_106.jpg', 1, ['r16c5']), ('kifu_24171_frame_108.jpg', 1, ['r16c5']), ('kifu_24171_frame_109.jpg', 1, ['r16c5']), ('kifu_24171_frame_111.jpg', 1, ['r16c5']), ('kifu_24171_frame_112.jpg', 1, ['r16c6']), ('kifu_24171_frame_113.jpg', 1, ['r16c5']), ('kifu_24171_frame_116.jpg', 1, ['r16c5']), ('kifu_24171_frame_119.jpg', 1, ['r16c5']), ('kifu_24171_frame_121.jpg', 1, ['r16c5']), ('kifu_24171_frame_122.jpg', 1, ['r16c6'])]
boxes the new rule keeps but the old one dropped: 0, of which on no label: 0 []
VERDICT: FAIL  (valid: images == expected and recall >= 0.95; pass: real max <= 0.25, no label lost or recoloured by the new merges, no revived box on an empty point)
```

`VERDICT: FAIL`

## Why it's FAIL (no tuning suggestions — threshold is Fan's call)

The run is `valid` (209/209 images, recall(old) 0.9997 ≥ 0.95). Three of the four pass conditions fail:

1. **Real-vs-real IoMin max 0.675 > gate 0.25.** Two genuinely distinct stones (both present as separate YOLO labels) overlap that much in `kifu_24171_frame_146.jpg` at board positions `r15c1`/`r15c2`. A second, recurring cluster sits around 0.34–0.38 at `r16c5`/`r16c6` across many frames of the same game (`kifu_24171_frame_098`, `104`, `109`, `112`, `123`, `134`, `136`, `149`, `151`, `161`, among others — 462 pairs total exceed 0.20).
2. **45 labels cost by the new rule's merges** (`labels the new rule's merges cost: 45`) — all at board position `r16c5` or `r16c6`, spread across `kifu_24171_frame_091` through `kifu_24171_frame_122` and beyond (full list in the Step 3 output above, truncated to 20 entries by the script itself).
3. **45 labels lose their correct-colour box** (`labels that lose their correct-colour box: 45`) — the same image/position set as (2).

**Revived boxes are clean**: 0 boxes kept by the new rule but dropped by the old one, so 0 revived-on-no-label — that pass condition holds on its own.

The `r16c5`/`r16c6` cluster (items 2 and 3, identical counts and identical image list) and the `r15c1`/`r15c2` outlier driving the real-max reading are the loci; no other positions appear in the lost/recoloured lists.

## 主会话复核（2026-09-23，事实记录，不含门槛建议）

两处失败点逐一看了原图和部署模型的原始框（从 home-ubuntu 重新拉回 4 帧，在板上用同一个 `go4_s.rknn` 重跑；图在 `gate-evidence/`）：

1. **`kifu_24171_frame_146` r15c1/r15c2（IoMin 0.675）是标注造成的误读，合并本身是对的。** 那一行三颗黑子都偏在交叉点左边约 0.3 格（框心 c0.67 / c1.67 / c2.9 一带）。
   被并掉的是 c2.04 那个置信度 0.284 的框，它与 c1.67 那颗子的框互压 0.677、中心只差 0.37 格，是那颗子的重复框，旧规则同样会并掉它。
   标注 `r14.75 c1.32`（边长 43 px，比周围小一圈）没有落在任何一颗子上，于是脚本把「子 + 它的重复框」当成了两颗真子。
2. **`kifu_24171` r16c5/r16c6（IoMin 0.34–0.38，45 帧）是真的丢子。** 两颗白子贴在一起。左边那颗的检测框被拉向右边约 0.2 格：
   两框中心距 0.75 格、互压 0.38，几何上与影子框（偏 0.56–0.75 格、互压 0.326–0.44）没有区别。新规则把置信度较低的那颗真白子并掉了。
   见 `gate-evidence/kifu_24171_frame_098_dets.jpg`：红框是被并掉的，绿框是保留的。
3. 一个区分量的读数（样本很少，仅供判断方向）：只被新条款并掉的框，离最近交叉点的距离（格）——
   09-23 白天那局 12 帧（视差校正后）共 36 个影子框，最小 0.45、中位 0.55；
   kifu_24171 被误并的真白子框（3 帧，未做视差校正）是 0.04–0.08。

## 第二版：去影子一步（2026-09-23）

### 数据来源

同第一版：`$SCR/dets_labelled.json`（`$SCR=/tmp/shadow-labelled.kezv`）是板上用 `go4_s.rknn` 对 209 张标注图导出的去重前原始框；`$SCR/labels` 是配套的 YOLO 标注。

### 「旧」与「新」

- 旧：`dedup_detections`（`katrain/vision/stone_detector.py`）单独一步，不带影子处理。
- 新：`dedup_detections` 之后再加 `BoardStateExtractor.drop_shadow_boxes`（`katrain/vision/board_state.py`）。
- 两者都取自工作树 PYTHONPATH 上的代码，HEAD `51faae2a`（`feat(vision): drop a stone's shadow box after dedup, in the board state`）。

### Step 2 自检（09-23 白天那局 12 帧，`truth_board.json` 已知答案，视差校正开）

Run 1（`--expect-images 12 --parallax 19.612,9.0,0.989689`）：

```
images 12 (expected 12)  labelled stones 1296  recall(old) 1.0000
parallax on 19.612,9.0,0.989689  SHADOW_MIN_OFFSET 0.35
label-matched boxes, cells from their point: p50 0.12 p90 0.23 p99 0.34 p99.9 0.35 max 0.36  (at or above the threshold: 2)
boxes the shadow step dropped: 36, of which label-matched before: 0 []
labels the shadow step costs: 0 []
labels that lose their correct-colour box: 0 []
VERDICT: PASS  (valid: images == expected and recall >= 0.95; pass: no label lost or recoloured by the shadow step)
```

Run 2（刻意错误的 `--expect-images 13`，只取末行）：

```
VERDICT: INVALID  (valid: images == expected and recall >= 0.95; pass: no label lost or recoloured by the shadow step)
```

两次读数都与计划里记录的原型实测值一致（`images 12 ... recall(old) 1.0000`、`p50 0.12 p90 0.23 p99 0.34 p99.9 0.35 max 0.36`、`dropped 36 / label-matched before 0`、代价 0、颜色 0、`VERDICT: PASS`；第二次 `VERDICT: INVALID`）。进入 Step 3。

### Step 3：209 张标注集完整跑

命令：`PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 uv run python superpowers/tracks/vision-optimizations/shadow-dedup/measure_shadow_step.py $SCR/dets_labelled.json $SCR/labels --expect-images 209`

```
images 209 (expected 209)  labelled stones 21178  recall(old) 0.9997
parallax off  SHADOW_MIN_OFFSET 0.35
label-matched boxes, cells from their point: p50 0.18 p90 0.28 p99 0.35 p99.9 0.38 max 0.46  (at or above the threshold: 200)
boxes the shadow step dropped: 0, of which label-matched before: 0 []
labels the shadow step costs: 0 []
labels that lose their correct-colour box: 0 []
VERDICT: PASS  (valid: images == expected and recall >= 0.95; pass: no label lost or recoloured by the shadow step)
```

`VERDICT: PASS`

结果与计划里记录的原型实测值一致（`recall(old) 0.9997`、`p50 0.18 p90 0.28 p99 0.35 p99.9 0.38 max 0.46`、`dropped 0`、代价 0、颜色 0、`VERDICT: PASS`）：209 张标注图的去重后原始框里，没有一个框够远离交叉点、又和另一个框重叠到会被 `drop_shadow_boxes` 判成影子——这一步在这个标注集上零删除，因此对真子框零代价。

### 闸能变红：阈值变异读数

在临时 worktree `/tmp/shadow-gate-mut`（`git worktree add /tmp/shadow-gate-mut HEAD`，HEAD `708154c7`）里把
`katrain/vision/board_state.py` 的 `SHADOW_MIN_OFFSET` 依次改成 0.25 和 0.30，跑同一条 Step 3 命令
（`$SCR=/tmp/shadow-labelled.kezv`，未被本次操作修改）：

`SHADOW_MIN_OFFSET = 0.25`：

```
images 209 (expected 209)  labelled stones 21178  recall(old) 0.9997
parallax off  SHADOW_MIN_OFFSET 0.25
label-matched boxes, cells from their point: p50 0.18 p90 0.28 p99 0.35 p99.9 0.38 max 0.46  (at or above the threshold: 4488)
boxes the shadow step dropped: 1, of which label-matched before: 1 [('kifu_24171_frame_116.jpg', 'r16c6')]
labels the shadow step costs: 1 [('kifu_24171_frame_116.jpg', 1, ['r16c6'])]
labels that lose their correct-colour box: 1 [('kifu_24171_frame_116.jpg', 1, ['r16c6'])]
VERDICT: FAIL  (valid: images == expected and recall >= 0.95; pass: no label lost or recoloured by the shadow step)
```

`SHADOW_MIN_OFFSET = 0.30`：

```
images 209 (expected 209)  labelled stones 21178  recall(old) 0.9997
parallax off  SHADOW_MIN_OFFSET 0.3
label-matched boxes, cells from their point: p50 0.18 p90 0.28 p99 0.35 p99.9 0.38 max 0.46  (at or above the threshold: 1109)
boxes the shadow step dropped: 0, of which label-matched before: 0 []
labels the shadow step costs: 0 []
labels that lose their correct-colour box: 0 []
VERDICT: PASS  (valid: images == expected and recall >= 0.95; pass: no label lost or recoloured by the shadow step)
```

这说明 209 张图上「删 0 个、PASS」不是闸看不见：阈值放到 0.25 时它当场抓到 r16c6 这颗真子。
