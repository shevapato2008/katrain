# kiosk 必须永远退得出对局 — 设计说明（2026-09-20）

配套计划：`docs/superpowers/plans/2026-09-20-kiosk-exit-always-works.md`

## 0. 验收标准（用户原话，全文按这两条判）

- **R1**：「我们需要保证这边可以退出棋局就可以了」—— 无论远端平台怎样、服务端会话是否还在，
  用户必须**永远**能从 kiosk 屏幕上离开对局。
- **R2**：「前端界面不能出现 `Request failed 404` 这种类型的报错，需要弹窗和用户说明情况
  然后给出退出当前界面的方式」—— 原始 HTTP/JSON 报错文本不得上屏；给人话 + 出口。

## 1. 现象

2026-09-20 在 RK3562 上与星阵（Golaxy）跨平台对局中，按 退出 / 认输 得到：

```
Request failed 404: {"detail": "Session not found"}
```

用户被卡在对局页，屏幕上退不出去。

## 2. 这个 404 是本机的，不是星阵的

`/api/resign` 的**第一行**就是 `_get_session_or_404(manager, request.session_id)`
（`katrain/web/server.py:2057`），它在任何平台/网关分支（`:2082-2087`）之前执行。
`_get_session_or_404`（`:3394-3398`）把 `SessionManager.get_session` 的 `KeyError`
（`katrain/web/session.py:126-131`）翻成 404。

**所以它陈述的事实只有一个：本机 `_sessions` 里没有这个 id。** 星阵结束最多是诱因。

已排除的其它来源：

| 机制 | 裁定 |
|---|---|
| 服务重启（内存态全丢） | **排除** —— `ActiveEnterTimestamp=2026-09-20 15:56:00`，17:00–20:05 journal 无 Started/Stopped |
| `max_sessions` 容量驱逐 | **排除** —— 满了抛 `RuntimeError("Session limit reached")`（`session.py:66-74`），不驱逐活会话；日志 0 次 |
| 星阵/网关侧结束 | **排除为 404 来源** —— `reason=="game_ended"` 那条是 200 空操作（`server.py:2094-2098`）；`platforms/manager.py:274-288` 只动网关自己的 `_active_games` |
| 显式 `DELETE /api/session/{id}` / `/api/multiplayer/leave` / logout | 可能，今天无证据 |
| **空闲超时驱逐** `now - last_access > 3600`（`session.py:231`） | **唯一时序吻合的候选** |

### 为什么对局开着也会过期

全仓唯一的 `session.touch()` 在 `session.py:131` —— **只有走 `get_session` 的请求才续期**。
而在一局安静下来的跨平台对局里，没有任何东西在走它：

- WS 的 ping/pong 分支不调 `get_session`（`server.py:3207-3208`；只在连接时调一次 `:3153`）
- vision 状态轮询不带 session_id（`api/v1/endpoints/vision.py:106-131`）
- LED 的 240 秒 reassert 走另一个 watchdog（`physical_play_orchestrator.py:503` → `server.py:724`），不续期

板上时间线：`Engine game started: golaxy … -> session 83902fe4…` @ 17:12:59，
**最后一次 genmove tunnel 调用 17:21:47**，此后到 19:47 零活动、vision 持续 `paused=True`。
按 3600 秒，30 秒一次的扫描（`server.py:3298`）应在 **18:22–18:24** 之间驱逐它。

### 诚实边界（不要写成「已证实」）

没有任何一条日志直证这次驱逐或这次 404：`uvicorn.run(..., access_log=False)`
（`server.py:4077`），且驱逐成功不打日志（`session.py:198-243` 只在 shutdown 异常时 warning）。
全天 `grep -i 'session not found'` = **0 条**，`grep -icE '"(GET|POST) /'` = **0**。

**空闲驱逐是唯一时序一致的候选，不是被记录下来的事实。**
最便宜的定案实验见 §6。

## 3. 为什么用户退不出去（R1 今天在代码层面就是破的）

屏幕上每一个出口都**要求服务端先成功**：

```tsx
try { await session.handleAction('resign'); }
catch (error) { setResignError(...); return; }      // GamePage.tsx:1220-1223
session.clearPhysicalEngineError();
navigate('/kiosk/play');                             // :1228  ← 在 catch 之后
```

认输框（`:1168-1180`）、本地认输（`:798-805`）同形。失败时既不导航、也不
`setShowExitConfirm(false)`，框原地不动。

唯一**不需要服务端成功**的出口「先离开，不认输」（`:1207-1214`）闸在
`session.connectionLost` 上。而那个 flag 只在 WebSocket `onclose` 时置位
（`useGameSession.ts:233-242`），`handleAction` 的 catch（`:303-308`）**从不碰它**。

**决定性的一环：后端驱逐会话时不关 WebSocket。**
`remove_session`（`session.py:185-189`）和 `_cleanup_locked`（`session.py:216-243`）
只 pop + `session.katrain.shutdown()`（后者 `interface.py:1923-1929` 只关 KataGo）；
`/ws/{session_id}` 的 `while True: receive_json()`（`server.py:3205-3208`）从不复查
`_sessions`。⇒ **会话没了而 WS 还开着，`connectionLost` 恒为 null，逃生按钮根本不渲染。**

另一个写对了的出口「回到对弈」（`:546-559`，注释写明「盒上全屏没有浏览器后退入口」）
闸在 `loadFailed = !session.gameState && !!session.error`（`:381`）—— 局面已加载后恒 false，
覆盖不到局中失败。

剩下只有「取消」（回到同一块坏屏）和「退出」（再打一次必然再 404）。

## 4. 为什么屏幕上出现原始报错（R2）

- **产生点**：`katrain/web/ui/src/api.ts:355`
  `` throw new ApiError(response.status, `Request failed ${response.status}: ${body}`, detail) ``
  （同形第二处在 `:377`）。`body` 是原始响应文本。
- **透传**：`useGameSession.ts:305-307` `setError(message)` 后 rethrow
  → `GamePage.tsx:803 / 1173 / 1221` `setResignError(error.message)`
- **渲染**：`GamePage.tsx:1333-1334` `<Alert severity="error">{resignError}</Alert>`（5 秒自动消失，框不关）

**仓里已经有为这个坑写的工具，不许新造**：

- `katrain/web/ui/src/utils/requestFailure.ts` 的 `requestFailureKind()` —— `status===404 → 'not_found'`。
  文件头注释写的就是「别把 `Request failed 503: {…}` 印给用户」。
- `katrain/web/ui/src/kiosk/components/report/reviewPresentation.ts:245` 的
  `failureLine(prefix, kind, t)` —— 「做什么没成 · 为什么」。
- 正确用法样板：`kiosk/pages/ReportDetailPage.tsx:290-299`（注释「不印原文」）。
- 现成的「人话 + 出口」文案：`GamePage.tsx:548-554` 的 `game:unavailable_title` /
  `game:unavailable_reason`（「这一局已经打不开了」/「可能是盒子重启过、这一局闲置太久被清理，
  或者它属于另一个账号。」）—— **正好是这次要说的话，直接复用这两个 key。**

**泄漏面**：kiosk 另有约 25 处直接把 `error.message` 上屏（平台连接、棋谱、死活题、教程、
标定等）。本轮**只收口对局流的 4 处**，其余列为后续（见 §5 不做）。

## 5. 设计决定

| 编号 | 决定 | 理由 |
|---|---|---|
| E1 | **驱逐/删除会话时关掉 `session.sockets`**，close code 1008、reason `session_gone` | 这一条让**既有的**逃生按钮自动点亮（`GamePage.tsx:1207` 是 truthiness 判断），是改动最小、复用最多的一条 |
| E2 | 前端为 1008 + `session_gone` 新增 `connectionLost='gone'` 档，**不复用 `'rejected'`** | `'rejected'` 那档的文案是「请重新登录后重试」（`useGameSession.ts:237`），对「会话过期」是错的 —— 重新登录救不了它；R2 要求说人话，说错话不算人话 |
| E2b | `'gone'` 这一档**同时**要写一句人话进 `error`，**不能置 null** | `useGameSession` 是共享件，galaxy 只读 `error`、从不读 `connectionLost`。置 null = galaxy 那边留着一块陈旧的可下棋盘、一句提示都没有，还会抹掉已有的错误（对抗复审 F5） |
| E2c | 三条通道（WS 关闭 / HTTP 404 / HTTP `session_gone` 体）**全部**汇进同一个 `'gone'` 信号，且汇在 hook 里 | 只处理其中一条，另两条照样坏。放在 hook 里所有消费者都受益，放在某一屏里只有那一屏受益 |
| E3 | **「先离开，不认输」永远渲染**，不挂任何闸；它不调服务端、不清 resume 指针 | 这是 R1 的无条件保证。离开而不认输是纯本地动作，**永远**合法 —— 正是按钮上写的那件事。旧设计只在 404 时放人走，而星阵的认输拒绝回 **409**（`server.py:2094`）且 WebSocket 完好，用户照样被困（对抗复审 F1） |
| E3b | resume 指针**只在 `'gone'` 这一支**清；「先离开」保留它 | 「先离开」之后那局可能还活着，`继续上一局` 就是回去的路。只有确知这局在服务端没了才该清 |
| E4 | **必须 `clearActiveSession('game')`**（`kiosk/utils/activeSession.ts:61`） | 否则「继续上一局」会转回这个死会话 |
| E5 | `/api/resign`、`/api/timeout` 对未知会话返回 200 `{"session_id": …, "status": "session_gone"}` —— **不带 `ended` / `state` / 任何结果** | 回收会话**不会**结束远端对局（真正的远端认输在 `gateway.py:399-420`，这条早返回根本走不到；`PlatformManager` 另有一套 active-game 上下文）。旧稿的 `{"ended": true}` 是撒谎：会让 kiosk 告诉用户「你认输了」，而那局在星阵那边可能还在下（对抗复审 F3） |
| E5b | 前端必须**消费** `status === 'session_gone'` | `handleAction` 只看 `result?.state`，这个体会被当成静默成功：框关了、棋局永不终局、页面完全不知道这局已死，连 resume 指针都不会清（对抗复审 F2） |
| E6 | E5 **不削弱鉴权**，但「会话不存在」与「会话在、你无权」**不得合并成同一个 200** | `guard_session_terminator`（`server.py:921`，防陌生人判负他人对局）的判据是 `session_owner_ids(session)`；会话不存在就没有可越权的对象，且空操作分支一行账都不写、不广播。合并两者才会变成鉴权旁路 |
| E7 | **不改 `ApiError.message` 的格式** | `api.ts:284-285` 注释点名 `KifuPage.test.tsx` 有基于 `"Request failed 500"` 的文本断言；R2 在 UI 层收口，不动那条闸 |
| E8 | 会话空闲回收本身**本轮不改** | 三个候选（WS ping 续期 / 不驱逐未终局对局 / 驱逐时关 socket）里，只有第三个改动小且风险低——那就是 E1。前两个会让「挂着不动的对局页」永不回收，而 RK3562 只有 2G 内存 |
| E9 | E1 的关 socket 要落在 `_shutdown_all`，**不是** `cleanup_expired` | `create_session` 的两条容量路径（`session.py:73` 与 `:87`）直接调 `_cleanup_locked` + `_shutdown_all`，**从不经过 `cleanup_expired`**。只改定时清理会整条漏掉（对抗复审 F4，内存复现：引擎关了、socket 一个没关） |
| E10 | kiosk 的连接 snackbar **任何一支都不得渲染 `session.error`** | 1008 凭据拒绝之后 `connectionLost` 停在 `'rejected'`，随后一次失败动作会把 `ApiError.message` 写进 `session.error`，那条 fallback 就把原文印出来了 —— R2 在这条路上仍然破（对抗复审 F6） |

## 6. 明确不做（本轮范围外）

- **§4 里另外 ~25 处 raw `error.message` 上屏** —— 同一形状，但不阻塞 R1/R2 的对局流。
  单独排期，按 `requestFailureKind` + `failureLine` 逐个替换。
- **改 `session_timeout` 或加会话保活** —— 见 E8。
- **补日志把 §2 的诚实边界定案** —— 这是本轮唯一值得顺手做的取证：
  在 `server.py:3396` 的 `except KeyError` 里加一行 `warning`，在 `session.py` 的 pop 处加一行
  `info`。**已并入计划 Task 1**，因为它同时是 E1 的可观测性前提。

## 7. 验收（板上，非单测）

1. 对局中拔掉网 / 等会话过期后按 退出 —— **能离开**，回到 `/kiosk/play`
2. 屏幕上**不出现** `Request failed`、`{"detail"`、`404` 任一字样
3. 弹窗说的是人话，并且**框里有一个能离开的按钮**
4. 离开后点「继续上一局」**不会**转回那个死会话
5. 会话被回收时，journal 里能看到那一行 `session evicted`（本轮新增）


---

## 8. Revision（2026-09-20，对抗复审后）

本计划第一稿经 Codex 对抗式复审，判定 **needs-attention**，六条发现**全部经源码核实成立**，
其中两条是我自己引入的跨任务缺陷。设计已按下表改写，上面的 E 表是改写后的版本。

| # | 发现 | 落在哪条决定 |
|---|---|---|
| F1 高 | 只在 404 放人走 ⇒ 星阵认输拒绝回 **409** 且 socket 完好时用户照样被困 | E3（「先离开」永远渲染） |
| F2 高 | Task 2 的 200 回执**无人消费** ⇒ `handleAction` 当成静默成功，棋局永不终局、resume 指针不清；且它**抵消**了 Task 3 赖以触发的 404 信号 | E5b、E2c |
| F3 中 | `{"ended": true}` 把「本机会话没了」说成「对局结束了」，而远端可能还在下 | E5（改成 `status`，不带任何结果） |
| F4 中 | 关 socket 只放在 `cleanup_expired` ⇒ `create_session` 的两条容量驱逐路径整条漏掉 | E9 |
| F5 中 | `'gone'` 分支 `setError(null)` ⇒ galaxy（只读 `error`）留着陈旧可下棋盘、零提示 | E2b |
| F6 中 | 连接 snackbar 的 `{session.error}` fallback 仍可达并泄漏原文；且第一稿的测试把 `session.error` 永久钉成 null，**测不出这个泄漏** | E10 |

另有一条工程提醒已并入计划 Task 4 Step 1：现有 `beforeEach` 写在 `describe('GamePage')` **里面**，
新增的兄弟 suite 拿不到 mock 重置，必须提到文件作用域。
