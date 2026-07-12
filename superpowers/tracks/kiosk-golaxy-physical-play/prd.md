# PRD：星阵人机对弈接入物理棋盘（LED 引导 + 摄像头识别）

- **Track**: `kiosk-golaxy-physical-play`
- **分支**: `feature/kiosk-play-golaxy`（worktree `/Users/fan/Repositories/katrain-kiosk-play-golaxy`，已合 develop 至 f06440c4）
- **作者**: fan
- **日期**: 2026-07-11
- **状态**: 已实现（待 rk3562 真机验证）
- **前置轨道**:
  - [`kiosk-play-golaxy/plan.md`](../kiosk-play-golaxy/plan.md) — 星阵人机对弈闭环（已上线真机验证，含 §12 设置面板、§13 分析道具）
  - [`kiosk-physical-play/prd.md`](../kiosk-physical-play/prd.md) — 自由对弈物理棋盘化一期（PhysicalPlayOrchestrator 后端编排，已实现合入 develop）

---

## 1. 背景与动机

自由对弈的物理棋盘闭环（视觉落子注入 + LED 对账引导 + 混合确认兜底 + AI 支招白灯）已由
kiosk-physical-play 一期实现并合入 develop。星阵人机对弈（golaxy engine-play）作为跨平台对战的
首个可用平台也已真机验证。本轨道把两者接通：**用户在物理棋盘上与星阵 AI 对弈** ——
摆子经摄像头识别注入、星阵 AI 回招由 LED 点亮引导、支招道具白灯闪烁。

physical-play PRD R8.1 的「落子事件源抽象」（编排器只消费 `game_update` state dict）为本轨道打了底：
**大部分管线已天然兼容**，本轨道是缺口修补 + 加固，不是重建。

### 1.1 已核实的兼容现状（勿重查）

| 环节 | 现状 | 证据 |
|---|---|---|
| 视觉落子 → 星阵隧道 | ✅ 已通 | `_vision_move_poller` 平台分支 `gateway.play_move`（`server.py:1999-2009`），engine 分支进隧道；失败 re-arm 检测 |
| 对局页 vision 管线 | ✅ 已挂 | `GamePage` 的 `useVisionSync`/`PhysicalBoardGuard`/相机断连提示/LED 徽标不区分 `engineMode`；engine 路由已被 guard 包裹（`KioskApp.tsx:57`） |
| board 模式平台栈 | ✅ 已注册 | `_init_platform_manager` 在 board 模式调用（`server.py:524`）；星阵 token 存设备端 credential store |
| 回合校验 | ✅ 已通 | poller R1.3 用 `last_state["player_to_move"]` 校验，engine 局同样成立 |
| 落子中飞行豁免 | ✅ 已通 | 隧道等待期物理盘多一颗人类子，`LedPlanner` 单子豁免（`physical_play.py:162-168`）不点蓝灯 |
| pass | ✅ 无冲突 | engine 局 pass 后端显式拒绝（`gateway.py:112-113`），物理盘本也无法表达 pass |

### 1.2 已核实的缺口（本轨道要修的）

| # | 缺口 | 证据 |
|---|---|---|
| G1 | **星阵 AI 落子不亮灯**：编排器只给 `player_type == "player:ai"` 的颜色点灯，而 engine 局经 `create_multiplayer_session` 双方都是 `"human"` | `physical_play_orchestrator.py:247-259`、`session.py:80-82` |
| G2 | **前端 `humanColor` 推导失效**：取「第一个 human 类型的颜色」→ engine 局双方都 human → 恒为 `'B'`；执白/猜先局的棋盘回合门控、AI 落子坐标横幅全错 | `GamePage.tsx:177-178, 288-290` |
| G3 | **隧道失败 = 无限自动重试**：物理子已在盘上，poller 失败 re-arm 后该子反复被确认 → 反复打星阵 API，无屏幕兜底 | `server.py:1999-2009` |
| G4 | **engine 局悔棋破坏 adapter 状态**：`/api/undo` 只挡 ranked（`server.py:645-651`），engine 局悔棋后 `ctx.moves` 与棋局树脱节；`rebuild_engine_moves`（`adapter.py:935`）**从未被调用** → 下一手 genmove 发错误的 moves 序列 | grep 全仓无调用点 |
| G5 | **星阵支招道具未接白灯**：本地自由对弈支招有完整的白灯闪烁+检测挂起实现（`show_hint`，`physical_play_orchestrator.py:330`），engine 局的支招（golaxy options 隧道）只画屏幕叠加 | `platforms.py:235-260`、`GamePage.tsx:372-408` |

---

## 2. 已拍板决定（2026-07-11 brainstorm，用户确认）

| # | 决定 |
|---|---|
| D1 | **范围只做星阵人机（engine-play）**。OGS/野狐人人对弈的物理化留二期（需远程对局代理设计，见 physical-play PRD §3.5）。 |
| D2 | **隧道失败 = 有限重试 + 屏幕兜底**：自动重试 2-3 次后弹屏幕对话框（手动重试 / 拿回棋子撤销这手 / 认输退出），期间暂停落子检测防止重复打隧道。 |
| D3 | **星阵支招接白灯**：engine 局点「支招」→ 星阵 options 隧道返回候选 → 复用 `show_hint` 白灯闪烁 + 检测挂起，与屏幕叠加同步。 |
| D4 | **rk3562 真机一局为 DoD**：在 rk3562（`ssh rk3562-direct`，网线直连 MacBook）上物理下完一局星阵人机。需确认 SBC 经 Mac 共享上网可达 `api.19x19.com`。 |
| D5 | **engine pending 期间后端禁止 undo/redo**（409），前端按钮同步禁用（codex 评审 B2/Q2 采纳）。 |
| D6 | **genmove 有界自动重试的安全论证**：genmove 隧道无服务端对局状态、无道具计费（7003 仅分析隧道）、未 commit 前无权威 AI 手 ⇒ 重发安全；**分析道具绝不自动重试**（codex B5 部分反驳后的定稿口径）。 |
| D7 | **AI terminal（pass/resign）时先把人类最后一手落进本地树**再终局（修现存记谱缺失，codex Q3）。 |
| D8 | **「拿回棋子」须视觉确认**（目标格空 + 整盘与数字盘一致，连续 N 稳定 tick）后才恢复检测（codex B4）。 |
| D9 | 引擎对手标记走 **web state 新字段 `platform_engine_color`**，不占用 core `player_subtype`（codex M6）。 |

---

## 3. 用户体验流程

### 3.1 主流程（与自由对弈物理版一致，对手换成星阵）

```
kiosk 跨平台对弈 → 星阵已连接 → 人机设置（级别/先手/让子）→ 开局
  ├─ [开局] 空盘检查（残子蓝灯引导拿除）；让子局 LED 逐点红灯引导摆黑子（复用 _setup_cells_from_state）
  │         人执白/猜先得白：星阵 AI 先手已随开局落进数字盘 → LED 点亮该点引导摆黑子
  ├─ [对局循环]
  │    用户回合：物理盘摆子 → 3 帧确认 → poller → gateway engine 分支 → 星阵隧道
  │              → 屏幕「确认中」chip → 隧道返回 → 数字盘按 [human, AI] 顺序落子
  │    AI 回合（隧道返回后）：LED 点亮星阵落子点（AI 执黑→红 / 执白→绿）+ 屏幕坐标横幅
  │              → 用户替 AI 摆子 → 视觉确认 → 灯灭；提子蓝灯同 batch 混色（复用对账循环）
  ├─ [支招道具] 屏幕点「支招」→ 星阵 options 隧道（扣道具次数）→ 白灯闪烁 top-N + 屏幕叠加
  │              → 检测挂起 → 关闭/超时/落子 → 白灯灭、检测恢复；7003 → 充值提示（不点灯）
  ├─ [异常兜底] 隧道失败：自动重试 N 次 → 弹对话框（重试/拿回棋子/认输）；
  │              盘面不一致/遮挡/漂移：复用 physical-play 一期的混合确认 UX（零改动）
  └─ [终局] 认输/数子 → 屏幕结果 → LED 清灯 → 退出 unbind
```

### 3.2 隧道失败兜底（D2 细化）

| 阶段 | 行为 |
|---|---|
| 第 1-2 次失败 | poller 静默自动重试（物理子被再次确认 → 重新提交同一手；安全性论证见 D6）。只有 `engine_error` 类失败计数；pending/终局/非法手各有独立处置（plan Task 7 状态转移表） |
| 达到阈值 | 暂停落子检测（防继续打隧道）→ 广播 `physical_engine_error`（含 recovery token）→ 屏幕对话框 |
| 用户选「重试」 | 后端以 token CAS 消费失败记录后重新提交；成功 → 恢复检测续行；失败 → 对话框留存并显示错误 |
| 用户选「拿回棋子」 | 进入 `awaiting_removal`：检测保持暂停 + 蓝灯/屏幕指引 → **视觉确认目标格已空且整盘与数字盘一致（连续 N 稳定帧）** → resync + 恢复检测（这手从未进数字盘，无需悔棋）。未拿/拿错/拿回又放回均不恢复，超时续引导（D8） |
| 用户选「认输」 | 走既有 resign 链路（`resign_engine_game` → game_ended → 清灯退出） |

### 3.3 悔棋（G4 修复后的语义）

- engine 局允许悔棋（星阵隧道无状态，重建 moves 序列后继续 genmove 是安全的）；**但 pending（genmove 等待）期间后端禁止 undo/redo（D5）**。
- 悔棋 → `game_update` 盘面回退 → 编排器对账自动点灯：多余物理子→蓝灯拿除引导（拿除类以屏幕清单+主通道为准，蓝灯辅助——physical-play R2.3 既有约定）。
- 每次 engine 提交前从棋局树主线重建 `ctx.moves`（G4 修复核心），悔棋/前后导航后状态永不脱节。

---

## 4. 功能需求

### R1 星阵 AI 落子 LED 引导（修 G1）
- R1.1 engine 局开局时在 web state 设 `platform_engine_color`（仿 `game_type` 先例的 interface 字段，经 `get_state()` 单一信源下发，前后端共用；D9）。
- R1.2 `_guided_colors_from_state` 识别该标记，把星阵 AI 的颜色纳入引导色 → AI 落子亮灯（执黑红/执白绿）、提子蓝灯、悔棋恢复灯全部经既有对账循环自动成立。
- R1.3 标记不得复用 `player_type="player:ai"` —— 那会触发前端本地 AI 请求语义（`deriveAiTurnState`/`API.aiMove`）。

### R2 前端回合门控与横幅修复（修 G2）
- R2.1 `humanColor` 推导改为「非平台引擎标记的一方」；执白/猜先局正确。
- R2.2 AI 落子坐标横幅（`GamePage.tsx:170-185`）同一修复；`deriveAiTurnState` 在 engine 局不误判。
- R2.3 隧道等待期的「确认中/思考中」状态显示沿用既有 `platform_move_pending` + vision `move_pending` chip，不新增状态机。

### R3 隧道失败有界重试 + 屏幕兜底（修 G3，D2）
- R3.1 poller 平台分支增加按局失败计数；连续失败 ≤2 次自动重试（复用物理子重确认的天然重试环）。
- R3.2 达阈值：暂停落子检测 + 广播 `physical_engine_error`（含坐标与错误摘要）。
- R3.3 新端点：重试（重新提交记录坐标）与撤回（用户拿除棋子后 resync adopt=digital + 恢复检测）。
- R3.4 前端对话框：重试 / 拿回棋子（附指引）/ 认输；i18n 中文默认。
- R3.5 纯屏幕 engine 局（无 vision）行为不变（现有 engineErrorToast）。

### R4 悔棋安全（修 G4）
- R4.1 每次 `submit_engine_move` 前由 manager/gateway 从 session 棋局树主线重建 `ctx.moves`（调用既有 `rebuild_engine_moves`）。
- R4.2 悔棋后物理盘恢复引导 = 既有对账循环，无新代码；集成测试覆盖「悔 2 手 → 物理恢复 → 续下 → genmove moves 序列正确」。

### R5 星阵支招白灯（修 G5，D3）
- R5.1 engine analysis 端点在 `kind=="options"` 成功且该 session 正被 vision 绑定时，把候选点转 vision 网格坐标调 `orchestrator.show_hint`（白灯闪烁 + 检测挂起 + 超时自灭，全部复用）。
- R5.2 前端叠加关闭/落子失效时调既有 `POST /api/v1/hint/dismiss` 同步灭灯。
- R5.3 领地/变化图不点灯（变化序列上灯无意义且干扰）；`7003` 次数不足不点灯只弹充值提示（既有）。
- R5.4 本地自由对弈 hint 门控（`game_type != "free"` 403）不受影响——engine 局支招走 platforms 端点，不走 `/api/v1/hint`。

### R6 让子/执白开局物理化验证
- R6.1 让子局：星阵塞子（黑星位入 `ctx.moves`）+ 本地 `edit_game handicap` 根节点摆子 → `_setup_cells_from_state` 引导灯；集成测试断言引导单元格正确。
- R6.2 人执白：开局 AI 首手已在数字盘 → bind 后首个 tick 即点灯；测试覆盖。

### R7 rk3562 真机部署与验收（D4）
- R7.1 rk3562 经 Mac 网络共享可达 `api.19x19.com`（前置检查，不通则先解决路由/DNS）。
- R7.2 board 模式全链路：星阵登录（token 已持久化则自动重连）→ 开局 → 物理对弈一局 → 支招白灯 → 认输/数子。

---

## 5. 非目标（本期明确不做）

1. OGS/野狐人人对弈物理化（二期，需远程对局代理设计）。
2. 星阵升降级/联棋/高水平模式（golaxy 轨道本就未做）。
3. 语音提示（对齐 physical-play 一期口径：复用 `sound` 广播，不引入 tsumego 的 `useVoice`）。
4. 领地/变化图道具的 LED 表达（只做支招白灯）。
5. LED 为几何自动闪灯（硬规则，永久非目标）。
6. 9/13 路棋盘、计时对弈、服务重启续局（沿用两条前置轨道的 non-goals）。
7. 视觉/LED/编排器核心算法改动——本轨道只加标记识别与错误兜底钩子，不动对账循环语义。

---

## 6. 验收标准

1. **真机一局（DoD 核心）**：rk3562 board 模式，物理棋盘下完一局星阵人机（≥30 手），星阵每手落子灯、提子蓝灯正确，全程屏幕仅用于确认中状态/支招/认输。
2. **执白与让子**：人执白开局 AI 首手灯正确；让 4 子局 LED 引导摆子后正常续行。
3. **隧道失败兜底**：人为断网制造失败 → 自动重试后弹对话框；三个选项路径均可恢复/退出，且断网期间星阵 API 调用次数有界。
4. **悔棋**：engine 局悔 2 手 → LED 引导物理恢复 → 续下一手，后端日志确认 genmove `moves` 与棋局树一致。
5. **支招白灯**：点支招 → 白灯闪烁 top-N 与屏幕一致 → 显示期间摆子不被误识别 → 关闭恢复；`7003` 不点灯。
6. **回归**：纯屏幕 engine 局（Mac server 模式）行为不变；本地自由对弈物理版不变；摆谱/死活棋不变；`CI=true uv run pytest tests` 相对基线无新增失败；`npm run build` 与 `npm run build:kiosk-2d` 双绿。

---

## 7. 依赖与风险

| 项 | 状态 | 影响 |
|---|---|---|
| rk3562 外网可达性 | **未验证** | R7.1 前置检查；不通则真机验收改在 Mac + 硬件外接（降级路径） |
| 星阵账号 + 道具余额 | 用户持有 | 支招白灯真机验证需道具次数 > 0 |
| genmove 高级别延迟（最长 ~180s） | 已知 | 隧道等待期物理盘多一子靠飞行豁免；用户此期间再摆子会被 pending 拒绝 → 天然排队重试，plan 中有测试覆盖 |
| 提交协议改造面 | codex B1/B2 采纳 | gateway engine 分支需要预校验+锁内原子应用+位置断言；undo/redo 端点加 pending 守卫（plan Task 4） |
| LED UR 象限 v4 硬件 | 沿用现状 | 不阻塞；UI 容忍路径已兜底 |
