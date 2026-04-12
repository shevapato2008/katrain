# Report Module Implementation Plan

最后更新：2026-04-12

本文档不再描述最初的目标态，而是明确区分：

1. 当前已经完成并落库/上线的部分
2. 仍然需要继续开发的部分

## 1. 当前实现状态总览

### 1.1 已完成的主线能力

- [x] 报告对象绑定到 `user_games`
- [x] 普通报告和深度报告统一落在 `report_tasks` / `report_task_moves`
- [x] `POST /api/v1/reports/`、`GET /api/v1/reports/`、`GET /api/v1/reports/{taskId}`、`GET /api/v1/reports/{taskId}/moves` 已接通
- [x] 报告任务 ownership 校验、同局同类型幂等、`force=true` 覆盖已实现
- [x] `ReportAnalyzerService` 已在 `katrain-web` 内启动并消费队列
- [x] analyzer 已支持逐手落库、断点续跑、有限重试、stale running task reset
- [x] 默认报告并发数已配置化，当前默认值为 `3`
- [x] 一级页已改成“中间棋盘 + 右侧棋局列表”结构
- [x] 一级页已支持本地 SGF 导入和棋谱库导入
- [x] 一级页已支持搜索、分页、卡片内创建普通/深度报告
- [x] 一级页已支持 `pending` / `running` / `completed` 的状态展示
- [x] 二级页已切换到接近直播详情页的布局
- [x] 二级页已复用 `AiAnalysis`、`TrendChart`、`PlaybackBar`
- [x] 前后端对应测试已经补齐到当前主路径
- [x] 所有前端文字已接入 i18n（11 种语言），左侧栏已从"表现报告"改为"复盘"
- [x] 导入棋局基于 `sgf_hash` 去重，同一用户同一棋局不会重复入库
- [x] 棋谱库导入对话框分页大小与棋谱库主页对齐（20 条/页）
- [x] 报告分析器增加逐手重试（3 次，间隔 2 秒），减少因瞬时网络错误导致整个任务失败
- [x] 二级页导航落子时播放落子音效，与直播模块保持一致

### 1.2 当前不是 bug 的行为

以下行为需要在计划中明确标记为“按现状设计如此”，避免重复误判：

- [x] 同时提交 4 份报告时，默认只会有 3 份进入 `running`
- [x] 第 4 份会停留在 `pending`
- [x] 前端应该显示“排队中”，而不是伪装成“卡住”
- [x] 报告执行器当前属于 `katrain-web`，不是 `katrain-cron`

## 2. 当前代码对应的模块分布

### 2.1 后端

- `katrain/web/api/v1/endpoints/reports.py`
- `katrain/web/report/analyzer.py`
- `katrain/web/core/models_db.py`
- `katrain/web/core/config.py`
- `katrain/web/server.py`

### 2.2 前端一级页

- `katrain/web/ui/src/galaxy/pages/report/ReportsPage.tsx`
- `katrain/web/ui/src/galaxy/components/report/ReportGameCard.tsx`
- `katrain/web/ui/src/galaxy/components/report/ReportImportMenu.tsx`
- `katrain/web/ui/src/galaxy/components/report/ReportLocalImportDialog.tsx`
- `katrain/web/ui/src/galaxy/components/report/ReportLibraryImportDialog.tsx`

### 2.3 前端二级页

- `katrain/web/ui/src/galaxy/pages/report/ReportDetailPage.tsx`
- `katrain/web/ui/src/galaxy/components/report/ReportMetaPanel.tsx`

### 2.4 测试

- `tests/web_ui/test_reports_api.py`
- `tests/web_ui/test_reports_db.py`
- `tests/web_ui/test_report_analyzer.py`
- `katrain/web/ui/src/galaxy/pages/report/ReportsPage.test.tsx`
- `katrain/web/ui/src/galaxy/pages/report/ReportDetailPage.test.tsx`

## 3. 已完成项明细

### 3.1 后端数据与接口

- [x] `ReportTask` / `ReportTaskMove` 已建模，并配置 relationship
- [x] 普通报告与深度报告通过 `report_type` 区分
- [x] `requested_visits` 当前映射为 `normal=500`、`deep=2000`
- [x] `get_report_moves` 已支持读取逐手分析结果
- [x] API 层已经支持返回 ownership、top moves、delta score、delta winrate

### 3.2 报告分析器

- [x] 报告分析是逐手发请求，不是整盘一次性提交
- [x] 每一步分析完成后立即落库
- [x] 恢复时从数据库里最后一手继续
- [x] `playSelectionValue` 已正确映射为 `top_moves[].psv`
- [x] 失败任务会在重试上限内重新进入 `pending`
- [x] stale running task 会在超时后回到 `pending`
- [x] 并发 worker 已支持同时跑多条任务
- [x] 当前默认并发数为 `3`

### 3.3 一级页

- [x] 页面结构已经切换为中间棋盘 + 右侧侧栏
- [x] 棋盘下方报告按钮已移除
- [x] 右侧侧栏已经支持搜索、分页、导入和卡片操作
- [x] 本地导入支持文件选择和 SGF 文本粘贴
- [x] 棋谱库导入支持搜索和分页
- [x] 导入后支持直接生成普通报告或深度报告
- [x] 卡片已展示比赛名、日期、手数、结果、棋手名、黑白标识
- [x] 已完成 badge 已支持跳转到对应二级页
- [x] active task 已支持进度条
- [x] `pending` 和 `running` 已在 UI 中分开呈现为“排队中”和“生成中”
- [x] 当 `total_moves` 尚未回填时，前端已回退到 `game.move_count`
- [x] 一级页已在存在 active task 时每 2 秒轮询刷新

### 3.4 二级页

- [x] 页面已经改成左侧大棋盘、右侧分析栏、底部回放
- [x] 已接入 `TRY / 领地 / 手数 / 建议` 四个开关
- [x] 已接入 `AiAnalysis`
- [x] 已接入 `TrendChart`
- [x] 已接入 `PlaybackBar`
- [x] 在任务为 `pending` 或 `running` 时会继续轮询刷新
- [x] 页面顶部已提供“进入研究室”入口

## 4. 当前仍然存在的差距

### 4.0 对弈模块完赛自动入库 ✅ 已完成

- [x] 对于已登录用户，只要在”对弈”模块完成一局棋，无论是 `play_human` 还是 `play_ai`，都必须自动写入 `user_games`
- [x] 自动保存后的棋局应直接出现在 `/galaxy/report`，不需要二次导入
- [x] 自动保存时必须尽量完整记录双方姓名、对局时间、结果、SGF、`source`、`game_type`

当前代码状态：

- [x] `play_human` 完赛后会自动写入 `user_games`（通过 `GameRepository.record_multiplayer_game`）
- [x] `play_ai` 完赛后自动写入 `user_games`（通过 `_record_ai_game` in server.py）
- [x] 自动入库覆盖 resign、timeout、count 三条完赛路径
- [x] AI 对局设置时自动将人类玩家名设为用户名，AI 玩家名设为计算段位
- [x] 后端测试已覆盖：resign/timeout 自动入库、匿名用户不保存、AI 名称回退、报告页可见性、多人对弈不重复保存

### 4.1 二级页与直播详情页还未完全对齐

- [x] `user_games` 已添加 `round_name` 字段
- [x] `user_games` 已有 `black_rank`（早已存在）
- [x] `user_games` 已有 `white_rank`（早已存在）
- [x] 头部信息已添加来源 badge、棋手等级、round_name、对局结果
- [x] 棋谱库导入已传递 black_rank/white_rank/round_name
- [x] 复盘详情的数据模型是 `task + moves + user_game`（按设计保留，不同于直播页的统一语义对象）
- [x] 报告页没有评论区和直播特有状态（按设计保留差异，非缺陷）

### 4.2 任务运维能力还不完整

- [x] 失败任务已有”重试”按钮（一级页棋局卡片 + 后端 retry API）
- [x] 进程重启后立即恢复所有 `running` 任务（无条件重置为 `pending`，断点续跑）
- [x] 已添加队列总览（summary API + 前端 chip 展示 pending/running/failed 数量）
- [x] 报告消费器已迁移到 katrain-cron（ReportAnalyzerJob）

### 4.3 一级页还有可继续打磨的细节

- [x] 搜索占位文案已更新为”按棋手、标题或赛事搜索”，匹配后端实际搜索字段
- [x] 卡片已展示棋手等级（black_rank/white_rank）
- [x] 用户自己的棋局标题已根据 source+game_type 自动生成（如”人机自由对弈”）
- [x] 多任务排队时，侧栏顶部已展示队列总览 chip（running/queued/failed 数量）
- [x] 棋局卡片已添加删除按钮，支持确认对话框和级联删除

## 5. 下一阶段开发计划

以下计划按优先级排序，都是“剩余工作”，不是已完成项。

### P0：补齐对弈模块完赛自动入库 ✅ 已完成

- [x] 梳理当前 `play_human` 自动入库链路，明确它经过的后端入口、`GameRepository` 字段映射和落库字段
- [x] 为 `play_ai` 增加对等的完赛自动入库逻辑，不论是数子结束、认输、超时还是其他完赛路径，都要写入 `user_games`
- [x] 统一 `play_human` 与 `play_ai` 的落库字段，至少保证：
  - `sgf_content`
  - `player_black`
  - `player_white`
  - `result`
  - `source`
  - `game_type`
  - `game_date` 或等价完赛时间
- [x] 补充前后端测试，验证已登录用户完赛后无需导入即可在报告页看到新棋局

### P1：补齐二级页元数据 ✅ 已完成

- [x] 扩展 `user_games` 添加 `round_name` 字段，全链路打通（模型/API/repo/前端类型）
- [x] 棋谱库导入已传递 `black_rank`、`white_rank`、`round_name`
- [x] 更新 `ReportMetaPanel`：添加棋手等级、来源 badge、round_name、对局结果
- [x] 来源 badge 支持 4 种来源类型 × 11 种语言 i18n

### P2：补任务恢复与重试体验 ✅ 已完成

- [x] 后端添加 `POST /api/v1/reports/{task_id}/retry` 端点（仅允许 failed 任务）
- [x] 一级页棋局卡片已显示失败任务的”重试”按钮（区分普通/深度）
- [x] 添加运行时 stale 检测：cron 轮询中每 60 周期检查 running > 30 分钟的任务并重置
- [x] 添加 `GET /api/v1/reports/summary` 端点返回 pending/running/completed/failed 计数
- [x] 一级页侧栏展示队列总览 chip（运行中/排队中/失败数）
- [x] 所有新增文案已接入 i18n（11 种语言）

### P3：迁移报告分析器到 katrain-cron ✅ 已完成

**动机**：报告分析（复盘）与实时对弈共享 KataGo:8000，3 个并发复盘任务会拖慢对弈响应。katrain-cron 已有独立的 KataGo:8002（GPU 1, 16 线程, 批处理优化），已将报告分析迁移到 cron 执行。

**方案**：数据库作为共享队列。katrain-web 只负责创建 `report_tasks` 记录，katrain-cron 负责轮询并执行分析。前端零改动。

#### Step 1: 在 katrain-cron 中添加 ReportTask / ReportTaskMove 模型

- [x] 在 `katrain/cron/models.py` 中添加 `ReportTaskDB`、`ReportTaskMoveDB`、`UserGameDB` 独立模型
- [x] 遵循 cron 约定：不从 `katrain/web/` 导入任何内容，使用 `extend_existing=True`

#### Step 2: 创建 ReportAnalyzerJob

- [x] 新建 `katrain/cron/jobs/report_analyze.py`
- [x] 采用与 `AnalyzeJob` 相同的 **持久异步循环** 模式
- [x] 使用 cron 的 `KataGoClient`（port 8002）替代 web 的 `RequestRouter`
- [x] 保留所有行为：并发=3、逐手重试、断点续跑、stale reset、SGF 解析、delta 计算

#### Step 3: 注册到 CronScheduler

- [x] 在 `katrain/cron/scheduler.py` 中作为持久循环启动，由 `config.REPORT_ANALYZE_ENABLED` 控制

#### Step 4: 添加配置项

- [x] `REPORT_ANALYZE_ENABLED`、`REPORT_CONCURRENCY`、`REPORT_POLL_INTERVAL` 已添加到 `katrain/cron/config.py`

#### Step 5: 从 katrain-web 移除 ReportAnalyzerService

- [x] 从 `server.py` 的 `_lifespan_server` 和 `_lifespan_board` 中移除启动/停止逻辑
- [x] 删除 `katrain/web/report/analyzer.py`
- [x] 移除 web config 中的 `REPORT_ANALYZER_CONCURRENCY`

#### Step 6: 更新部署

- [x] `docker-compose.yml` 已添加 `CRON_REPORT_ANALYZE_ENABLED=true` 和 `CRON_REPORT_CONCURRENCY=3`

#### 不变的部分

- 前端：零改动
- Reports API：留在 katrain-web
- 数据库 schema：不变
- 并发控制：全局最多 3 个并发任务

### P4：继续补测试 ✅ 已完成

- [x] 增加前端对多任务排队与并发显示的更强断言（多游戏 × 多状态同时渲染 + queue summary chip 验证）
- [x] 重试入口对应的 UI 测试已添加（failed → retry → API 调用）
- [ ] 浏览器级 E2E 覆盖（需 Playwright 基础设施，留作后续迭代）

### P5：棋局删除功能 ✅ 已完成

**动机**：用户下过的棋局只有自动入库逻辑，没有前端删除入口。用户无法清理不需要的棋局（如测试对局、重复导入等），棋局列表会越来越臃肿。

**现有基础设施**（已全部就绪）：

| 层 | 状态 | 位置 |
|----|------|------|
| DELETE API | ✅ 已有 | `katrain/web/api/v1/endpoints/user_games.py:163-173` |
| Repository | ✅ 已有 | `katrain/web/core/user_game_repo.py:153-166` — 带 user_id 权限校验 |
| 前端 API Client | ✅ 已有 | `katrain/web/ui/src/galaxy/api/userGamesApi.ts:148-152` — `UserGamesAPI.delete(token, gameId)` |
| DB Cascade | ✅ 已有 | `UserGame` → `UserGameAnalysis` (cascade=all,delete-orphan) + `ReportTask` (cascade=all,delete-orphan) → `ReportTaskMove` (cascade=all,delete-orphan) |

**唯一缺失**：前端 UI 层 — 棋局卡片没有删除按钮。

- [x] ReportGameCard 添加删除按钮（`onDelete` prop + `IconButton` + `DeleteOutlineIcon`）
- [x] ReportsPage 添加删除确认对话框（`deleteTarget` state + `Dialog` + 调用 `UserGamesAPI.delete`）
- [x] i18n 翻译（6 个 key × 11 种语言：delete_game/delete_confirm_title/delete_confirm_body/delete_success/delete_failed）
- [x] 前端测试（`ReportsPage.test.tsx` 新增删除流程用例）

## 6. 推荐执行顺序

1. ~~P0：对弈模块完赛自动入库~~ ✅ 已完成
2. ~~P3：迁移报告分析器到 katrain-cron~~ ✅ 已完成
3. ~~P5：棋局删除功能~~ ✅ 已完成
4. ~~P1：补齐二级页元数据~~ ✅ 已完成
5. ~~P2：补任务恢复与重试体验~~ ✅ 已完成

所有优先级已完成。唯一剩余项为浏览器级 E2E 测试（需 Playwright 基础设施）。

## 7. 当前验证基线

每次继续修改报告模块时，至少保持以下验证命令通过：

```bash
pytest tests/web_ui/test_report_analyzer.py tests/web_ui/test_reports_db.py tests/web_ui/test_reports_api.py tests/web_ui/test_user_data_api.py -q
npm test -- src/galaxy/pages/report/ReportsPage.test.tsx src/galaxy/pages/report/ReportDetailPage.test.tsx
npm run build
```

这三组命令已经是当前报告模块的最低回归基线，不应再回退到“只看页面能不能打开”。
