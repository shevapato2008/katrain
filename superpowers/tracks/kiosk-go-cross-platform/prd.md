# 围棋 kiosk · 跨平台对弈 —— 本轮需求（PRD）

- 日期：2026-09-14
- 分支 / worktree：`feature/kiosk-go-cross-platform` @ `/Users/fan/Repositories/katrain-kiosk-go-cross-platform`（基于 develop `6f7dc629`）
- 输入：2026-09-14 三轮调研条目包（`tracks-input/kiosk-go-cross-platform.json`，13 条），本文逐条回源码核过（见 §3 每条的「核实」行）
- 实施计划：同目录 `plan.md`

---

## 1. 背景与目标

跨平台对弈在盒上今天是「连得上、下不完整」：屏 07 能连星阵 / OGS（a979132a 刚把连接页、大厅、人机开局三屏从 token 闸里救出来），星阵人机也能开局落子，但**对局屏里还剩两道 token 闸**，盒上三颗付费道具按了没反应；**对弈首页的跨平台卡永远写「点击登录」**；星阵人机局**只能靠认输结束**——「停一手」弹英文 409 红条、「数子」毫无反应，AI 一旦停手 / 认输，屏上说「AI 连接出错」且这盘卡死；**盒上每一盘星阵局都不进棋谱库**，而屏 07 对所有平台承诺「下完自动存谱」。OGS 真人对局发出挑战后永远回不到盒子。

这一轮要让盒上用户得到：**星阵人机这一条路从首页到存谱是真的走得通、屏上每一句话都成立**——首页如实显示已连接、道具能用、没有点了会被拒的键、AI 结束对局时屏上说实话并正常终局、下完的每一盘进棋谱库；OGS 那条路本轮不接通，但**挑战那一句不再暗示会回到盒子**。多用户共用盒子时平台账号归谁、OGS 回盒排不排期，列为待 Fan 拍板。

## 2. 已经做完、不要动的

| 事实 | 出处 |
|---|---|
| 屏 07 / 08 / 09 与大厅的 14 处 token 闸已换 `isAuthenticated`；`api.ts` 的 `platform*` 一族签名已接受 `null`，写死的 `Authorization: Bearer` 已改 `authHeaders()` | `a979132a` |
| 屏 10 已上共享外壳：三颗道具键三态角标（数字 / `0` 红底不灰 / `—`）、无胜率块、棋谱折叠块（`history[].move/player`） | scope.md §27，`GameControlPanel.tsx:228-373` |
| 跨平台对弈**整局没有悔棋键**（Fan 2026-08-25 亲裁）；`usePlatformEvents` 调用点随之删掉 | `GameControlPanel.tsx:202-219` |
| 平台状态条不做（D-1）、`PlatformBadge.tsx` 已删（D-2）、39 档名单不做、挑战条件写死为只读读数 | scope.md §19 ①、§27 D-1/D-2；`PlatformLobbyPage.tsx:27-29` |
| 屏 08 自动匹配文案已撤回「配上就自动进对局」，改成「配上之后不会自动回到这台盒子」 | S1 `a8eb0a6e`，`PlatformLobbyPage.tsx:246-260` |
| 星阵 genmove 提交协议（先校验、position token、[人,AI] 原子落子、`reason` 分类）、实体盘引擎出错恢复框（重试 / 拿回棋子 / 认输）、支招白灯、`platform_engine_color` 亮灯 | kiosk-play-golaxy / kiosk-golaxy-physical-play 两条 track（2026-07-02～07-12） |
| 服务端档 `record_multiplayer_game` 跳过 id≤0 的合成对手 | `game_repo.py:35-43`，`tests/platforms/test_engine_game_record.py` |

## 3. 需求条目（本轮做）

> 盒上 = 严格盒端构建（`VITE_BOX_SSO_STRICT=true`），**JS 拿到的 `token` 恒为 `null`，身份在 HttpOnly cookie**。单测里「盒上」一律用 `token: null, isAuthenticated: true` 造。

### X7（P1）对局屏付费道具在盒上按了没反应

- **现象**：盒上星阵人机局，领地 / 支招 / 变化图按下去不发请求、没有进行中态；角标恒为「—」；实体盘支招白灯不亮。
- **核实**：成立，行号对。`GamePage.tsx:142` 只取 `{ token, user }`；`:335` `if (!engineMode || !token) return;`（`refreshItemCounts`）；`:501` `if (!sessionId || !token) return;`（`handleEngineAnalysis`）。`a979132a` 的改动文件里没有 `GamePage.tsx`。后端两个端点认 cookie，`api.ts` 两个封装已接受 `null`。
- **期望**：判别位换 `isAuthenticated`，`token` 只作凭据原样传下去（与 a979132a 同一判据）。
- **验收**：
  1. 单测：`token: null, isAuthenticated: true` 渲染 `engineMode` 对局页 → `API.platformEngineItems('golaxy', null)` 被调用；按「支招」→ `API.platformEngineAnalysis('golaxy', <sessionId>, 'options', null)` 被调用。
  2. 变异：把判别位改回 `!token`，上面两条红；还原绿。
  3. 上板：盒上开一局星阵人机，角标出数字；按支招出候选圈，实体盘模式下白灯亮。
- **依赖**：无。

### X8（P1）对弈首页跨平台卡在盒上永远「点击登录」+ X1（P3）野狐卡文案与屏 07 口径统一

- **现象**：盒上已连上星阵 / OGS，屏 01 仍写「点击登录 · 手机号 + 验证码」、绿点不亮、点卡先落到屏 07。野狐卡写「即将上线」，屏 07 同一个事实写「暂不能对弈」。
- **核实**：X8 成立（`PlayPage.tsx:43` 取 `{ user, token }`，`:51` `if (token)` 才请求 `/platforms/status`）。X1 更正：不只是两屏措辞不同——屏 07 头注释（`PlatformConnectPage.tsx:46-51`）明确判过「不写『即将上线』，没人给过日期，那是预测不是状态」，屏 01 仍是那句预测，**屏 01 违反的是本 track 自己写下的判据**。
- **期望**：状态请求的判别位换 `isAuthenticated`（effect 依赖 `[isAuthenticated, token]`）；野狐卡 `soon` 改用屏 07 那个 key：`t('platform:no_play_yet', '暂不能对弈')`，副标「接口还没通」不动。
- **验收**：
  1. 单测：`token: null, isAuthenticated: true`，`platformStatus` 回星阵已连接 → 星阵卡含「已连接」，点击去 `/kiosk/play/cross-platform/engine/golaxy`；`platformStatus` 以 `null` 被调用。
  2. 登出（`user: null, isAuthenticated: false, token: null`）后旧请求晚到 → 仍是全未连接默认名单（既有用例改夹具，登出的真形状是 `isAuthenticated: false`）。
  3. 野狐卡含「暂不能对弈」、不含「即将上线」、仍 disabled。
  4. 四图：屏 01 重取，只允许野狐卡徽标文字不同；Fan 确认。
  5. 上板：盒上连星阵后回屏 01，星阵卡绿点亮、写「已连接 · 人机对弈」，一步进人机开局。
- **注意**：修好之后乙用户在屏 01 会看到甲连上的「已连接」——这与屏 07 今天的行为一致，归属问题是 X11（待拍板），不在这条里处理。

### X4-a（P1 的可独立部分）屏 08 挑战文案说实话

- **现象**：发出挑战后 toast 写「挑战已发出 —— 接下来在对面那边」，确认框写「发出去就在对方那边了」；而屏 07 标题说「用这块实体盘下」。对方接受后盒子不会建局、不会跳转（X4 主体，待拍板）。
- **核实**：成立。`PlatformLobbyPage.tsx:109` toast、`:295` 确认框尾句；同屏自动匹配那句（`:259`）已是实话，挑战这两句没跟上。
- **期望**：两句都说清「对方接受后要去 {平台} 上下，不会回到这台盒子」，与自动匹配那句同一个事实同一种说法。
- **验收**：单测——确认框含「不会回到这台盒子」；点「发出挑战」成功后 toast 含「不会回到这台盒子」。

### X9-a（P1）星阵人机局撤掉「停一手」「数子」两颗注定被拒的键

- **现象**：按「停一手」→ 红条「Request failed 409: {"detail":"pass_not_supported"}」；下满 100 手按「数子」→ 后端走联机局分支回 `pending`，屏上什么都不发生。
- **核实**：成立。更正一处出处：「人类侧 UI 禁用」**当初落地过**——`3677f3d1`（2026-07-02）加了 `disableSpecialActions`；`8655be97`（2026-07-08 develop 合入 physical-play 的 merge）按 galaxy 参考改回「no blunt engineMode disable」，并用 `GamePageEngine.test.tsx:210` 把「停一手在 engineMode 可按」钉成了断言。后端 `gateway.py:285-286` 恒拒 pass；`server.py:2026-2064` 对 `player_w_id=-1` 的会话走联机数子。
- **期望**：`engineMode` 动作区只留「认输」（终局时照旧灰，与今天一致，不改终局版式）。依据是本组件自己写下的判据「**永久不可用 → 撤掉；暂时不可用 → 灰着**」（`GameControlPanel.tsx:213`，悔棋同一条）——这两颗在星阵局里开局就定死不可用。开关排右端 `.ghint` 在 `engineMode` 且未终局时写「暂不支持停一手、数子」（硬件故障仍优先）。
- **验收**：
  1. 单测：`engineMode` 面板里无「停一手」「数子」，有「认输」，`.ghint` 为「暂不支持停一手、数子」；非 `engineMode` 不受影响（既有用例全绿）。
  2. 真浏览器：`tests/kiosk-screen-05-game.spec.ts` 屏 10 用例的动作区标签改为 `['认输']`，「动作区贴底 / 右栏不滚」两条照旧成立。
  3. 四图：屏 10 重取；Fan 确认一颗「认输」横跨动作区的样子可接受（不接受的备选：两颗留着但灰 + 同一句 `.ghint`）。
- **承重判定**：不触发。动作区仍是一行，行高不变；撤回改动不改变任何元素的高度来源或裁切边界。

### X9-b（P1）AI 停手 / 认输时：如实终局，不再说「连接出错」、不再卡死

- **现象**：星阵 AI 返回非落点坐标（停一手 / 认输，编码从未抓到），后端当异常终局：平台上下文被摘掉，本地局没有结果；前端弹「AI 连接出错，请重试落子」，重试因「不是你的回合」继续失败；实体盘路径上屏幕停在「AI 思考中」。
- **核实**：成立。`golaxy/adapter.py:787-792` emit `game_ended("ai_special_coord")` 后抛 `GolaxyEngineTerminal`；`manager.py:348-354` 摘上下文；`gateway.py:205-223` 落下人那一手后抛 `reason="game_ended"`；`server.py:983-984` 一律 409；前端 `GamePage.tsx:448-456` 在 `engineMode` 下任何失败都弹 `engineErrorToast`。
- **裁定（本轮按此做，Fan 可推翻）**：本地局以 SGF 标准的「无胜负」`Void` 结束。理由：编码没抓到，**分不出是 AI 停手还是认输**；记成「你中盘胜」是替它选了一个结果，「不知道」退到最保守的那句。
- **期望**：
  - 后端：`WebKaTrain` 新增命令 `end_without_result`（当前节点 `end_state = "Void"`）；gateway 的终局分支在落下人那一手之后调用它；`POST /api/move` 对 `reason == "game_ended"` 回 **200 + 已终局的 state**（人那一手确实落下了、这局确实结束了，这次请求不是失败），其余 reason 仍 409。视觉那条路共用 gateway，自动得到同一个终局。
  - 前端：终局卡在「星阵局（`platform_engine_color` 有值）且 `end_result === 'Void'`」时多一行说明「星阵 AI 停手或认输了 · 本终端还分不出是哪一种，这盘不判胜负」。
- **验收**：
  1. 真栈集成测试（真 `SessionManager` + 真 `GolaxyAdapter`，只 mock genmove 返回 361）：`play_move` 抛 `reason="game_ended"`；本地主线 = 人那一手；`game.end_result == "Void"`；`is_platform_game` 为假。
  2. 端点测试：`/api/move` 遇 `game_ended` 回 200 且 `state.end_result == "Void"`；遇 `engine_error` 仍 409。
  3. 单测：终局卡在上述条件下出现说明行，普通终局不出现。
  4. 上板：需要星阵 AI 真的停手 / 认输才能复现（第三方行为，无法按需触发）→ 记为上板观察项，不作本轮合并闸。

### N13（P1）星阵人机局下完进棋谱库（盒上与服务端两种部署都成立）

- **现象**：盒上每一盘星阵人机局都不进棋谱库 / 复盘列表；屏 07「连上之后 · 下完自动存谱 · 进棋谱库，也能送去复盘」不成立。
- **核实**：成立，并补一处更正。认输走 `server.py:1926-1938` 联机分支调 `app.state.game_repo.record_multiplayer_game`，盒上 `game_repo = None`（`server.py:514`），AttributeError 被吞；AI 终局那条路完全不落账。**服务端档也不对**：同一分支不传名字、写 `source="play_human"`——星阵人机局在服务端被记成一局没有名字的「人人对局」。
- **能否不依赖 game_repo**：能。星阵人机局只有**一个** KaTrain 用户，对手是外部引擎，语义与人机局相同；人机局已有一条两种部署都通的落账路 `_record_ai_game`（盒上走 `repository_dispatcher.user_games_create`，远端优先、失败落本地并入同步队列；服务端走 `user_game_repo.create`）。它**不依赖** P2「跨盒人人对弈路线」/ P9「盒上账本」的裁定——那两条管的是两个 KaTrain 用户的局归谁。
- **期望**：新增模块级 `_record_platform_engine_game(app, session, user)`，经 `_record_ai_game`（新增可选参数 `data_overrides`）写一行 `user_games`：`source="play_ai"`，人那一方的名字写**账号名**（会话上是占位的 "Me"，复盘列表认「你」靠的正是存进去的名字，`reviewPresentation.ts:38-44`），对手名照会话，`result` = 本地终局结果。三处调用：
  1. `/api/resign` 星阵人机局（在 `gateway.resign` 摘掉上下文**之前**判定是不是引擎局），不再调 `record_multiplayer_game`；`game_end` 广播照旧。
  2. `/api/move` 遇 `game_ended`（X9-b）。
  3. 视觉路径 `_handle_confirmed_move` 遇 `game_ended`：这条路没有 `current_user`，落账认**会话主人**（`app.state.user_repo.get_user_by_id(session.user_id)`；盒上是 shadow user，查得到）。
  - 复盘列表把 `Void` 念成「这盘没有判出胜负」（`reviewPresentation.outcomeLine`），不原样念英文。
- **验收**：
  1. 端点测试：星阵人机局认输 → `_record_platform_engine_game` 被 await 一次、`record_multiplayer_game` 未调用、`game_end` 仍广播；OGS 类非引擎平台局认输 → 仍走 `record_multiplayer_game`（正对照）。
  2. 单测：helper 传给 `_RECORD_FN` 的 `data_overrides` = `{source: 'play_ai', player_black: <账号名>, player_white: '[golaxy] …'}`（人执白时对调）；局未结束时不写；`_record_ai_game` 真函数把 overrides 合进写库的 data。
  3. 视觉路径单测：`game_ended` 时以会话主人调 helper；查不到主人时不抛。
  4. 单测：`outcomeLine` 对 `Void` 输出「这盘没有判出胜负」；其他认不出的写法仍原样念。
  5. 上板：盒上下一盘星阵人机并认输 → 屏 19 历史对局出现「vs [golaxy] …」一行、结果「你(黑)中盘负」，能送去复盘；断网时认输 → 本地有行、联网后同步上云。
- **不含**：OGS 平台侧自然终局落账（`manager.end_platform_game` 只清内存），依赖 X4。

### X10-a（P2）实体盘「等待拿回棋子」弹层给出口 + 终局时释放恢复暂停并熄灯

- **现象**：星阵实体盘局网络出错→选「拿回棋子」后，等待弹层只有标题、转圈和一句话，没有任何按钮、点背景也关不掉；识别有一处对不上就永远挂住。另：暂停期间（引擎出错 / 等待拿回）认输，编排器不跑终局清灯那一支，灯可能一直亮到离开页面。
- **核实**：成立。`EngineMoveErrorDialog.tsx:139` 无 `onClose`，`:172-182` waiting 分支无 `DialogActions`；`physical_play_orchestrator.py:302-310` awaiting_removal 先分派、其余暂停原因直接 `continue`，都不看 `end_result`。更正：条目包说「M4 需要上板复现」——M4 的成因在代码里是确定的，可用现有 fake 单测；**只有 M3（打劫回提静默循环）需要上板**。
- **期望**：
  - 前端：waiting 分支加一颗「认输」（走页面既有的认输确认流，与 error 分支同一个 `onResign`）。这是 2026-07-11 登记的 M2。
  - 后端：编排器每个 tick 先检查「本局已终局且处在 engine_error / awaiting_removal 暂停中」→ 清掉这两个暂停原因并熄灯，交还普通 tick（普通 tick 见终局会保持熄灯）。这是 M4。
- **验收**：
  1. 单测：取消→进入等待态后出现「认输」，点击调 `onResign`、弹层不自行关闭（与 error 分支同一约定）。
  2. 单测（编排器）：先亮一颗灯 → `enter_engine_error` → 推一帧 `end_result="W+R"` → 释放函数返回真、暂停原因为空、`vision.paused` 为假、最后一次 LED 调用是 `clear`；`awaiting_removal` 同理；未终局时不释放。
  3. 上板：拔网线造出恢复框 → 拿回棋子 → 在等待态认输 → 弹层关、终局卡出、盘上灯灭。

## 4. 待 Fan 拍板

| # | 问题 | 选项 | 推荐与理由 | 不拍板时本轮怎么处理 |
|---|---|---|---|---|
| X11 | 一台盒子多人共用时，星阵 / OGS 平台账号归谁？（今天整台盒子一份连接：甲登星阵，launcher 切到乙，乙看到「已连接」、下人机和用付费道具都记在甲的星阵账号上；乙点登出会断掉甲的连接但只删乙自己的凭证） | A. **连接归连上它的那个 KaTrain 用户**：状态 / 开局 / 道具 / 分析 / 登出都校验归属，别人看到「未连接」；launcher 换身份时断开全部平台连接<br>B. 整台盒子共享一个平台账号，屏 07 明写「这台盒子的星阵账号：xxx（由甲连接）」，登出前提示会影响所有人<br>C. 每个用户一份适配器实例，并存多条连接 | **A**。付费道具扣的是连接者的钱、对局记在连接者的星阵账号上，这是隐私与计费边界，不能靠「大家都知道」；C 在 2G 的 RK3562 上多开长连接不值；B 让乙在不知情时花甲的钱。A 的实现量小（`_platform_user_ids` 已存归属，只是没人读） | 不改。X8 修好后屏 01 与屏 07 口径一致地显示全局连接状态 |
| X4 | OGS 真人对局回到盒子（对方接受 / 自动匹配配上后建本地局、跳对局屏、接收别人发来的挑战）排不排进下一轮？ | A. 下一轮做：先定「用户级（非 session 级）平台事件通道」，再接 `active_game` / `automatch_found` 与收挑战四个 API；需要 Fan 提供一个真 OGS 账号做端到端<br>B. 押后到 X11 定了之后 | **B**。事件要推给「哪个用户」取决于 X11 的归属规则；没有真账号端到端，适配器里没抓过的报文（`_on_active_game` 只 debug 打印）无法验证。X5（对手计时 / 读秒）、N4（会话类型与远端亮灯）、OGS 平台侧终局落账都挂在它下面 | 只做 X4-a（挑战文案说实话） |
| X6 | ① 做不做和星阵上的真人对弈（需抓 STOMP 报文）？② 屏 07 能力标（「实时对弈 · 房间」）说的是「平台有什么」还是「这台盒子能做什么」？③ 屏 07「连上之后」三句（用实体盘下 / 自动存谱 / 盒内段位不受影响）对 OGS 前两句不成立，要不要按平台分说？ | ① A 做 / B 不做<br>② A 维持「平台有什么」/ B 改成「盒子能做什么」（星阵只亮「人机对弈」，OGS 在 X4 通之前不亮「实时对弈」）<br>③ A 维持 / B 在 OGS 那一行尾注明「对局在 OGS 上下」 | ① **B**（星阵人机计划 2026-07-02 已列为非目标，协议未抓）；② **B**：同一页标题是「用这块实体盘下」，读者读到的是盒子能力；③ **B**：本轮 N13 让星阵那两句成立了，剩 OGS 不成立 | 不改 |
| X2 | KGS 排不排期？（2026-07-12 选型定为「工程下一步」，但 07-13 README 又列为待决，此后无答复；脚手架里接受 / 发挑战仍是 `NotImplementedError`，未注册、无入口） | A. 排进 X4 之后<br>B. 押后到上市后 | **A**。KGS 回盒需要的正是 X4 那条用户级事件通道，先有通道再接 KGS，否则会重复踩 OGS 的「挑战发出去回不来」 | 不动，界面上没有 KGS，用户不会被误导 |

## 5. 不在本轮

| 条目 | 类别 | 一句理由 |
|---|---|---|
| X1 野狐接入本身 | 已裁定不做 | Fan 2026-07-12 亲裁：要 Windows 客户端在环或官方商务合作，定为上市后 BD 里程碑；可由 Fan 重开。本轮只统一屏 01 文案 |
| X12 ① 平台状态条 | 已裁定不做 | scope §27 D-1（独立 agent 出裁、track 作者核过，非 Fan 亲裁）：「连没连上」没有可信来源，登录闩会撒谎；可重开，但须先有真心跳 |
| X12 ② 星阵 39 档名单 | 已裁定不做 | scope §19 ①（Fan 授权 agent 自裁，2026-08-24）；39 档都能选，只是不摊成列表 |
| X12 ③ OGS 挑战条件可选 | 已裁定不做 | 设计稿自己画成「条件是写死的 · 固定」；后端其实收 board_size/rules/ranked/handicap/komi，要开放时只动前端 |
| X12 ④ 星阵人机的升降级 / 9·13 路 / 重启续局 / 云端代理 | 已裁定本期不做 | kiosk-play-golaxy plan.md §1/§12（采纳 Codex/Gemini 评审）；9/13 路受实体盘 19 路硬件约束 |
| X5 OGS 对局屏计时 / 着法待确认 / 对手落子提示 | 依赖 X4 | 今天没有任何 OGS 对局能落到盒上，这层缺口对用户不可见 |
| N4 OGS 真人局会话类型为 free、不标远端色、LED 不为远端亮灯 | 依赖 X4 | 同上；X4 那一轮建局时一并设 `game_type` 与远端色 |
| N13 的 OGS 部分（平台侧自然终局不落账） | 依赖 X4 | 同上 |
| X10 的 M1（已终局时重试弹伪错误框）、M3（打劫回提静默循环）、I2（星阵服务器上棋谱镜像存储） | 需上板复现 / 非盒上可见 | M3 只能在实体盘上故意打劫复现；I2 只影响星阵那边存的谱；M1 需要「恢复框开着时对局在别处结束」这一时序，先上板看是否真出现 |
| P9 盒上 `game_repo = None`（人人对弈局不落账） | 归「人人对弈」模块 | 挂在 P2 跨盒人人对弈路线裁定下；本轮星阵局落账绕开了它，不修它 |
| 对局屏红条不可关、内容是后端原文（N25）；「图表」默认开（A9）；数子依赖分析分（A12） | 归 play-ai（对弈·AI）赛道 | 同在 `GamePage` / `GameControlPanel`，本轮不碰那几段 |
| 新文案补 PO | 全局待裁（Z1） | 本轮新 key 一律 `t('ns:key', '中文默认')`，不往 PO 里加 |

## 6. 与其它四条赛道的协调与共享文件

### 6.0 五条赛道统一协调规则（2026-09-14 主会话写定，五份 PRD 同文）

**基线**：五个分支从 develop `6f7dc629` 开出，提交文档前已快进到 develop `bad0c1fb`。中间 28 个提交全是视觉/LED 标定与盒端登录页，**不碰任何一份 plan 要改的文件**，plan 里的行号仍然有效。五个分支在同一个仓里，彼此不用 push 就看得见：`git log feature/kiosk-go-<赛道> -- <文件>`。

**会撞的地方（按风险排序）**

1. **对局结束 → 落账 / 结算（`server.py`）：两条赛道各设计了一套，必须收成一条。**
   - 对弈·AI（N22）：新增 `_finish_ended_game`，挂 `manager.on_game_ended`，`/api/move` 自然终局改走它。
   - 跨平台（N13）：新增 `_record_platform_engine_game` / `_session_owner`，给 `_record_ai_game(_locked)` 加 `data_overrides`，在 resign / move / 视觉三处落账。
   - **规则**：终局收尾的唯一入口归对弈·AI 的 `_finish_ended_game`。跨平台照 plan 做，`data_overrides` 与 `_record_platform_engine_game` 保留为薄 helper；合并时由后合并的一方（默认对弈·AI，见下方顺序）把跨平台的三处调用点收进 `_finish_ended_game`。
   - **合并验收**：`grep -n "_record_ai_game(\|_record_platform_engine_game(" katrain/web/server.py` 里，终局路径的调用只经过 `_finish_ended_game`。两套并存就不算合完（同形状的教训见记忆「两套并行实现」）。
2. **`/api/resign` 与 `interface.py` `_do_resign`**：对弈·AI（N21）改判负方；跨平台在旁边加 `_do_end_without_result`，并在 resign 里加平台落账分支。两处 hunk 相邻，属文本冲突。N21 的判负方修正对星阵局同样成立，合并时两边都留。
3. **`GameControlPanel.tsx`（+ test）**：
   - 跨平台只动 `engineMode` 那一支的动作数组与 `.ghint`（X9-a）。
   - 对弈·AI 新建 `gameKinds.ts`（`isFreeVsAi` 保留 `engineMode` 参数），并改 `analysisActions`。
   - **归属**：`engineMode` 局的按钮集合归跨平台，其余局型归对弈·AI。
4. **`GamePage.tsx`**：
   - 跨平台改 `:335-341` `refreshItemCounts`、`:501` `handleEngineAnalysis` 两处 token 闸（X7），另加 `EndgameCard` 的 Void 说明行。
   - 对弈·AI 改 N17 / N21 / N25 / A18 等处。
   - 对弈·AI **不要顺手改那两处 token 闸**（归跨平台）。
   - `tests/kiosk-screen-05-game.spec.ts` 两家都改，后合并方保留两边断言。
5. **`KioskApp.tsx`**：训练营 T9 改 `:132` 做题路由守卫；棋谱 K1/K4 改 `:56` import 与 `:137-145` 摆谱路由。hunk 相邻，属文本冲突，两边都留。
6. **`repository.py`**：两家都只**调用** `RepositoryDispatcher._remote_only`，都不改它本身。
   - 训练营改 `tsumego_*`（`:189-225`）与 `get_all_problems`（`:98-106`）。
   - 棋谱改 `kifu_list_albums` / `kifu_get_album`（`:251-270`）。
7. **请求失败分类**：复盘赛道新建 `src/utils/requestFailure.ts`。其它赛道本轮不依赖它，**也不要另建同职责的共享文件**（各自在本页内处理即可）。五家都合并后再收口，已登记为后续项。
8. **i18n**：五家都只写 `t('ns:key','中文默认')`，本轮不改任何 `.po`（并行改 11 份 `.po` 必冲突）。合并完统一交 `katrain-i18n-expert` 补 11 种语言，各赛道交付时附新增 key 清单。补不补、何时补仍由 Fan 定。
9. **四图存档**：取图目录各家不同，不冲突。跨平台重取 01/10，对弈·AI 重取 05，训练营 11，棋谱 17，复盘 19/20。重取前按 CLAUDE.md 跑两次比对，排除抖动。

**合并顺序（默认）**：改共享文件少的先合；改得最多的最后 rebase，由它负责解冲突。
1. **复盘/报告**：只新建共享文件，不改别家的文件。
2. **棋谱**：含 P0 K1，先落 `KioskApp` / `repository`。
3. **训练营**：rebase 到棋谱之上，解 `KioskApp` / `repository` 的相邻冲突。
4. **跨平台**：落账 helper 先落。
5. **对弈·AI**：13 个 Task，最大。最后 rebase，并按第 1 条把终局收尾收成一条。

例外：单个 P0 Task 只要不碰第 1、2 条所列代码，可以拆出来先合，不必等整条赛道。例如对弈·AI 的 N17 只动 `GamePage` / `useGameSession`。

**每次合并前**：
- `git merge develop`（或 rebase），然后跑本赛道 plan 的 Global Constraints：`npm run build` 与 `npm run build:kiosk-2d`、`npx tsc -b`，再按基线 diff 跑相关测试。
- 下一家 rebase 时，对照本节查**语义**冲突，不只看 git 报不报冲突。git 报「合得干净」不等于合得对。

### 6.1 本赛道会改、可能与别家重叠的文件（writer 按 plan 列出）


| 文件 | 本赛道改哪里 | 可能重叠的赛道 / 条目 |
|---|---|---|
| `katrain/web/ui/src/kiosk/pages/GamePage.tsx` | `:142` 解构、`:335-341` `refreshItemCounts`、`:501` `handleEngineAnalysis`、`EndgameCard`（`:115-136`）加一行说明 | play-ai（A5 终局卡死子、A7 AI支招、A9 图表默认、A12 数子、A17 终局反馈、N17 失效会话、N21 AI 思考时认输、N25 红条） |
| `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx`（+ `.test.tsx`） | `engineMode` 动作数组（`:309-321`）、`.ghint` 三元（`:421-427`）；测试文件在悔棋 `test.each` 后加一条 | play-ai（A4 ±10 手、A7、A11 棋谱折叠、N14 升降级领地、N21 认输禁用、N23 数子路数） |
| `katrain/web/ui/src/kiosk/pages/PlayPage.tsx`（+ `.test.tsx`） | `:43-60` 状态请求 effect、`:140-148` 野狐卡 `soon`；测试文件改 `expectAllDisconnected` 与登出用例夹具、末尾加盒端用例 | play-ai（A6 全部对局卡、N17 继续上一局）、kifu/tsumego（N10 继续上一局存储）、tsumego（N26「约战 · 有定级队列」文案） |
| `katrain/web/server.py` | `/api/move` 平台分支 except（`:983-984`）、`/api/resign` 落账分支（`:1883-1943`）、`_record_ai_game(_locked)` 签名与 data 合并（`:1599-1677`、`:1864-1872`）、`_handle_confirmed_move` except（`:3217-3224`）、新增模块级 `_record_platform_engine_game` / `_session_owner` | play-ai（A12 数子、N21 认输、升降级落账）、review（报告）、所有改服务端的赛道 |
| `katrain/web/interface.py` | `_do_resign` 旁新增 `_do_end_without_result`（`:1464-1469` 附近） | play-ai |
| `katrain/web/ui/src/kiosk/components/report/reviewPresentation.ts`（+ `.test.ts`） | `outcomeLine` 认 `Void` | review（复盘 / 报告） |
| `katrain/web/core/physical_play_orchestrator.py`（+ `tests/test_physical_play_orchestrator.py`） | `_run` 开头加一步、新增 `_release_recovery_on_game_end` | play-ai（A20 改用屏幕落子） |
| `katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx` | auth mock 改可变、改写「停一手可按」用例、新增盒端用例 | play-ai（若动 engineMode 相关断言） |
| `katrain/web/ui/tests/kiosk-screen-05-game.spec.ts` | 屏 10 用例动作区标签 | play-ai（屏 05 同文件） |
| `superpowers/tracks/kiosk-go-shell-align/visual/01-play/`、`visual/10-platform-game/` | 重取四图 | play-ai（屏 05 同一个 `GamePage`，若它重取 05） |
| 本赛道独占 | `PlatformLobbyPage.tsx`、`EngineMoveErrorDialog.tsx`、`platforms/gateway.py`、`tests/platforms/test_engine_gateway.py`、`tests/platforms/test_engine_integration.py`、新文件 `tests/platforms/test_engine_game_ledger.py`、`tests/test_vision_move_poller.py`（末尾追加一个 class）、`src/kiosk/__tests__/EngineMoveErrorDialog.test.tsx`、`PlatformLobbyPage.test.tsx`、`tests/kiosk-screen-10-platform-game.fourup.spec.ts` | —— |

## 7. 验证方式

| 层 | 做法 | 适用条目 |
|---|---|---|
| 前端单测 | `cd katrain/web/ui && npx vitest run <文件>`；结束时全量 `npx vitest run` 与动手前的**失败用例名集合**比（不比条数） | X7 X8 X1 X4-a X9-a X9-b N13（presentation） X10-a |
| 后端测试 | `uv run pytest <文件>`；结束时 `CI=true uv run pytest tests` 的失败用例名集合与基线比 | X9-b N13 X10-a |
| 类型检查 | `npx tsc -b`（`npx tsc --noEmit` 检查 0 个文件，无效） | 全部前端条目 |
| 两套构建 | `npm run build` 与 `npm run build:kiosk-2d` 都绿（`GamePage` / `api` 调用处在共享消费链上；`verify:kiosk-2d` 不许破） | 全部前端条目 |
| 真浏览器几何 | `tests/kiosk-screen-05-game.spec.ts` 屏 10 用例（vite dev，`playwright.visual.config.ts`） | X9-a |
| 四图对比 | 屏 01、屏 10 各跑**两次**取抖动底（屏 10 是 canvas 盘，抖动约 4500 像素），只提交内容真变了的屏；Fan 确认 | X1（屏 01）、X9-a（屏 10） |
| 承重实测 | 不触发：本轮没有改变任何受限高度区域里的节点结构（X9-a 动作区仍一行；X9-b 说明行在绝对定位的终局卡里、其子树无人读几何） | —— |
| 上板（盒上 token=null 真环境） | 严格盒端构建部署到 RK3562 后逐条走：X7 角标与支招白灯；X8 屏 01 已连接；N13 认输后屏 19 出现该局；X10-a 等待态认输后灯灭。X9-b 的 AI 终局依赖第三方行为，列观察项 | X7 X8 N13 X10-a（X9-b 观察） |
