# Codex 评审反馈：Baipu→YOLO 4-Class 自动标注与重训练计划

## 总判定

**小修后可实施**。整体架构方向成立：warp 空间标注、4 类单一事实源、LED 类运行时守卫、时间序验证集这些决策都合理。但计划还不能“直接交给零上下文工程师”无脑执行：存在一个复制即失败的代码缺口，以及多处会让标注质量、验证指标或线上行为偏乐观的风险。以下问题建议在执行前修进 `plan.md`。

## Blocker

- **[Blocker] Task 5/6（`plan.md:588-589`, `plan.md:739`） — `process_game()` 使用了未导入的 `ID_TO_NAME`，按计划复制代码会直接 `NameError`。**
  - 问题：Task 5 的导入只写了 `from katrain.vision.classes import LED_COLOR_TO_CLASS, NAME_TO_ID`，但 Task 6 统计里执行 `stats[ID_TO_NAME[b.class_id]] += 1`。计划自评说类型一致，但代码片段本身不一致。
  - 修改建议：把 Task 5 导入改成 `from katrain.vision.classes import LED_COLOR_TO_CLASS, NAME_TO_ID, ID_TO_NAME`，或在 `process_game()` 内改用 `CLASS_NAMES[b.class_id]`。同时在 `test_process_game_writes_matching_labels()` 里断言 `stats["black"]`, `stats["white"]`, `stats["led_red"]`, `stats["led_green"]` 都能正常累计，避免这个错误漏过。

## Major

- **[Major] Task 3-6 测试设计（`plan.md:247`, `plan.md:366`） — 核心 labeler 测试几乎全部依赖 `~/.katrain/...`，CI 缺 fixture 时会跳过，TDD 覆盖不足。**
  - 问题：真实数据 integration test 有价值，但不能作为唯一覆盖。缺真实采集时，`load_capture`、`reconstruct_board`、`estimate_global_shift`、`frame_boxes`、`process_game` 的关键逻辑都不会在 CI 中被执行。
  - 修改建议：新增一个 repo 内最小合成 fixture，例如 95x95 或 190x190 warp、`xs/ys`、2-3 个棋子、1 个 LED、一个含 capture 的 SGF/steps，覆盖：
    - `reconstruct_board()` 对 move/pass/setup/clear 的行为；
    - `estimate_global_shift()` 对已知平移的恢复误差；
    - `frame_boxes()` 的类别、数量、边界裁剪；
    - `process_game()` 输出 images/labels 一一匹配。
  - 真实 `kifu_24171` 只保留为 `@pytest.mark.integration` 或 skip 的额外验证。

- **[Major] Global Constraints / Task 3-6（`plan.md:19`, `plan.md:238-247`） — i18n `.mo` 手动前置条件让测试不够自包含。**
  - 问题：计划要求人工先跑 `uv run python i18n.py`，否则 pytest collection 会失败。对零上下文执行者和 CI 都不稳，而且测试模块在 skipif 前已经 import `baipu_autolabel`，skip 不会保护 collection。
  - 修改建议：不要把“手动生成 `.mo`”作为隐式环境状态。至少选择一种方案写进计划：
    - 在 `tests/conftest.py` 或相关测试 fixture 中显式编译/准备 i18n；
    - 或让 `baipu_autolabel.py` 懒加载 `katrain.core.baipu`，避免纯 box/shift 测试在 import 阶段触发 `core.lang`；
    - 或把最终测试命令统一写成 `uv run python i18n.py && CI=true uv run pytest ...`，并说明生成物是否需要提交或忽略。

- **[Major] Task 4（`plan.md:386-390`, `plan.md:489-505`） — 漂移估计只有“clamp 内”测试，没有准确性和锚点质量门禁，可能静默生成整帧偏移标签。**
  - 问题：当前测试只检查 `abs(dx/dy) <= 0.6 * spacing` 和无锚点返回 0；即使 LED 阈值失效、Hough 误检、median 被带偏，也可能通过。`return (0,0)` 在 board bump 后尤其危险，会让整帧标签错位。
  - 修改建议：计划里增加 `ShiftReport` 或 stats：`anchor_count`, `led_found`, `median_shift`, `mad/residual_px`, `fallback_used`。对合成 fixture 断言已知 shift 误差小于例如 `0.1 * spacing`；对真实 fixture 输出每帧 residual CSV，并在 `process_game()` 中当 `anchor_count == 0` 或 residual 超阈值时记录/可选择 fail。无锚点时优先使用上一帧 shift 或邻近帧插值，而不是无条件 `(0,0)`。

- **[Major] Task 4（`plan.md:441-444`） — HSV LED 阈值被硬编码且无校准/诊断路径，换光照或 LED 亮度时脆弱。**
  - 问题：红 `hue < 12 or > 168`、绿 `40 < hue < 90`、`s > 80, v > 120` 在当前采集可能有效，但后续“另一块盘/另一种光照”很可能漂。计划承认单盘数据少，但 labeler 本身也会受此影响。
  - 修改建议：把阈值做成 CLI 参数或配置常量，并输出每帧 LED centroid 是否找到、mask area、centroid-grid residual。必要时使用 `led_point` 附近 ROI 内的最大饱和/亮度连通域做自适应阈值，而不是固定 HSV 范围一刀切。

- **[Major] Task 5（`plan.md:531`, `plan.md:603-629`） — 统一 90px 左右的大方框同时标注棋子和 LED，标签噪声偏大，尤其边角和密集区。**
  - 问题：`2 * 0.85 * spacing` 在 spacing≈52.7 时约 90px，大于实际棋子直径，也远大于 LED 光斑。相邻交叉点水平/垂直框会明显重叠；LED 框会包含大量棋盘纹理或邻近棋子，模型学到的是“局部大区域”而不是 LED 小目标。
  - 修改建议：拆分 stone/LED box 策略：
    - stone box 用实际棋子半径估计或约 `0.95-1.15 * spacing` 的边长；
    - LED box 用 `detect_led_centroid()` 连通域 bbox 或较小固定边长（例如 `0.35-0.6 * spacing`），并设最小像素尺寸；
    - 对密集区域做 overlay QA 和 IoU 分布报告，避免邻格标签互相覆盖。

- **[Major] Task 5（`plan.md:621-629`） — `boxes_to_yolo_lines()` 未裁剪边界框，角点棋子/LED 的 bbox 会伸出图像。**
  - 问题：grid corner 在 `(0,0)` 或 `(949,949)`，90px box 的一半在图像外。虽然 normalized `cx/w` 仍在 0..1，实际训练框语义不准确，Ultralytics 的 label 校验/训练也可能产生边界异常或隐式裁剪。
  - 修改建议：先把 `(x1,y1,x2,y2)` clip 到 `[0,img_w/img_h]`，再重新计算 normalized center/size；增加测试覆盖角点 box，断言所有 xyxy 在图内，且宽高为裁剪后尺寸。

- **[Major] Task 2（`plan.md:197-203`） — 仅跳过 LED class 不能处理“同一交叉点同时有 LED 检测和误判棋子检测”的线上污染。**
  - 问题：目标之一是避免 LED 被误读成棋子。当前 guard 只忽略 class 2/3；如果模型在 LED 位置同时输出一个 class 0/1 石子框，board_state 仍会写幻影棋子。agnostic NMS 可以降低概率，但不能作为业务守卫。
  - 修改建议：在 `detections_to_board()` 或前置过滤中加入 LED grid suppression：先把 LED detections 映射到 grid，再忽略同一 grid 上低于/接近 LED 置信度的 stone detections；或至少增加测试暴露该风险，并在计划中说明为什么不做 suppression。

- **[Major] Task 7/9（`plan.md:806-808`, `plan.md:1088`） — 单盘时间序验证只能证明 smoke test，不能支撑 LED recall ≥0.9 的泛化结论。**
  - 问题：尾部 40 多帧仍是同一盘、同一相机、同一光照、同一棋盘材质，LED recall 只有几十个样本，阈值 `≥0.9` 更像 sanity gate，不是上线质量门槛。若后续多 `--game-dir`，当前 `temporal_split_dataset()` 只是按文件名全局排序，不能表达“整盘/整 session holdout”。
  - 修改建议：把 Task 9 的 gate 改为两层：
    - 当前单盘 temporal val：只作为 smoke gate，记录 per-class P/R 和混淆；
    - 上线前 gate：至少新增第二采集 session，按 session holdout 验证 LED recall、stone precision、LED-as-stone false positive。
  - 同时扩展 `temporal_split_dataset()` 或新增 `session_holdout_split_dataset()`，避免多盘数据被文件名排序误切。

- **[Major] Task 8/9（`plan.md:1004-1008`, `plan.md:1075-1088`） — 计划依赖 `copy_paste=0.4` 解决 LED 稀有类，但没有验证该增强是否真的对 detection 数据生效或是否 class-aware。**
  - 问题：LED 与棋子对象数约 1:100，单纯设置 Ultralytics 参数未必会有效提升 LED 采样频率；本环境未安装 ultralytics，无法确认当前版本行为。即使生效，也不保证优先复制 LED 类。
  - 修改建议：在计划中加入明确验证：训练日志/augment sample 中确认 LED copy-paste 出现；如果不生效，改为离线 class-balanced oversampling（复制含 LED 的图、裁剪/贴 LED ROI 到同一 warp 背景、或按类别加权采样）。不要把 `copy_paste` 当作已证明的稀有类解决方案。

- **[Major] Task 7（`plan.md:876-907`） — 新增 temporal split 函数但不改 CLI，容易让执行者继续使用旧的随机 split。**
  - 问题：`prepare_dataset.py` 现有 CLI 仍是 `--images/--labels --split` 调 `split_dataset()` 的随机切分。计划 Task 9 使用 Python one-liner 调 temporal 函数，但零上下文工程师很可能沿 README 或工具 help 使用旧 CLI，导致验证泄漏。
  - 修改建议：给 `prepare_dataset.py` 增加 `--split-mode random|temporal` 和 `--gap`，baipu runbook 使用 CLI 而不是 here-doc。也可以在 `split_dataset()` 文档里明确“baipu 连续帧禁止使用 random split”。

- **[Major] Task 9（`plan.md:1081-1088`, `plan.md:1094`） — validation 命令遗漏 `--imgsz 640`，训练/导出用 640 但验证默认 960，指标不可比。**
  - 问题：`train_model.py` 的 val 子命令默认 `--imgsz 960`。计划训练和 ONNX export 都是 640，但 val command 未传 imgsz，得到的 per-class recall 不是同一推理尺寸。
  - 修改建议：Task 9 Step 2 改成：
    ```bash
    uv run python -m katrain.vision.tools.train_model val \
      --data /tmp/go4/dataset/data.yaml \
      --model runs/detect/go4_n/weights/best.pt \
      --imgsz 640
    ```
    并在 README 指标表记录验证尺寸。

- **[Major] Task 9（`plan.md:1099-1106`） — RKNN sidecar 路径/文件名写错，验证的是 ONNX sidecar 而不是 RKNN sidecar。**
  - 问题：`export_rknn.py` 会输出 `best_rk3588.rknn` 和 `best_rk3588.meta.json`，但计划写“Expected: `best.rknn` + `.meta.json`”，且 `cat runs/detect/go4_n/weights/best.meta.json` 只是 ONNX sidecar。
  - 修改建议：把 runbook 改为检查 `runs/detect/go4_n/weights/best_rk3588.meta.json`，并在期望输出里写准确文件名。部署步骤也应明确 `.rknn` 必须和同名 `.meta.json` 一起拷贝。

## Minor / Nit

- **[Minor] Task 3 tests（`plan.md:252-269`） — 对真实棋局写死 `(20,20)`、`205`、`6 captured`，换 fixture 后测试会变成脆弱快照。**
  - 修改建议：保留这些断言作为 `kifu_24171` integration smoke，但核心测试用合成 SGF 自洽推导期望值；或从 `steps` 的 `removed` 统计推导最终棋子数，减少 magic number。

- **[Minor] Task 6（`plan.md:662`, `plan.md:782`） — `kifu_24171` 的 written 数描述前后不一致。**
  - 问题：Task 6 接口说明写 `written == frames == 212`，手动 gate 期望写 `~211`。
  - 修改建议：统一为 `212`，并明确包含 `frame_000` initial LED 和 `frame_211` final no LED。

- **[Minor] Task 7（`plan.md:876-907`） — `temporal_split_dataset()` 不清理输出目录，重复运行可能残留旧文件。**
  - 修改建议：函数开头如果 `output_dir` 已存在，可选择 fail fast 或提供 `overwrite=False/True` 参数；测试覆盖 rerun 不污染。

- **[Minor] Task 8（`plan.md:1004-1008`） — augmentation preset 固定值较多，但计划缺少实验记录模板。**
  - 修改建议：README/runbook 增加一张实验表：`imgsz`, `box policy`, `copy_paste`, `mosaic`, `model size`, per-class P/R/mAP, LED-as-stone FP。这样后续从 `640/n` 调到 `960/s` 时不会只凭印象。

- **[Minor] Task 10（`plan.md:1120-1138`） — 文档任务只说更新 README，没有要求记录 residual/overlay QA 产物。**
  - 修改建议：把 Task 6 的 overlay 抽检结论、Task 4 的 shift residual 分布、Task 9 的 per-class metrics 一起写入 README 或 `docs/vision-yolo4-runbook.md`，否则后续很难复盘模型质量。

## 建议的最低修订清单

1. 修复 `ID_TO_NAME` 未导入的 Blocker。
2. 增加合成 fixture 与非 skip 的 labeler 单元测试。
3. 给漂移估计加质量报告、准确性测试和无锚点 fallback。
4. 重做 box policy：stone/LED 分开设尺寸，并裁剪边界框。
5. validation/export runbook 改准：`--imgsz 640`，RKNN sidecar 文件名正确。
6. 明确单盘 temporal val 只是 smoke gate；上线前需要 session holdout 或更多采集数据。
