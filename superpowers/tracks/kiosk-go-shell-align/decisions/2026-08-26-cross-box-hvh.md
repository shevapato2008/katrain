# 一、另外三家到底怎么做的

**一句话:三家里只有国际象棋真做了在线大厅,形状是「盒端只出一张跳转卡,大厅屏和对局屏都由云端托管、规则权威在云端 adapter」;中国象棋和五子棋今天连入口都是灰的,云端也没有它们的实现。三家不一样,分开说。**

## 1.1 国际象棋(已上线)—— 盒端整页跳离 + 云端全权威大厅

| 层 | 住在哪 | 证据 |
|---|---|---|
| 入口 | 盒端棋类模块首页一张卡,带的不是 `path` 而是 `leaveTo` | `chess/ui/src/play/homePresentation.ts:82-91` |
| 跳转 | `window.location.assign()` 整页离开本源 → 盒上 wizard:8080 `/api/lobby/enter?game=chess` → 铸 30 秒一次性码 → 302 到云端 `/auth/callback` | `chess/ui/src/App.tsx:34`;`chess/ui/src/shell/boxUrls.ts:8,32`;`setup-wizard/app/routers/lobby.py:42-88`;`lobby_api/code_repo.py:26-45` |
| 大厅/房间 UI | **云端托管**。源码在 chess/ui 仓,但作为第二个构建目标产出,产物直接落进 lobby-platform 包内静态目录 | `chess/ui/package.json:16`;`chess/ui/vite.lobby.config.ts:27-29`;`lobby_api/main.py:162-168` |
| 对局权威状态 | **云端 lobby 进程内存**:`SessionManager._sessions` 里的 `GameSession`,持 `ChessAdapter.new_game()` 造的 `ChessGame`(内部包一个 `chess.Board`,外加双方 id / 着法串 / `_forced_result`) | `lobby_api/session.py:367`;`adapters/chess_adapter.py:17-25,175-176` |
| 走法判定 | **云端**。客户端只 POST `{session_id, move}`,云端在 session 锁内 `apply_move`,四道校验(已终局 / 回合 / UCI 解析 / `legal_moves`),`WrongTurn`→403、`IllegalMove`→400 | `lobby_api/routes.py:218-220,196-199,232-235`;`chess_adapter.py:57-66` |
| 客户端角色 | 本地 chess.js **只做拖拽预筛**,不推进局面 | `chess/ui/src/lobby/RoomBoard.tsx:3-7,150-151,173` |
| 实体盘 | **不可用,而且不是在这一层断的** —— chess 盒端全仓零视觉代码,`BoardConnectionStore` 是恒返回「未连接」的桩;云端大厅 bundle 连 import 都没有 | `chess/ui/src/shell/BoardConnectionStore.ts:11-21`;`chess/ui/src/shell/boardStatus.ts:41-44` |
| 落账 | 两处:①云端 `game_records` 一 session 一行(**只在终局写**,`session_id` UNIQUE 兜幂等);②事后盒端 `POST /api/games/lobby/sync` 把谱拉回本地复盘库,落成 `mode='lobby'` | `lobby_api/models_db.py:54-83`;`db_games.py:8-25`;`routes.py:166`;`chess/api/chess_api/main.py:439`;`chess/api/chess_api/db.py:147` |
| 进程重启 | 在飞的局全丢,这是明确写下、两家已同意的代价(J5) | `docs/superpowers/specs/2026-08-18-multichess-lobby-design.md:77,1707` |

附:云端大厅有 bot —— 30 个伪装成真人的 `users` 行(判别位只在服务端 `lobby.bot_accounts` 表,一个字节不上 wire),引擎是 lobby 进程自起的 Stockfish 子进程、depth 5 省中央算力,bot 走的是和真人**完全相同**的权威路径。`bot_pool.py:122-146`;`models_db.py:181-194`;`chess_adapter.py:117-120,146`;`bot.py:143-148`

## 1.2 中国象棋 / 五子棋(都没做)

| 层 | 状态 | 证据 |
|---|---|---|
| 入口 | 象棋:硬编码 `disabled`,无 onClick、无 URL;五子棋:`SoonCard`,写死 `<button disabled>` | `xiangqi/ui/src/screens/HubScreen.tsx:125`;`gomoku/ui/src/play/PlayModeSection.tsx:21-29,260` |
| 路由 | 象棋 `play/lobby` 存在,返回「建设中」占位屏 | `xiangqi/ui/src/App.tsx:1371,1114-1116` |
| 云端 | **两家在云端大厅里没有 adapter**。生产注册表只有 chess,`/ws/lobby?variant=xiangqi` 建连即 1008,三条 REST 一律 400 | `lobby_api/main.py:130-131`;`admin_bots.py:20`;`ws.py:208-210`;`routes.py:247-249` |
| UI 产物 | 只有 `chess/ui` 有 `build:lobby`;xiangqi/gomoku 的 `ui/src/lobby/` 目录在磁盘上不存在 | `chess/ui/package.json:16`;`superpowers/shared/lobby-wire/generate.py:201-205` |
| 更深一层 | 五子棋后端**没有人人对局这个概念**,`newgame` 一局必有一方是引擎 | `gomoku/ui/src/play/PlayModeSection.tsx:262-264` |

两条纠正,避免下游读错:

- 那张 disabled 卡是**被登记为待办**(徽标「即将上线」、类名 `is-todo is-soon`,`HubScreen.tsx:21,28`),不是一条「不做」的裁定。两处测试断言的只是「这张卡今天是 disabled」,实现它时那两条断言要一并改。
- **不要把「云端只存终局」当通例**。那是 lobby 的 `game_records` 这一张表的性质。三家自己的本地 sqlite 是**开局那一刻就插一行「进行中」**并逐手刷流水的(`gomoku/api/gomoku_api/db.py:246,259,295-310`;`chess/api/chess_api/db.py:328,615`),升降级那条链在云端还有带心跳的活局表(`ranked_api/envelope/models_db.py:217-231,392-395`)。

# 二、是不是瘦客户端

**是。而且比「瘦客户端」还极端一层:在线对局那一页根本不是盒子上的页面。但盒子本身没有变瘦。**

瘦到什么程度:

- 那一页由云端 origin 提供,刻意不带 react-router,退出用 `history.back()`,因为它和盒端页在不同源 —— `chess/ui/src/lobby/main.tsx:13-17`
- WebSocket 打的是 `window.location.host` = **云端自己**,不是盒子 —— `chess/ui/src/lobby/client.ts:262-264,358-359`
- 一步棋的唯一来源是触屏点击 → `POST /api/move` —— `RoomBoard.tsx:153-159`;`RoomPage.tsx:170-171`;`client.ts:396-402`
- 局面永远来自服务端 fen —— `RoomBoard.tsx:3-7`

还留在盒上的(所以「瘦」的是那一页,不是盒子):

- 盒端 chess 服务 :8002 照常在跑,只是这一局不参与 —— `provisioning/systemd/smartbox-chess.service:11,17`;`chess/api/chess_api/config.py:193-194`
- **身份**:一次性码由盒上 wizard 铸,盒上的 `sb_session` 才是登录状态的根 —— `setup-wizard/app/routers/lobby.py:55-88`
- **复盘库**:云端下完的局要靠盒端主动 `POST /api/games/lobby/sync` 拉回来才进本地复盘 —— `chess/api/chess_api/main.py:439`
- 人机、本地训练、升降级三条链全在盒上。升降级是**本地引擎下棋、只把结果送云端记账** —— `xiangqi/api/xiangqi_api/config.py:161-163`

# 三、围棋要不要照搬

**不必须。** 照搬到「共享大厅平台」那条路今天还走不通:围棋不在 `LOBBY_UI_GAMES` 里,云端拼不出 `/lobby/go/`,`game=go` 会静默落到大厅首页 —— `lobby_api/lobby_ui.py:14,18,21-23`。

先摆出围棋今天已有的东西,三条路线都建在这上面:

- **围棋自己的大厅、撮合、邀请、房间全都已经写好了**:`/ws/lobby`(`katrain/web/server.py:2353`)、排队 → `create_multiplayer_session` → 双方 `match_found`(`server.py:2415-2465`)、直邀带 120 秒 TTL 且一次性消费(`session.py:369,377,385`)、前端 `LobbyPage` 已挂在 `/kiosk/play/pvp/lobby`(`KioskApp.tsx:105`;`PlayPage.tsx:128`)。
- **缺的只有一件:它是进程内的。** `LobbyManager._online_users` 是内存 dict(`session.py:334,336`),`/users/online` 读的是同进程的 lobby_manager + 本地 user 表(`users.py:73-80`)。「在线」= 连着**这一台盒子**的那一个 uvicorn 进程。board 模式的 lifespan 自己写着这两个是 placeholder,而且 `game_repo = None`(`server.py:444-447`)。
- **围棋的规则权威不需要引擎**:提子/劫/自杀全是纯 Python(`katrain/core/game.py:153-215`);认输、超时、双 pass 终局都不经引擎(`interface.py:1366,1370`;`game.py:315-317`)。**只有数子出分要 KataGo**(`server.py:1838-1843` 读 `current_node.score`)。
  - 纠正一条被当成排除理由的话:「围棋缺了 KataGo 就判不了终局」是过强的。缺了只是**没有分数**,局照样能从第一手下到终局。
- **盒上有本地 KataGo**:`smartbox-katago-api.service:2,13`(:8000),katrain 走 http backend 连它(`smartbox-katrain.service:2`),引擎对 katrain 本来就是进程外 HTTP(`katrain/web/core/engine_client.py:7-15`)。所以「围棋必须把 GPU 依赖引进大厅进程」在**盒上**不成立;它只在**共享 lobby 云端**成立 —— 那个进程零出站 HTTP 客户端,镜像里只有 Stockfish(`platform-app/deploy/Dockerfile:74-78`、`engines.lock`)。

---

## 路线 A —— 云端只做撮合与账本,对局权威留在盒上

- **要动什么**:云端 katrain 加一个「在线名单 + 排队/邀请 + 着法转发 + 终局裁定」的服务面;盒端 `RemoteAPIClient` 加一条长连 —— 它今天**全是 httpx REST、零 WebSocket、零 lobby 方法**(全部方法就是 tsumego/kifu/user_games/ai-ladder/live/tutorial,`katrain/web/core/remote_client.py`);两台盒各维持自己的 `WebSession`,一方本地权威、另一方跟随。
- **盒上留什么**:全部。相机、几何标定、LED 串口、识别 worker、编排器、本地 KataGo、本地库。
- **实体盘**:能用,但有一个必须一起改的洞(见下)。
- **工作量**:中。围棋的大厅 UI、撮合、房间页都已经有了,不用重画。
- **有先例,不是凭空设计**:升降级 AI 对局就是这个形状 —— 盒上本地引擎下棋,云端只持账本,靠 reserve → activate → heartbeat → pending-settlement → end 五个 REST(`remote_client.py:248-297`)。这条链今天在跑。
- **第一个硬问题:LED 不会为远端真人亮灯。** `_guided_colors_from_state` 只把「AI 色」和 `platform_engine_color` 放进引导集合(`physical_play_orchestrator.py:415-434`),而 `create_multiplayer_session` 把两边都设成 `player_type="human"`(`session.py:103,105`)⇒ 集合为空 ⇒ `_needs_guidance` 恒 False(`physical_play.py:123-128,144`)⇒ 对面下的那一手,盒上不会亮灯告诉你摆哪。这条对 katrain 现有的大厅房间**已经成立**,不是新引入的。要么给远端真人色加一个和 `platform_engine_color` 同形的标记,要么明确「跨盒对弈不用实体盘」。

## 路线 B —— 照搬国象:大厅屏和房间屏搬到云端 katrain,盒子变瘦客户端

- **要动什么**:云端 katrain 出一套大厅+房间页;盒端出一张跳转卡,可复用 wizard 那条一次性码链(`/api/lobby/enter` 今天只认三个 slug,加一个 `go` 是一行,`setup-wizard/app/routers/lobby.py:84-86`,同时要动 `lobby_ui.py:18`)。云端 katrain 是 server 模式、逐手分析开着(`interface.py:157,226`),数子不会 400。
- **盒上留什么**:身份(`sb_session`)、本地复盘库、人机/死活/摆谱等全部离线功能。
- **实体盘:用不了。** 前端所有 vision/LED 调用都是相对路径 + 同源拼 URL(`katrain/web/ui/src/utils/websocketUrl.ts:26-28`),页面从云端加载 ⇒ `/api/v1/vision/*` 一起指向云端,那里没有相机。更硬的一层:`/api/v1/vision/bind` 必须能在**本进程**的 `session_manager` 里查到那个 session(`katrain/web/api/v1/endpoints/vision.py:184-186`),而 session 只活在内存里 —— 云端的 session 和盒上的相机结构上碰不到一起。
- **工作量**:大。两屏新做 + 身份三处不对齐。
- **第一个硬问题:`generation` 这一维在别的 origin 上不存在。** 盒上 katrain 的本地 JWT 带 `box_generation`,每次验 token 都要等于进程内 `active_generation`,换人/登出会置 None 并 1008 踢掉所有 socket(`katrain/web/core/box_sso.py:35-47`;`auth.py:214`)。「一台盒子换人,上一个人的凭据当场作废」这条不变量,在另一个 origin 的会话 cookie 上不成立。此外严格模式的 katrain 只认 `sb_go_token` 一个 cookie、WS 还要 Origin 精确相等(`box_sso.py:12,72-74,78-83`),浏览器可达的登录/注册/刷新/登出全部 403 —— 「从云端回落到围棋」今天没有入口。

## 路线 C —— 不搬云端,两台盒子经一个轻量中继互连

**技术判断:中继这个形状成立;「纯转发、两台盒各判各的」不成立。**

成立的那一半,理由落在既有事实上:

- 盒子之间不需要打洞。盒端已有一条成熟**出站**通道到云:`RemoteAPIClient` 的 base_url 来自 `KATRAIN_REMOTE_URL`,由 provision.sh 烧进每台盒的 `/etc/smartbox/identity.env`(`katrain/web/server.py:389-394`;`provisioning/provision.sh:490-491`);wizard 那边还有一条同形的中继给象棋升降级用(`http://127.0.0.1:8080/api/internal/xiangqi-ranked`,`xiangqi/api/xiangqi_api/config.py:161-163`)。「两台盒各自出站到一个中继」是既有形状的延伸,不是新基建。
- 围棋规则是纯确定性 Python(`katrain/core/game.py:153-215`),同一串着法在两台盒上算出同一个局面 —— **局面这一层不需要中央权威**。

不成立的那一半(为什么不能只做转发),四条:

1. **数子那一下没有单一裁判。** `_complete_count` 读 `current_node.score`(`server.py:1838-1843`),那是 KataGo 的 `scoreLead`。两台盒各有一台本地 KataGo,各算各的,两个数不保证相等 ⇒「谁的分数算数」没有答案。而且 board 模式下 MODE_PLAY 抑制逐手分析(`interface.py:157,226`),不显式触发一次分析,`score` 常态是 None,数子直接 400。
2. **两台盒上不存在同一个用户。** 盒上 katrain 的用户是 shadow user,键是**上游用户名**(`katrain/web/api/v1/endpoints/auth.py:180-185,209`);盒 A 的库里没有盒 B 那个人的行。而账号权威本来就在云端 katrain(`setup-wizard/app/config.py:45-46,191-192`;`provision.sh:490-491`)⇒「不搬云端」在身份这一层做不彻底,中继要么带一份可验的身份断言,要么回云端查。
3. **前端结构上连不到对方那台盒。** 盒上 katrain 绑 `--host 127.0.0.1 --port 8081`(`provisioning/systemd/smartbox-katrain.service:21`),前端一律用 `window.location.host` 拼 URL(`websocketUrl.ts:26-28`)。所以中继必须是**服务端到服务端**(盒 A 的 katrain 进程 ↔ 中继 ↔ 盒 B 的 katrain 进程),不能是浏览器直连 —— 这条链今天在 katrain 里一行都没有。
4. **超时/断线/落账没有仲裁人。** 盒上 `game_repo` 恒为 None(`server.py:447`),多人对局的落账路径在盒上是死的,源码注释自己记着这件事(`server.py:1807-1820`)。中继再轻,也得至少持一份「这局归谁、结果是什么」。

⇒ **结论:中继要么长成路线 A 的样子(云端持一份对局元数据 + 终局裁定,着法转发,规则和引擎留在盒上),要么就是路线 B。「纯 socket 转发的哑中继」这一档在围棋上不成立,卡点是数子和落账,不是网络。**

## 三条路线共同要先答的一个产品问题

**跨盒对弈到底用不用实体盘。** 用 —— 先解 `guided_colors` 那个洞(路线 A/C 可解,路线 B 结构上不可解);不用 —— 三条路线都简单一档,路线 B 的最大障碍直接消失。

# 四、还没查清、但会改变结论的

1. **「围棋保留自有后端(D1)」是不是 Fan 拍的板。** 仓里唯一出处是那份 design spec 表头的自称(`docs/superpowers/specs/2026-08-18-multichess-lobby-design.md:24`),而同一份文档第 3 行状态还是「待 Fan 复核」,没有第二处独立记录。若这条不是裁定,路线 B 的前提就松动。→ 查:Fan 自己的记录 / 那份 spec 的 review 回执。
2. **`LOBBY_ORIGIN` 的实际值** —— 国象在线大厅今天连的是哪台云端机器。那个值来自设备上的 `/etc/smartbox/cloud-endpoints.env`,两个仓里都没有(`chess/ui/src/shell/boxUrls.ts:19`)。→ 查:板上 `cat /etc/smartbox/cloud-endpoints.env`。
3. **盒上数子到底会不会 400,我没有真跑过。** 推理链每一环的代码都读到了(`KATRAIN_MODE=board`,`smartbox-katrain.service:14` → `suppress_auto_eval`,`interface.py:157` → `score is None` → 400,`server.py:1841`),但没有发过一次 `/api/count/request`。这条决定路线 A/C 里「数子」要补多大一块。→ 查:本地起 board 模式下一局到双 pass。
4. **`/kiosk/play/pvp/lobby` 这张卡在盒上今天是不是可见的。** 路由无条件注册(`KioskApp.tsx:105`)、入口卡不 disabled(`PlayPage.tsx:128`),但盒上 lobby 是 placeholder(`server.py:444-447`)⇒ 用户点进去会看到一个永远只有自己的大厅。是否已在盒上暴露,我没上板确认。→ 查:板上打开那一页,或 kiosk build 里有无开关把它藏起来。
5. **云端 katrain(go.sailorvoyage.top)现在是不是 server 模式、逐手分析是不是真开着。** 路线 B 的「数子不会 400」建在这上面,我只读到代码分支(`interface.py:157`),没读那台机器的部署配置。→ 查:那台机 katrain-web 容器的 `KATRAIN_MODE` 与 engine 配置。
6. **共享 lobby 云端主机能不能访问某个 KataGo。** 两个仓里都没有任何「lobby → katago」的地址或凭据 —— 这是部署事实,源码里本来也不该有。只在「围棋接共享大厅」这条被重新提上来时才需要。→ 查:那台机器的 compose / 防火墙。
7. **象棋/五子棋大厅的排期与阻塞点。** `docs/superpowers/plans/2026-08-18-multichess-lobby.md` 存在,我只读到零星几行,没通读任务清单。若那份计划已排了「四家统一」的路径,围棋选型应与之对齐而不是另起。→ 查:通读那份 plan 的任务清单。