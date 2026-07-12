# PRD：Kiosk 对弈模块 · 本地对弈（两人面对面对弈 + 存谱复盘）

- **Track**: `kiosk-local-play`
- **目标分支**: `feature/kiosk-local-play`
- **作者**: fan
- **日期**: 2026-07-12
- **状态**: 草案 (Draft)
- **配套文档**: [`plan.md`](./plan.md)（实现计划，另出）

---

## 1. 背景与动机

「对弈」是 kiosk 智能棋盘的一级模块，已落地「人机对弈（自由/升降级）」「跨平台对弈」「在线大厅」。
其下的**「人人对弈 · 本地对局」**卡片（`PlayPage` 「人人对弈」区，副标题「两人在智能棋盘上面对面对弈」）目前指向
`play/pvp/setup`，而该路由仍是 `PlaceholderPage` —— 功能空缺。

本轨道补齐这块：**两个人面对面坐在同一台 kiosk 前，用真实智能棋盘（或触屏兜底）对弈，全程本地闭环，
无 AI、无远程对手、无 LED 引导（双方各自摆自己的子）。对局终局后自动存谱，可在「对局历史」里回看并一键做 AI 复盘。**

**为什么现在做**：物理棋盘的视觉识别能力已在人机对弈中跑通，且 `_vision_move_poller` 按 `player_to_move`
通用归属落子（PRD `kiosk-physical-play` R8.1 明确「为本地对局留门：黑白双方都来自视觉」）。本地对弈是这套能力
最直接、成本最低的一次复用 —— 主对局页 `GamePage` 已支持人人对弈（`aiColor===null` 分支），对局路由
`play/pvp/local/game/:sessionId` 也已就位。缺的只是**建局设置页、双人 human 的后端建局分支、存谱来源区分 +
对局历史/复盘 UI**。

**顺带修复的现存隐患**：终局自动存谱 `_record_ai_game` 直接写本地 SQLite（`app.state.user_game_repo.create`），
**绕过 `RepositoryDispatcher`、从不入同步队列**；而对局列表/详情的 v1 API 走 dispatcher，**在线优先读远程**。
两者不一致 —— 在线状态下，本地记录的人机对弈棋谱在远程列表里根本刷不出来。本轨道把存谱统一改走 dispatcher，
一并修掉这个 bug。

---

## 2. 已拍板的设计决定（2026-07-12 brainstorm）

| # | 决定 | 摘要 |
|---|---|---|
| D1 | **落子输入 = 实体棋盘为主 + 触屏兜底** | 两人在实体智能棋盘摆子，摄像头识别双方落子（黑白都来自视觉，无 LED）；摄像头不可用时自动降级为触屏轮流点子（`playerColor=null`，按 `player_to_move` 交替）。 |
| D2 | **复盘 = 结束即存 + 对局历史列表 + 一键复盘** | 终局自动存谱；新建 kiosk「对局历史」浏览页（列当前账号 `user_games`，可筛「本地对局」）；每条可打开研究页做 AI 复盘；终局卡片提供「复盘本局」直达。 |
| D3 | **账号 = 需登录，归当前账号** | 沿用现有 `user_games` 归属逻辑（`current_user` + `session.user_id`）；未登录则在进入本地对弈前拦截、提示先登录。不做游客/匿名存储。 |
| D4 | **设置项** | 棋盘路数（9/13/19）、规则（中/日/韩/AGA）、贴目、让子、黑白双方姓名、用时（主时间 + 读秒）、落子确认音/当前手方提示。**不含** AI 策略/棋力（无 AI）。 |
| D5 | **存谱 = 同步到远程（走 dispatcher）** | 存谱改走 `dispatcher.user_games_create`：在线→远程服务器，离线→本地 + 自动排队补传（`SyncWorker` 已就绪）。换机/重登不丢谱，galaxy 网页端可复盘同一局。**同一改动修复 D1 段所述 HvAI 存谱 local-only 的 bug。** |

---

## 3. 范围

### 3.1 In scope（一期，本轨道）

1. **建局设置页 `PvpLocalSetupPage`**（`play/pvp/setup`）：以 `AiSetupPage` 为骨架，去 AI 策略/棋力，加黑白双方姓名。
2. **后端 `game_setup` 新增 `pvp_local` 分支**：黑白双方均设 `player:human`，无 AI player。
3. **对局页 HvH 门控**（改 `GamePage`）：`pvp_local` 时 `Board` 传 `playerColor=null`（触屏轮流）；视觉落子对双色通用；无 AI 思考/落子 banner；无 LED。
4. **存谱统一走 dispatcher + 来源区分**：`source="play_local"`；`_record_*` 路径接入 `RepositoryDispatcher`（含 HvAI bug 修复）。
5. **对局历史页 `GameHistoryPage`** + 入口 + kiosk 侧 `user_games` 读 API 薄封装。
6. **一键复盘**：`ResearchPage` 新增 `?user_game_id=` 加载分支；终局卡片「复盘本局」按钮。

### 3.2 Out of scope（descope，留门不做）

- 死子标记 / 精确目数分解（依赖后端 `dead_stones` 字段，Gate S，沿用 HvAI 现状）。
- 语音报点 / 语音交互。
- 对局中途换人、悔棋协商、双人各自计时的独立时钟 UI 增强（沿用现有计时器）。
- 游客/匿名对局与本地匿名存储（D3 已定需登录）。
- LED 相关任何新编排（本地对弈明确无 LED）。

---

## 4. 功能需求

### 4.1 建局（PvpLocalSetupPage）

- **R1.1** 进入 `play/pvp/setup` 前校验登录态；未登录展示提示 + 去登录入口（复用 `LobbyPage` 的 auth 守卫写法）。
- **R1.2** 左侧盘面预览（`LiveBoard`），右侧表单：棋盘路数、规则、贴目、让子、黑方姓名、白方姓名、用时开关（主时间 + 读秒时间 + 读秒次数）、落子确认音开关。
- **R1.3** 姓名可留空；留空时 SGF 的 `PB`/`PW` 及展示名回落为「黑方」/「白方」。
- **R1.4** 让子 > 0 时隐藏贴目输入（与 `AiSetupPage` 一致）。
- **R1.5** 「开始对弈」→ `createSession` → `gameSetup(session_id, 'pvp_local', settings)` → `writeActiveSession({route: /kiosk/play/pvp/local/game/:id})` → 跳转对局页。失败展示错误 Alert。

### 4.2 后端建局（game_setup · pvp_local）

- **R2.1** 新增 `elif mode == "pvp_local"` 分支：黑白双方 `update_player(player_type="player:human", player_subtype="player:human", name=...)`，无 `player:ai`。
- **R2.2** `session.game_type = "pvp_local"`；`new_game(size, handicap, komi, rules, game_type="pvp_local")`。
- **R2.3** 计时器配置复用 `free/ranked` 分支的 `time_enabled` 逻辑。
- **R2.4** `pvp_local` 在分析门控上等价于 `free`（允许分析/数子），但在存谱来源上可区分（→ `play_local`）。

### 4.3 对局进行（GamePage · HvH）

- **R3.1** HvH（`game_type==='pvp_local'`，两方均 human）时 `Board` 传 `playerColor=null`，触屏可轮流落子（按 `player_to_move`）。
- **R3.2** 实体棋盘：`_vision_move_poller` 按 `player_to_move` 通用注入双方落子；**须验证** 视觉落子后不触发任何「对方是 AI」的自动 genmove；**须验证** `pvp_local` 无 LED 编排（no-op）。
- **R3.3** 摄像头掉线 → 复用现有 toast「摄像头断开，已切换为触屏模式」→ 自动降级触屏。
- **R3.4** AI 思考中 / AI 落子提示 banner 在 HvH 天然不出现（`aiColor===null` 已门控）。
- **R3.5** 认输 / 退出确认沿用现有对话框。
- **R3.6** 数子：`pvp_local` 无 `player_b/w_id` → `is_multiplayer=False` → 走 HvAI 即时数子路径（KataGo 打分）；分析未就绪时返回现有「等待分析」提示。

### 4.4 存谱（同步到远程）

- **R4.1** 终局（认输 / 数子 / 双 pass）自动存谱：`source="play_local"`，黑白名取 SGF `PB/PW`（空则「黑方/白方」）。
- **R4.2** 存谱**走 `RepositoryDispatcher.user_games_create`**：在线→远程，离线→本地 + `SyncWorker` 队列补传。
- **R4.3** 同一改动把 HvAI 存谱也切到 dispatcher（`source` 动态化，`play_ai`/`play_local` 按 `game_type`）—— 修复 local-only 与 remote-first 读取不一致的 bug。
- **R4.4** dispatcher 在 server 模式可能不存在 → 需 `getattr` 回落到本地 repo（镜像 v1 端点的 `if dispatcher is not None` 守卫）。

### 4.5 对局历史 + 复盘

- **R5.1** 新建 `GameHistoryPage`：列当前账号 `user_games`（含 `play_ai` + `play_local`），可按 `source` 筛「本地对局」；每条显示黑白名 / 结果 / 手数 / 日期。
- **R5.2** 入口置于「人人对弈」区（或对局页终局卡片旁），least-invasive placement 由 plan 定。
- **R5.3** 点击历史条目 → `ResearchPage`，加载该局 SGF 做 AI 复盘。
- **R5.4** `ResearchPage` 新增 `?user_game_id=X`（对齐现有 `?kifu_id=` 模式）：从 user_games 取 SGF → `board.loadFromSGF` → 可选 `analyze=1`。
- **R5.5** 终局卡片「复盘本局」按钮：优先用刚存的 `user_game_id`；若前端拿不到该 id，则回落把当前对局 SGF（`API.saveSGF`）直接送入研究页。具体机制由 plan 依代码定。
- **R5.6** kiosk 侧新增 `userGamesApi` 薄封装，落位于**共享区 `src/api/`**（不得从 `src/galaxy/` 引入，遵 SBC 边界契约）。

---

## 5. 非功能需求 / 约束

- **SBC 构建边界契约**：本轨道只碰**共享区**（`src/api/`、`src/components/`、`src/hooks/`…）+ `src/kiosk/**`，不引 `three`/`@react-three`/galaxy/Board3D/VideoRecorder。改动共享文件须两套构建都跑（`npm run build` + `npm run build:kiosk-2d`），`npm run verify:kiosk-2d` 保持绿。
- **i18n**：所有静态串用 `t(key, '中文默认')`；复用既有 `ruleset:*` 等命名空间；默认中文（见记忆 i18n 架构 / 语言规约）。
- **测试**：前端 vitest/RTL（建局 payload、历史列表、HvH 门控、研究页加载分支）；后端 pytest（`pvp_local` 建局双 human、存谱走 dispatcher 的在线/离线两路），`CI=true` 跳 GPU。
- **登录/离线**：离线状态存谱不阻断本地复盘（本地 SGF 直接进研究页）。

---

## 6. 风险与验证点（交由 plan 落实）

| 风险 | 验证/缓解 |
|---|---|
| 视觉落子后误触发自动 AI genmove（HvH 不该有 AI 走子） | 定位 AI 走子触发点，确认无 `player:ai` 时自然跳过，否则加 `pvp_local` 守卫。 |
| `pvp_local` 误点 LED | 确认 LED 编排仅对 AI/远程对手落子触发，`pvp_local` 无此路径；否则显式 no-op。 |
| 存谱 sync→async 接线 | `_record_ai_game` 为同步函数、从同步端点调用；`dispatcher.user_games_create` 为 async。需把存谱路径接入事件循环（或改端点为 async），对齐 v1 端点 `await dispatcher...` 写法。 |
| 前端拿不到刚创建的 `user_game_id` | 「复盘本局」回落用 `API.saveSGF` 送研究页（R5.5）。 |
| `Board` HvH 落子锁死黑方 | `playerColor=null` 已验证允许 `player_to_move` 交替（Board.tsx:472/627）。 |

---

## 7. 分期与验收

**一期（本轨道）验收**：
1. 「人人对弈 · 本地对局」可从 `PlayPage` 建局、双人在实体棋盘/触屏完成一整局（含认输、数子、双 pass 终局）。
2. 终局自动存谱，`source=play_local`，在线时可在远程列表 / galaxy 端查到；离线时本地存 + 联网补传。
3. 「对局历史」页可列出并打开本地对局做 AI 复盘；终局卡片「复盘本局」可用。
4. HvAI 存谱同步 bug 一并修复（在线时人机对弈棋谱可在远程列表查到）。
5. 两套前端构建 + `verify:kiosk-2d` 全绿；前后端测试通过。

**留门（后续轨道）**：死子/精确目数、语音报点、独立双时钟 UI。
