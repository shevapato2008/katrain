# Plan：星阵人机对弈接入物理棋盘（kiosk-golaxy-physical-play）

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task（每任务后 spec+质量双评，末尾整支 review）。Steps use checkbox (`- [ ]`) syntax for tracking.
> PRD: [`prd.md`](./prd.md) · 评审: [`review-feedback-codex.md`](./review-feedback-codex.md)
> 状态: **v2（2026-07-11 按 codex 对抗性评审修订）** · 采纳记录见 §评审采纳记录

**Goal:** 用户在物理棋盘上与星阵 AI 对弈：摆子经摄像头识别注入星阵隧道，AI 回招 LED 点亮引导，支招道具白灯闪烁，隧道失败有屏幕兜底。修复 PRD §1.2 的 G1–G5 五个已核实缺口，并按评审补齐提交协议/恢复状态机。

**Architecture（v2）:** 不新建编排器、不动对账循环核心语义。六块设计：

1. **G1/G2 单一信源 = web state 新字段 `platform_engine_color`**（评审 M6：弃用 `player_subtype`，不污染 core Player/SGF）。仿 `game_type` 先例（`interface.py:143,487,501-505`）：`WebInterface` 新属性 + `get_state()` 序列化 + manager 开局时经 `session.katrain(...)` 设置。后端编排器与前端回合门控共读该字段。**绝不用 `player_type="player:ai"`**（触发前端本地 AI 请求语义）。
2. **提交协议（评审 B1/B2）**：engine 落子 = 「提交前本地合法性预校验 → pending 期间后端禁止 undo/redo → 隧道成功后在 `session.lock` 内原子应用 `[human, AI]` 两手 + 提交点位置断言」。位置断言失败（理论不可达，防御）→ 丢弃 AI 手、广播 engine_error、不半提交。
3. **G4 重建 v2（评审 B3）**：重建 `ctx.moves` = 让子前缀（从 engine config 恢复，非主线提取）+ 主线 moves；遇 pass/None coords **响亮失败**（engine 局树中不该有 pass；出现即 engine_error，绝不静默丢弃）。
4. **恢复状态机（评审 B4/B5/M1/M4/M5/m2）**：按 reason 分类的失败 episode（同一 game_id+坐标）；有界自动重试（genmove 无状态且无道具计费，重发安全——见 D6 论证）；达阈值 → `physical_engine_error`（带 recovery token）→ 屏幕对话框；「拿回棋子」进入 `awaiting_removal` 状态，**视觉确认盘面回到数字盘后**才 resync/恢复。
5. **暂停原因集合（评审 M2）**：编排器 `_suspended` 单布尔重构为 reasons 集合（`lag`/`hint`/`engine_error`/`awaiting_removal`），tick 挂起与 worker 检测暂停统一由聚合函数计算。
6. **支招白灯带位置令牌（评审 M7）**：分析请求前记录 position token（node id），返回后核对 session/绑定/token 一致才 `show_hint`，不一致丢弃不点灯。

**Tech Stack:** Python 3.11 / FastAPI / pytest（后端）；React + TS + MUI + Vitest（kiosk 前端）；现有 `PhysicalPlayOrchestrator` / `VisionService` / `LedService` / golaxy adapter 栈。

---

## 已拍板决定（v2 新增，落实评审 Question）

| # | 决定 | 依据 |
|---|---|---|
| D5 | **engine pending 期间后端禁止 undo/redo**（`/api/undo`、`/api/redo` 对 `ctx.is_pending` 的 engine 局返回 409）。前端按钮同步禁用，但后端约束是权威。 | 评审 B2/Q2；genmove 最长 ~180s 窗口内树变更会让旧响应落错节点 |
| D6 | **genmove 有界自动重试合法**：genmove 隧道无服务端对局状态、无道具计费（7003/`QuotaExhausted` 只存在于分析隧道，`engine_client.py:193-198` 已核）、我方未 commit 前不存在权威 AI 手——「响应丢失但服务端已处理」不留下任何可污染状态，重试得到不同 AI 手也无正确性问题。**分析道具（支招等）绝不自动重试**（用户手动触发，本就如此）。总 HTTP 次数上界 = poller 尝试数 × adapter 内部重试(≤2)，文档化。 | 评审 B5/Q1 的部分反驳，已核代码 |
| D7 | **AI terminal（pass/resign 特殊 coord）时仍先把人类这手落进本地树**再走终局链路——否则本地棋谱缺实际最后一手（现存缺陷，物理化会放大）。 | 评审 Q3；`adapter.py:788-792` 现状不提交 |
| D8 | 「拿回棋子」必须**视觉确认**目标格已空且整盘与数字盘一致（连续 N 稳定 tick）后才恢复检测；确认前保持暂停并持续引导。 | 评审 B4；`resync()` 的 union 基线会把未拿的子静默吞掉 |
| D9 | 让子局语义澄清：`handicap≥2` 后轮白。人执黑让子 → AI(W) 先手；**人执白+让子 = 黑方让子属 AI、人类(白)先手，无 AI opening**——UI 不禁止但测试矩阵按此语义写。 | 评审 Q4 |

## Global Constraints（每个任务隐含遵守）

- **LED 硬规则（永久）**：LED 绝不为几何自动闪灯；本轨道不触碰几何/重标定路径。
- **构建边界（根 CLAUDE.md SBC 契约）**：新前端文件只放 `src/kiosk/**`；改共享文件（`src/api.ts`、`src/hooks/useGameSession.ts` 等）后双构建必须绿：`npm run build` **和** `npm run build:kiosk-2d`。禁 three/galaxy/Board3D。
- **回归基线**：Task 0 实测记录 pytest 基线失败集；后续任务相对基线无新增失败。摆谱/死活棋/本地自由对弈物理版/纯屏幕 engine 局行为不变。
- **勿回归 golaxy 轨道既有修复**（`kiosk-play-golaxy/plan.md` §11）：genmove 鉴权 header、`6003→AuthExpired`、FK 守卫、token 持久化。
- **提交纪律不破**：adapter 的不可变 proposed_moves + 单一 commit 点语义不动；本计划的重建/校验都发生在 adapter 提交语义**之外**（manager/gateway 层）。
- **vision pause 所有权**：engine 恢复路径只用编排器own 的 `pause_detection/resume_detection` 家族，**禁止**碰 tsumego 的 `/vision/pause` 聚合布尔（single-owner，`service.py:144` 注释）。
- 引用代码用**符号名**为主、行号为辅（行号会漂移，实施时以符号定位）。
- Python 格式 `uv run black -l 120 katrain tests`；conventional commits（`feat(physical-golaxy): …`）。
- 前端新文案 `t('English key', '中文')`，默认中文，禁日文；静态串收尾统一走 `katrain-i18n-expert`（Task 13）。
- 坐标约定：vision 网格 row 0 = 顶；KaTrain GTP coords y 自底向上；`vision_rc = (board_size - 1 - y, x)`。**金标准（评审 M8 已纠正）**：KaTrain `(col=3, row=15)` = D16 → vision `(3, 3)`；KaTrain `(3, 3)` = D4 → vision `(15, 3)`。棋盘固定 19 路。
- 新增可调参数挂配置并有默认值；重试/恢复策略参数放独立的 recovery 配置段（不与 LED planner 参数混居，评审 m1）。

## 关键事实（写代码前必读，2026-07-11 已逐一核实）

1. `create_multiplayer_session` 双方 `player_type="human"`（`session.py:80-82`）。序列化字面值有 `"player:human"`/`"human"` 两种历史形态（`GamePage.tsx:35-43` 注释）——**前端测试 fixture 必须从后端契约测试导出的真实 get_state JSON 生成**（评审 m1：TS 单测调不了 Python，用 contract fixture 文件）。
2. poller 平台分支（`_vision_move_poller`，`server.py` 符号）：gateway 异常 → log + re-arm + continue。物理子仍在盘上 → 再次 ConfirmedMove → 天然重试环。G3 只需**计数、分类与截断**。
3. gateway `_play_engine_move` 三类异常：`GolaxyEngineTerminal`（终局，不可重试）；其它 → `"engine_error"`；`is_pending` → `"Previous move still pending"`（排队非失败）。恢复状态机需要 `PlatformMoveRejectedError.reason` 属性区分。
4. `rebuild_engine_moves`（`golaxy/adapter.py` 符号）现为全量覆盖 `ctx.moves`，**不含让子前缀恢复**；主线提取会丢根节点 AB setup 子（`edit_game` → `place_handicap_stones` 是 setup 不是 move node）。Task 5 重写接口。
5. `show_hint(points)`：入参 vision `(row,col)` tuple list；自带 dismiss-first、`_suspended` 挂起、白灯闪烁、超时自灭。`POST /api/v1/hint/dismiss` 无门控可复用。⚠️ `_end_hint()` 无条件 `_suspended=False` —— Task 6 重构掉这个共享布尔（评审 M2）。
6. `resync()` 的 detector 基线 = digital∪physical union，**遗留物理子不会重新注入也不会报警**——这正是「拿回棋子」不能直接 resync 的原因（评审 B4）。
7. engine analysis options 结果已解码为 KaTrain `(col,row)`；前端已有按 `current_node_id` 的 stale 叠加丢弃（`GamePage.tsx` 注释），后端 show_hint 需要对称的 token 守卫（评审 M7）。
8. `physical_reminder` 广播模式（orchestrator → `broadcast_to_session` → `useGameSession` → GamePage 对话框）是 `physical_engine_error` 的现成样板。
9. 导航入口盘点：REST 只有 `/api/undo`、`/api/redo`（`server.py:645,656`）；前端 `back-10`/`start` 动作最终也走这两个端点（Task 4 实施时以 grep 复核为准）。
10. poller 调 gateway 传 `user_id=0`；engine 分支不校验 user_id。恢复端点的 ownership 校验（评审 M5）以「vision 当前绑定 == session_id + recovery token CAS」为主，与既有 vision 端点鉴权口径一致（实施时核对 `endpoints/vision.py` 现状取齐）。
11. 隧道等待期物理盘多一子 → `LedPlanner` 单子飞行豁免已覆盖。等待期第二颗物理子的真实时序：poller 阻塞在 `await gateway.play_move`，第二个 ConfirmedMove 在队列排队，第一手返回后才被消费——此时多按「out-of-turn 忽略 + re-arm」或「恰为合法下一手注入」处理，**不是** gateway pending 拒绝（评审 M3）。Task 12 用真实 poller+可控 future 固化，不用 mock 直抛 pending。
12. `vision_pump.route_vision_event` 在未绑定时丢弃 ConfirmedMove，但 bind→unbind→rebind 之间队列残留可跨局注入（评审 M1）——bind/unbind 时清空 move 队列。
13. genmove 无道具计费；7003/`QuotaExhausted` 只在分析隧道（`engine_client.py:193-198,341-343`）。

---

## Task 0 — 基线确认

- [ ] `uv sync`；`CI=true uv run pytest tests -q` 记录基线失败集（写进本文件底部「基线记录」）。
- [ ] `cd katrain/web/ui && npm install && npm run build && npm run build:kiosk-2d` 双绿。
- [ ] 通读：`physical_play_orchestrator.py` 全文、`physical_play.py`（LedPlanner）、`gateway.py:41-115`、`golaxy/adapter.py:704-945`、`server.py` 的 `_vision_move_poller`、`GamePage.tsx:35-60,138-200,280-340`、`endpoints/vision.py`。
- [ ] grep 复核关键事实 #9（undo/redo 之外是否还有树变更入口：`navigate`/`goto`/`load_sgf` 等对活跃 engine 局的可达性），结论记录在下方基线记录。
- **Verification**: 基线记录已填；能复述全链路与六块设计。

## Task 1 — 后端：`platform_engine_color` 状态字段（G1/G2 信源，TDD）

- Files: Modify `katrain/web/interface.py`（属性 + `get_state()` 序列化 + 设置动作，仿 `game_type` 先例）、`katrain/web/platforms/manager.py`（`start_engine_game` 设置）；Test `tests/platforms/test_engine_manager.py` 追加。
- [ ] **写失败测试**：`start_engine_game`（mock adapter）后 `session.katrain.get_state()["platform_engine_color"] == ai_color`（执黑/执白两用例）；非 engine 局该字段为 `None`；**`edit_game` 后字段仍在**（评审 M6 持久性要求——字段挂 interface 不挂 Player，天然免疫，但测试固化）；resign/终局后不残留到新局。
- [ ] 实现：interface 属性默认 `None`；manager 在 `edit_game` 之后设置。导出契约 fixture：新增小工具测试把 engine 局 `get_state()` JSON dump 到 `katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json`（前端 Task 3 消费；评审 m1 的 contract fixture 方案）。
- [ ] 跑测试通过；commit。

## Task 2 — 后端：编排器识别引导色（TDD）

- Files: Modify `katrain/web/core/physical_play_orchestrator.py`（`_guided_colors_from_state`）；Test `tests/test_physical_play_orchestrator.py` 追加。
- [ ] **写失败测试**：state 含 `platform_engine_color:"W"` → 引导色 `{WHITE}`；`"B"` → `{BLACK}`；字段缺失/None → 现行为不变（`player:ai` 分支与双 human 空集均不回归）。用 Task 1 契约 fixture 构造。
- [ ] 实现：guided 条件扩为 `player_type == "player:ai"` **or** `bw == state.get("platform_engine_color")`。core 不 import platforms（读的是 state dict 字段，无依赖问题）。
- [ ] 集成冒烟：engine 局 state（AI=W 刚落一子、物理盘缺该子）→ tick 后 led 收到绿灯点。
- [ ] 跑测试通过；commit。

## Task 3 — 前端：humanColor/横幅修复（TDD）

- Files: Modify `GamePage.tsx`（helpers :35-52、横幅 :170-185、humanColor :288-291）、`GameState` 类型（加可选 `platform_engine_color`；**共享区，双构建**）；Test `GamePageEngine.test.tsx` 追加（用 Task 1 契约 fixture）。
- [ ] **写失败测试**：engine 局人执白（fixture `platform_engine_color:"B"`）→ humanColor `'W'`；AI(B) 落子后横幅显示 AI 坐标；人执黑不回归；本地 HvAI（player:ai）不回归；隧道等待期 `player_to_move` 仍是人类 → `aiThinking` 不误亮（断言）。
- [ ] 实现：`humanColor` = `platform_engine_color` 存在时取其对色；否则沿用现推导。`deriveAiTurnState.isAI` 增加 `platform_engine_color` 分支。
- [ ] 双构建绿；`npm test -- GamePageEngine` 绿；commit。
- **Review checkpoint（人工）**: Mac dev 模式开 engine 局，确认 AI 落子亮灯、执白局回合门控正确。

## Task 4 — 后端：提交协议硬化（B1/B2/D5/D7，TDD）

- Files: Modify `katrain/web/platforms/gateway.py`（`_play_engine_move`）、`katrain/web/server.py`（undo/redo 端点守卫）；Test `tests/platforms/test_engine_gateway.py` 追加。
- [ ] **写失败测试（四类 interleaving，评审 B1/B2 点名）**：
  1. **本地预校验**：物理/屏幕手在本地非法（ko/自杀/占位）→ 不打隧道、rejected `"illegal_move"`、`ctx.moves` 不变；
  2. **pending 期间 undo**：engine 局 pending 时 `POST /api/undo` → 409；pending 清除后可 undo；非 engine 局不受影响；
  3. **原子应用 + 位置断言**：genmove 等待期用可控 future 强改当前节点（模拟绕过守卫的树变更）→ 响应返回后位置断言失败 → 两手都不落、广播 engine_error、下次提交经 Task 5 重建自愈；
  4. **AI terminal 提交人类手（D7）**：mock 隧道返回特殊 coord → 人类这手先落进本地树 → 再广播 game_ended 终局。
- [ ] 实现：
  - `_play_engine_move` 开头：`session.lock` 内校验落点合法（复用 KaTrain game 合法性判断）+ 记录 `position_token = current_node_id`；
  - 成功分支：`session.lock` 内断言 `current_node_id == position_token` → 依序 `_local_play(human)`、`_local_play(ai)`（同锁内）→ 广播两个 confirmed；断言失败 → 丢弃 AI 手 + rejected `"position_changed"`（reason 属性见 Task 7）；
  - `GolaxyEngineTerminal` 分支：先 `_local_play(human)`（同样断言位置）再走既有终局广播；
  - `/api/undo`、`/api/redo`：`gateway.is_platform_game && ctx.is_engine && ctx.is_pending` → HTTP 409 `{"detail":"engine move pending"}`（守卫放 server 端点层，gateway 提供查询）。前端 undo 按钮在 pending 时禁用（`usePlatformEvents.pendingMove` 已有信号，小改随本 task）。
- [ ] 跑测试通过；`CI=true uv run pytest tests/platforms -q` 无新增失败；commit。

## Task 5 — 后端：重建 v2 = 让子前缀 + pass 响亮失败（B3，TDD）

- Files: Modify `katrain/web/platforms/manager.py`（`rebuild_engine_context` helper）、`katrain/web/platforms/golaxy/adapter.py`（`rebuild_engine_moves` 接口调整或新 helper）；Test `tests/platforms/test_engine_gateway.py` / 新 `test_engine_rebuild.py`。
- [ ] **先读** `_handicap_stones` 与 `EngineGameConfig.handicap`，确认前缀 = `_handicap_stones(config.handicap)`。
- [ ] **写失败测试（断言完整整数序列，评审 B3 点名）**：
  1. 分先局下 3 手悔 2 手再落 → 下次 genmove 收到的 moves CSV == 悔后主线编码（当前必挂红测）；
  2. 让 2/4/9 子局悔 1 手再落 → moves == 星位前缀 + 悔后主线；
  3. 当前节点在分支上（undo 后另下一手）→ moves 按当前路径重建；
  4. 主线含 pass 节点（手工构树）→ 重建抛错 → gateway 转 rejected `"engine_error"`，绝不静默丢 pass；
  5. 无悔棋连下 → 重建幂等，与现状完全一致。
- [ ] 实现：manager `rebuild_engine_context(session_id)`：从**当前节点回溯到根的路径**（不是 root 主线——支持分支导航）提取 move coords，None coords → raise；adapter 侧重建 = `_handicap_stones(config.handicap) + encode(path_moves)`。gateway `_play_engine_move` 在预校验后、`set_pending` 前调用；失败 → rejected 不半提交。
- [ ] 跑测试通过；commit。

## Task 6 — 后端：编排器暂停原因集合重构（M2，TDD）

- Files: Modify `katrain/web/core/physical_play_orchestrator.py`（`_suspended`/`_hint_active` → `self._pause_reasons: set[str]`）；Test `tests/test_physical_play_orchestrator.py` 追加。
- [ ] **写失败测试**：reasons 组合矩阵——hint 中 enter engine_error → dismiss hint 后**仍暂停**（error 未清）；error 中 show/dismiss hint → error 保持；lag（`not caught_up`）与两者叠加；`on_unbind` 清空全部 reasons 并恢复 worker；每种进入/退出顺序断言 `pause_detection/resume_detection` 调用序列正确（幂等，不重复调用）。
- [ ] 实现：`_pause_reasons` 集合 + 单一聚合函数 `_sync_pause_state()`（tick 挂起与 worker 检测暂停都由它算）；`show_hint/_end_hint/enter_engine_error/clear_engine_error/on_unbind` 只增删 reason。现有 hint 行为语义不变（外部测试不回归）。
- [ ] 跑测试通过；commit。

## Task 7 — 后端：恢复状态机（B5/M1/M4/m2，TDD）

- Files: Modify `katrain/web/server.py`（poller 平台分支）、`gateway.py`（`PlatformMoveRejectedError.reason`）、`physical_play_orchestrator.py`（`enter_engine_error/clear_engine_error`）、新 `katrain/web/core/engine_recovery.py`（episode 数据类 + reason 状态转移，纯逻辑可测）+ 配置段（`engine_move_max_attempts: int = 3` 等，独立 recovery 配置，评审 m1）；Test 新 `tests/test_engine_recovery.py`。
- [ ] `PlatformMoveRejectedError` 加 `reason` 属性；gateway 各 raise 点设置：`"illegal_move" | "position_changed" | "engine_error" | "game_ended" | "pending" | "move_rejected"`。
- [ ] **写失败测试（reason 状态转移表，评审 M4 点名）**：
  | reason | 计数 | 行为 |
  |---|---|---|
  | `engine_error` / `position_changed` | 同 episode（同 game_id+coords）+1 | 未达阈值 re-arm；达阈值 → `enter_engine_error` + 广播（带 token）+ **不再 re-arm** |
  | `pending` | 不计数、不清零 | 现行为（continue） |
  | `illegal_move` | 不计数 | re-arm（物理子非法：走既有 mismatch 兜底，不打隧道） |
  | `game_ended` | 清 episode | **不 re-arm**；灯态由终局 game_update 自然清理；episode/绑定清理断言 |
  | session missing | 清 episode | continue |
  - episode 语义（评审 m2）：坐标变化 → 新 episode；成功/cancel/unbind/game end/换 game_id → 清零；
  - **queue 卫生（评审 M1）**：`vision.bind_session`/`unbind` 时清空 `vision_move_queue` 与 pending ConfirmedMove（跨局注入测试：旧局 move 残留 → rebind 后不注入新局）。
- [ ] **写失败测试（orchestrator）**：`enter_engine_error(coords, token)` → `_pause_reasons` 加 `engine_error`；`clear_engine_error()` → 移除。
- [ ] 实现：失败记录 `{episode_key, count, coords, detail, recovery_token(uuid), game_id}` 存 `app.state.engine_recovery`（每 session 至多一条活动记录）；广播 `{"type":"physical_engine_error", col,row,attempts,detail,recovery_token}`。
- [ ] 跑测试通过；commit。

## Task 8 — 后端：恢复端点 retry/cancel + awaiting_removal（B4/M5/D8，TDD）

- Files: Modify `katrain/web/api/v1/endpoints/vision.py`（两个端点）、`physical_play_orchestrator.py`（`awaiting_removal` 逻辑挂 tick）；Test `tests/test_engine_recovery.py` 追加 + 端点 TestClient 测试。
- [ ] **写失败测试（retry）**：`POST /api/v1/vision/engine-move/retry {session_id, recovery_token}` →
  - token 匹配活动记录 + vision 当前绑定 == session_id → 重新 `gateway.play_move`；成功 → 清记录/reason、返回 ok；再失败 → 记录保持、返回 `{"ok":false,"detail"}`（HTTP 200）；
  - 旧 token / 无活动记录 / 绑定不符 → 409；**双击并发 retry → 恰一次提交**（token CAS：先原子摘取记录再提交）。
- [ ] **写失败测试（cancel → awaiting_removal，评审 B4 全场景）**：
  - cancel 后检测保持暂停，进入 `awaiting_removal`（reason 集合）；
  - 模拟观测盘：目标格仍有子 → 不恢复、持续引导（蓝灯该点 + 屏幕提示）；
  - 拿错子（别处少了）→ 不恢复；
  - 拿回又放回 → 不恢复；
  - 目标格空且整盘 == 数字盘、连续 N 稳定 tick → `resync()` + 清 reason/记录 + 恢复检测；
  - 超时（可配）→ 保持引导并再次广播提醒；unbind → 清理。
- [ ] 实现：`awaiting_removal` 复用 tick 循环的 observed board 对账（新增一个目标条件检查，不新开循环）；蓝灯引导复用 `_apply_points`。
- [ ] 跑测试通过；commit。

## Task 9 — 前端：隧道失败对话框（TDD）

- Files: Modify `src/hooks/useGameSession.ts`（`physical_engine_error` → state；共享区）、`src/api.ts`（`visionEngineMoveRetry/Cancel`，带 recovery_token；共享区）、`GamePage.tsx`；New `src/kiosk/components/physical/EngineMoveErrorDialog.tsx`；Test `EngineMoveErrorDialog.test.tsx` + `GamePageEngine.test.tsx` 追加。
- [ ] **写失败测试**：收到 `physical_engine_error` → 对话框（坐标 + 「星阵连接出错」+ attempts）；
  - 「重试」→ retry API（带 token）；`ok:false` → 留存显示错误；`ok:true` → 关闭；409（旧 token）→ 关闭并提示已过期；
  - 「拿回棋子」→ cancel API → 切换为「请拿回 X 处棋子」等待态（监听后续 `physical_reminder`/恢复广播关闭）；
  - 「认输」→ 复用现有 resign 确认流；
  - 纯屏幕局（`!isVisionEnabled`）不弹（engineErrorToast 不回归）。
- [ ] 实现；文案 `t()` 中文默认。
- [ ] `npm test` 绿；双构建绿；commit。
- **Review checkpoint（人工）**: Mac mock 断网走三按钮路径 + 拿回棋子等待态。

## Task 10 — 后端：支招白灯带位置令牌（G5/M7/M8，TDD）

- Files: Modify `katrain/web/api/v1/endpoints/platforms.py`（engine/analysis）；Test `tests/platforms/test_engine_analysis_endpoint.py` 追加。
- [ ] **写失败测试**：
  - `kind=="options"` 成功 + orchestrator 存在 + `vision.bound_session_id == session_id` + **请求前后 `current_node_id` 未变** → `show_hint` 收到 vision_rc list（金标准：KaTrain `(3,15)`=D16 → `(3,3)`；`(3,3)`=D4 → `(15,3)`，评审 M8 已纠正）；
  - 请求期间落子/undo（node id 变）→ 不点灯；unbind/换绑 → 不点灯；
  - `kind!="options"`、7003、orchestrator 缺席 → 不调不炸；show_hint 抛错不影响分析结果返回。
- [ ] 实现：请求前取 token，await 分析，返回后同校验再 `show_hint`（try/except 包裹）。
- [ ] 跑测试通过；commit。

## Task 11 — 前端：支招灯同步灭（TDD）

- Files: Modify `GamePage.tsx`（叠加清空路径调 dismiss）、`src/api.ts` 补 `hintDismiss`（若缺；共享区）；Test `GamePageEngine.test.tsx` 追加。
- [ ] **写失败测试**：engine 局 vision 开启，options 叠加因落子失效/用户关闭/离开页面 → `hintDismiss` 被调（**断言最终状态而非恰好一次**——端点幂等，StrictMode 重复无害，评审 m3）；非 options 叠加与纯屏幕局不调。
- [ ] 实现；双构建绿；commit。

## Task 12 — 集成测试收口（M3/M9/m4/D9）

- Files: New `tests/test_engine_physical_integration.py`（真实 poller + queue + 可控 future + 真 VisionService command 序列，参照 `tests/test_vision/test_sync_regressions.py` 的组装深度）。
- [ ] 用例 1（执白分先）：AI(B) 首手随 start 落进数字盘 → bind + tick → 该点红灯。
- [ ] 用例 2（人执黑让 4 子）：`_setup_cells_from_state` 引导 4 星位 → 视觉逐子到位 → AI(W) 首手灯亮。人执白+让子：无 AI opening、人类先手（D9 语义固化）。
- [ ] 用例 3（全链路一手）：真实 poller 消费 ConfirmedMove → gateway（mock 隧道可控 future）→ `[human, AI]` 顺序落子 → tick 后 AI 点亮。
- [ ] 用例 4（等待期第二颗子，评审 M3 口径）：genmove future 挂起时投第二个 ConfirmedMove → 第一手返回后才被消费 → 按真实时序断言其归宿（out-of-turn 忽略或成为合法下一手）+ detector 基线最终一致 + **不触发失败对话框**。
- [ ] 用例 5（模式切换，评审 M9）：tsumego 页残留 monitor/setup/paused 状态 → 进入 engine 局 bind → 断言 worker 收到的命令序列使检测处于正确态；engine error/hint 挂起中 unbind → 进 tsumego → 不残留暂停。
- [ ] 用例 6（边界抽样，评审 m4）：角点 (0,0)/(18,18) 编解码贯通；提子后 AI 落回原格（等待期豁免不误蓝灯）；AI 返回已占点 → position 断言/合法性防线拒绝且广播 engine_error；LED/vision 方法抛错不阻塞对局。
- [ ] 全绿后：`CI=true uv run pytest tests -q` 相对基线无新增失败；`uv run black -l 120 katrain tests`；commit。

## Task 13 — i18n + 收尾

- [ ] 新增静态文案走 `katrain-i18n-expert` skill 补全 11 语言（cn≠zh、jp≠ja；默认中文）；`uv run python i18n.py` 重生成 .mo。
- [ ] 双构建绿 + 全量 pytest 相对基线无新增失败；commit + push `feature/kiosk-play-golaxy`（用户既定：直接推送不开 PR）。
- **Review checkpoint（人工）**: 走查全部新 UI 文案。

## Task 14 — 真机部署与验收（用户参与，一次性）

- [ ] **前置**：`ssh rk3562-direct 'curl -sS -m 10 https://api.19x19.com/ -o /dev/null -w "%{http_code}"'` 确认外网。不通 → 先配 Mac 网络共享/路由/DNS（就地回报）。
- [ ] 部署本分支到 rk3562（沿用既有 board 模式部署方式）启动。
- [ ] 验收单（对照 PRD §6）：登录 → 物理 ≥30 手（AI 灯/提子蓝灯）→ 执白局与让子局开局引导 → 断网重试对话框三路径（含拿回棋子视觉确认）→ pending 期间悔棋被 409/按钮禁用 → 悔 2 手恢复续下（日志核 moves）→ 支招白灯 + 7003 → 摆谱/死活棋回归抽查。
- **Review checkpoint（人工）**: 验收单全过 → 合并策略（`superpowers:finishing-a-development-branch`）。

---

## Testing strategy 汇总

- 纯逻辑（recovery 状态机、重建序列、暂停 reasons）优先 TDD；隧道一律 mock，CI 不打真星阵。
- 集成层拒绝浅 mock：poller/queue/future 用真件（评审 M3）；VisionService 命令序列用真件（评审 M9）。
- 前端 fixture 从后端契约测试导出 JSON（评审 m1）。
- 关键回归三防线：① 无 `platform_engine_color` 的会话引导行为不变；② `player:ai`（本地自由对弈物理版）不回归；③ 纯屏幕 engine 局所有新钩子静默跳过。
- 真机验证只在 Task 14 做一次。

## 评审采纳记录（2026-07-11，codex）

| # | 反馈 | 处置 |
|---|---|---|
| B1 | 两手本地落子非事务、半提交 | **采纳**：提交协议（预校验 + 锁内原子应用 + 位置断言），Task 4；四类 interleaving 测试 |
| B2 | pending 窗口 undo/redo 竞争 | **采纳**：D5 后端 409 禁止 + 位置断言双保险，Task 4 |
| B3 | 重建丢让子前缀/pass | **采纳**：重建 v2 = config 前缀 + 路径回溯 + pass 响亮失败，Task 5；断言完整整数序列 |
| B4 | cancel 直接 resync 吞子 | **采纳**：D8 `awaiting_removal` 视觉确认后才恢复，Task 8；未拿/拿错/放回/超时全覆盖 |
| B5 | 重发不幂等、可能重复计费 | **部分采纳**：「响应丢失≠未处理」的分类要求采纳（reason 状态表，Task 7）；「重复计费」**反驳**——genmove 隧道无道具计费（`engine_client.py:193-198` 已核，7003 仅分析隧道），且无状态+未 commit 无权威结果 ⇒ 有界重试安全（D6 论证入档）；分析道具本就不自动重试 |
| M1 | 视觉事件跨局注入 | **采纳**：bind/unbind 清空 move 队列 + 跨 bind 测试，Task 7 |
| M2 | `_suspended` 共享布尔互解 | **采纳**：reasons 集合重构，Task 6（独立成任务、先于恢复状态机） |
| M3 | pending 测试模型失真 | **采纳**：Task 12 用例 4 真实时序（poller 阻塞 → 队列排队 → out-of-turn/合法下一手，非 gateway pending） |
| M4 | terminal 路径无收尾 | **采纳**：reason 状态转移表含 game_ended 清理，Task 7 |
| M5 | retry/cancel 无 ownership/token | **采纳**：recovery_token CAS + 绑定校验 + 并发双击测试，Task 8 |
| M6 | player_subtype 污染 core | **采纳**：改走 web state 新字段 `platform_engine_color`（D8→D1 设计），Task 1；含 edit_game 持久性测试 |
| M7 | 支招慢响应点旧灯 | **采纳**：position token 守卫，Task 10 |
| M8 | 金标准坐标写错（D16/D4 混淆） | **采纳**：已在 Global Constraints 与 Task 10 纠正 |
| M9 | tsumego↔engine 模式切换盲区 | **采纳**：Task 12 用例 5 真 VisionService 命令序列；Global Constraints 明确 pause 所有权 |
| m1 | 路径/行号/config 职责/TS fixture | **采纳**：符号引用为主；recovery 独立配置段；契约 fixture 方案 |
| m2 | 计数清零条件不清 | **采纳**：episode 语义定义入 Task 7 状态表 |
| m3 | 「恰好一次」脆弱断言 | **采纳**：改断言最终状态，端点幂等，Task 11 |
| m4 | 坐标/规则边界缺失 | **采纳**：Task 12 用例 6 抽样覆盖（角点/提子回填/占点/异常注入） |
| Q1 | genmove 幂等/计费语义 | **已答**：无计费、无状态（D6，代码证据）；PRD 措辞已改「论证安全」而非「天然安全」 |
| Q2 | pending 时悔棋是否允许 | **已答**：禁止（D5） |
| Q3 | AI terminal 丢最后人类手 | **已答**：D7 终局前先落人类手，Task 4 用例 4 |
| Q4 | 人执白+让子语义 | **已答**：D9 澄清并入测试矩阵，Task 12 用例 2 |
| Q5 | 未知结果是否需「弃局重开」 | **已答**：genmove 无需（D6）；错误对话框已含认输退出兜底 |

## 基线记录（Task 0 填写）

- pytest 基线失败集：*待填*
- 双构建基线：*待填*
- 树变更入口盘点结论：*待填*
