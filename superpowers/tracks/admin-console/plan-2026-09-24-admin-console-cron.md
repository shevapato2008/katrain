# 管理后台骨架 + cron 可视化（旧切片 1）Implementation Plan

> **更新提示（2026-09-24）**：教程管理现为第一个完整模块，后台账号独立于公开 `users` 表。本计划中的任务顺序和鉴权实现不得直接执行；见 [教程优先计划](./plan-2026-09-24-admin-tutorial-first.md)。cron 的记录器、健康判定等局部设计可在教程切片完成后复用，每个 🛑 用户确认和发布授权仍保留。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建一个独立进程的管理后台 katrain-admin（只绑 127.0.0.1，经 SSH 隧道访问），第一个完整功能是 cron 任务可视化：进程死活、9 个任务的健康状态、运行历史、两条分析队列。

**Architecture:**
- 后台是 katrain 仓里的新包 `katrain/web/admin/`，与 katrain-web 用同一个镜像、另一条启动命令，共用同一个 Postgres。它不建表，表由 katrain-web 的 `create_all` 建。
- 前端是 `katrain/web/ui/src/admin/` 下单独的 Vite 入口，输出到 `katrain/web/static-admin/`，不进公开包，也不进 kiosk 包。
- cron 侧新增 `katrain/cron/run_recorder.py`，负责把每次运行、心跳、运行期间的 ERROR 日志写进两张新表，后台只读展示。
- 顺序遵守 vertical-slice：设计稿 → 假数据前端 → 四图对比，**Fan 确认** → 契约 → 后端 → 集成 → 验收。

**Tech Stack:** FastAPI 0.115 + SQLAlchemy 2 + python-jose + APScheduler 3；React 19 + MUI 7 + react-router 6（HashRouter）+ Vite 8 + vitest 4 + Playwright。

**Spec:** `superpowers/tracks/admin-console/spec-2026-09-24-admin-console.md`（§5 骨架，§6 cron 可视化）

## Global Constraints

- 后台 API 前缀 `/api/admin`，端口 8010。`KATRAIN_ADMIN_ENV ∈ {local, test, prod}`。
- 会话令牌放在前端的 localStorage（键 `katrain_admin_token`），每次请求带 `Authorization: Bearer <令牌>`，8 小时过期；关标签页、重启浏览器都保持登录（Fan 2026-09-24 定，spec E8）。storage 能用时，前端不在内存里另存令牌：否则别的标签页点了「登出」，这一页还会拿旧令牌接着用。**后台不用 cookie**：cookie 不按端口隔离，本机任何一个被同一浏览器打开过的 localhost 服务都能拿到它（spec §5.3）。
- 后台的每个响应都带 CSP（`script-src 'self'`、`connect-src 'self'`、`frame-ancestors 'none'` 等）：令牌在 localStorage 里，页面上万一出现注入，也发不出令牌。
- 会话令牌的内容是 `{sub, type:"admin_session", aud:"katrain-admin", env, exp}`，校验时 **type、aud、env 三项都要查**。
- cron：心跳 30 秒一次；超过 120 秒没有心跳算失联；loop 超过 300 秒没有推进算卡住；运行历史保留 14 天；间隔 ≥ 60 秒的任务每次运行都记历史，更频繁的只记不成功的。
- `katrain/cron/**` 只许 import 标准库、sqlalchemy 和 `katrain.cron.*`（由 `tests/web_ui/test_cron_import_boundary.py` 守着）。
- 后台进程不调用 `init_db()`；新表都定义在 `katrain/web/core/models_db.py` 里，cron 侧写同名映射。
- 目标视口 1440×900；后台界面只做中文；文件名不许以 `log` 开头（登录页叫 `SignInPage.tsx`）。
- **Task 3 的四图对比经 Fan 明确确认之前，不做任何后端任务（Task 4 起）**。这是 Fan 定的硬性关卡。
- 只在 worktree `~/Repositories/katrain-admin-console`（分支 `feature/admin-console`）里工作，不碰共享主工作树的分支。
- 推送、部署、写生产库，**执行当下**都要 Fan 点头。先测试机，再生产。
- 提交信息末尾加 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`。
- 带管道的检查命令先写 `set -o pipefail`，否则退出码是 `tail` 的，失败也显示成功（release runbook 2026-09-23 记过这种事故）。生产上的发布命令一律不接管道。
- 本机 shell 是 zsh：不做词分割；`$VAR:t…` 会被当成路径修饰符，要写成 `${VAR}:…`。
- 执行者每次调用 Bash、每次 `ssh` 都是新 shell，变量留不到下一步。跨步骤要用的值（端口、PID、SHA、镜像 ID、时间戳）写进文件，或者在每条命令里写成字面量。
- 判断「有没有弄坏」一律用 Task 2 Step 1 写的 `newfail.sh`（pytest）和 `vitestnewfail.sh`（vitest），按用例名字和基线比。跑测试之前 `katrain/config.json` 必须是干净的（Task 2 Step 1 核对）：测试会改写这个已提交的文件，事后要还原，而还原会连带冲掉测试之前就有的改动。
- Task 8 起，本 worktree 里同步 Python 依赖一律写 `uv sync --extra web --extra cron`：APScheduler、beautifulsoup4、lxml 原先只写在 `requirements-cron.txt` 里，Task 8 把它们加成 `cron` extra；只写 `--extra web` 会把它们卸掉。
- 变异检查（亲眼看一条闸红一次）：改之前先 `cp` 备份被改的文件；跑测试时加 `PYTHONDONTWRITEBYTECODE=1`，同一秒内等长的改动和还原会让 Python 读到陈旧的 .pyc；用备份还原。**不要用 `git checkout` 还原**：这时本任务的改动还没提交，会被一起冲掉。

## Review Focus

- cron 进程被 SIGKILL 或 OOM 杀掉，来不及写任何东西：2 分钟内页面必须变成「失联」，不能停在最后一次的「正常」；重启之后，被打断的那次运行在历史里是「失败」，不是永远「运行中」→ Task 9 的 offline 用例、Task 7 的 `test_register_closes_runs_left_running_by_a_process_that_died`，加上 Task 12 的实停验证。
- cron 比 katrain-web 先启动（两边同时 `up`，表还没建）：web 建好表之后，下一次心跳就要把 9 行状态补上，不能一直空到下次重启 → Task 7 的 `test_heartbeat_fills_in_rows_when_the_table_appeared_after_register`。
- 任务吞掉了异常、只打了一条 ERROR 日志（cleanup.py 的写法）：必须显示「有报错」，不能显示「成功」→ Task 7 的 `test_a_job_that_swallows_its_exception_is_recorded_as_errors_not_success`。
- 同一个浏览器里同时开着测试和生产两条隧道，或者本机另一个端口上跑着别的服务：后台会话不能串号，也不能被那个服务拿到。令牌只放在按端口隔离的 localStorage 里，登录不设任何 cookie → Task 6 的 `test_login_returns_a_token_and_sets_no_cookie`、`test_token_for_other_env_is_rejected`，Task 2 `client.test.ts` 的 Authorization 用例，外加 `SignInPage.test.tsx` 的环境标签。
- 同一个浏览器开着两个后台标签页，在其中一个点「登出」：另一个的下一次请求必须回到登录页，不能拿内存里的旧令牌接着用 → Task 2 `client.test.ts` 的「别的标签页登出」用例。
- 管理员登录期间被撤掉权限：下一次请求就必须回到登录页 → Task 6 的 `test_revoking_is_admin_takes_effect_on_next_request`。

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `katrain/web/core/models_db.py` | 改（末尾追加） | `AdminAuditLog`、`CronJobStatus`、`CronJobRun` 三张表（web 侧是建表方） |
| `katrain/cron/models.py` | 改（末尾追加） | `CronJobStatusDB`、`CronJobRunDB`（cron 侧写入用，同名映射） |
| `katrain/cron/run_recorder.py` | 新建 | 运行记录、ERROR 捕获、心跳、loop 统计 |
| `katrain/cron/scheduler.py` | 改 | 所有运行都经过记录器；启动时登记；心跳任务 |
| `katrain/cron/jobs/analyze.py`、`report_analyze.py` | 改 | `last_iteration_at` + `heartbeat_stats()` |
| `katrain/cron/jobs/cleanup.py`、`katrain/cron/config.py` | 改 | 清理运行历史；两个新配置 |
| `pyproject.toml`、`uv.lock`、`requirements-cron.txt` | 改 | 新增 `cron` extra（APScheduler 3.x、bs4、lxml），本地才跑得了 cron 和调度器测试 |
| `katrain/web/admin/__init__.py`、`__main__.py`、`app.py`、`settings.py` | 新建 | 后台进程、启动闸、静态文件、SPA 兜底 |
| `katrain/web/admin/session.py`、`audit.py`、`routers/__init__.py`、`routers/auth.py` | 新建 | 会话（Bearer，不用 cookie）、登录/登出/me、审计 |
| `katrain/web/admin/cron_health.py`、`routers/cron.py` | 新建 | 健康判定、三个只读接口 |
| `katrain/web/ui/admin.html`、`vite.admin.config.ts` | 新建 | 后台自己的入口和构建配置 |
| `katrain/web/ui/src/admin/**` | 新建 | 后台前端 |
| `katrain/web/ui/package.json`、`eslint.config.js`、根目录 `.gitignore` | 改 | 脚本、导入边界、忽略构建产物 |
| `docker-compose.yml`、`Dockerfile.web`、`.claude/skills/server-deploy/SKILL.md` | 改 | 测试机部署 |
| `docs/operations/admin-console-access.md` | 新建 | 隧道访问方式、工作人员的受限账号 |
| `tests/web_ui/test_admin_*.py`、`test_cron_run_recorder.py`、`test_cron_status_tables_parity.py`、`_admin_helpers.py`；`tests/test_admin_compose.py` | 新建 | 测试 |
| release 分支：`Dockerfile.web`、`deploy/ucloud/compose.yml`、`deploy/ucloud/scripts/build-web.sh`、`tests/deploy/test_ucloud_artifacts.py` | 改（Task 15） | 生产部署 |

---

### Task 1: 设计稿（Artifact）—— 🛑 Fan 确认后才能进入 Task 2

**Files:**
- Create：`superpowers/tracks/admin-console/slice1/design/admin-cron-design.html`（自包含的本地设计稿，参考图只从它截）
- Create：`superpowers/tracks/admin-console/slice1/reference/{signin,ok,mixed,offline,error,missing,empty,drawer}.png`（1440×900 参考图）
- Create：`superpowers/tracks/admin-console/slice1/design-notes.md`（设计方向、配色、字号、状态色，以及 Artifact 链接）
- Create（临时，不提交）：`katrain/web/ui/tests/admin-reference.shoot.spec.ts`

**Interfaces:**
- Produces：8 张参考图，文件名就是状态名。Task 3 的实现截图用同样的 8 个文件名，一一对应
- Produces：本地设计稿的约定：用 `?state=<状态>` 切换，并把当前状态写到 `<body data-state="<状态>">` 上。截图前回读它，确认切到了对的屏
- Produces：`design-notes.md` 里确认过的视觉取值。Task 2 的 `theme.ts` 和 Step 13 的对齐都以它为准

- [ ] **Step 1：装前端依赖**（参考图要用 Playwright 截，worktree 里是空的）

Run：`cd /Users/fan/Repositories/katrain-admin-console/katrain/web/ui && npm ci`
Expected：`added N packages`，没有 `ERR!`。之后 Playwright 如果报 `Executable doesn't exist`，执行一次 `npx playwright install chromium`。

- [ ] **Step 2**：调用 `frontend-design` skill 定审美方向。输入：
  - 这是内部运维后台，延续站点的 zen 深色基调：`src/theme.ts` 的底色 #0f0f0f、面板 #252525、文字 #f5f3f0 / #b8b5b0、主色玉绿 #4a6b5c；
  - 信息密集的表格，界面全中文，数字用等宽数字；视口 1440×900；
  - 页头必须显著标出环境（本机 / 测试 / 生产），生产要最醒目。
- [ ] **Step 3**：调用 `ui-ux-pro-max` 补细节：九种健康状态（正常 / 运行中 / 有报错 / 该跑没跑 / 失败 / 卡住 / 失联 / 已停用 / 等待首次运行）的配色语义、表格密度、抽屉宽度、中文与数字混排的字体。
- [ ] **Step 4：做设计稿**。先按 Artifact 工具的要求调用 `quickstart`（intent: `design`），按它返回的类型做一份给 Fan 看的设计稿并发布；同时在 `superpowers/tracks/admin-console/slice1/design/admin-cron-design.html` 存一份自包含的本地 HTML（不引用任何网络资源），参考图只从这一份截。本地 HTML 用 `?state=` 切换下列状态，并执行 `document.body.dataset.state = state`：
  - `signin`：登录页，带环境标签；
  - `ok`：全部正常；
  - `mixed`：包含失败、有报错、该跑没跑、已停用、运行中；
  - `offline`：cron 失联；
  - `error`：刷新时接口返回 502，错误条写明状态码和原因（`502 Bad Gateway`）以及「页面数据停在 HH:MM:SS」，表格保留上一次的数据；
  - `missing`：错误条写 `503` 加原因（表不存在）；
  - `empty`：cron 还没上报过；
  - `drawer`：打开 fetch_list 的运行历史，已加载 200 条，列表停在顶部。

  数据形状必须与 spec §6.5 的接口契约一致。把 Artifact 链接写进 `design-notes.md`。

- [ ] **Step 5：按 1440×900 截 8 张参考图**

写一次性的截图脚本 `katrain/web/ui/tests/admin-reference.shoot.spec.ts`：
```ts
// One-off, not committed. run from katrain/web/ui:
//   npx playwright test --config=playwright.vite.config.ts tests/admin-reference.shoot.spec.ts
import path from 'node:path';
import { test, expect } from '@playwright/test';

const SLICE = path.resolve('../../../superpowers/tracks/admin-console/slice1'); // relative to katrain/web/ui
const STATES = ['signin', 'ok', 'mixed', 'offline', 'error', 'missing', 'empty', 'drawer'];

for (const state of STATES) {
  test(`reference ${state}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`file://${SLICE}/design/admin-cron-design.html?state=${state}`);
    // Read back which state is on screen: a failed switch produces the same kind of picture as a successful one.
    await expect(page.locator('body')).toHaveAttribute('data-state', state);
    await page.screenshot({ path: `${SLICE}/reference/${state}.png` });
  });
}
```
```bash
set -o pipefail
cd /Users/fan/Repositories/katrain-admin-console/katrain/web/ui
mkdir -p ../../../superpowers/tracks/admin-console/slice1/reference
npx playwright test --config=playwright.vite.config.ts tests/admin-reference.shoot.spec.ts --reporter=line 2>&1 | tail -5
rm tests/admin-reference.shoot.spec.ts
ls ../../../superpowers/tracks/admin-console/slice1/reference
```
Expected：`8 passed`，目录里正好 8 张 png。有哪一态失败，就是设计稿没切到那一屏：修设计稿再截，不许跳过。

- [ ] **Step 6：提交设计稿、参考图和说明**
```bash
set -o pipefail
cd /Users/fan/Repositories/katrain-admin-console
git add superpowers/tracks/admin-console/slice1/
git commit -m "design(admin): cron 可视化设计稿参考图（1440×900，8 态）

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git show --stat HEAD | tail -12
```
- [ ] **Step 7：🛑 停。把 Artifact 链接发给 Fan。他明确确认之后才能进入 Task 2。改动意见在本任务内反复迭代：改设计稿 → 重跑 Step 5 → 重新提交。**

---

### Task 2: 前端入口 + 假数据跑通整个界面（不接后端）

**Files:**
- Create：`katrain/web/ui/admin.html`、`katrain/web/ui/vite.admin.config.ts`
- Modify：`katrain/web/ui/package.json`（`scripts`）、`katrain/web/ui/eslint.config.js`、根目录 `.gitignore`（第 53 行之后）
- Create：`katrain/web/ui/src/admin/{main.tsx, AdminApp.tsx, theme.ts, session.tsx, envLabel.ts, jobLabels.ts, format.ts}`
- Create：`katrain/web/ui/src/admin/api/{client.ts, types.ts, authApi.ts, cronApi.ts}`
- Create：`katrain/web/ui/src/admin/pages/{SignInPage.tsx, CronPage.tsx}`、`katrain/web/ui/src/admin/components/{AdminShell.tsx, HealthChip.tsx, QueueCards.tsx, RunHistoryDrawer.tsx}`
- Create（**FIXTURE**，Task 13 删除）：`katrain/web/ui/src/admin/__fixtures__/cronFixture.ts`
- Test：`katrain/web/ui/src/admin/api/client.test.ts`、`src/admin/pages/CronPage.test.tsx`、`src/admin/pages/SignInPage.test.tsx`、`src/admin/components/RunHistoryDrawer.test.tsx`
- 不提交：`.superpowers/baseline/cron_slice_failed_before.txt`、`newfail.sh`、`vitestnewfail.sh`、`vitest_failed_before.txt`（Step 1 生成；之后每次「有没有弄坏」都用它们，Task 13 做最后一次全量对比）

**Interfaces:**
- Produces（TS 契约，Task 3 定稿，Task 10 的后端必须与之一致）：`src/admin/api/types.ts` 里的 `AdminEnv`、`AdminMe`、`AdminLogin`、`HealthState`、`RunStatus`、`CronJob`、`CronJobsResponse`、`CronRun`、`CronRunsResponse`、`QueueSummary`、`CronQueuesResponse`
- Produces：`adminFetch<T>(path, init?)`（有令牌就带 `Authorization: Bearer`，从不带 cookie）、`getToken()` / `setToken(token)` / `clearToken()`（localStorage 键 `katrain_admin_token`；只有 storage 被禁用时才退回内存）、`errorText(e)`、`AdminAuthError(message?)`、`AdminApiError(status, message)`
- Produces：data-testid `admin-env`、`admin-main`、`cron-error`、`cron-loading`、`cron-empty`、`cron-process`、`cron-table`、`cron-row-<name>`、`health-<state>`、`queue-live`、`queue-report`、`run-history-scroll`、`signin-env`

- [ ] **Step 1：改任何代码之前：装 Python 依赖，确认 `katrain/config.json` 是干净的，记录两份基线，写好「只报新增失败」的小脚本**（切片 0 已在这个 worktree 里装过依赖时，`uv sync` 很快结束）

```bash
cd /Users/fan/Repositories/katrain-admin-console
uv sync --extra web
git check-ignore -q .superpowers/baseline/x && echo ignored-ok   # 根目录 .gitignore:208 忽略了 .superpowers/
git diff --quiet -- katrain/config.json && echo config-clean
B=/Users/fan/Repositories/katrain-admin-console/.superpowers/baseline; mkdir -p $B
CI=true uv run pytest tests/web_ui -q -p no:cacheprovider --continue-on-collection-errors -rfE > $B/cron_slice_before.log 2>&1; echo "pytest exit=$?"
tail -1 $B/cron_slice_before.log
grep -E '^(FAILED|ERROR) ' $B/cron_slice_before.log | sed -E 's/ - .*//' | sort -u > $B/cron_slice_failed_before.txt
wc -l < $B/cron_slice_failed_before.txt
cat > $B/newfail.sh <<'SH'
#!/usr/bin/env bash
# 用法（在 worktree 根目录）：bash .superpowers/baseline/newfail.sh <基线文件> <pytest 参数…>
# 跑 pytest，只报基线里没有的失败。有新增失败 → 退出码 1；pytest 本身没跑成（中断、内部错误、用法错误、
# 一条都没收集到，或者没跑到 summary）→ 退出码 2。
set -uo pipefail
base="$1"; shift
log=$(mktemp)
CI=true uv run pytest "$@" -q -p no:cacheprovider -rfE > "$log" 2>&1
rc=$?
tail -1 "$log"
[ "$rc" -le 1 ] || { echo "!! pytest 退出码 $rc，日志在 $log"; exit 2; }
tail -1 "$log" | grep -qE '[0-9]+ (passed|failed|errors?)' || { echo "!! pytest 没有跑到 summary，日志在 $log"; exit 2; }
new=$(grep -E '^(FAILED|ERROR) ' "$log" | sed -E 's/ - .*//' | sort -u | comm -13 "$base" -)
[ -z "$new" ] && exit 0
echo "!! 新增失败："; echo "$new"; exit 1
SH
cat > $B/vitestnewfail.sh <<'SH'
#!/usr/bin/env bash
# 用法（在 worktree 根目录）：
#   bash .superpowers/baseline/vitestnewfail.sh --record <基线文件>   记下当前失败的用例名（改前端之前跑一次）
#   bash .superpowers/baseline/vitestnewfail.sh <基线文件>            只报基线里没有的失败：有 → 退出码 1
# vitest 本身没跑成（退出码不是 0/1、没生成报告、报告里一条用例都没有）→ 退出码 2。
# 报告每次写进新的临时文件，不会读到上一次留下的。
set -uo pipefail
record=0; [ "${1:-}" = "--record" ] && { record=1; shift; }
base="$1"
out="$(mktemp)"; rm -f "$out"; out="$out.json"
(cd katrain/web/ui && npx vitest run --reporter=json --outputFile="$out" > /dev/null 2>&1); rc=$?
[ "$rc" -le 1 ] || { echo "!! vitest 退出码 $rc"; exit 2; }
[ -s "$out" ] || { echo "!! vitest 没有生成报告"; exit 2; }
names="$(python3 - "$out" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
if not d.get("numTotalTests"):
    sys.exit(3)
names = set()
for f in d["testResults"]:
    file = f["name"].split("/katrain/web/ui/")[-1]
    if f.get("status") == "failed" and not f["assertionResults"]:
        names.add(f"{file} :: <文件本身没跑起来>")
    names |= {f"{file} :: {a['fullName']}" for a in f["assertionResults"] if a["status"] == "failed"}
print(f"# {d['numTotalTests']} tests, {len(names)} failed", file=sys.stderr)
print("\n".join(sorted(names)))
PY
)" || { echo "!! vitest 报告里一条用例都没有"; exit 2; }
if [ "$record" = 1 ]; then printf '%s\n' "$names" | grep . | sort -u > "$base"; exit 0; fi
new="$(printf '%s\n' "$names" | grep . | sort -u | comm -13 "$base" -)"
[ -z "$new" ] && exit 0
echo "!! 新增失败："; echo "$new"; exit 1
SH
bash $B/vitestnewfail.sh --record $B/vitest_failed_before.txt; echo "record exit=$?"
git status --short
```
Expected：
- 打印 `ignored-ok` 和 `config-clean`。**没打印 `config-clean` 就停**：`katrain/config.json` 在跑测试之前就有未提交的改动，先弄清楚是谁的，否则后面「还原被测试改写的 config.json」会把它一起冲掉；
- `pytest exit=0` 或 `1`（2–5 说明 pytest 本身没跑成，基线作废）；下一行是 pytest 的 summary（形如 `3 failed, 1234 passed … in 95.1s`）；`wc -l` 输出一个数（可以是 0）；
- 最后 `vitestnewfail.sh --record` 打印 `# N tests, M failed`，然后 `record exit=0`；
- `git status --short` 为空；如果出现了 `katrain/config.json`（测试改写的），执行 `git checkout -- katrain/config.json` 还原。

不要把还不存在的测试文件当参数传给 pytest：pytest 会以用法错误直接退出，基线就会**静默为空**。

- [ ] **Step 2：先写三个行为测试**

`src/admin/api/client.test.ts`：
```ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import { adminFetch, clearToken, getToken, setToken } from './client';

afterEach(() => {
  vi.unstubAllGlobals();
  clearToken();
});

// 每次调用都给一个新的 Response：同一个 Response 的 body 只能读一次，第二次 fetch 会报 "Body is unusable"。
const reply = (status: number, body: unknown) =>
  vi.fn().mockImplementation(async () => new Response(status === 204 ? null : JSON.stringify(body), { status }));

describe('adminFetch', () => {
  it('有令牌时带 Authorization: Bearer，没有时不带；从不带 cookie', async () => {
    const f = reply(200, { ok: 1 });
    vi.stubGlobal('fetch', f);
    setToken('t-123');
    await adminFetch('/api/admin/cron/jobs');
    clearToken();
    await adminFetch('/api/admin/cron/jobs');
    expect(new Headers(f.mock.calls[0][1].headers).get('Authorization')).toBe('Bearer t-123');
    expect(new Headers(f.mock.calls[1][1].headers).get('Authorization')).toBeNull();
    expect(f.mock.calls[0][1].credentials).toBe('omit');
  });

  it('401 抛 AdminAuthError，并带上服务端给的说明', async () => {
    vi.stubGlobal('fetch', reply(401, { detail: '用户名或密码错误，或该账号没有后台权限' }));
    await expect(adminFetch('/x')).rejects.toMatchObject({
      name: 'AdminAuthError',
      message: '用户名或密码错误，或该账号没有后台权限',
    });
  });

  it('其他错误抛 AdminApiError，带状态码和说明', async () => {
    vi.stubGlobal('fetch', reply(503, { detail: 'cron 状态表不存在' }));
    await expect(adminFetch('/x')).rejects.toMatchObject({ name: 'AdminApiError', status: 503, message: 'cron 状态表不存在' });
  });
});

describe('会话令牌', () => {
  it('存在 localStorage 里：关标签页、重启浏览器之后还在', () => {
    setToken('t-keep');
    expect(localStorage.getItem('katrain_admin_token')).toBe('t-keep');
  });

  it('别的标签页点了「登出」，这一页也立即拿不到令牌：内存里不留副本', () => {
    setToken('t-shared');
    localStorage.removeItem('katrain_admin_token'); // 另一个标签页的 clearToken()
    expect(getToken()).toBeNull();
  });
});
```

`src/admin/pages/CronPage.test.tsx`：
```tsx
import { act, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import CronPage from './CronPage';
import { getCronJobs, getCronQueues } from '../api/cronApi';
import { AdminApiError, AdminAuthError } from '../api/client';

const { expire } = vi.hoisted(() => ({ expire: vi.fn() }));
vi.mock('../api/cronApi', () => ({ getCronJobs: vi.fn(), getCronQueues: vi.fn(), getCronRuns: vi.fn() }));
vi.mock('../session', () => ({ useAdminSession: () => ({ expire }) }));

const OBSERVED = '2026-09-24T08:00:00+00:00';
const job = {
  name: 'fetch_list', kind: 'interval', interval_seconds: 60, enabled: true, health: { state: 'ok', reason: '上次开始于 12 秒前' },
  process_started_at: '2026-09-24T03:00:00+00:00', heartbeat_at: '2026-09-24T07:59:50+00:00',
  last_started_at: '2026-09-24T07:59:48+00:00', last_finished_at: '2026-09-24T07:59:49+00:00',
  last_success_at: '2026-09-24T07:59:49+00:00', last_status: 'success', last_duration_ms: 812, last_error: null,
  consecutive_failures: 0, loop_iteration_at: null, loop_stats: null,
};
const queues = {
  observed_at: OBSERVED,
  live_analysis: { by_status: { pending: 2 }, oldest_pending_at: null },
  report_tasks: { by_status: {}, oldest_pending_at: null },
};
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0); });
const renderPage = () => render(<MemoryRouter><CronPage /></MemoryRouter>);

beforeEach(() => {
  vi.useFakeTimers();
  vi.resetAllMocks();
  (getCronQueues as Mock).mockResolvedValue(queues);
});

describe('CronPage', () => {
  it('刷新失败时显示错误条，并保留上一次的数据', async () => {
    (getCronJobs as Mock)
      .mockResolvedValueOnce({ observed_at: OBSERVED, jobs: [job] })
      .mockRejectedValueOnce(new AdminApiError(502, 'Bad Gateway'));
    renderPage();
    await flush();
    expect(screen.getByTestId('cron-row-fetch_list')).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(15_000); });
    expect(screen.getByTestId('cron-error')).toHaveTextContent('502 Bad Gateway');
    expect(screen.getByTestId('cron-error')).toHaveTextContent('页面数据停在');
    expect(screen.getByTestId('cron-row-fetch_list')).toBeInTheDocument();
  });

  it('会话失效（401）交给会话层处理，不显示成数据错误', async () => {
    (getCronJobs as Mock).mockRejectedValue(new AdminAuthError());
    renderPage();
    await flush();
    expect(expire).toHaveBeenCalled();
    expect(screen.queryByTestId('cron-error')).toBeNull();
  });

  it('表不存在（503）时原样显示原因', async () => {
    (getCronJobs as Mock).mockRejectedValue(new AdminApiError(503, 'cron 状态表不存在：katrain-web 新版本还没启动过'));
    renderPage();
    await flush();
    expect(screen.getByTestId('cron-error')).toHaveTextContent('503 cron 状态表不存在');
  });

  it('没有登记任何任务时显示空态说明', async () => {
    (getCronJobs as Mock).mockResolvedValue({ observed_at: OBSERVED, jobs: [] });
    renderPage();
    await flush();
    expect(screen.getByTestId('cron-empty')).toHaveTextContent('还没有上报过');
  });
});
```

`src/admin/pages/SignInPage.test.tsx`：
```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi, type Mock } from 'vitest';
import SignInPage from './SignInPage';
import { getHealth } from '../api/authApi';
import { AdminAuthError } from '../api/client';

const { signIn } = vi.hoisted(() => ({ signIn: vi.fn() }));
vi.mock('../api/authApi', () => ({ getHealth: vi.fn() }));
vi.mock('../session', () => ({ useAdminSession: () => ({ me: null, signIn }) }));

describe('SignInPage', () => {
  it('显示正在登录哪个环境；登录失败时显示服务端的说明，且不跳转', async () => {
    (getHealth as Mock).mockResolvedValue({ status: 'ok', env: 'prod' });
    signIn.mockRejectedValue(new AdminAuthError('用户名或密码错误，或该账号没有后台权限'));
    render(
      <MemoryRouter initialEntries={['/signin']}>
        <Routes>
          <Route path="/signin" element={<SignInPage />} />
          <Route path="/cron" element={<div>CRON</div>} />
        </Routes>
      </MemoryRouter>
    );
    expect(await screen.findByTestId('signin-env')).toHaveTextContent('生产环境');
    fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'fan' } });
    fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'x' } });
    fireEvent.click(screen.getByRole('button', { name: '登录' }));
    expect(await screen.findByText('用户名或密码错误，或该账号没有后台权限')).toBeInTheDocument();
    expect(screen.queryByText('CRON')).toBeNull();
  });
});
```

`src/admin/components/RunHistoryDrawer.test.tsx`：
```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi, type Mock } from 'vitest';
import RunHistoryDrawer from './RunHistoryDrawer';
import { getCronRuns } from '../api/cronApi';
import { AdminAuthError } from '../api/client';
import type { CronJob } from '../api/types';

const { expire } = vi.hoisted(() => ({ expire: vi.fn() }));
vi.mock('../api/cronApi', () => ({ getCronRuns: vi.fn() }));
vi.mock('../session', () => ({ useAdminSession: () => ({ expire }) }));

const job = { name: 'fetch_list', kind: 'interval', interval_seconds: 60, health: { state: 'ok', reason: '' }, last_error: null } as unknown as CronJob;

describe('RunHistoryDrawer', () => {
  it('会话失效（401）交给会话层处理（回登录页），不显示成数据错误', async () => {
    (getCronRuns as Mock).mockRejectedValue(new AdminAuthError());
    render(<RunHistoryDrawer job={job} onClose={() => {}} />);
    await vi.waitFor(() => expect(expire).toHaveBeenCalled());
    expect(screen.queryByText(/无法获取运行记录/)).toBeNull();
  });
});
```

- [ ] **Step 3：跑测试，确认失败**：`cd katrain/web/ui && npx vitest run src/admin 2>&1 | tail -8`。期望结果：FAIL，报模块找不到。

- [ ] **Step 4：入口、构建配置、脚本、忽略规则**

`katrain/web/ui/admin.html`：
```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="robots" content="noindex, nofollow" />
    <title>KaTrain 管理后台</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/admin/main.tsx"></script>
  </body>
</html>
```

`katrain/web/ui/vite.admin.config.ts`：
```ts
// Admin console build: its own entry (admin.html) and its own output dir (../static-admin), so neither the
// public galaxy bundle (../static) nor the kiosk bundle (../static-kiosk-2d) ever contains admin code.
// vitest keeps using vite.config.ts; that file is deliberately untouched (the kiosk build depends on it).
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: true,
    proxy: { '/api/admin': { target: 'http://127.0.0.1:8010' } },
  },
  build: {
    outDir: '../static-admin',
    emptyOutDir: true,
    rollupOptions: { input: 'admin.html' },
  },
});
```

`package.json` 的 `scripts` 里，在 `"build:kiosk-2d"` 那一行之前加两行：
```json
    "dev:admin": "vite --config vite.admin.config.ts",
    "build:admin": "tsc -b && vite build --config vite.admin.config.ts",
```

根目录 `.gitignore`，在 `katrain/web/static-full-baseline/` 那一行之后加：
```
katrain/web/static-admin/
```

- [ ] **Step 5：ESLint 导入边界**。在 `eslint.config.js` 里：

5a. 在 `const forbiddenFromKiosk = [` 之前加：
```js
// Admin console boundary (superpowers/tracks/admin-console/spec-2026-09-24-admin-console.md §5.5):
// only src/admin/** may import admin code, or admin UI would ship inside a public/kiosk bundle.
const adminIsPrivate = {
  group: ['**/admin/**', '*/admin/*', '../admin/*', '../../admin/*', '../../../admin/*'],
  message: 'only src/admin/** may import admin code — it would ship admin UI inside a public bundle',
}

const forbiddenFromAdmin = [
  {
    group: ['**/kiosk/**', '*/kiosk/*', '../kiosk/*', '../../kiosk/*', '../../../kiosk/*'],
    message: 'admin console must not import kiosk code — the kiosk is a standalone SBC bundle',
  },
]
```
5b. 在 `forbiddenFromKiosk`、`forbiddenFromServer`、`forbiddenFromShared` 这三个数组的末尾，各加一项 `adminIsPrivate,`。

5c. 在 `defineConfig([ … ])` 里，紧跟第一个配置对象（`files: ['**/*.{ts,tsx}']` 那一块）之后、kiosk 那一块之前，插入一条兜底规则，管住 `main.tsx`、`AppRouter.tsx`、`GalaxyApp.tsx` 这些没被更窄规则覆盖到的公开入口：
```js
  {
    // 公开入口和其他没被更窄规则覆盖的文件，也不许 import 后台代码。必须放在下面几块之前：flat config 里
    // 同一条规则，后匹配到的那一块会整个替换前面的选项；下面几块自己的列表里已经带着 adminIsPrivate。
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['src/admin/**', '**/*.test.{ts,tsx}', '**/__tests__/**'],
    rules: {
      'no-restricted-imports': ['error', { patterns: [adminIsPrivate] }],
    },
  },
```

5d. 在 `defineConfig([ … ])` 的最后一个配置对象之后加：
```js
  {
    files: ['src/admin/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': ['error', { patterns: forbiddenFromAdmin }],
    },
  },
```

- [ ] **Step 6：API 层**

`src/admin/api/types.ts`：
```ts
// 后台接口契约（spec §6.5）。后端 katrain/web/admin/routers/*.py 的 pydantic 模型必须与这里一致。
export type AdminEnv = 'local' | 'test' | 'prod';
export interface AdminMe { username: string; env: AdminEnv }
export interface AdminLogin extends AdminMe { token: string }
export interface AdminHealth { status: string; env: AdminEnv }

export type HealthState = 'offline' | 'disabled' | 'pending' | 'stuck' | 'running' | 'failed' | 'errors' | 'overdue' | 'ok';
export type RunStatus = 'running' | 'success' | 'errors' | 'failed';

export interface LoopStats { in_flight: number; capacity: number; errors_total: number; last_error_at: string | null }

export interface CronJob {
  name: string;
  kind: 'interval' | 'loop';
  interval_seconds: number | null;
  enabled: boolean;
  health: { state: HealthState; reason: string };
  process_started_at: string | null;
  heartbeat_at: string | null;
  last_started_at: string | null;
  last_finished_at: string | null;
  last_success_at: string | null;
  last_status: RunStatus | null;
  last_duration_ms: number | null;
  last_error: string | null;
  consecutive_failures: number;
  loop_iteration_at: string | null;
  loop_stats: LoopStats | null;
}
export interface CronJobsResponse { observed_at: string; jobs: CronJob[] }

export interface CronRun {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: RunStatus;
  duration_ms: number | null;
  error_count: number;
  error: string | null;
}
export interface CronRunsResponse { runs: CronRun[]; next_before_id: number | null }

export interface QueueSummary { by_status: Record<string, number>; oldest_pending_at: string | null }
export interface CronQueuesResponse { observed_at: string; live_analysis: QueueSummary; report_tasks: QueueSummary }
```

`src/admin/api/client.ts`：
```ts
// 后台的所有请求都走这里。会话令牌放在 localStorage：它按「协议+主机+端口」隔离，本机别的端口上的页面读不到；
// 关标签页、重启浏览器之后还在，直到 8 小时后过期或点「登出」（spec E8）。每次请求带 Authorization: Bearer。
// 不用 cookie —— cookie 不分端口（spec §5.3）。
const TOKEN_KEY = 'katrain_admin_token';
// 只在浏览器禁用 storage 时用，活到刷新页面为止。storage 能用时它必须是空的：
// 否则别的标签页点了「登出」，这一页还会从内存里拿出旧令牌接着用。
let memoryToken: string | null = null;

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? memoryToken;
  } catch {
    return memoryToken;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    memoryToken = null;
  } catch {
    memoryToken = token; // storage blocked: only this page carries the token
  }
}

export function clearToken(): void {
  memoryToken = null;
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* nothing was stored */
  }
}

export class AdminAuthError extends Error {
  constructor(message = '未登录或会话已失效') {
    super(message);
    this.name = 'AdminAuthError';
  }
}

export class AdminApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'AdminApiError';
    this.status = status;
  }
}

async function detailOf(res: Response): Promise<string | undefined> {
  try {
    const body = await res.json();
    return typeof body?.detail === 'string' ? body.detail : undefined;
  } catch {
    return undefined;
  }
}

export async function adminFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const res = await fetch(path, { ...init, headers, credentials: 'omit' });
  if (res.status === 401) throw new AdminAuthError(await detailOf(res));
  if (!res.ok) throw new AdminApiError(res.status, (await detailOf(res)) ?? (res.statusText || '请求失败'));
  return (res.status === 204 ? undefined : await res.json()) as T;
}

/** 错误条上的文字：接口错误带上状态码（spec §6.7「写明状态码和原因」）。 */
export function errorText(e: unknown): string {
  if (e instanceof AdminApiError) return `${e.status} ${e.message}`;
  return e instanceof Error ? e.message : String(e);
}
```

`src/admin/api/authApi.ts`：
```ts
import { adminFetch, AdminAuthError, clearToken, getToken, setToken } from './client';
import type { AdminHealth, AdminLogin, AdminMe } from './types';

// FIXTURE 分支：删除条件与 cronApi.ts 相同（Task 13）。
const useFixture = import.meta.env.VITE_ADMIN_FIXTURE === 'true';
const fixture = () => import('../__fixtures__/cronFixture');

export const getHealth = async (): Promise<AdminHealth> =>
  useFixture ? (await fixture()).healthFixture() : adminFetch<AdminHealth>('/api/admin/health');

export const getMe = async (): Promise<AdminMe> => {
  if (useFixture) return (await fixture()).meFixture();
  if (!getToken()) throw new AdminAuthError(); // 这个浏览器还没登录过，或者已经登出：不必去问服务端
  return adminFetch<AdminMe>('/api/admin/auth/me');
};

export const login = async (username: string, password: string): Promise<AdminMe> => {
  const r = useFixture
    ? await (await fixture()).loginFixture()
    : await adminFetch<AdminLogin>('/api/admin/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) });
  setToken(r.token);
  return { username: r.username, env: r.env };
};

export const logout = async (): Promise<void> => {
  try {
    if (!useFixture) await adminFetch<void>('/api/admin/auth/logout', { method: 'POST' });
  } finally {
    clearToken(); // 服务端不存会话：丢掉令牌就是登出；那边只记一笔审计
  }
};
```

`src/admin/api/cronApi.ts`：
```ts
import { adminFetch } from './client';
import type { CronJobsResponse, CronQueuesResponse, CronRunsResponse } from './types';

// FIXTURE（切片 1 第 2–3 步）：VITE_ADMIN_FIXTURE=true 时用假数据跑界面。
// 删除条件：Task 12 接上真实接口、Task 13 验收通过后，与 src/admin/__fixtures__/ 在同一个提交里删掉。
const useFixture = import.meta.env.VITE_ADMIN_FIXTURE === 'true';
const fixture = () => import('../__fixtures__/cronFixture');

export async function getCronJobs(): Promise<CronJobsResponse> {
  if (useFixture) return (await fixture()).jobsFixture();
  return adminFetch<CronJobsResponse>('/api/admin/cron/jobs');
}

export async function getCronRuns(name: string, beforeId?: number): Promise<CronRunsResponse> {
  if (useFixture) return (await fixture()).runsFixture(name, beforeId);
  const q = new URLSearchParams({ limit: '50' });
  if (beforeId !== undefined) q.set('before_id', String(beforeId));
  return adminFetch<CronRunsResponse>(`/api/admin/cron/jobs/${encodeURIComponent(name)}/runs?${q}`);
}

export async function getCronQueues(): Promise<CronQueuesResponse> {
  if (useFixture) return (await fixture()).queuesFixture();
  return adminFetch<CronQueuesResponse>('/api/admin/cron/queues');
}
```

- [ ] **Step 7：Fixture**（`src/admin/__fixtures__/cronFixture.ts`）
```ts
// FIXTURE —— 只供切片 1 的 Task 2–3 使用（假数据跑界面、四图对比、承重实测）。
// 删除条件：Task 12 接上真实接口、Task 13 验收通过后，与 cronApi.ts / authApi.ts 里的 useFixture 分支
// 在同一个提交里删除。用法：/admin.html?fixture=<ok|mixed|offline|error|missing|empty|many>&env=<local|test|prod>#/cron
// 加 &signedout=1 表示「还没登录」（getMe 返回 401），用来截登录页。
import { AdminApiError, AdminAuthError } from '../api/client';
import type { AdminEnv, AdminHealth, AdminLogin, AdminMe, CronJob, CronJobsResponse, CronQueuesResponse, CronRun, CronRunsResponse } from '../api/types';

const params = () => new URLSearchParams(window.location.search);
const scenario = () => params().get('fixture') ?? 'mixed';
const env = () => (params().get('env') as AdminEnv | null) ?? 'test';
const OBSERVED = '2026-09-24T08:00:00+00:00';
const at = (secondsAgo: number) => new Date(Date.parse(OBSERVED) - secondsAgo * 1000).toISOString();

const LONG_ERROR =
  '[katrain_cron.fetch_list] fetch failed: ConnectTimeout: timed out while connecting to api.19x19.com\n' +
  '  File "katrain/cron/clients/xingzhen.py", line 88, in fetch\n'.repeat(12);

const base = (name: string, kind: 'interval' | 'loop', interval: number | null): CronJob => ({
  name, kind, interval_seconds: interval, enabled: true,
  health: { state: 'ok', reason: kind === 'loop' ? '循环 3 秒前推进过' : '上次开始于 12 秒前' },
  process_started_at: at(5 * 3600), heartbeat_at: at(10),
  last_started_at: at(12), last_finished_at: kind === 'interval' ? at(11) : null,
  last_success_at: kind === 'interval' ? at(11) : null, last_status: kind === 'interval' ? 'success' : 'running',
  last_duration_ms: kind === 'interval' ? 812 : null, last_error: null, consecutive_failures: 0,
  loop_iteration_at: kind === 'loop' ? at(3) : null,
  loop_stats: kind === 'loop' ? { in_flight: 9, capacity: 16, errors_total: 0, last_error_at: null } : null,
});

const NINE: CronJob[] = [
  base('fetch_list', 'interval', 60), base('poll_moves', 'interval', 3), base('poll_pandanet', 'interval', 300),
  base('translate', 'interval', 120), base('fetch_upcoming', 'interval', 7200), base('cleanup', 'interval', 86400),
  base('tutorial_backup', 'interval', 86400), base('analyze', 'loop', null), base('report_analyze', 'loop', null),
];

const mixed = (): CronJob[] => NINE.map((j) => {
  switch (j.name) {
    case 'fetch_list': return { ...j, health: { state: 'failed', reason: '连续 3 次不成功，最近一次抛出了异常' }, last_status: 'failed', last_error: LONG_ERROR, consecutive_failures: 3 };
    case 'translate': return { ...j, health: { state: 'errors', reason: '跑完了，但运行期间有报错' }, last_status: 'errors', last_error: '[katrain_cron.translate] DashScope 429 Too Many Requests', consecutive_failures: 1 };
    case 'fetch_upcoming': return { ...j, health: { state: 'overdue', reason: '上次开始于 5 小时前，间隔是 2 小时' }, last_started_at: at(5 * 3600) };
    case 'cleanup': return { ...j, enabled: false, health: { state: 'disabled', reason: '已被配置停用' } };
    case 'poll_pandanet': return { ...j, health: { state: 'running', reason: '已运行 42 秒' }, last_status: 'running', last_finished_at: null };
    default: return j;
  }
});

let errorCalls = 0;

export function jobsFixture(): Promise<CronJobsResponse> {
  switch (scenario()) {
    // 第一次成功、之后都 502：设计稿的 error 态是「错误条 + 页面数据停在 HH:MM:SS」，得先有过一次成功的数据。
    case 'error': return errorCalls++ === 0 ? Promise.resolve({ observed_at: OBSERVED, jobs: mixed() }) : Promise.reject(new AdminApiError(502, 'Bad Gateway'));
    case 'missing': return Promise.reject(new AdminApiError(503, 'cron 状态表不存在：katrain-web 新版本还没启动过'));
    case 'empty': return Promise.resolve({ observed_at: OBSERVED, jobs: [] });
    case 'offline': return Promise.resolve({ observed_at: OBSERVED, jobs: NINE.map((j) => ({ ...j, heartbeat_at: at(600), health: { state: 'offline', reason: 'cron 进程失联：10 分钟没有心跳' } })) });
    case 'many': return Promise.resolve({ observed_at: OBSERVED, jobs: Array.from({ length: 30 }, (_, i) => ({ ...NINE[i % 9], name: `${NINE[i % 9].name}_${i}` })) });
    case 'ok': return Promise.resolve({ observed_at: OBSERVED, jobs: NINE });
    default: return Promise.resolve({ observed_at: OBSERVED, jobs: mixed() });
  }
}

export function runsFixture(name: string, beforeId?: number): Promise<CronRunsResponse> {
  const start = beforeId ?? 201; // 一共 200 条，每页 50 条
  const ids = Array.from({ length: 50 }, (_, i) => start - 1 - i).filter((id) => id > 0);
  const runs: CronRun[] = ids.map((id) => ({
    id, started_at: at(id * 60), finished_at: at(id * 60 - 1),
    status: id % 17 === 0 ? 'failed' : id % 11 === 0 ? 'errors' : 'success',
    duration_ms: 800 + (id % 7) * 100, error_count: id % 17 === 0 || id % 11 === 0 ? 1 : 0,
    error: id % 17 === 0 ? `[${name}] ${LONG_ERROR}` : null,
  }));
  const last = ids[ids.length - 1];
  return Promise.resolve({ runs, next_before_id: last !== undefined && last > 1 ? last : null });
}

export function queuesFixture(): Promise<CronQueuesResponse> {
  return Promise.resolve({
    observed_at: OBSERVED,
    live_analysis: { by_status: { pending: 12, running: 16, success: 79611, failed: 3 }, oldest_pending_at: at(95) },
    report_tasks: { by_status: { running: 1, completed: 16 }, oldest_pending_at: null },
  });
}

export const meFixture = (): Promise<AdminMe> =>
  params().get('signedout') ? Promise.reject(new AdminAuthError()) : Promise.resolve({ username: 'fan', env: env() });
export const loginFixture = (): Promise<AdminLogin> => Promise.resolve({ username: 'fan', env: env(), token: 'fixture-token' });
export const healthFixture = (): Promise<AdminHealth> => Promise.resolve({ status: 'ok', env: env() });
```

- [ ] **Step 8：会话、主题和小工具**

`src/admin/theme.ts`：
```ts
import { createTheme } from '@mui/material/styles';
import { zenTheme } from '../theme';
import { CHINESE_UI_FONT } from '../galaxy/theme';

// 后台沿用站点的 zen 深色基调；字体栈与 galaxy 中文界面用同一个常量（spec §5.5）。admin.html 不加载网页字体，
// 没装 'LXGW WenKai' 的机器自然退到系统字体。具体取值以 Task 1 确认的设计稿为准（slice1/design-notes.md）。
export const adminTheme = createTheme(zenTheme, {
  typography: { fontFamily: CHINESE_UI_FONT },
  components: { MuiTableCell: { styleOverrides: { root: { fontVariantNumeric: 'tabular-nums' } } } },
});
```

`src/admin/envLabel.ts`：
```ts
import type { AdminEnv } from './api/types';

export const ENV_LABEL: Record<AdminEnv, string> = { local: '本机', test: '测试环境', prod: '生产环境' };
export const ENV_COLOR: Record<AdminEnv, 'default' | 'warning' | 'error'> = { local: 'default', test: 'warning', prod: 'error' };
```

`src/admin/jobLabels.ts`：
```ts
// 任务的中文名。名字不在表里（新加的任务）就原样显示原名，不猜。
const JOB_LABELS: Record<string, string> = {
  fetch_list: '直播列表抓取',
  poll_moves: '直播落子轮询',
  poll_pandanet: 'Pandanet 转播轮询',
  translate: '棋手 / 赛事名翻译',
  fetch_upcoming: '赛事预告抓取',
  cleanup: '过期数据清理',
  tutorial_backup: '教程数据备份',
  analyze: '直播 AI 分析',
  report_analyze: '用户复盘分析',
};

export const jobLabel = (name: string): string => JOB_LABELS[name] ?? name;
```

`src/admin/format.ts`：
```ts
export const fmtClock = (d: Date): string => d.toLocaleTimeString('zh-CN', { hour12: false });
export const fmtDateTime = (iso: string): string => new Date(iso).toLocaleString('zh-CN', { hour12: false });

export function fmtDuration(ms: number): string {
  if (ms < 1000) return `${ms} 毫秒`;
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s} 秒`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} 分 ${s % 60} 秒`;
  return `${Math.floor(m / 60)} 小时 ${m % 60} 分`;
}

export function fmtInterval(seconds: number): string {
  if (seconds < 60) return `每 ${seconds} 秒`;
  if (seconds < 3600) return `每 ${Math.round(seconds / 60)} 分钟`;
  return `每 ${Math.round(seconds / 3600)} 小时`;
}

/** 相对服务端 observed_at 的「多久之前」：用服务端的观测时刻，不用浏览器时钟（两边的钟可能对不齐）。 */
export function ago(iso: string, observedAt: string): string {
  return `${fmtDuration(Math.max(0, Date.parse(observedAt) - Date.parse(iso)))}前`;
}
```

`src/admin/session.tsx`：
```tsx
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Box, CircularProgress } from '@mui/material';
import { getMe, login as apiLogin, logout as apiLogout } from './api/authApi';
import { clearToken } from './api/client';
import type { AdminMe } from './api/types';

interface SessionValue {
  me: AdminMe | null;
  checking: boolean;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  expire: () => void;
}

const SessionContext = createContext<SessionValue | null>(null);

export function AdminSessionProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<AdminMe | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    getMe().then(setMe).catch(() => setMe(null)).finally(() => setChecking(false));
  }, []);

  const signIn = useCallback(async (username: string, password: string) => {
    setMe(await apiLogin(username, password));
  }, []);

  const signOut = useCallback(async () => {
    try {
      await apiLogout();
    } catch {
      /* 令牌已经在 apiLogout 里丢掉了；服务端这次没记上 logout 审计，不影响登出 */
    } finally {
      setMe(null);
    }
  }, []);

  const expire = useCallback(() => {
    clearToken();
    setMe(null);
  }, []);

  return (
    <SessionContext.Provider value={{ me, checking, signIn, signOut, expire }}>{children}</SessionContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components -- hook 和 Provider 放在一起，与 src/kiosk/context/*.tsx 同一写法
export function useAdminSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error('useAdminSession must be used inside AdminSessionProvider');
  return value;
}

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { me, checking } = useAdminSession();
  const location = useLocation();
  if (checking) {
    return (
      <Box sx={{ display: 'grid', placeItems: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }
  if (!me) return <Navigate to="/signin" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}
```

`src/admin/main.tsx`：
```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import AdminApp from './AdminApp';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AdminApp />
  </StrictMode>,
);
```

`src/admin/AdminApp.tsx`：
```tsx
import { CssBaseline, ThemeProvider } from '@mui/material';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { adminTheme } from './theme';
import { AdminSessionProvider, RequireAdmin } from './session';
import AdminShell from './components/AdminShell';
import SignInPage from './pages/SignInPage';
import CronPage from './pages/CronPage';

// HashRouter：后端和 vite dev 都不用配 SPA 回退，地址形如 http://localhost:8010/#/cron
export default function AdminApp() {
  return (
    <ThemeProvider theme={adminTheme}>
      <CssBaseline />
      <HashRouter>
        <AdminSessionProvider>
          <Routes>
            <Route path="/signin" element={<SignInPage />} />
            <Route element={<RequireAdmin><AdminShell /></RequireAdmin>}>
              <Route path="/cron" element={<CronPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/cron" replace />} />
          </Routes>
        </AdminSessionProvider>
      </HashRouter>
    </ThemeProvider>
  );
}
```

- [ ] **Step 9：页面和组件**

`src/admin/pages/SignInPage.tsx`：
```tsx
import { useEffect, useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Alert, Box, Button, Chip, Paper, Stack, TextField, Typography } from '@mui/material';
import { useAdminSession } from '../session';
import { getHealth } from '../api/authApi';
import { errorText } from '../api/client';
import type { AdminEnv } from '../api/types';
import { ENV_COLOR, ENV_LABEL } from '../envLabel';

export default function SignInPage() {
  const { me, signIn } = useAdminSession();
  const navigate = useNavigate();
  const location = useLocation();
  const [env, setEnv] = useState<AdminEnv | null>(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const from = (location.state as { from?: string } | null)?.from ?? '/cron';

  useEffect(() => {
    getHealth().then((h) => setEnv(h.env)).catch(() => setEnv(null));
  }, []);

  if (me) return <Navigate to={from} replace />;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(username, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box sx={{ minHeight: '100vh', display: 'grid', placeItems: 'center', bgcolor: 'background.default' }}>
      <Paper component="form" onSubmit={onSubmit} sx={{ p: 4, width: 380 }}>
        <Stack spacing={2}>
          <Typography variant="h6">KaTrain 管理后台</Typography>
          {env && <Chip data-testid="signin-env" label={`正在登录：${ENV_LABEL[env]}`} color={ENV_COLOR[env]} />}
          <TextField label="用户名" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus autoComplete="username" />
          <TextField label="密码" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          {error && <Alert severity="error">{error}</Alert>}
          <Button type="submit" variant="contained" disabled={busy || !username || !password}>
            {busy ? '登录中…' : '登录'}
          </Button>
        </Stack>
      </Paper>
    </Box>
  );
}
```

`src/admin/components/AdminShell.tsx`：
```tsx
import { NavLink, Outlet } from 'react-router-dom';
import { Box, Button, Chip, List, ListItemButton, ListItemText, Typography } from '@mui/material';
import { useAdminSession } from '../session';
import { ENV_COLOR, ENV_LABEL } from '../envLabel';

export default function AdminShell() {
  const { me, signOut } = useAdminSession();
  if (!me) return null;
  return (
    <Box sx={{ height: '100vh', display: 'grid', gridTemplateRows: '56px minmax(0, 1fr)', gridTemplateColumns: '200px minmax(0, 1fr)' }}>
      <Box component="header" sx={{ gridColumn: '1 / -1', display: 'flex', alignItems: 'center', gap: 2, px: 2, borderBottom: 1, borderColor: 'divider' }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>KaTrain 管理后台</Typography>
        <Chip data-testid="admin-env" size="small" label={ENV_LABEL[me.env]} color={ENV_COLOR[me.env]} />
        <Box sx={{ flex: 1 }} />
        <Typography variant="body2" color="text.secondary">{me.username}</Typography>
        <Button size="small" onClick={() => void signOut()}>登出</Button>
      </Box>
      <Box component="nav" sx={{ borderRight: 1, borderColor: 'divider', overflowY: 'auto' }}>
        <List dense>
          <ListItemButton component={NavLink} to="/cron">
            <ListItemText primary="定时任务" />
          </ListItemButton>
        </List>
      </Box>
      <Box component="main" data-testid="admin-main" sx={{ minHeight: 0, overflowY: 'auto', p: 3 }}>
        <Outlet />
      </Box>
    </Box>
  );
}
```

`src/admin/components/HealthChip.tsx`：
```tsx
import { Chip, Tooltip } from '@mui/material';
import type { HealthState } from '../api/types';

const LABEL: Record<HealthState, string> = {
  offline: '失联', disabled: '已停用', pending: '等待首次运行', stuck: '卡住', running: '运行中',
  failed: '失败', errors: '有报错', overdue: '该跑没跑', ok: '正常',
};
const COLOR: Record<HealthState, 'default' | 'success' | 'info' | 'warning' | 'error'> = {
  offline: 'error', disabled: 'default', pending: 'default', stuck: 'error', running: 'info',
  failed: 'error', errors: 'warning', overdue: 'warning', ok: 'success',
};

export default function HealthChip({ state, reason }: { state: HealthState; reason: string }) {
  return (
    <Tooltip title={reason}>
      <Chip size="small" data-testid={`health-${state}`} label={LABEL[state]} color={COLOR[state]} />
    </Tooltip>
  );
}
```

`src/admin/components/QueueCards.tsx`：
```tsx
import { Paper, Stack, Typography } from '@mui/material';
import type { CronQueuesResponse, QueueSummary } from '../api/types';
import { ago } from '../format';

function QueueCard({ title, q, observedAt, testid }: { title: string; q: QueueSummary; observedAt: string; testid: string }) {
  const n = (k: string) => q.by_status[k] ?? 0;
  return (
    <Paper data-testid={testid} sx={{ p: 2, flex: 1 }}>
      <Typography variant="subtitle2" color="text.secondary">{title}</Typography>
      <Typography variant="h6">排队 {n('pending')} · 进行中 {n('running')} · 失败 {n('failed')}</Typography>
      <Typography variant="caption" color="text.secondary">
        {q.oldest_pending_at ? `最早一条排队于 ${ago(q.oldest_pending_at, observedAt)}` : '当前没有排队'}
      </Typography>
    </Paper>
  );
}

export default function QueueCards({ queues }: { queues: CronQueuesResponse }) {
  return (
    <Stack direction="row" spacing={2}>
      <QueueCard title="直播分析队列" q={queues.live_analysis} observedAt={queues.observed_at} testid="queue-live" />
      <QueueCard title="用户复盘队列" q={queues.report_tasks} observedAt={queues.observed_at} testid="queue-report" />
    </Stack>
  );
}
```

`src/admin/components/RunHistoryDrawer.tsx`：
```tsx
import { useEffect, useState } from 'react';
import { Alert, Box, Button, Drawer, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material';
import { getCronRuns } from '../api/cronApi';
import { AdminAuthError, errorText } from '../api/client';
import type { CronJob, CronRun } from '../api/types';
import { useAdminSession } from '../session';
import { jobLabel } from '../jobLabels';
import { fmtDateTime, fmtDuration } from '../format';

const RUN_LABEL: Record<CronRun['status'], string> = { running: '运行中', success: '成功', errors: '有报错', failed: '失败' };

export default function RunHistoryDrawer({ job, onClose }: { job: CronJob | null; onClose: () => void }) {
  const { expire } = useAdminSession();
  const [runs, setRuns] = useState<CronRun[]>([]);
  const [next, setNext] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!job) return;
    let alive = true;
    setRuns([]);
    setNext(null);
    setError(null);
    setLoading(true);
    getCronRuns(job.name)
      .then((r) => { if (alive) { setRuns(r.runs); setNext(r.next_before_id); } })
      .catch((e) => {
        if (!alive) return;
        if (e instanceof AdminAuthError) expire(); // 会话失效交给会话层（回登录页），和 CronPage 一样
        else setError(errorText(e));
      })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [job, expire]);

  const loadMore = async () => {
    if (!job || next === null) return;
    setLoading(true);
    try {
      const r = await getCronRuns(job.name, next);
      setRuns((prev) => [...prev, ...r.runs]);
      setNext(r.next_before_id);
    } catch (e) {
      if (e instanceof AdminAuthError) expire();
      else setError(errorText(e));
    } finally {
      setLoading(false);
    }
  };

  const onlyFailures = job !== null && (job.kind === 'loop' || (job.interval_seconds ?? 0) < 60);

  return (
    <Drawer anchor="right" open={job !== null} onClose={onClose} slotProps={{ paper: { sx: { width: 640, display: 'flex', flexDirection: 'column' } } }}>
      {job && (
        <>
          <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider', flex: 'none' }}>
            <Typography variant="h6">{jobLabel(job.name)}</Typography>
            <Typography variant="body2" color="text.secondary">{job.health.reason}</Typography>
            {job.last_error && (
              <Box component="pre" sx={{ mt: 1, p: 1, bgcolor: 'background.default', whiteSpace: 'pre-wrap', maxHeight: 160, overflowY: 'auto', fontSize: 12 }}>
                {job.last_error}
              </Box>
            )}
          </Box>
          <Box data-testid="run-history-scroll" sx={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
            {error && <Alert severity="error">无法获取运行记录：{error}</Alert>}
            {!error && !loading && runs.length === 0 && (
              <Typography sx={{ p: 2 }} color="text.secondary">
                {onlyFailures ? '这个任务只记录不成功的运行，目前一次都没有。' : '还没有运行记录。'}
              </Typography>
            )}
            {runs.length > 0 && (
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow><TableCell>开始</TableCell><TableCell>结果</TableCell><TableCell>耗时</TableCell><TableCell>报错</TableCell></TableRow>
                </TableHead>
                <TableBody>
                  {runs.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell>{fmtDateTime(r.started_at)}</TableCell>
                      <TableCell>{RUN_LABEL[r.status]}</TableCell>
                      <TableCell>{r.duration_ms != null ? fmtDuration(r.duration_ms) : '—'}</TableCell>
                      <TableCell sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                        {r.error ?? ''}
                        {r.error_count > 1 && `（这次运行一共 ${r.error_count} 条报错，这里是第一条）`}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
            {next !== null && (
              <Box sx={{ p: 2 }}>
                <Button onClick={() => void loadMore()} disabled={loading}>加载更早的记录</Button>
              </Box>
            )}
          </Box>
        </>
      )}
    </Drawer>
  );
}
```

`src/admin/pages/CronPage.tsx`：
```tsx
import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Paper, Skeleton, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material';
import { getCronJobs, getCronQueues } from '../api/cronApi';
import { AdminAuthError, errorText } from '../api/client';
import type { CronJob, CronJobsResponse, CronQueuesResponse } from '../api/types';
import { useAdminSession } from '../session';
import { jobLabel } from '../jobLabels';
import HealthChip from '../components/HealthChip';
import QueueCards from '../components/QueueCards';
import RunHistoryDrawer from '../components/RunHistoryDrawer';
import { ago, fmtClock, fmtDateTime, fmtDuration, fmtInterval } from '../format';

const REFRESH_MS = 15_000;

function processLine(j: CronJobsResponse): string {
  const beats = j.jobs.map((x) => x.heartbeat_at).filter((x): x is string => !!x).sort();
  if (beats.length === 0) return 'cron 进程：还没有心跳记录';
  const offline = j.jobs.every((x) => x.health.state === 'offline');
  const started = j.jobs.map((x) => x.process_started_at).filter((x): x is string => !!x).sort().pop();
  return `cron 进程：${offline ? '失联' : '在线'} · 最后心跳 ${ago(beats[beats.length - 1], j.observed_at)}` +
    (started ? ` · 本次启动于 ${fmtDateTime(started)}` : '');
}

export default function CronPage() {
  const { expire } = useAdminSession();
  const [jobs, setJobs] = useState<CronJobsResponse | null>(null);
  const [queues, setQueues] = useState<CronQueuesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastOkAt, setLastOkAt] = useState<Date | null>(null);
  const [selected, setSelected] = useState<CronJob | null>(null);
  const alive = useRef(true);

  const load = useCallback(async () => {
    try {
      const [j, q] = await Promise.all([getCronJobs(), getCronQueues()]);
      if (!alive.current) return;
      setJobs(j);
      setQueues(q);
      setError(null);
      setLastOkAt(new Date());
    } catch (e) {
      if (!alive.current) return;
      if (e instanceof AdminAuthError) {
        expire();
        return;
      }
      setError(errorText(e));
    }
  }, [expire]);

  useEffect(() => {
    alive.current = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- 首次拉取是异步的：load() 只在 await 之后 setState
    void load();
    const timer = window.setInterval(() => void load(), REFRESH_MS);
    return () => {
      alive.current = false;
      window.clearInterval(timer);
    };
  }, [load]);

  return (
    <Stack spacing={2}>
      <Typography variant="h5">定时任务</Typography>
      {error && (
        <Alert severity="error" data-testid="cron-error">
          无法获取最新数据：{error}{lastOkAt ? `（页面数据停在 ${fmtClock(lastOkAt)}）` : ''}
        </Alert>
      )}
      {!jobs && !error && <Skeleton data-testid="cron-loading" variant="rounded" height={320} />}
      {jobs && (
        <>
          <Paper data-testid="cron-process" sx={{ p: 2 }}>
            <Typography variant="body2">{processLine(jobs)}</Typography>
          </Paper>
          {queues && <QueueCards queues={queues} />}
          {jobs.jobs.length === 0 ? (
            <Alert severity="info" data-testid="cron-empty">cron 进程还没有上报过任何任务：新版 cron 可能还没部署。</Alert>
          ) : (
            <Paper>
              <Table size="small" data-testid="cron-table">
                <TableHead>
                  <TableRow>
                    <TableCell>任务</TableCell><TableCell>状态</TableCell><TableCell>频率</TableCell><TableCell>上次开始</TableCell>
                    <TableCell>耗时</TableCell><TableCell>连续不成功</TableCell><TableCell>最近报错</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {jobs.jobs.map((job) => (
                    <TableRow key={job.name} data-testid={`cron-row-${job.name}`} hover onClick={() => setSelected(job)} sx={{ cursor: 'pointer' }}>
                      <TableCell>
                        {jobLabel(job.name)}
                        <Typography variant="caption" color="text.secondary" display="block">{job.name}</Typography>
                      </TableCell>
                      <TableCell><HealthChip state={job.health.state} reason={job.health.reason} /></TableCell>
                      <TableCell>{job.kind === 'loop' ? '常驻' : fmtInterval(job.interval_seconds ?? 0)}</TableCell>
                      <TableCell>{job.last_started_at ? ago(job.last_started_at, jobs.observed_at) : '—'}</TableCell>
                      <TableCell>{job.last_duration_ms != null ? fmtDuration(job.last_duration_ms) : '—'}</TableCell>
                      <TableCell>{job.consecutive_failures}</TableCell>
                      <TableCell sx={{ maxWidth: 360 }}>
                        <Typography variant="body2" noWrap title={job.last_error ?? ''}>{job.last_error ?? '—'}</Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Paper>
          )}
        </>
      )}
      <RunHistoryDrawer job={selected} onClose={() => setSelected(null)} />
    </Stack>
  );
}
```

- [ ] **Step 10：跑测试、类型检查和 lint**
```bash
set -o pipefail
cd /Users/fan/Repositories/katrain-admin-console/katrain/web/ui
npx vitest run src/admin 2>&1 | tail -6
npx tsc -b 2>&1 | tail -5
npx eslint src/admin eslint.config.js
```
期望结果：vitest 全部 PASS；`tsc -b` 没有输出；eslint 没有输出。这份配置里 `react-refresh/only-export-components` 和 `react-hooks/set-state-in-effect` 都是 error，不是 warning（仓里现有的 `AuthContext.tsx` 自己就带着这个 error）；本计划的代码按仓里先例（`src/kiosk/context/VisionContext.tsx`）在那两行用 `eslint-disable-next-line … -- 理由` 写明了为什么可以。

- [ ] **Step 11：边界规则的变异检查**（每条闸都要亲眼看到它红一次）
```bash
printf "import { jobLabel } from '../admin/jobLabels';\nexport const x = jobLabel;\n" > src/galaxy/__mut_admin.ts
npx eslint src/galaxy/__mut_admin.ts; echo "exit=$?"; rm src/galaxy/__mut_admin.ts
printf "import KioskApp from '../kiosk/KioskApp';\nexport const y = KioskApp;\n" > src/admin/__mut_kiosk.ts
npx eslint src/admin/__mut_kiosk.ts; echo "exit=$?"; rm src/admin/__mut_kiosk.ts
printf "import { jobLabel } from './admin/jobLabels';\nexport const z = jobLabel;\n" > src/__mut_public_admin.ts
npx eslint src/__mut_public_admin.ts; echo "exit=$?"; rm src/__mut_public_admin.ts
```
期望结果：三次都报 `no-restricted-imports`，`exit=1`；三个临时文件都已删除。第三次是 src 根目录下的文件，只有 5c 那条兜底规则管得到它。

- [ ] **Step 12：假数据界面能跑起来，也能构建**
```bash
set -o pipefail
npm run build:admin 2>&1 | tail -3
ls ../static-admin/admin.html ../static-admin/assets | head
lsof -iTCP:5174 -sTCP:LISTEN && echo '!! 5174 已被占用：先用 ps -o command= -p <pid> 查清是谁，别让截图打到别人的服务上'
(VITE_ADMIN_FIXTURE=true npm run dev:admin > /private/tmp/claude-501/admin-dev.log 2>&1 &)
for i in $(seq 1 60); do curl -sf http://127.0.0.1:5174/admin.html | grep -q 'KaTrain 管理后台' && break; sleep 1; done
curl -sf http://127.0.0.1:5174/admin.html | grep -q 'KaTrain 管理后台' && echo ready || echo '!! vite 没起来：看 /private/tmp/claude-501/admin-dev.log'
```
期望结果：构建以 `built in` 结尾；`static-admin/admin.html` 存在；在浏览器里打开 `http://127.0.0.1:5174/admin.html?fixture=mixed&env=test#/cron` 能看到完整界面。

- [ ] **Step 13：对齐设计稿**。拿 Task 1 的参考图逐屏对照，**只调整**上面这些文件里 `sx` 的数值、字号、颜色、间距和文案，让它与确认稿一致。**不改**数据流、data-testid 和状态语义。调整后重跑 Step 10。

- [ ] **Step 14：提交**（提交后用 `--stat` 核对文件清单，防止有文件被 `.gitignore` 吞掉）
```bash
set -o pipefail
cd /Users/fan/Repositories/katrain-admin-console
git add .gitignore katrain/web/ui/admin.html katrain/web/ui/vite.admin.config.ts katrain/web/ui/package.json katrain/web/ui/eslint.config.js katrain/web/ui/src/admin
git status --short --ignored katrain/web/ui/src/admin | grep '^!!' && echo "!! 有文件被忽略" || true
git commit -m "feat(admin-ui): 后台独立入口 + cron 页（假数据），导入边界

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git show --stat HEAD | tail -30
```

---

### Task 3: 四图对比 + 承重实测 + 契约定稿 —— 🛑 Fan 确认后才定契约、进后端

**Files:**
- Create：`superpowers/tracks/admin-console/slice1/impl/*.png`、`side-by-side/*.png`、`diff/*.png`、`visual-review.md`、`measurements.md`
- Create（临时，不提交）：`katrain/web/ui/tests/admin-impl.shoot.spec.ts`
- Create（临时，除非量出了错误数值）：`katrain/web/ui/tests/admin-cron.measure.spec.ts`
- Modify（仅当 Task 1–3 改动了字段时）：`katrain/web/ui/src/admin/api/types.ts`、`superpowers/tracks/admin-console/spec-2026-09-24-admin-console.md` §6.5

**Interfaces:**
- Consumes：Task 1 的 8 张参考图（文件名 = 状态名）；Task 2 的 fixture 地址 `/admin.html?fixture=<状态>&env=<环境>[&signedout=1]#/<路由>` 和 data-testid
- Produces：定稿的契约：`src/admin/api/types.ts` 与 spec §6.5 逐字段一致。Task 10 的 pydantic 模型照它写

- [ ] **Step 1：截实现图**（1440×900，与 Task 1 的 8 张参考图同名、一一对应）

vite dev 没在跑时（比如换了会话接着做），先起 fixture 模式。5174 上可能是别的会话的 vite，就绪判定要认页面标题：
```bash
cd /Users/fan/Repositories/katrain-admin-console/katrain/web/ui
curl -sf http://127.0.0.1:5174/admin.html | grep -q 'KaTrain 管理后台' || (VITE_ADMIN_FIXTURE=true npm run dev:admin > /private/tmp/claude-501/admin-dev.log 2>&1 &)
for i in $(seq 1 60); do curl -sf http://127.0.0.1:5174/admin.html | grep -q 'KaTrain 管理后台' && break; sleep 1; done
curl -sf http://127.0.0.1:5174/admin.html | grep -q 'KaTrain 管理后台' && echo ready || echo '!! vite 没起来：看 /private/tmp/claude-501/admin-dev.log'
```
写一次性的截图脚本 `katrain/web/ui/tests/admin-impl.shoot.spec.ts`：
```ts
// One-off, not committed. run from katrain/web/ui:
//   npx playwright test --config=playwright.vite.config.ts tests/admin-impl.shoot.spec.ts
import { test, expect, type Page } from '@playwright/test';

const BASE = process.env.ADMIN_BASE ?? 'http://127.0.0.1:5174';
const OUT = '../../../superpowers/tracks/admin-console/slice1/impl'; // relative to katrain/web/ui

// Each shot first waits for a marker only that screen has: a failed switch looks exactly like a successful one.
const SHOTS: Array<[string, string, (p: Page) => Promise<void>]> = [
  ['signin', '?fixture=ok&env=test&signedout=1#/signin', (p) => expect(p.getByTestId('signin-env')).toHaveText('正在登录：测试环境')],
  ['ok', '?fixture=ok&env=test#/cron', (p) => expect(p.getByTestId('health-ok')).toHaveCount(9)],
  ['mixed', '?fixture=mixed&env=test#/cron', (p) => expect(p.getByTestId('health-failed')).toBeVisible()],
  ['offline', '?fixture=offline&env=test#/cron', (p) => expect(p.getByTestId('health-offline')).toHaveCount(9)],
  // first load succeeds, the 15 s refresh gets 502: error bar + "页面数据停在"
  ['error', '?fixture=error&env=test#/cron', (p) => expect(p.getByTestId('cron-error')).toContainText('页面数据停在', { timeout: 20_000 })],
  ['missing', '?fixture=missing&env=test#/cron', (p) => expect(p.getByTestId('cron-error')).toContainText('cron 状态表不存在')],
  ['empty', '?fixture=empty&env=test#/cron', (p) => expect(p.getByTestId('cron-empty')).toBeVisible()],
];

for (const [state, query, ready] of SHOTS) {
  test(`impl ${state}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE}/admin.html${query}`);
    await ready(page);
    await page.screenshot({ path: `${OUT}/${state}.png` });
  });
}

test('impl drawer', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${BASE}/admin.html?fixture=mixed&env=test#/cron`);
  await page.getByTestId('cron-row-fetch_list').click();
  for (let i = 0; i < 3; i++) await page.getByRole('button', { name: '加载更早的记录' }).click();
  await expect(page.locator('[data-testid="run-history-scroll"] tbody tr')).toHaveCount(200);
  await page.getByTestId('run-history-scroll').evaluate((e) => { e.scrollTop = 0; });
  await page.screenshot({ path: `${OUT}/drawer.png` });
});
```
```bash
set -o pipefail
mkdir -p ../../../superpowers/tracks/admin-console/slice1/impl
npx playwright test --config=playwright.vite.config.ts tests/admin-impl.shoot.spec.ts --reporter=line 2>&1 | tail -5
rm tests/admin-impl.shoot.spec.ts
diff <(ls ../../../superpowers/tracks/admin-console/slice1/reference) <(ls ../../../superpowers/tracks/admin-console/slice1/impl) && echo same-names
```
Expected：`8 passed`；最后打印 `same-names`。

- [ ] **Step 2：并排图和叠加 / 差异图**：
```bash
cd /Users/fan/Repositories/katrain-admin-console/superpowers/tracks/admin-console/slice1
mkdir -p side-by-side diff
uv run --with pillow python - <<'PY'
from pathlib import Path
from PIL import Image, ImageChops
for ref in sorted(Path("reference").glob("*.png")):
    impl = Path("impl") / ref.name
    a, b = Image.open(ref).convert("RGB"), Image.open(impl).convert("RGB")
    assert a.size == b.size == (1440, 900), (ref.name, a.size, b.size)
    sbs = Image.new("RGB", (2880, 900)); sbs.paste(a, (0, 0)); sbs.paste(b, (1440, 0)); sbs.save(Path("side-by-side") / ref.name)
    ImageChops.difference(a, b).save(Path("diff") / ref.name)
    Image.blend(a, b, 0.5).save(Path("diff") / ref.name.replace(".png", "-overlay.png"))
    print(ref.name, "changed px:", sum(1 for p in ImageChops.difference(a, b).getdata() if p != (0, 0, 0)))
PY
```
期望结果：8 行输出，每一屏都生成了三类图。然后逐屏在 `visual-review.md` 里按这几项记录差异：构图、几何间距、组件层级、字体 / 色彩 / 材质、图标素材、文案、状态语义。

- [ ] **Step 3：承重实测**。取数之前先写死关系式：
  - M1（主区，`?fixture=many`，30 个任务）：应该滚的是 `admin-main`。要求 `scrollHeight > clientHeight`；写入 `scrollTop = 1e6` 后读回 > 0；滚轮拨一次，`scrollTop` 从 0 变成 > 0；滚动之后页头的 `top` 仍是 0；`|main.bottom − innerHeight| ≤ 1`。
  - M2（抽屉，200 条）：应该滚的是 `run-history-scroll`。要求 `scrollHeight > clientHeight`；写入 / 读回、滚轮两项同 M1；`|scroll.bottom − drawerPaper.bottom| ≤ 1`，也就是没有被裁掉；滚到底之后，「加载更早的记录」按钮的 `bottom` ≤ `scroll.bottom`（按钮够得着）。
  - M3（最空，`?fixture=empty`）：`|main.bottom − innerHeight| ≤ 1`，空态提示可见。这一项量的是塌陷，塌陷只有在内容最少时才看得出来。

  写成下面这个一次性的 spec，然后运行：
```ts
// katrain/web/ui/tests/admin-cron.measure.spec.ts — one-off; run: npx playwright test --config=playwright.vite.config.ts tests/admin-cron.measure.spec.ts
import { test, expect, type Page } from '@playwright/test';

const BASE = process.env.ADMIN_BASE ?? 'http://127.0.0.1:5174';
const near = (a: number, b: number) => Math.abs(a - b) <= 1;

async function open(page: Page, fixture: string) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${BASE}/admin.html?fixture=${fixture}&env=test#/cron`);
}

async function wheelMoves(page: Page, testid: string) {
  const el = page.getByTestId(testid);
  await el.evaluate((e) => { e.scrollTop = 1e6; });
  const written = await el.evaluate((e) => e.scrollTop);
  await el.evaluate((e) => { e.scrollTop = 0; });
  await el.hover();
  await page.mouse.wheel(0, 400);
  await expect.poll(() => el.evaluate((e) => e.scrollTop)).toBeGreaterThan(0);
  return written;
}

test('M1 主区能滚', async ({ page }) => {
  await open(page, 'many');
  await expect(page.getByTestId('cron-table')).toBeVisible();
  const m = await page.getByTestId('admin-main').evaluate((e) => ({ sh: e.scrollHeight, ch: e.clientHeight, bottom: e.getBoundingClientRect().bottom, vh: innerHeight }));
  console.log('M1', JSON.stringify(m));
  expect(m.sh).toBeGreaterThan(m.ch);
  expect(near(m.bottom, m.vh)).toBe(true);
  expect(await wheelMoves(page, 'admin-main')).toBeGreaterThan(0);
  expect(await page.locator('header').evaluate((e) => e.getBoundingClientRect().top)).toBe(0);
});

test('M2 抽屉 200 条能滚、没被裁、按钮够得着', async ({ page }) => {
  await open(page, 'mixed');
  await page.getByTestId('cron-row-fetch_list').click();
  for (let i = 0; i < 3; i++) await page.getByRole('button', { name: '加载更早的记录' }).click();
  await expect(page.locator('[data-testid="run-history-scroll"] tbody tr')).toHaveCount(200);
  const scroll = page.getByTestId('run-history-scroll');
  const m = await scroll.evaluate((e) => ({
    sh: e.scrollHeight, ch: e.clientHeight, bottom: e.getBoundingClientRect().bottom,
    paperBottom: (e.closest('.MuiDrawer-paper') as HTMLElement).getBoundingClientRect().bottom,
  }));
  console.log('M2', JSON.stringify(m));
  expect(m.sh).toBeGreaterThan(m.ch);
  expect(near(m.bottom, m.paperBottom)).toBe(true);
  expect(await wheelMoves(page, 'run-history-scroll')).toBeGreaterThan(0);
});

test('M3 最空不塌', async ({ page }) => {
  await open(page, 'empty');
  await expect(page.getByTestId('cron-empty')).toBeVisible();
  const m = await page.getByTestId('admin-main').evaluate((e) => ({ bottom: e.getBoundingClientRect().bottom, vh: innerHeight }));
  console.log('M3', JSON.stringify(m));
  expect(near(m.bottom, m.vh)).toBe(true);
});
```
（M2 数到 200 行时，fixture 的 200 条已经全部加载完，所以「加载更早的记录」按钮在第 3 次点击后应当消失。这一项只记录，不作判据。）

```bash
set -o pipefail
cd /Users/fan/Repositories/katrain-admin-console/katrain/web/ui
npx playwright test --config=playwright.vite.config.ts tests/admin-cron.measure.spec.ts --reporter=line 2>&1 | tail -20
```
期望结果：3 passed，打印出 M1、M2、M3 的数字。全部通过：删掉 spec，把数字和逐条判定写进 `measurements.md`。**量出过错误数值**：先修布局，再把这个 spec 改名为 `tests/admin-cron.spec.ts` 留作几何闸，与修复放在同一个提交里。

- [ ] **Step 4**：停掉本任务起的 vite。只杀命令行里带 `vite.admin.config` 的那个，5174 上可能是别的会话的服务：
```bash
for pid in $(lsof -tiTCP:5174 -sTCP:LISTEN); do ps -o command= -p $pid | grep -q vite.admin.config && kill $pid; done
```
- [ ] **Step 5：提交证据**：`git add superpowers/tracks/admin-console/slice1 katrain/web/ui/src/admin/__fixtures__ && git commit -m "test(admin-ui): cron 页四图对比与承重实测（1440×900）" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"`
- [ ] **Step 6：🛑 停。把并排图、差异图、`visual-review.md` 和 `measurements.md` 交给 Fan。他明确确认之后，才做 Step 7 的契约定稿，然后进入 Task 4（第一个后端任务）。**
- [ ] **Step 7：契约定稿**（Fan 确认之后）。对照 `katrain/web/ui/src/admin/api/types.ts` 和 spec §6.5，逐个字段核对名字、可空性和枚举值；设计稿如果增减了字段，两边同步改。再确认 spec §6.5 末尾的权威边界仍然成立：状态数据由 cron 写、后台只读；`health` 由后台按 `observed_at` 当场算出；任务的中文名在前端。
- [ ] **Step 8：提交契约**。有改动：
```bash
cd /Users/fan/Repositories/katrain-admin-console
git add katrain/web/ui/src/admin/api/types.ts superpowers/tracks/admin-console/spec-2026-09-24-admin-console.md
git commit -m "docs(admin): cron 契约定稿" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```
没有改动：在 `superpowers/tracks/admin-console/slice1/visual-review.md` 末尾记一句「契约无变更（YYYY-MM-DD，Fan 确认四图之后）」，只提交这个文件。

---

### Task 4: 三张新表（web 侧建表，cron 侧同名映射）

**Files:**
- Modify：`katrain/web/core/models_db.py`（末尾追加）
- Modify：`katrain/cron/models.py`（末尾追加）
- Test：`tests/web_ui/test_cron_status_tables_parity.py`

**Interfaces:**
- Produces：`models_db.AdminAuditLog`、`models_db.CronJobStatus`、`models_db.CronJobRun`；`katrain.cron.models.CronJobStatusDB`、`katrain.cron.models.CronJobRunDB`

- [ ] **Step 1：写测试**
```python
# tests/web_ui/test_cron_status_tables_parity.py
"""cron 侧和 web 侧对同一张表各有一个 ORM 类（与 report_tasks 同一做法）。

表只由 katrain-web 的 create_all 建。cron 侧如果多出一列，要等写入时才炸 —— 也就是只在
线上才看得见；少一列则永远写不进去。所以两边的列集合必须完全一致。
"""
from sqlalchemy import create_engine, inspect

from katrain.cron import models as cron_models
from katrain.web.core import models_db

PAIRS = [
    (models_db.CronJobStatus, cron_models.CronJobStatusDB),
    (models_db.CronJobRun, cron_models.CronJobRunDB),
]


def _default(d):
    return None if d is None else repr(getattr(d, "arg", d))


def _shape(model):
    """每一列决定表能收什么的全部属性：带长度的 SQL 类型、时区、可空、主键、单列索引、默认值与 server_default 的内容；
    再加上表的具名索引。"""
    cols = {
        c.name: (str(c.type), getattr(c.type, "timezone", None), c.nullable, c.primary_key, bool(c.index),
                 _default(c.default), _default(c.server_default))
        for c in model.__table__.columns
    }
    indexes = {(i.name, tuple(col.name for col in i.columns)) for i in model.__table__.indexes}
    return cols, indexes


def test_both_sides_map_identical_columns():
    for web, cron in PAIRS:
        assert web.__tablename__ == cron.__tablename__
        assert _shape(web) == _shape(cron), web.__tablename__


def test_web_create_all_builds_the_admin_tables():
    engine = create_engine("sqlite:///:memory:")
    models_db.Base.metadata.create_all(bind=engine)
    assert {"admin_audit_log", "cron_job_status", "cron_job_runs"} <= set(inspect(engine).get_table_names())
```
- [ ] **Step 2**：`CI=true uv run pytest tests/web_ui/test_cron_status_tables_parity.py -q -p no:cacheprovider`。期望结果：FAIL，报 `AttributeError: module 'katrain.web.core.models_db' has no attribute 'CronJobStatus'`。
- [ ] **Step 3：在 `models_db.py` 末尾追加**
```python


# ── Admin console (katrain-admin, superpowers/tracks/admin-console/spec-2026-09-24-admin-console.md) ─────────
# Schema owner is katrain-web (create_all in init_db). katrain-admin never creates tables.


class AdminAuditLog(Base):
    """Who did what in the admin console. Slice 1 writes login_success / login_failed / logout."""

    __tablename__ = "admin_audit_log"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    admin_user_id = Column(Integer, nullable=True)  # NULL for failed logins; no FK so user deletion never blocks
    username = Column(String(150), nullable=False)
    action = Column(String(64), nullable=False)
    target = Column(String(255), nullable=True)
    detail = Column(JSON, nullable=True)


class CronJobStatus(Base):
    """One row per cron job. Written by katrain-cron (katrain/cron/run_recorder.py), read by katrain-admin.
    Mirrored by katrain.cron.models.CronJobStatusDB — column sets must stay identical
    (tests/web_ui/test_cron_status_tables_parity.py)."""

    __tablename__ = "cron_job_status"

    job_name = Column(String(64), primary_key=True)
    kind = Column(String(16), nullable=False)  # interval / loop
    interval_seconds = Column(Integer, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    process_started_at = Column(DateTime(timezone=True), nullable=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    last_started_at = Column(DateTime(timezone=True), nullable=True)
    last_finished_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_status = Column(String(16), nullable=True)  # running / success / errors / failed
    last_duration_ms = Column(Integer, nullable=True)
    last_error = Column(Text, nullable=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    loop_iteration_at = Column(DateTime(timezone=True), nullable=True)
    loop_stats = Column(JSON, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)


class CronJobRun(Base):
    """Run history. Which runs get a row is decided by katrain/cron/run_recorder.py."""

    __tablename__ = "cron_job_runs"

    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String(64), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=False, index=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(16), nullable=False)
    duration_ms = Column(Integer, nullable=True)
    error_count = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)

    __table_args__ = (Index("ix_cron_job_runs_job_started", "job_name", "started_at"),)
```
- [ ] **Step 4：在 `katrain/cron/models.py` 末尾追加**
```python


class CronJobStatusDB(Base):
    """Maps to the same table as katrain.web.core.models_db.CronJobStatus (web owns the schema)."""

    __tablename__ = "cron_job_status"

    job_name = Column(String(64), primary_key=True)
    kind = Column(String(16), nullable=False)
    interval_seconds = Column(Integer, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    process_started_at = Column(DateTime(timezone=True), nullable=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    last_started_at = Column(DateTime(timezone=True), nullable=True)
    last_finished_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_status = Column(String(16), nullable=True)
    last_duration_ms = Column(Integer, nullable=True)
    last_error = Column(Text, nullable=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    loop_iteration_at = Column(DateTime(timezone=True), nullable=True)
    loop_stats = Column(JSON, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)


class CronJobRunDB(Base):
    """Maps to the same table as katrain.web.core.models_db.CronJobRun."""

    __tablename__ = "cron_job_runs"

    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String(64), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=False, index=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(16), nullable=False)
    duration_ms = Column(Integer, nullable=True)
    error_count = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)

    __table_args__ = (Index("ix_cron_job_runs_job_started", "job_name", "started_at"),)
```
- [ ] **Step 5**：重跑 Step 2 的命令。期望结果：2 passed。再跑 `CI=true uv run pytest tests/web_ui/test_cron_import_boundary.py -q -p no:cacheprovider`，期望结果：passed。
- [ ] **Step 6：变异检查**（本任务的改动还没提交，**不要用 `git checkout` 还原**，那会把它们一起冲掉）。两次变异分开做，每次都是备份、改、跑、还原：
```bash
set -o pipefail
cd /Users/fan/Repositories/katrain-admin-console
cp katrain/cron/models.py /private/tmp/claude-501/cron-models.py.bak
# 变异 1：cron 侧 CronJobStatusDB 少一列
python3 -c "import pathlib; p = pathlib.Path('katrain/cron/models.py'); s = p.read_text(); old = '    last_error = Column(Text, nullable=True)\n    consecutive_failures'; assert s.count(old) == 1; p.write_text(s.replace(old, '    consecutive_failures'))"
PYTHONDONTWRITEBYTECODE=1 CI=true uv run pytest tests/web_ui/test_cron_status_tables_parity.py -q -p no:cacheprovider 2>&1 | tail -3
cp /private/tmp/claude-501/cron-models.py.bak katrain/cron/models.py
# 变异 2：只改一列的长度
python3 -c "import pathlib; p = pathlib.Path('katrain/cron/models.py'); s = p.read_text(); old = 'job_name = Column(String(64), primary_key=True)'; assert s.count(old) == 1; p.write_text(s.replace(old, 'job_name = Column(String(255), primary_key=True)'))"
PYTHONDONTWRITEBYTECODE=1 CI=true uv run pytest tests/web_ui/test_cron_status_tables_parity.py -q -p no:cacheprovider 2>&1 | tail -3
cp /private/tmp/claude-501/cron-models.py.bak katrain/cron/models.py
PYTHONDONTWRITEBYTECODE=1 CI=true uv run pytest tests/web_ui/test_cron_status_tables_parity.py -q -p no:cacheprovider 2>&1 | tail -3
```
期望结果：前两次都 FAIL（第二次证明比较已经细到字符串长度）；最后一次 2 passed。
- [ ] **Step 7：提交** `feat(admin): cron 状态 / 运行历史 / 后台审计三张表`（`git add` 上面三个文件）。

---

### Task 5: 后台进程骨架（健康检查、启动闸、静态文件）

**Files:**
- Create：`katrain/web/admin/__init__.py`、`katrain/web/admin/settings.py`、`katrain/web/admin/app.py`、`katrain/web/admin/__main__.py`、`katrain/web/admin/routers/__init__.py`
- Test：`tests/web_ui/test_admin_app.py`

**Interfaces:**
- Produces：`create_admin_app(session_factory=None, static_dir: Path | None = None, env: str | None = None) -> FastAPI`，其中 `app.state.session_factory` 和 `app.state.admin_env` 供依赖读取；`check_startup() -> str`；`NOT_BUILT: str`；`CSP: str`（每个响应都带）

- [ ] **Step 1：写测试**
```python
# tests/web_ui/test_admin_app.py
"""katrain-admin 骨架：独立 app、启动闸、公开站点上零后台路由。"""
import pytest
from fastapi.testclient import TestClient

from katrain.web.admin import settings as admin_settings
from katrain.web.admin.app import NOT_BUILT, create_admin_app
from katrain.web.core.config import settings

STRONG = "k" * 48


def _client(static_dir):
    return TestClient(create_admin_app(session_factory=lambda: None, static_dir=static_dir, env="test"))


def test_health_needs_no_login(tmp_path):
    r = _client(tmp_path).get("/api/admin/health")
    assert r.status_code == 200 and r.json() == {"status": "ok", "env": "test"}


def test_spa_says_so_when_frontend_not_built_then_serves_admin_html(tmp_path):
    r = _client(tmp_path).get("/")
    assert r.status_code == 503 and r.text == NOT_BUILT
    (tmp_path / "admin.html").write_text("<html>admin</html>", encoding="utf-8")
    client = _client(tmp_path)
    assert client.get("/").text == "<html>admin</html>"
    assert client.get("/api/admin/nope").status_code == 404


@pytest.mark.parametrize(
    "mode,key,env,message",
    [("board", STRONG, "test", "KATRAIN_MODE"), ("server", "short", "test", "SECRET_KEY"), ("server", STRONG, "staging", "KATRAIN_ADMIN_ENV")],
)
def test_startup_guards_refuse(monkeypatch, mode, key, env, message):
    monkeypatch.setattr(settings, "KATRAIN_MODE", mode)
    monkeypatch.setattr(settings, "SECRET_KEY", key)
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", env)
    with pytest.raises(RuntimeError, match=message):
        admin_settings.check_startup()


def test_startup_guards_accept_a_sane_config(monkeypatch):
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "SECRET_KEY", STRONG)
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", "prod")
    assert admin_settings.check_startup() == "prod"


def test_every_response_carries_the_csp(tmp_path):
    """令牌在前端 localStorage 里（session.py 说明了为什么不用 cookie），页面这一侧靠 CSP：只许本源脚本、只许向本源发请求。"""
    (tmp_path / "admin.html").write_text("<html>admin</html>", encoding="utf-8")
    client = _client(tmp_path)
    for path in ("/", "/api/admin/health", "/api/admin/nope"):
        csp = client.get(path).headers.get("content-security-policy", "")
        assert "script-src 'self'" in csp and "connect-src 'self'" in csp and "frame-ancestors 'none'" in csp, path


def test_public_app_exposes_no_admin_routes(app):
    """核心隔离性质：公开的 katrain-web 上一条 /api/admin 路由都没有（FastAPI 0.115：include_router 直接展开成 APIRoute）。"""
    paths = [getattr(r, "path", "") or "" for r in app.routes]
    assert [p for p in paths if p.startswith("/api/admin")] == []
    assert any(p.startswith("/api/v1/") for p in paths), "sanity: the probe must actually see the public routes"
```
- [ ] **Step 2**：`CI=true uv run pytest tests/web_ui/test_admin_app.py -q -p no:cacheprovider`。期望结果：FAIL，报 `ModuleNotFoundError: katrain.web.admin`。

- [ ] **Step 3：实现**

`katrain/web/admin/__init__.py`：
```python
"""katrain-admin: the loopback-only admin console (superpowers/tracks/admin-console/spec-2026-09-24-admin-console.md)."""
```
`katrain/web/admin/routers/__init__.py`：
```python
"""Routers mounted under /api/admin by katrain.web.admin.app."""
```
`katrain/web/admin/settings.py`：
```python
"""katrain-admin 的启动配置与启动闸。

后台绝不能在盒子上跑，也不能用弱密钥签会话。环境名会写进令牌：测试机与生产两条隧道各在自己的
本机端口上，令牌放在按端口隔离的 localStorage 里，env 再兜一层，互不串号。
"""
import os

from katrain.web.core.config import assert_secret_key_is_safe, settings

ADMIN_ENVS = ("local", "test", "prod")


def admin_env() -> str:
    return os.getenv("KATRAIN_ADMIN_ENV", "local").strip()


def check_startup() -> str:
    """不安全就抛 RuntimeError；安全就返回环境名。"""
    if settings.KATRAIN_MODE != "server":
        raise RuntimeError(f"katrain-admin 只能在服务端运行（KATRAIN_MODE={settings.KATRAIN_MODE!r}），盒子上不许启动后台。")
    assert_secret_key_is_safe("server", settings.SECRET_KEY)
    env = admin_env()
    if env not in ADMIN_ENVS:
        raise RuntimeError(f"KATRAIN_ADMIN_ENV 必须是 {ADMIN_ENVS} 之一，现在是 {env!r}。")
    return env
```
`katrain/web/admin/app.py`：
```python
"""katrain-admin：独立进程的管理后台。

只挂 /api/admin/* 和后台自己的前端（katrain/web/static-admin/）。公开的 katrain-web 上一条后台路由都没有；
这个进程只在 127.0.0.1 上发布端口，经 SSH 隧道访问。不调 init_db：表结构归 katrain-web。
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from katrain.web.admin import settings as admin_settings

DEFAULT_STATIC_DIR = Path(__file__).resolve().parent.parent / "static-admin"
NOT_BUILT = "后台前端未构建：在 katrain/web/ui 下运行 npm run build:admin"
# 令牌在前端 localStorage 里（session.py），页面这一侧的防线是 CSP：只许加载本源的脚本、只许向本源发请求，
# 页面上万一出现注入，也执行不了外来脚本、发不出令牌。MUI（emotion）运行时插 <style>，所以 style-src 要 'unsafe-inline'。
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
)


def create_admin_app(session_factory=None, static_dir: Path | None = None, env: str | None = None) -> FastAPI:
    if session_factory is None:
        from katrain.web.core.db import SessionLocal

        session_factory = SessionLocal
    app = FastAPI(title="katrain-admin", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.session_factory = session_factory
    app.state.admin_env = env or admin_settings.admin_env()

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/api/admin/health")
    async def health():
        return {"status": "ok", "env": app.state.admin_env}

    # ── API routers (must be registered before the SPA catch-all below) ──

    # ── Frontend ──
    static_root = Path(static_dir) if static_dir else DEFAULT_STATIC_DIR
    index = static_root / "admin.html"
    if (static_root / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static_root / "assets"), name="admin-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            return PlainTextResponse("Not Found", status_code=404)
        if not index.is_file():
            return PlainTextResponse(NOT_BUILT, status_code=503)
        return FileResponse(index)

    return app
```
`katrain/web/admin/__main__.py`：
```python
"""python -m katrain.web.admin [--host 127.0.0.1] [--port 8010]

默认只监听 127.0.0.1。容器里要传 --host 0.0.0.0，由 compose 只把端口发布到宿主机的 127.0.0.1。
"""
import argparse
import logging

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="KaTrain admin console (reach it through an SSH tunnel)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    from katrain.web.admin.app import create_admin_app
    from katrain.web.admin.settings import check_startup

    env = check_startup()
    uvicorn.run(create_admin_app(env=env), host=args.host, port=args.port, log_level=args.log_level)


if __name__ == "__main__":
    main()
```
- [ ] **Step 4**：重跑 Step 2 的命令。期望结果：全部 passed。
- [ ] **Step 5：变异检查**。这条闸守的是「公开站点上零后台路由」，要亲眼看到它能红：在 `katrain/web/server.py` 里紧跟着 `app.include_router(api_router, prefix="/api/v1")` 那一行之后，临时加一行 `app.add_api_route("/api/admin/mut", lambda: {})`，跑 `test_public_app_exposes_no_admin_routes`，确认 FAIL；然后删掉这一行，再确认 PASS。
- [ ] **Step 6：进程能真的起来**：
```bash
KATRAIN_SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_urlsafe(48))") KATRAIN_ADMIN_ENV=local \
  KATRAIN_DATABASE_URL=sqlite:////private/tmp/claude-501/admin-smoke.db uv run python -m katrain.web.admin --port 8019 &
sleep 4; curl -s http://127.0.0.1:8019/api/admin/health; echo; kill %1
```
期望结果：`{"status":"ok","env":"local"}`。
- [ ] **Step 7：提交** `feat(admin): katrain-admin 进程骨架（健康检查、启动闸、SPA）`。

---

### Task 6: 会话、登录 / 登出 / me、审计

**Files:**
- Create：`katrain/web/admin/session.py`、`katrain/web/admin/audit.py`、`katrain/web/admin/routers/auth.py`
- Modify：`katrain/web/admin/app.py`（在「API routers」注释下面挂上 auth router）
- Create：`tests/web_ui/_admin_helpers.py`；Test：`tests/web_ui/test_admin_auth.py`

**Interfaces:**
- Produces：`require_admin(request) -> dict`（读 `Authorization: Bearer <令牌>`；返回的用户 dict 含 `id`、`username`、`is_admin`；任何失败都抛 401）、`bearer_token(request) -> str | None`、`create_session_token(username, env, now=None) -> str`、`username_from_token(token, env) -> str | None`、`audit.record(db, action, username, admin_user_id=None, target=None, detail=None)`
- Produces（接口）：`POST /api/admin/auth/login` → `{username, env, token}`，**不设任何 cookie**；`POST /api/admin/auth/logout` → 204，只记审计；`GET /api/admin/auth/me` → `{username, env}`
- Produces（测试辅助）：`make_admin_client(monkeypatch, tmp_path, env="test") -> (TestClient, Session, engine)`、`login(client, username="boss", password="pw")`（登录，并把令牌设成这个 client 之后每个请求的默认请求头）、`bearer(token) -> dict`

- [ ] **Step 1：测试辅助和测试**

`tests/web_ui/_admin_helpers.py`：
```python
"""katrain-admin 测试共用：内存库 + 管理员 boss / 普通用户 carol / 哈希不可解析的管理员 ghost，外加登录。"""
from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.web.admin.app import create_admin_app
from katrain.web.core import models_db
from katrain.web.core.config import settings


def make_admin_client(monkeypatch, tmp_path, env="test"):
    monkeypatch.setattr(settings, "SECRET_KEY", "k" * 48)
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models_db.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    with Session() as s:
        s.add(models_db.User(username="boss", hashed_password=pwd.hash("pw"), is_admin=True))
        s.add(models_db.User(username="carol", hashed_password=pwd.hash("pw"), is_admin=False))
        s.add(models_db.User(username="ghost", hashed_password="not-a-bcrypt-hash", is_admin=True))
        s.commit()
    client = TestClient(create_admin_app(session_factory=Session, static_dir=tmp_path, env=env))
    return client, Session, engine


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def login(client, username="boss", password="pw"):
    """登录，并把令牌设成这个 client 之后每个请求的默认请求头（和前端每次请求都带 Authorization 一样）。"""
    r = client.post("/api/admin/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    client.headers.update(bearer(r.json()["token"]))
    return r
```

`tests/web_ui/test_admin_auth.py`：
```python
"""后台鉴权：登录/登出/me、令牌的三重校验、撤权即时生效、审计；登录不设任何 cookie。"""
import pytest
from fastapi import HTTPException

from katrain.web.admin.session import create_session_token
from katrain.web.core import models_db
from katrain.web.core.auth import create_access_token
from katrain.web.core.config import settings
from tests.web_ui._admin_helpers import bearer, login, make_admin_client

LOGIN_FAILED = "用户名或密码错误，或该账号没有后台权限"


@pytest.fixture
def ctx(monkeypatch, tmp_path):
    client, Session, _ = make_admin_client(monkeypatch, tmp_path)
    return client, Session


def _audit(Session):
    with Session() as s:
        rows = s.query(models_db.AdminAuditLog).order_by(models_db.AdminAuditLog.id).all()
        return [(r.action, r.username, (r.detail or {}).get("reason")) for r in rows]


def test_login_returns_a_token_and_sets_no_cookie(ctx):
    """令牌只交给页面自己（localStorage 按端口隔离）。cookie 不分端口，本机别的服务会收到它。"""
    client, Session = ctx
    r = login(client)
    body = r.json()
    assert (body["username"], body["env"]) == ("boss", "test") and body["token"]
    assert "set-cookie" not in r.headers
    assert client.get("/api/admin/auth/me").json() == {"username": "boss", "env": "test"}
    assert _audit(Session) == [("login_success", "boss", None)]


def test_no_token_is_401(ctx):
    client, _ = ctx
    assert client.get("/api/admin/auth/me").status_code == 401


@pytest.mark.parametrize(
    "username,password,reason",
    [("carol", "pw", "not_admin"), ("boss", "wrong", "bad_password"), ("nobody", "pw", "unknown_user"), ("ghost", "pw", "bad_password")],
)
def test_login_failures_share_one_message_but_audit_the_reason(ctx, username, password, reason):
    client, Session = ctx
    r = client.post("/api/admin/auth/login", json={"username": username, "password": password})
    assert r.status_code == 401 and r.json() == {"detail": LOGIN_FAILED}
    assert _audit(Session) == [("login_failed", username, reason)]


def test_guest_cannot_even_attempt(ctx):
    client, Session = ctx
    r = client.post("/api/admin/auth/login", json={"username": "guest", "password": "pw"})
    assert r.status_code == 401
    assert _audit(Session) == [("login_failed", "guest", "unknown_user")]


def test_public_access_token_is_rejected(ctx):
    """公开站点的 access token（没有 aud、type 是 access）进不了后台。它同时被 aud、type 两道检查挡住，
    所以这条证明不了任何一道单独在起作用 —— 那由下面三条伪造令牌的用例负责。"""
    client, _ = ctx
    r = client.get("/api/admin/auth/me", headers=bearer(create_access_token(data={"sub": "boss"})))
    assert r.status_code == 401


def _forge(**claims):
    """用同一把 SECRET_KEY 签一个后台令牌，只改传进来的那几项（传 None 表示去掉这一项），单独检验每一道检查。"""
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    body = {"sub": "boss", "type": "admin_session", "aud": "katrain-admin", "env": "test",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    body.update(claims)
    return jwt.encode({k: v for k, v in body.items() if v is not None}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def test_forged_control_token_is_accepted(ctx):
    """对照组：什么都不改的伪造令牌能进。下面两条被拒，才能归因到改掉的那一项。"""
    client, _ = ctx
    assert client.get("/api/admin/auth/me", headers=bearer(_forge())).status_code == 200


def test_token_without_aud_is_rejected(ctx):
    """python-jose 在传了 audience、而令牌里根本没有 aud 时照样放行（2026-09-24 实测）：挡住它的只有显式的 aud 比较。"""
    client, _ = ctx
    assert client.get("/api/admin/auth/me", headers=bearer(_forge(aud=None))).status_code == 401


def test_token_with_the_wrong_type_is_rejected(ctx):
    client, _ = ctx
    assert client.get("/api/admin/auth/me", headers=bearer(_forge(type="access"))).status_code == 401


def test_token_for_other_env_is_rejected(ctx):
    client, _ = ctx
    assert client.get("/api/admin/auth/me", headers=bearer(create_session_token("boss", "prod"))).status_code == 401


@pytest.mark.asyncio
async def test_admin_session_token_is_useless_on_the_public_site(monkeypatch):
    """反方向：公开站点解码时不传 audience，jose 会以 Invalid audience 拒绝带 aud 的后台令牌。"""
    from katrain.web.api.v1.endpoints.auth import get_user_from_token

    monkeypatch.setattr(settings, "SECRET_KEY", "k" * 48)

    class Repo:  # would hand out an admin if decoding ever succeeded
        def get_user_by_username(self, username):
            return {"id": 1, "uuid": None, "username": username, "hashed_password": "", "rank": "20k", "credits": 0, "is_admin": True, "avatar_url": None, "created_at": None}

    with pytest.raises(HTTPException) as excinfo:
        await get_user_from_token(create_session_token("boss", "test"), Repo())
    assert excinfo.value.status_code == 401


def test_revoking_is_admin_takes_effect_on_next_request(ctx):
    client, Session = ctx
    login(client)
    assert client.get("/api/admin/auth/me").status_code == 200
    with Session() as s:
        s.query(models_db.User).filter_by(username="boss").update({"is_admin": False})
        s.commit()
    assert client.get("/api/admin/auth/me").status_code == 401


def test_logout_is_audited(ctx):
    """服务端不存会话：登出 = 前端丢掉令牌 + 这里记一笔审计。撤权靠每次请求都查库的 is_admin。"""
    client, Session = ctx
    login(client)
    assert client.post("/api/admin/auth/logout").status_code == 204
    assert [a[0] for a in _audit(Session)] == ["login_success", "logout"]
```
- [ ] **Step 2**：`CI=true uv run pytest tests/web_ui/test_admin_auth.py -q -p no:cacheprovider`。期望结果：FAIL，报 `ModuleNotFoundError: katrain.web.admin.session`。

- [ ] **Step 3：实现**

`katrain/web/admin/session.py`：
```python
"""后台会话：签发 / 校验令牌、require_admin 依赖。

令牌交给前端放在 localStorage，每次请求带 `Authorization: Bearer <令牌>`；**不用 cookie**。cookie 不按端口
隔离：管理员用同一个浏览器打开过的任何一个 http://localhost:<端口> 服务，都能让浏览器把 cookie 送过去（先把浏览器
引到它自己的页面，再同站请求一次；Path、SameSite、换主机名都挡不住），拿到就能在隧道开着时重放。localStorage
按「协议+主机+端口」隔离，别的端口上的页面读不到；浏览器也不会自动带上它，所以不需要 CSRF 头。页面这一侧的防线是
app.py 给每个响应加的 CSP。

令牌与公开站点的 access token 用同一把 SECRET_KEY，靠三道显式检查区分，每一道都有自己的测试：
  1. aud == "katrain-admin"，**必须显式比较**：python-jose 在传了 audience、而令牌里根本没有 aud 时照样放行
     （2026-09-24 实测），只靠 decode 的 audience 参数，公开站点的 token 就能进后台。
  2. type == "admin_session"：aud 碰巧对上的别种令牌也进不来。
  3. env == 当前环境：测试与生产两条隧道各在自己的端口上，localStorage 本来就分开，env 再兜一层。
反方向：公开站点解码时不传 audience，带 aud 的令牌会被 jose 以 "Invalid audience" 拒掉（同日实测），
所以后台令牌也进不了公开站点。
"""
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

from katrain.web.core.auth import SQLAlchemyUserRepository
from katrain.web.core.config import settings

SESSION_TYPE = "admin_session"
AUDIENCE = "katrain-admin"
SESSION_HOURS = 8


def create_session_token(username: str, env: str, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    claims = {"sub": username, "type": SESSION_TYPE, "aud": AUDIENCE, "env": env, "exp": now + timedelta(hours=SESSION_HOURS)}
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def username_from_token(token: str, env: str) -> str | None:
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], audience=AUDIENCE)
    except JWTError:
        return None
    if claims.get("type") != SESSION_TYPE or claims.get("aud") != AUDIENCE or claims.get("env") != env:
        return None
    sub = claims.get("sub")
    return sub if isinstance(sub, str) and sub else None


def bearer_token(request: Request) -> str | None:
    scheme, _, value = request.headers.get("authorization", "").partition(" ")
    value = value.strip()
    return value if scheme.lower() == "bearer" and value else None


def user_repo(request: Request) -> SQLAlchemyUserRepository:
    return SQLAlchemyUserRepository(request.app.state.session_factory)


async def require_admin(request: Request) -> dict[str, Any]:
    """所有需要登录的后台接口都用它。每次按用户名重新查库，撤掉 is_admin 立即生效。任何失败都回 401。"""
    env = request.app.state.admin_env
    token = bearer_token(request)
    username = username_from_token(token, env) if token else None
    user = user_repo(request).get_user_by_username(username) if username else None
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或会话已失效")
    return user
```
`katrain/web/admin/audit.py`：
```python
"""后台操作审计（admin_audit_log）。以后每个会产生写操作的后台切片，都必须调用 record()。"""
from typing import Any

from katrain.web.core import models_db


def record(db, action: str, username: str, admin_user_id: int | None = None, target: str | None = None,
           detail: dict[str, Any] | None = None) -> None:
    db.add(models_db.AdminAuditLog(action=action, username=username[:150], admin_user_id=admin_user_id,
                                   target=target, detail=detail))
    db.commit()
```
`katrain/web/admin/routers/auth.py`：
```python
"""/api/admin/auth：登录、登出、我是谁。"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from katrain.web.admin import audit
from katrain.web.admin.session import create_session_token, require_admin, user_repo
from katrain.web.core.auth import verify_password
from katrain.web.core.box_sso import GUEST_USERNAME

router = APIRouter()

LOGIN_FAILED = "用户名或密码错误，或该账号没有后台权限"


class LoginBody(BaseModel):
    username: str
    password: str


class Me(BaseModel):
    username: str
    env: str


class LoginOut(Me):
    token: str


def _password_ok(password: str, hashed: str) -> bool:
    try:
        return verify_password(password, hashed)
    except (ValueError, TypeError):  # shadow/placeholder rows carry hashes passlib cannot even parse
        return False


@router.post("/login", response_model=LoginOut)
async def login(body: LoginBody, request: Request):
    env = request.app.state.admin_env
    username = body.username.strip()
    user = None if username.lower() == GUEST_USERNAME else user_repo(request).get_user_by_username(username)
    if user is None:
        reason = "unknown_user"
    elif not _password_ok(body.password, user["hashed_password"]):
        reason = "bad_password"
    elif not user.get("is_admin"):
        reason = "not_admin"
    else:
        reason = None
    with request.app.state.session_factory() as db:
        if reason:
            audit.record(db, "login_failed", username, detail={"reason": reason})
        else:
            audit.record(db, "login_success", user["username"], admin_user_id=user["id"])
    if reason:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=LOGIN_FAILED)
    return LoginOut(username=user["username"], env=env, token=create_session_token(user["username"], env))


@router.post("/logout", status_code=204)
async def logout(request: Request, admin: dict = Depends(require_admin)):
    """服务端不存会话：前端丢掉令牌就是登出，这里只记审计。撤权靠每次请求都查库的 is_admin。"""
    with request.app.state.session_factory() as db:
        audit.record(db, "logout", admin["username"], admin_user_id=admin["id"])
    return Response(status_code=204)


@router.get("/me", response_model=Me)
async def me(request: Request, admin: dict = Depends(require_admin)):
    return Me(username=admin["username"], env=request.app.state.admin_env)
```
在 `app.py` 里：文件顶部的 import 区加上 `from katrain.web.admin.routers import auth as auth_router`；再在 `# ── API routers (must be registered before the SPA catch-all below) ──` 这一行下面补上：
```python
    app.include_router(auth_router.router, prefix="/api/admin/auth")
```
- [ ] **Step 4**：`CI=true uv run pytest tests/web_ui/test_admin_auth.py tests/web_ui/test_admin_app.py -q -p no:cacheprovider`。期望结果：全部 passed。
- [ ] **Step 5：变异检查**。两道检查各做一次，每次都是：先 `cp katrain/web/admin/session.py /private/tmp/claude-501/session.py.bak`，改，用 `PYTHONDONTWRITEBYTECODE=1 CI=true uv run pytest tests/web_ui/test_admin_auth.py -q -p no:cacheprovider` 跑，再 `cp /private/tmp/claude-501/session.py.bak katrain/web/admin/session.py` 还原：
  - 删掉 `username_from_token` 里的 `claims.get("aud") != AUDIENCE or ` → 只有 `test_token_without_aud_is_rejected` 变红；
  - 删掉 `claims.get("type") != SESSION_TYPE or ` → 只有 `test_token_with_the_wrong_type_is_rejected` 变红。
  （`test_public_access_token_is_rejected` 两次都还是绿的：公开令牌同时被两道挡住，这正是要用伪造令牌单独检验每一道的原因。）还原之后全部回到绿。
- [ ] **Step 6：提交** `feat(admin): 后台会话 —— 登录 / 登出 / me、令牌三重校验、Bearer 不用 cookie、审计`（`git add` 上面列出的文件）。

---

### Task 7: cron 运行记录器

**Files:**
- Create：`katrain/cron/run_recorder.py`
- Test：`tests/web_ui/test_cron_run_recorder.py`

**Interfaces:**
- Consumes：Task 4 的 `CronJobStatusDB`、`CronJobRunDB`
- Produces：
  - `install_error_capture() -> None`
  - `RunRecorder(session_factory, clock=utcnow)`，方法有：
    - `.register(jobs: list[tuple[str, str, int | None, bool]]) -> bool`（写进去了没有）、`.ensure_registered() -> bool`（没写进去就再试一次）
    - `async .run(job)`
    - `.enter_loop(name) -> Token`、`.exit_loop(token)`
    - `.loop_started(name)`
    - `.record_loop_crash(name, exc)`
    - `.heartbeat(loop_jobs: dict)`
    - `async .heartbeat_forever(loop_jobs, interval, stop: asyncio.Event)`
  - loop 任务需要提供的接口：`job.name`、`job.last_iteration_at: datetime | None`、`job.heartbeat_stats() -> dict`
  - 行为约定：登记时把本进程启动之前留下的 `running` 历史标成 `failed`；登记没写进去（表还没建、库一时连不上）时，每次 `heartbeat` 先重试完整的登记

- [ ] **Step 1：写测试**
```python
# tests/web_ui/test_cron_run_recorder.py
"""cron 运行记录器（katrain/cron/run_recorder.py）。表由 web 侧的 create_all 建，和生产一致。"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.cron.models import CronJobRunDB, CronJobStatusDB
from katrain.cron.run_recorder import RunRecorder, install_error_capture
from katrain.web.core import models_db


@pytest.fixture
def Session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models_db.Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


class Clock:
    def __init__(self):
        self.now = datetime(2026, 9, 24, 8, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


class Job:
    def __init__(self, name, behaviour):
        self.name = name
        self._behaviour = behaviour

    async def run(self):
        await self._behaviour()


async def _ok():
    pass


async def _swallowed():
    try:
        raise ValueError("upstream 500")
    except Exception:
        logging.getLogger("katrain_cron.cleanup").exception("CleanupJob failed")  # cleanup.py's idiom


async def _raises():
    raise RuntimeError("boom")


def _recorder(Session, *jobs):
    install_error_capture()
    rec = RunRecorder(Session, clock=Clock())
    rec.register([(name, "interval", interval, True) for name, interval in jobs])
    return rec


def _status(Session, name):
    with Session() as s:
        return s.get(CronJobStatusDB, name)


def _runs(Session, name):
    with Session() as s:
        return [r.status for r in s.query(CronJobRunDB).filter_by(job_name=name).order_by(CronJobRunDB.id)]


def test_success_is_recorded_as_success(Session):
    rec = _recorder(Session, ("fetch_list", 60))
    asyncio.run(rec.run(Job("fetch_list", _ok)))
    row = _status(Session, "fetch_list")
    assert (row.last_status, row.consecutive_failures) == ("success", 0)
    assert _runs(Session, "fetch_list") == ["success"]


def test_a_job_that_swallows_its_exception_is_recorded_as_errors_not_success(Session):
    rec = _recorder(Session, ("cleanup", 86400))
    asyncio.run(rec.run(Job("cleanup", _swallowed)))
    row = _status(Session, "cleanup")
    assert row.last_status == "errors"
    assert "CleanupJob failed" in row.last_error and "ValueError: upstream 500" in row.last_error
    assert row.consecutive_failures == 1


def test_an_escaping_exception_is_failed_and_re_raised(Session):
    rec = _recorder(Session, ("translate", 120))
    with pytest.raises(RuntimeError):
        asyncio.run(rec.run(Job("translate", _raises)))
    row = _status(Session, "translate")
    assert (row.last_status, row.last_error) == ("failed", "RuntimeError: boom")
    assert _runs(Session, "translate") == ["failed"]


def test_sub_minute_jobs_keep_only_unsuccessful_runs(Session):
    rec = _recorder(Session, ("poll_moves", 3))
    asyncio.run(rec.run(Job("poll_moves", _ok)))
    asyncio.run(rec.run(Job("poll_moves", _ok)))
    assert _runs(Session, "poll_moves") == []
    with pytest.raises(RuntimeError):
        asyncio.run(rec.run(Job("poll_moves", _raises)))
    assert _runs(Session, "poll_moves") == ["failed"]
    assert _status(Session, "poll_moves").last_status == "failed"


def test_recorder_write_failure_never_breaks_the_job(Session):
    rec = _recorder(Session, ("fetch_list", 60))
    ran = []

    async def _work():
        ran.append(1)

    def _db_down():
        raise RuntimeError("db down")

    rec._session_factory = _db_down
    asyncio.run(rec.run(Job("fetch_list", _work)))  # must not raise
    assert ran == [1]


def test_errors_logged_outside_a_run_are_not_attributed_to_any_job(Session):
    rec = _recorder(Session, ("fetch_list", 60))
    logging.getLogger("katrain_cron.elsewhere").error("unrelated")
    asyncio.run(rec.run(Job("fetch_list", _ok)))
    assert _status(Session, "fetch_list").last_status == "success"


def test_register_drops_rows_of_jobs_that_no_longer_exist(Session):
    _recorder(Session, ("renamed_away", 60))
    _recorder(Session, ("fetch_list", 60))
    with Session() as s:
        assert [r.job_name for r in s.query(CronJobStatusDB)] == ["fetch_list"]


def test_loop_crash_then_heartbeat(Session):
    clock = Clock()
    rec = RunRecorder(Session, clock=clock)
    rec.register([("analyze", "loop", None, True)])

    class Loop:
        name = "analyze"
        last_iteration_at = clock.now - timedelta(seconds=2)

        def heartbeat_stats(self):
            return {"in_flight": 3, "capacity": 16}

    rec.record_loop_crash("analyze", RuntimeError("katago gone"))
    rec.heartbeat({"analyze": Loop()})
    row = _status(Session, "analyze")
    assert row.loop_stats["in_flight"] == 3 and row.loop_stats["capacity"] == 16
    assert row.last_status == "failed" and "katago gone" in row.last_error
    assert row.consecutive_failures == 1  # the loop has not moved since the crash
    assert _runs(Session, "analyze") == ["failed"]

    Loop.last_iteration_at = clock.now + timedelta(seconds=15)  # restarted and iterating again
    rec.heartbeat({"analyze": Loop()})
    assert _status(Session, "analyze").consecutive_failures == 0


def test_registration_is_retried_until_the_table_exists():
    """cron 比 katrain-web 先启动：register() 时表还不存在，返回 False；web 建表之后，下一次心跳把登记补上。"""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    S = sessionmaker(bind=engine)
    rec = RunRecorder(S, clock=Clock())
    assert rec.register([("fetch_list", "interval", 60, True), ("analyze", "loop", None, True)]) is False
    models_db.Base.metadata.create_all(bind=engine)  # katrain-web starts and creates them
    rec.heartbeat({})  # 补登记必须由心跳自己做：这里不能再调 ensure_registered()，否则测不出心跳漏了它
    with S() as s:
        assert sorted(r.job_name for r in s.query(CronJobStatusDB)) == ["analyze", "fetch_list"]


def test_register_closes_runs_left_running_by_a_process_that_died(Session):
    """SIGKILL / OOM：上一个进程开了头、没来得及收尾的那条历史，不能在抽屉里永远「运行中」。"""
    with Session() as s:
        s.add(CronJobRunDB(job_name="fetch_list", started_at=Clock().now - timedelta(minutes=5), status="running", error_count=0))
        s.commit()
    _recorder(Session, ("fetch_list", 60))
    with Session() as s:
        run = s.query(CronJobRunDB).one()
        assert (run.status, run.finished_at is not None) == ("failed", True)
        assert "结束前退出" in run.error


def test_late_registration_closes_only_runs_from_before_this_process(Session):
    """首次登记没写进去（库一时连不上），之后在心跳里补做：只收尾本进程启动之前留下的 running，
    本进程自己正在跑的那一次不能被标成失败。"""
    clock = Clock()
    with Session() as s:
        s.add(CronJobRunDB(job_name="fetch_list", started_at=clock.now - timedelta(minutes=5), status="running", error_count=0))
        s.commit()
    rec = RunRecorder(Session, clock=clock)

    def _db_down():
        raise RuntimeError("db down")

    rec._session_factory = _db_down
    assert rec.register([("fetch_list", "interval", 60, True)]) is False
    rec._session_factory = Session
    clock.now += timedelta(seconds=30)
    with Session() as s:  # this process's own run, started after the process did
        s.add(CronJobRunDB(job_name="fetch_list", started_at=clock.now, status="running", error_count=0))
        s.commit()
    rec.heartbeat({})
    with Session() as s:
        assert [r.status for r in s.query(CronJobRunDB).order_by(CronJobRunDB.started_at)] == ["failed", "running"]
    assert _status(Session, "fetch_list") is not None
```
- [ ] **Step 2**：`CI=true uv run pytest tests/web_ui/test_cron_run_recorder.py -q -p no:cacheprovider`。期望结果：FAIL，报 `ModuleNotFoundError: katrain.cron.run_recorder`。

- [ ] **Step 3：实现 `katrain/cron/run_recorder.py`**
```python
"""把每个 cron 任务的运行情况写进 cron_job_status / cron_job_runs，供 katrain-admin 只读展示。

只依赖标准库、sqlalchemy 和 katrain.cron.*：Dockerfile.cron 只 COPY katrain/cron/，
由 tests/web_ui/test_cron_import_boundary.py 守着。表由 katrain-web 的 create_all 建；
cron 如果比 web 先启动，登记时表还不存在，写入失败按规矩 1 处理；web 建表之后，下一次心跳会把缺的状态行补上。

三条硬规矩：
1. 记录器自己出错，只记一条 WARNING，绝不影响任务本身。后果是心跳过期、后台显示「失联」：
   坏了会自己露出来，不会被藏住。
2. 任务吞掉了异常、只打一条 ERROR 日志（cleanup.py 的 `except Exception: logger.exception`），
   也必须被看见：运行期间挂一个 ContextVar，根 logger 上的 ErrorCapture 把 ERROR 记到这次运行上。
   记录器自己写库都放在 context 之外，所以它自己的报错不会记到任务头上。
3. 时间一律用 datetime.now(timezone.utc)。
"""

import asyncio
import contextvars
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import delete

from katrain.cron.models import CronJobRunDB, CronJobStatusDB

logger = logging.getLogger("katrain_cron.recorder")

ERROR_TEXT_LIMIT = 2000
# 间隔 ≥ 60 秒的任务，每次运行都进历史；更频繁的（poll_moves 3 秒一次）只记不成功的那几次。
RECORD_EVERY_RUN_MIN_INTERVAL = 60
PREVIOUS_PROCESS_EXITED = "cron 进程在这次运行结束前退出了（重启、部署或被杀）"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ErrorSink:
    """一次 interval 运行、或一条常驻循环的整个生命期里，收集到的 ERROR 日志。"""

    count: int = 0
    first: str | None = None
    last: str | None = None
    last_at: datetime | None = None

    def add(self, text: str) -> None:
        text = text[:ERROR_TEXT_LIMIT]
        self.count += 1
        if self.first is None:
            self.first = text
        self.last = text
        self.last_at = utcnow()


_current_sink: contextvars.ContextVar[ErrorSink | None] = contextvars.ContextVar("katrain_cron_error_sink", default=None)


class ErrorCapture(logging.Handler):
    """挂在根 logger 上。当前 context 里有 sink 时，把 ERROR 及以上记进去；没有就什么也不做。"""

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)

    def emit(self, record: logging.LogRecord) -> None:
        sink = _current_sink.get()
        if sink is None:
            return
        try:
            text = f"[{record.name}] {record.getMessage()}"
            if record.exc_info and record.exc_info[1] is not None:
                exc = record.exc_info[1]
                text = f"{text}: {type(exc).__name__}: {exc}"
            sink.add(text)
        except Exception:  # noqa: BLE001 — a logging handler must never raise
            pass


def install_error_capture() -> None:
    root = logging.getLogger()
    if not any(isinstance(h, ErrorCapture) for h in root.handlers):
        root.addHandler(ErrorCapture())


@dataclass
class _LoopState:
    sink: ErrorSink = field(default_factory=ErrorSink)
    last_crash_at: datetime | None = None


class RunRecorder:
    def __init__(self, session_factory, clock=utcnow):
        self._session_factory = session_factory
        self._clock = clock
        self._registry: list[tuple[str, str, int | None, bool]] = []
        self._process_started_at: datetime | None = None
        self._registered = False
        self._intervals: dict[str, int | None] = {}
        self._loops: dict[str, _LoopState] = {}

    # ── 进程启动时登记 ────────────────────────────────────────────────────────
    def register(self, jobs: list[tuple[str, str, int | None, bool]]) -> bool:
        """jobs = [(name, kind, interval_seconds, enabled)]，停用的也登记。返回是否写进去了。

        表还不存在（cron 比 katrain-web 先启动）或数据库一时连不上时写不进去：调度器最多等一会儿再发起第一次运行，
        之后每次 heartbeat 都会重试，直到写进去为止。"""
        self._registry = list(jobs)
        self._intervals = {name: interval for name, _kind, interval, _enabled in jobs}
        self._process_started_at = self._clock()
        return self.ensure_registered()

    def ensure_registered(self) -> bool:
        if not self._registered and self._registry:
            self._registered = self._write(self._register_rows, self._process_started_at) is True
        return self._registered

    def _register_rows(self, db, started):
        """upsert 全部任务，删掉代码里已经不存在的旧行；本进程启动之前开了头、没来得及收尾的运行（重启、部署、
        SIGKILL、OOM）一律标成失败。只收尾 started 之前的：登记若是在心跳里补做的，本进程自己的运行这时可能正在跑。"""
        now = self._clock()
        db.execute(delete(CronJobStatusDB).where(CronJobStatusDB.job_name.notin_([j[0] for j in self._registry])))
        stale = db.query(CronJobRunDB).filter(CronJobRunDB.status == "running", CronJobRunDB.started_at < started)
        for run in stale:
            run.status, run.finished_at, run.error = "failed", now, PREVIOUS_PROCESS_EXITED
        for name, kind, interval, enabled in self._registry:
            row = db.get(CronJobStatusDB, name)
            if row is None:
                row = CronJobStatusDB(job_name=name, consecutive_failures=0)
                db.add(row)
            row.kind, row.interval_seconds, row.enabled = kind, interval, enabled
            row.process_started_at = started
            row.heartbeat_at = row.updated_at = now
        return True

    # ── interval 任务 ─────────────────────────────────────────────────────────
    async def run(self, job) -> None:
        """包住一次 interval 运行。任务的异常原样再抛，交给调用方（APScheduler）记日志。"""
        name = job.name
        keep = (self._intervals.get(name) or 0) >= RECORD_EVERY_RUN_MIN_INTERVAL
        started = self._clock()
        t0 = time.monotonic()
        run_id = self._write(self._start_rows, name, started, keep)
        sink = ErrorSink()
        token = _current_sink.set(sink)
        exc: Exception | None = None
        cancelled = False
        try:
            await job.run()
        except asyncio.CancelledError:
            cancelled = True
            raise
        except Exception as e:
            exc = e
            raise
        finally:
            _current_sink.reset(token)
            if not cancelled:  # 进程关停时被取消：不写结束；下次启动时那一次立即运行会覆盖状态
                status = "failed" if exc is not None else ("errors" if sink.count else "success")
                # 吞掉异常的运行记第一条 ERROR：后面的报错多半是它引起的；error_count 记着一共几条。
                error = f"{type(exc).__name__}: {exc}"[:ERROR_TEXT_LIMIT] if exc is not None else sink.first
                duration_ms = int((time.monotonic() - t0) * 1000)
                self._write(self._finish_rows, name, run_id, started, status, error, sink.count, duration_ms, keep)

    def _start_rows(self, db, name, started, keep):
        row = db.get(CronJobStatusDB, name)
        if row is not None:
            row.last_started_at, row.last_status, row.updated_at = started, "running", started
        if not keep:
            return None
        run = CronJobRunDB(job_name=name, started_at=started, status="running", error_count=0)
        db.add(run)
        db.flush()
        return run.id

    def _finish_rows(self, db, name, run_id, started, status, error, error_count, duration_ms, keep):
        now = self._clock()
        row = db.get(CronJobStatusDB, name)
        if row is not None:
            row.last_finished_at, row.last_status, row.last_duration_ms, row.updated_at = now, status, duration_ms, now
            if status == "success":
                row.last_success_at = now
                row.consecutive_failures = 0
            else:
                row.last_error = error
                row.consecutive_failures = (row.consecutive_failures or 0) + 1
        run = db.get(CronJobRunDB, run_id) if run_id is not None else None
        if run is not None:
            run.finished_at, run.status, run.duration_ms = now, status, duration_ms
            run.error_count, run.error = error_count, error
        elif not keep and status != "success":
            db.add(CronJobRunDB(job_name=name, started_at=started, finished_at=now, status=status,
                                duration_ms=duration_ms, error_count=error_count, error=error))

    # ── 常驻循环 ──────────────────────────────────────────────────────────────
    def enter_loop(self, name: str) -> contextvars.Token:
        return _current_sink.set(self._loops.setdefault(name, _LoopState()).sink)

    def exit_loop(self, token: contextvars.Token) -> None:
        _current_sink.reset(token)

    def loop_started(self, name: str) -> None:
        self._write(self._loop_started_rows, name, self._clock())

    def _loop_started_rows(self, db, name, now):
        row = db.get(CronJobStatusDB, name)
        if row is not None:
            row.last_started_at, row.last_status, row.updated_at = now, "running", now

    def record_loop_crash(self, name: str, exc: BaseException) -> None:
        now = self._clock()
        self._loops.setdefault(name, _LoopState()).last_crash_at = now
        self._write(self._loop_crash_rows, name, now, f"{type(exc).__name__}: {exc}"[:ERROR_TEXT_LIMIT])

    def _loop_crash_rows(self, db, name, now, error):
        row = db.get(CronJobStatusDB, name)
        if row is not None:
            row.last_status, row.last_error, row.updated_at = "failed", error, now
            row.consecutive_failures = (row.consecutive_failures or 0) + 1
        db.add(CronJobRunDB(job_name=name, started_at=now, finished_at=now, status="failed", error_count=1, error=error))

    # ── 心跳 ──────────────────────────────────────────────────────────────────
    def heartbeat(self, loop_jobs: dict) -> None:
        self.ensure_registered()  # 登记还没写进去（表是后来才建的、库一时连不上）就先补做
        snapshot = {}
        for name, job in loop_jobs.items():
            state = self._loops.setdefault(name, _LoopState())
            stats = dict(job.heartbeat_stats())
            stats["errors_total"] = state.sink.count
            stats["last_error_at"] = state.sink.last_at.isoformat() if state.sink.last_at else None
            snapshot[name] = (getattr(job, "last_iteration_at", None), stats, state.sink.last, state.last_crash_at)
        self._write(self._heartbeat_rows, self._clock(), snapshot)

    def _heartbeat_rows(self, db, now, snapshot):
        for row in db.query(CronJobStatusDB).filter(CronJobStatusDB.job_name.in_(list(self._intervals))):
            row.heartbeat_at = row.updated_at = now
            if row.job_name not in snapshot:
                continue
            iteration_at, stats, last_error, last_crash_at = snapshot[row.job_name]
            row.loop_iteration_at, row.loop_stats = iteration_at, stats
            if last_error:
                row.last_error = last_error
            if iteration_at is not None and (last_crash_at is None or iteration_at > last_crash_at):
                row.consecutive_failures = 0

    async def heartbeat_forever(self, loop_jobs: dict, interval: float, stop: asyncio.Event) -> None:
        while not stop.is_set():
            self.heartbeat(loop_jobs)
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    # ── 写库（规矩 1）─────────────────────────────────────────────────────────
    def _write(self, fn, *args):
        try:
            with self._session_factory() as db:
                result = fn(db, *args)
                db.commit()
                return result
        except Exception:  # noqa: BLE001 — the recorder must never break a job
            logger.warning("cron run recorder write failed (%s)", fn.__name__, exc_info=True)
            return None
```
- [ ] **Step 4**：`CI=true uv run pytest tests/web_ui/test_cron_run_recorder.py tests/web_ui/test_cron_import_boundary.py -q -p no:cacheprovider`。期望结果：全部 PASS。
- [ ] **Step 5：变异检查**：把 `ErrorCapture.emit` 的第一行改成 `sink = None`，确认 `test_a_job_that_swallows_…` 变红；然后还原。
- [ ] **Step 6：提交** `feat(cron): 运行记录器 —— 状态、历史、吞掉的异常也看得见、心跳`。

---

### Task 8: 接进调度器 + 常驻循环 + 清理 + 配置

**Files:**
- Modify：`katrain/cron/config.py`（第 109 行 `CLEANUP_INTERVAL` 之后）
- Modify：`katrain/cron/scheduler.py`（整个文件，给出改后的全文）
- Modify：`katrain/cron/jobs/analyze.py`（import；`__init__`；while 循环的开头；Refill 那两行；新增方法）
- Modify：`katrain/cron/jobs/report_analyze.py`（`__init__`；while 循环的开头；新增方法）
- Modify：`katrain/cron/jobs/cleanup.py`
- Modify：`pyproject.toml`（新增 `cron` extra）、`uv.lock`、`requirements-cron.txt`（APScheduler 加上限 `<4`）
- Test：`tests/web_ui/test_cron_run_recorder.py`（追加三条）

**Interfaces:**
- Consumes：Task 7 的 `install_error_capture()`、`RunRecorder(session_factory)`、`.register(jobs)`、`async .run(job)`、`.enter_loop(name) -> Token`、`.exit_loop(token)`、`.loop_started(name)`、`.record_loop_crash(name, exc)`、`async .heartbeat_forever(loop_jobs, interval, stop)`；Task 4 的 `CronJobRunDB`
- Produces：`AnalyzeJob.last_iteration_at: datetime | None` 和 `AnalyzeJob.heartbeat_stats() -> {"in_flight": int, "capacity": int}`，`ReportAnalyzerJob` 也有这两项；`config.HEARTBEAT_INTERVAL`（默认 30）、`config.RUNS_RETENTION_DAYS`（默认 14）；`CronScheduler._schedule(job, interval)`：每一次运行（包括启动时立刻跑的那一次）都经 APScheduler 和记录器

- [ ] **Step 0：让本地装得上 cron 的依赖**。APScheduler、beautifulsoup4、lxml 原先只写在 `requirements-cron.txt` 里（给 `Dockerfile.cron` 用），`uv sync --extra web` 装不上：本任务的调度器测试一 import 就报 `ModuleNotFoundError: apscheduler`，Task 12 本机也起不来 cron。在 `pyproject.toml` 的 `[project.optional-dependencies]` 里、`board = [...]` 那一块之后加：
```toml
# katrain-cron 自己的依赖。Dockerfile.cron 从 requirements-cron.txt 装，两处要一起改；本地跑 cron 和调度器测试时装这个 extra。
cron = [
    "apscheduler>=3.10,<4",
    "beautifulsoup4",
    "lxml",
]
```
`requirements-cron.txt` 里的 `apscheduler>=3.10` 改成 `apscheduler>=3.10,<4`（4.x 是另一套 API，本计划用的是 3.x 的 `add_job(..., next_run_time=...)`）。然后：
```bash
cd /Users/fan/Repositories/katrain-admin-console
uv lock && uv sync --extra web --extra cron
.venv/bin/python -c "import apscheduler, bs4, lxml; print('cron deps ok, apscheduler', apscheduler.__version__)"
git diff --stat pyproject.toml uv.lock requirements-cron.txt
```
期望结果：打印 `cron deps ok, apscheduler 3.x.y`；`uv.lock` 只新增 apscheduler、tzlocal、beautifulsoup4、soupsieve、lxml 这几项。有别的包跟着升级就停下，看清楚再说。

- [ ] **Step 1：追加测试**（加在 `test_cron_run_recorder.py` 末尾）：
```python
def test_every_interval_run_is_started_by_apscheduler_through_the_recorder():
    """包括启动时立刻跑的那一次：只有一条路径，max_instances=1 才管得住全部运行。"""
    from katrain.cron.scheduler import CronScheduler

    sched = CronScheduler()
    added = []
    sched._scheduler.add_job = lambda func, trigger, **kw: added.append((func, trigger, kw))
    sched._schedule(Job("fetch_list", _ok), 60)
    ((func, trigger, kw),) = added
    assert func == sched._recorder.run and trigger == "interval"
    assert kw["args"][0].name == "fetch_list" and kw["seconds"] == 60 and kw["max_instances"] == 1
    assert kw["next_run_time"] is not None  # first run right away, still through APScheduler


def test_loop_jobs_expose_heartbeat_stats_without_touching_the_db():
    from katrain.cron import config
    from katrain.cron.jobs.analyze import AnalyzeJob
    from katrain.cron.jobs.report_analyze import ReportAnalyzerJob

    analyze, report = AnalyzeJob(), ReportAnalyzerJob()
    assert analyze.last_iteration_at is None and report.last_iteration_at is None
    assert analyze.heartbeat_stats() == {"in_flight": 0, "capacity": config.ANALYSIS_WINDOW_SIZE}
    assert report.heartbeat_stats() == {"in_flight": 0, "capacity": max(1, config.REPORT_CONCURRENCY)}


def test_cleanup_prunes_cron_runs_older_than_retention(Session, monkeypatch):
    from katrain.cron import config
    from katrain.cron.jobs import cleanup

    monkeypatch.setattr(cleanup, "SessionLocal", Session)
    now = datetime.now(timezone.utc)
    with Session() as s:
        s.add_all([
            CronJobRunDB(job_name="fetch_list", started_at=now - timedelta(days=config.RUNS_RETENTION_DAYS + 1), status="success", error_count=0),
            CronJobRunDB(job_name="fetch_list", started_at=now - timedelta(days=1), status="success", error_count=0),
        ])
        s.commit()
    asyncio.run(cleanup.CleanupJob().run())
    with Session() as s:
        assert s.query(CronJobRunDB).count() == 1
```
- [ ] **Step 2**：`CI=true uv run pytest tests/web_ui/test_cron_run_recorder.py -q -p no:cacheprovider`。期望结果：新加的三条都 FAIL，都报 `AttributeError`：`_schedule`、`last_iteration_at`、`RUNS_RETENTION_DAYS` 都还不存在。

- [ ] **Step 3：`config.py`**。在 `CLEANUP_INTERVAL = …` 那一行之后加：
```python

# Run recorder for the admin console (superpowers/tracks/admin-console/spec-2026-09-24-admin-console.md §6)
HEARTBEAT_INTERVAL = int(os.getenv("CRON_HEARTBEAT_INTERVAL", "30"))
RUNS_RETENTION_DAYS = int(os.getenv("CRON_RUNS_RETENTION_DAYS", "14"))
```

- [ ] **Step 4：`scheduler.py` 改后全文**
```python
"""APScheduler wrapper that registers and runs all cron jobs.

Every run goes through RunRecorder (katrain/cron/run_recorder.py) so katrain-admin can show it.
"""

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from katrain.cron import config
from katrain.cron.db import SessionLocal
from katrain.cron.run_recorder import RunRecorder, install_error_capture

logger = logging.getLogger("katrain_cron.scheduler")


class CronScheduler:
    """Manages all scheduled jobs and persistent loop jobs (Analyze, ReportAnalyze)."""

    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._analyze_task: asyncio.Task | None = None
        self._report_analyze_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()
        self._recorder = RunRecorder(SessionLocal)
        self._loop_jobs: dict = {}

    async def start(self):
        """Register jobs, start scheduler, and run until shutdown."""
        from katrain.cron.jobs.fetch_list import FetchListJob
        from katrain.cron.jobs.poll_moves import PollMovesJob
        from katrain.cron.jobs.poll_pandanet import PandanetPollJob
        from katrain.cron.jobs.translate import TranslateJob
        from katrain.cron.jobs.analyze import AnalyzeJob
        from katrain.cron.jobs.fetch_upcoming import FetchUpcomingJob
        from katrain.cron.jobs.cleanup import CleanupJob
        from katrain.cron.jobs.tutorial_backup import TutorialBackupJob

        # Interval jobs
        interval_jobs = [
            (FetchListJob, config.FETCH_LIST_INTERVAL, config.FETCH_LIST_ENABLED),
            (PollMovesJob, config.POLL_MOVES_INTERVAL, config.POLL_MOVES_ENABLED),
            (PandanetPollJob, config.PANDANET_POLL_INTERVAL, config.PANDANET_ENABLED),
            (TranslateJob, config.TRANSLATE_INTERVAL, config.TRANSLATE_ENABLED),
            (FetchUpcomingJob, config.FETCH_UPCOMING_INTERVAL, config.FETCH_UPCOMING_ENABLED),
            (CleanupJob, config.CLEANUP_INTERVAL, config.CLEANUP_ENABLED),
            (TutorialBackupJob, config.TUTORIAL_BACKUP_INTERVAL, config.TUTORIAL_BACKUP_ENABLED),
        ]

        # Register every job (disabled ones too) so the admin console can show all of them.
        install_error_capture()
        registry = [(job_cls.name, "interval", interval, enabled) for job_cls, interval, enabled in interval_jobs]
        registry.append(("analyze", "loop", None, config.ANALYZE_ENABLED))
        registry.append(("report_analyze", "loop", None, config.REPORT_ANALYZE_ENABLED))
        # 先登记，再发起第一次运行：表还不存在（cron 比 katrain-web 先启动）时，启动那一次的记录会整个丢掉，日任务要
        # 空着显示「等待首次运行」一整天。最多等 60 秒：老版本的 katrain-web 根本没有这几张表时，不能因此把任务本身也停掉，
        # 之后每次心跳都会重试完整的登记。
        registered = self._recorder.register(registry)
        for _ in range(12):
            if registered:
                break
            logger.warning("cron_job_status is not writable yet (katrain-web may not have created it); retrying in 5s")
            await asyncio.sleep(5)
            registered = self._recorder.ensure_registered()

        # Start scheduler first (jobs will be added and run immediately)
        self._scheduler.start()
        logger.info("Scheduler started")

        # Every run -- the first one, right now, included -- is started by APScheduler (see _schedule)
        for job_cls, interval, enabled in interval_jobs:
            if not enabled:
                logger.info("Job %s is disabled, skipping", job_cls.name)
                continue
            self._schedule(job_cls(), interval)
            logger.info("Registered job %s (interval=%ds, first run now)", job_cls.name, interval)

        # AnalyzeJob runs as a persistent async loop, not via APScheduler interval
        if config.ANALYZE_ENABLED:
            analyze_job = AnalyzeJob()
            self._loop_jobs["analyze"] = analyze_job
            self._analyze_task = asyncio.create_task(self._run_analyze_loop(analyze_job))
            logger.info("AnalyzeJob persistent loop started")
        else:
            logger.info("AnalyzeJob is disabled, skipping")

        # ReportAnalyzerJob: persistent loop for user game report analysis
        if config.REPORT_ANALYZE_ENABLED:
            from katrain.cron.jobs.report_analyze import ReportAnalyzerJob

            report_job = ReportAnalyzerJob()
            self._loop_jobs["report_analyze"] = report_job
            self._report_analyze_task = asyncio.create_task(self._run_analyze_loop(report_job))
            logger.info("ReportAnalyzerJob persistent loop started (concurrency=%d)", config.REPORT_CONCURRENCY)
        else:
            logger.info("ReportAnalyzerJob is disabled, skipping")

        # Heartbeat: proves the process is alive and carries the loops' own counters
        self._heartbeat_task = asyncio.create_task(
            self._recorder.heartbeat_forever(self._loop_jobs, config.HEARTBEAT_INTERVAL, self._shutdown_event)
        )

        # Block until shutdown signal
        await self._shutdown_event.wait()

    def _schedule(self, job, interval: int) -> None:
        """每一次运行（包括启动时立刻跑的那一次）都由 APScheduler 发起，max_instances=1 管得住全部运行，
        记录器同一时刻只看得到这个任务的一次运行。以前启动那一次是单独 create_task 的，不受 max_instances
        约束：它若比后面一次定时运行更晚结束，就会把较旧的结果盖到状态行上。"""
        self._scheduler.add_job(
            self._recorder.run,
            "interval",
            args=[job],
            seconds=interval,
            id=job.name,
            name=job.name,
            max_instances=1,
            misfire_grace_time=interval,
            next_run_time=datetime.now(timezone.utc),
        )

    async def _run_analyze_loop(self, job):
        """Run a persistent loop job continuously, restarting on unexpected errors."""
        token = self._recorder.enter_loop(job.name)
        try:
            while not self._shutdown_event.is_set():
                self._recorder.loop_started(job.name)
                try:
                    await job.run()
                except asyncio.CancelledError:
                    logger.info("%s cancelled", job.name)
                    break
                except Exception as exc:
                    logger.exception("%s crashed, restarting in 10s", job.name)
                    self._recorder.record_loop_crash(job.name, exc)
                    await asyncio.sleep(10)
        finally:
            self._recorder.exit_loop(token)

    async def shutdown(self):
        """Graceful shutdown: stop scheduler, cancel loops and the heartbeat."""
        logger.info("Shutting down scheduler")
        self._scheduler.shutdown(wait=False)
        for task in [self._analyze_task, self._report_analyze_task, self._heartbeat_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._shutdown_event.set()
        logger.info("Scheduler shut down")
```

- [ ] **Step 5：`analyze.py`**
  - 在 `import asyncio` 之后加 `from datetime import datetime, timezone`；
  - 在 `__init__` 的 `self._katago = KataGoClient()` 之后加：
```python
        # Heartbeat payload for katrain/cron/run_recorder.py — plain counters, no DB access.
        self.last_iteration_at: datetime | None = None
        self._in_flight_count = 0
        self._window = self.window_size
```
  - 把 `while self._running:` 下面紧跟的 `if not in_flight:` 改成：
```python
        while self._running:
            self.last_iteration_at = datetime.now(timezone.utc)
            self._in_flight_count = len(in_flight)
            if not in_flight:
```
  - 把
```python
            # Refill
            slots = self._effective_window_size() - len(in_flight)
```
  改成：
```python
            # Refill
            self._window = self._effective_window_size()
            slots = self._window - len(in_flight)
```
  - 在 `run()` 方法之后加：
```python
    def heartbeat_stats(self) -> dict:
        """Read by RunRecorder.heartbeat every CRON_HEARTBEAT_INTERVAL seconds."""
        return {"in_flight": self._in_flight_count, "capacity": self._window}
```

- [ ] **Step 6：`report_analyze.py`**
  - 在 `__init__` 的 `self.poll_interval = config.REPORT_POLL_INTERVAL` 之后加 `self.last_iteration_at: datetime | None = None`；
  - 把 `run()` 里的 `while self._running:` 下一行 `try:` 改成：
```python
        while self._running:
            self.last_iteration_at = datetime.now(timezone.utc)
            try:
```
  - 在 `stop()` 之后加：
```python
    def heartbeat_stats(self) -> dict:
        """Read by RunRecorder.heartbeat every CRON_HEARTBEAT_INTERVAL seconds."""
        return {"in_flight": len(self._workers), "capacity": self.max_concurrent_tasks}
```

- [ ] **Step 7：`cleanup.py`**
  - 把 `from datetime import datetime, timedelta` 改成 `from datetime import datetime, timedelta, timezone`；
  - 把 `from katrain.cron.models import LiveMatchDB, LiveAnalysisDB, UpcomingMatchDB` 改成 `from katrain.cron.models import CronJobRunDB, LiveMatchDB, LiveAnalysisDB, UpcomingMatchDB`；
  - `stats` 字典里加一项 `"runs_deleted": 0,`；
  - 在 `stats["upcoming_deleted"] = upcoming_deleted` 之后、`db.commit()` 之前加：
```python

            # 4. Prune cron run history (written by run_recorder.py, read by katrain-admin)
            runs_cutoff = datetime.now(timezone.utc) - timedelta(days=config.RUNS_RETENTION_DAYS)
            stats["runs_deleted"] = (
                db.query(CronJobRunDB).filter(CronJobRunDB.started_at < runs_cutoff).delete(synchronize_session=False)
            )
```
  - 把完成日志改成：
```python
                self.logger.info(
                    "CleanupJob completed: matches=%d, analysis=%d, upcoming=%d, cron_runs=%d",
                    stats["matches_deleted"],
                    stats["analysis_deleted"],
                    stats["upcoming_deleted"],
                    stats["runs_deleted"],
                )
```
- [ ] **Step 8**：`CI=true uv run pytest tests/web_ui/test_cron_run_recorder.py tests/web_ui/test_cron_import_boundary.py tests/web_ui/test_report_analyzer.py -q -p no:cacheprovider`。期望结果：全部 PASS。`test_report_analyzer.py` 是改了 `report_analyze.py` 之后最可能回归的地方。
- [ ] **Step 9：提交** `feat(cron): 所有运行经过记录器；常驻循环心跳；清理 14 天前的运行历史`（连同 Step 0 改的 `pyproject.toml`、`uv.lock`、`requirements-cron.txt`）。

---

### Task 9: 健康判定（纯函数）

**Files:**
- Create：`katrain/web/admin/cron_health.py`
- Test：`tests/web_ui/test_admin_cron_health.py`

**Interfaces:**
- Produces：`derive_health(row, now: datetime) -> Health(state: str, reason: str)`、`as_utc(dt) -> datetime | None`

- [ ] **Step 1：写测试**
```python
# tests/web_ui/test_admin_cron_health.py
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from katrain.web.admin.cron_health import derive_health

NOW = datetime(2026, 9, 24, 8, 0, tzinfo=timezone.utc)


def ago(seconds):
    return NOW - timedelta(seconds=seconds)


def row(**kw):
    base = dict(kind="interval", interval_seconds=60, enabled=True, heartbeat_at=ago(10), last_started_at=ago(20),
                last_status="success", consecutive_failures=0, loop_iteration_at=None, loop_stats=None)
    base.update(kw)
    return SimpleNamespace(**base)


def loop(**kw):
    return row(kind="loop", interval_seconds=None, last_status="running", loop_iteration_at=ago(5), **kw)


CASES = [
    ("offline", row(heartbeat_at=ago(121))),
    ("offline", row(heartbeat_at=None)),
    ("disabled", row(enabled=False)),
    ("pending", row(last_started_at=None, last_status=None)),
    ("stuck", row(last_status="running", last_started_at=ago(601))),  # max(3×60, 600) = 600
    ("running", row(last_status="running", last_started_at=ago(30))),
    ("failed", row(last_status="failed", consecutive_failures=2)),
    ("errors", row(last_status="errors")),
    ("overdue", row(last_started_at=ago(181))),  # 2×60 + 60 = 180
    ("ok", row(last_started_at=ago(179))),
    ("pending", row(kind="loop", interval_seconds=None, loop_iteration_at=None)),
    ("stuck", row(kind="loop", interval_seconds=None, last_status="running", loop_iteration_at=ago(301))),
    ("failed", row(kind="loop", interval_seconds=None, last_status="failed", loop_iteration_at=ago(5))),
    ("errors", loop(loop_stats={"last_error_at": ago(300).isoformat()})),
    ("ok", loop(loop_stats={"last_error_at": ago(601).isoformat()})),
]


@pytest.mark.parametrize("expected,r", CASES, ids=[f"{i}-{c[0]}" for i, c in enumerate(CASES)])
def test_derive_health(expected, r):
    assert derive_health(r, NOW).state == expected


def test_naive_timestamps_from_sqlite_are_treated_as_utc():
    naive = row(heartbeat_at=ago(10).replace(tzinfo=None), last_started_at=ago(20).replace(tzinfo=None))
    assert derive_health(naive, NOW).state == "ok"


def test_offline_wins_over_everything_else():
    assert derive_health(row(heartbeat_at=ago(600), last_status="failed"), NOW).state == "offline"
```
- [ ] **Step 2**：`CI=true uv run pytest tests/web_ui/test_admin_cron_health.py -q -p no:cacheprovider`。期望结果：FAIL，报 `ModuleNotFoundError`。
- [ ] **Step 3：实现 `katrain/web/admin/cron_health.py`**
```python
"""cron 任务的健康状态：后台按「观测时刻」当场算，自上而下，命中即停（spec §6.4）。

SQLite 的 DateTime 不存时区（测试跑的是 SQLite），不带时区的时间一律当 UTC 处理。
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

OFFLINE_AFTER = timedelta(seconds=120)  # cron 每 30 秒写一次心跳
LOOP_STUCK_AFTER = timedelta(seconds=300)
LOOP_ERRORS_WINDOW = timedelta(minutes=10)
INTERVAL_STUCK_FLOOR = timedelta(seconds=600)
OVERDUE_GRACE = timedelta(seconds=60)


@dataclass(frozen=True)
class Health:
    state: str
    reason: str


def as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _parse(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return as_utc(datetime.fromisoformat(iso))
    except ValueError:
        return None


def human(delta: timedelta) -> str:
    s = max(0, int(delta.total_seconds()))
    if s < 60:
        return f"{s} 秒"
    if s < 3600:
        return f"{s // 60} 分钟"
    if s < 86400:
        return f"{s // 3600} 小时"
    return f"{s // 86400} 天"


def derive_health(row, now: datetime) -> Health:
    now = as_utc(now)
    heartbeat = as_utc(row.heartbeat_at)
    if heartbeat is None or now - heartbeat > OFFLINE_AFTER:
        return Health("offline", f"cron 进程失联：{human(now - heartbeat)}没有心跳" if heartbeat else "cron 进程从未上报心跳")
    if not row.enabled:
        return Health("disabled", "已被配置停用")
    if row.kind == "loop":
        iteration = as_utc(row.loop_iteration_at)
        if iteration is None:
            return Health("pending", "进程启动后循环还没有推进过")
        if now - iteration > LOOP_STUCK_AFTER:
            return Health("stuck", f"循环已经 {human(now - iteration)}没有推进")
        if row.last_status == "failed":
            return Health("failed", "循环刚崩溃，正在重启")
        last_error_at = _parse((row.loop_stats or {}).get("last_error_at"))
        if last_error_at is not None and now - last_error_at <= LOOP_ERRORS_WINDOW:
            return Health("errors", f"{human(now - last_error_at)}前有报错")
        return Health("ok", f"循环 {human(now - iteration)}前推进过")
    interval = timedelta(seconds=row.interval_seconds or 0)
    started = as_utc(row.last_started_at)
    if started is None:
        return Health("pending", "进程启动后还没有运行过")
    if row.last_status == "running":
        limit = max(3 * interval, INTERVAL_STUCK_FLOOR)
        if now - started > limit:
            return Health("stuck", f"已运行 {human(now - started)}，超过了 {human(limit)}")
        return Health("running", f"已运行 {human(now - started)}")
    if row.last_status == "failed":
        return Health("failed", f"连续 {row.consecutive_failures} 次不成功，最近一次抛出了异常")
    if row.last_status == "errors":
        return Health("errors", "跑完了，但运行期间有报错")
    if now - started > 2 * interval + OVERDUE_GRACE:
        return Health("overdue", f"上次开始于 {human(now - started)}前，间隔是 {human(interval)}")
    return Health("ok", f"上次开始于 {human(now - started)}前")
```
- [ ] **Step 4**：重跑 Step 2 的命令。期望结果：全部 passed。
- [ ] **Step 5：提交** `feat(admin): cron 健康判定（九态，自上而下命中即停）`。

---

### Task 10: cron 的三个只读接口

**Files:**
- Create：`katrain/web/admin/routers/cron.py`
- Modify：`katrain/web/admin/app.py`（挂上 cron router）
- Test：`tests/web_ui/test_admin_cron_api.py`

**Interfaces:**
- Consumes：`require_admin`（Task 6）、`derive_health` / `as_utc`（Task 9）、`models_db.CronJobStatus` / `CronJobRun` / `LiveAnalysisDB` / `ReportTask`
- Produces：`GET /api/admin/cron/jobs`、`GET /api/admin/cron/jobs/{name}/runs`、`GET /api/admin/cron/queues`，响应形状与 `src/admin/api/types.ts` 一致

- [ ] **Step 1：写测试**
```python
# tests/web_ui/test_admin_cron_api.py
"""/api/admin/cron/*：要登录；形状与 src/admin/api/types.ts 一致；分页；表不存在时 503。"""
from datetime import datetime, timedelta, timezone

import pytest

from katrain.web.core import models_db
from tests.web_ui._admin_helpers import login, make_admin_client

@pytest.fixture
def ctx(monkeypatch, tmp_path):
    # 「现在」在夹具执行时取，不在模块导入时取：全量测试跑得久，导入时取的时间会让心跳老过 120 秒、变成失联。
    now = datetime.now(timezone.utc)
    client, Session, engine = make_admin_client(monkeypatch, tmp_path)
    with Session() as s:
        s.add(models_db.CronJobStatus(job_name="fetch_list", kind="interval", interval_seconds=60, enabled=True,
                                      process_started_at=now - timedelta(hours=1), heartbeat_at=now - timedelta(seconds=10),
                                      last_started_at=now - timedelta(seconds=20), last_status="success", consecutive_failures=0))
        s.add(models_db.CronJobStatus(job_name="analyze", kind="loop", interval_seconds=None, enabled=True,
                                      heartbeat_at=now - timedelta(seconds=10), last_status="running", consecutive_failures=0,
                                      loop_iteration_at=now - timedelta(seconds=3),
                                      loop_stats={"in_flight": 2, "capacity": 16, "errors_total": 0, "last_error_at": None}))
        for i in range(60):
            s.add(models_db.CronJobRun(job_name="fetch_list", started_at=now - timedelta(minutes=60 - i), status="success", error_count=0))
        s.add(models_db.ReportTask(user_id=1, user_game_id="g1", status="pending", created_at=now - timedelta(minutes=5)))
        s.add(models_db.ReportTask(user_id=1, user_game_id="g2", status="pending", created_at=now - timedelta(minutes=2)))
        s.add(models_db.ReportTask(user_id=1, user_game_id="g3", status="completed"))
        s.commit()
    return client, engine, now


def test_everything_needs_a_session(ctx):
    client, _, _ = ctx
    for path in ("/api/admin/cron/jobs", "/api/admin/cron/jobs/fetch_list/runs", "/api/admin/cron/queues"):
        assert client.get(path).status_code == 401, path


def test_jobs_shape_and_health(ctx):
    client, _, _ = ctx
    login(client)
    body = client.get("/api/admin/cron/jobs").json()
    assert [j["name"] for j in body["jobs"]] == ["analyze", "fetch_list"]
    by = {j["name"]: j for j in body["jobs"]}
    assert by["fetch_list"]["health"]["state"] == "ok"
    assert by["analyze"]["health"]["state"] == "ok" and by["analyze"]["loop_stats"]["in_flight"] == 2
    assert by["fetch_list"]["heartbeat_at"].endswith("+00:00") or by["fetch_list"]["heartbeat_at"].endswith("Z")


def test_runs_are_newest_first_and_paginate(ctx):
    client, _, _ = ctx
    login(client)
    first = client.get("/api/admin/cron/jobs/fetch_list/runs").json()
    assert len(first["runs"]) == 50
    ids = [r["id"] for r in first["runs"]]
    assert ids == sorted(ids, reverse=True) and first["next_before_id"] == ids[-1]
    second = client.get(f"/api/admin/cron/jobs/fetch_list/runs?before_id={first['next_before_id']}").json()
    assert len(second["runs"]) == 10 and second["next_before_id"] is None
    assert client.get("/api/admin/cron/jobs/fetch_list/runs?limit=201").status_code == 422
    assert client.get("/api/admin/cron/jobs/nope/runs").status_code == 404


def test_queues_count_by_status_and_report_the_oldest_pending(ctx):
    client, _, now = ctx
    login(client)
    body = client.get("/api/admin/cron/queues").json()
    assert body["report_tasks"]["by_status"] == {"pending": 2, "completed": 1}
    oldest = datetime.fromisoformat(body["report_tasks"]["oldest_pending_at"].replace("Z", "+00:00"))
    assert abs((oldest - (now - timedelta(minutes=5))).total_seconds()) < 1
    assert body["live_analysis"] == {"by_status": {}, "oldest_pending_at": None}


def test_jobs_say_503_when_the_tables_do_not_exist(ctx):
    client, engine, _ = ctx
    login(client)
    models_db.CronJobStatus.__table__.drop(engine)
    r = client.get("/api/admin/cron/jobs")
    assert r.status_code == 503 and "cron 状态表不存在" in r.json()["detail"]
```
- [ ] **Step 2**：`CI=true uv run pytest tests/web_ui/test_admin_cron_api.py -q -p no:cacheprovider`。期望结果：FAIL，全部返回 404（路由还不存在）。
- [ ] **Step 3：实现 `katrain/web/admin/routers/cron.py`**
```python
"""/api/admin/cron：cron 任务状态、运行历史、两条分析队列。全部只读，状态数据由 katrain-cron 写。"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.exc import OperationalError, ProgrammingError

from katrain.web.admin.cron_health import as_utc, derive_health
from katrain.web.admin.session import require_admin
from katrain.web.core import models_db

router = APIRouter(dependencies=[Depends(require_admin)])

TABLES_MISSING = "cron 状态表不存在：katrain-web 新版本还没启动过"


class HealthOut(BaseModel):
    state: str
    reason: str


class CronJobOut(BaseModel):
    name: str
    kind: str
    interval_seconds: int | None
    enabled: bool
    health: HealthOut
    process_started_at: datetime | None
    heartbeat_at: datetime | None
    last_started_at: datetime | None
    last_finished_at: datetime | None
    last_success_at: datetime | None
    last_status: str | None
    last_duration_ms: int | None
    last_error: str | None
    consecutive_failures: int
    loop_iteration_at: datetime | None
    loop_stats: dict | None


class CronJobsOut(BaseModel):
    observed_at: datetime
    jobs: list[CronJobOut]


class CronRunOut(BaseModel):
    id: int
    started_at: datetime
    finished_at: datetime | None
    status: str
    duration_ms: int | None
    error_count: int
    error: str | None


class CronRunsOut(BaseModel):
    runs: list[CronRunOut]
    next_before_id: int | None


class QueueOut(BaseModel):
    by_status: dict[str, int]
    oldest_pending_at: datetime | None


class CronQueuesOut(BaseModel):
    observed_at: datetime
    live_analysis: QueueOut
    report_tasks: QueueOut


@router.get("/jobs", response_model=CronJobsOut)
async def list_jobs(request: Request):
    now = datetime.now(timezone.utc)
    try:
        with request.app.state.session_factory() as db:
            rows = db.query(models_db.CronJobStatus).order_by(models_db.CronJobStatus.job_name).all()
    except (OperationalError, ProgrammingError):
        raise HTTPException(status_code=503, detail=TABLES_MISSING)
    jobs = []
    for r in rows:
        h = derive_health(r, now)
        jobs.append(CronJobOut(
            name=r.job_name, kind=r.kind, interval_seconds=r.interval_seconds, enabled=r.enabled,
            health=HealthOut(state=h.state, reason=h.reason),
            process_started_at=as_utc(r.process_started_at), heartbeat_at=as_utc(r.heartbeat_at),
            last_started_at=as_utc(r.last_started_at), last_finished_at=as_utc(r.last_finished_at),
            last_success_at=as_utc(r.last_success_at), last_status=r.last_status, last_duration_ms=r.last_duration_ms,
            last_error=r.last_error, consecutive_failures=r.consecutive_failures or 0,
            loop_iteration_at=as_utc(r.loop_iteration_at), loop_stats=r.loop_stats,
        ))
    return CronJobsOut(observed_at=now, jobs=jobs)


@router.get("/jobs/{name}/runs", response_model=CronRunsOut)
async def list_runs(request: Request, name: str, limit: int = Query(50, ge=1, le=200), before_id: int | None = Query(None, ge=1)):
    try:
        with request.app.state.session_factory() as db:
            if db.get(models_db.CronJobStatus, name) is None:
                raise HTTPException(status_code=404, detail="没有这个任务")
            q = db.query(models_db.CronJobRun).filter(models_db.CronJobRun.job_name == name)
            if before_id is not None:
                q = q.filter(models_db.CronJobRun.id < before_id)
            rows = q.order_by(models_db.CronJobRun.id.desc()).limit(limit + 1).all()
    except (OperationalError, ProgrammingError):
        raise HTTPException(status_code=503, detail=TABLES_MISSING)
    page = rows[:limit]
    return CronRunsOut(
        runs=[CronRunOut(id=r.id, started_at=as_utc(r.started_at), finished_at=as_utc(r.finished_at), status=r.status,
                         duration_ms=r.duration_ms, error_count=r.error_count or 0, error=r.error) for r in page],
        next_before_id=page[-1].id if len(rows) > limit else None,
    )


def _queue(db, status_col, created_col) -> QueueOut:
    counts = db.query(status_col, func.count()).group_by(status_col).all()
    oldest = db.query(func.min(created_col)).filter(status_col == "pending").scalar()
    return QueueOut(by_status={str(k): int(v) for k, v in counts}, oldest_pending_at=as_utc(oldest))


@router.get("/queues", response_model=CronQueuesOut)
async def queues(request: Request):
    now = datetime.now(timezone.utc)
    with request.app.state.session_factory() as db:
        live = _queue(db, models_db.LiveAnalysisDB.status, models_db.LiveAnalysisDB.created_at)
        reports = _queue(db, models_db.ReportTask.status, models_db.ReportTask.created_at)
    return CronQueuesOut(observed_at=now, live_analysis=live, report_tasks=reports)
```
在 `app.py` 里，顶部 import 加上 `from katrain.web.admin.routers import cron as cron_router`；在 auth router 那一行之后加：
```python
    app.include_router(cron_router.router, prefix="/api/admin/cron")
```
- [ ] **Step 4**：`CI=true uv run pytest tests/web_ui/test_admin_cron_api.py tests/web_ui/test_admin_auth.py tests/web_ui/test_admin_app.py -q -p no:cacheprovider`。期望结果：全部 passed。（SQLite 上 `func.min` 返回**不带时区**的 `datetime`（2026-09-24 用 SQLAlchemy 2.0.46 实测），`as_utc` 按 UTC 补上时区；PG 上返回带时区的值。两种都不用另外处理。）
- [ ] **Step 5：提交** `feat(admin): cron 三个只读接口（任务、运行历史、队列）`。

---

### Task 11: 测试机部署配置 + 访问文档

**Files:**
- Modify：`docker-compose.yml`（katrain-web 加 `image:`；新增服务 katrain-admin）
- Modify：`Dockerfile.web`（`RUN cd katrain/web/ui && npm install && npm run build` 那一行）
- Modify：`.claude/skills/server-deploy/SKILL.md`（架构表加一行；第 7 步、第 8 步的命令）
- Create：`docs/operations/admin-console-access.md`
- Test：`tests/test_admin_compose.py`

**Interfaces:**
- Consumes：Task 5 的启动命令 `python3 -m katrain.web.admin --host 0.0.0.0 --port 8010`，以及启动闸要的环境变量 `KATRAIN_SECRET_KEY`、`KATRAIN_ADMIN_ENV`；Task 2 的 `npm run build:admin`
- Produces：develop 的 compose 服务 `katrain-admin`（镜像 `katrain-web:local`，只发布 `127.0.0.1:8010`）；运维文档 `docs/operations/admin-console-access.md`

- [ ] **Step 1：写测试**
```python
# tests/test_admin_compose.py
"""测试机的 compose：katrain-admin 只发布到 127.0.0.1。阿里云网关经 WireGuard 能到这台机器的所有网卡。"""
from pathlib import Path

import yaml

SERVICES = yaml.safe_load((Path(__file__).resolve().parents[1] / "docker-compose.yml").read_text(encoding="utf-8"))["services"]


def test_admin_is_published_on_loopback_only():
    ports = SERVICES["katrain-admin"]["ports"]
    assert ports and all(str(p).startswith("127.0.0.1:") for p in ports), ports


def test_admin_runs_the_web_image_with_the_admin_entrypoint():
    admin = SERVICES["katrain-admin"]
    assert admin["image"] == SERVICES["katrain-web"]["image"] == "katrain-web:local"
    assert admin["command"][:3] == ["python3", "-m", "katrain.web.admin"]
    assert "KATRAIN_ADMIN_ENV=test" in admin["environment"]
```
- [ ] **Step 2**：`CI=true uv run pytest tests/test_admin_compose.py -q -p no:cacheprovider`。期望结果：FAIL，报 `KeyError: 'katrain-admin'`。
- [ ] **Step 3：`docker-compose.yml`**
  - katrain-web 的 `build:` 块之后加一行 `    image: katrain-web:local`；
  - 在 `katrain-cron:` 服务之前插入：
```yaml
  # 管理后台（superpowers/tracks/admin-console/spec-2026-09-24-admin-console.md）。与 katrain-web 同一个镜像，
  # 只发布到 127.0.0.1：阿里云网关经 WireGuard 只到得了 10.8.0.2:8001，碰不到这里。
  # 访问方式见 docs/operations/admin-console-access.md（SSH 隧道）。
  katrain-admin:
    image: katrain-web:local
    container_name: katrain-admin
    pull_policy: never   # 镜像由上面 katrain-web 那一项在本机构建；测试机连不上 Docker Hub，不许去拉
    command: ["python3", "-m", "katrain.web.admin", "--host", "0.0.0.0", "--port", "8010"]
    depends_on:
      - katrain-web
    restart: unless-stopped
    ports:
      - "127.0.0.1:8010:8010"
    environment:
      - KATRAIN_SECRET_KEY=${KATRAIN_SECRET_KEY:?KATRAIN_SECRET_KEY 必须在 .env 里设置}
      - KATRAIN_DATABASE_URL=postgresql://katrain_user:${POSTGRES_PASSWORD:-katrain_secure_password_CHANGE_ME}@host.docker.internal:5432/katrain_db
      - KATRAIN_ADMIN_ENV=test
    extra_hosts:
      - "host.docker.internal:host-gateway"
```
- [ ] **Step 4：`Dockerfile.web`**：把 `RUN cd katrain/web/ui && npm install && npm run build` 改成 `RUN cd katrain/web/ui && npm install && npm run build && npm run build:admin`。
- [ ] **Step 5：`server-deploy` skill**（`.claude/skills/server-deploy/SKILL.md`。凡是写死了服务集合的地方都要改，漏一处，照着它部署的人就会漏掉 admin）：
  - 架构图：`katrain-cron` 那个框下面加一个框：
```
                 ┌───────────────┐
  127.0.0.1:8010 │ katrain-admin │ 管理后台：与 katrain-web 同一个镜像，只经 SSH 隧道访问
                 └───────────────┘
```
  - 容器表 `| katrain-cron | … |` 那一行之后加：`| katrain-admin | katrain-web:local（同一镜像） | 127.0.0.1:8010 | — | **compose** | 管理后台，只经 SSH 隧道访问（docs/operations/admin-console-access.md） |`；
  - 表格下面那段说明：「manages **web + cron + minio + minio-setup**」改成「manages **web + cron + admin + minio + minio-setup**」，「only ever touches web/cron/minio」改成「only ever touches web/cron/admin/minio」；
  - 第 7 步：标题改成「Rebuild & restart KaTrain web/cron/admin」；命令改成 `docker compose up -d --build katrain-web katrain-cron katrain-admin`；正文补一句「`katrain-admin` 用 katrain-web 刚构建出来的同一个镜像（`pull_policy: never`），不单独构建」；
  - 第 8 步加一行 `curl -s http://127.0.0.1:8010/api/admin/health   # {"status":"ok","env":"test"}`；
  - 开头 `description` 里的「KaTrain web/cron」改成「KaTrain web/cron/admin」；
  - 「Selective Deployment」里「First MinIO bring-up: … then recreate web/cron (step 7)」改成「… then recreate web/cron/admin (step 7)」。
- [ ] **Step 6：写 `docs/operations/admin-console-access.md`**
````markdown
# 管理后台访问方式（katrain-admin）

后台进程只在服务器的 127.0.0.1:8010 上监听，公网和 WireGuard 网关都到不了。访问时先开一条 SSH 隧道，把本机端口转到服务器的 127.0.0.1:8010；隧道开着以后，后台就是浏览器里的一个普通网页。

| 环境 | 开隧道（Mac 终端 / Windows PowerShell 通用） | 浏览器打开 |
|---|---|---|
| 测试（home-ubuntu） | `ssh -N -L 8010:127.0.0.1:8010 home-ubuntu` | http://localhost:8010 |
| 生产（ucloud-v100） | `ssh -N -L 8011:127.0.0.1:8010 ucloud-v100` | http://localhost:8011 |

两条隧道可以同时开着：本机端口不同，登录状态也按端口各存各的（放在浏览器的 localStorage 里），不会串号。登录一次管 8 小时，关标签页、重启浏览器都不用重新登录；**在别人也会用的电脑上（例如烧录用的 Windows 机），用完点页头的「登出」**。页头会醒目地标出当前是哪个环境。

## Windows：做成双击即用

新建 `打开生产后台隧道.bat`：
```bat
@echo off
rem 窗口开着隧道就在，关掉窗口隧道就断。
ssh -N -L 8011:127.0.0.1:8010 ucloud-v100
```
Windows 10/11 自带 OpenSSH 客户端。`ucloud-v100` 这个主机别名需要写在 `%USERPROFILE%\.ssh\config` 里，内容与 Mac 上的配置相同。

## 给工作人员开「只能转发、不能登录 shell」的账号（需要时照做）

在生产服务器上（测试机要先经过阿里云跳板机，工作人员在跳板机上也需要一个同样受限的账号）：
```bash
NAME=<工作人员代号>
sudo adduser --disabled-password --gecos "" --shell /usr/sbin/nologin "admintunnel-$NAME"
sudo install -d -m 700 -o "admintunnel-$NAME" -g "admintunnel-$NAME" "/home/admintunnel-$NAME/.ssh"
echo 'restrict,port-forwarding,permitopen="127.0.0.1:8010" ssh-ed25519 AAAA...<工作人员的公钥>' \
  | sudo tee "/home/admintunnel-$NAME/.ssh/authorized_keys" >/dev/null
sudo chown "admintunnel-$NAME:" "/home/admintunnel-$NAME/.ssh/authorized_keys"
sudo chmod 600 "/home/admintunnel-$NAME/.ssh/authorized_keys"
```
这样的账号只能把本机端口转发到 127.0.0.1:8010，拿不到 shell，也连不到服务器上的其他端口。后台账号本身（`users.is_admin`）另外开。
````
- [ ] **Step 7**：重跑 Step 2 的命令，期望结果：2 passed。再执行 `docker compose config -q && echo compose-ok`，期望结果：`compose-ok`（需要本机有 Docker；没有的话，这一步留到 Task 14 在测试机上执行）。
- [ ] **Step 8：变异检查**：先 `cp docker-compose.yml /private/tmp/claude-501/compose.yml.bak`，把端口临时改成 `"8010:8010"`，确认 `test_admin_is_published_on_loopback_only` 变红；然后 `cp /private/tmp/claude-501/compose.yml.bak docker-compose.yml` 还原（不要用 `git checkout`，本任务的改动还没提交）。
- [ ] **Step 9：提交** `deploy(admin): 测试机 compose 加 katrain-admin（只绑 127.0.0.1）+ 访问文档`。

---

### Task 12: 集成 —— 本机真实跑起 web + cron + admin

**Files:**
- Create：`superpowers/tracks/admin-console/slice1/integration-local.png`、`integration-local-offline.png`；`visual-review.md` 加「集成」一节
- Create（临时，不提交）：`katrain/web/ui/tests/admin-integration.walk.spec.ts`

**Interfaces:**
- Consumes：`python -m katrain --ui web`（启动时建表；空库且设了 `KATRAIN_ADMIN_BOOTSTRAP_PASSWORD` 时建管理员 `admin`，见 `server.py` 的 bootstrap 分支）；`python -m katrain.cron`（Task 8 接好的记录器）；`python -m katrain.web.admin`（Task 5、6、10）；`npm run build:admin`（Task 2）
- Produces：两张集成截图，以及「cron 被 SIGKILL 之后 150 秒内 9 个任务全部显示失联」的实测结果

- [ ] **Step 1：备份本机配置**（本机的 `--ui web` 退出时会改写它）：
`cp ~/.katrain/config.json /private/tmp/claude-501/katrain-config.json.bak 2>/dev/null || echo "no config.json"`

- [ ] **Step 2：构建后台前端，用一个一次性的 SQLite 库起三个进程**。直接用 `.venv/bin/python`：这样记下的 PID 就是 Python 进程本身，不是 `uv` 的外壳，Step 3 的 SIGKILL 才真的杀到 cron。
```bash
set -o pipefail
cd /Users/fan/Repositories/katrain-admin-console
(cd katrain/web/ui && npm run build:admin 2>&1 | tail -2)
E=/private/tmp/claude-501/admin-e2e; mkdir -p $E; rm -f $E/e2e.db
export KATRAIN_DATABASE_URL=sqlite:///$E/e2e.db
export KATRAIN_SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_urlsafe(48))")
KATRAIN_ADMIN_BOOTSTRAP_PASSWORD=e2e-admin-pw .venv/bin/python -m katrain --ui web --port 8001 --disable-engine > $E/web.log 2>&1 & echo $! > $E/web.pid
for i in $(seq 1 180); do curl -sf -o /dev/null http://127.0.0.1:8001/ && break; sleep 1; done   # 首次运行会先构建公开前端，可能要一两分钟
.venv/bin/python -m katrain.cron > $E/cron.log 2>&1 & echo $! > $E/cron.pid
KATRAIN_ADMIN_ENV=local .venv/bin/python -m katrain.web.admin --port 8010 > $E/admin.log 2>&1 & echo $! > $E/admin.pid
for i in $(seq 1 30); do curl -sf http://127.0.0.1:8010/api/admin/health && break; sleep 1; done; echo
```
Expected：最后打印 `{"status":"ok","env":"local"}`。

- [ ] **Step 3：真浏览器走一遍**（1440×900。打的是后台进程自己发出去的构建产物，与部署后一致）

写一次性的脚本 `katrain/web/ui/tests/admin-integration.walk.spec.ts`：
```ts
// One-off, not committed. Needs web + cron + admin from Step 2. run from katrain/web/ui:
//   npx playwright test --config=playwright.vite.config.ts tests/admin-integration.walk.spec.ts
import { readFileSync } from 'node:fs';
import { test, expect } from '@playwright/test';

const BASE = 'http://127.0.0.1:8010';
const E = '/private/tmp/claude-501/admin-e2e';
const SLICE = '../../../superpowers/tracks/admin-console/slice1'; // relative to katrain/web/ui

test.setTimeout(6 * 60_000);

test('本机真实数据：登录 → 9 个任务 → 运行历史 → cron 被杀后失联', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const cspViolations: string[] = [];
  page.on('console', (m) => { if (m.text().includes('Content Security Policy')) cspViolations.push(m.text()); });
  await page.goto(`${BASE}/#/signin`);
  await expect(page.getByTestId('signin-env')).toHaveText('正在登录：本机');
  await page.getByLabel('用户名').fill('admin');
  await page.getByLabel('密码').fill('e2e-admin-pw');
  await page.getByRole('button', { name: '登录' }).click();
  await expect(page.getByTestId('admin-env')).toHaveText('本机');

  // cron registers all 9 jobs at start (disabled ones too); the heartbeat says the process is alive.
  await expect(page.locator('[data-testid^="cron-row-"]')).toHaveCount(9, { timeout: 60_000 });
  await expect(page.getByTestId('cron-process')).toContainText('在线');

  // fetch_list (every 60 s) runs once at startup and keeps every run, so its history is not empty.
  await expect(page.getByTestId('cron-row-fetch_list')).not.toContainText('等待首次运行', { timeout: 60_000 });
  await page.getByTestId('cron-row-fetch_list').click();
  await expect(page.locator('[data-testid="run-history-scroll"] tbody tr').first()).toBeVisible();
  await page.keyboard.press('Escape');

  const states = await page.locator('[data-testid^="cron-row-"]').evaluateAll((rows) =>
    rows.map((r) => `${r.getAttribute('data-testid')!.slice(9)}=${r.querySelector('[data-testid^="health-"]')!.getAttribute('data-testid')!.slice(7)}`),
  );
  console.log('states', states.join(' '));
  await page.screenshot({ path: `${SLICE}/integration-local.png` });

  // SIGKILL is the OOM-killer case: cron gets no chance to write anything. 120 s + one 15 s refresh.
  process.kill(Number(readFileSync(`${E}/cron.pid`, 'utf8').trim()), 'SIGKILL');
  await expect(page.getByTestId('health-offline')).toHaveCount(9, { timeout: 150_000 });
  await page.screenshot({ path: `${SLICE}/integration-local-offline.png` });
  expect(cspViolations).toEqual([]); // 打包出来的脚本、MUI 的内联样式都没被 CSP 拦掉
});
```
```bash
set -o pipefail
cd /Users/fan/Repositories/katrain-admin-console/katrain/web/ui
npx playwright test --config=playwright.vite.config.ts tests/admin-integration.walk.spec.ts --reporter=line 2>&1 | tail -25
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8010/api/admin/cron/jobs   # 不带令牌
curl -sI http://127.0.0.1:8010/ | grep -i '^content-security-policy'
rm tests/admin-integration.walk.spec.ts
```
Expected：`1 passed`（其中包括「CSP 没有拦掉页面自己的任何东西」），日志里打出 9 个任务各自的状态；第一条 curl 打印 `401`，第二条打印出 CSP 头。本机连不上的外部源（KataGo 等）应当让对应任务显示「有报错」或「失败」，不能是「正常」：拿打印出来的状态对照 `$E/cron.log` 逐个核对，结论写进 `slice1/visual-review.md` 的「集成」一节。

- [ ] **Step 4：收尾**
```bash
E=/private/tmp/claude-501/admin-e2e
for f in web admin cron; do kill "$(cat $E/$f.pid)" 2>/dev/null; done   # cron 已在 Step 3 被 SIGKILL，它报错可以忽略
lsof -iTCP:8001 -sTCP:LISTEN; lsof -iTCP:8010 -sTCP:LISTEN
cp /private/tmp/claude-501/katrain-config.json.bak ~/.katrain/config.json 2>/dev/null || true
cd /Users/fan/Repositories/katrain-admin-console && git status --short
```
Expected：两条 `lsof` 都没有输出；`git status --short` 只列出这一步新增的截图和 `visual-review.md`（`katrain/config.json` 如果被改了，执行 `git checkout -- katrain/config.json` 还原）。

- [ ] **Step 5：提交**
```bash
git add superpowers/tracks/admin-console/slice1/integration-local.png superpowers/tracks/admin-console/slice1/integration-local-offline.png superpowers/tracks/admin-console/slice1/visual-review.md
git commit -m "test(admin): 本机 web+cron+admin 集成验证截图" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: 删掉 fixture、全量验证、两套边界

**Files:**
- Delete：`katrain/web/ui/src/admin/__fixtures__/cronFixture.ts`
- Modify：`katrain/web/ui/src/admin/api/cronApi.ts`、`katrain/web/ui/src/admin/api/authApi.ts`（删掉 fixture 分支）

**Interfaces:**
- Consumes：Task 2 的 `useFixture` 分支和 `src/admin/__fixtures__/`；Task 2 Step 1 记下的 `.superpowers/baseline/cron_slice_failed_before.txt`、`vitest_failed_before.txt`
- Produces：不含 fixture 的 `src/admin/`，以及三套构建产物

- [ ] **Step 1：删除 fixture**：
  - `git rm -r katrain/web/ui/src/admin/__fixtures__`；
  - 删掉 `cronApi.ts` 和 `authApi.ts` 里的 `useFixture`、`fixture` 两个常量，以及每个函数里 `if (useFixture) …` / `useFixture ? … :` 的那一支（`login` 里只留 `adminFetch<AdminLogin>(…)` 那一支，`logout` 里的 `if (!useFixture)` 去掉条件、保留请求和 `finally { clearToken(); }`），其余只留 `adminFetch` 调用；
  - 确认：`grep -rn "VITE_ADMIN_FIXTURE\|__fixtures__\|useFixture" katrain/web/ui/src/admin`，期望没有输出。
- [ ] **Step 2：Python 全量，按名字和基线比**：
```bash
cd /Users/fan/Repositories/katrain-admin-console
bash .superpowers/baseline/newfail.sh .superpowers/baseline/cron_slice_failed_before.txt tests/web_ui --continue-on-collection-errors; echo "newfail exit=$?"
set -o pipefail; CI=true uv run pytest tests/test_admin_compose.py -q -p no:cacheprovider 2>&1 | tail -2; echo "compose exit=$?"
git status --short
```
期望结果：`newfail exit=0`；`compose exit=0`（2 passed）。`git status` 里出现了 `katrain/config.json` 的话（测试改写的；Task 2 Step 1 已确认它在测试之前是干净的），执行 `git checkout -- katrain/config.json` 还原。
- [ ] **Step 3：前端：vitest 按名字和基线比，三套构建，公开包和 kiosk 包里没有后台代码**
```bash
cd /Users/fan/Repositories/katrain-admin-console
bash .superpowers/baseline/vitestnewfail.sh .superpowers/baseline/vitest_failed_before.txt; echo "vitest-newfail exit=$?"
```
期望结果：`vitest-newfail exit=0`（1 会列出新增失败；2 说明 vitest 本身没跑成）。
```bash
cd /Users/fan/Repositories/katrain-admin-console/katrain/web/ui
set -euo pipefail
npx eslint src/admin eslint.config.js
npm run build 2>&1 | tail -2
npm run build:kiosk-2d 2>&1 | tail -2
npm run build:admin 2>&1 | tail -2
if grep -rl "katrain-admin\|/api/admin" ../static ../static-kiosk-2d; then echo "!! 公开包或 kiosk 包里有后台代码"; exit 1; fi
echo boundaries-ok
```
期望结果：eslint 没有 error；三个构建都以 `built in` 结尾，kiosk 那个还打印 `✅ kiosk boundary clean`；最后打印 `boundaries-ok`。这是一次性核对，spec §5.5 说明了为什么不做成常设的闸。
- [ ] **Step 4：提交** `chore(admin): 删掉 cron 页 fixture（Task 12 已接真实接口）`。按 spec，fixture 必须在这个提交里删掉。

---

### Task 14: 🛑 部署测试机，Fan 验收（推送和部署前都要 Fan 点头）

**Interfaces:**
- Consumes：Task 11 的 compose 服务 `katrain-admin` 和 `server-deploy` 的第 7、8 步；切片 0 Task 6 在测试机上实测过能登录的管理员账号

- [ ] **Step 1**：跟上 develop，跑本切片的测试；测试通过、🛑 Fan 点头之后再快进推送：
```bash
cd /Users/fan/Repositories/katrain-admin-console && git fetch origin && git merge --no-edit origin/develop
CI=true uv run pytest tests/web_ui/test_admin_app.py tests/web_ui/test_admin_auth.py tests/web_ui/test_admin_cron_api.py tests/web_ui/test_admin_cron_health.py tests/web_ui/test_cron_run_recorder.py tests/web_ui/test_cron_status_tables_parity.py tests/test_admin_compose.py -q -p no:cacheprovider; echo "pytest exit=$?"
```
期望结果：`pytest exit=0`。然后才执行 `git push origin HEAD:develop`（被拒说明 develop 又前进了：重新 fetch、merge、测试、push）。
- [ ] **Step 2**：`ssh home-ubuntu "cd ~/Repositories/katrain && git pull --ff-only && docker compose up -d --build katrain-web katrain-cron katrain-admin && docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' | grep katrain"`
- [ ] **Step 3：验证**：
```bash
ssh home-ubuntu "ss -ltnp | grep ':8010 '"                                      # 只能看到 127.0.0.1:8010
ssh home-ubuntu "curl -s http://127.0.0.1:8010/api/admin/health"                # {"status":"ok","env":"test"}
ssh home-ubuntu "curl -fsS http://127.0.0.1:8001/api/v1/health"                # katrain-web 本身：develop 的 compose 没给它配 healthcheck，别等 (healthy)
curl -s -o /dev/null -w '%{http_code}\n' https://go.sailorvoyage.top/api/admin/health   # 期望 404：公网上没有这个入口
ssh home-ubuntu "docker exec katrain-postgres psql -U katrain_user -d katrain_db -At -c 'SELECT job_name, last_status, heartbeat_at FROM cron_job_status ORDER BY 1;'"
```
- [ ] **Step 4**：开隧道 `ssh -N -L 8010:127.0.0.1:8010 home-ubuntu`，在浏览器里打开 http://localhost:8010：
  - 页头显示「测试环境」；
  - 用 Fan 的管理员账号登录（切片 0 的 Task 6 已经授权并实测过）；
  - 9 个任务都有真实状态。
- [ ] **Step 5：🛑 Fan 验收。** 验收通过后，切片 1 才算满足 vertical-slice 的「完成的定义」：可部署、状态诚实、已集成、已验收、fixture 已删。

---

### Task 15: 🛑 生产部署（每一步都要 Fan 点头）

**Files**（release 分支，在 Step 2 建的临时 worktree `/private/tmp/claude-501/rel-admin-console` 里）:
- Modify：`Dockerfile.web`、`deploy/ucloud/compose.yml`、`deploy/ucloud/scripts/build-web.sh`、`tests/deploy/test_ucloud_artifacts.py`、`docs/operations/ucloud-migration-runbook.md`

**Interfaces:**
- Consumes：develop 上本切片的全部提交；切片 0 Task 6 在生产上实测过能登录的管理员账号（容器名、库名以切片 0 Task 6 Step 1 实际查到的为准）
- Produces：生产上的 `katrain-admin` 服务（只绑 127.0.0.1:8010）、三张新表、runbook 里的一条发布记录

- [ ] **Step 1：先把连带发布的提交列给 Fan**：`git -C /Users/fan/Repositories/katrain fetch origin && git -C /Users/fan/Repositories/katrain log --oneline --no-merges origin/release/ucloud-20260805..origin/develop`。发布会连带 develop 自上次发布以来的全部提交；🛑 Fan 同意后再继续。
- [ ] **Step 2：合并到 release**（临时 worktree；路径写成字面量，因为每次调用 Bash 都是新 shell）：
```bash
git -C /Users/fan/Repositories/katrain worktree add /private/tmp/claude-501/rel-admin-console -b release-merge-admin-console origin/release/ucloud-20260805
cd /private/tmp/claude-501/rel-admin-console && git merge --no-edit origin/develop; echo "merge exit=$?"; git status --short | grep '^UU' || true
```
`Dockerfile.web` 几乎一定会冲突：develop 和 release 各有一份完全不同的 Dockerfile.web。冲突时保留 release 的版本（`git checkout --ours Dockerfile.web && git add Dockerfile.web`），再手工加上 Step 3 的改动。其他冲突逐个判断，release 一侧的 `PREVIEW_MODE` 守卫一律保留。合并提交之后核对：
```bash
grep -c '^FROM' /private/tmp/claude-501/rel-admin-console/Dockerfile.web
```
期望结果：`4`，即 release 自己那份 4 阶段构建。develop 那份只有 1 个 `FROM`：看到 1 就说明合并把它换掉了。
- [ ] **Step 3：release 分支上的四处改动**
  1. `Dockerfile.web`：ui-builder 阶段把 `RUN npm run build` 改成 `RUN npm run build && npm run build:admin`；runtime 阶段在 `COPY --from=ui-builder --chown=10001:10001 /src/static /app/katrain/web/static` 之后加 `COPY --from=ui-builder --chown=10001:10001 /src/static-admin /app/katrain/web/static-admin`；source-pruner 的 `rm -rf` 列表加上 `/app/katrain/web/static-admin \`。
  2. `deploy/ucloud/compose.yml`：在 `katrain-cron:` 之前加：
```yaml
  katrain-admin:
    profiles: [production]
    restart: unless-stopped
    image: ${WEB_IMAGE:?WEB_IMAGE is required}
    user: "10001:10001"
    command: ["python3", "-m", "katrain.web.admin", "--host", "0.0.0.0", "--port", "8010"]
    environment:
      KATRAIN_DATABASE_URL: postgresql://${KATRAIN_DB_USER:-katrain_user}:${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}@postgres:5432/${KATRAIN_DB_NAME:-katrain_db}
      KATRAIN_SECRET_KEY: ${KATRAIN_SECRET_KEY:?KATRAIN_SECRET_KEY is required}
      KATRAIN_ADMIN_ENV: prod
    ports:
      - 127.0.0.1:8010:8010   # 只绑回环：不绑 WireGuard 地址，网关碰不到
    depends_on:
      postgres:
        condition: service_healthy
      katrain-web:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:8010/api/admin/health"]
      interval: 15s
      timeout: 5s
      retries: 10
    mem_limit: 1g
    cpus: 1
    logging:
      driver: json-file
      options:
        max-size: 10m
        max-file: "5"
    networks:
      - backend
```
  3. `deploy/ucloud/scripts/build-web.sh`：在容器内容检查（`docker run --rm "$IMAGE_TAG" sh -ec '` 那一段）里加两行：`python -c '\''import katrain.web.admin.app'\''` 和 `test -f /app/katrain/web/static-admin/admin.html`。
  4. `tests/deploy/test_ucloud_artifacts.py`：
     - `test_production_adds_exactly_one_cron` 里的 `set(preview) | {"katrain-cron"}` 改成 `set(preview) | {"katrain-cron", "katrain-admin"}`；
     - `test_long_running_services_have_health_restart_resource_and_log_limits` 的服务名元组加上 `"katrain-admin"`；
     - `test_application_images_state_and_service_dns_contract` 末尾加 `assert immutable.fullmatch(production["katrain-admin"]["image"])`；
     - 新增：
```python
def test_admin_console_is_production_only_and_loopback_only():
    preview = render_compose()["services"]
    production = render_compose(production=True)["services"]
    assert "katrain-admin" not in preview
    admin = production["katrain-admin"]
    assert [p.get("host_ip") for p in admin["ports"]] == ["127.0.0.1"]  # not even the WireGuard address
    assert admin["image"] == production["katrain-web"]["image"]
    assert admin["command"][:3] == ["python3", "-m", "katrain.web.admin"]
    assert admin["environment"]["KATRAIN_ADMIN_ENV"] == "prod"
```
  然后在合并结果上跑 release 的闸：部署产物测试；preview 守卫（preview 模式下，结算、回收预扣、补账、周期结算、直播、平台初始化这 7 个会写生产的动作一个都不许跑；合并报「无冲突」也不等于守卫还在）；本切片的测试。
```bash
cd /private/tmp/claude-501/rel-admin-console && uv sync --extra web --extra cron
set -o pipefail
CI=true uv run pytest tests/deploy "tests/web_ui/test_backend_setup.py::test_preview_mode_keeps_local_app_without_production_effects" -q -p no:cacheprovider 2>&1 | tail -3; echo "gate exit=$?"
CI=true uv run pytest tests/web_ui/test_admin_app.py tests/web_ui/test_admin_auth.py tests/web_ui/test_admin_cron_api.py tests/web_ui/test_admin_cron_health.py tests/web_ui/test_cron_run_recorder.py tests/web_ui/test_cron_status_tables_parity.py tests/web_ui/test_cron_import_boundary.py -q -p no:cacheprovider 2>&1 | tail -3; echo "slice exit=$?"
```
  期望结果：`gate exit=0`、`slice exit=0`，有一个不是 0 就不许推。提交之后，🛑 Fan 点头再执行 `git -C /private/tmp/claude-501/rel-admin-console push origin HEAD:release/ucloud-20260805`，然后用 `git -C /private/tmp/claude-501/rel-admin-console rev-parse --short HEAD` 取得下面的 `<SHA>`。
- [ ] **Step 4：在 ucloud-v100 上发布**（每一条执行前都要 Fan 点头）。每次 `ssh` 都是新 shell：`<SHA>`、`<TS>`、`<WEB_ID>`、`<CRON_ID>` 在每条命令里写成字面量；回滚锚点写进服务器上的 `/opt/katrain/backups/anchors-<SHA>.txt`。容器名和库名以切片 0 Task 6 Step 1 实际查到的为准。和切片 0 的发布相比有三处不同：`CRON_IMAGE` 这次一定要重建（`katrain/cron/` 改了）；这次有 DDL（katrain-web 启动时建三张新表）；多了一个服务 `katrain-admin`，而且要先起 web、建好表，再起 cron 和 admin。

4a. **先看盘，再动手**。取代码、构建两个镜像、pg_dump、恢复验证库都要占盘，峰值约 6–7 GB：
```bash
ssh ucloud-v100 "df -B1 -P /; ls -1 /opt/katrain/releases; readlink /opt/katrain/current"
```
Expected：可用空间（`df` 第 4 列）≥ 10 GB 才继续。不够就停下，把 `releases/` 清单和 `current` 的指向交给 Fan，由他决定回收哪几个旧 release 目录。**`current` 指向的那个目录不能删，那是回滚锚点。**

4b. **记下回滚锚点**（镜像 ID 不是密钥；env 里其他行一律不打印）：
```bash
ssh ucloud-v100 'sudo bash -s' <<'SH'
set -euo pipefail
A=/opt/katrain/backups/anchors-<SHA>.txt
OLD=$(readlink /opt/katrain/current)
W=$(grep '^WEB_IMAGE=' /etc/katrain/ucloud.env | cut -d= -f2)
C=$(grep '^CRON_IMAGE=' /etc/katrain/ucloud.env | cut -d= -f2)
docker image inspect --format '{{.Id}}' "$W" "$C" > /dev/null
printf 'OLD_RELEASE=%s\nOLD_WEB_IMAGE=%s\nOLD_CRON_IMAGE=%s\n' "$OLD" "$W" "$C" | tee "$A"
SH
```
Expected：打印三行 `OLD_RELEASE=…`、`OLD_WEB_IMAGE=sha256:…`、`OLD_CRON_IMAGE=sha256:…`，没有报错，即两个旧镜像都还在（回滚要用）。

4c. **取代码**（不接管道。runbook 2026-09-23：`clone --depth 1` 连败两次，那次是靠旧目录增量 fetch 再 archive 发出去的）：
```bash
ssh ucloud-v100 "sudo git clone --depth 1 --branch release/ucloud-20260805 https://github.com/shevapato2008/katrain.git /opt/katrain/releases/<SHA>; echo clone-exit=\$?; sudo git -C /opt/katrain/releases/<SHA> rev-parse --short HEAD"
```
Expected：`clone-exit=0`，下一行等于 `<SHA>`。**失败时的兜底**：先 `ssh ucloud-v100 "ls -d /opt/katrain/releases/*/.git"` 找一个带 `.git` 的旧目录（下面叫 `<GITDIR>`，写它所在的目录），然后：
```bash
ssh ucloud-v100 "sudo git -C <GITDIR> fetch --depth 1 origin release/ucloud-20260805 && sudo git -C <GITDIR> rev-parse --short FETCH_HEAD"
ssh ucloud-v100 "set -o pipefail; sudo mkdir /opt/katrain/releases/<SHA> && sudo git -C <GITDIR> archive <SHA> | sudo tar -x -C /opt/katrain/releases/<SHA>; echo archive-exit=\$?"
```
Expected：第一条打印的正好是 `<SHA>`；第二条 `archive-exit=0`。`mkdir` 报「已存在」时停下，先看清那个目录是怎么来的，**不要 `rm -rf` 带占位符的路径**。

4d. **构建两个镜像**（日志写文件，只看结果行，退出码不被管道吞掉）：
```bash
ssh ucloud-v100 "cd /opt/katrain/releases/<SHA> && sudo deploy/ucloud/scripts/build-web.sh katrain-web:<SHA> > /tmp/build-web-<SHA>.log 2>&1; echo build-exit=\$?; grep -E 'image_id=|size_bytes=' /tmp/build-web-<SHA>.log"
ssh ucloud-v100 "cd /opt/katrain/releases/<SHA> && sudo docker build --pull=false -f Dockerfile.cron -t katrain-cron:<SHA> . > /tmp/build-cron-<SHA>.log 2>&1; echo build-exit=\$?; sudo docker image inspect --format '{{.Id}}' katrain-cron:<SHA>"
```
Expected：两个 `build-exit=0`；第一条打印的 `image_id=sha256:…` 下面叫 `<WEB_ID>`，第二条打印的 ID 下面叫 `<CRON_ID>`。`build-web.sh` 的容器内容自检里要有 Step 3 加的两项（能 import `katrain.web.admin.app`、`static-admin/admin.html` 存在）。

4e. **备份，并实际恢复验证一次**（这次有 DDL，更不能省）：
```bash
ssh ucloud-v100 'sudo bash -s' <<'SH'
set -euo pipefail
TS=<TS>   # 例如 20260925-1030；写成字面量，发布记录也要用
PG=katrain-ucloud-postgres-1; DB=katrain_prod_20260725; V=katrain_restore_verify_$TS; W=/tmp/restore-verify-$TS
mkdir -p "$W"
TABLES=$(docker exec "$PG" psql -U katrain_user -d "$DB" -At -c "select tablename from pg_tables where schemaname='public' order by 1")
N=$(printf '%s\n' "$TABLES" | grep -c . || true)
[ "$N" -gt 0 ] || { echo "!! 表清单是空的：什么都没比较，不能算通过"; exit 1; }
counts() { for t in $TABLES; do printf '%s %s\n' "$t" "$(docker exec "$PG" psql -U katrain_user -d "$1" -At -c "select count(*) from \"$t\"")"; done; }
counts "$DB" > "$W/before"
docker exec "$PG" pg_dump -U katrain_user -Fc "$DB" > /opt/katrain/backups/prod-$TS.dump
counts "$DB" > "$W/after"
echo "DUMP=/opt/katrain/backups/prod-$TS.dump" >> /opt/katrain/backups/anchors-<SHA>.txt
docker exec "$PG" createdb -U katrain_user "$V"
docker exec -i "$PG" pg_restore -U katrain_user -d "$V" < /opt/katrain/backups/prod-$TS.dump
echo "pg_restore exit=0"
counts "$V" > "$W/restored"
# dump 拿的是它开始那一刻的快照：dump 前后行数没变的表，恢复出来必须一模一样；dump 期间有写入的表，
# 恢复出来的行数必须落在前后两个数之间。其余一律算对不上。
BAD=0
paste "$W/before" "$W/after" "$W/restored" | awk '{ b=$2; a=$4; r=$6; lo=(b<a?b:a); hi=(b>a?b:a); if (r<lo || r>hi) { print "MISMATCH", $1, "before=" b, "after=" a, "restored=" r; bad=1 } } END { exit bad }' || BAD=1
docker exec "$PG" dropdb -U katrain_user "$V"
[ "$BAD" = 0 ] || { echo "!! 行数对不上，见上面的 MISMATCH"; exit 1; }
echo "row-count check passed: $N tables"
SH
```
Expected：打印 `pg_restore exit=0` 和 `row-count check passed: <N> tables`（N 是生产库的表数，几十张，不是 0），ssh 退出码 0。有 `MISMATCH` 时脚本以非 0 退出：停下，把输出交给 Fan。脚本因为别的原因中途退出时，手工 `dropdb katrain_restore_verify_<TS>` 清掉验证库。

4f. **生成候选 env**（正在用的 env 这一步不动；只打印改动的行数，不打印内容，env 里有密钥）：
```bash
ssh ucloud-v100 'sudo bash -s' <<'SH'
set -euo pipefail
C=/etc/katrain/ucloud.env.candidate-<SHA>
install -m 600 -o root -g root /etc/katrain/ucloud.env "$C"
sed -i "s|^WEB_IMAGE=.*|WEB_IMAGE=<WEB_ID>|; s|^CRON_IMAGE=.*|CRON_IMAGE=<CRON_ID>|" "$C"
echo "changed lines: $(diff /etc/katrain/ucloud.env "$C" | grep -c '^[<>]' || true)"
stat -c '%U:%G %a' "$C"
SH
```
Expected：`changed lines: 4`（WEB_IMAGE、CRON_IMAGE 各一删一增）；`root:root 600`。

4g. **用候选 env 跑预检**：
```bash
ssh ucloud-v100 "cd /opt/katrain/releases/<SHA> && sudo deploy/ucloud/scripts/preflight.sh --phase full --env-file /etc/katrain/ucloud.env.candidate-<SHA>; echo preflight-exit=\$?"
```
Expected：全绿。**容量闸红了，不要自己越过**：runbook 的规矩是任何一道预检红了就停。把输出里的 `available_bytes` 和 4a 的盘面交给 Fan，由他当场决定是先回收空间，还是这一次越过。最近几次发布的记录都写着「同因越过」（那道闸按迁移的峰值 38.5 GB 设，不是普通发布的峰值），但越不越过由 Fan 当场决定，本计划不预先授权。其他任何一道闸红了都停。决定不发了：`ssh ucloud-v100 "sudo rm /etc/katrain/ucloud.env.candidate-<SHA>"`，正在用的 env 从头到尾没动过。

4h. **启用候选 env、切换 `current`、dry-run**：
```bash
ssh ucloud-v100 'sudo bash -s' <<'SH'
set -euo pipefail
BAK=/opt/katrain/backups/ucloud.env.$(date +%Y%m%dT%H%M%S).bak
cp -p /etc/katrain/ucloud.env "$BAK"
echo "ENV_BACKUP=$BAK" >> /opt/katrain/backups/anchors-<SHA>.txt
mv /etc/katrain/ucloud.env.candidate-<SHA> /etc/katrain/ucloud.env
ln -sfn /opt/katrain/releases/<SHA> /opt/katrain/current
cd /opt/katrain/current
docker compose --env-file /etc/katrain/ucloud.env -f deploy/ucloud/compose.yml -f deploy/ucloud/compose.production.yml --profile production up -d --dry-run katrain-web katrain-cron katrain-admin
SH
```
Expected：只新建或重建 `katrain-web`、`katrain-cron`、`katrain-admin`，外加一次性的 `minio-setup`；`katago-*` 和 `postgres` 只出现 `Waiting` / `Healthy`。不对就执行 4j。

4i. **分两步起服务**（Fan 点头后）：先起 web、等它健康、确认三张表已经建好，再起 cron 和 admin：
```bash
ssh ucloud-v100 "cd /opt/katrain/current && sudo docker compose --env-file /etc/katrain/ucloud.env -f deploy/ucloud/compose.yml -f deploy/ucloud/compose.production.yml --profile production up -d katrain-web"
ssh ucloud-v100 'for i in $(seq 1 60); do s=$(sudo docker inspect -f "{{.State.Health.Status}}" katrain-ucloud-katrain-web-1); [ "$s" = healthy ] && break; sleep 5; done; echo "katrain-web=$s"; [ "$s" = healthy ]'
ssh ucloud-v100 "sudo docker exec katrain-ucloud-postgres-1 psql -U katrain_user -d katrain_prod_20260725 -At -c \"select count(*) from information_schema.tables where table_schema='public' and table_name in ('admin_audit_log','cron_job_status','cron_job_runs')\""
ssh ucloud-v100 "cd /opt/katrain/current && sudo docker compose --env-file /etc/katrain/ucloud.env -f deploy/ucloud/compose.yml -f deploy/ucloud/compose.production.yml --profile production up -d katrain-cron katrain-admin"
ssh ucloud-v100 'for i in $(seq 1 60); do s=$(sudo docker inspect -f "{{.State.Health.Status}}" katrain-ucloud-katrain-admin-1); [ "$s" = healthy ] && break; sleep 5; done; echo "katrain-admin=$s"; [ "$s" = healthy ]'
ssh ucloud-v100 'for i in $(seq 1 60); do s=$(sudo docker inspect -f "{{.State.Health.Status}}" katrain-ucloud-katrain-cron-1); [ "$s" = healthy ] && break; sleep 5; done; echo "katrain-cron=$s"; [ "$s" = healthy ]'
for u in / /galaxy /api/v1/health; do printf '%s -> ' "$u"; curl -s -o /dev/null -w '%{http_code}\n' "https://modelstella.com$u"; done
```
Expected：`katrain-web=healthy`；表数 `3`；`katrain-admin=healthy`、`katrain-cron=healthy`（没到 healthy 时那条 ssh 以非 0 退出）；三个外网探针都是 `200`。**任何一项不对就执行 4j**，不要在生产上现场排查。

4j. **回滚**（只在 4h / 4i 失败时执行；执行前 Fan 点头）：
```bash
ssh ucloud-v100 'sudo bash -s' <<'SH'
set -euo pipefail
. /opt/katrain/backups/anchors-<SHA>.txt
cp "$ENV_BACKUP" /etc/katrain/ucloud.env
ln -sfn "$OLD_RELEASE" /opt/katrain/current
docker rm -f katrain-ucloud-katrain-admin-1 || true   # 旧版本的 compose 里没有这个服务，up 不会替你停它
cd /opt/katrain/current
docker compose --env-file /etc/katrain/ucloud.env -f deploy/ucloud/compose.yml -f deploy/ucloud/compose.production.yml --profile production up -d katrain-web katrain-cron
SH
```
然后重跑 4i 里等 web、等 cron 健康的两行和外网探针，要求都恢复 healthy、探针 200。三张新表留在库里无害：旧代码不读它们，旧 cron 也不写。
- [ ] **Step 5：验证生产**：
```bash
ssh ucloud-v100 "sudo ss -ltnp | grep ':8010 '"                                      # 只有 127.0.0.1:8010
curl -s -o /dev/null -w '%{http_code}\n' https://modelstella.com/api/admin/health     # 404
ssh ucloud-v100 "sudo docker exec katrain-ucloud-postgres-1 psql -U katrain_user -d katrain_prod_20260725 -At -c 'SELECT count(*) FROM cron_job_status;'"   # 9
```
然后开隧道 `ssh -N -L 8011:127.0.0.1:8010 ucloud-v100`，打开 http://localhost:8011：页头显示「生产环境」，Fan 用管理员账号登录，能看到 9 个任务的真实状态。
- [ ] **Step 6：在 runbook 里补一条发布记录**（`/private/tmp/claude-501/rel-admin-console/docs/operations/ucloud-migration-runbook.md`），格式照 2026-09-23 那条。其中要写明：新服务 katrain-admin 只绑 127.0.0.1；新增三张表；镜像 ID；备份文件与恢复验证结果；回滚锚点（`anchors-<SHA>.txt` 的内容）；代码是 clone 来的还是走了兜底；预检容量闸怎么处理的；发布前后的探针。提交并推送 release 分支（🛑 Fan 点头）。然后删临时 worktree：先执行 `git -C /private/tmp/claude-501/rel-admin-console status --ignored` 确认没有需要保留的东西，再执行 `git -C /Users/fan/Repositories/katrain worktree remove /private/tmp/claude-501/rel-admin-console`。

---

## Self-Review 记录

- **对照 spec 的覆盖**：
  - §5.1 进程与网络：Task 5、11、15；
  - §5.2 结构：Task 4–10；
  - §5.3 鉴权：Task 6；§5.4 审计：Task 6；
  - §5.5 前端隔离：Task 2 的 Step 4、5、11，以及 Task 13 的 Step 3；
  - §5.6 部署：Task 11、14、15；§5.7 访问：Task 11 的 Step 6；
  - §6.2 两张表：Task 4；§6.3 记录方式：Task 7、8；§6.4 健康判定：Task 9；§6.5 契约：Task 2 的 types.ts、Task 3 的 Step 7、Task 10；§6.6 七步：Task 1–3、12–14；§6.7 诚实：CronPage 的三条测试和 Task 12 的 Step 3；
  - §7 测试：分散在各任务里；§8 不做的事：本计划里没有对应的任务。
- **占位符扫描**：`<工作人员代号>`、`<工作人员的公钥>` 出现在运维文档模板里，属于运维执行时才有的输入；生产发布里的 `<release 分支尖端的 short sha>`、`<WEB_ID>`、`<CRON_ID>` 是运行时才知道的值，每一个都写明了从哪条命令的输出取得。
- **名字一致**：
  - `create_admin_app`、`check_startup`、`require_admin`、`bearer_token`、`username_from_token`、`create_session_token`、`getToken` / `setToken` / `clearToken`、`errorText`、`RunRecorder.run`、`register`、`heartbeat`、`heartbeat_forever`、`enter_loop`、`exit_loop`、`loop_started`、`record_loop_crash`、`derive_health`、`as_utc`，在定义它们的任务和使用它们的任务里写法一致；
  - loop 任务的 `last_iteration_at` 和 `heartbeat_stats()` 在 Task 7 的测试和 Task 8 的实现之间一致；
  - TS 类型与 pydantic 模型的字段一一对应（Task 2 的 types.ts 对 Task 10）。
- **2026-09-24 按 writing-plans 模板复核**：
  - 原来单独的「准备环境 + 记录基线」（旧 Task 0）和「契约定稿」（旧 Task 4）都不是能单独验收的交付物，按 Task Right-Sizing 并进用到它们的任务：`npm ci` 进 Task 1（截参考图要用 Playwright），Python 依赖和两份基线进 Task 2 的 Step 1，契约定稿成为 Task 3 的 Step 7–8。其后的任务依次前移一个编号。
  - 所有任务都有了 Interfaces。
  - 旧 Task 16 写的是「命令与切片 0 计划 Task 7 Step 4 完全相同，只有三处不同」，违反「不许写 Similar to Task N」，现在 Task 15 Step 4 写全了命令。
  - 参考图、实现截图、本机集成三处原来只有文字描述，补上了可以直接运行的 Playwright 脚本。fixture 的 `error` 态改成「第一次成功、之后 502」，这样才截得出设计稿里「错误条 + 页面数据停在」那一屏。
  - vitest 基线从「数通过数」改成按用例名字做差；停 vite 时只杀自己起的那个进程。
- **2026-09-24 Codex 第一轮对抗评审（15 条）之后的修订**：
  - 采纳：跑测试之前先确认 `katrain/config.json` 干净，再允许还原；cron 比 web 先启动时，心跳把缺的状态行补上（原先要等到下次重启）；启动那一次也经 APScheduler，`max_instances` 管得住全部运行，不会旧结果盖新状态；登记时把上一个进程留下的 `running` 历史标成失败；备份比对时表清单不许为空；发布改成候选 env 先过预检、再原子替换，写明回滚（包括删掉旧 compose 不认识的 admin 容器）；pytest 退出码只接受 0/1，并确认跑到了 summary；错误条带状态码；API 测试的「现在」在夹具里取；ESLint 兜底规则管住 `main.tsx`、`AppRouter.tsx` 这些公开入口；字体复用 `CHINESE_UI_FONT`；server-deploy 凡写死服务集合处都改；parity 比到字符串长度、时区和索引。
  - 部分采纳：`localhost` 上 cookie 不分端口。没有改成每个环境一个 `*.localhost` 主机名（Safari 未必能解析，Windows 上的工作人员还要另配），而是把 cookie 的 Path 限定到 `/api/admin`：发往本机其他端口普通页面的请求不再带它。剩下的风险写进了 spec §5.3。
  - 不采纳：「最后一条报错」改存运行里的最后一条 ERROR。现在存的是第一条，通常就是根因，后面的报错多半由它引起；`error_count` 记着总条数。spec §6.2 写明了这个语义。
  - 同形状排查：切片 0 那一轮的发现（看盘、回滚锚点、clone 兜底、`pipefail`、zsh 分词、每次调用都是新 shell）在这份计划里同样存在，一并改了；另外发现变异检查原先写的是用 `git checkout` 还原，那会冲掉本任务还没提交的改动，已改成先备份再还原。
  - 两家的发现没有重合：切片 0 那一轮盯发布与令牌，这一轮盯 cron 语义与会话边界。
- **2026-09-24 Codex 第二轮（9 条）之后的修订**，全部采纳：
  - 会话改成令牌放 sessionStorage + `Authorization: Bearer`，**不用 cookie**，所有响应加 CSP。第一轮的 `Path=/api/admin` 只是降低概率：本机被攻陷的服务可以先把浏览器引到它自己的页面，再同站请求自己的 `/api/admin/…`，cookie 照样送过去；换成每环境一个主机名也一样，端口不参与 cookie 匹配。sessionStorage 按端口隔离，是这一类问题的根治。代价原本是关掉标签页要重新登录（spec E8）；Fan 2026-09-24 改为保持登录，见本节最后一条。
  - 本地装不上 APScheduler：Task 8 新增 `cron` extra（APScheduler 3.x、bs4、lxml），并给 `requirements-cron.txt` 加上 `<4`。
  - 表晚建：调度器最多等 60 秒登记成功，再发起第一次运行；之后每次心跳重试**完整**登记；登记只收尾本进程启动之前留下的 `running`。
  - 备份比对：dump 前后各数一遍，恢复出来的行数必须落在两数之间，对不上就非零退出。
  - 门禁：`| tail` 的代码块统一补 `pipefail`；vitest 改用 `vitestnewfail.sh`（报告每次新生成）；vite 等待循环失败时不再打印 `ready`；构建与边界核对用 `set -euo pipefail`。
  - 抽屉的 401 交给会话层，加测试。
  - 「最近报错」的文案与数据一致：存的是第一条，运行历史注明「一共 N 条，这里是第一条」。
  - parity 比到默认值的内容，两次变异分开写。
  - server-deploy 再补 description 和 MinIO 那两处。
  - 同形状（来自切片 0 那一轮）：生产等健康要显式失败，并且等 cron；测试机的 katrain-web 没有 healthcheck，用 curl 健康端点。
- 两轮评审到此结束（Fan 定的上限是两轮）。第二轮之后的这批修订没有再经过 Codex，改动最大的是 Task 6 的会话方案；Fan 如果想再过一遍，可以单独让 Codex 只审 Task 2、5、6。
- **把计划里的后端代码真跑了一遍**（2026-09-24，导出代码树 + 主 venv + 临时装的 APScheduler 3.11）：计划原文里所有「在某行之后加 / 改成」的锚点都对得上，Task 4–10 的 61 条测试全过。变异检查发现两条测试是空的，已修：
  - 公开令牌同时被 aud、type 两道挡住，删掉任何一道它都还是绿的，原 Step 5 的「删 type 检查、看它变红」照做会红不了。现在用伪造令牌给每道检查各配一条测试，另加一条对照用例证明伪造出来的令牌本身能进。
  - 「心跳重试登记」那条测试最后自己调了 `ensure_registered()`，心跳漏掉重试它也照样绿，已去掉。
  - 前端也真跑了一遍（导出代码树 + 主工作树的 node_modules）：`tsc -b` 通过（先放一个类型错误确认它确实在查 admin 的文件）；vitest 起初 1 条失败，是 `client.test.ts` 的 `reply()` 给两次 fetch 返回同一个 `Response`，第二次读 body 报 `Body is unusable`，第一版就有这个问题，已改成每次返回新的；ESLint 报出两处 error，原计划误写成「warning 可以接受」，已按仓里先例补上 `eslint-disable-next-line … -- 理由`。
- **2026-09-24 Fan 定：后台保持登录。** 令牌从 sessionStorage 换到 localStorage，两者隔离性相同（都按协议+主机+端口），多出的两条风险和上限写在 spec §5.3。换存储顺带暴露一个原先不存在的问题：旧的内存兜底每次登录都在内存里存一份，换成多个标签页共用的 localStorage 之后，别的标签页点了「登出」，这一页还会从内存里拿出旧令牌接着用。现在只在 storage 被禁用时才放内存，`client.test.ts` 加了两条用例（存在 localStorage 里；别的标签页登出后本页拿不到令牌）。前端按新原文重新实跑：`tsc -b`、eslint 通过，vitest 11 条全过；两次变异（登录时照旧在内存里存一份 / 换回 sessionStorage）各让对应的用例变红。
