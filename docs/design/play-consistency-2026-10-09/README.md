# 对局页面统一设计

2026-10-09，Galaxy 已获用户视觉确认。kiosk 曾撤回自由/升降级重排，随后用户明确要求在线大厅更接近现有星阵 kiosk 大厅；当前主文件 `index.html` 已加入这一新版大厅设计。字体和品牌图使用仓库现有资产。

## 设计范围

主表面为操作型页面：选择玩法、配置条件、邀请棋友，再进入对局。

- Galaxy：对局入口、自由对弈、升降级对弈、对战大厅统一页头和内容舞台。
- kiosk：本次仅重新设计在线大厅，参考仓库现有星阵大厅；自由/升降级页面不在此次修订范围内。
- Galaxy 界面正文、标题、按钮、数字与英文统一霞鹜文楷；kiosk 补齐现有共享栈的中文楷体，品牌沿用既有外壳。
- 返回对局：左上角固定 44×44 箭头图标键，三个子模块位置、图标、命中范围一致。图标沿用现有 ArrowBack 轮廓。均返回对应平台的对局入口。
- Galaxy 内容最大宽度 1440，页头间距 24，连续舞台圆角 12，分栏边界和主按钮一致。小屏按正文再行动区的顺序堆叠。
- 大厅快速匹配仅面向已定级用户，按同段位匹配；直接邀请不限定级和段位，仍要求对方空闲。所有大厅对局不计升降段位。
- 升降级页保持服务端分配对手、固定规则、净胜分和正式预约门禁；设计不改变计分或预约契约。
- 自由对弈保留现有规则、执子、让子、贴目、对手和计时设置。不同 AI 策略的详细配置在落地时沿用现有控件。

## UI/UX Pro Max 优化

采用现有设计系统；本地检索的 Navigation / Back Button、Typography / Font Size Scale 和 Font Loading 规则，落实为可预测返回、统一字号层级和含楷体的完整字体栈。React 指引落实为真正的按钮、具名表单和弹窗焦点管理。无新增产品功能或额外视觉主题。

## 当前代码修复

- `LobbyPage.css` 的 serif、sans、mono 全部改用共享 `--font-*`，每条栈都有 SmartBox Kai。
- 服务端直接邀请机器人移除定级/同段位门禁，保留机器人在线、空闲、席位预留与创建失败回滚。快速匹配门禁保持。
- Galaxy 已按确认稿实现共享页头、舞台与完整楷体栈；kiosk 大厅保持原布局，并补上独立只读观战入口。设计样例不进入生产业务数据。

## 前一轮代码完成与验收

- kiosk 点击他人棋局进入 `/kiosk/play/pvp/watch/:sessionId`；自己的棋局继续返回原对局页面。观战复用现有星阵 474px 棋盘骨架，每 2 秒串行同步中央只读盘面，不建立本地实体盘对局。
- Galaxy 与 kiosk 未定级均可直接邀请任意段位的空闲真人或机器人；快速匹配仍要求完成定级，并按同段位匹配。
- 当前预览为真实 React 页面配合浏览器拦截的验收数据；已部署 RK3562 的大厅实图仅作为布局参考。本轮代码尚未推送、集成或部署。
- 2026-10-09 最终聚焦检查：6 个受影响前端测试文件 **111/111**；观战与既有大厅边界后端 **48/48**；普通前端构建及 `build:smartbox-kiosk-2d` 严格盒子构建通过，`git diff --check` 通过。
- 独立 GPT-6-astra max 先规格核对、再代码及同尺寸真实视觉审核，Galaxy 与 kiosk 均 **Approved**。详见 [GALAXY-REVIEW.md](GALAXY-REVIEW.md)、[KIOSK-REVIEW.md](KIOSK-REVIEW.md)。

### 运行截图

- [kiosk 原布局与实现并排](kiosk-hall-side-by-side.png)、[新增大厅观战](kiosk-spectator-implementation.png)、[星阵观战参考与实现并排](kiosk-spectator-side-by-side.png)。
- Galaxy [自由对弈](galaxy-free-implementation.png)、[升降级对弈](galaxy-rated-implementation.png)、[对战大厅](galaxy-hall-implementation.png)；同目录包含各自 reference、side-by-side、overlay、diff 及手机预览。
- `runtime-checks.json`、`kiosk-runtime-checks.json` 记录实际 CDP 字形、几何与入口/返回行为；不是仅检查 CSS 字体名称。

## 预览与检查

顶部选择器切换平台、页面和段位。页面内返回、快速匹配指引、邀请弹窗、筛选和执子可操作。真实开局与观战不在此静态稿执行。`?capture=1&view=hall&surface=galaxy` 隐藏设计工具条；`view=free/rated/home` 切换页面。

目标检查：Galaxy 1440×900 与 2048×1152，移动端 430×880，kiosk 1024×600。审核覆盖页头一致性、字体实际渲染、空间与动作层级、未定级邀请和匹配的不同门禁。发布前不把设计样例带入生产。

## 用户补充裁定

- 三模块排版统一只针对 Galaxy。
- kiosk 大厅点别人对局应进入只读观战，参考已有星阵观战骨架。
- 两个平台未定级可直接邀请任意段位的空闲棋友，只有快速匹配先要求定级。
- `index-v1-superseded.html` 和早先 `REVIEW.md` 关于 kiosk 重排的结论已作废；不得据此修改设备布局。

## 最新修订：kiosk 在线大厅 v3

用户在上述代码验收后重新指定在线大厅的视觉方向：尽量接近现有星阵 kiosk 大厅，补上木色棋盘、观战人数和正确黑白执子颜色。这是新的大厅设计稿，之前“不重排大厅”的范围限制由本次明确要求更新；自由/升降级仍不重排。

直接预览：`index.html?surface=kiosk&view=hall`。`index-v2-before-star-hall.html` 保留本次修订前的文档。Galaxy 的自由页在 1440×900 下与修订前截图逐像素一致。

- 主表面为浏览并选择棋局/棋友。采用星阵的页头、68px 操作卡、标签列表与两列 90px 棋局卡；大厅框同样为 `x=16, y=248, width=992, height=330`（1024×600）。
- 保留快速匹配、直接邀请、观战和返回入口。点击“邀请棋友”切到名单；未定级邀请正常、快速匹配显示定级指引；自己不可邀请、忙碌棋友不可邀请。只有已定级时“同段位”筛选可用。
- 棋手头像角标与卡片中间的小棋盘均使用独立黑/白样式：黑子接近纯黑，白子为白色实心。小棋盘沿用星阵的木色识别图标，不伪装成实时盘面，也不因此逐局读取棋盘快照。
- 观战人数位于卡片右上角，使用眼睛图标加“人观战”，不把星阵“人在房间”人数误当观众。静态稿数据都是明确标注的设计示例；产品落地读取服务端 `spectator_count`，未取得有效数值时显示“观战人数未返回”，不得用示例值或默认 0 补齐。目前该字段由 socket 数推导，不能计入新的 HTTP 轮询观众；准确人数需在落地时明确观众统计来源，不能将轮询请求数当人数。
- UI/UX Pro Max 聚焦优化：所有主触控目标至少 44px，相邻按钮间距 8px；中文使用完整霞鹜文楷栈；黑白同时有文字执子标签；标签支持方向键/Home/End，弹窗支持 Escape 和焦点循环。
- 本次仅修改 HTML 设计文档，不改产品前后端或部署设备。页面内样例限于设计稿，后续产品不能带入这些棋友、棋局或人数。

验收截图：`kiosk-hall-v3-games.png`、`kiosk-hall-v3-players.png`、定级/邀请弹窗截图，以及同尺寸星阵参考 `kiosk-golaxy-hall-reference.png` 与 v3 的 side-by-side/overlay/diff。交互、实际字体、无溢出和浏览器错误记录见 `kiosk-hall-v3-checks.json`。本次视觉审核使用独立的 v3 报告，前一轮 `KIOSK-REVIEW.md` 不代表本稿批准。

claude-design 自查：0/10 通用模板问题；主表面是浏览棋局，操作卡服务于已有匹配/邀请功能，沿用产品配色、字体与密度。独立 **GPT-6-astra max 视觉与设计逻辑审核：Approved**，无 must-fix；详见 [KIOSK-HALL-V3-REVIEW.md](KIOSK-HALL-V3-REVIEW.md)。等待用户视觉确认后再落地产品。


## kiosk 在线大厅 v3 落地完成（2026-10-10）

用户已确认 v3 设计并授权开发。当前 `feature/admin-console` 已获取并合入最新 `develop`（两者基线均 `9f28d43d`，没有新冲突）；本轮实现与此前已批准的 Galaxy 排版、直接邀请、kiosk 只读观战改动一起保留。

- 实际 React 大厅已采用两列棋局卡、木色棋盘识别图标、真实黑白执子角标与棋友标签名单。1024×600 下大厅框 `16/248/992/330`、首卡 `24/304/484/90` 与批准稿一致。中文 CDP 字形为 LXGW WenKai，无中文回退；现有外壳与 Latin 栈保留。
- 原匹配、跨段位/未定级邀请、自身对局返回与他人只读观战已经集成。邀请先确认再发送；标签、弹窗键盘与焦点可操作。账号变更取消旧名单请求，告警缩短列表，目标画布无溢出。
- 中央观战人数按认证用户去重合并 WS/HTTP，排除两名棋手，机器人对局无需假定存在两个棋手 socket。盒子转发中央数据，不以本地镜像计算。人数变化立即推送；HTTP 观众离开/隐藏停止心跳后约 10 秒到期并通知房间，大厅在下次 10 秒列表刷新反映。未知人数明确显示“观战人数未返回”。旧原始 socket 字段保留，新增权威人数兼容传递。
- 小棋盘仅为识别图标，不逐房拉取盘面，不调用引擎，不使用生产假人数/假棋友。观察身份是会话内临时状态，无数据库/新后台服务。

**统一执行验证：** 9 个相关前端文件 152/152；后端 presence/spectator/lobby/chat-WS 99/99；普通构建、`build:smartbox-kiosk-2d` 与 `git diff --check` 均通过。严格盒子构建通过 SSO 与 kiosk 模块边界检查。后端子任务另覆盖已有 strict-box/广播/会话关闭测试。本轮没有进行推送、合并发布或服务器/RK3562 部署。

**独立 GPT-6-astra max：** 计划最多两轮（第二轮 Approved）；随后规格审核 Approved，再代码质量与真实视觉审核 Approved，无 Critical/Important。见 [计划审核](KIOSK-HALL-IMPLEMENTATION-PLAN-REVIEW.md)、[规格审核](KIOSK-HALL-V3-SPEC-REVIEW.md)、[代码与视觉审核](KIOSK-HALL-V3-CODE-VISUAL-REVIEW.md)。既有应用抗锯齿与静态稿的差别如实记为非阻塞渲染差异，未宣称逐像素完全相同。

**真实实现预览：** [棋局列表](kiosk-hall-v3-games-implementation.png)、[棋友列表](kiosk-hall-v3-players-implementation.png)、[邀请确认](kiosk-hall-v3-invite-implementation.png)、[定级指引](kiosk-hall-v3-placement-implementation.png)、[错误状态](kiosk-hall-v3-error-implementation.png)。浏览器 fixture 仅存在验收脚本/测试中；[运行检查](kiosk-hall-v3-runtime-checks.json)记录实际字体、几何、邀请、观战返回与无溢出。同目录有 games/players 的 implementation-side-by-side、overlay、diff，对照已批准稿。
