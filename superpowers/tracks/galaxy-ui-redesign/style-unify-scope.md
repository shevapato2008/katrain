# galaxy 全站风格统一 · 范围与决策（2026-08-20，Fan 已确认）

本文是本轮工作的**范围裁定**，不是设计规格也不是实施计划。
- 设计权威：`docs/superpowers/specs/2026-08-06-galaxy-board-template-ladder-design.md`（用户已确认）
- 已批准的视觉样板：`superpowers/tracks/galaxy-ui-redesign/visual/approved/live-template/`（12 视口）
- **作废文档**：本目录 `design.md`（历史审计，部分规则已被覆盖）与 `plan.md`（历史计划，明写「待重写」）。
  两者只可当背景读，**不得据以实现**；冲突一律以上面的 spec 为准。

## 0. 本轮的前提：样板已经跑通

`docs/superpowers/plans/2026-08-06-galaxy-shared-foundation-live-template.md` 84/84 步已完成并合入
develop。共享基础（`GalaxyTopBar` / `MainLayout` / `ModulePlate` / `ContentPageHeader` /
`GalaxyBottomNav` / `useGalaxySidebar` / `BoardPageShell` / galaxy 字体分片）**已经存在，不要重建**。

已迁移到模板的页面（照抄对象，不要改它们）：
- `src/galaxy/pages/live/LiveMatchPage.tsx` —— 棋盘页样板，`BoardPageShell` + `ModulePlate`
- `src/galaxy/pages/GamePage.tsx` —— 升降级对弈，同上
- `src/galaxy/pages/AiSetupPage.tsx` —— 内容页样板，`ContentPageHeader`

本轮就是 spec §2.4 里写的那句「其他页面在后续全站风格统一阶段迁移」。

## 1. 决策一 · 棋盘页范围：6 个，全做

| 页面 | 行数 | spec §1.2 点名 |
|---|---:|---|
| `src/galaxy/pages/ResearchPage.tsx` 研究 | 693 | 是 |
| `src/galaxy/pages/TsumegoProblemPage.tsx` 死活题 | 458 | 是 |
| `src/galaxy/pages/report/ReportDetailPage.tsx` 复盘 | 261 | 是 |
| `src/galaxy/pages/KifuLibraryPage.tsx` 棋谱库 | 516 | 是 |
| `src/galaxy/pages/GameRoomPage.tsx` 人人对弈 | 348 | **否 —— 本轮追加** |
| `src/galaxy/pages/tutorials/TutorialFigurePage.tsx` 教程图 | 507 | **否 —— 本轮追加** |

后两个 spec 没点名，Fan 在 2026-08-20 明确追加：「全站风格统一」要名副其实，不留孤岛。
注意这两个是六个里最难的：`TutorialFigurePage` 带棋盘编辑工具条（`useBoardEditor` +
`BoardEditToolbar`），`GameRoomPage` 带实时对局状态。**排在最后做**，前四个把模式跑顺再碰。

⚠️ `TutorialFigurePage` 与 tutorial-module 赛道有重叠风险；动它之前先 `git log --oneline -10 --
katrain/web/ui/src/galaxy/pages/tutorials/` 看有没有并行改动，有就先说，别闷头改。

## 2. 决策二 · 内容页范围：12 个，只换页头

挂 `ContentPageHeader`，**不动承重结构**：
`Dashboard.tsx`、`PlayMenu.tsx`、`HvHLobbyPage.tsx`、`live/LivePage.tsx`、`report/ReportsPage.tsx`、
`TsumegoCategoriesPage.tsx`、`TsumegoLevelsPage.tsx`、`TsumegoListPage.tsx`、`TsumegoUnitsPage.tsx`、
`tutorials/TutorialLandingPage.tsx`、`tutorials/TutorialBooksPage.tsx`、`tutorials/TutorialBookDetailPage.tsx`

按 spec §2.4：单行布局，**左上角返回箭头图标键 + 标题**；上一级简称不上屏、只进无障碍名；根级页面（Dashboard）只留标题。

> **2026-08-22 修订**：返回按钮改为**左上角箭头图标键**，上一级简称不上屏、只进无障碍名。
> 依据 Fan 当日裁定「返回按钮都放到右边栏的左上角吧。不止限于复盘页面」并授权改文档。
> 权威条款见规范 §2.4；实现在 `galaxy/components/layout/ModulePlate.tsx` 一处。
英文 eyebrow、面包屑、长副标题、状态说明、chip **一律不进页头**，需要保留的下沉到正文首个业务区。

## 3. 决策三 · 视觉与承重关卡的粒度

Fan 2026-08-20 裁定，**收敛于直播样板那轮的 12 视口全量**：

- **棋盘页**：每页 3 档视口 —— `1440x900`（标准）、`1024x768`（窄，左栏默认收起）、`430x880`（竖屏）。
  每档四图齐全：参考图 / 实现截图 / 并排图 / 叠加图+差异图。参考图用
  `visual/approved/live-template/` 对应视口那张作为**模板一致性**参照，不是像素基线。
- **内容页**：12 个页面只换页头、不改承重链，合成**一张对比板**一次性确认，不逐页取图。
- **承重实测（不可收敛，逐个棋盘页做）**：每个棋盘页按用户级 CLAUDE.md 在**真浏览器**目标视口下量，
  **量之前先把数据造到会溢出**。判据先写死关系式再读数，具体像素只记录不作判据。
  jsdom 对布局事实无权作证 —— 断言对象是浏览器算出的布局结论的测试，不许用 jsdom 写。
  参照清单：`superpowers/tracks/galaxy-ui-redesign/s0-loadbearing-checklist.md`（它量的是 S0 的链，
  本轮要按每页自己的链重写关系式，**不要照抄条目**）。

## 4. 不在本轮范围

- 不重新设计视觉方向。08-06 的方向已获用户批准，本轮是**搬运**不是**重画**。
- 不动 `src/kiosk/**`（另一套设备约束）。
- 不实现 spec §5.3 那两个升降级契约缺口（`counting_eligibility` / settlements 查询端点）。
- 不动棋盘绘制资产（`board.png`、棋子、坐标、最后一手标记）。
- 不改后端契约。本轮是纯表现层迁移；任何需要改 API 的发现，记下来问，不要顺手改。

## 5. 硬闸

- `npm run build` 与 `npm run build:kiosk-2d` **都要绿**。共享领地（`src/components/`、`src/hooks/`、
  `src/theme.ts` 等）被 kiosk 共用，改一处两边都受影响。
- kiosk dist 体积基线**必须是同一 commit 上现跑的一次构建**，不能拿磁盘上现成的 dist 当基线。
- `npx tsc --noEmit` **是空的**（根 tsconfig 是 `files: []` + references，命令行 `--noEmit` 不跟
  references）。要类型检查用 `npx tsc -b`。
- 生产代码里不留模拟业务数据；取图用真实后端真实数据，不用 fixture 顶替。
