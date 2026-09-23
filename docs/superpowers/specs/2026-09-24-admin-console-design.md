# 管理后台（katrain-admin）设计：骨架 · cron 可视化 · 前置安全修复

- 日期：2026-09-24
- 状态：待 Fan 审阅
- 分支：`feature/admin-console`（worktree `~/Repositories/katrain-admin-console`，基于 develop `ddedbf9b`）
- 执行计划：
  - 切片 0（安全修复）：`docs/superpowers/plans/2026-09-24-tutorial-admin-guard.md`
  - 骨架 + 切片 1（cron 可视化）：`docs/superpowers/plans/2026-09-24-admin-console-cron.md`

## 0. 一句话

在 katrain 仓里加一个**独立进程**的管理后台：只绑 127.0.0.1，公网网关不转发，管理员经 SSH 隧道用浏览器打开；公开的 katrain-web 上一条后台路由都不挂。第一个完整做完的功能是 cron 任务可视化；动工前先把调研中发现的三个安全问题单独修掉。

## 1. 已定决策（Fan，2026-09-24）

| # | 决策 | 由来 |
|---|---|---|
| D1 | 后台代码放 **katrain 仓**。金镜像以后做成后台里的通用「制品库」，镜像的 manifest 和上传脚本归 smartbox-software 的 provisioning | 依赖方向是 smartbox → katrain（`vendor/katrain` 子模块）；你列的几项里多数的数据和代码都在 katrain |
| D2 | 访问方式：**SSH 隧道**。后台进程只绑 127.0.0.1，nginx 和阿里云网关都不转发；连上隧道后就是浏览器里的普通网页 | Fan 确认可以用网页展示后选定 |
| D3 | 三个安全问题**先单独修**（切片 0），不等后台 | 未登录也能改教程的漏洞在生产上开着 |
| D4 | 第一个完整切片：**cron 可视化** | 只读、风险低，最适合验证骨架 |
| D5 | 本轮只出设计文档和执行计划，**不写代码** | Fan 2026-09-24 |

## 2. 默认决策（没有单独问，按常规做法定；Fan 可以推翻任何一条）

| # | 默认 | 理由 |
|---|---|---|
| E1 | 后台界面只做中文，不进 i18n | 内部工具，使用者都是中文用户 |
| E2 | 权限只有一级：`users.is_admin`，不做多角色 | 现在只有 1–2 个管理员；有非工程的编辑人员加入时再加「编辑」角色 |
| E3 | 第一版不做双因素登录 | 入口在 SSH 之后（SSH 密钥 + 后台口令），暴露面已经很小 |
| E4 | cron 页第一版**只读**：不做「立即运行 / 暂停」 | 这两项需要后台进程远程控制 cron 进程，是另一件事 |
| E5 | 目标视口 **1440×900**（桌面浏览器） | 四图对比和布局实测都在这个视口下做 |
| E6 | 后台端口 8010；隧道到本机的端口：测试机用 8010，生产用 8011 | 两条隧道可以同时开着，不会混 |
| E7 | 审计日志第一版只记登录成功 / 失败 / 登出，暂不做查看页 | 切片 1 没有写操作；查看页和用户管理切片一起做 |

## 3. 现状（2026-09-24 读代码核实）

- 管理员标志和鉴权已有：`users.is_admin`（`katrain/web/core/models_db.py:83`），`get_current_admin_user`（`katrain/web/api/v1/endpoints/auth.py:155`，服务端模式下只认 `Authorization: Bearer`）。全仓只有计费的两个接口在用它。`/auth/me` 已经返回 `is_admin`，但前端的 User 类型里没声明这个字段。
- 公开应用是 `create_app()`（`server.py:913`，2476 行的工厂，路由都是它内部的闭包），**没有办法只拿一部分出来复用**。以独立进程共享同一个 Postgres 的先例是 `katrain/cron`。
- 建表全靠公开 web 启动时的 `init_db()`：`models_db.Base.metadata.create_all` 加 `migrations.py` 补列补索引（`katrain/web/core/auth.py:118`）。**cron 从来不建表**，它和 web 对同一张表各写一个 ORM 类（例如 `report_tasks`）。
- 测试机上 cron 的镜像**只有 `katrain/cron/`**（`Dockerfile.cron`），由 `tests/web_ui/test_cron_import_boundary.py` 守着；生产上的 cron 跑的是 web 镜像（`CRON_IMAGE`）。
- cron 有 9 个任务：7 个 APScheduler 定时任务（`scheduler.py:34-69`，另外启动时还会立刻各跑一次），2 个常驻循环（直播分析 `analyze`、用户复盘 `report_analyze`）。**没有任何运行记录**。不少任务会吞掉自己的异常（例如 `cleanup.py:103` 的 `except Exception: logger.exception(...)`），所以在外面包一层只能看到「没抛异常」，看不到「失败了」。
- 部署有两套：
  - 测试机 home-ubuntu 用根目录的 `docker-compose.yml`（develop 分支），katrain-web 绑在所有网卡的 8001，阿里云网关经 WireGuard 访问 `10.8.0.2:8001`。
  - 生产 ucloud-v100 用 `deploy/ucloud/compose.yml`（**只存在于 `release/ucloud-20260805` 分支**），katrain-web 绑 `127.0.0.1:8001` 和 `10.8.0.3:8001`。生产的 Dockerfile.web 是 4 阶段构建；`tests/deploy/test_ucloud_artifacts.py` 把服务名写成了**精确集合**，而且要求每个端口只能绑 127.0.0.1 或 10.8.0.3。
- 前端：`vite.config.ts` 只有 galaxy 和 kiosk 两种构建，输出到 `static/` 和 `static-kiosk-2d/`；`eslint.config.js` 有 kiosk / galaxy / 共享区三组导入边界。**根目录 `.gitignore:16` 的 `log*` 加上 `core.ignorecase=true`，会把 `LoginPage.tsx`、`Login.tsx` 静默忽略掉**（`AdminLoginPage.tsx`、`SignInPage.tsx` 不受影响）。`static-admin/` 目前没有被忽略。

## 4. 切片 0：三个安全问题（独立计划，先做）

| 问题 | 位置 | 修法 |
|---|---|---|
| 教程的四个写接口未登录也能调用 | `tutorials.py:150/195/212/232`（改棋盘 / 生成语音 / 改解说 / 审核） | 统一改成 `Depends(get_current_admin_user)`：未登录 401，非管理员 403，guest 403；`changed_by` / `verified_by` 记管理员用户名 |
| `GET /board/devices` 把全部盒子的 IP 返回给任意登录用户 | `board.py:84` | 改成 `get_current_admin_user`。`POST /board/heartbeat` **不动**，那是盒子自己上报用的 |
| 生产上的 `admin/admin` 还能登录（9/6 的记录） | 生产库 | **由 Fan 决定**是改口令还是撤掉 `is_admin`。计划里只给查询和执行命令，不自己动生产库 |

前端改动：`AuthContext` 的 User 类型加上 `is_admin?: boolean`。`TutorialFigurePage` 只对管理员显示以下控件：编辑、逻辑检查、确认审核、初始化空棋盘、编辑模式下的工具条和取消/保存、编辑讲解、生成语音、保存文字、识别调试面板。非管理员看到的是：棋盘、手数滑条、原书页对照、讲解文字、音频、视频。

**这次修复会改变谁能编辑教程**：`tests/web_ui/test_guest_write_block.py` 里的 `test_tutorial_writer_anonymous_still_2xx` 是 box-sso 那次**有意**保留的「未登录可写」（R3-F1），原因应该是 Mac 本机做教程时没有登录。修完以后，Fan 在 Mac 本机、测试机、生产上编辑教程，都需要一个 `is_admin = true` 的账号。计划里有专门一步，先确认各环境的管理员账号，再发布。

隐藏编辑控件会改变右栏里 `railBody` 的高度来源（`BoardPageShell.tsx:186` 的 actions 区域变空）。按 vertical-slice 的反查规则，这会触发承重结构实测：要在最空和会溢出两种内容下各量一次。

## 5. 后台骨架

### 5.1 进程与网络

```
Mac / Windows 浏览器 ── http://localhost:8010 ──▶ ssh -L ──▶ 服务器 127.0.0.1:8010 ── katrain-admin 容器
                                                                               │
                                        （与 katrain-web 共用同一个 Postgres）◀──┘
阿里云网关 ──WireGuard──▶ katrain-web :8001        （网关碰不到 8010）
```

- `katrain-admin` 与 katrain-web 用**同一个镜像**，只是启动命令不同：`python3 -m katrain.web.admin --host 0.0.0.0 --port 8010`（容器内监听所有网卡），主机侧只发布 `127.0.0.1:8010:8010`。**「只绑回环」由端口发布这一层保证**，并各有一条测试守着：develop 的 compose 一条，release 分支的 compose 一条，后者要求 katrain-admin 的 host_ip 只能是 127.0.0.1，连 10.8.0.3 也不行。
- 启动闸（缺一项就拒绝启动）：
  - `KATRAIN_MODE == "server"`，后台绝不在盒子上跑；
  - `assert_secret_key_is_safe("server", SECRET_KEY)`；
  - `KATRAIN_ADMIN_ENV ∈ {local, test, prod}`。
- 后台进程**不调用 `init_db()`**，表结构只由 katrain-web 负责。表还没建出来时，接口返回 503 并说明原因，不要装成「没有数据」。

### 5.2 后端结构

```
katrain/web/admin/
  __init__.py
  __main__.py      # python -m katrain.web.admin：argparse --host（默认 127.0.0.1）/--port（默认 8010）+ uvicorn
  app.py           # create_admin_app(session_factory=None, static_dir=None)
  settings.py      # KATRAIN_ADMIN_ENV 读取与校验 + 启动闸
  session.py       # 后台会话令牌、cookie、require_admin 依赖、CSRF 头校验
  audit.py         # record(db, action, username, admin_user_id=None, detail=None)
  cron_health.py   # derive_health(row, now) 纯函数
  routers/auth.py  # /api/admin/auth/{login,logout,me}
  routers/cron.py  # /api/admin/cron/{jobs,jobs/{name}/runs,queues}
```

新表都定义在 `katrain/web/core/models_db.py` 里，由 katrain-web 启动时的 `create_all` 建：`admin_audit_log`、`cron_job_status`、`cron_job_runs`。cron 侧在 `katrain/cron/models.py` 对后两张表写同名映射（沿用 `report_tasks` 的做法），另有一条测试保证两边的列集合完全一致。

### 5.3 鉴权

- **会话令牌**：用 `settings.SECRET_KEY` 签 HS256 JWT，内容为 `{sub, type:"admin_session", aud:"katrain-admin", env, exp: 8 小时}`。
  - 校验时**必须同时**满足：用 `audience="katrain-admin"` 解码、`type == "admin_session"`、`env == KATRAIN_ADMIN_ENV`。
  - 原因：2026-09-24 实测 python-jose 的行为是，**传了 audience、而 token 里根本没有 aud 时，照样放行**。只靠 aud，公开站点的 access token 就能进后台。
  - 反方向不用改公开站点：公开站点解码时不传 audience，带 aud 的 token 会被 jose 以「Invalid audience」拒掉（同日实测）。
- **cookie**：名字是 `katrain_admin_<env>`，HttpOnly、SameSite=Strict、Path=/、Max-Age 8 小时；**不设 Secure**，因为走的是 SSH 隧道里的 http://localhost。cookie 不按端口隔离，名字里带上 env，两条隧道同时开着也不会互相顶掉。
- **每次请求**都按用户名重新查一次库，并要求 `is_admin = true`，撤权立即生效。
- **CSRF**：所有非 GET 请求（含登录）必须带 `X-Katrain-Admin: 1` 请求头。后台不开 CORS，别的网页（包括本机其他端口）发不出带自定义头的跨源请求。
- **登录失败**只回一句笼统的话：「用户名或密码错误，或该账号没有后台权限」；具体原因（查无此人 / 口令错 / 不是管理员）写进审计日志。
- 不做登录限流：入口在 SSH 之后，想暴力试口令得先有 SSH 权限。

### 5.4 审计日志

`admin_audit_log` 的列：`id`、`created_at`（tz）、`admin_user_id`（登录失败时为空）、`username`、`action`（String 64）、`target`（可空）、`detail`（JSON，可空）。
切片 1 只写 `login_success` / `login_failed` / `logout` 三种。以后每个会产生写操作的切片，都必须调用 `audit.record`。

### 5.5 前端结构与构建隔离

```
katrain/web/ui/
  admin.html               # 后台自己的 HTML 入口
  vite.admin.config.ts     # 输出到 ../static-admin；dev 端口 5174；/api/admin 代理到 127.0.0.1:8010
  src/admin/
    main.tsx  AdminApp.tsx  jobLabels.ts
    api/{client.ts, cronApi.ts, types.ts}
    pages/{SignInPage.tsx, CronPage.tsx}      # 不许叫 Login*（会被 .gitignore 吞掉）
    components/{AdminShell.tsx, HealthChip.tsx, RunHistoryDrawer.tsx}
```

- 新增 `npm run dev:admin` 和 `npm run build:admin`，**不改动现有的 `vite.config.ts`**。kiosk 的构建依赖它，零改动就零风险。vitest 仍然用原来的配置跑全树测试。
- ESLint 边界：`src/admin/**` 不许导入 `src/kiosk/**`；kiosk、galaxy/pages/ZenModeApp、共享区都不许导入 `**/admin/**`。
- `.gitignore` 加一行 `katrain/web/static-admin/`，必须在第一次构建前加。
- **有意不做**：没有给公开包再加一条「构建产物里不许有后台代码」的 grep 闸。后台 JS 就算漏进公开包，泄露的也只是界面代码：后台接口在公网上不存在，数据拿不到。ESLint 边界加上两个入口物理分开，已经够用。
- 主题：复用 `src/theme.ts` 的 `zenTheme`，字体栈用 `src/galaxy/theme.ts` 的中文字体 `CHINESE_UI_FONT`。具体视觉方向在切片 1 第 1 步按 frontend-design → ui-ux-pro-max 定。
- 页头要显著显示当前环境（测试 / 生产 / 本机，颜色区分），防止两条隧道都开着时在生产上误操作。

### 5.6 部署

**测试机（develop，根目录 `docker-compose.yml`）**
- katrain-web 加上 `image: katrain-web:local`。新增服务 `katrain-admin`：`image: katrain-web:local`，不写 build，启动命令同上，端口 `127.0.0.1:8010:8010`，数据库和密钥等环境变量与 katrain-web 一致，另加 `KATRAIN_ADMIN_ENV=test`。
- develop 的 `Dockerfile.web` 在 `npm run build` 后面加 `&& npm run build:admin`。
- `server-deploy` skill 的第 7 步改成 `docker compose up -d --build katrain-web katrain-cron katrain-admin`。

**生产（`release/ucloud-20260805`）**
- `Dockerfile.web` 的 ui-builder 阶段加上 `npm run build:admin`；runtime 阶段 `COPY --from=ui-builder /src/static-admin /app/katrain/web/static-admin`；source-pruner 的删除列表加 `static-admin`。
- compose 新增 `katrain-admin`：`profiles: [production]`，`image: ${WEB_IMAGE}`，user 10001，**端口只绑 `127.0.0.1:8010:8010`**，healthcheck 打 `/api/admin/health`，mem 1g / cpu 1，日志上限与其他服务相同，依赖 postgres 健康。
- 同步修改 `test_ucloud_artifacts.py`：服务集合、生产比预览多出的服务、绑定检查（admin 只能是 127.0.0.1）、长期服务的配置检查、镜像不可变检查。
- `build-web.sh` 的冒烟检查加两项：能 import `katrain.web.admin.app`；`static-admin/admin.html` 存在。
- 发布走现有的手工流程：合并 develop → clone 到 release 目录 → `build-web.sh` → pg_dump 备份并实际恢复验证 → preflight → 改 env（**`WEB_IMAGE` 和 `CRON_IMAGE` 都要换**，因为 cron 代码改了）→ 切换 current 软链 → `up -d katrain-web katrain-cron katrain-admin`。
- 顺序：**先测试机，再生产**（Fan 2026-08-31 定的规矩）。

### 5.7 访问方式

新增运维文档 `docs/operations/admin-console-access.md`，内容：
- Mac：`ssh -N -L 8010:127.0.0.1:8010 home-ubuntu` 后打开 http://localhost:8010；生产用 `ssh -N -L 8011:127.0.0.1:8010 ucloud-v100` 后打开 http://localhost:8011。
- Windows：PowerShell 里执行同样的命令（Windows 10/11 自带 OpenSSH），可以做成双击运行的 `.bat`。
- 给工作人员开**只能转发、不能登录 shell** 的 SSH 账号：账号 shell 设为 `/usr/sbin/nologin`，`authorized_keys` 里写 `restrict,port-forwarding,permitopen="127.0.0.1:8010" ssh-ed25519 …`。测试机要先经阿里云跳板机，工作人员在跳板机上也需要一个同样受限的账号。第一版只有 Fan 自己用，这部分写成「需要时照做」。

## 6. 切片 1：cron 可视化

### 6.1 用户旅程

管理员打开隧道，进入 http://localhost:8010，登录后落在「定时任务」页，看到：
- cron 进程是否活着；
- 9 个任务各自的健康状态、上次运行时间、耗时、连续失败次数、最后一条报错；
- 直播分析队列和复盘队列的积压情况。

点开任意一个任务，可以看到它最近的运行历史和完整报错。页面每 15 秒自动刷新。

### 6.2 数据：两张新表

`cron_job_status`（每个任务一行，主键 `job_name`）：

| 列 | 类型 | 说明 |
|---|---|---|
| job_name | String(64) PK | 与 `BaseJob.name` 一致 |
| kind | String(16) | `interval` / `loop` |
| interval_seconds | Integer，可空 | loop 为空 |
| enabled | Boolean | 被配置停用的任务也登记，页面上显示「已停用」 |
| process_started_at | DateTime(tz) | 本次 cron 进程的启动时间 |
| heartbeat_at | DateTime(tz) | cron 进程每 30 秒写一次，判断进程是否活着 |
| last_started_at / last_finished_at / last_success_at | DateTime(tz)，可空 | |
| last_status | String(16)，可空 | `running` / `success` / `errors` / `failed` |
| last_duration_ms | Integer，可空 | |
| last_error | Text，可空 | 截断到 2000 字符 |
| consecutive_failures | Integer，默认 0 | `failed` 或 `errors` 加一，`success` 清零 |
| loop_iteration_at | DateTime(tz)，可空 | 只有 loop 用：最近一次循环推进的时间 |
| loop_stats | JSON，可空 | 只有 loop 用：`{in_flight, capacity, errors_total, last_error_at}` |
| updated_at | DateTime(tz) | |

`cron_job_runs`（运行历史）：`id` PK、`job_name`（索引）、`started_at`（索引）、`finished_at`、`status`、`duration_ms`、`error_count`、`error`（Text，截断）。另建复合索引 `(job_name, started_at)`。

写入策略：
- 间隔 ≥ 60 秒的任务，**每次运行**都写一行：开始时写 `running`，结束时更新。
- 间隔 < 60 秒的任务（目前只有 `poll_moves`，3 秒一次），**只在不成功时**写一行。
- loop 只有崩溃重启时写一行 `failed`。
- 量级：约 2,500 行/天，保留 14 天，约 3.5 万行。
- 状态行每次运行都更新（poll_moves 相当于每 3 秒一次 UPDATE，对 PG 来说可以忽略）。

### 6.3 cron 侧的记录方式（`katrain/cron/run_recorder.py`）

- **只依赖标准库、sqlalchemy 和 `katrain.cron.*`**，由现有的 `test_cron_import_boundary.py` 自动把关。
- **错误捕获**：在根 logger 上挂一个级别为 ERROR 的 `logging.Handler`，配合 `contextvars.ContextVar` 标记「当前是哪个任务在跑」。任务运行期间任何地方打出的 ERROR 日志都会记到这次运行上，包括第三方 client 模块的 logger，以及任务内部 `create_task` 派生出来的子任务（它们会继承 context）。这样，任务把异常吞掉之后，页面也能显示「有报错」，而不是「成功」。
- **定时任务**：`_run_job_once(job)` 和 `add_job(...)` 的回调都换成 `recorder.run(job)`。执行顺序是：先写「开始」→ 设置 context → `await job.run()` → 复位 context → 写「结束」。记录器自己的写库**放在 context 之外**，所以它自己的报错不会记到任务头上。状态判定：异常逃出任务是 `failed`；跑完了但期间有 ERROR 日志是 `errors`；否则是 `success`。
- **常驻循环**：`AnalyzeJob` 和 `ReportAnalyzerJob` 在每次循环开头更新 `self.last_iteration_at`，并各加一个 `heartbeat_stats()` 方法，返回在途数和容量。`_run_analyze_loop` 给整个循环设置 context，循环里的 ERROR 日志累计到这个循环的统计里；`job.run()` 抛出异常就记一行 `failed`。
- **心跳**：调度器里单开一个 asyncio 任务，每 `CRON_HEARTBEAT_INTERVAL`（30 秒）为所有已登记的任务写一次 `heartbeat_at`。loop 任务顺带写入 `loop_iteration_at`、`loop_stats` 和 `last_error`。
- **登记**：进程启动时，把 9 个任务（包括被停用的）全部 upsert 一遍，并**删掉**名字已不在当前代码里的旧行，免得改名后留下一行永远显示「失联」的假记录。
- **记录器写库失败时**：记一条 WARNING 日志，绝不影响任务本身。后果是心跳过期、页面显示「失联」，失败就这样自然暴露出来，不会被藏住。
- **时间**：一律用 `datetime.now(timezone.utc)`。
- **保留期**：`CleanupJob` 删除 `CRON_RUNS_RETENTION_DAYS`（默认 14 天）之前的运行记录。
- **已知的小重叠**：启动时的那一次立即运行，和 APScheduler 的第一次定时运行，理论上可能重叠（`max_instances` 只管 APScheduler 自己发起的运行）。后果只是状态行被更新两次，不影响正确性，接受。

### 6.4 健康状态判定（后台侧的纯函数，自上而下，命中即停）

| 状态 | 页面标签 | 条件 |
|---|---|---|
| offline | 失联 | 现在 − heartbeat_at > 120 秒 |
| disabled | 已停用 | enabled = false |
| pending | 等待首次运行 | interval：last_started_at 为空；loop：loop_iteration_at 为空 |
| stuck | 卡住 | interval：last_status = running，且已运行超过 max(3×间隔, 600 秒)；loop：现在 − loop_iteration_at > 300 秒 |
| running | 运行中 | interval：last_status = running |
| failed | 失败 | last_status = failed |
| errors | 有报错 | interval：last_status = errors；loop：最近 10 分钟内有 ERROR |
| overdue | 该跑没跑 | interval：现在 − last_started_at > 2×间隔 + 60 秒 |
| ok | 正常 | 以上都不满足 |

SQLite 里的 DateTime 不带时区（测试用的是 SQLite），所以判定函数把不带时区的时间一律当 UTC 处理；接口输出的时间统一是带时区的 ISO 字符串。

### 6.5 后台 API 契约（切片 1 第 4 步定稿）

```
GET  /api/admin/health            → 200 {"status":"ok","env":"test"}（不需登录，给 compose healthcheck 用）
POST /api/admin/auth/login        body {username,password}；头 X-Katrain-Admin: 1
                                  → 200 {"username","env"} + Set-Cookie | 401 {"detail":"用户名或密码错误，或该账号没有后台权限"} | 403 缺 CSRF 头
POST /api/admin/auth/logout       → 204，清除 cookie
GET  /api/admin/auth/me           → 200 {"username","env"} | 401
GET  /api/admin/cron/jobs         → 200 {"observed_at", "jobs":[{name, kind, interval_seconds, enabled,
                                          health:{state, reason}, process_started_at, heartbeat_at,
                                          last_started_at, last_finished_at, last_success_at, last_status,
                                          last_duration_ms, last_error, consecutive_failures,
                                          loop_iteration_at, loop_stats}]}
                                  | 503 {"detail":"cron 状态表不存在：katrain-web 新版本还没启动过"}
GET  /api/admin/cron/jobs/{name}/runs?limit=50&before_id=
                                  → 200 {"runs":[{id, started_at, finished_at, status, duration_ms, error_count, error}],
                                         "next_before_id": int|null} | 404 任务不存在；limit 上限 200
GET  /api/admin/cron/queues       → 200 {"observed_at",
                                         "live_analysis":{"by_status":{…},"oldest_pending_at"},
                                         "report_tasks":{"by_status":{…},"oldest_pending_at"}}
```
- 权威边界：状态数据由 cron 进程写、后台只读；`health` 由后台根据 `observed_at` 当场算出；任务的中文名放在前端的 `jobLabels.ts`，遇到不认识的名字就直接显示原名。
- 所有需要登录的接口，没有会话都回 401，前端统一跳回登录页。

### 6.6 页面（按 vertical-slice 七步循环）

1. **设计稿**：先用 frontend-design 定方向，再用 ui-ux-pro-max 补细节，做成 Artifact。覆盖以下屏：登录页、外壳（页头显示环境、左侧导航只有「定时任务」、页头右侧是用户和登出）、定时任务页。定时任务页要画出这些状态：全部正常、有失败任务、cron 失联、接口出错、表不存在、运行历史抽屉（200 条）。**Fan 确认后才进入下一步**。
2. **Fixture 前端**：假数据只放在 `src/admin/__fixtures__/`，由 `VITE_ADMIN_FIXTURE=true` 打开，生产构建时通过 DCE 去掉。**删除条件**：第 6 步接上真实接口、第 7 步验收通过后，在同一个提交里删除。
3. **四图对比 + 承重实测**：视口 1440×900。承重实测包括：运行历史列表灌 200 条后能滚、滚轮能拨动、不被祖先裁掉；主区域灌 30 个任务后能滚；0 个任务时不塌陷。**Fan 确认后才进入下一步**。
4. **契约**：按 6.5 定稿，写成 TS 类型和 pydantic 响应模型。
5. **后端**：6.2、6.3、6.4 和 6.5。
6. **集成**：本机真实起一套 web + cron + admin，页面接真实数据。
7. **验收**：自动化测试、真实浏览器验收、删除 fixture。然后部署（先测试机，再生产）。

### 6.7 状态诚实

- 加载中显示骨架。
- 接口出错时：显示错误条，写明状态码和原因，保留上一次的数据，但标成「数据停在 HH:MM:SS」。
- 表不存在时（503）：原样显示原因。
- cron 失联时：全部任务显示「失联」，**不再显示**上一次的「正常」。
- 没有登记任何任务时：空态写明「cron 进程还没上报过，可能新版 cron 还没部署」。

## 7. 测试策略（相称）

- **切片 0**：四个接口和盒子列表，各覆盖未登录 401、非管理员 403、guest 403、管理员 200；更新 `test_guest_write_block.py` 和 `test_tutorial_db_api.py` 里原来锁定旧行为的用例；前端加一条「非管理员看不到编辑控件、仍能看到讲解和音频」；右栏承重实测。
- **骨架**：
  - 公开应用的 openapi 里**没有任何** `/api/admin` 路径，这是核心隔离性质；
  - 后台在 board 模式、弱密钥、未知 env 这三种情况下都拒绝启动；
  - 会话：带公开站点的 access token 访问后台必须 401（守住 jose 的那个行为）；缺 CSRF 头 403；撤掉 is_admin 后下一次请求 401；
  - compose：develop 与 release 两边，katrain-admin 的端口都只绑 127.0.0.1。
- **cron**：
  - 记录器：吞掉异常的任务记为 `errors`；抛出异常记为 `failed`；记录器写库失败不影响任务；间隔 < 60 秒的成功运行不写历史；
  - 两边的模型列集合一致；
  - `derive_health` 表驱动测试，覆盖每个状态各一例，外加不带时区的时间；
  - 三个接口的返回结构和 401。
- 前端只测行为：401 跳回登录；接口出错时显示错误条并保留旧数据。布局相关的一律交给真实浏览器实测，不写 jsdom 的几何断言。
- 基线对比：新增的失败按**测试名**和基线比，不按条数比。

## 8. 这一轮不做的事

双因素登录、多角色、以用户身份登录（模拟登录）、cron 的立即运行 / 暂停、审计日志查看页、后台 i18n、把计费那两个 admin 接口搬进后台（留到计费切片）、公开包的后台代码 grep 闸（理由见 5.5）。

## 9. 风险与对策

| 风险 | 对策 |
|---|---|
| 切片 0 发布后，Fan 自己没法编辑教程了 | 发布前先确认各环境的管理员账号（计划里有专门一步，要 Fan 决定） |
| 合并 develop 到 release 时 `Dockerfile.web` 冲突（两边是完全不同的两份） | 冲突按 release 的版本解决，再手工加上 build:admin 和 COPY 两处；计划里写明 |
| cron 在 web 建表之前启动，写入失败 | 记录器吞掉写库错误，下次重试；web 启动建表后自动恢复 |
| 撞上 `log*` 忽略规则，新文件没进 git | 文件名避开 log 开头；每个任务提交后用 `git show --stat` 核对文件清单 |
| 生产 compose 的精确集合测试挡住新服务 | 计划里明确列出要改的每一条断言 |

## 10. 后续模块（各自单独出设计和计划）与待定问题

后续顺序（建议）：
1. 性能监控（嵌入 Grafana / Netdata）
2. 教程工作台迁入（**待定：权威库放哪台**）
3. 金镜像制品库（**待定：存放位置，以及 N100 与存储之间的网络**）
4. 用户与计费（包括审计查看页，以及把计费两个 admin 接口迁入）
5. YOLO 数据集
6. 盒子设备页（**前提：要先把心跳接上**，目前 katrain 和 smartbox 两个仓里都没有调用方）
7. 配置体检页
8. 报错追踪与告警
