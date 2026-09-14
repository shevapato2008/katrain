# 围棋 kiosk 棋谱模块（kiosk-go-kifu）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让盒上的摆谱走得完、不拍照：出口回棋谱屏、非 19 路谱进门即拦、上线态只用灯不用摄像头；断网时棋谱库说「要联网」。

**Architecture:** K1 把 `/kiosk/baipu` 死页换成到 `/kiosk/kifu` 的重定向并改掉五处入口；K4 在服务端加默认关的采集模式开关（`--baipu-collect` + `GET /api/v1/baipu/mode`），前端新增 `BaipuSessionRoute` 先问模式、只在采集态套标定守卫，`BaipuSessionPage` 按 `collect` prop 分上线态 / 采集态；K2 在摆谱屏（所有入口的汇合点）拦非 19 路；N9 让 board 模式棋谱库两条 dispatcher 路径走现成的 `_remote_only`（离线 → 503），前端按 `ApiError.status === 503` 换文案。

**Tech Stack:** React + TypeScript + Vite（vitest / Playwright），FastAPI + pytest，KaTrain board 模式 `RepositoryDispatcher`。

**Spec:** `superpowers/tracks/kiosk-go-kifu/prd.md`（本轮做：K1、K4、K2、N9 棋谱库那一半；待拍板 D1–D7 不进任务）

## Global Constraints

> **开工前先读 `prd.md` §6.0**：五条赛道的共享文件归属与合并顺序（尤其 `server.py` 终局落账只留一条入口）。与本 plan 冲突时以 §6.0 为准。

- 在 worktree `/Users/fan/Repositories/katrain-kiosk-go-kifu`（分支 `feature/kiosk-go-kifu`）里开发；**不 push、不合并 develop**，合并由 Fan 决定；不在别的 worktree 里 checkout；做基线对照实验要开 `git worktree add`，不在本 worktree 里 `git checkout HEAD -- <dir>`（会冲掉未提交的活）。
- 改了共享领地（本计划动 `src/api/baipuApi.ts`、`src/api/kifuApi.ts`）⇒ `npm run build` 与 `npm run build:kiosk-2d` 都必须绿，后者末尾 `✅ kiosk boundary clean`；kiosk 边界（`verify:kiosk-2d`、`eslint.config.js` 边界规则）不许破。`src/kiosk/**` 不得 import `src/galaxy/**`、`Board3D`、`VideoRecorderPage*`。
- 类型检查用 `npx tsc -b`（`npx tsc --noEmit` 检查 0 个文件）；`*.test.ts(x)` 不在 tsc 范围内，测试文件的类型错误不会被它抓到。
- 盒上 token 恒为 null：任何「发不发请求 / 渲不渲染」的判别位用 `isAuthenticated`，不用 token。本计划新增的判别位只有 `collect`（来自 `/baipu/mode`）与 `ApiError.status`，都不读 token。
- 新文案一律 `t('ns:key', '中文默认')`；**不往 PO 里加 key**（补不补待 Fan 裁定，prd §4 D7 列了本轮新增的 13 个 key）；新 key 不得与 PO 已有 msgid 同名（已核对 13 个均为 0 命中）。
- Python 用 `uv run black -l 120`，但**只让它改本任务写的代码**：`server.py`、`tests/test_baipu_api.py`、`tests/test_baipu_capture.py` 在基线上就不是 black 干净的，对它们只跑 `--diff`（见 Task 4 Step 7）；后端测试 `CI=true uv run pytest <文件>`（测试在 `tests/test_baipu_api.py`、`tests/test_baipu_capture.py`、`tests/web_ui/`）；前端单测 `cd katrain/web/ui && npx vitest run <文件>`。
- 测试判据是**基线 diff**：Task 0 记录失败用例**名字集合**，Task 7 比名字集合，不比条数。已知负载相关不稳定名单（`ReportsPage.test.tsx`、`ReportsPage.polling.test.tsx`、`TutorialFigurePage.test.tsx` 超时）变红时先单独跑一遍，绿就不算回归。
- Playwright e2e 打的是构建产物：`tests/baipu.spec.ts` 用默认 `playwright.config.ts`（起 :8002 真后端、服务 `katrain/web/static`）⇒ **改源码后先 `npm run build` 再跑**。它会在退出时改写 `~/.katrain/config.json`：跑前 `cp` 备份、跑后还原。`kiosk-shell-*.spec.ts` 与四图用 `--config=playwright.visual.config.ts`（vite dev server :5173，不起 Python 后端，接口全靠 `page.route` 桩）。
- 视觉 / 布局改动走 CLAUDE.md 的四图对比与承重实测关卡（`npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-17-baipu.fourup.spec.ts`；jsdom 不作布局证据），**视觉通过需 Fan 确认**；K4 后端任务（Task 4）必须在 Fan 确认屏 17 上线态四图之后才开始。
- pytest 之后查一次 `git status --short katrain/config.json`：测试可能改写被提交的 `katrain/config.json`，有变动就 `git checkout -- katrain/config.json` 还原，不提交它。
- 建新文件后用 `git add <file>` + `git diff --cached --stat` 确认进了暂存区（仓里 `.gitignore` 会静默吞掉某些文件名），不要只看 `git status`。
- commit 信息结尾加 `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`。

## File Structure

| 文件 | 动作 | 职责 / 所属任务 |
|---|---|---|
| `katrain/web/ui/src/kiosk/KioskApp.tsx` | Modify | `/kiosk/baipu` 改重定向（T1）；会话路由换 `BaipuSessionRoute`（T2） |
| `katrain/web/ui/src/kiosk/pages/BaipuListPage.tsx` | Delete | 不可达的旧选谱页（T1） |
| `katrain/web/ui/src/kiosk/pages/BaipuSessionRoute.tsx` | Create | 问 `/baipu/mode`，决定套不套 `PhysicalBoardGuard`（T2） |
| `katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx` | Modify | 出口（T1）、`collect` 两态（T2）、非 19 路拦截（T5） |
| `katrain/web/ui/src/api/baipuApi.ts` | Modify | `BaipuAPI.mode()`（T2）、`forgetSgf()`（T5） |
| `katrain/web/ui/src/kiosk/pages/KifuPage.tsx` | Modify | 「摆到实体盘」卡开搜索（T1）、503 文案（T6） |
| `katrain/web/ui/src/kiosk/pages/KifuDetailPage.tsx` | Modify | 非 19 路灰键（T5）、503 文案（T6）、头注一处过期引用（T1） |
| `katrain/web/ui/src/kiosk/pages/TutorialCategoriesPage.tsx` | Modify | 「去摆谱」改指 `/kiosk/kifu`（T1） |
| `katrain/web/ui/src/api/kifuApi.ts` | Modify | 非 2xx 抛 `ApiError`（T6） |
| `katrain/web/api/v1/endpoints/baipu.py` | Modify | `_collect_enabled`、`GET /mode`、`/capture` 门（T4） |
| `katrain/web/core/baipu_capture.py` | Modify | `resolve_baipu_collect`（T4） |
| `katrain/web/server.py` | Modify | `--baipu-collect` 参数、`app.state.baipu_collect`（T4） |
| `katrain/vision/README.md` | Modify | 采集启动命令加 `--baipu-collect`（T4） |
| `katrain/web/core/repository.py` | Modify | `kifu_list_albums` / `kifu_get_album` 走 `_remote_only`（T6） |
| `katrain/web/api/v1/endpoints/kifu.py` | Modify | dispatcher 分支映射 503 / 404（T6） |
| 测试（vitest） | Create/Modify | `src/kiosk/__tests__/BaipuSessionPage.test.tsx`（新，T1/T2/T5）、`src/kiosk/__tests__/BaipuSessionRoute.test.tsx`（新，T2）、`src/api/baipuApi.test.ts`（T2）、`src/kiosk/__tests__/KifuPage.test.tsx`（T1/T6）、`src/kiosk/__tests__/KifuDetailPage.test.tsx`（T5/T6）、`src/kiosk/pages/TutorialCategoriesPage.test.tsx`（T1）、`src/kiosk/__tests__/KioskApp.test.tsx`（T1） |
| 测试（Playwright） | Modify | `tests/baipu.spec.ts`（T1/T2）、`tests/kiosk-shell-scroll.spec.ts`（T2）、`tests/kiosk-shell-contract.spec.ts`（T1）、`tests/kiosk-shell-geometry.spec.ts`（T1）、`tests/kiosk-screen-17-baipu.fourup.spec.ts`（T3） |
| 测试（pytest） | Create/Modify | `tests/test_baipu_api.py`、`tests/test_baipu_capture.py`（T4）、`tests/web_ui/test_kifu_offline.py`（新，T6） |

**任务顺序与依赖：** T0 → T1（K1）→ T2（K4 前端）→ T3（屏 17 四图关卡，**停下等 Fan**）→ T4（K4 后端，Fan 确认后）。T5（K2）、T6（N9）与 T3 的关卡无依赖，等 Fan 期间可以先做；T7 收尾放最后。

---

### Task 0: 环境与基线

**Files:** 无源码改动。基线产物放 `$HOME/.cache/kiosk-go-kifu/baseline/`（不进仓）。

**Interfaces:**
- Consumes: 无
- Produces: `$BASE/vitest-fail.txt`、`$BASE/pytest-fail.txt`（排序后的失败用例名集合），供 Task 7 比对；`$BASE/config.json.bak`

- [ ] **Step 1: 确认位置与分支**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu
git rev-parse --abbrev-ref HEAD      # 期望:feature/kiosk-go-kifu
git log --oneline -1                 # 期望:6f7dc629 或本赛道自己之后的提交
git status --short                   # 期望:只有 superpowers/tracks/kiosk-go-kifu/ 下的文档
```

- [ ] **Step 2: 装依赖、编 .mo（worktree 里没有 `.venv` 和 `node_modules`）**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu
uv sync
uv run python i18n.py || true        # 今天会退 1(有语言没翻完),判据看产物不看退出码
ls katrain/i18n/locales/*/LC_MESSAGES/katrain.mo | wc -l   # 期望:≥ 10
cd katrain/web/ui && npm ci
```

- [ ] **Step 3: 备份 config.json，记前端基线**

```bash
BASE="$HOME/.cache/kiosk-go-kifu/baseline"; mkdir -p "$BASE"
cp ~/.katrain/config.json "$BASE/config.json.bak" 2>/dev/null || true
cd /Users/fan/Repositories/katrain-kiosk-go-kifu/katrain/web/ui
npx vitest run --reporter=json --outputFile="$BASE/vitest.json" > "$BASE/vitest.log" 2>&1 || true
python3 - "$BASE/vitest.json" > "$BASE/vitest-fail.txt" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
for f in d["testResults"]:
    for a in f["assertionResults"]:
        if a["status"] == "failed":
            print(f'{f["name"].split("katrain/web/ui/")[-1]} > {a["fullName"]}')
EOF
sort -o "$BASE/vitest-fail.txt" "$BASE/vitest-fail.txt"; wc -l "$BASE/vitest-fail.txt"
npx tsc -b && echo TSC_OK
```

Expected: `TSC_OK`；`vitest-fail.txt` 行数记下（scope §8 记过的形状是个位数）。

- [ ] **Step 4: 记后端基线**

```bash
BASE="$HOME/.cache/kiosk-go-kifu/baseline"
cd /Users/fan/Repositories/katrain-kiosk-go-kifu
CI=true uv run pytest tests -q -rfE > "$BASE/pytest.txt" 2>&1 || true
grep -E '^(FAILED|ERROR) ' "$BASE/pytest.txt" | sed -E 's/ - .*//' | sort -u > "$BASE/pytest-fail.txt"
tail -3 "$BASE/pytest.txt"; wc -l "$BASE/pytest-fail.txt"
git status --short katrain/config.json   # 期望:空;有变动就 git checkout -- katrain/config.json
```

- [ ] **Step 5: 不提交**（本任务无源码改动）

---

### Task 1: K1 · 摆谱的出口与入口不再指向死页

**Files:**
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx:56`（删 import）、`:137-144`（注释 + 路由）
- Delete: `katrain/web/ui/src/kiosk/pages/BaipuListPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx:334,350,554,622`
- Modify: `katrain/web/ui/src/kiosk/pages/KifuPage.tsx:225-230`
- Modify: `katrain/web/ui/src/kiosk/pages/TutorialCategoriesPage.tsx:192`
- Modify: `katrain/web/ui/src/kiosk/pages/KifuDetailPage.tsx:22`（头注里一处过期引用）
- Create: `katrain/web/ui/src/kiosk/__tests__/BaipuSessionPage.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/KifuPage.test.tsx:115-119`
- Modify: `katrain/web/ui/src/kiosk/pages/TutorialCategoriesPage.test.tsx:185`
- Modify: `katrain/web/ui/src/kiosk/__tests__/KioskApp.test.tsx`（加 mock 与一条用例）
- Modify: `katrain/web/ui/tests/baipu.spec.ts:86-88,122`
- Modify: `katrain/web/ui/tests/kiosk-shell-contract.spec.ts:172-176,192`
- Modify: `katrain/web/ui/tests/kiosk-shell-geometry.spec.ts:1277-1296,1322`

**Interfaces:**
- Consumes: 无
- Produces: 路由 `/kiosk/baipu` ⇒ `<Navigate to="/kiosk/kifu" replace />`；`BaipuSessionPage` 所有离开路径 `navigate('/kiosk/kifu')`；测试文件 `BaipuSessionPage.test.tsx` 的 `renderPage()`、`move()`、`STEPS`、`META` 夹具（Task 2、Task 5 在此文件上追加）

- [ ] **Step 1: 写失败的单测 —— 摆谱屏三种离开都回棋谱屏**

`git ls-files katrain/web/ui/src/kiosk/__tests__/BaipuSessionPage.test.tsx` 先确认为空（新文件，不是覆盖）。创建：

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import BaipuSessionPage from '../pages/BaipuSessionPage';
import type { BaipuStep } from '../../api/baipuApi';

/**
 * 屏 17 · 摆谱进行中 —— **行为 / 调用级**的单测(谁被导航到哪、发没发哪个请求、屏上说了哪句)。
 * ⚠️ jsdom 没有布局引擎:右栏装不装得下、动作区贴不贴底,判据在 `tests/kiosk-shell-scroll.spec.ts`。
 */

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const { baipuLoad, baipuCapture } = vi.hoisted(() => ({ baipuLoad: vi.fn(), baipuCapture: vi.fn() }));
vi.mock('../../api/baipuApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/baipuApi')>();
  return { ...actual, BaipuAPI: { ...actual.BaipuAPI, load: baipuLoad, capture: baipuCapture } };
});

const { ledPoint } = vi.hoisted(() => ({ ledPoint: vi.fn() }));
vi.mock('../../api/ledApi', () => ({
  LedAPI: {
    point: ledPoint,
    points: vi.fn(() => Promise.resolve({ ok: true, connected: true })),
    clear: vi.fn(() => Promise.resolve({ ok: true, connected: true })),
  },
}));

const move = (i: number, row: number, col: number, color: 'B' | 'W'): BaipuStep => ({
  kind: 'move', move_index: i, property: color, row, col, color, removed: [], board_hash: `h${i}`,
});
const STEPS: BaipuStep[] = [move(0, 3, 15, 'B'), move(1, 15, 3, 'W')];
const META = { player_black: '申真谞', player_white: '柯洁', handicap: 0, komi: 7.5, ruleset: 'chinese' };

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/kiosk/baipu/session/g1']}>
      <Routes>
        <Route path="/kiosk/baipu/session/:source" element={<BaipuSessionPage />} />
      </Routes>
    </MemoryRouter>,
  );

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  Element.prototype.scrollIntoView = vi.fn();   // jsdom 缺口,不是产品要绕的东西
  localStorage.setItem('baipu:sgf:g1', JSON.stringify({ id: 'g1', name: '三星杯', sgf: '(;SZ[19];B[pd];W[dp])', savedAt: 1 }));
  baipuLoad.mockResolvedValue({ board_size: 19, steps: STEPS, meta: META });
  baipuCapture.mockResolvedValue({ kind: 'disabled' });
  ledPoint.mockResolvedValue({ ok: true, connected: true });
});

describe('屏 17 摆谱 · 出口都回棋谱屏(K1)', () => {
  // `/kiosk/baipu` 那一页没有页控条、不在 Dock 词典里 ⇒ 盒上进去就出不来。
  it('退出确认里按「退出」回 /kiosk/kifu', async () => {
    renderPage();
    await screen.findByTestId('baipu-pcard');
    fireEvent.click(screen.getByRole('button', { name: /棋谱/ }));
    fireEvent.click(screen.getByTestId('baipu-exit-confirm-action'));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/kifu');
  });

  it('读谱失败时页控条返回回 /kiosk/kifu', async () => {
    baipuLoad.mockRejectedValue(new Error('baipu/load failed 422: bad'));
    renderPage();
    await screen.findByTestId('baipu-load-error');
    fireEvent.click(screen.getByRole('button', { name: /棋谱/ }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/kifu');
  });

  it('摆完按「完成」回 /kiosk/kifu,并清掉这份的进度', async () => {
    renderPage();
    await screen.findByTestId('baipu-pcard');
    fireEvent.click(screen.getByRole('button', { name: '确认落子' }));
    await waitFor(() => expect(screen.getByTestId('baipu-pcard')).toHaveTextContent('把白子放'));
    fireEvent.click(screen.getByRole('button', { name: '确认落子' }));
    await waitFor(() => expect(screen.getByTestId('baipu-pcard')).toHaveAttribute('data-mood', 'done'));
    fireEvent.click(screen.getByRole('button', { name: '完成' }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/kifu');
    expect(localStorage.getItem('baipu:progress:g1')).toBeNull();
  });
});
```

- [ ] **Step 2: 改另外三份单测的期望（先红）**

`src/kiosk/__tests__/KifuPage.test.tsx:115-119` 整条换成：

```tsx
  it('「摆到实体盘」展开名局搜索 —— 摆谱没有自己的选谱页,挑谱就在这儿', async () => {
    renderPage();
    fireEvent.click(screen.getByText('摆到实体盘').closest('button')!);
    expect(screen.getByTestId('kifu-search')).toBeInTheDocument();
    await waitFor(() => expect(getAlbums).toHaveBeenLastCalledWith({ q: undefined, page: 1, page_size: 6 }));
    expect(mockNavigate).not.toHaveBeenCalled();
  });
```

`src/kiosk/pages/TutorialCategoriesPage.test.tsx:185`：

```tsx
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/kifu');
```

`src/kiosk/__tests__/KioskApp.test.tsx`：在 `vi.mock('../pages/ReportsPage', …)` 那段下面加

```tsx
vi.mock('../pages/KifuPage', () => ({
  default: () => <h1>KIOSK_KIFU_PAGE</h1>,
}));
```

并在 `it('redirects /kiosk to /kiosk/play', …)` 之后加：

```tsx
  it('/kiosk/baipu 重定向到棋谱屏 —— 那一页没有任何出口,旧链接不许再落进去', () => {
    // token 给 null:盒上 token 恒为 null,守卫判的是 isAuthenticated。
    mockUseAuth.mockReturnValue({
      isAuthenticated: true, isLoading: false,
      user: { id: 1, username: '张三', rank: '2D', credits: 0 },
      login: vi.fn(), logout: vi.fn(), token: null,
    });
    renderApp('/kiosk/baipu');
    expect(screen.getByRole('heading', { name: 'KIOSK_KIFU_PAGE' })).toBeInTheDocument();
  });
```

- [ ] **Step 3: 跑一遍确认红**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu/katrain/web/ui
npx vitest run src/kiosk/__tests__/BaipuSessionPage.test.tsx src/kiosk/__tests__/KifuPage.test.tsx src/kiosk/pages/TutorialCategoriesPage.test.tsx src/kiosk/__tests__/KioskApp.test.tsx
```

Expected: FAIL —— 摆谱屏三条期望 `/kiosk/kifu` 实得 `/kiosk/baipu`；KifuPage 那条找不到 `kifu-search`；课程那条期望 `/kiosk/kifu`；KioskApp 那条找不到 `KIOSK_KIFU_PAGE`。

- [ ] **Step 4: 改实现**

`BaipuSessionPage.tsx` 四处 `navigate('/kiosk/baipu')` 全部换成 `navigate('/kiosk/kifu')`（`:334`、`:350`、`:554`、`:622`）：

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu/katrain/web/ui
sed -i '' "s#navigate('/kiosk/baipu')#navigate('/kiosk/kifu')#g" src/kiosk/pages/BaipuSessionPage.tsx
grep -c "navigate('/kiosk/kifu')" src/kiosk/pages/BaipuSessionPage.tsx   # 期望:4
```

`KifuPage.tsx:225-230` 那张卡换成：

```tsx
          <KioskCard
            title={t('kifu:place_on_board', '摆到实体盘')}
            sub={t('kifu:place_sub', '灯一手一手指着摆')}
            icon="grid-nine"
            // 摆谱没有自己的选谱页(2026-09-14 删了 `/kiosk/baipu`,那一页盒上进去出不来):
            // 挑谱就是在这儿搜,点进屏 16 再按「摆到实体盘」。所以这张卡**展开搜索**,不跳转。
            onClick={() => setSearchOpen(true)}
          />
```

`TutorialCategoriesPage.tsx:192`：`onClick={() => navigate('/kiosk/baipu')}` → `onClick={() => navigate('/kiosk/kifu')}`。

`KifuDetailPage.tsx:22`：`(逐手回放 / 摆到实体盘 / 去研究)现在散在 \`KifuPage\` 的预览栏和 \`BaipuListPage\` 里。` → `(逐手回放 / 摆到实体盘 / 去研究)原来散在 \`KifuPage\` 的预览栏和 \`BaipuListPage\`(2026-09-14 已删)里。`

`KioskApp.tsx`：删掉 `:56` 的 `import BaipuListPage from './pages/BaipuListPage';`；把 `:137-144` 的注释与 `baipu` 路由换成：

```tsx
          {/* ⚠️ research / live 两条**下了 Dock 但路由照旧存在**(规范 §3:研究并进复盘、直播并进棋谱)。
              `baipu` 这一条 2026-09-14 改成重定向:它原来挂的 `BaipuListPage` 是 7 月的选谱页,
              没有页控条、不在 Dock 词典里 ⇒ 盒上进去就出不来,而摆谱屏的返回 / 退出 / 完成、
              屏 15「摆到实体盘」、屏 23「去摆谱」全都指着它。选谱早被屏 15 搜索 + 屏 16 详情取代
              (稿子屏 15 注释:「摆到实体盘」和「导入 SGF」进的是同一条摆谱流程),
              所以删页,留一条重定向接住旧链接。 */}
          <Route path="research" element={<ResearchPage />} />
          <Route path="kifu" element={<KifuPage />} />
          <Route path="kifu/:kifuId" element={<KifuDetailPage />} />
          <Route path="baipu" element={<Navigate to="/kiosk/kifu" replace />} />
```

删页：

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu
git rm katrain/web/ui/src/kiosk/pages/BaipuListPage.tsx
rg -n "BaipuListPage" katrain/web/ui/src katrain/web/ui/tests   # 期望:只剩注释里的历史提法(KioskApp.tsx / KifuDetailPage.tsx)与下一步要删的那一行
```

- [ ] **Step 5: 改两份真浏览器闸与 e2e 里对死页的依赖**

`tests/kiosk-shell-contract.spec.ts`：删掉 `:192` 的 `'src/kiosk/pages/BaipuListPage.tsx', // (A) 摆谱屏`；在 `:172` 那段（`2026-08-24 屏 17 摆谱重画…`）结尾之后追加一行注释：

```ts
//      2026-09-14 `/kiosk/baipu` 改成重定向到棋谱屏:`BaipuListPage.tsx` 整个文件删了(K1)。
```

`tests/kiosk-shell-geometry.spec.ts`：
- `:1277` `// ── D2 稿外五屏:只接壳,不推导版式 ───…` → `// ── D2 稿外几屏:只接壳,不推导版式 ───…`
- `:1280` ` * 摆谱 / 直播 / 研究 / 跨平台 / 标定 —— 稿子没画这五屏。**没有参照物就没有四图闸**,` → ` * 直播 / 研究 / 跨平台 / 标定 —— 稿子没画这几屏。**没有参照物就没有四图闸**,`，并在这一行下面加 ` * (摆谱选谱页 \`/kiosk/baipu\` 2026-09-14 改成重定向到棋谱屏 —— 它不再是一屏,从名单里拿掉。)`
- `:1283`、`:1286`、`:1322` 三处「这五屏」→「这几屏」
- 删掉 `D2_SCREENS` 里的 `['/kiosk/baipu', '摆谱'],`

`tests/baipu.spec.ts`：
- `:122` `await expect(page).toHaveURL(/\/kiosk\/baipu$/);` → `await expect(page).toHaveURL(/\/kiosk\/kifu$/);`
- 第一条用例 `:88` `await expect(page.getByRole('button', { name: '完成' })).toBeEnabled();` 之后加：

```ts
    // 「完成」回棋谱屏(K1)—— 以前回的 `/kiosk/baipu` 没有任何出口。
    await page.getByRole('button', { name: '完成' }).click();
    await expect(page).toHaveURL(/\/kiosk\/kifu$/);
```

- [ ] **Step 6: 跑测试确认绿**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu/katrain/web/ui
npx vitest run src/kiosk/__tests__/BaipuSessionPage.test.tsx src/kiosk/__tests__/KifuPage.test.tsx src/kiosk/pages/TutorialCategoriesPage.test.tsx src/kiosk/__tests__/KioskApp.test.tsx
npx tsc -b && echo TSC_OK
npx playwright test --config=playwright.visual.config.ts tests/kiosk-shell-contract.spec.ts tests/kiosk-shell-geometry.spec.ts -g "D2 |图标不许"
cp ~/.katrain/config.json "$HOME/.cache/kiosk-go-kifu/baseline/config.json.t1" 2>/dev/null || true
npm run build && npx playwright test tests/baipu.spec.ts
cp "$HOME/.cache/kiosk-go-kifu/baseline/config.json.t1" ~/.katrain/config.json 2>/dev/null || true
```

Expected: vitest 四个文件 PASS；`TSC_OK`；契约闸与 D2 四屏 PASS；`baipu.spec.ts` 全部 PASS（含退出落 `/kiosk/kifu`、完成落 `/kiosk/kifu`）。

- [ ] **Step 7: 取一张真运行时截图给 Fan 过目（相称性：纯导航改动，不做四图）**

⚠️ 不要在裸 `npm run dev` 上手点：vite 把 `/api` 代理到 :8001，视觉这一套不起后端 ⇒ 屏 16 读不到谱、`auth/me` 不通，走不到摆谱屏。用一份**临时、不进仓**的 spec 桩掉接口取图（`--config=playwright.visual.config.ts` 会自己起 :5173）。先 `git ls-files katrain/web/ui/tests/tmp-kifu-shots.spec.ts` 确认为空，再建：

```ts
// 临时取图脚本 —— 不 git add,Task 5 Step 7 用完删掉。
import { test, type Page } from '@playwright/test';
import { KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
const OUT = `${process.env.HOME}/.cache/kiosk-go-kifu`;
const STEPS = (size: number) => ({
  board_size: size,
  meta: { player_black: '申真谞', player_white: '柯洁', handicap: 0, komi: 7.5, ruleset: 'chinese' },
  steps: [{ kind: 'move', move_index: 0, property: 'B', row: 3, col: 3, color: 'B', removed: [], board_hash: 'h0' }],
});

const boot = async (page: Page, size: number) => {
  await stubBackendStatics(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'shot');
    localStorage.setItem('katrain_language', 'cn');
    localStorage.setItem('baipu:sgf:s1', JSON.stringify({ id: 's1', name: '三星杯半决赛', sgf: '(;SZ[19];B[pd])', savedAt: 1 }));
  });
  await page.route('**/api/v1/auth/me', (r) => r.fulfill({ json: { id: 1, username: '访客', rank: '5段', credits: 0 } }));
  await page.route('**/api/v1/geometry/status', (r) => r.fulfill({ json: {
    phase: 'disabled', session_calibrated: false, last_error: null,
    capabilities: { camera_ready: false, led_ready: false, geometry_ready: false, recognition_ready: false },
  } }));
  await page.route('**/api/v1/baipu/mode', (r) => r.fulfill({ json: { collect: false } }));
  await page.route('**/api/v1/baipu/load', (r) => r.fulfill({ json: STEPS(size) }));
  await page.route('**/api/v1/led/**', (r) => r.fulfill({ json: { ok: true, connected: true, shown_at: null, errors: [] } }));
  await page.route('**/api/v1/kifu/albums*', (r) => r.fulfill({ json: { items: [], total: 0, page: 1, page_size: 1 } }));
  await page.route('**/live/matches*', (r) => r.fulfill({ json: { matches: [], live_count: 0, total: 0 } }));
};

test('K1 退出落在棋谱屏', async ({ page }) => {
  await boot(page, 19);
  await page.goto('/kiosk/baipu/session/s1');
  await page.getByRole('button', { name: /棋谱/ }).click();
  await page.getByTestId('baipu-exit-confirm-action').click();
  await page.waitForURL(/\/kiosk\/kifu$/);
  await page.waitForSelector('.kiosk-dock');
  await page.screenshot({ path: `${OUT}/k1-exit-to-kifu.png` });
});
```

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu/katrain/web/ui
npx playwright test --config=playwright.visual.config.ts tests/tmp-kifu-shots.spec.ts -g K1
```

把 `$HOME/.cache/kiosk-go-kifu/k1-exit-to-kifu.png`（应是带 Dock 的棋谱屏）附在交付说明里。这份临时 spec 留到 Task 5 Step 7 再用，**Step 8 不要 add 它**。

- [ ] **Step 8: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu
git add katrain/web/ui/src/kiosk/KioskApp.tsx katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx \
  katrain/web/ui/src/kiosk/pages/KifuPage.tsx katrain/web/ui/src/kiosk/pages/TutorialCategoriesPage.tsx \
  katrain/web/ui/src/kiosk/pages/KifuDetailPage.tsx \
  katrain/web/ui/src/kiosk/__tests__/BaipuSessionPage.test.tsx katrain/web/ui/src/kiosk/__tests__/KifuPage.test.tsx \
  katrain/web/ui/src/kiosk/pages/TutorialCategoriesPage.test.tsx katrain/web/ui/src/kiosk/__tests__/KioskApp.test.tsx \
  katrain/web/ui/tests/baipu.spec.ts katrain/web/ui/tests/kiosk-shell-contract.spec.ts katrain/web/ui/tests/kiosk-shell-geometry.spec.ts
git diff --cached --stat     # 期望:含 BaipuListPage.tsx 的删除与 BaipuSessionPage.test.tsx 的新增
git commit -m "fix(kiosk-go): 摆谱结束后落进没有出口的 /kiosk/baipu —— 五处入口改回棋谱屏,旧页删掉留重定向(K1)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: K4 前端 · 上线态摆谱不拍照、不先标定

**Files:**
- Modify: `katrain/web/ui/src/api/baipuApi.ts:75-132`（`BaipuMode` 类型 + `BaipuAPI.mode()`）
- Create: `katrain/web/ui/src/kiosk/pages/BaipuSessionRoute.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx:57,145`（行号是 `6f7dc629` 上的；Task 1 改过这个文件后会偏移 1–3 行，**按下文引用的原文定位**，本计划所有行号同此口径）
- Modify: `katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx:53-58,116,210-225,263-268,402-405,440,462-498,520-531,575`
- Modify: `katrain/web/ui/src/api/baipuApi.test.ts`（加 `mode()` 两条）
- Create: `katrain/web/ui/src/kiosk/__tests__/BaipuSessionRoute.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/BaipuSessionPage.test.tsx`（`renderPage` 收 `collect`，加 K4 三条）
- Modify: `katrain/web/ui/tests/baipu.spec.ts:30-55` 及四条采集用例
- Modify: `katrain/web/ui/tests/kiosk-shell-scroll.spec.ts:1185-1210,1261,1279`

**Interfaces:**
- Consumes: Task 1 的 `BaipuSessionPage.test.tsx` 夹具（`renderPage`、`move`、`STEPS`、`META`、`baipuCapture`、`mockNavigate`）
- Produces:
  - `export interface BaipuMode { collect: boolean }`（`src/api/baipuApi.ts`）
  - `BaipuAPI.mode(): Promise<BaipuMode>` —— 永不 reject；非 200 / 网络错 / `collect !== true` 一律 `{ collect: false }`
  - `default export function BaipuSessionRoute(): JSX.Element`（`src/kiosk/pages/BaipuSessionRoute.tsx`）
  - `BaipuSessionPage` 签名变为 `({ collect }: { collect: boolean }) => JSX.Element`
  - 上线态折叠块 `data-testid="baipu-led-fold"`；采集态沿用 `baipu-cam-fold`
  - HTTP 契约（Task 4 实现）：`GET /api/v1/baipu/mode` → `{"collect": boolean}`

- [ ] **Step 1: 写失败的单测**

`src/api/baipuApi.test.ts` 末尾追加：

```ts
describe('摆谱拍不拍照:BaipuAPI.mode()', () => {
  it('后端明说 collect:true 才是采集态', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ collect: true }), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    })));
    expect(await BaipuAPI.mode()).toEqual({ collect: true });
  });

  // 猜成「拍」的代价:盒上每一手都可能被几何 / 灯的 409 卡住;猜成「不拍」的代价:
  // 采数据的人一眼看见屏上没有「已采集 N 帧」。所以问不到一律当「不拍」。
  it('问不到一律当不拍:旧后端 404 / 网络错 / 不认识的回包', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"detail":"Not Found"}', { status: 404 })));
    expect(await BaipuAPI.mode()).toEqual({ collect: false });
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    expect(await BaipuAPI.mode()).toEqual({ collect: false });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ collect: 'yes' }), { status: 200 })));
    expect(await BaipuAPI.mode()).toEqual({ collect: false });
  });
});
```

新建 `src/kiosk/__tests__/BaipuSessionRoute.test.tsx`（先 `git ls-files` 确认不存在）：

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import BaipuSessionRoute from '../pages/BaipuSessionRoute';

const { modeMock } = vi.hoisted(() => ({ modeMock: vi.fn() }));
vi.mock('../../api/baipuApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/baipuApi')>();
  return { ...actual, BaipuAPI: { ...actual.BaipuAPI, mode: modeMock } };
});
vi.mock('../pages/BaipuSessionPage', () => ({
  default: ({ collect }: { collect: boolean }) => <div data-testid="session" data-collect={String(collect)} />,
}));
vi.mock('../components/vision/PhysicalBoardGuard', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div data-testid="guard">{children}</div>,
}));

const renderRoute = () => render(<MemoryRouter><BaipuSessionRoute /></MemoryRouter>);

beforeEach(() => { vi.clearAllMocks(); });

describe('摆谱入口:拍不拍照决定要不要先标定(K4)', () => {
  it('上线态不套标定守卫 —— 只用灯,灯的行列换算不需要摄像头', async () => {
    modeMock.mockResolvedValue({ collect: false });
    renderRoute();
    expect(await screen.findByTestId('session')).toHaveAttribute('data-collect', 'false');
    expect(screen.queryByTestId('guard')).toBeNull();
  });

  it('采集态照旧先过标定守卫 —— 拍照要几何锁', async () => {
    modeMock.mockResolvedValue({ collect: true });
    renderRoute();
    expect(await screen.findByTestId('session')).toHaveAttribute('data-collect', 'true');
    expect(screen.getByTestId('guard')).toBeInTheDocument();
  });

  it('还没问到时屏上有页控条 —— 不许再造一块没有出口的屏', () => {
    modeMock.mockReturnValue(new Promise(() => {}));
    renderRoute();
    expect(screen.getByTestId('baipu-pagebar')).toBeInTheDocument();
  });
});
```

`src/kiosk/__tests__/BaipuSessionPage.test.tsx`：把 `renderPage` 换成收 `collect`（默认上线态），并追加一组：

```tsx
const renderPage = (collect = false) =>
  render(
    <MemoryRouter initialEntries={['/kiosk/baipu/session/g1']}>
      <Routes>
        <Route path="/kiosk/baipu/session/:source" element={<BaipuSessionPage collect={collect} />} />
      </Routes>
    </MemoryRouter>,
  );
```

```tsx
describe('屏 17 摆谱 · 上线态不拍照(K4,Fan 2026-09-14)', () => {
  it('确认落子只推进:一次 /capture 都不发(开局帧也不拍),屏上没有「帧 / 拍照 / 摄像头」', async () => {
    renderPage(false);
    await screen.findByTestId('baipu-pcard');
    fireEvent.click(screen.getByRole('button', { name: '确认落子' }));
    await waitFor(() => expect(screen.getByTestId('baipu-pagebar')).toHaveTextContent('第 2 / 2 手'));
    expect(baipuCapture).not.toHaveBeenCalled();
    expect(screen.getByTestId('baipu-led-fold')).toHaveTextContent('红灯 = 放黑子');
    expect(screen.queryByTestId('baipu-cam-fold')).toBeNull();
    expect(screen.getByTestId('baipu-session-page').textContent).not.toMatch(/帧|拍照|摄像头/);
  });

  it('提子那一手:「已移除」之后照样只推进,不拍照', async () => {
    baipuLoad.mockResolvedValue({
      board_size: 19, meta: META,
      steps: [move(0, 3, 15, 'B'), { ...move(1, 0, 0, 'W'), removed: [{ row: 3, col: 15 }] }],
    });
    renderPage(false);
    await screen.findByTestId('baipu-pcard');
    fireEvent.click(screen.getByRole('button', { name: '确认落子' }));
    await waitFor(() => expect(screen.getByTestId('baipu-pcard')).toHaveTextContent('把白子放'));
    fireEvent.click(screen.getByRole('button', { name: '确认落子' }));
    await waitFor(() => expect(screen.getByTestId('baipu-pcard')).toHaveAttribute('data-mood', 'removal'));
    fireEvent.click(screen.getByRole('button', { name: '已移除 1 子' }));
    await waitFor(() => expect(screen.getByTestId('baipu-pcard')).toHaveAttribute('data-mood', 'done'));
    expect(baipuCapture).not.toHaveBeenCalled();
  });

  it('采集态一个字没变:开局帧照拍,确认落子发 /capture', async () => {
    baipuCapture.mockResolvedValue({ kind: 'ok', result: { ok: true, path: '/c/g1/frame_001.jpg' } });
    renderPage(true);
    await screen.findByTestId('baipu-pcard');
    await waitFor(() => expect(baipuCapture).toHaveBeenCalledWith(expect.objectContaining({ move_index: -1 })));
    fireEvent.click(screen.getByRole('button', { name: '确认落子' }));
    await waitFor(() => expect(baipuCapture).toHaveBeenCalledWith(expect.objectContaining({ move_index: 0 })));
    expect(screen.getByTestId('baipu-cam-fold')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 跑一遍确认红**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu/katrain/web/ui
npx vitest run src/api/baipuApi.test.ts src/kiosk/__tests__/BaipuSessionRoute.test.tsx src/kiosk/__tests__/BaipuSessionPage.test.tsx
```

Expected: FAIL —— `BaipuAPI.mode is not a function`；`BaipuSessionRoute` 模块不存在；上线态两条里 `baipuCapture` 被调用、`baipu-led-fold` 不存在。

- [ ] **Step 3: `baipuApi.ts` 加 `mode()`**

在 `export type BaipuCaptureOutcome = …`（`:75-78`）之后加：

```ts
/** 这台机器摆谱时拍不拍照。见 `BaipuAPI.mode`。 */
export interface BaipuMode {
  collect: boolean;
}
```

在 `BaipuAPI` 对象里 `capture` 之后（`:131` 那个 `},` 后面）加：

```ts
  /**
   * 摆谱拍不拍照(`GET /baipu/mode`)。拍照只为采 YOLO 训练数据,上线版不拍(Fan 2026-09-14)。
   * **问不到一律当「不拍」**:旧后端没这个端点(404)、网络错、回包不认识,全落到上线态。
   * 猜成「拍」的代价是盒上每一手都可能被几何 / 灯的 409 卡住;猜成「不拍」的代价是
   * 采数据的人一眼看见屏上没有「已采集 N 帧」。
   * ⚠️ 不要拿 `/capture` 回不回 404 去猜:盒子为了几何标定总是带着 `--capture-camera` 起。
   */
  mode: async (): Promise<BaipuMode> => {
    try {
      const response = await fetch(`${API_BASE}/mode`);
      if (!response.ok) return { collect: false };
      const body = await response.json().catch(() => null);
      return { collect: body?.collect === true };
    } catch {
      return { collect: false };
    }
  },
```

- [ ] **Step 4: 新建 `BaipuSessionRoute.tsx`**

```tsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BaipuAPI } from '../../api/baipuApi';
import { useTranslation } from '../../hooks/useTranslation';
import PhysicalBoardGuard from '../components/vision/PhysicalBoardGuard';
import { KioskPagebar } from '../shell/KioskPagebar';
import BaipuSessionPage from './BaipuSessionPage';

/**
 * `/kiosk/baipu/session/:source` 的入口:先问这台机器摆谱拍不拍照,再决定要不要先标定。
 *
 * - **上线态(`collect=false`,盒子默认)**:不套 `PhysicalBoardGuard`。摆谱只用灯,灯的
 *   (行,列)→灯珠是公式 LUT,不需要摄像头。以前这条路由无条件套守卫 ⇒ 服务每次重启
 *   `session_calibrated=false`,不先标定摄像头就进不了摆谱,而上线版摆谱根本不用摄像头。
 * - **采集态(`collect=true`,`--baipu-collect` 起的采集机)**:照旧先过守卫 —— 拍照要几何锁。
 *
 * 守卫必须包在**页面外面**、不能挪进页面里:页面挂着时它的效应会点灯,而标定台也在点灯。
 * 还没问到时也给页控条:这一屏不许再是一块没有出口的屏(K1 修的就是这个)。
 */
export default function BaipuSessionRoute() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [collect, setCollect] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    void BaipuAPI.mode().then((m) => { if (!cancelled) setCollect(m.collect); });
    return () => { cancelled = true; };
  }, []);

  if (collect === null) {
    return (
      <div className="kiosk-layout-b" data-testid="baipu-session-page">
        <KioskPagebar
          testId="baipu-pagebar"
          backLabel={t('baipu:back_kifu', '棋谱')}
          onBack={() => navigate('/kiosk/kifu')}
          title={t('baipu:title', '摆谱')}
        />
        <div className="empty" data-testid="baipu-loading"><h4>{t('baipu:loading', '正在读这份谱')}</h4></div>
      </div>
    );
  }
  if (!collect) return <BaipuSessionPage collect={false} />;
  return (
    <PhysicalBoardGuard sub={t('baipu:guard_sub_collect', '采集训练数据要先让摄像头看清盘面')}>
      <BaipuSessionPage collect />
    </PhysicalBoardGuard>
  );
}
```

`KioskApp.tsx`：`:57` `import BaipuSessionPage from './pages/BaipuSessionPage';` → `import BaipuSessionRoute from './pages/BaipuSessionRoute';`；`:145` 整行 →

```tsx
          <Route path="baipu/session/:source" element={<BaipuSessionRoute />} />
```

（`PhysicalBoardGuard` 的 import 保留：做题路由 `:132` 还在用。）

- [ ] **Step 5: `BaipuSessionPage.tsx` 按 `collect` 分两态（逐块替换，其余一个字不动）**

(a) 头注 `:56-58` 三行：

```tsx
 * **这一屏的主角不在屏幕上,在实体盘上。** 灯点着下一手该落哪儿,人把子摆上去,摄像头采一帧
 * (那些帧是 YOLO 的训练数据)。提子要人**自己**把死子拿下来;拍照那一刻手不能在盘上。
 * 屏幕在这儿只是副驾 —— 所以右栏第一块不是棋谱也不是记账,是「**现在轮到你摆哪一颗**」。
```

换成：

```tsx
 * **这一屏的主角不在屏幕上,在实体盘上。** 灯点着下一手该落哪儿,人把子摆上去,按一下确认。
 * 提子要人**自己**把死子拿下来。屏幕在这儿只是副驾 —— 所以右栏第一块不是棋谱也不是记账,
 * 是「**现在轮到你摆哪一颗**」。
 *
 * ## 两态:上线态不拍照,采集态拍(2026-09-14,Fan 纠正)
 *
 * 「拍照」只为收集 YOLO 训练数据,上线版不需要。`collect` 由 `BaipuSessionRoute` 问
 * `GET /api/v1/baipu/mode` 得来(问不到 = `false`):
 *  · `collect=false`(上线态,盒子默认):确认只推进,不发 `/capture`、不拍开局帧、不响快门;
 *    摄像头那块换成「灯 · 颜色对照」(同样三行,右栏的账不变);确认键图标不画相机。
 *  · `collect=true`(`--baipu-collect` 起的采集机):下面写的这一整页原样 —— 拍照那一刻手不能
 *    在盘上,那些帧是训练数据。
 * ⚠️ 判别位只有 `collect`。盒子为了几何标定总是带着 `--capture-camera` 起,
 *    「有采集服务」**不等于**「要拍照」。
```

(b) `:116` `const BaipuSessionPage = () => {` → `const BaipuSessionPage = ({ collect }: { collect: boolean }) => {`

(c) `:210-212` 与 `:225`：

```tsx
  // 开局那一帧(空盘 + 全灯):尽力而为,失败不拦路。**只有采集态拍。**
  useEffect(() => {
    if (collect && phase === 'guiding' && k === 0 && resumePrompt === null && !initialCapturedRef.current && sgf && steps.length > 0) {
```

依赖数组 `}, [phase, k, resumePrompt, sgf, source, steps.length, overwriteExisting]);` → `}, [collect, phase, k, resumePrompt, sgf, source, steps.length, overwriteExisting]);`

(d) `:263-268` `handleConfirm` 整个换成：

```tsx
  const handleConfirm = () => {
    if (!currentStep) return;
    // 提子要人先把死子拿下来,拿完才存帧 —— 否则那一帧上是一个不该存在的局面。
    if (currentStep.removed.length > 0 && phase === 'guiding') { setPhase('await_removal'); return; }
    if (collect) void doCapture(k); else advance();
  };
```

(e) `:402-405` 页控条副标题：

```tsx
          sub={interpolate(
            collect
              ? t('baipu:pagebar_sub', '第 {i} / {n} 手 · 已采集 {f} 帧')
              : t('baipu:pagebar_sub_placed', '第 {i} / {n} 手'),
            { i: Math.min(k + (phase === 'done' ? 0 : 1), steps.length), n: steps.length, f: frameCount },
          )}
```

(f) `:440` 摆完那句：

```tsx
                <p>{collect
                  ? interpolate(t('baipu:done_hint', '一共 {n} 手 · 采到 {f} 帧'), { n: steps.length, f: frameCount })
                  : interpolate(t('baipu:done_hint_placed', '一共 {n} 手'), { n: steps.length })}</p>
```

(g) `:462-498` 摄像头折叠块：把注释行 `{/* ── 摄像头 ── 这本账既是采集记录,也是那条 LED 图例的落点 */}` 换成 `{/* ── 摄像头(采集态)/ 灯(上线态)── 这本账也是那条 LED 图例的落点 */}`；在原 `<KioskFold fold="cam" …>` 前插入 `{collect ? (`，原 `</KioskFold>`（`:498`）之后接：

```tsx
        ) : (
          /* 上线态没有摄像头这回事。**行数和采集态一样是三行** —— 右栏的账是死的(页头「四条通栏横幅一条都不进右栏」那段),
             这一块一变高就压着法表。图例文案沿用那三句,色点仍是灯的真值。 */
          <KioskFold
            fold="led"
            testId="baipu-led-fold"
            title={t('baipu:led_title', '灯 · 颜色对照')}
            value={t('baipu:led_value', '摆好再按确认')}
            bodyClassName="ledger"
          >
            <div className="lrow">
              <b>{t('baipu:legend_black', '红灯 = 放黑子')}</b>
              <span className="led" style={{ background: LED_HEX.black }} aria-hidden="true" />
            </div>
            <div className="lrow">
              <b>{t('baipu:legend_white', '绿灯 = 放白子')}</b>
              <span className="led" style={{ background: LED_HEX.white }} aria-hidden="true" />
            </div>
            <div className="lrow">
              <b>{t('baipu:legend_remove', '蓝灯 = 该拿走')}</b>
              <span className="led" style={{ background: LED_HEX.remove }} aria-hidden="true" />
            </div>
          </KioskFold>
        )}
```

(h) `:520-531` 动作区前两格：

```tsx
            mood === 'removal'
              ? {
                key: 'removed',
                // 相机图标只在真拍照时出现 —— 上线态画个相机,等于屏上说「这一下要拍照」。
                icon: collect ? 'camera' : 'hand-pointing',
                label: interpolate(t('baipu:removed_done', '已移除 {n} 子'), { n: currentStep?.removed.length ?? 0 }),
                disabled: capturePending,
                onClick: () => { if (collect) void doCapture(k); else advance(); },
              }
              : {
                key: 'confirm',
                icon: collect ? 'camera' : 'hand-pointing',
```

（`label` / `disabled` / `reason` / `onClick: handleConfirm` 往下原样。）

(i) `:575` 接着摆弹窗正文：

```tsx
            <p>{interpolate(
              collect
                ? t('baipu:resume_body', '上次摆到第 {n} 手。重新开始会覆盖已经采过的帧。')
                : t('baipu:resume_body_placed', '上次摆到第 {n} 手。从头摆要先把盘上的子都拿下来。'),
              { n: resumePrompt },
            )}</p>
```

- [ ] **Step 6: 单测转绿、类型检查**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu/katrain/web/ui
npx vitest run src/api/baipuApi.test.ts src/kiosk/__tests__/BaipuSessionRoute.test.tsx src/kiosk/__tests__/BaipuSessionPage.test.tsx src/kiosk/__tests__/KioskApp.test.tsx
npx tsc -b && echo TSC_OK
rg -n "collect" src/kiosk/pages/BaipuSessionPage.tsx | wc -l   # 回读:应 ≥ 12 处,确认 (a)–(i) 都落了
```

Expected: 全部 PASS（含 Task 1 的三条 K1 用例，它们现在走上线态）；`TSC_OK`。

- [ ] **Step 7: e2e 与真浏览器闸挂上 `mode` 桩**

`tests/baipu.spec.ts`：
- 头注末尾加一段：

```ts
 *
 * ⚠️ **2026-09-14 摆谱分两态**(Fan:拍照只为采训练数据,上线版不拍)。`setupSession` 默认挂
 * `/baipu/mode → {collect:false}`(上线态:不发 `/capture`);要测拍照的四条用例自己再挂
 * `collectMode(page)`。这份跑在 :8002 真后端上,那台没起采集服务 ⇒ geometry 404 ⇒ 守卫放行。
```

- `setupSession` 里 `/baipu/load` 那行之后加：

```ts
  await page.route('**/api/v1/baipu/mode', (route) => route.fulfill({ json: { collect: false } }));
```

- 删掉 `captureDisabled` 函数（`:49-55`）和它的四处调用；在它原来的位置放：

```ts
// 采集态(`--baipu-collect` 起的采集机)。Playwright 后挂的 route 先匹配,盖过 setupSession 那条。
async function collectMode(page: Page) {
  await page.route('**/api/v1/baipu/mode', (route) => route.fulfill({ json: { collect: true } }));
}
```

- 第一条用例 `guides through moves, removal, and completion`：`await setupSession(page);` 之后加

```ts
    const captures: string[] = [];
    page.on('request', (r) => { if (r.url().includes('/api/v1/baipu/capture')) captures.push(r.url()); });
```

  在 `await expect(page.getByRole('button', { name: '完成' })).toBeEnabled();` 之后、Task 1 加的「完成」点击之前加 `expect(captures, '上线态一次都不许拍照').toEqual([]);`
- `operator confirmation captures once…`、`legacy mismatch response…`、`capture failure keeps…`、`restart uses same directory…` 四条：`await setupSession(page);` 之后各加 `await collectMode(page);`

`tests/kiosk-shell-scroll.spec.ts` 的 `bootBaipu`（`:1185`）签名与开头换成：

```ts
const bootBaipu = async (page: Page, opts: { capture?: 'ok' | 'fail' | 'hang'; collect?: boolean } = {}) => {
  // 上线态(默认)不拍照、不套标定守卫;采集失败 / 拍照遮罩那两态要显式 `collect: true`。
  await page.route('**/api/v1/baipu/mode', (route) => route.fulfill({ json: { collect: opts.collect ?? false } }));
  if (opts.collect) {
    // 采集态外面套着 `PhysicalBoardGuard`:不桩 geometry,vite 代理连不上 :8001 ⇒ phase 停在 required
    // ⇒ 整屏换成标定台。以前这几条绿不绿取决于 :8001 在不在(§33 那条「闸绿取决于另一个进程」)。
    await page.route('**/api/v1/geometry/status', (route) => route.fulfill({
      json: {
        phase: 'disabled', session_calibrated: false, last_error: null,
        capabilities: { camera_ready: false, led_ready: false, geometry_ready: false, recognition_ready: false },
      },
    }));
  }
```

（下面 `/baipu/load`、`/led/**`、`/baipu/capture` 三条 route 与后续原样。）`:1261` `bootBaipu(page, { capture: 'fail' })` → `bootBaipu(page, { capture: 'fail', collect: true })`；`:1279` `bootBaipu(page, { capture: 'hang' })` → `bootBaipu(page, { capture: 'hang', collect: true })`。

- [ ] **Step 8: 跑 e2e 与承重闸**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu/katrain/web/ui
npx playwright test --config=playwright.visual.config.ts tests/kiosk-shell-scroll.spec.ts -g "摆谱"
npx playwright test --config=playwright.visual.config.ts tests/kiosk-shell-geometry.spec.ts -g "屏 17"
cp ~/.katrain/config.json "$HOME/.cache/kiosk-go-kifu/baseline/config.json.t2" 2>/dev/null || true
npm run build && npx playwright test tests/baipu.spec.ts
cp "$HOME/.cache/kiosk-go-kifu/baseline/config.json.t2" ~/.katrain/config.json 2>/dev/null || true
```

Expected: 摆谱三条承重闸 PASS（第一条现在跑的是上线态，241 手、右栏 516、动作区贴底、着法块 ≥3 行；后两条跑采集态）；屏 17 顶栏闸 PASS；`baipu.spec.ts` 全 PASS（上线态零 capture 请求；采集态四条照旧）。

- [ ] **Step 9: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu
git add katrain/web/ui/src/api/baipuApi.ts katrain/web/ui/src/api/baipuApi.test.ts \
  katrain/web/ui/src/kiosk/pages/BaipuSessionRoute.tsx katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx \
  katrain/web/ui/src/kiosk/KioskApp.tsx \
  katrain/web/ui/src/kiosk/__tests__/BaipuSessionRoute.test.tsx katrain/web/ui/src/kiosk/__tests__/BaipuSessionPage.test.tsx \
  katrain/web/ui/tests/baipu.spec.ts katrain/web/ui/tests/kiosk-shell-scroll.spec.ts
git diff --cached --stat     # 期望:BaipuSessionRoute.tsx 与 BaipuSessionRoute.test.tsx 两个新文件都在
git commit -m "feat(kiosk-go): 上线版摆谱不拍照 —— 先问 /baipu/mode,上线态只推进、不先标定摄像头(K4 前端)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: K4 视觉关卡 · 屏 17 上线态四图 + 承重复核（**停下等 Fan 确认**）

**Files:**
- Modify: `katrain/web/ui/tests/kiosk-screen-17-baipu.fourup.spec.ts:27-35`（头注）、`:65-104`（`boot` 里的桩）、`:136-139`（实现图标签带）
- Regenerate: `superpowers/tracks/kiosk-go-shell-align/visual/17-baipu/1024x600/17-baipu--{reference,implementation,side-by-side,diff}.png`

**Interfaces:**
- Consumes: Task 2 的上线态 UI（`baipu-led-fold`、页控条副标题 `第 i / n 手`、`hand-pointing` 图标）
- Produces: 屏 17 上线态四图 + 三个边缘计数；Fan 的明确确认（Task 4 的前置条件）

- [ ] **Step 1: 四图脚本钉死上线态**

头注 `:27-34`（「其余预期差异」那一组）末尾、`:34` 之后加一条：

```ts
 *  · **2026-09-14 起取的是上线态**(Fan:拍照只为采 YOLO 训练数据,上线版不拍)。稿子那块
 *    「摄像头 · 这一手要采一帧 / 已采集 12 帧 / 最近保存」整块换成「灯 · 颜色对照」三行;
 *    页控条副标题不写帧数;「确认落子」图标是 hand-pointing。采集态不取四图(只在采集机上出现)。
```

`boot` 里 geometry 那段注释第一行 `// ⚠️ **这条不是装饰,是这一屏的四图能不能自己站住的前提。**` 之后加一行：

```ts
  // (2026-09-14 起只有采集态套守卫;上线态这条桩不再是前提,留着:mode 桩哪天被误删、页面退回采集态时,不至于整屏换成标定台。)
```

把 `:96-99` 这段

```ts
  // 采集在这台机器上是通的:回一份成功,好让「已采集 N 帧 / 最近保存」有真数。
  await page.route('**/api/v1/baipu/capture', (route) => route.fulfill({
    json: { path: '/data/baipu/s1/move_012.jpg', geometry_correction: null },
  }));
```

换成：

```ts
  // 取的是**上线态**(盒子默认)。钉死 `collect:false`:不让这张图随 :8001 上起的是不是采集机而变 ——
  // 与上面 `geometry/status` 那条同一个判据(一张随后端在不在而变的实现图,不是这一屏的实现图)。
  await page.route('**/api/v1/baipu/mode', (route) => route.fulfill({ json: { collect: false } }));
```

实现图标签带 `:136-139` 这四行

```ts
      + '**「已采集 13 帧」比稿子多一帧,是稿子少算了**:数据契约写着 '
      + '`frames.length = 1(开局空盘那帧) + 非 pass 落子数`，摆到第 13 手 = 1 + 12 = 13 · '
      + '「最近保存」印的是**文件名**不是稿子那句「第 12 手」——盘前的人要拿它去磁盘上对，'
      + '而手数在同一块账的第一行已经有了',
```

换成：

```ts
      + '**上线态不拍照(Fan 2026-09-14:拍照只为采 YOLO 训练数据)**:'
      + '稿子「摄像头 · 这一手要采一帧 / 已采集 12 帧 / 最近保存」整块换成「灯 · 颜色对照 / 摆好再按确认」，'
      + '同样三行，右栏的账不变 · 页控条副标题只写「第 13 / 241 手」，不写帧数 · '
      + '「确认落子」图标是 hand-pointing 不是相机——上线态画相机等于屏上说「这一下要拍照」',
```

- [ ] **Step 2: 取图（跑两遍，第二遍给本屏自己的抖动底噪）**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu/katrain/web/ui
npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-17-baipu.fourup.spec.ts 2>&1 | grep "fourup 17-baipu"
cp ../../../superpowers/tracks/kiosk-go-shell-align/visual/17-baipu/1024x600/17-baipu--implementation.png "$HOME/.cache/kiosk-go-kifu/impl-run1.png"
npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-17-baipu.fourup.spec.ts 2>&1 | grep "fourup 17-baipu"
```

Expected: 两遍都打印 `[fourup 17-baipu] both=… refOnly=… implOnly=…`，且两遍三个数相差在几百以内（屏 17 的盘是 SVG，底噪 ~200 像素量级）。旧值 `both=41734 refOnly=23971 implOnly=24577`（scope §22）；只改了右栏三行文字与一个图标，三个数应**同一量级**、不会变一个量级。若量级变了，先打开 diff 图看红绿是不是聚在右栏折叠块 / 页控条 / 动作区第一格，再往下走。

- [ ] **Step 3: 四图逐项比对并记录**

打开 `superpowers/tracks/kiosk-go-shell-align/visual/17-baipu/1024x600/` 的四张图，逐项写下（写进交付说明，不写报告文件）：
构图（左盘 516 + 16 + 右栏 460 未变）· 几何间距（折叠块头高、三行 ledger 行距与采集态一致）· 组件层级（页控条 → pcard → 灯折叠块 → 着法块 → 动作区）· 字体 / 色彩（`.lrow b` 衬线 13px；三颗色点红 / 绿 / 蓝与 `LED_HEX` 一致）· 图标（第一格 hand-pointing）· 文案（与标签带所列偏离一一对上，没有标签带以外的偏离）· 状态语义（盘上候选圈仍红色 = 黑棋）。

- [ ] **Step 4: 承重结构复核（反查 + 复用既有真浏览器闸）**

反查：把 Task 2 的 (e)(g)(h) 撤回去，页面上有没有元素的高度来源或裁切边界会变？折叠块三行换三行（`.lrow` 行高由 `b` 决定，采集态同样有 `b`）、副标题单行变短、图标同尺寸 ⇒ **不触发新测量**。既有闸就量在这条链上，Task 2 Step 8 已在上线态跑绿；把那次输出里三条摆谱用例的结果贴进交付说明，并写明：
- 本该滚的是 `[data-testid="baipu-moves-fold"] .mvrows`（不是右栏）——`movesOverflow > 100`（241 手造溢出）
- 右栏 `railH === 516`、`railOverflow ≤ 0`、`actsBottom === railBottom`、`movesH ≥ 72`
- 坐标系 / 落点：不适用 —— 本屏不读 `offsetTop` 与 `scrollTop` 做定位比较，`scrollIntoView({block:'nearest'})` 由浏览器算

- [ ] **Step 5: 请 Fan 确认 —— 停在这里**

把四张图（或并排图 + 差异图）与 Step 3/4 的记录交给 Fan。**Fan 明确确认之前不开始 Task 4。** 等待期间可以做 Task 5、Task 6（与本关卡无依赖）。Fan 若要改文案 / 图标，回 Task 2 Step 5 改完再从本任务 Step 2 重来。

- [ ] **Step 6: Commit（Fan 确认后）**

只提交屏 17 这一屏的目录。Step 2 只跑屏 17 一份 spec，正常不会动别的屏；若别的屏目录也被改写（有人跑过全量 `npm run fourup`），**不要** `git checkout HEAD --` 还原（Global Constraints 禁的就是在本 worktree 里这么做 —— 别人的在制品可能就在那儿），只是不 add 它们：下面的 `git add` 只点名 `17-baipu/`，提交前用 `git diff --cached --stat` 确认暂存区里没有别的屏。

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu
git status --short superpowers/tracks/kiosk-go-shell-align/visual/   # 期望:只有 17-baipu/ 下的图(参考图字节不变时只有三张)
git add katrain/web/ui/tests/kiosk-screen-17-baipu.fourup.spec.ts superpowers/tracks/kiosk-go-shell-align/visual/17-baipu/1024x600/
git diff --cached --stat
git commit -m "test(kiosk-go): 屏 17 四图改取上线态 —— 灯的颜色对照替掉摄像头那块,Fan 已确认(K4)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: K4 后端 · 采集模式开关与 `GET /api/v1/baipu/mode`（Fan 确认 Task 3 之后）

**Files:**
- Modify: `katrain/web/core/baipu_capture.py:316-325`（其后加 `resolve_baipu_collect`）
- Modify: `katrain/web/api/v1/endpoints/baipu.py:102-110`（`_collect_enabled`、`/mode`、`/capture` 门）
- Modify: `katrain/web/server.py:548`、`:663-678`、`:679-681`、`:3462-3472`
- Modify: `katrain/vision/README.md:5-13`
- Test: `tests/test_baipu_api.py:93-102,208-213`（改夹具）+ 新用例；`tests/test_baipu_capture.py:384-392` 之后加一条

**Interfaces:**
- Consumes: Task 2 定下的 HTTP 契约 `GET /api/v1/baipu/mode` → `{"collect": boolean}`
- Produces:
  - `resolve_baipu_collect(cli: Optional[bool] = None, env: Optional[str] = None) -> bool`（`katrain/web/core/baipu_capture.py`）
  - `app.state.baipu_collect: bool`（lifespan 设，默认 False）
  - CLI `--baipu-collect`（store_true）/ 环境变量 `KATRAIN_BAIPU_COLLECT`（`1/true/yes/on`，大小写与首尾空白不敏感）
  - `/baipu/capture`：`not (capture 存在 and baipu_collect)` ⇒ 404 `"Capture service not enabled"`（与今天无采集服务时同一个形状，前端 `disabled` 分支照旧认得）

- [ ] **Step 1: 写失败的测试**

`tests/test_baipu_api.py` 的 `_client`（`:93-102`）换成：

```python
    def _client(self, tmp_path, capture=True, geometry=True, led=True, collect=True):
        app = FastAPI()
        app.include_router(baipu.router, prefix="/baipu")
        if capture:
            app.state.capture = _FakeCapture(tmp_path)
        if geometry:
            app.state.geometry = _geo()
        if led:
            app.state.led = _FakeLed()
        # 这组测的是**采集机**上的 /capture;上线态(开关没开)那一种单独测。
        app.state.baipu_collect = collect
        return TestClient(app)
```

`:208-213` 那段 fiducial 用例里 `app.state.baipu_fiducial_mode = "every-move"` 之后加 `app.state.baipu_collect = True`。

`TestBaipuCaptureEndpoint` 里 `test_409_without_geometry` 之前加：

```python
    def test_404_when_capture_service_exists_but_collect_is_off(self, tmp_path):
        # 盒子为了几何标定总是带着 --capture-camera 起 ⇒ 采集服务在盒上恒在。
        # 上线版摆谱不拍照(Fan 2026-09-14):开关没开就当没有采集,一张帧都不许写。
        c = self._client(tmp_path, collect=False)
        r = c.post("/baipu/capture", json={"game_id": "g", "move_index": -1, "sgf": "(;SZ[19];B[pd])"})
        assert r.status_code == 404
        assert not (tmp_path / "g").exists()

    def test_mode_is_collect_only_with_capture_service_and_switch(self, tmp_path):
        assert self._client(tmp_path).get("/baipu/mode").json() == {"collect": True}
        assert self._client(tmp_path, collect=False).get("/baipu/mode").json() == {"collect": False}
        assert self._client(tmp_path, capture=False).get("/baipu/mode").json() == {"collect": False}
```

`tests/test_baipu_capture.py` 在 `test_resolve_fiducial_mode_precedence` 之后加：

```python
def test_resolve_baipu_collect_defaults_off():
    from katrain.web.core.baipu_capture import resolve_baipu_collect

    assert resolve_baipu_collect() is False  # 上线版默认不拍照
    assert resolve_baipu_collect(None, "") is False
    assert resolve_baipu_collect(None, "0") is False
    assert resolve_baipu_collect(True, None) is True  # --baipu-collect
    assert resolve_baipu_collect(None, "1") is True  # KATRAIN_BAIPU_COLLECT=1
    assert resolve_baipu_collect(None, " TRUE ") is True
```

- [ ] **Step 2: 跑测试确认红**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu
CI=true uv run pytest tests/test_baipu_api.py tests/test_baipu_capture.py -q
```

Expected: FAIL —— `test_404_when_capture_service_exists_but_collect_is_off` 得 200 或 409；`/baipu/mode` 404；`ImportError: cannot import name 'resolve_baipu_collect'`。其余既有用例 PASS。

- [ ] **Step 3: 实现 `resolve_baipu_collect`**

`katrain/web/core/baipu_capture.py` 在 `resolve_fiducial_mode`（`:316-325`）之后加：

```python
_TRUTHY = ("1", "true", "yes", "on")


def resolve_baipu_collect(cli=None, env=None) -> bool:
    """摆谱要不要逐手拍照采帧:CLI ``--baipu-collect`` > ``$KATRAIN_BAIPU_COLLECT`` > **默认关**。

    拍照只为收集 YOLO 训练数据,上线版摆谱不拍(Fan 2026-09-14)。
    **不能拿「采集服务在不在」代替这个开关**:盒子为了几何标定总是带着 ``--capture-camera`` 起,
    采集服务在盒上恒在(``smartbox-katrain.service.d/20-vision-led.conf``)。
    """
    if cli:
        return True
    return str(env or "").strip().lower() in _TRUTHY
```

- [ ] **Step 4: 端点**

`katrain/web/api/v1/endpoints/baipu.py`，在 `@router.post("/capture")`（`:102`）之前加：

```python
def _collect_enabled(request: Request) -> bool:
    """采集态 = 采集服务在 **且** 启动时显式开了 ``--baipu-collect``。见 ``resolve_baipu_collect``。"""
    state = request.app.state
    return getattr(state, "capture", None) is not None and bool(getattr(state, "baipu_collect", False))


@router.get("/mode")
async def baipu_mode(request: Request) -> Dict[str, bool]:
    """摆谱屏进门先问这一句:拍不拍照。``collect=false`` 时前端不发 /capture、不套标定守卫。"""
    return {"collect": _collect_enabled(request)}
```

`baipu_capture` 函数开头两行（`:104-106`）

```python
    capture = getattr(request.app.state, "capture", None)
    if capture is None:
        raise HTTPException(status_code=404, detail="Capture service not enabled")
```

换成：

```python
    # 上线态(开关没开)与「没有采集服务」回同一个 404 —— 前端 `disabled` 分支认的就是这个形状。
    if not _collect_enabled(request):
        raise HTTPException(status_code=404, detail="Capture service not enabled")
    capture = request.app.state.capture
```

- [ ] **Step 5: `server.py` 接线**

`:548` `app.state.capture = None` 之后加一行 `app.state.baipu_collect = False`。

`:663` `from katrain.web.core.baipu_capture import resolve_fiducial_mode` → `from katrain.web.core.baipu_capture import resolve_baipu_collect, resolve_fiducial_mode`；在 `app.state.baipu_drift_threshold_cells = …`（`:668`）之后加：

```python
        # 上线版摆谱不拍照(Fan 2026-09-14)。采集服务在这里总是起的(几何标定要它),
        # 拍不拍由这个开关单独决定,默认关。采 YOLO 训练数据时给 --baipu-collect。
        app.state.baipu_collect = resolve_baipu_collect(
            getattr(settings, "_baipu_collect", None), os.getenv("KATRAIN_BAIPU_COLLECT")
        )
```

`:678` `log.info("Capture service started (camera=%s)", capture_config.camera_device)` →

```python
        log.info(
            "Capture service started (camera=%s, baipu_collect=%s)",
            capture_config.camera_device,
            app.state.baipu_collect,
        )
```

`:679-681` 的 `else:` 分支里 `app.state.geometry = None` 之后加 `app.state.baipu_collect = False`。

参数表：在 `--baipu-fiducial-mode` 那个 `parser.add_argument(...)`（`:3462-3469`）之后加：

```python
    parser.add_argument(
        "--baipu-collect",
        action="store_true",
        help="摆谱时逐手拍照采 YOLO 训练帧(需同时给 --capture-camera)。默认关:上线版摆谱不拍照。"
        " Also settable via $KATRAIN_BAIPU_COLLECT=1.",
    )
```

`:3471-3472` 的 `if args.baipu_fiducial_mode: …` 之后加：

```python
    if args.baipu_collect:
        settings._baipu_collect = True
```

- [ ] **Step 6: README 写清采集机要加开关**

`katrain/vision/README.md` 第一个启动命令代码块（`:7-13`）之后加一段：

```markdown
To capture YOLO training frames while replaying a kifu (摆谱), add `--baipu-collect` (or set `KATRAIN_BAIPU_COLLECT=1`). Without it 摆谱 runs in release mode: LEDs guide each move and the operator confirms, no photos are taken, and `POST /api/v1/baipu/capture` returns 404 even though the capture service is running (geometry calibration only needs `--capture-camera`).
```

- [ ] **Step 7: 测试转绿、格式化、确认端点真的挂进了应用**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu
uv run black -l 120 katrain/web/core/baipu_capture.py katrain/web/api/v1/endpoints/baipu.py
# ⚠️ 下面三份在 6f7dc629 上**本来就不是 black 干净的**(black 24.10 实测:server.py 有一处
# `report_settlement_task = asyncio.create_task(` 三行并一行,两份测试各有 10 / 24 行既有差异)。
# 整文件跑 black 会把这些**与本任务无关**的 hunk 一起改掉 —— server.py 是五条赛道共用的,
# 那就是白送一处合并冲突。所以只看 diff、不改写:diff 里若出现**本任务新写的代码**,照 diff 手工改;
# 既有那几处不动。
uv run black -l 120 --diff katrain/web/server.py tests/test_baipu_api.py tests/test_baipu_capture.py 2>/dev/null | grep -E '^[-+][^-+]'
CI=true uv run pytest tests/test_baipu_api.py tests/test_baipu_capture.py tests/web_ui/test_board_lifespan_camera_degraded.py -q
git status --short katrain/config.json     # 期望:空
cp ~/.katrain/config.json "$HOME/.cache/kiosk-go-kifu/baseline/config.json.t4" 2>/dev/null || true
(uv run python -m katrain --ui web --host 127.0.0.1 --port 8012 > "$HOME/.cache/kiosk-go-kifu/server-t4.log" 2>&1 &) ; sleep 20
curl -s http://127.0.0.1:8012/api/v1/baipu/mode; echo
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8012/api/v1/baipu/capture \
  -H 'Content-Type: application/json' -d '{"game_id":"g","move_index":-1,"sgf":"(;SZ[19];B[pd])"}'
pkill -f "katrain --ui web --host 127.0.0.1 --port 8012"
cp "$HOME/.cache/kiosk-go-kifu/baseline/config.json.t4" ~/.katrain/config.json 2>/dev/null || true
```

Expected: pytest 全 PASS；`curl` 第一条打印 `{"collect":false}`（证明 `/mode` 在真应用的 `/api/v1/baipu` 前缀下挂上了）；第二条打印 `404`。（本机没接摄像头，`collect=true` 那一支由 Step 1 的端点测试背书；采集机上启动日志会印 `baipu_collect=True`。）

- [ ] **Step 8: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu
git add katrain/web/core/baipu_capture.py katrain/web/api/v1/endpoints/baipu.py katrain/web/server.py \
  katrain/vision/README.md tests/test_baipu_api.py tests/test_baipu_capture.py
git diff --cached --stat
git commit -m "feat(baipu): 采集模式开关默认关 —— 盒子为标定总带着 --capture-camera,拍不拍照改由 --baipu-collect 决定(K4 后端)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: K2 · 只摆 19 路（摆谱屏拦、棋谱详情灰键）

**Files:**
- Modify: `katrain/web/ui/src/api/baipuApi.ts:208-214`（`clearProgress` 之后加 `forgetSgf`）
- Modify: `katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx:5-8`（import）、`:122-124`（state）、`:156-164`（load 回调）、`:337-340`（错误态）
- Modify: `katrain/web/ui/src/kiosk/pages/KifuDetailPage.tsx:1-14`（import）、`:179-187`（动作键）
- Test: `katrain/web/ui/src/kiosk/__tests__/BaipuSessionPage.test.tsx`（加一组）、`katrain/web/ui/src/kiosk/__tests__/KifuDetailPage.test.tsx`（加一条）

**Interfaces:**
- Consumes: Task 1/2 的 `BaipuSessionPage.test.tsx` 夹具（`renderPage(collect?)`、`move`、`META`、`ledPoint`）
- Produces: `export function forgetSgf(id: string): void` —— 从 `baipu:recent` 摘掉该 id，并删 `baipu:sgf:<id>`、`baipu:progress:<id>`；吞掉 `localStorage` 异常

- [ ] **Step 1: 写失败的测试**

`BaipuSessionPage.test.tsx` 追加：

```tsx
describe('屏 17 摆谱 · 只摆 19 路(K2)', () => {
  // 实体盘和灯阵都是 19 路。13 路的行列发给灯,会亮在实体盘左上角那一块 —— 每一颗都错位。
  it('13 路的谱:说清摆不了、一颗灯都不点,并从「最近摆过」和本地缓存里拿掉', async () => {
    localStorage.setItem('baipu:recent', JSON.stringify([
      { id: 'g1', name: '三星杯', savedAt: 1 }, { id: 'other', name: '别的', savedAt: 1 },
    ]));
    localStorage.setItem('baipu:progress:g1', JSON.stringify({ k: 0, frames: 0, updatedAt: 1 }));
    baipuLoad.mockResolvedValue({ board_size: 13, steps: [move(0, 3, 3, 'B')], meta: META });
    renderPage();
    expect(await screen.findByText('这是 13 路的谱，摆不了')).toBeInTheDocument();
    expect(ledPoint).not.toHaveBeenCalled();
    expect(localStorage.getItem('baipu:sgf:g1')).toBeNull();
    expect(localStorage.getItem('baipu:progress:g1')).toBeNull();
    expect(JSON.parse(localStorage.getItem('baipu:recent')!)).toEqual([{ id: 'other', name: '别的', savedAt: 1 }]);
    fireEvent.click(screen.getByRole('button', { name: /棋谱/ }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/kifu');
  });
});
```

`KifuDetailPage.test.tsx` 的 `describe('屏 16 棋谱详情 · 两个出口', …)` 里追加：

```tsx
  it('13 路的谱「摆到实体盘」灰着,并说明实体盘只摆得了 19 路', async () => {
    baipuLoad.mockResolvedValue({
      board_size: 13, meta: {},
      steps: [step({ move_index: 0, property: 'B', row: 3, col: 3, color: 'B' })],
    });
    renderPage();
    await waitLoaded();
    const btn = screen.getByRole('button', { name: '摆到实体盘' });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute('title', expect.stringContaining('13 路'));
  });
```

- [ ] **Step 2: 跑测试确认红**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu/katrain/web/ui
npx vitest run src/kiosk/__tests__/BaipuSessionPage.test.tsx src/kiosk/__tests__/KifuDetailPage.test.tsx
```

Expected: FAIL —— 找不到「这是 13 路的谱，摆不了」（页面照常进 guiding 并点灯）；详情那条按钮不是 disabled。

- [ ] **Step 3: `baipuApi.ts` 加 `forgetSgf`**

在 `clearProgress`（`:208-214`）之后加：

```ts
/**
 * 把一份谱从「最近摆过」、本地缓存和进度里整份拿掉。
 * 只给「这份谱摆不了」那一种用(K2:非 19 路)—— 留着它,棋谱屏会给一颗点了还是摆不了的「接着摆」。
 */
export function forgetSgf(id: string): void {
  try {
    localStorage.removeItem(SGF_KEY(id));
    localStorage.removeItem(PROGRESS_KEY(id));
    const recent = (safeParse<BaipuRecentEntry[]>(localStorage.getItem(RECENT_KEY)) ?? []).filter((e) => e.id !== id);
    localStorage.setItem(RECENT_KEY, JSON.stringify(recent));
  } catch {
    // localStorage 不可用时没有东西可删
  }
}
```

- [ ] **Step 4: 摆谱屏拦非 19 路**

`BaipuSessionPage.tsx:5-8` 的 import 里 `BaipuAPI, getCachedSgf, saveProgress, getProgress, clearProgress,` → `BaipuAPI, getCachedSgf, saveProgress, getProgress, clearProgress, forgetSgf,`。

`:124` `const [loadError, setLoadError] = useState<string | null>(null);` 之后加：

```tsx
  /** 读到的谱不是 19 路时记下它的路数。实体盘和灯阵只有 19 路。 */
  const [wrongSize, setWrongSize] = useState<number | null>(null);
```

`:156-158` 的

```tsx
      .then((resp) => {
        if (cancelled) return;
        setSteps(resp.steps);
```

换成：

```tsx
      .then((resp) => {
        if (cancelled) return;
        // 实体盘和灯阵都是 19 路。别的路数的行列发给灯会亮在左上角那一块 —— 每一颗都错位。
        // **这里是所有入口(屏 16 / 导入 SGF / 接着摆)的唯一汇合点**,所以拦在这儿,不在入口各拦一遍。
        // 顺手把它从「最近摆过」里拿掉:留着的话棋谱屏会给一颗点了还是摆不了的「接着摆」。
        if (resp.board_size !== 19) {
          forgetSgf(source);
          setWrongSize(resp.board_size);
          setPhase('error');
          return;
        }
        setSteps(resp.steps);
```

`:337-340` 错误态那块

```tsx
        <div className="empty" data-testid="baipu-load-error">
          <h4>{sgf ? t('baipu:load_failed', '没读出这份谱') : t('baipu:no_sgf', '这台盒子上没有这份谱')}</h4>
          {loadError && <p>{loadError}</p>}
        </div>
```

换成：

```tsx
        <div className="empty" data-testid="baipu-load-error">
          {wrongSize !== null ? (
            <>
              <h4>{interpolate(t('baipu:wrong_size', '这是 {n} 路的谱，摆不了'), { n: wrongSize })}</h4>
              <p>{t('baipu:wrong_size_hint', '实体盘和灯都是 19 路的 —— 别的路数摆上去每一颗都会错位。')}</p>
            </>
          ) : (
            <>
              <h4>{sgf ? t('baipu:load_failed', '没读出这份谱') : t('baipu:no_sgf', '这台盒子上没有这份谱')}</h4>
              {loadError && <p>{loadError}</p>}
            </>
          )}
        </div>
```

- [ ] **Step 5: 棋谱详情灰键**

`KifuDetailPage.tsx` import 区加 `import { interpolate } from '../utils/interpolate';`。`:179-187` 的 `baipu` 动作换成：

```tsx
    {
      key: 'baipu',
      icon: 'grid-nine',
      label: t('kifu:place_on_board', '摆到实体盘'),
      onClick: goBaipu,
      // 实体盘和灯阵只有 19 路。摆谱屏自己也会拦(它是所有入口的汇合点),这里先灰掉,别让人白跳一趟。
      disabled: !album?.sgf_content || boardSize !== 19,
      reason: album?.sgf_content && boardSize !== 19
        ? interpolate(t('kifu:wrong_size_reason', '这是 {n} 路的谱 —— 实体盘只摆得了 19 路'), { n: boardSize })
        : t('kifu:need_sgf', '这一局还没读到谱'),
    },
```

- [ ] **Step 6: 测试转绿**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu/katrain/web/ui
npx vitest run src/kiosk/__tests__/BaipuSessionPage.test.tsx src/kiosk/__tests__/KifuDetailPage.test.tsx src/kiosk/__tests__/KifuPage.test.tsx
npx tsc -b && echo TSC_OK
```

Expected: PASS（含既有「摆到实体盘先缓存再进摆谱屏」那条 —— 19 路不受影响）；`TSC_OK`。

- [ ] **Step 7: 一张真运行时截图（相称性：错误态文案，参考图里没有这一态，不做四图）**

同 Task 1 Step 7 的理由，不在裸 `npm run dev` 上手点（`/baipu/load` 走代理到 :8001，没后端就只会看到「没读出这份谱」而不是路数那一态）。在 Task 1 建的临时 `tests/tmp-kifu-shots.spec.ts` 末尾加：

```ts
test('K2 13 路谱在摆谱屏被拦下', async ({ page }) => {
  await boot(page, 13);
  await page.goto('/kiosk/baipu/session/s1');
  await page.getByText('这是 13 路的谱，摆不了').waitFor();
  await page.screenshot({ path: `${OUT}/k2-wrong-size.png` });
});
```

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu/katrain/web/ui
npx playwright test --config=playwright.visual.config.ts tests/tmp-kifu-shots.spec.ts -g K2
rm tests/tmp-kifu-shots.spec.ts
git status --short tests/    # 期望:没有 tmp-kifu-shots.spec.ts
```

把 `$HOME/.cache/kiosk-go-kifu/k2-wrong-size.png` 附在交付说明里。「从最近摆过里拿掉」由 Step 1 的单测断言 `localStorage`，不另取图。

- [ ] **Step 8: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu
git add katrain/web/ui/src/api/baipuApi.ts katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx \
  katrain/web/ui/src/kiosk/pages/KifuDetailPage.tsx \
  katrain/web/ui/src/kiosk/__tests__/BaipuSessionPage.test.tsx katrain/web/ui/src/kiosk/__tests__/KifuDetailPage.test.tsx
git diff --cached --stat
git commit -m "fix(kiosk-go): 9/13 路的谱能进只认 19 路灯阵的摆谱 —— 摆谱屏拦下并从最近摆过里拿掉,详情灰键(K2)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: N9（棋谱库那一半）· 断网时说「要联网」，不说「没搜到」

**Files:**
- Modify: `katrain/web/core/repository.py:251-270`
- Modify: `katrain/web/api/v1/endpoints/kifu.py:1-13`（import）、`:64-67`、`:99-104`
- Create: `tests/web_ui/test_kifu_offline.py`
- Modify: `katrain/web/ui/src/api/kifuApi.ts:1-14`
- Modify: `katrain/web/ui/src/kiosk/pages/KifuPage.tsx:1-16`（import）、`:91`（state）、`:121-130`、`:256-267`
- Modify: `katrain/web/ui/src/kiosk/pages/KifuDetailPage.tsx:1-14`（import）、`:89`（state）、`:111-113`、`:243-246`
- Test: `katrain/web/ui/src/kiosk/__tests__/KifuPage.test.tsx`、`katrain/web/ui/src/kiosk/__tests__/KifuDetailPage.test.tsx`

**Interfaces:**
- Consumes: 现成的 `RepositoryDispatcher._remote_only(call, unavailable_detail)`（`repository.py:364-376`：离线 / `httpx.TransportError` / 远端 5xx ⇒ `RemoteServiceUnavailableError`；远端 4xx 原样抛 `httpx.HTTPStatusError`）；现成的 `ApiError(status, message)`（`src/api.ts:268-275`）
- Produces:
  - board 模式 `GET /api/v1/kifu/albums`、`GET /api/v1/kifu/albums/{id}`：连不上云端 ⇒ 503 `{"detail": "Remote kifu service unavailable"}`；远端 404 ⇒ 404；在线成功照旧（server 模式分支不动）
  - `KifuAPI.getAlbums / getAlbum` 非 2xx 抛 `ApiError`（`message` 仍是 `Request failed <status>: <body>`）

- [ ] **Step 1: 写失败的后端测试**

`git ls-files tests/web_ui/test_kifu_offline.py` 先确认为空。创建：

```python
"""board 模式棋谱库:连不上云端是 503,不是空库(N9)。

以前 `RepositoryDispatcher.kifu_*` 离线回空列表 / None ⇒ 列表端点 200 空、详情端点 404,
屏 15 写「没有对得上的谱 · 换棋手名再试」—— 人会去反复换关键词,而真实原因是没网。
判据落在**端点给出的状态码**上:前端靠 503 分出「要联网」和「没搜到」。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import HTTPException

from katrain.web.api.v1.endpoints import kifu
from katrain.web.core.repository import RemoteKifuRepository, RepositoryDispatcher


class _Connectivity:
    def __init__(self, online: bool):
        self.is_online = online


def _dispatcher(online=True, *, search=None, get=None):
    remote = MagicMock()
    remote.search_kifu = search or AsyncMock(return_value={"items": [], "total": 0, "page": 1, "page_size": 6})
    remote.get_kifu = get or AsyncMock(return_value={"id": 7})
    return RepositoryDispatcher(
        connectivity_manager=_Connectivity(online),
        remote_tsumego=MagicMock(),
        remote_kifu=RemoteKifuRepository(remote),
        remote_user_games=MagicMock(),
        local_user_game_repo=MagicMock(),
        remote_client=remote,
    )


def _request(dispatcher):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(repository_dispatcher=dispatcher)))


def _status_error(code):
    request = httpx.Request("GET", "https://cloud.example/api/v1/kifu/albums/7")
    return httpx.HTTPStatusError("upstream", request=request, response=httpx.Response(code, request=request))


@pytest.mark.asyncio
async def test_offline_list_is_503_not_an_empty_library():
    with pytest.raises(HTTPException) as exc:
        await kifu.list_kifu_albums(request=_request(_dispatcher(online=False)), q=None, page=1, page_size=6, db=None)
    assert exc.value.status_code == 503
    assert exc.value.detail == "Remote kifu service unavailable"


@pytest.mark.asyncio
async def test_offline_detail_is_503_not_not_found():
    with pytest.raises(HTTPException) as exc:
        await kifu.get_kifu_album(request=_request(_dispatcher(online=False)), album_id=7, db=None)
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_cloud_unreachable_is_503():
    d = _dispatcher(search=AsyncMock(side_effect=httpx.ConnectError("refused")))
    with pytest.raises(HTTPException) as exc:
        await kifu.list_kifu_albums(request=_request(d), q=None, page=1, page_size=6, db=None)
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_cloud_404_stays_404():
    d = _dispatcher(get=AsyncMock(side_effect=_status_error(404)))
    with pytest.raises(HTTPException) as exc:
        await kifu.get_kifu_album(request=_request(d), album_id=7, db=None)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Kifu album 7 not found"


@pytest.mark.asyncio
async def test_online_passes_through():
    d = _dispatcher()
    listed = await kifu.list_kifu_albums(request=_request(d), q=None, page=1, page_size=6, db=None)
    assert listed["total"] == 0
    assert await kifu.get_kifu_album(request=_request(d), album_id=7, db=None) == {"id": 7}
```

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu
CI=true uv run pytest tests/web_ui/test_kifu_offline.py -q
```

Expected: FAIL —— 离线两条没有抛 `HTTPException`（列表回了空 dict、详情抛 404 而不是 503）；`test_cloud_unreachable_is_503` 同样回空。`test_online_passes_through` 与 `test_cloud_404_stays_404`（今天 None ⇒ 404）PASS。

- [ ] **Step 2: 后端实现**

`katrain/web/core/repository.py:251-270` 整段换成：

```python
    # ── Kifu (online-only: offline / cloud failure = 503, never an empty library) ──
    #
    # 棋谱库只在云端,盒上没有本地副本。以前这两条离线回空列表 / None,端点就把「连不上」
    # 说成了「没搜到 / 没有这一局」,屏 15 写「没有对得上的谱 · 换棋手名再试」。
    # 远端 404 照旧是 404:`_remote_only` 只把离线、传输错误和 5xx 收成不可用。

    async def kifu_list_albums(self, q=None, page=1, page_size=20):
        return await self._remote_only(
            lambda: self.remote_kifu.list_albums(q, page, page_size), "Remote kifu service unavailable"
        )

    async def kifu_get_album(self, album_id):
        return await self._remote_only(lambda: self.remote_kifu.get_album(album_id), "Remote kifu service unavailable")
```

`katrain/web/api/v1/endpoints/kifu.py`：import 区加

```python
import httpx
```

与

```python
from katrain.web.core.repository import RemoteServiceUnavailableError
```

在 `@router.get("/albums", …)` 之前加：

```python
async def _from_dispatcher(call, not_found_detail: str):
    """board 模式走云端。**连不上是 503,不是空库**(见 `RepositoryDispatcher.kifu_list_albums` 那段注释)。"""
    try:
        return await call()
    except RemoteServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        detail = not_found_detail if status == 404 else f"Remote kifu request failed ({status})"
        raise HTTPException(status_code=status, detail=detail) from exc
```

`:66-67`

```python
    if dispatcher is not None:
        return await dispatcher.kifu_list_albums(q, page, page_size)
```

→

```python
    if dispatcher is not None:
        return await _from_dispatcher(lambda: dispatcher.kifu_list_albums(q, page, page_size), "Kifu albums not found")
```

`:101-104`

```python
    if dispatcher is not None:
        result = await dispatcher.kifu_get_album(album_id)
        if not result:
```

→

```python
    if dispatcher is not None:
        result = await _from_dispatcher(
            lambda: dispatcher.kifu_get_album(album_id), f"Kifu album {album_id} not found"
        )
        if not result:
```

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu
uv run black -l 120 katrain/web/core/repository.py katrain/web/api/v1/endpoints/kifu.py tests/web_ui/test_kifu_offline.py
CI=true uv run pytest tests/web_ui/test_kifu_offline.py tests/web_ui/test_kifu_list.py tests/web_ui/test_board_report_proxy.py tests/web_ui/test_tsumego_offline.py -q
git status --short katrain/config.json
```

Expected: 全 PASS；`config.json` 无变动。

- [ ] **Step 3: 写失败的前端测试**

`src/kiosk/__tests__/KifuPage.test.tsx`：import 区加 `import { ApiError } from '../../api';`；在「库读不到时如实报错并给重试」那条之后加：

```tsx
  it('棋谱库连不上云端(503)时说「要联网」,不印原文,也不说「没搜到」', async () => {
    getAlbums.mockImplementation((o: { page_size?: number }) => (o?.page_size === 6
      ? Promise.reject(new ApiError(503, 'Request failed 503: {"detail":"Remote kifu service unavailable"}'))
      : Promise.resolve({ items: [], total: 0, page: 1, page_size: 1 })));
    renderPage();
    fireEvent.click(screen.getByText('搜棋谱').closest('button')!);
    expect(await screen.findByText('棋谱库要联网才能搜')).toBeInTheDocument();
    expect(screen.queryByText(/Request failed/)).toBeNull();
    expect(screen.queryByText('没有对得上的谱')).toBeNull();
    expect(screen.getByRole('button', { name: '重试' })).toBeInTheDocument();
  });
```

`src/kiosk/__tests__/KifuDetailPage.test.tsx`：import 区加 `import { ApiError } from '../../api';`；在「读不到就报错,并且重试真的会再拉一次」之后加：

```tsx
  it('连不上云端(503)时说「要联网」,不印原文;重试照样再拉一次', async () => {
    getAlbum.mockRejectedValueOnce(new ApiError(503, 'Request failed 503: {"detail":"Remote kifu service unavailable"}'));
    renderPage();
    expect(await screen.findByText('这一局要联网才能读')).toBeInTheDocument();
    expect(screen.queryByText(/Request failed/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    await waitLoaded();
  });
```

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu/katrain/web/ui
npx vitest run src/kiosk/__tests__/KifuPage.test.tsx src/kiosk/__tests__/KifuDetailPage.test.tsx
```

Expected: FAIL —— 新两条找不到「要联网」文案（屏上是「棋谱库读不到」/「这一局读不到」+ 原文）。

- [ ] **Step 4: 前端实现**

`src/api/kifuApi.ts:1-14` 换成：

```ts
// API functions for kifu album (tournament game records) module

import type { KifuAlbumListResponse, KifuAlbumDetail } from '../types/kifu';
import { ApiError } from '../api';

const API_BASE = '/api/v1/kifu';

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    const body = await response.text();
    // 带上 `status`:board 模式下棋谱库连不上云端是 **503**,屏上要说「要联网」而不是「没搜到」。
    // 消息格式不变(`Request failed <status>: <body>`),按文本断言的既有测试照旧。
    throw new ApiError(response.status, `Request failed ${response.status}: ${body}`);
  }
  return response.json();
}
```

`src/kiosk/pages/KifuPage.tsx`：import 区加 `import { ApiError } from '../../api';`；`:91` `const [listError, setListError] = useState<string | null>(null);` 之后加

```tsx
  /** 列表失败是不是「连不上云端」(503)。棋谱库只在云端,这一种要说「要联网」,别的照原样报。 */
  const [listOffline, setListOffline] = useState(false);
```

`:128-130` 的

```tsx
      .catch((err: Error) => {
        if (!cancelled) { setListError(err.message); setAlbums(null); }
      });
```

→

```tsx
      .catch((err: Error) => {
        if (!cancelled) {
          setListError(err.message);
          setListOffline(err instanceof ApiError && err.status === 503);
          setAlbums(null);
        }
      });
```

`:257-259` 的

```tsx
                <h4>{t('kifu:list_failed', '棋谱库读不到')}</h4>
                <p>{listError}</p>
```

→

```tsx
                <h4>{listOffline ? t('kifu:list_offline', '棋谱库要联网才能搜') : t('kifu:list_failed', '棋谱库读不到')}</h4>
                <p>{listOffline
                  ? t('kifu:list_offline_hint', '这台盒子现在连不上云端。摆过的谱和导入的 SGF 不受影响。')
                  : listError}</p>
```

`src/kiosk/pages/KifuDetailPage.tsx`：import 区加 `import { ApiError } from '../../api';`；`:89` `const [error, setError] = useState<string | null>(null);` 之后加

```tsx
  /** 读不到是不是「连不上云端」(503)—— 棋谱库只在云端。 */
  const [offline, setOffline] = useState(false);
```

`:111-113` 的

```tsx
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
```

→

```tsx
      .catch((e: Error) => {
        if (!cancelled) {
          setError(e.message);
          setOffline(e instanceof ApiError && e.status === 503);
        }
      });
```

`:245-246` 的

```tsx
            <h4>{t('kifu:load_failed', '这一局读不到')}</h4>
            <p>{error}</p>
```

→

```tsx
            <h4>{offline ? t('kifu:detail_offline', '这一局要联网才能读') : t('kifu:load_failed', '这一局读不到')}</h4>
            <p>{offline ? t('kifu:detail_offline_hint', '棋谱库在云端，这台盒子现在连不上。') : error}</p>
```

- [ ] **Step 5: 测试转绿、共享领地两套构建**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu/katrain/web/ui
npx vitest run src/kiosk/__tests__/KifuPage.test.tsx src/kiosk/__tests__/KifuDetailPage.test.tsx src/kiosk/components/report/ReportLibraryImportDialog.test.tsx src/galaxy/components/research/CloudSGFPanel.test.tsx
npx tsc -b && echo TSC_OK
npm run build && npm run build:kiosk-2d 2>&1 | tail -3
```

Expected: 四个测试文件 PASS（后两份是 `KifuAPI` 的另外两个消费者，确认抛 `ApiError` 没把它们打坏）；`TSC_OK`；两套构建绿，末尾 `✅ kiosk boundary clean`。

- [ ] **Step 6: board 模式实走一次（本机）**

本机没有 board 模式的完整配置时跳过这一步，改由 Task 7 的上板清单第 ③ 条验证。能起的话：`KATRAIN_MODE=board` 起服务、断开外网，`curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:<port>/api/v1/kifu/albums?page=1&page_size=6` 期望 `503`，并在 kiosk 屏 15 展开搜索截一张「棋谱库要联网才能搜」附在交付说明里。

- [ ] **Step 7: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu
git add katrain/web/core/repository.py katrain/web/api/v1/endpoints/kifu.py tests/web_ui/test_kifu_offline.py \
  katrain/web/ui/src/api/kifuApi.ts katrain/web/ui/src/kiosk/pages/KifuPage.tsx katrain/web/ui/src/kiosk/pages/KifuDetailPage.tsx \
  katrain/web/ui/src/kiosk/__tests__/KifuPage.test.tsx katrain/web/ui/src/kiosk/__tests__/KifuDetailPage.test.tsx
git diff --cached --stat     # 期望:test_kifu_offline.py 新文件在
git commit -m "fix(kiosk-go): 断网时棋谱库说「没有对得上的谱」—— 连不上云端改回 503,屏上说要联网(N9 棋谱库)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: 收尾 · 两套构建、e2e、基线 diff、上板清单

**Files:** 无新改动（只有发现回归时回到对应任务修）；上板结果回填 `superpowers/tracks/kiosk-go-kifu/prd.md` §7。

**Interfaces:**
- Consumes: Task 0 的 `$BASE/vitest-fail.txt`、`$BASE/pytest-fail.txt`；Task 1–6 全部提交
- Produces: 「新增失败 = 空集」的证据；上板清单

- [ ] **Step 1: 类型与两套构建**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu/katrain/web/ui
npx tsc -b && echo TSC_OK
npm run build && npm run build:kiosk-2d 2>&1 | tail -3
# kiosk 边界规则在 eslint 里(tsc / vite 都不查);只看本轮动过的源码文件上的报错
npx eslint src/kiosk/KioskApp.tsx src/kiosk/pages/BaipuSessionRoute.tsx src/kiosk/pages/BaipuSessionPage.tsx \
  src/kiosk/pages/KifuPage.tsx src/kiosk/pages/KifuDetailPage.tsx src/kiosk/pages/TutorialCategoriesPage.tsx \
  src/api/baipuApi.ts src/api/kifuApi.ts
```

Expected: `TSC_OK`；末尾 `✅ kiosk boundary clean`；eslint 没有 `no-restricted-imports`（边界）类报错。其它规则的报错若在 `6f7dc629` 上同一行就有，不算本轮的。

- [ ] **Step 2: 前端全量，比名字集合**

```bash
BASE="$HOME/.cache/kiosk-go-kifu/baseline"
cd /Users/fan/Repositories/katrain-kiosk-go-kifu/katrain/web/ui
npx vitest run --reporter=json --outputFile="$BASE/vitest-after.json" > "$BASE/vitest-after.log" 2>&1 || true
python3 - "$BASE/vitest-after.json" > "$BASE/vitest-after-fail.txt" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
for f in d["testResults"]:
    for a in f["assertionResults"]:
        if a["status"] == "failed":
            print(f'{f["name"].split("katrain/web/ui/")[-1]} > {a["fullName"]}')
EOF
sort -o "$BASE/vitest-after-fail.txt" "$BASE/vitest-after-fail.txt"
echo "== 新增失败 =="; comm -13 "$BASE/vitest-fail.txt" "$BASE/vitest-after-fail.txt"
echo "== 不再失败 =="; comm -23 "$BASE/vitest-fail.txt" "$BASE/vitest-after-fail.txt"
```

Expected: 「新增失败」为空。不为空时：属于已知负载相关名单的，单独 `npx vitest run <文件>` 跑一遍，绿就不算；其余一律当本轮造成的回归处理（按文件名判「看着不相关」不算数 —— 进程级共享状态的污染恰恰落在无关文件里）。

- [ ] **Step 3: 后端全量，比名字集合**

```bash
BASE="$HOME/.cache/kiosk-go-kifu/baseline"
cd /Users/fan/Repositories/katrain-kiosk-go-kifu
CI=true uv run pytest tests -q -rfE > "$BASE/pytest-after.txt" 2>&1 || true
grep -E '^(FAILED|ERROR) ' "$BASE/pytest-after.txt" | sed -E 's/ - .*//' | sort -u > "$BASE/pytest-after-fail.txt"
echo "== 新增失败 =="; comm -13 "$BASE/pytest-fail.txt" "$BASE/pytest-after-fail.txt"
git status --short katrain/config.json   # 期望:空
```

Expected: 「新增失败」为空；`katrain/config.json` 无变动（有就 `git checkout -- katrain/config.json`，不提交）。

- [ ] **Step 4: e2e 与真浏览器闸全跑一遍**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-kifu/katrain/web/ui
cp ~/.katrain/config.json "$HOME/.cache/kiosk-go-kifu/baseline/config.json.t7" 2>/dev/null || true
npm run build && npx playwright test tests/baipu.spec.ts
cp "$HOME/.cache/kiosk-go-kifu/baseline/config.json.t7" ~/.katrain/config.json 2>/dev/null || true
npx playwright test --config=playwright.visual.config.ts tests/kiosk-shell-contract.spec.ts tests/kiosk-shell-geometry.spec.ts tests/kiosk-shell-scroll.spec.ts
```

Expected: `baipu.spec.ts` 全 PASS；三份外壳闸没有红。若有红的用例与本轮改动无关（Task 0 没记 Playwright 基线），在 `6f7dc629` 上另开 `git worktree add` 装依赖后跑同一条用例复现，复现得出来才不算本轮造成的；**不要**在本 worktree 里 checkout 旧提交做对照。

- [ ] **Step 5: 上板清单交给 Fan（RK3562，一次只跑一家，人工在场）**

部署本分支的后端与 **`npm run build:smartbox-kiosk-2d`** 产物后，逐条走并把结果回填 prd §7。⚠️ 不是 `build:kiosk-2d`：盒子是 `KATRAIN_BOX_SSO=1`，非严格包不得部署上去（`smartbox-software/provisioning/README.md:359-361`），部署错包会先卡在登录链上，下面四条一条都走不到。
1. **K4**：不改 provisioning（开关默认关）；服务重启后**不做标定**，从屏 15 搜一局 → 屏 16 →「摆到实体盘」，能直接进摆谱、灯色正确（黑红 / 白绿 / 提子蓝），按到摆完；摆之前先记 `sudo ls /root/.katrain/baipu_captures/`，摆完再看一次，没有新目录（服务以 root 跑、drop-in 没给 `--capture-dir` ⇒ 目录在 **root 的**家目录下，用别的账号看 `~` 等于没验）；`curl -s http://127.0.0.1:8081/api/v1/baipu/mode` 回 `{"collect":false}`。
2. **K1**：摆谱中「← 棋谱 → 退出」、摆完「完成」都落在棋谱屏，Dock 可见。
3. **N9**：拔掉外网，屏 15 展开搜索看到「棋谱库要联网才能搜」；屏 16 进一局看到「这一局要联网才能读」。
4. **顺带记录**：屏 15「导入 SGF」在全屏 Chromium 里能不能弹出文件选择器（S5）；上线态连按「确认落子」有没有出现一次触摸跳两手（prd §5 观察项）。

- [ ] **Step 6: 不单独提交**（Step 5 的回填随 Fan 确认后与文档一起提交）

---

## Self-Review（写完后对照 prd 自查的结果）

**1. Spec 覆盖**

| prd 条目 | 任务 |
|---|---|
| K1 五处入口 + 重定向 + 删页 + e2e 落点 | Task 1 |
| K4 前端：`mode()`、问不到当不拍、上线态不套守卫 / 不发 capture / 文案图标、采集态原样 | Task 2 |
| K4 屏 17 上线态四图 + Fan 确认 + 承重复核 | Task 3 |
| K4 后端：`--baipu-collect` / `KATRAIN_BAIPU_COLLECT` 默认关、`/mode`、`/capture` 门、README | Task 4 |
| K2 摆谱屏拦非 19 路 + 从最近摆过拿掉 + 详情灰键 | Task 5 |
| N9 棋谱库 503 + 前端「要联网」 | Task 6 |
| prd §7 基线 diff、两套构建、e2e、上板清单 | Task 7 |
| prd §4 D1–D7、§5 全部 | 不进任务（待拍板 / 不在本轮）；D1、D2 的「不拍板时」默认做法就是 Task 2/4 |

**2. 占位扫描：** 无 TBD / 「适当处理」/「同 Task N」。唯一的条件步骤是 Task 6 Step 6（本机起不了 board 模式时跳过，由 Task 7 Step 5 第 ③ 条上板补）。行号全部以 `6f7dc629` 为准，前序任务改过同一文件时按引用原文定位（Task 2 Files 已注明）。

**3. 名字一致性（跨任务核对过）：** `BaipuMode` / `BaipuAPI.mode()`（T2 定义，T4 实现的契约 `{"collect": bool}`）；`BaipuSessionPage({ collect })`（T2）与 `renderPage(collect = false)` 夹具（T2 改、T5 用）；`baipu-led-fold` / `baipu-cam-fold`（T2、T3）；`forgetSgf(id)`（T5）；`resolve_baipu_collect(cli, env)`、`_collect_enabled(request)`、`app.state.baipu_collect`、`settings._baipu_collect`（T4）；`_from_dispatcher(call, not_found_detail)`（T6）；503 的 `detail` 串 `"Remote kifu service unavailable"`（T6 实现与测试一致）。

**4. 相称性自查：** 新增测试只落在本轮真正改变的行为上（出口去向、上线态零 capture、采集态不变、路数拦截、503 文案、开关默认关、端点挂载）；没有新写 jsdom 布局断言，布局证据复用 `kiosk-shell-scroll.spec.ts` 既有三条；四图只做屏 17 上线态这一屏，导航与错误态文案各一张运行时截图；没有为双击误触、非方形 SGF、PO 翻译预先加工作（prd §5 记录）。
