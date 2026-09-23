# 管理后台骨架 + cron 可视化（切片 1）Implementation Plan

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
- cookie 名 `katrain_admin_<env>`，HttpOnly、SameSite=Strict、Path=/、8 小时，不设 Secure。
- 非 GET 请求必须带 `X-Katrain-Admin: 1`。
- 会话令牌的内容是 `{sub, type:"admin_session", aud:"katrain-admin", env, exp}`，校验时 **type、aud、env 三项都要查**。
- cron：心跳 30 秒一次；超过 120 秒没有心跳算失联；loop 超过 300 秒没有推进算卡住；运行历史保留 14 天；间隔 ≥ 60 秒的任务每次运行都记历史，更频繁的只记不成功的。
- `katrain/cron/**` 只许 import 标准库、sqlalchemy 和 `katrain.cron.*`（由 `tests/web_ui/test_cron_import_boundary.py` 守着）。
- 后台进程不调用 `init_db()`；新表都定义在 `katrain/web/core/models_db.py` 里，cron 侧写同名映射。
- 目标视口 1440×900；后台界面只做中文；文件名不许以 `log` 开头（登录页叫 `SignInPage.tsx`）。
- **Task 3 的四图对比经 Fan 明确确认之前，不做任何后端任务（Task 4 起）**。这是 Fan 定的硬性关卡。
- 只在 worktree `~/Repositories/katrain-admin-console`（分支 `feature/admin-console`）里工作，不碰共享主工作树的分支。
- 推送、部署、写生产库，**执行当下**都要 Fan 点头。先测试机，再生产。
- 提交信息末尾加 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`。

## Review Focus

- 同一个浏览器里同时开着测试和生产两条隧道（都在 localhost，cookie 不分端口）：不能串号，页头必须显示正确的环境 → Task 6 的 `test_token_for_other_env_is_rejected`，外加登录页显示环境的 `SignInPage.test.tsx`。
- 任务吞掉了异常、只打了一条 ERROR 日志（cleanup.py 的写法）：必须显示「有报错」，不能显示「成功」→ Task 7 的 `test_a_job_that_swallows_its_exception_is_recorded_as_errors_not_success`。
- cron 进程被 SIGKILL 或 OOM 杀掉，来不及写任何东西：2 分钟内页面必须变成「失联」，不能一直停在最后一次的「正常」→ Task 9 的 offline 用例，加上 Task 12 的实停验证。
- 管理员登录期间被撤掉权限：下一次请求就必须回到登录页 → Task 6 的 `test_revoking_is_admin_takes_effect_on_next_request`。
- 测试用的 SQLite 返回不带时区的时间，和带时区的「现在」相减会直接抛 TypeError → Task 9 的 `test_naive_timestamps_from_sqlite_are_treated_as_utc`。

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
| `katrain/web/admin/__init__.py`、`__main__.py`、`app.py`、`settings.py` | 新建 | 后台进程、启动闸、静态文件、SPA 兜底 |
| `katrain/web/admin/session.py`、`audit.py`、`routers/__init__.py`、`routers/auth.py` | 新建 | 会话、CSRF、登录/登出/me、审计 |
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
  - `error`：刷新时接口返回 502，错误条写明原因和「页面数据停在 HH:MM:SS」，表格保留上一次的数据；
  - `missing`：503，表不存在；
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
cd /Users/fan/Repositories/katrain-admin-console/katrain/web/ui
mkdir -p ../../../superpowers/tracks/admin-console/slice1/reference
npx playwright test --config=playwright.vite.config.ts tests/admin-reference.shoot.spec.ts --reporter=line 2>&1 | tail -5
rm tests/admin-reference.shoot.spec.ts
ls ../../../superpowers/tracks/admin-console/slice1/reference
```
Expected：`8 passed`，目录里正好 8 张 png。有哪一态失败，就是设计稿没切到那一屏：修设计稿再截，不许跳过。

- [ ] **Step 6：提交设计稿、参考图和说明**
```bash
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
- Test：`katrain/web/ui/src/admin/api/client.test.ts`、`src/admin/pages/CronPage.test.tsx`、`src/admin/pages/SignInPage.test.tsx`
- 不提交：`.superpowers/baseline/cron_slice_failed_before.txt`、`vitest_before.json`、`vitest_failed_before.txt`（Step 1 生成，Task 13 拿来做差）

**Interfaces:**
- Produces（TS 契约，Task 3 定稿，Task 10 的后端必须与之一致）：`src/admin/api/types.ts` 里的 `AdminEnv`、`AdminMe`、`HealthState`、`RunStatus`、`CronJob`、`CronJobsResponse`、`CronRun`、`CronRunsResponse`、`QueueSummary`、`CronQueuesResponse`
- Produces：`adminFetch<T>(path, init?)`、`AdminAuthError(message?)`、`AdminApiError(status, message)`
- Produces：data-testid `admin-env`、`admin-main`、`cron-error`、`cron-loading`、`cron-empty`、`cron-process`、`cron-table`、`cron-row-<name>`、`health-<state>`、`queue-live`、`queue-report`、`run-history-scroll`、`signin-env`

- [ ] **Step 1：改任何代码之前，装 Python 依赖并记录两份基线**（只记失败用例的名字。切片 0 已在这个 worktree 里装过依赖时，`uv sync` 很快结束）

```bash
cd /Users/fan/Repositories/katrain-admin-console
uv sync --extra web
git check-ignore -q .superpowers/baseline/x && echo ignored-ok   # 根目录 .gitignore:208 忽略了 .superpowers/
B=/Users/fan/Repositories/katrain-admin-console/.superpowers/baseline; mkdir -p $B
CI=true uv run pytest tests/web_ui -q -p no:cacheprovider --continue-on-collection-errors -rfE 2>&1 \
  | grep -E '^(FAILED|ERROR) ' | sed -E 's/ - .*//' | sort -u > $B/cron_slice_failed_before.txt
wc -l < $B/cron_slice_failed_before.txt
(cd katrain/web/ui && npx vitest run --reporter=json --outputFile=$B/vitest_before.json > /dev/null 2>&1); echo "vitest exit=$?"
python3 - "$B/vitest_before.json" "$B/vitest_failed_before.txt" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
names = set()
for f in d["testResults"]:
    file = f["name"].split("/katrain/web/ui/")[-1]
    if f.get("status") == "failed" and not f["assertionResults"]:
        names.add(f"{file} :: <文件本身没跑起来>")
    names |= {f"{file} :: {a['fullName']}" for a in f["assertionResults"] if a["status"] == "failed"}
open(sys.argv[2], "w").write("".join(n + "\n" for n in sorted(names)))
print(d["numTotalTests"], "tests,", len(names), "failed")
PY
git status --short; git checkout -- katrain/config.json 2>/dev/null || true
```
Expected：打印 `ignored-ok`；`wc -l` 输出一个数（可以是 0）；最后打印 vitest 的用例总数和失败数。不要把还不存在的测试文件当参数传给 pytest：pytest 会以用法错误直接退出，基线就会**静默为空**。

- [ ] **Step 2：先写三个行为测试**

`src/admin/api/client.test.ts`：
```ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import { adminFetch } from './client';

afterEach(() => vi.unstubAllGlobals());

const reply = (status: number, body: unknown) =>
  vi.fn().mockResolvedValue(new Response(status === 204 ? null : JSON.stringify(body), { status }));

describe('adminFetch', () => {
  it('非 GET 请求带上 X-Katrain-Admin: 1，GET 不带', async () => {
    const f = reply(200, { ok: 1 });
    vi.stubGlobal('fetch', f);
    await adminFetch('/api/admin/auth/login', { method: 'POST', body: '{}' });
    await adminFetch('/api/admin/cron/jobs');
    expect(new Headers(f.mock.calls[0][1].headers).get('X-Katrain-Admin')).toBe('1');
    expect(new Headers(f.mock.calls[1][1].headers).get('X-Katrain-Admin')).toBeNull();
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
    expect(screen.getByTestId('cron-error')).toHaveTextContent('Bad Gateway');
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
    expect(screen.getByTestId('cron-error')).toHaveTextContent('cron 状态表不存在');
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

5c. 在 `defineConfig([ … ])` 的最后一个配置对象之后加：
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
// 后台的所有请求都走这里：同源 cookie 会话；非 GET 请求带 X-Katrain-Admin: 1（后端的 CSRF 闸）。
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
  const method = (init.method ?? 'GET').toUpperCase();
  const headers = new Headers(init.headers);
  if (method !== 'GET') headers.set('X-Katrain-Admin', '1');
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const res = await fetch(path, { ...init, method, headers, credentials: 'same-origin' });
  if (res.status === 401) throw new AdminAuthError(await detailOf(res));
  if (!res.ok) throw new AdminApiError(res.status, (await detailOf(res)) ?? `${res.status} ${res.statusText}`);
  return (res.status === 204 ? undefined : await res.json()) as T;
}
```

`src/admin/api/authApi.ts`：
```ts
import { adminFetch } from './client';
import type { AdminHealth, AdminMe } from './types';

// FIXTURE 分支：删除条件与 cronApi.ts 相同（Task 13）。
const useFixture = import.meta.env.VITE_ADMIN_FIXTURE === 'true';
const fixture = () => import('../__fixtures__/cronFixture');

export const getHealth = async (): Promise<AdminHealth> =>
  useFixture ? (await fixture()).healthFixture() : adminFetch<AdminHealth>('/api/admin/health');

export const getMe = async (): Promise<AdminMe> =>
  useFixture ? (await fixture()).meFixture() : adminFetch<AdminMe>('/api/admin/auth/me');

export const login = async (username: string, password: string): Promise<AdminMe> =>
  useFixture
    ? (await fixture()).loginFixture()
    : adminFetch<AdminMe>('/api/admin/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) });

export const logout = async (): Promise<void> =>
  useFixture ? undefined : adminFetch<void>('/api/admin/auth/logout', { method: 'POST' });
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
import type { AdminEnv, AdminHealth, AdminMe, CronJob, CronJobsResponse, CronQueuesResponse, CronRun, CronRunsResponse } from '../api/types';

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
export const loginFixture = (): Promise<AdminMe> => Promise.resolve({ username: 'fan', env: env() });
export const healthFixture = (): Promise<AdminHealth> => Promise.resolve({ status: 'ok', env: env() });
```

- [ ] **Step 8：会话、主题和小工具**

`src/admin/theme.ts`：
```ts
import { createTheme } from '@mui/material/styles';
import { zenTheme } from '../theme';

// 后台沿用站点的 zen 深色基调；字体用系统自带的中文字体栈，后台不加载网页字体。
// 具体取值以 Task 1 确认的设计稿为准（superpowers/tracks/admin-console/slice1/design-notes.md）。
const FONT = "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif";

export const adminTheme = createTheme(zenTheme, {
  typography: { fontFamily: FONT },
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
import { AdminAuthError } from './api/client';
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
    } catch (e) {
      if (!(e instanceof AdminAuthError)) throw e;
    }
    setMe(null);
  }, []);

  const expire = useCallback(() => setMe(null), []);

  return (
    <SessionContext.Provider value={{ me, checking, signIn, signOut, expire }}>{children}</SessionContext.Provider>
  );
}

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
      setError(err instanceof Error ? err.message : '登录失败');
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
import type { CronJob, CronRun } from '../api/types';
import { jobLabel } from '../jobLabels';
import { fmtDateTime, fmtDuration } from '../format';

const RUN_LABEL: Record<CronRun['status'], string> = { running: '运行中', success: '成功', errors: '有报错', failed: '失败' };

export default function RunHistoryDrawer({ job, onClose }: { job: CronJob | null; onClose: () => void }) {
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
      .catch((e) => { if (alive) setError(e instanceof Error ? e.message : String(e)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [job]);

  const loadMore = async () => {
    if (!job || next === null) return;
    setLoading(true);
    try {
      const r = await getCronRuns(job.name, next);
      setRuns((prev) => [...prev, ...r.runs]);
      setNext(r.next_before_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
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
                        {r.error ?? (r.error_count ? `${r.error_count} 条报错` : '')}
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
import { AdminAuthError } from '../api/client';
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
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [expire]);

  useEffect(() => {
    alive.current = true;
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
                    <TableCell>耗时</TableCell><TableCell>连续不成功</TableCell><TableCell>最后一条报错</TableCell>
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
cd /Users/fan/Repositories/katrain-admin-console/katrain/web/ui
npx vitest run src/admin 2>&1 | tail -6
npx tsc -b 2>&1 | tail -5
npx eslint src/admin eslint.config.js
```
期望结果：vitest 全部 PASS；`tsc -b` 没有输出；eslint 没有 error（和 `AuthContext.tsx` 同款的 `react-refresh/only-export-components` warning 可以接受）。

- [ ] **Step 11：边界规则的变异检查**（每条闸都要亲眼看到它红一次）
```bash
printf "import { jobLabel } from '../admin/jobLabels';\nexport const x = jobLabel;\n" > src/galaxy/__mut_admin.ts
npx eslint src/galaxy/__mut_admin.ts; echo "exit=$?"; rm src/galaxy/__mut_admin.ts
printf "import KioskApp from '../kiosk/KioskApp';\nexport const y = KioskApp;\n" > src/admin/__mut_kiosk.ts
npx eslint src/admin/__mut_kiosk.ts; echo "exit=$?"; rm src/admin/__mut_kiosk.ts
```
期望结果：两次都报 `no-restricted-imports`，`exit=1`；两个临时文件都已删除。

- [ ] **Step 12：假数据界面能跑起来，也能构建**
```bash
npm run build:admin 2>&1 | tail -3
ls ../static-admin/admin.html ../static-admin/assets | head
lsof -iTCP:5174 -sTCP:LISTEN && echo '!! 5174 已被占用：先用 ps -o command= -p <pid> 查清是谁，别让截图打到别人的服务上'
(VITE_ADMIN_FIXTURE=true npm run dev:admin > /private/tmp/claude-501/admin-dev.log 2>&1 &)
for i in $(seq 1 60); do curl -sf http://127.0.0.1:5174/admin.html | grep -q 'KaTrain 管理后台' && break; sleep 1; done; echo ready
```
期望结果：构建以 `built in` 结尾；`static-admin/admin.html` 存在；在浏览器里打开 `http://127.0.0.1:5174/admin.html?fixture=mixed&env=test#/cron` 能看到完整界面。

- [ ] **Step 13：对齐设计稿**。拿 Task 1 的参考图逐屏对照，**只调整**上面这些文件里 `sx` 的数值、字号、颜色、间距和文案，让它与确认稿一致。**不改**数据流、data-testid 和状态语义。调整后重跑 Step 10。

- [ ] **Step 14：提交**（提交后用 `--stat` 核对文件清单，防止有文件被 `.gitignore` 吞掉）
```bash
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
for i in $(seq 1 60); do curl -sf http://127.0.0.1:5174/admin.html | grep -q 'KaTrain 管理后台' && break; sleep 1; done; echo ready
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


def _shape(model):
    return {c.name: (type(c.type).__name__, c.nullable, c.primary_key) for c in model.__table__.columns}


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
- [ ] **Step 6：变异检查**：临时删掉 cron 侧的 `last_error` 那一行，跑 parity 测试，确认它变红；然后还原（`git checkout -- katrain/cron/models.py` 之前先确认这个文件里只有本任务的改动，否则手工删行再补回）。
- [ ] **Step 7：提交** `feat(admin): cron 状态 / 运行历史 / 后台审计三张表`（`git add` 上面三个文件）。

---

### Task 5: 后台进程骨架（健康检查、启动闸、静态文件）

**Files:**
- Create：`katrain/web/admin/__init__.py`、`katrain/web/admin/settings.py`、`katrain/web/admin/app.py`、`katrain/web/admin/__main__.py`、`katrain/web/admin/routers/__init__.py`
- Test：`tests/web_ui/test_admin_app.py`

**Interfaces:**
- Produces：`create_admin_app(session_factory=None, static_dir: Path | None = None, env: str | None = None) -> FastAPI`，其中 `app.state.session_factory` 和 `app.state.admin_env` 供依赖读取；`check_startup() -> str`；`NOT_BUILT: str`

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

后台绝不能在盒子上跑，也不能用弱密钥签会话。环境名会写进 cookie 名和令牌：
测试机与生产两条隧道都在 localhost 上，cookie 不分端口，靠它互不串号。
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


def create_admin_app(session_factory=None, static_dir: Path | None = None, env: str | None = None) -> FastAPI:
    if session_factory is None:
        from katrain.web.core.db import SessionLocal

        session_factory = SessionLocal
    app = FastAPI(title="katrain-admin", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.session_factory = session_factory
    app.state.admin_env = env or admin_settings.admin_env()

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
- Produces：`require_admin(request) -> dict`（用户 dict，包含 `id`、`username`、`is_admin`；任何失败都抛 401）、`require_csrf_header(request)`（缺少请求头抛 403）、`cookie_name(env) -> str`、`create_session_token(username, env, now=None) -> str`、`audit.record(db, action, username, admin_user_id=None, target=None, detail=None)`
- Produces（测试辅助）：`make_admin_client(monkeypatch, tmp_path, env="test") -> (TestClient, Session, engine)`、`login(client, username="boss", password="pw")`、`CSRF`

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

CSRF = {"X-Katrain-Admin": "1"}


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


def login(client, username="boss", password="pw"):
    r = client.post("/api/admin/auth/login", json={"username": username, "password": password}, headers=CSRF)
    assert r.status_code == 200, r.text
    return r
```

`tests/web_ui/test_admin_auth.py`：
```python
"""后台鉴权：登录/登出/me、会话令牌的三重校验、CSRF 头、撤权即时生效、审计。"""
import pytest
from fastapi import HTTPException

from katrain.web.admin.session import cookie_name, create_session_token
from katrain.web.core import models_db
from katrain.web.core.auth import create_access_token
from katrain.web.core.config import settings
from tests.web_ui._admin_helpers import CSRF, login, make_admin_client

LOGIN_FAILED = "用户名或密码错误，或该账号没有后台权限"


@pytest.fixture
def ctx(monkeypatch, tmp_path):
    client, Session, _ = make_admin_client(monkeypatch, tmp_path)
    return client, Session


def _audit(Session):
    with Session() as s:
        rows = s.query(models_db.AdminAuditLog).order_by(models_db.AdminAuditLog.id).all()
        return [(r.action, r.username, (r.detail or {}).get("reason")) for r in rows]


def test_admin_logs_in_gets_a_strict_httponly_cookie_and_me(ctx):
    client, Session = ctx
    r = login(client)
    assert r.json() == {"username": "boss", "env": "test"}
    cookie = r.headers["set-cookie"].lower()
    assert cookie.startswith(cookie_name("test")) and "httponly" in cookie and "samesite=strict" in cookie
    assert client.get("/api/admin/auth/me").json() == {"username": "boss", "env": "test"}
    assert _audit(Session) == [("login_success", "boss", None)]


@pytest.mark.parametrize(
    "username,password,reason",
    [("carol", "pw", "not_admin"), ("boss", "wrong", "bad_password"), ("nobody", "pw", "unknown_user"), ("ghost", "pw", "bad_password")],
)
def test_login_failures_share_one_message_but_audit_the_reason(ctx, username, password, reason):
    client, Session = ctx
    r = client.post("/api/admin/auth/login", json={"username": username, "password": password}, headers=CSRF)
    assert r.status_code == 401 and r.json() == {"detail": LOGIN_FAILED}
    assert _audit(Session) == [("login_failed", username, reason)]


def test_guest_cannot_even_attempt(ctx):
    client, Session = ctx
    r = client.post("/api/admin/auth/login", json={"username": "guest", "password": "pw"}, headers=CSRF)
    assert r.status_code == 401
    assert _audit(Session) == [("login_failed", "guest", "unknown_user")]


def test_login_without_csrf_header_is_403(ctx):
    client, _ = ctx
    assert client.post("/api/admin/auth/login", json={"username": "boss", "password": "pw"}).status_code == 403


def test_public_access_token_is_rejected(ctx):
    """python-jose 在传了 audience、而令牌里根本没有 aud 时照样放行 —— 这里靠 type 检查挡住。"""
    client, _ = ctx
    client.cookies.set(cookie_name("test"), create_access_token(data={"sub": "boss"}))
    assert client.get("/api/admin/auth/me").status_code == 401


def test_token_for_other_env_is_rejected(ctx):
    client, _ = ctx
    client.cookies.set(cookie_name("test"), create_session_token("boss", "prod"))
    assert client.get("/api/admin/auth/me").status_code == 401


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


def test_logout_clears_the_cookie_and_is_audited(ctx):
    client, Session = ctx
    login(client)
    assert client.post("/api/admin/auth/logout", headers=CSRF).status_code == 204
    assert client.get("/api/admin/auth/me").status_code == 401
    assert [a[0] for a in _audit(Session)] == ["login_success", "logout"]
```
- [ ] **Step 2**：`CI=true uv run pytest tests/web_ui/test_admin_auth.py -q -p no:cacheprovider`。期望结果：FAIL，报 `ModuleNotFoundError: katrain.web.admin.session`。

- [ ] **Step 3：实现**

`katrain/web/admin/session.py`：
```python
"""后台会话：签发 / 校验令牌、cookie、require_admin 依赖、CSRF 头。

令牌与公开站点的 access token 用同一把 SECRET_KEY，靠两处区分：
  1. type == "admin_session"，必须显式检查。python-jose 在传了 audience、而令牌里根本没有 aud 时
     照样放行（2026-09-24 实测）。只靠 aud 的话，公开站点的 token 就能进后台。
  2. aud == "katrain-admin"。公开站点解码时不传 audience，带 aud 的令牌会被 jose 以
     "Invalid audience" 拒掉（同日实测），所以后台令牌反过来也进不了公开站点。
env 也写进令牌和 cookie 名：两条隧道都在 localhost 上，cookie 不分端口。
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
CSRF_HEADER = "x-katrain-admin"


def cookie_name(env: str) -> str:
    return f"katrain_admin_{env}"


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


def set_session_cookie(response, token: str, env: str) -> None:
    # 不设 secure：只经 SSH 隧道在 http://localhost 上访问。
    response.set_cookie(
        key=cookie_name(env), value=token, httponly=True, samesite="strict", path="/", max_age=SESSION_HOURS * 3600
    )


def clear_session_cookie(response, env: str) -> None:
    response.delete_cookie(key=cookie_name(env), path="/")


def user_repo(request: Request) -> SQLAlchemyUserRepository:
    return SQLAlchemyUserRepository(request.app.state.session_factory)


def require_csrf_header(request: Request) -> None:
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="缺少 X-Katrain-Admin 请求头")


async def require_admin(request: Request) -> dict[str, Any]:
    """所有需要登录的后台接口都用它。每次按用户名重新查库，撤掉 is_admin 立即生效。任何失败都回 401。"""
    require_csrf_header(request)
    env = request.app.state.admin_env
    token = request.cookies.get(cookie_name(env))
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
from katrain.web.admin.session import (
    clear_session_cookie,
    create_session_token,
    require_admin,
    require_csrf_header,
    set_session_cookie,
    user_repo,
)
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


def _password_ok(password: str, hashed: str) -> bool:
    try:
        return verify_password(password, hashed)
    except (ValueError, TypeError):  # shadow/placeholder rows carry hashes passlib cannot even parse
        return False


@router.post("/login", response_model=Me)
async def login(body: LoginBody, request: Request, response: Response):
    require_csrf_header(request)
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
    set_session_cookie(response, create_session_token(user["username"], env), env)
    return Me(username=user["username"], env=env)


@router.post("/logout", status_code=204)
async def logout(request: Request, admin: dict = Depends(require_admin)):
    with request.app.state.session_factory() as db:
        audit.record(db, "logout", admin["username"], admin_user_id=admin["id"])
    resp = Response(status_code=204)
    clear_session_cookie(resp, request.app.state.admin_env)
    return resp


@router.get("/me", response_model=Me)
async def me(request: Request, admin: dict = Depends(require_admin)):
    return Me(username=admin["username"], env=request.app.state.admin_env)
```
在 `app.py` 里：文件顶部的 import 区加上 `from katrain.web.admin.routers import auth as auth_router`；再把 `# ── API routers (must be registered before the SPA catch-all below) ──` 这一行下面补上：
```python
    app.include_router(auth_router.router, prefix="/api/admin/auth")
```
- [ ] **Step 4**：`CI=true uv run pytest tests/web_ui/test_admin_auth.py tests/web_ui/test_admin_app.py -q -p no:cacheprovider`。期望结果：全部 passed。
- [ ] **Step 5：变异检查**：把 `username_from_token` 里 `claims.get("type") != SESSION_TYPE or` 这一截临时删掉，确认 `test_public_access_token_is_rejected` 变红；然后还原，再确认它变绿。
- [ ] **Step 6：提交** `feat(admin): 后台会话 —— 登录 / 登出 / me、令牌三重校验、CSRF 头、审计`（`git add` 上面列出的文件）。

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
    - `.register(jobs: list[tuple[str, str, int | None, bool]])`
    - `async .run(job)`
    - `.enter_loop(name) -> Token`、`.exit_loop(token)`
    - `.loop_started(name)`
    - `.record_loop_crash(name, exc)`
    - `.heartbeat(loop_jobs: dict)`
    - `async .heartbeat_forever(loop_jobs, interval, stop: asyncio.Event)`
  - loop 任务需要提供的接口：`job.name`、`job.last_iteration_at: datetime | None`、`job.heartbeat_stats() -> dict`

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
```
- [ ] **Step 2**：`CI=true uv run pytest tests/web_ui/test_cron_run_recorder.py -q -p no:cacheprovider`。期望结果：FAIL，报 `ModuleNotFoundError: katrain.cron.run_recorder`。

- [ ] **Step 3：实现 `katrain/cron/run_recorder.py`**
```python
"""把每个 cron 任务的运行情况写进 cron_job_status / cron_job_runs，供 katrain-admin 只读展示。

只依赖标准库、sqlalchemy 和 katrain.cron.*：Dockerfile.cron 只 COPY katrain/cron/，
由 tests/web_ui/test_cron_import_boundary.py 守着。表由 katrain-web 的 create_all 建；
cron 如果在 web 建表之前启动，写入会失败，按规矩 1 处理，建表之后自然恢复。

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
        self._intervals: dict[str, int | None] = {}
        self._loops: dict[str, _LoopState] = {}

    # ── 进程启动时登记 ────────────────────────────────────────────────────────
    def register(self, jobs: list[tuple[str, str, int | None, bool]]) -> None:
        """jobs = [(name, kind, interval_seconds, enabled)]，停用的也登记。删掉代码里已经不存在的旧行。"""
        self._intervals = {name: interval for name, _kind, interval, _enabled in jobs}
        self._write(self._register_rows, jobs, self._clock())

    def _register_rows(self, db, jobs, now):
        db.execute(delete(CronJobStatusDB).where(CronJobStatusDB.job_name.notin_([j[0] for j in jobs])))
        for name, kind, interval, enabled in jobs:
            row = db.get(CronJobStatusDB, name)
            if row is None:
                row = CronJobStatusDB(job_name=name, consecutive_failures=0)
                db.add(row)
            row.kind, row.interval_seconds, row.enabled = kind, interval, enabled
            row.process_started_at = row.heartbeat_at = row.updated_at = now

    # ── interval 任务 ─────────────────────────────────────────────────────────
    async def run(self, job) -> None:
        """包住一次 interval 运行。任务的异常原样再抛，交给调用方（APScheduler / _run_job_once）记日志。"""
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
- Test：`tests/web_ui/test_cron_run_recorder.py`（追加三条）

**Interfaces:**
- Consumes：Task 7 的 `install_error_capture()`、`RunRecorder(session_factory)`、`.register(jobs)`、`async .run(job)`、`.enter_loop(name) -> Token`、`.exit_loop(token)`、`.loop_started(name)`、`.record_loop_crash(name, exc)`、`async .heartbeat_forever(loop_jobs, interval, stop)`；Task 4 的 `CronJobRunDB`
- Produces：`AnalyzeJob.last_iteration_at: datetime | None` 和 `AnalyzeJob.heartbeat_stats() -> {"in_flight": int, "capacity": int}`，`ReportAnalyzerJob` 也有这两项；`config.HEARTBEAT_INTERVAL`（默认 30）、`config.RUNS_RETENTION_DAYS`（默认 14）；`CronScheduler._recorder`（测试会替换它）

- [ ] **Step 1：追加测试**（加在 `test_cron_run_recorder.py` 末尾）：
```python
def test_scheduler_routes_startup_runs_through_the_recorder():
    from katrain.cron.scheduler import CronScheduler

    sched = CronScheduler()
    calls = []

    class FakeRecorder:
        async def run(self, job):
            calls.append(job.name)

    sched._recorder = FakeRecorder()
    asyncio.run(sched._run_job_once(Job("fetch_list", _ok)))
    assert calls == ["fetch_list"]


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
- [ ] **Step 2**：`CI=true uv run pytest tests/web_ui/test_cron_run_recorder.py -q -p no:cacheprovider`。期望结果：新加的三条都 FAIL。`test_scheduler_routes_…` 是断言 `[] == ['fetch_list']` 不成立，因为启动时那一次运行还没有经过记录器；另外两条报 `AttributeError`（`last_iteration_at`、`RUNS_RETENTION_DAYS`）。

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
        self._recorder.register(registry)

        # Start scheduler first (jobs will be added and run immediately)
        self._scheduler.start()
        logger.info("Scheduler started")

        # Register and immediately run each job once, then schedule for intervals
        for job_cls, interval, enabled in interval_jobs:
            if not enabled:
                logger.info("Job %s is disabled, skipping", job_cls.name)
                continue
            job = job_cls()

            # Run immediately on startup (non-blocking)
            logger.info("Running %s immediately on startup", job.name)
            asyncio.create_task(self._run_job_once(job))

            # Schedule for regular intervals — through the recorder, like the startup run
            self._scheduler.add_job(
                self._recorder.run,
                "interval",
                args=[job],
                seconds=interval,
                id=job.name,
                name=job.name,
                max_instances=1,
                misfire_grace_time=interval,
            )
            logger.info("Registered job %s (interval=%ds)", job.name, interval)

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

    async def _run_job_once(self, job):
        """Run a job once (through the recorder), logging any errors without crashing."""
        try:
            await self._recorder.run(job)
        except Exception:
            logger.exception("Job %s failed on startup", job.name)

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
- [ ] **Step 9：提交** `feat(cron): 所有运行经过记录器；常驻循环心跳；清理 14 天前的运行历史`。

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

NOW = datetime.now(timezone.utc)


@pytest.fixture
def ctx(monkeypatch, tmp_path):
    client, Session, engine = make_admin_client(monkeypatch, tmp_path)
    with Session() as s:
        s.add(models_db.CronJobStatus(job_name="fetch_list", kind="interval", interval_seconds=60, enabled=True,
                                      process_started_at=NOW - timedelta(hours=1), heartbeat_at=NOW - timedelta(seconds=10),
                                      last_started_at=NOW - timedelta(seconds=20), last_status="success", consecutive_failures=0))
        s.add(models_db.CronJobStatus(job_name="analyze", kind="loop", interval_seconds=None, enabled=True,
                                      heartbeat_at=NOW - timedelta(seconds=10), last_status="running", consecutive_failures=0,
                                      loop_iteration_at=NOW - timedelta(seconds=3),
                                      loop_stats={"in_flight": 2, "capacity": 16, "errors_total": 0, "last_error_at": None}))
        for i in range(60):
            s.add(models_db.CronJobRun(job_name="fetch_list", started_at=NOW - timedelta(minutes=60 - i), status="success", error_count=0))
        s.add(models_db.ReportTask(user_id=1, user_game_id="g1", status="pending", created_at=NOW - timedelta(minutes=5)))
        s.add(models_db.ReportTask(user_id=1, user_game_id="g2", status="pending", created_at=NOW - timedelta(minutes=2)))
        s.add(models_db.ReportTask(user_id=1, user_game_id="g3", status="completed"))
        s.commit()
    return client, Session, engine


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
    client, _, _ = ctx
    login(client)
    body = client.get("/api/admin/cron/queues").json()
    assert body["report_tasks"]["by_status"] == {"pending": 2, "completed": 1}
    oldest = datetime.fromisoformat(body["report_tasks"]["oldest_pending_at"].replace("Z", "+00:00"))
    assert abs((oldest - (NOW - timedelta(minutes=5))).total_seconds()) < 1
    assert body["live_analysis"] == {"by_status": {}, "oldest_pending_at": None}


def test_jobs_say_503_when_the_tables_do_not_exist(ctx):
    client, _, engine = ctx
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
- [ ] **Step 5：`server-deploy` skill**：
  - 在容器表 `| katrain-cron | … |` 那一行之后加：`| katrain-admin | katrain-web:local（同一镜像） | 127.0.0.1:8010 | — | **compose** | 管理后台，只经 SSH 隧道访问（docs/operations/admin-console-access.md） |`；
  - 第 7 步的命令改成 `docker compose up -d --build katrain-web katrain-cron katrain-admin`；
  - 第 8 步加一行 `curl -s http://127.0.0.1:8010/api/admin/health   # {"status":"ok","env":"test"}`。
- [ ] **Step 6：写 `docs/operations/admin-console-access.md`**
````markdown
# 管理后台访问方式（katrain-admin）

后台进程只在服务器的 127.0.0.1:8010 上监听，公网和 WireGuard 网关都到不了。访问时先开一条 SSH 隧道，把本机端口转到服务器的 127.0.0.1:8010；隧道开着以后，后台就是浏览器里的一个普通网页。

| 环境 | 开隧道（Mac 终端 / Windows PowerShell 通用） | 浏览器打开 |
|---|---|---|
| 测试（home-ubuntu） | `ssh -N -L 8010:127.0.0.1:8010 home-ubuntu` | http://localhost:8010 |
| 生产（ucloud-v100） | `ssh -N -L 8011:127.0.0.1:8010 ucloud-v100` | http://localhost:8011 |

两条隧道可以同时开着：本机端口不同，cookie 名里也带着环境名，不会串号。页头会醒目地标出当前是哪个环境。

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
- [ ] **Step 8：变异检查**：把端口临时改成 `"8010:8010"`，确认 `test_admin_is_published_on_loopback_only` 变红；然后还原。
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
});
```
```bash
cd /Users/fan/Repositories/katrain-admin-console/katrain/web/ui
npx playwright test --config=playwright.vite.config.ts tests/admin-integration.walk.spec.ts --reporter=line 2>&1 | tail -25
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8010/api/admin/auth/logout   # 不带 X-Katrain-Admin 头
rm tests/admin-integration.walk.spec.ts
```
Expected：`1 passed`，日志里打出 9 个任务各自的状态；curl 打印 `403`。本机连不上的外部源（KataGo 等）应当让对应任务显示「有报错」或「失败」，不能是「正常」：拿打印出来的状态对照 `$E/cron.log` 逐个核对，结论写进 `slice1/visual-review.md` 的「集成」一节。

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
  - 删掉 `cronApi.ts` 和 `authApi.ts` 里的 `useFixture`、`fixture` 两个常量，以及每个函数里 `if (useFixture) …` / `useFixture ? … :` 的那一支，只留 `adminFetch` 调用；
  - 确认：`grep -rn "VITE_ADMIN_FIXTURE\|__fixtures__\|useFixture" katrain/web/ui/src/admin`，期望没有输出。
- [ ] **Step 2：Python 全量对比基线**：
```bash
cd /Users/fan/Repositories/katrain-admin-console
CI=true uv run pytest tests/web_ui -q -p no:cacheprovider --continue-on-collection-errors -rfE 2>&1 \
  | grep -E '^(FAILED|ERROR) ' | sed -E 's/ - .*//' | sort -u > .superpowers/baseline/cron_slice_failed_after.txt
comm -13 .superpowers/baseline/cron_slice_failed_before.txt .superpowers/baseline/cron_slice_failed_after.txt
CI=true uv run pytest tests/test_admin_compose.py -q -p no:cacheprovider
git status --short; git checkout -- katrain/config.json 2>/dev/null || true
```
期望结果：`comm` 没有输出（没有新增的失败）；`test_admin_compose.py` 2 passed。
- [ ] **Step 3：前端：vitest 按名字和基线做差，三套构建，公开包和 kiosk 包里没有后台代码**
```bash
cd /Users/fan/Repositories/katrain-admin-console/katrain/web/ui
B=/Users/fan/Repositories/katrain-admin-console/.superpowers/baseline
npx vitest run --reporter=json --outputFile=$B/vitest_after.json > /dev/null 2>&1; echo "vitest exit=$?"
python3 - "$B/vitest_after.json" "$B/vitest_failed_after.txt" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
names = set()
for f in d["testResults"]:
    file = f["name"].split("/katrain/web/ui/")[-1]
    if f.get("status") == "failed" and not f["assertionResults"]:
        names.add(f"{file} :: <文件本身没跑起来>")
    names |= {f"{file} :: {a['fullName']}" for a in f["assertionResults"] if a["status"] == "failed"}
open(sys.argv[2], "w").write("".join(n + "\n" for n in sorted(names)))
print(d["numTotalTests"], "tests,", len(names), "failed")
PY
comm -13 $B/vitest_failed_before.txt $B/vitest_failed_after.txt
npx eslint src/admin eslint.config.js
npm run build 2>&1 | tail -2 && npm run build:kiosk-2d 2>&1 | tail -2 && npm run build:admin 2>&1 | tail -2
grep -rl "katrain-admin\|/api/admin" ../static ../static-kiosk-2d | head
```
Expected：`comm` 没有输出；eslint 没有 error；三个构建都以 `built in` 结尾，kiosk 那个还打印 `✅ kiosk boundary clean`；最后的 grep 没有输出，即公开包和 kiosk 包里没有后台代码（这是一次性核对，spec §5.5 说明了为什么不做成常设的闸）。
- [ ] **Step 4：提交** `chore(admin): 删掉 cron 页 fixture（Task 12 已接真实接口）`。按 spec，fixture 必须在这个提交里删掉。

---

### Task 14: 🛑 部署测试机，Fan 验收（推送和部署前都要 Fan 点头）

**Interfaces:**
- Consumes：Task 11 的 compose 服务 `katrain-admin` 和 `server-deploy` 的第 7、8 步；切片 0 Task 5 在测试机上授权的管理员账号

- [ ] **Step 1**：跟上 develop，再快进推送：
```bash
cd /Users/fan/Repositories/katrain-admin-console && git fetch origin && git merge --no-edit origin/develop
CI=true uv run pytest tests/web_ui/test_admin_app.py tests/web_ui/test_admin_auth.py tests/web_ui/test_admin_cron_api.py tests/web_ui/test_admin_cron_health.py tests/web_ui/test_cron_run_recorder.py tests/web_ui/test_cron_status_tables_parity.py tests/test_admin_compose.py -q -p no:cacheprovider
git push origin HEAD:develop
```
- [ ] **Step 2**：`ssh home-ubuntu "cd ~/Repositories/katrain && git pull --ff-only && docker compose up -d --build katrain-web katrain-cron katrain-admin && docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' | grep katrain"`
- [ ] **Step 3：验证**：
```bash
ssh home-ubuntu "ss -ltnp | grep ':8010 '"                                      # 只能看到 127.0.0.1:8010
ssh home-ubuntu "curl -s http://127.0.0.1:8010/api/admin/health"                # {"status":"ok","env":"test"}
curl -s -o /dev/null -w '%{http_code}\n' https://go.sailorvoyage.top/api/admin/health   # 期望 404：公网上没有这个入口
ssh home-ubuntu "docker exec katrain-postgres psql -U katrain_user -d katrain_db -At -c 'SELECT job_name, last_status, heartbeat_at FROM cron_job_status ORDER BY 1;'"
```
- [ ] **Step 4**：开隧道 `ssh -N -L 8010:127.0.0.1:8010 home-ubuntu`，在浏览器里打开 http://localhost:8010：
  - 页头显示「测试环境」；
  - 用 Fan 的管理员账号登录（切片 0 的 Task 5 已经授权）；
  - 9 个任务都有真实状态。
- [ ] **Step 5：🛑 Fan 验收。** 验收通过后，切片 1 才算满足 vertical-slice 的「完成的定义」：可部署、状态诚实、已集成、已验收、fixture 已删。

---

### Task 15: 🛑 生产部署（每一步都要 Fan 点头）

**Files**（release 分支，在 Step 2 建的临时 worktree 里）:
- Modify：`Dockerfile.web`、`deploy/ucloud/compose.yml`、`deploy/ucloud/scripts/build-web.sh`、`tests/deploy/test_ucloud_artifacts.py`、`docs/operations/ucloud-migration-runbook.md`

**Interfaces:**
- Consumes：develop 上本切片的全部提交；切片 0 Task 5 在生产上授权的管理员账号（容器名、库名以那一步实际查到的为准）
- Produces：生产上的 `katrain-admin` 服务（只绑 127.0.0.1:8010）、三张新表、runbook 里的一条发布记录

- [ ] **Step 1：先把连带发布的提交列给 Fan**：`git -C /Users/fan/Repositories/katrain log --oneline --no-merges origin/release/ucloud-20260805..origin/develop`。发布会连带 develop 自上次发布以来的全部提交；🛑 Fan 同意后再继续。
- [ ] **Step 2：合并到 release**（临时 worktree）：
```bash
cd /Users/fan/Repositories/katrain && git fetch origin
REL=/private/tmp/claude-501/rel-admin-console
git worktree add "$REL" -b release-merge-admin-console origin/release/ucloud-20260805
cd "$REL" && git merge --no-edit origin/develop || git status --short | grep '^UU'
```
**`Dockerfile.web` 一定会冲突**：develop 和 release 各有一份完全不同的 Dockerfile.web。冲突时保留 release 的版本（`git checkout --ours Dockerfile.web`），然后手工加上 Step 3 的两处改动。其他冲突逐个判断。合并即使报「无冲突」，也要看一眼 `server.py` 里 `if settings.PREVIEW_MODE:` 守卫附近，确认没有启动期写库的动作跑到守卫外面去。
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
  然后执行：`cd "$REL" && uv sync --extra web && CI=true uv run pytest tests/deploy -q -p no:cacheprovider`，期望结果：全部通过。提交后，🛑 Fan 点头再 `git push origin HEAD:release/ucloud-20260805`。
- [ ] **Step 4：在 ucloud-v100 上发布**（每一行执行前都要 Fan 点头）。跟切片 0 的发布比有三处不同，已经写进下面的命令：`CRON_IMAGE` 这次一定要重建（`katrain/cron/` 改了）；这次有 DDL（katrain-web 启动时建三张新表），备份和实际恢复验证不能省；dry-run 和 `up -d` 带上三个服务。容器名 `katrain-ucloud-postgres-1` 和库名 `katrain_prod_20260725` 以切片 0 Task 5 Step 1 实际查到的为准。
```bash
SHA=<release 分支尖端的 short sha：Step 3 推送之后在本机执行 git -C "$REL" rev-parse --short HEAD>
sudo git clone --depth 1 --branch release/ucloud-20260805 https://github.com/shevapato2008/katrain.git /opt/katrain/releases/$SHA
sudo git -C /opt/katrain/releases/$SHA rev-parse --short HEAD          # 必须等于 $SHA
cd /opt/katrain/releases/$SHA
sudo deploy/ucloud/scripts/build-web.sh katrain-web:$SHA              # 记下输出的 image_id，下面叫 <WEB_ID>
sudo docker build --pull=false -f Dockerfile.cron -t katrain-cron:$SHA .
sudo docker image inspect --format '{{.Id}}' katrain-cron:$SHA         # 下面叫 <CRON_ID>
TS=$(date +%Y%m%d-%H%M)
sudo sh -c "docker exec katrain-ucloud-postgres-1 pg_dump -U katrain_user -Fc katrain_prod_20260725 > /opt/katrain/backups/prod-$TS.dump"
sudo docker exec katrain-ucloud-postgres-1 createdb -U katrain_user katrain_restore_verify_$TS
sudo sh -c "docker exec -i katrain-ucloud-postgres-1 pg_restore -U katrain_user -d katrain_restore_verify_$TS < /opt/katrain/backups/prod-$TS.dump"; echo "pg_restore exit=$?"
for t in $(sudo docker exec katrain-ucloud-postgres-1 psql -U katrain_user -d katrain_prod_20260725 -At -c "select tablename from pg_tables where schemaname='public' order by 1"); do
  a=$(sudo docker exec katrain-ucloud-postgres-1 psql -U katrain_user -d katrain_prod_20260725 -At -c "select count(*) from \"$t\"")
  b=$(sudo docker exec katrain-ucloud-postgres-1 psql -U katrain_user -d katrain_restore_verify_$TS -At -c "select count(*) from \"$t\"")
  [ "$a" = "$b" ] || echo "MISMATCH $t $a $b"
done; echo "row-count compare done"
sudo docker exec katrain-ucloud-postgres-1 dropdb -U katrain_user katrain_restore_verify_$TS
sudo cp /etc/katrain/ucloud.env /opt/katrain/backups/ucloud.env.$(date +%Y%m%dT%H%M%S).bak
sudo sed -i "s|^WEB_IMAGE=.*|WEB_IMAGE=<WEB_ID>|; s|^CRON_IMAGE=.*|CRON_IMAGE=<CRON_ID>|" /etc/katrain/ucloud.env
sudo stat -c '%U:%G %a' /etc/katrain/ucloud.env                                               # 必须是 root:root 600
sudo deploy/ucloud/scripts/preflight.sh --phase full --env-file /etc/katrain/ucloud.env       # 只有容量闸红属于历次都有的已知情况，要明说
sudo ln -sfn /opt/katrain/releases/$SHA /opt/katrain/current
cd /opt/katrain/current
sudo docker compose --env-file /etc/katrain/ucloud.env -f deploy/ucloud/compose.yml -f deploy/ucloud/compose.production.yml --profile production up -d --dry-run katrain-web katrain-cron katrain-admin
sudo docker compose --env-file /etc/katrain/ucloud.env -f deploy/ucloud/compose.yml -f deploy/ucloud/compose.production.yml --profile production up -d katrain-web katrain-cron katrain-admin
```
Expected：
- `pg_restore exit=0`，而且没有任何 `MISMATCH` 行；
- dry-run 的输出里只重建 `katrain-web`、`katrain-cron`、`katrain-admin`，外加一次性的 `minio-setup`；`katago-*` 和 `postgres` 只出现 `Waiting` / `Healthy`；
- `up -d` 之后 katrain-web、katrain-admin 转为 healthy，katrain-cron 为 Up。
- [ ] **Step 5：验证生产**：
```bash
ssh ucloud-v100 "sudo ss -ltnp | grep ':8010 '"                                      # 只有 127.0.0.1:8010
curl -s -o /dev/null -w '%{http_code}\n' https://modelstella.com/api/admin/health     # 404
ssh ucloud-v100 "sudo docker exec katrain-ucloud-postgres-1 psql -U katrain_user -d katrain_prod_20260725 -At -c 'SELECT count(*) FROM cron_job_status;'"   # 9
```
然后开隧道 `ssh -N -L 8011:127.0.0.1:8010 ucloud-v100`，打开 http://localhost:8011：页头显示「生产环境」，Fan 用管理员账号登录，能看到 9 个任务的真实状态。
- [ ] **Step 6：在 runbook 里补一条发布记录**，格式照 2026-09-06 那条。其中要写明：新服务 katrain-admin 只绑 127.0.0.1；新增三张表；发布前后的探针表。提交并推送 release 分支（🛑 Fan 点头）。删临时 worktree 之前，先执行 `git -C "$REL" status --ignored`。

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
  - `create_admin_app`、`check_startup`、`require_admin`、`require_csrf_header`、`cookie_name`、`create_session_token`、`RunRecorder.run`、`register`、`heartbeat`、`heartbeat_forever`、`enter_loop`、`exit_loop`、`loop_started`、`record_loop_crash`、`derive_health`、`as_utc`，在定义它们的任务和使用它们的任务里写法一致；
  - loop 任务的 `last_iteration_at` 和 `heartbeat_stats()` 在 Task 7 的测试和 Task 8 的实现之间一致；
  - TS 类型与 pydantic 模型的字段一一对应（Task 2 的 types.ts 对 Task 10）。
- **2026-09-24 按 writing-plans 模板复核**：
  - 原来单独的「准备环境 + 记录基线」（旧 Task 0）和「契约定稿」（旧 Task 4）都不是能单独验收的交付物，按 Task Right-Sizing 并进用到它们的任务：`npm ci` 进 Task 1（截参考图要用 Playwright），Python 依赖和两份基线进 Task 2 的 Step 1，契约定稿成为 Task 3 的 Step 7–8。其后的任务依次前移一个编号。
  - 所有任务都有了 Interfaces。
  - 旧 Task 16 写的是「命令与切片 0 计划 Task 7 Step 4 完全相同，只有三处不同」，违反「不许写 Similar to Task N」，现在 Task 15 Step 4 写全了命令。
  - 参考图、实现截图、本机集成三处原来只有文字描述，补上了可以直接运行的 Playwright 脚本。fixture 的 `error` 态改成「第一次成功、之后 502」，这样才截得出设计稿里「错误条 + 页面数据停在」那一屏。
  - vitest 基线从「数通过数」改成按用例名字做差；停 vite 时只杀自己起的那个进程。
