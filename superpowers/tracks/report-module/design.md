# “复盘”模块设计文档 (Report/Review Module Design)

## 1. 概述与核心定位
本模块旨在为 KaTrain 用户提供专属的“复盘报告”功能。它的核心体验对标星阵围棋的报告模块，但其使用边界限定于**当前登录用户自己的对局和导入棋谱的复盘与分析**（即 `user_games` 表中的数据）。

**关键规则：**
1. **统一的数据来源：** 报告对象统一绑定到 `user_games.id`。所有复盘报告必须基于 `user_games` 表中已有的记录。如果用户想上传新 SGF 进行复盘，必须先通过现有的 `/api/v1/user-games/` 接口创建对局记录。
2. **手动触发：** 用户的对弈结束后（或导入棋谱后），系统**不会自动启动复盘分析**。复盘操作必须由用户手动启动。
3. **分析方式对齐：** 采用和“直播 (Live)”模块相同的后台持久化服务分析模式 (`ReportAnalyzerService`)，不再使用不适合重型计算的 `BackgroundTasks`。

---

## 2. 后端存储与架构设计

### 2.1 数据模型扩展
后端数据库需要基于现有的 `user_games` 实体进行扩展，新增两个表来管理报告任务及其完整的每手快照结果。这避免了直接修改已有的 `user_game_analysis` 导致耦合过重，也能支撑未来更多维度的独立快照报告：

*   **复盘任务状态表 (`report_tasks`)**
    *   `id`: INTEGER PRIMARY KEY
    *   `user_id`: INTEGER (所有者校验)
    *   `user_game_id`: VARCHAR (关联 `user_games.id`)
    *   `report_type`: VARCHAR (普通 / 深度)
    *   `requested_visits`: INTEGER (根据报告类型设定的计算量)
    *   `status`: VARCHAR (pending / running / completed / failed)
    *   `total_moves`: INTEGER
    *   `analyzed_moves`: INTEGER
    *   `error_message`: TEXT
    *   `created_at`, `started_at`, `completed_at`
    *   包含 SQLAlchemy 关系 (relationship) 关联到 `UserGame` 和 `ReportTaskMove`。
*   **报告逐手快照表 (`report_task_moves`)** 
    按 `task_id` 存储完整的独立分析快照，以支撑详情页的所有分析图表展示，字段对齐现有的 `UserGameAnalysis`。
    *   `task_id`: INTEGER (关联 `report_tasks.id`)
    *   `move_number`: INTEGER
    *   `status`: VARCHAR
    *   `winrate`, `score_lead`, `visits`, `top_moves` (JSON), `ownership` (JSON)
    *   `actual_move`, `actual_player`, `delta_score`, `delta_winrate`
    *   `created_at`

*(注：不再修改 `init.sql`，直接通过 SQLAlchemy 的模型定义进行表结构的初始化)*

### 2.2 后端执行器设计
复用 `live_analyzer` 模式，实现独立的后台服务机制：
*   **持久化队列服务：** 新增 `ReportAnalyzerService`，在 FastAPI 生命周期 (`lifespan`) 启动与关闭。
*   **核心控制机制：** 
    *   **轮询与领取：** 服务内部循环轮询数据库中 `status='pending'` 的任务。
    *   **超时恢复 (Stale Task Reset)：** 定期检查卡在 `running` 状态过久的任务，将其重置为 `pending`。
    *   **失败重试：** 记录失败信息 (`error_message`)，允许手动或自动重试。
    *   **参数映射：** 根据 `report_type` (如 normal/deep) 解析出对应的 `requested_visits`。
    *   **初始化：** 开始分析前，解析 SGF 获取手数，更新 `total_moves`，然后逐手调用 KataGo 并将结果写入 `report_task_moves`。

### 2.3 核心 API 与幂等鉴权策略
所有的 API 请求必须校验用户对 `user_game_id` 的所有权 (Ownership)。
*   **请求幂等与重复生成：**
    *   如果数据库中针对同一局和相同类型已存在 `pending` 或 `running` 任务，则拒绝新建，直接返回该任务的进度状态。
    *   如果已存在 `completed` 任务，且用户未显式强制要求重跑，则返回旧任务结果。
*   **列表聚合：** 获取报告列表的接口需返回“用户拥有的全部 `user_games` 及其最新的 `report_tasks` 状态”，以保证前端能在一个列表中展示“未生成”、“生成中”和“已完成”三种状态。

---

## 3. 前端交互与页面设计

新增的页面代码应建立在现有的 Galaxy Layout 中 (`katrain/web/ui/src/galaxy/pages/report/`)。

### 3.1 一级页面：我的复盘报告 (My Reports)
**路由入口：`/galaxy/report`**
采用双 Panel 布局（左侧列表与信息，右侧预览），类似于现有的 `KifuLibraryPage`。

*   **列表区：**
    *   列出用户的全部历史对局和导入棋谱。数据源通过聚合接口或合并 `userGamesApi` 和报告状态获取。
    *   明确展示三种状态：未生成、生成中（带进度条和已分析手数）、已完成。
    *   **实时进度 (Polling)：** 前端实现短轮询钩子 (e.g., `useReportTasks()`)，每秒向后端查询并更新 `running/pending` 状态的任务的进度。
*   **生成报告交互流：**
    *   支持从列表中选取历史对局。
    *   支持本地 SGF 上传（前端调用 `POST /api/v1/user-games/` 创建对局后，再触发生成报告）。
    *   选定后请求生成 API，界面转入 Polling 状态展示进度条。

### 3.2 二级页面：详细复盘报告 (Report Detail)
**路由入口：`/galaxy/report/:taskId`**

*   **复用机制：**
    *   调用 `GET /api/v1/reports/{taskId}/moves` 接口获取完整快照数据。
    *   复用现有的分析面版组件（如 `ResearchAnalysisPanel` 的衍生版本）和棋盘组件 (`LiveBoard` / `ResearchBoard`)。
*   **分支探索支持 (Variation Exploration)：**
    *   本页面的初始状态为**只读模式**，专门用于沿着主线浏览报告快照数据、走势图和选点分析。
    *   如果在棋盘上进行了试下（分支操作），系统提供“进入研究室继续探索”的跳转按钮或模式切换，带参转入现有的 `Research` 模式进行进一步的主动分析计算。