# 围棋 kiosk · 跨平台对弈（本轮）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让盒上（token 恒为 null）的星阵人机这条路从对弈首页到存谱真的走得通、屏上每句话都成立，并把 OGS 挑战与实体盘恢复框里两处「说不出口 / 走不出去」补上。

**Architecture:** 三块互不依赖的前端小修（token 判别位、首页状态请求、挑战文案）先行；然后撤掉星阵局两颗注定被拒的键；再做一个后端小切片——AI 回停一手 / 认输时本地局以 `Void` 结束、`/api/move` 回 200，星阵局在认输 / AI 终局 / 实体盘 AI 终局三处经 `_record_ai_game` 落账到 `user_games`；最后前端把 `Void` 说成人话，并给实体盘等待态加出口、编排器终局时释放恢复暂停。数据契约只新增一个既有字段的取值（`end_result` / `user_games.result` = `"Void"`），不加字段。

**Tech Stack:** React 19 + TypeScript + Vite + vitest（`katrain/web/ui`）；FastAPI + pytest（`asyncio_mode = auto`）；Playwright（`playwright.visual.config.ts`，vite dev :5173）。

**Spec:** `superpowers/tracks/kiosk-go-cross-platform/prd.md`

## Global Constraints

> **开工前先读 `prd.md` §6.0**：五条赛道的共享文件归属与合并顺序（尤其 `server.py` 终局落账只留一条入口）。与本 plan 冲突时以 §6.0 为准。

- 在 worktree `/Users/fan/Repositories/katrain-kiosk-go-cross-platform`（分支 `feature/kiosk-go-cross-platform`）里开发；**不 push、不合并 develop**，合并由 Fan 决定；**不在别的 worktree 里 checkout**。所有命令用绝对路径或先 `cd` 到本 worktree。
- 本 worktree 起步时**没有** `.venv` 与 `node_modules`：先 `uv sync`，再 `cd katrain/web/ui && npm ci`（Task 0 做）。
- 改了共享领地（`src/components`、`hooks`、`api`、`features`、`context`、`utils` 等）或共享消费链上的 kiosk 页面，必须 `npm run build` 与 `npm run build:kiosk-2d` **都绿**；`verify:kiosk-2d`（kiosk 边界）不许破。
- 类型检查用 `npx tsc -b`（`npx tsc --noEmit` 检查 0 个文件，无效）；`*.test.tsx` 不在 tsc 范围内——mock 漏字段不会有类型错，只会运行时变 `undefined`。
- 盒上 `token` 恒为 `null`：任何「发不发请求 / 渲不渲染」的判别位用 `isAuthenticated`，不用 `token`；`token` 只当凭据原样往下传（`api.ts` 的 `platform*` 已接受 `null`）。
- 新文案一律 `t('ns:key', '中文默认')`；**不往 PO 里加 key**（补不补 PO 待 Fan 裁定）。
- Python 用 `uv run black -l 120 <文件>`；前端单测 `cd katrain/web/ui && npx vitest run <文件>`；后端 `uv run pytest <文件>`（pytest 配置在 `pyproject.toml`，`asyncio_mode = "auto"`，async 测试不必加 marker）。
- 测试判据是**基线 diff**：动手前（Task 0）跑一遍记录**失败用例名集合**，改完比名字集合（`comm`），**不比条数**。
- Playwright e2e（`playwright.config.ts`，:8002）打的是**构建产物**：改源码后先 `npm run build` 再跑。本计划用到的 `tests/kiosk-screen-05-game.spec.ts` 与四图走 `playwright.visual.config.ts`（vite dev :5173，自动起服务），打的是源码。⚠️ 该配置是 `reuseExistingServer: true`：另外四条赛道各有 worktree、也会起 :5173，**端口上已有别人的 dev server 时 Playwright 会静默复用它、量的是别人的树**。每次跑之前 `lsof -nP -iTCP:5173 -sTCP:LISTEN`：为空才跑；不为空就用 `lsof -p <PID> | grep cwd` 确认是本 worktree 的 `katrain/web/ui`，不是就等它结束（不许杀别人的进程）。
- 视觉 / 布局改动走 CLAUDE.md 的四图对比（`npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-XX-*.fourup.spec.ts`，jsdom 不作布局证据）；每屏**跑两次**取自己的抖动底（屏 10 是 canvas 盘，抖动约 4500 像素），只提交内容真变了的屏、四张图一起提交；**视觉通过需 Fan 确认**。本计划判定不触发承重实测（理由见 prd §7）。
- 共享文件与其它四条赛道重叠（prd §6）：只改计划里点名的行段，不顺手重排 / 重命名周边代码。
- 提交信息以 `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>` 结尾。

## File Structure

| 文件 | 责任 | Task |
|---|---|---|
| `katrain/web/ui/src/kiosk/pages/GamePage.tsx` | 道具两处判别位（X7）；终局卡 `Void` 说明行（X9-b） | 1, 7 |
| `katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx` | auth mock 可变 + 盒端用例；停一手用例改写；Void 说明行用例 | 1, 4, 7 |
| `katrain/web/ui/src/kiosk/pages/PlayPage.tsx`（+ `.test.tsx`） | 状态请求判别位（X8）；野狐卡徽标（X1） | 2 |
| `katrain/web/ui/src/kiosk/pages/PlatformLobbyPage.tsx`（+ `.test.tsx`） | 挑战 toast / 确认框说实话（X4-a） | 3 |
| `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx`（+ `.test.tsx`） | engineMode 只留认输 + `.ghint`（X9-a） | 4 |
| `katrain/web/ui/tests/kiosk-screen-05-game.spec.ts`、`tests/kiosk-screen-10-platform-game.fourup.spec.ts` | 屏 10 动作区断言与取图等待条件 | 4 |
| `katrain/web/interface.py` | 新命令 `end_without_result` | 5 |
| `katrain/web/platforms/gateway.py`（+ `tests/platforms/test_engine_gateway.py`、`tests/platforms/test_engine_integration.py`） | AI 终局分支结束本地局 | 5 |
| `katrain/web/server.py` | `/api/move` game_ended→200（5）；`_record_ai_game` 的 `data_overrides`、`_record_platform_engine_game`、`_session_owner`、resign / move / 视觉三处落账（6） | 5, 6 |
| `tests/platforms/test_engine_game_ledger.py`（新建，已确认 `git ls-files` 无同名） | move / resign 端点与落账 helper | 5, 6 |
| `tests/test_vision_move_poller.py` | 视觉路径以会话主人落账 | 6 |
| `katrain/web/ui/src/kiosk/components/report/reviewPresentation.ts`（+ `.test.ts`） | `Void` 念成人话 | 7 |
| `katrain/web/ui/src/kiosk/components/physical/EngineMoveErrorDialog.tsx`、`src/kiosk/__tests__/EngineMoveErrorDialog.test.tsx` | 等待态加「认输」（M2） | 8 |
| `katrain/web/core/physical_play_orchestrator.py`、`tests/test_physical_play_orchestrator.py` | 终局释放恢复暂停并熄灯（M4） | 8 |
| `superpowers/tracks/kiosk-go-shell-align/visual/01-play/`、`visual/10-platform-game/` | 四图重取 | 9 |

---

### Task 0: 环境与基线

**Files:** 无代码改动。

- [ ] **Step 1: 确认起点**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git rev-parse --abbrev-ref HEAD && git log --oneline -1 && git status --short
```
Expected: `feature/kiosk-go-cross-platform`；HEAD 是 `6f7dc629` 或其后只含 `superpowers/tracks/kiosk-go-cross-platform/` 文档的提交；工作树无源码改动。

- [ ] **Step 2: 装依赖**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv sync
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npm ci
```
Expected: 两条都成功退出。

- [ ] **Step 3: 前端基线（失败用例名集合）**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run --reporter=verbose > "${TMPDIR:-/tmp}/kgcp-vitest-before.log" 2>&1; grep -E '^\s+×' "${TMPDIR:-/tmp}/kgcp-vitest-before.log" | sed -E 's/ [0-9]+ms$//' | sort -u > "${TMPDIR:-/tmp}/kgcp-vitest-before.txt"; wc -l "${TMPDIR:-/tmp}/kgcp-vitest-before.txt"
```
Expected: 生成名字集合文件（行数记下即可，后面只比名字）。

- [ ] **Step 4: 后端基线（失败用例名集合）**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && CI=true uv run pytest tests -q -rfE > "${TMPDIR:-/tmp}/kgcp-pytest-before.log" 2>&1; grep -E '^(FAILED|ERROR) ' "${TMPDIR:-/tmp}/kgcp-pytest-before.log" | sed -E 's/ - .*$//' | sort -u > "${TMPDIR:-/tmp}/kgcp-pytest-before.txt"; tail -3 "${TMPDIR:-/tmp}/kgcp-pytest-before.log"
```
Expected: 末行是 pytest 汇总；名字集合文件已生成（其中应含 `tests/platforms/test_engine_move_guards.py` 的 20 条既有失败，Task 5/6 会用到）。跑完 `git status --short`：若 `katrain/config.json` 被测试改写成 `M`，`git checkout -- katrain/config.json` 还原。本 Task 不提交。

---

### Task 1: X7 —— 对局屏付费道具的两道 token 闸换 `isAuthenticated`

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx:142`（解构）、`:334-341`（`refreshItemCounts`）、`:501`（`handleEngineAnalysis` 早退）
- Test: `katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx:68-71`（auth mock）、`:187-190`（beforeEach）、`:340` 之后（新用例）

**Interfaces:**
- Consumes: `useAuth(): { token: string | null; isAuthenticated: boolean; user; … }`（`src/context/AuthContext.tsx`）；`API.platformEngineItems(platform: string, token: string | null | undefined)`、`API.platformEngineAnalysis(platform, sessionId, kind, token: string | null | undefined)`（`src/api.ts`，a979132a 已放宽）。
- Produces: 无新接口。

- [ ] **Step 1: 把 auth mock 改成可变，写两条盒端用例（先红）**

`GamePageEngine.test.tsx` 把

```tsx
// Mock auth
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'mock-token', isAuthenticated: true, user: { id: 1, username: 'test' }, login: vi.fn(), logout: vi.fn() }),
}));
```

替换为

```tsx
// Mock auth —— token 与 isAuthenticated 是**两个量**:严格盒端 token 恒 null 而人是登录的,
// 所以夹具必须能分别置位,不能让一个推另一个(a979132a 的 LobbyPage 夹具同一条)。
const authMock = vi.hoisted(() => ({ token: 'mock-token' as string | null, isAuthenticated: true }));
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    token: authMock.token, isAuthenticated: authMock.isAuthenticated,
    user: { id: 1, username: 'test' }, login: vi.fn(), logout: vi.fn(),
  }),
}));
```

`describe('GamePage engine mode')` 的 `beforeEach` 开头 `vi.clearAllMocks();` 之后加两行：

```tsx
    authMock.token = 'mock-token';
    authMock.isAuthenticated = true;
```

在 `describe('星阵隧道分析 (领地/支招/变化图)')` 里、`it('clicking 支招 calls API.platformEngineAnalysis(golaxy, sessionId, options, token)')` 之后插入：

```tsx
    // X7:盒上 token 恒为 null 而人是登录的。闸判 token 时这两条一个请求都不发 ——
    // 角标永远「—」、按下去没反应、实体盘支招白灯也不亮(白灯是后端在分析端点里点的)。
    // 变异记录:把 GamePage 里两处 `!isAuthenticated` 改回 `!token` → 这两条各红一次。
    it('盒端(token=null 但已登录):挂载时照样拉余次,凭据位传 null', async () => {
      authMock.token = null;
      renderPage(true);
      await waitFor(() => expect(API.platformEngineItems).toHaveBeenCalledWith('golaxy', null));
    });

    it('盒端(token=null 但已登录):按支招照样发分析请求', async () => {
      authMock.token = null;
      (API.platformEngineAnalysis as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: false, reason: 'insufficient', kind: 'options',
      });
      renderPage(true);

      fireEvent.click(screen.getByText('支招'));

      await waitFor(() => {
        expect(API.platformEngineAnalysis).toHaveBeenCalledWith('golaxy', 'test-session', 'options', null);
      });
    });
```

- [ ] **Step 2: 跑，确认两条新用例红、其余不变**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/__tests__/GamePageEngine.test.tsx`
Expected: 恰好 2 条 FAIL（「盒端(token=null 但已登录)…」两条，`platformEngineItems` / `platformEngineAnalysis` 未被调用），其余 PASS。

- [ ] **Step 3: 改 `GamePage.tsx`**

`:142`

```tsx
  const { token, user } = useAuth();
```

替换为

```tsx
  // token 只当**凭据**用（严格盒端恒为 null，身份在 HttpOnly sb_go_token cookie 里）；
  // 「发不发请求」一律判 isAuthenticated —— a979132a 同一判据，这一页当时漏了（X7）。
  const { token, user, isAuthenticated } = useAuth();
```

`refreshItemCounts`（`:334-341`）

```tsx
  const refreshItemCounts = useCallback(async () => {
    if (!engineMode || !token) return;
    try {
      setEngineItemCounts(await API.platformEngineItems(platform, token));
    } catch (e) {
      console.error(e);
    }
  }, [engineMode, token]);
```

替换为

```tsx
  const refreshItemCounts = useCallback(async () => {
    if (!engineMode || !isAuthenticated) return;
    try {
      setEngineItemCounts(await API.platformEngineItems(platform, token));
    } catch (e) {
      console.error(e);
    }
  }, [engineMode, isAuthenticated, token]);
```

`handleEngineAnalysis` 里（`:501`）

```tsx
    if (!sessionId || !token) return;
```

替换为

```tsx
    if (!sessionId || !isAuthenticated) return;
```

- [ ] **Step 4: 跑测试与类型检查**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/__tests__/GamePageEngine.test.tsx src/kiosk/pages/GamePage.test.tsx && npx tsc -b
```
Expected: 全 PASS；`tsc -b` 无输出退出 0。

- [ ] **Step 5: 变异验证（不提交）**

把 Step 3 的两处 `!isAuthenticated` 临时改回 `!token`，重跑 `npx vitest run src/kiosk/__tests__/GamePageEngine.test.tsx`，Expected：两条盒端用例红；`git diff` 确认后还原，再跑一次全绿。

- [ ] **Step 6: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx && git commit -m "$(cat <<'EOF'
fix(kiosk): 星阵对局屏剩下的两道 token 闸 —— 盒上三颗付费道具按了没反应

a979132a 漏了 GamePage:refreshItemCounts 与 handleEngineAnalysis 仍判 !token,
盒上 token 恒 null ⇒ 角标恒「—」、领地/支招/变化图不发请求、实体盘支招白灯不亮。
判别位换 isAuthenticated,token 只作凭据原样传。新增 2 条盒端用例,变异(改回 !token)各红一次。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: X8 + X1 —— 对弈首页在盒上拉平台状态；野狐卡与屏 07 同一个词

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/PlayPage.tsx:43`（解构）、`:46-60`（状态 effect）、`:138-148`（野狐卡）
- Test: `katrain/web/ui/src/kiosk/pages/PlayPage.test.tsx:70-76`（`expectAllDisconnected`）、`:265-280`（登出用例夹具）、文件末 `});` 之前（新用例）

**Interfaces:**
- Consumes: `API.platformStatus(token: string | null | undefined): Promise<PlatformStatusResponse>`；`mergePlatformStatus` / `defaultPlatforms`（`kiosk/constants/platforms.ts`，不改）；key `platform:no_play_yet`（屏 07 `PlatformConnectPage.tsx:263` 已在用）。
- Produces: 无新接口。

- [ ] **Step 1: 写测试（先红）**

`PlayPage.test.tsx` 的 `expectAllDisconnected` 把

```tsx
  expect(fox).toHaveTextContent('接口还没通');
  expect(fox).toBeDisabled();
};
```

替换为

```tsx
  expect(fox).toHaveTextContent('接口还没通');
  // X1:屏 07 那一行写的是「暂不能对弈」,并判过「即将上线」是预测不是状态(没人给过日期)。
  // 同一个事实两屏同一个词。
  expect(fox).toHaveTextContent('暂不能对弈');
  expect(fox).not.toHaveTextContent('即将上线');
  expect(fox).toBeDisabled();
};
```

用例 `'keeps disconnected defaults after logout when an older request resolves'` 里把

```tsx
    let auth = { user: { username: '友' }, isAuthenticated: true, token: 'A' as string | null };
    const requestA = deferred<{ platforms: PlatformInfo[] }>();
    useAuthMock.mockImplementation(() => auth);
    platformStatusMock.mockReturnValue(requestA.promise);
    const view = renderPage();

    auth = { ...auth, token: null };
```

替换为

```tsx
    let auth: { user: { username: string } | null; isAuthenticated: boolean; token: string | null } =
      { user: { username: '友' }, isAuthenticated: true, token: 'A' };
    const requestA = deferred<{ platforms: PlatformInfo[] }>();
    useAuthMock.mockImplementation(() => auth);
    platformStatusMock.mockReturnValue(requestA.promise);
    const view = renderPage();

    // 登出的真形状:AuthContext.logout 把 user 置 null ⇒ isAuthenticated 为假,token 也清掉。
    // 只把 token 置 null 在盒上**不是**登出(盒上 token 本来就恒为 null)。
    auth = { user: null, isAuthenticated: false, token: null };
```

在文件末尾 `describe('PlayPage')` 的最后一个 `it` 之后、收尾 `});` 之前插入：

```tsx
  // X8:盒上 token 恒为 null 而人是登录的。判 token 时这一屏永远停在全未连接的默认名单 ——
  // 已连上星阵的人看到「点击登录 · 手机号 + 验证码」,点卡先绕到屏 07。
  // 变异记录:把 PlayPage 的 `if (isAuthenticated)` 改回 `if (token)` → 这条红。
  it('盒端(token=null 但已登录):照样拉平台状态,已连接的星阵卡直达人机开局', async () => {
    useAuthMock.mockReturnValue({ user: { username: '友' }, isAuthenticated: true, token: null });
    platformStatusMock.mockResolvedValue({ platforms: [platformRecord('golaxy', true)] });

    renderPage();

    const golaxy = await screen.findByRole('button', { name: /^星阵围棋，已连接/ });
    expect(platformStatusMock).toHaveBeenCalledWith(null);
    fireEvent.click(golaxy);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/engine/golaxy');
  });
```

- [ ] **Step 2: 跑，确认红**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/pages/PlayPage.test.tsx`
Expected: 新用例 FAIL（找不到「星阵围棋，已连接」）；调用了 `expectAllDisconnected` 的用例 FAIL（没有「暂不能对弈」）。

- [ ] **Step 3: 改 `PlayPage.tsx`**

`:43`

```tsx
  const { user, token } = useAuth();
```

替换为

```tsx
  // token 只当**凭据**用（严格盒端恒为 null）；「发不发这次请求」判 isAuthenticated。
  // 判 token 时盒上每个已登录用户都停在全未连接的默认名单上（X8，a979132a 同一判据，这一页当时漏了）。
  const { user, token, isAuthenticated } = useAuth();
```

状态 effect（`:46-60`）

```tsx
  useEffect(() => {
    let current = true;
    setPlatforms(defaultPlatforms());

    if (token) {
      API.platformStatus(token).then((d) => {
        if (current) setPlatforms(mergePlatformStatus(d.platforms));
      }).catch(() => {
        if (current) setPlatforms(defaultPlatforms());
      });
    }

    return () => { current = false; };
  }, [token]);
```

替换为

```tsx
  useEffect(() => {
    let current = true;
    setPlatforms(defaultPlatforms());

    if (isAuthenticated) {
      API.platformStatus(token).then((d) => {
        if (current) setPlatforms(mergePlatformStatus(d.platforms));
      }).catch(() => {
        if (current) setPlatforms(defaultPlatforms());
      });
    }

    return () => { current = false; };
  }, [isAuthenticated, token]);
```

野狐卡（`:138-148`）

```tsx
            // 「即将上线」不是「锁定」:锁定意味着东西在、满足条件就给。接口没通的平台
            // 不许摆成锁着的样子 —— `comingSoon` 是 PLATFORM_META 里就有的真标记,不是这里现编的。
            if (meta.comingSoon) {
              return (
                <KioskCard
                  key={p.platform}
                  title={t(meta.label, meta.labelCn)}
                  sub={t('Not wired up yet', '接口还没通')}
                  icon={PLATFORM_ICON[p.platform] ?? 'globe-hemisphere-west'}
                  soon={t('Coming soon', '即将上线')}
                />
```

替换为

```tsx
            // 接口没通的平台不许摆成锁着的样子(锁定意味着东西在、满足条件就给)——
            // `comingSoon` 是 PLATFORM_META 里就有的真标记,不是这里现编的。
            // 徽标也不写「即将上线」:没人给过日期,那是预测不是状态。屏 07 同一行写的是
            // 「暂不能对弈」(`PlatformConnectPage.tsx` 头注释),同一个事实两屏共用同一个 key(X1)。
            if (meta.comingSoon) {
              return (
                <KioskCard
                  key={p.platform}
                  title={t(meta.label, meta.labelCn)}
                  sub={t('Not wired up yet', '接口还没通')}
                  icon={PLATFORM_ICON[p.platform] ?? 'globe-hemisphere-west'}
                  soon={t('platform:no_play_yet', '暂不能对弈')}
                />
```

- [ ] **Step 4: 跑测试与类型检查**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/pages/PlayPage.test.tsx && npx tsc -b
```
Expected: 全 PASS；`tsc -b` 退出 0。

- [ ] **Step 5: 变异验证（不提交）**

把 `if (isAuthenticated)` 临时改回 `if (token)`，重跑 `PlayPage.test.tsx`，Expected：「盒端(token=null 但已登录)…」红；还原后全绿。

- [ ] **Step 6: Commit**（屏 01 四图在 Task 9 统一重取）

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add katrain/web/ui/src/kiosk/pages/PlayPage.tsx katrain/web/ui/src/kiosk/pages/PlayPage.test.tsx && git commit -m "$(cat <<'EOF'
fix(kiosk): 对弈首页在盒上拉不到平台状态 —— 已连上的星阵也写「点击登录」

PlayPage 只在 token 为真时请求 /platforms/status,盒上 token 恒 null ⇒ 三张平台卡永远是
全未连接默认名单。判别位换 isAuthenticated。登出用例的夹具改成真形状(isAuthenticated=false),
只清 token 在盒上不是登出。

顺手统一野狐卡徽标:屏 07 早判过「即将上线」是预测不是状态,屏 01 改用同一个 key「暂不能对弈」。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: X4-a —— 屏 08 挑战那两句说实话

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/PlatformLobbyPage.tsx:109`（toast）、`:295`（确认框尾句）
- Test: `katrain/web/ui/src/kiosk/pages/PlatformLobbyPage.test.tsx:95-108`（用例「挑战先确认一次…」）

**Interfaces:**
- Consumes: `interpolate(template: string, vars: Record<string, string>)`（`kiosk/utils/interpolate`，本文件已 import）；`meta`（本组件内 `PLATFORM_META[platform]`）。
- Produces: 无。

- [ ] **Step 1: 写测试（先红）**

`PlatformLobbyPage.test.tsx` 用例 `'挑战先确认一次,发出去的条件和屏上那行读数同源'` 整条替换为：

```tsx
  it('挑战先确认一次,发出去的条件和屏上那行读数同源', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('platform-user')).toHaveLength(3));
    await userEvent.click(within(rowOf('stone_walker')).getByRole('button', { name: '挑战' }));

    const dlg = await screen.findByTestId('platform-challenge-confirm');
    expect(within(dlg).getByText('向 stone_walker 发起挑战？')).toBeInTheDocument();
    // X4-a:对方接受后盒子既不建局也不跳转(OGS `active_game` 事件没人接)。
    // 发之前就要说清 —— 同屏自动匹配那句早就这么说了。
    expect(dlg).toHaveTextContent('不会回到这台盒子');
    expect(platformSendChallenge, '还没确认就发出去了').not.toHaveBeenCalled();

    await userEvent.click(within(dlg).getByRole('button', { name: '发出挑战' }));
    await waitFor(() => expect(platformSendChallenge).toHaveBeenCalledWith(
      'ogs', { user_id: '1', board_size: 19, rules: 'chinese', ranked: true }, 'tok',
    ));
    // 发出之后那句 toast 也不许再暗示「接下来会在这边下」。
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('不会回到这台盒子'));
  });
```

- [ ] **Step 2: 跑，确认红**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/pages/PlatformLobbyPage.test.tsx`
Expected: 该用例 FAIL 于 `expect(dlg).toHaveTextContent('不会回到这台盒子')`；其余 PASS。

- [ ] **Step 3: 改 `PlatformLobbyPage.tsx`**

`:109`

```tsx
      setToast({ text: t('platform:challenge_sent', '挑战已发出 —— 接下来在对面那边'), bad: false });
```

替换为

```tsx
      // X4-a:对方接受之后这台盒子不会建局、不会跳转(适配器的 `active_game` 事件没人接,
      // 见文件头「那条诚实债」)。这句原来写「接下来在对面那边」,读起来像是会回来。
      setToast({
        text: interpolate(
          t('platform:challenge_sent', '挑战已发出。对方接受后要去 {name} 上下，不会回到这台盒子。'),
          { name: t(meta.label, meta.labelCn) },
        ),
        bad: false,
      });
```

`:295`

```tsx
              <b>{t('platform:challenge_ask_tail', '发出去就在对方那边了。')}</b>
```

替换为

```tsx
              <b>
                {interpolate(
                  t('platform:challenge_ask_tail', '发出去撤不回来；对方接受后要去 {name} 上下，不会回到这台盒子。'),
                  { name: t(meta.label, meta.labelCn) },
                )}
              </b>
```

- [ ] **Step 4: 跑测试与类型检查**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/pages/PlatformLobbyPage.test.tsx && npx tsc -b
```
Expected: 全 PASS；`tsc -b` 退出 0。

- [ ] **Step 5: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add katrain/web/ui/src/kiosk/pages/PlatformLobbyPage.tsx katrain/web/ui/src/kiosk/pages/PlatformLobbyPage.test.tsx && git commit -m "$(cat <<'EOF'
fix(kiosk): 屏 08 挑战文案不再暗示对局会回到盒子

OGS 对方接受挑战后盒子不建局也不跳转(active_game 没人接,X4 主体待拍板)。
确认框与发出后的 toast 都说清「要去 OGS 上下,不会回到这台盒子」,与同屏自动匹配那句同口径。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: X9-a —— 星阵人机局撤掉「停一手」「数子」

**Files:**
- Modify: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx:309-322`（`actions` 的 engineMode 分支）、`:413-428`（`.ghint` 注释与三元）
- Test: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.test.tsx`（悔棋 `test.each` 之后新增一条）
- Test: `katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx:210-222`（改写「停一手/认输 stay enabled」用例）
- Test: `katrain/web/ui/tests/kiosk-screen-05-game.spec.ts:400-403`（屏 10 动作区标签）
- Modify: `katrain/web/ui/tests/kiosk-screen-10-platform-game.fourup.spec.ts`（等待条件、两处说明文字）

**Interfaces:**
- Consumes: `KioskAction`（`kiosk/shell/KioskActions.tsx`）；本组件内 `isGameOver` / `canCount` / `countMin` / `hardwareFault` / `analysisRequiresLogin`。
- Produces: 无。

- [ ] **Step 1: 写测试（先红）**

`GameControlPanel.test.tsx`：在悔棋那条 `test.each([...])('悔棋:%s → %s', …)` 结束之后插入：

```tsx
  // ── 星阵人机:停一手 / 数子撤掉(X9,2026-09-14)──────────────────────────────
  // 两颗在星阵局里**开局就定死按了必被拒**:星阵 PASS 编码没抓到,后端对引擎局恒 409
  // `pass_not_supported`;数子走联机握手,对面是 `-1`,永远 pending。判据同悔棋:
  // 永久不可用 → 撤掉,原因写在开关排右端那一格。
  // 历史给 120 手:证明撤掉不是「还没到 100 手」,右端那句也不是数子手数提示。
  // 变异记录:engineMode 那一支把 pass/count 加回去 → 前两句红;删掉 ghint 的 engineMode 分支 → 最后一句红。
  test('星阵人机:动作区只剩认输,右端写明为什么', () => {
    const history = Array.from({ length: 120 }, (_, i) => ({ node_id: i, score: 0, winrate: 0.5 }));
    const { container } = panel({ game_type: 'free', history } as Partial<GameState>, { engineMode: true });
    expect(screen.queryByText('停一手')).toBeNull();
    expect(screen.queryByText('数子')).toBeNull();
    expect(screen.getByText('认输')).toBeInTheDocument();
    expect(container.querySelector('.gtoggles .ghint')).toHaveTextContent('暂不支持停一手、数子');
  });
```

`GamePageEngine.test.tsx` 把整条

```tsx
  it('停一手/认输 stay enabled in engineMode (galaxy-reference: no blunt engineMode disable)', async () => {
```

（到它的收尾 `});`，`:210-222`）替换为：

```tsx
  // X9(2026-09-14):上一版这里钉的是「engineMode 下停一手照样可按(galaxy 参考)」——
  // 那是 07-08 那次 merge 的写法,把 07-02 `3677f3d1` 的禁用改了回去。galaxy 那边没有星阵人机局,
  // 拿它当判据是量错了对象:星阵局里这两颗按下去一个 409、一个永远 pending。
  it('星阵人机没有停一手和数子;认输照旧走确认框', async () => {
    mockGameState.count_min_moves = 1;   // 手数够了也不该出现数子 —— 撤掉不是「还没到手数」
    renderPage(true);

    expect(screen.queryByText('停一手')).toBeNull();
    expect(screen.queryByText('数子')).toBeNull();
    fireEvent.click(screen.getByText('认输'));
    expect(screen.getByText('确认认输？')).toBeInTheDocument();
    expect(mockHandleAction).not.toHaveBeenCalledWith('pass');
  });
```

- [ ] **Step 2: 跑，确认红**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/components/game/GameControlPanel.test.tsx src/kiosk/__tests__/GamePageEngine.test.tsx`
Expected: 两条新用例 FAIL（找到了「停一手」）；其余 PASS。

- [ ] **Step 3: 改 `GameControlPanel.tsx` 的动作数组**

`:309-322`

```tsx
  const actions = engineMode
    ? [
      // 悔棋不在这里 —— 跨平台对弈**整局都没有**这颗键(见上面 `undoAllowed`)。
      // 稿子 `:1851` 画的是 `<button disabled>悔棋</button>`,理由「灰在这儿比点了被拒好」;
      // 那条理由只对「等一会儿就回来」成立,而这儿是永久没有。**实现反过来纠正稿子。**
      { key: 'pass', icon: 'hand-pointing' as const, label: t('game:pass', '停一手'), onClick: () => onAction('pass'), disabled: isGameOver },
      {
        key: 'count', icon: 'squares-four' as const, label: t('Score', '数子'),
        onClick: () => onAction('count'), disabled: !canCount,
        reason: t('game:count_min', '数子要下满 {n} 手').replace('{n}', String(countMin)),
      },
      { key: 'resign', icon: 'flag' as const, label: t('Resign', '认输'), onClick: () => onAction('resign'), danger: true, disabled: isGameOver },
    ]
    : [...analysisActions, ...playActions];
```

替换为

```tsx
  const actions = engineMode
    ? [
      // 悔棋不在这里 —— 跨平台对弈**整局都没有**这颗键(见上面 `undoAllowed`)。
      // 稿子 `:1851` 画的是 `<button disabled>悔棋</button>`,理由「灰在这儿比点了被拒好」;
      // 那条理由只对「等一会儿就回来」成立,而这儿是永久没有。**实现反过来纠正稿子。**
      //
      // 停一手 / 数子按同一条判据撤掉(X9,2026-09-14)。星阵的 PASS 编码从没抓到,后端
      // `gateway.pass_move` 对引擎局恒拒(409 `pass_not_supported`);数子走联机局握手,对面是 `-1`,
      // 永远 pending。两颗都是**开局就定死的按了必被拒** ⇒ 撤掉,原因写在开关排右端 `.ghint`。
      // (07-02 `3677f3d1` 灰掉过,07-08 merge 按 galaxy 参考改回可按 —— galaxy 没有星阵人机局,
      //  那条参考量错了对象。)终局时认输照旧灰着:这一排的终局版式不在这次改动里。
      { key: 'resign', icon: 'flag' as const, label: t('Resign', '认输'), onClick: () => onAction('resign'), danger: true, disabled: isGameOver },
    ]
    : [...analysisActions, ...playActions];
```

- [ ] **Step 4: 改 `.ghint`**

`:413-428`（从注释 `{/* 三句话抢同一格` 到 `</i>`）替换为：

```tsx
        {/* 几句话抢同一格,优先级是**按「这句话还会不会自己消失」排的**:
              ① `hardwareFault` —— 故障,最急,而且要用红。
              ② 星阵人机 —— 停一手 / 数子**整局都没有**(X9),这一句是它们不在的唯一解释;
                 这种局里没有分析键也没有数子手数,③④ 两句本来就不适用。
              ③ 游客 —— 三个键**不登录就永远不会亮**;这一句在触屏上是它们唯一的解释
                 (`reason` 落在 `title`/`aria-description` 上,手指够不着)。
              ④ 数子 —— 只关一个键,而且**下满手数它自己就好了**。
            ⚠️ 代价说清楚:游客在前 100 手看不到「数子要下满 N 手」那句。可以接受 ——
            数子键到时候自己会亮,而三个分析键不会。反过来排的话,游客整局都不知道
            那三个键为什么是灰的。 */}
        <i className="ghint" data-fault={hardwareFault ? 'true' : undefined}>
          {hardwareFault
            ?? (engineMode
              ? (isGameOver ? '' : t('game:golaxy_no_pass_count', '暂不支持停一手、数子'))
              : analysisRequiresLogin
                ? t('play:analysis_requires_login_hint', '领地 / 支招 / 图表 登录后可用')
                : !isGameOver && !canCount
                  ? t('game:count_min', '数子要下满 {n} 手').replace('{n}', String(countMin))
                  : '')}
        </i>
```

- [ ] **Step 5: 跑单测与类型检查**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/components/game/GameControlPanel.test.tsx src/kiosk/__tests__/GamePageEngine.test.tsx src/kiosk/__tests__/GamePageLedBadge.test.tsx src/kiosk/pages/GamePage.test.tsx && npx tsc -b
```
Expected: 全 PASS（`GamePageLedBadge` 守的是非星阵局的「数子要下满 100 手」与故障优先，不受影响）；`tsc -b` 退出 0。

- [ ] **Step 6: 改真浏览器断言与四图等待条件**

`tests/kiosk-screen-05-game.spec.ts:400-403`

```ts
  // 悔棋不在里面 —— **跨平台对弈整局都没有这颗键**(Fan 2026-08-25 亲裁)。
  // 上一版是四个键,第四个是「悔棋」,只在星阵算招期间撤掉 ⇒ 一局几十次四↔三来回翻,
  // 而这一排是 `grid-auto-columns: 1fr`,翻一次「认输」就在用户手指底下挪一格。
  expect(g.actionLabels, '星阵局的动作区不是三个键').toEqual(['停一手', '数子', '认输']);
```

替换为

```ts
  // 悔棋不在里面 —— **跨平台对弈整局都没有这颗键**(Fan 2026-08-25 亲裁)。
  // 停一手 / 数子也不在(X9,2026-09-14):星阵局里一个恒 409、一个永远 pending,开局就定死按了必被拒。
  // 三颗都是**整局不在**,不是来回翻 ⇒「认输」不会在用户手指底下挪格。
  expect(g.actionLabels, '星阵局的动作区只剩认输').toEqual(['认输']);
```

`tests/kiosk-screen-10-platform-game.fourup.spec.ts`：

(a) 把

```ts
  /**
   * 动作区就是三颗 —— **这一屏现在从第一帧起就是三颗**,不再有「四颗变三颗」那个过程。
   *
   * ⚠️ 所以这一句现在只是「这一排渲染出来了、且不多不少三颗」的守卫,
   * **它不再证明任何时序**;别把它读成「等到了某个状态」。
   * ⚠️ 也别退回去等 `button:disabled`:数子本来就是灰的(第 18 手 < `count_min_moves` 100),
   * 那个选择器立刻命中、测试通过而**什么都没证明** —— 量错了对象。
   */
  await page.waitForFunction(() =>
    document.querySelectorAll('[data-testid="game-actions"] button').length === 3);
```

替换为

```ts
  /**
   * 动作区只有一颗「认输」—— 从第一帧起就是一颗(X9,2026-09-14 撤掉停一手 / 数子)。
   *
   * ⚠️ 这一句只是「这一排渲染出来了、且不多不少一颗」的守卫,**不证明任何时序**。
   */
  await page.waitForFunction(() =>
    document.querySelectorAll('[data-testid="game-actions"] button').length === 1);
```

(b) 把说明注释里

```ts
 *  · **数子:稿子画成可按,实现是灰的 —— 这次是稿子错。** `canCount = !isGameOver && moves >= countMin`,
 *    这一帧第 18 手而 `count_min_moves` 是 100 ⇒ 灰,且开关排右端已经写出「数子要下满 100 手」。
 *    稿子在第 18 手把数子画成能按,和它自己写的中国规则局对不上。归「稿子画错」那一类。
```

替换为

```ts
 *  · **停一手 / 数子:稿子画成可按,实现整局不画(X9,2026-09-14)。** 星阵 PASS 编码没抓到,
 *    后端对引擎局恒 409;数子走联机握手,对面是 `-1`,永远 pending ⇒ 开局就定死按了必被拒,
 *    判据同悔棋(永久不可用 → 撤掉),开关排右端写「暂不支持停一手、数子」。
```

(c) 把 `implementationCaption` 里这一段

```ts
      + '**数子稿子画错**:第 18 手 < count_min_moves 100 ⇒ 该灰，右端也已写出原因 · '
```

替换为

```ts
      + '**停一手 / 数子整局不画**(X9):星阵 PASS 恒 409、数子握手对面是 -1 永远 pending，'
      + '判据同悔棋，右端写「暂不支持停一手、数子」 · '
```

- [ ] **Step 7: 真浏览器跑屏 10 用例**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-05-game.spec.ts
```
Expected: 全 PASS；控制台 `[10-platform-game]` 那行 `actionLabels` 为 `["认输"]`，`actionsBottom === railBottom`，`railOverflow <= 0`。（四图在 Task 9 统一取。）

- [ ] **Step 8: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx katrain/web/ui/src/kiosk/components/game/GameControlPanel.test.tsx katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx katrain/web/ui/tests/kiosk-screen-05-game.spec.ts katrain/web/ui/tests/kiosk-screen-10-platform-game.fourup.spec.ts && git commit -m "$(cat <<'EOF'
fix(kiosk): 星阵人机局撤掉停一手和数子 —— 一个按了弹 409 红条,一个按了永远没反应

星阵 PASS 编码没抓到,gateway 对引擎局恒拒;数子对 player_w_id=-1 的会话走联机握手,永远 pending。
两颗开局就定死按了必被拒,按本组件自己的判据(永久不可用 → 撤掉)撤掉,开关排右端写
「暂不支持停一手、数子」。07-02 3677f3d1 禁用过,07-08 merge 按 galaxy 参考改回可按 ——
galaxy 没有星阵人机局,那条参考量错了对象;钉住它的用例一并改写。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: X9-b 后端 —— AI 停手 / 认输时本地局以 `Void` 结束，`/api/move` 回 200

**Files:**
- Modify: `katrain/web/interface.py:1464-1469`（`_do_resign` / `_do_timeout` 之后新增 `_do_end_without_result`）
- Modify: `katrain/web/platforms/gateway.py:205-223`（`_play_engine_move` 的 `GolaxyEngineTerminal` 分支）
- Modify: `katrain/web/server.py:983-984`（`/api/move` 平台分支的 `except PlatformMoveRejectedError`）
- Test: `tests/platforms/test_engine_gateway.py:194-210`（`test_engine_terminal_ends_game` 补断言）
- Test: `tests/platforms/test_engine_integration.py`（文件末追加一条真栈用例）
- Create: `tests/platforms/test_engine_game_ledger.py`（move 端点两条）

**Interfaces:**
- Consumes: `GolaxyAdapter._genmove_committing` 对非落点坐标 emit `game_ended` 后抛 `GolaxyEngineTerminal`（`golaxy/adapter.py:787-792`，不改）；`PlatformManager._setup_callbacks` / `_on_game_ended`（`manager.py:293-354`，不改）；`PlatformMoveRejectedError(message, reason)`（`gateway.py:22-32`）。
- Produces:
  - `WebKaTrain` 命令 `"end_without_result"`：`session.katrain("end_without_result")` 把当前节点 `end_state` 置为 `"Void"`，随后照常 `update_state()`（广播 `game_update`、`session.game_ended = True`）。
  - `POST /api/move` 契约：gateway 抛 `reason == "game_ended"` 时回 **200** `{"session_id", "state"}`（`state.end_result == "Void"`）；其它 reason 照旧 409 `{"detail": str(e)}`。Task 6 在这个分支里加落账调用。
  - `tests/platforms/test_engine_game_ledger.py` 里的夹具 `HUMAN`、`_engine_session(end_result=None, human_color="B")`、`_gateway(is_engine=True)`、`_app(session, gateway)`、`_client(app)`，Task 6 复用。

- [ ] **Step 1: 写测试（先红）**

`tests/platforms/test_engine_gateway.py` 的 `test_engine_terminal_ends_game` 末尾（`assert "game_ended" in reasons` 之后）追加：

```python
        # X9: the LOCAL game ends too, without a result — an AI pass and an AI resign decode
        # identically today, so any winner written here would be a guess. Without this the
        # board sat on "AI to move" forever and every retry failed "not your turn".
        commands = [command for command, _ in session.katrain_calls]
        assert commands[-1] == "end_without_result"
        assert commands.index("play") < commands.index("end_without_result")
```

`tests/platforms/test_engine_integration.py` 文件末尾追加：

```python
@pytest.mark.asyncio
async def test_ai_special_coord_ends_the_local_game_without_result():
    """X9: genmove 回一个盘外坐标(星阵的停一手 / 认输都解成 UnknownSpecial)。

    真栈上要成立三件事:人那一手落下;本地局以 `Void` 结束(不再停在「轮到 AI」);
    平台上下文被摘掉。`_setup_callbacks` 在生产里由 `connect_platform` 挂上,
    这里 `_build_stack` 没走登录,手动挂 —— 否则 adapter 的 `game_ended` 没人接,
    第三条测的就不是生产里的形状。"""
    from katrain.web.platforms.gateway import PlatformMoveRejectedError

    sm, pm, gateway, adapter = _build_stack(genmove_return=GenmoveResult(coord=361, prob=0.0))
    pm._setup_callbacks(adapter)
    config = EngineGameConfig(level=1100, human_color="B")
    session_id = await pm.start_engine_game("golaxy", config, user_id=1)
    session = sm.get_session(session_id)

    with pytest.raises(PlatformMoveRejectedError) as exc_info:
        await gateway.play_move(session_id, 3, 3, user_id=1)

    assert exc_info.value.reason == "game_ended"
    assert _main_line(session) == [("B", (3, 3))]
    assert session.katrain.game.end_result == "Void"
    assert session.katrain.get_state()["end_result"] == "Void"
    assert not pm.is_platform_game(session_id)
```

新建 `tests/platforms/test_engine_game_ledger.py`：

```python
"""星阵人机局收尾的两件事:AI 结束对局时如实终局(X9),下完的每一盘进棋谱库(N13)。

接线照 `test_engine_move_guards.py`:`create_app()` 不跑 lifespan(真 Kivy 在非主线程初始化会崩),
会话用真 `WebSession` + MagicMock 的 katrain,gateway 用 MagicMock —— 这里测的是 server.py 里
**这几段分支本身**;gateway 的真行为在 test_engine_gateway.py / test_engine_integration.py。
"""

import threading
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from katrain.web.api.v1.endpoints.auth import get_current_user_optional
from katrain.web.models import User
from katrain.web.platforms.gateway import PlatformMoveRejectedError
from katrain.web.server import create_app
from katrain.web.session import WebSession

HUMAN = User(id=7, username="小明")


def _engine_session(end_result=None, human_color="B"):
    """星阵人机会话的形状:人坐一边,引擎那一边是合成 id `-1`,`user_id` 是人。"""
    katrain = MagicMock()
    katrain.game_type = "free"
    katrain.analysis_allowed = True
    katrain.get_state.return_value = {"end_result": end_result, "player_to_move": human_color, "history": []}
    katrain.game.end_result = end_result
    session = WebSession(session_id="eng-1", katrain=katrain, lock=threading.Lock())
    session.user_id = HUMAN.id
    session.player_b_id = HUMAN.id if human_color == "B" else -1
    session.player_w_id = HUMAN.id if human_color == "W" else -1
    return session


def _gateway(is_engine=True):
    gw = MagicMock()
    gw.is_platform_game.return_value = True
    gw.is_engine_game.return_value = is_engine
    gw.play_move = AsyncMock()
    gw.pass_move = AsyncMock()
    gw.resign = AsyncMock(return_value={"status": "ok"})
    return gw


def _app(session, gateway):
    app = create_app(enable_engine=False)
    app.state.session_manager._sessions[session.session_id] = session
    app.state.session_manager._schedule_broadcast = MagicMock()
    app.state.platform_gateway = gateway
    app.state.game_repo = MagicMock()
    app.dependency_overrides[get_current_user_optional] = lambda: HUMAN
    return app


def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestMoveWhenTheEngineEndsTheGame:
    async def test_game_ended_returns_the_ended_state_not_409(self):
        """人那一手落下了、这局在星阵那边结束了 —— 这次请求不是失败。回 409 的话前端会说
        「AI 连接出错,请重试落子」,而重试只会因为「不是你的回合」继续失败。"""
        session = _engine_session(end_result="Void")
        gw = _gateway()
        gw.play_move.side_effect = PlatformMoveRejectedError("AI returned non-move coord 361", reason="game_ended")
        app = _app(session, gw)

        async with _client(app) as ac:
            r = await ac.post("/api/move", json={"session_id": session.session_id, "coords": [3, 3]})

        assert r.status_code == 200, r.text
        assert r.json()["state"]["end_result"] == "Void"
        assert session.last_state["end_result"] == "Void"

    async def test_other_rejections_are_still_409(self):
        """正对照:只有 game_ended 改成 200,隧道故障等照旧 409(前端靠它弹重试提示)。"""
        session = _engine_session()
        gw = _gateway()
        gw.play_move.side_effect = PlatformMoveRejectedError("tunnel down", reason="engine_error")
        app = _app(session, gw)

        async with _client(app) as ac:
            r = await ac.post("/api/move", json={"session_id": session.session_id, "coords": [3, 3]})

        assert r.status_code == 409
        assert r.json()["detail"] == "tunnel down"
```

- [ ] **Step 2: 跑，确认红**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run pytest tests/platforms/test_engine_gateway.py tests/platforms/test_engine_integration.py tests/platforms/test_engine_game_ledger.py -q`
Expected: 3 条 FAIL——`test_engine_terminal_ends_game`（`commands[-1]` 是 `play`）、`test_ai_special_coord_ends_the_local_game_without_result`（`end_result` 为 None）、`test_game_ended_returns_the_ended_state_not_409`（409）；`test_other_rejections_are_still_409` PASS。

- [ ] **Step 3: `interface.py` 加命令**

在 `_do_timeout` 之后（`:1469` 后）插入：

```python

    def _do_end_without_result(self):
        """对局结束,不判胜负 —— SGF 的 `Void`。

        目前唯一的调用方是星阵人机局:AI 回了一个不是落点的坐标(停一手或认输;星阵这两种
        编码从没抓到过,`golaxy_to_katrain` 统一解成 UnknownSpecial),本地分不出是哪一种。
        记成「谁中盘胜」就是替它选了一个结果 ⇒ 记无胜负。`Game.end_result` 读的就是当前节点的
        `end_state`;`get_sgf` 只在结果带 `+` 时写 RE,存出来的谱不带 RE,与 SGF「无结果」一致。"""
        self.game.current_node.end_state = "Void"
```

- [ ] **Step 4: `gateway.py` 终局分支**

`:205-223`

```python
        except GolaxyEngineTerminal as e:
            # D7: the human's move is real and final (the adapter committed it on its
            # side before raising) — play it locally BEFORE the terminal/game_ended
            # broadcast, so the local record doesn't miss the actual last move. Still
            # position-gated: if the tree moved out from under us during the tunnel
            # wait, discard rather than mis-apply it to the wrong node.
            try:
                with session.lock:
                    if id(session.katrain.game.current_node) == position_token:
                        self._local_play(session_id, col, row)
                    else:
                        logger.warning(
                            f"Engine terminal for session {session_id}: position changed "
                            "during tunnel wait, discarding human move instead of misapplying it"
                        )
            finally:
                ctx.clear_pending()
```

替换为

```python
        except GolaxyEngineTerminal as e:
            # D7: the human's move is real and final (the adapter committed it on its
            # side before raising) — play it locally BEFORE the terminal/game_ended
            # broadcast, so the local record doesn't miss the actual last move. Still
            # position-gated: if the tree moved out from under us during the tunnel
            # wait, discard rather than mis-apply it to the wrong node.
            try:
                with session.lock:
                    if id(session.katrain.game.current_node) == position_token:
                        self._local_play(session_id, col, row)
                    else:
                        logger.warning(
                            f"Engine terminal for session {session_id}: position changed "
                            "during tunnel wait, discarding human move instead of misapplying it"
                        )
                    # X9: the engine has ended this game on its side (the manager already
                    # dropped the platform context via the adapter's game_ended). End the
                    # LOCAL game too, without a result: an AI pass and an AI resign decode
                    # identically today, so any winner written here would be a guess. Without
                    # this the board sat on "AI to move" forever and every retry failed
                    # "not your turn". Done on both branches above: the game is over either way.
                    session.katrain("end_without_result")
            finally:
                ctx.clear_pending()
```

（其后 `self._broadcast_rejected(session_id, "game_ended")` 与 `raise PlatformMoveRejectedError(str(e), reason="game_ended")` 两行不动——视觉路径的恢复状态机靠这个 reason 清掉 episode。）

- [ ] **Step 5: `server.py` `/api/move`**

`:983-984`（⚠️ 这两行在 `server.py` 里**出现两次**：`:983` 是 `/api/move`，`:1892` 是 `/api/resign`。只改 `/api/move` 那一处——Edit 时把它上面那行 `return {"session_id": session.session_id, "state": state}` 一起带进 old_string 保证唯一；`/api/resign` 那处不动。）

```python
            except PlatformMoveRejectedError as e:
                raise HTTPException(status_code=409, detail=str(e))
```

替换为

```python
            except PlatformMoveRejectedError as e:
                if e.reason != "game_ended":
                    raise HTTPException(status_code=409, detail=str(e))
                # X9: 星阵在它那边结束了这盘(AI 回了停一手或认输)。人那一手已经落下、本地局已由
                # gateway 以无胜负结束 ⇒ 这次请求不是失败,回终局态。回 409 的话前端会说「AI 连接出错,
                # 请重试落子」,而重试只会因为「不是你的回合」继续失败。
                state = session.katrain.get_state()
                session.last_state = state
                return {"session_id": session.session_id, "state": state}
```

- [ ] **Step 6: 跑测试、格式化**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run black -l 120 katrain/web/interface.py katrain/web/platforms/gateway.py katrain/web/server.py tests/platforms/test_engine_gateway.py tests/platforms/test_engine_integration.py tests/platforms/test_engine_game_ledger.py && uv run pytest tests/platforms/test_engine_gateway.py tests/platforms/test_engine_integration.py tests/platforms/test_engine_game_ledger.py tests/platforms/test_engine_move_guards.py tests/test_vision_move_poller.py tests/test_engine_physical_integration.py -q -rfE
```
Expected: 除 `test_engine_move_guards.py` 外全 PASS。
- ⚠️ `test_engine_move_guards.py` 在 `6f7dc629` 上**本来就红 20 条**（审查时在 HEAD 原树实跑：`_make_mock_session` 是 MagicMock，`session.user_id` 自动是个 MagicMock ⇒ `guard_session_reader` 当它有主人 ⇒ 401），只剩 4 条绿。判据是**失败用例名集合与 Task 0 基线相同**（`comm`），不是全绿；不许顺手修那个夹具（不是本轮的活）。
- ⚠️ `server.py` 在基线上**本来就不是 black 干净的**：black 会顺带把 `:341-343` 的 `app.state.report_settlement_task = asyncio.create_task(...)` 三行并成一行。那一块不是本 Task 的改动、又在多赛道共享文件里 ⇒ `git diff katrain/web/server.py` 核对后把那一块还原（`git checkout -p` 或手工改回），只留本 Task 的改动。Task 6 再跑 black 时同样处理。

- [ ] **Step 7: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add katrain/web/interface.py katrain/web/platforms/gateway.py katrain/web/server.py tests/platforms/test_engine_gateway.py tests/platforms/test_engine_integration.py tests/platforms/test_engine_game_ledger.py && git commit -m "$(cat <<'EOF'
fix(platforms): 星阵 AI 停手/认输时本地局如实结束 —— 不再报「AI 连接出错」且卡死

AI 回非落点坐标时 manager 摘掉了平台上下文,本地局却没有结果:屏上停在「轮到 AI」,
/api/move 一律 409 ⇒ 前端弹「AI 连接出错,请重试落子」,重试因「不是你的回合」继续失败。
星阵的停一手与认输编码没抓到、分不出是哪种 ⇒ 本地局以 SGF「无胜负」Void 结束
(新命令 end_without_result),/api/move 对 game_ended 回 200 + 终局态,其它 reason 仍 409。
视觉路径共用 gateway,同一个终局;reason 不变,恢复状态机照旧清 episode。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: N13 后端 —— 星阵人机局在三条终局路上落账到 `user_games`

**Files:**
- Modify: `katrain/web/server.py:1599`（`_record_ai_game_locked` 签名）、`:1676-1678`（`data` 构造之后合并 overrides）、`:1864-1870`（`_record_ai_game` 签名）
- Modify: `katrain/web/server.py:1883-1893`（`/api/resign` 判引擎局）、`:1926-1938`（落账分支）
- Modify: `katrain/web/server.py` `/api/move` 平台分支（Task 5 加的 `game_ended` 分支里补一行落账）
- Modify: `katrain/web/server.py:3107` 之前（新增模块级 `_session_owner`、`_record_platform_engine_game`）、`:3217-3222`（`_handle_confirmed_move` 的 `except PlatformMoveRejectedError`）
- Test: `tests/platforms/test_engine_game_ledger.py`（追加）、`tests/test_vision_move_poller.py`（追加）

**Interfaces:**
- Consumes: Task 5 的 `"end_without_result"` 命令与 `/api/move` 的 `game_ended` 分支；`tests/platforms/test_engine_game_ledger.py` 的 `HUMAN`、`_engine_session`、`_gateway`、`_app`、`_client`；`PlatformCommandGateway.is_engine_game(session_id) -> bool`（`gateway.py:99-106`）；`app.state.user_repo.get_user_by_id(user_id) -> dict | None`（`core/auth.py:219`，字段含 `id`、`username`）。
- Produces:
  - `_record_ai_game(session, app, current_user, result, data_overrides: dict | None = None)`（闭包，经 `server._RECORD_FN` 暴露）：`data_overrides` 在**非升降级**局里合进写库的 `data`。
  - 模块级 `def _session_owner(app, session) -> SimpleNamespace(id, username) | None`。
  - 模块级 `async def _record_platform_engine_game(app, session, user) -> None`：`user` 为 None 或 `session.katrain.game.end_result` 为空时不写；否则调 `_RECORD_FN(session, app, user, result, data_overrides={"source": "play_ai", "player_black": …, "player_white": …})`，人那一方写 `user.username`。

- [ ] **Step 1: 写测试（先红）**

`tests/platforms/test_engine_game_ledger.py` 文件头 import 段追加两行：

```python
from types import SimpleNamespace

import katrain.web.server as server
```

文件末尾追加：

```python
class TestMoveLedger:
    async def test_ai_terminal_move_is_recorded_for_the_requesting_user(self, monkeypatch):
        session = _engine_session(end_result="Void")
        gw = _gateway()
        gw.play_move.side_effect = PlatformMoveRejectedError("AI returned non-move coord 361", reason="game_ended")
        app = _app(session, gw)
        recorder = AsyncMock()
        monkeypatch.setattr(server, "_record_platform_engine_game", recorder)

        async with _client(app) as ac:
            r = await ac.post("/api/move", json={"session_id": session.session_id, "coords": [3, 3]})

        assert r.status_code == 200, r.text
        recorder.assert_awaited_once()
        assert recorder.await_args.args[1] is session
        assert recorder.await_args.args[2].id == HUMAN.id


class TestResignLedger:
    async def test_engine_resign_goes_through_the_ai_game_ledger(self, monkeypatch):
        """N13:星阵人机局只有一个 KaTrain 用户、对手是外部引擎 —— 走人机局那条两种部署都通的落账路。
        原来的 `record_multiplayer_game` 在盒上一次都没写进去过(`game_repo` 恒为 None),
        在服务端写进去的是一局没名字的 `play_human`。"""
        session = _engine_session(end_result="W+R")
        gw = _gateway(is_engine=True)

        async def _resign_drops_context(*_args, **_kwargs):
            # 真 gateway.resign 会经 adapter → manager 摘掉平台上下文 ⇒ 之后再问就不是引擎局了。
            # 「是不是引擎局」必须在它之前判;这一行让判晚了的实现当场红。
            gw.is_engine_game.return_value = False
            return {"status": "ok"}

        gw.resign.side_effect = _resign_drops_context
        app = _app(session, gw)
        recorder = AsyncMock()
        monkeypatch.setattr(server, "_record_platform_engine_game", recorder)

        async with _client(app) as ac:
            r = await ac.post("/api/resign", json={"session_id": session.session_id})

        assert r.status_code == 200, r.text
        recorder.assert_awaited_once()
        assert recorder.await_args.args[1] is session
        assert recorder.await_args.args[2].id == HUMAN.id
        app.state.game_repo.record_multiplayer_game.assert_not_called()
        sent = [call.args[1] for call in app.state.session_manager._schedule_broadcast.call_args_list]
        assert any(m.get("type") == "game_end" for m in sent), "引擎局认输也要照旧广播 game_end"

    async def test_non_engine_platform_resign_still_uses_the_multiplayer_repo(self, monkeypatch):
        """正对照:OGS 这类真人平台局(两个 KaTrain 侧用户的语义)不改路。"""
        session = _engine_session(end_result="W+R")
        app = _app(session, _gateway(is_engine=False))
        recorder = AsyncMock()
        monkeypatch.setattr(server, "_record_platform_engine_game", recorder)

        async with _client(app) as ac:
            r = await ac.post("/api/resign", json={"session_id": session.session_id})

        assert r.status_code == 200, r.text
        recorder.assert_not_awaited()
        app.state.game_repo.record_multiplayer_game.assert_called_once()


class TestRecordPlatformEngineGame:
    @staticmethod
    def _session(end_result, human_color="B"):
        session = _engine_session(end_result=end_result, human_color=human_color)
        me = SimpleNamespace(name="Me", human=False, ai=False, calculated_rank=None, sgf_rank=None)
        bot = SimpleNamespace(name="[golaxy] 星铠虾", human=False, ai=False, calculated_rank="2段", sgf_rank=None)
        session.katrain.players_info = {"B": me, "W": bot} if human_color == "B" else {"B": bot, "W": me}
        return session

    async def test_human_seat_gets_the_account_name_and_source_is_play_ai(self, monkeypatch):
        """会话上人那一方叫占位的 "Me";复盘列表认「你是哪一方」靠的正是存进去的名字。"""
        record = AsyncMock()
        monkeypatch.setattr(server, "_RECORD_FN", record, raising=False)
        session, app = self._session("W+R"), MagicMock()

        await server._record_platform_engine_game(app, session, HUMAN)

        record.assert_awaited_once()
        assert record.await_args.args == (session, app, HUMAN, "W+R")
        assert record.await_args.kwargs["data_overrides"] == {
            "source": "play_ai", "player_black": "小明", "player_white": "[golaxy] 星铠虾",
        }

    async def test_human_on_white_gets_the_name_on_white(self, monkeypatch):
        record = AsyncMock()
        monkeypatch.setattr(server, "_RECORD_FN", record, raising=False)

        await server._record_platform_engine_game(MagicMock(), self._session("B+R", human_color="W"), HUMAN)

        overrides = record.await_args.kwargs["data_overrides"]
        assert (overrides["player_black"], overrides["player_white"]) == ("[golaxy] 星铠虾", "小明")

    async def test_nothing_is_written_without_a_result_or_a_user(self, monkeypatch):
        record = AsyncMock()
        monkeypatch.setattr(server, "_RECORD_FN", record, raising=False)

        await server._record_platform_engine_game(MagicMock(), self._session(None), HUMAN)
        await server._record_platform_engine_game(MagicMock(), self._session("W+R"), None)

        record.assert_not_awaited()

    async def test_the_real_record_fn_writes_the_overrides_into_the_row(self):
        """不 mock `_RECORD_FN`:overrides 真的进了盒上那条 `repository_dispatcher.user_games_create` 的 data。"""
        create_app(enable_engine=False)  # `_RECORD_FN` 由 create_app 填上
        session = self._session("Void")
        session.katrain.get_sgf.return_value = "(;GM[1])"
        session.katrain.get_state.return_value = {
            "board_size": [19, 19], "history": [1, 2], "komi": 7.5, "ruleset": "chinese",
        }
        app = MagicMock()
        app.state.repository_dispatcher.user_games_create = AsyncMock(return_value={"id": "g1"})

        await server._record_platform_engine_game(app, session, HUMAN)

        app.state.repository_dispatcher.user_games_create.assert_awaited_once()
        kwargs = app.state.repository_dispatcher.user_games_create.await_args.kwargs
        assert kwargs["user_id"] == HUMAN.id
        data = kwargs["data"]
        assert data["source"] == "play_ai"
        assert (data["player_black"], data["player_white"]) == ("小明", "[golaxy] 星铠虾")
        assert data["result"] == "Void"
```

`tests/test_vision_move_poller.py` 文件末尾追加：

```python
class TestGameEndedIsRecordedForTheSessionOwner:
    """N13:实体盘上那一手之后星阵结束了这盘。这条路没有 HTTP 请求、没有 current_user ⇒ 认会话主人落账。"""

    def test_records_with_the_session_owner(self, monkeypatch):
        from unittest.mock import AsyncMock

        import katrain.web.server as server

        session = FakeSession()
        session.user_id = 7
        sm = FakeSessionManager({"s1": session})
        gateway = FakeGateway(outcomes=[PlatformMoveRejectedError("over", reason="game_ended")])
        app = _app(sm, gateway=gateway, tracker=EngineRecoveryTracker())
        app.state.user_repo = SimpleNamespace(
            get_user_by_id=lambda uid: {"id": uid, "username": "小明"} if uid == 7 else None
        )
        recorder = AsyncMock()
        monkeypatch.setattr(server, "_record_platform_engine_game", recorder)

        delay = asyncio.run(_handle_confirmed_move(app, FakeVision(), "s1", _move(), log))

        assert delay == 0.0
        recorder.assert_awaited_once()
        _, recorded_session, owner = recorder.await_args.args
        assert recorded_session is session
        assert (owner.id, owner.username) == (7, "小明")

    def test_unknown_owner_is_passed_as_none_and_nothing_raises(self, monkeypatch):
        from unittest.mock import AsyncMock

        import katrain.web.server as server

        sm = FakeSessionManager({"s1": FakeSession()})  # 没有 user_id,app 上也没有 user_repo
        gateway = FakeGateway(outcomes=[PlatformMoveRejectedError("over", reason="game_ended")])
        app = _app(sm, gateway=gateway, tracker=EngineRecoveryTracker())
        recorder = AsyncMock()
        monkeypatch.setattr(server, "_record_platform_engine_game", recorder)

        asyncio.run(_handle_confirmed_move(app, FakeVision(), "s1", _move(), log))

        assert recorder.await_args.args[2] is None
```

- [ ] **Step 2: 跑，确认红**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run pytest tests/platforms/test_engine_game_ledger.py tests/test_vision_move_poller.py -q`
Expected: 恰好 9 条 FAIL，**全部**是 `AttributeError: … has no attribute '_record_platform_engine_game'`——新增的 9 条（`TestMoveLedger` 1、`TestResignLedger` 2、`TestRecordPlatformEngineGame` 4、`TestGameEndedIsRecordedForTheSessionOwner` 2）都先 `monkeypatch.setattr(server, "_record_platform_engine_game", …)` 或直接调它，属性不存在时在断言之前就炸，**包括 `TestResignLedger` 的正对照**（审查时实跑确认）。其余既有用例 PASS。这一步的红只证明「helper 还不存在」；「引擎局判晚了」这种错由 Step 7 的变异来证（审查时实跑：该变异只红 `test_engine_resign_goes_through_the_ai_game_ledger` 一条）。

- [ ] **Step 3: `_record_ai_game(_locked)` 接受 `data_overrides`**

`:1599`

```python
    async def _record_ai_game_locked(session, app, current_user, result):
```

替换为

```python
    async def _record_ai_game_locked(session, app, current_user, result, data_overrides=None):
```

`data = {...}` 字典收尾处（`:1676-1678`）

```python
                "game_type": game_type,
                "game_date": game_date,
            }

            if game_type == "ai_ladder_ranked":
```

替换为

```python
                "game_type": game_type,
                "game_date": game_date,
            }

            # 调用方替这一局说清「它是什么局、谁坐哪边」—— 星阵人机局的两个座位都是 bare "human"、
            # 人那一方叫占位的 "Me",上面那段推不出来(`_record_platform_engine_game`)。
            # 升降级那一支自己校验 source,不接受外来覆盖。
            if data_overrides and game_type != "ai_ladder_ranked":
                data.update(data_overrides)

            if game_type == "ai_ladder_ranked":
```

`_record_ai_game`（`:1864-1870`）

```python
    async def _record_ai_game(session, app, current_user, result):
        record_lock = getattr(session, "record_game_lock", None)
        if not isinstance(record_lock, asyncio.Lock):
            record_lock = asyncio.Lock()
            session.record_game_lock = record_lock
        async with record_lock:
            await _record_ai_game_locked(session, app, current_user, result)
```

替换为

```python
    async def _record_ai_game(session, app, current_user, result, data_overrides=None):
        record_lock = getattr(session, "record_game_lock", None)
        if not isinstance(record_lock, asyncio.Lock):
            record_lock = asyncio.Lock()
            session.record_game_lock = record_lock
        async with record_lock:
            await _record_ai_game_locked(session, app, current_user, result, data_overrides=data_overrides)
```

- [ ] **Step 4: 模块级 helper**

在 `def _apply_engine_recovery_outcome(`（`:3107`）之前插入：

```python
def _session_owner(app: FastAPI, session):
    """会话主人,形状与 `current_user` 相同(只带 `id` / `username`)。

    视觉那条路没有 HTTP 请求,也就没有 `current_user`;要替会话落账时只能认主人。盒上的主人是
    shadow user,`user_repo` 里查得到。查不到返回 None —— 调用方就不写,不猜一个名字出来。"""
    user_id = getattr(session, "user_id", None)
    repo = getattr(app.state, "user_repo", None)
    if user_id is None or repo is None:
        return None
    row = repo.get_user_by_id(user_id)
    if not row:
        return None
    return SimpleNamespace(id=row["id"], username=row["username"])


async def _record_platform_engine_game(app: FastAPI, session, user) -> None:
    """N13 —— 星阵人机局落账。盒上与服务端两种部署都走 `_record_ai_game` 那条路。

    它只有**一个** KaTrain 用户、对手是外部引擎,语义就是人机局 ⇒ 不走 `record_multiplayer_game`
    (盒上 `app.state.game_repo` 恒为 None,一次都没写进去过;服务端写进去的是一局没名字的 `play_human`)。
    也因此它**不依赖**「跨盒人人对弈 / 盒上账本」的裁定 —— 那两条管的是两个 KaTrain 用户的局。

    替会话说清两件 `_record_ai_game` 自己推不出来的事:
      · `source` 写 `play_ai` —— 两个座位的 player_type 都是 bare "human";
      · 人那一方写**账号名** —— 会话上是占位的 "Me",而复盘列表认「你是哪一方」靠的正是存进去的名字
        (`kiosk/components/report/reviewPresentation.ts` `yourColor`)。
    局还没有结果、或者认不出是谁时不写。"""
    if user is None:
        return
    result = session.katrain.game.end_result
    if not result:
        return
    record = globals().get("_RECORD_FN")
    if record is None:
        return
    players = session.katrain.players_info
    names = {"B": players["B"].name or "", "W": players["W"].name or ""}
    names["B" if session.player_b_id == user.id else "W"] = user.username
    await record(
        session,
        app,
        user,
        result,
        data_overrides={"source": "play_ai", "player_black": names["B"], "player_white": names["W"]},
    )


```

- [ ] **Step 5: 三处调用**

(a) `/api/resign`（`:1883-1893`）

```python
        # Route through platform gateway for cross-platform games
        gateway = getattr(app.state, "platform_gateway", None)
        platform_game = bool(not ranked_ai and gateway and gateway.is_platform_game(request.session_id))
        if platform_game:
```

替换为

```python
        # Route through platform gateway for cross-platform games
        gateway = getattr(app.state, "platform_gateway", None)
        platform_game = bool(not ranked_ai and gateway and gateway.is_platform_game(request.session_id))
        # N13: 必须在 `gateway.resign` 之前判 —— 它会经 adapter → manager 摘掉平台上下文,之后再问就不是引擎局了。
        engine_game = bool(platform_game and gateway.is_engine_game(request.session_id))
        if platform_game:
```

落账分支（`:1926-1938`）

```python
        if is_multiplayer and current_user:
            winner_id = session.player_w_id if current_user.id == session.player_b_id else session.player_b_id
            result = f"{'W' if winner_id == session.player_w_id else 'B'}+R"
            try:
                app.state.game_repo.record_multiplayer_game(
                    sgf_content=session.katrain.get_sgf(),
                    result=result,
                    game_type=getattr(session, "game_type", "free"),
                    black_id=session.player_b_id,
                    white_id=session.player_w_id,
                )
            except Exception as e:
                logging.getLogger("katrain_web").error(f"Failed to record game result: {e}")
```

替换为

```python
        if is_multiplayer and current_user:
            winner_id = session.player_w_id if current_user.id == session.player_b_id else session.player_b_id
            result = f"{'W' if winner_id == session.player_w_id else 'B'}+R"
            if engine_game:
                # N13: 星阵人机局按人机局落账(见 `_record_platform_engine_game`)。
                await _record_platform_engine_game(app, session, current_user)
            else:
                try:
                    app.state.game_repo.record_multiplayer_game(
                        sgf_content=session.katrain.get_sgf(),
                        result=result,
                        game_type=getattr(session, "game_type", "free"),
                        black_id=session.player_b_id,
                        white_id=session.player_w_id,
                    )
                except Exception as e:
                    logging.getLogger("katrain_web").error(f"Failed to record game result: {e}")
```

（其后的 `game_end` 广播块不动。）

(b) `/api/move` —— Task 5 加的分支里，把

```python
                state = session.katrain.get_state()
                session.last_state = state
                return {"session_id": session.session_id, "state": state}
```

（**只改 `except PlatformMoveRejectedError` 里 `if e.reason != "game_ended"` 之后的那一份**，try 块里同形的三行不动）替换为

```python
                state = session.katrain.get_state()
                session.last_state = state
                await _record_platform_engine_game(app, session, current_user)  # N13
                return {"session_id": session.session_id, "state": state}
```

(c) `_handle_confirmed_move`（`:3217-3222`）

```python
        except PlatformMoveRejectedError as e:
            log.warning("Platform gateway rejected vision move: %s", e)
            rearm = _apply_engine_recovery_outcome(app, manager, session_id, game_id, coords, e.reason, str(e))
            if rearm:
```

替换为

```python
        except PlatformMoveRejectedError as e:
            log.warning("Platform gateway rejected vision move: %s", e)
            rearm = _apply_engine_recovery_outcome(app, manager, session_id, game_id, coords, e.reason, str(e))
            if e.reason == "game_ended":
                # N13: 实体盘上这一手之后星阵结束了这盘(gateway 已把本地局以无胜负结束)。
                # 这条路没有请求、没有 current_user ⇒ 认会话主人落账。
                await _record_platform_engine_game(app, session, _session_owner(app, session))
            if rearm:
```

- [ ] **Step 6: 跑测试、格式化**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run black -l 120 katrain/web/server.py tests/platforms/test_engine_game_ledger.py tests/test_vision_move_poller.py && uv run pytest tests/platforms/test_engine_game_ledger.py tests/test_vision_move_poller.py tests/test_local_play_recording.py tests/web_ui/test_ai_game_autosave.py tests/web_ui/test_game_termination_and_chat_identity.py tests/platforms/test_engine_move_guards.py -q -rfE
```
Expected: 除 `test_engine_move_guards.py` 基线就有的 20 条红（见 Task 5 Step 6，名字集合不许变）外全 PASS（后四个文件守的是既有落账 / 认输广播，确认没被改坏）。black 顺带改到的 `:341-343` 那一块照 Task 5 Step 6 还原。

- [ ] **Step 7: 变异验证（不提交）**

把 (a) 里 `engine_game = …` 那一行挪到 `if platform_game:` 块里 `await gateway.resign(...)` 之后，重跑 `uv run pytest tests/platforms/test_engine_game_ledger.py -q`，Expected：`test_engine_resign_goes_through_the_ai_game_ledger` 红；还原后绿。

- [ ] **Step 8: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add katrain/web/server.py tests/platforms/test_engine_game_ledger.py tests/test_vision_move_poller.py && git commit -m "$(cat <<'EOF'
fix(platforms): 星阵人机局下完进棋谱库 —— 盒上一盘都没存进去过

认输走联机局分支调 app.state.game_repo.record_multiplayer_game,盒上 game_repo 恒为 None,
AttributeError 被吞;AI 终局那条路完全不落账;服务端写进去的是一局没名字的 play_human。
星阵人机局只有一个 KaTrain 用户、对手是外部引擎,改走人机局那条两种部署都通的
_record_ai_game(新增 data_overrides):source=play_ai,人那一方写账号名(会话上是占位 "Me")。
三处调用:/api/resign(摘上下文之前判引擎局)、/api/move 的 game_ended、视觉路径的 game_ended(认会话主人)。
OGS 真人局不改路(正对照)。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: X9-b / N13 前端 —— 把 `Void` 说成人话

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx:122-123`（`EndgameCard` 结果徽标之后）
- Modify: `katrain/web/ui/src/kiosk/components/report/reviewPresentation.ts:96-101`（`outcomeLine`）
- Test: `katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx:202-208`（afterEach）、`:620` 之前（新 describe）
- Test: `katrain/web/ui/src/kiosk/components/report/reviewPresentation.test.ts:98-101`

**Interfaces:**
- Consumes: Task 5 起 `GameState.end_result` 可能为 `"Void"`；Task 6 起 `UserGameSummary.result` 可能为 `"Void"`；`GameState.platform_engine_color?: 'B' | 'W' | null`（`api.ts:113`）。
- Produces: 无。

- [ ] **Step 1: 写测试（先红）**

`GamePageEngine.test.tsx` 主 `afterEach`（`:202-208`）的 `mockGameState.count_min_moves = undefined;` 之后加：

```tsx
    mockGameState.end_result = null;
    mockGameState.platform_engine_color = undefined;
```

在 `describe('G2: engine-aware humanColor / aiTurn derivation (platform_engine_color)')` 之前插入：

```tsx
  // X9:星阵 AI 回了停一手或认输(编码没抓到,分不出是哪一种),后端以无胜负 `Void` 结束了这盘。
  // 结果徽标那一格只会写「?」—— 不补这一句,用户会以为结果丢了。
  describe('星阵 AI 结束对局(无胜负)', () => {
    it('星阵局以 Void 结束:终局卡说清为什么没有胜负', () => {
      mockGameState.end_result = 'Void';
      mockGameState.platform_engine_color = 'W';
      renderPage(true);
      expect(screen.getByTestId('endgame-no-result')).toHaveTextContent('星阵 AI 停手或认输了');
    });

    it('普通终局不出这一行(正对照)', () => {
      mockGameState.end_result = 'W+R';
      mockGameState.platform_engine_color = 'W';
      renderPage(true);
      expect(screen.getByTestId('endgame-card')).toBeInTheDocument();
      expect(screen.queryByTestId('endgame-no-result')).toBeNull();
    });
  });
```

`reviewPresentation.test.ts:98-101`

```ts
  it('后端存了别的写法就原样念,不猜', () => {
    expect(outcomeLine(game({ result: 'Void' }), 'B', t)).toBe('Void');
  });
```

替换为

```ts
  // `Void` 是 SGF 规范里定义好的「不判胜负」,今天由星阵人机局写进来(AI 停手或认输,分不出是哪种)。
  // 照它的意思念,不是猜;规范之外的写法仍原样念。
  it('Void 念成「这盘没有判出胜负」', () => {
    expect(outcomeLine(game({ result: 'Void' }), 'B', t)).toBe('这盘没有判出胜负');
    expect(outcomeLine(game({ result: 'void' }), null, t)).toBe('这盘没有判出胜负');
  });

  it('后端存了别的写法就原样念,不猜', () => {
    expect(outcomeLine(game({ result: 'Unknown' }), 'B', t)).toBe('Unknown');
  });
```

- [ ] **Step 2: 跑，确认红**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/__tests__/GamePageEngine.test.tsx src/kiosk/components/report/reviewPresentation.test.ts`
Expected: 「星阵局以 Void 结束…」与「Void 念成…」FAIL；其余 PASS。

- [ ] **Step 3: 改 `GamePage.tsx` `EndgameCard`**

```tsx
      <KioskResultBadge result={gameState.end_result!} rules={gameState.ruleset} />
```

替换为

```tsx
      <KioskResultBadge result={gameState.end_result!} rules={gameState.ruleset} />
      {/* X9:星阵 AI 回了停一手或认输(编码没抓到,分不出是哪一种),后端以无胜负 `Void` 结束了这盘。
          徽标那一格只会写「?」—— 这一句说清为什么没有胜负,而不是让人以为结果丢了。 */}
      {gameState.end_result === 'Void' && gameState.platform_engine_color && (
        <Typography
          variant="caption"
          data-testid="endgame-no-result"
          sx={{ color: 'text.secondary', textAlign: 'center', maxWidth: 320 }}
        >
          {t('game:engine_ended_no_result', '星阵 AI 停手或认输了 · 本终端还分不出是哪一种，这盘不判胜负')}
        </Typography>
      )}
```

- [ ] **Step 4: 改 `reviewPresentation.ts`**

```ts
  const m = raw.match(/^([BW])\+(.+)$/i);
  if (!m) return raw;                       // 后端存了别的写法就原样念,不猜
```

替换为

```ts
  // SGF 的 `Void` = 不判胜负。今天只由星阵人机局写进来(AI 停手或认输,本终端分不出是哪种,
  // server.py `_record_platform_engine_game`)。规范里有定义的值,照它的意思念,不算猜。
  if (/^void$/i.test(raw)) return t('review:no_result_line', '这盘没有判出胜负');
  const m = raw.match(/^([BW])\+(.+)$/i);
  if (!m) return raw;                       // 后端存了别的写法就原样念,不猜
```

- [ ] **Step 5: 跑测试与类型检查**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/__tests__/GamePageEngine.test.tsx src/kiosk/components/report/reviewPresentation.test.ts src/kiosk/pages/GamePage.test.tsx && npx tsc -b
```
Expected: 全 PASS；`tsc -b` 退出 0。

- [ ] **Step 6: 实运行预览（无设计稿参考，给 Fan 看一帧）**

这一态设计稿里没有，四图无参考图可比 ⇒ 按 CLAUDE.md 相称性取**一张真运行时截图**：
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && cat > "${TMPDIR:-/tmp}/kgcp-void-card.spec.ts" <<'EOF'
import { test } from '@playwright/test';
import { KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';
test.use({ viewport: KIOSK_VIEWPORT });
test('屏 10 · 星阵 AI 结束对局(Void)', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'preview');
    localStorage.setItem('katrain_language', 'cn');
    localStorage.setItem('kiosk_play_on_board', 'false');
  });
  const state = {
    game_id: 'void-preview', board_size: [19, 19], komi: 7.5, handicap: 0, ruleset: 'chinese', game_type: 'free',
    count_min_moves: 100, current_node_id: 1, current_node_index: 1,
    history: [{ node_id: 0, winrate: 0.5, score: 0, move: null, player: null }, { node_id: 1, winrate: 0.5, score: 0, move: 'D4', player: 'B' }],
    player_to_move: 'W', stones: [['B', [3, 3], null, 1]], last_move: [3, 3], prisoner_count: { B: 0, W: 0 },
    analysis: null, commentary: '', is_root: false, is_pass: false, end_result: 'Void', children: [], ghost_stones: [],
    platform_engine_color: 'W',
    players_info: {
      B: { player_type: 'player:human', player_subtype: '', name: '访客（你）', calculated_rank: '', periods_used: 0, main_time_used: 0 },
      W: { player_type: 'player:human', player_subtype: '', name: '星皮猴', calculated_rank: '2段', periods_used: 0, main_time_used: 0 },
    },
    note: '', ui_state: { show_children: false, show_dots: false, show_hints: false, show_policy: false,
      show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false },
  };
  await stubBackendStatics(page);
  await page.routeWebSocket('**/ws/**', () => {});
  await page.route('**/api/state**', (r) => r.fulfill({ json: { state } }));
  await page.route('**/api/v1/**', (r) => {
    const path = new URL(r.request().url()).pathname;
    if (path === '/api/v1/auth/me') return r.fulfill({ json: { id: 1, username: '访客', rank: '5段', credits: 0 } });
    // 与屏 10 四图同一套桩(`kiosk-screen-10-platform-game.fourup.spec.ts`):识别关着、几何 404。
    if (path === '/api/v1/vision/status') {
      return r.fulfill({ json: { enabled: false, camera_connected: false, pose_locked: false,
        sync_state: 'unbound', recognition_ready: false, led_connected: null, bound_session_id: null } });
    }
    if (path === '/api/v1/geometry/status') return r.fulfill({ status: 404, json: { detail: 'geometry disabled' } });
    return r.fulfill({ json: {} });
  });
  await page.goto('/kiosk/play/cross-platform/engine/game/void-preview');
  await page.waitForSelector('[data-testid="endgame-no-result"]');
  await page.screenshot({ path: `${process.env.TMPDIR ?? '/tmp'}/kgcp-void-card.png` });
});
EOF
cp "${TMPDIR:-/tmp}/kgcp-void-card.spec.ts" tests/zz-kgcp-void-card.preview.spec.ts && npx playwright test --config=playwright.visual.config.ts tests/zz-kgcp-void-card.preview.spec.ts; rm -f tests/zz-kgcp-void-card.preview.spec.ts
```
Expected: 用例 PASS，生成 `${TMPDIR}/kgcp-void-card.png`；用 Read 看图：终局卡里徽标「?」下方有那句说明、没有被截断。截图路径记进 Task 9 给 Fan 的确认清单。**临时 spec 必须删掉、不提交**（`git status` 不应出现它）。

- [ ] **Step 7: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx katrain/web/ui/src/kiosk/components/report/reviewPresentation.ts katrain/web/ui/src/kiosk/components/report/reviewPresentation.test.ts && git commit -m "$(cat <<'EOF'
feat(kiosk): 星阵 AI 结束对局时终局卡与复盘列表说清「这盘不判胜负」

后端以 SGF 的 Void 结束这类局(AI 停手或认输,分不出是哪种)。终局卡徽标只会写「?」,
补一句原因;复盘列表把 Void 念成「这盘没有判出胜负」,规范之外的写法仍原样念。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: X10-a —— 实体盘等待态加「认输」（M2）；终局时释放恢复暂停并熄灯（M4）

**Files:**
- Modify: `katrain/web/ui/src/kiosk/components/physical/EngineMoveErrorDialog.tsx:172-182`（waiting 分支）
- Test: `katrain/web/ui/src/kiosk/__tests__/EngineMoveErrorDialog.test.tsx`（`describe` 收尾 `});` 之前追加）
- Modify: `katrain/web/core/physical_play_orchestrator.py:293-300`（`_run` 循环开头）、`:412` 之后（`_complete_awaiting_removal` 之后新增方法）
- Test: `tests/test_physical_play_orchestrator.py`（在文件末 `def led_calls_for` 之前追加一个 class）

**Interfaces:**
- Consumes: 对话框既有的 `onResign` prop 与 `handleResign`；编排器既有的 `clear_engine_error()`、`clear_awaiting_removal()`、`_apply_points(points)`、`_latest_state`、`PAUSE_REASON_ENGINE_ERROR` / `PAUSE_REASON_AWAITING_REMOVAL`；测试文件既有的 `_orch(**cfg)`、`state(stones, end_result=None)`、`FakeLed`、`FakeVision`。
- Produces: `PhysicalPlayOrchestrator._release_recovery_on_game_end(self) -> bool`。

- [ ] **Step 1: 写测试（先红）**

`EngineMoveErrorDialog.test.tsx` 最后一个 `it` 之后、`describe` 收尾 `});` 之前插入：

```tsx
  // M2(2026-07-11 登记):等待态原来一颗键都没有、点背景也关不掉,而解除条件是「识别盘面与数字盘面
  // 整盘一致连续 N 帧」—— 反光、手影、识别不到盘面时会一直挂住,只能离开围棋应用。
  it('等待拿回棋子时也有出口:认输走页面的确认流,弹层自己不关', async () => {
    cancel.mockResolvedValueOnce({ ok: true, awaiting_removal: true });
    const onResign = vi.fn();
    render(<EngineMoveErrorDialog {...base} onResign={onResign} error={baseError} />);

    fireEvent.click(screen.getByText('拿回棋子'));
    expect(await screen.findByText('等待拿回棋子')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '认输' }));
    expect(onResign).toHaveBeenCalledTimes(1);
    expect(screen.getByText('等待拿回棋子')).toBeInTheDocument();
  });
```

`tests/test_physical_play_orchestrator.py` 在 `def led_calls_for(orch):` 之前插入：

```python
class TestRecoveryReleasedOnGameEnd:
    """X10 / M4:恢复框里认输(出错态或等待态都能认输)之后,engine_error / awaiting_removal 两个暂停
    会让 `_run` 跳过 `_tick_once` —— 而「终局清灯」只在 `_tick_once` 里 ⇒ 灯一直亮到离开对局页。"""

    @staticmethod
    def _lit(**cfg):
        orch, led, vision, _ = _orch(**cfg)
        orch.on_game_state(state([["B", [3, 15], None, 1]]))  # GTP y=15 -> vision row 3
        orch._tick_once()
        assert led.calls[-1] == ("set_points", [{"row": 3, "col": 3, "color": "black"}])
        return orch, led, vision

    def test_run_loop_releases_engine_error_and_clears_lamps_when_the_game_ends(self):
        """走真的 `_run` 循环 —— 证的是「接进了循环」,不只是那个方法本身对。
        变异记录:删掉 `_run` 里那一行调用 → 这条红(暂停原因还在、最后一次 LED 调用仍是 set_points)。"""
        orch, led, vision = self._lit(tick_interval_s=0.01)
        orch.enter_engine_error((3, 15), "tok-1")
        orch.on_game_state(state([["B", [3, 15], None, 1]], end_result="W+R"))

        async def run():
            task = asyncio.create_task(orch._run())
            await asyncio.sleep(0.05)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        asyncio.run(run())

        assert orch._pause_reasons == set()
        assert orch._suspended is False
        assert vision.paused is False
        assert led.calls[-1] == ("clear",)

    def test_awaiting_removal_is_released_when_the_game_ends(self):
        orch, led, vision = self._lit()
        orch.enter_engine_error((3, 15), "tok-1")
        orch.enter_awaiting_removal((3, 15))
        orch.on_game_state(state([["B", [3, 15], None, 1]], end_result="W+R"))

        assert orch._release_recovery_on_game_end() is True
        assert orch._awaiting_removal_context is None
        # `_lit` 那一 tick 盘上没摆子 ⇒ 已经挂着「欠一手」的 lag。lag 不归这里放:下一次普通 tick
        # 见终局会 `_set_caught_up(True)` 清掉它(上一条走真循环的用例证的正是这一步),
        # 而 lag 单独在时不挂起 tick。直接调方法时它还在 —— 写 `== set()` 会红(审查时实跑过)。
        assert orch._pause_reasons == {PhysicalPlayOrchestrator.PAUSE_REASON_LAG}
        assert orch._suspended is False
        assert led.calls[-1] == ("clear",)

    def test_nothing_is_released_while_the_game_is_still_running(self):
        orch, led, _ = self._lit()
        orch.enter_engine_error((3, 15), "tok-1")

        assert orch._release_recovery_on_game_end() is False
        assert PhysicalPlayOrchestrator.PAUSE_REASON_ENGINE_ERROR in orch._pause_reasons
        assert led.calls[-1] == ("set_points", [{"row": 3, "col": 3, "color": "black"}])


```

- [ ] **Step 2: 跑，确认红**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/__tests__/EngineMoveErrorDialog.test.tsx
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run pytest tests/test_physical_play_orchestrator.py -q
```
Expected: 前端「等待拿回棋子时也有出口…」FAIL（找不到「认输」按钮）；后端 `TestRecoveryReleasedOnGameEnd` 3 条 FAIL（前一条暂停原因仍在，后两条 `AttributeError: _release_recovery_on_game_end`）。

- [ ] **Step 3: 改 `EngineMoveErrorDialog.tsx` waiting 分支**

`:172-182`

```tsx
        ) : (
          <>
            <DialogTitle>{t('Waiting for stone removal', '等待拿回棋子')}</DialogTitle>
            <DialogContent sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <CircularProgress size={20} />
              <Typography variant="body2" color={emphasized ? 'warning.main' : 'text.primary'}>
                {t('Please remove the stone at {coord}', '请拿回 {coord} 处的棋子').replace('{coord}', coordLabel)}
              </Typography>
            </DialogContent>
          </>
        )}
```

替换为

```tsx
        ) : (
          <>
            <DialogTitle>{t('Waiting for stone removal', '等待拿回棋子')}</DialogTitle>
            <DialogContent sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <CircularProgress size={20} />
              <Typography variant="body2" color={emphasized ? 'warning.main' : 'text.primary'}>
                {t('Please remove the stone at {coord}', '请拿回 {coord} 处的棋子').replace('{coord}', coordLabel)}
              </Typography>
            </DialogContent>
            {/* M2(2026-07-11 登记):等待态原来一颗键都没有、点背景也关不掉,而解除条件是
                「识别盘面与数字盘面整盘一致连续 N 帧」—— 反光、手影、识别不到盘面时会一直挂住。
                给一个始终成立的出口:认输,走页面既有的确认流(与出错态同一个 handleResign,
                同样不自行关弹层 —— 确认之后由 GamePage 清掉)。 */}
            <DialogActions>
              <Button onClick={handleResign} color="error">
                {t('Resign', '认输')}
              </Button>
            </DialogActions>
          </>
        )}
```

- [ ] **Step 4: 改编排器**

`_run`（`:293-300`）

```python
    async def _run(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.config.tick_interval_s)
                if self._session_id is None:
                    continue
```

替换为

```python
    async def _run(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.config.tick_interval_s)
                if self._session_id is None:
                    continue
                # X10 / M4: 终局要先于两个恢复暂停被看见 —— 下面两支(awaiting_removal 分派、
                # `_suspended` 早退)都不看 end_result,放着不管灯会一直亮到离开对局页。
                try:
                    self._release_recovery_on_game_end()
                except Exception as e:  # defensive: LED problems must not kill the loop
                    logger.warning("physical-play game-end release error: %s", e)
```

在 `_complete_awaiting_removal` 方法之后（其 `broadcast_to_session(...)` 收尾、`@staticmethod def _guided_colors_from_state` 之前）插入：

```python
    def _release_recovery_on_game_end(self) -> bool:
        """X10 / M4:局已经结束,还挂着引擎出错 / 等待拿回的暂停 ⇒ 放掉并熄灯。

        终局之后这两个恢复流程都没有意义:没有下一手要重试,也没有下一手要等盘面对齐。
        放掉之后普通 tick 接手,它见 `end_result` 会保持熄灯(`_tick_once`)。hint 暂停不归这里
        (它有自己的超时)。返回是否放掉了。"""
        state = self._latest_state
        if not state or not state.get("end_result"):
            return False
        if (
            self.PAUSE_REASON_ENGINE_ERROR not in self._pause_reasons
            and self.PAUSE_REASON_AWAITING_REMOVAL not in self._pause_reasons
        ):
            return False
        self.clear_engine_error()
        self.clear_awaiting_removal()
        self._apply_points([])
        return True

```

- [ ] **Step 5: 跑测试、格式化、类型检查**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && uv run black -l 120 katrain/web/core/physical_play_orchestrator.py tests/test_physical_play_orchestrator.py && uv run pytest tests/test_physical_play_orchestrator.py tests/test_physical_play_recovery.py tests/test_engine_physical_integration.py -q
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run src/kiosk/__tests__/EngineMoveErrorDialog.test.tsx src/kiosk/__tests__/GamePageEngine.test.tsx && npx tsc -b
```
Expected: 全 PASS；`tsc -b` 退出 0。

- [ ] **Step 6: 变异验证（不提交）**

删掉 `_run` 里新加的 `self._release_recovery_on_game_end()` 那一行（连同 try/except），重跑 `uv run pytest tests/test_physical_play_orchestrator.py -q`，Expected：`test_run_loop_releases_engine_error_and_clears_lamps_when_the_game_ends` 红；还原后绿。

- [ ] **Step 7: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add katrain/web/ui/src/kiosk/components/physical/EngineMoveErrorDialog.tsx katrain/web/ui/src/kiosk/__tests__/EngineMoveErrorDialog.test.tsx katrain/web/core/physical_play_orchestrator.py tests/test_physical_play_orchestrator.py && git commit -m "$(cat <<'EOF'
fix(kiosk-physical-play): 等待拿回棋子的弹层给出口,终局时释放恢复暂停并熄灯

M2:星阵实体盘局网络出错后选「拿回棋子」,等待态没有任何按钮也关不掉,识别对不上就永远挂住。
加一颗「认输」,走页面既有确认流。
M4:engine_error / awaiting_removal 暂停会让 _run 跳过 _tick_once,而终局清灯只在那里 ⇒
恢复框里认输后灯一直亮到离开页面。每个 tick 先检查「已终局且挂着这两个暂停」→ 放掉并熄灯。
(2026-07-11 登记的 follow-up;M1/M3/I2 需上板,本次不动。)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: 收口闸 —— 两套构建、基线 diff、四图、给 Fan 的确认清单

**Files:**
- 重取：`superpowers/tracks/kiosk-go-shell-align/visual/01-play/1024x600/*`、`superpowers/tracks/kiosk-go-shell-align/visual/10-platform-game/1024x600/*`
- 无源码改动（若这里发现问题，回到对应 Task 修，别在本 Task 里顺手改）。

**Interfaces:**
- Consumes: Task 0 的 `${TMPDIR}/kgcp-vitest-before.txt`、`${TMPDIR}/kgcp-pytest-before.txt`；Task 7 的 `${TMPDIR}/kgcp-void-card.png`。
- Produces: 两屏四图存档；一份贴给 Fan 的确认清单（写在最终回报里，不落文件）。

- [ ] **Step 1: 类型检查、lint、两套构建**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx tsc -b && npm run build && npm run build:kiosk-2d
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx eslint src/kiosk/pages/GamePage.tsx src/kiosk/pages/PlayPage.tsx src/kiosk/pages/PlatformLobbyPage.tsx src/kiosk/components/game/GameControlPanel.tsx src/kiosk/components/report/reviewPresentation.ts src/kiosk/components/physical/EngineMoveErrorDialog.tsx
```
Expected: `tsc -b` 无输出；`npm run build` 成功；`npm run build:kiosk-2d` 成功且 `verify:kiosk-2d` 报 clean（exit 0）。
eslint **不是 0 error**：基线上这 6 个文件就报 `1 error, 4 warnings`——error 是 `PlayPage.tsx` 状态 effect 开头那句 `setPlatforms(defaultPlatforms())` 的 `react-hooks/set-state-in-effect`（改前在 `:49`，改后在 `:51`），4 条 warning 是 `GamePage.tsx` 既有的 `exhaustive-deps`（审查时在原树与改后树各跑一遍，两边都是 1 error / 4 warnings）。判据是**与基线同一组规则、同样条数，不许新增**；那条既有 error 不在本轮修（`npm run build` 不跑 lint，它不挡构建）。所以 eslint 单独一行跑，别用 `&&` 把构建串在它后面。

- [ ] **Step 2: 前端全量基线 diff**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx vitest run --reporter=verbose > "${TMPDIR:-/tmp}/kgcp-vitest-after.log" 2>&1; grep -E '^\s+×' "${TMPDIR:-/tmp}/kgcp-vitest-after.log" | sed -E 's/ [0-9]+ms$//' | sort -u > "${TMPDIR:-/tmp}/kgcp-vitest-after.txt"; echo '--- 新增失败 ---'; comm -13 "${TMPDIR:-/tmp}/kgcp-vitest-before.txt" "${TMPDIR:-/tmp}/kgcp-vitest-after.txt"
```
Expected: 「新增失败」下面为空。不为空时逐条看是不是本轮造的（进程级共享状态、mock 漏 `isAuthenticated`），回对应 Task 修；不许按「文件名看着无关」放过。

- [ ] **Step 3: 后端全量基线 diff**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && CI=true uv run pytest tests -q -rfE > "${TMPDIR:-/tmp}/kgcp-pytest-after.log" 2>&1; grep -E '^(FAILED|ERROR) ' "${TMPDIR:-/tmp}/kgcp-pytest-after.log" | sed -E 's/ - .*$//' | sort -u > "${TMPDIR:-/tmp}/kgcp-pytest-after.txt"; echo '--- 新增失败 ---'; comm -13 "${TMPDIR:-/tmp}/kgcp-pytest-before.txt" "${TMPDIR:-/tmp}/kgcp-pytest-after.txt"; uv run black -l 120 --check katrain/web/interface.py katrain/web/platforms/gateway.py katrain/web/core/physical_play_orchestrator.py tests/platforms/test_engine_game_ledger.py tests/test_vision_move_poller.py tests/test_physical_play_orchestrator.py tests/platforms/test_engine_gateway.py tests/platforms/test_engine_integration.py; uv run black -l 120 --diff katrain/web/server.py 2>/dev/null | grep '^@@'; git status --short katrain/config.json
```
Expected: 「新增失败」为空；black `--check` 全部 unchanged；`server.py` 的 `--diff` **恰好一个 hunk**，落在 `report_settlement_task` 那三行（基线就有，见 Task 5 Step 6），多出任何 hunk 都是本轮没格式化干净；`git status` 不显示 `katrain/config.json`——全量 pytest 里有测试会改写这份提交进仓库的配置，若显示 `M` 就 `git checkout -- katrain/config.json` 还原（Task 0 Step 4 跑完同样查一次），它不属于本轮改动。

- [ ] **Step 4: 真浏览器几何（屏 05 / 屏 10 同文件）**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui && npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-05-game.spec.ts
```
Expected: 全 PASS。

- [ ] **Step 5: 四图 —— 屏 01、屏 10 各跑两次**

Run:
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui
V=/Users/fan/Repositories/katrain-kiosk-go-cross-platform/superpowers/tracks/kiosk-go-shell-align/visual
for s in 01-play 10-platform-game; do
  npx playwright test --config=playwright.visual.config.ts "tests/kiosk-screen-${s%%-*}-"*.fourup.spec.ts 2>&1 | grep '\[fourup'
  rm -rf "${TMPDIR:-/tmp}/kgcp-run1-$s" && cp -R "$V/$s/1024x600" "${TMPDIR:-/tmp}/kgcp-run1-$s"
  npx playwright test --config=playwright.visual.config.ts "tests/kiosk-screen-${s%%-*}-"*.fourup.spec.ts 2>&1 | grep '\[fourup'
done
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git status --short superpowers/tracks/kiosk-go-shell-align/visual/
```
Expected: 两屏各打印两行 `[fourup …] both=… refOnly=… implOnly=…`；两次之间的差是本屏自己的抖动底（屏 10 约 4500 级，屏 01 约 200 级以内）。`git status` 显示两屏的 PNG 变了。

- [ ] **Step 6: 逐屏看四张图，判「内容变了」还是「只是抖动」**

用 Read 工具看每屏的 `--side-by-side.png` 与 `--diff.png`，并与提交前的实现图对照（`git show HEAD:superpowers/tracks/kiosk-go-shell-align/visual/<屏>/1024x600/<屏>--implementation.png > "${TMPDIR:-/tmp}/kgcp-old-<屏>.png"` 后 Read）。逐项记：构图 · 几何间距 · 组件层级 · 字体 / 色彩 · 图标 · 文案 · 状态语义。
Expected（写死的期望，先写再看）：
- 屏 01：**只有**野狐卡徽标文字由「即将上线」变「暂不能对弈」；徽标没有溢出卡片右缘、没有换行；其余像素差为散落抖动。
- 屏 10：动作区由三颗变**一颗横跨整行的「认输」**（描边 + `--bad` 字色，不是实心红）；开关排右端由「数子要下满 100 手」变「暂不支持停一手、数子」，一行放得下、不被截断；动作区仍贴右栏底；其余不变。
- 任何一屏若差异只有散落抖动（与第二次跑的差同量级、bbox 分散全图），`git checkout HEAD -- <该屏目录>` 还原，不提交。

- [ ] **Step 7: 提交四图（只提交内容真变了的屏，四张一起）**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-cross-platform && git add superpowers/tracks/kiosk-go-shell-align/visual/01-play/1024x600 superpowers/tracks/kiosk-go-shell-align/visual/10-platform-game/1024x600 && git commit -m "$(cat <<'EOF'
chore(kiosk-go): 重取屏 01 / 屏 10 四图 —— 野狐徽标文案、星阵局动作区只剩认输

屏 01 野狐卡徽标「即将上线」→「暂不能对弈」(与屏 07 同一个 key);屏 10 动作区撤掉停一手 / 数子,
开关排右端改写「暂不支持停一手、数子」。各跑两次取抖动底,只提交内容变化的屏。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 8: 回报给 Fan 的确认清单（不落文件，写进最终回报）**

逐条列出，等 Fan 明确确认；未确认前不得宣称视觉通过、不得合并：
1. 屏 01 四图：`superpowers/tracks/kiosk-go-shell-align/visual/01-play/1024x600/01-play--side-by-side.png`（野狐徽标文案）。
2. 屏 10 四图：`…/10-platform-game/1024x600/10-platform-game--side-by-side.png`——**一颗「认输」横跨动作区是否可接受**；不接受的备选是「停一手 / 数子留着但灰 + 同一句右端说明」（改 Task 4 Step 3 一处即可）。
3. 星阵 AI 无胜负终局卡：`${TMPDIR}/kgcp-void-card.png`（设计稿无此态，只有实现截图）；以及「以 `Void` 记无胜负」这条裁定本身（备选：记成人中盘胜）。
4. 上板清单（严格盒端构建部署到 RK3562 后，一次只跑一家）：
   - X7：星阵人机局角标出数字；按支招出候选圈；实体盘模式下支招白灯亮。
   - X8：连星阵后回屏 01，星阵卡绿点亮、写「已连接 · 人机对弈」，一步进人机开局。
   - N13：下一盘星阵人机并认输 → 屏 19 历史对局出现「vs [golaxy] …」、结果「你(黑)中盘负」，能送复盘；断网认输 → 本地有行、联网后同步上云。
   - X10-a：拔网线造出恢复框 → 拿回棋子 → 等待态认输 → 弹层关、终局卡出、盘上灯灭。
   - X9-b：观察项（需星阵 AI 真的停手 / 认输，无法按需触发）。

---

## Self-Review

**1. Spec 覆盖（prd §3 逐条）**

| PRD 条目 | 验收要点 | Task |
|---|---|---|
| X7 | 盒端两条请求照发；变异红；上板 | 1（上板在 9-Step 8） |
| X8 | 盒端拉状态、直达人机开局；登出夹具真形状；上板 | 2 |
| X1 | 野狐卡「暂不能对弈」；屏 01 四图 | 2、9 |
| X4-a | 确认框 + toast 含「不会回到这台盒子」 | 3 |
| X9-a | 面板无停一手 / 数子、`.ghint` 说明；屏 05 spec 屏 10 用例；屏 10 四图 | 4、9 |
| X9-b | 真栈 `Void`；`/api/move` 200 / 409 正对照；终局卡说明行；上板观察 | 5、7、9 |
| N13 | resign / move / 视觉三处落账；OGS 正对照；helper 名字与 source；真 `_RECORD_FN` 写入；`Void` 念成人话；上板 | 6、7、9 |
| X10-a | 等待态认输；编排器循环级释放 + 熄灯；未终局不释放；上板 | 8、9 |

prd §4 待拍板（X11 / X4 主体 / X6 / X2）与 §5 不在本轮的条目**没有任务**，符合 PRD。

**2. 占位扫描**：全文无 TBD / TODO / 「类似 Task N」；每个改代码的步骤都给了替换前后的完整片段；每条测试写全。

**3. 类型 / 命名一致性**：
- `end_without_result`（interface 命令，Task 5）↔ gateway 调用 `session.katrain("end_without_result")`（Task 5）↔ 测试断言 `commands[-1] == "end_without_result"`（Task 5）。
- `_record_platform_engine_game(app, session, user)`（Task 6 定义）↔ 三处调用参数顺序一致 ↔ 测试 `recorder.await_args.args[1] is session`、`args[2]` 是用户（Task 6）。
- `_record_ai_game(..., data_overrides=None)` ↔ helper 以关键字 `data_overrides=` 传（Task 6）↔ 测试读 `record.await_args.kwargs["data_overrides"]`。
- `_session_owner(app, session)` ↔ 视觉路径调用 ↔ 测试 `owner.id / owner.username`。
- `_release_recovery_on_game_end()`（Task 8）↔ `_run` 调用 ↔ 测试方法名一致。
- 前端 key：`platform:no_play_yet`（Task 2，复用屏 07）、`platform:challenge_sent` / `platform:challenge_ask_tail`（Task 3，改默认文案）、`game:golaxy_no_pass_count`（Task 4）、`game:engine_ended_no_result`（Task 7）、`review:no_result_line`（Task 7）——都不进 PO。
- `data-testid="endgame-no-result"`（Task 7 实现）↔ 单测与预览 spec 同名。
