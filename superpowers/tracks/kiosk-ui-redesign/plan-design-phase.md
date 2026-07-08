# 智星盒 StellaBox Kiosk UI 重设计 — Plan（活记录）

> 活记录：随进展更新。设计规范细节见同目录 `design.md`；本文件是**执行主线**（目标、状态、分阶段任务、决策、待办）。
> 分支：设计阶段落在 `feature/kiosk-play-golaxy`（仅文档/artifact）；**实现另开分支**（见 Phase 4）。
> 起始日期：2026-07-04。

## 1. 背景 / 为什么

kiosk 直接沿用网页外壳（`KioskLayout` → 72px 左 `NavigationRail`，图标 22 / 标签 11），在 **7″ 触摸屏**上左栏图标过小、与右侧大按钮**比例失衡**，整体“太丑”。目标：**先把主界面重做好看**，再逐模块推进；设计以 artifact 对比后定稿，视觉锁定再落地代码。

## 2. 目标 / 完成定义（DoD）

- 一套面向 **7″（1024×600 横屏基准）触控**的 kiosk 视觉系统：主屏一屏可见、大触控靶、有层次。
- 方向锁定 + 每个模块有定稿视觉（含状态/交互/竖屏）。
- 一份可据以实现的规范（tokens / 外壳组件 / 各模块内容），并映射到现有代码。
- 实现分支跑通、双构建绿、真机可用。

## 3. 现状（已完成）

- [x] 摸清现状外壳与内容来源（`KioskLayout` / `NavigationRail` / `StatusBar` / `PlayPage` / `navTabs`）。
- [x] 出 3 版对比 artifact（① 墨枰 / ② 素纸 / ③ 棋盘台），内嵌 Anthropic 风格开源替身字体（Hanken Grotesk + Newsreader）。
- [x] **选定 ③ 棋盘台 Board Console**（底部 Dock + 常驻智能棋盘台）。
- [x] 修正 ③：**Dock 选中项驱动内容**；「对弈」→ 对弈 hub（人机/人人），非主页仪表盘。
- [x] 写 `design.md`（设计系统 + 内容映射 + 落地映射）。
- [x] 建 `superpowers/tracks/kiosk-ui-redesign/`（design.md + plan.md + artifacts/）。
- [x] 出「对弈 hub 完整规范」artifact（`artifacts/play-hub-states.html`）— 交互五态 + 异步/数据态 + 竖屏 + 动效数值（待用户确认，见 Phase 1）。
- [x] **对弈链路纵向切透**（用户定：先切透一条链路）：自由对弈设置页 + 对局中 GamePage（`play-flow-setup-game.html`）+ 对局中 4 态（`game-states.html`）。见 design.md §5.1。
- [x] **盘面/棋子对齐 galaxy**：木纹 `board.png` + 网格线 `rgba(0,0,0,.7)` + 星位 `rgba(0,0,0,.85)` + 棋子 `B_stone.png`/`W_stone.png`（`<symbol>`+`<use>` 精灵表）+ 对比色最后一手环；取值来自 `Board.tsx`/`boardUtils.ts`，Playwright 本地渲染已验证（design.md §4.6）。

## 4. 决策记录

| 决策 | 内容 | 时间 |
|---|---|---|
| 方向 | ③ 棋盘台 Board Console（底部 Dock，拇指可达；左侧常驻智能棋盘台，突出硬件形态） | 2026-07-04 |
| 导航语义 | **Dock 当前项决定右侧内容**；左侧棋盘台在对弈/对局相关场景常驻 | 2026-07-04 |
| 字体 | 英文 Anthropic 风格：Newsreader（衬线，品牌/问候）+ Hanken Grotesk（无衬线，UI）。中文暂系统回退。真身 Styrene/衬线为商用授权，用开源替身，拿到真身再换 | 2026-07-04 |
| 屏幕基准 | 1024×600 横屏，主屏无滚动；触控靶 Dock≈120×70、主卡≥56 高 | 2026-07-04 |
| 仓库存法 | 本地 artifact 用 `@import ./fonts.css` 共享一份字体，避免存多份 700KB | 2026-07-04 |
| 品牌改名 | **弈航 / Yìháng → 智星盒 / StellaBox**；artifact+文档已改，代码级改名单独立项（design.md §7.6） | 2026-07-06 |
| Dock 图标 | 与 galaxy 一致，用 `@mui/icons-material`（映射见 design.md §4.4）；navTabs 两处待对齐 | 2026-07-06 |
| 跨平台作用域 | **跨平台对弈对 人机 与 人人 都开放**（前端本期先改；后端编排逻辑后续） | 2026-07-06 |
| 按钮等大 | 对弈 hub 六按钮统一等大网格；自由对弈仅以 jade 底色标主操作，不靠尺寸区分 | 2026-07-06 |
| 卡片图标 | hub 按钮图标对齐 galaxy `PlayMenu`（自由=SmartToy/升降级=SportsEsports/本地=Groups/在线=Public/跨平台=Hub），见 design.md §4.4 | 2026-07-06 |
| 品牌 logo | kiosk 复用 galaxy 既有设计 logo（`katrain/img/logo-white.png`），不用占位标记 | 2026-07-06 |
| 对弈是多页 | 对弈非单页；**纵向先切透一条链路**（hub→设置→对局中+4 态），建立骨架，其余模式复用换字段 | 2026-07-06 |
| 盘面对齐 galaxy | 所有盘面复刻 galaxy `Board.tsx`：`board.png` 木纹 + 线/星取值 + `B/W_stone.png` 棋子 + 对比色最后一手环（非 jade 环）。mockup 用 `<symbol>`+`<use>` 精灵表内联 base64 一次 | 2026-07-06 |
| 物理落子提示 | 对局中 amber 条「AI 已落子 R16 · 请在实体棋盘摆放白子」为 kiosk 物理对弈核心（对齐 kiosk-physical-play track） | 2026-07-06 |
| **仅横屏 · 放弃竖屏** | kiosk 只做 **1024×600 横屏**；**竖屏（600×1024）彻底不做**。已建的 hub 竖屏规范（play-hub-states §4）保留为历史参考，不再新增/落地 | 2026-07-06 |

## 5. 分阶段任务

### Phase 1 — 对弈 hub 完整细节（**出稿完成，待用户确认**）
把已定稿的对弈 hub 补齐到“可实现”的颗粒度。产出：`artifacts/play-hub-states.html`（在线 https://claude.ai/code/artifact/5e13c101-0942-46dc-ac65-d184793d08b6）。
- [x] **全状态**：主卡/次卡/chip/Dock/继续条 的 默认 · 悬停 · 按压 · 聚焦 · 禁用。
- [x] **数据态**：继续上一局 有/无；等级列表 加载中/失败/空；创建对局中。
- [x] **触控反馈**：按压缩放/时长/缓动/聚焦环/触控靶 数值表（spec §5）。
- [x] **竖屏变体**：600×1024（棋盘台压顶部横卡、hub 单列、Dock 底部不变）。
- [x] `design.md` 增补「对弈 hub 交互规范」小节（§4.5）。
- [x] **2026-07-06 用户三项修正**：① Dock 图标对齐 galaxy MUI；② 跨平台加入人机对弈（人机+人人都有）；③ 品牌改名 智星盒/StellaBox。两份 artifact + 本 track 文档已同步。
- [ ] **待用户确认（含上述三项）** → 确认后本阶段关闭，进 Phase 2。后端跨平台编排 + 代码级品牌改名转 Phase 4/独立任务。

### Phase 1b — 对弈链路纵向切透（**出稿完成，待用户确认**）
用户定「纵向先切透一条链路」：自由对弈 hub → 设置 → 对局中，建立设置页/对局页骨架与模式，其余模式复用。见 design.md §5.1。产出：
- [x] **自由对弈设置页**（`play-flow-setup-game.html` 左屏）：左棋盘台预览 + 右表单（棋盘/规则/我执/AI 策略/棋力/让子/贴目/用时 → 开始对弈 CTA）。字段取自 `AiSetupPage.tsx`。
- [x] **对局中 GamePage**（`play-flow-setup-game.html` 右屏）：顶栏 + 大盘 + 右栏(玩家卡/时钟/可视 toggle/操作) + amber 物理落子提示条。
- [x] **对局中 4 态**（`game-states.html`）：A AI思考中 · B 需校准挡屏（无 LED，对齐外框）· C 终局数子（地盘+死子红叉+结果卡）· D 认输确认。
- [x] **盘面/棋子对齐 galaxy**（§4.6）：3 份 board artifact 全部换 `board.png` 木纹 + `B/W_stone.png` 棋子 + 对比色最后一手环；Playwright 本地渲染验证黑/白两色 + 两种环。
- [x] `design.md` 增补 §4.6（盘面渲染）+ §5.1（对弈页面流）。
- [x] **`play-hub-states` 全面同步 d3 体系**：logo img / 等大 `.opt` 网格（弃 `.card.hero`+`.chip`）/ galaxy MUI 图标（SmartToy·SportsEsports·Hub·Groups·Public）/ 木纹棋盘棋子。§1~§4 全改，Playwright 渲染核对。至此四份对弈 artifact 组件体系统一。
- [x] Phase 1b 出稿完成，用户确认 → **直接进 Phase 2**（2026-07-06，用户定：竖屏不做，跳过竖屏变体）。
- [ ] **交界**：设置页开放贴目/规则/让子 = `tracks/kiosk-play-golaxy/` 「补全自由对弈设置面板」计划的前端落点；实现期对齐。

### Phase 2 — 逐模块出稿
按 `design.md` §5 依次：死活 → 研究 → 棋谱 → 摆谱 → 直播 → 教程 → 设置。每模块一版 artifact + 规范小节，用户逐个确认。

**死活（🟡 进行中）** —— 关键：kiosk 死活**已全量建成**（6 路由 + 共用解题引擎），本模块=视觉换皮，非新功能。IA=5 级下钻 + 解题页（design.md §5.2）。
- [x] 探明真实模块（galaxy + kiosk + 共用引擎 + 数据模型 + 图标/文案），Explore agent 出结构图。
- [x] **锚点两屏出稿**（`tsumego-flow.html`）：① 难度 hub（Dock「死活」选中，全宽 levels grid + 继续练习 + 进度点 + 上次高亮）；② 沉浸解题页（galaxy 盘面 + 级/题型 chip + 黑先 + hint + 用时/尝试/上次 + 悔棋/重置/提示/试下 + 上/下一题 + 实体棋盘标）。Playwright 渲染核对。
- [x] 决定 **智能棋盘台作用域**：仅有实时盘面场景显示（对弈 hub/对局、死活解题页）；浏览页全宽无 console（部分回答 §6 开放问题）。
- [x] 用户定 **死活双输入并存**（屏点 + 实体摆子，实体「非常重要」）。据 `kiosk-physical-tsumego` PRD/相位机出 **5 状态稿**（`tsumego-states.html`）：摆放黑棋(红灯)/做题中/应手(绿灯)/答错拿除(蓝灯)/答对(奖杯+白灯双闪)。LED 三通道 + 语音；**全程 MUI 图标无 emoji**。
- [x] 确立 **kiosk 全局禁用 emoji**（SBC 无 emoji 字体→豆腐块；design.md §4.2），庆祝用 `EmojiEvents` 奖杯，非 🎉；修掉锚点稿里的 ⚔️ chip。
- [ ] **待用户确认死活稿**（锚点两屏 + 5 状态）→ 再补：纯屏幕态（提示/不正确/试下）；浏览下钻 3 屏（题型/单元/列表 + MiniBoard 缩略）。

**研究（🟡 进行中）** —— 关键：kiosk 研究**当前仅占位表单**（`ResearchPage.tsx` + 「开始研究」跳通用 `GamePage`，**无真分析视图**）；完整复盘在 galaxy `ResearchPage`(693 行两级机)。本模块=**把 galaxy 研究下沉到 kiosk**，非纯换皮（design.md §5.3）。
- [x] 探明真实模块（Explore agent）：kiosk 占位 vs galaxy L1 编辑→L2 分析两级机；共用 `LiveBoard`/`Board.tsx`/`ResearchAnalysisPanel`/`quickAnalyze`+`analysisScan` 数据模型与 API。
- [x] **三屏出稿**（`research-flow.html`，在线 `28a2a9e2`）：① 编辑摆棋（Dock「研究」选中，居中盘 + 编辑工具 12 格 + 快速建议候选点 + 开始研究 CTA）；② AI 分析中（沉浸，烧瓶+旋转环+进度/ETA+取消）；③ 分析报告（沉浸，eval 色点盘 + 胜率条/目差 + AI 推荐表[实战手高亮] + 走势图 + 妙手/问题手 + 手数滑块导航 + 返回编辑）。Playwright 渲染核对，无 emoji。
- [x] 定 **研究只做 19 路**（同对弈；物理盘固定）；eval 色点沿用 galaxy `EVAL_COLORS`。
- [x] **研究子态出稿**（`research-states.html`，在线 `91ab54b8`）：摆子模式(摆黑 ghost)/删除模式(红叉)/领地叠加(ownership 暗亮格+目数)/分析失败(重试)/从棋谱库打开(modal→载入研究)。无 emoji（✕ 已换 SVG/叉）。
- [ ] **待用户确认研究稿**（三屏 + 5 子态）。落地注意 ③ 报告页需**新建**（现跳 `GamePage`），`Board.tsx` 共享地带双构建。
- [x] **对弈 GamePage 补 AI 走势图**（play-flow 右栏，重发布 `ddd9a8c7`；design.md §5.1②）——用户 2026-07-07 指出遗漏。

**棋谱（🟡 进行中）** —— 关键：棋谱**不是**个人云存档，是**只读赛事棋谱库**（`kifu_albums` 表；无本地/云端 tab、无上传删除、无缩略图、卡片不分用户）。kiosk `KifuPage`/galaxy `KifuLibraryPage` 同构：左列表(搜索+卡片+分页) + 右预览(LiveBoard+手数滑块+「在研究中打开」)。打开=建研究会话跳 `GamePage`（`kifu/:id` 现为占位）。图标 kiosk 现 `MenuBook`→应对齐 galaxy `LibraryBooks`。
- [x] Explore 探明真实模块（只读 kifu 库 + 两栏 + 研究交接 + 无缩略/无云端/无登录专属态）。
- [x] **出稿**（`kifu-flow.html`，在线 `b5cf5849`）：① 列表(搜索"三星杯"+5 卡+分页)+预览(盘+手数滑块 118/241+在研究中打开)；② 搜索空态+未选中占位。Dock「棋谱」lit。无 emoji。
- [ ] **待用户确认棋谱稿**。待补：预览加载 skeleton；分页跳转态。图标 `MenuBook`→`LibraryBooks` 实现期对齐。
**摆谱（✅ 出稿）** —— kiosk 独有 **LED 引导实体摆子+拍照采集**（非存局库，无 galaxy 版）。`baipu-flow.html`（在线 `a2adfad7`）4 屏：① 选谱(仅19路+导入+最近resume+kifu卡+预览) ② 引导摆子(下一手红/绿LED环+确认落子·拍照) ③ 拍照挡屏(请勿伸手) ④ 提子移除(蓝灯+已移除N子)。LED 黑红/白绿/提子蓝。无 emoji。待补：DriftBanner/采集失败/三确认弹窗/disabled态。
- [ ] **待用户确认摆谱稿**。
**直播（✅ 出稿）** —— 只读职业赛事观战（星阵/弈客/IGS 抓取，非视频/非用户观战/无弹幕），KataGo 解说。`live-flow.html`（在线 `fe9787a1`）2 屏：① 列表(左预览+PlaybackBar跟播+进入直播 · 右 热门/即将开始 tabs+直播中/历史 MatchCard 含来源徽章+胜率条) ② 观战(盘+AI标记 · MatchInfo+试下/形势/手数/AI+AI推荐表+走势+跟播)。轮询 30s/5s。无 emoji。待补：即将开始/结束/空态/PV浮层。
- [ ] **待用户确认直播稿**。
**教程（✅ 出稿）** —— 只读 4 级目录(分类→书目→章节树→学习页)，视频优先学习页(Option B 已实现)，镜像 galaxy 只读子集。`tutorial-flow.html`（在线 `02767307`）3 屏：① 分类卡网格 ② 书目+章节 accordion/小节树(图数+视频标) ③ 学习页(图解 SGFBoard+手数滑块+全盘/局部 · 视频播放器+说明+讲解音频)。Dock 教程=MenuBook。无 emoji/无进度追踪。待补：无视频 fallback/加载错误态。
- [ ] **待用户确认教程稿**。
**设置（✅ 出稿）** —— 单页设置 + 几何标定子页。`settings-flow.html`（在线 `c93e74c2`）2 屏：① 设置主页(实体棋盘状态+重新标定/屏幕方向仅横屏/死活自动下一题/**语言仅中英[去日韩]**/外部平台卡/**补账户+退出登录[kiosk 现无]**) ② 棋盘几何标定(双路画面+metrics+**手动触发不自动亮灯**)。主动修正 2 处+补 1 处。无 emoji。待补：标定进行中/失败诊断；语言账户接真实逻辑。

> **Phase 2 全 8 模块视觉稿完成（2026-07-07 通宵自主）**：对弈(+走势图修正)·死活·研究(+子态)·棋谱·摆谱·直播·教程·设置。全部未 push，等用户晨起视觉复核。逐模块「待补」子态见 design.md §5.x。

> 交界：物理各状态的**后端/编排实现**属另一 track `kiosk-physical-tsumego`（worktree `/Users/fan/Repositories/katrain-kiosk-physical-tsumego`，分支 `feature/kiosk-physical-tsumego`，**尚未开发完**）；本 track 只出视觉稿，实现期与其对齐相位机/LED/语音契约。

### Phase 3 — 外壳 / 组件规范
- [ ] Header、Dock、智能棋盘台面板、token 表（颜色/字阶/间距/圆角/阴影）成文，供实现直接取用。
- [ ] 定「智能棋盘台」作用域（全局常驻 vs 仅对弈/对局相关）。

### Phase 4 — 实现落地（**另开分支**）
- [ ] 新建实现分支（非 `feature/kiosk-play-golaxy`）。
- [ ] 按 `design.md` §6 改造：`NavigationRail`→底部 Dock；`StatusBar`→Header + 棋盘台状态格；`KioskLayout` 横屏新布局；`PlayPage` 换皮为对弈 hub。
- [ ] 遵守 SBC 双构建契约：`npm run build` 与 `build:kiosk-2d` 双绿；kiosk 边界不引 three/galaxy/Board3D。
- [ ] 真机验证（7″ 屏，触控、可读性、比例）。
- ~~竖屏 `TopTabBar` 路径同步更新~~ —— **不做**（仅横屏，2026-07-06）。

## 6. 待定 / 开放问题

1. 左侧智能棋盘台是否全模块常驻。
2. Anthropic 真身字体文件（拿到后替换 `fonts.css`）。
3. 遥控/键盘可达性（kiosk 是否有物理按键/遥控导航）。

## 7. 非目标 / 边界

- 本轮**只做设计**，不改运行代码（实现在 Phase 4 另分支）。
- 主界面优先，其它模块逐个推进，不一次铺开。
- 后端/引擎/对局逻辑不动。
- **竖屏（600×1024）不做** —— kiosk 仅横屏，竖屏变体一律不出稿、不落地（2026-07-06 定）。

## 8. 参考

- 设计规范：`design.md`
- Artifacts：`artifacts/d3-board-console.html`（选定）· `play-hub-states.html`（对弈 hub 规范）· `play-flow-setup-game.html`（设置→对局中）· `game-states.html`（对局 4 态）· `tsumego-flow.html`（死活 hub+解题页）· `tsumego-states.html`（死活物理 5 态）· `research-flow.html`（研究三屏）· `d1-ink-goban.html` · `d2-paper-launcher.html` · `fonts.css` · 盘面资源 `board.png`/`B_stone.png`/`W_stone.png`
- 在线：③ 棋盘台 https://claude.ai/code/artifact/a9ef18ea-6272-48a7-92ef-bafaa8447eea · 对弈 hub 规范 https://claude.ai/code/artifact/5e13c101-0942-46dc-ac65-d184793d08b6 · 对弈流程 https://claude.ai/code/artifact/ddd9a8c7-9aeb-426e-9194-191e655fb179 · 对局 4 态 https://claude.ai/code/artifact/6cb8e990-6900-4c9d-87d5-87e0610dee9c · 死活 hub+解题 https://claude.ai/code/artifact/916fad3d-a5de-4631-a74a-8dcb88910505 · 死活物理 5 态 https://claude.ai/code/artifact/fd0be9ae-a149-410e-a5eb-11c599f76dce · 研究三屏 https://claude.ai/code/artifact/28a2a9e2-b92f-44a0-a1a4-12e82e228826
- 构建脚本：`scratchpad/build_{d3,playhub,playflow,gamestates}.py`（相对引用 → base64 内联 + 石子 symbol 注入）
- 现有代码：`katrain/web/ui/src/kiosk/components/layout/{KioskLayout,NavigationRail,StatusBar,navTabs,TopTabBar}.tsx`、`pages/{PlayPage,AiSetupPage,GamePage}.tsx`、`components/game/GameControlPanel.tsx`、盘面 `components/Board.tsx` + `components/board/boardUtils.ts`
