# Review Feedback for Golaxy Engine Integration Plan

> To: Plan Author  
> From: Codex  
> Date: 2026-07-02  
> Subject: Review of `plan.md` for kiosk Golaxy engine-play integration

## Overall Assessment

`plan.md` 的协议事实和分阶段思路总体扎实，尤其是先做坐标/协议纯函数测试，再接 adapter/manager/前端的顺序是合理的。但我核对了当前 `katrain/web/platforms/`、`server.py`、board proxy 与 kiosk 前端后，发现几个计划对现有代码行为的假设不成立。下面的 Blocking 项不先改，实施时很容易出现棋谱顺序错误、board 模式跑不通、或星阵登录根本不可用。

---

## 🔴 Blocking

### 1. `submit_move` 内同步 emit AI 回招会把本地棋谱顺序落反

Ref: plan.md §3 lines 64-70, §4 Phase 2/3 lines 99-112; review-request §6 A1/B5

计划假设：`submit_move(game_id, col, row)` 内部 append 人类手、调用 genmove、append AI 手，并立刻 `await self._emit("opponent_move", PlatformMove(...))`，然后复用现有 gateway。

当前代码实际行为不支持这个顺序：

- `PlatformCommandGateway.play_move()` 是 remote-first：先 `await adapter.submit_move(...)`，成功后才 `_local_play(session_id, col, row)`，见 `katrain/web/platforms/gateway.py:49-66`。
- `_on_opponent_move()` 收到回调会立即 `session.katrain("play", coords=(move.col, move.row))`，见 `katrain/web/platforms/manager.py:141-150`。

因此如果 adapter 在 `submit_move()` 返回前 emit AI 手，KaTrain 当前轮次仍是人类方，AI 坐标会先被作为人类这一手落到本地；随后 gateway 再把人类坐标作为下一手落下，棋谱顺序和颜色都会错。

Required change:

- 不要把“AI 回招 emit”放在现有 `submit_move()` 的 await 过程中。
- 在计划里明确一种新的执行顺序，例如：
  - 新增 engine 专用 gateway 路径：`submit_engine_move()` 返回 AI move payload；gateway 先把人类手落到本地并确认，再注入/广播 AI 手。
  - 或者让 adapter 只负责 `genmove(proposed_moves)`，由 manager/gateway 统一提交本地人类手、更新 engine context、再提交 AI 手。
- Phase 2/3 必须增加一条集成测试：通过 gateway 落一手，人类手与 mocked AI 手最终在本地 session 中按 `[human, ai]` 顺序出现，且颜色正确。

### 2. board/kiosk 部署拓扑与现有代码不符，且“token 留服务端”方案没有可运行路径

Ref: plan.md §3 lines 72-75, Phase 5 line 127; review-request §6 A5/E14

计划写的是：adapter 与 `/api/v1/platforms/*` 跑在服务端，board/kiosk 通过现有 board-proxy 代理 `/api/v1/platforms/*` 到云端，token 不下发终端。

当前代码不是这样：

- `_init_platform_manager()` 在 server 和 board mode 都会注册本地 OGS/Fox/Golaxy adapter，见 `katrain/web/server.py:209-231` 和 board 初始化处 `server.py:455-456`。
- `board.py` 的 proxy 目前只覆盖 live/tutorial 等读接口；没有 `/api/v1/platforms/*` 代理，见 `katrain/web/api/v1/endpoints/board.py:107-145` 起的 live proxy。
- 本地 `/api/move`、`/api/state`、`/ws/{session_id}` 都在 board 进程内管理 session。如果 `/api/v1/platforms/golaxy/engine/start` 真在云端创建 session，board 本地并没有对应的 session/gateway/vision 状态。

Required change:

- 开工前先把部署拓扑写清楚，并配套任务：
  - Option A: engine game session 留在 board 本地，新增一个云端 Golaxy genmove proxy，只把 `moves/config` 发到云端换回 coord，星阵 token 存云端。这样 `/api/move`、vision、LED、WebSocket 都仍用本地 session。
  - Option B: 整个平台 session 都在云端，则必须代理/桥接 `/api/move`、`/api/state`、`/ws/{session_id}`、vision move submission 与 LED 引导所需事件，不只是 `/api/v1/platforms/*`。
- Phase 3/5 需要加入 board-mode 自动化或至少集成验证项，证明 chosen topology 下 session_id 属于正确进程，vision/gateway 对同一个 session 工作。

### 3. 星阵短信验证码登录当前没有 API 流程，Phase 4 才“确认可用”太晚

Ref: plan.md Phase 4 line 117, Phase 5 line 125, DoD line 173; review-request §6 E15

计划把“触发 SMS → 输码 → connect”写成前端 Phase 4 验证项，但当前后端登录 API 没有短信发送或短信登录分支：

- `PlatformLoginRequest` 只有 `username/password`，`platform_login()` 总是把第二个字段塞进 `auth_data={"password": ...}`，见 `katrain/web/api/v1/endpoints/platforms.py:22-24`、`74-76`。
- `GolaxyRestClient.login_sms()` 和 `request_sms_code()` 虽然存在，见 `katrain/web/platforms/golaxy/adapter.py:89-128`，但 `GolaxyAdapter.connect()` 没有调用短信登录。
- `PlatformConnectPage.tsx` 只是把 Golaxy 的第二个输入框标成“验证码”，然后调用通用 `platformLogin()`，见 `katrain/web/ui/src/kiosk/pages/PlatformConnectPage.tsx:28-31`、`60-66`。

Required change:

- 把短信登录移到 Phase 1/2 后端任务，而不是 Phase 4 手测：
  - `POST /{platform}/sms/request` 或 Golaxy 专用 endpoint；
  - login request 支持 `auth_method=sms_code` 或 Golaxy adapter 识别 `sms_code`；
  - adapter `connect()` 覆盖 password、sms_code、refresh_token 三条路径；
  - Token 刷新后的 `auth_data` 要持久化，否则长局/重连会退化。
- 添加后端 mock 测试和前端 component/API 测试。DoD 中“手机号登录成功”才可验证。

### 4. `PlatformMove` 不带 `game_id`，当前扫描 active games 会把 AI 回招路由到错误对局

Ref: plan.md Phase 3 line 109; review-request §6 A3

计划把 `_on_opponent_move` 扫描 active games 视为“单局 OK；如需可让 PlatformMove 带 game_id”。这不应再留到“如需”。当前模型中 `PlatformMove` 只有 `col,row,color,move_number`，见 `katrain/web/platforms/models.py:57-62`；manager 收到对手手后扫描第一个 `PLAYING` context，见 `katrain/web/platforms/manager.py:141-162`。

Golaxy engine-play 会在 adapter 内维护多个 synthetic game_id 的 context；即使产品 UI 暂时只开一局，server 进程也可能同时有 OGS/其他平台局或未来多 board 局。AI 回招一旦发到错误 session，就是直接污染棋谱。

Required change:

- Phase 2/3 直接把 `game_id` 加进 `PlatformMove`，或新增 `PlatformEvent` 包装，manager 按 `game_id` 直接查 `_active_games[game_id]`。
- 更新 OGS adapter emit 处和相关 contract/gateway tests。
- 不建议在新 engine-play 中继续依赖扫描。

### 5. engine context 的唯一真状态仍只在内存，恢复策略必须明确

Ref: plan.md §3 line 65, Phase 2 lines 99-106, Risks §8; review-request §6 A4/E15

Golaxy 隧道无状态意味着 KaTrain 的 `moves` 与 config 是唯一真状态。计划目前只说 adapter 内维护 `{moves, config}`，没有说明页面刷新、WebSocket 重连、SessionManager cleanup、进程重启、adapter disconnect/reconnect 后如何恢复。

页面刷新在当前 session 仍存活时可能没问题，但只要 platform context 丢失而本地 KaTrain game 还存在，下一手就无法构造完整 Golaxy history。server/board 重启后更是完全无法恢复。

Required change:

- 在 Phase 2/3 明确本期策略：
  - 最小可接受：从本地 KaTrain session game tree 重建 Golaxy coord list，并在 reconnect/refresh 路径测试；server 重启不恢复则要明确写入 non-goal 和 UX。
  - 更稳妥：持久化 `{synthetic_game_id, session_id, moves, config, status, last_ai_coord}`，每手成功后更新；start/reconnect 可恢复未完成 engine game。
- DoD 增加“刷新页面/重连后继续落子不会丢 moves history”。如果 server 重启不支持，也要在风险和 UX 中明确。

---

## 🟡 Important

### 1. timeout / retry 需要以“不可变 proposed_moves + 明确 pending 状态”设计

Ref: plan.md Phase 1 line 94; review-request §6 B5

Golaxy genmove 协议本身是无状态的，同一份完整 history 可以再次请求；真正危险的是本地 context 在请求前被提前 mutate，或超时后 UI/vision 继续提交下一手。

建议在计划中写明：

- 调用前构造 `proposed_moves = current_moves + [human_coord]`，不要先写入 canonical `moves`。
- 只有拿到合法 AI coord 后一次性 commit `moves = proposed_moves + [ai_coord]`。
- 超时后不要自动进入下一手；session 标记为 `engine_error` / `waiting_retry`，pending human move 的 UX 明确。
- 如果允许手动 retry，retry 使用同一份 `proposed_moves`，并防止再次 append human move。
- 测试覆盖 timeout 后 moves 不变、手动 retry 后只 append 一次人类手。

### 2. `code != "0"`、401、风控、非法 moves 需要错误分类和 token refresh 测试

Ref: plan.md Phase 1 line 94, Risks §8 line 165; review-request §6 B6/B8

Token 生命周期现在只是风险项，不是实施项。建议 Phase 1/2 明确 `engine_genmove` 的错误模型：

- 401/认证失效：refresh token 后重试一次，并 emit/persist new auth data。
- `code != "0"`：至少分成 auth、rate-limit/retryable、bad-history/fatal、unknown fatal。
- 网络错误/超时：进入 pending/error 状态，不吞掉异常。

当前 `PlatformManager._on_token_refreshed()` 只是 log，未保存新 token；如果计划依赖 token 持久化，需要补 manager/credential store 测试。

### 3. PASS / AI resign / invalid coord 必须防御性处理

Ref: plan.md Phase 1 line 94, Phase 5 line 126; review-request §6 B7

UI 禁用 human pass 不能防住 AI 主动 pass/resign 或协议返回特殊 coord。`golaxy_to_katrain()` 应该验证 `0 <= coord < board_size * board_size`；特殊值返回 typed result，例如 `Move | Pass | Resign | UnknownSpecialCoord`，adapter 决定 broadcast pass、结束对局或进入 fatal error。不要把负数/361 直接交给 `session.katrain("play")`。

同时 `/api/move` 的 pass 入口仍存在，engine game 的 `submit_pass` 应该明确 reject 或实现；只做前端隐藏不够。

### 4. 前端流程不能复用现有 lobby 入口，需要 engine-play capability

Ref: plan.md Phase 4 lines 116-120; review-request §6 D11/E13

当前 `PlatformConnectPage` 对所有已连接平台都导航到 `/kiosk/play/cross-platform/lobby?platform=...`。Golaxy engine-play 不是 users/challenges/automatch 流程；如果只是去掉 `comingSoon`，用户会进入一个不适用的 lobby。

建议新增 capability，例如 `supports_engine_play` 与 `engine_levels`：

- 后端 `list_platforms()` 返回 engine-play 能力。
- Golaxy connected card 显示“人机对弈/选择级别”入口，直接去 engine setup。
- OGS 仍走 lobby/challenge。
- 39 级表建议由后端 `GET /{platform}/engine/levels` 提供，前端只消费结构化数据；这样协议常量与 adapter 保持同源。

### 5. start_engine_game 必须配置本地 KaTrain session，而不只是创建 multiplayer session

Ref: plan.md Phase 3 lines 108-112

`create_multiplayer_session()` 当前只创建默认 session 并设置玩家名；计划传入的 `board_size, komi, rule, handicap, human_color` 没有明确如何应用到 KaTrain 本地 game。若未来 UI 暴露非默认 komi/rule/handicap，Golaxy 请求参数与本地棋局会不一致。

建议 Phase 3 加任务：

- 创建 session 后立即应用 board size、komi、rules、handicap，并写入玩家名/颜色。
- 如果本期只支持 19 路、Chinese、7.5、handicap=0，就在 request schema 中限制并测试 400，而不要给 UI/endpoint 暴露未实现配置。
- human 执白时，AI 首手必须在返回 session 前落进本地 session，并更新 engine moves/context 与初始 state。

### 6. resign/cleanup 路径需要关闭 PlatformManager context

Ref: plan.md Phase 2 line 102, Phase 3 line 112

gateway `resign()` 调 adapter 后只做本地 `session.katrain("resign")`；如果 adapter 只删除自己的 engine context，`PlatformManager._active_games` / `_session_to_game` 仍会把 session 视为 platform game。计划应要求：

- engine resign 后调用/emit game ended，或 gateway/manager 显式 `end_platform_game()`。
- 测试 resign 后再次 `/api/move` 不再走已删除的 engine context，且前端收到 game-ended/finished 状态。

### 7. 测试策略应补三类集成测试

Ref: plan.md §6; review-request §6 C9

现有测试层次还不够覆盖上述风险。建议新增：

- Gateway/manager/adapter 顺序测试：人类手先落、本地 state 更新、AI 手随后落，move_number 正确。
- Board-mode topology 测试：按最终拓扑验证 platform start/move 所在进程与 session 所在进程一致；若走 cloud proxy，验证 auth header/token 不到 terminal。
- 前端路由测试：Golaxy card 登录后进入 engine setup，不进入 lobby；SMS request/login 成功路径；kiosk-2d build 中没有 galaxy/three 引入。

---

## 🟢 Minor / Nit

### 1. 坐标边界用例再补完整

Ref: plan.md Phase 1 lines 89-96; review-request §6 C10

除 9 手实盘金标准外，建议显式测试：

- 四角：A19=0、T19=18、A1=342、T1=360。
- 天元/中心：K10=180（按跳过 I 的列编码 K=9）。
- 越界：col/row/coord 越界抛明确异常。

### 2. 协议常量建议放 `golaxy/engine_client.py` 或 `engine.py`

Ref: plan.md Phase 1 lines 92-94, Files §5

`adapter.py` 已经包含 auth 和 gameroom REST。engine tunnel 的参数、level table、coord result 类型会继续增长，单独文件更利于测试，也避免把人人对弈和 engine-play 逻辑混在一个大 adapter 文件中。

### 3. `supports_live_play=True` 的语义需要拆分

Ref: plan.md Phase 2 line 103

Golaxy engine-play 可玩，但不是传统 live platform game；`supports_live_play` 现在会被前端解释为“实时对弈”。建议新增 `supports_engine_play`，不要用 live/rooms/automatch flags 暗示 engine 功能。

---

## ❓ Questions

1. 最终部署到底是“board 本地维护 KaTrain session，云端只代理 Golaxy genmove”，还是“云端维护整局 platform session”？这会决定 Phase 3/5 的核心实现。
2. 本期是否真的要暴露 komi/rule/handicap/board_size 设置？如果不是，建议 request schema 限死默认值，减少协议未知面。
3. server 重启恢复是否是本期 DoD？如果不是，请在 Non-goals 和 UX 中明确用户会丢失未结束的人机局。
4. Golaxy 账号 token 是按 KaTrain 用户持久化，还是按 kiosk 设备/场馆持久化？这影响 board 模式 proxy、credential store、审计和退出登录行为。

---

## Suggested Plan Edits Summary

Before implementation, I would update `plan.md` in this order:

1. Rewrite §3 engine-play sequence so AI move is injected only after local human move is applied.
2. Choose and document the board/cloud topology; add concrete proxy or local-session tasks.
3. Move SMS login/token persistence/refresh into backend Phase 1/2 with tests.
4. Add `PlatformMove.game_id` and direct manager lookup in Phase 2/3.
5. Add context recovery/persistence policy and DoD coverage.
6. Add engine capability/levels endpoint and route Golaxy UI to engine setup, not lobby.
