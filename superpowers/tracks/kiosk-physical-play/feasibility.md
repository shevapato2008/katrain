# Kiosk 物理棋盘对弈 — 可行性调研报告

日期：2026-07-02　|　状态：调研完成，待写实施计划
范围：kiosk 对弈模块三个子模块接入物理棋盘（LED 矩阵显示落子 + 摄像头识别棋局）：
**人机对弈·自由对弈、人机对弈·升降级对弈、人人对弈·在线大厅**。

---

## 0. 结论摘要

**可行性：高。** 「视觉落子注入对局」的后端骨架已经存在并合入 develop——`_vision_move_poller`
（`katrain/web/server.py:1810`）已经把视觉确认的落子经 `session.katrain("play", coords)` 注入对局，
与前端点击走完全相同的 `game_update` 广播链路；kiosk 的 `GamePage` 挂载时已在调 `visionBind(sessionId)`，
全屏对局路由已被 `PhysicalBoardGuard requireRecognition` 包裹。**一期（人机对弈两个模式）的核心缺口
只有三块：对局 LED 编排、混合确认兜底 UX、AI 选点（白灯）功能**——都是在现成管线上加层，不动识别核心。

**二期（在线大厅）是唯一的大工程**：board（kiosk）模式下大厅/匹配是占位符（`server.py:319-320`），
需要新建 kiosk↔远程服务器的对局代理层。推荐按「把远程 KaTrain 服务器当作一个 platform adapter」
的思路实现（复用 `PlatformCommandGateway` 模式），这样视觉/LED 侧零改动。

最大的技术风险不在链路，而在两点：
1. **白灯/蓝灯可能被 YOLO 误识别**（模型只训了 black/white/led_red/led_green 四类）；
2. **SBC CPU 推理延迟**（onnx ~600ms/帧 × 3 帧一致性 ≈ 2s 确认延迟），对升降级的计时对局余量偏紧。
两者都有明确缓解路径（见 §5）。

---

## 1. 已确认的设计决定（2026-07-02 brainstorm）

| # | 决定 | 内容 |
|---|---|---|
| D1 | 落子确认 | **混合：自动为主 + 异常兜底**。摄像头连续识别、`MoveDetector` 自动确认；低置信/盘面不一致时屏幕提示用户确认或纠正。 |
| D2 | LED 语义（对局中） | ① 对手/AI 落子点：黑→红灯、白→绿灯；② 提子→蓝灯；③ 几何漂移：**保持硬规则**——先静默跑无 LED 外角重标定，失败才屏幕弹提示、由用户手动触发 LED 基准灯重标定（LED 绝不为几何自动闪灯）；④ 求助 AI 最佳选点：白灯闪烁 top-N（个数由后端设置决定）。 |
| D3 | AI 选点门控 | **必须用户点屏幕按钮手动触发，绝不自动**（后续可能加语音，现阶段只走触摸屏）。可用性由后端逻辑决定：自由人机对弈需用户有余额且场景开放；**升降级人机、人人对弈一律禁止**。引擎**可配置**：有余额走云端强引擎（复用 paid-analysis 计费轨道），无余额降级本地弱引擎或直接禁用。 |
| D4 | 分期 | **一期：自由对弈 + 升降级对弈**（本地闭环，骨架就绪）；**二期：在线大厅**（先设计好 kiosk↔远程对局代理再动手）。 |

---

## 2. 现状盘点：已有的骨架

### 2.1 视觉识别管线（`katrain/vision/`，~9.9K LOC，已合入 develop）

- **运行形态**：生产为独立进程 `VisionWorkerProcess`（`worker.py:471`），Mac 开发为线程
  `InProcessAdapter`（`worker_inprocess.py`）；由 board 模式 lifespan 以 `--vision-model` 启动
  （`server.py:380-386`），主进程经 `VisionService`（`service.py`）代理。
- **识别流程**：`CameraManager` 采集（MJPG、BUFFERSIZE=1，后台读线程）→ `MotionFilter` 动静门控 →
  几何锁 warp（train/serve 一致，`warp.warp_with_margin` + `adjust_M_for_resolution`）→ YOLO 四类检测
  （`black=0, white=1, led_red=2, led_green=3`，`classes.py:8`）→ 两步识别（置信度优先占格 +
  ≥0.6 溢出到最近空格，`board_state.py:57-108`）→ 输出 19×19 数组。
- **增量落子推断**：`MoveDetector.detect_new_move`（`move_detector.py:22`）——只接受「先前为空的交叉点上
  恰好出现一颗新子」，需 **3 帧一致**；`force_sync` 支持悔棋/重置后重建基线。
- **对局级对账**：`SyncStateMachine`（`sync.py:65`）比较「视觉观测盘面 vs 引擎期望盘面」，状态
  `SYNCED / CAPTURE_PENDING / MISMATCH_WARNING / BOARD_LOST / DEGRADED / SETUP_IN_PROGRESS`——
  这正是 D1 混合确认所需的异常信号源，事件经 `/ws/vision`（`server.py:1707`）推给前端。
- **几何漂移**：`GeometryDriftMonitor`（phaseCorrelate 平移）+ `RotationAwareDrift`（绝对位姿）+
  `DriftStateMachine`（STABLE→MOVING→settle→recalibrate），默认重标定策略是**无 LED 外角**
  `OuterCornerStrategy`（`calibration_strategies.py:17`，`server.py:412-419` 默认 `"auto"`）——与 D2③ 一致。
  注意：拥挤盘面下的实机精度尚未硬件验证（代码注记 "P12 Task 9 待硬件"）。
- **SBC 推理**：onnx CPU 为默认后端（~600ms/帧，`camera.py:80` 注记）；rknn NPU 后端已写
  （RK3588/3576/3562，`inference/rknn_backend.py`）但标记 experimental；转换工具链齐备
  （`tools/export_rknn.py` + `convert_rknn.sh`，x86 Docker）。

### 2.2 LED 控制链路（全链已落地）

```
前端 ledApi.ts →HTTP→ /api/v1/led/* (led.py) → LedService 串口线程 (led_service.py)
  →USB-CDC 115200→ ESP32-S3 固件 (smartbox-hardware-design/debug/led_bring_up_pio) → WS2812B×361
```

- **权威 LUT 在主机**：`rc2idx`（`led_service.py:40`），固件只认原始链索引 `SETI`。
- **REST 能力**：`POST /led/point|points|clear`、`GET /led/status`；颜色语义 `black→红 / white→绿 /
  remove→蓝`（`led_service.py:52-59`）。**每次 set_points = 清屏+重设（非叠加）**，一个 batch 可混色
  ——「AI 落子红/绿 + 提子蓝」可一次下发。
- **任意 RGB**：服务层 `set_rgb_points`（`led_service.py:197`）已有但**未暴露 REST**——白灯选点需要补。
- **两条队列语义**：UI 容忍路径（入队即返回、失败静默）vs strict 路径（SHOW 被 ack 才认）。对局显示用
  UI 容忍路径即可。
- **闪烁**：固件无 blink 指令；摆谱的提子闪烁是前端 effect 轮换驱动的（可复用该模式，或后端 asyncio 任务驱动）。
- **空闲失效保护**：>5 分钟无 `/led/*` 活动自动熄灯（`server.py:1782-1807`）。
- **硬件遗留**：UR 象限逐跳驱动裕量问题，v4 TX-side buffer 修复待验证（board-swap + freeze-spray）。

### 2.3 后端对局流

- 对局 API 挂根路径 `/api/*`（`server.py`），落子 `POST /api/move`（`MoveRequest{session_id, coords:[x,y], pass_move}`）。
- **AI 应手是后台线程自动触发**（`interface.py:612-641` → `_do_ai_move_and_broadcast`），结果经
  session WebSocket `/ws/{session_id}` 以 `game_update` 广播——LED 编排器可挂接的权威事件源。
- **升降级与自由对弈同一管线**，仅 `mode` 区分；ranked 反作弊已存在：`analysis_allowed` 关卡
  （`interface.py:200-202, 705-708`）屏蔽一切分析动作——D3 的服务端强制门控可直接复用。
- **视觉注入已打通**：`POST /api/v1/vision/bind` 绑定 session → `_vision_move_poller`
  （`server.py:1810-1861`）轮询 `ConfirmedMove` → `vision_move_to_katrain` → `session.katrain("play")`；
  平台对局则走 `gateway.play_move`。**跨平台对局的物理盘循环已被该 poller 覆盖**。
- **board 模式 = 胖客户端**：SBC 跑完整 FastAPI + 本地弱引擎（`engine_profiles["board"]`）+ SQLite +
  `RemoteAPIClient`（登录代理/心跳/直播教程转发 `board.py:_proxy`）+ `SyncWorker` 离线同步。
- **在线大厅仅 server 模式可用**：`Matchmaker`/`LobbyManager` 是单进程内存态（`session.py:183, 232`），
  board 模式下均为占位符、`game_repo=None`（`server.py:319-321`）。

### 2.4 前端现状（kiosk）

- 路由：自由/升降级 → `AiSetupPage`（`mode` 参数）→ `GamePage`；在线大厅 → `LobbyPage`
  （`/ws/lobby` 匹配 + `/ws/{sessionId}` 对局）→ 同一 `GamePage`。
- `GamePage` 已做：挂载 `visionBind` / 卸载 `visionUnbind`（`GamePage.tsx:43-48`）、AI 落子坐标 toast、
  `VisionContext` 3s 轮询 `/api/v1/vision/status`、`useVisionSync`（`/ws/vision` 事件）+
  `VisionSyncOverlay` 提示层。
- `Board.tsx` 无「外部落子」显式接口——不需要：服务端权威状态经 `game_update` 整体替换即可。
- **未接线**：`GamePage` 完全没调 LED；`MovePendingOverlay` 是占位符；混合确认交互不存在。
- 现成样板：摆谱 `BaipuSessionPage.tsx:268-297`（LED 点亮下一手/提子闪烁/离开清灯）、
  `LiveBoard` 的 `nextMovePoint`/`capturedPositions` 叠加层。

---

## 3. 差距分析（按子模块）

### 3.1 自由对弈（一期）——缺口最小

| 缺口 | 说明 |
|---|---|
| G1 对局 LED 编排 | AI 落子亮灯（红/绿）+ 提子蓝灯，落子/悔棋/新局/离场时的灯态生命周期。后端无此逻辑，前端 GamePage 未调 LED。 |
| G2 混合确认 UX | `SyncStateMachine` 事件已有，但 `MISMATCH_WARNING`/`ambiguous_stone`/`board_lost` 的屏幕确认、纠正流程未实现（`MovePendingOverlay` 占位）。 |
| G3 AI 选点（白灯） | 全新功能：触发按钮 + 计费/场景门控 + 引擎路由（云端/本地/禁用）+ REST 白灯接口 + 闪烁驱动 + 识别防误检。 |
| G4 悔棋/重开的物理一致性 | 数字盘悔棋后物理盘多子——需要「请拿走 X 处棋子」引导（蓝灯 + 屏幕提示）+ `MoveDetector.force_sync` 重建基线。 |

### 3.2 升降级对弈（一期）——在 3.1 之上增量

| 缺口 | 说明 |
|---|---|
| G5 选点强制禁用 | 前端隐藏按钮 + 服务端复用 `analysis_allowed` 关卡拒绝（ranked 已有该机制，hint endpoint 接入即可）。 |
| G6 计时余量 | ranked 强制开钟。视觉确认延迟（CPU ~2s）计入用户时间；需要明确「落子时刻」语义（建议：以视觉确认时刻为准，并在屏幕展示确认中状态），并推进 NPU 路径压延迟。 |
| G7 悔棋策略 | ranked 一般禁止悔棋，G4 在此模式可简化为「盘面异常恢复」流程。 |

### 3.3 在线大厅（二期）——结构性缺口

| 缺口 | 说明 |
|---|---|
| G8 大厅/匹配代理 | board 模式无 matchmaker。kiosk 需经远程服务器匹配：本地代理远程 `/ws/lobby`（或前端直连远程——不推荐，见 §4.2）。 |
| G9 远程对局会话桥 | 对局在远程服务器上，落子要提交远程并等 ACK，对手落子/计时/终局要回流本地（LED + 屏幕）。 |
| G10 断线/重连语义 | kiosk 网络抖动时的挂起、重连、超时判负规则。 |
| G11 计费/账户 | 远程 rated 局的段位记录在服务器侧（`game_repo`），本地 shadow user 体系需与之对齐（登录代理已有，`auth.py:91-126`）。 |

---

## 4. 方案架构

### 4.1 一期：本地人机闭环

**核心新增一个后端「物理对局编排器」（PhysicalPlayOrchestrator），其余全是接线。**

```
物理落子:  用户摆子 → vision worker (MoveDetector 3帧确认)
              → _vision_move_poller → session.katrain("play")   [已存在]
              → AI 后台线程应手                                   [已存在]
              → game_update 广播 → 前端棋盘更新                    [已存在]
              → [新] 编排器: LED 点亮 AI 落子(红/绿) + 提子(蓝)
              → [已存在] vision.set_expected_from_stones 更新期望盘面
异常兜底:  SyncStateMachine 事件 → /ws/vision → [新] 前端确认/纠正 UI
AI 选点:   [新] 屏幕按钮 → POST /api/v1/hint (门控+计费+引擎路由)
              → top-N → [新] /led/hint (白灯) + 后端闪烁任务
              → 选点显示期间挂起 MoveDetector，用户关闭/超时后恢复
```

关键设计点：

1. **LED 编排器放后端**（挂在 session 状态回调 / `_vision_move_poller` 旁），不放前端。理由：
   LED 是物理设备权威状态，前端可能刷新/断连；后端能拿到权威 `game_update`（含提子差分）；
   摆谱前端直调 LED 的模式对"对局"这种长生命周期状态不够健壮。前端只保留手动清灯/开关。
2. **一个 batch 混色下发**：`set_points([AI落子(black|white), *提子(remove)])`——清屏+重设语义天然合适。
3. **AI 选点白灯**：
   - 新增 REST：`POST /api/v1/led/hint`（暴露 `set_rgb_points` 的白色 + 闪烁参数），或在编排器内直驱服务层；
   - 闪烁由后端 asyncio 任务驱动（周期性 set/clear，非 strict 队列，361 灯刷新 ~11ms 无压力）；
   - **显示期间必须挂起 move 检测**（vision worker 加 pause 命令），防白灯误检（见 R1）；
   - 门控顺序：场景（free 才允许）→ `analysis_allowed`（ranked 拒绝）→ 余额（paid-analysis 轨道）→
     引擎路由（余额→云端强引擎；无余额→按配置降级本地或 403）。
4. **混合确认 UX**（替换占位的 `MovePendingOverlay`）：
   - `move_confirmed`：静默（棋盘已更新），可选轻提示音；
   - `ambiguous_stone` / `MISMATCH_WARNING`：屏幕弹差异视图（期望 vs 观测），按钮「采纳观测 / 忽略 / 暂停对局去整理棋盘」；
   - `board_lost` / `DEGRADED`：全屏遮罩「棋盘不可见」，恢复后自动消退；
   - 漂移：静默无 LED 重标定 → 失败才弹「重新定位」按钮（用户触发 LED 基准灯，守住 D2③ 硬规则）。
5. **升降级**：同一编排器，多两条策略开关（hint 禁用、悔棋禁用/简化）。

### 4.2 二期：在线大厅（推荐「remote-platform 适配器」方案）

两个候选：

- **方案 A：前端直连远程**（kiosk 前端直接连远程 `/ws/lobby` 和远程对局 API，本地后端只管视觉/LED）。
  否决理由：跨源认证复杂、视觉落子要从本地后端再绕到远程、LED 编排器拿不到权威对局事件，
  且与现有「board 模式所有远程访问经 `RemoteAPIClient`/`_proxy`」的架构相悖。
- **方案 B（推荐）：把远程 KaTrain 服务器实现为一个 platform adapter**。
  现有 `PlatformCommandGateway`（`platforms/gateway.py`）已定义「本地落子→远程 ACK→本地应用；
  对手落子→注入本地会话→广播」的完整模式，且 **`_vision_move_poller` 已经原生支持平台对局**
  （`server.py:1834` 走 `gateway.play_move`）。新写一个 `katrain_remote` adapter（大厅 WS 代理 +
  对局双向桥 + 计时/终局回流），则物理盘循环（视觉注入、LED 编排、混合确认）**零改动**复用一期成果。
  跨平台对弈（OGS 等）也自动共享同一物理盘体验——与"智能棋盘做所有平台枢纽"的产品愿景一致。

二期前置条件：一期编排器稳定运行；paid-analysis 轨道遗留的 board proxy 设计一并纳入；
G10 断线语义需与服务器端 forfeit 规则（`auth.py:252-297` 登出判负等）对齐设计。

---

## 5. 风险与缓解

| # | 风险 | 等级 | 缓解 |
|---|---|---|---|
| R1 | **白灯/蓝灯被 YOLO 误检**：模型只训了 black/white/led_red/led_green；白灯亮点可能被判为白子、蓝灯行为未知 | 高 | 短期：① 后端知道哪些交叉点亮着灯→在 `board_state` 对已点亮且非期望落子点做遮蔽；② 选点白灯显示期间挂起 MoveDetector（本来就要做）。长期：用现成摆谱采集台架收 led_white/led_blue 样本，扩为 6 类重训（采集流水线全套已有）。 |
| R2 | **SBC CPU 推理延迟**：onnx ~600ms/帧 × 3 帧一致 ≈ 2s 确认延迟，ranked 计时局体验受损 | 中高 | rknn NPU 后端已写（experimental），转换工具链齐备——一期内做 NPU 实机验证；不行则降 imgsz/一致性帧数权衡。落子时刻语义（G6）在 UI 明示「确认中」。 |
| R3 | 拥挤盘面外角重标定实机精度未验证（"P12 Task 9 待硬件"） | 中 | 一期实机验证项；失败兜底是屏幕提示用户手动触发 LED 重标定（流程已设计）。 |
| R4 | LED 硬件 UR 象限驱动裕量（v4 TX buffer 修复待验证） | 中 | 硬件轨道并行推进；软件层对 LED 写失败已是静默容忍（UI 路径），不阻塞对局。 |
| R5 | 悔棋/异常后物理盘与数字盘发散 | 中 | G4 引导流程（蓝灯 + 屏幕指示拿子）+ `force_sync` 重基线 + `SyncStateMachine` 对账兜底。 |
| R6 | LED 5 分钟空闲自动熄灯 vs 用户长考 | 低 | 编排器定期刷新当前灯态，或接受熄灭、在下一次状态变化时重亮（推荐后者，省电且简单）。 |
| R7 | 二期代理层复杂度（WS 双向桥、时钟同步、断线判负） | 高（二期） | 先出独立设计文档再动手（D4 已定）；复用 gateway 模式收敛范围。 |
| R8 | 摄像头独占：CameraHub 单持有者，vision 与摆谱 capture 不能同时用 | 低 | 对局模式只需 vision；进对局前若 capture 占用则由 guard 提示。 |

---

## 6. 工作量粗估与实施顺序（一期）

| 步骤 | 内容 | 规模 |
|---|---|---|
| 1 | 后端 LED 编排器（AI 落子/提子/生命周期/失效保护协调）+ 测试 | 中 |
| 2 | 前端 GamePage 接线：灯态指示、混合确认 UI（替换 MovePendingOverlay）、漂移提示流 | 中 |
| 3 | vision worker pause/resume 命令 + 已点亮交叉点遮蔽（R1 短期缓解） | 小 |
| 4 | AI 选点：hint endpoint（门控+计费+引擎路由）+ `/led/hint` 白灯 REST + 闪烁任务 + 按钮 UI | 中大 |
| 5 | 悔棋/重开物理一致性引导（G4） | 小中 |
| 6 | ranked 差异化（hint 禁用、计时语义、悔棋策略） | 小 |
| 7 | 实机验证：NPU 推理（R2）、拥挤盘面重标定（R3）、整局端到端 | 中（依赖硬件） |

依赖注意：hint 计费门控依赖 paid-analysis 轨道（phases 1–4a 在 `feature/rk3588-ui`，4b/5/6 未完），
而视觉/LED 代码在 `develop`——实施前需先确定分支整合策略。

二期（在线大厅）在一期落地后单独立项：`katrain_remote` platform adapter 设计文档 → 大厅代理 →
对局桥 → 断线语义 → 实机联调。

---

## 7. 开放问题（实施计划阶段再定）

1. 分支整合：paid-analysis（feature/rk3588-ui）与 develop 的合并顺序。
2. hint 的 top-N 个数、白灯闪烁频率/占空比的默认值与设置项归属（后端 config vs 管理端）。
3. ranked 局「落子时刻」的精确计时语义（视觉确认时刻 vs 物理放子估计时刻）。
4. led_white/led_blue 扩类重训的排期（依赖 R1 短期缓解的实测效果）。
5. 本地对局（两人面对面）不在本次范围，但一期编排器应预留双人类玩家的落子归属判定（黑白双方都来自视觉）。
