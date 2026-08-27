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

1. ~~**「围棋保留自有后端(D1)」是不是 Fan 拍的板。**~~ **2026-08-27 已查清:是。见下面「五、复审」①。我当时的依据本身是错的** —— 那份 spec 第 3 行的「待 Fan 复核」是**起草时的流程,不是状态**,而 `:22` 的 `## 1. 已定决策(2026-08-17/18,Fan 拍板)` 才是。**同一份文档里一行流程和一行状态并排,我读了流程那行。** 国象 track 已把表头改掉,并把「它骗过谁」写进文件。
2. **`LOBBY_ORIGIN` 的实际值** —— 国象在线大厅今天连的是哪台云端机器。那个值来自设备上的 `/etc/smartbox/cloud-endpoints.env`,两个仓里都没有(`chess/ui/src/shell/boxUrls.ts:19`)。→ 查:板上 `cat /etc/smartbox/cloud-endpoints.env`。
3. **盒上数子到底会不会 400,我没有真跑过。** 推理链每一环的代码都读到了(`KATRAIN_MODE=board`,`smartbox-katrain.service:14` → `suppress_auto_eval`,`interface.py:157` → `score is None` → 400,`server.py:1841`),但没有发过一次 `/api/count/request`。这条决定路线 A/C 里「数子」要补多大一块。→ 查:本地起 board 模式下一局到双 pass。
4. ~~**`/kiosk/play/pvp/lobby` 这张卡在盒上今天是不是可见的。**~~ **2026-08-27 部分查清,而且我写在这条里的前提是错的:「盒上 lobby 是 placeholder」不成立。** 见下面「五、复审」②。那个词来自 `server.py:444` 一行注释,而它下面构造的是**和 server 模式逐字相同的真 `LobbyManager()`/`Matchmaker()`**;`/ws/lobby` 无条件注册。**剩下没查清的只有「板上那张卡视觉上可不可见」,要上板。**
5. **云端 katrain(go.sailorvoyage.top)现在是不是 server 模式、逐手分析是不是真开着。** 路线 B 的「数子不会 400」建在这上面,我只读到代码分支(`interface.py:157`),没读那台机器的部署配置。→ 查:那台机 katrain-web 容器的 `KATRAIN_MODE` 与 engine 配置。
6. **共享 lobby 云端主机能不能访问某个 KataGo。** 两个仓里都没有任何「lobby → katago」的地址或凭据 —— 这是部署事实,源码里本来也不该有。只在「围棋接共享大厅」这条被重新提上来时才需要。→ 查:那台机器的 compose / 防火墙。
7. **象棋/五子棋大厅的排期与阻塞点。** `docs/superpowers/plans/2026-08-18-multichess-lobby.md` 存在,我只读到零星几行,没通读任务清单。若那份计划已排了「四家统一」的路径,围棋选型应与之对齐而不是另起。→ 查:通读那份 plan 的任务清单。
---

# 五、复审(2026-08-27,与国象 track 跨 session 对证)

Fan 让我找国象那个 session(`smartbox-software-chess-features`,worktree
`/Users/fan/Repositories/smartbox-software-chess-features`,分支 `feat/chess-features-2026-07-16`)
核实「瘦客户端 = 实体盘不可用」是否属实,并商定根本改法。往返六轮,双方各自回源核对方引的每一处。
**代码只动了一行注释(`server.py:444`),其余全部等 Fan。**

## ① 这不是新发现,是一个**已登记的待触发决策**,而触发条件今天到了

`smartbox-software/docs/superpowers/plans/2026-08-18-multichess-lobby.md:1492`(在
「## 复审触发器」标题下,独立一节)逐字:

> **实体盘联机一旦立项,D8 必须重审,大概率要转「盒 API 持上行 WS」那条路。** 传感盘接在盒子上,
> 而 D8 的房间屏在云端 origin,**读不到它**;而 kiosk-shell 规范明确要「用实体盘下在线对战」。
> 本轮不触发(只做自由对局,国象传感板尚未落地)。

Fan 2026-08-27 原话取消了那个免触发条件:「国际象棋、中国象棋……**后续也是会设计完成实体棋盘的**,
**远程对战大厅进行人人对弈是我们的核心卖点**」。

**决策归属(核过,不是推的):** `docs/superpowers/specs/2026-08-18-multichess-lobby-design.md:22`
的 `## 1. 已定决策(2026-08-17/18,Fan 拍板)` 下面,D6 = 「本 session 兼国象 track」,
`:5` = 「总协调:本 session」⇒ **大厅总协调是国象那个 session,Fan 八月拍过。**
而 **D8 标的是「P3 已裁」,和 D7/D9 一样是那条 track 在评审轮次里自裁的,不在 Fan 拍的 D1–D6 里**
⇒ **D8 的复审是它的活,不是 Fan 的。** 我一度准备把「无人认领」报给 Fan,那是把已定的事又摆回去,撤回。

## ② 「取样把会坏的那个东西排除掉了」—— 本轮最值钱的一条

`superpowers/shared/lobby-consensus.md` v2(2026-07-17)§3「盒=瘦客户端」+ §5「中央服务端权威」
是**四家基线**(围棋在适用范围内)。**该文件全文 6239 字节,`实体盘|传感盘|摄像头|LED|相机|physical`
零命中**(双方各自 grep 过)。而 §3 写明它的依据是:

> 「**围棋已这样部署**(`KATRAIN_MODE=server`;**盒上 `board` 模式大厅是 placeholder 不启用,
> 别拿它判断跨盒能力**)」

⇒ **当时拿来当范本的那份部署恰好没有实体盘;唯一有实体盘的那种部署被这句话明确排除在证据之外。**
三棋当时也都没有实体盘。**不是谁疏忽,是取样把冲突排除掉了。**

**而那句话今天连事实都不成立**(我核,国象复核):

| | 依据 |
|---|---|
| `/ws/lobby` 无条件注册 | `server.py:2353`(`@432aad7c` 上是 `:2345`)。全文件 `KATRAIN_MODE` 仅 5 处,无一在附近 |
| kiosk 大厅是真的 | `LobbyPage.tsx` 连 `/ws/lobby`、发 `start_matchmaking`、收 `match_found`。**`@432aad7c` 的 349 行版本就已经如此**,不依赖本分支的 103 个本地提交 |
| 编排器不挑 session 类型 | `server.py:562` `if app.state.vision is not None:` → `:569` 传**整个** `session_manager` |

🔴 **那个词的出处已经找到,并已就地修正**:`server.py:444` 原注释写着
「Lobby/matchmaker placeholders (not used in board mode…)」,**而它下面构造的是和 server 模式
(`:239`)逐字相同的真 `LobbyManager()`/`Matchmaker()`**(同一个类,`session.py:285/334`)。
board 模式真正独有的只有下一行 `game_repo = None`。**一行不实的注释被四家基线当成证据引用过。**

⇒ **推论:LED 那个缺陷今天在盒上就能触发** —— 有相机 + 大厅撮合成功 ⇒ 编排器照常驱动 ⇒ 引导集合空。
不需要跨盒,不需要云端。

## ③ 三条路线的裁决:我原来的 A 案早被否过,E′ 也绕不开它被否的那条

D8 当初评过四种形状。**D(盒 API 持上行 WS)就是本文的路线 A**,被否,四条理由里两条成立:

- ③ 盒 API 持 socket ⇒ **盒 API 重启(部署/OOM)= 云端认为两人同时离席**
- ④ 五方互斥下,大厅屏由 game 服务托管要占掉一个互斥槽,`launcher.html` 首页直连大厅那个零冷启动
  入口在 D 之下不可能存在

否 A(跨源直连)的理由也成立:`COOKIE_SAMESITE` 是**全局旋钮**,同一枚 cookie 供大厅 + 四棋类升降级 +
账号操作 ⇒ 为一块屏改 `none` = 给整台主机的账号/结算面重新引入 CSRF;且**全仓零 CORS 中间件**。

我提的 **E′**(大厅屏留云端,只有房间屏按有没有实体盘二选一)**绕开了 ④,但绕不开 ③**,理由是他们
契约自己写的:**WebSocket 握手不走 CORS,浏览器会把 cookie 原样带给任意第三方页面发起的 ws 连接,
唯一的防线就是 `SameSite=lax`** ⇒ 盒源页面对大厅是第三方页面 ⇒ **浏览器根本不发那枚 cookie**。
Origin 白名单只管服务端肯不肯采信。生产两条旋钮都关着:
`platform-app/deploy/deploy-ranked.sh:141` `LOBBY_COOKIE_SAMESITE=lax` / `:142`
`LOBBY_ALLOW_TOKEN_AUTH=0`,且 `DEPLOY-NOTES.md:156` 的 `assert_production_secrets()` 硬拒后者。

**⇒ 盒源房间屏的实时通道只能由盒上一个持凭据的进程代持。E′ 只能把 ③ 从「全程」收窄到「一局之内」。**

## ④ ③ 的解法是现成的,而且判据在围棋自己的代码里

`katrain/web/session.py:117-142` `ai_ladder_liveness_targets()`(升降级链,已过生产)逐字:

> liveness is reported by **the server that owns the session, not by the browser**: a closed tab
> does not mean the game is gone, and **the device the cloud is judging is the box, not the page**.

云端问的不是「socket 在不在」,是「这台盒子最近有没有安静下来」,配 takeover 规则。**最容易错的绑定点
也写死了:心跳绑 `game_ended`,故意不绑结算态** —— 绑错的后果原文写着(被拒结算的盒子会一直上报一局
没人在下的棋,reservation 永远 `active`,**账号在名下每台设备上被锁死在升降级之外**)。

这正是 Fan 2026-08-11 对四棋类 ranked 拍的 (d)「心跳绑本机这局还在下」。**不是新设计,是把已拍的口径
补到第四个地方。** 国象已采纳,并已指出它搬进大厅的对应物是 `not sess.game.is_over`,**不是**「存谱落地」
(`reaper.py` 的 `finalize_pending` 重试挂起时 session 还活着,绑存谱等于逐字重演围棋踩过的坑)。

## ⑤ 一条更便宜的:房间屏走轮询,③ 从结构上消失

盒上根本不建长连接 ⇒ 没有「盒进程重启 = 双方离席」。代价只有着法到达延迟。

**我一度说「围棋读秒吃不下轮询」,撤回,而且方向反了:** `clock_update` 在围棋**只从跨平台适配器来**
(`platforms/ogs/adapter.py:447`、`kgs/adapter.py:259` → `manager.py:336`),**围棋自己的大厅局今天
没有棋钟**,四家计划本轮也不做棋钟。围棋的 `timer/main_time` 只在升降级和 newgame 路径上用 ——
而升降级恰恰跑在④那条盒进程持心跳的链上,带钟,已过生产。⇒ **四家没有一家因为钟而否掉轮询**,
轮询从备选升为默认候选。

## ⑥ LED 缺陷:修法要重写,而且它拆成两件

缺陷本身复核无误:`physical_play_orchestrator.py:414-434` 的引导集合 =
`{player_type == "player:ai"} ∪ {platform_engine_color}`,而 `session.py:103,105` 把多人局两边都写
`player_type="human"` ⇒ 集合空。

🔴 **我原来提的「加第三种情况」是错的。** 三次同形(AI / 星阵远端引擎 / 跨盒远端真人)说明**谓词本身
是代理**,不是少一格。docstring 括号里已经把正确谓词写出来了:*vision observing them IS the move
source* ⇒ 判据是「**这一色的子由不由本机视觉产生**」。国象补的证据更强一档:
`platforms/manager.py:180-181` 的注释自己写着该字段的意图是
「which side is **not physically playable by the human**」—— **意图从第一天起就是正确谓词,
名字和取值却是关于引擎的。** 它不是先例,是一个在那个场景里碰巧等价的代理。

🔴 **但国象据此裁「现在修,不等 Fan」,理由是「不需要新设计」,这条被我驳回并由他撤回:** 正确谓词需要
一位**今天不存在**的状态。我核过 `interface.py:520-600` 的 `get_state()`:
`local|present|seat|at_board|this_box|device` **零命中**(正对照:`platform_engine_color` 命中 `:569`);
`my_color` 只活在 `platforms/`。而**谁来写这一位取决于架构**。

**⇒ 拆两件(国象把理由说得比我准,原话收下):**

> 「哪一色在本机」= 云端持的 `(game, color→user)` ⋈ 盒端持的 `(本机登录的是谁)`。
> **盒上多人局是唯一一种盒子两半都齐的情形**;跨盒时盒子缺前一半,**而那一半怎么拿到,就是 D8**。

1. **现在能做(与 D8 无关)**:盒上多人局 —— 本机登录的用户坐在盘前 ⇒ 引导另一色。**要盒上实机验收
   (LED 真亮才算数)。** 落地时带一条守卫:**断言「两边都是 human 的多人局」引导集合非空**,
   否则下次改动会把它静默变回空集,**而空集和「本来就不需要引导」在测试里长得一样**。
2. **必须等 D8**:跨盒时这一位由谁下发、房间屏在哪个源上拿到它。

## ⑦ 数子:围棋独有,而且 D9 那条闸转不过来

D9 给三棋的可微分闸(adapter 的终局判定必须与盒端 `xiangqi.js` 对同一串局面同结论)守的是
「两个不同实现不许分家」。围棋两端是**同一个实现**(KataGo)⇒ 同形的闸只能守「同一二进制在两台机器上
同分」,**那是在守权重/版本一致性,不是规则一致性,挡的事故整个换了一类。**

**而且比那还弱一档(我提,国象采纳):KataGo 的分是搜索出来的,同权重同版本跨机器也不保证逐位相同**
(访问数、线程调度、批处理都进结果)⇒ 「两台盒同权重同版本」是必要条件,**推不出同分**。

⇒ **围棋能建的闸只有「协议走完没走完」**(`count_request`/`count_rejected`/`count_timeout` 三件套),
不能建在「两个数相等」上。**建在相等上的闸会间歇红,然后长出白名单。**

## ⑧ 跨 session 对证本身的两条

- **两棵树。** 我的 `feature/kiosk-go-shell-align` HEAD `fd84f286` 领先 `origin/develop`(`14f58d43`)
  **103 个提交,全部本地未推**。国象 pin 在 `vendor/katrain` gitlink `432aad7c`(是 develop 的父)。
  ⇒ 我引的五条事实里**四条两棵树一致**(行号差 8),唯一分家的 `LobbyPage.tsx`(349 vs 553)**不承重**。
  **判据:「有一条对不上」不等于「整封作废」,要逐条问「这一条依赖那个差异吗」。**
  推分支不在本 session 授权内(常驻约束:只在被要求时提交、绝不 push),已报 Fan;国象同样不 bump
  gitlink(四条 track 共用)。**双方约定:凡引 katrain 事实一律标 SHA。**
- **国象 pin 的那个提交,下一个就是推翻它的更正**(`14f58d43 docs(spec): 更正 —— KataGo 侧早就实现了,
  缺的是部署`)。判据原文:「**我查的这个位置,是这类事实该待的地方吗**」—— 实现在不在只有源码说了算,
  一个旧镜像的响应只能证明**那个镜像**没有。已告知,其复审未引用受影响的那句。

## 需要 Fan 拍的(只剩两条 + 三件排期)

1. **要不要花 `SameSite=none` 那笔预算** —— 唯一「技术可行但代价是整台主机账号/结算面重新引入 CSRF」
   的取舍。双方都不替他判。
2. **`lobby-consensus.md §3` 改不改** —— 四家基线,且被设计稿 `:6` 标为「本文取代其冲突部分」。
   四家基线的修订不该由三棋的总协调单方面做。**新增理由:它引以为据的那句已经不是事实。**
3. **盒上时间(三件一次排完)**:LED 引导修完的实机验收 · 盒端重启到第一个心跳的**分布**
   (冷启/热重启各三次,报中位与最大;**并报云端那一侧同期看到的状态**——只量盒子这头,宽限窗够不够
   仍是推的)· PNA 那条盒上的一半。
4. **批不批 push 本分支**(国象核不动我引的行号;不批就继续标 SHA,不阻塞)。

**PNA 实测的取数顺序已钉死(先写死再取数):**
① **留痕对照** —— 盒上同源页面 fetch 那个端点,access log **必须**出现一条;**没出现就停**,
后面全部作废。② 盒上 kiosk chromium 打开公网大厅页,从那一页 fetch 同一端点,**同一次往返**,
判据是 access log 那条的 `Referer` 是 `https://lobby.…`。③ 三种结果各自的读法(通了 / 有 `OPTIONS`
无正式请求 = PNA 拒 / 什么都没有 = 浏览器没发)。④ 附 chromium `--version`。

⚠️ **这条实测的价值不对称,报的时候必须带上这句**:**失败 ⇒ D8 必须改,分支当场关闭;
成功 ⇒ 什么都没证明**(权威还在云端、云端→盒上 LED 的反向通道照样不存在)。**它是必要不充分。**
