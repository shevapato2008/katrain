# Design Review Feedback: RK3588 Smart Board Database Architecture

> Reviewer: Codex
> Date: 2026-02-09

## Summary Verdict

整体方向正确：`API-First + 本地 SQLite 离线缓冲`是当前约束下最务实的架构选择，明显优于“棋盘直连云端 PostgreSQL”或“每板一套 PostgreSQL”。但当前方案在“可重复同步（idempotency）”“认证续期与离线恢复”“运行态切换并发控制”“WebSocket链路一致性”四个点上存在落地风险，若不先补齐，实施后会出现重复写入、离线数据卡死、状态抖动和功能行为不一致问题。

## Critical Issues (must fix before implementation)

1. **`sync_queue` 缺少幂等设计，`create_user_game` 会出现重复写入风险。**  
   文档假设“本地生成 UUID + append-only 无冲突”，但现有 `POST /api/v1/user-games/` 入参不支持客户端传 `id`，服务端在创建时自行生成 `id`；在网络抖动重试时会产生重复棋谱。  
   参考：`superpowers/tracks/rk3588-database/design.md:212`、`superpowers/tracks/rk3588-database/design.md:213`、`katrain/web/api/v1/endpoints/user_games.py:14`、`katrain/web/core/user_game_repo.py:17`、`katrain/web/core/models_db.py:291`。  
   必须补充：`idempotency_key/client_op_id`（队列与服务端都要存），并让 `create_user_game` 支持“客户端主键写入”或“按幂等键去重”。

2. **`user_tsumego_progress` 的冲突策略与现有实现不一致，存在跨设备回退覆盖。**  
   文档写的是“attempts 取最大值”，但当前服务端逻辑是直接覆盖 `attempts`。同账号在两台棋盘离线后同步，后到达请求可能把更高 attempts 覆盖掉。  
   参考：`superpowers/tracks/rk3588-database/design.md:210`、`katrain/web/api/v1/endpoints/tsumego.py:237`。  
   必须补充：服务端 merge 规则（如 `attempts=max`、`completed=OR`、`first_completed_at=min_non_null`、`last_attempt_at=max`），并写成明确契约。

3. **认证生命周期闭环缺失：仅内存 token 无法覆盖“离线后再同步”的真实场景。**  
   方案写“token 缓存到内存且自动 refresh”，但现有后端只有 login/register/me/logout，无 refresh endpoint；token 默认 7 天。设备离线超过 token 有效期后，重连同步会失败。  
   参考：`superpowers/tracks/rk3588-database/design.md:269`、`superpowers/tracks/rk3588-database/design.md:340`、`katrain/web/api/v1/endpoints/auth.py:56`、`katrain/web/api/v1/endpoints/auth.py:69`、`katrain/web/api/v1/endpoints/auth.py:89`、`katrain/web/core/config.py:26`。  
   必须补充：refresh token / device credential 方案、离线期间到期后的重认证流程、sync_queue 在“未认证状态”下的暂停与恢复策略。

4. **在线/离线切换机制存在并发竞态，可能触发并行同步和双重执行。**  
   当前设计是 ConnectivityManager 切换状态后触发同步并切换 Repository，但未定义“单飞锁”“队列加锁字段”“请求级路由一致性”。网络抖动时极易出现两个同步 worker 同时消费同一批任务。  
   参考：`superpowers/tracks/rk3588-database/design.md:224`、`superpowers/tracks/rk3588-database/design.md:226`、`superpowers/tracks/rk3588-database/design.md:185`。  
   必须补充：`is_syncing` 进程锁 + `sync_queue` 行级租约字段（如 `status/locked_at/locked_by`），并规定切换窗口中 in-flight 请求的处理策略。

5. **WebSocket链路假设与现有前端实现冲突。**  
   文档写“在线时浏览器直连远程 WebSocket，不做本地代理”，但前端当前固定连 `window.location.host/ws/...`，在棋盘部署下默认连接本机 FastAPI。若不改造前端路由策略，在线多人/直播链路不会按文档描述工作。  
   参考：`superpowers/tracks/rk3588-database/design.md:358`、`superpowers/tracks/rk3588-database/design.md:156`、`superpowers/tracks/rk3588-database/design.md:157`、`katrain/web/ui/src/ZenModeApp.tsx:114`、`katrain/web/ui/src/galaxy/pages/HvHLobbyPage.tsx:89`。  
   必须补充：明确“本地代理 WS”或“前端按模式改为远端 WS URL”二选一，并定义认证 token 透传方式。

## Recommendations (should consider)

1. **补全 `sync_queue` 状态机字段。**  
   当前表缺少 `status/next_retry_at/last_http_status/last_error_code/user_id/device_id/idempotency_key/updated_at`，不利于回放、审计和运维。  
   参考：`superpowers/tracks/rk3588-database/design.md:185`。

2. **调整 roadmap 顺序：先做“认证闭环 + 幂等契约 + 观测”，再做 Repository 抽象。**  
   现在的 Phase 2-5 会把业务层改造放在前面，建议把“最难回滚的数据一致性能力”提前。  
   参考：`superpowers/tracks/rk3588-database/design.md:448`、`superpowers/tracks/rk3588-database/design.md:467`。

3. **离线可用性建议做“轻量内容包”而非完全不可用。**  
   完全禁用死活题/棋谱会明显拉低离线体验；可考虑预置小规模包（如 200-500 题 + 最近热门棋谱）。  
   参考：`superpowers/tracks/rk3588-database/design.md:154`、`superpowers/tracks/rk3588-database/design.md:355`。

4. **加入设备级可观测性。**  
   建议增加 board 心跳（`device_id`、`queue_depth`、`oldest_unsynced_age`、`last_sync_at`），服务端做告警（例如 24h 无心跳或失败率超阈值）。

5. **本地数据生命周期管理要显式定义。**  
   需要落地“已同步记录保留时长、清理策略、VACUUM 时机、磁盘水位阈值”。

## Minor Suggestions (nice to have)

1. **健康探测可加入延迟阈值与退避策略。**  
   不只看 reachability，也看 RTT，避免弱网下频繁抖动。  
   参考：`superpowers/tracks/rk3588-database/design.md:221`。

2. **离线 UI 文案需要产品化定义。**  
   对“不可用功能”给明确提示、重试按钮与预计恢复条件，不要只返回通用错误。

3. **升级流程避免手工 `rm db.sqlite3`。**  
   建议改成受控脚本：校验网络->强制同步->确认队列为空->备份->清库->重启。  
   参考：`superpowers/tracks/rk3588-database/design.md:381`。

4. **威胁模型建议补一页。**  
   包含设备被盗、离线暴力读取、调试口访问、token 泄露后的失效策略。

## Questions for the Author

1. 同一账号在两台棋盘离线做题后重连，`attempts/completed/first_completed_at` 的最终业务语义是什么？
2. 棋盘是否支持多用户切换登录？若支持，`sync_queue` 与本地缓存如何做到用户级隔离与清理？
3. 当队列出现永久失败（4xx 业务错误）时，期望的用户体验和运维处理流程是什么？
4. 在线模式下，多人对弈/直播功能是否是必须能力？如果是，WebSocket 你们计划走“本地代理”还是“前端直连远端”？
5. 可接受的最长离线时长是多少（7 天、30 天、90 天）？这个值会直接影响 token、队列和数据保留策略设计。
