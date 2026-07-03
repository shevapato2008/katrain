# 弈航 Kiosk UI 重设计 — Plan（活记录）

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

## 4. 决策记录

| 决策 | 内容 | 时间 |
|---|---|---|
| 方向 | ③ 棋盘台 Board Console（底部 Dock，拇指可达；左侧常驻智能棋盘台，突出硬件形态） | 2026-07-04 |
| 导航语义 | **Dock 当前项决定右侧内容**；左侧棋盘台在对弈/对局相关场景常驻 | 2026-07-04 |
| 字体 | 英文 Anthropic 风格：Newsreader（衬线，品牌/问候）+ Hanken Grotesk（无衬线，UI）。中文暂系统回退。真身 Styrene/衬线为商用授权，用开源替身，拿到真身再换 | 2026-07-04 |
| 屏幕基准 | 1024×600 横屏，主屏无滚动；触控靶 Dock≈120×70、主卡≥56 高 | 2026-07-04 |
| 仓库存法 | 本地 artifact 用 `@import ./fonts.css` 共享一份字体，避免存多份 700KB | 2026-07-04 |

## 5. 分阶段任务

### Phase 1 — 对弈 hub 完整细节（**出稿完成，待用户确认**）
把已定稿的对弈 hub 补齐到“可实现”的颗粒度。产出：`artifacts/play-hub-states.html`（在线 https://claude.ai/code/artifact/5e13c101-0942-46dc-ac65-d184793d08b6）。
- [x] **全状态**：主卡/次卡/chip/Dock/继续条 的 默认 · 悬停 · 按压 · 聚焦 · 禁用。
- [x] **数据态**：继续上一局 有/无；等级列表 加载中/失败/空；创建对局中。
- [x] **触控反馈**：按压缩放/时长/缓动/聚焦环/触控靶 数值表（spec §5）。
- [x] **竖屏变体**：600×1024（棋盘台压顶部横卡、hub 单列、Dock 底部不变）。
- [x] `design.md` 增补「对弈 hub 交互规范」小节（§4.5）。
- [ ] **待用户确认** → 确认后本阶段关闭，进 Phase 2。

### Phase 2 — 逐模块出稿
按 `design.md` §5 依次：死活 → 研究 → 棋谱 → 摆谱 → 直播 → 教程 → 设置。每模块一版 artifact + 规范小节，用户逐个确认。
- [ ] 死活 [ ] 研究 [ ] 棋谱 [ ] 摆谱 [ ] 直播 [ ] 教程 [ ] 设置

### Phase 3 — 外壳 / 组件规范
- [ ] Header、Dock、智能棋盘台面板、token 表（颜色/字阶/间距/圆角/阴影）成文，供实现直接取用。
- [ ] 定「智能棋盘台」作用域（全局常驻 vs 仅对弈/对局相关）。

### Phase 4 — 实现落地（**另开分支**）
- [ ] 新建实现分支（非 `feature/kiosk-play-golaxy`）。
- [ ] 按 `design.md` §6 改造：`NavigationRail`→底部 Dock；`StatusBar`→Header + 棋盘台状态格；`KioskLayout` 横屏新布局；`PlayPage` 换皮为对弈 hub。
- [ ] 遵守 SBC 双构建契约：`npm run build` 与 `build:kiosk-2d` 双绿；kiosk 边界不引 three/galaxy/Board3D。
- [ ] 竖屏 `TopTabBar` 路径同步更新。
- [ ] 真机验证（7″ 屏，触控、可读性、比例）。

## 6. 待定 / 开放问题

1. 竖屏变体的最终排布（Phase 1 出初稿）。
2. 左侧智能棋盘台是否全模块常驻。
3. Anthropic 真身字体文件（拿到后替换 `fonts.css`）。
4. 遥控/键盘可达性（kiosk 是否有物理按键/遥控导航）。

## 7. 非目标 / 边界

- 本轮**只做设计**，不改运行代码（实现在 Phase 4 另分支）。
- 主界面优先，其它模块逐个推进，不一次铺开。
- 后端/引擎/对局逻辑不动。

## 8. 参考

- 设计规范：`design.md`
- Artifacts：`artifacts/d3-board-console.html`（选定）· `play-hub-states.html`（对弈 hub 规范）· `d1-ink-goban.html` · `d2-paper-launcher.html` · `fonts.css`
- 在线：③ https://claude.ai/code/artifact/a9ef18ea-6272-48a7-92ef-bafaa8447eea · 对弈 hub 规范 https://claude.ai/code/artifact/5e13c101-0942-46dc-ac65-d184793d08b6
- 现有代码：`katrain/web/ui/src/kiosk/components/layout/{KioskLayout,NavigationRail,StatusBar,navTabs,TopTabBar}.tsx`、`pages/PlayPage.tsx`
