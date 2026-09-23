# 棋子成像视差修正 —— 设计(vision-stone-parallax)

- 日期:2026-09-22
- 分支 / worktree:`feature/vision-stone-parallax` @ `/Users/fan/Repositories/katrain-vision-stone-parallax`,
  从 `origin/develop` `34e9c7b6` 开出
- 输入:同目录 `prd.md`(需求)、`geometry.md`(推导)、`parallax_correct.py`(参考实现)
- 行号:本文所有行号都在上面这个 develop 提交上核过。`board_state.py` / `coordinates.py` / `config.py`
  自 PRD 的基线 `7a152df1` 以来没变;`worker_inprocess.py` 变过(+59 行),下文用的是新行号。

## 0. brainstorming 里定下的事

| # | 决定 | 理由(一句) |
|---|---|---|
| D1 | 标定结果存成**独立文件** `<hardware-vision-dir>/parallax/go-19x19.json`,每块棋盘一个文件 | 视差的寿命(支架 / 棋盘 / 棋子不变就一直有效)和几何的寿命(棋盘一碰就换代)不同,不能绑在同一代里。前提是标定那一刻 warp 与印刷网格对得上 —— 由 §2.5 的网格核对保证(codex 第 2 轮) |
| D2 | 送进识别代码走**构造参数** `BoardStateExtractor(config, parallax=None)`,不进 `BoardConfig` | 只有 geometry-lock 那个 extractor 该收到它;`BoardConfig` 两个 extractor 和训练工具都在用 |
| D3 | 只在 **geometry-lock 路径**(`worker_inprocess.py` 的 `_state_extractor_locked`)上装修正;BoardFinder 路径与 `worker.py` 保持恒等 | nadir 是在 geometry-lock 的网格坐标里标定的;BoardFinder 的 warp 以棋盘外缘为基准,坐标系不同 |
| D4 | 标定工具是**板上命令行工具**,跑之前停服务 | 摄像头被 katrain 进程占着;每台盒子装机时做一次,不值得做界面 |
| D5 | 标定图案 **17 点**:9 个星位 + 4 角 + 4 边中点 | 摆子误差 1.5 mm 时,被 2–8 mm 窗口误判失败的概率 9 点 2.5%、17 点 0.4% |
| D6 | `detection_points` **保持 4 元组**;原始→修正的对照走新方法,只写进「棋盘变化」那一行日志 | 4 处生产代码按 4 元组解包;每帧每个检测都写日志会刷爆 eMMC |
| D7 | 盘外 DROP:**原始坐标或修正后坐标任一个取整落在盘外就 DROP** | 守 prd §1 第 5 条;修正关着时两者相同,逐位等于今天 |
| D8 | 本轮只做围棋;不做多记录格式、不做「每种棋子一个 k」 | 象棋 / 国象将来可能改用霍尔传感器;`apply_parallax` 本身不含棋类信息,需要时可直接复用 |

## 1. 修正插在哪

板上的识别链(全部在 `katrain/vision/`,跑在 katrain web 进程里的 `InProcessAdapter`):

```
相机帧
 → _warp_frame                     worker_inprocess.py:203-217   几何锁单应 + 1 格边距
 → FrameAverager + enhance         worker_inprocess.py:384-385
 → StoneDetector.detect            worker_inprocess.py:388       Detection.x_center / y_center(矫正图像素)
 → pixel_to_physical + continuous_grid_pos
                                   board_state.py:108-109 / :131-132   → (fx, fy)
 → 【apply_parallax】              ← 只在这里,每个检测只做一次
 → 到交点的距离:round(:110 / :239)、残差 :226、粘滞 :205、最近空点 :256、存在维持 :273、
   worker 日志诊断 worker_inprocess.py:226
```

第 5 步的所有消费方都从同两处拿坐标,所以只改那两处,下游全部自动用修正后的坐标。

**`apply_parallax` 不是幂等的**(PRD P1-1 期望 1 写了「幂等」,是笔误):调两次等于系数 k²。
所以实现上把「像素 → 原始网格坐标 → 修正后网格坐标」收进一个私有方法,`_grid_cell` 和
`detection_points` 都只经过它;下游拿到的已经是修正后的坐标,不再有第二次修正的机会。

## 2. 组件

### 2.1 `coordinates.apply_parallax(fx, fy, nadir, k)`

```python
def apply_parallax(fx, fy, nadir, k):
    if nadir is None or k is None or k == 1.0:
        return fx, fy
    return nadir[0] + (fx - nadir[0]) * k, nadir[1] + (fy - nadir[1]) * k
```

纯函数、无状态。`physical_to_grid` / `continuous_grid_pos` 一字不动。

`k == 1.0` 也直接返回原值:浮点里 `nadir + (fx − nadir) * 1.0` 不一定等于 `fx`
(`9.0 + (0.1 − 9.0)` = `0.09999999999999964`),不短路的话「k=1 时逐位相同」(P1-1 验收 1)做不到。

### 2.2 新模块:`katrain/vision/parallax.py`(数学)与 `parallax_store.py`(文件)

拆两个文件:一个纯数学、一个管磁盘,并行开发时互不改同一个文件。都不依赖摄像头。

`parallax.py`(纯 numpy):

- `ParallaxParams(nadir_fx, nadir_fy, k)`:frozen dataclass,extractor 只需要这三个数;`.nadir`、`.to_dict()`。
- `fit_parallax(points, detected, camera_height_mm) -> FitResult`:`parallax_correct.fit_from_samples`
  的移植,但**在流水线自己的网格坐标里拟合**:P = 交点 (col, row),D = 原始 (fx, fy)。
  `FitResult` 带 `k, nadir_fx, nadir_fy, m, rms_cells, max_resid_cells, worst_index, h_implied_mm, n` 与 `.params`。
  - 少于 3 点、样本共线、`|1−m|` 小到解不出 nadir,都抛 `ValueError`,不返回病态解。
  - 共线:这个 3 参数模型对共线样本**数学上并不退化**(原型实测共线一排也能解出精确的 k),
    只有全部重合才解不出。仍按 PRD P1-2 验收 3 拒收,理由是「标定要两个方向都有跨度」。
    判据用去均值后样本矩阵的秩 < 2(共线与重合都会命中)。

`parallax_store.py`(标准库):

- `ParallaxCalibration`:文件里的完整记录(见 §3),带 `.params`、`to_json_dict()`、`from_json_dict()`(校验)。
- `parallax_path(dir)`、`load_parallax(path) -> (ParallaxCalibration | None, reason)`(从不抛)、
  `save_parallax(path, calib)`(先校验,再写临时文件并 `os.replace`)。
- `H_IMPLIED_WINDOW_MM = (2.0, 8.0)`:工具与加载共用。
- `attach_parallax(vision_config, hardware_vision_dir, current_generation) -> (新 config, 日志级别, 日志文本)`:
  server 启动时调用的纯函数,单测覆盖;server 里只剩四行。
  - `camera_height_mm`(H)**只用来算 `h_implied`**,修正本身不用它。工具默认值 339.44,
    出处 `geometry.md` §3(ver9 `lens_mm` z 348.942 − 盘面 z 9.5)。这不违反「不写死 CAD 值」:
    写死的禁令针对 nadir,H 在这里只是诊断口径。

**不对 nadir 本身做合理性检查,也不写 nadir 的数值断言(无噪用例除外)。** nadir = b/(1−m),
1−m ≈ 0.0103,b 的误差被放大约 100 倍:0.3 mm 噪声下 nadir 误差 p95 = 29 mm。
但修正输出 P = k·D + (1−k)·C 里 C 的系数是 1−k,两者相消,修正残差 p95 只有 0.38 mm。
所以检查一律量修正输出与 `h_implied`,不量 nadir。标定时 warp 与棋盘的错位也不靠 nadir 合理性检查去抓
(拟合把它整个吸收,nadir 看起来完全正常),而是靠 §2.5 的印刷网格核对。

### 2.3 `BoardStateExtractor`(`board_state.py`)

- 构造:`__init__(self, config=None, parallax: ParallaxParams | None = None)`。
- 新私有方法 `_positions(det, img_w, img_h) -> (fx_raw, fy_raw, fx, fy, on_board)`:唯一调用 `apply_parallax` 的地方。
  `on_board` = 原始与修正后都取整在盘内;**盘外的检测 (fx, fy) 一律返回原始坐标**(见下面的更正)。
- `_grid_cell`:用修正后的 (fx, fy) 取整;**原始或修正任一取整出界就返回 None**(D7)。
- `detection_points`:返回值形状不变 `[(fy, fx, class_id, confidence)]`,里面是修正后的坐标。
- 新方法 `parallax_points(detections, img_w, img_h) -> [(fy_raw, fx_raw, fy, fx, class_id, confidence)]`:
  只给日志诊断用。
- `_assign_occupancy_aware`:内部改用 `_positions`(它需要原始坐标来执行 D7);残差、粘滞、
  最近空点、存在维持都用修正后的坐标。
  - **更正(2026-09-22,codex 评审 [high])**:初稿写「粘滞和存在维持都要求那格已有子,不能在空点上加子,
    所以不构成『推回盘内』」—— 这个判断漏了**移除**:用户拿走一颗边缘子后,一个原始坐标在 (9, −0.8)
    的盘外误检,修正后离 (0, 9) 只有 0.59 格(存在维持半径 0.6、粘滞半径 0.65),会把这颗已经不在的子
    一帧一帧地维持下去,移除流程永远等不到结束;基线下它离 0.8 格,当帧就消失。
    改为:**盘外(原始或修正任一出界)的检测,在所有下游(DROP、粘滞、存在维持、诊断)里都用原始坐标**,
    行为与没有修正时完全一样;修正只作用于两种坐标都在盘内的检测。由 `_positions` 一处保证。

`parallax=None` 时 `_positions` 返回 `(fx, fy, fx, fy)`,D7 两个判据相同,全部输出逐位等于今天。

### 2.4 接线

```
server.py 生命周期(:726 构造 VisionService 前,hardware_vision_dir 在 :617)
  attach_parallax(vision_config, hardware_vision_dir, 当前几何代次) → load_parallax(<dir>/parallax/go-19x19.json)
  → 成功:vision_config.parallax = {"nadir_fx":…, "nadir_fy":…, "k":…}
    打 INFO:parallax on + 棋盘 / 棋子 / k / nadir / h_implied / rms / n / fitted_at /
            标定时的几何代次 / 当前几何代次
  → 文件不存在:INFO「parallax off: not calibrated」
  → 文件无效:WARNING「parallax off: <原因>」
VisionServiceConfig.parallax: dict | None = None → to_worker_config() 带上 "parallax"
InProcessAdapter.__init__:ParallaxParams(**config["parallax"]) 只交给 _state_extractor_locked
```

- `worker.py`(子进程 / BoardFinder)与 `_state_extractor`(BoardFinder 兜底)**不接**。
- 视差不跟几何代次绑定(D1)。几何换代后参数依然有效:nadir 以网格线为锚,棋盘被碰 10 mm,
  修正结果变化不到 0.01 格(×(1−k))。标定时的几何代次只记录、只打日志,**不做开关**。
- 反过来的情形不是 ×(1−k) 而是 ×1(codex 第 2 轮 [high]):**标定那一刻** warp 与棋盘对不上(平移 t),
  拟合 D = mP + b 把 t 整个吸收进 nadir,残差为零、h 照样合理;几何一重锁,它就变成永久的
  k·(t_运行 − t_标定) ≈ t 误差。上一条只因为 §2.5 在标定前后核对了 warp 与印刷线才成立。
- 运行中不热加载。重标视差后重启服务(标定工具本来就要求先停服务)。

### 2.5 标定工具 `katrain/vision/tools/calibrate_parallax.py`

照 `live_demo_locked.py` 的写法,在板上跑,**先停 `smartbox-katrain`**:

1. 读当前几何:`HardwareVisionStateStore(<dir>).load_current(camera, w, h)`,只读。记下 `generation`。
2. 开摄像头:分辨率与**曝光策略都照服务**(几何代次里的 `profile.strategy` 是 `hardware_auto_then_lock`
   就 `lock_exposure=True, exposure=None`,AWB 不锁);要求锁曝光却 `controls_effective` 不为 True 就拒绝标定
   (codex 评审:在不同曝光下标定,会把与曝光相关的检测偏差固化进 k 与 nadir)。每帧:`adjust_M_for_resolution` → `warp_with_margin` →
   `enhance_for_inference`(与服务相同的 `--enhance`)→ `StoneDetector.detect`。
   不做 `FrameAverager`:下一步本来就对多帧取中位数。
3. **空盘网格核对(摆子前)**:采 5 帧空盘,只做 warp(不增强),逐像素取中位数,量印刷网格线相对保存的几何
   偏了多少(`grid_offset`:black-hat 取细暗线,行 / 列投影,梳状搜索 ±0.5 格定整体,逐线亚像素峰,取中位数;
   期望位置用 warp 自己的几何 `pad + i·(out_size−1)/18`)。偏 > 0.10 格(与 `GeometryDriftMonitor` 判「棋盘动了」
   同一个阈值)或 19 条线里一致的少于 15 条 → 当场拒绝,提示先重锁几何。线印在 h=0、跟棋盘一起动,
   所以这个偏移就是拟合会吸收掉的那个平移。不留绕过开关。
4. 打印 17 个标定点(D5)让操作员摆子,黑白交替。等画面静止后采 `--frames`(默认 30)帧。
   采完让操作员收掉全部子(不挪棋盘),再做一次同样的网格核对(抓摆子过程中碰动棋盘)。两次偏移都打印。
5. 每帧用 `BoardStateExtractor(BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS)).parallax_points(...)`
   取**原始**坐标,和线上完全同一套换算。按「原始坐标取整」配对到标定点。
6. 逐项检查,**任一不过就报「标定失败」和原因,不写文件**:
   - 摆子前、收子后两次网格核对都通过(没量就不算通过)
   - 每个标定点在 ≥ 80% 的帧里恰好有一个棋子检测(只看黑白两类,LED 类不算),否则点名漏摆
   - 标定点以外的交点,在 ≥ 20% 的帧里出现棋子检测 → 失败(多摆或持续误检);只出现一两帧的瞬时误检不算
   - `fit_parallax` 不抛错
   - `h_implied` ∈ [2, 8] mm(prd P1-2 验收 4)
   - 单点残差 ≤ 0.30 格(约 6.9 mm),否则点名那颗子摆歪了。阈值取 0.30 而不是更紧:摆子误差
     1.5 mm(约 0.066 格)时,17 点里至少一点超过 0.15 格的概率约 70%,超过 0.30 格约 0.05%
7. 通过:写 `parallax/go-19x19.json`(§3),打印 k、nadir、rms、h_implied、最差点。
   `--dry-run` 只打印不写。
8. 采帧(第 2–5 步)与判定写文件(第 6–7 步)拆成两个函数,判定那一半可以用合成检测与合成空盘图单测,不需要摄像头。

混叠:接近整格的偏移会读成 ≈0(0.95 格读成 −0.05),这种情况 17 点配对必然失败(每个点都换了格)。
`BoardConfig` 的 mm 映射比 warp 网格小 0.99853 倍,拟合一并吸收,对修正无害,但 `h_implied` 读数因此低约 0.5 mm。

### 2.6 诊断(P2)

- `worker_inprocess._log_board_delta`(:223)改用 `parallax_points`:每个变化格附近那条检测的描述
  从 `B0.85@0.12` 变成 `B0.85@0.12 pl0.18`,`pl` 是修正位移 \|Δ\|(格);原始坐标取整和修正后取整
  落在不同格子时再加一个 `*`,表示「被视差救回」。修正关着时 `pl0.00`、不会有 `*`。
  末尾再带原始 → 修正后的连续坐标 `(fy_raw,fx_raw)>(fy,fx)`(codex 评审:PRD P2 收窄的是频率,不是坐标)。
  今天只有「消失的格」带这段描述;**新增的格也带上**(`(1,9)B~B0.90@0.40 pl0.20* (0.40,9.00)>(0.60,9.00)`)——
  「这一手是被视差救回来的」看的正是新增的那一格。`(r,c)颜色` 这个前缀保持原样:
  vision-recognition-stability 的 §7 验收按它 grep。
- 服务启动那一行(§2.4)。
- **不动**:`ambiguous_stone` 事件结构、`worker.py`(它永远不修正)。
- 修正前后 `unbacked=True` 的对照,直接数现有日志里的 ambiguous 提示行
  (`worker_inprocess.py:525` 那条 `peak conf 0.00`),不新增字段。

## 3. 文件格式

`/var/lib/smartbox/hardware/vision/parallax/go-19x19.json`(板上;目录来自 `--hardware-vision-dir`)。
`HardwareVisionStateStore` 只读写 `generations/` 与 `current.json`,不会碰这个子目录。

```json
{
  "schema": 1,
  "board": "go-19x19",
  "stone_set": "ver9-22x7",
  "nadir_fx": 9.02, "nadir_fy": 19.58, "k": 0.98969,
  "m": 1.01042, "h_implied_mm": 3.47, "camera_height_mm": 339.44,
  "rms_cells": 0.031, "max_resid_cells": 0.07, "n_samples": 17, "n_black": 9, "n_white": 8,
  "frames": 30, "geometry_generation": "<代次>", "fitted_at": "2026-09-22T10:00:00+08:00"
}
```

`load_parallax` 的拒收条件:`schema != 1`、`board != "go-19x19"`、缺字段或多字段、任一数值非有限、
`k` 不在 (0, 1)、`camera_height_mm` ≤ 0、`m·k` 不等于 1、**`camera_height_mm·(1−k)` 与 `h_implied_mm` 不符、
由 k 重算的高度不在 [2, 8]**。高度闸必须约束**真正被使用的 k**,不能只看文件里另写的一个字段 ——
否则单独被改坏的 k 会凭一个过期的 `h_implied_mm` 过关(codex 评审)。拒收时修正关闭并给出原因,不抛到生命周期外。

`rms` 存格而不存 mm:(fx, fy) 两个方向的物理格距不同(ver9 是 23.7 / 22.0),换成 mm 要多一个
「哪个方向是长边」的假设。工具打印时附一个按平均格距 22.85 mm 换算的近似值,只供人读。

## 4. 失效方式

| 情形 | 行为 |
|---|---|
| 没标定过(文件不存在) | 修正关,INFO 一行,行为等于今天 |
| 文件坏了 / 字段非法 / 棋盘不对 | 修正关,WARNING 一行写明原因 |
| 几何漂移重标定换代 | 参数照用;启动日志里两个代次不同,属正常 |
| 有人动了摄像头杆 | **系统发现不了**,参数过期。操作规程:动杆、换棋盘、换棋子后都要重标 |
| 标定时摆子多了 / 少了 / 歪了 / h 超窗口 | 工具报失败并点名原因,不写文件,旧文件原样保留 |
| 停服务后、标定过程中棋盘被碰,或几何本来就过期(> 0.10 格) | 空盘网格核对拒绝,不写文件;先重锁几何再标 |
| 未启用 geometry lock(BoardFinder 兜底) | 那条路径本来就不装修正 |

## 5. 测试(每条对上 prd.md §3 的验收)

| 测试 | 对应验收 | 能否在基线上变红 |
|---|---|---|
| `apply_parallax`:nadir / k 为 None、k=1 是恒等;nadir 是不动点;与参考公式逐点相等 | P1-1 验收 1、4 | 新函数,基线上不存在 |
| **关着时逐位相同**:在基线提交上用 `BoardStateExtractor` 跑一套固定随机检测(含边距目标、同点碰撞、粘滞、存在维持、LED 掩码、颜色翻转),把 `_grid_cell` / `detection_points` / `detections_to_board`(两种模式)/ `cell_top` / `cell_confidences` 的输出存成金样;新代码在 `parallax=None` 与 `k=1` 两种情况下都必须逐位等于金样 | P1-1 验收 1 | 金样取自基线,改坏了关着时的行为就会变红 |
| 361 点:参考 `forward()` 造检测位置,过 `_grid_cell` 全部落回原交点 | P1-1 验收 2(健全性,基线上也全过) | 否,只作健全性检查 |
| **第 1–5 排各往远离镜头方向多偏 0.35 格**:不修正时 63/95 落到相邻交点,修正后 0/95;另一条钉住第 0 排的代价(外偏 0.3 格修正前后都 DROP) | P1-1 验收 2(区分用) | 是 |
| 边距带(远端 fy ∈ (−0.71, −0.5)、两侧 fx ∈ (−0.60, −0.5)):先断言这些点**修正后取整确实落在盘内**(前提),再断言 `_grid_cell` 返回 None、空盘上 occupancy 路径不落子 | P1-1 验收 3 | 是:如果 DROP 只看修正后坐标就会红 |
| **盘外误检不维持已移除的边缘子**(codex 反例:原始 (9, −0.8)):先断言修正后坐标够得着、原始坐标够不着(前提),再多帧跑,黑子(粘滞)与 LED 类(存在维持)两种都必须当帧消失 | P1-1 验收 3 | 是:盘外检测若带修正后坐标进入粘滞 / 存在维持就会红 |
| 单次修正:`detection_points` 的坐标等于 `apply_parallax` 恰好一次,不等于两次 | 设计 §1 | 是 |
| `fit_parallax` 无噪:k、nadir 误差 < 1e-6,`rms_cells` < 1e-9 | P1-2 验收 1 | 新函数 |
| `fit_parallax` 加 ±0.3 mm 噪声,9 点,固定种子 200 次:`h_implied` 相对误差 p95 < 20%,且全盘修正残差最大值 p95 < 1.0 mm | P1-2 验收 2(改写后) | 完全不修正时两项都是 100% / 5 mm,必红 |
| 少于 3 点、共线、m≈1 → `ValueError` | P1-2 验收 3 | 新函数 |
| 工具判定一半(合成检测):漏摆、多摆、同点两个检测、h 超窗口、单点残差过大 → 失败且**不写文件、旧文件不变**;通过 → 文件字段齐全;`--dry-run` 不写 | P1-2 验收 4 | 新代码 |
| **网格核对**(合成空盘图):对齐读 0、19/19 线;0.25 格读准并拒绝;门限两侧 (−0.12, 0.07) 拒 / (0.06, 0.05) 过;±0.45 读准;逐线 0.06 格印刷误差能过、叠加 0.25 格偏移仍拒;无网格的木纹图一律「找不到」 | codex 第 2 轮 | 新代码 |
| **codex 反例**:所有检测 fy 统一 +0.25 格 —— 先断言 `evaluate` 单独**通过**(残差 < 1e-9、h ≈ 3.5,前提:拟合看不见),再断言带着量出的网格偏移时拒绝、旧文件不变;开始对齐 / 结束偏移也拒绝;整格偏移由配对拒绝;没量网格就拒绝 | codex 第 2 轮 | 是:`decide_and_write` 忽略网格偏移就会红(变异在一次性 worktree 里做) |
| `load_parallax`:不存在 / 各种非法 / 正常 | D1 | 新代码 |
| 接线:`to_worker_config` 带 `parallax`;`InProcessAdapter` 只给 locked extractor | D2、D3 | 新代码 |
| 日志:修正开着时 board delta 行带 `pl` 与 `*`;关着时 `pl0.00`;`ambiguous_stone` 事件字段集合不变 | P2 | 字段集合那条沿用现有测试 |
| **上板**:标定一次,记 k / nadir / rms / h_implied;两套固定摆位(15–18 路 × C/G/K/O/S 共 20 手、顺序颜色写死;A 故意外偏 8 mm 复现故障,B 正常摆;每手 15 秒、四类记录、不悔棋),修正前后各跑一遍;门槛事先定死(修正前 A ≥ 5/20 出错否则证据不足;修正后 A 20/20、unbacked ≤ 一半;B 前后 20/20),见 `handoff.md` | P1-1 验收 5、P1-2 验收 4、P2 | 人工 |

测试一律用 worktree 自己的 venv(`uv sync --extra web --extra vision --extra board` 之后的
`.venv/bin/python -m pytest`)。基线:`tests/test_vision` 651 passed(2026-09-22,develop `34e9c7b6`)。
仓库里的测试不 import `superpowers/tracks/` 下的参考脚本;需要的正向模型在测试里自带一份,
常量标明是合成数据。

## 6. 不做

- 不碰 YOLO 权重、推理后端、warp / board_finder / geometry_lock / 四角检测、`physical_to_grid`。
- 不做 kiosk 标定界面、不做运行中热加载、不做多棋盘多记录、不做每种棋子一个 k。
- 不改 `worker.py`(子进程 / BoardFinder 路径)。
- 不对 nadir 做合理性检查(标定时的错位由 §2.5 网格核对抓)。

## 7. 已知代价

1. **最外一圈往盘外方向偏的棋子,容差不恢复**,仍是今天的约 6.5 mm(D7 的直接代价)。盘内各排恢复。
2. 摄像头杆被动过而没重标,系统发现不了(§4)。
3. 棋盘对位(prd §5 第 1 条)做完之后要重标一次。
4. 标定时 ≤ 0.10 格的 warp 错位网格核对看不见,会变成同样大小的永久修正误差 —— 与服务自己判「棋盘动了」的容差相同。
