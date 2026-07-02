# Review Request：Kiosk 死活棋物理棋盘化（PRD + 实施计划，实现前设计审阅）

- **日期**: 2026-07-02
- **审阅对象**（同目录，均为中文文档）:
  - `superpowers/tracks/kiosk-physical-tsumego/prd.md` — 需求与设计决定（T1–T9）、验收标准、风险
  - `superpowers/tracks/kiosk-physical-tsumego/plan.md` — 11 个 TDD 任务的逐步实施计划（含完整代码片段）
- **审阅时机**: **尚未写任何实现代码**。这是动手前的最后一轮设计/计划审查，目标是把设计缺陷、
  竞态、遗漏的边界情况在实现前找出来。
- **仓库**: 本 worktree（`/Users/fan/Repositories/katrain-kiosk-physical-tsumego`，分支
  `feature/kiosk-physical-tsumego`，基于 develop@96e64f53）。计划中引用的所有代码行号
  以当前工作区为准，可直接打开核对。

---

## 1. 三分钟背景

KaTrain 是 Go/围棋教学应用（FastAPI 后端 + React/Vite 前端）。产品形态之一是跑在
RK3588 SBC 上的 **kiosk 触屏终端**，外接一块带 **361 颗 LED**（每个交叉点一颗）和
**顶置摄像头**（YOLO 识别黑/白子 + 红/绿 LED）的实体棋盘。

对弈（下棋）的物理化在另一条轨道 `kiosk-physical-play` 上做（后端编排，权威状态在
后端 Game session）。**本轨道**做的是**死活棋（tsumego）做题页**的物理化：

- LED 引导用户在实体棋盘上摆出题目初始局面（黑子亮红灯、白子亮绿灯，摆一颗灭一颗）；
- 摄像头识别用户的物理落子，注入**现有的前端判题逻辑**（沿 SGF 树判对错，零改动）;
- 答对/答错三通道反馈（屏幕 + 声音 + 灯光）、对方应手点灯、提示白灯、答错拿除引导、换题清盘；
- 顺带修复一个实机乱码 bug（答对提示 🎉 emoji 在 SBC 上因缺字形显示豆腐块）。

关键前提（已调研核实，PRD §1 有证据链）：

1. **判题 100% 在前端** `useTsumegoProblem`（React state 里沿 SGF 树走分支），后端只存 SGF、
   记进度。因此本轨道选择**前端编排**（新 hook `usePhysicalTsumego` 直调 LED REST 并消费
   vision WebSocket 事件），与对弈轨道的后端编排原则一致——权威状态在哪，编排就在哪。
2. 视觉后端已有 `SyncStateMachine`，含专为死活题设计的 `SETUP_IN_PROGRESS` 状态
   （逐帧比对目标盘面并发进度事件），但因两处断线从未真正工作：前端 `useVisionSync`
   在 `sessionId===null` 时不开 WS；后端 worker 只有 game-session BIND 才喂帧。
   本计划的后端改动主要就是打通这两处（monitor 模式 + pause 命令 + extra 子检测 + 3 个 REST）。
3. 视觉交互统一为两种模式交替（架构核心简化）：**「逼近目标盘面」**（setup 语义，覆盖
   清盘/初始摆放/应手确认/错着拿除/试下退出校验）与**「等一手新子」**（move 监测，仅用户
   回合开启）。提示/试下期间两者皆挂起。

---

## 2. 请重点审阅的问题

### A. 前端编排状态机（plan Task 8，风险最高的部分）

`usePhysicalTsumego` 相位机：`off → clearing → setup → ready → replying / removing → solved`。
计划里给出了完整的 hook 代码（plan.md Task 8 Step 1）。请审：

1. **事件消费的丢失/重复风险**：hook 用 `latestEvent`（单事件 state）+ `processedEventRef`
   去重。若两个事件在一次 React 渲染间隙内先后到达（WS onmessage 连发），`latestEvent`
   会被覆盖，前一个事件丢失。计划风险 #4 自己也承认了这点并给了备选（`syncEvents` 队列 +
   已处理索引）。**问题：应该现在就改成队列式消费，还是等实机出问题再改？丢一个
   `setup_progress` 无害（下一帧会再发），但丢 `setup_complete` 或 `move_confirmed` 呢？**
2. **`replying` 相位的收敛逻辑**：答对后对方应手由 `useTsumegoProblem` 内部 `setTimeout 300ms`
   自动落到屏幕，hook 靠「watch `stones` 变化 + phase==='replying'」把新盘面 POST 成 setup
   target，并点亮最后一颗子的灯。请审：`stones` 更新与 `setup_complete` 事件之间是否存在
   顺序竞态（比如用户手快，应手还没落屏幕就先在物理盘摆了子）？此时物理盘会比 target 多
   一颗子（extra），setup 语义能否自愈？
3. **答错含提子的边界**（plan 风险 #5）：错着提走了对方子时，恢复目标是错着前盘面，
   用户需要「取回错着 + 放回被提子」。v1 语音只有泛提示、屏幕只列 extra（missing 只有数字）。
   这个简化可接受吗？会不会造成用户困惑卡死？
4. **`solved` 相位的时序**：`celebrate()` 是 async 双闪（约 1.2s），期间若用户点「下一题」
   （problemId 变化 → restartKey 翻转 → enable-effect 重跑 → `ledClear`），闪烁循环里的
   `ledPoints` 还会继续 set 吗？（celebrate 没有 abort 机制。）
5. **restartKey 接线**（plan Task 9 Step 3(g)）：为了换题时重启物理流程，页面用
   `physicalCycle` state + effect 递增，hook 的 enable-effect 依赖 `[enabled, restartKey]`。
   这个写法能保证「换题必先走 clearing」吗？有没有更简洁的模式（比如直接把 problemId
   传进 hook 当依赖）？

### B. 后端 vision 改动（plan Task 1–4）

6. **`_check_setup` 严格相等**（Task 1）：`SETUP_COMPLETE` 改为要求 `matched == total` 且
   `extra` 为空，完成后 `_expected_board = observed.copy()`、状态转 `SYNCED`。请对照
   `katrain/vision/sync.py` 现有状态机核对：这个转移对后续 move 检测的基线是否正确？
   清盘场景（target=空盘）完成后转 SYNCED 是否会让 move 检测在「摆初始局面」阶段误报落子？
   （计划的答案是 gating：monitor 模式下 move 检测只在 SYNCED 且 hook 随即 POST 新的
   setup target 把状态机拉回 SETUP_IN_PROGRESS——请审这个窗口期。）
7. **gating 函数语义**（Task 2）：`should_detect_moves(bound, monitor, paused, sync_state)`
   ——bound（对弈）路径完全不看 sync_state 以保持现状，monitor 路径只在 `synced`。
   两个 worker（`worker.py` 子进程版 / `worker_inprocess.py`）改动是否等价、有没有漏改点？
8. **事件路由**（Task 3）：monitor 模式发 **dict** 事件走 `/ws/vision`，对弈路径继续发
   `ConfirmedMove` dataclass 给 poller。这个「按类型分流」依赖 `server.py` WS handler
   只转发 dict 的现状——是隐式契约，值得加测试或注释锁定吗？另外 `/ws/vision` 的事件
   队列是**单消费者**（第一个轮询到的连接取走），kiosk 页面若意外开了两条 WS（比如
   GeometryVideoPanel 复用），事件会被分流。计划赌「做题页只开一条」，够稳吗？
9. **REST 设计**（Task 4）：`/vision/monitor`、`/vision/pause`、`/vision/expected-board`
   三个端点无鉴权、无幂等标识（kiosk 局域网单机可接受？），`pause` 是全局布尔而非
   引用计数——若「提示」与「试下」同时开又先后关，先关的一方会把另一方的 pause 也解掉。
   页面层用 `paused = showHint || isTryMode` 单一布尔透传规避了这点——请确认这个规避是否完备。

### C. 计划本身的质量

10. **Task 9 Step 3(e) 的 matched 计算**：
    `matched={(stones.length) - physical.missing.length - (physical.stage === 'black' ? 0 : 0)}`
    ——末尾的三元表达式恒为 0，且 `stones.length` 是全部目标子数、`missing` 是**当前阶段**
    过滤后的缺子数，两者口径不一致（白阶段时 matched 会虚高）。这是计划里的明显笔误/
    逻辑错，请给出正确口径（或建议 BoardSetupGuide 直接吃 stage 内的 matched/total）。
11. **TDD 结构**：Task 6/7/8/9（纯前端）没有单元测试，只有构建验证 + 实机验收。
    `usePhysicalTsumego` 是全计划最复杂的状态机——值得上 vitest/@testing-library
    做 hook 级测试吗？还是相位机逻辑先抽成纯函数（reducer 形式）再测？
    （仓库前端现状：只有 Playwright e2e，无单测框架。引入成本 vs 收益请给判断。）
12. **遗漏检查**：对照 PRD §3 的用户流程图逐条走查 plan 的任务覆盖——有没有 PRD 承诺
    但计划没落地的环节？（我们自查发现的简化已列在 plan「Self-Review 记录」：提示白灯
    v1 常亮不闪、答对双闪用空星位、换题走全清。这些 PRD 允许。）
13. **屏幕/物理双输入并存**（PRD TR1）：物理模式下屏幕点击落子仍可用。若用户屏幕点了
    一手，物理盘就落后于屏幕一颗子——计划里哪个机制负责把物理盘拉回一致？（`ready`
    相位下屏幕落子后没有显式 POST 新 expected-board/setup target 的路径——这可能是
    真空白，请确认并给建议。）

### D. 值得挑战的设计决定（有既定结论，但欢迎推翻）

- 前端编排（vs 判题下沉后端）：PRD §5 非目标 1 已拍板保持前端判题。若你认为前端编排
  在可靠性上不可救药，请给出具体失败场景。
- LED 由前端直调 REST（vs 后端统一编排 LED）：仿现有摆谱页模式。
- 语音用预生成 mp3 静态资产（vs 运行时 TTS）：SBC 离线可用性优先。

---

## 3. 硬约束（审阅时请检查计划没有违反）

1. **kiosk 构建边界**：`src/kiosk/**` 只能 import 共享区（`src/components/`、`src/hooks/`、
   `src/api*`、`src/utils/` 等）+ `src/kiosk/`；禁止 three.js/galaxy。改共享文件必须
   `npm run build && npm run build:kiosk-2d` 双绿。（详见仓库根 `CLAUDE.md`「SBC 构建边界契约」。）
2. **LED 颜色语义不可变更**：`black`→红、`white`→绿、`remove`→蓝；新增 `hint`→白。
   固件同亮上限 MAX_ON=200；固件无 blink，闪烁由主机驱动。
3. **LED 绝不为几何自动闪灯**（硬规则）：本计划不得触碰几何/标定代码。
4. **判题保持前端 SGF 树**，不引入引擎判题；死活题提示免费不限次，不接计费。
5. **对弈模块零改动**（对弈物理化在 `feature/kiosk-physical-play` 轨道）；对弈既有行为
   （bound 路径）不得回归。
6. pytest 基线：develop@96e64f53 上有 ~53 项环境性预存失败；验收口径是**不新增失败**。

---

## 4. 关键代码索引（供对照计划核实）

**后端（计划要改的）**
- `katrain/vision/sync.py:236-265` — `_check_setup`（Task 1 改这里）
- `katrain/vision/worker.py:256-334` / `katrain/vision/worker_inprocess.py:171-234` — 帧循环
  与命令处理（Task 3）
- `katrain/vision/service.py` / `katrain/vision/ipc.py` — service 方法 + CommandType（Task 2/3）
- `katrain/web/api/v1/endpoints/vision.py` — 新 REST（Task 4）
- `katrain/web/core/led_service.py:52-59` — COLOR_RGB（Task 5）

**前端（计划要改/新建的）**
- `katrain/web/ui/src/hooks/useTsumegoProblem.ts:336-477` — `placeStone` 判题（**不改**，
  只消费；`:509-522` `undo()` 的 isFailed 分支是答错恢复的关键依赖）
- `katrain/web/ui/src/kiosk/hooks/useVisionSync.ts:67-68` — sessionId gate（Task 6 解耦）
- `katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx` — 页面集成（Task 9）
- `katrain/web/ui/src/kiosk/components/vision/BoardSetupGuide.tsx` — 摆放引导 UI（Task 9）
- `katrain/web/ui/src/kiosk/components/tsumego/SuccessOverlay.tsx:117-120` /
  `katrain/web/ui/src/galaxy/components/tsumego/SuccessOverlay.tsx:137-147` — 乱码修复（Task 10）
- `katrain/web/ui/src/api/ledApi.ts` — LED client（Task 5）
- 新建：`src/kiosk/hooks/usePhysicalTsumego.ts`（Task 8）、`src/kiosk/hooks/useVoice.ts`（Task 7）

**坐标约定**（全计划统一，审阅代码片段时留意换算）：vision 坐标 `board[row][col]`
row 0 = 顶；前端 Stone `coords=[col, y]` y 0 = 底；转换 `visionRow = boardSize - 1 - y`。
LED REST 用 vision 坐标。

---

## 5. 期望的反馈格式

请按以下分级输出发现，每条注明**文档与章节/任务号**（如 `plan.md Task 8 Step 1`）或
**代码位置**，并给出具体修改建议（不是泛泛的「建议考虑」）：

- **[Blocker]** 设计缺陷/竞态/数据丢失——实现前必须改计划
- **[Major]** 高概率返工点或明显更优的替代方案
- **[Minor]** 笔误、口径不一致、可读性
- **[Question]** 需要作者补充信息才能判断的点

§2 列出的 13 个问题请逐条给出明确判断（同意计划现状 / 建议修改 + 怎么改）。
除此之外自由发挥——尤其欢迎找出我们没列进 §2 的问题。
