# Shared Vision Legal-Move Synchronization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 合法实体落子从视觉确认到数字棋谱提交期间，不再被共享同步模块报成“多余棋子”，自由、升降级及跨平台对弈同时受益；真正错子、缺子继续及时提示，紫灯与 UI 使用同一异常语义。

**Architecture:** 保留现有 MoveDetector、SyncStateMachine、两种 worker 和独立提交协程。在共享同步层增加一个轻量的“这一颗已确认的子正在提交”记录，其有效期只覆盖本次实际提交调用，数字权威更新或 finally 的 token 释放结束归属。它只拥有一个精确交叉点，不把观测写成数字权威，不新增识别状态枚举、全局等待窗或第二套棋局状态机。

**Tech Stack:** Python / numpy、FastAPI asyncio、现有 worker IPC、pytest；React/TypeScript 共享视觉恢复 reducer、Vitest。

---

## Chunk 1: 已证实根因与边界

### 基线与交付约束

- 2026-11-05 重新 `git fetch origin develop`；基线 **`fb916f12516dd510080fb736a48a825dc206bc37`**。
- 计划分支：`plan/vision-legal-move-mismatch-20261105`。
- 独立 worktree：`/tmp/katrain-vision-mismatch-plan-20261105`；通过 `--no-checkout` 后设置精确 sparse 路径才检出。没有检出、读取、遍历或 stat `data/kifu-album/`，后续同样禁止；禁止全树 `git status`。
- 目前只写本计划，没有修改产品代码、运行设备动作、部署或重启。ROOT 统一安排独立 Astra max 审计划，最多两轮；本文作者不自行建立审核队列。审过后由 ROOT 派 fresh implementer。
- 源证据：`/tmp/ladder-mismatch-investigation-20261105/investigation.txt`、`events-precise.log`、`event-analysis.json`。

### 用户现象与证据

用户按正常顺序继续下棋时提示有时自行消失，但会反复弹出，紫灯和大量提示文案干扰对局。当前目标是消除错误异常分类，不以缩文案或逐页面遮罩替代修复。

2026-11-05 20:32–20:51 的升降级局中，63 次视觉确认全部成功提交：48 次快确认（3 帧），15 次慢确认（5 帧）。15 次慢确认正好分为 13 条多余子误报及 2 条已有 stale 过滤成功拦截；48 次快确认未出现该种误报。F3 黑子精确顺序如下：

```text
20:33:54.918644 move_pending
20:33:55        board_lost → board_reacquired（清掉前端 pending）
20:33:56.490010 move confirmed，5/5 帧
20:33:56.525752 illegal_change，positions=[F3黑]，missing=[]
20:33:56.526850 LED submit 1
20:33:56.538349 Ranked vision move submitted
20:33:57.436038 synced
```

代码根因有两个连贯边界：

1. worker 在确认后推进 MoveDetector 基线并发 ConfirmedMove，但 SyncStateMachine 仍拿旧数字盘比较；同步的 5 帧阈值也正好达标。
2. 实际 `VisionService._drain_worker()` 把 ConfirmedMove 与 dict 事件拆为两个 deque，`poll_events()` 只返回 dict，`get_confirmed_move()` 另取落子。两个协程无提交先后保证；`vision_pump.py` 的 app-level move_queue 注释已与实际路径不符。不能只改 pump 中那个实际上未消费的队列。

已有 `is_stale_illegal_change()` 只在数字盘已经有子时才有效，挡不住比提交早 12.6ms 的错误事件；前端 4 秒 pending 豁免还会被 board_lost / node_advanced 清掉，且从来不能阻止后端点紫灯。

### 实际共享范围

| 场景 | 实际链路 | 本修复适用方式 |
|---|---|---|
| 自由/访客 AI 对弈 | bound worker → ConfirmedMove → `_handle_confirmed_move` 本地提交 | 使用共享待提交归属与同一提交结果协议 |
| 升降级 AI 对弈 | 同一 worker/service/poller；增加 ranked binding/seat/turn guard | 同上；不做升降级专用豁免，不削弱 guard |
| 跨平台人机/在线对弈 | 同一路径后 `await gateway.play_move()`；失败可能进入现有恢复流程 | 归属持续到权威提交/拒绝；远端 pending 不能被当成功提交 |
| 中央 PvP 房间 | 同一 bound 确认，`bridge.forward_move()`，权威为返回/推送的 room state | 同上，使用 room 权威盘；重绑后旧结果不能影响新局 |
| 无 session 的实体做题/摆谱 monitor | worker 发 dict `move_confirmed`，由任务前端判题/推进 target | 没有数字棋局提交，本协议默认不创建归属；错误答案不能借“确认过”绕过校验。共享 sync 的真实异常路径保持原语义，做正常推进回归 |
| 面对面 `pvp_local` | token-bound full-board LocalWindowObservation；普通 ConfirmedMove 被拒 | 保留已有全盘窗口权威，不接入自动提交归属；回归证明不串线 |
| RKNN inprocess / subprocess vision | 两者都有“确认后再 sync.update”顺序 | 都接同一共享 sync API 和 IPC 字段，禁止只修 RK 后端 |

### 明确不在本次猜改的内容

其余 3 条缺子提示涉及两种现象：D16 原始检测有子而旧参考矩阵空、持续 reference veto；另四颗 B/C 列棋子在 raw delta 中一起消失约 15 秒再恢复。没有原图，不能裁定遮挡、检测或参考矩阵的物理原因。单独保留证据和待验证项，本次不改 reference veto、去抖阈值、7 秒 missing hold、相机/模型参数，不将缺子一起豁免。

## Chunk 2: 最小共享契约

### 一条待提交记录，不是新业务状态机

在 `SyncStateMachine` 中最多保留一个 bound 自动确认的归属记录，数据来自 worker 确认的精确 `(row,col,color)`。记录只表达“提交结果尚未回来”，不能表达“此手已合法”。建议沿现有 ConfirmedMove 增加 `binding_epoch`、`expected_revision` 字段，继续复用 `observation_seq`；三者构成关联 token，不另引入 UUID、持久化表或网络服务。

- epoch 在实际 bind/unbind 时分配；每个发布者必须持有**产生时捕获**的 `(session对象, game/room身份, binding_epoch)` 来源，Service 验来源后才接受 expected，不能在旧数据到达时补上“当前epoch”。
- revision 与真实 board/node 快照在**同一次当前权威读取的临界区**固定并排入命令队列；同盘同 node 的分析流重复回推不增加。普通 expected 接口不再接受无来源的 bound 快照。具体发布路径、锁序及迟到检查见下节，不能仅靠 Service 接收端的缓存差异给任意旧快照分配新版本。
- worker 只对 bound、非 local-window、确已走自动确认分支的点创建归属；必须是该 expected 版本上的空点，且当前同一有效观测确实是该颜色。ambiguous、未确认候选、monitor 确认不能获此权限。
- token 的零值保留现有 unstamped 测试/兼容语义，但**不能创建异常豁免**。新增时序测试必须使用非零 epoch/observation_seq，避免 `0 == 0` 假阳性。
- 一颗归属未解决前不发第二颗自动 ConfirmedMove；仍持续同步全盘，第二颗 extra、换色、其他缺子照常属于可提示的异常。没有额外合法回合能在前一手尚无权威结论时自动成立。

### 同步比较算法

1. worker 在放出 ConfirmedMove **之前、同一轮 `_sync.update()` 之前**登记归属，修复第 5 帧源头分类；不得只在广播末端隐藏事件。
2. expected board、`_prev_expected_board`、原始/稳定/有效观测都保持真实值；禁止把确认子临时写进 expected，禁止伪造 synced、节点确认或棋谱落子。
3. 同步照常计算所有 unexpected、ripe_missing、placement_pending 和 board-lost。仅在归属 token 仍有效、当前观测点颜色一致且数字 expected 仍空时，将**这一点**标为提交中。不能把整个 payload 丢掉；同帧另一错子/缺子必须继续进入原来的异常路径。
4. 原始异常 fingerprint/帧计数继续推进；若达到阈值但唯一异常是归属点，则不发 illegal_change，**不把它重置成“刚开始积累”**，也不发 synced。真实其他点的首见时间、missing hold 和计数不因归属被延后。
5. 提交被拒后，如果这点仍在且原稳定阈值已经满足，下一可读稳定帧就必须报 actionable illegal_change，不能再等一个新的 5 帧窗，更不能靠反复确认/拒绝把错误永久藏住。重新布防只重置 MoveDetector，不能冲掉 sync 已有异常证据。
6. 归属点消失或变色即取消其豁免；保留现有 submit-time presence 校验，不把“曾经确认”当作现在仍在。任何已在棋谱里的真缺子始终走原 missing 路径。

### 真正的 expected 发布者与来源固定点（R1 V1）

不把结果 ACK 做成第二条 expected 写入通道。实际发布点必须纳入实现，不能只改 service/poller：

| 当前代码位置 | 最小接线与来源要求 |
|---|---|
| `physical_play_orchestrator.py:89–109`，`on_bind` 包装 callback | bind 时捕获上述来源。`wrapped` 可继续调用旧 `_orig` 完成它自己的会话广播，但传给实体盘的调用必须携带捕获来源；禁止调用裸 `self.on_game_state(state)` 让旧 A callback 被当成当前 B |
| 同文件 `on_game_state:147–185` | 统一的 bound expected 发布者。先在事件循环核对来源仍是活动 binding、同 session/game，再更新 `_latest_state`、local-confirm mode、pause/recovery/LED，最后发布 expected；旧来源在**任何当前实体状态副作用之前**退出。AI/尾随广播线程通过 bind 时保存的 loop `call_soon_threadsafe` 传递原来源，不能排队后再取当前来源 |
| 同一绑定内的迟到快照 | 不直接给传入 callback 的旧 `state` 盖新 revision。事件循环应用时，在本地游戏既有 `ai_ladder_commit_lock` 下读取当前 `session.katrain.get_state()`，并在同一锁持有期间校验来源、固定 board/node/revision、排入 expected 命令。读快照到排队之间无 await、不放开该 authority lock。这样延迟 A-node 回调最多触发重读当前 B-node，不会把旧盘写成更高版本；undo 回到旧节点也依实际当前盘处理 |
| `server.py:3683–3695` `apply_pvp_box_state`、`:5350–5372` bridge forward 后 | 中央 PvP 权威为经既有 `bridge.newer_state` 合并的 `session.last_state`，不能拿本地占位 `katrain.get_state()`覆盖它。来源固定为 room/game身份、session对象及发起时的 binding epoch；await 后先验源，再做当前实体盘副作用；发布时读取合并后的当前 mirror，固定 revision 与入队间无 await |
| `api/v1/endpoints/vision.py:188–270` bind/初始 expected | initial seed 经同一发布者，不再独立推一次未标来源 expected。无 orchestrator 时沿用明确 fallback，携带捕获来源并按上行 authority-lock 规则读取当前权威。远程 `fetch_state` 前捕获当前 binding/auth generation，回来先检查未被另一 bind/unbind/auth change 取代，才允许完成这次绑定，禁止旧请求回来把新绑定改回去 |
| `server.py:5226–5230` `_rearm_detection` 和各 await 后分支 | 开始处理 ConfirmedMove 时捕获原来源；`_rearm_detection`、`_apply_engine_recovery_outcome`、`enter_remote_disconnected`、tracker success/reset、`on_game_state` 等当前实体副作用前都先验源，**不能等 ACK 时才验**。不为旧请求从当前 binding 重新生成来源 |
| `api/v1/endpoints/vision.py:456–461` 手动 expected 与 monitor | 无绑定 monitor 继续既有 target API。bound 时不得让无来源手动 board 覆盖权威；走当前权威的既有 resync 路径或拒绝不适用调用，不增加相机观测接纳通道 |

实现保持一个小的来源检查/当前权威发布入口，放在现有 orchestrator，缺 orchestrator 的既有 fallback 复用相同读取/验源约束；不新增通用发布总线或持久化版本系统。orchestrator 的 bind/unbind 和实体副作用在事件循环序列化；Service 的短元数据锁只检验来源/固定 revision/发送，不在其锁内再获取游戏锁（既有游戏锁 → Service 元数据锁，锁内无 await）。同 session 重复 bind 的幂等判断还须匹配来源，不能在 Service 换了 epoch 后继续复用旧 wrapper。

### 归属生命周期与实际 gateway 出口（R1 V2）

归属严格限制在本次 `_handle_confirmed_move()` 实际调用生命周期内；不创建 detached pending owner，不向 `ctx` 增加 vision 生命周期。用一个极小的 `RELEASE_CONFIRMED_MOVE(token)` IPC 命令即可，**只携带 token，不携带 board/node/revision、不写 expected、不清平台 pending**。现有数字权威回推仍是唯一 expected 通道；新命令仅在失败/取消/guard early-return 这些“不一定产生新 expected”的路径释放 worker 记录，现有接口缺少这条通知，因此不能仅靠猜时间或等下一局来释放。

- handler 的每个出口统一经 finally 释放该 token；旧 epoch/token 的释放是 no-op，不能结算下一颗子。
- 成功/已实际提交的 terminal 出口，finally 在释放前通过上述**同一来源发布者** flush 当前权威中尚未发布的 board/node；只发送已变化的权威版本，不发送无变化板来额外 rearm。确认子可以随正常 expected 推进更早解除；FIFO 命令顺序保证 flush 在 release 之前，即便原 callback 因 250ms throttle 尚未到达也不制造新竞态。
- 失败、未知或取消时，flush 若发现权威没有变化就是 no-op；保留原代码是否 rearm、是否暂停/进入恢复的决策，release 本身只取消豁免。finally 不重新布防一个原本按恢复策略应暂停的动作。

| 真实代码出口 | 本次视觉归属如何结束；现有平台状态谁负责 |
|---|---|
| `gateway.play_move` 当前调用仍在 await | 本次调用仍拥有这一个点，其他异常照常比较。没有额外超时；用既有 gateway transport/ACK 超时 |
| 普通平台 `gateway.py:197–202` 成功 | 返回前已 `_local_play`；当前权威 publisher flush → finally release；不根据 HTTP 发送成功预测落子 |
| 星阵引擎 `:405–468` 成功或已提交的 terminal | 原 guard 已验证并在锁内提交人/AI着法；当前权威 publisher flush，terminal 记录/恢复保持原有语义；release 不制造快照 |
| `:176–177` `reason="pending"` | **上一动作**尚未结束，本次从未发送；finally 立即释放当前 token。绝不能因 `ctx.is_pending` 留下当前点豁免，也不清上一动作 |
| OGS `:295–298` exact echo + locally confirmed | 返回 ok 前已获数字权威；正常 publisher flush → release；不是虚构的 `{status:"pending"}` 返回 |
| OGS `:300–305` 不确定发送异常 | 实际是保留 `ctx.is_pending`、置 `needs_resync` 后抛 engine_error/position_changed。finally **取消本次视觉临时归属**，这不等于断言远端拒绝；不清 ctx、不重发、不伪造 accepted。旧数字盘尚未确认该点时仍可如实提示差异；平台原 reconcile/recovery 状态照常保留 |
| 迟到 OGS echo / snapshot | 仍由现有 `manager._on_opponent_move:624–665` 或 `_on_game_snapshot:735–750` 核对序号/坐标并提交、清 pending/needs_resync，触发现有 callback 的带来源 publisher。它不需寻找已释放 vision token；expected 真正一致后自然 synced |
| guard/合法性/轮次/presence/session 拒绝；gateway/bridge异常；task cancel | finally 释放；已成熟异常下一稳定帧可见。先验来源才允许现有 rearm/recovery/暂停副作用，旧 A 不能使 B 进入恢复、清 pause 或重布防 |
| undo/nav/resync/几何模式重建；unbind/rebind | 立即使旧归属失效；旧队列和 ACK 被 epoch/token 校验丢弃，不能回滚当前 expected |

不新增“pending 返回值”协议，不给 OGS 建第二个重试/核销系统。测试必须驱动真实 gateway 的上述异常/确认分支与现有 manager 的迟到 echo/reconcile 路径；只 mock adapter 的网络结果，不能用自造 pending 字典代替真实生命周期。

### LED 与 UI 同一语义

共享 SyncStateMachine 产出的新 illegal_change 明确代表 actionable anomaly。可在 payload 增加 `actionable: true` 作为新契约标记，已有 positions/missing 坐标形状不变；此标记只能由上述比较器发出，不由页面推断。

- pump 对合法提交中单点根本收不到 illegal_change，紫灯与 UI 自然都不发生；保留现有 post-commit stale 过滤作为旧事件防线。
- 新 actionable 事件绕过 `visionRecovery.ts` 里单点 pending / platformPendingStone 的旧启发式隐藏，避免“拒绝后的真错子亮紫灯但 UI 仍不提示”。旧未标记事件保持现有兼容行为；pending chip、ambiguous、capture、board-lost 表现不另改。
- LED 仍只消费同一 actionable illegal_change 的 positions/missing，不新增独立 LED 判错器；同一指纹冷却及 synced 清除保留。布局、长文案和页面专属覆盖不在本次改动中。

## Chunk 3: 按依赖顺序实现与验证

### Task 1: 共享同步归属和源头第 5 帧回归

**Files:**
- Modify: `katrain/vision/ipc.py`（token 字段与仅结算 token 的 release 命令）
- Modify: `katrain/vision/sync.py`（单点归属和比较，不改阈值/expected 权威）
- Modify: `katrain/vision/worker_inprocess.py`、`katrain/vision/worker.py`（确认前登记，处理 release/失效，两 dispatcher 对称）
- Tests: `tests/test_vision/test_sync.py`、`tests/test_vision/test_sync_regressions.py`、`tests/test_vision/test_worker_commands.py`

- [ ] 先用现有 worker harness 的真实 MoveDetector/SyncStateMachine 组合，构造峰值 0.68、consistency=5 的单颗正常子，连续驱动 5 帧；第 5 帧同时观察 ConfirmedMove 和同步输出。测试当前应失败：确有 illegal_change；修复后不得有它，也不能伪造 synced。
- [ ] 在两个真实 dispatcher/harness 上各复现一次，不能只 mock 新共享 helper 就宣称 worker 已接入；快确认 0.80/3 帧作为控制组。
- [ ] 实现上文共享契约；增加同帧额外一子、颜色变化、已成熟缺子、capture pending、board_lost/reacquire 的聚焦断言：归属只排除自己，其他点保持原始阈值与 payload。
- [ ] 测拒绝/撤销后下一稳定帧立即报已成熟错子；持续拒绝重试不能重新买到一个隐藏窗；同点同色但不同 token 的结果不串线。
- [ ] 运行上述新增 tests，先记录 red，再实现并记录 green。只在其足够验证后提交一个 core 修复 commit，不做模型/参考图/识别参数附带改动。

### Task 2: 服务到数字提交的所有权闭环

**Files:**
- Modify: `katrain/vision/service.py`（验证原来源、固定 expected revision、token-only release、旧队列过滤）
- Modify: `katrain/web/core/physical_play_orchestrator.py:89-185`（捕获 wrapper 来源、事件循环应用前验源、统一读取/发布当前权威）
- Modify: `katrain/web/api/v1/endpoints/vision.py:188-270,456-461`（bind seed/fallback 与手动 expected 边界）
- Modify: `katrain/web/server.py:3683-3695,5012-5065,5193-5501`（中央 mirror、提交所有出口及 await 后副作用前验源；不重写平台提交策略）
- Modify: `katrain/web/core/vision_pump.py`（仅必要的身份过滤/更新失真的队列说明）
- Tests: `tests/test_vision/test_service_event_routing.py`、`tests/test_vision/test_worker_commands.py`、`tests/test_vision_move_poller.py`、`tests/test_vision_pump.py`
- Tests: `tests/test_physical_play_orchestrator.py`、`tests/test_vision_bind_state.py`（source callback/重绑）
- Tests: `tests/platforms/test_gateway.py`、`tests/platforms/test_manager_routing.py`（仅扩展真实 OGS uncertain/echo harness；生产 gateway/manager 语义不改）

- [ ] 增加确定性 asyncio Event barrier 测试：先让 worker 确认并把两个 deque 排好，再刻意让 pump 先跑、poller 后提交；不能依赖 sleep 碰巧通过。确认 LED show_attention 与视觉客户端都没有收到错误。
- [ ] 同一测试轮换“落子先提交/expected 回推晚到”和“expected 先回推/结果晚到”；最终只有单一 publisher 的实际权威快照可被 synced ACK；release 命令不得有快照字段。
- [ ] 本地自由、ranked guard、中央 bridge 用现有 fake 覆盖成功/拒绝/session缺失/terminal/presence drop/cancel 的 finally。平台另用真实 gateway：previous-action pending 必须释放本次 token；OGS uncertain异常保留 ctx/needs_resync 但释放 vision 归属，再驱动真实 manager echo 或 snapshot reconcile 收敛。不得伪造 explicit pending 返回值，不改变原 guard/恢复计数或网络重试。
- [ ] 用现有 orchestrator/service/poller harness 加 barrier：保存 A 的旧 wrapper 或让 A bridge 正在 await → 绑定 B → 释放 A；断言 B 的 expected/revision、pending、pause、recovery episode 全部不变，旧 wrapper 不能给 A 快照盖 B epoch。再在同一绑定内延迟 A-node 回调、提交 B-node 后释放旧回调，断言重新读取 B 当前权威而非把旧 snapshot 分配新 revision。
- [ ] 同一 harness 补旧 IPC/release 迟到、undo 回到相同坐标/同色、相同矩阵不同 node，以及 remote bind fetch 返回前已被新 bind/auth generation 取代；所有检查早于 rearm/recovery/实体副作用。
- [ ] 补齐 Task 1 的生命周期接线；保留 split deque 及现有提交协程，不为修此竞态重构为串行网络阻塞总线。
- [ ] 运行本任务聚焦测试，绿后提交 service/submit 连接 commit。

### Task 3: 共用恢复语义与代表性用户旅程

**Files:**
- Modify: `katrain/web/ui/src/kiosk/hooks/useVisionSync.ts`（仅需要的 additive wire typing；实施时 sparse 补入此明确文件）
- Modify: `katrain/web/ui/src/kiosk/components/vision/visionRecovery.ts`
- Tests: `katrain/web/ui/src/kiosk/components/vision/visionRecovery.test.ts`、`VisionSyncOverlay.test.tsx`
- Tests: `tests/test_vision_pump.py`、`tests/test_physical_play_orchestrator.py`（复用 attention 测试）

- [ ] 新契约 actionable 异常即使恰与前端 pending 相同也显示；未标记旧事件保持兼容。先加失败断言，再改共享 reducer，不做自由/升降级各一份逻辑。
- [ ] 回放 F3 的 pending → board_lost/reacquired → 确认/提交 → synced 事件轨迹：源头无错误事件、无对话框、无紫灯；不得只断言“页面把它隐藏了”。
- [ ] 回放真实错子/缺子：到原阈值后，同一坐标同时送客户端与 attention；用户继续下一手、节点变化和 pending 不得清掉/隐藏未解决的真实异常；真实匹配 synced 后才恢复。
- [ ] 运行 monitor 的 setup→move_confirmed→target 更新，以及 pvp_local full-board window 现有代表测试，证明未把它们改成单点自动接纳。未发现相同根因时不要为“统一”扩展新协议。
- [ ] 绿后提交 shared presentation contract commit。若实现不用新增 wire type，删除相应文件改动项而非制造无用重构。

### Task 4: 最低充分总验与交付

- [ ] 执行后端聚焦回归（使用已有项目测试环境，无需 GPU）：

```bash
CI=true uv run pytest tests/test_vision/test_sync.py tests/test_vision/test_sync_regressions.py tests/test_vision/test_worker_commands.py tests/test_vision/test_service_event_routing.py tests/test_vision/test_service_monitor.py tests/test_vision/test_gating.py tests/test_vision/test_local_confirmation_window.py tests/test_vision_move_poller.py tests/test_vision_pump.py tests/test_physical_play_orchestrator.py tests/test_local_move_confirmation.py tests/test_vision_bind_state.py tests/platforms/test_gateway.py tests/platforms/test_manager_routing.py -q
```

预期：全部通过；不运行无关棋谱导入/数据扫描，不访问禁读目录。任何既有失败只记录直接相关影响，勿扩为无关整库排障。含真实 TestClient lifespan 的测试先复核当前启动配置满足禁读边界；若不满足，改用上述既有纯 harness，不能为补证启动目录扫描。

- [ ] 在 `katrain/web/ui` 运行现有 Vitest（实施前从该文件的 package.json 确认脚本）：

```bash
npm test -- --run src/kiosk/components/vision/visionRecovery.test.ts src/kiosk/components/vision/VisionSyncOverlay.test.tsx
```

预期：新旧事件兼容、正常过渡与真实异常均通过。不为逻辑修复增加整站截图矩阵；若当前 test 脚本名称不同，使用实际 vitest 脚本并记录命令。

- [ ] 用本地 fake worker + fake submission 的真实事件链展示一段正常慢确认与一段拒绝后的错子，不发硬件命令。自动化充分后不重复造审计脚本或全量回归。
- [ ] 查看限定文件 diff / `git diff --check -- <上述明确源码/测试/计划路径>`，保留他人修改，报告验证命令及结果。不能使用全树 status 或任何禁读 pathspec。
- [ ] 交付 core/source、异步所有权、真实异常、共享旅程覆盖的摘要；另列两个 missing 现象仍待原图验证。ROOT 安排审核及集成；本计划不授权实施者自行部署、改设备、点灯或发布。

### 验收标准

1. 慢确认第 5 帧和提交队列任意合法调度下，合法新子不产生 actionable illegal_change、紫灯或对话框；源头不伪造数字盘/同步成功。
2. 归属不能跨绑定、节点/盘面代次、undo、resync、模式/几何重建存活；旧结果不能授权/撤销新落子。
3. 合法自己的子在提交中也不能遮住第二颗错子、换色或真实缺子；拒绝后的既成熟错误下一稳定帧可见，没有新增延迟窗。
4. 自由、升降级和跨平台共用修复；monitor 和 pvp_local 不被错误接管。
5. 紫灯与 UI 对同一 actionable 事件一致，继续下棋不会因前端启发式掩盖真实异常。
6. 没有把缺少原图的参考 veto / 15 秒检测消失问题“猜改”或称为已根治，没有无关重构和生产动作。

**Round 1 修订记录：** V1 增补真实 publisher/file map、来源在 wrapper/await 前捕获、实体副作用前验源，以及当前权威读取至 revision 固定/入队的同一临界区；ACK 简化为 token-only release，expected 不新增写入通道。V2 删除虚构 pending 返回值/接管，按实际 gateway 和 OGS manager 分支结算，uncertain 只取消临时视觉归属、保留既有平台 reconcile。仅修改计划，交 ROOT 安排 Round 2，不自行追加审核。
