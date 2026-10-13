# Galaxy 对局一致性与 kiosk 大厅观战计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. 独立文件范围可并行；最终先做规格核对，再做 GPT-6-astra max 代码与真实视觉审核。

**Goal:** 实施用户已确认的 Galaxy 三模块布局；RK3562 大厅保持现有布局，修复楷体、观战入口和未定级直接邀请。

**Architecture:** Galaxy 使用一个小型共享页框复用 ContentPageHeader，保持现有业务控件和服务端契约。kiosk 大厅沿用现有双列布局；观战独立复用星阵观战骨架，用只读快照同步中央对局，不创建本地棋局、不绑定摄像头、不调用对局动作。

**Tech Stack:** 现有 React、MUI、CSS、FastAPI、pytest、Vitest、Playwright/CDP。

## 已确认范围

- 用户已确认 `docs/design/play-consistency-2026-10-09/index.html` 的 Galaxy 设计，补充要求所有界面文字统一霞鹜楷体。
- 用户明确撤回 kiosk 的重排：当前 RK3562 大厅无需大改；自由/升降级/大厅的排版一致性问题只针对 Galaxy。
- kiosk 需允许点正在进行的棋局观战，参考现有星阵观战页。Galaxy 已可观战。
- 两个平台未定级都能直接邀请任意段位的空闲真人或机器人；快速匹配才需要定级，仍按同段位匹配。
- 本轮不改计分、定级、开局预约、AI 参数范围、正式对局状态机或机器人投放配置。
- 已有 `server.py` 邀请修复和参数化测试、`LobbyPage.css` 字体修复属于本轮，保留。
- 最后交付真实预览与审核结果；不把新布局审核通过等同于已部署。

## Chunk 1：最小共享基础

**Files:**
- Create: `katrain/web/ui/src/galaxy/components/layout/PlayPageLayout.tsx`
- Create: `katrain/web/ui/src/galaxy/components/layout/PlayPageLayout.css`
- Modify: `docs/design/play-consistency-2026-10-09/index.html`、`README.md`

- [x] 保留上一版 HTML，主稿撤掉 kiosk 自由/升降级重排；kiosk 只显示沿现有代码生成的大厅字体预览。
- [x] 主稿 Galaxy 的 UI/title/mono 字体全部先使用自托管 SmartBox Kai（霞鹜文楷），不把拉丁字体放在它前面。
- [x] 建立 `PlayPageLayout({title,status,children})`：根 `.galaxy-play-page`，滚动高度由现有 MainLayout 提供；内层最大宽度1440、桌面上下30/40与左右32，小屏20/16且留底栏空间。
- [x] 页头复用 `ContentPageHeader parentLabel="对局" parentTo="/galaxy/play"`。仅在共享页框内限定页头56高、返回44×44、标题32px/600（小屏26），间隔12与下边距24。保留 GameNavigationProvider 的导航行为，不修改其他模块的 ModulePlate 几何。
- [x] CSS 定义共享舞台边界/圆角12、侧栏340（窄屏300、手机堆叠）、按钮44px。所有正文/标签/标题/数字/英文使用霞鹜楷体；SVG图标保留。
- [x] 使用现有字体资产：Galaxy 的 LXGW WenKai 子集覆盖中文；中文主题字体栈补充共享 SmartBox Kai 覆盖其缺失的拉丁字符，避免外壳与内容数字/英文落回系统 sans。不下载新字体，不重构全站主题。

## Chunk 2：Galaxy 自由和升降级页面

**Owner:** 独立实现智能体；只改以下文件及对应测试。

**Files:**
- Modify: `katrain/web/ui/src/galaxy/pages/AiSetupPage.tsx`
- Modify: `katrain/web/ui/src/galaxy/components/aiLadder/AiLadderRatedSetup.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/AiSetupPage.test.tsx`（有新增行为才补断言）

- [x] 三条分支（游客升降级、登录升降级、自由对弈及加载态）全部使用共享页框和返回入口。
- [x] 自由对弈将现有两组控件放进连续舞台左侧，右侧显示当前设置摘要与主行动/返回。保留所有策略、棋力阶梯、时间开关与详细参数、取值范围和提交逻辑；摘要从当前状态计算，不用 HTML 样例值。
- [x] 升降级既有主信息与右侧挑战保持，调整为共享舞台侧栏/间距/按钮，保留加载、错误、游客登录、挡局、结算回执与预约门禁。
- [x] 运行已有 `AiSetupPage.test.tsx` 和 `AiLadderRatedSetup.test.tsx`；仅补返回或摘要变化的有意义覆盖，不建立新的样式快照测试层。

## Chunk 3：Galaxy 大厅

**Owner:** 独立实现智能体；只改以下文件及对应测试。

**Files:**
- Modify: `katrain/web/ui/src/galaxy/pages/HvHLobbyPage.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/HvHLobbyPage.css`
- Modify: `katrain/web/ui/src/galaxy/pages/HvHLobbyPage.test.tsx`（需要时）

- [x] 使用共享页框，段位状态放页头右侧，说明下沉正文。
- [x] 按确认稿对齐快速匹配条、进行中对局和棋友两列（1.3:1、gap22）、面板间距、按钮与霞鹜楷体；保留名单筛选、实时数据、错误/重试、所有邀请码和观战路由。
- [x] 对局卡保留可点击观战及自己的返回棋盘，按钮和键盘行为可操作；不引入展示用业务数据。
- [x] 运行已有大厅测试，核对未定级匹配打开指引但邀请发出 `invite`，不改真人优先与延迟匹配。

## Chunk 4：kiosk 只读观战

**Owner:** 独立实现智能体；避免改已有参与者镜像/物理对局路径。

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/LobbyPage.tsx` 与 `.test.tsx`
- Create: `katrain/web/ui/src/kiosk/pages/PvpSpectatorPage.tsx` 与 `.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`（新增观战路由）
- Create: `katrain/web/api/pvp_spectator.py` 与 `tests/web_ui/test_pvp_spectator.py`
- Modify: `katrain/web/server.py`（只注册新路由；保留现有邀请改动）

- [x] 先用现有大厅测试证明别人棋局不可点击；补点卡片进入独立 `/kiosk/play/pvp/watch/:sessionId` 的回归。自己的棋局继续原 room 路由。
- [x] 新观战页复用 `golaxy-spectator.css`、KioskPagebar、GoBoardSvg 的现有观战几何（1024×600 下左侧474px，右侧自适应）；返回大厅、双方姓名/段位、当前手数与对局状态。以实时盘面为第一期；不显示不可用的假历史控件/分析/对局动作。
- [x] 快照 GET `/api/pvp/spectate/{session_id}`：登录必需；盒子经现有 PvpBoxBridge.check_user/request 用服务端云凭证读取中央同一 `/api/pvp/spectate/{central_id}` 端点，使用原始中央ID，不把它当本地ID、不创建镜像。固定路径仅接受安全 session ID。
- [x] 中央仅允许 session.game_type 为 free/pvp_lobby 且双方席位均为整数的公开大厅对局（真人正数、机器人负数）。router factory 注入 create_app 内现有 viewer 授权与 `session_state_for_read`；私有AI、其他用户的单人对局和匿名访问不可暴露。返回中央 session_id、public_lobby:true、真实 state，以及沿用 active/multiplayer 权威来源的双方姓名/段位。盒子核对中央 ID 与公开标记，明确区分401/404/503。
- [x] 响应为真实 state，不下发云凭证。没有任何 POST/动作转发。观战不绑定 vision、LED、engine、实体盘或主计时回调，角色永远只读。
- [x] 每2秒串行读取快照；卸载/换房间/切账号取消或忽略旧请求；错误说当前不是实时态并给重试，404保留已取得终局或明确已结束/不存在。后台隐藏时停止轮询，恢复重新同步。
- [x] 用现有 state.stones（坐标约定按现有Board转换）画盘；若展示时钟，必须复用现有服务端权威时钟组件，不能刷新重置本地倒计时。不能可靠显示则不新增时钟。
- [x] 测试匿名/私有局阻断、已登录大厅读取、盒子云/本地ID及账号generation边界、旧响应和退出无动作/无物理绑定。不要扩张为通用WS代理或历史重建系统。

## 验证与审核

- [x] 聚焦 pytest：既有 `test_lobby_boundaries.py`（31项已通过）与新观战授权测试；Vitest：受影响的4个页面/组件测试。
- [x] 真实 React 预览 Galaxy 三页1440×900；同尺寸参考/实现/并排/差异四图，核对页头、边界、字体、动作。只增加一张手机自由页确认可滚动和行动可达。
- [x] CDP 抽查中文标题/按钮/元数据，以及Galaxy数字和英文的实际字体，不仅看 font-family 字符串。
- [x] 1024×600 下比较 RK3562 大厅实图与字体修复预览；布局保持。观战页与现有星阵骨架比较并验证读盘与回大厅。
- [x] 先核对本计划的规格，再由独立 GPT-6-astra max 做代码和视觉审核，修复实际阻塞项。引用最新用户裁定，旧 REVIEW 的 kiosk 重排结论已失效。
- [x] `git diff --check` 与前端生产构建；停止无关全量回归。完成后向用户报告真实预览、测试和审核状态。

## 完成记录

2026-10-09：两个独立实现任务及 kiosk 观战任务完成；计划由 GPT-6-astra max 两轮审核通过，最终 Galaxy 与 kiosk 规格、代码、真实视觉均 Approved。最终受影响前端 111 项、后端 48 项通过，普通及严格盒子构建通过。截图与审核见 `docs/design/play-consistency-2026-10-09/`。尚未提交、推送、合并或部署。
