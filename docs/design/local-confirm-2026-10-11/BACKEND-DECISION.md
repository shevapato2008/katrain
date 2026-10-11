# 本地对弈逐手确认：后端实施裁定

日期：2026-10-12。独立决策代理依据用户授权裁定；前端实际 1024×600 界面已确认。本文件只决定当前切片的最小后端实现，不引入新的通用识别框架。

## 1. 已决定的行为

- 仅 `pvp_local` 使用确认流程。屏幕预选不写棋谱；`/api/local/confirm` 才提交最后选点。
- 实体盘在一手确认窗口内运行完整现有多帧识别，稳定结果成功或失败后关闭窗口。相机设备、采集线程、模型与标定保持就绪。
- 首次实体盘绑定属于准备阶段：先有限地建立干净初始参考帧，再开始本局计时。此后等待玩家的阶段不运行回合推理或盘面对比。
- 确认期间双钟暂停；成功从新节点为下一方继续计时，失败从原节点为原方继续计时。无计时局不因确认而启钟。
- `no_stone`、`multiple_stones`、`capture_remaining`、`timeout` 等通过 `state.local_confirmation` 原地提示，不发旧“盘面不一致”或疑似落子弹窗。
- **停一手直接提交，不打开相机窗口。** 这是用户后续要求，优先于旧 README 第 8 条“短暂核对实体盘”。双停与终局界面继续走原逻辑。
- 成功普通落子沿用现有带 `after_node_id` 的音效，只响一次；预选、失败、重复回执、虚手不新增落子音效。

## 2. 代码事实与实现位置

已读 `worker_inprocess.py`、`worker.py`、`service.py`、`ipc.py`、`gating.py`、`move_detector.py`、`reference_frame.py` 的调用关系，以及 `server.py` 的两条 vision 消费链、`PhysicalPlayOrchestrator`、`WebSession` 与 `WebKaTrain` 的计时/提交实现。

关键事实：

1. `InProcessAdapter` 拥有当前完整链路：运动过滤、几何变换、AE、帧平均、增强、检测、阴影框过滤、阈值迟滞与 sustain、逐格投票、用户否认、参考帧否决、置信峰、多帧 MoveDetector、疑似子后处理。不可另写单帧识别路径。
2. `PAUSE_DETECTION` 只挡落子和 sync，仍运行模型推理；`needs_frames()` 在 bound 时恒真。二者目前都不能表达“本地局等待确认时停止推理”。
3. `BIND`、`UNBIND`、`RESET_SYNC` 会使参考帧失效。不能把它们当每手开关。
4. 当前 `worker.py` 子进程实现没有 `reference_check`。板端因注入 `CameraHub` 实际使用 `InProcessAdapter`，不能只凭配置中的 `process_mode` 判断能力。
5. `MoveDetector` 故意忽略提子，并可在多个新增点中确认领先候选；一个 `ConfirmedMove` 本身不证明“整盘只有一手且提净”。
6. `PhysicalPlayOrchestrator` 会根据盘面 lag 暂停识别；若照搬到逐手确认，未入谱的新子会反过来阻塞本次确认。
7. `WebKaTrain._do_play` 吞掉 `IllegalMoveException` 并记录日志。无异常或 HTTP 200 不代表实际入谱，必须核对提交后的节点。

最小归属：

- 新增 `katrain/web/core/local_confirmation.py`，一个会话内 controller，负责输入模式、单个活动请求、幂等结果、窗口期限、计时暂停、整盘规则核对与结果投影。挂在现有 `WebSession`；不建数据库表，不创建另一套游戏对象权威。
- `WebKaTrain.get_state()` 输出 controller 的小型状态投影，确保 HTTP、刷新与现有 WS `game_update` 一致。`WebKaTrain` 仅增加本地确认的有效暂停标志与必要状态入口。
- `server.py` 提供轻量 endpoint、将窗口观测交给 controller，并复用现有终局收尾。规则仍由现有 game validator 和真实 `katrain('play', ...)` 决定。
- vision 的改动限于 IPC/service 的专用窗口接口及 `InProcessAdapter` 上的 gate、观测戳、窗口缓存；普通自由对弈沿用原入口。

## 3. Worker / Service 契约

名字可按现有命名约定调整，但职责不可混用：

| 操作 | 语义 |
| --- | --- |
| `set_local_confirmation_mode(enabled, binding_id)` | 选择本地逐手模式；绑定代际必须区分换局，同局重连幂等。关闭时清理窗口，不能意外恢复旧窗口。 |
| 初次 `bootstrap(expected_board, node_id)` | 只在实体绑定准备阶段，最多 8 秒，沿用完整管线获取干净参考；禁止落子/sync业务事件。成功立即停止，失败明确 unavailable。 |
| `open_local_window(token, expected_board, expected_node_id, expected_color, deadline_monotonic)` | 原子建立本手基线与新帧下界，只能有一个窗口。 |
| `cancel_local_window(token)` | 关闭匹配窗口，幂等；晚到的旧 cancel 不可关闭新窗口。 |
| `complete_local_window(token, accepted_board, expected_node_id)` | 关闭匹配窗口、同步成功后的权威盘面，并尝试从该窗口缓存的合格帧更新参考；不再采一帧或多做一次推理。 |

观测至少携带 `binding_id`、不可复用的 `token`、`observation_seq`、`camera_seq`、`camera_ts`、**完整后处理之后的 `board`**、可选 `candidate`，以及区分 pending / ambiguous 所需的信息。`candidate` 必须已经通过现有 MoveDetector、置信峰、suspect 和 ambiguous 门限。controller 不能从一个新增格子自行制造“已确认候选”。

窗口观测是内部事件，不进入 `/ws/vision` 的旧 UI 协议。统一复用 `VisionService` 的单一 drain 分流；controller 不再直接读 worker queue，不与现有 pump 抢队列。

当前物理确认能力只给完整 `InProcessAdapter`，并要求实际生效的 `reference_check=on`；`shadow` 只记录而不否决，不能当作满足参考帧保护。配置不满足或子进程 worker 不具备此能力时返回 unavailable；不在本切片复制整套参考帧算法到 `worker.py`，更不能悄悄使用其较少的后处理。屏幕确认不依赖这项能力。保持自由对弈配置不变，RK3562 发布检查现有启动参数确为 `on`。

### 新帧与累计状态

- 本地窗口使用已有 `read_frame_identified()`，不再仅在 observer 开启时读取帧标识。只接受 `camera_ts > opened_at` 且严格递增的 `camera_seq`。重复读取同一个相机帧不得增加稳定计数。
- open 在 worker 处理命令的边界清除帧平均、运动累计、投票历史、候选/置信峰、旧 ambiguous cooldown、promoter 和窗口稳定计数；MoveDetector `force_sync` 到**权威落子前盘面**。
- **保留参考帧、仍有效的用户否认样本、格点 suspicion、模型、曝光与几何。** 不调用会清参考帧的通用 reset/bind。open 不能采用“权威盘面 ∪ 旧物理盘面”作基线，否则会吞掉待确认子。
- idle 的 gate 位于昂贵图像推理之前。相机采集线程继续保有设备并清缓冲；不得每手开关相机或加载模型。预览消费者也不能暗中重开本地回合识别。
- worker 自身检查有限 deadline；controller 同样拥有期限及 finally 清理，避免 HTTP 断连或消费者异常永久停钟。命令在帧边界停止；已在途的帧不得越过 token 与节点检查提交。

### 初始与每手参考帧

- 初次 bootstrap 必须早于起钟与可确认状态；如已有同一绑定/有效几何的干净参考，可直接 ready。原 `_maybe_capture_reference` 的全部守卫仍有效，尤其 raw-voted 和 raw-observed 都必须等于权威初始盘面，不能用 reference 修正后的盘面自证。
- 最长 8 秒仍没有合格参考时关闭准备推理、报告 unavailable，不假称 ready；重新准备可以重试，不无限自动重试。玩家在准备完成前放上新子应整理盘面后重试，不能把它标成空盘拍进参考。
- 同局重复绑定不得销毁参考、重开 bootstrap 或重置计时。新局/新几何真正改变时才遵守原失效规则。
- 每次完整管线仍照常执行 `_reference_check` 和原捕获守卫。窗口结束前缓存本手最后合格观测的灰度图、pre-reference raw-voted / raw-observed、几何及亮灯/veto状态，仅在内存存一份。
- 服务端成功提交后，complete 必须核对 token 和几何没有改变，设置真实已提交盘面，再以缓存帧运行**同一参考捕获守卫**。两份 raw 盘面不等于新权威盘面、有亮灯、reference veto 或其它原守卫不满足时，保留旧参考；禁止为更新参考而放宽守卫。
- 失败/cancel 保留上一份参考；不持续推理来“等待盘面修好”。下一次点击重新开窗。

## 4. 一手判定与旧视觉路径隔离

controller 先把本次权威盘面记作 `before`。在锁内对当前 game 作只读副本：浅复制 game，再复制 `board/chains/prisoners/last_capture`，显式核坐标边界，调用现有 `_validate_move_and_update_chains(move, ignore_ko=False)`，从副本生成 `after`。不在真实 game 上临时 play/undo，不触碰真实树、分析、时钟或音效。

判定顺序：

1. token、会话、game 对象/id、node 对象/id、轮到颜色、未终局、binding/input 与请求上下文都匹配，才读取本观测；过期事件直接丢弃。
2. 成功必须是正常门限给出的本方 `candidate`，完整后处理盘面恰好等于合法预演的 `after`；整盘稳定性不能只用一个候选坐标代替。原有逐格投票与多帧候选确认均保留。
3. 明确错误使用连续 `move_confirm_frames` 个不同相机帧的同一稳定盘面；不凭一张动手/闪烁帧立即失败。两个或更多新增点为 `multiple_stones`；完全等于 `before` 且没有 pending/ambiguous 证据为 `no_stone`。
4. 只有一个合法本方新增点、差异仅为这手应提掉但还留在盘上的旧子时，为 `capture_remaining`，points 指向这些残留子。其它错色、无关缺子或非法变化为 `illegal_move`，不接受“允许任意移走子”的近似比较。
5. 遮挡、弱子或不稳定读数等没有形成可信结果，至本窗口 8 秒 deadline 为 `timeout`；相机/标定/worker不可用为 `unavailable`。ambiguous 保留原算法的拒绝自动落子含义，不能因为用户按过确认就跳过置信门限。

成功或错误都只产生一次终态并关闭窗口，整理后的重试需要新的 `request_id`。旧普通 `ConfirmedMove` 对已启用确认的 `pvp_local` 必须被 poller 拒绝；绝不再进 `_handle_confirmed_move` 自动提交。

`_vision_event_pump` 在普通 fan-out / `route_vision_attention` **之前**处理/过滤本地窗口事件。旧队列中的 `illegal_change`、`capture_pending`、`ambiguous_stone`、`move_pending` 等不能绕到旧弹窗或 LED attention。相机/标定真实故障仍用现有恢复能力，但不能把本次普通可重试结果转译成“盘面不一致”。

本地确认期间，`PhysicalPlayOrchestrator` 保留权威 expected-board 推送与绑定生命周期；停止对未入谱盘面运行自由对弈的 lag/recovery 规划，不让 lag pause 卡住窗口。清掉上一模式残余灯与 attention；不另建 LED 状态机。其它 game_type 的行为保持原有分支。

## 5. 提交、计时与幂等

- `/api/local/confirm` 复用会话访问权限；只接受本地对局及已 ready 的 input。严格核 `session/game/node/color` 和 action/coords 组合。
- 同会话使用既有锁序 `session.lock → katrain.ai_ladder_commit_lock`。开始与最终提交均在这些锁内重读 live game，不能以 `last_state` 广播帧作权威；等待识别时不持 threading lock。
- 活动请求保存原 game/node 对象引用及 id，防止换局、导航或对象替换后错误提交。成功 CAS 检查与 `katrain('play', ..., guard=True, expected_player=color)` 必须在同一提交锁范围内完成。核对新节点确已产生才记 accepted。
- 暂停前 `update_timer()` 结算至点击受理时刻，并先检查真实 `clock_exhausted()`；已经超时者沿用现有超时终局，不能靠确认先暂停而躲过判负。
- 使用独立的本地确认有效暂停标志，计时器与 `state.timer.paused` 都读“原 timer_paused OR 确认暂停”。不要把原来关闭计时或手动暂停的状态改丢。
- 结束时在锁内清除**本活动请求**的暂停、重置 `last_timer_update`，避免把暂停时段补记给任意一方。成功节点切换后下一方开始；失败未切节点则本方继续。旧 finally 不能清掉新请求的暂停。
- HTTP 等待与服务器任务分离；客户端断连/刷新不取消已经受理的服务器确认，也不延长期限。任务必须有限完成，异常 finally 关闭窗口并恢复计时。
- 同一 `request_id` 同一请求体：进行中加入同一个结果，已完成返回缓存 accepted/失败结果；不同请求体复用 id 返回冲突；另一个 id 在活动窗口中返回 busy/conflict，不开第二窗。
- 幂等命中先于旧 node 拒绝，才能处理“已提交但响应丢失”的重试。返回**当前权威 state**，不把旧缓存画面覆盖新节点。缓存只需会话内有界存储（例如每局最近 128 个请求），不新增持久化。
- 本地确认启用后，旧 `/api/move` 不能绕过新入口；识别中旧落子/停手/认输/数子/导航/改局/手动暂停等冲突动作在后端也要锁住。正常退出/unbind/会话删除则明确取消窗口。最终节点检查仍是最后一道防线。
- 复用现有 `_finish_ended_game`；双停不另写计分/终局状态。成功 `_do_play` 现有 sound 即足够，controller 不再播第二次。

## 6. 屏幕准备的必要小补充

当前有 vision 的盒子即使选择 screenFallback，WS 也不启动棋钟，直到第一手提交才由 `update_timer` 兜底。因此只实现 confirm 会让第一手预选思考时间不计入。

裁定增加一个幂等本地 ready 动作（例如 `POST /api/local/ready`，携带 session、expected_game_id、input=screen），由真实屏幕棋盘挂载后调用；核会话/对局后 `start_clock()`，并记录 controller 当前 input。实体盘 ready 复用现有 bind，但等 bootstrap 合格后才起钟。活动窗口中拒绝切模式。此补充不新增页面或数据库。

## 7. 必须验证的风险，限定本切片

1. 多次屏幕改选只在确认时入一手；非法点、busy、重复 request 与响应丢失重试不多入谱、不多响。虚手在两个 input 下均不调用相机窗口。
2. 物理闲置无推理；开窗只用点击后的不同新帧；完整参考否决真实运行。bootstrap 与成功 capture 不用修正后盘面自证；失败/重试/同局重绑不丢参考。
3. 一手普通合法落子、合法提子且拿净、多子、无子、残留提子、无关缺子、错色、劫/自杀，以及遮挡/相机故障的有限失败。使用真实 game validator 的小棋局即可。
4. 两个并发确认、相同请求重入、旧窗口晚到事件、旧取消晚到、新局/节点变化，以及 disconnect/cancel/exception 后暂停释放。验证确认前已超时不能逃逸。
5. 暂停期间双方都不扣时；成功下一方、失败原方；无计时/原暂停不误启动；屏幕 fallback 首手思考计时；准备未完成不计时。
6. 本地错误不出现旧 mismatch/ambiguous 弹窗，正常 free 路径仍可连续识别；终局沿用既有界面。
7. RK3562 实测一次 bootstrap、一手成功、一手失败与空闲推理停止，记录实际延时。8 秒是有限资源上限，不是正常落子延时承诺；没有设备证据不声称设备验收通过。

无需为了这次改动扩展成全模式识别重构、全面模糊测试或新证据基础设施。上述边界是本次实际并发、计时及棋谱完整性风险。

## 8. 阻塞与授权结论

无须再次询问用户前端或产品确认。可以按本裁定直接实现。

实施/设备验收必须解决的硬边界是：初始参考 readiness、确认窗口 fresh-frame/token、合法完整提子盘面、计时 finally、旧视觉路由隔离。缺少完整 InProcessAdapter 能力、有效标定或合格参考时，物理确认应诚实 unavailable；屏幕确认可独立工作。代码中未发现需要先完成其它大规模架构改造的依赖。
