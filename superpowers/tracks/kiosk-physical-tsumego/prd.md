# PRD：Kiosk 死活棋（Tsumego）物理棋盘化（LED 引导摆题/应手 + 摄像头识别做题）

- **Track**: `kiosk-physical-tsumego`
- **目标分支**: `feature/kiosk-physical-tsumego`（worktree `/Users/fan/Repositories/katrain-kiosk-physical-tsumego`，基于 develop @ 96e64f53）
- **作者**: fan
- **日期**: 2026-07-02
- **状态**: 草案 (Draft)
- **关联轨道**: `kiosk-physical-play`（对弈物理化，分支 `feature/kiosk-physical-play`，文档在该分支
  `superpowers/tracks/kiosk-physical-play/{feasibility.md, prd.md}`）——视觉/LED 基础设施调研与
  对弈侧设计在那边；两轨道有共享件（见 §5 TR2.5/TR4 与 §8），**本轨道先建、对弈轨道复用**。
- **范围**: kiosk 死活棋做题页（`/kiosk/tsumego/problem/:problemId`）接入物理棋盘。
  覆盖：物理模式开关、初始局面摆放引导、物理落子做题、下一步提示白灯、答对/答错三通道反馈、
  试下适配、换题清盘，以及**修复 kiosk 答对提示乱码 bug + 统一两端文案**。

---

## 1. 背景与关键调研事实（2026-07-02，两个探索代理 + 人工核实）

1. **视觉 setup 集成早已铺线但 inert**：kiosk 做题页已被 `PhysicalBoardGuard requireRecognition` 包裹
   （`KioskApp.tsx:66`）、已把初始局面 POST `/api/v1/vision/setup-mode`（`TsumegoProblemPage.tsx:194-207`）、
   已内置 `BoardSetupGuide`（matched/total/missing 逐子引导 UI，`:365-372`）；后端 `SyncStateMachine`
   有专为死活题设计的 `SETUP_IN_PROGRESS`（`sync.py:236-264` `_check_setup` 逐帧比对并发
   `SETUP_PROGRESS{matched,total,missing}`/`SETUP_COMPLETE`）。**但两处断线使其从未工作**：
   - 前端 `useVisionSync.ts:67-68`：`sessionId===null` 时不开 `/ws/vision` WS；
   - 后端 `worker.py:290`：`_bound` 门槛——只有 game-session BIND 才喂帧给状态机，
     `ENTER_SETUP_MODE` 不置 `_bound`（`:326-328`），setup 事件永不产生。
2. **判题 100% 在前端**：`useTsumegoProblem.placeStone`（`useTsumegoProblem.ts:336-477`）沿 SGF 树
   找分支判对错（`sgfParser.ts:256` `isCorrectPath`：TE/GB/GW vs BM/DO + 中英文注释关键词）；
   对方应手 = 取主线第一子、`setTimeout 300ms` 自动落（`:433-466`）；提子也在前端（`removeCaptures`）。
   后端只存 SGF（`tsumego_problems.sgf_content`）+ 记进度（POST `/progress` 不判题）。
   → 对弈用的 `_vision_move_poller`→`session.katrain("play")` 注入路径**不适用**（做题无 Game 会话）。
3. **`/ws/vision` 事件通道已承载 `move_confirmed` 等事件**——物理落子可作为前端 `placeStone` 的
   第二输入源，判题逻辑零改动。
4. **LED 同亮上限实为固件 `MAX_ON=200`**（`smartbox-hardware-design/debug/led_bring_up_pio/src/main.cpp:35`，
   已亲自核实；协议文档骨架里的 20 已过时；真正兜底是 FastLED 5V/1500mA 限流）
   → 初始局面（常 5–30 子）一次全亮电气上可行。
5. **乱码 bug 定位**（证据充分）：两端答对文字共用同一 i18n 目录（`tsumego:solved`，cn=「正确！」，
   `.po/.mo`/传输全链干净 UTF-8），kiosk 不渲染 SGF 注释——文字链路复现不出乱码。
   **最可能元凶 = 🎉 emoji 缺字形**：两端 `SuccessOverlay` 都渲染 🎉（kiosk `SuccessOverlay.tsx:119`），
   kiosk 只自托管 Noto Sans SC + JetBrains Mono（`kiosk/theme.ts:4-8`）、无 emoji 字体，SBC 系统
   缺 emoji 字体即显豆腐块；galaxy 靠桌面系统字体正常。次要嫌疑：设备 `.mo` 不同步（实机核实项）。
   另发现 kiosk 侧栏 Alert 用不存在的 key `Correct!`（走 fallback「正确!」），两端文案本就不统一。
6. **声音机制现成**：前端 `useSound`（`Audio` API + `/assets/sounds/*` 静态资产），做题页已接
   落子/提子/答错(boing)/答对(victory1) 音。无会话场景后端 sound 广播不可用也不需要。
7. **提示功能现成**：屏幕绿色圈显示 SGF 正解点（单点、本地、免费不限次，`toggleHint` +
   `TsumegoBoard.tsx:224-230`）。
8. **试下 = 前端本地快照分支**（`tryModeSnapshotRef`，`useTsumegoProblem.ts:575-608`），
   无对错判定，物理盘在试下期间本来不动。
9. board 模式题库经 `RepositoryDispatcher`→远端拉取（离线读空）；进度离线本地落库+发件箱同步。
10. `TsumegoBoard` 全盘渲染（角部题显示整个 19 路盘），题目坐标即盘面坐标，物理映射无需转换。
11. **LED 服务现状**：REST `/api/v1/led/{point,points,clear,status}`（黑→红/白→绿/拿除→蓝，
    每次 set_points = 清屏+重设整帧）；任意 RGB 的 `set_rgb_points`（`led_service.py:197`，白灯用）
    **未暴露 REST**；固件无 blink 指令，闪烁由主机驱动。

---

## 2. 已拍板的设计决定（2026-07-02 brainstorm）

| # | 决定 | 内容 |
|---|---|---|
| T1 | 物理模式开关 | 做题页提供「使用物理棋盘 / 退出」按钮（手动 opt-in）；**状态记住上次选择**（localStorage），首次默认关。 |
| T2 | 初始局面摆放 | 先摆全部黑棋（红灯），再摆全部白棋（绿灯）；**只点亮未摆的子、摆一颗灭一颗**（进度反馈；硬件允许全亮但保留此交互）；kiosk 界面文字 + 语音提示协同；摄像头逐子识别并在界面展示（复用 BoardSetupGuide）。 |
| T3 | 对方应手点灯 | **加入**：应手点亮棋色灯（黑→红/白→绿），用户替对方摆子，视觉确认后灯灭。 |
| T4 | 提示白灯 | 屏幕提示按钮物理化：SGF 正解点白灯闪烁（**单点**）；**照旧免费不限次**；显示期间挂起识别。与对弈轨道「AI 支招 top-N 计费」是两个不同功能，互不影响。 |
| T5 | 答对/答错三通道 | 界面 + 声音（现成）+ 灯光（新增）：**答错 = 错着点蓝灯闪烁**（语义直接衔接拿除引导）；**答对 = 若干空交叉点白灯双闪**（避开被子压住的点）。 |
| T6 | 答错恢复 | 蓝灯指示拿除错着（及已落的应手），但**棋子会压住蓝灯**→ 主通道 = kiosk 界面显示待拿除的子 + 语音提示（泛提示，不必具体到坐标），灯光为辅。拿除后视觉确认回到错着前局面再重试。 |
| T7 | 试下 | 不做 LED 适配；**进入试下挂起物理盘识别，退出时校验物理盘仍与题面一致**（不一致走异常恢复）。 |
| T8 | 换题 | **全清再摆（v1）**：屏幕+语音提示清空棋盘（灯光辅助），视觉确认空盘后进入下一题摆放引导。差分重摆留二期优化。 |
| T9 | 乱码修复 | **去 emoji 换 SVG/MUI 图标 + 统一两端答对文案**（都走 `tsumego:solved`；清理 kiosk 用不存在 key `Correct!` 的重复 Alert）；实机核实 `.mo` 作为验证步骤。 |

---

## 3. 用户体验流程

```
进入做题页（物理模式开，按 T1 记忆）
  ├─ [清盘检查] 盘上有子 → 屏幕+语音「请清空棋盘」→ 视觉确认空盘
  ├─ [摆放初始局面]（vision setup 模式）
  │    阶段1：全部黑子位置红灯亮 → 语音「请摆放黑棋」→ 每摆对一颗该灯灭、界面进度 +1
  │    阶段2：全部白子位置绿灯亮 → 语音「请摆放白棋」→ 同上
  │    完成 → SETUP_COMPLETE → 语音「摆放完成，请开始解题」→ 进入做题
  ├─ [做题循环]（move 监测开）
  │    用户在物理盘落子 → MoveDetector 确认 → 前端 placeStone() 判题
  │      ├─ 答错 → 屏幕 Alert/抖动 + boing 音 + 错着蓝灯闪
  │      │         → 界面列出待拿除的子 + 语音「答错了，请取回棋子」
  │      │         → 视觉确认回到错着前局面 → 继续重试
  │      ├─ 答对未完 → 应手自动落屏幕 + 应手点棋色灯亮
  │      │         → 用户替对方摆子 → 视觉确认 → 灯灭
  │      │         → （若判题含提子：界面+语音引导拿除被吃子，视觉确认）→ 等下一手
  │      └─ 答对完成 → SuccessOverlay（图标版，无 emoji）+ victory 音
  │                  + 若干空点白灯双闪 → auto-advance / 下一题 → [换题清盘 T8]
  ├─ [提示] 点提示按钮 → 屏幕绿圈照旧 + 正解点白灯闪烁 → 识别挂起 → 关闭/落子前恢复
  ├─ [试下] 进入 → 识别挂起，纯屏幕自由探索 → 退出 → 校验物理盘与题面一致
  └─ [退出物理模式 / 离开页面] → LED 清灯、退出 setup/监测、记忆开关状态
```

**视觉模式只有两种，交替使用**（架构核心简化）：
- **「逼近目标盘面」**（setup 语义）：初始摆放、应手摆放、提子/错着拿除、换题清盘、试下退出校验——
  全部统一为 `enter_setup_mode(target_board)`，等观测盘面 == 目标盘面；
- **「等一手新子」**（move 监测）：仅在轮到用户落子时开启。
提示/试下期间两者皆挂起。

**编排归属**：判题状态在前端 React → **前端编排**（LED 由前端直调、状态机在前端 hook），
与对弈轨道「权威状态在后端 session → 后端编排」的原则一致（权威状态在哪，编排就在哪）。

---

## 4. 功能需求

### TR1 物理模式开关
- 做题页「使用物理棋盘」切换按钮；状态 localStorage 持久化（T1）；
  关闭时页面行为与现状完全一致（含 vision setup 调用也不发）。
- `PhysicalBoardGuard` 语义调整：物理模式关闭时不强制标定就绪（现 `requireRecognition` 无条件）。
- 屏幕点击落子在物理模式下**仍然可用**（双输入并存）。

### TR2 视觉链路接通（后端小改，本轨道最基础的接线）
- TR2.1 前端：`useVisionSync` 支持无 sessionId 打开 `/ws/vision`（订阅与 bind 解耦）。
- TR2.2 后端：worker 放行 setup——`ENTER_SETUP_MODE` 使帧进入 `SyncStateMachine`
  （引入 `setup_active`/monitor 门槛或等效机制，不依赖 game-session BIND）。
- TR2.3 `_check_setup` 增加**多余子（extra）**输出：目标盘面比观测少子时（拿除引导场景），
  事件需给出「该拿走哪些」；`SETUP_COMPLETE` 必须要求观测与目标**完全相等**（现状是否如此需先核实）。
- TR2.4 无 bound session 时 move 监测可独立运行并经 WS 发 `move_confirmed`
  （`_vision_move_poller` 因 `bound_session_id` 为空天然跳过，不冲突）。
- TR2.5 挂起/恢复识别命令（**共享件**：对弈轨道同样需要，本轨道先建）。

### TR3 物理落子做题（前端编排）
- 新 hook（如 `usePhysicalTsumego`）：消费 `/ws/vision` 的 `move_confirmed` → 调 `placeStone(x,y)`
  （判题/应手/提子零改动）；按 §3 状态机在「setup 目标」与「move 监测」间切换，每步后把
  判题产生的新盘面设为 setup 目标或 move 基线。
- 非用户回合（应手未摆完、拿除未完成）检测到的落子不注入判题，走引导提示。

### TR4 LED 编排（前端直调，仿摆谱模式）
- 初始摆放：missing 列表驱动红/绿灯（T2）；应手灯（T3）；错着/拿除蓝灯（T5/T6）；
  答对空点白灯双闪（T5，前端从当前盘面选空点，如星位中的空点，数量 ≤9）；提示白灯闪烁（T4）。
- 生命周期：进入/退出物理模式、离开页面、换题时 `clear`；5 分钟失效保护熄灯后由下一状态变化重亮。
- 白灯依赖新 REST（暴露 `set_rgb_points` + 闪烁驱动，**共享件**，本轨道先建、对弈轨道复用）。
- LED 写失败不阻塞做题（UI 容忍路径），`/led/status` 不健康时显示降级徽标、流程照走（屏幕引导兜底）。

### TR5 三通道反馈与乱码修复（T5/T9）
- SuccessOverlay（两端）：🎉 替换为 MUI SVG 图标（如 `EmojiEvents`/`Celebration`）——彻底免疫字体问题；
  kiosk 与 galaxy 视觉/文案统一，均用 `t('tsumego:solved')`（cn=「正确！」）。
- 清理 kiosk 侧栏 `t('Correct!','正确!')` Alert（key 不存在，且与 SuccessOverlay 重复）。
- 实机验证步骤：kiosk 设备上查 `/api/translations?lang=cn` 返回字节，排除 `.mo` 不同步的次要嫌疑。
- 答错保留现有 Alert + boing 音，增加蓝灯闪（T5）；kiosk 可补 galaxy 已有的棋盘抖动动画（对齐体验）。

### TR6 语音提示（新）
- 预生成一小组中文语音片段（edge-tts，教程轨道流水线现成）：
  「请清空棋盘」「请摆放黑棋」「请摆放白棋」「摆放完成，请开始解题」「答对了」
  「答错了，请取回棋子」「请提走被吃的棋子」。
- 静态资产（如 `/assets/sounds/voice/*.mp3`），前端 `useSound` 扩展或新 `useVoice` hook 播放；
  仅物理模式播放语音（纯屏幕模式保持现状）。

### TR7 试下与换题（T7/T8）
- 试下：进入挂起识别（TR2.5），退出用 setup 校验（target=当前题面）；不一致 → 屏幕引导恢复。
- 换题/重做本题：全清引导（setup target=空盘）→ 下一题摆放；
  auto-advance（答对 1.5s 跳下一题）在物理模式下改为「清盘引导完成后再进入下一题」。

---

## 5. 非目标

1. 判题下沉后端 / 引入引擎判题（保持 SGF 树前端判题）。
2. 死活题接计费（提示免费不限次，T4）。
3. 差分换题（二期优化）、局部棋盘渲染、非 19 路题的物理支持（v1 仅 19 路，见 Q1）。
4. galaxy 网页端的物理棋盘支持（物理硬件只在 kiosk）。
5. LED 为几何自动闪灯（硬规则：LED 绝不为几何自动闪灯，重标定主路径是无 LED 外角法，
   LED 基准灯仅限用户手动触发——与对弈轨道一致）。
6. 对弈模块的任何改动（对弈物理化在 `feature/kiosk-physical-play` 轨道）。

---

## 6. 验收标准

1. **实机完整闭环**：开启物理模式，完成一道多手死活题——清盘检查、黑红/白绿分阶段摆放
   （摆一颗灭一颗、界面进度、语音提示）、物理落子判题、应手点灯并确认、答对三通道反馈、换题清盘引导。
2. **答错流**：物理下出错着 → 蓝灯闪 + 界面列出待拿除子 + 语音 → 拿除后可重试并最终答对。
3. **含提子的题**：应手或用户落子产生吃子时，拿除引导正确、视觉确认后流程继续。
4. **提示**：白灯闪烁正解点，显示期间在物理盘摆子不被误注入；关闭后识别恢复。
5. **试下**：试下期间碰物理盘不影响题目状态；退出校验通过/不通过两条路径都正确。
6. **乱码修复**：kiosk 答对提示与 galaxy 视觉一致、无豆腐块/乱码（实机验证 + `.mo` 字节核实）；
   两端文案统一为 `tsumego:solved`。
7. **开关记忆**：退出重进保持上次选择；物理模式关闭时所有现有行为不变（回归）。
8. **健壮性**：LED/摄像头断连时做题可降级为纯屏幕继续；页面退出无 LED 残留。
9. `npm run build` + `npm run build:kiosk-2d`（含 `verify:kiosk-2d`）双绿；
   `CI=true uv run pytest tests` 相对基线（develop@96e64f53）无新增失败。

---

## 7. 风险与开放问题

| # | 风险/问题 | 说明与缓解 |
|---|---|---|
| R1 | `_check_setup` 对「多余子」的行为未验证 | 实施首项核实：`SETUP_COMPLETE` 是否要求完全相等、`missing` 之外是否需新增 `extra` 字段（TR2.3）。 |
| R2 | 白灯/蓝灯 YOLO 误检（模型只训了 black/white/led_red/led_green 四类） | 显示期间挂起识别（TR2.5）+ 已点亮点遮蔽；长期 led_white/led_blue 扩类重训（与对弈轨道共享收益）。 |
| R3 | 应手/摆放等待中用户乱动子 | setup 语义天然容错（观测≠目标就不前进），界面持续显示 missing/extra 引导。 |
| R4 | board 模式离线时题库读空 | 既有行为，但物理模式依赖在线拉题；界面需明确离线提示。 |
| R5 | SBC 推理延迟（onnx CPU ~600ms/帧 × 3 帧一致 ≈ 2s 确认） | 做题为回合制、无计时压力，可接受；rknn NPU 验证在对弈轨道推进，收益共享。 |
| Q1 | 库中 boardSize≠19 的题占比 | 实施时查数据；v1 对非 19 路题隐藏物理模式开关。 |
| Q2 | 语音音色/语言配置 | 沿用教程轨道 TTS 配置？实施时定。 |
| Q3 | 与 `sbc-tsumego-parity` 轨道的协调 | 该轨道（kiosk 死活题导航/进度对齐 galaxy）改同一批页面且含「Vision 残留清理」项——先后顺序与冲突需对齐。 |
| Q4 | 正解标注口径 | `isCorrectPath` 匹配「正解/成功/失败/错」等关键词，数据 skill 文档提到「✓/✗」标记——若题库真用 ✓/✗ 会走「第一分支=正解」兜底，判题物理化前建议抽查题库核对。 |
| Q5 | 与对弈轨道的共享件归属 | 白灯 REST、pause/resume、亮灯点遮蔽在**本轨道先建**；两分支先后合回 develop 时以先合者为准、后合者 rebase 复用。 |

---

## 8. 实施阶段

- **TP1 接线与摆放引导**：TR2.1/2.2（WS 无 session + worker 放行 setup）→ 初始摆放全流程
  （missing 红/绿灯 + BoardSetupGuide + 开关按钮/记忆 + 清盘检查）。交付用户功能点 (1)(2)。
- **TP2 物理落子做题闭环**：TR2.4 + TR3 + 应手点灯（T3）+ 含提子流。
- **TP3 对错三通道 + 乱码修复**：TR5 + 答错拿除引导（TR2.3 extra 支持）。交付功能点 (4)。
- **TP4 提示白灯 + 试下 + 换题**：TR4 白灯 REST（共享件）+ TR2.5 + TR7。交付功能点 (3)。
- **TP5 语音**：TR6。
- **TP6 实机验证**：验收 §6 全项。

---

## 9. 关键文件清单（预估改动面）

**前端（kiosk 为主，守构建边界：kiosk 文件只 import 共享区 + `src/kiosk/`）**
- `kiosk/pages/TsumegoProblemPage.tsx`：物理模式开关、状态机挂载、LED 编排、语音
- 新 hook：`kiosk/hooks/usePhysicalTsumego.ts`
- `hooks/useVisionSync.ts`：无 session 开 WS（TR2.1，共享文件影响两端——双构建验证）
- `components/tsumego/SuccessOverlay`（kiosk `kiosk/components/tsumego/` + galaxy
  `galaxy/components/tsumego/` 两份）：去 emoji 换图标、文案统一（TR5）
- `kiosk/components/vision/BoardSetupGuide.tsx`：黑/白分阶段、extra 子显示
- `api/ledApi.ts`：hint 白灯方法

**后端**
- `katrain/vision/worker.py`/`sync.py`/`service.py`/`ipc.py`：setup 放行、extra 子、pause/resume、
  无 bind 的 move 监测（TR2）
- `katrain/web/api/v1/endpoints/led.py` + `katrain/web/core/led_service.py`：白灯 REST（共享件）
- `katrain/web/api/v1/endpoints/vision.py`：暂停/恢复端点（共享件）

**资产**
- `katrain/sounds/voice/*.mp3`（TR6 预生成语音）

**测试**
- setup extra/complete 语义单测、无 bind move 监测单测、白灯 REST 测试、
  两端 SuccessOverlay 渲染回归、做题页物理模式开/关行为回归
