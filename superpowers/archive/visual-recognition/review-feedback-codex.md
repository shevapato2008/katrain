# Review Feedback: `plan.md` (Codex)

## Findings (按严重级别)

1. [Critical] Python 版本基线与计划代码语法不兼容。  
证据: 计划声明 `Python 3.10+` 在 `superpowers/tracks/visual-recognition/plan.md:9`，并大量使用 `X | None` 注解（例如 `superpowers/tracks/visual-recognition/plan.md:386`、`superpowers/tracks/visual-recognition/plan.md:1257`）。当前仓库声明支持 `>=3.9` 在 `pyproject.toml:6`，CI 也测试 `3.9` 在 `.github/workflows/test_and_build.yaml:44`。  
影响: 按计划直接实现后，在 Python 3.9 环境会出现导入/类型注解兼容问题，CI 可能直接失败。  
建议: 二选一。要么把项目最低版本统一提升到 3.10（并同步 CI、文档、发布策略），要么保留 3.9 并改为 `Optional/Union`（或开启 `from __future__ import annotations` 后统一审查）。

2. [Critical] 坐标系定义前后冲突，且与 KaTrain 现有 `Move`/SGF 约定不一致。  
证据: `superpowers/tracks/visual-recognition/plan.md:1659` 说 `(0,0)` 是 top-left 且对应 `A1`，`superpowers/tracks/visual-recognition/plan.md:1661` 又说 `row 0 = bottom`。测试还定义 `grid_to_sgf(0,0) == "aa"` 在 `superpowers/tracks/visual-recognition/plan.md:1631`。但 KaTrain 现有实现中，SGF y 轴是反向映射，见 `katrain/core/sgf_parser.py:62` 与 `katrain/core/sgf_parser.py:66`。  
影响: 视觉输出转换成 GTP/SGF 时，极易出现上下翻转或错位，直接影响 KataGo 落子正确性。  
建议: 不要新建一套 `gtp_bridge` 规则，优先复用 `katrain.core.sgf_parser.Move`（`from_gtp`/`gtp`/`sgf`），并在视觉模块只做“图像坐标 -> KaTrain canonical coords”一次转换。

3. [Critical] 目标写的是“集成到 KaTrain/KataGo”，但交付停在矩阵输出，没有落到现有对局流程。  
证据: 目标写在 `superpowers/tracks/visual-recognition/plan.md:5`；`DetectionPipeline.process_frame` 只返回 `(board, warped)` 在 `superpowers/tracks/visual-recognition/plan.md:1257` 到 `superpowers/tracks/visual-recognition/plan.md:1286`；`live_demo` 只做显示和打印在 `superpowers/tracks/visual-recognition/plan.md:1388` 到 `superpowers/tracks/visual-recognition/plan.md:1403`。现有实际下子入口是 `katrain/web/server.py:309`。  
影响: 即使视觉识别成功，也没有端到端“识别 -> 下子 -> 引擎响应”的可运行闭环。  
建议: 增加明确任务：视觉增量检测 -> 生成 `Move` -> 调用现有 play 接口（desktop/web），并定义冲突处理（误检回滚、重复帧去重、人工确认开关）。

4. [High] 任务顺序有依赖错位，Demo 在关键能力之前。  
证据: `Task 10 Live demo` 在 `superpowers/tracks/visual-recognition/plan.md:1303`，而 `Task 11 MoveDetector` 在 `superpowers/tracks/visual-recognition/plan.md:1422`，`Task 12 GTP/SGF` 在 `superpowers/tracks/visual-recognition/plan.md:1579`。  
影响: Demo 阶段无法验证“稳定落子确认 + 坐标桥接”这些核心功能，后续又要回改 pipeline。  
建议: 把 `MoveDetector` 和坐标桥接提前到 Demo 之前，且在 `Task 9` 就把 pipeline 输出定义为“候选棋盘 + 已确认增量落子（可空）”。

5. [High] 运动滤波放置位置退化于 Fe-Fool，且阈值策略过脆。  
证据: Fe-Fool 在原始帧先做 `absdiff` 再进 `find_focus`（`/Users/fan/Repositories/Fe-Fool/code/robot/window_detection.py:253` 到 `/Users/fan/Repositories/Fe-Fool/code/robot/window_detection.py:260`）。计划里先做 `find_focus` 再做运动滤波（`superpowers/tracks/visual-recognition/plan.md:1270` 到 `superpowers/tracks/visual-recognition/plan.md:1277`），并使用 `max_diff` 单点阈值（`superpowers/tracks/visual-recognition/plan.md:928` 到 `superpowers/tracks/visual-recognition/plan.md:931`）。  
影响: 计算成本更高，且对局部高亮/反光/自动曝光特别敏感，容易误判不稳定。  
建议: 先在 raw frame 做稳定性筛选（或只在棋盘 ROI），指标改为“变化像素占比 + 连续帧平滑”，不要只用全局最大像素差。

6. [High] 依赖管理策略不一致，CI 可重复性不足。  
证据: Task 4 里建议直接 `uv add ultralytics opencv-python` 在 `superpowers/tracks/visual-recognition/plan.md:529`，Task 13 又改成 optional extra 在 `superpowers/tracks/visual-recognition/plan.md:1711`。当前 CI 只同步 `dev` 组（`.github/workflows/test_and_build.yaml:49` 到 `.github/workflows/test_and_build.yaml:52`）并跑全量测试（`.github/workflows/test_and_build.yaml:54`）。  
影响: 很容易出现“本地能跑、CI 失败”或团队环境依赖漂移。  
建议: 统一一种方式。若走 optional extra，则 CI 增加 `--extra vision` 任务；若不想让默认 CI 装视觉依赖，则把视觉测试打 marker 并分离 job。

7. [Medium] 核心测试用例过于“模拟化”，对真实风险覆盖不足。  
证据: `StoneDetector` 测试并未验证 ultralytics 结果解析契约，仅测试 dataclass/手工过滤（`superpowers/tracks/visual-recognition/plan.md:539` 到 `superpowers/tracks/visual-recognition/plan.md:579`）。`BoardFinder` 主要是合成矩形图（`superpowers/tracks/visual-recognition/plan.md:303` 到 `superpowers/tracks/visual-recognition/plan.md:351`）。  
影响: 单测通过不代表真实摄像头环境可用。  
建议: 增加小规模真实图片回归集（明暗、反光、倾斜、遮挡），以及 ultralytics `Results` 的结构化 mock 契约测试。

8. [Medium] 训练脚本命令提示与实现不一致。  
证据: 脚本打印了 `--validate --weights` 用法在 `superpowers/tracks/visual-recognition/plan.md:1121`，但参数定义里没有这些选项（`superpowers/tracks/visual-recognition/plan.md:1097` 到 `superpowers/tracks/visual-recognition/plan.md:1105`）。  
影响: 使用者会直接按提示执行并报错。  
建议: 要么补上 `validate` 子命令，要么删掉该提示并给出真实验证命令（例如 `yolo val ...`）。

9. [Medium] 棋盘状态聚合缺少冲突解析，结果可能不稳定。  
证据: 当前直接 `board[pos_y][pos_x] = det.class_id + 1` 在 `superpowers/tracks/visual-recognition/plan.md:806`。  
影响: 同一交叉点出现多个框（双类冲突/重复框）时，结果取决于检测列表顺序。  
建议: 引入每交叉点“最高置信度胜出 + 置信度差阈值 + 冲突标志位”，供上层决定是否延迟确认。

10. [Medium] 线性映射假设缺少相机标定闭环。  
证据: 架构按线性映射推进在 `superpowers/tracks/visual-recognition/plan.md:7`，状态映射核心在 `superpowers/tracks/visual-recognition/plan.md:804` 到 `superpowers/tracks/visual-recognition/plan.md:806`，但计划内没有相机畸变标定任务。  
影响: 19x19 边角位最容易累积误差，终盘密集时会导致落点漂移。  
建议: 增加 `calibrate_camera.py`（一次性标定 + 参数持久化）与 `undistort` 前处理；把“角点误差/格点误差”纳入验收指标。

## 建议的修订实施顺序

1. 先做“版本与依赖基线”决策。明确 Python 最低版本、vision 依赖安装策略、CI job 划分。  
2. 定义唯一坐标规范（图像坐标、棋盘矩阵坐标、KaTrain Move 坐标）并先写 round-trip 测试。  
3. 实现并验证 `BoardFinder + MotionFilter`（含真实样本回归），再做数据采集。  
4. 训练/验证检测模型，明确离线指标阈值（mAP、误检率、终盘密集场景召回）。  
5. 在 pipeline 内引入“冲突解析 + 多帧确认 + Move 输出”。  
6. 直接接入现有对局入口（例如 `katrain/web/server.py:309`）做端到端演示。  
7. 最后补充 demo、文档和发布打包验证（含可选依赖对桌面/web 的影响）。

## 正向评价

1. 模块边界总体清晰，`katrain/vision/` 的包结构是合理的。  
2. 先拆基础能力再做集成的思路是对的，且多数任务具备可测试性。  
3. 从 Fe-Fool 迁移的方向可行，但需要先解决坐标规范和工程化基线问题，避免“功能可跑但无法稳定集成”。
