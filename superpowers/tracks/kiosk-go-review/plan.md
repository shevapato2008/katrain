# 围棋 kiosk · 复盘/报告(kiosk-go-review)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 本轮要做三件事:① 屏 19 / 屏 20 的「失误 / 妙手」和胜率红段统一用服务端七档;② 请求失败时屏上说清是连不上、找不到还是积分不足,不再印后端原文;③ 盒上(token=null)从报告点「去研究」能打开那一局。

**Architecture:** 纯前端,没有后端与数据契约改动。
- R1:`reportStats.ts` 改走屏 20 已有的 `toMoveAnalysisMap → gradedMoves` 管线,删除旧单边轴常量与无人消费的 `keyMoves`。
- N24 / R5:两个 `authFetch` 在错误对象上挂 `status` / `body`(message 不变);新增共享纯函数 `utils/requestFailure.ts` 做分类;两个复盘钩子多暴露 `errorKind`;kiosk 两屏用 `reviewPresentation.ts` 的 `failureLine` 组织中文。
- S1 / N7:两处 token 判别位改为 `isAuthenticated`。

**Tech Stack:** React 18 + TypeScript + Vite,vitest + @testing-library/react,Playwright(仅一次真运行时预览与 PO 闸)。

**Spec:** `superpowers/tracks/kiosk-go-review/prd.md`

## Global Constraints

> **开工前先读 `prd.md` §6.0**：五条赛道的共享文件归属与合并顺序（尤其 `server.py` 终局落账只留一条入口）。与本 plan 冲突时以 §6.0 为准。

- 在 worktree `/Users/fan/Repositories/katrain-kiosk-go-review`(分支 `feature/kiosk-go-review`)里开发;**不 push、不合并 develop**,合并由 Fan 决定;不在别的 worktree 里 checkout。
- 本轮改动触及共享领地(`src/api/`、`src/features/`、`src/utils/`),必须 `npm run build` 与 `npm run build:kiosk-2d` 都绿;kiosk 边界(`verify:kiosk-2d`)不许破;共享文件不许 import `src/kiosk/**` / `src/galaxy/**` / `src/pages/**`。
- 类型检查用 `npx tsc -b`(`npx tsc --noEmit` 检查 0 个文件);`*.test.ts(x)` 不在 tsc 范围内,测试文件里的类型错不会被它发现。
- 盒上 token 恒为 null:任何「发不发请求 / 渲不渲染」的判别位用 `isAuthenticated`,不用 `token`;`token` 只作凭据(可为 null)与身份键。
- 新文案一律 `t('ns:key', '中文默认')`;**不往 PO 里加 key**(本轮已定不补,五条赛道合并后统一补,见 PRD §4 I18N-PO)。沿用 PO 里已有的 key 时,中文默认串必须与 cn PO 的 msgstr 逐字一致(`kiosk-shell-contract.spec.ts` 那条闸会查)。
- 本轮没有 Python 改动。若执行中不得不动 Python:格式化用 `uv run black -l 120 <文件>`,测试用 `uv run pytest <文件>`(本 worktree 没有 `.venv`,先 `uv sync --extra web`)。
- 前端单测:`cd /Users/fan/Repositories/katrain-kiosk-go-review/katrain/web/ui && npx vitest run <文件>`。
- 测试判据是**基线 diff**:动手前跑一遍全量 vitest,记下失败用例的**名字集合**;改完再跑,比名字集合,不比条数(Task 1 / Task 9 给出命令)。
- Playwright e2e(`playwright.config.ts`,:8002)打的是构建产物,改源码后要先 build 再跑;本计划只用 `playwright.visual.config.ts`(vite dev,:5173),不需要 build。
- 视觉 / 布局改动走 CLAUDE.md 的四图对比与承重实测关卡(`npm run fourup`;jsdom 不作布局证据),视觉通过需 Fan 确认。**本轮核过不触发**:没有 CSS 与盒子链改动,四图 fixture 的输出不变(PRD §7);N24 只做一次真运行时预览。
- 相称性:简单文案 / 判别位修复不堆测试层;N7 不加单测(jsdom 测不到 effect 之前那一帧)。
- 提交信息用中文,风格跟 `git log`(`fix(kiosk): …` / `refactor(kiosk-report): …`),结尾加一行 `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`。`git add` 逐个写文件名;新建文件 add 之后用 `git diff --cached --stat` 确认确实进了暂存区(仓里的 `.gitignore` 会静默吞掉某些文件名)。

---

## File Structure

| 文件 | 动作 | 职责 |
|---|---|---|
| `katrain/web/ui/src/kiosk/pages/ResearchPage.tsx` | 改 `:134`、`:437-455` | S1:`user_game_id` 深链判 `isAuthenticated`;取谱失败写副标题;provenance 返回路径用带 `task` 的 `backPath` |
| `katrain/web/ui/src/kiosk/pages/ResearchPage.userGame.test.tsx` | 改 | S1 回归钉子 |
| `katrain/web/ui/src/kiosk/pages/ReportsPage.tsx` | 改 `:12`、`:48-55`、`:75`、`:119-120`、`:145-176`、`:216-221`、`:246-250`、`:345-348`、`:365-367`、`:388-390`、`:533-540`、`:606-608` | N7 初值;R1 注释;N24 屏 19 的话 |
| `katrain/web/ui/src/features/report/reportStats.ts` | 改(整文件重写) | R1:失误 / 妙手 / 红段候选改走七档管线;删 `keyMoves` 与两个常量 |
| `katrain/web/ui/src/features/report/reportStats.test.ts` | 改 | R1 单测 |
| `katrain/web/ui/src/kiosk/components/report/ReviewWinratePlot.tsx` | 改 `:1`、`:37-46` | R1:红段只在 `bad` 手里挑 |
| `katrain/web/ui/src/kiosk/pages/ReportsPage.test.tsx` | 改 | R1 页面级钉子;N24 屏 19 文案 |
| `katrain/web/ui/tests/report-kiosk.spec.ts` | 改 `:102-103`(仅注释) | 去掉对已删 `keyMoves` 的引用 |
| `katrain/web/ui/src/kiosk/pages/ReportDetailPage.test.tsx` | 改 `:118`(Task 4,仅注释);`:143`、`:635-700`(Task 7) | 去掉 `keyMoves` 引用;N24 屏 20 文案 |
| `katrain/web/ui/src/utils/requestFailure.ts` | **新建** | N24 / R5:按数字 status 与 `detail.code` 分类 |
| `katrain/web/ui/src/utils/requestFailure.test.ts` | **新建** | 分类器单测 |
| `katrain/web/ui/src/api/reportApi.ts` | 改 `:88-91` | 错误对象挂 `status` / `body` |
| `katrain/web/ui/src/api/userGamesApi.ts` | 改 `:116-119` | 同上 |
| `katrain/web/ui/src/api/reportApi.test.ts`、`userGamesApi.test.ts` | 改 | 各加一条 |
| `katrain/web/ui/src/kiosk/components/report/reviewPresentation.ts` | 改(追加) | `failureReason` / `failureLine` |
| `katrain/web/ui/src/kiosk/components/report/reviewPresentation.test.ts` | 改(追加) | 一条 |
| `katrain/web/ui/src/features/report/useReportDetail.ts` | 改 `:14-39`、`:91-94`、`:156-159`、`:188`、`:221-231` | 暴露 `errorKind` |
| `katrain/web/ui/src/features/report/useReportTasks.ts` | 改 `:28-42`、`:66-67`、各 `setError` 处、`:268-278` | 暴露 `errorKind` |
| `katrain/web/ui/src/features/report/useReportDetail.test.tsx`、`useReportTasks.test.tsx` | 改 | 各加一条 |
| `katrain/web/ui/src/kiosk/pages/ReportDetailPage.tsx` | 改 `:12-16`、`:72-74`、`:126-128`、`:275-295`、`:321-331`、`:447-449` | N24 屏 20 的话 |

任务顺序:Task 1 基线 → Task 2 S1 → Task 3 N7 → Task 4 R1 → Task 5 分类器与 API → Task 6 钩子 → Task 7 屏 20 → Task 8 屏 19 → Task 9 收尾验证与预览。Task 2、3、4 互相独立;Task 5 → 6 → 7 / 8 有依赖;Task 8 与 Task 3、Task 4 改同一个文件,按序做。

---

### Task 1: 准备 worktree 依赖并记录基线

**Files:**
- 不改仓内文件。基线写到 git 目录下(不会被跟踪):`$(git rev-parse --absolute-git-dir)/review-baseline/`

**Interfaces:**
- Produces:`$BASE/before-failed.txt`(失败用例名字集合,每行 `相对路径 :: fullName`)与 `$BASE/failed-names.cjs`(Task 9 复用)。

- [ ] **Step 1: 确认工作树干净、装依赖**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-review
git status --short
git rev-parse --abbrev-ref HEAD
cd katrain/web/ui && npm ci
```

预期:分支是 `feature/kiosk-go-review`。`git status` 除本赛道 `superpowers/tracks/kiosk-go-review/` 两份文档外无改动(若主会话已提交,则完全干净)。`npm ci` 以 0 退出。

- [ ] **Step 2: 写失败名提取脚本**

```bash
BASE="$(git -C /Users/fan/Repositories/katrain-kiosk-go-review rev-parse --absolute-git-dir)/review-baseline"
mkdir -p "$BASE"
cat > "$BASE/failed-names.cjs" <<'EOF'
// 从 vitest JSON 报告里取「失败用例的名字集合」。基线比的是名字,不是条数。
const report = require(process.argv[2]);
const out = [];
for (const file of report.testResults) {
  const rel = file.name.replace(/^.*\/katrain\/web\/ui\//, '');
  if (file.status === 'failed' && file.assertionResults.length === 0) out.push(`${rel} :: <文件级失败>`);
  for (const a of file.assertionResults) {
    if (a.status === 'failed') out.push(`${rel} :: ${a.fullName}`);
  }
}
console.log(out.sort().join('\n'));
EOF
```

- [ ] **Step 3: 跑全量 vitest 与 tsc,落基线**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-review/katrain/web/ui
BASE="$(git -C /Users/fan/Repositories/katrain-kiosk-go-review rev-parse --absolute-git-dir)/review-baseline"
npx vitest run --reporter=json --outputFile="$BASE/before.json" > "$BASE/before.log" 2>&1; echo "vitest_exit=$?"
node "$BASE/failed-names.cjs" "$BASE/before.json" > "$BASE/before-failed.txt"
wc -l < "$BASE/before-failed.txt"
npx tsc -b; echo "tsc_exit=$?"
```

预期:`before-failed.txt` 写出(行数照实记下,可以是 0);`tsc_exit=0`。本仓 develop `b50fb32b`(UI 源码与本 worktree 相同)上,相关 9 个测试文件共 190 条全绿,供参考。**不提交**。

---

### Task 2: S1 · 研究屏 `user_game_id` 深链判 `isAuthenticated`

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/ResearchPage.tsx:134`, `:437-455`
- Test: `katrain/web/ui/src/kiosk/pages/ResearchPage.userGame.test.tsx`

**Interfaces:**
- Consumes:`useAuth()` 的 `{ token, isAuthenticated }`(`context/AuthContext.tsx:147`,`isAuthenticated = !!user`)。
- Produces:无对外接口变化。新增文案 key `research:user_game_failed`(默认「这一局读不到」)。

- [ ] **Step 1: 改测试的 auth 桩,写四条测试(三条先红、一条守卫)**

在 `ResearchPage.userGame.test.tsx` 里:

1)第 2、3 行 import 改成:

```tsx
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
```

2)把第 74 行

```tsx
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ token: 'tok' }) }));
```

换成

```tsx
const { auth } = vi.hoisted(() => ({
  auth: { current: { token: 'tok' as string | null, isAuthenticated: true } },
}));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => auth.current }));
```

3)把第 82 行 `beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear(); });` 换成

```tsx
beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  auth.current = { token: 'tok', isAuthenticated: true };
});
```

4)在 `describe('ResearchPage local-play review entry', …)` 里、`it('loads a recorded game by ?user_game_id', …)` 之后追加:

```tsx
  /**
   * S1 回归钉子(2026-09-14 调研):盒上严格 SSO 的 token 恒为 null,人是登录的
   * (凭据在 HttpOnly cookie 里)。闸判在 token 上时,屏 20「去研究」在盒上打开的是一块空盘。
   * 变异验证:把 ResearchPage 里的 `!isAuthenticated` 改回 `!token`,这条红。
   */
  it('token 为 null 而已登录(盒上):照样按 ?user_game_id 取谱', async () => {
    auth.current = { token: null, isAuthenticated: true };
    renderAt('/kiosk/research?user_game_id=g1&from=report');
    await waitFor(() => expect(get).toHaveBeenCalledWith(null, 'g1'));
    await waitFor(() => expect(loadFromSGF).toHaveBeenCalledWith('(;GM[1]FF[4])'));
  });

  it('没登录时不去取谱', async () => {
    auth.current = { token: null, isAuthenticated: false };
    renderAt('/kiosk/research?user_game_id=g1&from=report');
    await act(async () => { await Promise.resolve(); });
    expect(get).not.toHaveBeenCalled();
  });

  it('谱取不到时副标题说出来,不留一块没有解释的空盘', async () => {
    get.mockRejectedValueOnce(Object.assign(new Error('Request failed 503: {}'), { status: 503 }));
    renderAt('/kiosk/research?user_game_id=g1&from=report');
    expect(await screen.findByText('这一局读不到')).toBeInTheDocument();
  });

  /**
   * 盒上以前 provenance 永远是 null,返回键落在组件里算好的 `backPath`(带 `task` ⇒ 这一份报告)。
   * S1 修通之后 provenance 有了,它若还写 `BACK` 表里的 `backTo.path`(报告**列表**),
   * 盒上「去研究 → 返回」就从回到这份报告退成回到列表 —— 屏 20 的单测注释明写 `task` 是为了回到这一份。
   */
  it('从报告进来,返回键回的是这一份报告,不是报告列表', async () => {
    auth.current = { token: null, isAuthenticated: true };
    render(
      <ThemeProvider theme={kioskTheme}>
        <MemoryRouter initialEntries={['/kiosk/research?user_game_id=g1&from=report&task=42']}>
          <Routes>
            <Route path="/kiosk/research" element={<ResearchPage />} />
            <Route path="/kiosk/report" element={<div>复盘屏</div>} />
            <Route path="/kiosk/report/:taskId" element={<div>报告屏</div>} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>,
    );
    const bar = screen.getByTestId('research-pagebar');
    await waitFor(() => expect(bar.querySelector('.kiosk-pagebar__sub')).toHaveTextContent('我的对局'));
    fireEvent.click(within(bar).getByRole('button', { name: /复盘/ }));
    expect(await screen.findByText('报告屏')).toBeInTheDocument();
  });
```

- [ ] **Step 2: 跑测试,确认按预期失败**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-review/katrain/web/ui && npx vitest run src/kiosk/pages/ResearchPage.userGame.test.tsx`

预期:
- 「token 为 null 而已登录」FAIL(`get` 未被调用,`waitFor` 超时);
- 「谱取不到时副标题说出来」FAIL(找不到「这一局读不到」);
- 「从报告进来,返回键回的是这一份报告」FAIL(token 为 null 时副标题永远不出现,`waitFor` 超时;若只改判别位而 provenance 仍写 `backTo.path`,它会落到「复盘屏」照样红);
- 「没登录时不去取谱」PASS(改前本来就不发请求,它守的是改后别把闸整个拿掉);
- 原有两条 PASS。

- [ ] **Step 3: 改 ResearchPage**

`ResearchPage.tsx:134`:

```tsx
  const { token, isAuthenticated } = useAuth();
```

`ResearchPage.tsx:437-455` 整段换成:

```tsx
  const userGameRef = useRef(false);
  useEffect(() => {
    const id = searchParams.get('user_game_id');
    // ⚠️ 判 `isAuthenticated`,不判 `token`:盒上严格 SSO 的 token 恒为 null(凭据在 HttpOnly
    // cookie 里),判 `!token` 等于把每个已登录的人都当成未登录。屏 20「去研究」是全仓唯一
    // 带 `user_game_id` 进来的入口,盒上打开的就是一块空盘(2026-09-14 调研 S1)。
    if (!id || userGameRef.current || !isAuthenticated) return;
    userGameRef.current = true;
    UserGamesAPI.get(token, id).then(async (detail) => {
      if (!detail.sgf_content) return;
      board.loadFromSGF(detail.sgf_content);
      const head = detail.title
        || `${detail.player_black ?? t('research:black', '黑方')} vs ${detail.player_white ?? t('research:white', '白方')}`;
      const stamp = detail.game_date ?? detail.created_at;
      const when = stamp ? Date.parse(stamp) : NaN;
      setProvenance({
        label: `${t('research:from_my_games', '我的对局')}：${head}${Number.isNaN(when) ? '' : ` · ${whenLabel(when, t)}`}`,
        // `backPath` 不是 `backTo.path`:从屏 20 进来时带着 `task`,返回要回**这一份报告**而不是列表。
        // 盒上以前 provenance 永远是 null、返回键碰巧走的就是 `backPath`;这里修通后不许把它退回列表。
        backPath, backLabel: backTo.label,
      });
      if (searchParams.get('analyze') === '1') await startScan(detail.sgf_content);
    }).catch((err) => {
      console.error('Failed to load user game for deep link:', err);
      // 取不到就说取不到:一块没有副标题的空盘,看起来和「还没开始摆」一模一样。
      setProvenance({
        label: t('research:user_game_failed', '这一局读不到'),
        backPath, backLabel: backTo.label,
      });
    });
  }, [searchParams, token, isAuthenticated]); // eslint-disable-line react-hooks/exhaustive-deps
```

- [ ] **Step 4: 跑测试,确认通过、研究屏其它单测不回归**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-review/katrain/web/ui && npx vitest run src/kiosk/pages/ResearchPage.userGame.test.tsx src/kiosk/__tests__/ResearchPage.test.tsx && npx tsc -b`

预期:两个文件全部 PASS;`tsc -b` 0 退出。

- [ ] **Step 5: 提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-review
git add katrain/web/ui/src/kiosk/pages/ResearchPage.tsx katrain/web/ui/src/kiosk/pages/ResearchPage.userGame.test.tsx
git diff --cached --stat
git commit -m "$(cat <<'EOF'
fix(kiosk): 盒上从报告点「去研究」是空棋盘 —— 深链的闸还钉在 token 上

屏 20「去研究」是全仓唯一带 user_game_id 进研究屏的入口。ResearchPage 那条
加载 effect 先判 !token 就返回,而盒上严格 SSO 的 token 恒为 null,依赖里的
token 也永不变 ⇒ 不重试、盘空、没有任何提示。下游 UserGamesAPI.get 本来就
接受 null、靠 cookie 认证,只是前端判据错。改判 isAuthenticated;取谱失败时
副标题写「这一局读不到」,不留一块没有解释的空盘。provenance 的返回路径改用
带 task 的 backPath —— 否则修通后盒上「返回」会从这份报告退成报告列表。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: N7 · 复盘列表加载态初值判 `isAuthenticated`

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/ReportsPage.tsx:119`
- Test: 既有 `katrain/web/ui/src/kiosk/pages/ReportsPage.test.tsx`、`ReportsPage.polling.test.tsx`(不新增)

**Interfaces:**
- Consumes / Produces:无。

- [ ] **Step 1: 改初值**

`ReportsPage.tsx:119`

```tsx
  const [gamesLoading, setGamesLoading] = useState(Boolean(token));
```

换成

```tsx
  // 初值判 `isAuthenticated` 不判 `token`:盒上 token 恒为 null,判 token 时首帧 gamesLoading=false、
  // games=[],列表回来之前会先闪一帧「还没有下过的棋」(2026-09-14 调研 N7)。
  // 不配单测:jsdom 的 render 包在 act 里,effect 在断言前已经跑完,「effect 之前那一帧」测不到。
  const [gamesLoading, setGamesLoading] = useState(isAuthenticated);
```

- [ ] **Step 2: 跑屏 19 既有单测**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-review/katrain/web/ui && npx vitest run src/kiosk/pages/ReportsPage.test.tsx src/kiosk/pages/ReportsPage.polling.test.tsx`

预期:全部 PASS。

- [ ] **Step 3: 提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-review
git add katrain/web/ui/src/kiosk/pages/ReportsPage.tsx
git commit -m "$(cat <<'EOF'
fix(kiosk): 复盘列表加载态初值还在读 token —— 盒上首帧会先闪一下空态

2c2034e0 把复盘链的请求闸改成了 isAuthenticated,同文件 gamesLoading 的初值
漏了:盒上 token 恒为 null ⇒ 首帧 loading=false、games=[],落进「还没有下过的棋」。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---
### Task 4: R1 · 屏 19 三格与胜率红段改走服务端七档

**Files:**
- Modify(整文件重写): `katrain/web/ui/src/features/report/reportStats.ts`
- Modify: `katrain/web/ui/src/kiosk/components/report/ReviewWinratePlot.tsx:1`, `:37-46`
- Modify(仅注释): `katrain/web/ui/src/kiosk/pages/ReportsPage.tsx:48-55`, `katrain/web/ui/tests/report-kiosk.spec.ts:102-103`, `katrain/web/ui/src/kiosk/pages/ReportDetailPage.test.tsx:118`
- Test: `katrain/web/ui/src/features/report/reportStats.test.ts`, `katrain/web/ui/src/kiosk/pages/ReportsPage.test.tsx`

**Interfaces:**
- Consumes:`gradedMoves`、`isBad`、`isBrilliant`(`features/analysis/moveGrade.ts:40-46`、`:387-401`);`toMoveAnalysisMap(reportMoves: ReportTaskMove[], userGameId: string): Record<number, MoveAnalysis>`(`features/report/reportModel.ts:180`)。
- Produces:
  - `summarizeReportMoves(moves: readonly ReportTaskMove[], color: 'B' | 'W'): ReportSummary`(签名不变,`mistakes` / `brilliants` 语义改为七档)。
  - `interface WinratePoint { moveNumber: number; winrate: number; player: 'B' | 'W' | null; bad: boolean }`(**`deltaScore` 字段删除,换成 `bad`**)。
  - 删除导出:`BRILLIANT_SCORE_GAIN`、`MISTAKE_SCORE_LOSS`、`KeyMove`、`keyMoves`。

- [ ] **Step 1: 改 `reportStats.test.ts`,写失败测试**

1)把第 1-11 行的 import 换成:

```ts
import { describe, expect, it } from 'vitest';

import type { ReportTaskMove } from '../../api/reportApi';
import type { TopMove } from '../../types/live';
import { gradedMoves, isBad, isBrilliant } from '../analysis/moveGrade';
import { toMoveAnalysisMap } from './reportModel';
import { summarizeReportMoves, winrateSeries } from './reportStats';
```

2)`it('白方:只算白走的那一手,和黑方互不影响', …)` 里的 `expect(s.mistakes).toBe(0);` 改成下面两行。`GAME` 夹具不带 `grade`,走 `gradedMoves` 的退回规则,白那手亏 2 目 ≤ −1.5,落「小亏」,与屏 20「失误」tab 同一个桶:

```ts
    // 夹具不带 grade ⇒ 走 gradedMoves 的退回规则:亏 2 目 ≤ −1.5 是「小亏」,与屏 20「失误」tab 同桶。
    expect(s.mistakes).toBe(1);
```

3)把整条 `it('阈值就是仓里已有的那两个数 —— 换了就和报告详情对不上', …)`(第 81-94 行)换成:

```ts
  // 云端太旧、整份报告一手 grade 都没有时,退回规则**只在 gradedMoves 一处** —— 这里不另写一份。
  it('整份报告都没有 grade 时,退回规则和屏 20 是同一条', () => {
    const edge = [
      move({ move_number: 0, score_lead: 0, winrate: 0.5 }),
      move({ move_number: 1, actual_player: 'B', delta_score: 2, score_lead: 2, winrate: 0.6 }),
      move({ move_number: 2, actual_player: 'B', delta_score: -3, score_lead: -1, winrate: 0.4 }),
      move({ move_number: 3, actual_player: 'B', delta_score: 1.99, score_lead: 1, winrate: 0.5 }),
      move({ move_number: 4, actual_player: 'B', delta_score: -1.49, score_lead: -2, winrate: 0.4 }),
    ];
    const s = summarizeReportMoves(edge, 'B');
    const screen20 = gradedMoves(toMoveAnalysisMap(edge, 'g'));
    expect(s.brilliants).toBe(screen20.filter(isBrilliant).length);
    expect(s.mistakes).toBe(screen20.filter(isBad).length);
    expect(s.brilliants).toBe(1);   // 正好 2 算,1.99 不算
    expect(s.mistakes).toBe(1);     // 正好 -3 算,-1.49 不到小亏线
  });
```

4)在文件里 `const GAME: ReportTaskMove[] = [ … ];` 定义之后追加一份文件级夹具(`summarizeReportMoves` 与 `winrateSeries` 两组共用):

```ts
/**
 * R1 回归夹具(2026-09-14 调研):grade 与 delta_score **故意打架**,而且打架的方式让
 * 「旧口径的黑 + 白」与「屏 20 的双方合计」**两个数都不相等** —— 否则等式那条改前也是绿的。
 *   旧口径(delta ≥2 妙 / ≤−3 失误):黑 妙1 失1,白 妙1 失0 ⇒ 合计 妙2 失1
 *   七档(isBrilliant / isBad):     黑 妙0 失1,白 妙1 失1 ⇒ 合计 妙1 失2
 */
const FIGHTING: ReportTaskMove[] = [
  move({ move_number: 0, winrate: 0.5, score_lead: 0 }),
  // 黑:两次搜索之差 +3(旧口径妙手),服务端判「最佳」
  move({ move_number: 1, winrate: 0.6, score_lead: 3, actual_player: 'B', delta_score: 3, grade: 'best' }),
  // 白:旧口径 −1(不算失误),服务端判「小亏」
  move({ move_number: 2, winrate: 0.62, score_lead: 4, actual_player: 'W', delta_score: -1, grade: 'inaccuracy' }),
  // 黑:旧口径 −4(失误),服务端在同一次搜索里只算亏 1 目,判「尚可」
  move({ move_number: 3, winrate: 0.45, score_lead: 0, actual_player: 'B', delta_score: -4, grade: 'playable' }),
  // 白:旧口径 +2.5(妙手),服务端也判「妙手」
  move({ move_number: 4, winrate: 0.4, score_lead: -1, actual_player: 'W', delta_score: 2.5, grade: 'brilliant' }),
  // 黑:两次搜索之差只有 −2(旧口径不算),服务端同一次搜索里算亏 7 目,判「恶手」
  move({ move_number: 5, winrate: 0.2, score_lead: -8, actual_player: 'B', delta_score: -2, grade: 'blunder' }),
];
```

再在 `describe('summarizeReportMoves —— 三格指标', …)` 的末尾(`it('先验缺席时复杂度退回 0,不整条崩掉', …)` 之后)追加:

```ts
  // R1 回归钉子。变异验证:把 summarizeReportMoves 退回按 delta_score 阈值数,这两条都红。
  it('失误 / 妙手按服务端七档数,不按两次搜索之差', () => {
    expect(summarizeReportMoves(FIGHTING, 'B')).toMatchObject({ brilliants: 0, mistakes: 1 });
    expect(summarizeReportMoves(FIGHTING, 'W')).toMatchObject({ brilliants: 1, mistakes: 1 });
  });

  it('黑的格 + 白的格 = 屏 20 折叠头「妙 a · 坏 b」那两个数', () => {
    const screen20 = gradedMoves(toMoveAnalysisMap(FIGHTING, 'g'));
    const black = summarizeReportMoves(FIGHTING, 'B');
    const white = summarizeReportMoves(FIGHTING, 'W');
    expect(black.brilliants + white.brilliants).toBe(screen20.filter(isBrilliant).length);
    expect(black.mistakes + white.mistakes).toBe(screen20.filter(isBad).length);
  });

  // 服务端给了 grade、这一行却没有 delta_score(`toMoveAnalysisMap` 只要胜率与目差就收这一手,
  // `_moves_with_grades` 只补 grade 不补 delta_score):屏 20 照样把它数进「坏」。
  // 准确率要 delta_score、算不了是它自己的事,两格不许跟着归零。
  // 变异验证:把「counted === 0 就整体返回 0」那种提前返回放回去,这条红。
  it('grade 有值而 delta_score 为 null:准确率是 null,失误照数,与屏 20、红段一致', () => {
    const noDelta = [
      move({ move_number: 0, winrate: 0.5, score_lead: 0 }),
      move({ move_number: 1, winrate: 0.2, score_lead: -8, actual_player: 'B', delta_score: null, grade: 'blunder' }),
    ];
    const s = summarizeReportMoves(noDelta, 'B');
    expect(s).toMatchObject({ accuracy: null, counted: 0, mistakes: 1, brilliants: 0 });
    expect(s.mistakes).toBe(gradedMoves(toMoveAnalysisMap(noDelta, 'g')).filter(isBad).length);
    expect(winrateSeries(noDelta).find((p) => p.moveNumber === 1)?.bad).toBe(true);
  });
```

5)把 `describe('winrateSeries —— 曲线的点', …)` 里第一条 `it` 整条换成下面两条:

```ts
  it('黑方胜率原样带出来,谁走的那一手也带着;坏手标记走七档的退回规则', () => {
    expect(winrateSeries(GAME)).toEqual([
      { moveNumber: 0, winrate: 0.5, player: null, bad: false },
      { moveNumber: 1, winrate: 0.46, player: 'B', bad: false },
      { moveNumber: 2, winrate: 0.55, player: 'W', bad: true },    // 亏 2 目 ⇒ 小亏
      { moveNumber: 3, winrate: 0.72, player: 'B', bad: false },
    ]);
  });

  it('红段候选(bad)与三格里的「失误」是同一个桶 —— 按 grade,不按 delta_score', () => {
    expect(winrateSeries(FIGHTING).filter((p) => p.bad).map((p) => p.moveNumber)).toEqual([2, 5]);
  });
```

6)删掉整个 `describe('keyMoves —— 重点手', …)`(第 129-194 行,文件末尾,共 6 条 `it`)。

- [ ] **Step 2: 在 `ReportsPage.test.tsx` 加页面级钉子**

在 `describe('屏 19 · 这一局的胜率', …)` 里、`it('算过了就按黑方胜率画,掉分最狠的那一手单独一段红', …)` 之后追加:

```tsx
  /**
   * R1 回归钉子(2026-09-14 调研):三格与红段都要和屏 20 用同一套判据。
   * 第 1 手「两次搜索之差」掉 4 分(过了旧失误线),可服务端在同一次搜索里只算它亏 1 目、判「尚可」。
   * 旧实现会在这里数出「失误 1 手」并画红段;按七档,这一局没有坏手。
   */
  it('三格和红段都按服务端七档 —— 旧失误线上的「尚可」不算失误、不画红', async () => {
    mocks.getMoves.mockResolvedValue([
      reportMove({ move_number: 0, winrate: 0.5, score_lead: 0 }),
      reportMove({ move_number: 1, winrate: 0.3, score_lead: -4, actual_player: 'B', delta_score: -4, grade: 'playable' }),
      reportMove({ move_number: 2, winrate: 0.35, score_lead: -5, actual_player: 'W', delta_score: -1, grade: 'very_good' }),
      reportMove({ move_number: 3, winrate: 0.55, score_lead: -2, actual_player: 'B', delta_score: 3, grade: 'best' }),
    ]);
    mocks.hookResult = { ...mocks.hookResult, reportStatesByGame: { a: { completedNormal: task() } } };
    renderPage();
    await waitFor(() => expect(screen.getByTestId('review-winrate-plot')).toHaveAttribute('data-state', 'plotted'));
    expect(cellValue('失误')).toBe('0 手');
    expect(cellValue('妙手')).toBe('0 手');
    expect(screen.queryByTestId('review-winrate-drop')).toBeNull();
  });
```

并把同文件 `it('有报告时三格是真数字 —— 妙手那一格数的是 delta_score ≥ 2 的手', …)` 的标题改成 `'有报告时三格是真数字(夹具不带 grade,走 gradedMoves 的退回规则)'`,测试体不动。

- [ ] **Step 3: 跑测试,确认按预期失败**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-review/katrain/web/ui && npx vitest run src/features/report/reportStats.test.ts src/kiosk/pages/ReportsPage.test.tsx`

预期 FAIL:
- 「白方:只算白走的那一手」(旧实现 mistakes=0);
- 「失误 / 妙手按服务端七档数」「黑的格 + 白的格 = 屏 20」(旧实现合计 妙2 失1,屏 20 是 妙1 失2);
- 「grade 有值而 delta_score 为 null」(旧实现 counted=0 提前返回 mistakes=0,且没有 `bad` 字段);
- winrateSeries 两条(`bad` 字段不存在);
- 屏 19「三格和红段都按服务端七档」(旧实现写「1 手」、有红段)。

预期 PASS(改前就绿,是守卫不是回归钉子):「整份报告都没有 grade 时,退回规则和屏 20 是同一条」。它守的是改后别在 `reportStats.ts` 里另写一份退回规则。

- [ ] **Step 4: 重写 `reportStats.ts`**

整文件替换为:

```ts
import type { ReportTaskMove } from '../../api/reportApi';
import type { MoveAnalysis } from '../../types/live';
import { gradedMoves, isBad, isBrilliant } from '../analysis/moveGrade';
import { toMoveAnalysisMap } from './reportModel';

/**
 * 从一份**已经跑完的报告**里算出复盘屏左栏那三格(准确率 / 失误 / 妙手)和胜率曲线的点。
 *
 * ## 数据在哪儿(2026-08-22 核实)
 *
 * `report_task_moves` 每一行 = **走完第 N 手之后**那个局面的分析
 * (`cron/jobs/report_analyze.py:304` 送进去的是 `moves[:move_number]`)。所以
 * **第 N 手的候选着法在第 N-1 行里** —— 那一行的 `top_moves` 是「该走第 N 手时
 * KataGo 给的十个候选」,每个带 `score_lead` / `winrate` / `prior`。
 * `GET /api/v1/reports/{task_id}/moves` 原样吐出来,旧报告缺 `grade` 时服务端按需补算。
 *
 * ## 失误 / 妙手:和屏 20 走同一条管线(2026-09-14 改,调研 R1)
 *
 * 以前这两格按 `delta_score`(两次独立搜索之差)自己数:≥2 算妙手、≤−3 算失误。
 * 那根轴上界卡在 0 附近,「妙手」基本只在搜索噪声上触发(`docs/move-grading/design.md` §1);
 * 而屏 20 的「妙 a · 坏 b」和妙手 / 失误 tab 早已改读服务端七档 ⇒ 同一局两屏数字对不上。
 *
 * 现在两格都经 `toMoveAnalysisMap → gradedMoves` 判级,**与屏 20 逐字同一条路**:
 *  - 失误 = `isBad`(小亏 / 失误 / 恶手),与屏 20「失误」tab 同一个桶;
 *  - 妙手 = `isBrilliant`;
 *  - 云端太旧、整份报告一手 grade 都没有时,退回规则只写在 `gradedMoves` 里,这里不另写。
 * 区别只有一个:这两格**只数视角那一方**(左栏写着是谁的视角),屏 20 折叠头是双方合计。
 * ⇒ 黑的格 + 白的格 = 屏 20 的数。`reportStats.test.ts` 钉着这条等式。
 *
 * ## 准确率没换轴
 *
 * 照搬 `katrain/core/ai.py:212-262` 的 `game_report()`:
 * `100 × 0.75^加权丢分`,权重是「这一手有多难」(候选着法按 policy 先验加权的平均丢分)。
 * **不自己发明公式** —— 桌面版和 web 版的对局报告显示的就是这个数,同一局在两处必须一样。
 * 它仍建在 `delta_score` 上;`ai.py` 换不换轴是 move-grading 登记的遗留,两边必须一起动。
 */

export interface ReportSummary {
  /** 0–100。**null = 一手都没算进来**(报告是空的 / 这个颜色没有落过子),不是 0。 */
  accuracy: number | null;
  mistakes: number;
  brilliants: number;
  /** 被算进**准确率**的手数(有 delta_score 的那些)。失误 / 妙手两格不看它 —— 它们走判级管线。 */
  counted: number;
}

interface Candidate {
  move?: string | null;
  score_lead?: number | null;
  prior?: number | null;
}

/**
 * `top_moves` 在接口上是 `TopMove[] | null`,但它来自 `JSON` 列 —— 真跑起来什么都可能是。
 * 只挑我们要的两个字段,缺了就当这条候选不存在。
 */
function candidatesOf(move: ReportTaskMove | undefined): Candidate[] {
  const raw = move?.top_moves;
  if (!Array.isArray(raw)) return [];
  return raw as unknown as Candidate[];
}

const sign = (player: 'B' | 'W'): number => (player === 'B' ? 1 : -1);

/**
 * 一手棋有多难 —— `ai.py:236-243` 那段。候选着法按 policy 先验加权的平均丢分:
 * 满盘只有一步不亏的时候这个数大,随便走都差不多的时候接近 0。
 *
 * 先验缺席时**退回 0**(= 这手不难),和 `ai.py` 的 `filtered_cands` 过滤一致 ——
 * 那边要求 `"prior" in d`,这里要求 `prior != null`(JSON 列里缺字段读出来是 undefined)。
 */
function complexityOf(prevRootScore: number, cands: Candidate[], player: 'B' | 'W'): number {
  const s = sign(player);
  let weighted = 0;
  let priors = 0;
  for (const c of cands) {
    if (c.prior == null || c.score_lead == null) continue;
    const candPointsLost = s * (prevRootScore - c.score_lead);
    weighted += Math.max(candPointsLost, 0) * c.prior;
    priors += c.prior;
  }
  if (priors <= 0) return 0;
  return Math.min(1, weighted / priors);
}

/**
 * 屏 20 用的就是这一条:`useReportDetail` 里 `toMoveAnalysisMap`,`MoveGradePanel` 里 `gradedMoves`。
 * 屏 19 拿同一份逐手数据再走一遍,两屏才不会各判各的。
 */
function gradedReportMoves(moves: readonly ReportTaskMove[]): MoveAnalysis[] {
  return gradedMoves(toMoveAnalysisMap([...moves], ''));
}

/**
 * @param moves  `GET /reports/{id}/moves` 的返回,**按 move_number 升序**(接口已经排好)
 * @param color  算谁的 —— 准确率是**分颜色**的,两个人的手混在一起算出来的数没有意义
 */
export function summarizeReportMoves(
  moves: readonly ReportTaskMove[],
  color: 'B' | 'W',
): ReportSummary {
  const byNumber = new Map<number, ReportTaskMove>();
  for (const m of moves) byNumber.set(m.move_number, m);

  let counted = 0;
  let lossSum = 0;
  let weightSum = 0;

  for (const move of moves) {
    if (move.actual_player !== color) continue;
    if (move.delta_score == null) continue;      // 第 0 行(空盘)和算失败的那些行
    counted += 1;

    // `ai.py:231` —— 亏分才计,赚的那些按 0 算(赚分不该把准确率抬到 100 以上)
    const pointsLost = Math.max(0, -move.delta_score);
    const prev = byNumber.get(move.move_number - 1);
    const complexity = prev?.score_lead == null
      ? 0
      : complexityOf(prev.score_lead, candidatesOf(prev), color);
    // `ai.py:244` —— 简单局面走错扣得狠,难局面走错网开一面;下界 0.05 让它永远有点权重
    const adjWeight = Math.max(0.05, Math.min(1, Math.max(complexity, pointsLost / 4)));
    lossSum += pointsLost * adjWeight;
    weightSum += adjWeight;
  }

  // 两格**不看 counted**:`counted` 只数有 delta_score 的手(准确率要它),而判级那条管线只要胜率与目差。
  // 服务端给了 grade、这一行没有 delta_score 时,屏 20 照样数它 —— 这里若跟着 counted 归零,等式就破了。
  const mine = gradedReportMoves(moves).filter((m) => m.player === color);
  const mistakes = mine.filter(isBad).length;
  const brilliants = mine.filter(isBrilliant).length;
  if (counted === 0) return { accuracy: null, mistakes, brilliants, counted: 0 };
  const weightedLoss = lossSum / (weightSum || 1e-6);
  return { accuracy: 100 * 0.75 ** weightedLoss, mistakes, brilliants, counted };
}

export interface WinratePoint {
  moveNumber: number;
  /** **黑方**胜率 0–1。cron 那条线固定 `reportAnalysisWinratesAs: "BLACK"`(`clients/katago.py:83`), 所以这个字段跟谁走子无关。 */
  winrate: number;
  /** 走出这个局面的那一手是谁下的 —— 红段(掉分的那一手)要靠它判方向。 */
  player: 'B' | 'W' | null;
  /**
   * 这一手是不是坏手(小亏 / 失误 / 恶手)。**与三格里的「失误」、屏 20 的失误 tab 同一个桶** ——
   * 红段只在这些手里挑,屏上标红的那一手才一定能在失误 tab 里找到。
   */
  bad: boolean;
}

/**
 * 曲线的点。**只取真算出来的那些行** —— 中间断掉的手数不补点、不插值:
 * 一条连起来的线会把「只算到第 40 手」画成「整局都算过了」。
 */
export function winrateSeries(moves: readonly ReportTaskMove[]): WinratePoint[] {
  const badMoves = new Set(gradedReportMoves(moves).filter(isBad).map((m) => m.move_number));
  const points: WinratePoint[] = [];
  for (const m of moves) {
    if (m.winrate == null) continue;
    points.push({
      moveNumber: m.move_number,
      winrate: m.winrate,
      player: m.actual_player === 'B' || m.actual_player === 'W' ? m.actual_player : null,
      bad: badMoves.has(m.move_number),
    });
  }
  return points;
}
```

- [ ] **Step 5: 改 `ReviewWinratePlot.tsx`**

第 1 行:

```tsx
import type { WinratePoint } from '../../../features/report/reportStats';
```

第 37-46 行(`worstDropIndex` 开头到 `if (p.player == null) continue;`)换成:

```tsx
/** 掉得最狠的那一手 —— 红的那一段就是它。返回的是**后一个点**在数组里的下标。 */
function worstDropIndex(points: readonly WinratePoint[]): number | null {
  let worst: number | null = null;
  let worstSwing = 0;
  for (let i = 1; i < points.length; i += 1) {
    const p = points[i];
    // 候选只在坏手(小亏 / 失误 / 恶手)里挑 —— 与三格里的「失误」、屏 20 失误 tab 同一个桶(服务端七档)。
    // 以前卡的是 `delta_score ≤ −3` 那条旧线,标红的那一手可能根本不在失误 tab 里。
    if (!p.bad || p.player == null) continue;
```

(第 47 行起的 `// 走子方的损失换算成胜率…` 与循环剩余部分不动。)

- [ ] **Step 6: 改两处过期注释**

`ReportsPage.tsx:52-55`:

```tsx
 * **围棋这条线不是**:报告是 cron 离线跑的(`katrain/cron/jobs/report_analyze.py`),
 * 每手 500 或 2000 次计算,跟盒子算力无关;而且这个仓里已经有一份妙手口径
 * (`features/report/reportModel.ts:192`,`delta_score >= 2`),不用现发明。
 * ⇒ 照稿子写「妙手」。算式和出处见 `features/report/reportStats.ts`。
```

换成

```tsx
 * **围棋这条线不是**:报告是 cron 离线跑的(`katrain/cron/jobs/report_analyze.py`),
 * 每手 500 或 2000 次计算,跟盒子算力无关;判级在服务端(`katrain/core/move_grade.yaml` 七档)。
 * ⇒ 照稿子写「妙手」。2026-09-14 起两格与屏 20 走同一条判级管线,见 `features/report/reportStats.ts`。
```

`tests/report-kiosk.spec.ts:102-103`:

```ts
  // 第 3 手是黑走的,黑的胜率从 54% 掉到 30% —— `keyMoves` 要**目和胜率同时掉**才收，
  // 只把 `delta_score` 写成负数、胜率却一路上扬,那一手一样进不了「重点手」。
```

换成

```ts
  // 第 3 手是黑走的,黑的胜率从 54% 掉到 30% —— 胜率图的红段要**这一手是坏手、胜率也真掉了**才画,
  // 只把分数写成负数、胜率却一路上扬,那一手一样不会标红。
```

`src/kiosk/pages/ReportDetailPage.test.tsx:118`(注释里点了 `keyMoves` 的名字,不改的话 Step 7 那条 `rg` 不会零命中):

```tsx
 * 旧的「重点手」走 `reportStats.keyMoves(moves)`(按胜率掉点挑),
```

换成

```tsx
 * 旧的「重点手」按胜率掉点挑(那份实现 2026-09-14 已删),
```

- [ ] **Step 7: 跑测试与类型检查**

Run:

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-review/katrain/web/ui
npx vitest run src/features/report/reportStats.test.ts src/kiosk/pages/ReportsPage.test.tsx src/kiosk/pages/ReportDetailPage.test.tsx src/features/report/reportModel.test.ts
npx tsc -b
rg -n "MISTAKE_SCORE_LOSS|BRILLIANT_SCORE_GAIN|keyMoves" src || echo "旧常量零命中"
rg -n "deltaScore" src --glob '!**/reportModel.ts' || echo "deltaScore 零命中"
```

预期:四个文件全部 PASS;`tsc -b` 0 退出;两条 `rg` 分别输出「旧常量零命中」「deltaScore 零命中」(`reportModel.ts` 里的局部变量 `deltaScore` 是 `toMoveAnalysisMap` 给退回规则算布尔量的输入,保留)。

- [ ] **Step 8: 提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-review
git add katrain/web/ui/src/features/report/reportStats.ts katrain/web/ui/src/features/report/reportStats.test.ts \
  katrain/web/ui/src/kiosk/components/report/ReviewWinratePlot.tsx katrain/web/ui/src/kiosk/pages/ReportsPage.tsx \
  katrain/web/ui/src/kiosk/pages/ReportsPage.test.tsx katrain/web/ui/tests/report-kiosk.spec.ts \
  katrain/web/ui/src/kiosk/pages/ReportDetailPage.test.tsx
git diff --cached --stat
git commit -m "$(cat <<'EOF'
fix(kiosk-report): 屏 19 的失误/妙手与两屏红段还在旧单边轴上 —— 和屏 20 对不上

屏 19 三格按 delta_score(两次搜索之差)≥2 / ≤−3 自己数,胜率图红段也卡在
≤−3 那条线;屏 20 的「妙 a · 坏 b」与失误 tab 早已读服务端七档 ⇒ 同一局两屏
数字对不上,屏 20 内部红段与失误 tab 也分裂。

改为和屏 20 走同一条 toMoveAnalysisMap → gradedMoves 管线:失误 = isBad、
妙手 = isBrilliant,旧云端退回规则只在 gradedMoves 一处;红段候选同一个桶。
黑格 + 白格 = 屏 20 的数,单测钉住。准确率不换轴(与 ai.py 一起动)。
顺带删掉只剩单测消费的 keyMoves 与两个旧阈值常量。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---
### Task 5: N24 / R5 · 请求失败分类器、API 错误带状态码、屏上的话

**Files:**
- Create: `katrain/web/ui/src/utils/requestFailure.ts`
- Create: `katrain/web/ui/src/utils/requestFailure.test.ts`
- Modify: `katrain/web/ui/src/api/reportApi.ts:88-91`, `katrain/web/ui/src/api/userGamesApi.ts:116-119`
- Modify(追加): `katrain/web/ui/src/kiosk/components/report/reviewPresentation.ts`
- Test: `katrain/web/ui/src/api/reportApi.test.ts`, `katrain/web/ui/src/api/userGamesApi.test.ts`, `katrain/web/ui/src/kiosk/components/report/reviewPresentation.test.ts`

**Interfaces:**
- Produces:
  - `export type RequestFailureKind = 'offline' | 'not_found' | 'no_credits' | 'bad_sgf' | 'other';`
  - `export function requestFailureKind(error: unknown): RequestFailureKind;`(`src/utils/requestFailure.ts`,共享领地,零 import)
  - `export function cacheBackedReadFailureKind(error: unknown): RequestFailureKind;`(同文件;`not_found` 降为 `other`,给「云端失败退本机缓存」的 `GET /user-games/{id}` 用)
  - `ReportsAPI.*` / `UserGamesAPI.*` 非 2xx 时拒绝的 `Error` 上多两个自有属性:`status: number`、`body: string`;`message` 不变。
  - `export function failureReason(kind: RequestFailureKind, t: TFn): string;`(`other` 返回 `''`)
  - `export function failureLine(prefix: string, kind: RequestFailureKind, t: TFn): string;`(有原因时 `${prefix} · ${reason}`,否则 `prefix`)——都在 `kiosk/components/report/reviewPresentation.ts`。

- [ ] **Step 1: 写分类器的失败测试**

新建 `src/utils/requestFailure.test.ts`:

```ts
import { describe, expect, it } from 'vitest';

import { cacheBackedReadFailureKind, requestFailureKind } from './requestFailure';

const httpError = (status: number, body = '') =>
  Object.assign(new Error(`Request failed ${status}: ${body}`), { status, body });

describe('requestFailureKind —— 请求失败分几类', () => {
  // 盒上报告 / 对局接口经本机服务代理云端,云端连不上时本机回 503「Remote … unavailable」。
  it('502 / 503 / 504 是连不上', () => {
    expect(requestFailureKind(httpError(503, '{"detail":"Remote report service unavailable"}'))).toBe('offline');
    expect(requestFailureKind(httpError(502))).toBe('offline');
    expect(requestFailureKind(httpError(504))).toBe('offline');
  });

  it('404 是找不到 —— 和连不上分开说', () => {
    expect(requestFailureKind(httpError(404, '{"detail":"Report task not found"}'))).toBe('not_found');
  });

  // 计费闸今天关着(BILLING_ENFORCED 默认 False 且读不到 env);开闸后创建报告会回这个。
  it('402 且 code 是 insufficient_credits 才算积分不足', () => {
    expect(requestFailureKind(httpError(402, '{"detail":{"code":"insufficient_credits","need":125,"have":0}}')))
      .toBe('no_credits');
    expect(requestFailureKind(httpError(402, 'Payment Required'))).toBe('other');
  });

  it('400 且 code 是 unparsable_sgf 是谱读不出来', () => {
    expect(requestFailureKind(httpError(400, '{"detail":{"code":"unparsable_sgf","message":"bad"}}'))).toBe('bad_sgf');
    expect(requestFailureKind(httpError(400, '{"detail":"Only failed tasks can be retried"}'))).toBe('other');
  });

  // 分不出就说分不出:不许把一个没有状态码的错猜成「连不上」。
  it('没有数字 status 的错、以及其余状态码,一律 other', () => {
    expect(requestFailureKind(new Error('boom'))).toBe('other');
    expect(requestFailureKind(new TypeError('Failed to fetch'))).toBe('other');
    expect(requestFailureKind('no details')).toBe('other');
    expect(requestFailureKind(null)).toBe('other');
    expect(requestFailureKind(Object.assign(new Error('x'), { status: '503' }))).toBe('other');
    expect(requestFailureKind(httpError(409, 'report already exists'))).toBe('other');
  });

  // `api.ts` 的 `ApiError`、`features/aiLadder` 的 `AiLadderApiError` 只带 status 不带 body。
  it('只带 status 不带 body 的错(ApiError 形状)也能分', () => {
    expect(requestFailureKind(Object.assign(new Error('Request failed 503: x'), { status: 503 }))).toBe('offline');
  });
});

describe('cacheBackedReadFailureKind —— 读的是「云端失败退本机缓存」的接口', () => {
  // 盒上 GET /user-games/{id}:云端连不上 / 超时 / 回任何 HTTP 错都退本机缓存,缓存里没有也回 404。
  // 这条 404 证明不了「云端没有这一局」,不许被说成「已经不在了」。
  it('404 降为 other,其余照 requestFailureKind', () => {
    expect(cacheBackedReadFailureKind(httpError(404, '{"detail":"Game not found"}'))).toBe('other');
    expect(cacheBackedReadFailureKind(httpError(503))).toBe('offline');
    expect(cacheBackedReadFailureKind(new Error('boom'))).toBe('other');
  });
});
```

- [ ] **Step 2: 给两个 API 客户端各加一条失败测试**

`src/api/reportApi.test.ts`,在 `it('surfaces non-success response text', …)` 之后追加:

```ts
  // N24:屏上要分「连不上 / 找不到 / 积分不足」,所以错误对象得带着状态码与原始 body;
  // message 保持原句 —— galaxy 屏上与上一条单测都认它。
  it('非 2xx 时拒绝的错误带 status 与原始 body,message 不变', async () => {
    const body = '{"detail":"Remote report service unavailable"}';
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      text: vi.fn().mockResolvedValue(body),
    }));

    await expect(ReportsAPI.get(null, 7)).rejects.toMatchObject({
      message: `Request failed 503: ${body}`,
      status: 503,
      body,
    });
  });
```

`src/api/userGamesApi.test.ts`,在 `it('surfaces non-success response text', …)` 之后追加:

```ts
  it('非 2xx 时拒绝的错误带 status 与原始 body,message 不变', async () => {
    const body = '{"detail":"Remote server unavailable"}';
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      text: vi.fn().mockResolvedValue(body),
    }));

    await expect(UserGamesAPI.delete(null, 'game-1')).rejects.toMatchObject({
      message: `Request failed 503: ${body}`,
      status: 503,
      body,
    });
  });
```

- [ ] **Step 3: 给 `failureLine` 加一条失败测试**

`src/kiosk/components/report/reviewPresentation.test.ts`:第 4 行 import 改成

```ts
import { failureLine, failureReason, outcomeLine, rowDisc, rowState, rowTitle, yourColor } from './reviewPresentation';
```

文件末尾追加:

```ts
describe('failureLine —— 请求失败时屏上怎么说', () => {
  // 分不出原因时**不编一个**:「稍后再试」对一个永久的 409 是假话。也不印后端原文。
  it('分得出原因就说「做什么没成 · 为什么」,分不出只说前半句', () => {
    expect(failureLine('删除对局失败', 'offline', t)).toBe('删除对局失败 · 连不上云端');
    expect(failureLine('报告读不出来', 'not_found', t)).toBe('报告读不出来 · 已经不在了');
    expect(failureLine('生成报告', 'no_credits', t)).toBe('生成报告 · 积分不足');
    expect(failureLine('导入 SGF 失败', 'bad_sgf', t)).toBe('导入 SGF 失败 · 这份谱读不出来');
    expect(failureLine('删除对局失败', 'other', t)).toBe('删除对局失败');
    expect(failureReason('other', t)).toBe('');
  });
});
```

- [ ] **Step 4: 跑测试,确认失败**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-review/katrain/web/ui && npx vitest run src/utils/requestFailure.test.ts src/api/reportApi.test.ts src/api/userGamesApi.test.ts src/kiosk/components/report/reviewPresentation.test.ts`

预期 FAIL:`requestFailure.test.ts` 整个文件导入失败(模块不存在);两个 API 客户端新加的那条(没有 `status` / `body`);`reviewPresentation.test.ts` 的 `failureLine`(未导出)。其余原有用例 PASS。

- [ ] **Step 5: 实现分类器**

新建 `src/utils/requestFailure.ts`:

```ts
/**
 * 请求失败分几类 —— **屏上怎么说由调用方定,这里只分类**。
 *
 * 为什么要分:盒上报告与对局接口经本机服务代理云端(`RepositoryDispatcher._remote_only`),
 * 云端连不上时回 503。屏 20 以前一律写「未找到复盘。」,再把 `Request failed 503: {…}`
 * 印在下面:「连不上」被说成「找不到」,那段原文用户也看不懂(2026-09-14 调研 N24)。
 *
 * 判据只认**数字 `status`**,不认类。`reportApi` / `userGamesApi` 的 `authFetch`、`api.ts` 的
 * `ApiError`、`AiLadderApiError` 都带它。在 catch 块里做 `instanceof`,模块被 mock 掉时会自己抛
 * (`kiosk/pages/AiSetupPage.tsx` 那段注释踩过)。没有 status 的一律 `other`,**不猜**:
 * `fetch` 自己抛的 TypeError 在盒上意味着本机服务没起,那时这一屏本身就不在了。
 *
 * 这个文件在共享领地(两个构建都打进去),不许 import `src/kiosk/**` / `src/galaxy/**`。
 */
export type RequestFailureKind = 'offline' | 'not_found' | 'no_credits' | 'bad_sgf' | 'other';

/** 后端 `HTTPException(detail={"code": …})` 的那个 code。body 不是这个形状就是 null。 */
function detailCode(body: unknown): string | null {
  if (typeof body !== 'string' || body === '') return null;
  try {
    const parsed = JSON.parse(body) as { detail?: { code?: unknown } } | null;
    const code = parsed?.detail?.code;
    return typeof code === 'string' ? code : null;
  } catch {
    return null;
  }
}

export function requestFailureKind(error: unknown): RequestFailureKind {
  const carrier = (typeof error === 'object' && error !== null ? error : {}) as {
    status?: unknown;
    body?: unknown;
  };
  if (typeof carrier.status !== 'number') return 'other';
  const { status } = carrier;
  if (status === 502 || status === 503 || status === 504) return 'offline';
  if (status === 404) return 'not_found';
  const code = detailCode(carrier.body);
  // 402 来自 `endpoints/reports.py` 的计费闸(今天关着);只认 code,不认状态码本身。
  if (status === 402 && code === 'insufficient_credits') return 'no_credits';
  if (status === 400 && code === 'unparsable_sgf') return 'bad_sgf';
  return 'other';
}

/**
 * 读的是「云端失败就退本机缓存」的接口时用这个。今天只有盒上的 `GET /user-games/{id}`:
 * `core/repository.py` 的 `user_games_get` 在云端连不上 / 超时 / 回任何 HTTP 错时都退回本机缓存,
 * 缓存里没有,`endpoints/user_games.py` 的 `get_user_game` 也回 404。
 * ⇒ 这条 404 **证明不了云端没有这一局**(列表从云端读到、随后断网、点一局本机没缓存过的,就是它),
 * 说「已经不在了」是编原因。降为 `other`,屏上只说「做什么没成」。
 *
 * 报告接口(`endpoints/reports.py` 的 `_dispatch_remote_only`)与删除(`_remote_only`)不退缓存,
 * 上游 404 原码透传,那里的 404 是云端说的,照用 `requestFailureKind`。
 */
export function cacheBackedReadFailureKind(error: unknown): RequestFailureKind {
  const kind = requestFailureKind(error);
  return kind === 'not_found' ? 'other' : kind;
}
```

- [ ] **Step 6: 两个 `authFetch` 挂 `status` / `body`**

`src/api/reportApi.ts:88-91`:

```ts
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed ${response.status}: ${body}`);
  }
```

换成

```ts
  if (!response.ok) {
    const body = await response.text();
    // `status` / `body` 挂在错误上,给 `utils/requestFailure.ts` 分「连不上 / 找不到 / 积分不足」;
    // message 保持原句 —— galaxy 屏上与既有单测都认这一句。
    throw Object.assign(new Error(`Request failed ${response.status}: ${body}`), { status: response.status, body });
  }
```

`src/api/userGamesApi.ts:116-119` 做一模一样的替换(同样三行换成同样四行加两行注释)。

- [ ] **Step 7: 屏上的话**

`src/kiosk/components/report/reviewPresentation.ts`:第 4 行 `import { interpolate } from '../../utils/interpolate';` 之后加一行

```ts
import type { RequestFailureKind } from '../../../utils/requestFailure';
```

文件末尾追加:

```ts
/**
 * 请求失败时屏上那半句「为什么」。**不印后端原文**:以前屏 20 写「未找到复盘。」,
 * 下面直接是 `Request failed 503: {"detail":"Remote server unavailable"}`,用户看不懂,
 * 也看不出是网络的事(2026-09-14 调研 N24)。
 *
 * 分不出原因(`other`)时返回空串,**不编一个原因**:「稍后再试」对一个永久的 409 是假话。
 */
export function failureReason(kind: RequestFailureKind, t: TFn): string {
  switch (kind) {
    case 'offline': return t('review:failure_offline', '连不上云端');
    case 'not_found': return t('review:failure_not_found', '已经不在了');
    case 'no_credits': return t('review:failure_no_credits', '积分不足');
    case 'bad_sgf': return t('review:failure_bad_sgf', '这份谱读不出来');
    default: return '';
  }
}

/** 「做什么没成 · 为什么」。原因分不出时只说前半句。 */
export function failureLine(prefix: string, kind: RequestFailureKind, t: TFn): string {
  const reason = failureReason(kind, t);
  return reason ? `${prefix} · ${reason}` : prefix;
}
```

- [ ] **Step 8: 跑测试与类型检查**

Run:

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-review/katrain/web/ui
npx vitest run src/utils/requestFailure.test.ts src/api/reportApi.test.ts src/api/userGamesApi.test.ts src/kiosk/components/report/reviewPresentation.test.ts
npx tsc -b
npx eslint src/utils/requestFailure.ts src/api/reportApi.ts src/api/userGamesApi.ts src/kiosk/components/report/reviewPresentation.ts
```

预期:四个文件全部 PASS;`tsc -b` 0 退出;eslint 无报错。

- [ ] **Step 9: 提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-review
git add katrain/web/ui/src/utils/requestFailure.ts katrain/web/ui/src/utils/requestFailure.test.ts \
  katrain/web/ui/src/api/reportApi.ts katrain/web/ui/src/api/reportApi.test.ts \
  katrain/web/ui/src/api/userGamesApi.ts katrain/web/ui/src/api/userGamesApi.test.ts \
  katrain/web/ui/src/kiosk/components/report/reviewPresentation.ts katrain/web/ui/src/kiosk/components/report/reviewPresentation.test.ts
git diff --cached --stat   # 必须看到 requestFailure.ts 与 requestFailure.test.ts 两个新文件
git commit -m "$(cat <<'EOF'
feat(kiosk-report): 请求失败先分类再说话 —— 连不上、找不到、积分不足不再是同一段原文

reportApi / userGamesApi 的 authFetch 抛的是 Error('Request failed 503: {…}'),
错误上没有状态码,调用方只能把原文上屏。现在挂上 status / body(message 不变,
galaxy 与既有单测照旧),新增共享纯函数 utils/requestFailure.ts 按数字 status 与
detail.code 分五类(402 insufficient_credits 是计费闸开闸后的防御,不改默认值);
cacheBackedReadFailureKind 给「云端失败退本机缓存」的读接口用,404 不当「没有」;
kiosk 复盘用 failureLine 说「做什么没成 · 为什么」,分不出原因时不编。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---
### Task 6: N24 · 两个复盘钩子暴露 `errorKind`

**Files:**
- Modify: `katrain/web/ui/src/features/report/useReportDetail.ts:1-11`, `:14-39`, `:91-94`, `:128-139`, `:156-159`, `:188`, `:221-231`
- Modify: `katrain/web/ui/src/features/report/useReportTasks.ts:1-42`, `:66-67`, 8 处 `setError(…)`, `:268-278`
- Test: `katrain/web/ui/src/features/report/useReportDetail.test.tsx`, `katrain/web/ui/src/features/report/useReportTasks.test.tsx`

**Interfaces:**
- Consumes:`requestFailureKind`、`RequestFailureKind`(Task 5,`src/utils/requestFailure.ts`)。
- Produces:
  - `UseReportDetailResult` 新增 `errorKind: RequestFailureKind | null`;非法 task id 时是 `'not_found'`。
  - `UseReportTasksResult` 新增 `errorKind: RequestFailureKind | null`;`clearError()` 同时清掉它。
  - `error: string | null` 语义、取值不变(galaxy 照旧读它)。

- [ ] **Step 1: 写失败测试**

`useReportDetail.test.tsx`:

1)在 `it('rejects a malformed task ID without making requests', …)` 的 `expect(result.current.error).toBe('Invalid report task ID');` 之后加一行:

```ts
    expect(result.current.errorKind).toBe('not_found');
```

2)在该条之后追加:

```ts
  // N24:盒上云端连不上时本机回 503。屏 20 要据此说「连不上」,不说「未找到」,也不印原文。
  it('读失败时 errorKind 给出是哪一类(503 ⇒ offline),error 原文照旧', async () => {
    const body = '{"detail":"Remote report service unavailable"}';
    mockReportGet.mockRejectedValueOnce(
      Object.assign(new Error(`Request failed 503: ${body}`), { status: 503, body }),
    );
    const { result } = renderHook(() => useReportDetail(null, '7', true));
    await settle();

    expect(result.current.game).toBeNull();
    expect(result.current.error).toBe(`Request failed 503: ${body}`);
    expect(result.current.errorKind).toBe('offline');
  });

  // 报告接口不退缓存,上游 404 原码透传 ⇒ 那是云端说「没有这份报告」。
  // 对局那一路(GET /user-games/{id})盒上云端失败会退本机缓存,缓存没有也 404 ⇒ 证明不了「没有」,降为 other。
  // 变异验证:把对局那一路也改用 requestFailureKind,第二段红。
  it('报告 404 ⇒ not_found;对局那一路 404 ⇒ other(可能只是本机缓存里没有)', async () => {
    const notFound = (detail: string) => Object.assign(
      new Error(`Request failed 404: {"detail":"${detail}"}`), { status: 404, body: `{"detail":"${detail}"}` },
    );
    mockReportGet.mockRejectedValueOnce(notFound('Report task not found'));
    const first = renderHook(() => useReportDetail(null, '7', true));
    await settle();
    expect(first.result.current.errorKind).toBe('not_found');
    first.unmount();

    mockUserGameGet.mockRejectedValueOnce(notFound('Game not found'));
    const second = renderHook(() => useReportDetail(null, '7', true));
    await settle();
    expect(second.result.current.game).toBeNull();
    expect(second.result.current.errorKind).toBe('other');
  });
```

`useReportTasks.test.tsx`,在 `it('clears a visible error without changing the current task snapshot', …)` 之后追加:

```ts
  // N24 / R5:计费闸开闸后,创建报告会被 402 insufficient_credits 拒收(今天闸关着)。
  it('创建被 402 insufficient_credits 拒收时 errorKind = no_credits;clearError 一起清', async () => {
    const { result } = renderHook(() => useReportTasks(null, true));
    await settle();
    const body = '{"detail":{"code":"insufficient_credits","need":125,"have":0}}';
    mockCreate.mockRejectedValueOnce(
      Object.assign(new Error(`Request failed 402: ${body}`), { status: 402, body }),
    );

    await act(async () => {
      await expect(result.current.createReport({ userGameId: 'game-2', totalMoves: 80 })).rejects.toThrow();
    });

    expect(result.current.error).toBe(`Request failed 402: ${body}`);
    expect(result.current.errorKind).toBe('no_credits');

    act(() => result.current.clearError());
    expect(result.current.error).toBeNull();
    expect(result.current.errorKind).toBeNull();
  });
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-review/katrain/web/ui && npx vitest run src/features/report/useReportDetail.test.tsx src/features/report/useReportTasks.test.tsx`

预期:四条新 / 改的用例 FAIL(`errorKind` 是 `undefined`),其余 PASS。

- [ ] **Step 3: 改 `useReportDetail.ts`**

1)第 11 行 `import { nextReportCursor, toMoveAnalysisMap } from './reportModel';` 之后加:

```ts
import { cacheBackedReadFailureKind, requestFailureKind, type RequestFailureKind } from '../../utils/requestFailure';
```

2)`UseReportDetailResult` 里 `error: string | null;` 之后加:

```ts
  /**
   * 这条错属于哪一类(`utils/requestFailure.ts`)。**屏上说什么由调用方按它定** ——
   * `error` 是原文,盒上断网时是 `Request failed 503: {"detail":…}`,不能直接上屏。
   */
  errorKind: RequestFailureKind | null;
```

3)第 37-39 行

```ts
function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Failed to load report';
}
```

换成

```ts
interface Failure {
  message: string;
  kind: RequestFailureKind;
}

/** 非法 task id 在屏上就是「没有这份报告」。 */
const INVALID_TASK_FAILURE: Failure = { message: INVALID_TASK_ID_ERROR, kind: 'not_found' };

function failureOf(error: unknown, classify: (error: unknown) => RequestFailureKind = requestFailureKind): Failure {
  return {
    message: error instanceof Error ? error.message : 'Failed to load report',
    kind: classify(error),
  };
}
```

4)第 92-94 行

```ts
  const [error, setError] = useState<string | null>(
    enabled && parsedTaskId === null ? INVALID_TASK_ID_ERROR : null,
  );
```

换成

```ts
  const [failure, setFailure] = useState<Failure | null>(
    enabled && parsedTaskId === null ? INVALID_TASK_FAILURE : null,
  );
```

5)`refresh` 里那段请求(第 128-160 行):
- 第 128 行 `const request = (async () => {` 之后、`try {` 之前加:

```ts
      // 对局那一路(GET /user-games/{id})盒上云端失败会退本机缓存,缓存没有也回 404 ——
      // 那条 404 证明不了「没有」,分类时要降级(见 `cacheBackedReadFailureKind`)。
      let gameReadFailed = false;
```

- 第 139 行 `if (gameResult.status === 'rejected') throw gameResult.reason;` 换成:

```ts
        if (gameResult.status === 'rejected') {
          gameReadFailed = true;
          throw gameResult.reason;
        }
```

- 第 156 行 `setError(null);` → `setFailure(null);`
- 第 159 行 `setError(errorMessage(refreshError));` 换成:

```ts
        setFailure(failureOf(refreshError, gameReadFailed ? cacheBackedReadFailureKind : requestFailureKind));
```

6)第 188 行 `setError(enabled && parsedTaskId === null ? INVALID_TASK_ID_ERROR : null);` → `setFailure(enabled && parsedTaskId === null ? INVALID_TASK_FAILURE : null);`

7)返回对象里 `error,` 换成:

```ts
    error: failure?.message ?? null,
    errorKind: failure?.kind ?? null,
```

- [ ] **Step 4: 改 `useReportTasks.ts`**

1)第 17 行 `} from './reportModel';` 之后加:

```ts
import { requestFailureKind, type RequestFailureKind } from '../../utils/requestFailure';
```

2)`UseReportTasksResult` 里 `error: string | null;` 之后加:

```ts
  /**
   * 这条错属于哪一类(`utils/requestFailure.ts`)。**屏上说什么由调用方按它定** ——
   * `error` 是原文(列表 / 创建 / 重试任一处失败),盒上断网时是 `Request failed 503: {…}`。
   */
  errorKind: RequestFailureKind | null;
```

3)第 40-42 行

```ts
function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
```

换成

```ts
interface Failure {
  message: string;
  kind: RequestFailureKind;
}

function failureOf(error: unknown, fallback: string): Failure {
  return { message: error instanceof Error ? error.message : fallback, kind: requestFailureKind(error) };
}
```

4)第 66-67 行

```ts
  const [error, setError] = useState<string | null>(null);
  const clearError = useCallback(() => setError(null), []);
```

换成

```ts
  const [failure, setFailure] = useState<Failure | null>(null);
  const clearError = useCallback(() => setFailure(null), []);
```

5)本文件其余 `setError`,逐处替换(改完 `rg -n "setError|errorMessage" src/features/report/useReportTasks.ts` 必须零命中):
- 五处 `setError(null);`(refresh 成功、挂载 effect、createReport 开头与成功、retryReport 开头)→ `setFailure(null);`
- refresh 的 catch:

```ts
        setError(errorMessage(
          refreshError,
          translationRef.current('report:load_tasks_failed', 'Failed to load report tasks'),
        ));
```

→

```ts
        setFailure(failureOf(
          refreshError,
          translationRef.current('report:load_tasks_failed', 'Failed to load report tasks'),
        ));
```

- createReport 的 catch:`setError(errorMessage(createError, translationRef.current('report:create_task_failed', 'Failed to create report task'),));` 同样把 `setError(errorMessage(` 换成 `setFailure(failureOf(`,参数不动。
- retryReport 的 catch:`setError(errorMessage(retryError, translationRef.current('report:retry_failed', 'Failed to retry report'),));` 同上。

6)返回对象里 `error,` 换成:

```ts
    error: failure?.message ?? null,
    errorKind: failure?.kind ?? null,
```

- [ ] **Step 5: 跑测试与类型检查**

Run:

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-review/katrain/web/ui
rg -n "setError|errorMessage" src/features/report/useReportTasks.ts src/features/report/useReportDetail.ts || echo "零命中"
npx vitest run src/features/report/useReportDetail.test.tsx src/features/report/useReportTasks.test.tsx \
  src/galaxy/pages/report/ReportsPage.test.tsx src/galaxy/pages/report/ReportDetailPage.test.tsx \
  src/kiosk/pages/ReportsPage.test.tsx src/kiosk/pages/ReportsPage.polling.test.tsx src/kiosk/pages/ReportDetailPage.test.tsx
npx tsc -b
```

预期:`rg` 输出「零命中」;七个文件全部 PASS(galaxy 两屏不读 `errorKind`,行为不变);`tsc -b` 0 退出。

- [ ] **Step 6: 提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-review
git add katrain/web/ui/src/features/report/useReportDetail.ts katrain/web/ui/src/features/report/useReportDetail.test.tsx \
  katrain/web/ui/src/features/report/useReportTasks.ts katrain/web/ui/src/features/report/useReportTasks.test.tsx
git commit -m "$(cat <<'EOF'
feat(report): 复盘两个钩子带出 errorKind —— 屏上说什么由调用方按类定

useReportDetail / useReportTasks 原来只给一句 error 原文。内部改存
{ message, kind },对外 error 不变(galaxy 照旧),新增 errorKind:
503 ⇒ offline、报告 404 / 非法 id ⇒ not_found、402 insufficient_credits ⇒ no_credits。
对局那一路(GET /user-games/{id})盒上云端失败会退本机缓存、缓存没有也 404,
那条 404 证明不了「没有」⇒ 降为 other。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---
### Task 7: N24 · 屏 20 报告详情:连不上 / 找不到分开说,不印原文

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/ReportDetailPage.tsx:12`, `:16`, `:72-74`, `:127`, `:288-295`, `:321-331`, `:447-449`
- Test: `katrain/web/ui/src/kiosk/pages/ReportDetailPage.test.tsx:143`, `:635-700`

**Interfaces:**
- Consumes:`useReportDetail(...).errorKind`(Task 6);`requestFailureKind`(Task 5);`failureLine` / `failureReason`(Task 5)。
- Produces:新增文案 key `review:detail_failed`(「这份报告没读出来」)、`review:refresh_failed`(「没刷新成功」)、`review:recompute_failed`(「重算没发出去」)。`report-detail-error` 容器多一个 `data-failure` 属性(值为分类)。

- [ ] **Step 1: 改测试**

1)第 143 行 `setCurrentMove, loading: false, error: null as string | null, refresh,` 换成:

```tsx
    setCurrentMove, loading: false, error: null as string | null, errorKind: null as string | null, refresh,
```

2)第 635-643 行 `it('重算失败时话说出来,盘和数据还在;重试加载能把那条错清掉', …)` 整条换成:

```tsx
  it('重算失败时话说出来(不印原文),盘和数据还在;重试加载能把那条错清掉', async () => {
    retry.mockRejectedValueOnce(Object.assign(new Error('Request failed 503: {"detail":"x"}'), { status: 503 }));
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: '重算' }));
    expect(await screen.findByText('重算没发出去 · 连不上云端')).toBeInTheDocument();
    expect(screen.queryByText(/Request failed/)).toBeNull();
    expect(screen.getByTestId('live-board')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '重试加载' }));
    await waitFor(() => expect(screen.queryByText('重算没发出去 · 连不上云端')).toBeNull());
  });
```

3)第 661-674 行两条 `it('整局读不到时报错并给重试', …)`、`it('一时的错不许把已经在屏上的东西清掉', …)` 整体换成:

```tsx
  it('整份报告没有了:说「未找到复盘。」,不印原文,给重试', () => {
    detail = {
      ...baseDetail(), game: null,
      error: 'Request failed 404: {"detail":"Report task not found"}', errorKind: 'not_found',
    };
    renderPage();
    expect(screen.getByText('未找到复盘。')).toBeInTheDocument();
    expect(screen.queryByText(/Request failed/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '重试加载' }));
    expect(refresh).toHaveBeenCalled();
  });

  /**
   * N24 回归钉子(2026-09-14 调研):盒上报告接口全走云端,断网就是 503。
   * 以前这里写「未找到复盘。」,下面再印 `Request failed 503: {…}` —— 把「连不上」说成「找不到」。
   */
  it('连不上云端时说「这份报告没读出来 · 连不上云端」,不说「未找到」', () => {
    detail = {
      ...baseDetail(), game: null,
      error: 'Request failed 503: {"detail":"Remote report service unavailable"}', errorKind: 'offline',
    };
    renderPage();
    const block = screen.getByTestId('report-detail-error');
    expect(within(block).getByText('这份报告没读出来')).toBeInTheDocument();
    expect(within(block).getByText('连不上云端')).toBeInTheDocument();
    expect(screen.queryByText('未找到复盘。')).toBeNull();
    expect(screen.queryByText(/Request failed/)).toBeNull();
  });

  it('一时的错不许把已经在屏上的东西清掉,也不印原文', () => {
    detail = { ...baseDetail(), error: 'Request failed 503: {"detail":"x"}', errorKind: 'offline' };
    renderPage();
    expect(screen.getByTestId('live-board')).toBeVisible();
    expect(screen.getByText('没刷新成功 · 连不上云端')).toBeInTheDocument();
    expect(screen.queryByText(/Request failed/)).toBeNull();
  });
```

4)`it('换一份报告时,上一份的变化、试下和错都不许跟过来', …)` 里(行号是改动前的;2)3)做完后会后移,按原文定位):第 689 行 `expect(await screen.findByText(/旧任务重试失败/)).toBeVisible();` → `expect(await screen.findByText('重算没发出去')).toBeVisible();`;第 699 行 `expect(screen.queryByText(/旧任务重试失败/)).toBeNull();` → `expect(screen.queryByText('重算没发出去')).toBeNull();`(第 677 行的 `new Error('旧任务重试失败')` 不动:它没有 status,落 `other`,屏上只说前半句)。

- [ ] **Step 2: 跑测试,确认失败**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-review/katrain/web/ui && npx vitest run src/kiosk/pages/ReportDetailPage.test.tsx`

预期 FAIL:上面改 / 加的五条(屏上还是原文、还是「未找到复盘。」);其余 PASS。

- [ ] **Step 3: 改 `ReportDetailPage.tsx`**

1)第 12 行 `import { sgfToMoves } from '../../utils/sgfSerializer';` 之后加:

```tsx
import { requestFailureKind } from '../../utils/requestFailure';
```

第 16 行换成:

```tsx
import { failureLine, failureReason, outcomeLine, rowTitle, yourColor } from '../components/report/reviewPresentation';
```

2)删掉第 72-74 行的 `function messageFrom(error: unknown): string { … }`(连同它后面那个空行)。

3)第 127 行换成:

```tsx
    task, game, moves, analysisByMove, currentMove, setCurrentMove, loading, error, errorKind, refresh,
```

4)`handleRetryReport` 的 catch(第 288-292 行):

```tsx
    } catch (failure) {
      if (identityRef.current === requestIdentity) {
        setRetryFailure({ identity: requestIdentity, message: messageFrom(failure) });
      }
```

换成

```tsx
    } catch (failure) {
      if (identityRef.current === requestIdentity) {
        // 不印原文:盒上断网时 failure.message 是 `Request failed 503: {…}`。
        setRetryFailure({
          identity: requestIdentity,
          message: failureLine(t('review:recompute_failed', '重算没发出去'), requestFailureKind(failure), t),
        });
      }
```

同一个 `useCallback` 的依赖(第 295 行)换成:

```tsx
  }, [isAuthenticated, refresh, reportIdentity, t, taskId, token]);
```

5)第 321-331 行的 `if (!game) { … }` 整块换成:

```tsx
  if (!game) {
    // 「连不上」和「没有这份报告」是两件事。以前一律写「未找到复盘。」,再把后端原文印在下面 ——
    // 盒上报告接口全走云端,断网时就是 503,屏上却说「未找到」(2026-09-14 调研 N24)。
    // `not_found` 只来自报告接口(云端 404 原码透传)或非法 id;对局那一路的 404 钩子里已降为 other。
    const kind = error ? (errorKind ?? 'other') : 'not_found';
    const reason = kind === 'not_found' ? '' : failureReason(kind, t);
    return shell(
      <div className="empty" data-testid="report-detail-error" data-failure={kind}>
        <h4>{kind === 'not_found' ? t('report:not_found', '未找到复盘。') : t('review:detail_failed', '这份报告没读出来')}</h4>
        {reason && <p>{reason}</p>}
        <button type="button" className="kiosk-btn kiosk-btn--pill pill" onClick={() => void handleRefresh()}>
          {t('report:retry_load', '重试加载')}
        </button>
      </div>,
    );
  }
```

6)第 449 行 `{retryError || error}` 换成:

```tsx
            {retryError ?? failureLine(t('review:refresh_failed', '没刷新成功'), errorKind ?? 'other', t)}
```

- [ ] **Step 4: 跑测试与类型检查**

Run:

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-review/katrain/web/ui
npx vitest run src/kiosk/pages/ReportDetailPage.test.tsx
npx tsc -b
npx eslint src/kiosk/pages/ReportDetailPage.tsx
```

预期:全部 PASS;`tsc -b` 0 退出;eslint 无报错。

- [ ] **Step 5: 提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-review
git add katrain/web/ui/src/kiosk/pages/ReportDetailPage.tsx katrain/web/ui/src/kiosk/pages/ReportDetailPage.test.tsx
git commit -m "$(cat <<'EOF'
fix(kiosk): 屏 20 断网时说「未找到复盘。」还印一段 Request failed 503 原文

盒上报告接口全走云端,云端不可达就是 503。整份读不到时按 errorKind 分开说:
找不到 ⇒「未找到复盘。」;其余 ⇒「这份报告没读出来」+ 原因。刷新失败、重算失败
的告警行同样改成「做什么没成 · 为什么」,不再把后端原文贴上屏。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---
### Task 8: N24 / R5 · 屏 19 复盘列表:所有出错处不印原文

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/ReportsPage.tsx`(行号按 `6f7dc629` 标注;Task 3 / Task 4 之后会偏移一两行,**按下面引用的原文定位**):`:16`、`:21-23`、`:75`、`:120`、`:144-147`、`:157`、`:171`、`:220`、`:249`、`:347`、`:366`、`:389`、`:533-536`、`:606-608`
- Test: `katrain/web/ui/src/kiosk/pages/ReportsPage.test.tsx`(`:185` 之后新增一条、`:243`、`:452`、`:606`、`:627` 之后新增一条、`:650`,并在 `:662` 之前新增一个 describe)

**Interfaces:**
- Consumes:`useReportTasks(...).errorKind`(Task 6);`requestFailureKind` / `cacheBackedReadFailureKind` / `RequestFailureKind`、`failureLine` / `failureReason`(Task 5)。
- Produces:新增文案 key `review:tasks_failed`(「报告任务出错了」)。复用已有 key:`report:preview_failed`、`review:moves_failed`、`report:import_failed`、`report:library_import_failed`、`report:delete_failed`、`review:list_failed`(默认串与 cn PO 一致,不改)。

- [ ] **Step 1: 改 / 加测试**

1)第 243-249 行 `it('列表读不到时报错,重试能反复点', …)` 整条换成:

```tsx
  // 注意:盒上列表断网时 `user_games_list` 退本机缓存(200 + authority=local_cache),走不到这里;
  // 这条钉的是「分得出原因就说原因、不印原文」这根接线,不是盒上断网的真实路径。
  it('列表读不到时报错(分得出原因说原因,不印原文),重试能反复点', async () => {
    mocks.list.mockRejectedValueOnce(
      Object.assign(new Error('Request failed 503: {"detail":"Remote server unavailable"}'), { status: 503 }),
    );
    renderPage();
    expect(await screen.findByText('对局列表读不到')).toBeInTheDocument();
    expect(screen.getByText('连不上云端')).toBeInTheDocument();
    expect(screen.queryByText(/Request failed/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    await waitFor(() => expect(rows()).toHaveLength(2));
  });
```

2)第 452-458 行 `it('报告读不出来时那句话就是错误本身,不是一条假曲线', …)` 整条换成:

```tsx
  it('报告读不出来时那句话说的是这件事(不印原文),不是一条假曲线', async () => {
    mocks.hookResult = { ...mocks.hookResult, reportStatesByGame: { a: { completedNormal: task() } } };
    mocks.getMoves.mockRejectedValue(
      Object.assign(new Error('Request failed 404: {"detail":"Report task not found"}'), { status: 404 }),
    );
    renderPage();
    expect(await screen.findByText('报告读不出来 · 已经不在了')).toBeInTheDocument();
    expect(screen.getByTestId('review-winrate-plot')).toHaveAttribute('data-state', 'empty');
  });
```

2b)在 `describe('屏 19 · 列表与选中', …)` 里、`it('点另一行换选中,左栏跟着换那一局', …)` 之后追加:

```tsx
  /**
   * N24 反例(2026-09-15 计划审查):盒上 GET /user-games/{id} 云端失败会退本机缓存,缓存没有也回 404。
   * 列表从云端读到、随后断网、点一局本机没缓存过的 ⇒ 预览 404。这条 404 证明不了「云端没有」,
   * 不许说「已经不在了」,也不印原文。变异验证:预览那处改用 requestFailureKind,这条红。
   */
  it('预览 404 只说「棋谱预览加载失败」,不说「已经不在了」、不印原文', async () => {
    mocks.get.mockRejectedValue(
      Object.assign(new Error('Request failed 404: {"detail":"Game not found"}'), { status: 404 }),
    );
    renderPage();
    expect(await screen.findByText('棋谱预览加载失败')).toBeInTheDocument();
    expect(screen.queryByText(/已经不在了/)).toBeNull();
    expect(screen.queryByText(/Request failed/)).toBeNull();
  });
```

3)`it('导入失败时错留在对话框里,输入不丢', …)` 里 `expect(await screen.findByText('SGF 不合法')).toBeInTheDocument();` 换成:

```tsx
    // 没有 status 的错落 other ⇒ 只说「做什么没成」,不把 error.message 贴进对话框。
    expect(await screen.findByText('导入 SGF 失败')).toBeInTheDocument();
    expect(screen.queryByText('SGF 不合法')).toBeNull();
```

3b)在 `it('从棋谱库导入走的是同一条路 —— 把那一局复制进你自己的对局表', …)` 之后追加。桩用的是**今天 `KifuAPI` 真实抛出的形状**(`src/api/kifuApi.ts:8-12`,普通 `Error`、不带 `status`),不替生产代码加它没有的字段:

```tsx
  // 棋谱库在云端;今天 KifuAPI 抛的错不带 status ⇒ 分不出原因,只说前半句,不印原文。
  // kifu 赛道 T6 把它改抛 ApiError(status) 之后,这里自动能说「连不上云端」(分类器只认数字 status)。
  it('从棋谱库导入失败:只说「从棋谱库导入失败」,不印原文,也不往下建对局', async () => {
    mocks.getAlbum.mockRejectedValueOnce(new Error('Request failed 503: {"detail":"Remote server unavailable"}'));
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /导入棋谱复盘/ }));
    fireEvent.click(await screen.findByRole('menuitem', { name: '从棋谱库导入' }));
    fireEvent.click(await screen.findByText('库赛事'));
    fireEvent.click(screen.getByRole('button', { name: '仅导入' }));
    expect(await screen.findByText('从棋谱库导入失败')).toBeInTheDocument();
    expect(screen.queryByText(/Request failed/)).toBeNull();
    expect(mocks.create).not.toHaveBeenCalled();
  });
```

4)`it('删除失败时说出来,并且留在原地', …)` 里 `expect(await screen.findByText('删不掉')).toBeInTheDocument();` 换成:

```tsx
    expect(await screen.findByText('删除对局失败')).toBeInTheDocument();
    expect(screen.queryByText('删不掉')).toBeNull();
```

5)在 `describe('屏 19 · 不碰实体盘', …)` 之前新增:

```tsx
describe('屏 19 · 报告任务出错怎么说', () => {
  // R5 防御半:计费闸开闸后,创建报告会被 402 insufficient_credits 拒收(今天闸关着)。
  it('被 402 积分不足拒收:告警行说「积分不足」,不把 JSON 原文贴上屏', async () => {
    mocks.hookResult = {
      ...mocks.hookResult,
      error: 'Request failed 402: {"detail":{"code":"insufficient_credits","need":125,"have":0}}',
      errorKind: 'no_credits',
    };
    renderPage();
    await waitFor(() => expect(rows()).toHaveLength(2));
    expect(document.querySelector('.rverr')).toHaveTextContent('积分不足');
    expect(screen.queryByText(/Request failed/)).toBeNull();
  });

  it('分不出原因时说一句笼统的,也不印原文', async () => {
    mocks.hookResult = { ...mocks.hookResult, error: 'Request failed 409: report already exists', errorKind: 'other' };
    renderPage();
    await waitFor(() => expect(rows()).toHaveLength(2));
    expect(document.querySelector('.rverr')).toHaveTextContent('报告任务出错了');
    expect(screen.queryByText(/Request failed/)).toBeNull();
  });
});
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-review/katrain/web/ui && npx vitest run src/kiosk/pages/ReportsPage.test.tsx`

预期 FAIL:上面改 / 加的八条(屏上仍是原文);其余 PASS。

- [ ] **Step 3: 改 `ReportsPage.tsx`**

1)`import { replayBaipuSteps, type BoardState } from '../../utils/baipuReplay';` 之后加:

```tsx
import { cacheBackedReadFailureKind, requestFailureKind, type RequestFailureKind } from '../../utils/requestFailure';
```

`reviewPresentation` 那条 import 换成:

```tsx
import {
  failureLine, failureReason, outcomeLine, rowDisc, rowState, rowTitle, yourColor, type RowState,
} from '../components/report/reviewPresentation';
```

2)删掉这一行:

```tsx
const messageOf = (error: unknown, fallback: string) => (error instanceof Error ? error.message : fallback);
```

3)

```tsx
  const [gamesError, setGamesError] = useState<string | null>(null);
```

换成

```tsx
  /** 列表读不到的**原因类别**。存类别不存原文:原文在盒上断网时是 `Request failed 503: {…}`。 */
  const [gamesFailure, setGamesFailure] = useState<RequestFailureKind | null>(null);
```

4)

```tsx
    reportStatesByGame, error: tasksError, clearError: clearTasksError,
```

换成

```tsx
    reportStatesByGame, error: tasksError, errorKind: tasksErrorKind, clearError: clearTasksError,
```

5)`loadGames` 里 `setGamesError(null);` → `setGamesFailure(null);`;catch 里

```tsx
      setGamesError(messageOf(error, translationRef.current('report:load_games_failed', '加载对局列表失败')));
```

换成

```tsx
      setGamesFailure(requestFailureKind(error));
```

6)五处 `messageOf(error, <前半句>)` 换成 `failureLine(<前半句>, <分类>, translationRef.current)`,前半句原样保留。**预览那一处分类用 `cacheBackedReadFailureKind`**(它读的是 `UserGamesAPI.get`,盒上云端失败退本机缓存、缓存没有也 404),其余四处用 `requestFailureKind`:

```tsx
        // 预览读的是 GET /user-games/{id}:盒上云端失败会退本机缓存,缓存没有也回 404 ⇒ 404 不能说成「已经不在了」。
        setDetailError(failureLine(translationRef.current('report:preview_failed', '棋谱预览加载失败'), cacheBackedReadFailureKind(error), translationRef.current));
```

```tsx
        setMovesError(failureLine(translationRef.current('review:moves_failed', '报告读不出来'), requestFailureKind(error), translationRef.current));
```

```tsx
      setLocalImportError(failureLine(translationRef.current('report:import_failed', '导入 SGF 失败'), requestFailureKind(error), translationRef.current));
```

```tsx
      // 这个 catch 前面还有 `KifuAPI.getAlbum`:今天它抛的错不带 status ⇒ 那一步失败落 other、只说前半句。
      // kifu 赛道 T6 改抛 ApiError(status) 后自动分得出;本赛道不改 kifuApi.ts(归 kifu 赛道,改了必冲突)。
      setLibraryImportError(failureLine(translationRef.current('report:library_import_failed', '从棋谱库导入失败'), requestFailureKind(error), translationRef.current));
```

```tsx
      setActionError(failureLine(translationRef.current('report:delete_failed', '删除对局失败'), requestFailureKind(error), translationRef.current));
```

7)列表错误块:

```tsx
              {gamesError ? (
                <div className="empty">
                  <h4>{t('review:list_failed', '对局列表读不到')}</h4>
                  <p>{gamesError}</p>
```

换成

```tsx
              {gamesFailure ? (
                <div className="empty">
                  <h4>{t('review:list_failed', '对局列表读不到')}</h4>
                  {failureReason(gamesFailure, t) && <p>{failureReason(gamesFailure, t)}</p>}
```

8)「生成报告」区告警行:

```tsx
                <p className="rverr" role="status">
                  {actionError || tasksError}
```

换成

```tsx
                <p className="rverr" role="status">
                  {/* 报告任务那条错可能来自列表、创建或重试,前半句说不准是哪件 ⇒ 只说原因,
                      分不出原因时才用一句笼统的。不印原文(盒上断网时是 Request failed 503: {…})。 */}
                  {actionError || failureReason(tasksErrorKind ?? 'other', t) || t('review:tasks_failed', '报告任务出错了')}
```

- [ ] **Step 4: 跑测试、类型检查、lint**

Run:

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-review/katrain/web/ui
rg -n "messageOf|gamesError" src/kiosk/pages/ReportsPage.tsx || echo "零命中"
npx vitest run src/kiosk/pages/ReportsPage.test.tsx src/kiosk/pages/ReportsPage.polling.test.tsx
npx tsc -b
npx eslint src/kiosk/pages/ReportsPage.tsx
```

预期:`rg` 输出「零命中」;两个文件全部 PASS;`tsc -b` 0 退出;eslint 无报错。

- [ ] **Step 5: 提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-review
git add katrain/web/ui/src/kiosk/pages/ReportsPage.tsx katrain/web/ui/src/kiosk/pages/ReportsPage.test.tsx
git commit -m "$(cat <<'EOF'
fix(kiosk): 屏 19 七处出错把后端原文直接上屏 —— 改说「做什么没成 · 为什么」

列表、预览、逐手、删除、两种导入、报告任务告警行,原来都是 error.message 原样上屏,
盒上断网时就是 Request failed 503: {"detail":…}。现在按请求失败类别说原因,
分不出时只说前半句;报告任务那条 402 insufficient_credits 说「积分不足」
(计费闸今天关着,这是防御,不改默认值)。预览读的对局接口在盒上会退本机缓存,
它的 404 不说「已经不在了」;棋谱库那一步的 KifuAPI 错今天不带 status,只说前半句。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---
### Task 9: 收尾 · 基线 diff、两套构建、PO 闸、一次真运行时预览

**Files:**
- Create(临时,不提交,用完删除):`katrain/web/ui/tests/zz-review-failure-preview.spec.ts`
- 不改仓内其它文件。

**Interfaces:**
- Consumes:Task 1 的 `$BASE/before-failed.txt` 与 `$BASE/failed-names.cjs`;`tests/helpers/fourup.ts` 的 `freezeClock` / `stubBackendStatics` / `KIOSK_VIEWPORT`。

- [ ] **Step 1: 全量 vitest,按名字集合比基线**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-review/katrain/web/ui
BASE="$(git -C /Users/fan/Repositories/katrain-kiosk-go-review rev-parse --absolute-git-dir)/review-baseline"
npx vitest run --reporter=json --outputFile="$BASE/after.json" > "$BASE/after.log" 2>&1; echo "vitest_exit=$?"
node "$BASE/failed-names.cjs" "$BASE/after.json" > "$BASE/after-failed.txt"
echo "== 新增失败(必须为空) =="; comm -13 "$BASE/before-failed.txt" "$BASE/after-failed.txt"
echo "== 修好的 =="; comm -23 "$BASE/before-failed.txt" "$BASE/after-failed.txt"
```

预期:「新增失败」一节为空。若不为空,先按名字判断是不是本轮改动造成的(**不许按文件名「看着无关」放过**),修到为空再往下走。

- [ ] **Step 2: 类型检查、lint、两套构建**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-review/katrain/web/ui
npx tsc -b; echo "tsc_exit=$?"
npx eslint src/utils/requestFailure.ts src/api/reportApi.ts src/api/userGamesApi.ts \
  src/features/report/reportStats.ts src/features/report/useReportDetail.ts src/features/report/useReportTasks.ts \
  src/kiosk/components/report/reviewPresentation.ts src/kiosk/components/report/ReviewWinratePlot.tsx \
  src/kiosk/pages/ReportsPage.tsx src/kiosk/pages/ReportDetailPage.tsx src/kiosk/pages/ResearchPage.tsx; echo "eslint_exit=$?"
npm run build; echo "build_exit=$?"
npm run build:kiosk-2d; echo "build_kiosk_exit=$?"
```

预期:四个 exit 都是 0。`build:kiosk-2d` 的输出里 `verify:kiosk-2d` 通过(没有 three / `@react-three` 命中)。

- [ ] **Step 3: PO 闸(本轮新增了 kiosk 文案)**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-review/katrain/web/ui
npx playwright test --config=playwright.visual.config.ts tests/kiosk-shell-contract.spec.ts
```

预期:全部 PASS。尤其是「t(key, 默认值) 的占位符必须和 cn PO 里那条一致」和「t(key, 中文默认值) 的默认值不许和 PO 里那条说的是两回事」两条。这个配置会起 vite dev(:5173,`reuseExistingServer`)。

- [ ] **Step 4: 一次真运行时预览(屏 20 连不上云端)**

写临时 spec `tests/zz-review-failure-preview.spec.ts`:

```ts
import { expect, test } from '@playwright/test';

import { freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });

// 临时预览,不提交:看 N24 的话在 1024×600、460 宽的右栏壳里放不放得下、有没有原文。
test('预览:屏 20 报告接口回 503', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'preview');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: '访客', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/v1/geometry/status', (route) => route.fulfill({
    json: {
      phase: 'disabled', session_calibrated: false, last_error: null,
      capabilities: { camera_ready: false, led_ready: false, geometry_ready: false, recognition_ready: false },
    },
  }));
  await page.route('**/api/v1/reports/41', (route) => route.fulfill({
    status: 503, json: { detail: 'Remote report service unavailable' },
  }));

  await page.goto('/kiosk/report/41');
  const block = page.getByTestId('report-detail-error');
  await expect(block).toContainText('这份报告没读出来');
  await expect(block).toContainText('连不上云端');
  await expect(page.getByText(/Request failed/)).toHaveCount(0);
  await page.screenshot({ path: process.env.PREVIEW_OUT! });
});
```

运行并看图:

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-review/katrain/web/ui
BASE="$(git -C /Users/fan/Repositories/katrain-kiosk-go-review rev-parse --absolute-git-dir)/review-baseline"
PREVIEW_OUT="$BASE/preview-20-offline.png" npx playwright test --config=playwright.visual.config.ts tests/zz-review-failure-preview.spec.ts
rm tests/zz-review-failure-preview.spec.ts
git -C /Users/fan/Repositories/katrain-kiosk-go-review status --short
```

预期:spec PASS。用 Read 打开 `$BASE/preview-20-offline.png` 人眼确认三点:① 页控条「← 复盘」在;② 中间是「这份报告没读出来 / 连不上云端 / 重试加载」;③ 屏上没有英文原文、没有溢出。`git status --short` 无输出(临时 spec 已删,截图在 git 目录里不被跟踪)。

若这一步因工具链(非产品)问题跑不起来:按用户 CLAUDE.md 第 5 条修一次;还不行就改用 `npm run dev` 手动打开 `http://127.0.0.1:5173/kiosk/report/41`(没有后端时 `/api/v1/reports/41` 会被 vite 代理打成 5xx),看同一屏,在交付说明里写明用的是哪种方式。

- [ ] **Step 5: 交付说明(写在给主会话 / Fan 的回复里,不写文件)**

列出:
1. 本轮 7 个提交的 `git log --oneline` 摘要;
2. 基线 diff 结果(新增失败为空;修好了哪些,若有);
3. 两套构建与 PO 闸结果;
4. 预览截图路径与人眼结论;
5. **建议上板项**(不作为合并前置,Fan 定时机;按「先 home-ubuntu 测试环境再生产」):严格 SSO 构建(token=null)上 ① 屏 20「去研究」盘上有子、副标题是「我的对局:…」,点「← 复盘」回到同一份报告;② 断开云端时屏 20 说「这份报告没读出来 · 连不上云端」,屏 19「生成报告」区说「连不上云端」;③ 顺带看屏 19 首帧有没有闪「还没有下过的棋」;
6. 待 Fan 拍板的 R6 阅读位置,见 PRD §4;以及本轮新增、未进 PO 的 key 清单(供合并后统一补 11 种语言)。

本任务不提交。

---

## Self-Review

**1. Spec 覆盖(对照 `prd.md` §3):**

| PRD 条目 | 验收点 | 任务 |
|---|---|---|
| S1 | 验收 1-4(token=null 取谱 / 未登录不发 / 失败副标题 / 返回回到这份报告) | Task 2 Step 1-4 |
| S1 | 验收 5(上板) | Task 9 Step 5 建议上板项 ① |
| N7 | 初值改 `isAuthenticated`、既有单测绿、不加单测 | Task 3 |
| R1 | 验收 1(七档计数 + 黑白合计 = 屏 20) | Task 4 Step 1(4) |
| R1 | 验收 2(`winrateSeries` 带 `bad`) | Task 4 Step 1(5) |
| R1 | 验收 3(屏 19 页面级:0 手、无红段) | Task 4 Step 2 |
| R1 | 验收 4(旧常量零命中) | Task 4 Step 7 |
| R1 | 验收 5(四图 fixture 走退回路径、输出不变 ⇒ 不重跑 fourup) | Global Constraints「视觉关卡本轮核过不触发」;推导见 PRD R1 验收 5 |
| N24 | 验收 1(分类器) | Task 5 Step 1 / 5 |
| N24 | 验收 2(API 错误带 status / body) | Task 5 Step 2 / 6 |
| N24 | 验收 3(钩子 errorKind) | Task 6 |
| N24 | 验收 4(屏 20) | Task 7 |
| N24 | 验收 5(屏 19) | Task 8 |
| N24 | 验收 6(真运行时预览) | Task 9 Step 4 |
| N24 | 验收 7(PO 闸) | Task 9 Step 3 |
| R5 防御半 | 402 → `no_credits` → 「积分不足」 | Task 5 Step 1(分类器)、Task 6 Step 1(钩子)、Task 8 Step 1(5)(屏 19) |
| R1 补(2026-09-15 计划审查) | grade 有值而 delta_score 为 null 时两格照数、与屏 20 / 红段一致 | Task 4 Step 1(4)、Step 4 |
| N24 补(2026-09-15 计划审查) | 盒上 `GET /user-games/{id}` 退本机缓存 ⇒ 它的 404 不说「已经不在了」(钩子对局那一路、屏 19 预览) | Task 5 `cacheBackedReadFailureKind`、Task 6 Step 1 / 3(5)、Task 8 Step 1(2b) / 3(6) |
| N24 补(2026-09-15 计划审查) | 棋谱库导入:`KifuAPI` 今天不带 status ⇒ 只说前半句、不印原文;不改 `kifuApi.ts`(归 kifu 赛道 T6) | Task 8 Step 1(3b) / 3(6) |
| PRD §7 | 基线 diff、tsc -b、两套构建、eslint | Task 1、Task 9 Step 1-2 |

待拍板的 R6 与已定不补的 I18N-PO 按 PRD §4 不进任务;§5 各项不进任务。

**2. 占位扫描:** 每一步的代码都是完整的。Task 8 Step 3(6) 的五行 `failureLine(...)` 逐行写全;Task 5 Step 6 的 userGamesApi 替换写明「同样三行换成同样四行」,替换前后的原文与 reportApi 那处逐字相同(已核 `userGamesApi.ts:116-119` 与 `reportApi.ts:88-91` 同形)。

**3. 类型与命名一致性:**
- `RequestFailureKind` 五个值 `'offline' | 'not_found' | 'no_credits' | 'bad_sgf' | 'other'`:Task 5 定义,Task 6 / 7 / 8 与各测试只用这五个。
- `requestFailureKind(error: unknown)`(Task 5)→ Task 6 `failureOf` 默认分类、Task 7 重算 catch、Task 8 列表与四处 `failureLine`。
- `cacheBackedReadFailureKind(error: unknown)`(Task 5)→ Task 6 `useReportDetail` 对局那一路、Task 8 预览那一处。
- `failureReason(kind, t)` / `failureLine(prefix, kind, t)`(Task 5)→ Task 7、8 调用参数顺序一致。
- 钩子字段名 `errorKind`(Task 6)→ Task 7 解构 `errorKind`、Task 8 解构为 `errorKind: tasksErrorKind`;测试桩字段名同为 `errorKind`。
- `WinratePoint.bad`(Task 4)→ `ReviewWinratePlot.worstDropIndex` 读 `p.bad`;`deltaScore` 字段删除,Task 4 Step 7 用 `rg` 与 `tsc -b` 确认没有残留读者。
- 夹具 `FIGHTING`(Task 4 Step 1(4),文件级)被 `summarizeReportMoves` 与 `winrateSeries` 两组测试共用。
