# 星阵实时大厅与开局入口 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将用户确认的星阵专属首页落实为 1024 × 600 React 页面，接入真实对局和在线棋友列表，并为观战、快速匹配和房间对弈建立有协议事实支撑的开局流程。

**Architecture:** 复用 `GolaxyHomePage`、平台账号鉴权、现有星阵 adapter 和跨平台对局桥接。列表通过盒端代理取星阵 REST，前端只接收最小字段。开局前设置页保存屏幕/实体盘选择；星阵 AI 保持原设置页。观战与 PvP 各自从已证实的快照/事件起步，协议不足时停在独立事实闸，不发送猜测的写请求。

**Tech Stack:** React + TypeScript + Vitest/Playwright，FastAPI + httpx + pytest；目标视口 1024 × 600。

**Approved design:** `docs/previews/golaxy-live-lobby-1024x600.html`；规格：`docs/superpowers/specs/2026-10-01-golaxy-lobby-and-pregame-design.md`。原星阵协议文档的 PvP 结论是 NO-GO；本计划的 Task 4 专门更新该结论。运行时视觉确认之前不得进入本切片的后端实现。

**Scope rule:** 本计划的 Tasks 1–3 是可独立交付的只读大厅切片。Tasks 4–6 为观战和 PvP 的事实闸；在写请求/实时协议被证实前，不把预览里的可点击示意当成生产可用功能。若事实闸无法通过，先交付真实大厅并向用户说明缺口，另按事实写可执行的后续计划，不猜 API。

**Current gate (2026-10-01):** 已用本机 Chrome 在 1024 × 600 跑完星阵大厅、快速匹配、建房、入房和现有人机设置共 5 个运行时截图状态；`docs/previews/golaxy-live-lobby-runtime-review-1024x600.html` 提供参考图、运行图、并排和叠加对照。聚焦 Vitest 22/22、`tsc -b` 和 Playwright 5/5 通过。用户已明确确认运行时布局，Task 2 后端切片可开始。首页房间样本仍只在截图测试拦截层；人机设置沿用现有页，木纹使用共享棋盘组件。

---

## Chunk 1: 实时大厅

### Task 1: React 运行时与 7 英寸视觉确认

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/GolaxyHomePage.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/GolaxyHomePage.test.tsx`
- Modify: `katrain/web/ui/src/kiosk-shell/golaxy-home.css`
- Create: `katrain/web/ui/src/kiosk/pages/GolaxyPregameSetupPage.tsx`
- Create: `katrain/web/ui/src/kiosk/pages/GolaxyPregameSetupPage.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.routes.test.tsx`
- Modify: `katrain/web/ui/src/api.ts`
- Modify: `katrain/web/ui/tests/kiosk-screen-07-09-platform.fourup.spec.ts`

**Contract:** 首页不读写 `kiosk_play_on_board`，只列真实房间/棋友；旧 AI 卡仍进入 `/kiosk/play/cross-platform/engine/golaxy`。两个 PvP 卡分别进入 `/kiosk/play/cross-platform/golaxy/setup/quick` 与 `/setup/room`；两个设置页都有返回星阵首页、屏幕/实体盘选择和仅 19 路实体盘的约束。选择调用现有 `playInputState` / `writePlayOnBoard`，不开局前不创建对局；因写协议未核实，最终提交按钮明确暂不可用。观战卡在协议证实前只显示明确的“观战接入中”，不能画空盘冒充同步棋谱。Playwright 用隔离的 API 拦截样本，生产代码无样例房号/棋手。

- [x] **Step 1: 写失败的前端测试。** `GolaxyHomePage.test.tsx` 断言：首页没有“落子”控件；快速匹配/房间卡进入各自 `/golaxy/setup/{mode}`，AI 进入既有设置；房间双列卡包含房号、类型、让先/分先、双方昵称/段位、阶段、观战人数；在线棋友标签切换；加载、真实空列表、失败/重试不同；接口异常不显示“暂无对局”；房间点击不进入假观战棋盘。`GolaxyPregameSetupPage.test.tsx` 与路由测试断言两个 URL 可直达/刷新、返回星阵首页、创建/加入房间切换、选择屏幕/实体盘并持久化、摄像头不可用时实体盘禁用、提交按钮暂不可用且不会发写请求。`platformRooms` 和 `platformUsers` 只通过 `API` mock，不在生产代码硬编码示意响应。
- [x] **Step 2: 跑 `cd katrain/web/ui && npx vitest run src/kiosk/pages/GolaxyHomePage.test.tsx`。** 新断言在旧页面失败。
- [x] **Step 3: 实现最小布局与状态。** 沿用 `KioskPagebar`、`KioskSecLabel`、`KioskCard`、`KioskSetupBoard` 和现有设置控件；在 `KioskApp.tsx` 登记 quick/room 两条确定路由，新页用 `useParams` 只接受这两个 mode，未知模式返回星阵首页。首页新增卡片字段排版及加载/错误/空态。为 API 增加明确的 `GolaxyRoom`、`GolaxyOnlinePlayer` 类型和 `platformRooms` 返回类型；先在测试/Playwright 拦截层提供字段形状，不向生产代码注入 Fixture。删除首页 `chooseInput`、`inputTick` 和相关 CSS；保留 AI 设置页现有 `setup-input`。
- [x] **Step 4: 在 1024 × 600 取参考稿、React 运行图、并排和叠加图。** 逐项检查首页、快速匹配设置、创建/加入房间设置和 AI 现有设置的页控条、三张开局卡、双列房间、在线棋友、滚动范围、文字/状态和 44 px 触控区；说明提交暂不可用的协议原因，修复本次页面的偏差后给用户确认。用户已确认此视觉关卡。
- [x] **Step 5: 跑该 Vitest 与 `cd katrain/web/ui && npx tsc -b`，预期通过。**

### Task 2: 星阵真实房间与在线用户数据

**Files:**
- Modify: `katrain/web/platforms/golaxy/adapter.py`
- Modify: `katrain/web/platforms/golaxy/PROTOCOL.md`
- Modify: `katrain/web/api/v1/endpoints/platforms.py`
- Modify: `katrain/web/ui/src/api.ts`
- Create: `tests/web_ui/test_golaxy_lobby.py`

**Contract:** 复用有所有者校验的 `GET /api/v1/platforms/golaxy/rooms`、`GET /api/v1/platforms/golaxy/users`；盒端调用星阵 `GET /api/social/gameroom/list`、`GET /api/social/gamezone/user/list`。现有通用 `/users` 对无 `q` 请求走 `get_open_challenges()`；本任务只为 `golaxy` 改为 `get_online_users()`，保留 OGS 分支。只传房号、状态、19 路/规则等已确认字段和双方展示信息；未知字段为 `null` 或不显示，绝不伪造。平台返回业务非成功码、结构错误、超时或认证失效时返回可诊断的 502/401，不返回 `200 []`。实际空列表才回 `[]`。初次重连以认证的用户列表检查令牌，若过期先用已有刷新令牌重试一次并持久化；运行中再次过期则返回 401，引导重新连接，不由并发列表请求各自刷新。所有者以当前平台连接为准，不在日志保存星阵令牌或完整个人资料。

- [x] **Step 1: 将已观察到的匿名化房间和用户响应最小字段写入 `PROTOCOL.md`。** 对照星阵当前 JS 调用点确认分页、字段路径、业务 `code`/`data` 语义；不知道的字段不映射。已在 RK3562 取得真实成功用户列表的匿名化字段；没有保存个人资料。
- [x] **Step 2: 写失败的 `tests/web_ui/test_golaxy_lobby.py`。** 用 `httpx.MockTransport` 检查鉴权头只到星阵、成功/空列表映射、异常 code/畸形响应/超时；通过真实 `PlatformManager` 和 HTTP 测试客户端检验 `/golaxy/rooms`、无 `q` 的 `/golaxy/users`、其他用户不能读该账号、OGS 无 `q` 仍走原挑战列表分支；上游失败不是空列表。
- [x] **Step 3: 在 `GolaxyRestClient` 增加两个只读方法，`GolaxyAdapter.get_rooms/get_online_users` 做字段规范化。** 在平台端点增加星阵无 `q` 的专用分派及字段投影，不改变 OGS。初次 `connect()` 验证已存令牌时调用认证的用户列表，401 时只在该串行连接流程刷新一次并发出 `token_refreshed` 供 manager 持久化。API 层区分运行中 401 与上游 502，避免泄露响应正文。没有改动人机引擎通道；本阶段对未知段位/观战人数返回空值。
- [x] **Step 4: 跑 `pytest -q tests/web_ui/test_golaxy_lobby.py tests/web_ui/test_platform_scan_login.py`，预期通过。** 实现代理报告加上令牌持久化套件 65 项通过，规格与质量复审通过；最后别名优先级的聚焦 14 项再次通过。

### Task 3: 大厅前后端闭环

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/GolaxyHomePage.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/GolaxyHomePage.test.tsx`
- Modify: `katrain/web/ui/tests/kiosk-screen-07-09-platform.fourup.spec.ts`

- [x] **Step 1: 用真实盒端类型打通列表。** 页面登录连接成功后分别取房间/棋友；切标签不丢另一列表；可见时 30 秒刷新，卸载即清理，失败可重试。当前只显示已证实的手数；进行中/已结束状态的 wire 映射尚未实测，不猜阶段。房间卡观战入口在 Task 4 完成前只给可见的待接提示。
- [x] **Step 2: 测试空、失败、重试与刷新竞态。** 旧请求迟到不能覆盖较新结果，断开连接后不继续展示前账号的列表；对真实示例字段做一次 API 层集成测试。房间首卡点击的反馈现位于固定大厅标题，切标签会清理。
- [x] **Step 3: 运行 `pytest -q tests/web_ui/test_golaxy_lobby.py`、前端聚焦 Vitest、`npx tsc -b`，并在 1024 × 600 再取一张真实契约形状的运行时图。** 已通过，Fixture 仅在测试拦截层；规格和质量复审均通过。RK3562 已连接，但新代码尚未部署，真机旅程留在交付阶段验证。

## Chunk 2: 观战与星阵 PvP 契约

### Task 4: 核实观战初始棋谱与增量

**Files:**
- Modify: `katrain/web/platforms/golaxy/PROTOCOL.md`
- Create: `katrain/web/ui/src/kiosk/pages/GolaxySpectatorPage.tsx`（先做运行时视觉关卡）
- Modify: `katrain/web/platforms/golaxy/adapter.py`
- Modify: `katrain/web/api/v1/endpoints/platforms.py`
- Create: `tests/web_ui/test_golaxy_spectator_contract.py`

- [x] **Step 1: 对同一正在进行的普通星阵房间，核实初始棋谱与增量。** 已实测认证 `GET /api/social/gameroom/info/{room.id}` 为 HTTP 200/code 0；31 秒内对 4 个进行中、19 路、0 让子房间重复 GET，`moveNum/situation` 从 27→29、37→39、43→49、43→44，旧序列全部是新序列前缀。官网房间控制器也读取这个 GET 并轮询；`/wsgame/game/meta|state/{id}` 对 room ID/game ID 均返回 404，不用这些猜测路径。
- [x] **Step 2: 先按已确认交互稿做只读观战运行时页，在 1024 × 600 取参考、实现、并排和叠加图，交给用户确认。** 从大厅房间卡进入；使用共享 `GoBoardSvg` 但保留该页布局。Fixture 仅在测试；页面分别呈现加载、同步中、失败和离开，不画假棋局。`docs/previews/golaxy-spectator-runtime-review-1024x600.html` 已获用户确认，规格和质量复审通过；房间/身份切换旧盘首帧问题已修复。
- [x] **Step 3: 用已核实的 GET 构建只读观战快照端点与测试。** 所有者前后双重校验；解析 `gameMetaDto.gameState.situation` 有序历史，以纯 Python `sgfmill.boards.Board` 重放提子和 pass，依赖已加入 web/板端。按 `golaxy_to_katrain` 的自下向上 row 输出 GTP，Q16/Q4 非对称测试通过。只对已实测的 `boardSize=19, handicap=0, startMoveNum=0, gameType='82', rule='chinese'` 开放；其他布局 422，畸形历史/上游异常 502，失效登录 401。只返回白名单快照字段，不返回令牌或原始上游响应。规格与质量复审通过，项目 `.venv` 聚焦套件 87/87 通过。
- [ ] **Step 4: 观战页可见时每 10 秒读取完整快照并替换本机状态；卸载/隐藏时停止，旧请求不得覆盖新请求。** 代码与聚焦测试已完成并通过规格、质量复审：顺序 GET，隐藏/卸载中止，恢复立即同步，刷新中保留同房间同身份的上次盘并标状态，失败清盘；401/422/502 与终局未知胜负有明确提示。还需 RK3562 可访问后，至少验证一个星阵进行中房间，才能勾选本步。未取得 terminal wire 样本之前只标记星阵报告的 `gameroomStatus=40`，不自行推断胜负。
- [x] **Step 5: 把官网静态证据和本次匿名化实测写入 `PROTOCOL.md`。** 文档已记录全序列黑先重放、`-1` pass、坐标方向、已实测元数据位置与当前支持边界。真实提子/pass/终局 wire 样本仍缺；终局 `result` 保持 `null`，不自行推测胜负。

### Task 5: 核实快速匹配与房间写协议

**Files:**
- Modify: `katrain/web/platforms/golaxy/PROTOCOL.md`

- [ ] **Step 1: 在获授权、可控的星阵测试会话中捕获快速匹配的开始、心跳、匹配成功、取消/超时，以及建房、按号入房、配置协商、座次、落子/停一手、认输/终局的匿名化 REST/STOMP 帧。** 官方网页静态 JS 的调用路径只作线索，不替代响应和事件样本。避免误匹配陌生棋手；若无法安全取得真实帧，记录缺口，不发送猜测写请求。
- [ ] **Step 2: 对每个行为写事实表：请求体、响应码/业务码、事件体、失败/重试、游戏 ID、权威终局。** 核对现有 adapter 中 `submit_move({x,y})` 和 `supports_rooms=True` 的猜测是否成立；未证实时不得开放真实匹配/房间提交。
- [ ] **Step 3: 契约齐备后另写完整观战/PvP 计划，并在用户已批准的 UI 基础上实施：API 状态/取消、远端权威棋局桥接、视觉识别、终局保存及 RK3562 真局验收。** Task 4 与 Task 5 的事实合并提交第二次独立 gpt-6-astra max 计划审核；未齐备时向用户说明实证缺口和下一次可控测试所需动作。

### Task 6: 本切片代码复审与交付

**Files:** 仅 Tasks 1–3 实际变更的文件。

- [ ] **Step 1: 按 `superpowers:subagent-driven-development` 对独立实现任务做规格与代码质量复审，修复阻塞项；最后再按 `superpowers:requesting-code-review` 复审本切片整体。**
- [ ] **Step 2: 对照用户确认设计逐条报告：真实大厅、AI 返回、快速匹配/房间、观战分别处于已接通或协议待证状态。** 仅把完成且通过验收的代码提交/合入；设备部署前再次核对真机连接与构建。

---

**Completion criteria for this plan:** 真实星阵房间与在线棋友可在盒上刷新显示；首页不再出现落子设置，AI 落子设置保留；每个显示的数据都来自星阵，失败不伪装为空。观战与 PvP 仅在各自事实闸和后续实施测试通过后宣称可用。
