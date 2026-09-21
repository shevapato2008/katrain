# 棋子识别稳定性 — 设计说明（2026-09-20）

配套计划：`docs/superpowers/plans/2026-09-20-vision-recognition-stability.md`
证据来源：`docs/2026-09-20-kiosk-device-session.md`（同日 RK3562 上板实测）

---

## 1. 设备实测的五种失效

2026-09-20 在 RK3562（hostname `gzpeite`）上，一局与星阵（Golaxy）的跨平台对弈，
17:13:17 → 17:21:47 共 510 秒窗口内，服务端产生 93 条 `illegal_change` 事件。
（注意：**93 是服务端事件数，不是用户看到的弹窗数** —— 客户端
`visionRecovery.ts:131-137` 已有 4 秒去重窗口，把同一批事件重放进已部署的 reducer
只开 ~4 次弹窗。任何以「93 次弹窗」为前提的收益估算都是错的。）

| 代号 | 失效 | 实测证据 |
|---|---|---|
| F1 | **幻影注入** | O1 = vision `(18,13)`，以 0.57 置信被确认，并在确认后 3.02 秒自动提交给星阵。该点当日在 3 个进程内闪烁 69 次、累计点亮 405 秒；10:43:19 另一局也曾以 0.50 被确认过一次。**它是一个固定假阳性点。** |
| F2 | **真子被饿死** | L17 = vision `(2,10)`：全天日志中 `move confirmed: (2,10)` **0 次**，coord 314 不在该局 60 手之内 —— 用户摆了半小时的那颗白子从未进入对局。R18 = vision `(1,16)` 卡 71 秒，最终由用户在弹窗上按「采纳为我的落子」才进入（日志无 `Vision move submitted`，仅星阵侧收到 coord 339）。 |
| F3 | **已落子点颜色翻转** | 局内 65 次。Q2 = vision `(17,15)` 一个点翻转 41 次、横跨 27 分钟，其中 8 条 `illegal_change ... (17, 15, 1)`（观测为黑）推送到了客户端。数字盘面上 Q2 恒为 `W`。 |
| F4 | **看不见的真子** | 93 条事件里 37 条（40%）带 `missing`，其中 Q2 ×35、R2 ×2。 |
| F5 | **事件风暴** | 24 个指纹、2.38 秒中位重复间隔；三个点（L17 ×54、R18 ×24、Q2 ×43）贡献 79/93。 |

设备当前参数（`ps` 实读）：
`--vision-confidence 0.40 --vision-confidence-keep 0.30 --vision-ambiguous-confidence 0.42`，
代码默认 `move_confirm_frames=5`、`move_confirm_fast_frames=3`、
`move_confirm_fast_confidence=0.70`、`move_miss_grace=2`、
`illegal_change_frames=5`、`board_lost_threshold=10`。

**O1 的 0.57 同时越过 0.40（add）和 0.42（ambiguous）两道闸，所以它是自动提交的，
不是用户确认的。** 把全盘门槛调高能挡住它，但会把 L17/R18 那类弱真子一并变成弹窗 ——
这正是 F2 的痛点。因此门槛必须**按点自适应**，不能全盘统一。

---

## 2. 三个结构性成因

### C1 — 整盘 diff 是「这一手算不算数」的唯一判据

`katrain/vision/move_detector.py:79` 构建全盘 diff，`:91-95` 在 `len(diff_positions) > 1`
时硬重置（清空 count / pending / misses）。

后果：**观测盘面上任何一点的错误都会污染全盘判据。** 三个出口当日全部命中 ——
注入（F1，幻影单独出现时自己确认）、饿死（F2，幻影与真子共存时真子被重置）、
噪声（F3，已落子点翻色也算一处 diff）。

F2 的主因是 F1：一个**持续点亮**的空点幻影使每一帧都 ≥2 处 diff，于是没有任何手
能凑满 `consistency_frames`。F3 的翻色约每 25 秒一次，不足以持续饿死，是次要来源。

### C2 — 不可撤回提交前不复核

worker 确认 → `ConfirmedMove` 入队 → `_vision_move_poller` 每 0.1 秒轮询 →
`server.py:3612 _handle_confirmed_move` 做鉴权/轮次检查 → 落子 / 发往星阵。

实测 确认→提交 中位 0.45 秒，O1 那次 3.02 秒；**而那颗幻影在提交前 1.46 秒
就已经从观测盘面消失（`~none`）**。这段时间内没有任何一处再看一眼棋盘。

附带缺口：`katrain/vision/service.py:212-214` 的 `get_detected_board()`
**不调用 `refresh_status()`**，读的是缓存副本。

### C3 — 颜色只锚在观测，不锚在"这个点已经有子"这个事实

`board_state.py:87-95 _passes_hysteresis` 只在 `prev_board`（上一帧稳定观测）
同色时允许 keep 档检测维持；`:244-251` 的 presence sustain 只覆盖
`(prev != EMPTY) & (board == EMPTY)`（子不会凭空消失），
**不覆盖 `(prev != EMPTY) & (board != EMPTY) & (board != prev)`（子不会当场变色）**。

---

## 3. 手数顺序：现有保证与唯一缺口

**棋谱的手数交替是结构性保证的，不由识别决定**：

- `interface.py:1486` → `self.game.play(Move(coords, player=self.next_player_info.player))`
  —— 落进棋谱的颜色**永远取服务端的 `next_player`**，视觉读到的颜色说了不算。
- `sgf_parser.py:355-365` → `next_player` 由上一手颜色推出，结构上不可能黑黑连走。
- `interface.py:1465` → `expected_player` 不符抛 `EndgameConflict("stale_turn")`。
  **读错颜色的结果是「这一手被丢掉」，不是「落成错的颜色」。**
- `interface.py:1453` → 判别与落子在 `ai_ladder_commit_lock` 内原子完成。
- `service.py:243` → 确认队列 FIFO（`popleft`）。
- `gateway.py:169` → `ctx.is_pending` 拒绝「上一手还在飞时」再提交。

**唯一缺口**：`server.py:3612` 的轮次检查读 `session.last_state`（代码自己的注释
承认是「可能过期的广播帧」），而「真正的判别在对局提交锁里」只写在**本地对局**
那个 `else` 分支（带 `guard=True, expected_player=...`）。
**跨平台（星阵）分支过完那个过期检查就直接进网关，没有提交锁里的轮次复核。**
O1 走的正是这条路。

---

## 4. 设计决定（含已拍板项）

| 编号 | 决定 | 理由 |
|---|---|---|
| D1 | **L0 失败方向 = 只在「确证消失」时拦截**；`detected_board is None`（运动/未找到盘面/丢帧）一律放行 | 真子不会消失 ⇒ 对真子零误杀；O1 那次是确证为空。**2026-09-21 复审修正**：「零误杀」要收窄成**零丢手**。完全遮挡（手停在那颗子上方）下 `detected_board` 会在真子处合法读到 EMPTY —— `board_state.py` 的 presence sustain 只在该点附近**还有某类检测**时才保住它，全遮挡一个都没有。代价有界：L0 取消会走 `_rearm_detection()`，那颗子在后面的帧里重新确认，**丢的是时延不是这一手**。这是视觉管线的既有性质，不是 L0 引入的 |
| D1b | **L0 的「确证」必须建立在比该次确认更新的一次观测上**（`observation_seq` 打在 `WorkerStatus` 与 `ConfirmedMove` 两边） | `worker.py:827` 的状态发布是 **1 Hz**：8fps 下一颗子可能在 t=0.25 落、t=0.75 确认，而最新已发布的盘面还是 t=0.00 那张空盘 ⇒ 只看「现在空不空」会丢真手，正是 D1 承诺不会发生的事。墙钟跨进程不可靠，用 worker 自持的观测计数器 |
| D2 | **L3 落点选 Site B（观测锚定）**，不用 Site A（`_expected_np` 当分类先验） | `SET_EXPECTED_BOARD` 往返约 1.1 秒滞后；提子/悔棋窗口内拿过期权威压真实观测会制造新错 |
| D3 | **L3 保留逃生口**：连续 `COLOR_FLIP_RELEASE_FRAMES` 帧反色则放行并恢复 `sync.py:362-364（`expected != EMPTY and observed != EMPTY and expected != observed` 那条 elif；**2026-09-21 更正**：原文写 351-353，那三行今天是 `placement_pending` 分支，不是颜色分支）` 的「颜色放错了」提示 | 否则那条分支变死码，系统失去唯一一条告知摆错颜色的路 |
| D4 | **L2 只用一个信号：候选被放弃**（出现后耗尽 miss grace 仍未确认）。不做跨进程 IPC 回灌，**也不罚「同点短窗内重复确认」**。**2026-09-21 fix round 1 修正**：suspect 格的额外门槛**只加在 worker 的 ambiguous 路由闸上**（`SUSPECT_CONFIDENCE_BONUS`），**绝不加在 `detect_new_move` 的确认帧数上**——第一版曾把 suspect 格的所需帧数翻倍，判断依据「放弃是真子从不会做的事」是**假的**：`MoveDetector` 类注释自己就写着 `miss_grace` 存在的理由——弱置信度真子本来就会闪断一两帧；一颗在 keep 闸附近震荡的弱真子，只要震荡够久，产生的正是这一条唯一信号，这正是当天 F2 那批真子伤亡的实测特征。更严重的是，帧数门槛卡在 `detect_new_move` 的返回值上，而这个返回值同时是自动落子**和**确认卡的入口（stuck-stone promoter 只在**没有任何候选**pending 时才跑），于是一颗攒不满翻倍帧数的 suspect 格在任何路径上都 confirm 不了——制造出「静默永久丢手」，恰恰是这个 F1 修复本该防止、结果却亲手制造出的最坏结果。单独的路由闸已经够用：当天真子 peak_conf 实测 min=0.55、p25=0.72（117 手真局，`config_service.py`），而 (18,13) 两次自动确认分别在 0.50、0.57（且都已是 peak 值）；`0.42 + 0.25 = 0.67` 正好卡在两者中间——幻影必进卡，多数真子仍自动落子；即使一颗真子弱到 min=0.55 那一档、又恰好落在 suspect 格上，代价也只是多按一次确认，不会丢手。重复确认那条被**否决**：`MoveDetector` 类注释里的 caller-owned-baseline 契约**故意**让未被处理的确认每 `consistency_frames` 重发一次（弱真子靠它反复向用户要确认卡），罚重复会让一颗合法弱子每几帧加 3 分而衰减每 300 帧才减 1 分，分数跑飞、门槛抬高后**即使置信度回升也永久进不来**——这条论证同样适用于「不要罚放弃信号在确认帧数上」：跑飞的门槛，无论挂在哪个轴上，代价都是同一种「permanently 进不来」。**fix round 2 补充**：这个路由闸只挡 `self._bound` 分支（会提交/转发的对局路径）；monitor 模式（`if not self._bound:`）不查置信度也不查 `is_suspect`，L2 在那条路径上不提供任何防护，见 §5。<br><br>**2026-09-21 fix round 1 决策：窄幅推翻「重复确认」那条否决。**「同点短窗内重复确认」**对自动落子的确认继续否决**，对**被路由到确认卡的确认**解除：新增 `SUSPICION_CARDED = 1` 与 `MoveDetector.charge_carded_confirmation()`，两个 worker 在 `if conf < ambiguous_gate:` 分支的**第一句**（在 `AMBIG_REPROMPT_FRAMES` 抑制判断**之前**）调用它，**绝不**在自动落子的 `else` 分支调用。为什么这一窄口子不重蹈 D4 原本担心的「分数跑飞 ⇒ 即使置信度回升也永久进不来」——这是结构事实不是判断：（i）`is_suspect` 在整棵树里**只有两个非测试消费者**（`worker.py` 与 `worker_inprocess.py` 的 ambiguous 路由闸）；（ii）它在那里的唯一效果是 `ambiguous_gate = min(0.95, ambiguous_gate + SUSPECT_CONFIDENCE_BONUS)`，加成是**常数**，分数是 3 还是 3000 闸都是 0.67；（iii）那个闸的 `else` 分支就是确认卡，而卡无论如何都会发。所以「变成 suspect」**不可能丢手**，只能把一次自动落子换成一次点击；（iv）被这里罚到的格子**本来就已经在走确认卡**，这一分改不了这颗子的去向。`detect_new_move` 里已无任何 `is_suspect` 检查（fix round 1 移除并有注释禁止重新引入），本轮由 `test_a_suspect_cell_still_confirms_on_the_same_frame_count` 钉住。**D4 的「不做跨进程 IPC 回灌」这一条不约束本机制**：`worker.py` 自己就是那个子进程，它持有的 `MoveDetector` 活在同一个进程里，这是同一函数内相隔九行的一次直接方法调用——没有队列、没有 `WorkerCommand`、没有进程边界。那条否决约束的是复审提出的「从 poller 的拒绝/未采纳回灌」变体，而那个变体本身也被否了：幻影自动落子是**被采纳**的（过了轮次检查、到了星阵、成了这局的一部分），「未被采纳」对最要紧的那种情况根本不触发。实测（400 帧一局）：真子峰值落在当天实测的 0.55–0.80 带里时**没有任何格子被罚过一分**；把每颗真子的峰值都压到 0.42 闸以下，有两格越过阈值，而到达用户手里的子数**加不加这个信号完全一样**（且两边 `autoplayed = 0`）。幻影跨过 `SUSPICION_THRESHOLD` 的时间从第 68 帧提前到第 16 帧，重负载下从第 120 帧提前到第 16 帧 |
| D8 | **L1 的 `required_frames` 只授予「调用方测的那一格」**（进入方法时的 leader），其余候选一律用 `consistency_frames` | worker 每帧按 `peak_for(pending_move)` 现算，那是关于**某一颗子**的证据。leader 为 suspect 而需要更多帧时，若快通道外溢，旁边一颗 0.50 的普通候选会提前确认并越过设备 0.42 的自动落子闸 |
| D9 | **L3 的「放行」必须闩住，直到稳定盘面真的采纳新颜色** | 两个 worker 都对 extractor 输出做两帧投票（`np.where(observed == prev_observed, observed, last_stable)`），而传给 extractor 的 `prev_board` 就是那张稳定盘面。只放行一帧永远凑不满两帧一致 ⇒ 第 16 帧重新压制，颜色**永久卡死**，逃生口和 `sync.py:362-364（`expected != EMPTY and observed != EMPTY and expected != observed` 那条 elif；**2026-09-21 更正**：原文写 351-353，那三行今天是 `placement_pending` 分支，不是颜色分支）` 一起变成不可达 |
| D5 | **L4 `missing` 同时要求墙钟时长 + 最小观测帧数** | `gating.py:39` 的 `should_feed_sync_frame` 在有运动时**不喂帧**，只用墙钟会把「手遮挡 3 秒」误判成「持续缺席 7 秒」 |
| D6 | **L1 精确并列（count 与 first_seen 都相同）时不确认** | 保留现有 `test_ignores_multiple_simultaneous_new_stones` 的语义（同帧出现两颗子 = 真歧义），把改动面收到最小。<br><br>**2026-09-21 fix round 1 修正（复审 Finding 2）**：这条规则原先写在 `ready` 上，而**快通道下只有 `fast_cell` 进得了 `ready`**（`len(ready) == 1`），于是整条规则被绕过——实测 `consistency_frames=5, miss_grace=2, required_frames=3`，同帧亮起并同步推进的两颗子给出 `[None, None, (18,13,W), (2,10,W)]`：**两颗都确认了**，相隔一帧，赢家由 `_leader()` 的 `min()` 在集合迭代序里挑。现改为在**本帧正在推进的格子**（`current`）上找并列。两条已验证而非假设的性质：（i）慢通道上与原判据**等价**——16000 条随机三格出现序列零分歧（原判据只在「`ready.sort` 是同键稳定排序 ⇒ 精确并列项必然相邻」这个**未写出来的**前提下才对 3 个以上候选成立，见复审 Finding 7；新循环不再依赖排序）；（ii）**不会**因为一个 miss-grace 中的并列候选而挡住 leader——并列只在 `current` 里找，缺席本帧的候选按定义就不在「同步推进」，为它挡住 leader 等于静默丢一手真子（F2），比这条规则要防的幻影更糟。该性质由 `test_a_miss_graced_tied_candidate_does_not_block_the_leader` 钉住 |
| D7 | **L2 先于 L1 落地** | L1 让真子能在幻影旁边确认，但也让持续幻影更容易自己数满；L2 + L0 是它的前置安全网 |

### 4b. fix round 1（2026-09-21）补充：两处记录性更正与一条已知残余

**（a）`move_pending` 芯片的机制，更正——并且判定为不改。** round 0 的任务书说「卡片路由的确认之后（没有 `force_sync`），亚军成为新的 leader，于是 `pending_after != pending_before` 触发一次误导性的 `move_pending`」。**这个机制不可能发生**：`move_pending` 那一段是 `if move_result is not None:` 的 `else`，所以它在产生了确认的那一帧根本不会跑。真正的触发是**上一任 leader 在本帧被 age out 之后的 leader 换届**，芯片因此落到一个已经当了好几帧候选的格子上——实测 200 帧里 30 次芯片中有 3 次是这种（L1 之前：16 次中 0 次）。**不改**：它纯属展示层，前端本轮不可动；而显而易见的一行修法（再加 `and self._move_detector.count == 1`）会把一个**真的正在确认中**的格子的合法芯片一起压掉，拿一个误导性标记换成没有标记，不值。

**（b）两个 worker 里把 `pending_move is not None` 当 MUTE 用的两处已换成 `about_to_confirm`**（`count == consistency_frames - 1`）：`_promote_stuck_stone` 闸与 `_run_ae` 闸。L1 之后每个变化的格子都是自己的候选，`pending_move is not None` 的含义变成了「全盘任意一格有未过期候选」——两格同时亮时实测 200 帧里只开 1 帧（L1 之前 199/200），等于把亚 add 置信度真子**唯一**一条到达用户的路永久闭掉（正是当天 (2,10) 那颗真子全天 0 次 `move confirmed` 的形状），也把软件 AE 冻死（`ExposureController` 在被 mute 时连**评估**都不做，`_last_eval` 是在 `update()` 里面设的）。候选的**计数**有界而它的存在没有：候选在 `consistency_frames` 处确认并被删除，所以 `count` 是循环的，不会闩住。

**（c）已知残余，本轮明确不修：D6 精确并列死锁。** 两格在同一帧亮起、此后都不闪，则 `first_seen` 相同且计数同步增长，D6 每一帧都判精确并列 ⇒ **120 帧 0 次确认**，计数无界增长。这是**既有行为**（`2545a061` 的整盘硬重置对同一输入给出同样的零），并且只要**这一组精确并列的格子（含 leader 自己）在 `current` 里只剩一个**，死锁就在当帧解除（并列是在「本帧的 diff」里找的，见 D6）。**fix round 2 更正**：这句原先写成「两格里任意一格有一帧不出现就当帧自愈」，那只对**恰好两格**成立，而 `disruption_threshold = 4` 允许三格同时 diff。三格同帧齐步的实测：**掉一格死锁仍在**（0 次确认），**掉两格**才在当帧确认。两格时新旧两句等价，这是记录性错误，不是新的静默路径——三格那种情况本身是会被点名的（f5 的 `ILLEGAL_CHANGE` 列出三格，3 个多子远低于 `board_lost_threshold = 10`）。不修的理由：逃生口意味着在两颗互相矛盾的子里挑一颗注入，那是在本分支正在加固的那段代码里新开一条静默注入路。`test_two_lockstep_cells_deadlock_until_one_of_them_drops_out` 把当前行为钉住，避免它日后被当成回归重新发现。

**（c-2）为什么这条残余可以接受：它绝大多数情况下不是静默的，而它替换掉的东西更糟。**
「F2 比 F1 更糟」说的是**静默**丢手。死锁的两颗子留在物理盘上，对数字盘而言是 `unexpected` 多子（`sync.py` 第 356–364 行：expected 为 EMPTY、observed 非 EMPTY、且不是数字提子/悔棋待清理），`SyncStateMachine` 的 4d 段（当前第 441–471 行）会数它们：同一组异常位置连续稳定 `illegal_change_frames`（默认 5，`sync.py:79`）帧后置 `SyncState.MISMATCH_WARNING` 并发出 `ILLEGAL_CHANGE`，`data["positions"]` 里**逐格列出**这两个点；两个 worker 都把每一条 sync 事件原样投进事件队列（`worker.py:577-578` / `worker_inprocess.py:601-602`）。2 个多子远低于 `board_lost_threshold`（默认 10），也不会被 4c 的提子分支吞掉。

拿它和**item C 之前**同一份快通道输入比：D8 让只有 `fast_cell` 进得了 `ready`，所以旧 D6 不执行，其中一格按 `min()` 的集合迭代序被选中（幻影和真子精确并列时**可能是幻影**）并在快帧数上确认；快通道的定义就是峰值 ≥ 0.70，高于 suspect 闸 0.67（复审 Finding 6），所以它**自动落子**、提交到星阵——**不可撤回**。这是决定性的那一半，没有任何补救。随后自动落子分支 `force_sync(observed_board)`，基线里含**两颗**子，另一格不再是 diff、候选也被清掉，从此静默——**直到**下一次 `SET_EXPECTED_BOARD` 把基线推回数字盘（`worker.py:707-709`），那之后它重新变成 diff 并可重新累积。所以那一格是「静默延迟至少一个对局更新往返（D2 实测约 1.1 秒）」，**不是**永久丢手——这一点比初稿的说法弱，是读代码核出来的。即便如此，item C 之前那条路仍然是「一次不可撤回的、由哈希序挑出来的提交 + 一段静默」，item C 之后是「两格都不确认 + 一条点名两格的警告」。

**fix round 2 重写：要分三个轴看，不是一个轴。** 这里原先只列了三种情况，它们只变化了「这两格自己的
出现形态」这一个轴，把另外三个变量按最有利的取值默认固定住了，而且没有说出来：**(i) 这两格是不是异常指纹的唯一
贡献者**——`current_mismatch`（`sync.py:445-449`）是**整盘对象**，4d 用 `np.array_equal` 跟上一帧比，盘上任何
**另一格**进出异常集合都会把 `_mismatch_count` 打回 1；**(ii) `_compare_boards` 到底走不走得到 4d**——
`DEGRADED`（`sync.py:207-208`）、`BOARD_LOST` / 4b（`sync.py:410-416`）、`CAPTURE_PENDING` / 4c
（`sync.py:419-440`，**粘滞**）三条分支都会先返回；**(iii) 事件发出来之后，前端让不让它上屏**——见轴 C。
轴 A / B 每一条都是跑出来的，不是推出来的
（`consistency_frames=5, miss_grace=2`，默认 `illegal_change_frames=5`，数字盘为空，两格在 `(2,10)`/`(18,13)`）。

**轴 A —— 这两格自己的出现形态：**
1. 两格持续亮着 ⇒ 异常指纹稳定 ⇒ 5 帧后 `ILLEGAL_CHANGE` 点名两格（实测 f5 / f10 / f15…，状态 `mismatch_warning`）。当天实测的亮起时长约 13 帧（5.9 秒 / 2.3 fps）远大于 5，所以**实测那种剖面属于这一类**。
2. **这一组精确并列的格子（含 leader 自己）在 `current` 里只剩一个** ⇒ 并列不成立 ⇒ 另一格当帧确认，死锁解除（见 D6 与上面（c）的更正）。注意这**不是**「任意一格有一帧不出现」：三格同帧齐步时掉一格死锁仍在，要掉两格才解。
3. 两格**完全同步**地闪（同帧亮、同帧灭），且每段亮起短于 `illegal_change_frames`：候选计数靠 `miss_grace` 跨过暗帧继续累积，而 4e「无异常」分支在每个暗帧把 `_mismatch_count` 清零（`sync.py:507-508`），于是死锁继续、警告也攒不满——**这一种是静默的**（实测「亮 3 暗 2」：0 次确认、0 次 `ILLEGAL_CHANGE`、终态 `synced`）。代价有界：每段暗帧超过 `miss_grace` 都会给两格各记一分 `SUSPICION_ABANDON`（L2 正是为这种闪烁剖面建的），而它取代的是「按哈希序挑一颗提交给活人对手」。这个取舍是有意的，不是疏漏。

**轴 B —— 4d 会不会以一份稳定够 `illegal_change_frames` 帧的指纹跑到底：**
4. **指纹被别处搅动（N4）：两格持续亮着，却一次都不被点名。** 盘上**另有一格**以短于 `illegal_change_frames` 的节奏进出异常集合就够了。实测 120 帧，第三格为「亮 1 暗 1 / 亮 1 暗 2 / 亮 2 暗 2 / 亮 1 暗 4 / 亮 2 暗 3 / 亮 4 暗 1」时，`ILLEGAL_CHANGE` 全是 **0**（对照：没有第三格时 24 次）；从「亮 5 暗 1」起恢复报（20 次）。边界很利：**第三格的亮段与暗段都不到 `illegal_change_frames` 时压制成立**。第三格**不会**解开 D6 死锁——它 `first_seen` 不同，两格仍与彼此精确并列、仍占着 `ready[0]`。这一条直接推翻情况 1 的机制叙述：两格的确一直亮着，指纹却不稳定，**因为指纹是整盘对象**。不是全静默——`sync.py:471-472` 那条不发事件的 `elif` 会把状态置成 `mismatch_warning`，`/api/vision-status` 上看得到「不同步」——但**没有任何事件点名这两格**，而「`data["positions"]` 里逐格列出」正是上面那段论证倚重的那一半。准确的说法是**有笼统警告、从不点名**，是介于情况 1 和情况 3 之间的第三档。
5. **4d 根本到不了（N5）：`CAPTURE_PENDING` 是粘滞的。** 只要数字提子还没被物理拿走，4c 就一直在 4d 之前返回（`sync.py:439-440`）。实测两格死锁且持续亮着、`(9,9)` 有一颗未拿走的提子，60 帧：**0 次确认、0 次 `ILLEGAL_CHANGE`、全程 `capture_pending`**。那段时间里两颗子对对局而言不存在，而用户只被告知「请拿走被提的子」。`BOARD_LOST`（`sync.py:416`）与 `DEGRADED`（`sync.py:207-208`）同样在 4d 之前返回，且 4b 还会把 `_mismatch_board` / `_mismatch_count` 清零，之后 debounce 从头再来。提子是正常行棋，这个窗口有多长取决于用户多久才动手。

**轴 C —— 事件发出来了，用户看不看得见（fix round 2 补，只读前端核出来的，不改前端）：**
7. **警告通道被别的卡占着（前端整条丢弃）。** 上面几条讲的都是 `ILLEGAL_CHANGE` **事件**发不发得出来。
   发出来之后还有一段：`katrain/web/ui/src/kiosk/components/vision/visionRecovery.ts:140` 是
   `if (state.blocking?.kind === 'capture' || state.blocking?.kind === 'stone') return state;`——
   **已经有卡立着的时候，这条 `illegal_change` 被整条丢掉**，而**唯一**会把两格名字放进界面状态的是
   落到底的 `:157` `return { ...state, blocking: { kind: 'mismatch', positions, missing } }`。
   `ambiguous_stone` 设的正是 `kind: 'stone'`（`:119`）。所以：事件点名了两格，用户屏幕上却是**另一
   个点的另一张卡**。触发条件要有**第三格**先立起一张卡（死锁的那两格自己不发 `ambiguous_stone`——它们
   压根没 confirm；但死锁期间 `about_to_confirm` 长期为假，`_promote_stuck_stone` 每帧都在跑，一颗亚
   add 的第三格足以立卡），或者有一张提子卡。
   **对上面那段论证的修正只有一句：「`data["positions"]` 里逐格列出这两个点」说的是事件，不是用户看到
   的东西。** 「不是静默的」只在**没有别的东西在抢这条警告通道**时才成立。

**总结一句：死锁只有在「两格连续亮够 `illegal_change_frames` 帧」且「盘上没有别的东西在搅动异常指纹」且
「sync 没有停在 `CAPTURE_PENDING` / `BOARD_LOST` / `DEGRADED`」且「前端此刻没有别的卡立着」这四条同时
成立时，才会被点名告诉用户。** 其余情形要么是一条笼统的、不点名的警告，要么事件发了但屏幕上是别的东西，
要么是沉默。这不改变裁定——另一半仍然是「按哈希序挑一颗不可撤回地提交给活人对手」，本轮也不需要任何代码
改动（前端本轮不可动，这一条是只读核出来的）——但它改变 §7 该怎么读：**「日志里没有 `ILLEGAL_CHANGE`」
不是「没有发生死锁」的证据，而「屏幕上没弹点名两格的提示」连「事件没发出」都推不出来。**

---

## 5. 五层与失效的对应

**fix round 2 补充**：L2 只守 `self._bound`（绑定对局、会提交/转发的那条路径）。两个 worker 里
`if not self._bound:` 分支（monitor 模式，即物理死活棋）在 `move_result` 一非 None 就直接
`event_queue.put(move_event(...))`，完全不查置信度也不查 `is_suspect`——一个固定假阳性点在
monitor 模式下照样会自动注入。这是视觉管线的既有行为，不是这一轮改的范围：F1 指的是**跨平台
不可撤回提交**，monitor 模式不转发给任何外部平台。下表不要读成「L2 是全盘防护」。

| 失效 | L0 提交前复核 | L1 diff 局部化 | L2 点级信誉 | L3 颜色不变式 | L4 missing 解耦 |
|---|:-:|:-:|:-:|:-:|:-:|
| F1 幻影注入 | ✅ 兜底 | | ✅ 根治 | | |
| F2 真子饿死 | | ✅ 根治 | ✅ 减少源头* | ✅ 减少源头 | |
| F3 颜色翻转 | | | | ✅ 根治 | |
| F4 看不见真子 | | | | ✅ 部分 | ✅ 根治 |
| F5 事件风暴 | 间接 | 间接 | 间接 | 间接 | ✅ 砍掉 40% |

\* L2/F2：fix round 1 之前，suspect 格的帧数翻倍曾让 L2 对 F2 是**净负债**——见 D4；那笔负债已随该乘数移除而清零。**fix round 2 更正**：残余代价不是零——见 D4，一颗真子若峰值置信度落在 [0.55, 0.67) 之间又恰好在 suspect 格上，会被路由到确认卡而不是自动落子。代价是多按一次确认，不再是丢手。

**L2/F1 的残余，fix round 2 更正：它不是「首闪」那一种。** 原先这里写成「首闪」，意思是只有会话里的第一次闪烁躲得过 L2、此后声誉就会关上门。**这个说法把残余说小了。**真正的机制是：**L2 的两个信号对「峰值本来就在闸上方的格子」一个都不触发。**`charge_carded_confirmation` 不可能触发——它只在被路由到确认卡时才收费，而峰值在闸上方的格子按定义走的是自动落子那一支，从来不被发卡；`SUSPICION_ABANDON` 也不可能触发——它只罚「出现过、又耗尽 miss grace 仍未确认」的候选，而这种格子的候选是以**确认**收场的，确认之后 `force_sync` 直接把候选删掉，根本轮不到 aging loop 去数它的 miss。忠实复刻 worker 循环（自动落子 → `force_sync(observed)`；下游拒绝 → `_rearm_detection()` → `SET_EXPECTED_BOARD` 推回被污染的基线 → `force_sync(digital)`，对照 `worker_inprocess.py:655-670`）跑 400 帧、峰值 0.57、闸 0.42：

| 剖面 | 自动落子尝试 | 发卡 | 峰值 suspicion |
|---|---|---|---|
| 当天实测的 13 亮 / 13 暗，且被下游拒绝 | 6 | 26 | 40 |
| **持续亮着** | **80** | 0 | **0** |
| 短闪（亮段短于 `consistency_frames`） | 0 | 0 | 49 |

所以：当天那种**闪烁**剖面最终确实会变 suspect，但不是靠第一次闪烁之后就关门——它要靠**亮→暗边界上的放弃信号**攒够，实测约 6 次自动落子尝试（≈34 秒）之后才到，而不是 1 次；而一个**持续亮着**、峰值又在闸上方的假阳性点，**永远停在 suspicion 0**，L2 对它自始至终没有任何作用。读这一段时不要把「首闪之后就有信誉兜底」当成成立的前提。

**上面这条更正不动下面这个结论**——「至多注入一次」靠的是「被接受之后那个点就进了数字盘、不再是 diff」，跟声誉攒得快不快无关：实测：当 p(单次闪烁峰值 ≥ 0.42) = 1.0 时，注入概率加不加 `charge_carded_confirmation` 都是 1.000，`2545a061` 也是 1.000；按当天实测的 p = 0.03（69 次闪烁里 2 次自动确认）计，一次约 110 秒会话里至少注入一次的概率从 0.105 降到 0.022。唯一能关掉这条残余的机制是把 `--vision-ambiguous-confidence` 抬到 0.57 以上，而 §6 把全局门槛冻结了——抬上去会连同低闸本来要救的弱真子一起挡掉。**这条残余是 §1 末段记录的、属于 owner 的既定取舍，不是 L1 的缺陷**；§7 的板上验收就是用来观察它的。

---

## 6. 明确不做（本轮范围外）

- **P0-2 服务端弹窗指纹冷却** —— 降级。客户端已去重到 ~4 窗；先前「冷却能砍 74%」
  的估算建立在「93 次弹窗」这个错误前提上，**证据不足**。前五层落地后重新测量再定。
- **升降级结算 422**（`get_sgf()` 不调 `update_root_properties()`）—— 用户明确
  「这个我们后面修」。且已知一行修复不够：补上之后错误会移到 `player_white`
  （`player_name()` 产出 `AI (ai:ladder)` 而记录端存 `17级`），且云端跑的是它自己
  那份代码，尚未有人读过。
- **`(18,13)` 的物理根因取证** —— 需要 dump warped 局部裁图人眼判读，不是代码改动。
  产出可能是几何修复，也可能是 `project_yolo_4class_retrain` 的训练数据待办。
  本轮 L2 先在软件侧把它关掉。
- **全局门槛调整**（`--vision-confidence` 等）—— 会牺牲弱真子，见 §1 末段。
- **给 `board_state.py` / `sync.py` 补日志** —— fix round 2 明确拒绝。这两个模块今天**一条 logger 调用都没有**，而本轮它们已经过复审；在收尾轮往已复审完的模块里新开一条输出通道是范围扩张。代价照实记在 §7 第 5 条：L3 的压制因此没有正面锚点，那一条只能按**条件性**记录，不能记成通过。下一轮若要让它可证伪，该加的是 L3 压制成功时的一行（「在 (r,c) 压住了一次 B↔W 翻转，streak=N」），不是别的。

---

## 7. 验收（板上，非单测）

前五层落地后，在 RK3562 上跑一局跨平台对弈。

**先读这一段，再读断言。fix round 2 重排并补判据。** 下面五条里有四条是「**某件坏事没有发生**」的形状。
缺席本身不是证据：**那件坏事如果根本没有机会发生，断言照样是绿的，而它什么也没证明**。所以每一条都写明了
两件事——(i) 能证明「条件确实出现过」的**正面锚点**，如果有的话；(ii) **条件没出现时这一条是 UNTESTED，
不是 PASSED**。第 1 条是唯一一条自身就有信息量的，已经提到最前面。

1. **（原第 5 条，唯一自足的一条）星阵侧收到的手数与本地棋谱逐手一致。** 这是**逐手全等**断言，不是缺席
   断言：每一手都要在两边都出现，且同点、同色、同序。它自己就能证伪，不依赖这一局里是否碰巧发生了什么，
   也不需要别的锚点。**先看这一条。** 它不通过就没有必要往下看。

2. **（原第 2 条）`(18,13)` 不得被提交。** 两条判据缺一不可：日志里**没有** `move confirmed: (18,13)`
   （也没有任何一条提交行带 col=13 row=18），**并且**星阵侧全程收不到 coord 13。
   **fix round 2 改写坐标与判据本身，round 1 那版是错的**：
   - **提交行有两条，别只 grep 一条。** `_handle_confirmed_move` 里是
     `server.py:3777` 的 `Ranked vision move submitted:`（**小写 v**，升降级分支，打完就
     `return 0.0`，根本走不到下面那条）和 `server.py:3883` 的 `Vision move submitted:`。
     盒子上常态就是升降级会话，所以**大小写敏感地 grep `Vision move submitted` 恰好漏掉最
     常见的那条**。判据写成大小写不敏感的 `grep -i 'vision move submitted'`，或者同时列两个
     字面量。
   - **坐标推导**（可复核，不要照抄数字）：`katrain/vision/katrain_bridge.py:29`
     `vision_move_to_katrain` 把 vision `(row, col)` 转成 `katrain_row = 18 - row`
     （GTP 约定，row 0 在底）；`katrain/web/platforms/gateway.py` 的
     `_play_engine_turn` 把这个 `(col, katrain_row)` 原样当 `human_coords` 传给
     `adapter.submit_engine_move(game_id, col, row)`；`golaxy/coords.py:74`
     `katrain_to_golaxy` 算 `row * 19 + col`。串起来：
     `coord = (18 - vision_row) * 19 + vision_col`。这条公式复现了 §1 自己记录的
     两个实测值——L17 `(2,10)` → `(18-2)*19+10 = 314`，R18 `(1,16)` →
     `(18-1)*19+16 = 339`——对 `(18,13)` 代入得 `(18-18)*19+13 = 13`，**不是 314**
     （314 是 L17 的 coord，round 1 那版把它错配到了 `(18,13)` 头上，字面意思正好
     颠倒：314 出现在星阵侧其实是**好消息**——L17 那颗饿死的真子终于进局了）
   - **正面锚点（fix round 2 新增）**：这一条的缺席部分有锚，用它，别只看缺席。如果 `(18,13)` 这一局里
     真的闪过并凑满了确认，它会被路由到确认卡，而那条路径**是打日志的**——两个 worker 的
     `move at (18,13) confirmed but peak conf … < … — ambiguous prompt; … suspicion=N`
     （`worker_inprocess.py:510-520` / `worker.py:462-472`），而且那一行**自带 `suspicion=`**，
     正好说明 L2 的计数在动。所以这一条要这样读：**期望看到 ambiguous 那一行、同时看不到
     `move confirmed: (18,13)` 那一行**。**两行都没有 ⇒ 这一局那颗幻影压根没出现 ⇒ 这一条是
     UNTESTED，不是 PASSED**：要么再跑一局，要么如实记「本局未证到 L2 的路由闸」。
   - **两条判据缺一不可**：那两条提交行（上面第一点列的 `Ranked vision move submitted:`
     与 `Vision move submitted:`）都只在 worker 的 `ConfirmedMove` 经
     `_vision_move_poller` → `_handle_confirmed_move` 这条路走通时才打出。但 suspect
     格现在只改路由、不改帧数，所以 `(18,13)` 大概率会被路由
     到确认卡（`ambiguous_stone` 事件），**若用户手滑在卡片上点了「确认」**，前端
     `VisionSyncOverlay.tsx` 的 `handleAmbiguousConfirm` 直接调
     `API.playMove(sessionId, {x, y})`（`x, y` 由 `BoardMismatchDialog.tsx` 的
     `rcToXy(row, col, boardSize) = {x: col, y: boardSize-1-row}` 算出，同一套
     `18-row` 翻转），**完全绕开** `_handle_confirmed_move`，两条提交行**一条都不会打**。
     §1 的 F2 条目自己就记录过这个形状（R18 那次「日志无 `Vision move submitted`，仅星阵
     侧收到 coord 339」）。所以只看日志键会漏判——**coord 13 这道后备判据，正是用来兜住
     这次意外点击的**
   - 该点反复触发 `ambiguous_stone` 事件、弹出确认卡、日志里 `suspicion` 非零，是
     这次修复的**预期新行为，不是回归**；只有它绕过确认卡（无论走自动落子分支，
     还是走用户误触确认卡）、真正提交进棋谱或发给星阵（`col=13 row=18` 落子，或
     星阵侧出现 coord 13），才是验收失败
   - **fix round 2：上面那条佐证从「预期」升级为「必需」。** 没有它，这一条的结果记
     **NOT EXERCISED**，不记 PASS。两种可查的痕迹任一即可：worker 那条
     `ambiguous prompt; … suspicion=N`，或事件泵的 `[DIAG-VIS] ambiguous_stone data={…}`
     （`server.py` 的 `_diag_log_vision_evt`，logger `katrain_web.vision`，INFO 级，除
     `setup_progress` / `vision_status` 外每条 dict 事件都带完整 payload）

3. **（替换原第 4 条）手掌按住一颗子：短按不报、久按必报。** 原第 4 条是「手臂划过棋盘不产生
   `illegal_change`」，**fix round 2 整条换掉，因为它激发的是另一个子系统**。`gating.py:39-41`
   的 `should_feed_sync_frame = not frame_present or motion_stable`：手臂划过时帧是**在**的而运动
   **不**稳定 ⇒ `False` ⇒ `SyncStateMachine.update()` 那一帧**根本不会被调用**。所以那条断言在
   `10455ba5` 上是绿的，把 L4 整块删掉也还是绿的——它认证的是既有的运动闸，不是 L4。

   L4 的对象是**相反**的手势：一只手**停**在一颗已落子上不动。这时 `motion_stable` 为真，帧照喂，
   缺子的判定真的会走到 4a-bis 的 hold。两半都要做，**缺一半就不算做过**：
   - **短按**：手掌盖住一颗已落的子约 5 秒（< `missing_hold_seconds`，默认 7.0，`sync.py:85`）后抬手
     ⇒ 全程**不得**出现 `illegal_change`（hold 正在起作用）；
   - **久按**：同一颗子按住**超过** 7 秒 ⇒ **必须**出现一条 `illegal_change`，且它的
     `data["missing"]` 里**点名这颗子的 `[row, col]`**（hold 按设计到期）。
   第二半是这一条能被证伪的原因；只写第一半就又变成「什么都没发生也算过」，那正是原第 4 条的毛病。

   **怎么观察**：`sync.py` 自己没有日志，但事件泵有——`server.py` 的 `_diag_log_vision_evt` 会打
   `[DIAG-VIS] illegal_change data={'positions': …, 'missing': …}`（logger `katrain_web.vision`，
   INFO 级）。**用这条日志判定，不要用屏幕**：屏幕上看不看得见是另一回事，见下一段。

   **两条反向的读法，都不成立：**
   - 看不到 `illegal_change` **不能**推出「盘面没问题」——连着 §4b(c-2) 的总结句读：死锁只有在
     「两格连续亮够 `illegal_change_frames` 帧」且「盘上没有别的东西在搅动异常指纹」且「sync 没有
     停在 `CAPTURE_PENDING` / `BOARD_LOST` / `DEGRADED`」且「前端此刻没有别的卡立着」四条同时成立
     时才会被点名。
   - **屏幕上没弹出点名两格的提示，也不能推出事件没发出**——见 §4b(c-2) 的情况 7：前端在已有确认卡
     时会把整条 `illegal_change` 丢掉。日志和屏幕在这一条上不是同一个证据。

4. **（原第 1 条）L17 那类边缘真子能自己进入对局**，不靠用户按「采纳为我的落子」。**这一条有前提**：
   这一局里必须真的出现过**弱置信度的边缘真子**。一局下来每一手都清清楚楚的话，这一条是**空的**——
   它只是说「一件本来就不会发生的事没有发生」。取证方式：数这一局 `move confirmed:` 行里
   `peak_conf < 0.55`（当天实测真子 peak 的下限）的手数。**是 0 ⇒ UNTESTED，不是 PASSED。**

5. **（原第 3 条）已落子点的 `board delta` 里不出现同点 B↔W 交替。** 这一条**既不能主动激发、也没有
   正面锚点**，如实写在这里而不是记成通过：颜色翻转要靠光照/角度碰巧制造，没法按需复现；而 **L3 压制
   成功时什么日志都不会打**——`board_state.py` 全文 0 条 logger 调用，`sync.py` 同样一条都没有，
   本轮**明确不加**（往已复审完的模块里补日志是本轮拒绝的范围扩张，见 §6 的口径）。于是
   「`board delta` 里没有同点 B↔W 交替」在一局里有两种**长得完全一样**的成因：**L3 挡住了**，和
   **这一局根本没发生过颜色翻转**。所以按**条件性**记录：只有当能从别处独立确认「这一局确实发生过
   翻转」时它才有判据价值——例如人眼看到物理盘上某颗子被反复读成另一色，或颜色写错那条路真的走到了
   4a 的 `expected != EMPTY and observed != EMPTY and expected != observed` 分支
   （`sync.py:362-364`）并发出 `ILLEGAL_CHANGE`。**拿不到这种独立确认 ⇒ UNTESTED，不是 PASSED。**
