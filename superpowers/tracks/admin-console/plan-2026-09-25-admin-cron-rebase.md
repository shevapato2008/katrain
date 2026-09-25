# 定时任务可视化：基于现有专用后台的 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents are appropriate) or superpowers:executing-plans. Steps use checkboxes. Fan 当前要求在 `feature/admin-console` 的同一 worktree 内逐模块推进；不要为本计划再开并行开发 worktree。

**Goal:** 在现有独立管理后台中增加只读 cron 状态、运行历史和两条队列的本地完整用户旅程。

**Architecture:** 保留已上线代码中的 `admin:fan` 专用身份、Bearer 会话、同源静态入口和 loopback Compose 配置，不执行旧 cron 计划的共享 `users.is_admin` 鉴权、后台骨架、管理员引导步骤。cron 进程负责记录状态及历史；后台只读查询并现场判定健康；React 页面沿用教程后台主题和会话。新表仍由公开 web 的 schema 初始化建立，admin 进程不建表。

**Tech Stack:** FastAPI、SQLAlchemy、APScheduler 3、React/Vite/Vitest、Playwright；原始数据字段与状态规则见 [spec §6](./spec-2026-09-24-admin-console.md) 和 [旧 cron 计划](./plan-2026-09-24-admin-console-cron.md) 的 Task 4、7–10。

---

## 当前边界与停点

- 本计划只推进本地设计、Fixture、契约、实现和本机隔离数据验收。旧计划 Task 14–15 的测试/生产发布步骤已经与现有身份和仓库状态不符，发布前须重审；每次 SSH、真实库写入、push、部署仍须 Fan 当场授权。
- 教程模块仍是“本机实现与合成媒体预览、外部 Edge TTS/目标环境/Fan 最终验收待办”。Fan 最新指令和独立 GPT-6 Astra 仅允许在此状态下继续本地 cron 设计及隔离 Fixture，不能把教程标记完成或越过外部操作关卡。
- 新模块的设计稿与同视口四图由 Fan 委托独立 GPT-6 Astra 夜间裁定，结论及证据要记录；明日 Fan 在 MacBook 网页复核。任何 Agent 决定都不代替外部操作批准。
- 当前工作树另有用户/其他工具留下的 `.playwright-cli` 删除状态；只暂存本计划明确涉及的路径，不恢复、清理或一并提交这些文件。

## 文件边界

| 路径 | 职责 |
|---|---|
| `superpowers/tracks/admin-console/slice1/design/*` | 本地 HTML 设计稿、参考截图、视觉记录 |
| `katrain/web/ui/src/admin/cron/CronPage.tsx`、`CronPage.css`、`types.ts` | 只呈现契约数据与操作状态，不持有后台密钥 |
| `katrain/web/ui/src/admin/cron/__fixtures__/cronFixture.ts` | 开发预览专用示例数据；真实集成并验收后删除 |
| `katrain/web/ui/src/admin/main.tsx`、`AdminApp.tsx`、`api/client.ts` | 现有会话、导航、API 接入；避免重建登录与 token 存储 |
| `katrain/web/core/models_db.py`、`katrain/cron/models.py` | 状态及历史同名映射，由 web 建表 |
| `katrain/cron/run_recorder.py`、`scheduler.py`、有关 loop job | 进程心跳、运行结果、ERROR 捕获与循环推进 |
| `katrain/web/admin/routers/cron.py`、`cron_health.py`、`app.py` | 后台只读接口与现场健康判定 |
| `tests/web_ui/test_cron_*.py`、`test_admin_cron_*.py`、`src/admin/cron/*.test.tsx` | 本切片边界测试 |

## Task 1：设计稿与视觉裁定

- [x] 已用 `ui-ux-pro-max` 检索监控/密集表格/状态反馈规则，保持 Fan 选定的 B 石墨铜、C 雾白蓝和楷体；用 `claude-design` 的 Monitor/Inspect 构图完成 [HTML 设计稿](./slice1/design/admin-cron-design.html)。
- [x] 第一版 1440×900 Chromium 已截夜间正常/失联/历史，白天失败/接口错误/空表/零任务/加载/登录参考图；历史抽屉实测 200 行且独立可滚，控制台 0 error。该组图在下项修订后已过期，仅作构图参考。
- [x] 独立 GPT-6 Astra 复核 HTML 后指出并推动失败排序、历史语义、旧数据时间和文字对比度的局部修正；最新 HTML 的源码与状态语义复核通过。见 [设计说明](./slice1/design/design-notes.md)。
- [x] 修订后用本地服务与 Playwright Chromium 在 1440×900 重拍异常、历史、首次加载、接口错误、失联和正常代表图；七张 `v2` 图逐张核对像素尺寸。控制台 0 errors / 0 warnings，200 条历史独立滚动区滚轮实测 `scrollTop: 0 → 600`。旧图已标明只作构图参考。
- [x] 🛑 独立 GPT-6 Astra 已逐张查看七张修订后 1440×900 真渲染图，结论 **APPROVE FOR LOCAL FIXTURE**、无必改项；仅解除本地 Fixture 关卡。Fan 最终视觉复核、四图确认及后端关卡仍分别保留。

## Task 2：隔离 Fixture 前端

- [x] 测试先红：独立入口预览可切九个设计状态，`admin` 生产构建和公开 Galaxy/kiosk 构建不包含 Fixture 数据；九行表格可滚，200 条运行历史可滚，零任务不显示虚假正常。
- [x] 在 `src/admin/cron/` 加契约类型和纯展示页，复用现有后台布局/会话与 B/C 主题。开发期仅在显式 `VITE_ADMIN_FIXTURE=true` 且 `import.meta.env.DEV` 的预览路径加载 `__fixtures__`；生产路径不使用示例数据。
- [x] 1440×900 真浏览器走通状态切换、任务选中/历史抽屉、重试/刷新反馈；对照 Task 1 的关键参考图检查层级、字体、间距、色彩、语义。九行在 1440×900 一屏可见，在 1440×768 可滚；历史 200 条滚轮实测 0→600。
- [x] 🛑 已保存参考图、Fixture 实现图、并排图、叠加/差异图与视觉差异记录；独立 GPT-6 Astra 逐张审阅后裁定 **APPROVE**、无必改项，可进入本地契约与后端。Fan 明日复核仍可要求返工；外部操作关卡不变。

## Task 3：冻结契约，补表与记录器

- [x] 对照现有 `AdminApp` 和 `createAdminApi`，将旧 spec §6.5 的 `/api/admin/cron/jobs`、`runs`、`queues` 字段定稿，见 [cron-contract.md](./slice1/cron-contract.md)、TS 类型与 Pydantic 响应模型；**不使用旧计划中的 `token` 登录响应或公开 `users.is_admin`**。聚焦契约测试先红后绿（1 passed）。
- [x] 模型一致性测试先红，再在 `models_db.py` 和 `katrain/cron/models.py` 增加 `cron_job_status` / `cron_job_runs`；只由 web schema 初始化建表，不由 admin 启动建表。
- [x] 记录器测试先红，覆盖成功、失败、ERROR 后返回、短间隔成功不写历史、SIGKILL 后遗留运行重启标失败、建表晚于 cron 时重试登记、记录器写库失败不影响任务；按旧 Task 7 的已验证局部实现最小接入 `run_recorder.py`。
- [x] 调度器与 loop job 接记录器、30 秒心跳和清理；保留 `katrain/cron/**` 的 import 边界。我复跑模型、记录器、import 边界及复盘分析聚焦测试 **22 passed**；尚未提交，待本地集成验收后整体检查并仅暂存本模块路径。

## Task 4：后台只读接口与真实集成

- [x] 健康判定纯函数表驱动测试先红，再实现 `offline → disabled → pending → stuck → running → failed → errors → overdue → ok` 顺序（spec §6.4），时间统一 UTC；37 项聚焦健康测试通过。
- [x] API 测试先红，验证三个接口的 401、503 表不存在、分页上限 200 和队列摘要；在现有 `get_current_admin` 下挂只读路由，不碰现有登录及审计契约。我复跑 API、契约、健康和后台鉴权 **63 passed**。错误文本写入截断由记录器测试覆盖；真实接口集成仍待办。
- [x] 前端换真实 API，15 秒轮询；接口出错保留旧数据但标明采样时间，401 回登录，失联由后台判定所有任务；开发期 Fixture 入口/样式已删，示例仅留测试专用数据，生产构建不含示例业务值。独立 Astra 复核发现的普通 503 误当缺表、旧轮询覆盖新状态已测试先红后绿修复。
- [x] 本机临时 SQLite 用 web schema 建表、cron 记录器写入合成任务、专用 admin 进程提供真实 API，Chromium 检查登录、切换、异常优先、完整错误历史、15 秒轮询后抽屉保留；截图在设计说明。调度器/loop 路径由聚焦测试覆盖；**未运行会访问外部服务的正式 cron 作业，也未把本机 smoke 冒充三服务部署验收**。复核 Python **90 passed**、管理前端 **48 passed**、后台/Galaxy/kiosk 构建和 kiosk 边界检查通过。这里没有运行真实环境 DB 命令。

## Task 5：交付关卡

- [x] 更新 `codex-report.md`、设计/契约/测试证据；列出仍未做的测试与目标环境验收，不把本机通过写成生产可用。cron 四个提交已按 Fan 当次授权推送至 `origin/feature/admin-console` 的 `60d157c1`；报告更新仍是后续本地改动。
- [ ] 🛑 向 Fan 交本地浏览器地址及结果。每条 push、测试部署、生产部署、真实库写入或远程连接分别等待 Fan 当场批准；旧计划 Task 14–15 要按新专用身份与当前分支重新核对后才可执行。
