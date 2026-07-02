# PRD：Kiosk 对弈模块物理棋盘化（LED 显示落子 + 摄像头识别棋局）

- **Track**: `kiosk-physical-play`
- **目标分支**: `feature/kiosk-physical-play`（worktree `/Users/fan/Repositories/katrain-kiosk-physical-play`，基于 develop @ 96e64f53）
- **作者**: fan
- **日期**: 2026-07-02
- **状态**: 草案 (Draft)
- **配套文档**: [`feasibility.md`](./feasibility.md)（同目录，2026-07-02 深度可行性调研：现状盘点、差距分析、架构方案、风险清单——本 PRD 不重复其内容，只在需要处引用）
- **范围**: kiosk 对弈模块三个子模块接入物理棋盘：**人机对弈·自由对弈、人机对弈·升降级对弈、人人对弈·在线大厅**。
  物理棋盘 = 361 颗 WS2812 LED 矩阵（显示落子/提示）+ 摄像头（识别棋局、确认落子）。
  **分两期**：一期 = 自由对弈 + 升降级对弈（本地闭环）；二期 = 在线大厅（kiosk↔远程对局代理）。

---

## 1. 背景与动机

智能棋盘的视觉识别能力（YOLO 四类检测、几何锁定、增量落子推断）与 LED 控制链路（串口服务、REST、权威 LUT）
已在摆谱（baipu）/ 训练数据采集轨道上跑通并合入 develop。现在要把这两项能力从「采集工具」升级为
**核心对弈体验**：用户在真实棋盘上摆子对弈，AI/对手的落子由 LED 在物理棋盘上点亮指示，
屏幕退居为计分板 + 兜底交互面板。

产品愿景（见记忆 cross_platform_play）：智能棋盘是所有围棋平台的物理入口——本轨道的一期打通
「物理棋盘 ↔ 本地 AI」，二期打通「物理棋盘 ↔ 在线对手」，为后续跨平台（OGS/野狐/星阵）复用同一物理循环打底。

**关键事实**（feasibility §0/§2）：「视觉落子注入对局」的后端主干已存在——
`_vision_move_poller`（`server.py:1810`）把视觉确认的落子经 `session.katrain("play")` 注入对局；
kiosk `GamePage` 挂载时已调 `visionBind(sessionId)`；对局路由已被 `PhysicalBoardGuard requireRecognition` 包裹。
本轨道一期的新增量集中在：**对局 LED 编排、混合确认兜底 UX、AI 选点（白灯）功能、物理一致性引导**。

---

## 2. 已拍板的设计决定（2026-07-02 brainstorm，全文见 feasibility §1）

| # | 决定 | 摘要 |
|---|---|---|
| D1 | 落子确认 = **混合** | 自动为主（MoveDetector 3 帧一致确认即落子）+ 异常兜底（低置信/盘面不一致时屏幕确认/纠正）。 |
| D2 | LED 四种语义 | ① AI/对手落子：黑→红、白→绿；② 提子→蓝；③ 几何漂移：**保持硬规则**（LED 绝不为几何自动闪灯；静默无 LED 外角重标定为主，失败才由用户手动触发 LED 重标定）；④ AI 最佳选点：白灯闪烁 top-N（个数由后端设置决定）。 |
| D3 | AI 选点门控 | 只能屏幕按钮**手动触发**（绝不自动；后续或加语音）。自由人机：需余额 + 场景开放（走 paid-analysis 计费轨道）；**升降级、人人对弈一律禁止**。引擎可配置：有余额→云端强引擎，无余额→按配置降级本地弱引擎或禁用。 |
| D4 | 分两期 | 一期自由+升降级；二期在线大厅（先出 kiosk↔远程对局代理设计再动手，推荐 remote-platform-adapter 方案，见 feasibility §4.2）。 |

---

## 3. 用户体验流程（一期核心 journey）

### 3.1 自由对弈全流程

```
选「自由对弈」→ AiSetupPage 配置（AI 策略/段位/棋盘/用时/执子色）→ 进入对局页
  ├─ [开局检查] 视觉确认物理棋盘为空盘（SETUP_IN_PROGRESS）
  │    · 盘上有残子 → 屏幕提示清盘，蓝灯点亮残子位置引导拿除
  │    · 让子局 → LED 逐点点亮让子星位（红灯），用户照灯摆黑子，视觉逐子确认
  ├─ [对局循环]
  │    用户回合：在物理盘摆子 → MoveDetector 3 帧确认 → 自动落子 → 屏幕更新 + 落子音
  │    AI 回合：AI 生成落子 → LED 点亮该点（AI 执黑→红 / 执白→绿）+ 屏幕高亮
  │              → 用户替 AI 把对应颜色棋子摆到亮灯处 → 视觉确认摆放正确 → 灯灭
  │              → 若有提子：蓝灯点亮全部待拿除的子（与 AI 落子灯同一 batch 混色下发）
  │              → 用户拿除 → 视觉确认盘面一致 → 蓝灯灭 → 回到用户回合
  │    （用户自己落子产生的提子同理：落子生效后蓝灯指示对方死子，拿完灯灭）
  ├─ [屏幕专属动作]（物理盘无法表达）：停一手 pass、认输、申请数子、悔棋、AI 支招（§3.3）
  └─ [终局] 数子/认输 → 屏幕展示结果 → LED 清灯 → 退出时 visionUnbind + led clear
```

**LED 熄灭时机**：以「视觉确认物理动作完成」为准（AI 子摆好→落子灯灭；死子拿完→蓝灯灭），
而非固定超时。5 分钟空闲失效保护（`server.py:1782`）会自动熄灯，属可接受行为：
下一次状态变化时编排器重新下发灯态即可（feasibility R6）。

### 3.2 升降级对弈（在 3.1 之上的差异）

- 强制开钟（现状已如此）；**落子时刻 = 视觉确认时刻**，确认期间屏幕显示「确认中」状态（开放问题 Q3）。
- **AI 支招按钮不出现**，服务端 `analysis_allowed` 关卡双重拒绝。
- 悔棋禁用（ranked 惯例）；异常纠正流程（§3.4）保留但不产生「改棋」语义——只用于恢复物理盘与对局的一致。

### 3.3 AI 支招（选点白灯）

```
用户点「AI 支招」按钮（仅自由对弈显示）
  → 后端门控链：场景开放? → 非 ranked? → 余额充足?（paid-analysis）→ 引擎路由（云端强 / 降级本地 / 403）
  → 返回 top-N 选点（N 由后端设置，默认建议 3）
  → 物理盘：白灯闪烁 N 个点；屏幕：同步高亮 + 各选点胜率/目差
  → 显示期间视觉 move 检测挂起（防白灯误检，feasibility R1）
  → 用户点「关闭」或超时（默认建议 30s）→ 白灯灭 → 检测恢复
  → 计费：按 paid-analysis 轨道规则扣费并在屏幕反馈余额
```

### 3.4 异常兜底（D1 混合确认的「兜底」半边）

| 触发 | 信号源（已存在） | 屏幕行为 | LED 行为 |
|---|---|---|---|
| 疑似落子但置信不足 | `ambiguous_stone` 事件 | 卡片「检测到疑似落子于 X，确认/忽略」 | 无 |
| 观测盘面 ≠ 期望盘面 | `MISMATCH_WARNING` | 差异视图（期望 vs 观测），选项：采纳观测 / 恢复物理盘（列出增删清单）/ 暂停对局 | 恢复模式下：多余子→蓝灯；缺失子→按棋色红/绿灯 |
| 棋盘不可见/遮挡 | `BOARD_LOST` / `DEGRADED` | 全屏遮罩「棋盘不可见」，恢复自动消退 | 保持现灯态 |
| 几何漂移 | `DriftStateMachine` | 静默无 LED 外角重标定；失败才弹「重新定位」按钮（用户触发 LED 基准灯重标定，守 D2③ 硬规则） | 仅用户触发后点基准灯 |
| 悔棋/跳变导航 | 用户屏幕操作 | 「请按指示恢复盘面」+ 增删清单 | 多余子蓝灯、需补回的子红/绿灯；完成后 `force_sync` 重建基线 |

### 3.5 在线大厅（二期，概要）

匹配、对局均发生在远程服务器；kiosk 本地负责视觉输入与 LED 输出。用户体验与 3.1 一致，
差异仅在「AI 回合」换成「对手回合」（等待时长不可控，需等待态 UI + 计时同步）+ 断线重连语义。
架构走 remote-platform-adapter（feasibility §4.2 方案 B），本 PRD 不展开，二期另立设计文档。

---

## 4. 功能需求

### R1 物理落子输入（视觉自动确认）
- R1.1 用户回合在物理盘摆子，经 `MoveDetector`（3 帧一致）确认后自动注入对局（复用 `_vision_move_poller`，无新增落子通道）。
- R1.2 落子生效时屏幕即时更新 + 落子音（复用现有 `sound` 广播）。
- R1.3 回合归属校验：非用户回合检测到新子 → 不注入，走 §3.4 异常流（AI 回合期待的是 AI 落子点的子，见 R2.2）。
- R1.4 pass / 认输 / 数子申请 = 屏幕按钮（现有 API：`/api/move pass_move` `/api/resign` `/api/count/*`）。

### R2 对局 LED 编排（后端编排器，核心新增）
- R2.1 新增后端 **PhysicalPlayOrchestrator**：订阅权威对局状态变化（session 状态回调 / `_vision_move_poller` 旁路），
  统一驱动 LED；前端不直接为对局逻辑调 LED（对比：摆谱页是前端直调——对局生命周期更长、需断连健壮性，权威在后端）。
- R2.2 AI 落子：点亮落子点（AI 执黑→红 `black`、执白→绿 `white`）；**等待视觉确认用户已替 AI 摆子**
  （观测盘面达到期望）后熄灭。摆错位置 → §3.4 mismatch 流。
- R2.3 提子：与落子灯同一 batch 混色下发蓝灯（`remove`）；视觉确认拿除后熄灭。
  **注意（2026-07-02 洞察，源自死活棋轨道讨论）：待拿除的子会把其下 LED 压住，蓝灯只是辅助通道——
  拿除类引导（提子、悔棋恢复）必须以屏幕列出待拿除子 + 语音提示为主通道。**
- R2.4 让子局开局：LED 引导摆让子（逐点或一次全亮，实施时定）；空盘检查残子用蓝灯指示。
- R2.5 生命周期：进对局绑定时 `clear`；退出/断连/会话过期时 `clear`；5 分钟失效保护熄灯后由下一次状态变化重新下发。
- R2.6 LED 写失败不阻塞对局（沿用 UI 容忍路径 `strict=False` 语义）；`/led/status` 不健康时屏幕显示物理棋盘降级徽标。

### R3 混合确认兜底 UX（前端，替换占位组件）
- R3.1 实现 §3.4 表格的全部四类屏幕交互（`ambiguous_stone`、`MISMATCH_WARNING`、`BOARD_LOST`、漂移），
  信号复用 `/ws/vision` + `SyncStateMachine`（`sync.py:65`），替换占位的 `MovePendingOverlay`。
- R3.2 差异视图必须给出可执行的恢复清单（哪些点多子/少子/错色），配合 R2 的恢复灯。
- R3.3 恢复完成 → `MoveDetector.force_sync` 重建基线 → 回 `SYNCED`。

### R4 AI 支招（选点白灯，全新功能）
- R4.1 新增 hint 端点（如 `POST /api/v1/hint`）：门控链 = 场景（仅 free）→ `analysis_allowed`（ranked 拒绝）→
  余额（paid-analysis）→ 引擎路由（云端强引擎 / 降级本地 / 禁用，后端可配置）。
- R4.2 返回 top-N 选点（N 后端可配置）；白灯闪烁 = 暴露服务层 `set_rgb_points`（`led_service.py:197`）
  的 REST（如 `POST /api/v1/led/hint`）+ 后端 asyncio 闪烁任务（周期 set/clear）。
- R4.3 **显示期间挂起 move 检测**（vision worker 新增 pause/resume 命令）；关闭/超时后恢复。
- R4.4 触发只能来自屏幕按钮（D3）；升降级/人人对弈不渲染按钮 + 服务端强制拒绝。
- R4.5 计费扣减与余额反馈接 paid-analysis 轨道（依赖项，见 §8）。

### R5 物理一致性引导（悔棋/导航/开局）
- R5.1 空盘检查（开局）与残子清理引导（R2.4）。
- R5.2 悔棋/重做/跳变导航后：生成物理盘增删清单 → 屏幕 + LED 引导（§3.4 末行）→ `force_sync`。
- R5.3 自由对弈允许悔棋（现有按钮），升降级禁用。

### R6 升降级差异化
- R6.1 hint 双重禁用（R4.4）；悔棋禁用（R5.3）；计时语义（§3.2，待 Q3 拍板）。
- R6.2 其余与自由对弈共用同一编排器与 UX（前端仍是同一 `GamePage`，`mode` 区分）。

### R7 视觉防误检加固（支撑 R2/R4）
- R7.1 短期：后端把「当前点亮的交叉点集合」告知 vision（或在 `board_state` 层遮蔽已点亮且非期望落子点），
  hint 白灯期间直接挂起检测（R4.3）。
- R7.2 长期（可与一期并行）：用摆谱采集台架收 `led_white`/`led_blue` 样本，扩 6 类重训（feasibility R1）。

### R8 在线大厅（二期，本期只留接口）
- R8.1 一期编排器不得写死「对手 = 本地 AI」：落子事件源抽象为「对局状态变化」，二期远程对手即插即用。
- R8.2 二期正式需求（大厅代理、对局桥、断线语义、段位记录对齐）在二期设计文档中定义。

---

## 5. 非目标（一期明确不做）

1. 在线大厅的实际联通（二期）；跨平台对弈（OGS/野狐/星阵）的物理化（复用二期成果，另行排期）。
2. 本地对局（两人面对面）——但 R8.1 的抽象为其留门（黑白双方都来自视觉）。
3. 语音交互（D3 提及"后续可能"）。
4. LED 为几何自动闪灯的任何形式（硬规则，永久非目标）。
5. 固件改动（现有 `SETI/SHOW/CLEAR/BRIGHT` 指令集够用；闪烁由主机驱动）。
6. 拍谱/摆谱模块的行为变更（共享 LED/vision 服务，但不动其流程）。

---

## 6. 现状可复用资产（已核实，详见 feasibility §2）

| 层 | 资产 | 位置 |
|---|---|---|
| 视觉→落子注入 | `_vision_move_poller` → `session.katrain("play")` | `katrain/web/server.py:1810-1861` |
| 增量识别 | `MoveDetector`（3 帧一致 + `force_sync`） | `katrain/vision/move_detector.py:22` |
| 对账状态机 | `SyncStateMachine`（6 态） | `katrain/vision/sync.py:65` |
| 视觉事件通道 | `/ws/vision` + 前端 `useVisionSync`/`VisionSyncOverlay` | `server.py:1707`；`src/kiosk/hooks/useVisionSync.ts` |
| 视觉绑定 | `GamePage` 挂载即 `visionBind(sessionId)` | `src/kiosk/pages/GamePage.tsx:43-48` |
| LED 服务 | `LedService`（串口线程 + 权威 LUT + strict/非strict 双队列） | `katrain/web/core/led_service.py` |
| LED REST | `/api/v1/led/point|points|clear|status`（黑红/白绿/提子蓝） | `katrain/web/api/v1/endpoints/led.py` |
| 任意 RGB（未暴露 REST） | `set_rgb_points` | `led_service.py:197` |
| 对局管线 | `AiSetupPage`+`GamePage`+`useGameSession`+`/ws/{sessionId}` | `src/kiosk/pages/`、`src/hooks/useGameSession.ts` |
| ranked 反作弊关卡 | `analysis_allowed` | `katrain/web/interface.py:200-202,705-708` |
| 漂移/重标定 | `DriftStateMachine` + `OuterCornerStrategy`（无 LED 默认） | `katrain/vision/drift_state_machine.py`、`calibration_strategies.py:17` |
| LED 引导样板 | 摆谱页（前端直调 LED + 提子闪烁 + 离场清灯） | `src/kiosk/pages/BaipuSessionPage.tsx:268-297` |
| 占位待替换 | `MovePendingOverlay`（"确认中…"空壳） | `src/kiosk/components/`（见 feasibility §2.4） |

**当前不存在、必须新建**：PhysicalPlayOrchestrator（R2）、混合确认 UI（R3）、hint 端点 + 白灯 REST + 闪烁任务（R4）、
vision pause/resume + 亮灯点遮蔽（R7.1）、物理一致性引导（R5）。

---

## 7. 验收标准（一期）

1. **纯物理对弈闭环**：在实机（SBC + 摄像头 + LED 棋盘）上完整下完一盘 19 路人机自由对弈，
   全程仅在物理棋盘摆子（屏幕只用于 pass/认输/数子），AI 每手落子灯、每次提子蓝灯均正确，终局清灯。
2. **让子局**：LED 正确引导让子摆放后正常开局。
3. **混合确认**：人为制造 ①摆错 AI 落子点 ②多摆一子 ③手遮挡棋盘 ④移动棋盘（漂移）四类异常，
   屏幕兜底流程均可恢复对局且不产生错着；全程 LED 无一次为几何自动闪灯。
4. **AI 支招**：自由对弈中按钮触发 → 白灯闪烁 top-N + 屏幕同步；显示期间摆子不被误识别；
   关闭后检测恢复；无余额时按配置降级/拒绝并有明确提示。
5. **升降级**：支招按钮不可见且服务端拒绝；计时含视觉确认期且 UI 有「确认中」状态；结果正确计入升降级。
6. **悔棋恢复**：自由对弈悔棋后按屏幕+LED 指引恢复盘面，`force_sync` 后继续对弈无错乱。
7. **健壮性**:拔插 LED USB / 摄像头后对局不崩，恢复后灯态与识别自动回归；LED 不健康时屏幕有降级徽标。
8. **回归**：摆谱模块行为不变；`CI=true uv run pytest tests` 相对基线（develop@96e64f53：37 failed 预存）无新增失败；
   `npm run build` 与 `npm run build:kiosk-2d`（含 `verify:kiosk-2d`）双绿。
9. 新增可调参数(top-N、闪烁频率、确认帧数等)有后端配置项与合理默认值。

---

## 8. 依赖与前置

| 依赖 | 状态 | 影响 |
|---|---|---|
| paid-analysis 计费轨道 | phases 1–4a 在 `feature/rk3588-ui`，4b/5/6 未完 | R4.5 计费门控。**动手前须定分支整合策略**（本分支基于 develop）。R4 可先以"场景+ranked 门控 + 引擎路由"落地，计费钩子留接口后接。 |
| rknn NPU 推理验证 | 后端已写，experimental | R2 延迟体验（CPU ~600ms/帧×3 帧 ≈ 2s 确认）。一期内实机验证（feasibility R2）。 |
| 拥挤盘面外角重标定实机精度 | "P12 Task 9 待硬件" | §3.4 漂移流的主路径质量（feasibility R3）。 |
| LED UR 象限 v4 硬件修复 | 待 board-swap 验证 | 不阻塞软件；UI 容忍路径已兜底（feasibility R4）。 |
| led_white/led_blue 扩类重训 | 未排期 | R7.2 长期方案；短期靠 R7.1 遮蔽+挂起。 |

---

## 9. 待确认问题

1. **Q1 分支整合**：paid-analysis（`feature/rk3588-ui`）与本分支（基于 develop）的合并顺序 / R4.5 是否一期后接。
2. **Q2 hint 参数默认值**：top-N 个数（建议 3）、白灯闪烁频率/占空比、展示超时（建议 30s）、每局次数上限？
3. **Q3 ranked 计时语义**：落子时刻 = 视觉确认时刻（建议）还是估计的物理放子时刻？确认延迟是否从用时中补偿？
4. **Q4 AI 落子等待语义**：用户迟迟不替 AI 摆子怎么办（灯常亮直到失效保护？屏幕提醒？是否阻塞用户下一手——建议阻塞，物理盘必须跟上对局）。
5. **Q5 双人类玩家抽象**（R8.1）：一期编排器按「落子事件源」抽象的具体接口形态，实施计划时定。
6. **Q6 音效/提示音**：AI 落子、异常、提子各配何种提示音（现有 `sound` 广播机制可承载）。

---

## 10. 实施阶段（一期）

- **P1 编排器骨架 + AI 落子灯**：PhysicalPlayOrchestrator（R2.1/R2.2/R2.5/R2.6）+ 自由对弈端到端
  「摆子→AI 应手→灯亮→摆 AI 子→灯灭」最小闭环（不含提子/异常）。
- **P2 提子 + 物理一致性**：R2.3/R2.4/R5（提子蓝灯、让子引导、悔棋恢复、开局检查）。
- **P3 混合确认 UX**：R3 全量（四类异常屏幕流 + 恢复灯 + force_sync）。
- **P4 AI 支招**：R4 + R7.1（hint 端点、白灯 REST、闪烁任务、检测挂起/遮蔽、按钮 UI、门控）。
- **P5 升降级差异化**：R6（含 Q3 拍板后的计时语义）。
- **P6 实机验证与加固**：NPU 推理验证、拥挤盘面重标定验证、验收标准 §7 全项过一遍。
- **（二期另立项）P7 在线大厅**：remote-platform-adapter 设计文档 → 实现。

每阶段完成须保持：双前端构建绿、pytest 相对基线无新增失败、摆谱模块回归正常。

---

## 11. 关键文件清单（预估改动面）

**后端（新增）**
- `katrain/web/core/physical_play_orchestrator.py`（R2，新）
- `katrain/web/api/v1/endpoints/hint.py` 或并入现有 endpoint（R4，新）
- `led_service.py` / `endpoints/led.py`：暴露白灯/hint REST（R4.2）
- `katrain/vision/worker.py`/`service.py`/`ipc.py`：pause/resume 命令 + 亮灯点遮蔽（R7.1）
- `server.py`：编排器装配进 board 模式 lifespan；`_vision_move_poller` 挂接点

**后端（复用/微调）**
- `interface.py`（`analysis_allowed` 接 hint 门控）、`sync.py`、`move_detector.py`（force_sync 触达）

**前端（kiosk，改动须守构建边界：只 import 共享区 + `src/kiosk/`）**
- `GamePage.tsx`：物理模式状态条、支招按钮、异常兜底挂载
- 新组件：混合确认差异视图 / 恢复清单（替换 `MovePendingOverlay`）、物理棋盘健康徽标
- `useVisionSync.ts`：事件覆盖面对齐 R3
- `AiSetupPage.tsx`：ranked 下隐藏支招相关设置（如有）

**测试**
- 新增：编排器单测（灯态 vs 对局状态转移表）、hint 门控矩阵测试、pause/遮蔽单测、异常流集成测试
- 既有回归：`test_led_service.py`、`test_led_api.py`、摆谱相关、`tests/web_ui/` 对局相关
