# Plan：星阵人机对弈接入物理棋盘（kiosk-golaxy-physical-play）

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task（每任务后 spec+质量双评，末尾整支 review）。Steps use checkbox (`- [ ]`) syntax for tracking.
> PRD: [`prd.md`](./prd.md)（同目录，先读）· 状态: 草案（待 codex 对抗性评审）· Written 2026-07-11

**Goal:** 用户在物理棋盘上与星阵 AI 对弈：摆子经摄像头识别注入星阵隧道，AI 回招 LED 点亮引导，支招道具白灯闪烁，隧道失败有屏幕兜底。修复 PRD §1.2 的 G1–G5 五个已核实缺口。

**Architecture:** 不新建编排器、不动对账循环语义。五个缺口各自最小改动：
1. **G1/G2 单一信源**：engine 局开局时给虚拟对手在 `players_info` 打 `player_subtype` 标记 → 后端编排器与前端回合门控共用同一信号（经既有 `game_update` state dict 下发，刷新/重连天然恢复）。**绝不用 `player_type="player:ai"`**（会触发前端本地 AI 请求语义）。
2. **G3 有界重试**：poller 平台分支加按局连续失败计数（只数 `engine_error` 类失败）；达阈值 → 编排器挂起检测 + 广播 `physical_engine_error` → 前端对话框 → 重试/撤回两个新 vision 端点收尾。
3. **G4 提交前重建**：gateway engine 分支每次提交前从 session 棋局树主线重建 `ctx.moves`（调用既有但从未接线的 `rebuild_engine_moves`），悔棋/导航永不脱节。
4. **G5 复用 show_hint**：platforms engine/analysis 端点在 `kind=="options"` 成功且 session 被 vision 绑定时调 `orchestrator.show_hint`（白灯闪烁/检测挂起/超时自灭全复用）；前端叠加关闭时调既有 `/api/v1/hint/dismiss`。

**Tech Stack:** Python 3.11 / FastAPI / pytest（后端）；React + TS + MUI + Vitest（kiosk 前端）；现有 `PhysicalPlayOrchestrator` / `VisionService` / `LedService` / golaxy adapter 栈。

---

## Global Constraints（每个任务隐含遵守）

- **LED 硬规则（永久）**：LED 绝不为几何自动闪灯；本轨道不触碰几何/重标定路径。
- **构建边界（根 CLAUDE.md SBC 契约）**：新前端文件只放 `src/kiosk/**`；改共享文件（`src/api.ts`、`src/hooks/useGameSession.ts`、`src/components/Board.tsx` 等）后必须双构建绿：`npm run build` **和** `npm run build:kiosk-2d`（含 `verify:kiosk-2d`）。禁 three/galaxy/Board3D。
- **回归基线**：Task 0 实测并记录 `CI=true uv run pytest tests` 基线失败集；后续任务相对基线**无新增失败**。摆谱/死活棋/本地自由对弈物理版/纯屏幕 engine 局行为不变。
- **勿回归 golaxy 轨道既有修复**（`kiosk-play-golaxy/plan.md` §11）：genmove 鉴权 header、`6003→AuthExpired`、FK 守卫、token 持久化。
- **提交纪律不破**：`submit_engine_move` 的不可变 proposed_moves + 单一 commit 点语义不动（G4 重建发生在提交**之前**，不在重试路径中间）。
- Python 格式 `uv run black -l 120 katrain tests`；提交信息 conventional 风格（`feat(physical-golaxy): …` / `fix(kiosk): …`）。
- 前端新文案 `t('English key', '中文')`（`useTranslation`），默认中文，禁日文；静态串收尾统一走 `katrain-i18n-expert`（Task 10）。
- 坐标约定：vision 网格 row 0 = 顶、col 0 = 左；KaTrain GTP coords y 自底向上；换算 `vision_rc = (board_size - 1 - y, x)`（与 `hint.py:100` 一致）。棋盘固定 19 路。
- 新增可调参数（重试阈值等）挂 `PhysicalPlayConfig`，有默认值。

## 关键事实（写代码前必读，2026-07-11 已逐一核实）

1. `create_multiplayer_session` 双方 `player_type="human"`（`session.py:80-82`）；`update_player` 支持 `player_subtype`（`interface.py:874`），且 `players_info` 序列化已含 `player_subtype` 字段（`interface.py:446-451`）——标记通道现成。
   ⚠️ 序列化后的 `player_type` 字面值有 `"player:human"`/`"human"` 两种历史形态（`GamePage.tsx:35-43` 注释），**测试必须走真实 `create_multiplayer_session` 路径取实际值，禁止手写字符串 mock**。
2. poller 平台分支在 `server.py:1999-2009`：gateway 异常 → log + re-arm expected board + continue。物理子仍在盘上 → 几秒后再次 ConfirmedMove → 天然重试环（G3 的「自动重试」不需要新循环，只需要**计数与截断**）。
3. gateway 引擎分支 `_play_engine_move`（`gateway.py:76-105`）三类异常：`GolaxyEngineTerminal`（对局结束，**不可重试**）→ rejected `"game_ended"`；其它异常 → rejected `"engine_error"`；`is_pending` 时抛 `"Previous move still pending"`（**不是失败**，是排队）。G3 计数必须只数 engine_error 类——需要给 `PlatformMoveRejectedError` 加 `reason` 属性（见 Task 5）。
4. `rebuild_engine_moves(game_id, moves_coords)`（`adapter.py:935-945`）已存在但全仓**零调用点**。让子局 `ctx.moves` 开头是塞入的星位黑子（`adapter.py` `_handicap_stones`）——重建时必须保留该前缀语义（Task 4 先读实现再接线，让子局回归测试必备）。
5. `show_hint(points)`（`physical_play_orchestrator.py:330-340`）：入参 vision `(row,col)` tuple list；自带 dismiss-first、检测挂起（`_suspended` + `_sync_pause_state`）、白灯闪烁任务、超时自灭；`POST /api/v1/hint/dismiss`（`hint.py:135-140`）无门控可直接复用。
6. `orchestrator.resync()`（`physical_play_orchestrator.py:135-179`）= 「以数字盘为准重建视觉基线并恢复」——G3「拿回棋子」路径的现成收尾。
7. engine analysis 的 options 结果已解码为 KaTrain `(col,row)` 列表（`adapter.py:_decode_options`，`platforms.py:235-260` 返回）；白灯需转 vision_rc。
8. `physical_reminder` 的广播模式（`physical_play_orchestrator.py:294-326` → `session_manager.broadcast_to_session` → `useGameSession.ts:99-100` → GamePage 对话框）是 `physical_engine_error` 事件的现成样板。
9. `/api/undo`（`server.py:645-651`）只挡 ranked；engine 局悔棋今天就会脱节 `ctx.moves`（G4 是**现存 bug**，纯屏幕 engine 局同样受益于修复）。
10. poller 对 gateway 的调用传 `user_id=0`（`server.py:2001`）；engine 分支不校验 user_id，无需改。
11. 隧道等待期（可长达 180s）：数字盘还没有人类这手（remote-first），物理盘多一子 → `LedPlanner` 单子飞行豁免（`physical_play.py:162-168`）已覆盖；用户此期间再摆一子 → pending 拒绝 → 排队重试（本计划不改，Task 9 集成测试固化该行为）。

---

## Task 0 — 基线确认

- [ ] `uv sync`；`CI=true uv run pytest tests -q` 记录基线失败集（写进本文件底部「基线记录」节）。
- [ ] `cd katrain/web/ui && npm install && npm run build && npm run build:kiosk-2d` 双绿。
- [ ] 通读：`physical_play_orchestrator.py`（全文 ~380 行）、`physical_play.py`（LedPlanner）、`gateway.py:41-115`、`adapter.py:704-945`（engine 方法）、`server.py:1952-2027`（poller）、`GamePage.tsx:35-60,138-200,280-340`。
- **Verification**: 基线记录已写入；能复述「物理子 → poller → gateway engine 分支 → 隧道 → [human,AI] 落子 → 编排器点灯」全链路。
- **Review checkpoint**: 无（机械任务）。

## Task 1 — 后端：engine 对手标记（G1 上半，TDD）

- Files: Modify `katrain/web/platforms/manager.py`（`start_engine_game` :152-161 附近）、`katrain/web/platforms/models.py`（常量）；Test `tests/platforms/test_engine_manager.py`。
- [ ] `models.py` 加常量 `ENGINE_PLAYER_SUBTYPE = "platform:engine"`。
- [ ] **先核实副作用**：grep 全仓 `player_subtype` 消费方（后端 `interface.py:446,562,874`、前端）。确认对 `player_type="human"` 的一方设置 subtype 不影响 rank 显示 / AI 策略解析 / 记谱。若有冲突，就地回报改用独立字段（不擅自扩散改动面）。
- [ ] **写失败测试**：`start_engine_game`（mock adapter，参照既有 test_engine_manager 风格）后，`session.katrain.get_state()["players_info"]` 中 bot 颜色的 `player_subtype == "platform:engine"`、`player_type` 仍是 human 形态；人类颜色 subtype 无标记。执黑/执白两个用例。
- [ ] 实现：`start_engine_game` 在 `edit_game` 后对 bot 颜色调 `session.katrain("update_player", bw=ai_bw, player_type=<现值不变>, player_subtype=ENGINE_PLAYER_SUBTYPE, name=bot_name)`。注意保留现有名字设置行为。
- [ ] 跑测试通过；`CI=true uv run pytest tests/platforms -q` 相对基线无新增失败；commit。

## Task 2 — 后端：编排器识别引导色（G1 下半，TDD）

- Files: Modify `katrain/web/core/physical_play_orchestrator.py`（`_guided_colors_from_state` :247-259）；Test `tests/test_physical_play_orchestrator.py`。
- [ ] **写失败测试**：state 中 W 方 `player_subtype=="platform:engine"`（player_type human）→ `_guided_colors_from_state` 返回 `{WHITE}`；双 human 无标记 → 空集（现行为不回归）；`player:ai` 分支不回归。**用 Task 1 真实 session 的 get_state() 输出构造用例**（关键事实 #1 的字面值陷阱）。
- [ ] 实现：guided 条件扩为 `player_type == "player:ai" or player_subtype == ENGINE_PLAYER_SUBTYPE`（从 models 导入常量；orchestrator 不依赖 platforms 包的话就地定义同值常量并注释来源，避免 core→platforms 反向依赖——**实施时二选一并说明**）。
- [ ] 集成冒烟（同文件测试内）：构造 orchestrator + 假 vision/led，喂 engine 局 state（AI=W 刚落一子、物理盘缺该子）→ tick 后 led 收到绿灯点。
- [ ] 跑测试通过；commit。

## Task 3 — 前端：humanColor/横幅修复（G2，TDD）

- Files: Modify `katrain/web/ui/src/kiosk/pages/GamePage.tsx`（:35-52 helpers、:170-185 横幅、:288-291 humanColor）、`GameState` 类型定义（`players_info` 加可选 `player_subtype`，位置随类型现居处：`src/api.ts` 或 `src/types/`——**属共享区，双构建**）；Test `src/kiosk/__tests__/GamePageEngine.test.tsx`（已有文件，追加用例）。
- [ ] **写失败测试**：engine 局人执白（B=bot 带 `player_subtype:'platform:engine'`，W=human）→ humanColor 推导为 `'W'`；AI(B) 落子后横幅显示 AI 坐标；人执黑现行为不回归；本地 HvAI（player:ai）不回归。
- [ ] 实现：抽 `isEngineOpponent(gs, c) = gs.players_info?.[c]?.player_subtype === 'platform:engine'`；humanColor = 「player_type 为 human 形态**且**非 engineOpponent」的颜色（两处 :177-178 与 :288-290 统一改）；`deriveAiTurnState.isAI` 增加 engineOpponent 分支（使 `aiColor` 在 engine 局有值——注意隧道等待期 `player_to_move` 仍是人类、`aiThinking` 不会误亮，测试断言之）。
- [ ] `npm run build` + `npm run build:kiosk-2d` 双绿；`npm test -- GamePageEngine` 绿；commit。
- **Review checkpoint（人工）**: G1+G2 合并效果——Mac dev 模式（in-process vision 或 mock）开一局 engine 局，确认 AI 落子亮灯、执白局回合门控正确。

## Task 4 — 后端：提交前重建 ctx.moves（G4，TDD）

- Files: Modify `katrain/web/platforms/gateway.py`（`_play_engine_move` :76 入口处）、`katrain/web/platforms/manager.py`（新 helper）；Test `tests/platforms/test_engine_gateway.py`。
- [ ] **先读** `adapter.py:935-945` `rebuild_engine_moves` 与让子塞子逻辑（`_handicap_stones`），确认重建语义是否保留让子前缀：让子星位在本地棋局树中是**根节点 setup 子（无 move number）**，不在主线 moves 里——重建函数若只收主线 moves，需要 adapter 侧自行补前缀或 helper 侧显式传入。**以真实代码为准定接口，测试覆盖让子局。**
- [ ] **写失败测试**：
  1. 分先局：mock genmove 下 3 手 → `session.katrain("undo", 2)` → 再经 gateway 落一手 → 断言本次 genmove 收到的 moves CSV 与悔棋后的棋局树主线一致（这是当前必挂的红测）。
  2. 让 4 子局：悔 1 手再落 → moves 前缀仍是 4 颗星位。
  3. 无悔棋正常连下 → 行为与现状完全一致（重建幂等）。
- [ ] 实现：manager 加 `def rebuild_engine_context(self, session_id) -> None`（从 session 棋局树主线提取 coords，调 adapter.`rebuild_engine_moves`；参照 manager 现有 tree 提取代码若有）；gateway `_play_engine_move` 在 `set_pending` 前调用。异常处理：重建失败（树异常）→ 直接 rejected `"engine_error"`，不半提交。
- [ ] 跑测试通过；commit。

## Task 5 — 后端：有界重试 + 错误挂起 + 收尾端点（G3，TDD）

- Files: Modify `katrain/web/server.py`（poller :1999-2009）、`katrain/web/platforms/gateway.py`（异常 reason）、`katrain/web/core/physical_play_orchestrator.py`（error 挂起 API）、`katrain/web/core/physical_play.py`（`PhysicalPlayConfig` 加 `engine_move_max_attempts: int = 3`）、`katrain/web/api/v1/endpoints/vision.py`（两个新端点）；Test 新 `tests/test_engine_physical_retry.py`（+ `tests/platforms/test_engine_gateway.py` 补 reason 断言）。
- [ ] `PlatformMoveRejectedError` 加 `reason: str` 属性（`"engine_error" | "game_ended" | "pending" | ...`），gateway 三个 raise 点设置（`gateway.py:84-93` 与 `:47`）。既有捕获方不受影响（属性新增，str 语义不变）。
- [ ] **写失败测试（poller 层，模拟 gateway）**：
  1. 连续 `engine_error` 失败 `max_attempts-1` 次内 → 每次 re-arm（现行为），无广播；
  2. 第 `max_attempts` 次 → 调 `orchestrator.enter_engine_error(coords)` + `broadcast_to_session` 收到 `{"type":"physical_engine_error", col, row, attempts, detail}`，**且不再 re-arm**（检测已挂起，不会再自动打隧道）;
  3. `reason=="pending"` / `"game_ended"` 的异常**不计数**；
  4. 中途成功一次 → 计数清零。
- [ ] **写失败测试（orchestrator）**：`enter_engine_error` → move detection 暂停（复用 `_sync_pause_state` 家族，仿 `_hint_active` 加 `_engine_error_active` 标志）；`clear_engine_error(resync: bool)` → 恢复；`resync=True` 走既有 `resync()`。
- [ ] **写失败测试（端点）**：
  - `POST /api/v1/vision/engine-move/retry` `{session_id}` → 用 poller 存储的失败坐标重新 `gateway.play_move`；成功 → 清错误态+计数、返回 ok；再失败 → 保持错误态、返回 `{"ok":false,"detail"}`（HTTP 200，前端对话框留存）。无错误态时 404/409。
  - `POST /api/v1/vision/engine-move/cancel` `{session_id}` → `orchestrator.clear_engine_error(resync=True)` + 清计数（用户已拿回棋子；这手从未进数字盘）。
- [ ] 实现：失败状态存 `app.state.vision_engine_failures: dict[str, dict]`（session_id → {count, coords, detail}）；poller 只在 vision 绑定的平台局分支读写；session unbind/结束时清理（挂 unbind 端点或 orchestrator.on_unbind）。
- [ ] 跑测试通过；`CI=true uv run pytest tests -q` 相对基线无新增失败；commit。

## Task 6 — 前端：隧道失败对话框（G3 前端，TDD）

- Files: Modify `katrain/web/ui/src/hooks/useGameSession.ts`（`physical_engine_error` 消息 → state，仿 `physicalReminder` :99-100 模式；**共享区，双构建**）、`src/api.ts`（`visionEngineMoveRetry`/`visionEngineMoveCancel`；共享区）、`GamePage.tsx`（挂载对话框）；New `src/kiosk/components/physical/EngineMoveErrorDialog.tsx`；Test 新 `src/kiosk/__tests__/EngineMoveErrorDialog.test.tsx` + `GamePageEngine.test.tsx` 追加。
- [ ] **写失败测试**：收到 `physical_engine_error` → 对话框弹出，显示坐标与「星阵连接出错」文案；三按钮：
  - 「重试」→ 调 retry API；返回 `ok:false` → 对话框留存显示错误；`ok:true` → 关闭；
  - 「拿回棋子」→ 显示指引文案（拿除 X 处棋子）→ 确认后调 cancel API → 关闭；
  - 「认输」→ 复用现有 resign 确认流（`GamePage.tsx:555` 一带）。
  - 纯屏幕局（`!isVisionEnabled`）不订阅/不弹（现有 engineErrorToast 不回归）。
- [ ] 实现；文案 `t()` 中文默认。
- [ ] `npm test` 相关文件绿；双构建绿；commit。
- **Review checkpoint（人工）**: Mac 上 mock 断网（如 hosts 屏蔽 api.19x19.com 或 mock adapter 抛错）走一遍三按钮路径。

## Task 7 — 后端：支招白灯（G5 上半，TDD）

- Files: Modify `katrain/web/api/v1/endpoints/platforms.py`（engine/analysis :235-260）；Test `tests/platforms/test_engine_analysis_endpoint.py` 追加。
- [ ] **写失败测试**：`kind=="options"` 成功、`app.state.physical_play` 存在、`app.state.vision.bound_session_id == session_id` → `orchestrator.show_hint` 被调，入参为候选点的 vision_rc list（金标准：KaTrain `(col=3,row=3)` D16 → vision_rc `(15,3)`）；`kind=="area"/"variation"` 不调；`QuotaExhausted`(7003) 不调；vision 未绑定该 session 不调；orchestrator 缺席（server 模式）不调不炸。
- [ ] 实现：候选 `(col,row)` → `(board_size-1-row, col)`；`board_size` 从 session 棋局取（固定 19 亦断言）。show_hint 调用包 try/except（LED 失败不阻塞分析结果返回，R2.6 精神）。
- [ ] 跑测试通过；commit。

## Task 8 — 前端：支招灯同步灭（G5 下半，TDD）

- Files: Modify `GamePage.tsx`（overlay 失效 effect :199-202、`handleEngineAnalysis` :372-408、退出清理）；`src/api.ts` 若无 `hintDismiss` 则补（共享区）；Test `GamePageEngine.test.tsx` 追加。
- [ ] **写失败测试**：engine 局 vision 开启时——支招叠加因落子失效 / 用户切换关闭 / 离开页面 → `API.hintDismiss` 恰好一次；非 options 叠加与纯屏幕局不调。
- [ ] 实现：跟踪当前叠加 kind，`options` 且 `isVisionEnabled` 时在清空路径统一调 dismiss（幂等，多调无害但测试卡「恰好一次」防抖动）。
- [ ] `npm test` 绿；双构建绿；commit。

## Task 9 — 集成测试：让子/执白/排队/端到端（TDD 收口）

- Files: New `tests/test_engine_physical_integration.py`（参照 `tests/platforms/test_engine_integration.py` 与 `tests/test_physical_play_orchestrator.py` 的组装方式，mock 隧道 + 假 vision/led）。
- [ ] 用例 1（执白开局）：人执白 → start 后 AI(B) 首手已在数字盘 → orchestrator bind + tick → led 收到该点红灯。
- [ ] 用例 2（让 4 子）：让子局 start → `_setup_cells_from_state` 引导 4 星位 → 模拟视觉逐子到位 → 灯灭 → AI(W) 首手灯亮。
- [ ] 用例 3（全链路一手）：模拟 ConfirmedMove → poller → gateway（mock genmove 返回 AI 手）→ 数字盘 `[human, AI]` 顺序 → tick 后 AI 点亮、human 不亮。
- [ ] 用例 4（隧道等待排队）：pending 期间第二个 ConfirmedMove → `reason=="pending"` 不计失败数、不触发对话框、re-arm 后可重试（固化关键事实 #11 行为）。
- [ ] 全绿后：`CI=true uv run pytest tests -q` 相对基线无新增失败；`uv run black -l 120 katrain tests`；commit。

## Task 10 — i18n + 收尾

- [ ] 新增静态文案（对话框/指引/按钮）走 `katrain-i18n-expert` skill 补全 11 语言（cn≠zh、jp≠ja；默认中文）。
- [ ] `uv run python i18n.py` 重新生成 .mo（如该 skill 流程要求）。
- [ ] 双构建绿 + 全量 pytest 相对基线无新增失败；commit + push `feature/kiosk-play-golaxy`（用户既定：直接推送不开 PR）。
- **Review checkpoint（人工）**: 走查全部新 UI 文案。

## Task 11 — 真机部署与验收（用户参与，一次性）

- [ ] **前置**：`ssh rk3562-direct` 确认外网：`curl -sS -m 10 https://api.19x19.com/ -o /dev/null -w '%{http_code}'`。不通 → 先配 Mac 网络共享/路由/DNS（就地回报，不算开发失败）。
- [ ] 部署本分支到 rk3562（沿用既有 board 模式部署方式），带 `--vision-model/--led-serial-port/--capture-camera` 等既有旗标启动。
- [ ] 验收单（对照 PRD §6）：
  1. 星阵登录（持久 token 自动重连或 SMS）→ 开局；
  2. 物理下 ≥30 手：每手 AI 灯、提子蓝灯正确；
  3. 执白局 + 让子局各开一局验证开局引导；
  4. 断网重试对话框三路径；
  5. 悔 2 手恢复续下，后端日志 moves 与树一致；
  6. 支招白灯 + 7003 路径（需道具余额）；
  7. 摆谱/死活棋回归抽查。
- **Review checkpoint（人工）**: 验收单全过 → 决定合并策略（`superpowers:finishing-a-development-branch`）。

---

## Testing strategy 汇总

- 纯函数/状态机优先 TDD；隧道一律 mock（respx/httpx 或 adapter mock），CI 不打真星阵。
- 关键回归三防线：① 双 human 无标记 → 引导色空集（本地人人/远程平台局不误点灯）；② `player:ai` 分支（本地自由对弈物理版）不回归；③ 纯屏幕 engine 局（server 模式无 orchestrator）所有新钩子静默跳过。
- 前端测试用 `create_multiplayer_session` 真实序列化形态构造 fixture（player_type 字面值陷阱）。
- 真机验证只在 Task 11 做一次。

## Risks / open questions（评审前）

- `player_subtype` 是否有隐性消费方（Task 1 第一步核实；冲突则换独立字段，改动面等价）。
- `rebuild_engine_moves` 让子前缀语义（Task 4 第一步读代码定接口）。
- 编排器 `enter_engine_error` 与 hint 挂起（`_suspended`）并存时的状态机组合（Task 5 测试覆盖：error 中触发 hint、hint 中触发 error）。
- poller 失败计数的清理时机（unbind/对局结束/换局），防跨局残留（Task 5 实现+测试）。
- rk3562 外网路径未验证（Task 11 前置，有 Mac 降级路径）。

## 基线记录（Task 0 填写）

- pytest 基线失败集：*待填*
- 双构建基线：*待填*
