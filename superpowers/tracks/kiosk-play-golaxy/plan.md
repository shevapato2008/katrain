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
