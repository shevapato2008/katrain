# Report card charging progress Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 用户确认的三条：Galaxy 进度改为 Kiosk 充电样式；卡片黑白棋手分列两侧、中间结果/手数；两端只有实际运行报告占用右侧进度区，其余卡片占满宽度。

**Architecture:** 仅改现有 React 展示组件与 CSS。复用 ReportProgressColumn、presentReportTier 和既有棋谱卡排版，不修改任务、计费、轮询、进度计算、服务器或数据库。与已通过 Astra Max 的报告失败引导一并发布。

**Tech Stack:** React/TypeScript、MUI、既有 Kiosk CSS、Vitest、真实浏览器预览、现有云端/RK 发布工具。

## Chunk 1: 冻结视觉与状态契约

用户已逐条确认并授权按传统流程开发部署。ui-ux-pro-max 采用现有绿色充电填充、字体、间距、黑白棋子和棋谱卡设计，不建立新主题。

- Galaxy 两行进度均采用 Kiosk 的绿色横向填充、百分比、运行扫光与 reduced-motion。保持原列宽（Galaxy126px、Kiosk120px），不使用圆环或SVG。
- 只有 `presentReportTier(...).status === 'running'` 的档位显示进度。普通/高级独立；无运行档位时整个进度组件返回 null，外部行切换为单列1fr，不留 gap/空白。pending、missing、completed、failed均不展示右侧进度；pending必须在卡片文字区明确显示既有report:queuing（排队中），不混称正在分析；失败及查看报告继续现有卡片状态和菜单。不依赖选择卡片或仅打开菜单，后台仍在运行的任务也显示，避免刷新后丢失进度。
- 单档运行只显示该档；双档运行两档显示。运行但100%仍显示，直到任务真实变为completed后收起。
- Galaxy 参考现有 KifuLibraryPage：标题/日期在上，黑棋手左、白棋手右，中间结果和手数；不再把两位棋手上下堆叠。保留来源/星阵、段位、选中态和键盘选择。Kiosk已有RecordMatchLine左右布局继续复用，中间补充手数（若已有则避免重复）。不改棋谱库本身、不新增操作按钮。
- 列表卡片整体高度与原版保持接近（Galaxy104px、Kiosk74px）；长名字截断但完整title可读，运行列不导致页面横向溢出。

## Chunk 2: 两个边界明确的实施任务

### Task A: 共享进度显示（独占共享3文件）
Files: `src/features/report/ReportProgressColumn.tsx`、`reportProgress.css`、`ReportProgressColumn.test.tsx`（均相对katrain/web/ui）。
- [x] 修改已有聚焦用例：两端仅running可见、无运行返回空、单/双档、100%运行仍可见、填充百分比与aria一致、无圆环；运行一次红测。
- [x] 用map→filter(status===running)，无运行return null。两端都渲染现有report-tier-fill与百分比，删除圆环结构及专属CSS，公共行复用现有Kiosk样式。列auto行高34px/gap6px，单档不留空行。
- [x] 绿测并只提交上述文件，不改卡片或plan。

### Task B: 两端卡片与空间回收（独占页面/卡片文件）
Files: `src/galaxy/components/report/ReportGameCard.tsx`及test、`src/kiosk/pages/ReportsPage.tsx`及test、`src/kiosk/pages/personalGamesReviewed.css`，如需中间手数可最小扩展既有 `src/kiosk/components/records/RecordMatchLine.tsx` 与 `recordMatchLine.css` 的可选detail展示，仅历史卡传入，不改棋谱库。必要时只调整现有页面测试中旧“全档总显示”的断言。
- [x] 先加聚焦用例：有running→data-has-running-report=true，单独进度列；仅完成/排队/失败/未开始→false、无预留列。运行红测。
- [x] 从现有presentReportTier判断running，Galaxy grid用`minmax(0,1fr) 126px`或`minmax(0,1fr)`；Kiosk行加相同data属性，CSS用1fr与`minmax(0,1fr) 120px`切换，组件内部负责档位过滤。
- [x] Galaxy棋手改左右同排、中间结果+手数，采用既有KifuLibraryPage的MUI布局，保留title/rank/键盘选择/活动手数元数据；Kiosk沿用RecordMatchLine。不要引入跨主题共享组件或改业务hook。
- [x] 定向卡片/两个报告页测试通过，只提交本人文件。与Task A无共享编辑。

## Chunk 3: 验证、审核和发布

- [x] 计划独立Astra Max审核一轮已完成，唯一必要修订是pending卡片文字明确“排队中”，主代理已纳入后实施；本轮局部展示任务不扩张反复设计审核。
- [x] 主代理规格检查后独立Astra Max代码审核至通过，只覆盖新展示增量，已审核弹窗无需重复审核。
- [x] 一次真实浏览器预览：Kiosk1024×600、Galaxy与原截图同尺寸1920×1080CSS像素（截图为2x）；比较卡片结构、空间、进度可读性和既有弹窗。聚焦测试和两端构建，避免全量回归矩阵。Fixture放ignored output并在发布前删除。
- [ ] fetch最新develop→mergefeature→定向复验→commit/pushfeature；合入develop并push；隔离parent工作树更新smartbox-software/vendor/katrain并pushmain，保留无关WIP。
- [ ] 使用server-deploy技能选择性发布前端到home-ubuntu及ucloud-v100，保留运行配置/网络/凭据，不重启无关数据库/GPU/Cron；核对实际Galaxy报告页。
- [ ] 无其它部署进程且RK无活动对局/标定时，用标准app事务部署rk3562-local，恢复原页面并核对版本和实际页面。空间不足仅清用户已授权的过期发布产物，保留用户数据与活动资源。报告发布commit与验收边界。
