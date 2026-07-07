# 评审请求：Baipu→YOLO 4-Class 自动标注与重训练计划

> **致评审者（Codex / Gemini）：** 你是一名资深的 CV/ML 工程师 + 代码评审。请评审同目录下的实施计划 **`plan.md`**，判断它在**架构、ML 方法论、正确性、测试设计、可实施性**五个维度上是否成立、是否可直接交给一名「不了解本代码库」的工程师按 TDD 逐任务实施。请带着**对抗性**视角：主动找出会导致返工、训练失败、或线上行为错误的隐患，而不是复述计划。

---

## 1. 背景：这是个什么系统

**KaTrain** 是一个围棋（Go/Baduk）教学与对弈应用，后端接 KataGo AI 引擎。其中有一条**实体棋盘（smart board / 摆谱 baipu）**产品线：一块装了**摄像头 + LED 引导灯**的物理围棋盘，部署在 RK3588 等 ARM 单板机（NPU）上。

工作流程：
- **LED 引导落子**：系统点亮某个交叉点的 LED 指示下一手该下哪、下什么颜色——**红灯引导黑棋的下一手，绿灯引导白棋的下一手**。
- **摄像头识别棋盘**：部署端 (`katrain/vision/worker.py`) 把每帧原始相机画面用单应矩阵 `M` 透视校正（warp）成一张 **950×950 的正方形棋盘图**，然后在这张 warp 后的图上跑 **YOLO11 目标检测**，再把检测框映射回 19×19 交叉点，得到棋盘状态。
- 当前检测模型只有 **2 类：`black`、`white`（黑白棋子）**。

**摆谱采集（baipu capture）**会为一盘棋落盘整套 ground truth：
- 每手一帧原始相机图 `frame_NNN.jpg`；
- 整盘棋的 **SGF 棋谱**（权威记录，含提子）；
- `manifest.json`：每帧的元数据——已落到第几手 (`applied_move_index`)、该帧点亮的引导 LED 位置与颜色 (`led_point.{row,col,color}`) 等；
- `geometry.npz`：**冻结的棋盘几何**——单应矩阵 `M`、`out_size=950`、每条网格线的像素坐标 `xs`/`ys`。

## 2. 需求：从 2 类重训练为 4 类

把检测模型从 2 类扩展为 **4 类：`black=0, white=1, led_red=2, led_green=3`**，目的有二：
1. 让模型能把**引导 LED 当作独立类别识别**，避免 LED 被误读成棋子而污染棋盘状态；
2. 为后续 LED 相关功能铺路。

**核心巧思——零人工标注**：不手工画框。利用 **SGF（每手精确的棋子位置/颜色）+ LED 元数据（每帧精确的 LED 位置/颜色）+ 冻结几何（每个交叉点在 warp 空间的精确像素坐标）**，自动合成精确的 4 类 YOLO 标注框。

**LED 颜色→类别映射（务必确认逻辑自洽）**：manifest 里 `led_point.color` 表示「**即将落子的颜色**」。`color == "black"`（下一手是黑）→ 点**红**灯 → `led_red (2)`；`color == "white"` → 点**绿**灯 → `led_green (3)`。即「红引导黑、绿引导白」。

**数据现状**：目前只有**一盘棋、一块盘、一种光照**的采集 `~/.katrain/baipu_captures/kifu_24171`，共 **212 帧（frame_000..frame_211）**，总手数 211。

## 3. 计划的架构与关键决策（详见 `plan.md`）

1. **在 warp 后的 950×950 空间标注**（与部署端 `worker.py` 喂给检测器的空间一致），**不在原始帧上标注**——避免 train/serve 空间错配。
2. **逐帧全局漂移补偿**：实测发现每帧标注误差的主因**不是棋子高度造成的视差（parallax）**，而是冻结几何网格与真实棋盘之间的**全局平移漂移**——棋盘在约第 85 手被碰了一下，平移跳变约 16px，且棋子与 LED 同步漂移（相关性 0.97）；一个「朝图像中心按 k·间距径向收缩」的视差模型被数据否决（R²≈0）。因此用**每帧一个全局 (dx,dy)** 补偿，由该帧自身的锚点（恒在的引导 LED + 无相邻子的孤立棋子）鲁棒中位数估计，并 clamp 到 `≤0.6·间距`，残差用较大的框来吸收。
3. **导出/推理链已是类别无关的**：`export_onnx` 从 `model.names` 写出 `.meta.json` sidecar，`export_rknn` 和 onnx/rknn 后端按 sidecar 动态切类别——**这部分无需改代码**，正确性只取决于训练时 `data.yaml` 的 `nc:4`。
4. **运行时守卫**：现 `board_state.py` 用 `board[...] = det.class_id + 1` 写棋盘，LED（2/3）会被写成幻影棋子（3/4）——加一行守卫跳过非棋子类。
5. **小数据集训练要点**：COCO 预训练 `yolo11n`；`imgsz=640`；**`hsv_h=0.0`**（色相是区分红/绿 LED 的唯一信号，抖动色相=污染标签）；`copy_paste` 过采样约 100:1 稀有的 LED 类；**时间序（非随机）train/val 划分**并在边界丢弃若干帧，防止相邻近重复帧泄漏到验证集。

## 4. 任务拆解（10 个任务，TDD：先写失败测试→实现→提交）

| # | 任务 | 产出 |
|---|---|---|
| 1 | 4 类单一事实源 `katrain/vision/classes.py` | `CLASS_NAMES/NAME_TO_ID/ID_TO_NAME/STONE_CLASS_IDS/LED_COLOR_TO_CLASS` |
| 2 | `board_state.py` 运行时守卫 | 跳过非棋子类检测 |
| 3 | 采集加载器 + warp 网格 + 棋盘重建 | `load_capture/warp_frame/grid_point/reconstruct_board/mean_grid_spacing` |
| 4 | 逐帧全局漂移补偿 | `detect_led_centroid/detect_isolated_stone_centroids/estimate_global_shift` |
| 5 | 4 类框生成 + YOLO 标注写出 + 校验叠加图 | `Box/frame_boxes/boxes_to_yolo_lines/draw_overlay` |
| 6 | CLI 驱动（产出 images/labels/verify） | `process_game/main` |
| 7 | 时间序划分 + 4 类 `data.yaml` | `temporal_split_dataset` + 改 `write_data_yaml` |
| 8 | `train_model.py` 的 LED-safe 增强预设 | `LED_SAFE_AUG/build_train_kwargs` |
| 9 | 训练/验证/导出 runbook（非单测） | best.pt / .onnx / .rknn + meta sidecar |
| 10 | 文档 | `katrain/vision/README.md` |

## 5. 已经被本轮 review 用真实数据核对过的事实（请勿重复核验，但欢迎挑战）

> 以下已逐条在真机数据上验证通过——你可以**质疑其判断**，但不必再花精力确认这些**事实**：

- **manifest schema**：`frames[].{file, applied_move_index, led_point.{row,col,color}}`、`board_size`、`total_moves`、`sgf_path`、`geometry_path`、`game_id` 全部存在。
- **geometry.npz**：含 `M / out_size(=950) / xs / ys`（间距≈52.72px）。
- **代码事实**：`stone_detector.py:12` 是 `CLASS_NAMES={0:"black",1:"white"}`；`Detection` 无 width/height 字段；`board_state.py:33` 是 `det.class_id + 1`；`build_steps_from_sgf(sgf)["steps"]` 与 `expected_board_from_steps(steps,k,19)` 签名一致；导出链确为类别无关。
- **magic numbers**：`build_steps_from_sgf` 得 211 步全为 `move`；`expected_board_from_steps(steps,39)`→(20 黑,20 白)；`(steps,210)`→205 子（211−6 提子）；`frame_211.jpg` 为 `final_no_led` 且 `led_point is None`。
- **已发现并已修补的一个前置坑**：Tasks 3–6 的测试 import `core.baipu`→`core.game`→`core.lang`，若未编译 i18n `.mo` 文件，会在 **pytest collection 阶段**抛 `FileNotFoundError: ...domain 'katrain'`。计划已新增前置「先 `uv run python i18n.py`」。

## 6. 请重点评审的问题（按维度）

**A. 架构判断**
- 「warp 空间标注 + 逐帧全局平移补偿」是不是对的建模？有没有更稳的漂移模型（例如逐帧重估单应、或仿射而非纯平移）？把「视差」一并否决是否过度——少量子高视差是否会在棋盘边缘系统性地影响框位？
- `clamp ≤0.6·间距` 与「用大框吸收残差」是否会在密集对杀区造成相邻交叉点的框互相覆盖、IoU 标签噪声？

**B. ML 方法论（最关心）**
- **单盘/单光照/单相机**的数据，训出来的 4 类模型泛化性如何？计划承认 val 偏乐观——但即便如此，时间序划分（首 80% 连续块训练、尾部验证、边界丢 gap）是否足以给出有意义的 LED recall？验证门槛「`led_red`/`led_green` recall ≥ 0.9」在单盘上意义多大？
- 增强选择：`hsv_h=0.0`（合理）、`copy_paste=0.4`、`mosaic=1.0`、`fliplr=0.5`、`mixup=0`、`degrees=0` ——对「稀有 LED 类 + 固定盘」的取舍是否恰当？`imgsz=640` 还是 960 更稳（LED 是小目标）？
- 框尺寸：边长 `2·0.85·间距` 再 clamp 到 `[70,150]px`——对 950 空间、间距≈52.7px 而言（→约 90px），固定框 vs. 按棋子实际半径自适应，哪个对小目标 LED 与棋子混合更好？

**C. 正确性风险**
- `estimate_global_shift` 里**硬编码的 HSV 阈值**（红 `hue<12 or >168`、绿 `40<hue<90`，`s>80,v>120`）在不同光照/不同 LED 亮度下是否脆弱？锚点全失败时返回 (0,0) 是否会让该帧标注整体偏移？
- `detect_isolated_stone_centroids` 的 HoughCircle 参数（`param2=18` 等）对镜面反光的棋子是否可靠？误检会不会把 shift 带偏（虽有中位数鲁棒化）？
- **train/serve warp 源不同**：训练用冻结的 `geometry.npz` 的 `M`，线上 `worker.py` 用实时 `board_finder` 角点。计划已列为残余风险——这个 gap 会不会大到让线上 mAP 显著掉？该不该在计划内就强制「用与线上同一条 warp 路径」？

**D. 测试设计**
- 大量测试依赖真实 fixture `~/.katrain/baipu_captures/kifu_24171`（缺失则 skip）。在 CI 上这些核心逻辑就**完全没被测**——是否应补一个**合成的最小 fixture**（造一张假 warp 图 + 假 manifest/geometry）来覆盖 box 生成与 shift 估计的纯逻辑？
- 写死的 magic numbers（(20,20)、205、6 提子）虽已对当前数据验证，但换一盘棋就会失效——测试该不该改成「从 SGF 自洽推导」而非硬编码？

**E. 完整性 / 可实施性**
- 有没有遗漏的边界：让子棋（AB/AW setup）、pass、AE 清盘（`core.baipu` 支持 `clear` step）在重建与标注里是否都被正确处理？
- 一个零上下文的工程师，能否**只靠 `plan.md`** 把 10 个任务跑通？哪一步的代码/命令/预期输出不够具体？

## 7. 期望的输出格式

请按**严重度**给出结构化结论：

- **Blocker** — 不修就无法实施 / 必然训练失败或线上错误
- **Major** — 强烈建议修，否则结果质量存疑
- **Minor / Nit** — 锦上添花

每条请给：`[严重度] 位置（plan.md 的 Task/章节 或 文件:行） — 问题 — 具体修改建议`。

最后给一个**总判定**：`可直接实施` / `小修后可实施` / `需重做某部分`，并用 1–2 句说明理由。

---

**参考文件（如可访问代码库，请直接查阅）：**
- 实施计划：`superpowers/tracks/yolo-train/plan.md`
- 核心逻辑：`katrain/core/baipu.py`（`build_steps_from_sgf` / `expected_board_from_steps`）
- 部署推理：`katrain/vision/worker.py`（warp→detect）、`katrain/vision/board_state.py`、`katrain/vision/stone_detector.py`
- 训练/数据工具：`katrain/vision/tools/{train_model,prepare_dataset,download_dataset,export_onnx,export_rknn}.py`
- 真实采集样本：`~/.katrain/baipu_captures/kifu_24171/{manifest.json,geometry.npz,game.sgf,frame_*.jpg}`
