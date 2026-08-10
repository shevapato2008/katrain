# Galaxy 升降级跨设备对局后端 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把已确认的未完成对局界面接入真实云端账户级权威，使同一账号跨终端最多一局升降级对局，任一终局入口只结算一次，并在共享 `user_games` 中记录终端来源。

**Architecture:** 新增职责单一的云端 `ai_ladder_active_games` 表表示账号级唯一占用，盒端既有 `ai_ladder_pending_games` 继续只做本地耐久镜像；`ai_ladder_game_ledger.game_id` 继续作为 first-terminal-wins 的不可变终局决定。盒端开局前向云端预约并取得冻结对手和 `game_id`；正常终局通过现有 outbox 提交棋谱和结果，远端主动结束则由云端生成最小合法 SGF。所有云端终局都走同一数据库事务并在其中写 `user_games`、ledger/profile、删除活动占用。

**Tech Stack:** FastAPI、Pydantic、SQLAlchemy、SQLite/PostgreSQL、httpx、pytest、React/Vitest（仅真实契约回归）

---

## Chunk 1: 云端权威基础

### Task 1: 终端来源字段与无损迁移

**Files:**
- Modify: `katrain/web/core/models_db.py`
- Modify: `katrain/web/core/migrations.py`
- Modify: `katrain/web/core/user_game_repo.py`
- Modify: `katrain/web/api/v1/endpoints/user_games.py`
- Test: `tests/web_ui/test_migrations.py`
- Test: `tests/test_user_game_repo.py`

- [ ] **Step 1: 写失败测试**

覆盖：旧库无损创建 `ai_ladder_active_games`；增加本地 `ai_ladder_pending_games.reservation_key`、`ai_ladder_game_ledger.origin_device_id/deciding_device_id/terminal_source` 和 `user_games.origin_device_id`；既有行保留；用户棋局 repository/API 能读写可空 `origin_device_id`。

- [ ] **Step 2: 运行聚焦测试并确认 RED**

Run: `python -m pytest tests/web_ui/test_migrations.py tests/test_user_game_repo.py -q`

- [ ] **Step 3: 实现最小模型与迁移**

字段约束：

```text
AiLadderActiveGame.user_id              unique，账号级唯一活动/待结算局
AiLadderActiveGame.game_id              unique，不透明幂等键
AiLadderActiveGame.origin_device_id     non-null for new reservations
AiLadderActiveGame.origin_session_id    nullable，激活后可写入但不向其他终端返回
AiLadderActiveGame.state                reserved|active|pending_settlement
AiLadderActiveGame.version              CAS 版本
AiLadderActiveGame.reservation_key_hash 服务端签发的一次性预约密钥摘要
AiLadderActiveGame.frozen_config        规则/贴目/用时/对手完整冻结快照
AiLadderActiveGame.created_at/updated_at 生命周期时间
AiLadderPendingGame.reservation_key      本地持有的云端预约凭证；legacy 可空且永不进入公开响应/日志
AiLadderGameLedger.origin_device_id     nullable only for legacy rows
AiLadderGameLedger.deciding_device_id   nullable only for legacy rows
AiLadderGameLedger.terminal_source      played_result|remote_resign|recovery；legacy 可空
AiLadderGameLedger.decided_at           权威终局时间
UserGame.origin_device_id               nullable（导入/研究及 legacy 无终端来源）
```

新表由 `create_all` 无损创建；新列使用现有 `add_missing_columns` 增量迁移。把活动表加入 `PROTECTED_TABLES`，迁移必须幂等，既有 pending/ledger/user_games 行的新字段保持可空。迁移测试必须证明盒端重启后能从 pending 镜像恢复 `reservation_key` 并继续 outbox 结算。

- [ ] **Step 4: 运行聚焦测试并确认 GREEN**

Run: `python -m pytest tests/web_ui/test_migrations.py tests/test_user_game_repo.py -q`

- [ ] **Step 5: 提交**

Commit: `扩展升降级终端来源模型`

### Task 2: 账户级预约与统一终局事务

**Files:**
- Modify: `katrain/web/core/ai_ladder_ranked.py`
- Modify: `katrain/web/core/user_game_repo.py`
- Test: `tests/web_ui/test_ai_ladder_ranked.py`

- [ ] **Step 1: 写失败测试**

覆盖：同用户只允许一个预约；预约冻结 `game_id/user_color/opponent/origin_device_id` 并签发不可回读的一次性预约密钥；不同用户不冲突；只有持预约密钥者可执行 `reserved → active`，取消只允许持密钥者在 `reserved` 状态执行；正常结果与远端认输并发/顺序重放时第一份 ledger 获胜；事务只写一条 `user_games`、一条 ledger、只更新一次 profile，并清除占用；远端认输生成 `RE[user resigned]` 的最小合法 19 路 SGF；旧无预约 settlement 保持兼容。

- [ ] **Step 2: 运行聚焦测试并确认 RED**

Run: `python -m pytest tests/web_ui/test_ai_ladder_ranked.py -q`

- [ ] **Step 3: 实现 repository 原子边界**

新增清晰的 domain 方法：`reserve_game`、`activate_reservation`、`mark_pending_settlement`、`cancel_reservation`、`get_blocking_game`、`finalize_reserved_game`。预约密钥只以哈希存库，代替可伪造的设备 ID 承担原设备专属动作授权。`finalize_reserved_game` 在一个写事务内：先做 replay 快路径；锁定当前用户活动行；获得锁后再次检查 ledger；验证冻结字段与终局来源；创建或验证同 ID 的 `UserGame`；调用现有评级判定逻辑写 ledger/profile；删除活动行；提交。唯一键竞争必须捕获后回读 ledger 回执。不得先删占用，也不得由 endpoint 直接改段位。

- [ ] **Step 4: 运行聚焦测试并确认 GREEN**

Run: `python -m pytest tests/web_ui/test_ai_ladder_ranked.py -q`

- [ ] **Step 5: 提交**

Commit: `建立升降级账户级终局事务`

### Task 3: 云端预约、状态与结束 API

**Files:**
- Modify: `katrain/web/api/v1/endpoints/ai_ladder.py`
- Test: `tests/web_ui/test_ai_ladder_api.py`

- [ ] **Step 1: 写失败测试**

覆盖内部预约 API、总览 `blocking_game`、按局 status、主动结束、重复结束、跨设备 ownership、不泄露其他设备 session、404 不泄露他人对局、正常结算与结束竞态、共享 `user_games.origin_device_id/source/game_type`。

- [ ] **Step 2: 运行新增测试并确认 RED**

Run: `python -m pytest tests/web_ui/test_ai_ladder_api.py -q`

- [ ] **Step 3: 实现契约**

新增：

```http
POST   /api/v1/ai-ladder/games/reserve
POST   /api/v1/ai-ladder/games/{game_id}/activate
POST   /api/v1/ai-ladder/games/{game_id}/pending-settlement
DELETE /api/v1/ai-ladder/games/{game_id}/reservation
GET    /api/v1/ai-ladder/games/{game_id}/status
POST   /api/v1/ai-ladder/games/{game_id}/end
```

远程盒端请求用 `X-StellaBox-Device-ID` 提供来源标签；它不承担授权。预约返回高熵 `reservation_key`，只有密钥持有者能 activate、取消、标 pending 或提交 `played_result`；数据库只保存摘要。`/status` 返回显式 `blocking_game: null|object`；session 绝不从云端返回。`/pending-settlement` 执行 `active → pending_settlement`；`/end` 允许同账号任意设备执行，固定用户结果 `loss`、`terminal_source=remote_resign`，同步完成终局并只返回 `settled` 回执；409 竞态携带同一 settled receipt。

内部 `reserved` 只是本地 session 创建的短暂准备态，对外映射为现有 `blocking_game.state=active` 且不返回 `session_id`，因此前端仍呈现“刷新状态 + 结束该对局”，不扩展已冻结的状态联合。用户已经确认任意设备可立即结束占用，所以 `/end` 允许结束 `reserved|active|pending_settlement`；而补偿取消只允许持预约密钥者在 `reserved` 状态执行。两者并发时使用同一行锁：取消先赢表示本地从未成功开局，终局先赢则产生不可撤销负局，取消必须重放已结算结果而不能清除 ledger。

扩展 `/settlements` 接收可选但严格校验的 `game_record`；新预约局必须走统一终局事务，legacy 无预约提交继续走现有幂等 settlement。

- [ ] **Step 4: 运行聚焦测试并确认 GREEN**

Run: `python -m pytest tests/web_ui/test_ai_ladder_api.py -q`

- [ ] **Step 5: 提交**

Commit: `提供升降级跨设备权威接口`

## Chunk 2: 盒端集成与 Fixture 退出

### Task 4: Remote client 与盒端开局预约

**Files:**
- Modify: `katrain/web/core/remote_client.py`
- Modify: `katrain/web/api/v1/endpoints/ai_ladder.py`
- Modify: `katrain/web/server.py`
- Test: `tests/web_ui/test_remote_ai_ladder_methods.py`
- Test: `tests/web_ui/test_ai_ladder_api.py`

- [ ] **Step 1: 写失败测试**

覆盖每次云端请求携带设备 ID；盒端 status 代理云端并仅在本地同 ID 会话可恢复时补 `session_id`；盒端开局必须先云端预约、持有预约密钥、创建本地 session 后激活；本地失败用预约密钥取消仍为 `reserved` 的预约；无网络/无认证不创建正式局；正常终局 outbox 携带同一 `game_id`、预约密钥、`origin_device_id` 和完整 `game_record`。

- [ ] **Step 2: 运行聚焦测试并确认 RED**

Run: `python -m pytest tests/web_ui/test_remote_ai_ladder_methods.py tests/web_ui/test_ai_ladder_api.py tests/web_ui/test_ladder_settlement_sync.py -q`

- [ ] **Step 3: 实现盒端代理与失败补偿**

把 board mode 的升降级 status/start/end/game-status 转到 `RemoteAPIClient`；预约密钥保存在本地 pending 镜像（不得进入 UI/API 响应或日志），本地 session 与 pending 仅为执行镜像。保留现有本地耐久保存与 outbox，但云端回执覆盖本地乐观 profile。删除 `_recover_pending` 中“本节点无 session 即清占用”的行为。

- [ ] **Step 4: 运行聚焦测试并确认 GREEN**

Run: `python -m pytest tests/web_ui/test_remote_ai_ladder_methods.py tests/web_ui/test_ai_ladder_api.py tests/web_ui/test_ladder_settlement_sync.py -q`

- [ ] **Step 5: 提交**

Commit: `接通盒端升降级云端预约`

### Task 5: 原设备终局感知与真实前后端集成

**Files:**
- Modify: `katrain/web/server.py`
- Modify: `katrain/web/ui/src/features/aiLadder/api.ts`
- Modify: `katrain/web/ui/src/galaxy/pages/AiSetupPage.tsx`
- Test: `tests/web_ui/test_ai_ladder_api.py`
- Test: `katrain/web/ui/src/features/aiLadder/api.test.ts`
- Test: `katrain/web/ui/src/galaxy/pages/AiSetupPage.test.tsx`

- [ ] **Step 1: 写失败测试**

覆盖原设备按局状态查询、远端结束后拒绝新落子/保存且不会产生第二终局；设置页 fixture 注入移除后仍显示真实状态；结束后真实刷新显示回执。

- [ ] **Step 2: 运行聚焦测试并确认 RED**

Run: `python -m pytest tests/web_ui/test_ai_ladder_api.py -q`

Run: `cd katrain/web/ui && npm test -- --run src/features/aiLadder/api.test.ts src/galaxy/pages/AiSetupPage.test.tsx`

- [ ] **Step 3: 实现 5 秒有界轮询与写前校验**

只对活动升降级 session 轮询；收到 `pending_settlement|settled` 后标记 session 终止、停止引擎动作、拒绝落子/保存，并复用现有结算反馈。测试目录网络 route 可保留为确定性回归，生产组件的 fixture props/模拟业务状态删除。

- [ ] **Step 4: 聚焦验证**

Run: `python -m pytest tests/web_ui/test_ai_ladder_api.py tests/web_ui/test_ladder_settlement_sync.py -q`

Run: `cd katrain/web/ui && npm test -- --run src/features/aiLadder/api.test.ts src/galaxy/pages/AiSetupPage.test.tsx src/galaxy/components/aiLadder/AiLadderRatedSetup.test.tsx && npx tsc -p tsconfig.app.json --noEmit`

- [ ] **Step 5: 提交**

Commit: `完成升降级跨设备对局闭环`

### Task 6: 当前旅程自动化验收

**Files:**
- Modify: `docs/superpowers/plans/2026-08-09-galaxy-ai-ladder-active-game-backend.md`
- Test: `tests/web_ui/test_ai_ladder_api.py`
- Retain unchanged: `katrain/web/ui/tests/galaxy-ai-ladder-active-game-visual.spec.ts`

- [x] **Step 1: 明确真实契约与视觉回归的测试分层**

状态、预约/激活、结束、回执和数据库约束由真实 FastAPI/SQLite 测试实例验收；Playwright 的网络 route
继续只承担已确认页面的确定性视觉回归，不作为业务契约证据，也不引入生产测试端点或 seed 服务。生产组件中已无
模拟生命周期业务数据，因此本切片的生产 Fixture 删除条件已经满足；测试目录中的隔离 route 作为回归资产保留。

- [x] **Step 2: 执行最小验收矩阵**

`test_cross_device_ranked_journey_has_one_receipt_and_one_auditable_write` 通过公共 API 串起：设备 A 开局（内部完成
reserve/activate）；设备 B 看到 `other_device` 并主动结束；A 读取 settled 后继续落子被 409 拒绝；两端读取同一
receipt；SQLite 中恰有一条 `user_games` 和一条 ledger，且 `origin_device_id=galaxy-a`、
`deciding_device_id=galaxy-b`、`terminal_source=remote_resign`。这些行为此前已有分散测试覆盖，本步骤是验收测试组织，
没有发现需要生产改动的 RED 缺口。

- [x] **Step 3: 运行聚焦切片验证**

Run: `python -m pytest tests/web_ui/test_ai_ladder_api.py::test_cross_device_ranked_journey_has_one_receipt_and_one_auditable_write -q`

Expected: PASS；不重复运行本阶段无改动的视觉和全量前端测试。

- [x] **Step 4: 提交验收资产**

Commit: `验收升降级跨设备对局闭环`

## 明确不做

- 不改围棋 41 阶评级算法、AI 目录或已冻结对手配方。
- 不新建升降级专属历史表，不把 `source` 混用为设备来源。
- 不实现跨设备续弈、设备管理页、通用消息中心或 kiosk 视觉改造。
- 不扩展为四棋共享数据库；只保持可复用的契约原则。
- 不做全量测试矩阵；只跑当前高风险事务、迁移、API 和已确认 Galaxy 旅程的聚焦测试。
