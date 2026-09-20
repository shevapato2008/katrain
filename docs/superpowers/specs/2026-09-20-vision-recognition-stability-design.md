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
| D3 | **L3 保留逃生口**：连续 `COLOR_FLIP_RELEASE_FRAMES` 帧反色则放行并恢复 `sync.py:351-353` 的「颜色放错了」提示 | 否则那条分支变死码，系统失去唯一一条告知摆错颜色的路 |
| D4 | **L2 只用一个信号：候选被放弃**（出现后耗尽 miss grace 仍未确认）。不做跨进程 IPC 回灌，**也不罚「同点短窗内重复确认」**。**2026-09-21 fix round 1 修正**：suspect 格的额外门槛**只加在 worker 的 ambiguous 路由闸上**（`SUSPECT_CONFIDENCE_BONUS`），**绝不加在 `detect_new_move` 的确认帧数上**——第一版曾把 suspect 格的所需帧数翻倍，判断依据「放弃是真子从不会做的事」是**假的**：`MoveDetector` 类注释自己就写着 `miss_grace` 存在的理由——弱置信度真子本来就会闪断一两帧；一颗在 keep 闸附近震荡的弱真子，只要震荡够久，产生的正是这一条唯一信号，这正是当天 F2 那批真子伤亡的实测特征。更严重的是，帧数门槛卡在 `detect_new_move` 的返回值上，而这个返回值同时是自动落子**和**确认卡的入口（stuck-stone promoter 只在**没有任何候选**pending 时才跑），于是一颗攒不满翻倍帧数的 suspect 格在任何路径上都 confirm 不了——制造出「静默永久丢手」，恰恰是这个 F1 修复本该防止、结果却亲手制造出的最坏结果。单独的路由闸已经够用：当天真子 peak_conf 实测 min=0.55、p25=0.72（117 手真局，`config_service.py`），而 (18,13) 两次自动确认分别在 0.50、0.57（且都已是 peak 值）；`0.42 + 0.25 = 0.67` 正好卡在两者中间——幻影必进卡，多数真子仍自动落子；即使一颗真子弱到 min=0.55 那一档、又恰好落在 suspect 格上，代价也只是多按一次确认，不会丢手。重复确认那条被**否决**：`MoveDetector` 类注释里的 caller-owned-baseline 契约**故意**让未被处理的确认每 `consistency_frames` 重发一次（弱真子靠它反复向用户要确认卡），罚重复会让一颗合法弱子每几帧加 3 分而衰减每 300 帧才减 1 分，分数跑飞、门槛抬高后**即使置信度回升也永久进不来**——这条论证同样适用于「不要罚放弃信号在确认帧数上」：跑飞的门槛，无论挂在哪个轴上，代价都是同一种「permanently 进不来」。**fix round 2 补充**：这个路由闸只挡 `self._bound` 分支（会提交/转发的对局路径）；monitor 模式（`if not self._bound:`）不查置信度也不查 `is_suspect`，L2 在那条路径上不提供任何防护，见 §5 |
| D8 | **L1 的 `required_frames` 只授予「调用方测的那一格」**（进入方法时的 leader），其余候选一律用 `consistency_frames` | worker 每帧按 `peak_for(pending_move)` 现算，那是关于**某一颗子**的证据。leader 为 suspect 而需要更多帧时，若快通道外溢，旁边一颗 0.50 的普通候选会提前确认并越过设备 0.42 的自动落子闸 |
| D9 | **L3 的「放行」必须闩住，直到稳定盘面真的采纳新颜色** | 两个 worker 都对 extractor 输出做两帧投票（`np.where(observed == prev_observed, observed, last_stable)`），而传给 extractor 的 `prev_board` 就是那张稳定盘面。只放行一帧永远凑不满两帧一致 ⇒ 第 16 帧重新压制，颜色**永久卡死**，逃生口和 `sync.py:351-353` 一起变成不可达 |
| D5 | **L4 `missing` 同时要求墙钟时长 + 最小观测帧数** | `gating.py:39` 的 `should_feed_sync_frame` 在有运动时**不喂帧**，只用墙钟会把「手遮挡 3 秒」误判成「持续缺席 7 秒」 |
| D6 | **L1 精确并列（count 与 first_seen 都相同）时不确认** | 保留现有 `test_ignores_multiple_simultaneous_new_stones` 的语义（同帧出现两颗子 = 真歧义），把改动面收到最小 |
| D7 | **L2 先于 L1 落地** | L1 让真子能在幻影旁边确认，但也让持续幻影更容易自己数满；L2 + L0 是它的前置安全网 |

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

---

## 7. 验收（板上，非单测）

前五层落地后，在 RK3562 上跑一局跨平台对弈，断言：

1. L17 那类边缘真子**能自己进入对局**，不靠用户按「采纳为我的落子」
2. **无 `Vision move submitted` 且 col=13 row=18；星阵侧全程收不到 coord 13**——
   **fix round 2 改写坐标与判据本身，round 1 那版是错的**：
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
   - **两条判据缺一不可**：`Vision move submitted` 只在 worker 的 `ConfirmedMove`
     经 `_vision_move_poller` → `server.py:3612 _handle_confirmed_move` 这条路走通
     时才打出。但 suspect 格现在只改路由、不改帧数，所以 `(18,13)` 大概率会被路由
     到确认卡（`ambiguous_stone` 事件），**若用户手滑在卡片上点了「确认」**，前端
     `VisionSyncOverlay.tsx` 的 `handleAmbiguousConfirm` 直接调
     `API.playMove(sessionId, {x, y})`（`x, y` 由 `BoardMismatchDialog.tsx` 的
     `rcToXy(row, col, boardSize) = {x: col, y: boardSize-1-row}` 算出，同一套
     `18-row` 翻转），**完全绕开** `_handle_confirmed_move`，不会打 `Vision move
     submitted`。§1 的 F2 条目自己就记录过这个形状（R18 那次「日志无 `Vision move
     submitted`，仅星阵侧收到 coord 339」）。所以只看日志键会漏判——**coord 13 这
     道后备判据，正是用来兜住这次意外点击的**
   - 该点反复触发 `ambiguous_stone` 事件、弹出确认卡、日志里 `suspicion` 非零，是
     这次修复的**预期新行为，不是回归**；只有它绕过确认卡（无论走自动落子分支，
     还是走用户误触确认卡）、真正提交进棋谱或发给星阵（`col=13 row=18` 落子，或
     星阵侧出现 coord 13），才是验收失败
3. 已落子点的 `board delta` 里不出现同点 B↔W 交替
4. 手臂划过棋盘不产生 `illegal_change`
5. 星阵侧收到的手数与本地棋谱逐手一致
