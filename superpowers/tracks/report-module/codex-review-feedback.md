# KaTrain "复盘"模块设计评审反馈

## 总体评价

Gemini 的方案在产品方向上是对的：它抓住了“自动存谱、手动触发分析、异步进度、两级页面、报告详情复用现有分析视图”这些核心需求。`design.md` 作为高层说明，已经覆盖了大部分用户故事，能让人理解这个模块想做成什么。

但从“能不能在当前仓库里顺利落地”的角度看，这份 `plan.md` 还不能直接执行。最大问题不是思路完全错误，而是它对现有代码库的认知不够准确，导致数据库对象、后台任务模型、前端接入点、测试路径都和仓库现状有明显偏差。如果按当前 plan 直接开工，前 2 到 3 个任务就会和现有实现发生冲突。

我的结论是：

- 产品目标理解：较好
- 技术方向：基本正确
- 与当前仓库贴合度：偏低
- 可执行性：需要先重写前半段方案，再开始实现

## 方案里的优点

- 明确区分了“自动保存棋谱”和“手动生成报告”，这一点符合算力成本和未来付费化预期。
- 已经意识到需要异步任务、进度回传、结果持久化，这些都是复盘模块的关键。
- 报告页分成一级页和详情页，这个信息架构是合理的。
- 详情页想复用现有分析视图，而不是完全重做一套 UI，这个方向是对的。

## 主要问题

### 1. 数据模型指向了错误的主实体

当前计划把 `report_tasks.game_id` 设计成 `games(id)` 外键，并假设它是整数主键。但这个模块的需求范围是“当前登录用户自己的对局和导入棋谱”，在现有仓库里更贴近的实体其实是 `user_games`，而不是 `games`。

仓库现状：

- `katrain/web/core/models_db.py` 已有 `UserGame`
- `UserGame.id` 是字符串主键，不是整数
- 导入 SGF、个人棋谱库、研究棋局都已经围绕 `user_games` 建模

这意味着：

- 当前 plan 不能覆盖 imported games
- 当前 plan 也没有真正接到已有的个人棋谱库能力上
- `INTEGER REFERENCES games(id)` 这类设计会和现有数据模型冲突

修改建议：

- 把报告对象改成 `user_game_id -> user_games.id`
- 明确“上传 SGF”先落成一条 `user_games` 记录，再基于它创建 report task
- 不要把“个人复盘报告”建立在 `games` 表上

### 2. 结果存储和现有分析表重复，但又不够完整

当前计划新建了 `report_moves`，但仓库里已经存在 `user_game_analysis`，而且字段更完整：

- `winrate`
- `score_lead`
- `visits`
- `top_moves`
- `ownership`
- `move`
- `actual_player`
- `delta_score`
- `delta_winrate`

相反，Gemini 方案里的 `report_moves` 只写了：

- `move_number`
- `board_hash`
- `top_moves`

这不足以支撑报告详情页的核心功能：

- 胜率走势图
- 目差走势图
- 当前手实际着法和推荐着法对比
- 变化图探索
- 手数级别的失误/妙手分类

修改建议：

- 不要直接照抄当前 `report_moves` 结构
- 先明确二选一：
- 方案 A：复用 `user_game_analysis`，另外新增 `report_tasks` 管理进度和报告类型
- 方案 B：保留独立的 `report_task_moves`，但字段必须补齐到能完整支撑详情页
- 如果考虑未来长期支持 Normal / Deep 多版本并存，我更建议方案 B，但必须是“按 task 存完整快照”，不是当前这个半成品 `report_moves`

### 3. `BackgroundTasks` 不适合这里的重型任务

`plan.md` 把核心分析工作挂到 FastAPI `BackgroundTasks`。这对于发送邮件、写日志这类轻任务可以，但不适合“几百手到上千手逐手调用 KataGo”的重型计算任务。

问题包括：

- 任务生命周期和 Web 进程强耦合
- 服务重启后任务状态难恢复
- 没有明确的队列、并发控制、抢占、重试和 stale task 恢复机制
- 不利于后续做优先级和付费额度控制

而当前仓库已经有更合适的先例：

- `katrain/web/live/analyzer.py`
- `katrain/web/live/analysis_repo.py`

这套模式是“数据库持久化队列 + 后台循环处理 + stale task reset + retry/priority”，明显比 `BackgroundTasks` 更接近复盘模块需要的形态。

修改建议：

- 不要用 `BackgroundTasks` 做报告主任务执行器
- 优先复用 live analyzer 的模式，做一个 `ReportAnalyzerService`
- 在 `server.py` 的 lifespan 中启动/停止这个服务
- 任务状态至少要有：`pending` / `running` / `completed` / `failed`
- 还需要：`error_message`、`started_at`、`completed_at`、`retry_count`

补充判断：

- 现在不一定要直接上 Celery/Redis
- 如果当前部署是单实例或单进程，数据库驱动的后台服务已经够用
- 只有在明确要多实例扩容、任务量很大、或要跨进程可靠消费时，再考虑 Celery/Redis

### 4. 实时进度只是被提到，但没有真正被规划

Gemini 在设计里写了“Polling 或 WebSocket”，但在任务拆分里并没有真正落实哪一种方案，也没有给前端具体实现步骤。Task 5 只是一个本地 mock 的 `reports` 状态数组，不能说明实时进度真的会落地。

当前仓库其实已经有成熟先例：

- `ResearchPage.tsx` 有轮询分析进度的模式
- 其他模块也有 WebSocket 和 polling 的既有代码风格

修改建议：

- v1 先明确选择 polling，不要同时写 “Polling / WebSocket” 模糊处理
- 轮询频率建议 1 秒
- 只对 `pending/running` 的任务轮询
- 一级列表接口直接返回 `total_moves`、`analyzed_moves`、`status`
- 前端写成独立 hook，例如 `useReportTasks()` 或 `useReportProgress(taskId)`

### 5. 前端接入点与现有项目结构不一致

计划里写的是：

- 新建 `katrain/web/ui/src/pages/ReportsPage.tsx`
- 修改 `katrain/web/ui/src/App.tsx`

但当前项目实际不是这个结构：

- 路由入口在 `katrain/web/ui/src/AppRouter.tsx`
- Galaxy 模式页面挂在 `katrain/web/ui/src/GalaxyApp.tsx`
- 现有报告入口 `/galaxy/report` 已经在 sidebar 和 dashboard 中占位，但还未启用

这说明 Gemini 的 plan 并没有对着当前前端结构写。

修改建议：

- 新页面应落在 `katrain/web/ui/src/galaxy/pages/`
- 路由应加在 `GalaxyApp.tsx`
- sidebar 里的 `/galaxy/report` 入口应从 disabled 改成可用
- 不要新造一个脱离现有 Galaxy layout 的独立页面体系

### 6. 一级页面只做了“报告列表壳子”，没有覆盖完整用户流程

需求里一级页至少包含两部分：

- 我的报告
- 生成报告

但 Task 5 只给了一个 `ReportsPage` 的 mock UI，而且和需求仍有差距：

- 没有历史棋局导入 / 本地 SGF 上传
- 没有 Normal / Deep 选择
- 没有“生成后跳回我的报告并显示实时进度”的流程
- “查看复盘报告”按钮被做在每个列表项里，而需求更像“选中后在右侧底部统一显示操作按钮”

修改建议：

- 把“选游戏 / 上传 SGF / 选报告类型 / 创建任务 / 回到列表观察进度”明确拆成单独任务
- 明确 UI 是单 route 下双 panel，还是 `report/new` + `report` 两个 route
- 如果想更贴近现有代码，一级页可以复用 `KifuLibraryPage` 的“列表 + 棋盘预览”布局

### 7. 详情页没有说明如何支持“变化图探索”

需求里明确写了“Supports exploring variations”。这不是一个纯数据显示页就能自动满足的需求。

当前仓库里能真正支持变化图探索的是带 session 的分析页面，例如：

- `ResearchPage.tsx`
- `ResearchAnalysisPanel.tsx`

Gemini 的 `ReportDetailPage` 只是一个占位壳子，没有说明：

- 详情页是否会创建一个只读 research session
- 是否允许在报告页分支落子
- 分支状态和持久化报告数据如何并存
- 如果用户切到非主线节点，报告中的 Top Moves 和图表如何解释

修改建议：

- 在设计里明确“报告详情页”的运行模式
- 我建议 v1 明确为“主线复盘查看器 + 可跳转到 Research 继续研究”
- 如果一定要在详情页内支持变化图探索，就需要明确 session 方案，而不是只说“类似现有分析视图”

### 8. 缺少鉴权、幂等、重复生成和失败恢复策略

当前 endpoint 草图里没有认真处理这些实际问题：

- 用户是否拥有该 `user_game`
- 同一局棋同一种报告类型重复点击“生成”怎么办
- 生成中再次点击怎么办
- 已完成报告再次生成是否复用旧结果
- 失败任务是否可重试

这是复盘模块的核心业务规则，不是实现细节。

修改建议：

- `POST /reports` 必须校验当前用户是否拥有该 `user_game`
- 对 `(user_id, user_game_id, report_type)` 制定幂等策略
- 建议规则：
- 若已有 `pending/running` 任务，直接返回现有任务
- 若已有 `completed` 且未 `force=true`，返回现有结果
- 若用户显式要求重跑，再创建新任务

### 9. 迁移方案不符合当前仓库的数据库事实

Gemini 把 Task 1 写成：

- 新建 SQL migration
- 修改 `katrain/postgres/init.sql`

但当前仓库实际数据库事实是：

- 主要模型定义在 `katrain/web/core/models_db.py`
- 测试大量使用 SQLite
- `Base.metadata.create_all()` 是现有测试和部分运行模式的重要路径

如果只改 `init.sql` 和一份 PostgreSQL migration，SQLite / board mode / 单元测试都不会自然跟上。

修改建议：

- 主改动应先落在 SQLAlchemy model
- repository 层和测试一起更新
- `katrain/postgres/init.sql` 只作为 PostgreSQL 冷启动补充，不应是唯一真相来源

### 10. 缺少测试计划

当前 `plan.md` 每个 task 都带 commit step，但没有测试 step。这对一个跨数据库、后台任务、前端路由、用户鉴权的功能来说不够严谨。

修改建议：

- 后端至少补：
- repository 测试
- API 鉴权 / ownership 测试
- worker 任务状态推进测试
- 前端至少补：
- 一级页列表状态展示测试
- 进度 polling 测试
- 详情页基础渲染测试

可参考现有测试位置：

- `tests/test_user_game_repo.py`
- `tests/web_ui/test_user_data_api.py`
- 前端 `katrain/web/ui/src/galaxy/pages/*.test.tsx`

## 我建议 Gemini 重写后的技术方案

### 推荐架构

我建议把最终方案改成下面这个版本：

1. 报告对象统一绑定到 `user_games`
2. 新增 `report_tasks` 表，用来表示一次报告生成任务
3. 新增 `report_task_moves` 表，按 `task_id + move_number` 存完整逐手结果
4. 后台执行器不要用 `BackgroundTasks`，改为 DB-backed `ReportAnalyzerService`
5. 进度回传 v1 使用 polling
6. 一级页复用现有个人棋谱库与棋盘预览能力
7. 详情页复用现有分析面板和棋盘组件，但要明确是否只读

### 推荐表结构方向

`report_tasks` 至少应包含：

- `id`
- `user_id`
- `user_game_id`
- `report_type`
- `requested_visits`
- `status`
- `total_moves`
- `analyzed_moves`
- `error_message`
- `created_at`
- `started_at`
- `completed_at`

`report_task_moves` 至少应包含：

- `task_id`
- `move_number`
- `status`
- `winrate`
- `score_lead`
- `visits`
- `top_moves`
- `ownership`
- `actual_move`
- `actual_player`
- `delta_score`
- `delta_winrate`
- `created_at`

建议索引：

- `report_tasks(user_id, created_at desc)`
- `report_tasks(user_game_id, report_type, created_at desc)`
- `report_tasks(status, created_at)`
- `report_task_moves(task_id, move_number)` 唯一索引

### 推荐 API 轮廓

- `GET /api/v1/reports`
  返回当前用户的报告列表，附带对应 `user_game` 摘要和最新任务状态
- `POST /api/v1/reports`
  为某个 `user_game_id` 创建报告任务
- `GET /api/v1/reports/{task_id}`
  返回单个任务状态和摘要
- `GET /api/v1/reports/{task_id}/moves`
  返回详情页需要的逐手分析结果
- `POST /api/v1/reports/import`
  如果不复用 `user-games` 上传接口，才需要单独做；否则可省略

### 推荐前端拆分

- `GalaxyApp.tsx` 新增 `/galaxy/report`
- `GalaxyApp.tsx` 新增 `/galaxy/report/:taskId`
- 一级页拆成：
- 右侧游戏/报告列表
- 中间棋盘预览
- 底部统一操作区
- “生成报告”可以是弹窗，也可以是二级子页面，但要明确
- 详情页尽量复用：
- `LiveBoard`
- `ResearchAnalysisPanel`
- 现有 user game API / auth API / translation hook

## 建议 Gemini 立即修改的点

- 把 `games(id)` 全部改成 `user_games.id`
- 把“只改 SQL migration + init.sql”的思路改成“先改 SQLAlchemy models + repo + tests”
- 删除 `BackgroundTasks` 方案，改成 DB-backed 后台服务
- 明确 v1 只用 polling，不再写 “Polling / WebSocket” 双选模糊表述
- 重新设计结果表，确保能支撑 winrate graph、score graph、top moves、ownership、actual move、delta
- 在 API 设计里加入 ownership 校验、幂等策略、失败重试策略
- 在前端计划里改成对接 `GalaxyApp.tsx`、`userGamesApi.ts`、现有 Galaxy layout
- 给一级页补上“上传 SGF / 从历史棋局选取 / 选报告类型 / 创建任务 / 跳转并看进度”完整流程
- 给详情页补上“如何支持变化图探索”的明确机制
- 给整个 plan 补测试任务，不要只有 commit step 没有验证 step

## 最后的判断

如果只问“这份方案值不值得继续打磨”，答案是值得，因为产品方向是清楚的。

如果问“能不能按当前 `plan.md` 直接分任务给 agent 开始写代码”，我的答案是否定的。建议先重写 Task 1 到 Task 3，再进入实现阶段。否则你会在数据库建模、后台任务执行方式、前端接线位置这三个地方连续返工。
