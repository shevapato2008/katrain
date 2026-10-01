# 星阵与 OGS 专属入口 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从对弈首页进入星阵或 OGS 后，登录和返回都落到该平台的专属页；删除重复的跨平台平台选择页，并让专属页上的操作与真实平台能力一致。

**Architecture:** 保留现有登录、星阵人机设置和平台 API。新增星阵专页；将现有 OGS 大厅整理为 OGS 专页，使用真实的公开挑战接口。对弈首页仍是唯一平台选择入口，旧 `/kiosk/play/cross-platform` 地址只做返回对弈首页的兼容重定向。星阵人人对弈缺少已核实协议，必须先完成独立协议核验；核验之前页面明确显示未接通，不呈现可点击的匹配、房间或虚构棋友。

**Tech Stack:** React、React Router、TypeScript、Vitest、FastAPI、Python pytest；目标屏 1024 × 600。

**Approved design:** `docs/previews/platform-dedicated-homes-1024x600.html`（2026-09-30 用户确认）；先前设计与协议调查见 `docs/superpowers/plans/2026-09-23-kiosk-cross-platform-v2.md` 的切片 B、D。HTML 的棋友、公开挑战是排版样例，生产界面只使用真实响应。

**Current gate (2026-09-30):** 用户已确认修正后的 1024 × 600 星阵及 OGS 运行时布局；参考图、运行时图、并排和叠加对照见 `docs/previews/platform-homes-runtime-compare.html`。专页、导航、OGS 公开挑战、接受/继续对局、权威快照与终局保存已实现；直邀等待保活及按账号隔离的待约战恢复已接通。聚焦后端 179 项、前端 218 项和严格 RK3562 2D 构建通过，两个独立代码复审均已通过。OGS 双账号真局尚未验证，用户暂时没有测试账号；“确认无死子”仅能发送空死子集合，不能代替 OGS 死子标记同步。Task 8 星阵人人对弈协议核查为 NO-GO，详见星阵协议文档；缺少获授权的 PvP 实测帧。RK3562 直连网卡当前未枚举，设备部署待链路恢复。

**Scope boundary:** 本计划交付平台专页、导航收口和 OGS 已有接口可支撑的公开挑战。星阵实时人人对弈必须以 `katrain/web/platforms/golaxy/PROTOCOL.md` 中核实的请求及事件帧为前提，不能据旧计划的推断协议实现。协议核验是本计划的最后一项任务；获得事实后另写独立垂直切片计划接通快速匹配、房间、邀请和远端棋局。核验没有通过时，不以模拟业务数据或静态可点击按钮冒充完成。

---

## Chunk 1: 专属页与真实数据

### Task 1: 星阵专页

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/GolaxyHomePage.tsx`
- Create: `katrain/web/ui/src/kiosk/pages/GolaxyHomePage.test.tsx`
- Create: `katrain/web/ui/src/kiosk-shell/golaxy-home.css`

**Interface:** `API.platformStatus(token)` 取 `connected` 和 `saved_username`；`playInputState(isVisionEnabled, 19)` 与 `writePlayOnBoard` 处理落子方式；人机卡导航到 `/kiosk/play/cross-platform/engine/golaxy`。没有已核实的星阵 PvP 数据端点，不请求用户或房间列表。

- [ ] **Step 1: 写失败测试。** 覆盖加载中、连接失效、真实账号名、有摄像头/无摄像头的屏幕与实体盘选择；确认人机按钮进入星阵设置，快速匹配及房间不可点且说明“人人对弈还没接通”，棋友样例不出现。用 `API.platformStatus`、`useVision` 和导航 mock，不伪造星阵 PvP 成功响应。
- [ ] **Step 2: 运行 `cd katrain/web/ui && npx vitest run src/kiosk/pages/GolaxyHomePage.test.tsx`，确认新增测试因缺组件失败。**
- [ ] **Step 3: 最小实现。** 复用 `KioskPagebar`、`KioskSecLabel`、`KioskCard` 和现有 `go-screens.css` 设计 token。按审核稿实现页控条、落子方式、三张模式卡；连接失败给返回登录入口，获取状态失败给重试；页面不显示未经返回的星阵号、棋友、房间。点击实体盘只在 `playInputState` 允许时调用 `writePlayOnBoard(true)`，屏幕则写 `false`。
- [ ] **Step 4: 跑上述测试和 `cd katrain/web/ui && npx tsc -b`，预期通过。**

### Task 2: OGS 专页的临时 Fixture 与视觉关卡

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/PlatformLobbyPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/PlatformLobbyPage.test.tsx`
- Create: `katrain/web/ui/src/kiosk-shell/ogs-home.css`
- Create: `katrain/web/ui/src/kiosk/pages/platformHome.fixture.ts`（只在测试构建中导入，Task 5 删除）

**Interface:** 本步只做目标运行时预览，不调用新后端。OGS 页按审核稿画出落子方式、三张卡、公开挑战；Fixture 在测试构建中由显式开关注入，生产运行时不得引用。有效筛选仅为“全部实时局 / 19 路”；“同级别”没有当前 OGS 用户段位字段，暂不画可操作按钮。搜索只按用户名，不承诺搜索不存在的对局名称。不可用的匹配/发起挑战卡明确写“盒上尚未接通”，不发请求。

- [ ] **Step 1: 写页面失败测试。** 断言页控条、落子方式、三卡、真实字段形状的公开挑战行、不可用卡说明；无账号段位和对局名称时不显示伪筛选。运行 `cd katrain/web/ui && npx vitest run src/kiosk/pages/PlatformLobbyPage.test.tsx`，预期新增断言失败。
- [ ] **Step 2: 只实现 Fixture 驱动的布局和交互外壳。** Fixture 用 `PlatformChallenge` 对应的测试对象，不进入生产 API 分支；此时接受按钮只在 Fixture 预览中说明目标交互，不向 OGS 发请求。
- [ ] **Step 3: 在 1024 × 600 目标 viewport 比较批准 HTML、实现截图、并排图、叠加图；记录构图、间距、层级、字体、图标、文案和状态差异并修正。** 将真实运行时预览给用户确认；该确认是仓库用户旅程流程要求的前端关卡。用户确认前不进行 Tasks 3–4 的后端写入。

### Task 3: OGS 公开挑战数据契约

**Files:**
- Modify: `katrain/web/platforms/ogs/adapter.py`
- Modify: `katrain/web/platforms/gateway.py`
- Modify: `katrain/web/api/v1/endpoints/platforms.py`
- Modify: `katrain/web/server.py`
- Modify: `katrain/web/platforms/ogs/PROTOCOL.md`
- Create: `tests/web_ui/test_ogs_open_challenges.py`
- Modify: `katrain/web/ui/src/api.ts`

**Interface:** `GET /api/v1/platforms/ogs/challenges` 成功仍是 `{challenges: PlatformChallenge[]}`。真正没有可下的实时局返回 `[]`；OGS REST 失败而缓存为空时抛出可诊断异常，由端点返回 502，前端呈现“没能取回列表”和重试。仅接纳 9/13/19 路、方形、实时、非联棋的挑战；未知速度或联棋字段不猜测为可接受。筛选前保留原始 seek/REST 字段；已证实的字段与示例响应写进协议文档。

- [ ] **Step 1: 从 OGS 的实际 seek graph 和 REST 返回各取一份匿名化样本，确认 `speed`、`rengo`、`width`、`height` 在两路数据中的真实路径，记录到 `PROTOCOL.md`。** 只保存必要字段，不保存用户凭据。如果任一路无法取得可验证字段，该路不启用“只列实时”承诺，页面保持错误/未就绪状态而不假装空列表。
- [ ] **Step 2: 写 `tests/web_ui/test_ogs_open_challenges.py` 失败测试。** 两路样本分别覆盖实时 19 路、实时 9/13 路、通信局、联棋、矩形盘、未知速度、真实空列表和 REST 抛错；端点测试断言上游失败是 502 而非 `200 []`。运行 `pytest -q tests/web_ui/test_ogs_open_challenges.py`，预期过滤/错误断言失败。
- [ ] **Step 3: 在原始对象解析前统一判断支持性，再产生 `PlatformChallenge`；让 REST 失败向端点传播并转为 502。** 前端在 `api.ts` 写明确切 `PlatformChallenge`/`{challenges: ...}` 类型，不使用 `any` 猜数据。重跑上述 pytest，预期通过。

### Task 4: OGS 在线对局桥接

**Files:**
- Modify: `katrain/web/session.py`
- Modify: `katrain/web/platforms/manager.py`
- Modify: `katrain/web/platforms/ogs/adapter.py`
- Modify: `katrain/web/platforms/ogs/realtime_client.py` and `katrain/web/platforms/models.py`（早到事件、回调及每局时钟需要时）
- Modify: `katrain/web/api/v1/endpoints/platforms.py`
- Modify: `katrain/web/platforms/gateway.py` and `katrain/web/server.py`（远端回显、计分、认输、超时的权威边界）
- Modify: `katrain/web/interface.py`（仅当现有终局命令不能保存 OGS 明确返回的结果，以及需要阻止远端对局调用本地分析时）
- Modify: `katrain/web/ui/src/hooks/useGameSession.ts`
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`
- Create: `tests/web_ui/test_ogs_platform_game_bridge.py`
- Modify: `katrain/web/ui/src/hooks/useGameSession.connection.test.tsx`

**Interface:** 接受挑战的 `/challenge/accept` 返回 `{session_id, game}`，对应真实 `pvp_online` 会话；对方接受我方挑战或自动匹配完成时，OGS `active_game`/`automatch/start` 事件创建同一类会话，且重复事件不重复创建。新增 `GET /api/v1/platforms/ogs/active-game` 只向当前平台账号所有者返回 `{session_id|null, pending_challenge_id|null}`；专页用它展示“继续对局”或待接受约战而不因旧局自动跳转。进入已开始的局时必须先恢复 OGS 权威快照，再消费增量帧。认输、计分、超时及最终结果以 OGS 为权威；本机不按棋面估分，也不在远端回执前宣布胜方。

- [ ] **Step 1: 写桥接失败测试。** `PlatformManager.start_platform_game()` 对 9/13/19 路、规则、让子、贴目及 B/W 座次创建正确且归当前用户所有的 `pvp_online` 会话；接受挑战能路由到它；重复 `active_game` 和 `automatch/start` 只有一个 session，启动时不漏首个 `active_game`，重连后不重复注册回调；OGS 快照已有让子及多手棋时先恢复初始摆子、落子历史、轮次、阶段，再接增量帧且不重复落子；本机落子与停一手须等远端回显或权威快照确认，超时和拒绝后不先改本地盘面；对手停一手及多局时钟只作用于对应局；远端明确的终局结果更新本地状态并广播 `game_end`，后续落子被拒；他人请求 `active-game` 不泄露 session。运行 `pytest -q tests/web_ui/test_ogs_platform_game_bridge.py`，预期失败。
- [ ] **Step 2: 给 `SessionManager.create_multiplayer_session` 加可选 `initial_game_type`，默认值保持旧调用行为；平台桥接传 `pvp_online` 并用 `edit_game(size, rules, handicap, komi)` 设置真实条件，拒绝不支持的盘形。** 使用平台账号的 `user_id` 归属。`accept_challenge`、`_on_active_game`、`_on_automatch_start` 经同一个幂等创建入口；`active-game` 端点执行现有 `require_platform_owner` 鉴权。
- [ ] **Step 3: 接入快照与增量。** 用 `fetch_game_snapshot` / OGS `gamedata` 的 `initial_state`、`moves`、`phase` 恢复棋盘和当前轮次，再注册后续 move/clock/phase。官方 goban 协议的 `initial_state.black/white` 是编码坐标串，须先摆开局子；`moves` 是 `[[x,y,delta?,color?,extra?], ...]` 或 JGOF 对象数组，不是扁平三元组。`game/{id}/move` 的 `move_number` 按官方客户端校验是落成后的 1 基手数；以 game_id 和远端手数去重，同一 game_id 的重复 `active_game` 不重播历史。处理连接早到的 `active_game`，重连后从远端快照对账，避免重复回调；时钟事件带 game_id，不能默认派给第一局。官方源码只确认格式，尚无本账号实局样本；字段无法验证时返回显式错误，不能开启一张空盘。运行 Step 1 的快照测试，预期通过。
- [ ] **Step 4: 接入对局命令与平台终局。** `gateway.py` 的 OGS 落子、停一手只发送远端命令，等待相同 game_id、坐标和远端 move number 的回显或权威快照确认后再落入本地；超时、拒绝或重连时先对账，不盲目重发。认输先送远端，等待远端 phase/gamedata 的权威结果后再记本机终局；计分按 OGS stone removal phase 发送 `accept`/`reject`，不让本机数子端点等虚拟玩家 `-1` 或直接本地算胜方；远端未确认为 finished 时，本机超时逻辑不得抢先裁定。OGS 返回的 winner player-id 根据该局 black/white id 转成 B/W，outcome 转成真实 SGF 结果，无法确定则 `Void`；`PlatformManager._on_game_ended` 在清理上下文前提交终局、保存状态、广播现有 `game_end`。`useGameSession`/`GamePage` 以同一 socket 消费时钟、阶段及终局，不开第二条相争的 socket。聚焦测试包括：回显延迟/拒绝/重连、对手轮次认输、双边计分确认完成、计分拒绝继续对局、远端终局前本机超时不判负。
- [ ] **Step 5: 运行上述 pytest 和 `cd katrain/web/ui && npx vitest run src/hooks/useGameSession.connection.test.tsx`，预期通过。**

### Task 5: OGS 页面接入真实后端，删除 Fixture

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/PlatformLobbyPage.tsx` and `.test.tsx`
- Modify: `katrain/web/ui/src/kiosk-shell/ogs-home.css`
- Remove: `katrain/web/ui/src/kiosk/pages/platformHome.fixture.ts`

- [ ] **Step 1: 写前端失败测试。** 覆盖真实 `{challenges}`、成功空态、502 失败与重试、实体盘禁用非 19 路接受、屏幕可接受 9/13 路、确认后调用 `platformAcceptChallenge` 并按返回的 `session_id` 进入 `/kiosk/play/cross-platform/game/{session_id}`；断言活动会话写入 `onBoard`。搜索仅按用户名；没有账号段位字段时不出现“同级别”可点筛选。
- [ ] **Step 2: 接上真实请求与会话。** `找人下` 保留已有用户名搜索，但发出挑战前确认；对方接受后由 Task 4 的 `active-game` 回盒。快速匹配卡只有在 Task 4 的事件链已测通时才启用；“发起公开挑战”缺取消/收回链时明确不可用，不画可配置条件。所有列表行来自 API，删除 Fixture 文件及引用。
- [ ] **Step 3: 跑 `cd katrain/web/ui && npx vitest run src/kiosk/pages/PlatformLobbyPage.test.tsx src/hooks/useGameSession.connection.test.tsx && npx tsc -b`，预期通过。**

---

## Chunk 2: 导航收口与设备验收

### Task 6: 所有入口和返回路径一致

**Files:**
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/PlayPage.tsx` and `.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/PlatformLoginPage.tsx` and `.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/PlatformEngineSetupPage.tsx` and `.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/PlatformLobbyPage.tsx` and `.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx` and related focused tests
- Create: `katrain/web/ui/src/kiosk/components/settings/PlatformAccounts.tsx` and `.test.tsx`
- Remove: `katrain/web/ui/src/kiosk/pages/PlatformConnectPage.tsx` and `.test.tsx`
- Modify: affected `katrain/web/ui/tests/kiosk-*.spec.ts` only where they still assert or navigate to the removed selection page

**Route contract:**

| Start | Destination |
|---|---|
| 对弈首页星阵，未连接 | `/kiosk/play/cross-platform/login/golaxy` |
| 对弈首页星阵，已连接；星阵登录成功 | `/kiosk/play/cross-platform/golaxy` |
| 对弈首页 OGS，未连接 | `/kiosk/play/cross-platform/login/ogs` |
| 对弈首页 OGS，已连接；OGS 登录成功 | `/kiosk/play/cross-platform/ogs` |
| 星阵人机设置返回 | `/kiosk/play/cross-platform/golaxy` |
| 任一专页 / 登录页返回对弈 | `/kiosk/play` |
| 旧 `/kiosk/play/cross-platform` | 重定向 `/kiosk/play` |
| 旧 `/kiosk/play/cross-platform/lobby?platform=ogs` | 重定向 OGS 专页 |
| OGS 接受/继续对局 | `/kiosk/play/cross-platform/game/{session_id}`，用普通在线对局状态，不设 `engineMode` |

- [ ] **Step 1: 更新聚焦路由测试并确认旧行为下失败。** 分别覆盖未连接、已连接、扫码/密码/验证码登录成功、设置页退出、登录页返回、旧书签、直接刷新专页；断言不会出现跨平台选择页或回到人机设置页。
- [ ] **Step 2: 加 `golaxy`、`ogs` 与普通平台对局的路由。** 用 `<Navigate replace>` 接住旧书签；移除 `PlatformConnectPage` 路由、组件和其独立测试。把它的断开确认、失败反馈移入设置页 `PlatformAccounts`，用 `/status` 的真实账号列表和已有 `/logout` 接口，测试取消不请求、确认仅断开目标账号、失败后不显示“已断开”。设置页去连接只去 `/kiosk/play`。
- [ ] **Step 3: 更新首页、登录、星阵人机设置、OGS 专页的导航目标。** 不用浏览器 history 作为主要返回逻辑，刷新后仍按上表回去。页面保留 `backToState` 对真实对局的约定。
- [ ] **Step 4: 跑受影响 Vitest 与 `cd katrain/web/ui && npx tsc -b`，预期通过。** 用 `rg -n '/kiosk/play/cross-platform' katrain/web/ui/src/kiosk` 逐条检查旧选择页链接，只允许兼容重定向和子路由。

### Task 7: 1024 × 600 集成复核及验收

**Files:**
- Modify: `katrain/web/ui/tests/kiosk-screen-07-09-platform.fourup.spec.ts`、`katrain/web/ui/tests/kiosk-shell-scroll.spec.ts` 中被新专页取代的场景
- Modify: `katrain/web/ui/tests/helpers/reference-shots.json` 仅当对应快照登记必须改动
- Modify: affected `katrain/i18n/locales/*` for new user-facing keys

- [ ] **Step 1: 在 1024 × 600 viewport 对正式 Golaxy、OGS 页各取一张图，同已确认的 Task 2 运行时预览比较集成后有无偏差。** 只使用隔离的测试响应，生产代码不含样例账号或挑战。
- [ ] **Step 2: 检查各专页的加载、空态、失败、长列表滚动及软键盘；检查可点击目标至少 44 px。** 仅修复本次可见的偏差和阻塞交互。
- [ ] **Step 3: 运行聚焦前后端测试、前端构建和受影响 Playwright 用例。** 记录实际命令、通过数和跳过原因；不以整仓回归代替这些行为验收。
- [ ] **Step 4: 如能访问 RK3562，在设备上走一次首页→平台登录→专页→人机设置/OGS 挑战→返回路径；如暂不能访问，明确报告设备验收未完成。**

### Task 8: 星阵人人对弈协议事实闸

**Files:**
- Modify: `katrain/web/platforms/golaxy/PROTOCOL.md`

- [ ] **Step 1: 在获授权的星阵测试账号和真实网页会话中，分别观察快速匹配、建房/入房、邀请与落子/终局的请求、响应、STOMP 订阅及消息体。** 不记录令牌、手机号或完整认证报文；不使用未经授权的其他账号。
- [ ] **Step 2: 写协议事实表。** 每个行为列触发时机、请求字段、响应字段、事件帧、取消/超时以及错误态，并标注实际观测或仍未知。对照旧计划中的三个推断：快速匹配是否升降战、邀请局赛制、STOMP 帧结构。
- [ ] **Step 3: 仅在关键契约均核实且能测试时，写星阵 PvP 的下一份独立垂直切片计划。** 无法核实时报告阻塞事实，维持专页上的不可用状态，不用猜测协议上线。

---

**Completion criteria:** 星阵和 OGS 都有专页；登录成功、返回及旧书签路径正确；跨平台选择页不再渲染；OGS 公开挑战来自真实响应且可支持的接受行为进入盒上对局；星阵 PvP 状态与已核实能力一致。星阵人人对弈功能完成与否单独按 Task 8 的协议闸和后续切片报告，不能将本计划的导航完成表述为星阵 PvP 完成。
