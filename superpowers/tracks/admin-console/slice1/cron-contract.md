# cron 只读契约（本地切片 1）

此契约沿用现有独立后台的 `admin:fan` Bearer 会话，不使用公开 Galaxy 的 `users.is_admin`；旧计划中的登录响应 `{username, env, token}` 已被现有 `{access_token, token_type}` 取代。cron 仅写状态及历史，admin 只读并在查询时判定健康。前端中文任务名只在 `jobLabels.ts`，未知名称显示原名。

| 请求 | 成功响应 | 异常 |
|---|---|---|
| `GET /api/admin/cron/jobs` | `{observed_at, jobs:[CronJob]}` | 401；状态表未建时 503，明确提示 web 未建表 |
| `GET /api/admin/cron/jobs/{name}/runs?limit=50&before_id=` | `{runs:[CronRun], next_before_id}`；`limit` 最大 200 | 401；任务不存在 404 |
| `GET /api/admin/cron/queues` | `{observed_at, live_analysis, report_tasks}` | 401 |

字段真源是 [spec §6.2–6.5](../spec-2026-09-24-admin-console.md)；同形定义分别在 [`cron_schemas.py`](../../../../katrain/web/admin/cron_schemas.py) 与 [`types.ts`](../../../../katrain/web/ui/src/admin/cron/types.ts)。时间均输出带时区 ISO 字符串，SQLite 的 naive datetime 由读取端视为 UTC。`CronJob.health` 只由 admin 按采样时刻现场计算，优先级为 `offline → disabled → pending → stuck → running → failed → errors → overdue → ok`。运行历史 `error` 和状态 `last_error` 在写入时截到 2000 字符；运行历史的 `error_count` 仍保留本次 ERROR 总数。队列按状态计数，提供最老 pending 时间，没有 pending 则为 null。

浏览器状态独立于 API：首次 loading 不声称健康；503 表未建和零任务分别给空态；网络/API 错误保留前一次成功采样并显式标旧；401 清除后台 token 回登录；心跳逾 120 秒则所有任务显示失联。15 秒轮询不得关闭已打开的历史抽屉。Fixture 仅用于 Vite 开发预览，本地真实接口验收后删除。
