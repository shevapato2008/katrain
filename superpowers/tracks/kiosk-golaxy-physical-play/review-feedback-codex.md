# Codex 对抗性评审：kiosk-golaxy-physical-play

评审对象：`prd.md`、`plan.md`（2026-07-11 草案）。本评审按当前 worktree 实际代码核对，重点检查棋谱一致性、异步时序、physical-play/tsumego 共用视觉服务及测试策略。

结论：方向可行，但当前计划不能直接实施。至少 B1–B5 必须先改设计；否则会出现远端 `ctx.moves`、本地棋局树和物理盘三者分叉，且部分“恢复”路径会把错误状态静默固化。

## Blocking

### B1. `submit_engine_move` 成功后、本地两手落子不是事务；计划把“提交前重建”误当成完整一致性修复

证据：`gateway.py::_play_engine_move` 先等待 `adapter.submit_engine_move`；adapter 在合法 AI 返回后已经把 `ctx.moves = proposed_moves + [ai]` 永久提交。随后 gateway 才依次 `_local_play(human)`、`_local_play(ai)`。这两个本地操作没有锁住整个两手事务，也没有回滚；`finally` 只清 pending。任一 `_local_play` 因非法点、当前节点变化、会话删除或内部异常失败，远端 context 已前进而本地树只前进 0 或 1 手。poller 捕获所有异常后又会 re-arm，导致同一物理子再次发起新一轮 genmove。

Plan Task 4 只在下一次提交前重建 `ctx.moves`，不能修复当前请求“AI 已算出但本地只落人类手”的半提交，也没有决定该 AI 结果应保留、丢弃还是重算。后者会重复消耗隧道/道具并可能得到不同 AI 手。

要求：先定义并实现明确的提交协议。至少在网络调用前锁定并校验 session 当前节点/轮次/落点，保存 position token；返回后在同一 session 锁内再次核对 token，再原子应用 `[human, AI]`，或提供确定的补偿/终止路径。必须测试“人类本地落子失败”“AI 本地落子失败”“等待期间 undo/redo/nav/session removal”四类 interleaving，而不只是 adapter 抛错。

### B2. “每次提交前从主线重建”没有并发屏障，180 秒等待期间 undo/redo/nav 会造成旧响应覆盖新棋局

证据：`ctx.is_pending` 只阻止 gateway 的另一平台命令；`/api/undo`、`/api/redo` 直接持 `session.lock` 修改当前节点，完全不检查 platform pending。`submit_engine_move` 对 `proposed_moves` 做快照后可等待最长约 180 秒；期间用户悔棋或导航，旧请求返回后 gateway 仍无条件把旧 human/AI 两手落到“新的当前节点”。

Plan Task 4 的 rebuild 发生在 pending 设置之前一次，无法防止等待窗口内变化；Task 9 只测第二个视觉 ConfirmedMove，没有测 undo/redo/nav 与 in-flight genmove 的竞争。

要求：engine pending 时禁止 undo/redo/nav，或给棋局树版本号并在响应提交前 CAS；失败时不得应用旧响应。前端按钮禁用不能替代后端约束。增加真实 asyncio barrier 测试，控制 genmove 在 undo/redo 前后返回。

### B3. `rebuild_engine_moves(game_id, moves_coords)` 会丢失让子 setup，当前 Task 4 接口与假设不成立

证据：让子在本地由 `edit_game` 调 `root.place_handicap_stones`，属于根节点 AB/setup，没有 move node；adapter 开局则用 `_handicap_stones` 把同一批黑子预先写进 `ctx.moves`。现有 `rebuild_engine_moves` 只是把传入 `(col,row)` 全量转换后覆盖 `ctx.moves`，不会自行恢复 handicap 前缀。Plan 已意识到风险，但仍把实现步骤写成“从主线提取 coords，调现有 helper”，这条路径必然删除前缀。

另外，主线提取若过滤 `move.coords is None`，pass 也会丢失；若传 `None`，现 helper 类型和转换均不支持。即使本期 UI 禁止 engine pass，SGF 导航/历史树仍不能靠未声明假设保证没有 pass。

要求：把重建 API 改为从 engine config 恢复 handicap 前缀并显式编码 pass，或让 manager 构造“完整 tunnel history”而非普通坐标列表。测试必须断言具体传给下一次 genmove 的完整整数序列，而非只断言 helper 被调用；覆盖 handicap 2/4/9、当前节点在分支上、pass、根节点。

### B4. “拿回棋子 → `resync()`”端点没有验证棋子已拿回，会把仍在盘上的失败手静默吞入视觉基线

证据：`PhysicalPlayOrchestrator.resync()` 调 `vision.reset_sync(expected=digital)`；现有注释明确说明 detector baseline 使用 digital∪physical union，使仍在物理盘上的 leftover 不会重新注入。也就是说用户未拿子或拿错子时，Task 5 的 cancel 仍会恢复 detection，并把那颗额外子变成 inert baseline；之后数字盘与物理盘长期不一致，且不会再次形成该手。

这与 PRD §3.2“视觉确认盘面回到数字盘状态后恢复”不一致。计划中的端点实际上没有等待或确认步骤。

要求：cancel 必须进入 `awaiting_removal` 状态，保持 move detection 暂停，依据连续稳定帧确认目标格为空且整盘与 digital 相符后才 resync/恢复；超时继续显示引导。测试覆盖未拿、拿错、遮挡/unknown、拿回后又放回、session 换绑。

### B5. 失败自动重发不能被称为安全幂等；“API 调用次数有界”也未被当前计数模型保证

证据：超时/断网异常不能证明服务端未处理请求。星阵隧道虽以完整 moves 入参无服务端对局状态，但 genmove/道具扣费、随机性和响应结果并不因此幂等。第一次请求可能已经成功并扣费，仅响应丢失；poller re-arm 后再次调用会重复扣费并可能返回另一手。adapter 内部本身还会做 AuthExpired/Retryable 重试，因此“poller 尝试 3 次”不等于底层 HTTP 调用至多 3 次。

Plan Task 5 仅按被再次确认的 `engine_error` 次数计数；每次失败到 re-arm 之间也没有先原子设置错误状态，重复/排队的 ConfirmedMove 可能增加调用数。

要求：PRD 删除“重发安全”和精确调用次数承诺，区分“明确拒绝（可重试）”与“结果未知（不可自动重试）”。若 API 无 idempotency key/status query，未知结果应立即人工兜底或终止本局，不能静默自动重算。测试需在 HTTP 边界模拟“服务端处理成功、客户端超时”。

## Major

### M1. poller 的视觉事件不携带 session id，unbind/rebind 后存在跨局注入

`ConfirmedMove` 被 destructive queue 缓存，但 `_vision_move_poller` 消费时才读取当前 `vision.bound_session_id`。旧局确认事件若在 unbind/rebind 之间留在队列，可被注入新局。新增的 `vision_engine_failures[session_id]` 不能解决事件归属问题；反而 retry endpoint 还会保存旧坐标。

要求：入队时封装 `{session_id/generation, move}`，消费时核对 binding generation；unbind、bind 和 session end 清空/作废旧 generation。加入旧局 move 跨 bind 的测试。

### M2. 建议的 error/hint 暂停状态会与现有 `_suspended` 单布尔互相解除

现有 `show_hint()` 设置 `_suspended=True`、`_hint_active=True`；`dismiss_hint()` 的 `_end_hint()` 无条件把 `_suspended=False`。`_sync_pause_state()` 当前只聚合 `_hint_active or not _caught_up`。如果 Task 5 另加 `_engine_error_active` 但仍复用 `_suspended`，error 中 show/dismiss hint 会让 tick 恢复；hint 中进入/清 error 也可能错误 resume。`on_unbind()` 先 dismiss hint，再清 session，亦需要清所有 reason。

要求：不要继续扩展共享布尔。改成明确的 pause reasons 集合/独立 flags，并让 tick suspension 与 worker detection pause 都由同一聚合函数计算。覆盖 hint+lag+engine_error 的所有进入/退出顺序及 unbind。

### M3. `pending` 被计划写成“re-arm 后可重试”，但现代码的 pending 分支实际上难以由单线程 poller触发，测试模型与生产时序不一致

poller 在 `await gateway.play_move(...)` 时阻塞，不能同时消费第二个 ConfirmedMove；worker detection 又在确认时推进 baseline。第二手事件可能排队，等第一请求返回后才消费，此时 pending 已清除，随后会按新的 `player_to_move` 被判 out-of-turn 或甚至成为合法下一手，而不是 gateway `reason==pending`。纯 mock 直接令 gateway 抛 pending 无法固化真实行为。

要求：Task 9 使用真实 poller+queue+可控 future，明确决定等待期第二颗物理子应被丢弃、保留到下一人类回合还是触发 mismatch；测试事件顺序和最终 detector baseline，不只测 failure counter。

### M4. terminal/game-ended 路径计划“不计数”但没有收尾，会持续 re-arm 或留下物理失败手

当前 poller捕获所有 gateway 异常并 re-arm。给异常加 `reason` 后，Task 5 只说 `game_ended` 不计数，没有说明是否 continue/re-arm、清灯、unbind、清 failure。`GolaxyEngineTerminal` 已通过 callback 触发 manager 清 context；若仍 re-arm，下一次同一石子可能走已不存在/已结束 context 的路径。

要求：为每个 reason 定义状态转移表：pending、明确拒绝、未知结果、game_ended、session missing。terminal 必须停止检测/结束绑定或进入终局物理清理，不得只“不计数”。

### M5. retry/cancel 新端点缺少 session ownership、当前绑定和局版本校验

现有 analysis endpoint 已有“认证但不校验 session ownership”的弱点；新 retry 是有副作用操作，不能照搬。仅提交 `{session_id}` 会允许登录用户重试其他 session；旧对话框也可能在新局/重绑后重放保存坐标。

要求：校验当前用户拥有该 session、vision 当前绑定同一 session、engine context/game id 与失败记录一致、棋局版本未变化；失败记录含 opaque recovery token，端点以 token CAS 消费。测试跨用户、旧 token、换局、双击并发 retry/cancel。

### M6. `player_subtype="platform:engine"` 会污染通用游戏语义和 SGF 元数据，且 Task 1 的调用方式可能覆盖字段

`player_subtype` 在 core 中代表 human game mode / AI strategy，并参与 player 字符串/SGF 信息；它不是纯展示标签。虽然 human 的 `strategy` 会忽略 subtype，但把平台身份塞入该字段仍扩大了跨层耦合。Task 1 还建议再次 `update_player(... player_type=<现值>, name=...)`，容易把 `edit_game`/后续 reset 的 player 信息覆盖；其持久性也没有测试（edit_game、load SGF、swap players 后是否仍在）。

要求：优先在 web state 增加明确的 `platform_engine_color`/`player_role`，来源应是 `PlatformGameContext.my_color`，而不是篡改 KaTrain core Player。若坚持 subtype，至少测试 edit_game 前后、undo/redo、SGF save/load、swap/reset，并确认不进入 SGF rank/comment。

### M7. 支招结果与棋局位置没有绑定，慢响应可在落子后点亮旧候选

`engine_analysis` 使用 adapter 当前 `ctx.moves` 发请求，返回后 endpoint 才调用 `show_hint`。期间游戏可能完成一手、undo、结束或解绑/重绑；仅检查“此刻 bound_session_id 相同”不足以证明候选属于当前 position。`show_hint` 还会暂停检测，导致陈旧结果主动阻塞新局面。

要求：请求前记录 position token（当前 node id/move history hash），返回后再次核对 session、game id、token 和 `kind`；不一致则丢弃且不点灯。测试 analysis future 等待期间 move/undo/unbind/rebind/end。

### M8. `show_hint` 的坐标金标准在 plan 中写错，容易掩盖上下翻转错误

计划写“KaTrain `(col=3,row=3)` D16 → vision `(15,3)`”。在本项目约定中 KaTrain/GTP row 0 自底向上，`(3,3)` 的确是 D4，对应 vision row 15；D16 应是 KaTrain `(3,15)`，对应 vision `(3,3)`。公式是对的，文字金标准是错的。

要求：修正文案并用 D4/D16 两个非对称用例，避免测试名称和数值互相矛盾。

### M9. physical-play 与 tsumego 共用 VisionService，计划未测试模式切换和残留 pause/setup/monitor 状态

tsumego 通过 `/vision/setup-mode`、`/vision/monitor`、`/vision/pause` 控制同一 worker；physical play 通过 bind、pause_detection/resume_detection 控制。现注释已明确 `/vision/pause` 是“single-owner aggregate boolean，禁止独立 caller”。计划新增 error pause/hint，但测试只在 orchestrator fake 上验证，没有覆盖从 tsumego 页面退出后进入 engine 局、engine error/hint 后进入 tsumego、浏览器异常卸载等模式切换。

要求：增加真实 VisionService command 序列测试，明确 bind 是否强制退出 monitor/setup/paused，unbind 是否恢复安全 idle；不要让 engine recovery endpoint调用 tsumego 的通用 pause owner。

## Minor

### m1. 代码位置和命名有多处过时/含糊

- `adapter.py` 实际路径是 `katrain/web/platforms/golaxy/adapter.py`，不是泛指的 `adapter.py`。
- `_vision_move_poller` 的关键行号会漂移，评审/计划应引用符号而非 `server.py:1999-2009`。
- `PhysicalPlayConfig` 在 `katrain/web/core/physical_play.py`，但 retry 计数是 transport/recovery policy；塞进 LED planner config 会混合职责。
- “测试必须走真实 create_multiplayer_session 输出”与前端 TS 单测无法直接调用 Python session 的说法矛盾；应生成后端契约 fixture 或后端序列化 contract test。

### m2. “连续失败”清零条件定义不足

成功、cancel、unbind、game end、换 game id 应清零；pending/out-of-turn 是否打断连续序列未定义。坐标变化时必须新建 episode，不能把 A 点两次失败和 B 点一次失败合并到阈值。

### m3. 前端 “hintDismiss 恰好一次”是脆弱断言

端点语义应幂等，React StrictMode/unmount/effect 竞态可能合理地产生重复 dismiss。更重要的是使用 position token 保证旧 dismiss 不会关闭新 hint。测试应断言最终状态和 token 归属，不宜以全生命周期网络次数恰好一次作为核心正确性。

### m4. 测试计划缺少坐标/规则边界

应补 0/18 四角、提子后立即落回、打劫非法手、自杀规则差异、满盘/终局、摄像头 unknown/遮挡、AI 返回人类落点/越界点、session 删除和 LED/vision 方法抛错。当前主要 happy path 不足以证明物理棋谱不会错乱。

## Question

### Q1. 星阵 genmove 是否有请求幂等键、请求查询或计费语义？

这是决定 B5 恢复策略的前置事实。若没有官方保证，“自动重试 2–3 次”应从 PRD 移除。

### Q2. engine 局是否真的允许用户在 pending 时悔棋/导航？

PRD 明确允许悔棋，却未说明 pending 窗口。建议拍板为 pending 时禁止；若要允许，必须实现版本化丢弃旧响应。

### Q3. engine 终局如何处理 AI pass/resign？

当前 adapter 把任何 non-move coord 作为 terminal 且不把最后 human move提交进 `ctx.moves`，gateway 也不会把这手人类棋落到本地树。若 AI 对人类这手回应 pass/resign，本地棋谱会遗漏实际最后一手。这是现存逻辑问题，物理接入会放大，需决定 terminal response 是否仍提交 human move并记录 pass/result。

### Q4. “人执白 + 让子”是否是允许配置？

adapter 规则是 handicap≥2 后白走，AI 颜色由 human_color 反推；若人执白，黑方 AI 的让子已作为 setup 摆好，但 side-to-move 是人类白，因此不会有 AI opening。PRD 的“让子局 AI(W) 首手”只适用于人执黑。UI 是否禁止不合常规的组合，测试矩阵需明确。

### Q5. 物理失败恢复是否接受“放弃本局并重新开局”作为未知结果兜底？

若星阵 API 无幂等/查询能力，这是唯一能严格避免远端结果不确定继续污染棋谱的方案之一，应在 UX 决策中明确。

## 建议的计划调整顺序

1. 先解决 B1/B2/B3：定义 position token、pending 期间允许操作、完整 tunnel history（含 handicap/pass）和本地提交协议。
2. 再解决 B5：按星阵 API 的真实幂等/计费能力重写失败状态机。
3. 将 recovery 设计成带 token 的状态机：`submitting → unknown/failed → awaiting_removal/retrying → resolved`；B4/M1/M4/M5 一并纳入。
4. 把 orchestrator pause 改为 reason 聚合，并补 physical↔tsumego 模式切换测试。
5. 最后接 player role 与 options LED；两者都必须携带/校验 position token。

在上述调整完成前，不建议开始现有 Task 1–11 的逐任务实现。
