# “复盘”模块设计文档（当前实现状态）

最后更新：2026-04-11

## 1. 模块定位
“复盘”模块当前已经落地为一个基于 `user_games` 的个人报告工作台，包含两个页面：

1. 一级页 `/galaxy/report`
2. 二级页 `/galaxy/report/:taskId`

它的职责不是直播，也不是完整研究室，而是围绕“我的棋局”完成以下闭环：

1. 选择已有棋局或导入新棋局
2. 为该棋局创建普通报告或深度报告
3. 在报告任务运行期间查看排队和进度
4. 在报告完成后进入二级页按主线浏览 AI 复盘结果

报告对象严格绑定到 `user_games.id`。不管棋局来自本地 SGF 还是公共棋谱库，都会先导入 `user_games`，再创建报告任务。

新增的基础产品约束：

1. 只要是已登录用户，在“对弈”模块中完成的棋局，无论是人人对弈还是人机对弈，都必须自动落入 `user_games`
2. 自动落库时必须尽可能完整记录：
   - `sgf_content`
   - 双方姓名
   - 对局时间
   - 结果
   - `game_type`
   - `source`
3. 这些自动保存的对局不需要用户再次导入，应该直接出现在“复盘/报告”模块一级页列表中
4. “复盘/报告”模块不应只服务于”导入棋谱”场景，也必须覆盖”用户刚刚下完的一盘棋”

### i18n 状态

模块所有前端用户可见文字已接入 Gettext i18n 系统，支持 11 种语言（en/cn/tw/jp/ko/de/es/fr/ru/tr/ua）。左侧导航栏已从”表现报告”更名为”复盘”（en: Review, jp: 検討, ko: 복기）。所有 `report:*` 翻译键定义在 `scripts/batch_translate_galaxy.py`，前端组件统一使用 `useTranslation()` hook。

## 2. 当前后端设计

### 2.1 数据模型
报告模块当前使用两张表：

- `report_tasks`
- `report_task_moves`

这两张表位于同一套数据库模型中，不存在“普通报告一张表、深度报告另一张表”的拆分。

`report_tasks` 的关键字段：

- `user_game_id`：绑定 `user_games.id`
- `report_type`：`normal` 或 `deep`
- `requested_visits`：当前映射为 `normal=500`、`deep=2000`
- `status`：`pending` / `running` / `completed` / `failed`
- `total_moves`
- `analyzed_moves`
- `retry_count`
- `error_message`

`report_task_moves` 用于存每一手的快照分析结果，按 `(task_id, move_number)` 唯一。

### 2.2 API
当前前后端已经接通以下接口：

- `POST /api/v1/reports/`
- `GET /api/v1/reports/`
- `GET /api/v1/reports/{task_id}`
- `GET /api/v1/reports/{task_id}/moves`

行为说明：

- 创建报告时做 ownership 校验，只允许当前用户为自己的 `user_game` 建报告
- 默认保留同局同类型的幂等规则
- 如果请求 `force=true`，会新建一条同类型任务
- 普通报告和深度报告是同一张 `report_tasks` 表中的不同行

报告页之所以能直接消费“对弈模块”完赛后的棋局，是因为一级页直接读取 `user_games` 列表，而不是单独维护一份报告专用棋局源。

### 2.3 执行器与调度
当前报告执行器是 `katrain-web` 进程内启动的 `ReportAnalyzerService`，不是 `katrain-cron`。

也就是说：

- 创建任务入口在 `katrain-web`
- 消费 `pending` 队列的 worker 也在 `katrain-web`
- `katrain-cron` 当前没有参与报告生成

默认最大并发任务数是 `3`，由 `REPORT_ANALYZER_CONCURRENCY` 控制，可通过环境变量 `KATRAIN_REPORT_ANALYZER_CONCURRENCY` 覆盖。

### 2.4 任务执行语义
当前执行语义已经不是“整盘一次性分析完再写库”，而是逐手推进：

1. 解析 SGF，得到整盘主线
2. 对 `move_number = 0..N` 逐手向 KataGo 发请求
3. 每分析完一手，立即写入 `report_task_moves`
4. 同时更新 `report_tasks.analyzed_moves`
5. 全部完成后把任务标记为 `completed`

这意味着：

- 已完成的步数会边分析边落库
- 进程中途退出时，已经提交的步数不会丢
- 恢复后会从库里最后一手继续，而不是从头开始

### 2.5 失败恢复与续跑
当前实现已经包含以下恢复机制：

- 断点续跑：根据已存在的 `report_task_moves` 找到恢复起点
- 有限重试：默认最多 `3` 次
- stale running task reset：运行中任务超过 5 分钟未更新，会被重置回 `pending`

当前限制也需要明确：

- 进程刚重启后，旧的 `running` 任务不是“立刻恢复”，而是等待 stale 窗口后再被捞起
- 当前没有单独的“手动重试失败任务”前端入口

## 3. 一级页：`/galaxy/report`

### 3.1 页面结构
当前一级页已经改成“中间棋盘 + 右侧列表”的结构：

- 最左侧：Galaxy 全局导航
- 中间主区：当前选中棋局的只读预览棋盘
- 右侧侧栏：棋局列表、导入、搜索、分页、报告操作

这一点已经和早期“列表在左、棋盘在右”的旧方案不同。

### 3.2 中间棋盘区
中间区域当前职责是预览当前选中棋局，不承担报告任务管理。

现状：

- 默认展示当前选中棋局的终局盘面
- 使用 `LiveBoard`
- 下方使用 `PlaybackBar`
- 支持拖动进度、前后手、自动播放、首尾跳转
- 不再在棋盘下方放“生成普通报告 / 生成深度报告”按钮

这是当前实现与星阵一级页最接近的一部分。

### 3.3 右侧侧栏
右侧栏当前已经具备四个区域：

1. 导入入口
2. 搜索框
3. 棋局卡片列表
4. 分页

#### 导入入口
当前不是单按钮，而是下拉菜单，包含两条路径：

- 从本地导入 SGF
- 从棋谱库导入

本地导入现状：

- 支持文件选择
- 也支持直接粘贴 SGF 文本
- 会解析基础信息后写入 `user_games`
- 支持“仅导入”“导入并生成普通报告”“导入并生成深度报告”

棋谱库导入现状：

- 使用弹窗承载
- 支持搜索和分页
- 可选择公共棋谱记录后抓取 SGF
- 导入后同样写入 `user_games`
- 也支持“仅导入”“导入并生成普通报告”“导入并生成深度报告”

需要强调的是，导入只是 `user_games` 的补充来源，不是唯一来源。

`/galaxy/report` 当前和未来都应同时覆盖三类来源：

- 对弈模块完赛后自动写入的 `play_human`
- 对弈模块完赛后自动写入的 `play_ai`
- 用户主动导入的 `import` / `kifu_library`

#### 搜索与分页
当前一级页已经接上：

- 搜索参数 `q`
- 页码参数 `page`
- URL search params 持久化

搜索后端当前依赖现有 `user-games` 列表搜索能力，实际匹配字段是：

- `title`
- `player_black`
- `player_white`
- `event`

前端当前分页大小是 `12`。

#### 棋局卡片
当前卡片已经不再是最初那种“标题 + 手数 + 状态”的极简形态，而是展示：

- 比赛名或标题
- 日期
- 手数
- 结果
- 黑白双方名字
- 黑白子颜色标记

卡片上的报告状态当前由前端归并：

- `activeNormal`
- `activeDeep`
- `completedNormal`
- `completedDeep`

渲染规则：

- 已完成的类型显示 badge 按钮，可进入对应二级页
- 仍缺失的类型可继续生成
- 同类型如果已有 active task，不再同时展示该类型的 completed badge
- `pending` 显示为“排队中”
- `running` 显示为“生成中”
- 进度条展示 `analyzed_moves / total_moves`
- 如果任务还未回填 `total_moves`，前端回退用 `game.move_count`

### 3.4 一级页轮询语义
当前一级页并不是 WebSocket 推送，而是定时轮询。

现状：

- 只要页面上存在 `pending` 或 `running` 报告任务
- 前端就每 2 秒调用一次 `ReportsAPI.list`
- 这样右侧卡片会自动更新进度，不需要手动刷新

### 3.5 一级页的并发语义
这里必须和当前代码保持一致：

- UI 允许用户连续为多个不同棋局发起报告
- 后端默认最大并发 worker 数是 `3`
- 所以第 4 条及之后的任务默认会停留在 `pending`
- 这不是 bug，而是当前队列设计

也就是说，当前产品语义是：

- “支持多局同时提交”
- “支持前三条并行分析”
- “更多任务排队并显示 `排队中`”

而不是“默认 5 条齐头并进”。

## 4. 二级页：`/galaxy/report/:taskId`

### 4.1 当前目标与已实现部分
二级页已经从早期的“摘要页”改成更接近直播详情页的结构，但还没有做到完全同构。

当前布局：

- 左侧：大棋盘
- 右侧：Meta + 功能开关 + AI 推荐 + 趋势图
- 底部：`PlaybackBar`

### 4.2 已接入的直播侧能力
二级页当前已经复用或对齐了以下直播模块能力：

- `LiveBoard`
- `AiAnalysis`
- `TrendChart`
- `PlaybackBar`

右侧功能开关当前有：

- `TRY`
- `领地`
- `手数`
- `建议`

当前也支持在报告页里进行轻量试下，但它仍然不是完整研究室。

### 4.3 数据加载与刷新
二级页当前会同时拉：

- `GET /reports/{taskId}`
- `GET /reports/{taskId}/moves`
- `GET /user-games/{gameId}`

并且在任务状态为 `pending` 或 `running` 时持续轮询，所以打开一个尚未完成的报告详情页时，内容会继续推进，而不是只加载一次。

### 4.4 当前与直播二级页的真实差异
这里不能再写成“已完全对齐”，因为代码现状还没到。

当前仍存在这些差异：

1. `user_games` 还没有直播详情页那套完整元数据
2. 缺少 `round_name`、`black_rank`、`white_rank`、来源 badge 等更完整的头部信息
3. 复盘详情还是 `task + moves + user_game` 三段式数据模型，不是直播页的 `match + analysis` 语义模型
4. 没有评论区、直播状态、刷新/跟随最新等直播语义
5. 当前页面上已经去掉独立的“报告摘要 / 精彩手 / 失误手”大区块，转而尽量收回到直播页那种 `AiAnalysis + TrendChart` 的结构

所以准确表述应该是：

- “已经向直播二级页显著靠拢”
- “但仍未完全对齐”

## 5. 当前已验证的测试覆盖

当前和报告模块直接相关、已经实际跑通的测试包括：

- `tests/web_ui/test_reports_api.py`
- `tests/web_ui/test_reports_db.py`
- `tests/web_ui/test_report_analyzer.py`
- `tests/web_ui/test_ai_game_autosave.py`
- `katrain/web/ui/src/galaxy/pages/report/ReportsPage.test.tsx`
- `katrain/web/ui/src/galaxy/pages/report/ReportDetailPage.test.tsx`

这些测试当前覆盖的核心点包括：

- 报告任务创建、幂等、`force=true`
- `report_tasks` / `report_task_moves` 关系
- analyzer 的断点续跑、重试、并发、`psv` 持久化
- 一级页导入入口、卡片操作、排队文案（已切换到 i18n 英文 fallback 断言）
- 二级页直播式壳子和核心区块渲染
- AI 对弈完赛自动入库（resign/timeout/count）

## 6. 当前未完成项

以下能力仍然属于后续项，不应在文档中写成”已完成”：

1. ~~对弈模块的 `play_ai` 完赛自动落 `user_games`~~ ✅ 已完成
2. ~~统一”完赛自动入库”元数据，确保 `play_human` 与 `play_ai` 都写入对局时间、双方名、结果、SGF 等报告页所需字段~~ ✅ 已完成
3. 报告页中更明确地区分不同 `source` 的来源展示
1. 二级页与直播详情页的完整元数据对齐
2. 失败任务的显式“重试”按钮
3. 进程重启后立刻恢复 `running` 任务，而不是等待 stale reset
4. 报告消费器迁移到独立 worker 或 `katrain-cron`
5. 更完整的报告结论层，例如更强的关键手摘要和产品化结论文案

## 7. 本轮结论
截至当前版本，“复盘”模块已经不是纯方案状态，而是一个可运行的最小闭环：

1. 用户可以导入自己的棋局
2. 用户可以创建普通/深度报告
3. 报告会在 `katrain-web` 内部队列中分析
4. 页面会显示 `排队中`、`生成中`、`已完成`
5. 报告完成后可以进入二级页按主线浏览 AI 分析

但它仍然是“已上线的第一版”，不是最终形态。后续文档与代码都应该围绕“补足直播级详情体验、补强任务恢复与运维能力”继续推进。
