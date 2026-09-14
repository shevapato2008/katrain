# 围棋 kiosk · 训练营(kiosk-go-tsumego)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让盒上训练营:屏幕做题不再被标定台挡住,屏上每句话与实际一致,换账号不串「上次」,并接通「只做错过的」。

**Architecture:** 九个任务,按依赖排序。T9 在路由层加一个按做题偏好决定是否套标定守卫的包装(照对弈 `PlayInputGuard` 的形状);N9 先改后端契约(盒上题库读取失败 ⇒ 503,复用 `RepositoryDispatcher._remote_only`),再改前端把 503 说成「连不上云端题库」;N10 把训练营三个指针改成 `:u<id>` 按人存;文案、实体右栏两个小任务;T1 用屏 13 的同一副骨架加一个错题页,并让做题屏认 `?set=wrong` 的快照序列;最后一个任务跑真浏览器承重闸、四图与两套构建,交 Fan 视觉确认。

**Tech Stack:** React 18 + TypeScript + Vite + react-router-dom 6.30、vitest + Testing Library、Playwright(e2e 与四图);FastAPI + httpx + pytest(asyncio_mode=auto)。

**Spec:** `superpowers/tracks/kiosk-go-tsumego/prd.md`(同目录)。本计划只覆盖 PRD §3 的「本轮做」条目:T9、N9(训练营)、N10(训练营)、N26③、N8(文案)、T4(文案)、T8(死键)、N12、T1。§4 的 D1 / D2 / D3 不进任务。

## Global Constraints

> **开工前先读 `prd.md` §6.0**：五条赛道的共享文件归属与合并顺序（尤其 `server.py` 终局落账只留一条入口）。与本 plan 冲突时以 §6.0 为准。

- 在 worktree `/Users/fan/Repositories/katrain-kiosk-go-tsumego`(分支 `feature/kiosk-go-tsumego`)里开发;**不 push、不合并 develop**,合并由 Fan 决定;**不在别的 worktree 里 checkout**(10 个 katrain worktree 共用一条 stash 栈,也不要 `git stash pop`)。
- 这个 worktree 起步时**没有 `.venv` 也没有 `node_modules`**:第一次先 `cd /Users/fan/Repositories/katrain-kiosk-go-tsumego && uv sync`,再 `cd katrain/web/ui && npm ci`。
- 改了共享领地(`src/components`、`src/hooks`、`src/api*`、`src/features`、`src/context`、`src/utils` 等)必须 `npm run build` 与 `npm run build:kiosk-2d` 都绿;kiosk 边界(`verify:kiosk-2d`)不许破。本计划只有 Task 3 动共享领地(`src/hooks/useTsumegoProblem.ts`)。
- 类型检查用 `cd katrain/web/ui && npx tsc -b`。`npx tsc --noEmit` 检查 0 个文件,**不算数**;`*.test.ts(x)` 不在 tsc 范围内,测试文件里的类型错误只有 vitest 跑到才会暴露。
- 盒上 token 恒为 null:任何「发不发请求 / 渲不渲染」的判别位用 `isAuthenticated` / `user`,**不用 `token`**。本计划按人存的 id 取 `useAuth().user?.id`。
- 新文案一律 `t('tsumego:<camelKey>', '中文默认')`;**不往 PO 里加 key**(补不补 PO 待 Fan 裁定)。新 key 不许与 cn PO 里已有 msgid 撞名(翻译表赢过默认值):每个任务写完跑 `grep -o 'msgid "tsumego:[^"]*"' /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/i18n/locales/cn/LC_MESSAGES/katrain.po`,本计划用到的新 key 一个都不应出现在输出里。
- Python 格式:`uv run black -l 120 <文件>`。后端测试:`cd /Users/fan/Repositories/katrain-kiosk-go-tsumego && uv run pytest <文件> -v`。前端单测:`cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui && npx vitest run <文件>`(测试在 `src/kiosk/__tests__/`)。
- **测试判据是基线 diff**:Task 1 Step 1 跑一遍全量,记录失败用例**名字集合**;之后每个任务收尾比名字集合(`comm -13`),不比条数。新出现的失败一律当作本任务造成的,不许按文件名判「看着不相关」。
- Playwright e2e(`playwright.config.ts`)打的是 `:8002` 上 `python -m katrain --ui web` 服务的**构建产物**:改源码后先 `npm run build` 再跑。四图(`playwright.visual.config.ts`)打 `:5173` 的 vite dev server。两份配置都是 `reuseExistingServer`:**跑之前先 `lsof -nP -iTCP:8002 -iTCP:5173 -sTCP:LISTEN`**,有进程就用 `lsof -p <pid> | grep cwd` 确认它的工作目录是本 worktree,否则会静默打到别的赛道的代码上;不是本 worktree 的就等它结束或换端口,不许杀别人的进程。
- `python -m katrain --ui web` 退出时会改写 `~/.katrain/config.json`:跑 e2e 前 `cp ~/.katrain/config.json /private/tmp/claude-501/katrain-config.bak`,跑完拷回。
- 视觉 / 布局改动走 CLAUDE.md 的四图对比与承重实测关卡(jsdom 不作布局证据);四图用 `npx playwright test --config=playwright.visual.config.ts <spec>` 只取本计划改到的屏;**视觉通过需 Fan 确认**。Canvas 屏(14)抖动地板约 4500 像素,判断前把同一屏连取两次、diff 两次的结果;只抖动没实质变化的屏 `git checkout HEAD -- <那一屏目录>` 还原,不提交。
- 改一把存储钥匙,grep 的不只是 `src/`,还有 `tests/*.spec.ts` 的 fixture:`grep -rn "<旧钥匙>" katrain/web/ui/src katrain/web/ui/tests`。
- **不改**这几个共享文件:`src/kiosk/utils/activeSession.ts`、`src/kiosk/components/vision/PlayInputGuard.tsx`、`src/kiosk/components/vision/PhysicalBoardGuard.tsx`、`src/kiosk/components/vision/GeometryCalibrationScreen.tsx`、`katrain/web/core/repository.py` 里的 `_remote_only` 本身。
- 每个任务一个提交,信息用 `fix(kiosk-tsumego): …` / `feat(kiosk-tsumego): …`,正文说清改了什么、为什么;结尾按执行会话给定的署名行。提交前 `git status --short` 确认只有本任务的文件(katrain 的 `.gitignore` 有 `log*`,新文件用 `git add <路径>` 后 `git diff --cached --stat` 确认真的进了暂存区)。
- 上板验证在 RK3562 上一次只跑一家的测试(2G 内存)。
- 文中行号一律按 `6f7dc629`。同一文件被前面的任务改过之后行号会漂 —— **以每一步给出的代码锚点(要替换的原文)为准**,行号只是帮你找。

## File Structure

| 文件 | 职责 | 任务 |
|---|---|---|
| `katrain/web/ui/src/kiosk/components/vision/TsumegoInputGuard.tsx`(新) | 做题路由外层:偏好开才套 `PhysicalBoardGuard` | 1 |
| `katrain/web/ui/src/kiosk/__tests__/TsumegoInputGuard.test.tsx`(新) | 守卫两态 | 1 |
| `katrain/web/ui/src/kiosk/KioskApp.tsx` | 做题路由换守卫;加错题页路由 | 1、7 |
| `katrain/web/core/repository.py` | 四个题库读取方法走 `_remote_only`;`get_all_problems` 不吞分类失败 | 2 |
| `katrain/web/api/v1/endpoints/tsumego.py` | 盒上分支把「连不上」翻成 503、云端 4xx 原样转回 | 2 |
| `tests/web_ui/test_tsumego_board_unavailable.py`(新) | 上面两件的契约 | 2 |
| `katrain/web/ui/src/hooks/useTsumegoProblem.ts` | 非 404 错误抛 `HTTP <status>` | 3 |
| `katrain/web/ui/src/kiosk/pages/tsumegoUnits.ts` | 503 判别与错误文案;三个按人存的指针;错题快照读写 | 3、4、7 |
| `katrain/web/ui/src/kiosk/pages/TsumegoPage.tsx` | 错误 / 空态文案;按人读指针;问候副标 | 3、4、5 |
| `katrain/web/ui/src/kiosk/pages/TsumegoUnitsPage.tsx` | 错误 / 空态;按人写分类;整级文案;错题卡接通 | 3、4、5、7 |
| `katrain/web/ui/src/kiosk/pages/TsumegoUnitListPage.tsx` | 错误 / 空态;按人写分类;整级文案;`set="wrong"` 错题页 | 3、4、5、7 |
| `katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx` | 实体开关认「几何本次开机确认过」;错误文案;按人写指针;退一手原因;删死键调用;`?set=wrong` | 1、3、4、5、6、8 |
| `katrain/web/ui/src/kiosk/pages/TsumegoCategoriesPage.tsx`、`TsumegoLevelPage.tsx` | 只改错误提示那一处 | 3 |
| `katrain/web/ui/src/kiosk/components/vision/BoardSetupGuide.tsx` | 删「开始答题」;文案走 `t()` | 6 |
| `katrain/web/ui/src/kiosk/components/tsumego/PhysicalStatePanel.tsx` | 拿除标签写棋盘坐标 | 6 |
| `katrain/web/ui/tests/kiosk-screen-11-training.fourup.spec.ts`、`tests/kiosk-shell-scroll.spec.ts` | fixture 钥匙跟着 N10 改 | 4 |
| `katrain/web/ui/tests/kiosk-screen-11-training.fourup.spec.ts`(标签带)、`kiosk-screen-12-units.fourup.spec.ts`、`kiosk-screen-13-problems.fourup.spec.ts` | 标签带文字跟着 N26③ / N8 / T1 改 | 9 |
| `katrain/web/ui/tests/kiosk-tsumego-wrong.spec.ts`(新) | 错题页承重闸(真滚轮;错题页一建好就当场量) | 7 |
| `katrain/web/ui/tests/kiosk-tsumego-wrong.fourup.spec.ts`(新) | 错题页 / 做题屏错题模式四图 | 9 |

---

### Task 1: T9 做题路由按偏好决定套不套标定守卫(含开工基线)

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/vision/TsumegoInputGuard.tsx`
- Create: `katrain/web/ui/src/kiosk/__tests__/TsumegoInputGuard.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx:36-37`(import)、`:132`(做题路由)
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx:91-92`(`physicalAvailable` 加「几何本次开机确认过」,见 Step 7)
- Test: `katrain/web/ui/src/kiosk/__tests__/TsumegoProblemPage.test.tsx`(加 `GeometryContext` mock 与两条用例,见 Step 7)

**Interfaces:**
- Consumes: `readPhysicalMode(): boolean`(`src/kiosk/pages/tsumegoUnits.ts:116`,默认 `false`);`PhysicalBoardGuard({ children, sub, requireRecognition? })`(不改);`PHYSICAL_MODE_KEY = 'kiosk_tsumego_physical'`;`useOptionalGeometry(): { status: GeometryStatus } | null`(`src/kiosk/context/GeometryContext.tsx`)
- Produces: `default export TsumegoInputGuard({ children }: { children: ReactNode })`

- [ ] **Step 1: 装环境并记录基线(整个计划只做这一次)**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego && uv sync
cd katrain/web/ui && npm ci
mkdir -p /private/tmp/claude-501/kiosk-go-tsumego
npx vitest run --reporter=json --outputFile=/private/tmp/claude-501/kiosk-go-tsumego/vitest-baseline.json || true
node -e "const r=require('/private/tmp/claude-501/kiosk-go-tsumego/vitest-baseline.json');for(const f of r.testResults)for(const a of f.assertionResults)if(a.status==='failed')console.log(f.name.replace(/.*\/src\//,'src/')+' :: '+a.fullName)" | sort > /private/tmp/claude-501/kiosk-go-tsumego/vitest-baseline-failed.txt
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego
CI=true uv run pytest tests/web_ui -q -rf 2>&1 | grep '^FAILED' | sed 's/ - .*//' | sort > /private/tmp/claude-501/kiosk-go-tsumego/pytest-baseline-failed.txt
git status --short katrain/config.json
wc -l /private/tmp/claude-501/kiosk-go-tsumego/*-baseline-failed.txt
```

Expected:两份失败名单写出来(可以非空 —— 那是基线,不是本计划造成的)。`git status --short katrain/config.json` 应无输出;若显示 `M`,是测试改写了仓里那份 config(已知坑),执行 `git checkout -- katrain/config.json` 还原后再往下。

之后每个任务收尾的比较命令(下文称「**基线比较**」):

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui
npx vitest run --reporter=json --outputFile=/private/tmp/claude-501/kiosk-go-tsumego/vitest-now.json || true
node -e "const r=require('/private/tmp/claude-501/kiosk-go-tsumego/vitest-now.json');for(const f of r.testResults)for(const a of f.assertionResults)if(a.status==='failed')console.log(f.name.replace(/.*\/src\//,'src/')+' :: '+a.fullName)" | sort > /private/tmp/claude-501/kiosk-go-tsumego/vitest-now-failed.txt
comm -13 /private/tmp/claude-501/kiosk-go-tsumego/vitest-baseline-failed.txt /private/tmp/claude-501/kiosk-go-tsumego/vitest-now-failed.txt
```

Expected:`comm -13` 无输出(没有新增失败)。本计划里**有意改名或删掉**的用例会从名单里消失,那只会出现在 `comm -23` 一侧,不算回归。

- [ ] **Step 2: 写失败的测试**

`katrain/web/ui/src/kiosk/__tests__/TsumegoInputGuard.test.tsx`:

```tsx
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import TsumegoInputGuard from '../components/vision/TsumegoInputGuard';
import { GeometryProvider } from '../context/GeometryContext';
import { GeometryAPI } from '../../api/geometryApi';
import { PHYSICAL_MODE_KEY, readPhysicalMode, writePhysicalMode } from '../pages/tsumegoUnits';

/**
 * 做题路由外面那一层(T9)。前置状态一律造成「几何没就绪、本次开机没确认过」——
 * 那正是盒子重启后的样子,也正是裸 `PhysicalBoardGuard` 会挡人的那一态。
 * 第一条先钉住「开着实体开关时挡得住」:造不出这个前置,第二条会因为守卫本来就放行而假绿。
 */

vi.mock('../../api/geometryApi', () => ({
  GeometryAPI: {
    status: vi.fn(), calibrate: vi.fn(), cancel: vi.fn(),
    confirmExisting: vi.fn(), lock: vi.fn(), layout: vi.fn(),
  },
}));

const NOT_CALIBRATED = {
  phase: 'required' as const, session_calibrated: false, last_valid: true,
  capabilities: { camera_ready: true, led_ready: true, geometry_ready: false },
};

const renderGuard = () => render(
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter>
      <GeometryProvider>
        <TsumegoInputGuard><div>做题内容</div></TsumegoInputGuard>
      </GeometryProvider>
    </MemoryRouter>
  </ThemeProvider>,
);

beforeEach(() => {
  localStorage.removeItem(PHYSICAL_MODE_KEY);
  vi.mocked(GeometryAPI.status).mockResolvedValue(NOT_CALIBRATED);
});

describe('TsumegoInputGuard', () => {
  it('打开过实体开关的人:没确认标定就先去标定台', async () => {
    writePhysicalMode(true);
    renderGuard();
    expect(await screen.findByTestId('calib-screen')).toBeInTheDocument();
    expect(screen.queryByText('做题内容')).not.toBeInTheDocument();
  });

  it('默认(实体开关关着)在屏幕上做题:不被标定挡住', async () => {
    expect(readPhysicalMode()).toBe(false);
    renderGuard();
    expect(await screen.findByText('做题内容')).toBeInTheDocument();
    expect(screen.queryByTestId('calib-screen')).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui && npx vitest run src/kiosk/__tests__/TsumegoInputGuard.test.tsx`
Expected: FAIL,`Failed to resolve import "../components/vision/TsumegoInputGuard"`

- [ ] **Step 4: 写守卫**

`katrain/web/ui/src/kiosk/components/vision/TsumegoInputGuard.tsx`:

```tsx
import { useState, type ReactNode } from 'react';
import PhysicalBoardGuard from './PhysicalBoardGuard';
import { readPhysicalMode } from '../../pages/tsumegoUnits';

/**
 * 做题路由外面那一层(T9)。形状照 `PlayInputGuard`(对弈,2026-08-23)。
 *
 * `PhysicalBoardGuard` 守的是「要用实体盘就得先标定」,它本身没错;错在它被**无条件**
 * 套在做题上 —— 做题的实体开关默认是**关**的(`tsumegoUnits.ts` 的 `readPhysicalMode`),
 * 只想在屏幕上做题的人,盒子一重启(几何恒为 required)就被整屏换成标定台,
 * 做题屏里专为这种情况写的「物理棋盘需先确认棋盘标定 / 去标定」也永远渲染不到。
 *
 * ⇒ 开关开着才走那道守卫。不要求识别就绪,和改之前一样。**不改 `PhysicalBoardGuard` 自己**:
 * 摆谱也用它,对弈那边包的是另一把偏好键。
 *
 * ⚠️ 偏好只在挂载时读一次(`useState` 的惰性初始化),不在每次渲染时读:
 * 渲染时读的话,人在做题屏里一拨开关、下一次上层重渲染时这里的子树就从「守卫包着」变成
 * 「直接渲染」,做题屏会被整个卸载重挂,这一题的计时和落子全没了。
 * 读一次够用:做题屏里要**打开**实体开关,要求识别就绪**且几何本次开机确认过**
 * (`TsumegoProblemPage` 的 `physicalAvailable`,放行条件照抄 `PhysicalBoardGuard`)。
 * 已知边角:同一次进入里先关掉开关、之后几何又失效,这一次仍会被标定台拦下 —— 按返回再进就好。
 */
const TsumegoInputGuard = ({ children }: { children: ReactNode }) => {
  const [onBoard] = useState(readPhysicalMode);
  return onBoard
    ? <PhysicalBoardGuard sub="实体做题要先让摄像头看清盘面">{children}</PhysicalBoardGuard>
    : <>{children}</>;
};

export default TsumegoInputGuard;
```

(`sub` 那句是从 `KioskApp.tsx:132` 原样搬过来的,不是新文案。)

- [ ] **Step 5: 跑测试确认通过**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui && npx vitest run src/kiosk/__tests__/TsumegoInputGuard.test.tsx`
Expected: PASS(2 passed)

- [ ] **Step 6: 接到路由上**

`katrain/web/ui/src/kiosk/KioskApp.tsx`,在 `import PlayInputGuard from './components/vision/PlayInputGuard';` 下面加一行:

```tsx
import TsumegoInputGuard from './components/vision/TsumegoInputGuard';
```

把 `:132` 这一行:

```tsx
          <Route path="tsumego/problem/:problemId" element={<PhysicalBoardGuard sub="实体做题要先让摄像头看清盘面"><TsumegoProblemPage /></PhysicalBoardGuard>} />
```

换成:

```tsx
          {/* ⚠️ 2026-09-14(T9):不再裸套 `PhysicalBoardGuard`。做题的实体开关默认关,
              屏幕做题的人不该被标定台挡住 —— 和对弈那四条换成 `PlayInputGuard` 是同一件事。
              **不要退回裸的 `PhysicalBoardGuard`。** */}
          <Route path="tsumego/problem/:problemId" element={<TsumegoInputGuard><TsumegoProblemPage /></TsumegoInputGuard>} />
```

`PhysicalBoardGuard` 的 import 保留(摆谱路由 `baipu/session/:source` 还在用)。

- [ ] **Step 7: 页内实体开关也要认「几何本次开机确认过」(T9 的另一半,先红后绿)**

为什么必须有这一步:守卫摘掉之后,「标定没确认」只剩页内那颗实体开关把关,而它今天只看 `visionStatus.recognitionReady`(`TsumegoProblemPage.tsx:92`)。`server.py` 启动时会把持久化的标定锁**直接推进识别 worker**(`Push a persisted geometry lock into the vision worker at startup` 那段,`app.state.vision.set_geometry(app.state.geometry)`)⇒ 盒子一重启 `recognition_ready` 就是真,而几何是 `required / session_calibrated=false`。不补这一步:屏幕做题的人进题后能直接把实体开关拨开,在一份本次开机没人确认过的标定上判对错、记进度;PRD 验收里那句「物理棋盘需先确认棋盘标定」也渲染不到(它只在 `!physicalAvailable` 时出现)。

(a) `src/kiosk/__tests__/TsumegoProblemPage.test.tsx`,在 `vi.mock('../hooks/useVisionSync', …)` 之前加:

```tsx
// 几何状态:默认 null(= 没有 GeometryProvider,页面不管几何,和改之前一样);单条用例按需造。
const { mockGeometry } = vi.hoisted(() => ({ mockGeometry: { value: null as null | { status: unknown } } }));
vi.mock('../context/GeometryContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../context/GeometryContext')>();
  return { ...actual, useOptionalGeometry: () => mockGeometry.value };
});
```

最外层 `beforeEach` 里 `mockVision.recognitionReady = false;` 下面加一行 `mockGeometry.value = null;`。

在 `it('实体棋盘开关:条件不够时按不动,而且右边写出为什么', …)` 之后追加:

```tsx
  it('服务重启后识别已就绪、几何本次开机没确认:实体开关按不动,提示去确认并给「去标定」(T9)', () => {
    mockVision.enabled = true;
    mockVision.recognitionReady = true;   // 启动时持久化的锁已经推进识别 worker
    hookReturn = { ...defaultHookReturn, boardSize: 19 };
    mockGeometry.value = {
      status: {
        phase: 'required', session_calibrated: false, last_valid: true,
        capabilities: { camera_ready: true, led_ready: true, geometry_ready: false },
      },
    };
    renderPage('p1');
    expect(screen.getByTestId('physical-mode-toggle')).toBeDisabled();
    expect(screen.getByTestId('puzzle-toggle-hint')).toHaveTextContent('物理棋盘需先确认棋盘标定');
    expect(screen.getByRole('button', { name: '去标定' })).toBeInTheDocument();
  });

  it('几何本次开机确认过了,实体开关才按得动', () => {
    mockVision.enabled = true;
    mockVision.recognitionReady = true;
    hookReturn = { ...defaultHookReturn, boardSize: 19 };
    mockGeometry.value = {
      status: {
        phase: 'ready', session_calibrated: true, last_valid: true,
        capabilities: { camera_ready: true, led_ready: true, geometry_ready: true },
      },
    };
    renderPage('p1');
    expect(screen.getByTestId('physical-mode-toggle')).not.toBeDisabled();
  });
```

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui && npx vitest run src/kiosk/__tests__/TsumegoProblemPage.test.tsx`
Expected: FAIL —— 第一条(开关没灰、提示为空、没有「去标定」);第二条现在就 PASS(守的是改完别把开关锁死)。

(b) `src/kiosk/pages/TsumegoProblemPage.tsx:91-92`,把

```tsx
  // recognition_ready = 相机+模型+几何全就绪；物理盘固定 19 路（PRD Q1：非 19 路题隐藏物理模式）
  const physicalAvailable = visionStatus.enabled && visionStatus.recognitionReady && boardSize === 19;
```

换成

```tsx
  // recognition_ready = 相机+模型+几何全就绪；物理盘固定 19 路（PRD Q1：非 19 路题隐藏物理模式）
  // ⚠️ 2026-09-14(T9):recognition_ready **不含「本次开机确认过」**。服务启动时持久化的标定锁
  // 直接推进识别 worker ⇒ 盒子一重启它就是真,而几何是 required / session_calibrated=false。
  // 做题路由不再无条件套 `PhysicalBoardGuard` 之后,这颗开关是唯一的关 ⇒ 放行条件照抄那道守卫。
  // 没有 GeometryProvider(单测)时不管几何,和改之前一样;`disabled` = 没有摄像头服务,也放行。
  const geoStatus = geometry?.status;
  const geometryConfirmed = !geoStatus || geoStatus.phase === 'disabled'
    || (geoStatus.phase === 'ready' && geoStatus.session_calibrated && geoStatus.capabilities.geometry_ready);
  const physicalAvailable =
    visionStatus.enabled && visionStatus.recognitionReady && geometryConfirmed && boardSize === 19;
```

(`geometry` 在 `:75` 已经由 `useOptionalGeometry()` 取到;`physicalHint` 那一串不用改 —— `!physicalAvailable` 之后它按 `geoPhase` 自己说「需先确认」/「已失效」并挂「去标定」。)

再跑一次同一条命令,Expected: PASS。

- [ ] **Step 8: 类型检查、路由相关测试、基线比较**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui
npx tsc -b
npx vitest run src/kiosk/__tests__/TsumegoInputGuard.test.tsx src/kiosk/__tests__/TsumegoProblemPage.test.tsx src/kiosk/__tests__/navigation.integration.test.tsx src/kiosk/__tests__/PhysicalBoardGuard.test.tsx
grep -n "PhysicalBoardGuard sub=\"实体做题" src/kiosk/KioskApp.tsx
```

Expected:tsc 无输出;四个文件全 PASS;`grep` 无输出(做题路由上不再有裸守卫)。然后跑 Step 1 的「基线比较」,`comm -13` 无输出。

- [ ] **Step 9: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego
git add katrain/web/ui/src/kiosk/components/vision/TsumegoInputGuard.tsx katrain/web/ui/src/kiosk/__tests__/TsumegoInputGuard.test.tsx katrain/web/ui/src/kiosk/KioskApp.tsx katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx katrain/web/ui/src/kiosk/__tests__/TsumegoProblemPage.test.tsx
git diff --cached --stat
git commit -m "fix(kiosk-tsumego): 做题页不再无条件套标定守卫 —— 实体开关关着的人盒子一重启就进不了题"
```

---

### Task 2: N9 后端 —— 盒上题库读取连不上云端时回 503,不回空列表

**Files:**
- Modify: `katrain/web/core/repository.py:23-24`(加常量)、`:98-106`(`RemoteTsumegoRepository.get_all_problems`)、`:189-227`(四个 `tsumego_get_*`)
- Modify: `katrain/web/api/v1/endpoints/tsumego.py:12-16`(import)、`:88` `def level_sort_key` 之前(加 `_board_read`)、`:103-106`、`:141`、`:194`、`:228`、`:269`
- Create: `tests/web_ui/test_tsumego_board_unavailable.py`

**Interfaces:**
- Consumes: `RepositoryDispatcher._remote_only(call, unavailable_detail)`(`repository.py:364`,**不改**:离线或 `_remote_client is None` ⇒ `RemoteServiceUnavailableError`;`httpx.TransportError` / 5xx ⇒ 同上;4xx ⇒ 原样抛 `httpx.HTTPStatusError`)
- Produces(契约,Task 3 依赖):盒上 `GET /api/v1/tsumego/levels`、`/levels/{level}/categories`、`/levels/{level}/problems`、`/levels/{level}/categories/{category}`、`/problems/{id}` —— 连不上云端 ⇒ **503**;云端回 4xx ⇒ **同一个状态码**;成功 ⇒ 原样。服务器模式(`app.state.repository_dispatcher` 不存在)一行不变。

- [ ] **Step 1: 写失败的测试**

`tests/web_ui/test_tsumego_board_unavailable.py`:

```python
"""Board-mode tsumego reads (N9): 盒上题库是在线直读的,连不上云端必须说出来。

改之前 `RepositoryDispatcher.tsumego_get_*` 在离线 / 连不上 / 云端回错时一律回 `[]` / `None`,
端点把它当真结果 ⇒ 训练营写「这台盒子上还没有题 · 题库随云端同步下来」,做题屏写「Problem not found」。
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from katrain.web.api.v1.endpoints import tsumego as tsumego_endpoints
from katrain.web.core.db import get_db
from katrain.web.core.repository import (
    RemoteServiceUnavailableError,
    RemoteTsumegoRepository,
    RepositoryDispatcher,
)

REMOTE_METHODS = ("get_levels", "get_all_problems", "get_problems", "get_problem")
CALLS = [
    ("tsumego_get_levels", ()),
    ("tsumego_get_all_problems", ("15k",)),
    ("tsumego_get_problems", ("15k", "capturing")),
    ("tsumego_get_problem", ("p1",)),
]


class _Connectivity:
    def __init__(self, online: bool):
        self.is_online = online


def _status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "http://cloud.test/api/v1/tsumego/levels")
    return httpx.HTTPStatusError(str(code), request=request, response=httpx.Response(code, request=request))


def _remote(side_effect=None, value=None):
    remote = MagicMock()
    for name in REMOTE_METHODS:
        setattr(remote, name, AsyncMock(side_effect=side_effect, return_value=value))
    return remote


def _dispatcher(online: bool, remote_tsumego) -> RepositoryDispatcher:
    # `remote_client` 必须传:`_remote_only` 把「没注入 remote_client」也当成不可用。生产 server.py 恒注入。
    return RepositoryDispatcher(
        connectivity_manager=_Connectivity(online),
        remote_tsumego=remote_tsumego,
        remote_kifu=MagicMock(),
        remote_user_games=MagicMock(),
        local_user_game_repo=MagicMock(),
        remote_client=MagicMock(),
    )


def _app(dispatcher: RepositoryDispatcher) -> FastAPI:
    app = FastAPI()
    app.include_router(tsumego_endpoints.router, prefix="/api/v1/tsumego")
    app.dependency_overrides[get_db] = lambda: None
    app.state.repository_dispatcher = dispatcher
    return app


# ── dispatcher ──


@pytest.mark.asyncio
@pytest.mark.parametrize("method,args", CALLS)
async def test_offline_raises_unavailable_and_never_calls_cloud(method, args):
    remote = _remote(value=[])
    with pytest.raises(RemoteServiceUnavailableError):
        await getattr(_dispatcher(False, remote), method)(*args)
    for name in REMOTE_METHODS:
        getattr(remote, name).assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("method,args", CALLS)
@pytest.mark.parametrize("error", [httpx.ConnectError("boom"), httpx.ReadTimeout("slow"), _status_error(503)])
async def test_transport_failure_or_cloud_5xx_raises_unavailable(method, args, error):
    with pytest.raises(RemoteServiceUnavailableError):
        await getattr(_dispatcher(True, _remote(side_effect=error)), method)(*args)


@pytest.mark.asyncio
@pytest.mark.parametrize("method,args", CALLS)
async def test_cloud_4xx_is_passed_through_not_swallowed(method, args):
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await getattr(_dispatcher(True, _remote(side_effect=_status_error(404))), method)(*args)
    assert exc_info.value.response.status_code == 404


@pytest.mark.asyncio
async def test_online_success_is_returned_as_is():
    levels = [{"level": "15k", "categories": {"capturing": 3}, "total": 3}]
    assert await _dispatcher(True, _remote(value=levels)).tsumego_get_levels() == levels


@pytest.mark.asyncio
async def test_all_problems_fails_whole_when_one_category_fails():
    """改之前 `gather(return_exceptions=True)` 静默丢掉失败的分类:列表缺一块,`total` 还是全量。"""
    client = MagicMock()
    client.get_levels = AsyncMock(
        return_value=[{"level": "15k", "categories": {"capturing": 2, "tesuji": 1}, "total": 3}]
    )

    async def get_problems(level, category, offset=0, limit=20):
        if category == "tesuji":
            raise httpx.ConnectError("boom")
        return [{"id": "c1", "category": "capturing", "hint": ""}, {"id": "c2", "category": "capturing", "hint": ""}]

    client.get_problems = AsyncMock(side_effect=get_problems)
    with pytest.raises(httpx.ConnectError):
        await RemoteTsumegoRepository(client).get_all_problems("15k")


# ── endpoints ──


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/tsumego/levels",
        "/api/v1/tsumego/levels/15k/categories",
        "/api/v1/tsumego/levels/15k/problems",
        "/api/v1/tsumego/levels/15k/categories/capturing",
        "/api/v1/tsumego/problems/p1",
    ],
)
async def test_every_board_read_endpoint_offline_is_503(path):
    app = _app(_dispatcher(False, _remote(value=[])))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)
    assert response.status_code == 503, response.text


@pytest.mark.asyncio
async def test_problem_endpoint_cloud_404_stays_404():
    app = _app(_dispatcher(True, _remote(side_effect=_status_error(404))))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/tsumego/problems/nope")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_levels_endpoint_online_returns_cloud_payload():
    levels = [{"level": "15k", "categories": {"capturing": 3}, "total": 3}]
    app = _app(_dispatcher(True, _remote(value=levels)))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/tsumego/levels")
    assert response.status_code == 200
    assert response.json() == levels
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-tsumego && uv run pytest tests/web_ui/test_tsumego_board_unavailable.py -v`
Expected: FAIL —— `test_offline_raises_unavailable…` 报 `DID NOT RAISE`(现在回 `[]`/`None`);`test_every_board_read_endpoint_offline_is_503` 拿到 200 / 404;`test_all_problems_fails_whole…` 报 `DID NOT RAISE`。`test_online_success_is_returned_as_is` 与 `test_levels_endpoint_online_returns_cloud_payload` 现在就是 PASS(它们守的是「改完别把成功路径改坏」)。

- [ ] **Step 3: 改 dispatcher 与 `get_all_problems`**

`katrain/web/core/repository.py`,在 `class RemoteServiceUnavailableError` 定义之后加:

```python
# 盒上题库读取在云端不可用时的说明。前端只认 503 这个状态码,这句只进日志与响应 detail。
TSUMEGO_UNAVAILABLE = "Remote tsumego service unavailable"
```

`RemoteTsumegoRepository.get_all_problems` 里,把

```python
        results = await asyncio.gather(
            *(fetch_category(cat, cnt) for cat, cnt in categories.items()),
            return_exceptions=True,
        )

        all_problems: List[Dict] = []
        for result in results:
            if isinstance(result, list):
                all_problems.extend(result)
```

换成

```python
        # 任一分类取失败就整体失败(N9)。吞掉它会返回一份缺块的列表,而 `total` 仍是全量 ——
        # 「全部题目」页照样画、照样翻页,缺的那一类没人看得出来。
        results = await asyncio.gather(*(fetch_category(cat, cnt) for cat, cnt in categories.items()))

        all_problems: List[Dict] = []
        for result in results:
            all_problems.extend(result)
```

把 `# ── Tsumego (online-only, offline = unavailable) ──` 那一行起、到 `tsumego_get_problem` 方法结束(`# ── Tsumego progress` 之前)整段换成:

```python
    # ── Tsumego (online-only) ──
    #
    # 盒上题库是**在线直读**的:盒子上不存题,也没有任何同步。所以连不上云端时**不许**回空列表 ——
    # 前端会把空列表说成「这台盒子上还没有题」、把 None → 404 说成「这道题不存在」(N9)。
    # 走 `_remote_only`:离线 / 传输失败 / 云端 5xx ⇒ RemoteServiceUnavailableError(端点翻成 503);
    # 云端 4xx 原样抛(端点转回同一个状态码)。

    async def tsumego_get_levels(self):
        return await self._remote_only(lambda: self.remote_tsumego.get_levels(), TSUMEGO_UNAVAILABLE)

    async def tsumego_get_all_problems(self, level, page=1, page_size=50):
        return await self._remote_only(
            lambda: self.remote_tsumego.get_all_problems(level, page, page_size), TSUMEGO_UNAVAILABLE
        )

    async def tsumego_get_problems(self, level, category, offset=0, limit=20):
        return await self._remote_only(
            lambda: self.remote_tsumego.get_problems(level, category, offset, limit), TSUMEGO_UNAVAILABLE
        )

    async def tsumego_get_problem(self, problem_id):
        return await self._remote_only(lambda: self.remote_tsumego.get_problem(problem_id), TSUMEGO_UNAVAILABLE)
```

- [ ] **Step 4: 改端点**

`katrain/web/api/v1/endpoints/tsumego.py`,在 `from katrain.web.core.models_db import …` 下面加:

```python
from katrain.web.core.repository import RemoteServiceUnavailableError
```

在 `def level_sort_key` 之前加:

```python
async def _board_read(call):
    """盒上题库读取(N9):连不上云端 ⇒ 503;云端自己回 4xx ⇒ 同一个状态码。**不许折成空列表或 404。**"""
    try:
        return await call()
    except RemoteServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        raise HTTPException(status_code=status, detail=f"Cloud tsumego service returned {status}") from exc
```

五处替换(都在 `if dispatcher is not None:` 分支里):

```python
    # Board mode: delegate to repository dispatcher (online → remote; cloud unreachable → 503, see _board_read)
    dispatcher = getattr(request.app.state, "repository_dispatcher", None)
    if dispatcher is not None:
        return await _board_read(dispatcher.tsumego_get_levels)
```

```python
        levels = await _board_read(dispatcher.tsumego_get_levels)
```

```python
        return await _board_read(lambda: dispatcher.tsumego_get_all_problems(level, page, page_size))
```

```python
        return await _board_read(lambda: dispatcher.tsumego_get_problems(level, category, offset, limit))
```

```python
        result = await _board_read(lambda: dispatcher.tsumego_get_problem(problem_id))
```

(第一处替换的是 `get_levels` 里原来的注释 + 三行;其余四处各替换一行 `await dispatcher.tsumego_get_…(…)`。`get_problem` 后面那句 `if not result: raise HTTPException(404…)` 保留。)

- [ ] **Step 5: 跑测试确认通过,并跑相邻测试**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego
uv run black -l 120 katrain/web/core/repository.py katrain/web/api/v1/endpoints/tsumego.py tests/web_ui/test_tsumego_board_unavailable.py
uv run pytest tests/web_ui/test_tsumego_board_unavailable.py tests/web_ui/test_tsumego_offline.py tests/web_ui/test_board_report_proxy.py -v
grep -n "return \[\]\|return None" katrain/web/core/repository.py | sed -n 1,20p
```

Expected:三个文件全 PASS;`grep` 的输出里不再有落在 `tsumego_get_*` 四个方法里的行(kifu 那几行属于棋谱赛道,保留)。

- [ ] **Step 6: 后端基线比较**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego
CI=true uv run pytest tests/web_ui -q -rf 2>&1 | grep '^FAILED' | sed 's/ - .*//' | sort > /private/tmp/claude-501/kiosk-go-tsumego/pytest-now-failed.txt
comm -13 /private/tmp/claude-501/kiosk-go-tsumego/pytest-baseline-failed.txt /private/tmp/claude-501/kiosk-go-tsumego/pytest-now-failed.txt
git status --short katrain/config.json
```

Expected:`comm -13` 无输出;`katrain/config.json` 无改动(有就 `git checkout -- katrain/config.json`)。

- [ ] **Step 7: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego
git add katrain/web/core/repository.py katrain/web/api/v1/endpoints/tsumego.py tests/web_ui/test_tsumego_board_unavailable.py
git diff --cached --stat
git commit -m "fix(tsumego): 盒上题库连不上云端时回 503 —— 不再折成空列表让训练营说「还没有题」"
```

---

### Task 3: N9 前端 —— 503 说成「连不上云端题库」,空态不再说「随云端同步」

**Files:**
- Modify: `katrain/web/ui/src/hooks/useTsumegoProblem.ts:283`(**共享领地**,galaxy 也用)
- Modify: `katrain/web/ui/src/kiosk/pages/tsumegoUnits.ts`(文件末尾加两个导出)
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoPage.tsx:100-115`、`TsumegoUnitsPage.tsx:99-121`、`TsumegoUnitListPage.tsx:135-157`、`TsumegoProblemPage.tsx:378-401`、`TsumegoCategoriesPage.tsx:106`、`TsumegoLevelPage.tsx:77`
- Test: `src/hooks/useTsumegoProblem.test.ts`、`src/kiosk/__tests__/TsumegoPage.test.tsx`、`TsumegoUnitListPage.test.tsx`、`TsumegoProblemPage.test.tsx`、`TsumegoLevelPage.test.tsx`

**Interfaces:**
- Consumes: Task 2 的契约 —— 盒上连不上云端 ⇒ 503。各页 fetch 失败时抛的都是 `new Error(\`HTTP ${res.status}\`)`(做题屏经 hook,Step 3 改成同一格式)。
- Produces:
  - `isCloudUnreachable(error: string | null | undefined): boolean` —— `error === 'HTTP 503'`
  - `loadErrorCopy(t: (key: string, defaultText?: string) => string, error: string): { title: string; body: string }` —— 503 ⇒ `{ '连不上云端题库', '题库在云端，盒子上不存题。等网络或云端恢复后再点重试。' }`;其它 ⇒ `{ '题库读不到', error }`

- [ ] **Step 1: 写失败的测试**

`src/hooks/useTsumegoProblem.test.ts` 文件末尾追加:

```ts
describe('load errors', () => {
  it('只有 404 说「Problem not found」;其它状态码原样带上 —— 503 不许被说成题不存在', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503, json: async () => ({}) })));
    const unavailable = renderHook(() => useTsumegoProblem('p1'));
    await waitFor(() => expect(unavailable.result.current.error).toBe('HTTP 503'));

    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 404, json: async () => ({}) })));
    const missing = renderHook(() => useTsumegoProblem('p2'));
    await waitFor(() => expect(missing.result.current.error).toBe('Problem not found'));
  });
});
```

`src/kiosk/__tests__/TsumegoPage.test.tsx`:把 `it('题库是空的时候说的是「还没同步」,不是「读不到」', …)` 整条换成下面两条:

```tsx
  it('题库真是空的时候说「还没有题」,不说「随云端同步下来」—— 盒上题库是在线直读的,没有同步', async () => {
    (global.fetch as any).mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
    renderPage();
    await waitFor(() => expect(screen.getByTestId('tsumego-empty')).toBeInTheDocument());
    expect(screen.getByText('题库里还没有题')).toBeInTheDocument();
    expect(screen.queryByText(/随云端同步/)).toBeNull();
    expect(screen.queryByTestId('tsumego-error')).toBeNull();
  });

  it('连不上云端(503)时说「连不上云端题库」,不说「没有题」,重试键还在', async () => {
    (global.fetch as any).mockResolvedValueOnce({ ok: false, status: 503, json: () => Promise.resolve({}) });
    renderPage();
    const box = await screen.findByTestId('tsumego-error');
    expect(within(box).getByText('连不上云端题库')).toBeInTheDocument();
    expect(within(box).getByText('题库在云端，盒子上不存题。等网络或云端恢复后再点重试。')).toBeInTheDocument();
    expect(within(box).getByRole('button', { name: '重试' })).toBeInTheDocument();
    expect(screen.queryByTestId('tsumego-empty')).toBeNull();
  });
```

(原来那条 `HTTP 500` 的「读不到时写出原因」保留不动 —— 它守的是「不许把所有错误都说成没网」。)

`src/kiosk/__tests__/TsumegoUnitListPage.test.tsx`,在 `it('这一类真的一道题都没有时,说的是「还没有题」', …)` 里 `expect(screen.queryByTestId('problems-error')).toBeNull();` 之后加一行:

```tsx
    expect(screen.queryByText(/随云端同步/)).toBeNull();
```

并在同一 `describe` 末尾追加:

```tsx
  it('连不上云端(503)时说「连不上云端题库」,不把状态码甩给人看', async () => {
    (global.fetch as any).mockResolvedValueOnce({ ok: false, status: 503, json: () => Promise.resolve({}) });
    renderPage();
    const box = await screen.findByTestId('problems-error');
    expect(within(box).getByText('连不上云端题库')).toBeInTheDocument();
    expect(within(box).queryByText(/HTTP 503/)).toBeNull();
    expect(within(box).getByRole('button', { name: '重试' })).toBeInTheDocument();
  });
```

`src/kiosk/__tests__/TsumegoProblemPage.test.tsx`,在 `describe('读题的三态', …)` 里 `it('读不到时写出原因', …)` 之后追加:

```tsx
    it('连不上云端(HTTP 503)时说「连不上云端题库」,不说「这道题读不到」', () => {
      hookReturn = { ...defaultHookReturn, error: 'HTTP 503' };
      renderPage();
      const box = screen.getByTestId('puzzle-error');
      expect(box).toHaveTextContent('连不上云端题库');
      expect(box).not.toHaveTextContent('这道题读不到');
    });
```

`src/kiosk/__tests__/TsumegoLevelPage.test.tsx`,在 `it('shows error on fetch failure', …)` 之后追加:

```tsx
  it('shows the cloud-unreachable copy on 503', async () => {
    (global.fetch as any).mockResolvedValueOnce({ ok: false, status: 503, json: () => Promise.resolve({}) });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/连不上云端题库/)).toBeInTheDocument();
    });
  });
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui && npx vitest run src/hooks/useTsumegoProblem.test.ts src/kiosk/__tests__/TsumegoPage.test.tsx src/kiosk/__tests__/TsumegoUnitListPage.test.tsx src/kiosk/__tests__/TsumegoProblemPage.test.tsx src/kiosk/__tests__/TsumegoLevelPage.test.tsx`
Expected: FAIL —— 新加 / 改过的 7 条失败(hook 1 条拿到 `Problem not found` 而不是 `HTTP 503`;`TsumegoPage` 2 条、`TsumegoUnitListPage` 2 条、做题屏 1 条、全部题目页 1 条找不到「连不上云端题库」/「题库里还没有题」,或空态里仍有「随云端同步」)。其余原有用例 PASS。

- [ ] **Step 3: 改 hook 的错误格式**

`src/hooks/useTsumegoProblem.ts:283`,把

```ts
        if (!res.ok) throw new Error('Problem not found');
```

换成

```ts
        // 只有 404 才是「题不存在」。盒上连不上云端是 503(N9)—— 一律说成 not found 等于
        // 把「没网」讲成「没这道题」。其它状态码照各页 fetch 的惯例抛 `HTTP <status>`。
        if (!res.ok) throw new Error(res.status === 404 ? 'Problem not found' : `HTTP ${res.status}`);
```

- [ ] **Step 4: 在 `tsumegoUnits.ts` 末尾加判别与文案**

```ts
/**
 * 盒上题库读取为什么失败(N9)。盒上题库是**在线直读**的(`core/repository.py` 的 `tsumego_*`
 * 走 `_remote_only`):盒子上不存题,也没有任何同步。连不上云端 / 云端 5xx ⇒ 后端回 503。
 * 各页 fetch 失败时抛的都是 `HTTP <status>`,所以判别就是这一个字面量。
 */
export const isCloudUnreachable = (error: string | null | undefined): boolean => error === 'HTTP 503';

/**
 * 错误块的两行字。503 说「连不上」并说清题在哪;其它错误照旧「读不到」+ 原因,
 * **不许把所有错误都说成没网** —— 404 / 500 各有各的原因。
 */
export function loadErrorCopy(
  t: (key: string, defaultText?: string) => string,
  error: string,
): { title: string; body: string } {
  return isCloudUnreachable(error)
    ? {
        title: t('tsumego:cloudUnreachable', '连不上云端题库'),
        body: t('tsumego:cloudUnreachableBody', '题库在云端，盒子上不存题。等网络或云端恢复后再点重试。'),
      }
    : { title: t('Problem set unavailable', '题库读不到'), body: error };
}
```

- [ ] **Step 5: 六个页面接上**

(1)`TsumegoPage.tsx`:import 行改为

```tsx
import { CATEGORY_META, categoryRank, levelChinese, loadErrorCopy, readLastCategory, readLastLevel } from './tsumegoUnits';
```

`:100-115` 的错误块与空态换成:

```tsx
        {error ? (
          <div className="empty" data-testid="tsumego-error">
            <h4>{loadErrorCopy(t, error).title}</h4>
            <p>{loadErrorCopy(t, error).body}</p>
            <button type="button" className="kiosk-btn kiosk-btn--pill pill" onClick={load}>
              {t('Retry', '重试')}
            </button>
          </div>
        ) : levels === null ? (
          <div className="empty" data-testid="tsumego-loading">
            <h4>{t('Loading problem set…', '正在读题库…')}</h4>
          </div>
        ) : (
          <div className="empty" data-testid="tsumego-empty">
            {/* 接口真回了空。**不说「随云端同步下来」**:盒上题库是在线直读的,没有同步这回事(N9)。 */}
            <h4>{t('tsumego:bankEmpty', '题库里还没有题')}</h4>
          </div>
        )}
```

(2)`TsumegoUnitsPage.tsx`:import 里加 `loadErrorCopy`;`:101-102` 两行换成

```tsx
              <h4>{loadErrorCopy(t, error).title}</h4>
              <p>{loadErrorCopy(t, error).body}</p>
```

并删掉 `:120` 那一行 `<p>{t('The problem set syncs down from the cloud.', …)}</p>`(`h4` 保留)。

(3)`TsumegoUnitListPage.tsx`:import 里加 `loadErrorCopy`;`:137-138` 两行换成同样两行;删掉 `:156` 那一行「随云端同步」的 `<p>`。

(4)`TsumegoProblemPage.tsx`:从 `./tsumegoUnits` 的 import 列表里加 `isCloudUnreachable, loadErrorCopy`;错误块里

```tsx
            <h4>{t('tsumego:problemLoadError', '这道题读不到')}</h4>
            <p>{error}</p>
```

换成

```tsx
            {/* 503 = 盒子连不上云端(N9),这时「这道题读不到」会被读成题坏了。 */}
            <h4>{isCloudUnreachable(error) ? loadErrorCopy(t, error).title : t('tsumego:problemLoadError', '这道题读不到')}</h4>
            <p>{loadErrorCopy(t, error).body}</p>
```

(5)`TsumegoCategoriesPage.tsx`:加 `import { loadErrorCopy } from './tsumegoUnits';`,`:106` 换成

```tsx
        <Alert severity="error">{`${loadErrorCopy(t, error).title} · ${loadErrorCopy(t, error).body}`}</Alert>
```

(6)`TsumegoLevelPage.tsx`:同 (5),改 `:77`。

- [ ] **Step 6: 跑测试确认通过,新 key 不撞 PO,两套构建**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui
npx vitest run src/hooks/useTsumegoProblem.test.ts src/kiosk/__tests__/TsumegoPage.test.tsx src/kiosk/__tests__/TsumegoUnitsPage.test.tsx src/kiosk/__tests__/TsumegoUnitListPage.test.tsx src/kiosk/__tests__/TsumegoProblemPage.test.tsx src/kiosk/__tests__/TsumegoLevelPage.test.tsx src/kiosk/__tests__/TsumegoCategoriesPage.test.tsx
grep -rn "'题库随云端同步" src/kiosk/pages/Tsumego*.tsx
grep -o 'msgid "tsumego:[^"]*"' ../../../katrain/i18n/locales/cn/LC_MESSAGES/katrain.po | grep -E 'cloudUnreachable|bankEmpty'
npx tsc -b && npm run build && npm run build:kiosk-2d
```

Expected:vitest 全 PASS;两个 `grep` 都无输出;tsc 无输出;两次 build 成功,`build:kiosk-2d` 末尾 `verify:kiosk-2d` 退出码 0。然后跑「基线比较」,`comm -13` 无输出。

- [ ] **Step 7: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego
git add katrain/web/ui/src/hooks/useTsumegoProblem.ts katrain/web/ui/src/hooks/useTsumegoProblem.test.ts katrain/web/ui/src/kiosk/pages/tsumegoUnits.ts katrain/web/ui/src/kiosk/pages/TsumegoPage.tsx katrain/web/ui/src/kiosk/pages/TsumegoUnitsPage.tsx katrain/web/ui/src/kiosk/pages/TsumegoUnitListPage.tsx katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx katrain/web/ui/src/kiosk/pages/TsumegoCategoriesPage.tsx katrain/web/ui/src/kiosk/pages/TsumegoLevelPage.tsx katrain/web/ui/src/kiosk/__tests__/TsumegoPage.test.tsx katrain/web/ui/src/kiosk/__tests__/TsumegoUnitListPage.test.tsx katrain/web/ui/src/kiosk/__tests__/TsumegoProblemPage.test.tsx katrain/web/ui/src/kiosk/__tests__/TsumegoLevelPage.test.tsx
git diff --cached --stat
git commit -m "fix(kiosk-tsumego): 断网时训练营说「连不上云端题库」—— 不再说「这台盒子上还没有题 · 随云端同步下来」"
```

---

### Task 4: N10 训练营「上次那一档 / 那一类」与「接着上次」按账号存

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/tsumegoUnits.ts:84-107`(上次档位)、`:133-157`(上次分类),并新增「接着上次」读写
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoPage.tsx:1-8`(import)、`:44-46`
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoUnitsPage.tsx:74-77`、`TsumegoUnitListPage.tsx:100-103`
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx:26`(import)、`:169-181`
- Test: `src/kiosk/__tests__/TsumegoPage.test.tsx`、`TsumegoUnitsPage.test.tsx`、`TsumegoUnitListPage.test.tsx`、`TsumegoProblemPage.test.tsx`
- Modify(fixture):`katrain/web/ui/tests/kiosk-screen-11-training.fourup.spec.ts:38-45`、`tests/kiosk-shell-scroll.spec.ts:154-159`

**Interfaces:**
- Consumes: `useAuth()`(`src/context/AuthContext.tsx:153`)的 `user?.id: number`;盒上 token=null 但 `user` 有值。
- Produces(Task 7 / 8 依赖):
  - `type TsumegoUserId = number | string | null | undefined`
  - `readLastLevel(userId: TsumegoUserId): string | null` / `writeLastLevel(userId: TsumegoUserId, level: string): void` —— 钥匙 `kiosk_tsumego_last_level:u<id>`
  - `readLastCategory(userId)` / `writeLastCategory(userId, category)` —— `kiosk_tsumego_last_category:u<id>`
  - `interface PracticeResume { label: string; route: string }`;`readPracticeResume(userId): PracticeResume | null` / `writePracticeResume(userId, r: PracticeResume): void` —— `kiosk_tsumego_resume:u<id>`
  - `userId` 为 `null/undefined` 时读回 `null`、写什么都不做。

- [ ] **Step 1: 写失败的测试**

四个页面测试文件,各在顶部 `vi.mock(...)` 那一组里加(路径相对 `src/kiosk/__tests__/`):

```tsx
// 训练营的「上次」三样按账号存(N10)。盒上 token 恒为 null、身份在 user 上 —— 这里照盒上的样子造。
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: { id: 7, username: '甲', rank: '5段', credits: 0 }, isAuthenticated: true, token: null }),
}));
```

`TsumegoPage.test.tsx`:
- 把文件里所有 `localStorage.setItem('kiosk_tsumego_last_level', …)` 改成 `localStorage.setItem('kiosk_tsumego_last_level:u7', …)`,`'kiosk_tsumego_last_category'` 改成 `'kiosk_tsumego_last_category:u7'`(`:77`、`:106`、`:107`、`:117` 四处)。
- 把 `it('有未完成的练习才出「接着上次」', …)` 里的 `localStorage.setItem('kiosk_active_practice', JSON.stringify({ kind: 'practice', label: …, route: …, ts: Date.now() }))` 换成:

```tsx
    localStorage.setItem(
      'kiosk_tsumego_resume:u7',
      JSON.stringify({ label: '15 级 · 吃子 · 第 1 题', route: '/kiosk/tsumego/problem/p12' })
    );
```

- 在同一 `describe` 末尾追加:

```tsx
  it('别人的「上次」不串过来:另一个账号存下的三样,这个账号一样都看不见', async () => {
    localStorage.setItem('kiosk_tsumego_last_level:u8', '14k');
    localStorage.setItem('kiosk_tsumego_last_category:u8', 'semeai');
    localStorage.setItem(
      'kiosk_tsumego_resume:u8',
      JSON.stringify({ label: '14 级 · 对杀 · 第 3 题', route: '/kiosk/tsumego/problem/x' })
    );
    // 2026-09-14 之前那几把不分人的旧钥匙:没有主人,不迁移、不再读。
    localStorage.setItem('kiosk_tsumego_last_level', '14k');
    localStorage.setItem('kiosk_active_practice', JSON.stringify({ kind: 'practice', label: '旧的', route: '/x', ts: 1 }));
    renderPage();
    // 作用域退回最弱那一档,而不是 u8 / 旧钥匙上的 14 级。
    await waitFor(() => expect(screen.getByText('15 级 · 3 类')).toBeInTheDocument());
    expect(screen.queryByTestId('tsumego-resume-card')).toBeNull();
    expect(document.querySelectorAll('.kiosk-card.is-current')).toHaveLength(0);
  });
```

`TsumegoUnitsPage.test.tsx:196` 与 `TsumegoUnitListPage.test.tsx:283`:把 `localStorage.getItem('kiosk_tsumego_last_category')` 改成 `localStorage.getItem('kiosk_tsumego_last_category:u7')`。

`TsumegoProblemPage.test.tsx`,在 `describe('TsumegoProblemPage · 屏 14 做题屏', …)` 末尾追加:

```tsx
  it('进一道题就把「上次」三样记在这个账号名下(N10)', () => {
    renderPage('p1');
    expect(localStorage.getItem('kiosk_tsumego_last_level:u7')).toBe('15k');
    expect(localStorage.getItem('kiosk_tsumego_last_category:u7')).toBe('手筋');
    expect(JSON.parse(localStorage.getItem('kiosk_tsumego_resume:u7')!)).toEqual({
      label: '15 级 · 手筋 · 第 2 题',
      route: '/kiosk/tsumego/problem/p1',
    });
    // 不分人的旧钥匙一个都不写。
    expect(localStorage.getItem('kiosk_tsumego_last_level')).toBeNull();
    expect(localStorage.getItem('kiosk_active_practice')).toBeNull();
  });
```

(`SEQUENCE = ['p0','p1','p2']`,`p1` 是第 2 题;测试里的 `category` 是 `'手筋'`,`t('tsumego:手筋', '手筋')` 回默认值。)

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui && npx vitest run src/kiosk/__tests__/TsumegoPage.test.tsx src/kiosk/__tests__/TsumegoUnitsPage.test.tsx src/kiosk/__tests__/TsumegoUnitListPage.test.tsx src/kiosk/__tests__/TsumegoProblemPage.test.tsx`
Expected: FAIL —— 读写还在旧钥匙上:`上次做的那一档决定分类的作用域` 找不到「14 级 · 2 类」;「接着上次」不出;`…:u7` 的 `getItem` 为 `null`;新加的「别人的上次不串过来」因为旧钥匙 `kiosk_tsumego_last_level=14k` 仍被读到而失败。

- [ ] **Step 3: 改 `tsumegoUnits.ts`**

把 `:84-107`(`LAST_LEVEL_KEY` 那段注释起、到 `writeLastLevel` 结束)换成:

```ts
/**
 * 训练营的三样「上次」—— 上次那一档、上次那一类、接着上次 —— **按账号存**(N10)。
 * 盒子是共用设备:不分人的话,乙登录会看到甲的「接着上次 · 15 级 · 吃子 · 第 3 题」。
 * 钥匙照做题进度那把的命名(`TsumegoProgressContext` 的 `tsumego_progress:u<id>`)。
 * 2026-09-14 之前那几把不分人的旧钥匙**不迁移、不再读**:它们没有主人。
 *
 * 实体开关 `kiosk_tsumego_physical` **不在这里,仍按盒存** —— 它说的是这台盒子那块盘接好没有,
 * 和谁登录无关。
 *
 * 这三样是**指针不是进度**(R2 / §3.5):不重新引入「每一档做完了多少」那个刻意没做的数。
 */
export type TsumegoUserId = number | string | null | undefined;

const scopedKey = (base: string, userId: TsumegoUserId): string | null =>
  userId === null || userId === undefined ? null : `${base}:u${userId}`;

function readScoped(base: string, userId: TsumegoUserId): string | null {
  const key = scopedKey(base, userId);
  if (!key) return null;
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeScoped(base: string, userId: TsumegoUserId, value: string): void {
  const key = scopedKey(base, userId);
  if (!key) return;
  try {
    localStorage.setItem(key, value);
  } catch {
    /* best-effort */
  }
}

export const LAST_LEVEL_KEY = 'kiosk_tsumego_last_level';

/** 这个账号上次进的那一档,没有就 `null`。 */
export function readLastLevel(userId: TsumegoUserId): string | null {
  return readScoped(LAST_LEVEL_KEY, userId);
}

export function writeLastLevel(userId: TsumegoUserId, level: string): void {
  writeScoped(LAST_LEVEL_KEY, userId, level);
}
```

把 `:133-157`(`LAST_CATEGORY_KEY` 那段注释起、到 `writeLastCategory` 结束)换成:

```ts
/**
 * 这个账号上次做的那一类(训练营「按分类」那一排的 `is-current`)。和上次那一档同一种东西:
 * **指针不是进度**,也按账号存 —— 见 `LAST_LEVEL_KEY` 上面那段。
 */
export const LAST_CATEGORY_KEY = 'kiosk_tsumego_last_category';

export function readLastCategory(userId: TsumegoUserId): string | null {
  return readScoped(LAST_CATEGORY_KEY, userId);
}

export function writeLastCategory(userId: TsumegoUserId, category: string): void {
  writeScoped(LAST_CATEGORY_KEY, userId, category);
}

/**
 * 训练营「接着上次」那一条。原来借 `utils/activeSession.ts` 的 `practice` 槽存,那把钥匙不分人;
 * 挪到这里按账号存。`activeSession.ts` 本身不动(对弈也用它),`practice` 槽从此没有消费者 —— 已登记。
 */
export const RESUME_KEY = 'kiosk_tsumego_resume';

export interface PracticeResume {
  /** 屏上那一行,如「15 级 · 吃子 · 第 3 题」。 */
  label: string;
  /** 点「继续」去哪儿,如 `/kiosk/tsumego/problem/1014`(错题模式带 `?set=wrong`)。 */
  route: string;
}

export function readPracticeResume(userId: TsumegoUserId): PracticeResume | null {
  const raw = readScoped(RESUME_KEY, userId);
  if (!raw) return null;
  try {
    const p = JSON.parse(raw) as Partial<PracticeResume> | null;
    return p && typeof p.label === 'string' && typeof p.route === 'string' ? { label: p.label, route: p.route } : null;
  } catch {
    return null;
  }
}

export function writePracticeResume(userId: TsumegoUserId, resume: PracticeResume): void {
  writeScoped(RESUME_KEY, userId, JSON.stringify({ label: resume.label, route: resume.route }));
}
```

- [ ] **Step 4: 四个页面接上账号 id**

(1)`TsumegoPage.tsx`:删掉 `import { readActiveSession } from '../utils/activeSession';`,加 `import { useAuth } from '../../context/AuthContext';`,并把 `./tsumegoUnits` 那行 import 补上 `readPracticeResume`。`:44-46` 换成:

```tsx
  const { user } = useAuth();
  const userId = user?.id;
  const resume = readPracticeResume(userId);
  const lastLevel = readLastLevel(userId);
  const lastCategory = readLastCategory(userId);
```

(`resumeBar` 里用的 `resume.label` / `resume.route` 两个字段名不变。)

(2)`TsumegoUnitsPage.tsx`:加 `import { useAuth } from '../../context/AuthContext';`;组件体开头(`const { unitProgress, progress } = useTsumegoProgress();` 下面)加 `const { user } = useAuth();`;`:74-77` 换成

```tsx
  // 进了这一类就记下来 —— 训练营那一排的 `is-current` 靠它。**指针不是进度**,按账号存(N10)。
  useEffect(() => {
    if (category) writeLastCategory(user?.id, category);
  }, [category, user?.id]);
```

(3)`TsumegoUnitListPage.tsx`:同 (2),改 `:100-103`(注释保留原句「深链直接进这一层时…」,末尾补「按账号存(N10)」)。

(4)`TsumegoProblemPage.tsx`:删掉 `import { writeActiveSession } from '../utils/activeSession';`;加 `import { useAuth } from '../../context/AuthContext';`;`./tsumegoUnits` 的 import 列表补上 `writePracticeResume`;组件体里 `const { progress } = useTsumegoProgress();` 下面加 `const { user } = useAuth();`;`:169-181`(`// Populate the hub 继续练习 card …` 那行注释起、到 `}, [problem, currentIndex]);` 止)换成:

```tsx
  // 训练营首页「接着上次」+ 两处高亮(B2.2/B2.4),每进一道题写一次 —— 按账号存(N10)。
  useEffect(() => {
    if (!problem) return;
    writeLastLevel(user?.id, problem.level);
    writeLastCategory(user?.id, problem.category);
    writePracticeResume(user?.id, {
      label: `${levelChinese(problem.level)} · ${t(`tsumego:${problem.category}`, problem.category)} · 第 ${currentIndex + 1} 题`,
      route: `/kiosk/tsumego/problem/${problem.id}`,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- snapshot label written once per problem; `t` intentionally excluded
  }, [problem, currentIndex, user?.id]);
```

- [ ] **Step 5: 真浏览器 fixture 的钥匙跟着改**

`tests/kiosk-screen-11-training.fourup.spec.ts:38-45` 换成(那一屏 `auth/me` 回 `id: 1`):

```ts
    // ⚠️ 钥匙**带 user id**(N10,2026-09-14):「上次」三样按账号存,`auth/me` 回 id=1 ⇒ `:u1`。
    localStorage.setItem('kiosk_tsumego_resume:u1', JSON.stringify({
      label: '15 级 · 吃子 · 第 1 题',
      route: '/kiosk/tsumego/problem/fourup-fixture',
    }));
    localStorage.setItem('kiosk_tsumego_last_level:u1', '15k');
    localStorage.setItem('kiosk_tsumego_last_category:u1', 'capturing');
```

`tests/kiosk-shell-scroll.spec.ts:154-159`(`bootTraining` 里;那段 `auth/me` 回 `id: 1`)换成:

```ts
    localStorage.setItem('kiosk_tsumego_last_level:u1', '15k');
    if (withResume) {
      localStorage.setItem('kiosk_tsumego_resume:u1', JSON.stringify({
        label: '15 级 · 吃子 · 第 1 题', route: '/kiosk/tsumego/problem/x',
      }));
    }
```

- [ ] **Step 6: 跑测试确认通过,并 grep 旧钥匙**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui
npx vitest run src/kiosk/__tests__/TsumegoPage.test.tsx src/kiosk/__tests__/TsumegoUnitsPage.test.tsx src/kiosk/__tests__/TsumegoUnitListPage.test.tsx src/kiosk/__tests__/TsumegoProblemPage.test.tsx src/kiosk/__tests__/navigation.integration.test.tsx
grep -rn "kiosk_active_practice\|readActiveSession('practice')\|writeActiveSession" src/kiosk/pages/Tsumego*.tsx tests/kiosk-screen-11-training.fourup.spec.ts tests/kiosk-shell-scroll.spec.ts
grep -rn "'kiosk_tsumego_last_level'\|'kiosk_tsumego_last_category'" src tests | grep -v "__tests__/TsumegoPage.test.tsx\|__tests__/TsumegoProblemPage.test.tsx"
npx tsc -b
```

Expected:vitest 全 PASS;第一个 `grep` 无输出;第二个 `grep` 只剩 `tsumegoUnits.ts` 里两个 `*_KEY` 常量定义那两行(排除的两个测试文件里,旧钥匙是**有意**出现的:一个预置旧钥匙断言它不再被读,一个断言它不再被写);tsc 无输出。然后跑「基线比较」,`comm -13` 无输出。

- [ ] **Step 7: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego
git add katrain/web/ui/src/kiosk/pages/tsumegoUnits.ts katrain/web/ui/src/kiosk/pages/TsumegoPage.tsx katrain/web/ui/src/kiosk/pages/TsumegoUnitsPage.tsx katrain/web/ui/src/kiosk/pages/TsumegoUnitListPage.tsx katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx katrain/web/ui/src/kiosk/__tests__/TsumegoPage.test.tsx katrain/web/ui/src/kiosk/__tests__/TsumegoUnitsPage.test.tsx katrain/web/ui/src/kiosk/__tests__/TsumegoUnitListPage.test.tsx katrain/web/ui/src/kiosk/__tests__/TsumegoProblemPage.test.tsx katrain/web/ui/tests/kiosk-screen-11-training.fourup.spec.ts katrain/web/ui/tests/kiosk-shell-scroll.spec.ts
git diff --cached --stat
git commit -m "fix(kiosk-tsumego): 训练营「上次」和「接着上次」按账号存 —— 盒子共用时乙不再看到甲的继续"
```

---

### Task 5: 三句屏上承诺改成真的 —— N26③ 问候副标、N8 整级文案、T4 退一手原因

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoPage.tsx:72`
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoUnitsPage.tsx:211`
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoUnitListPage.tsx:280`
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx:351-353`
- Test: `src/kiosk/__tests__/TsumegoPage.test.tsx:54-60`、`navigation.integration.test.tsx:89-93`、`TsumegoUnitsPage.test.tsx:187-192`、`TsumegoUnitListPage.test.tsx:222-228`、`TsumegoProblemPage.test.tsx:516-523`

**Interfaces:**
- Consumes: 无(纯文案)
- Produces: 新 key `tsumego:greetSub`、`tsumego:wholeLevelSub`、`tsumego:wholeLevelRow`、`tsumego:undoPhysicalReset`(均不在 PO 里,屏上显示中文默认值)

- [ ] **Step 1: 改测试断言(先红)**

`TsumegoPage.test.tsx`,`it('问候行和副标照稿子', …)` 整条换成:

```tsx
  it('问候行照稿子;副标说的是在哪儿做题都成立的那句,不说「题在实体盘上摆好」', async () => {
    renderPage();
    await waitFor(() => {
      expect(document.querySelector('.kiosk-greet b')?.textContent).toBe('今天练点什么');
    });
    // 实体做题开关默认关、无摄像头的盒子根本没有实体盘 —— 稿子那句只在一种情况下成立(N26③)。
    expect(screen.getByText('落子即判，走错当场退回')).toBeInTheDocument();
    expect(screen.queryByText(/实体盘上摆好/)).toBeNull();
  });
```

`navigation.integration.test.tsx:92`:把 `'题在实体盘上摆好，落子即判'` 换成 `'落子即判，走错当场退回'`。

`TsumegoUnitsPage.test.tsx`,`it('「整级一起做」进的是这一档的全部题', …)` 里 `await waitFor(…'3 段全部'…)` 之后加:

```tsx
    // 整级页是按分类排好的(N8),不许说「六类混在一起」。
    expect(screen.getByText('按分类排好，不分单元')).toBeInTheDocument();
    expect(screen.queryByText(/混在一起/)).toBeNull();
```

`TsumegoUnitListPage.test.tsx`,`it('「整级一起做」进这一档的全部题', …)` 里 `await waitFor(() => expect(cells()).toHaveLength(UNIT_SIZE));` 之后加:

```tsx
    expect(screen.getByText('这一级的全部题，按分类排好')).toBeInTheDocument();
    expect(screen.queryByText(/混在一起|认出这是哪一类/)).toBeNull();
```

`TsumegoProblemPage.test.tsx:516-523`,那条 `it('实体模式下「退一手」按不动,而且说得出为什么', …)` 的最后一行换成:

```tsx
      // 原来写「请直接把子拿掉，按灯光提示走」—— 状态机里没有这条流程,拿掉子机器毫无反应(T4)。
      expect(undoBtn).toHaveAttribute('title', '实体棋盘上退不了一手；想重来，按「重摆」');
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui && npx vitest run src/kiosk/__tests__/TsumegoPage.test.tsx src/kiosk/__tests__/navigation.integration.test.tsx src/kiosk/__tests__/TsumegoUnitsPage.test.tsx src/kiosk/__tests__/TsumegoUnitListPage.test.tsx src/kiosk/__tests__/TsumegoProblemPage.test.tsx`
Expected: FAIL —— 上面五处各一条,找不到新句 / `title` 仍是旧句。

- [ ] **Step 3: 改四句文案**

`TsumegoPage.tsx:72`:

```tsx
      {/* 稿子写「题在实体盘上摆好，落子即判」—— 实体做题开关默认关,无摄像头的盒子根本没有实体盘,
          那句只在一种情况下成立(N26③)。换成屏幕 / 实体盘 / 有无摄像头都成立的一句。 */}
      <span>{t('tsumego:greetSub', '落子即判，走错当场退回')}</span>
```

`TsumegoUnitsPage.tsx:211`:

```tsx
              // 全部题目页按分类再按题号排、卡上贴着分类、做题屏上/下一题只在本分类里走 ⇒
              // 不是「混在一起」(N8)。真混排待 Fan 拍板(prd.md §4 D2)。
              sub={t('tsumego:wholeLevelSub', '按分类排好，不分单元')}
```

`TsumegoUnitListPage.tsx:280`:

```tsx
                {/* 同屏 12 那张卡(N8):不是混排,不说「认出这是哪一类」。 */}
                <em>{t('tsumego:wholeLevelRow', '这一级的全部题，按分类排好')}</em>
```

`TsumegoProblemPage.tsx:351-353`:

```tsx
      // 实体模式下屏幕上按一下会让机器和盘对不上,所以灰着。**原因只许说做得到的事**:
      // 状态机里没有「用户主动收回一手」这条流程,拿掉子机器毫无反应(T4);
      // 「重摆」在实体模式下会重走清盘 → 摆题(`handleReset`),这句是真的。真流程待 Fan 拍板(prd.md §4 D1)。
      disabled: physicalEnabled,
      reason: t('tsumego:undoPhysicalReset', '实体棋盘上退不了一手；想重来，按「重摆」'),
```

- [ ] **Step 4: 跑测试确认通过,新 key 不撞 PO**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui
npx vitest run src/kiosk/__tests__/TsumegoPage.test.tsx src/kiosk/__tests__/navigation.integration.test.tsx src/kiosk/__tests__/TsumegoUnitsPage.test.tsx src/kiosk/__tests__/TsumegoUnitListPage.test.tsx src/kiosk/__tests__/TsumegoProblemPage.test.tsx
grep -rn --exclude-dir=__tests__ --exclude='*.test.ts' --exclude='*.test.tsx' -e "'六类混在一起" -e "'题在实体盘上摆好" -e "按灯光提示走'" src/kiosk
grep -o 'msgid "tsumego:[^"]*"' ../../../katrain/i18n/locales/cn/LC_MESSAGES/katrain.po | grep -E 'greetSub|wholeLevel|undoPhysicalReset'
npx tsc -b
```

Expected:vitest 全 PASS;两个 `grep` 都无输出(第一个只找 `t()` 里那三句**默认值字面量**(带引号),所以不会命中新写的注释;测试文件已排除 —— 测试里的 `queryByText(/混在一起/)` 是在断言它**不**出现);tsc 无输出。然后跑「基线比较」。

- [ ] **Step 5: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego
git add katrain/web/ui/src/kiosk/pages/TsumegoPage.tsx katrain/web/ui/src/kiosk/pages/TsumegoUnitsPage.tsx katrain/web/ui/src/kiosk/pages/TsumegoUnitListPage.tsx katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx katrain/web/ui/src/kiosk/__tests__/TsumegoPage.test.tsx katrain/web/ui/src/kiosk/__tests__/navigation.integration.test.tsx katrain/web/ui/src/kiosk/__tests__/TsumegoUnitsPage.test.tsx katrain/web/ui/src/kiosk/__tests__/TsumegoUnitListPage.test.tsx katrain/web/ui/src/kiosk/__tests__/TsumegoProblemPage.test.tsx
git diff --cached --stat
git commit -m "fix(kiosk-tsumego): 三句屏上承诺改成真的 —— 问候副标、整级「混在一起」、实体模式退一手的原因"
```

---

### Task 6: 实体做题右栏 —— T8 删掉永远按不动的「开始答题」,N12 拿除标签写棋盘坐标

**Files:**
- Modify: `katrain/web/ui/src/kiosk/components/vision/BoardSetupGuide.tsx`(整文件重写,96 行 → 约 75 行)
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx:516-525`(调用点去掉两个 prop)
- Modify: `katrain/web/ui/src/kiosk/components/tsumego/PhysicalStatePanel.tsx:10-16`(import)、`:73-75`(组件体开头)、`:126-136`(拿除标签)
- Test: `katrain/web/ui/src/kiosk/__tests__/tsumego-components.test.tsx:1-2`(import)、`:189-199`,文件末尾新增一个 `describe`

**Interfaces:**
- Consumes: `xyToCoord(x: number, y: number, size = 19): string`(`src/kiosk/shell/goBoard.ts:105`,`x`=列、`y`=从上往下数的行,返回 `"Q16"`);`interpolate(template, values)`(`src/kiosk/utils/interpolate.ts`);`useTranslation()`(`src/hooks/useTranslation.ts`)
- Produces: `BoardSetupGuideProps` 变为 `{ matched: number; total: number; missing: Array<[number, number]>; extra?: Array<[number, number, number]>; stage?: 'black' | 'white' | null; onSkip: () => void }`(**删掉** `isComplete`、`onStartProblem`);新 key `tsumego:setupStageBlack`、`tsumego:setupStageWhite`、`tsumego:setupMatched`、`tsumego:setupExtra`、`tsumego:setupSkip`、`tsumego:removeAt`

- [ ] **Step 1: 写失败的测试**

`tsumego-components.test.tsx` 第 2 行改为:

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
```

import 区(`:22` `import SuccessOverlay …` 下面)加:

```tsx
import BoardSetupGuide from '../components/vision/BoardSetupGuide';
```

`:189-199` 那条 `it('phase "removing" -> …', …)` 换成:

```tsx
  it('phase "removing" -> D 答错拿除, DeleteSweep icon, 蓝 LED label, 拿除标签写棋盘坐标', () => {
    // 识别网格是 [row(0=最上), col, color]。取一个行列不对称的点:行列颠倒会写成 D4,
    // 忘了「行号 1 在最下」会写成 Q4,照抄下标就是原来那个「拿除 (3,15)」(N12)。
    renderPanel('removing', { extra: [[3, 15, 1]] as [number, number, number][] });
    expect(screen.getByTestId('physical-state-panel')).toHaveAttribute('data-phase', 'removing');
    expect(screen.getByTestId('DeleteSweepIcon')).toBeInTheDocument();
    expect(screen.getByText('答错拿除')).toBeInTheDocument();
    expect(screen.getByText('蓝')).toBeInTheDocument();
    const chips = screen.getAllByTestId('removal-item');
    expect(chips).toHaveLength(1);
    expect(chips[0]).toHaveTextContent('拿除 Q16');
    expect(fetchSpy).not.toHaveBeenCalled();
  });
```

文件末尾追加:

```tsx
describe('BoardSetupGuide(实体做题 · 摆题中)', () => {
  const renderGuide = (onSkip = vi.fn()) =>
    render(
      <ThemeProvider theme={kioskTheme}>
        <BoardSetupGuide matched={3} total={7} missing={[]} extra={[[0, 0, 2]]} stage="white" onSkip={onSkip} />
      </ThemeProvider>,
    );

  it('没有「开始答题」—— 状态机摆好就自动进答题,那颗键在它可见的整个期间都按不动(T8)', () => {
    renderGuide();
    expect(screen.queryByText('开始答题')).toBeNull();
  });

  it('进度与多余子照常说,「跳过设置」按得动', () => {
    const onSkip = vi.fn();
    renderGuide(onSkip);
    expect(screen.getByText('请摆放白棋 · 已匹配 3/7 颗子')).toBeInTheDocument();
    expect(screen.getByText(/盘上有 1 颗多余\/错色棋子/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '跳过设置' }));
    expect(onSkip).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui && npx vitest run src/kiosk/__tests__/tsumego-components.test.tsx`
Expected: FAIL —— `removing` 那条拿到 `拿除 (3,15)`;「没有开始答题」那条找到了按钮;另一条因为 `isComplete` / `onStartProblem` 是必填 prop 在类型上不合,但 vitest 不做类型检查,运行时应 PASS(它守的是改完别坏)。

- [ ] **Step 3: 重写 `BoardSetupGuide.tsx`**

```tsx
import { Box, Button, LinearProgress, Typography } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';
import { interpolate } from '../../utils/interpolate';

interface BoardSetupGuideProps {
  matched: number;
  total: number;
  missing: Array<[number, number]>; // [row, col] positions
  extra?: Array<[number, number, number]>;
  stage?: 'black' | 'white' | null;
  onSkip: () => void;
}

/**
 * 实体做题「摆题中」那一段的引导。只有做题屏一个调用方(`TsumegoProblemPage`)。
 *
 * 2026-09-14(T8):**删掉「开始答题」键**。调用方写死 `isComplete={false}` 和空回调,
 * 而状态机一摆好就自动进答题(`physicalTsumegoMachine.ts` 的 `toReady`)、这块引导随之消失 ——
 * 那颗键在它可见的整个期间都按不动,右栏一直挂着一颗死键。
 * 「跳过设置」保留:它等于关掉实体模式,人在摆盘时想放弃,出口就该在眼前。
 *
 * 皮肤没换(仍是 7 月的 MUI):稿子没画实体摆题这一态,重画与上板走查一起做(prd.md §5)。
 */
const BoardSetupGuide = ({ matched, total, missing: _missing, extra = [], stage = null, onSkip }: BoardSetupGuideProps) => {
  const { t } = useTranslation();
  const progress = total > 0 ? (matched / total) * 100 : 0;
  const matchedText = interpolate(t('tsumego:setupMatched', '已匹配 {matched}/{total} 颗子'), { matched, total });
  const stageText =
    stage === 'black'
      ? t('tsumego:setupStageBlack', '请摆放黑棋')
      : stage === 'white'
        ? t('tsumego:setupStageWhite', '请摆放白棋')
        : null;

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 1.5,
        p: 2,
        bgcolor: 'background.paper',
        borderRadius: 2,
        border: '1px solid',
        borderColor: 'divider',
      }}
    >
      <Typography variant="body1" sx={{ fontWeight: 500 }}>
        {stageText ? `${stageText} · ${matchedText}` : matchedText}
      </Typography>
      {extra.length > 0 && (
        <Typography variant="body2" color="warning.main">
          {interpolate(
            t('tsumego:setupExtra', '盘上有 {n} 颗多余/错色棋子，请先取走（屏上红叉 ✕ 标注，实体棋盘白灯闪烁）'),
            { n: extra.length },
          )}
        </Typography>
      )}

      <LinearProgress variant="determinate" value={progress} sx={{ height: 8, borderRadius: 1 }} />

      <Box sx={{ display: 'flex', gap: 1.5, mt: 0.5 }}>
        <Button variant="outlined" size="medium" onClick={onSkip} sx={{ flex: 1 }}>
          {t('tsumego:setupSkip', '跳过设置')}
        </Button>
      </Box>
    </Box>
  );
};

export default BoardSetupGuide;
```

- [ ] **Step 4: 调用点去掉两个 prop**

`TsumegoProblemPage.tsx:516-525` 换成:

```tsx
                  <BoardSetupGuide
                    matched={physical.stageMatched}
                    total={physical.stageTotal}
                    missing={physical.missing}
                    extra={physical.extra}
                    stage={physical.stage}
                    onSkip={() => setPhysical(false)}
                  />
```

- [ ] **Step 5: 拿除标签写棋盘坐标**

`PhysicalStatePanel.tsx`,import 区(`import type { PhysicalTsumegoState, PhysicalPhase } …` 下面)加:

```tsx
import { useTranslation } from '../../../hooks/useTranslation';
import { interpolate } from '../../utils/interpolate';
import { xyToCoord } from '../../shell/goBoard';
```

组件体第一行(`:74` `const visual = phaseVisual(state.phase);` 之前,**必须在 `if (!visual) return null;` 之前**,hook 不许放在提前返回之后)加:

```tsx
  const { t } = useTranslation();
```

`:126-136` 的拿除块换成:

```tsx
      {state.phase === 'removing' && (state.extra ?? []).length > 0 && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
          {/* 标签写**棋盘坐标**(跳 I、行号 1 在最下),不写识别网格的 0 起下标 —— 蓝灯常被
              要拿的那颗子压住,这一排是主通道,「(3,15)」普通人对不上是哪颗(N12)。
              换算只许走 `shell/goBoard.ts` 那一份;实体盘固定 19 路。
              语音 `wrong_remove` 由状态机念(`physicalTsumegoMachine.ts`),这里不管。 */}
          {(state.extra ?? []).map(([row, col], i) => (
            <Chip
              key={`${row}-${col}-${i}`}
              data-testid="removal-item"
              size="small"
              label={interpolate(t('tsumego:removeAt', '拿除 {coord}'), { coord: xyToCoord(col, row, 19) })}
              sx={{ bgcolor: LED_HEX.remove, color: 'common.white' }}
            />
          ))}
        </Box>
      )}
```

- [ ] **Step 6: 跑测试确认通过,类型检查,新 key 不撞 PO**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui
npx vitest run src/kiosk/__tests__/tsumego-components.test.tsx src/kiosk/__tests__/TsumegoProblemPage.test.tsx
npx tsc -b
grep -rn "onStartProblem\|isComplete=" src/kiosk
grep -o 'msgid "tsumego:[^"]*"' ../../../katrain/i18n/locales/cn/LC_MESSAGES/katrain.po | grep -E 'setupStage|setupMatched|setupExtra|setupSkip|removeAt'
```

Expected:两个测试文件全 PASS;tsc 无输出(调用点不再传被删掉的 prop);两个 `grep` 都无输出。然后跑「基线比较」。

- [ ] **Step 7: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego
git add katrain/web/ui/src/kiosk/components/vision/BoardSetupGuide.tsx katrain/web/ui/src/kiosk/components/tsumego/PhysicalStatePanel.tsx katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx katrain/web/ui/src/kiosk/__tests__/tsumego-components.test.tsx
git diff --cached --stat
git commit -m "fix(kiosk-tsumego): 实体做题右栏 —— 删掉永远按不动的「开始答题」,拿除列表写棋盘坐标不写下标"
```

---

### Task 7: T1(上)「只做错过的」接通入口 + 错题页(屏 13 同一副骨架)

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/tsumegoUnits.ts`(`writeSequence` 之后加错题快照读写与口径函数)
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoUnitsPage.tsx:31-36`(文件头那段「为什么是灰的」)、`:142-143`(`wrongCount`)、`:215-221`(卡)
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoUnitListPage.tsx`(import 区 + 组件整段,见 Step 5)
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx:136`(在它前面加一条路由)
- Test: `src/kiosk/__tests__/TsumegoUnitsPage.test.tsx:174-185`、`TsumegoUnitListPage.test.tsx:230-243`,并在后者新增 `describe('错题页(T1)')`
- Create: `katrain/web/ui/tests/kiosk-tsumego-wrong.spec.ts`(错题页承重闸,e2e 配置;见 Step 7–9 —— **错题页一建好就当场量**,不攒到 Task 9 的取图关卡)

**Interfaces:**
- Consumes: Task 3 的 `loadErrorCopy`;Task 4 的 `writeLastCategory(userId, category)` 与 `useAuth`;Task 5 改好的整级文案 `tsumego:wholeLevelRow`
- Produces(Task 8 依赖):
  - `wrongSequenceKey(level: string, category: string): string` —— `kiosk_problems_<level>_<category>_wrong`
  - `readWrongSequence(level: string, category: string): string[] | null`(读不到 = `null`)
  - `writeWrongSequence(level: string, category: string, ids: string[]): void`
  - `isWrongEntry(entry: { attempts?: number; completed?: boolean } | undefined): boolean` —— `attempts > 0 && !completed`
  - 路由 `/kiosk/tsumego/:level/:category/wrong` → `<TsumegoUnitListPage set="wrong" />`;点格导航到 `/kiosk/tsumego/problem/<id>?set=wrong`

- [ ] **Step 1: 写失败的测试**

`TsumegoUnitsPage.test.tsx:174-185`,那条 `it('「只做错过的」按不动,但道数是真的 …', …)` 整条换成:

```tsx
  it('「只做错过的」有错题时按得动,进这一类的错题页;道数是真的(T1)', async () => {
    progressMap['q0'] = { completed: false, attempts: 2 };
    progressMap['q5'] = { completed: false, attempts: 1 };
    progressMap['q7'] = { completed: true, attempts: 3 };   // 做对了,不算错题
    progressMap['q9'] = { completed: false, attempts: 0 };  // 没试过,也不算
    renderPage();
    await waitFor(() => expect(screen.getByText('只做错过的')).toBeInTheDocument());
    const card = screen.getByText('只做错过的').closest('button') as HTMLButtonElement;
    expect(within(card).getByText('现在有 2 道')).toBeInTheDocument();
    expect(within(card).queryByText('还没接')).toBeNull();
    expect(card.disabled).toBe(false);
    fireEvent.click(card);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/15k/capturing/wrong');
  });

  it('一道错题都没有时「只做错过的」灰着 —— 没有可作用的对象,副标照写「现在有 0 道」', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('只做错过的')).toBeInTheDocument());
    const card = screen.getByText('只做错过的').closest('button') as HTMLButtonElement;
    expect(within(card).getByText('现在有 0 道')).toBeInTheDocument();
    expect(card.disabled).toBe(true);
  });
```

`TsumegoUnitListPage.test.tsx`:在 `renderPage` 定义下面加:

```tsx
/** 错题页。**两条路由都挂上**:顺带证明静态段 `wrong` 在 v6 的最佳匹配里赢过 `:unit`。 */
const renderWrong = (level = '15k', category = 'capturing') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[`/kiosk/tsumego/${level}/${category}/wrong`]}>
        <Routes>
          <Route path="/kiosk/tsumego/:level/:category/:unit" element={<TsumegoUnitListPage />} />
          <Route path="/kiosk/tsumego/:level/:category/wrong" element={<TsumegoUnitListPage set="wrong" />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );
```

`:230-243` 那条 `it('「只做错过的」按不动,数是整类的真数,而且点名了 scope', …)` 整条换成:

```tsx
  it('「只做错过的」:数是整类的真数、点名了 scope,「开始」进这一类的错题页(T1)', async () => {
    progressMap['q0'] = { completed: false, attempts: 2 };   // 错过,还没对
    progressMap['q7'] = { completed: true, attempts: 3 };    // 做对了 ⇒ 不算
    progressMap['q9'] = { completed: false, attempts: 0 };   // 没试过 ⇒ 不算
    progressMap['q40'] = { completed: false, attempts: 1 };  // 第 3 单元的 —— 整类都算
    seedSequence();
    renderPage();
    await waitFor(() => expect(cells()).toHaveLength(UNIT_SIZE));
    const row = screen.getByTestId('row-wrong');
    expect(within(row).getByText(/把这一类做错的重来一遍 · 现在有 2 道/)).toBeInTheDocument();
    expect(within(row).queryByText('还没接')).toBeNull();
    fireEvent.click(within(row).getByRole('button', { name: '开始' }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/15k/capturing/wrong');
  });

  it('一道错题都没有时错题那一行的「开始」灰着', async () => {
    seedSequence();
    renderPage();
    await waitFor(() => expect(cells()).toHaveLength(UNIT_SIZE));
    expect(within(screen.getByTestId('row-wrong')).getByRole('button', { name: '开始' })).toBeDisabled();
  });
```

同一文件最外层 `describe` 的末尾(最后一个 `it` 之后、`});` 之前)追加:

```tsx
  describe('错题页(T1)', () => {
    beforeEach(() => {
      progressMap['q3'] = { completed: false, attempts: 1 };
      progressMap['q7'] = { completed: true, attempts: 3 };    // 做对了 ⇒ 不在错题里
      progressMap['q9'] = { completed: false, attempts: 0 };   // 没试过 ⇒ 不在
      progressMap['q41'] = { completed: false, attempts: 2 };  // 第 3 单元的 —— 整类都算
      seedSequence();
    });

    it('页控条写「这一档 · 这一类 · 错题」;格子只有试过没做对的,格上是整类真题号', async () => {
      renderWrong();
      await waitFor(() => expect(cells()).toHaveLength(2));
      expect(screen.getByText(/15 级 · 吃子 · 错题/)).toBeInTheDocument();
      expect(cellText()).toEqual([['4', '1 次'], ['42', '2 次']]);
      expect(cells()[0].getAttribute('aria-label')).toBe('第 4 题，做错过，1 次');
      // 每一道都没做对,不许随便指一格当「下一道」。
      expect(document.querySelector('.qgrid button.now')).toBeNull();
    });

    it('数据条三格:现在有几道 / 平均尝试次数 / 这一类已做对', async () => {
      renderWrong();
      await waitFor(() => expect(cells()).toHaveLength(2));
      expect(screen.getByTestId('stat-wrong-count').textContent).toBe('2 道');
      expect(screen.getByTestId('stat-avg-tries').textContent).toBe('1.5');
      expect(screen.getByTestId('stat-solved-in-category').textContent).toBe('1 / 45');
    });

    it('点一格:先把这份题单存成快照,再带着 ?set=wrong 进做题屏', async () => {
      renderWrong();
      await waitFor(() => expect(cells()).toHaveLength(2));
      fireEvent.click(cells()[1]);
      expect(JSON.parse(sessionStorage.getItem('kiosk_problems_15k_capturing_wrong')!)).toEqual(['q3', 'q41']);
      expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/problem/q41?set=wrong');
    });

    it('换一批只剩「整级」—— 错题那一行指向自己,不画', async () => {
      renderWrong();
      await waitFor(() => expect(cells()).toHaveLength(2));
      expect(screen.queryByTestId('row-wrong')).toBeNull();
      expect(screen.getByText('15 级全部')).toBeInTheDocument();
    });

    it('这一类一道错题都没有时说清楚,并给回单元的路', async () => {
      for (const k of Object.keys(progressMap)) delete progressMap[k];
      renderWrong();
      await waitFor(() => expect(screen.getByTestId('problems-no-wrong')).toBeInTheDocument());
      fireEvent.click(within(screen.getByTestId('problems-no-wrong')).getByRole('button', { name: '单元' }));
      expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/15k/capturing');
    });
  });
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui && npx vitest run src/kiosk/__tests__/TsumegoUnitsPage.test.tsx src/kiosk/__tests__/TsumegoUnitListPage.test.tsx`
Expected: FAIL —— 卡仍 `disabled` 且挂「还没接」;行里没有「开始」键;`TsumegoUnitListPage` 不认 `set` prop,错题页渲染的是第 1 单元的 20 格。

- [ ] **Step 3: `tsumegoUnits.ts` 加错题快照与口径**

在 `writeSequence` 函数之后(`:45` 之后)插入:

```ts
/**
 * 「只做错过的」那份题单的**快照**(T1)。点错题页格子的**那一刻**写:
 * 做题途中做对一道,它不会从上/下一题的序列里消失;回到错题页时再按最新进度重算。
 * 形状和整类那条顺序表一样(`string[]`,整类顺序),钥匙多一个 `_wrong`。
 */
export const wrongSequenceKey = (level: string, category: string) => `${sequenceKey(level, category)}_wrong`;

/** 读快照。读不到返回 `null` —— 做题屏据此退回整类行为,不假装还在错题里。 */
export function readWrongSequence(level: string, category: string): string[] | null {
  try {
    const raw = sessionStorage.getItem(wrongSequenceKey(level, category));
    if (raw === null) return null;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === 'string') : null;
  } catch {
    return null;
  }
}

export function writeWrongSequence(level: string, category: string, ids: string[]): void {
  try {
    sessionStorage.setItem(wrongSequenceKey(level, category), JSON.stringify(ids));
  } catch {
    /* best-effort */
  }
}

/** 「做错过的」= 试过、还没做对。屏 12 的卡、屏 13 的行、错题页三处**同一个口径**,只许在这里写一次。 */
export const isWrongEntry = (entry: { attempts?: number; completed?: boolean } | undefined): boolean =>
  (entry?.attempts ?? 0) > 0 && !entry?.completed;
```

- [ ] **Step 4: 屏 12 的卡接通,路由加一条**

`TsumegoUnitsPage.tsx`:`./tsumegoUnits` 的 import 补上 `isWrongEntry`。

文件头 `:31-36`(「── 「只做错过的」为什么是灰的 ──」那一段,不含最后的 ` */`)换成:

```tsx
 * ── 「只做错过的」(T1,2026-09-14 接通)──────────────────────────────────
 * 「做错过的」= 试过、还没做对(`isWrongEntry`),整类口径。去处是错题页
 * `/kiosk/tsumego/:level/:category/wrong` —— 屏 13 同一副骨架,只换题从哪儿来(稿子原注)。
 * 做题屏的上/下一题认 `?set=wrong` 的快照,不动整类那条顺序表。
 * 0 道时灰(`disabled`,不是 `soon`:功能接好了,只是这会儿没有可作用的对象)。
```

`:142-143`(`// 做错过的 = 试过、但还没做对。这个数算得出来,去处没有 —— 见文件头。` 那行注释 + 下一行 `const wrongCount = …`)换成:

```tsx
  // 做错过的 = 试过、但还没做对。口径只在 `isWrongEntry` 写一次。
  const wrongCount = problemIds.filter((id) => isWrongEntry(progress[id])).length;
```

`:215-221` 那张卡换成:

```tsx
            <KioskCard
              title={t('Only the ones I got wrong', '只做错过的')}
              sub={interpolate(t('tsumego:wrong_now', '现在有 {n} 道'), { n: wrongCount })}
              icon="arrow-clockwise"
              disabled={wrongCount === 0}
              onClick={() => navigate(`/kiosk/tsumego/${level}/${category}/wrong`)}
            />
```

`KioskApp.tsx`,在 `<Route path="tsumego/:level/:category/:unit" element={<TsumegoUnitListPage />} />` **之前**加:

```tsx
          {/* 错题页(T1):屏 13 同一副骨架,题从「这一类里试过、还没做对的」来。
              静态段 `wrong` 在 v6 最佳匹配里本来就赢过 `:unit`,放在前面是给人读的。 */}
          <Route path="tsumego/:level/:category/wrong" element={<TsumegoUnitListPage set="wrong" />} />
```

- [ ] **Step 5: `TsumegoUnitListPage` 加 `set="wrong"` 一支**

import 区:`./tsumegoUnits` 那一组改成

```tsx
import {
  CATEGORY_META,
  UNIT_SIZE,
  isWrongEntry,
  levelChinese,
  loadErrorCopy,
  readSequence,
  writeLastCategory,
  writeSequence,
  writeWrongSequence,
} from './tsumegoUnits';
```

(`useAuth` 的 import 在 Task 4 已经加过。)

文件头注释末尾(` */` 之前)补一段:

```tsx
 *
 * ── 错题页(T1,2026-09-14)`set="wrong"` ─────────────────────────────────
 * 路由 `/kiosk/tsumego/:level/:category/wrong`。稿子这一屏「换一批」那组的原注是
 * 「同一副骨架，只换题从哪儿来」⇒ 不另起一屏,同一个组件换题源:
 *   · 格子 = 这一类里「试过、还没做对」的全部题(`isWrongEntry`),格上写**整类真题号**;
 *   · 数据条三格换成「现在有几道 / 平均尝试次数 / 这一类已做对」—— 「本单元已做对」恒 0、
 *     「平均用时」对没做对的题恒「—」,两格在这里没话可说;
 *   · 点格那一刻写快照(`writeWrongSequence`),做题屏靠 `?set=wrong` 只在快照里翻页;
 *   · 「换一批」只留整级那一行 —— 错题那一行指向自己。
 * 错题多于 20 道时这一屏**会滚**(屏 13 本来那一支断言的是「满编 20 格不滚」),
 * 能不能滚归 `tests/kiosk-tsumego-wrong.spec.ts` 那条真浏览器闸。
```

把 `const TsumegoUnitListPage = () => {` 起到文件末尾 `export default TsumegoUnitListPage;` 之前整段换成:

```tsx
const TsumegoUnitListPage = ({ set = 'unit' }: {
  /** `unit` = 第 N 单元那 20 道(屏 13 本来那一屏);`wrong` = 错题页(见文件头)。 */
  set?: 'unit' | 'wrong';
}) => {
  const { level, category, unit } = useParams<{ level: string; category: string; unit: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { progress } = useTsumegoProgress();
  const { user } = useAuth();
  const isWrongSet = set === 'wrong';

  const [allIds, setAllIds] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const unitNumber = Math.max(1, Number.parseInt(unit || '1', 10) || 1);
  const offset = (unitNumber - 1) * UNIT_SIZE;

  const load = useCallback((lvl: string, cat: string, signal: AbortSignal) => {
    setError(null);
    // 屏 12 刚写过这条顺序表 —— 常路到此为止,一次接口都不取。
    const cached = readSequence(lvl, cat);
    if (cached && cached.length > 0) {
      setAllIds(cached);
      return;
    }
    setAllIds(null);
    fetch(`/api/v1/tsumego/levels/${lvl}/categories/${cat}?limit=1000`, { signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: ProblemSummary[]) => {
        const ids = Array.isArray(data) ? data.map((p) => p.id) : [];
        setAllIds(ids);
        writeSequence(lvl, cat, ids);
      })
      .catch((err: Error) => {
        if (err.name !== 'AbortError') setError(err.message);
      });
  }, []);

  useEffect(() => {
    if (!level || !category) return;
    const controller = new AbortController();
    load(level, category, controller.signal);
    return () => controller.abort();
  }, [level, category, load]);

  // 深链直接进这一层时,训练营那一排的 `is-current` 也要跟上。**指针不是进度**,按账号存(N10)。
  useEffect(() => {
    if (category) writeLastCategory(user?.id, category);
  }, [category, user?.id]);

  const meta = category ? CATEGORY_META[category] : undefined;
  const categoryName = category ? t(`tsumego:${category}`, meta?.zh ?? category) : '';
  const levelName = level ? levelChinese(level) : '';
  const backToUnits = () => navigate(`/kiosk/tsumego/${level}/${category}`);

  const unitIds = allIds ? allIds.slice(offset, offset + UNIT_SIZE) : [];
  // 做错过的 = 试过、还没做对,整类口径(和屏 12 的卡同一个数)。错题页的格子就是它。
  const wrongIds = allIds ? allIds.filter((id) => isWrongEntry(progress[id])) : [];
  const listIds = isWrongSet ? wrongIds : unitIds;
  const judged = t('Judged on placement', '落子即判');

  const pagebar = (
    <KioskPagebar
      testId="problems-pagebar"
      title={
        isWrongSet
          ? `${levelName} · ${categoryName} · ${t('tsumego:wrongSet', '错题')}`
          : `${levelName} · ${categoryName} · ${interpolate(t('tsumego:unit_n', '第 {n} 单元'), { n: unitNumber })}`
      }
      // 题号范围 / 道数只在**真有**时写 —— 读不到 / 越界 / 0 道时写出来是在断言一件不知道的事。
      sub={
        listIds.length === 0
          ? undefined
          : isWrongSet
            ? `${interpolate(t('tsumego:wrong_now', '现在有 {n} 道'), { n: wrongIds.length })} · ${judged}`
            : `${interpolate(t('tsumego:problemRange', '第 {start}-{end} 题'), {
                start: offset + 1,
                end: offset + unitIds.length,
              })} · ${judged}`
      }
      backLabel={t('Units', '单元')}
      onBack={backToUnits}
    />
  );

  if (allIds === null || error || listIds.length === 0) {
    return (
      <div className="kiosk-layout-b">
        {pagebar}
        <KioskScrollZone>
          {error ? (
            <div className="empty" data-testid="problems-error">
              <h4>{loadErrorCopy(t, error).title}</h4>
              <p>{loadErrorCopy(t, error).body}</p>
              <button
                type="button"
                className="kiosk-btn kiosk-btn--pill pill"
                onClick={() => {
                  if (level && category) load(level, category, new AbortController().signal);
                }}
              >
                {t('Retry', '重试')}
              </button>
            </div>
          ) : allIds === null ? (
            <div className="empty" data-testid="problems-loading">
              <h4>{t('Loading problem set…', '正在读题库…')}</h4>
            </div>
          ) : allIds.length === 0 ? (
            <div className="empty" data-testid="problems-empty">
              <h4>{t('No problems in this category yet', '这一类下面还没有题')}</h4>
            </div>
          ) : isWrongSet ? (
            // 这一类里没有「试过、还没做对」的题。进度先读本地、再合并服务端,合并到了会自己重渲。
            <div className="empty" data-testid="problems-no-wrong">
              <h4>{t('tsumego:noWrong', '这一类现在没有做错过的题')}</h4>
              <button type="button" className="kiosk-btn kiosk-btn--pill pill" onClick={backToUnits}>
                {t('Units', '单元')}
              </button>
            </div>
          ) : (
            // 单元号越界(手打的地址 / 题库缩了)。**说清楚一共有几个单元**,别只说「没有」。
            <div className="empty" data-testid="problems-out-of-range">
              <h4>{t('No such unit', '没有这一单元')}</h4>
              <p>
                {interpolate(
                  t('tsumego:unit_range', '这一类一共 {total} 道题，只有 {units} 个单元。'),
                  { total: allIds.length, units: Math.ceil(allIds.length / UNIT_SIZE) },
                )}
              </p>
              <button type="button" className="kiosk-btn kiosk-btn--pill pill" onClick={backToUnits}>
                {t('Units', '单元')}
              </button>
            </div>
          )}
        </KioskScrollZone>
      </div>
    );
  }

  // 「试了几次」—— 见文件头:`attempts` 数的是**失败**的那几次,做对的那一次要自己加回来。
  const triesOf = (id: string) => {
    const e = progress[id];
    if (!e) return 0;
    return (e.attempts ?? 0) + (e.completed ? 1 : 0);
  };

  const solved = unitIds.filter((id) => progress[id]?.completed).length;
  const solvedInCategory = allIds.filter((id) => progress[id]?.completed).length;
  // 「下一道要做的」= 本单元第一个还没做对的。全做完了就没有;错题页每一道都没做对,也不指。
  const nowId = isWrongSet ? null : unitIds.find((id) => !progress[id]?.completed) ?? null;

  const triedList = listIds.map(triesOf).filter((n) => n > 0);
  const avgTries = triedList.length > 0 ? triedList.reduce((a, b) => a + b, 0) / triedList.length : null;

  const durations = unitIds
    .map((id) => progress[id]?.lastDuration)
    .filter((v): v is number => typeof v === 'number' && v > 0);
  const avgSeconds =
    durations.length > 0 ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length) : null;

  const openProblem = (id: string) => {
    if (!isWrongSet) {
      navigate(`/kiosk/tsumego/problem/${id}`);
      return;
    }
    // 快照在**点下去那一刻**写:做题途中做对一道,它不会从上/下一题里消失(T1)。
    if (level && category) writeWrongSequence(level, category, wrongIds);
    navigate(`/kiosk/tsumego/problem/${id}?set=wrong`);
  };

  return (
    <div className="kiosk-layout-b">
      {pagebar}
      <KioskScrollZone resetKey={`${level}/${category}/${isWrongSet ? 'wrong' : unitNumber}`}>
        <div className="kiosk-stats">
          {isWrongSet ? (
            <div className="kiosk-stat">
              <div className="kiosk-stat__v" data-testid="stat-wrong-count">
                {wrongIds.length}<small> {t('tsumego:dao', '道')}</small>
              </div>
              <div className="kiosk-stat__k">{t('tsumego:wrongStatLabel', '做错过、还没做对')}</div>
            </div>
          ) : (
            <div className="kiosk-stat">
              <div className="kiosk-stat__v">
                {solved}<small> / {unitIds.length}</small>
              </div>
              <div className="kiosk-stat__k">{t('Solved in this unit', '本单元已做对')}</div>
            </div>
          )}
          <div className="kiosk-stat">
            {/* 一道都没试过时写「—」:平均值没有被测对象,写 `0.0` 是在断言「平均试了 0 次」。 */}
            <div className="kiosk-stat__v" data-testid="stat-avg-tries">
              {avgTries == null ? '—' : avgTries.toFixed(1)}
            </div>
            <div className="kiosk-stat__k">{t('Average tries', '平均尝试次数')}</div>
          </div>
          {isWrongSet ? (
            <div className="kiosk-stat">
              <div className="kiosk-stat__v" data-testid="stat-solved-in-category">
                {solvedInCategory}<small> / {allIds.length}</small>
              </div>
              <div className="kiosk-stat__k">{t('tsumego:solvedInCategory', '这一类已做对')}</div>
            </div>
          ) : (
            <div className="kiosk-stat">
              <div className="kiosk-stat__v" data-testid="stat-avg-time">
                {avgSeconds == null ? (
                  '—'
                ) : avgSeconds < 60 ? (
                  <>{avgSeconds}<small> {t('sec', '秒')}</small></>
                ) : (
                  <>
                    {Math.floor(avgSeconds / 60)}<small> {t('min', '分')} </small>
                    {avgSeconds % 60}<small> {t('sec', '秒')}</small>
                  </>
                )}
              </div>
              <div className="kiosk-stat__k">{t('Average time', '平均用时')}</div>
            </div>
          )}
        </div>

        <section className="kiosk-section">
          <KioskSecLabel
            zh={interpolate(t('tsumego:these_n_problems', '这 {n} 道题'), { n: listIds.length })}
            en="Problems"
          />
          <div className="qgrid" data-testid="problems-grid">
            {listIds.map((id, i) => {
              const done = !!progress[id]?.completed;
              const isNow = !done && id === nowId;
              const tries = triesOf(id);
              const triesText = interpolate(t('tsumego:tries_n', '{n} 次'), { n: tries });
              const state = done
                ? t('Solved', '做对了')
                : isNow
                  ? t('Next up', '下一道')
                  : isWrongSet
                    ? t('tsumego:wrongState', '做错过')
                    : t('Not attempted', '还没做过');
              // 错题页写这道题在**这一类里的真题号**,不写它在错题里排第几 —— 做题屏、单元页说的都是这个号。
              const n = isWrongSet ? allIds.indexOf(id) + 1 : offset + i + 1;
              const problemNo = interpolate(t('tsumego:problem_no', '第 {n} 题'), { n });
              return (
                <button
                  type="button"
                  key={id}
                  className={done ? 'ok' : isNow ? 'now' : undefined}
                  aria-current={isNow ? 'step' : undefined}
                  aria-label={tries > 0 ? `${problemNo}，${state}，${triesText}` : `${problemNo}，${state}`}
                  onClick={() => openProblem(id)}
                >
                  <b>{n}</b>
                  {/* 试过就写试了几次;一次没试过的那一格,只有「下一道」那张有话可说。 */}
                  <em>{tries > 0 ? triesText : isNow ? t('You are here', '在这儿') : '—'}</em>
                </button>
              );
            })}
          </div>
        </section>

        <section className="kiosk-section">
          <KioskSecLabel zh={t('Other sets', '换一批')} en="Other sets" />
          <div className="kiosk-rows">
            <div className="kiosk-row">
              <span className="kiosk-row__lead">{t('Whole level', '整级')}</span>
              <div className="kiosk-row__t">
                <b>{`${levelName}${t('all', '全部')}`}</b>
                {/* 同屏 12 那张卡(N8):不是混排,不说「认出这是哪一类」。 */}
                <em>{t('tsumego:wholeLevelRow', '这一级的全部题，按分类排好')}</em>
              </div>
              <div className="kiosk-row__end">
                <button
                  type="button"
                  className="kiosk-btn kiosk-btn--pill"
                  onClick={() => navigate(`/kiosk/tsumego/${level}/all`)}
                >
                  {t('Start', '开始')}
                </button>
              </div>
            </div>
            {/* 错题页上不画这一行:它指向自己。 */}
            {!isWrongSet && (
              <div className="kiosk-row" data-testid="row-wrong">
                <span className="kiosk-row__lead">{t('Wrong', '错题')}</span>
                <div className="kiosk-row__t">
                  <b>{t('Only the ones I got wrong', '只做错过的')}</b>
                  <em>
                    {t('Redo the ones you got wrong in this category', '把这一类做错的重来一遍')}
                    {' · '}
                    {interpolate(t('tsumego:wrong_now', '现在有 {n} 道'), { n: wrongIds.length })}
                  </em>
                </div>
                <div className="kiosk-row__end">
                  {/* 0 道时灰:没有可作用的对象。有就进错题页(T1)。 */}
                  <button
                    type="button"
                    className="kiosk-btn kiosk-btn--pill"
                    disabled={wrongIds.length === 0}
                    onClick={() => navigate(`/kiosk/tsumego/${level}/${category}/wrong`)}
                  >
                    {t('Start', '开始')}
                  </button>
                </div>
              </div>
            )}
          </div>
        </section>
      </KioskScrollZone>
    </div>
  );
};
```

- [ ] **Step 6: 跑测试确认通过,类型检查,新 key 不撞 PO**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui
npx vitest run src/kiosk/__tests__/TsumegoUnitsPage.test.tsx src/kiosk/__tests__/TsumegoUnitListPage.test.tsx src/kiosk/__tests__/navigation.integration.test.tsx
npx tsc -b
grep -rn "还没接" src/kiosk/pages/TsumegoUnitsPage.tsx src/kiosk/pages/TsumegoUnitListPage.tsx
grep -o 'msgid "tsumego:[^"]*"' ../../../katrain/i18n/locales/cn/LC_MESSAGES/katrain.po | grep -E 'wrongSet|noWrong|"tsumego:dao"|wrongStatLabel|solvedInCategory|wrongState'
```

Expected:vitest 全 PASS(屏 13 原有用例一条不少,外加本任务新增的错题页 5 条与入口 2 条);tsc 无输出;两个 `grep` 都无输出(`TsumegoUnitsPage.tsx` 文件头那段旧说明已在 Step 4 换掉;`TsumegoUnitListPage.tsx` 行内那句「§14 那个琥珀标」随 Step 5 整段替换一起没了)。然后跑「基线比较」。

- [ ] **Step 7: 写错题页承重闸(当场量,不攒到 Task 9)**

CLAUDE.md 承重关卡的反查:把这一任务撤回去,错题页那条滚动区的**内容高度来源**就没了 —— 屏 13 原来那一支格子数恒 ≤ 20、断言「不滚」,错题页格子数是「这一类里试过没做对的**全部**」、可以远多于 20 ⇒ 「能不能滚」必须在这一刻用真浏览器量。这条闸只依赖本任务的路由与进度钥匙,不依赖 Task 8。

`katrain/web/ui/tests/kiosk-tsumego-wrong.spec.ts`:

```ts
import { expect, test } from '@playwright/test';

/**
 * 错题页(T1)的承重闸。
 *
 * 屏 13 本来那一支断言的是「满编 20 格一屏装得下、**不滚**」(`kiosk-shell-scroll.spec.ts`)。
 * 错题页复用同一副骨架,但格子数是「这一类里试过、还没做对的」**全部**题 —— 可以远多于 20
 * ⇒ 这一支**必须能滚**,而且滚到底最后一格在视口里。
 *
 * 「能不能滚」只认真浏览器 + 真滚轮(jsdom 没有布局引擎;`scrollTop = n` 证明不了用户能滚)。
 * 60 道错题是**造的输入**;溢不溢出、data-at、最后一格在哪,是浏览器算的**结论**。
 * 先断言前置状态成立 —— 造不出「装不下」,这条闸就没有被测对象,必须当场红。
 */
test.use({ viewport: { width: 1024, height: 600 } });

const IDS = Array.from({ length: 90 }, (_, i) => `w${i}`);
const WRONG = IDS.slice(0, 60);

test('错题页:60 道装不下时通栏自己滚,真滚轮滚得到最后一格,滚动条不占宽', async ({ page }) => {
  await page.addInitScript((wrong) => {
    localStorage.setItem('token', 'kiosk-tsumego-wrong');
    localStorage.setItem('katrain_language', 'cn');
    // 进度钥匙分人(`tsumego_progress:u<id>`),下面 auth/me 回 id=1。
    localStorage.setItem('tsumego_progress:u1', JSON.stringify(
      Object.fromEntries(wrong.map((id) => [id, { completed: false, attempts: 1 }])),
    ));
  }, WRONG);
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') {
      return route.fulfill({ json: { id: 1, username: 'tester', rank: '5段', credits: 0 } });
    }
    if (path.startsWith('/api/v1/tsumego/levels/') && path.includes('/categories/')) {
      return route.fulfill({ json: IDS.map((id) => ({ id })) });
    }
    return route.fulfill({ json: {} });
  });
  await page.goto('/kiosk/tsumego/15k/capturing/wrong');
  await page.waitForSelector('.qgrid button:nth-child(60)');

  const pre = await page.evaluate(() => {
    const sc = document.querySelector('.kiosk-side__scroll') as HTMLElement;
    return { cells: document.querySelectorAll('.qgrid button').length, overflow: sc.scrollHeight - sc.clientHeight };
  });
  expect(pre.cells, '没造出 60 道错题 —— 下面量的就不是「装不下」那一态').toBe(60);
  expect(pre.overflow, '60 道还装得下 —— 前置状态没造出来,这条闸没有被测对象').toBeGreaterThan(100);

  const zone = page.locator('.kiosk-scrollzone').first();
  await expect(zone).toHaveAttribute('data-at', 'top');
  const geom = await page.evaluate(() => {
    const z = document.querySelector('.kiosk-scrollzone') as HTMLElement;
    const sc = z.querySelector('.kiosk-side__scroll') as HTMLElement;
    return { zoneW: Math.round(z.getBoundingClientRect().width), clientW: sc.clientWidth };
  });
  expect(geom.zoneW, '通栏不是 992').toBe(992);
  expect(geom.clientW, '滚动条占了布局宽度 —— 992 就不是 992 了').toBe(992);

  // **真滚轮**。
  await page.mouse.move(500, 300);
  await page.mouse.wheel(0, 5000);
  await expect.poll(() => zone.getAttribute('data-at')).toBe('end');

  const last = await page.evaluate(() => {
    const sc = document.querySelector('.kiosk-side__scroll') as HTMLElement;
    const cells = document.querySelectorAll('.qgrid button');
    const cell = cells[cells.length - 1] as HTMLElement;
    return {
      cellBottom: Math.round(cell.getBoundingClientRect().bottom),
      zoneBottom: Math.round(sc.getBoundingClientRect().bottom),
    };
  });
  expect(last.cellBottom, '滚到底了最后一格还在视口外').toBeLessThanOrEqual(last.zoneBottom);
  console.log(`[wrong-list] 溢出 ${pre.overflow}px(只记录,不作判据)`);
});
```

- [ ] **Step 8: 构建并跑承重闸与原有滚动闸**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui
lsof -nP -iTCP:8002 -sTCP:LISTEN
mkdir -p /private/tmp/claude-501/kiosk-go-tsumego
cp ~/.katrain/config.json /private/tmp/claude-501/kiosk-go-tsumego/katrain-config.bak
npm run build
npx playwright test tests/kiosk-tsumego-wrong.spec.ts tests/kiosk-shell-scroll.spec.ts -g "错题页|训练营|单元列表|题目列表"
cp /private/tmp/claude-501/kiosk-go-tsumego/katrain-config.bak ~/.katrain/config.json
```

Expected:`lsof` 若有输出,先按 Global Constraints 确认它的 cwd 是本 worktree;之后全部 PASS —— 新闸 1 条,`kiosk-shell-scroll.spec.ts` 里训练营两条、单元列表一条、题目列表两条(「满编 20 格一屏装得下」必须仍然绿)。

- [ ] **Step 9: 让新闸的红分支跑一次(变异),再还原**

把 `kiosk-tsumego-wrong.spec.ts` 里 `const WRONG = IDS.slice(0, 60);` 临时改成 `IDS.slice(0, 5)`,只跑新闸:

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui
npx playwright test tests/kiosk-tsumego-wrong.spec.ts
```

Expected:FAIL,停在「没造出 60 道错题」(或「60 道还装得下」)—— 前置断言确实会拦。改回 `IDS.slice(0, 60)`,再跑一次,PASS。把「变异:WRONG 取 5 道 ⇒ 红在前置断言」一句补进该文件顶部注释末尾。(跑前后照 Step 8 备份 / 还原 `~/.katrain/config.json`。)

- [ ] **Step 10: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego
git add katrain/web/ui/src/kiosk/pages/tsumegoUnits.ts katrain/web/ui/src/kiosk/pages/TsumegoUnitsPage.tsx katrain/web/ui/src/kiosk/pages/TsumegoUnitListPage.tsx katrain/web/ui/src/kiosk/KioskApp.tsx katrain/web/ui/src/kiosk/__tests__/TsumegoUnitsPage.test.tsx katrain/web/ui/src/kiosk/__tests__/TsumegoUnitListPage.test.tsx katrain/web/ui/tests/kiosk-tsumego-wrong.spec.ts
git diff --cached --stat
git commit -m "feat(kiosk-tsumego): 「只做错过的」接通 —— 屏 12/13 可点,错题页用屏 13 同一副骨架,点格写快照"
```

---

### Task 8: T1(下)做题屏认 `?set=wrong` —— 上/下一题只在错题快照里走

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx`:`:2`(import)、`:14-24`(`./tsumegoUnits` import)、`:118-158`(顺序表)、`:169-181`(Task 4 改过的「上次」effect)、`:187-202`(两个导航函数)、`:307-319`(单元号 / 返回去处)、`:366-367`(「下一题」键)、`:461`(页控条标题)、`:630-634`(单元块标题)。行号按 `6f7dc629`,Task 1 / 3 / 4 已经在前面插过行 —— **以锚点原文为准**
- Test: `katrain/web/ui/src/kiosk/__tests__/TsumegoProblemPage.test.tsx:6`(import),文件末尾最外层 `describe` 里新增 `describe('错题模式 ?set=wrong(T1)')`

**Interfaces:**
- Consumes: Task 7 的 `readWrongSequence(level, category): string[] | null`、`wrongSequenceKey(level, category)`;Task 4 的 `writePracticeResume(userId, { label, route })`
- Produces: 做题屏内部的 `inWrongSet: boolean` 与派生出的 `sequence: string[]`(错题模式 = 快照,否则 = 整类顺序表);所有导航在错题模式下带 `?set=wrong`,回错题页 `/kiosk/tsumego/<level>/<category>/wrong`

- [ ] **Step 1: 写失败的测试**

`TsumegoProblemPage.test.tsx:6` 改成:

```tsx
import { AUTO_ADVANCE_KEY, sequenceKey, wrongSequenceKey } from '../pages/tsumegoUnits';
```

在最外层 `describe('TsumegoProblemPage · 屏 14 做题屏', …)` 的末尾(最后一个 `it` / 子 `describe` 之后)追加:

```tsx
  describe('错题模式 ?set=wrong(T1)', () => {
    // 整类顺序表是 ['p0','p1','p2'](最外层 beforeEach 写的);错题快照是另一条。
    // hook mock 恒返回 id 'p1' 的题,**路由参数**决定这一道在序列里排第几 —— 与原有用例同一个做法。
    const renderWrong = (problemId: string, search = '?set=wrong') =>
      render(
        <ThemeProvider theme={kioskTheme}>
          <MemoryRouter initialEntries={[`/kiosk/tsumego/problem/${problemId}${search}`]}>
            <Routes>
              <Route path="/kiosk/tsumego/problem/:problemId" element={<TsumegoProblemPage />} />
            </Routes>
          </MemoryRouter>
        </ThemeProvider>
      );
    const button = (name: string) => screen.getByRole('button', { name });

    beforeEach(() => {
      sessionStorage.setItem(wrongSequenceKey('15k', '手筋'), JSON.stringify(['q3', 'p1', 'q41']));
    });

    it('页控条写「错题 第 i / n 道」;上/下一题只在快照里走,而且带着 ?set=wrong', () => {
      renderWrong('p1');
      expect(screen.getByTestId('puzzle-pagebar')).toHaveTextContent('错题 第 2 / 3 道');
      fireEvent.click(button('上一题'));
      expect(mockNavigate).toHaveBeenLastCalledWith('/kiosk/tsumego/problem/q3?set=wrong');
      fireEvent.click(button('下一题'));
      expect(mockNavigate).toHaveBeenLastCalledWith('/kiosk/tsumego/problem/q41?set=wrong');
    });

    it('最后一道时键写「返回错题」,回错题页;页控条返回键同一个去处', () => {
      renderWrong('q41');
      fireEvent.click(button('返回错题'));
      expect(mockFlush).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenLastCalledWith('/kiosk/tsumego/15k/手筋/wrong');
      fireEvent.click(within(screen.getByTestId('puzzle-pagebar')).getByText('错题'));
      expect(mockNavigate).toHaveBeenLastCalledWith('/kiosk/tsumego/15k/手筋/wrong');
    });

    it('单元块换成「错题 · n 道」,点阵画的是快照那几道', () => {
      renderWrong('p1');
      expect(screen.getByTestId('puzzle-unit')).toHaveTextContent('错题 · 3 道');
      expect(screen.getByTestId('puzzle-dots').querySelectorAll('i')).toHaveLength(3);
      expect(screen.getByTestId('puzzle-dots').querySelectorAll('i.now')).toHaveLength(1);
    });

    it('快照很长时点阵最多画 20 个(当前这道所在的那 20 个)—— 右栏不滚,多一行就把动作区顶出画布', () => {
      // 造的是**输入**(45 道错题);断言的是组件算出来的 <i> 个数,不是布局结论。
      // 上限 20 = 整类模式一个单元的点数 ⇒ 右栏的高度来源和改之前同一个最大值。
      const long = Array.from({ length: 45 }, (_, i) => (i === 25 ? 'p1' : `w${i}`));
      sessionStorage.setItem(wrongSequenceKey('15k', '手筋'), JSON.stringify(long));
      renderWrong('p1');
      expect(screen.getByTestId('puzzle-pagebar')).toHaveTextContent('错题 第 26 / 45 道');
      expect(screen.getByTestId('puzzle-unit')).toHaveTextContent('错题 · 45 道');
      expect(screen.getByTestId('puzzle-dots').querySelectorAll('i')).toHaveLength(20);
      expect(screen.getByTestId('puzzle-dots').querySelectorAll('i.now')).toHaveLength(1);
    });

    it('「接着上次」记下带 ?set=wrong 的路由 —— 点「继续」回来还在错题里', () => {
      renderWrong('p1');
      expect(JSON.parse(localStorage.getItem('kiosk_tsumego_resume:u7')!)).toEqual({
        label: '15 级 · 手筋 · 错题第 2 道',
        route: '/kiosk/tsumego/problem/p1?set=wrong',
      });
    });

    it('快照里没有这道题(深链、换了标签页)⇒ 退回整类,不假装还在错题里', () => {
      sessionStorage.setItem(wrongSequenceKey('15k', '手筋'), JSON.stringify(['x', 'y']));
      renderWrong('p1');
      expect(screen.getByText('第 2 题')).toBeInTheDocument();
      fireEvent.click(button('下一题'));
      expect(mockNavigate).toHaveBeenLastCalledWith('/kiosk/tsumego/problem/p2');
    });

    it('没带 ?set=wrong 时,就算 sessionStorage 里有快照也照整类走', () => {
      renderWrong('p1', '');
      expect(screen.getByText('第 2 题')).toBeInTheDocument();
      fireEvent.click(button('下一题'));
      expect(mockNavigate).toHaveBeenLastCalledWith('/kiosk/tsumego/problem/p2');
    });
  });
```

并把文件第 2 行的 import 补上 `within`:

```tsx
import { render, screen, fireEvent, act, within } from '@testing-library/react';
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui && npx vitest run src/kiosk/__tests__/TsumegoProblemPage.test.tsx`
Expected: FAIL —— 前五条失败(页控条仍写「第 2 题」、导航不带 `?set=wrong`、没有「返回错题」、单元块写「第 1 单元」、点阵个数不对、续做路由不带查询串);后两条(退回整类)现在就 PASS,它们守的是改完别把整类行为弄坏。

- [ ] **Step 3: 顺序表拆成「整类」和「这一趟在走的」**

`:2`:

```tsx
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
```

`./tsumegoUnits` 的 import 列表补上 `readWrongSequence`。

`:118`:

```tsx
  const [sequence, setSequence] = useState<string[]>([]);
```

换成

```tsx
  const [categorySequence, setCategorySequence] = useState<string[]>([]);
```

同一个 effect 里的两处 `setSequence(seq);` / `setSequence(ids);` 分别改成 `setCategorySequence(seq);` / `setCategorySequence(ids);`。

紧接在这个 effect 结束(`}, [problem]);`)之后、`const currentIndex = useMemo(` 之前插入:

```tsx
  // ---- 错题模式(T1)----
  // `?set=wrong` 且错题快照里有这道题 ⇒ 上/下一题、做对自动下一题、实体模式做对后的翻页,
  // 全部只在快照里走(快照由错题页在点格那一刻写,见 `TsumegoUnitListPage`)。
  // 快照读不到 / 不含这道题(深链、换了标签页)⇒ 退回整类,**不假装还在错题里**。
  const [searchParams] = useSearchParams();
  const wantWrongSet = searchParams.get('set') === 'wrong';
  const wrongSequence = useMemo(
    () => (wantWrongSet && problem ? readWrongSequence(problem.level, problem.category) : null),
    [wantWrongSet, problem],
  );
  const inWrongSet = !!problemId && !!wrongSequence && wrongSequence.includes(problemId);
  const sequence = inWrongSet && wrongSequence ? wrongSequence : categorySequence;
```

(`currentIndex` / `isFirst` / `isLast` / `prevId` / `nextId` 以及 `sequence.length === 0` 那两处原因文案都读 `sequence`,一行不用改。)

- [ ] **Step 4: 「上次」effect、两个导航函数带上错题模式**

Task 4 改好的那个 effect 换成:

```tsx
  // 训练营首页「接着上次」+ 两处高亮(B2.2/B2.4),每进一道题写一次 —— 按账号存(N10)。
  // 错题模式下记带 `?set=wrong` 的路由:点「继续」回来还在错题里(T1)。
  useEffect(() => {
    if (!problem) return;
    writeLastLevel(user?.id, problem.level);
    writeLastCategory(user?.id, problem.category);
    const head = `${levelChinese(problem.level)} · ${t(`tsumego:${problem.category}`, problem.category)}`;
    writePracticeResume(
      user?.id,
      inWrongSet
        ? {
            label: `${head} · ${interpolate(t('tsumego:wrongResume', '错题第 {n} 道'), { n: currentIndex + 1 })}`,
            route: `/kiosk/tsumego/problem/${problem.id}?set=wrong`,
          }
        : { label: `${head} · 第 ${currentIndex + 1} 题`, route: `/kiosk/tsumego/problem/${problem.id}` },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps -- snapshot label written once per problem; `t` intentionally excluded
  }, [problem, currentIndex, user?.id, inWrongSet]);
```

`navigateToProblem` 与 `goToUnits`(`:186-203`)换成:

```tsx
  const navigateToProblem = useCallback(
    (id: string) => {
      flushProgress(); // persist the leaving problem's attempt (4.1/4.2)
      // 错题模式下翻页要带着 `?set=wrong`,否则下一道就掉回整类了(T1)。
      navigate(`/kiosk/tsumego/problem/${id}${inWrongSet ? '?set=wrong' : ''}`);
    },
    [navigate, flushProgress, inWrongSet],
  );

  const goToUnits = useCallback(() => {
    flushProgress();
    if (problem) {
      navigate(`/kiosk/tsumego/${problem.level}/${problem.category}${inWrongSet ? '/wrong' : ''}`);
    } else {
      navigate(-1);
    }
  }, [navigate, problem, flushProgress, inWrongSet]);
```

- [ ] **Step 5: 单元块、返回去处、「下一题」键、页控条标题**

`:307-319`(`// 这一题属于第几单元 —— …` 那行注释起、到 `const backLabel = …;` 止;下面的 `const backToUnit = useCallback(…)` 不动)换成:

```tsx
  // 这一题属于第几单元 —— 顺序表算得出来就算,算不出来(深链 + 取不到)就退回类目那一层。
  // 错题模式下没有「第几单元」:单元块画的是这份错题快照,返回去错题页(T1)。
  // ⚠️ 点阵**最多 20 个**(当前这道所在的那 20 个):右栏五块摆满 516、没有滚动,`.dots` 是
  // 10 列网格 —— 快照 60 道就是 6 行,把动作区顶出画布。和整类模式一个单元同一个上限 ⇒ 右栏高度来源不变。
  const unitNumber = !inWrongSet && currentIndex >= 0 ? Math.floor(currentIndex / UNIT_SIZE) + 1 : null;
  const wrongPage = inWrongSet && currentIndex >= 0 ? Math.floor(currentIndex / UNIT_SIZE) : 0;
  const unitIds = inWrongSet
    ? sequence.slice(wrongPage * UNIT_SIZE, (wrongPage + 1) * UNIT_SIZE)
    : unitNumber === null
      ? []
      : sequence.slice((unitNumber - 1) * UNIT_SIZE, unitNumber * UNIT_SIZE);
  const backTarget = problem
    ? inWrongSet
      ? `/kiosk/tsumego/${problem.level}/${problem.category}/wrong`
      : unitNumber === null
        ? `/kiosk/tsumego/${problem.level}/${problem.category}`
        : `/kiosk/tsumego/${problem.level}/${problem.category}/${unitNumber}`
    : null;
  const backLabel = inWrongSet
    ? t('tsumego:wrongSet', '错题')
    : unitNumber === null
      ? categoryName
      : interpolate(t('tsumego:unit_n', '第 {n} 单元'), { n: unitNumber });
```

`actions` 里 `isLast ? { key: 'next', icon: 'squares-four', label: t('tsumego:backToUnit', '返回单元'), onClick: backToUnit } : …` 那一项的 `label` 换成:

```tsx
          label: inWrongSet ? t('tsumego:backToWrong', '返回错题') : t('tsumego:backToUnit', '返回单元'),
```

页控条 `title={interpolate(t('tsumego:problem_no', '第 {n} 题'), { n: currentIndex >= 0 ? currentIndex + 1 : 1 })}` 换成:

```tsx
          title={
            inWrongSet
              ? interpolate(t('tsumego:wrongProgress', '错题 第 {i} / {n} 道'), { i: currentIndex + 1, n: sequence.length })
              : interpolate(t('tsumego:problem_no', '第 {n} 题'), { n: currentIndex >= 0 ? currentIndex + 1 : 1 })
          }
```

单元块 `<h3>`(`data-testid="puzzle-unit"` 里)换成:

```tsx
          <h3>
            {inWrongSet
              ? `${t('tsumego:wrongSet', '错题')} · ${interpolate(t('tsumego:wrong_total', '{n} 道'), { n: sequence.length })}`
              : unitNumber === null
                ? t('tsumego:unitUnknown', '这一单元')
                : `${interpolate(t('tsumego:unit_n', '第 {n} 单元'), { n: unitNumber })} · ${interpolate(t('tsumego:unit_total', '{n} 题'), { n: unitIds.length })}`}
          </h3>
```

- [ ] **Step 6: 跑测试确认通过,类型检查,新 key 不撞 PO**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui
npx vitest run src/kiosk/__tests__/TsumegoProblemPage.test.tsx src/kiosk/__tests__/TsumegoUnitListPage.test.tsx
npx tsc -b
grep -o 'msgid "tsumego:[^"]*"' ../../../katrain/i18n/locales/cn/LC_MESSAGES/katrain.po | grep -E 'wrongResume|backToWrong|wrongProgress|wrong_total'
```

Expected:两个文件全 PASS(做题屏原有用例一条不少);tsc 无输出;`grep` 无输出。然后跑「基线比较」。

- [ ] **Step 7: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego
git add katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx katrain/web/ui/src/kiosk/__tests__/TsumegoProblemPage.test.tsx
git diff --cached --stat
git commit -m "feat(kiosk-tsumego): 做题屏认 ?set=wrong —— 错题快照里翻页、返回错题页,快照对不上就退回整类"
```

---

### Task 9: 真浏览器关卡 —— 四图重取、两套构建、全量回归,交 Fan 视觉确认

**Files:**
- Create: `katrain/web/ui/tests/kiosk-tsumego-wrong.fourup.spec.ts`(四图,visual 配置;文件名**不**匹配 `kiosk-screen-*.fourup.spec.ts`,不会混进 27 屏存档)
- Modify: `katrain/web/ui/tests/kiosk-screen-11-training.fourup.spec.ts:82`、`tests/kiosk-screen-12-units.fourup.spec.ts:58`、`tests/kiosk-screen-13-problems.fourup.spec.ts:68`(标签带文字)
- 产物:`superpowers/tracks/kiosk-go-shell-align/visual/{11-training,12-units,13-problems}/1024x600/*.png`(重取)、`superpowers/tracks/kiosk-go-tsumego/visual/{13w-wrong,14w-puzzle-wrong}/1024x600/*.png`(新)
- (错题页承重闸 `tests/kiosk-tsumego-wrong.spec.ts` 已在 Task 7 Step 7–9 写好并跑过 —— 承重关卡要求当场量,不在这里补。)

**Interfaces:**
- Consumes: Task 4 的钥匙 `tsumego_progress:u<id>`(进度,已有)与 `kiosk_tsumego_*:u<id>`;Task 7 的路由 `/kiosk/tsumego/:level/:category/wrong` 与快照钥匙 `kiosk_problems_<level>_<category>_wrong`;`captureFourUp` / `freezeClock` / `stubBackendStatics` / `KIOSK_VIEWPORT`(`tests/helpers/fourup.ts`)
- Produces: 无代码接口;产出是四图存档

- [ ] **Step 1: 改屏 12 / 13 四图的标签带文字**

`tests/kiosk-screen-12-units.fourup.spec.ts` 的 `implementationCaption` 末尾那段 `· 「只做错过的」灰是真的(算得出、没地方去)` 换成:

```ts
 · 「只做错过的」已接通(T1),这里灰是因为**进度没造** ⇒ 0 道 · 「整级」副标改成「按分类排好，不分单元」(N8:整级页不是混排,稿子那句不成立)
```

`tests/kiosk-screen-13-problems.fourup.spec.ts:68` 那一行 `+ '「只做错过的」不摆按不动的「开始」,只挂 §14 琥珀标',` 换成:

```ts
      + '「只做错过的」已接通(T1):行尾是「开始」,进错题页 · 「整级」那行改成「这一级的全部题，按分类排好」(N8:不是混排)',
```

屏 11 的 `implementationCaption` 末尾补一句(`tests/kiosk-screen-11-training.fourup.spec.ts:82` 那个字符串里,`环恒「—」是真的:这一层算不出每档进度` 之后):

```ts
 · 问候副标是「落子即判，走错当场退回」不是稿子的「题在实体盘上摆好」(N26③:实体开关默认关)
```

- [ ] **Step 2: 写错题页 / 做题屏错题模式的四图**

`katrain/web/ui/tests/kiosk-tsumego-wrong.fourup.spec.ts`:

```ts
import { test, type Page } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = (slug: string) => resolve(process.cwd(),
  `../../../superpowers/tracks/kiosk-go-tsumego/visual/${slug}/1024x600`);

/**
 * 错题页与做题屏错题模式(T1)。**稿子没有单独画这两态** —— 稿子原注写的是「同一副骨架，只换题从哪儿来」,
 * 所以参考图分别拿屏 13 与屏 14:比的是骨架(几何、层级、组件),不是文案。
 * 进度造进 `tsumego_progress:u1`(真存储真格式),`auth/me` 回 id=1。
 */
const PROBLEM = {
  id: 'demo-atari', level: '15k', category: 'capturing', hint: '黑先', boardSize: 19,
  initialBlack: ['co', 'bp', 'eo', 'fp'], initialWhite: ['cp', 'ep'], sgfContent: '',
};
const IDS = Array.from({ length: 45 }, (_, i) => ({ id: i === 3 ? PROBLEM.id : `p${i}` }));
const PROGRESS = {
  p0: { completed: true, attempts: 0, lastDuration: 18 },
  p1: { completed: true, attempts: 1, lastDuration: 40 },
  [PROBLEM.id]: { completed: false, attempts: 1 },
  p8: { completed: false, attempts: 2 },
  p20: { completed: false, attempts: 1 },
  p33: { completed: false, attempts: 3 },
};

const boot = async (page: Page, snapshot: string[] | null) => {
  await freezeClock(page);
  await page.addInitScript(({ progress, snap }) => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
    localStorage.setItem('kiosk_tsumego_physical', 'false');
    localStorage.setItem('tsumego_progress:u1', JSON.stringify(progress));
    if (snap) sessionStorage.setItem('kiosk_problems_15k_capturing_wrong', JSON.stringify(snap));
  }, { progress: PROGRESS, snap: snapshot });
  await stubBackendStatics(page);
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') {
      return route.fulfill({ json: { id: 1, username: '访客', rank: '5段', credits: 0 } });
    }
    if (path.startsWith('/api/v1/tsumego/problems/')) return route.fulfill({ json: PROBLEM });
    if (path.startsWith('/api/v1/tsumego/levels/') && path.includes('/categories/')) {
      return route.fulfill({ json: IDS });
    }
    return route.fulfill({ json: {} });
  });
};

test('四图:错题页 ←→ sample-go/shots/13-problems.png(同一副骨架)', async ({ page }) => {
  await boot(page, null);
  await page.goto('/kiosk/tsumego/15k/capturing/wrong');
  await page.waitForSelector('.qgrid button:nth-child(4)');
  await page.waitForLoadState('networkidle');
  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '13-problems.png'),
    outDir: OUT('13w-wrong'),
    slug: '13w-wrong',
    referenceCaption: '参考:sample-go/shots/13-problems.png · 稿子没画错题页;原注「同一副骨架，只换题从哪儿来」⇒ 拿屏 13 比骨架',
    implementationCaption:
      '实现:/kiosk/tsumego/15k/capturing/wrong @1024×600 · 时钟冻 16:40 · 题号 45 个与进度(4 道试过没做对)是 fixture · '
      + '数据条换成「现在有几道 / 平均尝试次数 / 这一类已做对」· 格上写整类真题号 · 换一批只剩整级',
  });
  console.log(`[fourup 13w-wrong] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});

test('四图:做题屏错题模式 ←→ sample-go/shots/14-puzzle.png(同一副骨架)', async ({ page }) => {
  await boot(page, [PROBLEM.id, 'p8', 'p20', 'p33']);
  await page.goto(`/kiosk/tsumego/problem/${PROBLEM.id}?set=wrong`);
  await page.waitForSelector('.kiosk-layout-a .dots i:nth-child(4)');
  await page.waitForLoadState('networkidle');
  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '14-puzzle.png'),
    outDir: OUT('14w-puzzle-wrong'),
    slug: '14w-puzzle-wrong',
    referenceCaption: '参考:sample-go/shots/14-puzzle.png · 稿子没画错题模式 ⇒ 拿屏 14 比骨架',
    implementationCaption:
      '实现:/kiosk/tsumego/problem/:id?set=wrong @1024×600 · 时钟冻 16:40 · 题目逐子同屏 14 fixture · '
      + '页控条「错题 第 1 / 4 道」、返回键「错题」、单元块「错题 · 4 道」;其余与屏 14 同',
  });
  console.log(`[fourup 14w-puzzle-wrong] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
```

- [ ] **Step 3: 取四图(屏 11 / 12 / 13 重取 + 两张新的),各取两次判抖动**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui
lsof -nP -iTCP:5173 -sTCP:LISTEN
npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-11-training.fourup.spec.ts tests/kiosk-screen-12-units.fourup.spec.ts tests/kiosk-screen-13-problems.fourup.spec.ts tests/kiosk-tsumego-wrong.fourup.spec.ts
npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-11-training.fourup.spec.ts tests/kiosk-screen-12-units.fourup.spec.ts tests/kiosk-screen-13-problems.fourup.spec.ts tests/kiosk-tsumego-wrong.fourup.spec.ts
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego && git status --short superpowers/tracks/kiosk-go-shell-align/visual superpowers/tracks/kiosk-go-tsumego/visual
```

Expected:6 条四图全部跑完,控制台打印 6 行 `both/refOnly/implOnly`(两次的数应在同一量级;屏 11–13 的盘是 DOM/SVG,抖动地板约 200 像素)。`git status` 显示屏 11 / 12 / 13 三个目录的 `*--implementation.png` 等为 `M`,本赛道 `visual/` 为新增。**逐张打开**四类图(参考、实现、并排、差异),对照 PRD §3 N26③ / N8 / T1 的「期望」逐条看:屏 11 问候副标、屏 12 整级卡副标与错题卡、屏 13 整级行与错题行「开始」键、错题页骨架与屏 13 同几何、做题屏错题模式的页控条 / 单元块。某屏两次之间差异是散点而改动本身不在那一屏(例如只有抖动),`git checkout HEAD -- <那一屏目录>` 还原,不提交。

- [ ] **Step 4: 两套构建 + 全量基线比较**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego/katrain/web/ui
npx tsc -b && npm run build && npm run build:kiosk-2d
npx playwright test tests/kiosk-copy-placeholders.spec.ts
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego && CI=true uv run pytest tests/web_ui -q -rf 2>&1 | grep '^FAILED' | sed 's/ - .*//' | sort > /private/tmp/claude-501/kiosk-go-tsumego/pytest-now-failed.txt
comm -13 /private/tmp/claude-501/kiosk-go-tsumego/pytest-baseline-failed.txt /private/tmp/claude-501/kiosk-go-tsumego/pytest-now-failed.txt
git status --short katrain/config.json
```

Expected:tsc 无输出;两次 build 成功,`verify:kiosk-2d` 退出码 0;`kiosk-copy-placeholders.spec.ts` PASS(真翻译表下屏上没有残留的 `{n}` / `{coord}`);`comm -13` 无输出;`katrain/config.json` 无改动。再跑一次前端「基线比较」,`comm -13` 无输出。(跑 e2e 前后照 Task 7 Step 8 备份 / 还原 `~/.katrain/config.json`。)

- [ ] **Step 5: Commit(标签带 + 四图存档)**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-tsumego
git add katrain/web/ui/tests/kiosk-tsumego-wrong.fourup.spec.ts katrain/web/ui/tests/kiosk-screen-11-training.fourup.spec.ts katrain/web/ui/tests/kiosk-screen-12-units.fourup.spec.ts katrain/web/ui/tests/kiosk-screen-13-problems.fourup.spec.ts superpowers/tracks/kiosk-go-shell-align/visual/11-training superpowers/tracks/kiosk-go-shell-align/visual/12-units superpowers/tracks/kiosk-go-shell-align/visual/13-problems superpowers/tracks/kiosk-go-tsumego/visual
git diff --cached --stat
git commit -m "test(kiosk-tsumego): 屏 11–13 四图重取 + 错题页 / 做题屏错题模式四图"
```

(若 Step 3 判定某屏只是抖动而还原了,`git add` 列表里去掉那一屏。)

- [ ] **Step 6: 交 Fan 视觉确认,并列出上板清单**

把以下发给 Fan(不 push、不合并):
1. 四图目录:`superpowers/tracks/kiosk-go-shell-align/visual/{11-training,12-units,13-problems}/1024x600/`、`superpowers/tracks/kiosk-go-tsumego/visual/{13w-wrong,14w-puzzle-wrong}/1024x600/`,每屏看 `--side-by-side.png` 与 `--diff.png`;
2. 视觉确认前**不算完成**;
3. 上板清单(RK3562,board 模式,token=null;照 prd.md §7「上板」一行逐条走,板上一次只跑一家):重启服务后实体开关关 / 开两种状态各进一次题(开关按盒存;关着时开关灰且提示去确认标定);断网看「连不上云端题库」;甲乙换账号看「接着上次」;实体做题摆题引导无「开始答题」、答错拿除写棋盘坐标且与蓝灯一致;顺带走 kiosk-physical-tsumego PRD §6 全项并留记录(T10);
4. 待拍板三件:prd.md §4 D1 / D2 / D3。

---

## Self-Review(写完计划后对照 prd.md 自查)

**1. 需求覆盖**

| prd.md §3 条目 | 落在哪 | 验收里「必须上板」的那一半 |
|---|---|---|
| T9 做题页不再无条件套标定守卫(含页内实体开关认几何确认) | Task 1 | Task 9 Step 6 清单第 1 条 |
| N9(训练营)503 与文案 | Task 2(后端契约)→ Task 3(前端) | 清单第 2 条 |
| N10(训练营)「上次」按账号存 | Task 4(含两份 e2e fixture) | 清单第 3 条 |
| N26③ 问候副标 | Task 5;四图屏 11 在 Task 9 | —— |
| N8(文案)整级不说混排 | Task 5;四图屏 12 / 13 在 Task 9 | —— |
| T4(文案)退一手原因 | Task 5 | 清单第 4 条(实体模式) |
| T8(死键)删「开始答题」 | Task 6 | 清单第 4 条 |
| N12 拿除写棋盘坐标 | Task 6 | 清单第 4 条(与蓝灯位置一致只能在板上看) |
| T1 只做错过的 | Task 7(入口 + 错题页 + 承重闸)→ Task 8(做题屏快照翻页,点阵上限 20)→ Task 9(两组新四图) | —— |
| §7 两套构建 / tsc -b / 基线 diff / 四图 / 承重 | Task 3 Step 6(共享领地那一次)、每个任务收尾的「基线比较」、Task 7 Step 7–9(承重闸,当场量)、Task 9 Step 1–4 | —— |

§4 的 D1 / D2 / D3 与 §5 的全部条目**没有**任务 —— 按 PRD 的约定,待拍板与不在本轮的不进计划。

**2. 占位扫描** —— 已 grep `TBD|TODO|implement later|fill in|Similar to Task`,零命中。所有代码步骤给了完整代码;所有「跑」给了命令与预期。

**3. 名字与签名一致性**

- `readLastLevel / writeLastLevel / readLastCategory / writeLastCategory` 在 Task 4 定义为**首参 `userId`**;Task 4 的四个页面、Task 7 Step 5 的整段组件、Task 8 Step 4 的 effect 都按 `(user?.id, …)` 调用。
- `readPracticeResume / writePracticeResume(userId, { label, route })`:Task 4 定义,Task 4 首页读、Task 8 做题屏写(错题模式 route 带 `?set=wrong`)。
- `isCloudUnreachable / loadErrorCopy(t, error)`:Task 3 定义,Task 3 六个页面与 Task 7 Step 5 的错误块使用。
- `wrongSequenceKey / readWrongSequence / writeWrongSequence / isWrongEntry`:Task 7 Step 3 定义;Task 7 屏 12 卡 / 错题页用 `isWrongEntry` 与 `writeWrongSequence`,Task 8 用 `readWrongSequence`,Task 8 测试用 `wrongSequenceKey`,Task 9 四图 fixture 用字面量 `kiosk_problems_15k_capturing_wrong`(与 `wrongSequenceKey('15k','capturing')` 同值)。
- 路由 `/kiosk/tsumego/:level/:category/wrong`:Task 7 Step 4 加路由,Task 7 测试 / Task 8 返回去处 / Task 9 两个 spec 用同一条。
- `BoardSetupGuide` 删掉 `isComplete` / `onStartProblem`:Task 6 Step 3 改组件,Step 4 改唯一调用点,Step 6 `grep` 确认零残留。
- `TSUMEGO_UNAVAILABLE`(后端常量)只在 `repository.py` 内使用;端点只认异常类型,不认这句字符串。

**4. 已知的顺序依赖** —— Task 3 → Task 7(错误块写法)、Task 4 → Task 7 / 8(`userId` 签名)、Task 5 → Task 7(整级那行文案在 Task 7 的整段替换里必须保持 Task 5 的新句)、Task 2 → Task 3(503 契约)、Task 7 → Task 8 → Task 9。Task 1 / 3 / 4 / 5 / 6 / 8 都改 `TsumegoProblemPage.tsx` 与 `TsumegoProblemPage.test.tsx`,**按编号顺序串行做**(后面的锚点建立在前面改完的文本上),不要并行派发。

## 执行交接

计划写完后由主会话决定执行方式:推荐 superpowers:subagent-driven-development(每个任务一个新子代理,任务之间复审);或 superpowers:executing-plans 在同一会话里分批执行。无论哪种,**Task 9 Step 6 的 Fan 视觉确认与上板清单不可跳过**,确认前本赛道不算完成、不合并。
