# RK3562 上板验收与修复 — 2026-09-20

一天的实测记录。**所有数字都是板上量的**，不是推理出来的；推理出来又被实测推翻的也记在这里，
因为下一轮最容易重走的就是那几条。

设备：RK3562 / gzpeite，`ssh rk3562-direct`（只有这一个 host 通）。
本日两次部署：`939165a4`（上午）、`756643f5`（下午）。SmartBox `main` → `06d78d77f`。

---

## 1. 结论速查

| # | 问题 | 结论 | 状态 |
|---|---|---|---|
| 1 | 落子音早于屏上出子 | **软件次序是对的**，七手实测画面领先 203–2124 ms。剩余嫌疑只在「画布→面板」那一段，页内仪器看不见 | Fan 2026-09-20 说「已缓和很多，先不修」⇒ 挂起 |
| 2 | 反复「盘面与对局不一致」 | **主因不是阳光，是终局后视觉从不解绑**（78% 的弹窗出在终局后那 26 分钟）。已修 P0-1；P0-2 未做 | 部分修复，证据已满 |
| 3 | 白天 LED 偏暗 | **软件无余量**。两级都在 255；通道数与闪烁两条现场实验均被否定 | 否定结论，软件侧关闭 |
| 4 | 倒计时与超时声音不同步 | **倒计时本来就是对的**。`countdownbeep.wav` 是 5 秒 5 声的整轨，却被按秒重放 5 遍 | 已修并上板 |
| 5 | 计时起点（Fan 当场提出） | 建局 → 棋盘可用之间 69 秒全记在人类头上 | 已修并上板 |

---

## 2. 已修并已部署（`756643f5`）

### 2.1 终局即停止视觉比对（P0-1）

`PhysicalPlayOrchestrator.PAUSE_REASON_GAME_OVER`。触发条件是
`end_result and not awaiting_count` —— **两半都要**：两次虚手之后 `end_result` 已经写上而
`awaiting_count` 仍为真、盘面还活着，只看 `end_result` 会让一颗阳光鬼子在数子没完时杀掉视觉。

用 **pause 不用 unbind**：终局后仍允许悔棋（`GamePage.tsx` 只在升降级局里过滤 undo），
unbind 是单向门，悔棋回到可下局面后实体盘会一直是死的。
`service.py` 的 `pause_detection` docstring 原来说「paused 时 SyncStateMachine 照跑」，
与 `gating.py:34-35` 的实际行为相反 —— 一并改掉，按那句话选机制的人会走错。

配套两处：
- `server.py` 的 `_rearm_unless_terminal`：终局原因（`already_ended` / `remote_ended`）不再重新布防。
  重新布防会把同一个冻结盘面再推一遍，于是同一颗子每个一致性窗口重新确认、重新被拒。
- `GamePage.tsx` 终局后整个卸掉 `VisionSyncOverlay`：`visionRecovery.ts:84` 里**唯一**能清
  `blocking` 的路径是收到 `synced`，而终局后那段 `synced` 是 **0 条** ⇒ 后端停了也清不掉屏上已经开着的弹窗。

### 2.2 倒计时整轨只放一次

`katrain/sounds/countdownbeep.wav` 本地实测：**5.000 秒，内含 5 声，峰值在 0/1/2/3/4s**。
桌面版 `gui/controlspanel.py:242-247` 是进窗口放一次、离开 `stop_sound`。
kiosk 却每剩余一整秒放一次整轨 ⇒ **5 份重叠**，峰值落在 T−1 秒、一直响到 **T+3 秒**，
而卡片在 T 就写「0:00 超时」。

改成窗口边沿触发 + 离开即停；`useSound` 新增 `stop(name)`，并对 `countdownbeep`
复用缓存元素（克隆的元素停不掉，而且每次重解析 src 在这台板上要 140–1065 ms）。

⚠️ `GameControlPanel.playAi.test.tsx` 原来断言「每秒只响一次 = 5 次调用」——
**它守的就是这个缺陷本身**，已改写。典型的「闸也会过期」。

### 2.3 计时起点改为「棋盘可用」

`WebKaTrain.start_clock()`，幂等，三个触发点：
- 实体盘局：视觉绑定（`api/v1/endpoints/vision.py`）——**在绑上之前一颗子也放不进去**
- 无视觉的部署：对局 WS 接上（`server.py`）
- 屏幕降级局：第一手落下（`interface.update_timer` 兜底）—— 这种局永远不会有视觉绑定，
  没这条兜底钟永远不起步、超时永远不判

⚠️ WS 那处**必须**判 `vision_service.enabled`：盒子上
`physicalPlay = !screenFallback && isVisionEnabled`（设备能力，不是单局设置）⇒ 板上每一局都是实体盘局，
而 WS 永远比视觉绑定先到。在那里用 WS 起步就是把 69 秒又记回去。

---

## 3. 实测数据

### 3.1 上午那局（46 分钟，`939165a4`）—— 三窗口普查

| 窗口 | 时长 | illegal_change | already_ended | board_lost | synced | mean_conf | bound |
|---|---|---|---|---|---|---|---|
| 对局进行中 | 994.7s | 53 | 0 | 6 | 88 | 0.738 | True |
| **终局后仍绑定** | 1567.7s | **191** | **732** | 10 | **0** | 0.784 | True |
| 第二局 | 4619.7s | **0** | 0 | 0 | 0 | 0.580 | **False** |

**78% 的弹窗出在终局后那一段，而那一段的平均置信度比对局中还高。**
第二局同样白天、盘上还留着 100+ 颗子、更晚 ⇒ 0 次弹窗，因为 `bound=False`。
**变量是绑定状态，不是光照。** 把问题(2) 归给阳光是取样错误。

终局后那 10 次 `board_lost` 里有 **7 次超过 10 秒弹窗闸，最长 389 秒**（几乎肯定是在收子）。

### 3.2 计时不对等（实测截图）

10:40 屏上：白方 **4:37 剩余** vs fan **0:36 剩余**。
白方是数字侧瞬时落子，人类要俯身摆子 ⇒ 同一时限对两侧不对等。叠加 69 秒空窗。
该局最终以 `白胜超时` 结束，而盘面是 **黑 99.3% / 黑 +54.3 目**。

### 3.3 下午那局（53 分钟，`756643f5`，P0-1 已上板）

```
Clock started            2      ← 验收①通过:起点是 vision bound,不是建局
move confirmed         108
Vision move submitted   89
synced                 180
illegal_change          75
board_lost              21  →  board_reacquired 21(全部恢复)
already_ended            0
视觉单帧 enh+infer: 216 采样  均值 363ms  p95 438ms  最大 519ms
```

`board_lost` 21 次：中位 **1.2s**、最大 **3.7s**、**超过 10 秒闸的 0 次** ⇒ 用户一次都没看到那个弹窗。
上午那 7 次超闸全部在「终局后仍绑定」段，已被 P0-1 消掉。

### 3.4 音画时差（七手，页内时间戳与后端日志对齐）

| 这一手 | 棋子画进画布 | `play_call` | 画面领先 |
|---|---|---|---|
| 黑 (2,16) | 12.960 | 15.084 | 2124 ms |
| AI 白 | 15.782 | 16.298 | 516 ms |
| 黑 (4,12) | 22.169 | 22.372 | 203 ms |
| AI 白 | 24.585 | 24.925 | 340 ms |
| 黑 (4,11) | 35.660 | 36.627 | 967 ms |
| AI 白 | 37.929 | 38.199 | 270 ms |

`drawImage` 计数每多一颗子涨 1（12→13→…→19），可逐手核对。

同时量到两个此前没人知道的数：
- **rAF 间隔 67–172 ms** ⇒ 页面只有 **6–15 fps**，不是 60
- **`play_call → playing` 29–383 ms**，抖动一个数量级

⇒ 双 RAF 买到的余量（2 帧 = 130–340ms）与音频启动延迟**同量级**。
它是一场设计上只是勉强赢的竞速，帧率一掉就可能翻盘。

---

## 4. 未完成

### P0-2 · `illegal_change` 指纹冷却 +「忽略」要粘（证据已满，未实现）

下午那局 53 分钟：

```
illegal_change 75 条,只有 16 个不同指纹
  x22  [(14,17,1), (18,18,2)]     ← 同一指纹连报 22 次
  x18  [(14,17,1)]
  x8   missing=[(16,17,2)]
同指纹相邻间隔:中位 2.35s,最小 2.21s
```

**62 次里 46 次是纯重复。** 按一次「忽略」只买 2.35 秒。
加指纹冷却后弹窗从 62 降到 ~16（降 74%）。

落法（来自复审，已裁定）：
- key 用 `frozenset(unexpected)`，**不要**用完整 payload —— `missing` 一侧在遮挡/光照下本来就抖，
  放进 key 等于 key 永远在变，冷却形同虚设（实测：完整 key 存活 78/244，仅 positions key 存活 40/244）
- `visionRecovery.ts` 加 `dismissedMismatch`，由 `synced` 和 `node_advanced` 清。
  **这条比后端冷却更重要** —— 终局后那段教会我们 `synced` 不是可靠的清理信号
- `self._state = SyncState.MISMATCH_WARNING`（`sync.py:405`）**必须留在抑制分支之外**，
  移进去的话被抑制的帧看起来像「棋盘还在丢」，10 秒后弹出棋盘检测异常
- 冷却时钟用 `time.monotonic()`，不要传 `update()` 的 `now`（后者有 `time.time()` 回落，挂钟回拨会把冷却变成静音）
- **不加** episode 级 30s/120s 退避（过度设计，还会压掉真实的新异常）

### 分配残差闸（第 1 层，未实现）

`board_state.py:71-85` / `205-212`：只要 `round(fy)/round(fx)` 落在 `[0,18]` 就接受，
而 `margin_cells=1.0` 让 warp 四周各多出一整格木头 ⇒ **边缘点的接受带向外延伸半个格子到裸木框上**。
亚格残差算了（`:197`）但只用来排序（`:204`），从不用于拒绝。

现场确认的假阳性点：**T1 `(18,18)`**（Fan 目视为空）、`(14,17)`（Fan 清盘后仍在报）、`(18,13)`、`(11,5)`。
⚠️ 这条发现被对抗式验证 **3/3 驳回**（理由是幻影类别其实是 off-point、以内部黑子为主，不是 edge/white），
但两次实测的幻影点都在边缘/角 ⇒ **落地前必须先用真数据重新定性**，不要照抄。

### P2 · 音画时差的带符号测量（未做）

唯一还能推进(1) 的动作，需要**外部录像**：手机高帧率对着 7" 屏 + 同一段录音，
数「棋子可见帧 → 咔哒起音」的帧数，记**数值和符号**。
页内仪器、CDP 录屏（本机最高 **3 fps**，间隔 80–650ms）、jsdom 都量不了这个数。

---

## 5. 被实测推翻的推理（下次别重走）

1. **「阳光是问题(2) 的主因」** —— 被三窗口表推翻。第二局同样白天、更多子、0 次弹窗。
2. **「幻影子以白色为主（反光读成白子）」** —— 活局内黑子实例 65 个 vs 白子 13 个，board delta 增删近乎对称。
3. **「`board_lost` 整局 0 次」** —— 我那次 grep 只覆盖开局头几分钟。实际 16 次，只是都在 1–2 秒内恢复、
   没到 10 秒弹窗闸，所以用户没看见。**结论对，但给的证据是错的。**
4. **「两份 worker 都要查」** —— `KATRAIN_MODE=board` ⇒ `service.py:42` 选 `InProcessAdapter`，
   `worker.py` 在 RK3562 上**根本不执行**。
5. **「KataGo 占满 Mali 2 秒导致画面晚」** —— 被 `Processing batch` 行推翻：2 秒窗口里只有 2 次前向，
   其余 1.81 秒是 `maxTime: 2.0` 在空等。
6. **「LED 可以靠多点通道或闪烁变亮」** —— Fan 两次现场并排实验均否定。
   这两条要标成 **already-tested-negative**，否则下一轮必然重提。
7. **「(4) 的不同步是音频输出延迟」** —— 是次要项。主因是资产被按秒重放（3 秒 > 1065ms 的三倍）。

---

## 6. 工具与环境（下次直接用）

- 部署配方：`docs/superpowers/plans/2026-09-17-physical-play-sync-feedback.md` Task 11 九步，**照走，别凭记忆**
- 链路取证：`smartbox-software/scripts/deploy-main-to-rk3562.sh check`（四条全过才动手）
- 回滚：`/root/deploy-backups/katrain-latest`，命令在上面那份计划 Task 11 Step 3
- 引擎就绪的判据是 `"local":"reachable"`，**不是 `"ok"`** —— 我按 `ok` 轮询过，白等了 600 秒
- CDP：`ssh -N -f -L 19222:127.0.0.1:9222 rk3562-direct`，Chromium 120
  - 页内 `setInterval` 采样会被主线程饿死、读到陈旧值（实测出现 690ms 空洞、17 秒读不到已经画上的子）——
    **要用外部驱动的逐次 `Runtime.evaluate` 探针**
  - `.click()` 不触发 React handler，要用 `Input.dispatchMouseEvent`
- 板上录音：`arecord -D plughw:1,0`（card 1 = USB 摄像头麦克风）。**环境一吵就不可用** ——
  实测本底从 53 升到 128 时，检出的「起始」早于 `play()` 206ms，物理上不可能
- LED 现场实验：`POST /api/v1/led/points`，只接受具名颜色（`black`=纯红 / `white`=纯绿 / `hint`=白）

---

## 7. 下次从哪接着走

1. **P0-2**（证据已满，落法已裁定，见 §4）—— 前后端两半必须同批落
2. 终局后停止比对的**设备验收**还差一格：下完一局后停在对局页 3 分钟，
   `journalctl --since <终局时刻> | grep -c already_ended` 必须为 **0**，
   且 `bound=` 仍为 `True`（证明是 pause 不是 unbind）；再悔一步棋确认可逆。
   **升降级局要另跑一遍** —— 本日日志走的是非升降级分支（`Vision move B refused`），
   替 `server.py` 升降级那一支作不了证
3. 读秒音（验收③）**一次都还没验** —— 需要本地对局设置里配 byo-yomi
4. 分配残差闸：先用真数据重新定性（见 §4 的警告）
5. LED：软件侧已关闭，要动就是硬件（导光柱／聚光散光膜／遮光罩／更高光强灯珠／改出光角度）。
   需要的输入是**照度计读数**，目前只有「目视差不多」

---

## 8. 顺带修掉的两笔债

- **`.game-win-trophy` 的闸误报**：`@media (prefers-reduced-motion)` 里的条件覆盖被
  `goScreensCssCollision.test.ts` 判成跨屏碰撞。改的是**判据本身**（补 at-rule 嵌套），不是加白名单；
  判据函数已导出并用内联 CSS 直接测两侧（顶层重复仍要抓、media 覆盖不算）
- **测试会改写 `~/.katrain/config.json`（用户真实配置）**，而**下一次**运行时
  `tests/platforms/test_engine_manager.py::test_dump_engine_game_state_fixture`（收集序 479 行，
  远早于 test_timer 的 4466 行）会把它读进签入的 `engine_game_state.json`。
  本次新用例已改为只碰 per-instance 的 `active_game_timer`。
  那份 fixture 本身长期落后于 `get_state()` ⇒ **任何人跑完全量树都是脏的**，判「是不是我造成的」必须与基线对照。
