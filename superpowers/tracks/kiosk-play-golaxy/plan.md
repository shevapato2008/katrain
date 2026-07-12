# Plan: Kiosk 跨平台对弈 — 星阵围棋 (Golaxy) 人机对弈接入

> Branch: `feature/kiosk-play-golaxy` · Worktree: `/Users/fan/Repositories/katrain-kiosk-play-golaxy`
> Protocol reference: [`golaxy-protocol.md`](./golaxy-protocol.md) (same folder — read it first)
> Status: **人机对弈闭环已上线并真机验证 (2026-07-03)** · 原计划 Phase 0–5 已实现 · Written 2026-07-02 after full live protocol capture
> **Revised 2026-07-02** after external plan review (Codex + Gemini, see [`review-feedback-codex.md`](./review-feedback-codex.md) / [`review-feedback-gemini.md`](./review-feedback-gemini.md)); 采纳记录见 §10。
> **2026-07-03 补记**：落子鉴权/记谱/凭证 5 项修复已完成并推送 → §11；下一步「补全自由对弈设置面板(开放贴目/规则/让子)」计划 → §12。

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

---

## 11. 2026-07-03 修复记录（已完成并推送 `feature/kiosk-play-golaxy`）

原计划 Phase 0–5 实现后，真机对弈暴露出「每手落子报 AI 连接出错」等一串问题。经真机变体矩阵定位并端到端验证，以下 5 项已修复、测试、提交、推送：

1. **genmove 鉴权 header（核心落子修复）**：隧道要 **`Authorization: bearer <access_token>` + 浏览器 `Origin`/`Referer`/`User-Agent`**。原计划/协议文档写的 `Auth_token: <token>`（raw/bearer、±浏览器头）实测**一律** HTTP 200 `code=6003 msg="invalid token"`，即便 token 全新有效。已改 `engine_client.py`；`golaxy-protocol.md` §1/§2 与本 plan §2 同步更正。
2. **`6003` / "invalid token" → `AuthExpired`**：星阵对失效/无效 token 返回 **HTTP 200 + body `code=6003`**（非 401），故 `_classify_response_code` 把 `code=="6003"` 或 msg 含 "invalid token" 归为 `AuthExpired`，触发 refresh 后重试一次（原来会误判 `Fatal`）。
3. **`record_multiplayer_game` 跳过合成对手 id（≤0）**：引擎 AI 记为 player `-1`，`users` 表无此行 → `ForeignKeyViolation` 回滚整个事务（连人类那行也丢）。改用 `_make_game(user_id)` 助手，`black_game/white_game` 仅在 id>0 时建，`canonical = black_game or white_game`。一次性覆盖全部 4 条记谱路径（`game_repo.py`）。
4. **`auth.py` 登出中途记谱**：原调用不存在的 `GameRepository.record_game()` → 每次登出必抛 `AttributeError`，记谱失败且跳过 session 清理。改走带守卫的 `record_multiplayer_game(...)`，并包 best-effort try/except，记谱失败不阻断 `remove_session`。
5. **Finding A — 连接时持久化真 token（kiosk 重启痛点）**：`connect_platform` 成功分支先设 `_platform_user_ids` + `_setup_callbacks`，再持久化「输入 auth_data merge 上 `adapter.get_auth_data()` 的真 access/refresh token」而非只存一次性 `sms_code`。新增 `GolaxyAdapter.get_auth_data`（薄委托 `GolaxyRestClient.get_auth_data`）；OGS 无此法 → 行为不变。服务重启后可用持久 token 自动重连，免重扫短信。

**测试**：`tests/platforms/test_golaxy_engine_client.py`（鉴权 header + `6003`→AuthExpired）、`test_engine_game_record.py`（SQLite `PRAGMA foreign_keys=ON` 的 FK 守卫，已验证判别性）、`test_manager_token_persist.py`（初次连接持久化真 token / 无 get_auth_data 时行为不变）。`CI=true uv run pytest tests/platforms` 全绿。

**真机实锤**：一局 19 手每手 genmove `HTTP 200` 无 6003；认输无 `ForeignKeyViolation`；面板贴目 7.5。

> 已知 4 个 `test_ai_game_autosave.py` 失败经 `git stash` 核验为**基线既有**（单人 AI autosave 路径，与本次改动无关），未修，另议。

---

## 12. 后续计划：补全「自由对弈」设置面板（开放 贴目/规则/让子）

> **REQUIRED SUB-SKILL**：用 `superpowers:subagent-driven-development` 逐任务执行，每任务后 spec+质量双评，末尾整支 review。Phase 0 是硬前提，先跑。

**Goal**：让 kiosk 人机（=星阵**自由对弈**）设置面板**对齐星阵真实配置**。**棋盘固定 19 路**。

> **SCOPE 更正（2026-07-03，依 `golaxy-protocol.md` §8.4 从星阵 app.js 提取的权威配置；v2 mockup 已发 Artifact 待批）**：星阵自由对弈在 19 路**唯一可调的是「让子」+「先手/颜色」+「对手等级」**；棋盘/规则/贴目/计时全固定。故本期 = **① 加「让子」下拉**（分先/让先/让2子…让9子；**komi 自动推导**：chinese 分先 7.5、让先 0、让N子 N）+ **② 颜色扩为 猜先/执黑/执白**。**删除**原计划的独立 komi 选择器与中/日规则选择器（19 路星阵只给中国规则，日本规则仅 13/9 路）。下方 Task 2a/2b/2d 按此口径执行（komi 不再是自由字段，而是 handicap 的函数）。

**背景/与 §1 的关系**：§1 曾把「非默认棋局配置」列为 non-goal（固定 19/chinese/7.5/0），当时为最小化未验证协议面。本节**有意开放**其中 komi/rule/handicap —— 因隧道本就接受这些参数（见下），且用户需要更完整的设置。棋盘 9/13 路仍 non-goal（物理 kiosk 是 19 路：361-LED、摄像头标定、`coords.py` 均按 19 写死）。升降级/联棋/高水平三个大类模式亦本期不做（§12 末）。

**为什么可行（已探明，勿重查）**：
- 隧道客户端 `engine_genmove(..., komi, rule, handicap, board_size)` **已是函数参数**并一路透传：`engine_client.py:118-128` → 适配器 `_call_genmove` 传 `ctx.config.*`（`adapter.py:562-570`）。只有 `style/elodiff/resign/org/context_name` 是写死常量。**隧道客户端与 `EngineGameConfig` dataclass 无需改动。**
- 收窄只在两处：前端只发 `{level, human_color}`（`PlatformEngineSetupPage.tsx:61`；类型 `api.ts:356-361`）；后端 `EngineStartRequest`（`platforms.py:32-50`）`extra="forbid"` 只放行 `level`+`human_color`。

### Global Constraints（每个任务都隐含遵守）
- **只暴露隧道确实接受的能力**：rule=japanese/korean、handicap 只在 chinese/分先 下验证过 → Phase 0 未验证通过的项**不上 UI**。
- **SBC 双构建**（根 CLAUDE.md §构建边界）：`api.ts` 属 shared territory，改后 `npm run build` **和** `npm run build:kiosk-2d`（含 `verify:kiosk-2d`）都要绿。前端只用 shared + `src/kiosk/`，禁 three/galaxy/Board3D。
- **i18n**：新文案一律走 `t("en","中文")`（`useTranslation`）。默认中文，禁日文。
- **凭证安全**：Phase 0 抓包务必 redact `Authorization`/`refresh_token`，勿写仓库或日志。
- **19 路固定**：棋盘在 UI 上是只读展示项，不发 `board_size`（沿用默认 19）。
- **勿回归**：§11 的 FK 守卫、token 持久化、6003 分类不能破。

### Phase 0 — 实测「自由对弈」真实可调面 ✅ 已完成（2026-07-03，真机 token 直打隧道，详见 `golaxy-protocol.md` §8）
**结论**：komi 完全生效；rule 中国✅/日本✅/**韩国❌(8008 拒绝)**；handicap = **塞 N 颗标准星位(黑)进 `moves` 开头 + 发 `handicap=N`**（空 moves 时 handicap 被忽略，不自动摆子），塞完轮白。让子局 komi 惯例 0.5。→ 三项全可实现，仅排除韩国规则。下方原始探查步骤保留作记录。

<details><summary>原始 Phase 0 探查步骤（已执行）</summary>
- [ ] 用**已持久化的 access token**（§11 Finding A 后凭证库已有真 token）写一个一次性探针脚本（放 scratchpad，勿入仓库），对 `genmove` 隧道逐一试：`rule=japanese`、`rule=korean`、`handicap=2..9`（chinese）各发一次，记录 `code`/`data.coord`/是否报错。**判定各项是否被隧道接受。**
- [ ] **让子语义**（最关键）：`handicap=4 & moves=[]` 发一次 → 看返回 coord 是否是「白对 4 子让子局的合理第一手」。据此判定：服务端**自动摆星位**（我们 `moves=[]` 即可、白先），还是需要**我们把 N 个让子点当黑开局塞进 `moves`**。若判不准，用 `/browse`（gstack，禁 `mcp__claude-in-chrome__*`）登录 19x19.com 自由对弈开一局让子，抓首个 genmove 请求的 `moves`/`handicap` 实值佐证。
- [ ] **komi 联动**：确认让子局 komi 取值（通常 0.5）、日/韩规则默认 komi（6.5）。
- **产出**：把结论写成一段「自由对弈参数对照」追加进 `golaxy-protocol.md`（新 §「自由对弈」）。
- **决策点**：某项无法干净支持（尤其让子需大改开局流）→ **就地回报请用户定夺，不硬塞**。**komi 是保底必成项**（低风险）。Phase 1+ 的 UI/校验集合以 Phase 0 结论为准。

</details>

### Phase 1 — 设计稿（mockup-first）✅ 已完成（v2 mockup 用户已确认 2026-07-03）
- [x] 自由对弈设置面板 mockup v2（仿星阵真实布局：规则行 棋盘·让子·贴目；棋手行 先手·计时；对手=等级），Artifact 已发、用户确认「v2可以」。删除了臆造的 komi 预设选择器。

### Phase 2 — 实现（确认口径；TDD，逐 Task）

> **口径（对齐星阵 app.js，见 §8.4）**：客户端只发 `level` + `human_color`(`"B"|"W"|"nigiri"`) + `handicap`(让子值：`0`=分先, `-1`=让先, `2..9`=让N子)。**komi/rule/board 服务端派生固定**：rule=chinese、board=19；komi = f(handicap)：分先→7.5、让先→0、让N子→N。让子实现 = 塞 N 颗标准星位(黑) + genmove 带 `handicap=N`（N=让子值≥2，否则 0）。`nigiri` 服务端随机定黑白。**不引入 komi/规则 选择器。**

**Interfaces（供各 Task 对齐；exact 值以此为准）**
- 让子值 → (stones, komi, name)：`0→(0,7.5,"分先")`, `-1→(0,0.0,"让先")`, `2→(2,2.0,"让2子")`, `3→(3,3.0)`, `4→(4,4.0)`, `5→(5,5.0)`, `6→(6,6.0)`, `7→(7,7.0)`, `8→(8,8.0)`, `9→(9,9.0,"让9子")`。合法集合 = `{-1,0,2,3,4,5,6,7,8,9}`（**无 1**）。
- 先手 `human_color`：`"B"`(执黑) / `"W"`(执白) / `"nigiri"`(猜先，服务端 `random.choice(["B","W"])`)。
- 19 路标准让子星位（Golaxy coord，供塞子）：
  ```
  D4=288 Q4=300 D16=60 Q16=72 D10=174 Q10=186 K4=294 K16=66 K10(天元)=180
  2子=[288,72]  3子=[288,72,300]  4子=[288,300,60,72]
  5子=[288,300,60,72,180]  6子=[288,300,60,72,174,186]
  7子=[288,300,60,72,174,186,180]  8子=[288,300,60,72,174,186,294,66]
  9子=[288,300,60,72,174,186,294,66,180]
  ```
- 塞子后**轮白**（Phase 0 §8.3 实测）；空手（分先/让先）轮黑。AI 开局条件统一：`side_to_move == ai_color`，其中 `side_to_move = "W" if stones>=2 else "B"`，`ai_color = "W" if human=="B" else "B"`。

**Task A — 后端请求模型 + komi/nigiri 派生**
- Files: Modify `katrain/web/api/v1/endpoints/platforms.py`（`EngineStartRequest` :32-50、`start_engine` 构造 config :173，import `random`）；Test `tests/platforms/test_platforms_engine_start.py`（新，现有 FastAPI TestClient 风格）。
- [ ] **写失败测试**：`EngineStartRequest` 接受 `{level, human_color, handicap}`；`handicap∈{-1,0,2..9}` 合法、`1/10/99` → 422；`human_color∈{"B","W","nigiri"}` 合法、其它 → 422。派生：`_komi_for_handicap(0)==7.5`、`(-1)==0.0`、`(4)==4.0`；`_resolve_color("B")=="B"`、`("nigiri")∈{"B","W"}`。端点构造出的 `EngineGameConfig`：`rule=="chinese"`、`board_size==19`、`handicap==stones`(让4子→4，分先/让先→0)、`komi==派生值`、`human_color==解析后`(nigiri 落到 B/W)。
- [ ] 跑测试确认失败。
- [ ] **实现**（保留 `extra="forbid"`）：
  ```python
  _VALID_HANDICAP = {-1, 0, 2, 3, 4, 5, 6, 7, 8, 9}  # 让子值；无 1

  def _komi_for_handicap(h: int) -> float:
      if h == 0:  return 7.5   # 分先 (chinese)
      if h == -1: return 0.0   # 让先
      return float(h)          # 让N子 -> komi N

  def _handicap_stone_count(h: int) -> int:
      return h if h >= 2 else 0  # 分先/让先无子

  class EngineStartRequest(BaseModel):
      """Human-vs-AI engine game request (Golaxy 自由对弈, 19-board, chinese).
      Client picks: level, 先手/颜色 (human_color), 让子 (handicap value).
      komi/rule/board_size are derived/fixed server-side (see §8.4)."""
      model_config = {"extra": "forbid"}
      level: int
      human_color: str = "B"   # "B" | "W" | "nigiri"
      handicap: int = 0        # 让子值: 0=分先, -1=让先, 2..9=让N子

      @field_validator("human_color")
      @classmethod
      def _color(cls, v):
          if v not in ("B", "W", "nigiri"):
              raise ValueError("human_color must be 'B', 'W', or 'nigiri'")
          return v

      @field_validator("handicap")
      @classmethod
      def _handicap(cls, v):
          if v not in _VALID_HANDICAP:
              raise ValueError(f"handicap must be one of {sorted(_VALID_HANDICAP)}")
          return v
  ```
  端点 `start_engine`（:173）：
  ```python
  import random  # module top
  color = random.choice(["B", "W"]) if req.human_color == "nigiri" else req.human_color
  config = EngineGameConfig(
      level=req.level, human_color=color,
      komi=_komi_for_handicap(req.handicap),
      rule="chinese", handicap=_handicap_stone_count(req.handicap), board_size=19,
  )
  ```
  响应体加入解析后的 `human_color`（供 nigiri 时前端渲染，若响应已含初始盘/颜色则复用）。更新 docstring。
- [ ] 跑测试通过；commit。

**Task B — 适配器让子塞子 + 开局着手方**
- Files: Modify `katrain/web/platforms/golaxy/adapter.py`（新增 `_handicap_stones`；`start_engine_game` :454）；Test `tests/platforms/test_engine_handicap.py`（新，mock `engine_genmove`）。
- [ ] **写失败测试**：`_handicap_stones(2)==[288,72]`、`(4)==[288,300,60,72]`、`(9)==[288,300,60,72,174,186,294,66,180]`、`(0)==[]`；人执黑让 4 子：`start_engine_game` 后 `ctx.moves` 前 4 手 == 让4子星位且**紧接一手 AI 白棋**（第 5 手），genmove 调用带 `handicap=4`+完整 moves；人执白让 4 子：塞 4 黑子后**不**自动 genmove（等人白落）；分先人执黑：`ctx.moves==[]` 且不自动 genmove；分先人执白：AI(黑)先手一手（现有行为不回归）。
- [ ] 跑测试确认失败。
- [ ] **实现**：模块内 `_HANDICAP_STONES: dict[int,list[int]]` 按上表；`_handicap_stones(n)=_HANDICAP_STONES.get(n, [])`。`start_engine_game`：
  ```python
  stones = config.handicap  # 已是 stone count (0/2..9)
  ctx.moves = list(_handicap_stones(stones))
  side_to_move = "W" if stones >= 2 else "B"
  ai_color = "W" if config.human_color == "B" else "B"
  if side_to_move == ai_color:
      # AI 先落一手（复用现有 _genmove_committing / 首手分支，:493-495 的统一化）
      <genmove once, append AI move>
  ```
  `_call_genmove` 已传 `ctx.config.handicap`+`ctx.config.komi`（:562-570），无需改。
- [ ] 跑测试通过；commit。

**Task C — 前端 api.ts + 设置面板（⚠️ api.ts 属 shared，双构建）**
- Files: Modify `katrain/web/ui/src/api.ts`（`platformEngineStart` body 类型）、`katrain/web/ui/src/kiosk/pages/PlatformEngineSetupPage.tsx`（:114-127 的颜色 chip + 只读规则行）。
- [ ] `api.ts`：body 类型改为 `{ level: number; human_color: "B" | "W" | "nigiri"; handicap: number }`。
- [ ] `PlatformEngineSetupPage.tsx`：
  - state：`handicap`(默认 0)、`humanColor`(默认 `"nigiri"` 或 `"B"`)。
  - **让子**：MUI `Select`，选项 `分先(0)/让先(-1)/让2子(2)…让9子(9)`，label 走 `t(...)`；旁显派生贴目（分先=黑贴7.5、让N子=黑贴N、让先=0）。
  - **先手**：`OptionChips` 三选 `猜先(nigiri)/执黑(B)/执白(W)`（替换现 :114-122 的黑/白二选）。
  - **固定只读展示**（替换 :124-127）：`棋盘 19 路 · 规则 中国 · 不计时`。
  - start 载荷（:61）：`API.platformEngineStart(platform, { level, human_color: humanColor, handicap }, token)`。
- [ ] `npm run build` **和** `npm run build:kiosk-2d` 都绿。commit。

### Phase 3 — 测试 + 双构建 + 格式化 + 推送
- [ ] `CI=true uv run pytest tests/platforms -q` 全绿；`uv run black -l 120 katrain tests`。
- [ ] `npm run build` **和** `npm run build:kiosk-2d` 都绿。
- [ ] 提交推送 `feature/kiosk-play-golaxy`（用户既定：直接推送、不开 PR）。
- **端到端验证**（用户自己终端起服务 `... --port 8002 --disable-engine`）：新面板可选 贴目/让子/(规则)；起一局让子看日志 genmove `HTTP 200`、`handicap`/`moves` 与 Phase 0 一致、AI 正常回手；认输无 `ForeignKeyViolation`。

### 本节明确不做（后续）
- 升降级对弈（规则固定+定级 `elodiff≠0`+计时）、联棋对弈（人+AI 配对流程）、高水平对弈（疑似自由对弈锁最强档子集）。
- 棋盘 9/13 路（需重做 coords/LED/摄像头）。
- 引擎对局内存态跨服务重启续局。

---

## 13. 后续计划：局内分析道具对接（领地 / 支招 / 变化图）—— 对齐 Golaxy 付费道具

### Context（为什么）
对局态右栏现有的 领地/建议/图表 走的是**本地 KataGo 分析**（`GameControlPanel.tsx:61-63` → `GamePage.tsx:231` 的 `onToggleAnalysis`）。跨平台星阵人机对弈用 `--disable-engine` 起、隧道只回 genmove，**这三个按钮无数据即失效**；且用本地引擎给星阵局助战 = 挂第二引擎作弊。本期把它们改为**调星阵自己的分析隧道**（§9），严格对齐 Golaxy 人机对弈的三个**付费限次道具**：领地 / 支招 / 变化图。

### 现状（已完成的前置）
- ✅ 协议逆向 + **实测定稿**：四端点 `area/options/judge/variation` 的参数与响应，见 `golaxy-protocol.md` §9 + **§9.5（2026-07-07 浏览器自动化直打隧道实测）**。
- ✅ 视觉稿（严格对齐、用户待确认）：`kiosk-ui-redesign/artifacts/game-golaxy-engine.html`（Artifact `5f03d019…`）。5 屏：默认/支招/变化图/领地/**7003 道具用尽**。

### Non-goals（本期明确不做）
- **不**在 engineMode 启用任何本地 KataGo 分析（禁作弊）。**不**自造"免费"分析（本地弱网不准 + 助战问题）。
- **不**在 kiosk 内代充/兑换（`7003` 仅引导去星阵 App 充值）。
- **不**加"形势"按钮、**不**加胜率走势图（星阵人机对弈本就没有）。
- `options`/`variation` 除 `coord` 外的每手子字段（`winrate`/`prob`/`visits`）本期尽力解析、缺失不阻塞（只画候选点/变化序列即可）。

### Global Constraints（每个任务都隐含遵守）
- **engineMode 下禁用本地分析**：`GamePage.tsx` 的 `analysisToggles`（ownership/hints/score，:27-29）与 `API.hint`（:144）在 engineMode **不得走本地引擎**；改为调星阵隧道或隐藏。
- **SBC 双构建**：`api.ts` 属 shared territory，改后 `npm run build` **和** `npm run build:kiosk-2d`（含 `verify:kiosk-2d`）都要绿。前端只用 shared + `src/kiosk/`。
- **坐标**：`variation`/`options` 响应的 `coord` 是**整数数组**，逐个走 `golaxy/coords.py` 已验证 codec 反解（`row=19-floor(c/19)`, `col=c%19`）画到盘上。
- **凭证安全**：复用引擎对局 ctx 已持有的 token/鉴权（同 `_call_genmove` `adapter.py:597`）；不新增 token 处理、不写日志。
- **计费诚实**：`7003 "item is not sufficient"` → 归一化为 typed error → UI 显"次数不足·请在星阵充值"。
- **勿回归**：genmove 隧道、§11 FK 守卫 / token 持久化 / 6003 分类不能破。

### Interfaces（exact，全部取自 `golaxy-protocol.md` §9.5 实测）
- 端点：`GET https://api.19x19.com/api/engine/dcnn/tunnel/{area|options|judge|variation}`，`serve:engine`，鉴权同 genmove（`Authorization: bearer <token>` + 浏览器 Origin/Referer/UA）。
- 参数（不发 `type`）：`moves`(完整历史 CSV) · `board_size=19` · `boardsize=19` · `komi` · `rule` · `handicap` · `level=8888`(满血分析) · `style` · `org=golaxy_web` · `context_name=ai_game_player`。
- 响应：
  - `variation` / `options` → `{"code":"0","data":{"winrate":0..1,"delta":<目差>,"coord":[<int>...]}}`（`coord`=手序坐标数组；`variation` 无需指定展开哪手）。
  - `judge` → `{"code":"0","data":{"belong":"<361 字符 U/B/W>","winner":"U|B|W|D","delta":<目差>}}`。
  - `area` → `{"code":"0","data":{"winrate":<黑胜率>,"delta":<黑目差>,"area":[<722 个 float>]}}`；**前 361 = 每点归属**（下标即 coord，`>0`黑/`<0`白），**后 361 本样本≈-0.99 常量弃用**。已抓（2026-07-07 充值后实测，§9.5）。
  - `options` → `{"code":"0","data":{"coord":[..],"prob":[..],"winrate":[..],"delta":[..]}}`（4 个等长并行数组，本次 5 候选）。已抓（§9.5）。
  - 额度不足 → `{"code":"7003","msg":"item is not sufficient","data":""}`（`area/options/variation` 各自独立计数；`judge` 本次 code 0，勿据此当无限免费）。

### Phase 0 — 补两处实测（需 领地 额度 > 0；用户 1 次操作）
- [x] **area 成功响应** ✅（2026-07-07，用户充值后浏览器直打隧道）：`data.area` 是 **722 长扁平数组**（前 361 = 每点归属，下标即 coord，`>0`黑/`<0`白，实盘校验 黑D4[288]=+0.683、白Q4[300]=-0.729；后 361 本样本≈-0.99 常量、弃用）+ 顶层 `winrate`/`delta`。同时补抓 **options 成功结构**（`coord/prob/winrate/delta` 4 等长数组）+ 复测 variation。均记入 `golaxy-protocol.md` §9.5。
- [ ] **剩余次数端点**：抓星阵"我的道具/剩余次数"接口（前端 `propsMine`/`userPropsNotice` 的数据源，非 tunnel 响应）——用于 kiosk 预显角标（领地N/支招N/变化图N）。**未抓** → 按 MVP 兜底：不预显次数，仅在 `7003` 时提示，角标留空/问号。
- ~~决策点：area 成功结构与预期不符~~ → 已就地回报并定案：722 数组、kiosk 用前 361 项作归属叠加。

### Phase 1 — engine_client 兄弟端点（TDD，httpx MockTransport，仿 `test_golaxy_engine_client.py`）
- Files: Modify `katrain/web/platforms/golaxy/engine_client.py`（加 `GOLAXY_{AREA,OPTIONS,JUDGE,VARIATION}_URL` 常量 + `QuotaExhausted(GolaxyEngineError)` 类 + `engine_analysis(kind, access_token, moves, config)` 复用 `_BROWSER_UA`/headers/`_classify_response_code`）；Test `tests/platforms/test_golaxy_engine_analysis.py`（新）。
- [ ] **写失败测试**：mock 返回 §9.5 的三种真实体 →
  - `variation`/`options` 解析出 `{winrate, delta, coord:[...]}`（`coord` 为 int list）。
  - `judge` 解析出 `{belong(str len 361), winner, delta}`。
  - `code=="7003"` → 抛 `QuotaExhausted`（不作为 network/auth 错误）；`6003` 仍 → `AuthExpired`（不回归 `_classify_response_code`）。
- [ ] 实现：一个 `engine_analysis(kind, ...)` 内部按 kind 选 URL、构造 §Interfaces 参数（`level=8888`）、GET、`_classify` 后 `json.loads` data、按 kind 返回 dataclass（`VariationResult`/`JudgeResult`/`AreaResult`）。
- [ ] 跑测试通过；commit。

### Phase 2 — adapter 分析方法（用引擎对局 ctx；TDD，mock client）
- Files: Modify `katrain/web/platforms/golaxy/adapter.py`（加 `async def engine_analysis(self, game_id, kind) -> AnalysisResult`，读 `ctx.moves`+`ctx.config`，调 client，`coord` 数组经 `coords.py` 反解为 `(col,row)` 列表；`judge.belong` 转 361 长 ownership 网格）；Test `tests/platforms/test_engine_analysis_adapter.py`（新，mock `engine_client.engine_analysis`）。
- [ ] **写失败测试**：`ctx.moves=[72,300]`、kind=variation → 返回结构含反解后的 `(col,row)` 序列（首个 `coord=60` → `(col=3,row=3)`=D16 等，用 §3 金标准校验）；kind=judge → `belong` 361 项映射为每点 `B/W/U`；`QuotaExhausted` 透传为 typed。未知 `game_id` → 现有 `not found` 行为。
- [ ] 实现；`_call_genmove` 一带的鉴权/UA 复用，不改 genmove 路径。
- [ ] 跑测试通过；commit。

### Phase 3 — endpoint + manager + api.ts（api.ts 双构建）
- Files: Modify `katrain/web/api/v1/endpoints/platforms.py`（加 `POST /{platform}/engine/analysis`，仿 `start_engine` :193-221 的 `pm` 委派）、`katrain/web/platforms/manager.py`（加 `engine_analysis(platform, session_id, kind, user_id)` 仿 :136-148）、`katrain/web/ui/src/api.ts`（加 `platformEngineAnalysis(platform, sessionId, kind, token)` + 返回类型）；Test `tests/platforms/test_engine_analysis_endpoint.py`（新，TestClient）。
- [ ] 后端：请求 `{session_id, kind∈{"area","options","judge","variation"}}`；`QuotaExhausted` → 返回 `{"ok":false,"reason":"insufficient","kind":kind}`（HTTP 200，前端据此弹充值提示，不当 500）；成功 → `{"ok":true,"kind":kind,"data":<反解结构>}`。校验 kind 白名单 → 非法 422。
- [ ] `api.ts`：`platformEngineAnalysis` body 类型 + 响应 union（success/insufficient）。
- [ ] `npm run build` **和** `build:kiosk-2d` 都绿；后端测试通过；commit。

### Phase 4 — 前端 GamePage engineMode 右栏（对齐 game-golaxy-engine.html 稿）
- Files: Modify `katrain/web/ui/src/kiosk/pages/GamePage.tsx`、`katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx`、盘面叠加层（复用 `Board` 的标记层）。
- [ ] `GameControlPanel`：`engineMode` 时把 领地/建议/图表 三 toggle（:61-63）换成 **领地/支招/变化图** 三按钮 → 调 `API.platformEngineAnalysis`；互斥（同时只亮一个叠加）；角标显剩余次数（Phase 0 拿到则真值，否则留空）。
- [ ] `GamePage`：engineMode 下 `analysisToggles`/`API.hint`（:144）**不走本地引擎**；分析结果存 state，按 kind 渲染盘面叠加：
  - 支招/变化图 → `coord` 序列画候选点 / 编号变化序列（稿 B/C）。
  - 领地 → area/ `judge.belong` 画归属叠加（稿 D）。
  - `{ok:false,reason:"insufficient"}` → 弹"次数不足·请在星阵充值"（稿 E，不代充）。
- [ ] 确认 engineMode **不渲染**胜率图/形势按钮。
- [ ] `npm run build` **和** `build:kiosk-2d` 都绿；commit。

### Phase 5 — 端到端真机验证（用户，1 次，需道具额度）
- [ ] 起 `--disable-engine` 服务，星阵人机对局中：变化图/支招显候选与序列（坐标正确）；领地显归属；额度用尽走 `7003` 充值提示；genmove/认输不回归。
- [ ] `CI=true uv run pytest tests/platforms -q` 全绿；`uv run black -l 120 katrain tests`；推送 `feature/kiosk-play-golaxy`。

### Definition of Done（本期）
领地/支招/变化图 三道具在 engineMode 走星阵隧道、坐标正确叠加、互斥、`7003` 引导充值；本地 KataGo 分析在 engineMode 全关；双构建绿；协议 §9.5 补齐 area 成功结构。

### Open questions
- `area` 成功响应结构（Phase 0 待抓）。
- 剩余次数端点（Phase 0；抓不到则 MVP 不预显角标）。
- `winrate`/`delta` 视角（轮走方 vs 固定黑）——落地时对一眼；本期 UI 主要用 `coord`，视角影响小。

---

## 14. 后续计划：rk3562 真机上板部署（视觉 NPU + LED + 实机对弈走查）

> **REQUIRED SUB-SKILL**：用 `superpowers:executing-plans` 逐 Phase 执行，每 Phase 末尾 **Verification**（可观测证据）+ **Review checkpoint**。硬件相关步骤（Phase A）需人工在设备旁操作。
> **Written 2026-07-12**，依据当日 `ssh rk3562-direct` 真机诊断（见下「诊断快照」）。这一节把「上板部署」正式并入本 track —— §12/§13 是软件闭环，本节是把闭环真正跑到物理棋盘上。

**Goal**：让 `feature/kiosk-play-golaxy` 的 kiosk 在真机 rk3562（GZPEITE P04 板）上跑通「摄像头识别落子 + LED 引导」，使 **自由对弈 / 升降级对弈 / 跨平台星阵对弈** 三个子模块可做实机走查。

**Architecture**：视觉走 **YOLOv11s INT8 `.rknn` → RK3562 NPU（rknnlite + librknnrt.so）**；LED 走 **Board B 上的 ESP32（原生 USB-CDC）→ WS2812**；两者由 katrain `web.server` 的 board-mode 子进程 vision worker + LED 串口驱动，**通过 systemd `ExecStart` 参数（或 config.json）显式开启**。

### ⚠️ 跨仓库归属（golden image 前提，2026-07-12 核对 `smartbox-software/provisioning`）

**这个 track 的物理链路 = 两仓库协作**：
- **代码**在本仓库 `feature/kiosk-play-golaxy`（Tasks 0-13 done），以 **git 子模块 `smartbox-software/vendor/katrain`** 被消费（需 bump 到 `7d1b0c32`）。
- **部署/接线/可复制性**在 **`smartbox-software/provisioning`**，不在本仓库。golden image = 跑 `provision.sh` 各 section（apt-deps→python-stack→katago→**katrain**→…→systemd→**image-prep**）后 `dd`。

**现状 gap（provisioning 里视觉+LED 的真实覆盖度）**：
- **LED：只装了一半、没接线。** `provision.sh` katrain section 显式装 `pyserial>=3.5`「for the LED guidance board」（意图有），但 **systemd `smartbox-katrain.service` 不传 `--led-serial-port` ⇒ LED 永不启动**；且**无 udev 规则**给 ESP32 串口一个稳定节点（`/dev/ttyACM0` 序号跨机会漂）。
- **视觉/NPU：完全没 provision。** venv-katrain 的 `requirements-web.txt` **只有 pyserial，没有 opencv**（opencv-python-headless 只在主 venv 的 `requirements-board.txt`）；`provisioning/` 全仓 **零** `rknnlite`/`.rknn`/`vision-model`/`vision-backend`/`capture-camera` 引用；`wheels/` 空；无 `vision` section。
- ⇒ **Phase A–D 是单板 bring-up 验证；真正进 golden image 必须落地为 `smartbox-software/provisioning` 改动（Phase E）**，否则烧一台配一台、无法复制。

### 诊断快照（2026-07-12，`ssh rk3562-direct` = 10.0.0.3 / hostname `gzpeite`）

这台设备是 smartbox 多游戏机，围棋跑 `smartbox-katrain.service`。当日实测**视觉+LED 半条链路整条没 provision 上去**，具体：

| 层 | 现状 | 证据 |
|---|---|---|
| NPU 硬件/驱动 | ✅ 就绪但没人用 | RKNPU driver v0.9.8；`/usr/lib/librknnrt.so` 在 |
| 视觉模型 | ❌ 全盘无 `.rknn/.onnx/.pt` | 只有 `vendor/katrain/.../tools/Dockerfile.rknn` |
| 推理运行时 | ❌ 无 venv 装了 rknnlite/ultralytics/onnxruntime；`venv-katrain` 连 cv2/pyserial 都没有 | 逐 venv `python -c import` 全 fail |
| katrain 启动参数 | ❌ 裸启，无任何视觉/LED flag | `ExecStart=/opt/smartbox/venv-katrain/bin/python -m katrain.web.server --host 127.0.0.1 --port 8081`；provisioning 模板 `/root/smartbox-software/provisioning/systemd/smartbox-katrain.service:16` 本身就是空的 |
| config.json 视觉段 | ❌ 只有 `engine` 段 | `/mnt/data/weiqi/dot-katrain/config.json`（bind→`/root/.katrain`）无 vision/capture/led/board |
| 服务日志 | ❌ 无 vision/camera/led/geometry 启动记录，只有 remote 健康检查 | `journalctl -u smartbox-katrain` |
| 摄像头硬件 | ✅ 真连着 | `/dev/video0` = HBV HD CAMERA（USB，index 0）；`lsusb` 可见 `0ac8:0346` |
| LED（ESP32/Board B） | ❌ USB 总线上不存在 | `lsusb` 只有摄像头+hub；无 `/dev/ttyUSB*`/`/dev/ttyACM*`（`/dev/ttyS*` 是 SoC 板载 UART，非 LED） |

**结论对齐用户三问**：yolov11s **未部署**、NPU **未用于视觉**、**帧率 N/A**（视觉进程没起）；摄像头 OK、LED 未枚举。

**根因（近端）**：katrain 服务端按参数开关视觉/LED —— `server.py:2215 if args.vision_model:`、`server.py:2248 if args.led_serial_port:`。裸启无参 ⇒ 视觉 worker 与 LED 串口**永不初始化** ⇒ 围棋界面「摄像头/LED 未识别」是后端真没连，不是前端 bug。

**LED 硬件事实（来自 `smartbox-hardware-design/pcb/引脚核对清单.html`）**：LED 由 **Board B（棋智盒侧）上的 ESP32** 驱动 —— ESP32 `GPIO4(IO4) → WS2812 DIN`，ESP32 `USB D+/D-(IO19/IO20) → SBC USB`（**原生 USB-CDC**，故 Mac 上呈现为 `/dev/cu.usbmodem2101`，Linux 上应是 `/dev/ttyACM0`）。当日 ESP32 **没在 SBC USB 总线枚举**，图纸自带告警「USB D+/D-(IO19/IO20) 接反会导致 USB 不识别」。

### Global Constraints（每个 Phase 隐含遵守）
- **只诊断先行**：改动运行中的生产服务前先 `systemctl` 备份/记录原状；改 systemd 用 `systemctl edit`（drop-in）而非直接改 `/etc` 主单元，验证通过后再回写 provisioning 模板 `/root/smartbox-software/provisioning/systemd/smartbox-katrain.service` 并提 smartbox-software 仓库（否则重 provision 会覆盖）。
- **RK3562 = 单核 ~1 TOPS NPU**：模型固定 **s 尺寸**（`go4_s_best.pt`，blur 增强、Mac A/B 验证最优且尺寸适配），imgsz 640；不要上 m/x。
- **模型帧（关键教训，见 [[project_kiosk_golaxy_physical_play]]）**：屏幕候选点与 LED 必须指同一交叉点；vision/LED 是 row0=top，runtime `Candidate.row` 是 core/bottom-anchored → 需 `board_size-1-row` 翻转。上板走查务必**中盘**核对（开局角部对称会掩盖镜像错误）。
- **凭证/日志安全**：真机走查用真星阵账号；抓包/日志 redact `Authorization`/`refresh_token`。**新增（评审 critic#1）**：Phase D 真账号登录会把真 `refresh_token` 落盘到 `~/.katrain/credentials/<device_id>`（0600，可能明文兜底，位于持久 `/mnt/data/weiqi/dot-katrain` bind）——共享/返修机务必走查后清理该凭证。
- **勿回归**：§11 FK 守卫 / token 持久化 / 6003 分类、§12 让子、§13 分析道具都不能破。**走查须真在设备上验**（不能只 D3 查 FK+6003）：token 持久化要跨 **C5 服务重启**验、§12 让子、§13 领地/变化图各点一次。
- **⚠️ 用户 go-ahead 门禁（2026-07-12 评审新增，硬约束）**：本节 Phase A–D 每一条 `ssh` / `pip install` / `scp` / `systemctl restart` / 驱动 LED 的命令都在**改动运行中的生产机 gzpeite**（`venv-katrain` 是 `smartbox-katrain.service` 的解释器）。「只诊断/只写不执行」在拿到用户**显式 go-ahead 前全程有效**——Phase B **不是**「纯软件可无人值守并行」（B4/B5/B6 写 live venv + scp 模型 = 上机改动）。每次上机前逐条报备、留 C1 式回滚点；离线 FPS 自测用**一次性 venv**，勿污染 `venv-katrain`。
- **视觉运行位置更正（评审证实，`service.py:42` + `server.py:414`）**：`--capture-camera` 一给（本节 C2 必给）⇒ `frame_source=camera_hub` 非空 ⇒ VisionService 走 **InProcessAdapter，视觉与 web server 同进程同解释器**（= `venv-katrain`，因 ExecStart 用它），**不是**独立子进程。依赖装 `venv-katrain` 仍对（server 本体在 venv-katrain），但 **in-process ⇒ rknnlite/opencv/模型任一崩溃会拖垮整个围棋服务**（E8 冒烟测试、go-ahead 门禁据此加严）。原文「vision worker 是子进程」前提作废。

---

### 14.1 评审采纳记录（2026-07-12 · Codex + Claude 双路对抗评审，71 条去重后 34 主题）

> 两路独立对抗评审：**Codex**（`codex exec`，读源码，25 条）+ **Claude fan-out**（5 lens + 完整性 critic，46 条）。均**代码定位/实证接地**（Claude 用 `git check-ignore` 实证）。下表去重后按主题裁决；**★ = 已本人复验为真**（命令/源码），直接改进下方 Phase。

| # | 反馈（来源，去重） | 裁决 | 落地位置 |
|---|---|---|---|
| A1 | ★ C2 `--vision-ae-target 145` 是标量，但 `config_service.py:66` 做 `ae_target.split("-")` 解包 (lo,hi) → 标量崩服务 | **采纳** | C2 改 `120-170` 带区间 |
| A2 | ★ 模型文件名漂移：`export_rknn.py:124` 出 `{stem}_{target}.rknn` = `go4_s_rk3562.rknn`，plan 各处写 `go4_s.rknn`/`go4_s_best.rknn` 不符 | **采纳** | B1/B3/B6/C2/E3 统一实名 `go4_s_rk3562.rknn` |
| A3 | ★ `convert_rknn.sh` 只挂 `$PROJECT_ROOT:/work`，B1/B2 写 host `/tmp` + 取 sibling repo `katrain-yolo-train` → 容器内不可见，转换必失败 | **采纳** | B1/B2 产物落 worktree 内、校准路径写 `/work/...` |
| A4 | ★ `.gitignore:31 models/` 吞掉 `katrain/vision/models/`（`git check-ignore` 实证匹配），§14 E3 未加豁免 | **采纳** | E3 加 `!katrain/vision/models/` 或 `git add -f` |
| A5 | ★ E1↔E3 顺序/原子性：`7d1b0c32` 无模型；E3 提交模型必产**新** commit，E1 须 bump 到新 SHA（非 7d1b0c32），且受 D 合并决定门禁 | **采纳** | E 重排：先提交模型→再 bump 子模块到该 SHA |
| A6 | ★ 模型路径分裂：B6/C2 验证 `/mnt/data/weiqi/models/`，E3 装 `/opt/smartbox/share/katrain-vision/` → 验证的与出厂的不是同一路径 | **采纳** | C2 与 E4 用**同一路径**；或 E 后按 /opt 复验 B7/D |
| A7 | ★ C2 drop-in 只覆盖 ExecStart，未保证 `KATRAIN_MODE=board`——worker 子进程/inproc 选择、kiosk 构建 (`server.py:2350/554`) 皆依赖它 | **采纳** | C2 显式确认/设置 `Environment=KATRAIN_MODE=board` |
| A8 | ★ C6 `/geometry/status locked:true` 在**从未标定**的板上为假：`server.py:484-485` 仅 `if exists` 加载；启动自推是**重启持久**非首标定；真门是 `phase=ready/session_calibrated/geometry_ready/recognition_ready` | **采纳** | C6 要求重启后**新 13 锚点标定** + 断言全 readiness 字段 |
| A9 | ★ in-process 视觉（见上「运行位置更正」）：`service.py:42` 有 `--capture-camera` 即 InProcessAdapter，非子进程 | **采纳** | Global Constraints 已更正；E8 冒烟须覆盖 |
| A10 | Phase A 把「软件可修」(host 端 `cdc_acm` 未 load / 未烧录固件) 和「硬件」(D+/D-接反·未上电) 混为一个「软件改不动」判决 | **采纳** | A2 按 `lsusb` 分叉 + ROM 下载模式判别（见改写） |
| A11 | A4 自造 LED 帧协议，但协议已定在 `led_service.py`：`BRIGHT/CLEAR/SETI/SHOW`@115200、`OK/ERR` ack、开机 `READY` banner；且原生 CDC 下 baud 是 no-op | **采纳** | A4 改走真 `LedService`/精确帧；点几个点勿全亮（WS2812 掉压 critic#6） |
| A12 | 节点稳定性全推到 E5(udev)，但 C2 硬编 bare `ttyACM0`（会漂）；`set_points(strict=False)` 断连仍回 `ok:True` → D 静默在 LED 断连下「通过」 | **采纳** | A3/C2 用 `/dev/serial/by-id/...`；D 加 `strict=True` LED 连通预检 |
| A13 | D「中盘核对」可被**镜像不变点**满足（翻转是 row-only `18-row`，不动点 row=9 中心行，星位↔星位）；单点不足证明全路径翻转 | **采纳** | D 定 ≥3 个**非中心非对称**坐标（跨上下半盘）+ 具名 core/screen/vision/LED(row,col)+链号 |
| A14 | 每手 AI 引导翻转 (`orchestrator:446` + `sync.py:437`) 与刚恢复的 `支招` 翻转 (`platforms.py:181`) 是**独立实现**，三必查项零覆盖；`支招` 在 ranked 被 403 挡 → D2 无坐标校验 | **采纳** | D 显式覆盖每手引导 + 星阵`支招`路径；D2 加非-支招坐标校验 |
| A15 | D1「本地 KataGo 引擎」实为 HTTP `127.0.0.1:8000`（`config.py:18`）非子进程 → 未言明前置：该引擎在机上是否在跑 | **采纳** | D1 加前置：确认本地 KataGo HTTP 引擎在线 |
| A16 | E 缺**逐机几何标定**流：出厂镜像无 `geometry_lock.npz` ⇒ `recognition_ready=false` ⇒ 物理对弈死，直到人工标定 | **采纳** | E 加 firstboot/操作员逐机几何标定（金镜像大缺口） |
| A17 | rknnlite wheel ↔ toolkit2 build ↔ 设备 `librknnrt.so` ↔ 驱动 v0.9.8 四者版本无锁；`Dockerfile.rknn:24` `--no-deps rknn-toolkit2` 无版本钉；B3(转) 在 B4(读设备版本) 之前 | **采纳（proportional）** | B 重排：先读设备 `.so` 版本→再钉 wheel/toolkit；记 hash + init_runtime soak；换 `.so` 视为受控迁移非顺手兜底 |
| A18 | B7 测的是 raw 帧直喂 StoneDetector，非运行时（warp+clahe+frame-avg(8) 后）管线；FPS/精度不代表生产 | **采纳** | B7 测端到端（含 warp/clahe/均值）+ p50/p95 落子→确认延迟 |
| A19 | fp16 兜底与 INT8 验收门混淆 → INT8 回归可能静默出厂 | **采纳** | fp16 标「仅诊断」；B7 验收的 INT8 制品 = E 出厂的同一份（记 hash） |
| A20 | INT8 校准欠采样 LED 类：普通对局帧几乎无点亮 led_red/green → 两类量化范围近零样本 | **采纳（proportional）** | B2 校准集须含**点亮 LED 帧** + white/眩光/弱光；逐类召回抽验 vs .pt |
| A21 | systemd 沙箱只查了 `PrivateDevices`；未审 `ProtectSystem/DevicePolicy/DeviceAllow/ReadWritePaths/组`，及 `~/.katrain` 写(geometry_lock/credentials) | **采纳** | C3 审**生效单元**全量；确认 BindPaths `dot-katrain→/root/.katrain` 使 `~/.katrain` 可写 |
| A22 | 曝光双主：in-proc V4L2 锁 (`camera.py:168-173` `CAP_PROP_AUTO_EXPOSURE=0.25` when `lock_exposure`) vs 软件 AE 打架 | **采纳** | C4 单一曝光主；`v4l2-ctl --list-ctrls` 探测；每次设备起都设（非一次性） |
| A23 | 摄像头单主/CameraHub 双开、协商格式/FPS 未证；1080p 硬编未验 HBV 可协商带宽 | **采纳（proportional）** | C 预检共享 CameraHub 单 fd + `v4l2-ctl --list-formats-ext` 记实际格式/FPS |
| A24 | 类序契约：运行时 `stone_detector.py:13` 固定 `[black,white,led_red,led_green]`，与 export `meta.classes` 顺序可能不符 | **采纳** | B 加一次类序对照断言 |
| A25 | udev 只配宽 VID/PID、无唯一 serial/interface、无 service 排序 → 多 Espressif 绑错/开机早于 symlink；且非 303a 桥(1a86/10c4/0403) 分支未纳入 | **采纳** | E5 匹配 serial+interface + `After=` 设备/重连契约；含桥接 VID |
| A26 | E7 firstboot 一次性设曝光，但 V4L2 控件在插拔/重启复位 | **采纳** | E7 改每次 service/设备起都设，firstboot 仅留不可变项 |
| A27 | E8 契约测试仅查「文本存在」(包名/flag/文件)，证不了 ABI/模型完整性/udev/单元起 | **采纳** | E8 加镜像级冒烟：`import rknnlite`+`init_runtime`、模型校验和、`systemd-analyze verify`、udev、readiness 断言 |
| A28 | opencv 装法(在线 PyPI)与 rknnlite 离线纪律不一致；numpy ABI 未钉(2.x 风险)；E3 缺制品来源清单 | **采纳（proportional）** | E2 opencv 亦离线 wheel + 钉 `numpy<=1.26.4`(constraints)；E3 加制品清单(源 .pt hash/校准 rev/toolkit 版/输出 hash) |
| A29 | E3「决策已定」但「本节风险」仍把模型分发列为**未决**——自相矛盾；且 write-many(重训) 与 KataGo write-once 不同构，git 膨胀 | **采纳** | 删/标记那条 open question；E3 补 git 膨胀/轮换/大小策略 |
| A30 | 多游戏 smartbox：board 模式服务持续独占摄像头，与其它游戏硬件/target 互斥未验 | **采纳（note）** | E/D 加：确认围棋期 katrain 独占相机、smartbox 互斥放行 |
| A31 | 语音/emoji 引导（语音为主，`useVoice.ts:24-28` 失败静默 `.catch`）从未在机上 provision/验证 | **采纳** | D 加：机上验证语音+屏幕引导实际出声/显字（mp3 资源在、音频通） |
| A32 | B7 100 帧突发测不了**稳态/热**：无风扇 RK3562 整局连跑，冷测≠热后 throttle | **采纳（note）** | B7 补热浸后稳态 FPS / throttle 观察 |
| A33 | C1 备份仅 `systemctl cat`，不含 drop-in/env/enable 态；未定远端执行身份与回滚 | **采纳（minor）** | C1 备份全 fragment/env/enable + 定回滚 |
| A34 | `systemctl edit` 的 `override.conf` 在「回写模板」后成残留，与 provisioning 的 `vision.conf` 并存合并 | **采纳（minor）** | E 清理手工 override.conf |
| R1 | Codex 的最重流程要求：正式分层校准语料 + 全 precision/recall/置信漂移/FP 率门、容器 digest 溯源官僚化 | **降级采纳** | 采其意、**降为 bring-up 相称**抽验（见 A17/A20/A28）——单板 bring-up + 首个金镜像，非认证级发布 |
| R2 | A3 VID/PID 白名单「可能漏真设备」 | **并入 A10/A25** | 不单列（前后 `lsusb`+`udevadm` 对比已含） |

**总裁决：34 主题全部采纳（其中 R1 降级为相称、R2 并项）；无「拒绝为误报」。** 双路评审质量高、代码接地、无幻觉。★ 8 条已本人复验为真（A1–A9 中带★者），是「服务起不来/转换失败/提交被吞/走查测不到镜像 bug」级的实缺陷。下方 Phase A–E 已按上表内联修订。

---

### Phase A — LED（ESP32 / Board B）USB 枚举上线（硬件优先，人工在设备旁）

> 目标：让 SBC 出现 `/dev/ttyACM0`（或 ttyUSB*），且 katrain LED 驱动能打开它点亮 WS2812。**这是硬件/固件问题，软件改不动**——先枚举成功再谈接线。

- [ ] **A1 基线记录**：`ssh rk3562-direct 'lsusb; ls /dev/ttyACM* /dev/ttyUSB* 2>&1'` 存档当前状态（预期仍只有摄像头）。
- [ ] **A2 边插边看**（人工）：`ssh rk3562-direct 'dmesg -w'`，同时插拔 Board B↔SBC 的 USB / 给 Board B 上电。**期望** `cdc_acm ... ttyACM0: USB ACM device`（ESP32 原生 CDC）。**A10（★ 按 `lsusb` 分叉，别一律判「硬件改不动」）**：
  - **(i) `lsusb` 有 `303a:*` 但无 `/dev/ttyACM*`** → **host 端软件问题，非硬件**：`dmesg | grep -i cdc_acm`、`modprobe cdc_acm`、查内核 `CONFIG_USB_ACM`（精简 RK3562 vendor 内核常没编）——一行 modprobe/补内核即可，**别改板**。
  - **(ii) `lsusb` 全无该设备** → 用 **ROM 下载模式判别固件 vs 硬件**：按住 BOOT/IO0 + 点 RST 强制下载模式，再看 `lsusb`/`dmesg`；出现 `303a` 下载设备（如 `303a:1001`）⇒ **USB 路径/供电/D± 都好，纯固件问题**（刷固件，软件可修）；连下载模式都无 ⇒ **供电/D+/D- 接反**（硬件，`就地回报`）。
  - **控制实验**：把 ESP32 线插到摄像头正在用的那个已知好 host 口，隔离「口的角色」与「设备故障」。
  - 本设计是**原生 CDC（只 303a）**：`ch34x/cp210x/ttyUSB` 分支在此板**不成立**（无桥接芯片），仅作脚注，别在那上面耗时。
- [ ] **A3 确认 VID/PID 与节点**：`ssh rk3562-direct 'lsusb | grep -iE "303a|1a86|10c4|0403"; ls -l /dev/ttyACM* /dev/ttyUSB*'`（303a=Espressif, 1a86=CH340, 10c4=CP210x, 0403=FTDI）。记下最终 LED 串口设备路径 `＄LED_PORT`。
- [ ] **A4 点灯自测**（⚠️ go-ahead）：**A11（★ 用真协议，别自造）**——协议已定在 `katrain/web/core/led_service.py`：ASCII 行命令 **`BRIGHT <n>` / `CLEAR` / `SETI <idx> <r> <g> <b>` / `SHOW`**，各 `\n` 结尾，`OK`/`ERR` 逐条 ack，115200，开机有 `READY` banner（`_open_serial` 会 drain）。**首选直接实例化 `LedService(serial_port=＄LED_BY_ID, ...)` 调 `clear()`/`set_points(strict=True)`**（走真路径，才能 gate Phase C；自造帧的自测不可证伪、可能假过/假败）。
  - **critic#6（掉压）**：首帧**别全亮**——WS2812 长链 + 每跳 ~0.5V 掉压余量（[[project_led_hardware_bringup]]，UR 末跳最弱），先 `BRIGHT` 调低点几个点，逐段验灯序 UL→LL→LR→UR（[[reference_led_lut_mapping]]）。
  - 原生 CDC 下 `--led-baud-rate` 是 no-op（仅真 UART 桥有意义），别在 baud 上纠结。
- **Verification**：**`/dev/serial/by-id/...` 稳定节点**存在（A12，别只认会漂的 `ttyACM0`）；`LedService.set_points(strict=True)` 能点亮指定交叉点、灯序符合 LUT。
- **Review checkpoint**：LED 硬件确认可控后再进 Phase C；若 A2 判为硬件（D+/D- 接反等需改板/重焊/刷固件），**就地回报用户**。**A9/go-ahead 更正**：Phase B **不是**「纯软件可无人值守并行」——B4/B5/B6 写 live `venv-katrain` + scp 上机，与 Phase A 一样受 go-ahead 门禁；「B 独立于 LED 硬件」为真，「B 免上机」为假。

---

### Phase B — 视觉 NPU（`.rknn`）转换与部署（Mac 侧转换 + SBC 侧落地）

> 链路：`go4_s_best.pt` →(Mac) `export_onnx` → `.onnx`+`.meta.json` →(Mac, Docker) `export_rknn --target rk3562 --quantize --dataset` → `.rknn`+`.meta.json` →(scp) SBC → rknnlite 加载跑 NPU。

> **⚠️ A3 关键（★ 复验 `convert_rknn.sh:30-34`）**：`convert_rknn.sh` 只把 **`$PROJECT_ROOT:/work`** 挂进容器。所以 **ONNX、校准图、`calibration.txt` 必须全落在 worktree（PROJECT_ROOT）内**，且传给容器的路径要用**容器内 `/work/...`**——不能用 host `/tmp` 或 sibling repo `~/Repositories/katrain-yolo-train`（容器里不可见 → 转换必失败）。下面统一用 worktree 内 `build/vision/` 暂存目录（记得 gitignore 或转换后清）。

- [ ] **B1 Mac：导 ONNX**（在**本 worktree** 内，用有 ultralytics 的 conda `py311_katago`）：
  ```bash
  conda activate py311_katago
  cd ＄WORKTREE && mkdir -p build/vision
  python -m katrain.vision.tools.export_onnx \
    --weights ~/Repositories/katrain-yolo-train/go4_s_best.pt \
    --imgsz 640 --out build/vision/go4_s.onnx   # 落 worktree 内（PROJECT_ROOT），不是 /tmp
  # 产出 build/vision/go4_s.onnx + go4_s.meta.json（含 imgsz/classes；classes 由 .pt 带出，勿手写）
  ```
  （export_onnx 的确切 flag 名以 `python -m katrain.vision.tools.export_onnx --help` 为准；`onnx_backend.py`/`rknn_backend.py` 靠 `.meta.json` 读 imgsz/classes。**A24**：转换后核对 `.meta.json` 的 `classes` 顺序 == 运行时 `stone_detector.py:13` 固定序 `[black,white,led_red,led_green]`。）
- [ ] **B2 Mac：备好 INT8 校准集**：拷 ~100–300 张校准图到 **`＄WORKTREE/build/vision/calib/`**（worktree 内），写 **`build/vision/calibration.txt`**，每行是**容器内路径 `/work/build/vision/calib/xxx.jpg`**（不是 host 绝对路径——A3）。
  - **A20（★ LED 类欠采样）**：普通对局帧几乎不含点亮 LED，INT8 会把 `led_red/led_green` 的量化范围按近零样本标定 → 走查时误灯/漏灯。校准集**必须掺入点亮 `led_red/led_green` 的帧** + white/眩光/弱光/空盘/边角，覆盖部署相机的曝光分布。
  - **A19（★ fp16 兜底=仅诊断）**：无合适校准集时可先出 fp16（`convert_rknn.sh --onnx /work/build/vision/go4_s.onnx --target rk3562`，不加 `--quantize`）**仅验 NPU 链路**；fp16≈fp32、召回≈`.pt` 但**不是出厂制品**。B7 验收与 E 出厂**必须是同一份量化 INT8 `.rknn`**（记 sha256），fp16 制品单独命名、勿混入。
- [ ] **B3 Mac：转 RKNN（Docker，rknn-toolkit2 2.3.2，target=rk3562）**：
  ```bash
  cd ＄WORKTREE  # 含 katrain/vision/tools/Dockerfile.rknn；PROJECT_ROOT 会挂成 /work
  ./katrain/vision/tools/convert_rknn.sh \
    --onnx /work/build/vision/go4_s.onnx --target rk3562 \
    --quantize --dataset /work/build/vision/calibration.txt   # 全用容器内 /work/... 路径（A3）
  # 产出 build/vision/go4_s_rk3562.rknn + go4_s_rk3562.meta.json（A2：export_rknn 命名 {stem}_{target}）
  ```
  评审修订：
  - **A2（★ 文件名）**：产物实名 = **`go4_s_rk3562.rknn`**（`export_rknn.py:124` = `{onnx_stem}_{target}`），不是 `go4_s.rknn`。下游 B6/C2/E3 一律用此实名。
  - **A17（★ 版本序）**：本步（转换）用的 toolkit2 版本须与 **B4 从设备 `librknnrt.so` 读到的运行时版本匹配**——故 **B4 的「读设备 `.so` 版本」应先于 B3 做**（见 B4 重排注）；`Dockerfile.rknn:24` 是 `--no-deps rknn-toolkit2` 无版本钉，须显式钉到与设备匹配的 2.3.x 并记 sha。
  - `export_rknn.py:19 SUPPORTED_TARGETS` 含 `rk3562`；`mean_values=[[0,0,0]] std_values=[[255,255,255]]` 已内置 = 输入 /255 归一（A? 归一化契约：`rknn_backend.py:_preprocess` 默认 `nhwc_uint8` = 归一化烘进模型；若 meta 标 `nchw_float32` 才在 host /255——转换与运行时须一致，B7 用 ONNX↔RKNN 同帧张量对拍确认）。
- [ ] **B4 SBC：确认 librknnrt 版本、装 rknnlite 运行时**（进 `venv-katrain`；⚠️ **上机改动 → 需 go-ahead**）：
  > **A17 重排（★）**：**「读设备 `.so` 版本」这一步要先于 B3 做**——B3 的 toolkit2 build 版本、B4 的 lite2 wheel、设备 `librknnrt.so`、驱动 v0.9.8 是**四者必须对齐**的链条；先读版本再钉 toolkit/wheel，别 build 完才发现不匹配。
  ```bash
  ssh rk3562-direct 'strings /usr/lib/librknnrt.so | grep -iE "librknnrt version" | head'   # ← 先做，记版本
  # 装与设备 .so **完全同版**的 rknn_toolkit_lite2 aarch64/cp311 wheel（不是 2.3.* glob，是实测那一版）
  ssh rk3562-direct '/opt/smartbox/venv-katrain/bin/pip install <rknn_toolkit_lite2-<EXACT>-cp311-*aarch64.whl>'
  ssh rk3562-direct '/opt/smartbox/venv-katrain/bin/python -c "from rknnlite.api import RKNNLite; print(\"rknnlite OK\")"'
  # + init_runtime soak（真加载 go4_s_rk3562.rknn 并 inference 一帧），import OK ≠ runtime OK
  ```
  **风险**：`import rknnlite` 成功 ≠ `init_runtime()`/inference 成功；wheel 与 `.so` 不匹配 `init_runtime` 返错误码（`rknn_backend.py` raise）。**A34/R1**：换/更新设备 `/usr/lib/librknnrt.so` 会波及**同机其它 NPU 消费者**，属**受控迁移**（单列审批 + 回滚），不是顺手兜底。记 wheel/toolkit/`.so`/driver 四者版本 + sha。
- [ ] **B5 SBC：装视觉/串口依赖**（`venv-katrain` 当前缺 cv2/numpy/pyserial）：
  ```bash
  ssh rk3562-direct '/opt/smartbox/venv-katrain/bin/pip install "numpy<=1.26.4" opencv-python-headless pyserial'
  ssh rk3562-direct '/opt/smartbox/venv-katrain/bin/python -c "import cv2,numpy,serial; print(cv2.__version__, numpy.__version__)"'
  ```
  （vision worker 是 katrain server 的子进程，用 `venv-katrain` 解释器 → 依赖必须装进 `venv-katrain`。）
- [ ] **B6 SBC：部署模型到出厂路径**（⚠️ go-ahead）：`scp` 到暂存后 `install -m0644` 到 **`/opt/smartbox/share/katrain-vision/go4_s_rk3562.rknn`(+`.meta.json`)** —— **A6：与 E3/E4 出厂路径同一**，让 C/D 验证的就是出厂制品。服务只读模型 → `ProtectSystem=strict` 下只读 `/opt` 完全 OK（原文「勿放只读 /opt」是把「服务不能写」误当「不能读」，已更正）。
- [ ] **B7 SBC：离线测**端到端**帧率（回答用户「每秒多少帧」）**：⚠️ 用**一次性 venv**（勿污染 `venv-katrain`，go-ahead 前不上机）。
  - **A18（★ 测生产管线非 raw 帧）**：运行时是对**几何 warp 后 + `--vision-frame-average 8` + `--vision-enhance clahe`** 的板面图跑 `StoneDetector.detect()`（`pipeline.py`），**不是** raw `/dev/video0`。测量须含 warp/均值/CLAHE 全链，并报 **p50/p95 从「物理落子」到「移动被接受」的端到端延迟**（不是裸 infer ms），对照 `--vision-move-frames` 默认 5。
  - **A32（热）**：无风扇 RK3562 整局连跑——除冷启 100 帧突发，另测**热浸后稳态** FPS + 观察是否 throttle。
  - 模型用 `/opt/smartbox/share/katrain-vision/go4_s_rk3562.rknn`, `backend="rknn"`；核对识别到黑/白/LED。
- **Verification**：`init_runtime` + 一帧 inference 成功（非仅 import）；端到端 p50/p95 延迟 + 冷/热 FPS 数值（回填本节与 [[project_kiosk_golaxy_physical_play]]）。
- **Review checkpoint**（**A16 可证伪化**）：拿一个**留出的带标注小集**（含 white/led）测 `.rknn` **逐类召回**并设阈值（对照 `.pt`/ONNX），而非「肉眼看有结果」；FPS 满足落子确认（≥5–10 FPS 端到端）。fp16 vs 最终 INT8 制品各记 sha，出厂 = 验收同一份。

---

### Phase C — 接线 katrain（systemd 参数开启 vision+capture+LED）

- [ ] **C1 备份现单元**：`ssh rk3562-direct 'systemctl cat smartbox-katrain > /root/smartbox-katrain.service.orig-20260712'`。
- [ ] **C2 加 drop-in 覆盖 ExecStart**（`systemctl edit smartbox-katrain`），补齐视觉/采集/LED 参数（值参照 [[reference_mac_kiosk_launch]] 的 Mac 验证配方，把 backend 换 rknn、串口换实测 `＄LED_PORT`）：
  ```ini
  [Service]
  # A7: worker/kiosk-build 都 gate 在 KATRAIN_MODE==board（server.py:2350/554）——drop-in 只覆盖
  # ExecStart，须确认基单元已有此 env；没有则本行显式补（否则视觉走 inproc/错构建）。
  Environment=KATRAIN_MODE=board
  ExecStart=
  ExecStart=/opt/smartbox/venv-katrain/bin/python -m katrain.web.server --host 127.0.0.1 --port 8081 \
    --vision-backend rknn \
    --vision-model /opt/smartbox/share/katrain-vision/go4_s_rk3562.rknn \
    --vision-camera 0 --vision-resolution 1920x1080 \
    --capture-camera 0 --capture-resolution 1920x1080 \
    --vision-confidence 0.40 --vision-confidence-keep 0.30 --vision-ambiguous-confidence 0.42 \
    --vision-enhance clahe --vision-auto-exposure software --vision-ae-target 120-170 \
    --led-serial-port /dev/serial/by-id/＄LED_BY_ID --led-baud-rate 115200 \
    --hint-engine local --hint-top-n 3
  ```
  评审修订（★ 复验）：
  - **A1**：`--vision-ae-target` 收 **`LO-HI` 带区间**（`config_service.py:66` 做 `.split("-")` 解包）——标量 `145` 会 `ValueError` 崩视觉。用 `120-170`（[[reference_mac_kiosk_launch]] 的 `145` 是错的，一并更正）。
  - **A2+A6**：模型实名 = `export_rknn` 出的 `go4_s_rk3562.rknn`（`{stem}_{target}`），**路径与 E3/E4 出厂路径统一**为只读 `/opt/smartbox/share/katrain-vision/`（服务只读模型，`ProtectSystem=strict` 下只读 OK；单板 bring-up 由 B6 `install` 到此）——这样 C/D 验证的就是 E 出厂的同一制品，消除「验 `/mnt/data`、出厂 `/opt`」分裂。
  - **A7**：`Environment=KATRAIN_MODE=board`（见上注）。
  - **A12**：串口用 `/dev/serial/by-id/...` 稳定路径（内核免费提供、免 udev），别用会漂的 bare `ttyACM0`；原生 CDC 下 `--led-baud-rate` 是 no-op。
  - 原有约束仍在：第一行空 `ExecStart=` 是 systemd 清原值的必需写法；`--capture-camera` 必给否则几何标定不起、setup 页恒显未连接；vision 与 capture 必须同 index 同分辨率否则 `server.py` `ValueError`。
- [ ] **C3 设备权限 + 沙箱全审（A21，★ 不止 `PrivateDevices`）**：`systemctl show smartbox-katrain` 审**生效单元**：`ProtectSystem`/`DevicePolicy`/`DeviceAllow`/`ReadWritePaths`/`ReadOnlyPaths`/`SupplementaryGroups`/`BindPaths`。逐项证服务身份能：开 `/dev/video0` 与 `＄LED_BY_ID`（cgroup device 控制器，非仅 DAC）、**读**模型 `/opt/smartbox/share/katrain-vision/`、**写** `~/.katrain`（`geometry_lock.npz`、§11 credentials）——`~/.katrain` 靠 `BindPaths=/mnt/data/weiqi/dot-katrain:/root/.katrain` 落到可写区，**须实测确认该 bind 生效**（`dataoffload` 硬化 profile 恰是 `DevicePolicy=closed`/`DeviceAllow=` 可能出没处）。root 运行不自动绕过沙箱。
- [ ] **C4 SBC v4l2 曝光（A22，★ 单一曝光主，别打架）**：注意**已有一个 in-process 硬件锁**——`camera.py:168-173` 在 `lock_exposure`（`capture_service.py:33` 默认 True）时置 `CAP_PROP_AUTO_EXPOSURE=0.25`。它与 `--vision-auto-exposure software` 若同时动会互相拉扯/过曝 LED 锚点。**先 `v4l2-ctl -d /dev/video0 --list-ctrls-menus` 探真控件名/范围**，选**一个**曝光主，记录 set/read-back 值，**几何标定前先稳住曝光**；`auto_exposure`/`exposure_time_absolute`/`gain`/`power_line_frequency` 各机可能命名不同（别照抄）。V4L2 控件插拔/重启会复位 → **每次设备起都设**（非一次性，E7 同理）。
- [ ] **C5 重启并看日志**：`systemctl daemon-reload && systemctl restart smartbox-katrain`；`journalctl -u smartbox-katrain -f` 应出现 vision worker 启动、模型加载成功、摄像头打开、几何标定服务、LED 串口打开（**对比启动前只有健康检查的基线**）。
- [ ] **C6 setup 页自检（A8，★ `locked:true` 在从未标定的板上为假）**：`server.py:484-485` 仅 `if geo_path.exists()` 加载锁、529-530 仅 `if geometry is not None` 推送——**启动自推是「重启持久」不是「首次标定」**。全新板无 `geometry_lock.npz` ⇒ `geometry=None` ⇒ `recognition_ready=false` ⇒ 物理对弈死。故 C6 = kiosk 进围棋 → **实跑一次 13 锚点几何标定**（空盘 → 自动标定），再断言 `/geometry/status`：**`phase=ready` + `session_calibrated=true` + `capabilities.geometry_ready=true` + `recognition_ready=true`**（不是只看 `locked`），并存响应留证。
- **Verification**：日志无 traceback；setup 页摄像头+LED=已连接；`/geometry/status` **四字段全绿**（非仅 locked）；LED `strict=True` 连通预检通过（A12：`set_points(strict=False)` 断连也回 `ok:True`，会掩盖 LED 掉线）。
- **Review checkpoint**：视觉+LED 都上线后再进 Phase D 实机对弈；回写 provisioning 模板（Global Constraints）。

---

### Phase D — 实机三项对弈走查（= 用户原始 (2)(3)(4)）

> 前置：Phase A/B/C 全绿（摄像头识别 + LED 引导 + 星阵链路都通）。走查按 [[project_kiosk_golaxy_physical_play]] 的「三项必查」。
>
> **坐标帧走查方法（A13/A14，★ 覆盖多个独立翻转实现）**：翻转是 **row-only（`18-row`），col 不动**——其不动集是 **row=9（第 10 线中心行）**，且**星位↔星位**（`(3,3)↔(3,15)` 仍是星位）。故「中盘一个点对上了」可能只是**踩中镜像不变点**，证明不了全盘。走查须：
> - **定 ≥3 个非中心、非对称坐标**（跨上/下半盘，如 row∈{2,6,16} 且 col≠row），每个都**具名**：core(bottom-anchored) → screen(渲染) → vision/LED(row0=top,`18-row`) → GTP(`row+1`) → 链号，拍照/存事件日志留证。
> - **分别验各条独立翻转路径**（它们是不同实现，一条对≠全对）：① **每手 AI 引导**（`orchestrator:446 _setup_cells_from_state` + 对照的 `sync.py:437 game_state_stones_to_board`，最高频路径）；② 星阵 **`支招`**（HEAD `7d1b0c32` 刚恢复的 `platforms.py:181 _maybe_show_hint`）；③ **错误对话框坐标文本**；④ **提子/awaiting_removal LED**；⑤ 本地 `支招`（`hint.py:99 vision_rc`，仅 free）。

- [ ] **D1 自由对弈（本地 KataGo 引擎人机）**：**A15 前置（★）**——「本地引擎」实为 HTTP `http://127.0.0.1:8000`（`config.py:18 LOCAL_KATAGO_URL`），**不是子进程**；先确认该 KataGo HTTP 服务在机上在跑（否则回手全失败）。流程：物理落子被识别 → 引擎回手 → LED 引导。**核对**：按上「坐标帧走查方法」，用**≥3 个非对称点**验**每手 AI 引导 LED == 屏幕候选点**（不只中盘一点）+ `支招`(free 走 `hint.py`)；拿错子/压灯时**引导屏 + 语音实际出声**（A31：`useVoice.ts:24-28` 播放失败 `.catch` 静默，须真听到/看到，别默认它在响）。
- [ ] **D2 升降级对弈（A14 ★ `支招` 在 ranked 被 403）**：升降级=ranked，`analysis_allowed=False`（`interface.py:210`）+ `game_type!='free'→403`（`hint.py`）⇒ **§13 领地/支招/变化图全禁**，D1 的「支招坐标校验」在此**不可用**。故 D2 的坐标校验改用**每手 AI 引导 LED vs 屏幕**（该路径 ranked 仍在）+ **错误对话框坐标**。另核对定级/升降级结算与段位变化；识别+LED 不回归。
- [ ] **D3 跨平台星阵对弈（人机）**：真星阵账号登录（本项目 SMS 流程）→ 选星铠虾级别 → 物理落子 → 星阵 genmove 回手（`HTTP 200` 无 6003）→ LED 引导。**核对**：星阵 `支招` 翻转（`platforms.py:181`，HEAD 刚恢复）用非对称点验；**错误对话框坐标文本 == LED 实际点亮位置**；故意物理打劫回提观察 M3 静默循环（见 §follow-up）；认输无 `ForeignKeyViolation`。
- [ ] **D4 在机回归（勿回归，Global Constraints）**：**token 持久化跨 C5 服务重启**（重启后免重扫 SMS 自动重连）、**§12 让子**（塞子+轮走方）、**§13 领地/变化图**各点一次——不能只 D3 查 FK+6003。
- **Verification**：三项各连续多手识别+回手+LED 正确；**≥3 非对称点镜像核对通过**（各独立翻转路径都验）；语音+屏幕引导实际可感知；token/让子/道具/记谱不回归。
- **Review checkpoint**：走查结论 + 遗留缺陷（对齐 [[project_kiosk_golaxy_physical_play]] 的 follow-up M1–M4、I2 坐标帧）回报，决定是否 merge。

### Phase E — 固化进 `smartbox-software/provisioning`（golden image 可复制）

> **仓库 = `smartbox-software`（非本仓库）。** Phase A–D 在单板验证通过的每一项，都要回落成 provisioning 改动，使 `provision.sh ... → image-prep → dd` 出的镜像开箱即带视觉+LED。改后跑 `provisioning/tests/` 契约测试。

> **⚠️ E 顺序更正（A4+A5，★ 复验）**：原 E1「bump 到 `7d1b0c32`」+ E3「提交模型进 katrain 仓库」自相矛盾——`7d1b0c32` **不含** `katrain/vision/models/`（HEAD 实测无此目录），而 E3 提交模型**必产新 commit**。且 `.gitignore:31 models/` 会**吞掉** `katrain/vision/models/*.rknn`（`git check-ignore` 实证匹配）。正确顺序：
> **(a)** 在 katrain 仓库 `.gitignore` 加豁免 `!katrain/vision/models/` 且 `!katrain/vision/models/*.rknn`（或 `git add -f`）→ **(b)** 提交 `go4_s_rk3562.rknn`+`.meta.json`+制品清单 → 拿到**新 SHA** → **(c)** E1 bump 子模块到**该新 SHA**（非 7d1b0c32）→ 受 **Phase D 的 merge/tag 决定门禁**（别让 provisioning 依赖未合并/会被 rebase 的分支）。

- [ ] **E1 子模块 bump**：`smartbox-software/vendor/katrain` 更新到**含模型 blob 的新 commit**（见上顺序 (b) 产出的 SHA，**不是** `7d1b0c32`），且该 commit 已过 Phase D merge 决定；确保含 Tasks 0-13 + `katrain/vision/` + `katrain/vision/models/go4_s_rk3562.rknn`。
- [ ] **E2 视觉依赖进 katrain section**（`provision.sh` `install_katrain`，约 :424-428）：
  - 把 **opencv-python-headless** 加进 venv-katrain（当前只在主 venv）。**A28**：与 rknnlite 一样走**离线 wheel**（勿在线 PyPI，破坏离线纪律），并**钉 `numpy<=1.26.4`**（constraints/lock + hash）——否则某次 provision 解析出 numpy 2.x 与 rknnlite ABI 打架（手测机是 1.26.4）。
  - **rknnlite**：离线 wheel 放 `provisioning/wheels/`，**用 B4 从设备实测的那一确切版本**（不是 `2.3.*` glob），katrain section `uv_pip_install "$venv_kt" provisioning/wheels/rknn_toolkit_lite2-<EXACT>-cp311-*aarch64.whl`。
- [ ] **E3 模型 artifact 落地**（**决策已定 2026-07-12：`.rknn`+`.meta.json` 纯 blob 提交进 katrain 仓库 `katrain/vision/models/go4_s.{rknn,meta.json}`，经 `vendor/katrain` 子模块消费——与现有 KataGo net 完全同构**：humanv0/98MB 分析 net 就是纯提交在 `katrain/models/` 且 provision `:494` 从 `$vendor_katrain` 读；**不上 git-LFS，不放对象存储**。理由：烧到 N 机速度两法相同（模型已 dd 进镜像）；provision 时本地拷贝最快最稳、无网络无漂移；模型与消费它的 `stone_detector.py`/`rknn_backend.py` 随子模块 bump 原子对齐；~7–12MB 远小于已纯提交的 98MB net。仅当模型转大（数百 MB）或高频重训致 git 膨胀时才改「Stockfish 式 pinned-URL+SHA256」。）
  - **A2 实名**：文件是 `go4_s_rk3562.rknn`（+`.meta.json`），非 `go4_s.rknn`。`install -m 0644 "$vendor_katrain/katrain/vision/models/go4_s_rk3562.rknn"（+meta）` → `/opt/smartbox/share/katrain-vision/`（= C2/B6 同一路径，A6）。
  - **A4 前置**：提交前 katrain `.gitignore` 必加 `!katrain/vision/models/`（`models/` 会吞它，已实证）。
  - **A28/A29 制品清单**：随 blob 提交一份 `go4_s_rk3562.manifest`（源 `.pt` sha + 校准集 rev + toolkit2/lite2/`.so` 版本 + 输出 `.rknn` sha + license），让后人能证「这份权重怎么来的」。
  - **A29 消除矛盾**：本 E3「决策已定」与「本节风险/Open questions」里仍列「模型 artifact 分发未决」冲突——删/标记那条 open question 为已决。并记 git-膨胀风险：视觉模型**会重训**（`go4_x→1080p→4class` 轨迹），与 write-once 的 KataGo net 不同构；定**轮换/大小策略**（例如只留最新 + tag 历史），转大到数百 MB 时改「pinned-URL+SHA256」。
- [ ] **E4 systemd 模板加视觉/LED flag**（`provisioning/systemd/smartbox-katrain.service` 或新增 `.service.d/vision.conf`）：把 Phase C2 验证过的 `--vision-backend rknn --vision-model … --vision-camera 0 --capture-camera 0 --*-resolution 1920x1080 --led-serial-port … --hint-*` 一组固化进 `ExecStart`（当前模板 `:16` 是裸的）。
- [ ] **E5 LED 串口 udev 稳定节点（A25，★ 唯一匹配 + 排序）**：udev 规则**匹配 serial + USB interface/path**（不是只宽 `303a:*`——多 Espressif 会绑错节点），建 `SYMLINK+="smartbox-led"`，flag 用 `--led-serial-port /dev/smartbox-led`。VID 取 **A3 实测值**（占位 `__FILL_FROM_A3__`；若 A2 判为桥接则含 `1a86/10c4/0403`）。加 **service 排序**（`After=`/`BindsTo=` 该设备或经 systemd `.device` 单元 + 重连契约），避免 systemd 早于 symlink 起 → LED 开机连不上。单板 bring-up 已先用 `/dev/serial/by-id/...`（A12），E5 是金镜像的跨机稳定化。
- [ ] **E6 摄像头稳定性**：确认 `/dev/video0` 为板载 USB 摄像头稳定 index（多摄像头/枚举顺序风险）；必要时同样加 udev by-path 规则 + flag 用符号链接。
- [ ] **E7 曝光/相机控件（A26 更正：不是 firstboot 一次性）**：V4L2 控件在**插拔/USB reset/reboot 会复位** → 必须**每次 service/设备起都设**（`ExecStartPre=` 或设备 udev `RUN`，排在相机枚举之后、katrain 开相机之前），不是 firstboot 一次性。firstboot 只留**不可变**初始化。
- [ ] **E9 逐机几何标定（A16，★ 金镜像大缺口）**：几何锁**天生逐机**（`server.py:483-485` 仅 `if exists` 加载）——出厂镜像**没有** `geometry_lock.npz` ⇒ `recognition_ready=false` ⇒ 物理对弈**开箱即死**，直到有人跑一次标定。E 必须给**逐机首标定流**：firstboot/操作员引导（空盘 → 13 锚点标定 → 存 `~/.katrain/geometry_lock.npz`），装机 SOP 里固化。**这是 A8 的出厂对应项**，不能只在单板 C6 验一次。
- [ ] **E8 契约测试 + 全流程验证（A27 升级：不止查文本存在）**：更新/新增 `provisioning/tests/` 断言 katrain section 装了 rknnlite/opencv、systemd 带视觉/LED flag+`KATRAIN_MODE=board`、模型就位（**含 sha 校验**）。**加镜像级冒烟**（文本存在证不了能跑）：服务身份下 `import rknnlite` + **`init_runtime` 真加载模型**、`systemd-analyze verify`、udev 规则命中测试、`/geometry/status` readiness 断言、冷启/插拔硬件验收。在**一台干净板**跑完整 `provision.sh` → `image-prep` → 烧录 → 复验 Phase C6/D + E9 逐机标定 全绿。**A34**：清理手工 `systemctl edit` 的 `override.conf`（provisioning 装 `vision.conf` 后二者并存会合并）。
- **Verification**：干净板经 provisioning 后开箱即视觉+LED 可用；契约测试绿。
- **Review checkpoint**：确认 golden image 覆盖，提 smartbox-software PR。

### 本节风险 / Open questions（2026-07-12 评审后更新）
- **归属**：视觉+LED 的可复制部署在 `smartbox-software/provisioning`，非本仓库；Phase A–D 的单板命令只是验证手段，勿当最终交付（否则烧一台配一台）。
- **模型 artifact 分发** —— ~~未决~~ **已决（A29 消除矛盾）**：纯 blob 提交进 katrain 仓库 `katrain/vision/models/`（需 `.gitignore` 豁免）经子模块消费，见 E1 顺序 + E3；git-LFS/对象存储仅在模型转数百 MB 时再议。
- **LED ESP32 不枚举** —— **A10 更正**：先按 `lsusb` 分叉——`303a` 在总线但无 tty = host 端 `cdc_acm`/内核（软件可修）；总线全无 → ROM 下载模式判固件 vs 硬件；只有供电/D+/D- 接反才是真硬件（就地回报）。别一律判「改板」。
- **四版本对齐** —— toolkit2 build == lite2 wheel == 设备 `librknnrt.so` == 驱动 v0.9.8；B4 先读设备版本再钉（A17）；换 `.so` = 受控迁移非顺手兜底。
- **INT8 量化精度** —— s 模型 INT8 弱光/白子/**LED 类**召回可能降（A20：校准集须含点亮 LED 帧）；fp16 仅诊断、出厂=B7 验收的同一份 INT8（A19）。
- **RK3562 单核 NPU FPS** —— B7 实测**端到端 + 热稳态**（A18/A32），非 raw/冷突发；落子确认需 ≥5–10 FPS 端到端。
- **逐机几何标定（A16）** —— 出厂镜像无 `geometry_lock.npz` ⇒ 开箱物理对弈死；E9 必须给逐机首标定流。
- **多游戏 smartbox 互斥（A30）** —— board 模式服务持续独占相机；须确认围棋期 katrain 独占 `/dev/video0`、与其它游戏 target/mutex 不冲突。
- **provisioning 回写** —— 改动只在 `/etc` drop-in 会被重 provision 覆盖，须回 smartbox-software 仓库模板；回写后清理手工 `override.conf`（A34）。
- **go-ahead 门禁（A9）** —— Phase A–D 每条上机命令改动生产机，需用户显式 go-ahead + 回滚点，非「只诊断」。
