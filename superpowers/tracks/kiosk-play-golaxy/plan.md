# Plan: Kiosk 跨平台对弈 — 星阵围棋 (Golaxy) 人机对弈接入

> Branch: `feature/kiosk-play-golaxy` · Worktree: `/Users/fan/Repositories/katrain-kiosk-play-golaxy`
> Protocol reference: [`golaxy-protocol.md`](./golaxy-protocol.md) (same folder — read it first)
> Status: ready to execute · Written 2026-07-02 after full live protocol capture
> **Revised 2026-07-02** after external plan review (Codex + Gemini, see [`review-feedback-codex.md`](./review-feedback-codex.md) / [`review-feedback-gemini.md`](./review-feedback-gemini.md)); 采纳记录见 §10。

---

## 1. Goal (本期范围)

让 kiosk「跨平台对弈」页面里的**星阵围棋卡片从「即将支持」变为可用**，并跑通**人机对弈 (vs 星阵 AI bot)** 的完整闭环：

```
用户在 KaTrain kiosk 选星阵 bot + 级别 → 在智能棋盘/kiosk 落子
  → KaTrain 后端调星阵 genmove 隧道 → 拿到 AI 回招 → 显示在棋盘 (并可 LED 引导)
```

**本期只做人机对弈 (自由对弈 / 不计时)。** 人人对弈、升降级对弈、联棋、高水平对弈、计时、数子/终局判定均**不在本期范围**。

### Non-goals（明确不做）
- 人人对弈 (gameroom / STOMP)。星阵 adapter 里已有的 `/api/social/wsgame/*` 路径**不动**。
- 计时对弈（本期固定 `不计时`，`countTime=0`）。
- 服务端数子/胜负判定（终局先只支持 `放弃/resign` 与自然停手；数子判定留后续）。
- **PASS**（人类侧 UI 禁用 + 后端显式拒绝；AI 侧特殊 coord 做防御性终局处理，见 Phase 1）。
- **服务重启后恢复未完人机局**。KaTrain 所有 web session 本就是内存态，重启丢所有本地对局；人机局不做超出产品基线的 DB 持久化。页面刷新/WS 重连场景**必须**可恢复（见 §3.2）。
- **非默认棋局配置**。本期固定 19 路 / chinese / komi 7.5 / handicap 0（与实盘验证一致），用户只选 bot 级别 + 执黑/白。request schema 对其它值直接 422/400，不给 UI 暴露未验证的协议面。
- 野狐 (fox)、OGS 的功能改动（`PlatformMove.game_id` 这类共享模型变更除外，OGS emit 处同步适配 + 测试保绿）。
- 3D 棋盘 / galaxy（kiosk 构建禁止引入，见 §7 构建边界）。

---

## 2. Key facts already verified (不要重新调研)

来自 2026-07-02 实盘抓包（详见 `golaxy-protocol.md`）：

1. **人机对弈是无状态 REST 隧道**，不是 WebSocket、没有服务器端 gameId、不需要星阵授权：
   ```
   GET https://api.19x19.com/api/engine/dcnn/tunnel/genmove
     Header: Authorization: bearer <access_token>   # 2026-07-03 真机更正（旧记录的 Auth_token 会被拒 6003）；另需浏览器 Origin/Referer/UA
     Query: moves=<CSV of coord ints>&board_size=19&boardSize=19&komi=7.5
            &rule=chinese&handicap=0&level=<eloScore>&style=555559&elodiff=0
            &resign=6&org=golaxy_web&context_name=ai_game_player
   → {"code":"0","msg":"","data":{"coord":<int 0-360>,"prob":<float>}}
   ```
   **无状态 ⇒ 用同一份完整 moves 重发请求是安全的**（服务端没有对局状态可污染）；危险的只有本地状态被提前修改。这是 §3.1 提交纪律的依据。
2. **坐标编码**：`coord = (19 - boardRow) * 19 + colIndex`，`colIndex` = 0..18 从左到右（A=0,…,H=7,J=8(跳过I),…,T=18），`boardRow` = 1..19（19 在最上）。等价于「从左上角起、先行后列的 0..360 序号」。反解：`row = 19 - floor(coord/19)`，`col = coord % 19`。
   - 实盘金标准 9 手 + 反解 2 例见 `golaxy-protocol.md` §3；另按公式推得边界值：**A19=0, T19=18, A1=342, T1=360, K10(天元)=180**，一并入单测。
3. **`level` 参数 = bot 的 `eloScore`**（星铠虾1级=1100）。完整 39 级表见 `golaxy-protocol.md`。
4. **鉴权**已在 `katrain/web/platforms/golaxy/adapter.py` 实现（手机号 OAuth2：密码 / 短信验证码 / refresh_token），REST client 层**已验证可用**。⚠️ 但 **adapter/端点/前端尚未把短信登录接线**：`GolaxyAdapter.connect()` 只走 token→refresh→password；`PlatformLoginRequest` 只有 username/password；前端只是把输入框改名为「验证码」。SMS 打通是本期**后端任务**（Phase 2/3），不是前端手测项。
5. 星阵的社交 WS (`wss://ws.19x19.com/.../WS_STOMP_ENDPOINT_GOLAXY`) **只负责在线状态/心跳**，与人机着手无关。

### 尚未抓到、需要在开发中补的两个小数据
- **PASS 的 coord 编码**（本期不支持人类 pass；但解码端必须防御 AI 返回特殊值，Phase 5 实测补抓）。
- **`resign=6` 的确切语义**（观测值为 6；疑似认输/让子边界。先原样透传，功能正常即可）。

---

## 3. Architecture decision（怎么把「人机局」装进现有中继管线）

现有跨平台对弈已有完整脚手架（OGS 端到端跑通）：
- `katrain/web/platforms/base.py` — `PlatformAdapter` 抽象（`connect`/`submit_move`/`on_opponent_move` 事件流）
- `katrain/web/platforms/manager.py` — `PlatformManager.start_platform_game()`（只认一个带 gameId 的 `PlatformGameSession`）
- `katrain/web/platforms/gateway.py` — `PlatformCommandGateway`（棋盘落子 → 提交远程 → ACK → 本地落子，**remote-first**）
- `katrain/web/api/v1/endpoints/platforms.py` — REST 端点
- 前端 `katrain/web/ui/src/kiosk/pages/PlatformConnectPage.tsx`（golaxy 现被 `comingSoon:true` 挡住；已连接平台一律进 lobby）

**核心设计：人机局 = 一个「KaTrain 本地对局 + 星阵引擎作为对方」的会话**，用**合成的本地 game_id**（星阵没有 gameId）标识。

### 3.1 Engine-play 调用时序（⚠️ 评审修订：不复用 `on_opponent_move` 中继）

> 原方案「`submit_move` 内同步 emit `opponent_move`」与现有代码时序冲突：gateway 是 remote-first（`gateway.py:49-66`，adapter 返回成功后才 `_local_play` 人类手），而 `_on_opponent_move` 收到回调**立即**落子（`manager.py:141-150`）。若在 `submit_move` await 期间 emit，AI 手会先于人类手落进本地对局，棋谱顺序与颜色全错。**废弃该方案。**

修订后的时序 —— **engine-play 走独立方法，AI 手作为返回值而非事件**：

- Adapter 新增 `submit_engine_move(game_id, col, row) -> PlatformMove | GolaxyGameEvent`（不叫 `submit_move`，不做 game_id 魔法分流；现有人人对弈 `submit_move` 语义不动）。
- Gateway 的 `play_move` 对 engine context 走新分支（按 `ctx.is_engine` 标志判断）：
  1. `ctx.set_pending("move")` + broadcast pending；
  2. adapter 内部：`proposed_moves = list(ctx_moves) + [encode(human)]`（**不可变副本，canonical moves 不先写**）→ 调隧道 → 成功后一次性 commit `moves = proposed_moves + [ai_coord]`，返回解码后的 AI `PlatformMove`；
  3. gateway 顺序落子：`_local_play(human)` → broadcast confirmed(human) → `_local_play(AI)` → broadcast confirmed(AI)；
  4. 任何一步失败：clear pending + broadcast rejected，**本地与 adapter context 均不产生半提交状态**。
- **超时/重试纪律**：隧道无状态 ⇒ 用同一份 `proposed_moves` 重试安全。策略 = 超长 read timeout（高级别 bot 思考慢，暂定 180s，Phase 5 实测校准）+ 失败后自动重试 1 次（同一 `proposed_moves`）+ 仍失败则 session 进入 `engine_error` 状态并广播，UI 提示可手动重试或放弃对局。**禁止**在未拿到合法 AI coord 时接受下一手人类落子（pending 机制已保证）。
- 人类执白：`start_engine_game` 创建后立即用空 moves 调一次 genmove，AI（黑）首手**落进本地 session 后**才返回 session_id。

这样 manager / 前端棋盘仍然只看到「我方落子 → 对方落子回来」的既有广播消息（`platform_move_pending/confirmed/rejected`），改动集中在 gateway 一个新分支 + adapter 新方法。

### 3.2 状态与恢复（评审修订：明确唯一真状态）

- **唯一可靠真状态 = 本地 KaTrain session 的 game tree**。adapter 的 engine context `{moves: list[int], config, status}` 只是运行时缓存。
- **重建规则**：context 丢失/不一致而 session 还在时（页面刷新、WS 重连、adapter reconnect），从 session game tree 主线重建 golaxy moves 列表（编码为 coord 序列）。Phase 2 提供 `rebuild_moves_from_game(session)` 并测试。
- 页面刷新/重连后继续落子**不丢历史**是本期 DoD；服务重启恢复是 non-goal（见 §1），UI 无需特殊处理（重启后 session 本身已不存在）。

### 3.3 运行位置（server vs board 模式）（⚠️ 评审修订：原「board-proxy 代理 + token 留云端」前提不成立）

> 核对代码：`_init_platform_manager()` 在 **server 与 board 两种模式都本地注册 adapter**（`server.py:206` / `server.py:456`），board 的 `/api/move` 直接走本进程 gateway；`board.py` 的 proxy 只覆盖 live/tutorial 读接口，**不存在** `/api/v1/platforms/*` 代理。原计划设想的「board-proxy 转发 platforms、token 不下发终端」没有可运行路径。

**本期拓扑（修订决定）：跟随现有架构 —— 平台栈在服务 kiosk 的进程内本地运行。**
- server 模式（`--ui web`）：adapter/gateway/session 全在 web server 进程（开发与主要验证路径）。
- board 模式：adapter/gateway/session 全在 board 进程（现状已如此），星阵 token 经既有 `PlatformCredentialStore` 按 KaTrain 用户存在**设备端**。`/api/move`、vision、LED、WebSocket 全部沿用本地 session，零新增代理。
- **后续硬化项（本期不做，列入 §8）**：若要求 token 不落终端，再加「云端 genmove 代理」（board 只发 `moves/config` 换回 coord，星阵凭证存云端）。
- ⚠️ **此决定与最初计划意图（token 留服务端）相反**，依据是现有代码拓扑 + 本期「技术打通」目标。Phase 0 review checkpoint 需与人确认。

---

## 4. Implementation phases

> 执行方式：配合 `superpowers:executing-plans`，每个 Phase 结束有 **Verification**（自动化优先）+ **Review checkpoint**（停下来给人 review）。尽量 TDD：先写测试再写实现。

### Phase 0 — 环境与基线确认
- [ ] 在 worktree 里 `uv sync`；`CI=true uv run pytest tests` 跑通现有测试（建立绿色基线）。
- [ ] 阅读 `golaxy-protocol.md` 与 `katrain/web/platforms/{base,manager,gateway}.py`、`golaxy/adapter.py`、`ogs/adapter.py`（OGS 是完成度最高的参考）。
- **Verification**: 基线测试全绿；能说清 OGS 从「accept challenge → start_platform_game → 落子中继 → on_opponent_move 广播」的完整链路。
- **Review checkpoint**: 与人对齐 §3 三个修订决定（engine 时序、状态恢复、**board 全本地拓扑/token 在设备端**）无异议再继续。

### Phase 1 — 坐标编解码 + genmove 客户端（纯函数，TDD）
- [ ] `katrain/web/platforms/golaxy/coords.py`（新）：`katrain_to_golaxy(col,row,board_size) -> int` 与 `golaxy_to_katrain(coord, board_size) -> GolaxyCoordResult`。
  - 解码返回 **typed result**（`Move(col,row) | Pass | Resign | UnknownSpecial(raw)`），越界/负数/361+ 不抛裸坐标给上层——**绝不**把未验证值直接交给 `session.katrain("play")`。PASS/RESIGN 特殊值本期按 UnknownSpecial 处理→对局进入 error/finished 并广播（Phase 5 实测后再细化）。
  - 单测金标准：实盘 9 手对照（Q16→72, Q4→300, D4→288, D16→60, Q10→186, R6→263, D10→174, C6→249, K4→294）+ 反解 249→C6, 286→B4 + 边界（A19=0, T19=18, A1=342, T1=360, K10=180）+ 越界抛明确异常。
- [ ] `katrain/web/platforms/golaxy/engine_client.py`（新，协议常量/级别表/错误分类与 gameroom 逻辑分离）：`engine_genmove(moves: list[int], *, level, komi, rule, handicap, board_size) -> GenmoveResult`。
  - 组 query（含 `style=555559, elodiff=0, org=golaxy_web, context_name=ai_game_player, resign=6, boardSize/board_size`），带 `Authorization: bearer <token>` header + 浏览器 Origin/Referer/UA（2026-07-03 真机更正），GET 隧道。
  - **错误分类**（typed exceptions）：`AuthExpired`（HTTP 401，**或 200-body `code=6003 msg="invalid token"`** → 上层触发 refresh 后重试一次）/ `Retryable`（网络错误、超时、疑似限流）/ `Fatal`（其它 `code != "0"`、响应结构异常）。不吞异常。
  - 39 级表作为模块常量（`eloScore/levelName/name/goalDifference/timing`），供 levels 端点使用。
- **Verification**: `uv run pytest tests/platforms/…golaxy…` 全绿；respx/httpx mock 断言拼出的 URL 与实盘一致（参数名、值正确，顺序无关）；错误分类各分支有测试。
- **Review checkpoint**: 展示编解码对照表、typed result 设计与 mock 出的请求。

### Phase 2 — Adapter engine-play 方法 + 本地 game context + SMS/token 接线
- [ ] `GolaxyAdapter` 新增（**不改**现有人人对弈 `submit_move` 语义）：
  - `start_engine_game(config) -> PlatformGameSession`（合成 local game_id；context={moves:[], config, status}；human 执白则先 genmove 一手，AI 首手随 session 返回）。
  - `submit_engine_move(game_id, col, row) -> PlatformMove`：按 §3.1 的 proposed_moves 纪律实现；内部包 token refresh（收到 `AuthExpired` → `refresh_access_token()` → 重试一次 → 仍失败 emit `auth_expired`）。
  - `rebuild_moves_from_game(session)`：从 KaTrain game tree 主线重建 moves（§3.2）。
  - `resign_engine_game(game_id)`：删除本地 context 并 **emit `game_ended`(game_id, result, winner)**，让 manager 走既有 `_on_game_ended` 清理 `_active_games`/`_session_to_game` 并广播 finished（不能只删 adapter 侧 context）。
  - capability：`supports_engine_play = True`（**新 flag**，加在 `base.py`，默认 False；不复用 `supports_live_play` 暗示 engine 能力）+ `get_engine_levels() -> list[dict]`。
- [ ] `PlatformMove` 加 `game_id: str` 字段（`models.py`）；`manager._on_opponent_move` 改为 `self._active_games.get(move.game_id)` 直查，**删除扫描逻辑**；同步更新 OGS adapter 的 emit 处与 `tests/platforms/test_adapter_contract.py`、`test_gateway.py`。
- [ ] SMS 登录接线（adapter 层）：`GolaxyAdapter.connect()` 增加 `auth_data["sms_code"]` 分支（调已有 `login_sms(phone, code)`）；成功后 emit `token_refreshed`。
- [ ] Token 持久化：`manager.connect_platform` 记录 platform→user_id；`_on_token_refreshed`（当前只打日志，`manager.py:212-213`）改为把 new_auth_data merge 回 `PlatformCredentialStore` 保存 —— 否则长局中 refresh 后的 token 只在内存，重连即退化。
- **Verification**: adapter 单测（mock `engine_genmove`）：moves 累积/提交纪律（失败不半提交、重试同一份 proposed_moves 只 append 一次人类手）、执白开局 AI 先手、401→refresh→重试链路、resign 后 emit game_ended、rebuild_moves 与 game tree 一致；PlatformMove.game_id 直查路由测试（两个并发 context 各收各的手）。
- **Review checkpoint**: 确认 adapter 状态机（moves 累积、颜色、commit 时机、错误分支）。

### Phase 3 — Manager / Gateway 接线 + REST 端点
- [ ] `manager.py`：`start_engine_game(platform, config, user_id) -> session_id`：
  - `create_multiplayer_session`（bot 名从级别表取，如 `[星阵] 星铠虾·1级`）后**显式初始化对局参数**：19 路、chinese、komi 7.5、handicap 0、玩家颜色/名字（`create_multiplayer_session` 现只设玩家名，不配棋局——不能默认它与星阵参数一致）。
  - 注册 `PlatformGameContext`（加 `is_engine: bool` 字段），remote_game_id = 合成 id。
- [ ] `gateway.py`：`play_move` 增加 engine 分支（§3.1 时序）；`pass_move` 对 engine context **显式拒绝**（`PlatformMoveRejectedError("pass_not_supported")`——前端隐藏不够，`/api/move` 的 pass 入口仍在）；`resign` 走 `resign_engine_game`。
- [ ] `katrain/web/api/v1/endpoints/platforms.py` 新增：
  - `POST /{platform}/sms/request`（body: phone）→ adapter `request_sms_code`（无此能力的平台 400）。
  - `PlatformLoginRequest` 加可选 `sms_code` 字段；有值时 `auth_data={"sms_code":...}` 走 SMS 分支。
  - `POST /{platform}/engine/start`（body: **只有** `level: int` + `human_color: "B"|"W"`；komi/rule/handicap/board_size 本期不收，schema 外字段 422）→ 返回 session_id + 初始盘面（含执白时 AI 首手）。
  - `GET /{platform}/engine/levels` → adapter 级别表（前端不硬编码 39 级）。
  - `GET /status` 返回体加 `supports_engine_play`。
- **Verification**: FastAPI TestClient（mock 隧道）：start → 落一手 → 本地 session 中 `[human, ai]` **顺序与颜色正确**（Codex Blocking 1 的回归测试，必须有）；pass 被拒；resign 后 context 清理、再落子不走 engine 路径且前端收到 finished；SMS request/login 成功路径；`CI=true uv run pytest tests` 全绿。
- **Review checkpoint**: 用 curl/httpx 脚本对着 mock 跑通一整局若干手。

### Phase 4 — 前端 kiosk：开放星阵 + 人机设置/对局 UI
- [ ] `PlatformConnectPage.tsx`：去掉 golaxy 的 `comingSoon:true`；登录框加「获取验证码」按钮（调 `/sms/request`，含倒计时防重发）；**已连接的星阵卡片不进 lobby**（现有代码对所有已连接平台一律 `navigate('…/lobby')`）——按 `supports_engine_play` 显示「人机对弈」入口，导航到 engine setup；OGS 仍走 lobby。
- [ ] 人机设置页（新 `src/kiosk/pages/PlatformEngineSetupPage.tsx`，参考 `AiSetupPage.tsx`）：bot/级别选择器（数据源 = `GET /{platform}/engine/levels`），执黑/白选择；komi/规则作为固定信息展示（chinese 7.5，不可改）。
- [ ] 对局页：调用 `POST …/engine/start`，之后走既有跨平台对局落子/显示组件；AI 回招通过既有 `platform_move_confirmed` 消息渲染；pass 按钮对 engine 局隐藏/禁用；`engine_error` 状态提示重试/放弃。
- [ ] `src/api.ts`：加 sms/request、engine/start、engine/levels 调用与类型。
- **Verification**: `npm run build` **和** `npm run build:kiosk-2d` **都绿**（§7）；前端测试：golaxy 卡片登录后进 engine setup 而非 lobby；Playwright/手测：登录 → 选星铠虾1级 → 开局 → 落子 → 看到 AI 回招。
- **Review checkpoint**: kiosk 界面走查（含「即将支持」已移除、级别选择正确映射 level、SMS 流程可用）。

### Phase 5 — 端到端真机验证（用真账号，一次性）
- [ ] server 模式本机：真实登录星阵（手机号+验证码，走**本项目 UI** 的 SMS 流程），选星铠虾1级，下 3–5 手，核对 KaTrain 显示的 AI 手 == 星阵 App 同局的手（用同账号在浏览器旁证）。**顺带校准 genmove 实测耗时上界**（高级别 bot 也试一手），回填 §3.1 的 timeout 值。
- [ ] 刷新页面/断开 WS 重连后继续落子，验证 §3.2 重建路径。
- [ ] 抓 PASS/AI 认输行为：故意下到 AI 可能 pass/resign 的局面（或让 AI 大优后 resign 参数生效），记录特殊 coord 值，回填 `golaxy-protocol.md` 与解码器。
- [ ] board 模式：在 board 进程本地验证 platforms 端点/登录/开局/落子全链路（§3.3 全本地拓扑，无代理）。
- **Verification**: 真机一局连续正确；刷新恢复正确；两套构建绿；`pytest` 绿。
- **Review checkpoint**: 决定合并策略（见 `superpowers:finishing-a-development-branch`）。

---

## 5. Files to touch (预估)

**后端**
- `katrain/web/platforms/golaxy/coords.py`（新：编解码 + typed result）
- `katrain/web/platforms/golaxy/engine_client.py`（新：隧道 client + 错误分类 + 39 级表常量）
- `katrain/web/platforms/golaxy/adapter.py`（engine-play 方法、SMS connect 分支、engine context、rebuild、resign→game_ended）
- `katrain/web/platforms/base.py`（`supports_engine_play` flag + engine 方法签名）
- `katrain/web/platforms/models.py`（`PlatformMove.game_id`、`PlatformGameContext.is_engine`）
- `katrain/web/platforms/manager.py`（`start_engine_game`、`_on_opponent_move` 直查、`_on_token_refreshed` 持久化）
- `katrain/web/platforms/gateway.py`（engine 分支时序、pass 拒绝、resign 清理）
- `katrain/web/platforms/ogs/adapter.py`（emit 处补 game_id，行为不变）
- `katrain/web/api/v1/endpoints/platforms.py`（sms/request、engine start/levels、login 加 sms_code、status 加 capability）
- `katrain/web/platforms/golaxy/PROTOCOL.md`（补 engine-play 段，或指向本 track 的 `golaxy-protocol.md`）
- 测试：`tests/platforms/`（coords、engine_client 错误分类、adapter 状态机、gateway 顺序回归、端点 with mock、SMS 流程）

**前端**（均在 kiosk 共享 territory + `src/kiosk/`）
- `src/kiosk/pages/PlatformConnectPage.tsx`（去 comingSoon、SMS 按钮、engine-play 入口路由）
- `src/kiosk/pages/PlatformEngineSetupPage.tsx`（新）
- 对局页接线（复用现有跨平台对局组件；pass 禁用、engine_error 提示）
- `src/api.ts` / `src/api/`（sms/request、engine start/levels 调用）

---

## 6. Testing strategy
- **纯函数优先 TDD**：坐标编解码用实盘对照 + 推导边界值做金标准单测。
- **协议层用 mock**（respx/httpx mock）：不在 CI 打真星阵；断言请求 URL 参数 + 解析逻辑 + 错误分类各分支。
- **端点用 FastAPI TestClient** + mock adapter。
- **三类关键集成测试**（评审补充）：
  1. gateway→manager→adapter 顺序回归：经 gateway 落一手，本地 session 按 `[human, ai]` 顺序、颜色、move_number 正确；
  2. 多 context 路由：两个 active context 并存时 `PlatformMove.game_id` 直查不串局；
  3. 前端路由：golaxy 连接后进 engine setup 不进 lobby；kiosk-2d 构建无 three/galaxy 引入（CI 已有）。
- **真机验证只在 Phase 5 人工做一次**（需真账号 + 一次性验证码）。
- `CI=true uv run pytest tests` 必须全绿；`uv run black -l 120 katrain tests` 格式化。

## 7. SBC 构建边界（必须遵守，见根 CLAUDE.md）
- 本功能在 **kiosk 构建**里。前端只用 **shared territory + `src/kiosk/`**；**禁止**引入 three.js / `@react-three/*` / `src/galaxy/*` / `Board3D` / `VideoRecorder`。
- 改动任一 shared 文件后，**`npm run build` 与 `npm run build:kiosk-2d` 都要跑**（后者含 `verify:kiosk-2d` 反 three.js 检查）。
- CI `kiosk_build.yml` 会在 PR 上跑同样检查。

## 8. Risks / open questions
- **Token 在设备端**（§3.3 修订的直接后果）：board 模式下星阵凭证存 kiosk 本地 credential store。可接受性需 Phase 0 确认；后续硬化 = 云端 genmove 代理（board 不持 token）。
- **genmove 延迟未标定**：高级别 bot 思考时间未知；timeout 初值 180s，Phase 5 实测回填。期间 UI 有 pending 态，不会重复提交。
- **隧道是否校验 Origin/Referer**：服务端 httpx 可自设 header；Phase 1 mock 之外，Phase 5 真机确认一次。
- **PASS / AI 认输 / 终局 / 数子**：本期最小化（人类只有 resign + 自然停手；AI 特殊 coord → 防御性终局）。数子判定与 `resign=6` 语义留待后续。
- **速率限制 / 反爬**：真机验证时留意 429/风控；必要时加合理 UA 和节流（`Retryable` 分类已预留退避挂点）。
- **法律灰色**：无公开 API 条款（用户已明确本期只做技术打通，法律另议）。
- **多设备并发**：约定 KaTrain 为唯一输入端，开局后不要在星阵 App 同时落子。

## 9. Definition of done（本期）
- kiosk 星阵卡片可用（无「即将支持」）；**手机号 + 短信验证码经本项目 UI 登录成功**（后端 mock 测试 + 真机各一次）。
- 能选任一 bot 级别开一局人机（自由对弈/不计时），在 KaTrain 落子并正确收到 AI 回招，连续多手无误；**本地棋谱顺序/颜色有自动化回归测试**。
- **页面刷新 / WS 重连后可继续落子，moves 历史不丢**（服务重启恢复为明确 non-goal）。
- resign 后平台 context 正确清理，再落子回到本地语义，前端收到 finished。
- 单测 + 端点测试绿；两套前端构建绿；真机一局验证通过。

---

## 10. 评审采纳记录（2026-07-02，Codex + Gemini）

| # | 反馈 | 处置 |
|---|---|---|
| Codex 🔴1 / Gemini 🟡1 | submit_move 内 emit AI 手会落反棋谱顺序（已对照 `gateway.py:49-66`、`manager.py:141-150` 证实） | **采纳**：改为独立 `submit_engine_move` 返回 AI 手，gateway 新分支控制落子顺序（§3.1）；加顺序回归测试（Phase 3） |
| Codex 🔴2 | board-proxy 不覆盖 platforms、两模式都本地注册 adapter，原拓扑前提不成立（已证实） | **采纳并修订决策**：本期 board 全本地、token 在设备端；云端 genmove 代理列为后续硬化（§3.3，Phase 0 需人工确认） |
| Codex 🔴3 | SMS 登录后端未接线，Phase 4 才验证太晚（已证实） | **采纳**：SMS 接线拆为 Phase 2（adapter）/ Phase 3（端点）/ Phase 4（UI）任务 + 测试；写入 DoD |
| Codex 🔴4 / Gemini 🟡2 | `PlatformMove` 无 game_id，扫描路由会串局（已证实） | **采纳**：本期直接加 `game_id` + manager 直查，OGS emit 同步适配（Phase 2） |
| Codex 🔴5 / Gemini 🔴1 | 状态唯一真状态在内存、恢复策略缺失 | **部分采纳**：唯一真状态 = 本地 game tree，moves 可重建，刷新/重连入 DoD；**拒绝 Gemini 的「必须 DB 持久化」**——KaTrain session 本就是内存态，服务重启丢所有本地对局，只给人机局做 DB 持久化超出产品基线（YAGNI），列为 non-goal（§3.2） |
| Gemini 🔴2 | 「超时后绝不能重试，否则 AI 多下一手」 | **结论采纳、论据修正**：隧道无状态，同一份 proposed_moves 重试是安全的（无服务端状态可污染）；真实风险是本地提前 mutate（Codex 🟡1 的框架正确）。采纳不可变 proposed_moves + 单一 commit 点 + 有限重试 + stalled/放弃 UX（§3.1） |
| Codex 🟡2 / Gemini 🟡3 | 错误分类 + token refresh 持久化（`_on_token_refreshed` 只打日志，已证实） | **采纳**：typed exceptions（Phase 1）、refresh 包装 + credential store 持久化 + 测试（Phase 2/3） |
| Codex 🟡3 / Gemini 🟡5 | PASS/AI resign/非法 coord 防御 | **采纳**：typed decode result、gateway pass 显式拒绝（Phase 1/3），Phase 5 实测补抓 |
| Codex 🟡4 / Gemini 🟡4 | engine-play capability + 后端 levels 端点，不进 lobby | **采纳**：`supports_engine_play` 新 flag、`GET /engine/levels`、卡片路由改造（Phase 2/3/4） |
| Codex 🟡5 | start_engine_game 须显式配置本地对局参数、限死 request schema | **采纳**（Phase 3；配置面收窄进 non-goals，回答 Codex ❓2） |
| Codex 🟡6 | resign 清理 manager context | **采纳**：resign → emit game_ended → 既有清理链路 + 测试（Phase 2/3） |
| Codex 🟡7 | 三类集成测试 | **采纳**（§6；board 拓扑测试按 §3.3 修订为全本地验证） |
| Codex 🟢1 / Gemini 🟢1 | 角/边/天元坐标用例 | **采纳**（边界值已按公式推导核验，§2/Phase 1） |
| Codex 🟢2 | 协议常量独立 `engine_client.py` | **采纳**（§5） |
| Codex 🟢3 | 不用 `supports_live_play` 暗示 engine 能力 | **采纳**（Phase 2） |
| Codex ❓1 | 部署拓扑二选一 | 已答：本期全本地（§3.3） |
| Codex ❓3 | 服务重启恢复是否 DoD | 已答：non-goal，明确写入 §1/§3.2 |
| Codex ❓4 | token 按用户还是按设备持久化 | 已答：沿用既有 credential store 按 KaTrain user_id 存储，board 模式即设备本地用户（§3.3） |
