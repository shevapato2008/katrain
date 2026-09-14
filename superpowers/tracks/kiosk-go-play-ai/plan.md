# 围棋 kiosk · 对弈·AI/升降级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让盒上一局棋从开局到结束胜负判对、记进账、结算得了,屏上说的每一句话都是真的(PRD §3 的 11 组条目)。

**Architecture:** 先修后端判胜负与收尾(`interface.py` 认输方 / 数子门槛 / 补分,`core/ai.py` 终局后不落子,
`server.py` 一个共用的终局收尾函数 + `session.py` 在请求之外结束对局时调用它),再修前端对局屏(加载失败出口、数子在途与原因、
玩家卡倒计时、右栏按对局类型、实体盘降级、错误条),最后是开局设置的策略 id 与升降级 503 分原因。
升降级的账本与结算逻辑一行不改,只给它补调用方;升降级局的终局判目等 Fan 拍板,不进本计划。

**Tech Stack:** Python 3.13 / FastAPI / pytest + pytest-asyncio;React 19 + TypeScript + Vite / vitest + Testing Library / Playwright(真浏览器 1024×600)。

**Spec:** `superpowers/tracks/kiosk-go-play-ai/prd.md`(本计划只覆盖其 §3「本轮做」;§4 待拍板的一概不做)

## Global Constraints

> **开工前先读 `prd.md` §6.0**：五条赛道的共享文件归属与合并顺序（尤其 `server.py` 终局落账只留一条入口）。与本 plan 冲突时以 §6.0 为准。

- 在 worktree `/Users/fan/Repositories/katrain-kiosk-go-play-ai`(分支 `feature/kiosk-go-play-ai`)里开发;**不 push、不合并 develop**,合并由 Fan 决定;**不在别的 worktree 里 checkout**。所有命令用绝对路径或先 `cd` 到本 worktree。
- 环境(2026-09-14 实测):本 worktree 的 `.venv` 没有 fastapi、`katrain/web/ui` 没有 `node_modules`。Task 0 先 `uv sync --extra web` 与 `npm ci`,不要借用主仓的环境跑本仓代码。
- 改了共享领地(`src/components`、`src/hooks`、`src/api.ts` + `src/api/`、`src/features`、`src/context`、`src/utils`、`src/types`)必须 `npm run build` 与 `npm run build:kiosk-2d` 都绿;kiosk 边界(`npm run verify:kiosk-2d`,已串在 `build:kiosk-2d` 里)不许破。共享文件不许 import `src/kiosk`/`src/galaxy`/`src/pages`。
- 类型检查用 `npx tsc -b`(`npx tsc --noEmit` 检查 0 个文件);`*.test.ts(x)` 不在 tsc 范围内,测试文件的类型错不会红。
- 盒上 token 恒为 null:任何「发不发请求 / 渲不渲染」的判别位用 `isAuthenticated`(或服务端下发的 `analysis_delivered` 等字段),不用 `token`。
- 新文案一律 `t('ns:key', '中文默认')`;**不往 PO 里加 key**(补不补 PO 待 Fan 裁定)。
- 格式化:Python `uv run black -l 120 <改到的 .py>`(⚠️ `katrain/web/server.py` 基线就有一处 black 不合规 —— `:341-343` 那个 `asyncio.create_task(_report_settlement_loop(...))` 三行;black 会顺手把它压成一行。提交前 `git diff katrain/web/server.py` 看到这一处就还原,不夹带:另外四条赛道也在改 server.py);前端 `npx eslint <改到的文件>` 不新增 error(基线已有的不算)。
- 前端单测:`cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui && npx vitest run <文件>`;后端:`cd /Users/fan/Repositories/katrain-kiosk-go-play-ai && CI=true uv run pytest <文件> -q`。
- **测试判据是基线 diff**:Task 0 在干净树上记录失败用例名字集合;每个 Task 结束比名字集合(`comm -13 基线 本次`),不比条数。报告里写「新增失败 = 空」。
- **真 `WebKaTrain` 的后端测试放 `tests/` 根目录**:`tests/web_ui/conftest.py:90` 把 `sys.modules["katrain.web.interface"]` 整个换成 MagicMock,放进 `tests/web_ui/` 就只是在测替身(`tests/web_ui/test_count_api.py` 的 `TestIntegration` 就是这样恒绿的)。这类测试文件首个用例断言拿到的是真类。
- **单跑时 `tests/test_play_ai_endgame.py` 不许和任何 `tests/web_ui/…` 文件放进同一条 pytest 命令**:参数里只要有一个 `tests/web_ui/` 下的文件,pytest 在**收集任何模块之前**就加载 `tests/web_ui/conftest.py`(initial conftest),`sys.modules["katrain.web.interface"]` 当场变成 MagicMock,根目录文件的 `from katrain.web.interface import WebKaTrain` 拿到的就是替身 —— 首条「真类」用例红,其余结论全不作数(2026-09-14 审查时用玩具目录复现)。本计划里凡是两者同跑的地方都已拆成两条命令;全量 `pytest tests` 不受影响(按名字排序,根目录的 `test_play_ai_endgame.py` 先于 `web_ui/` 被收集)。
- 跑完任何后端测试查 `git -C /Users/fan/Repositories/katrain-kiosk-go-play-ai status --short katrain/config.json` 为空 —— `force_package_config=True` 的实例会把仓里的 `katrain/config.json` 写回去。
- **Playwright e2e 打的是构建产物**(`playwright.config.ts` 起 `python -m katrain --ui=web --port 8002` 服务 `katrain/web/static`):改源码后先 `npm run build` 再跑。跑前 `lsof -nP -iTCP:8002 -sTCP:LISTEN`(四图用 `:5173`),端口若被**别的 worktree** 的进程占着(`lsof -p <PID> | grep cwd` 看目录),`reuseExistingServer` 会让你测到别人的包 —— 等它结束或与对方协调,不要杀别人的进程。`--ui web` 退出时会改 `~/.katrain/config.json`:跑 e2e 前 `cp ~/.katrain/config.json /tmp/kgpa-katrain-config.json`,跑完拷回。
- 视觉/布局改动走 CLAUDE.md 的四图对比与承重实测关卡:`npm run fourup` 重跑被改到的屏,跑两次 diff 两次结果得本屏抖动地板,只提交有内容变化的屏(`git checkout HEAD -- <屏目录>` 前先确认没有未提交的活);jsdom 不作布局证据;**视觉通过需 Fan 确认**,确认前不算完成。
- 升降级账本:`katrain/web/core/ai_ladder_ranked.py` 与 `ai_ladder_catalog.py` 本计划**一行不改**;升降级局不补分析(`analysis_allowed` 为假时一律不补)。
- 新建文件前先 `git ls-files <路径>` 与 `ls <路径>` 确认不存在,不用 `cat >` 覆盖既有文件;zsh 不做词分割,循环文件列表用数组或逐个写。
- 每个 Task 一次提交,提交信息结尾带 `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`;提交前 `git add` 明确列文件后用 `git diff --cached --stat` 确认(仓里 `.gitignore` 有 `log*`,macOS 大小写不敏感,新文件可能被静默吞掉)。

## File Structure

| 文件 | 职责 | Task |
|---|---|---|
| `katrain/core/ai.py` | `generate_ai_move` 落子前若对局已有终局结果则不落 | 2 |
| `katrain/web/interface.py` | `_do_resign(loser)`、`count_min_moves()`、`ensure_current_score()`、`game_ended_callback`(AI 线程收尾时调)、`timer_configured` | 2、3、4、5、6 |
| `katrain/web/server.py` | `/api/resign` 多人局传认输方;`/api/count/request` 用新门槛并先补分;`_apply_counted_result` / `_score_two_pass_end` / `_finish_ended_game` / 装钩子;`/api/move` 自然终局改走收尾函数 | 2、3、4、5 |
| `katrain/web/session.py` | `WebSession.end_game_lock`;`SessionManager.on_game_ended`、`_on_game_ended`,`create_session` 装 `game_ended_callback`(`_on_state` 不动) | 5 |
| `katrain/web/ui/src/kiosk/pages/GamePage.tsx` | 加载失败出口、认输框写明哪一方、数子在途与原因、超时回调、按需分析条件、实体盘降级、错误条 | 1、2、4、6、9、10、11 |
| `katrain/web/ui/src/kiosk/components/game/goClock.ts`(新) | 计时读数纯函数 + `useGoClock` | 6 |
| `katrain/web/ui/src/kiosk/components/game/gameKinds.ts`(新) | `isFreeVsAi` —— 胜率块/悔棋/按需分析共用的对局类型判别 | 9 |
| `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx` | 玩家卡时钟、升降级撤分析键、非胜率局显示棋谱 | 6、9 |
| `katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx` | 策略 id 与说明;升降级开局 503 分原因 | 7、8 |
| `katrain/web/ui/src/features/aiLadder/startErrors.ts`(新)、`useAiLadderStatus.ts`(`copy.ts` 不改) | 升降级 503 按 detail 分原因(共享领地) | 8 |
| `katrain/web/ui/src/kiosk/components/physical/PhysicalSyncEscalationDialog.tsx`、`components/game/RecalibrationModal.tsx`、`components/vision/VisionSyncOverlay.tsx` | 降级回调与文案 | 10 |
| `katrain/web/ui/src/hooks/useGameSession.ts` | `connectionLost`、`clearError`(共享领地,纯增量) | 11 |
| `katrain/web/ui/src/api.ts` | `GameState.timer.configured?: boolean`(共享领地,纯类型) | 6 |
| 测试(全部新建) | `tests/test_play_ai_endgame.py`、`tests/core/test_ai_commit_after_end.py`、`tests/web_ui/test_game_end_hook.py`、`tests/web_ui/test_play_ai_endgame_api.py`、`src/kiosk/pages/GamePage.playAi.test.tsx`、`src/kiosk/components/game/goClock.test.ts`、`src/kiosk/components/game/GameControlPanel.playAi.test.tsx`、`src/features/aiLadder/startErrors.test.ts`、`src/hooks/useGameSession.connection.test.tsx`、`tests/kiosk-screen-05-play-ai.spec.ts` | 各 Task |

阶段:**Phase 1(P0/P1)= Task 0–8**,**Phase 2(P2/P3)= Task 9–11**,Task 12 收尾验证。依赖:1 独立;2 → 3 → 4 → 5(同改 `server.py`/`interface.py`,顺序做);6 依赖 2;7、8 独立;9 依赖 6(同改 `GameControlPanel.tsx`);10、11 依赖 1(同改 `GamePage.tsx`)。

---

### Task 0: 环境与基线

**Files:**
- 无源码改动;基线输出写 `/tmp/kgpa-baseline/`

**Interfaces:**
- Consumes: 无
- Produces: `/tmp/kgpa-baseline/pytest-failed.txt`、`/tmp/kgpa-baseline/vitest-failed.txt`(失败用例名,每行一个,已排序去重),后续每个 Task 用它做 `comm -13`

- [ ] **Step 1: 装环境**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git status --short            # 期望:只有 `?? superpowers/tracks/kiosk-go-play-ai/`(本赛道 prd/plan,尚未提交);除此之外不空就停下来问,不要清
git rev-parse HEAD            # 记下来,期望 6f7dc629… 或本分支后续提交
uv sync --extra web
cd katrain/web/ui && npm ci
```
Expected: 两条安装都成功;`uv run python -c "import fastapi"` 不报错。

- [ ] **Step 2: 后端基线**

```bash
mkdir -p /tmp/kgpa-baseline
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git status --short katrain/config.json   # 期望:空
CI=true uv run pytest tests -q -rfE -p no:cacheprovider 2>&1 | tee /tmp/kgpa-baseline/pytest.log
grep -E '^(FAILED|ERROR) ' /tmp/kgpa-baseline/pytest.log | sed -E 's/ - .*//' | sort -u > /tmp/kgpa-baseline/pytest-failed.txt
wc -l /tmp/kgpa-baseline/pytest-failed.txt
git status --short katrain/config.json   # 期望:空;不空就 `git diff katrain/config.json` 看是哪条测试写的,记进报告后 `git checkout -- katrain/config.json`
```
Expected: 跑完(失败条数不重要,名字集合才是判据)。

- [ ] **Step 3: 前端基线**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npx vitest run --reporter=verbose 2>&1 | tee /tmp/kgpa-baseline/vitest.log
grep -E '^\s+×' /tmp/kgpa-baseline/vitest.log | sed -E 's/^\s+×\s+//; s/ [0-9]+ms$//' | sort -u > /tmp/kgpa-baseline/vitest-failed.txt
wc -l /tmp/kgpa-baseline/vitest-failed.txt
npx tsc -b && echo TSC_OK
```
Expected: `TSC_OK`;若 tsc 在干净树上就红,把输出存 `/tmp/kgpa-baseline/tsc.log` 并在报告里说明,后续 Task 以「不新增 tsc 错误」为准。

- [ ] **Step 4: 不提交**(本 Task 没有源码改动)

每个后续 Task 的「基线 diff」一步统一这样做(以后端为例,前端把文件名换成 vitest):

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
CI=true uv run pytest tests -q -rfE -p no:cacheprovider 2>&1 | tee /tmp/kgpa-now-pytest.log
grep -E '^(FAILED|ERROR) ' /tmp/kgpa-now-pytest.log | sed -E 's/ - .*//' | sort -u > /tmp/kgpa-now-pytest-failed.txt
comm -13 /tmp/kgpa-baseline/pytest-failed.txt /tmp/kgpa-now-pytest-failed.txt   # 期望:无输出
```

---

## Phase 1 · P0 / P1

### Task 1: N17 对局屏取状态失败时给出口(P0)

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`(`activeSession` 那个 effect 之后加一个 effect;`:352-357` 早退分支整段替换)
- Create: `katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx`(本赛道 GamePage 行为测试的共用测试文件,后续 Task 往里追加 `describe`)

**Interfaces:**
- Consumes: `useGameSession()` 已有返回值 `gameState`、`error`;`clearActiveSession(kind)`(`kiosk/utils/activeSession.ts`)
- Produces: 对局屏两种早退态 —— `data-testid="game-loading"`(转圈 + 「回到对弈」)与 `data-testid="game-unavailable"`(标题「这一局已经打不开了」+ 原因句 + 「回到对弈」);测试文件导出的桩对象 `sessionMock` / `vision` / `makeState` 形状供 Task 2/4/6/9/10/11 复用(同文件内)

- [ ] **Step 1: 写失败的测试(新建测试文件,含本赛道共用的桩)**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
git ls-files src/kiosk/pages/GamePage.playAi.test.tsx; ls src/kiosk/pages/GamePage.playAi.test.tsx   # 期望:都没有
```

`katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import { API, type GameState } from '../../api';
import GamePage from './GamePage';

/**
 * 对弈·AI/升降级赛道(superpowers/tracks/kiosk-go-play-ai)的 GamePage 行为测试。
 * 只证行为与文案(jsdom 没有布局引擎);右栏几何在 tests/kiosk-screen-05-play-ai.spec.ts 里用真浏览器量。
 * 身份按盒上口径桩:`token: null`、`isAuthenticated: true`。
 */

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: null, isAuthenticated: true, user: { id: 1, username: 'box-user' } }),
}));
vi.mock('../../components/Board', () => ({ default: () => <div data-testid="board" /> }));

interface MockPanelProps { onAction: (a: string) => void; onTimeout?: (c: 'B' | 'W') => void }
vi.mock('../components/game/GameControlPanel', () => ({
  default: (p: MockPanelProps) => (
    <div data-testid="game-control-panel">
      <button onClick={() => p.onAction('resign')}>MOCK_RESIGN</button>
      <button onClick={() => p.onAction('count')}>MOCK_COUNT</button>
      <button onClick={() => p.onTimeout?.('B')}>MOCK_TIMEOUT_B</button>
    </div>
  ),
}));

const { clearActiveSession, writeActiveSession } = vi.hoisted(() => ({
  clearActiveSession: vi.fn(),
  writeActiveSession: vi.fn(),
}));
vi.mock('../utils/activeSession', () => ({ clearActiveSession, writeActiveSession }));
vi.mock('../../api/geometryApi', () => ({ GeometryAPI: { calibrate: vi.fn().mockResolvedValue({}) } }));
vi.mock('../../features/aiLadder/api', () => ({ getAiLadderStatus: vi.fn() }));

const vision = vi.hoisted(() => ({ enabled: false, poseLocked: true }));
vi.mock('../context/VisionContext', () => ({
  useVision: () => ({
    visionStatus: {
      enabled: vision.enabled, cameraConnected: true, poseLocked: vision.poseLocked,
      syncState: 'idle', boundSessionId: null, ledConnected: null,
    },
    isVisionEnabled: vision.enabled,
    refreshStatus: vi.fn(),
  }),
}));
vi.mock('../hooks/useVisionSync', () => ({
  useVisionSync: () => ({ syncEvents: [], latestEvent: null, setupProgress: null, isSetupComplete: false }),
}));

const sessionMock = vi.hoisted(() => ({
  gameState: null as unknown,
  error: null as string | null,
  connectionLost: null as 'rejected' | 'dropped' | null,
  physicalReminder: null as unknown,
  handleAction: vi.fn(),
  setGameState: vi.fn(),
  clearError: vi.fn(),
}));
vi.mock('../../hooks/useGameSession', () => ({
  useGameSession: () => ({
    sessionId: 'play-ai-s1',
    setSessionId: vi.fn(),
    gameState: sessionMock.gameState,
    setGameState: sessionMock.setGameState,
    error: sessionMock.error,
    connectionLost: sessionMock.connectionLost,
    clearError: sessionMock.clearError,
    onMove: vi.fn().mockResolvedValue(undefined),
    onNavigate: vi.fn(),
    handleAction: sessionMock.handleAction,
    physicalReminder: sessionMock.physicalReminder,
    physicalEngineError: null,
    clearPhysicalEngineError: vi.fn(),
    awaitingRemovalReminder: null,
  }),
}));

const seat = (type: string, name: string) => ({
  player_type: type, player_subtype: '', name, calculated_rank: null, periods_used: 0, main_time_used: 0,
});

const makeState = (over: Partial<GameState> = {}): GameState => ({
  game_id: 'g', board_size: [19, 19], komi: 7.5, handicap: 0, ruleset: 'chinese',
  current_node_id: 5, current_node_index: 5, history: [], player_to_move: 'B', stones: [], last_move: null,
  prisoner_count: { B: 0, W: 0 }, analysis: null, commentary: '', is_root: false, is_pass: false, end_result: null,
  children: [], ghost_stones: [], note: '', language: 'cn', game_type: 'free', count_min_moves: 100,
  ui_state: {
    show_children: false, show_dots: false, show_hints: false, show_policy: false,
    show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false,
  },
  players_info: { B: seat('player:human', '我'), W: seat('player:ai', 'KataGo') },
  ...over,
} as GameState);

// 单独拎出来,是为了 `rerender(pageTree())` 能用同一棵树:改完桩的值再重渲,组件身份不变。
const pageTree = () => (
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter initialEntries={['/kiosk/play/ai/game/play-ai-s1']}>
      <Routes>
        <Route path="/kiosk/play/ai/game/:sessionId" element={<GamePage />} />
        <Route path="/kiosk/play" element={<div>PLAY_PAGE</div>} />
      </Routes>
    </MemoryRouter>
  </ThemeProvider>
);

const renderPage = () => render(pageTree());

beforeEach(() => {
  vi.clearAllMocks();
  sessionMock.gameState = null;
  sessionMock.error = null;
  sessionMock.connectionLost = null;
  sessionMock.physicalReminder = null;
  vision.enabled = false;
  vision.poseLocked = true;
  sessionStorage.clear();
  sessionMock.handleAction.mockResolvedValue(undefined);
  vi.spyOn(API, 'hintDismiss').mockResolvedValue({ ok: true });
});

describe('N17 · 取状态失败时对局屏给出口', () => {
  it('状态还没回来:转圈旁边就有「回到对弈」', () => {
    renderPage();
    expect(screen.getByTestId('game-loading')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '回到对弈' }));
    expect(screen.getByText('PLAY_PAGE')).toBeInTheDocument();
  });

  it('取状态失败:说清打不开、清掉「继续上一局」、给「回到对弈」', async () => {
    sessionMock.error = 'Failed to connect to game';
    renderPage();
    expect(screen.getByTestId('game-unavailable')).toBeInTheDocument();
    expect(screen.getByText('这一局已经打不开了')).toBeInTheDocument();
    await waitFor(() => expect(clearActiveSession).toHaveBeenCalledWith('game'));
    fireEvent.click(screen.getByRole('button', { name: '回到对弈' }));
    expect(screen.getByText('PLAY_PAGE')).toBeInTheDocument();
  });

  it('局面已经在屏上时,连接类错误不会把整屏换成「打不开」', () => {
    sessionMock.gameState = makeState();
    sessionMock.error = '实时连接已断开，棋盘不会自动更新，请刷新页面';
    renderPage();
    expect(screen.queryByTestId('game-unavailable')).toBeNull();
    expect(clearActiveSession).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui && npx vitest run src/kiosk/pages/GamePage.playAi.test.tsx`
Expected: 前两条 FAIL(找不到 `game-loading` / `game-unavailable`),第三条 PASS。

- [ ] **Step 3: 实现**

在 `GamePage.tsx` 里 `activeSession write-on-load / clear-on-end` 那个 `useEffect`(`:227-238`)之后插入:

```tsx
  // N17:取状态失败 = 这一局在服务端已经不在了(盒子重启、闲置超过 1 小时被回收),
  // 或者它不属于当前账号。「继续上一局」那个指针再留着,只会把人一次次领回这块打不开的屏。
  // 判据是「没有局面 **且** 有错」:局面到过之后的错(WS 断开)不在这里处理。
  const loadFailed = !session.gameState && !!session.error;
  useEffect(() => {
    if (loadFailed) clearActiveSession('game');
  }, [loadFailed]);
```

把早退分支(`if (!session.gameState) { return (<Box …><CircularProgress /></Box>); }`)整段替换为:

```tsx
  if (!session.gameState) {
    // N17:早退分支上没有页控条、没有 Dock、没有主页键 —— 这里不给出口,盒上就是一块死页
    // (全屏 chromium 没有地址栏,也没有后退手势)。转圈时也给,因为取状态可能一直不回来。
    return (
      <Box
        data-testid={loadFailed ? 'game-unavailable' : 'game-loading'}
        sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              gap: 2, height: '100%', px: 4, textAlign: 'center' }}
      >
        {loadFailed ? (
          <>
            <Typography sx={{ color: 'text.primary', fontSize: 18, fontWeight: 600 }}>
              {t('game:unavailable_title', '这一局已经打不开了')}
            </Typography>
            <Typography sx={{ color: 'text.secondary', fontSize: 14, maxWidth: 520 }}>
              {t('game:unavailable_reason', '可能是盒子重启过、这一局闲置太久被清理，或者它属于另一个账号。')}
            </Typography>
          </>
        ) : (
          <CircularProgress />
        )}
        <button type="button" className="kiosk-btn kiosk-btn--secondary" onClick={() => navigate('/kiosk/play')}>
          {t('game:back_to_play', '回到对弈')}
        </button>
      </Box>
    );
  }
```

- [ ] **Step 4: 跑测试确认通过 + 类型 + lint**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npx vitest run src/kiosk/pages/GamePage.playAi.test.tsx src/kiosk/pages/GamePage.test.tsx src/kiosk/__tests__/GamePageEngine.test.tsx
npx tsc -b && echo TSC_OK
npx eslint src/kiosk/pages/GamePage.tsx
```
Expected: 三个文件全 PASS;`TSC_OK`;eslint 只有基线就有的 warning,无新增 error。

- [ ] **Step 5: 真实运行时看一眼(一张图,不做四图 —— 稿子没有这一态)**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
lsof -nP -iTCP:5173 -sTCP:LISTEN   # 被别的 worktree 占着就换个时间,不要杀
npm run dev -- --host 127.0.0.1 --port 5173
```
另开终端用 `/browse`(gstack)打开 `http://127.0.0.1:5173/kiosk/play/ai/game/does-not-exist`,viewport 1024×600,截图存
`/Users/fan/Repositories/katrain-kiosk-go-play-ai/superpowers/tracks/kiosk-go-play-ai/visual/n17-game-unavailable-1024x600.png`。
Expected: 屏上是标题 + 原因句 + 「回到对弈」按钮,按钮可见不被裁;点按钮到对弈首页。截图交 Fan 确认。

- [ ] **Step 6: 基线 diff(前端)后提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git add katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx superpowers/tracks/kiosk-go-play-ai/visual/n17-game-unavailable-1024x600.png
git diff --cached --stat
git commit -m "fix(kiosk): 对局屏取状态失败时整屏转圈没有出口 —— 给「回到对弈」并清掉失效的「继续上一局」

N17(P0)。盒上 katrain 重启或会话闲置被回收后,「继续上一局」领进来的是一块只有转圈的死页。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: N21 认输判错方;终局之后 AI 着法不再落下

**Files:**
- Modify: `katrain/web/interface.py:1464-1465`(`_do_resign`)
- Modify: `katrain/core/ai.py:1974-1981`(`generate_ai_move` 的落子段)+ 在 `_ladder_remote_terminal`(`:1849-1850`)旁边加 `_game_already_ended`
- Modify: `katrain/web/server.py:1917-1918`(`/api/resign` 非升降级分支的 `session.katrain("resign")`)
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`(两个确认框的 `DialogTitle`)
- Create: `tests/test_play_ai_endgame.py`、`tests/core/test_ai_commit_after_end.py`、`tests/web_ui/test_play_ai_endgame_api.py`
- Test: `katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx`(追加)

**Interfaces:**
- Consumes: 无
- Produces: `WebKaTrain._do_resign(self, loser: Optional[str] = None) -> None`(`"B"`/`"W"` 为认输方,`None` 时由座位推);
  `katrain.core.ai._game_already_ended(game) -> bool`;测试文件 `tests/test_play_ai_endgame.py` 的 `_web_katrain()` / `_seat()` 与
  `tests/web_ui/test_play_ai_endgame_api.py` 的 `client` / `_make_user` / `_login` / `_inject_session` 供 Task 3/4/5/6 追加用例

- [ ] **Step 1: 写失败的后端测试**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
for f in tests/test_play_ai_endgame.py tests/core/test_ai_commit_after_end.py tests/web_ui/test_play_ai_endgame_api.py; do git ls-files "$f"; ls "$f" 2>/dev/null; done   # 期望:无输出
```

`tests/test_play_ai_endgame.py`:

```python
"""对弈·AI/升降级赛道:终局判定在**真** WebKaTrain 上的行为(superpowers/tracks/kiosk-go-play-ai)。

⚠️ 放在 tests/ 根目录是有意的:`tests/web_ui/conftest.py` 会把 `katrain.web.interface` 整个换成
MagicMock,放进那个目录就只是在测替身。第一条用例先证明拿到的是真类。
"""

# 主线程先把 kivymd 的窗口单例暖起来 —— 理由同 tests/test_local_play_setup.py 顶部那段。
import kivymd.app  # noqa: F401

import pytest

from katrain.core.constants import AI_DEFAULT, PLAYER_AI, PLAYER_HUMAN
from katrain.core.sgf_parser import Move
from katrain.web.interface import WebKaTrain


def _web_katrain():
    w = WebKaTrain(force_package_config=True, enable_engine=False)
    # force_package_config=True 时 save_config 会写回仓里的 katrain/config.json(update_config 末尾就调它)
    w.save_config = lambda *args, **kwargs: None
    w.start()
    return w


def _seat(w, human_colors):
    """直接改座位,不走 `w("update_player")`:那条路会 update_state,轮到 AI 时起一条后台线程,
    活得比用例长(见 tests/test_guest_free_play.py `_seat_two_humans` 的说明)。"""
    for bw in ("B", "W"):
        if bw in human_colors:
            w.players_info[bw].update(player_type=PLAYER_HUMAN)
        else:
            w.players_info[bw].update(player_type=PLAYER_AI, player_subtype=AI_DEFAULT)


def test_this_module_runs_against_the_real_interface():
    assert isinstance(WebKaTrain, type)
    assert WebKaTrain.__module__ == "katrain.web.interface"


# ---------------------------------------------------------------- N21 认输方


def test_resigning_while_the_ai_is_thinking_is_a_loss_for_the_human():
    w = _web_katrain()
    _seat(w, human_colors={"B"})
    w.game.play(Move(coords=(3, 3), player="B"))  # 人刚落子,轮到 AI(白)在算
    assert w.game.current_node.next_player == "W"
    w._do_resign()
    assert w.game.current_node.end_state == "W+R"


def test_resigning_on_the_humans_own_turn_is_still_a_loss_for_the_human():
    w = _web_katrain()
    _seat(w, human_colors={"W"})
    w.game.play(Move(coords=(3, 3), player="B"))  # AI(黑)已落子,轮到人(白)
    w._do_resign()
    assert w.game.current_node.end_state == "B+R"


def test_two_humans_face_to_face_the_side_to_move_resigns():
    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    w.game.play(Move(coords=(3, 3), player="B"))  # 轮到白
    w._do_resign()
    assert w.game.current_node.end_state == "B+R"


def test_an_explicit_loser_wins_over_the_seats():
    w = _web_katrain()
    _seat(w, human_colors={"B"})
    w.game.play(Move(coords=(3, 3), player="B"))
    w._do_resign("W")  # 多人局由 /api/resign 按请求者座位显式传
    assert w.game.current_node.end_state == "B+R"
```

`tests/core/test_ai_commit_after_end.py`:

```python
"""N21:对局一旦有了终局结果,后台还在算的 AI 着法不许再落到盘上。

人刚落子、AI 在算时按认输(或超时),结果写在 AI 开算时的那个节点上;从前 AI 算完照常 `game.play(move)`,
新节点没有终局标记,盘面回到对局中。
"""

from katrain.core import ai
from katrain.core.constants import AI_LADDER
from katrain.core.sgf_parser import Move


class _Node:
    def __init__(self):
        self.player, self.next_player = "B", "W"
        self.end_state = None
        self.depth = 0


class _Katrain:
    ai_ladder_remote_ended = False
    ai_ladder_commit_lock = None

    def log(self, *a, **k):
        pass

    def config(self, *a, **k):
        return {}


class _Game:
    def __init__(self):
        self.board_size = (19, 19)
        self.current_node = _Node()
        self.katrain = _Katrain()
        self.played = []

    def play(self, move):
        self.played.append(move)
        self.current_node = _Node()
        return self.current_node


def _ends_mid_generation(end_state):
    class _EndsMidGeneration(ai.AIStrategy):
        def generate_move(self):
            self.game.current_node.end_state = end_state  # 人在这段时间里认输/超时了
            return Move(coords=(3, 3), player="W"), "thought"

    return _EndsMidGeneration


def test_a_move_finished_after_the_game_ended_is_not_played(monkeypatch):
    monkeypatch.setitem(ai.STRATEGY_REGISTRY, "test:ends-mid-generation", _ends_mid_generation("W+R"))
    game = _Game()
    assert ai.generate_ai_move(game, "test:ends-mid-generation", {}) is None
    assert game.played == []
    assert game.current_node.end_state == "W+R"


def test_the_ladder_commit_path_refuses_too(monkeypatch):
    monkeypatch.setitem(ai.STRATEGY_REGISTRY, AI_LADDER, _ends_mid_generation("B+R"))
    game = _Game()
    assert ai.generate_ai_move(game, AI_LADDER, {}) is None
    assert game.played == []


def test_an_ordinary_move_is_still_played(monkeypatch):
    """正对照:没有终局时照常落子 —— 否则上面两条的 None 可能只是这条路本来就不通。"""

    class _Plain(ai.AIStrategy):
        def generate_move(self):
            return Move(coords=(3, 3), player="W"), "thought"

    monkeypatch.setitem(ai.STRATEGY_REGISTRY, "test:plain", _Plain)
    game = _Game()
    assert ai.generate_ai_move(game, "test:plain", {}) is not None
    assert len(game.played) == 1
```

`tests/web_ui/test_play_ai_endgame_api.py`:

```python
"""对弈·AI/升降级赛道的 HTTP 端点测试(superpowers/tracks/kiosk-go-play-ai)。

会话一律手工注入、katrain 是 MagicMock(`tests/web_ui/conftest.py` 把 interface 换成了替身):
这里证的是**端点把什么交给了 katrain、按什么顺序**;katrain 自己怎么判在 tests/test_play_ai_endgame.py 用真类证。
"""

import threading
import uuid
from unittest.mock import MagicMock

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from katrain.web.server import create_app


@pytest.fixture
def client(isolated_session_factory):
    app = create_app(enable_engine=False)
    app.state.session_factory = isolated_session_factory  # 必须在 TestClient 之前:lifespan 用它重建全部 repo
    with TestClient(app) as c:
        yield c
        for s in list(c.app.state.session_manager._sessions.values()):
            c.app.state.session_manager._sessions.pop(s.session_id, None)


def _make_user(client, name: str):
    from passlib.context import CryptContext

    unique = f"{name}-{uuid.uuid4().hex[:8]}"
    hashed = CryptContext(schemes=["bcrypt"], deprecated="auto").hash("password")
    user = client.app.state.user_repo.create_user(unique, hashed)
    return user["id"], unique


def _login(client, username: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": "password"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _inject_session(client, *, user_id=None, player_b_id=None, player_w_id=None, game_type="free"):
    session = MagicMock()
    session.session_id = uuid.uuid4().hex
    session.user_id = user_id
    session.player_b_id = player_b_id
    session.player_w_id = player_w_id
    session.mode = "play"
    session.game_type = game_type
    session.lock = threading.Lock()
    session.sockets = set()
    session.last_access = 0.0
    session.last_state = {"end_result": None}
    session.pending_count_request = None
    session.pending_count_timestamp = None
    session.game_ended = False
    session._recorded = False

    katrain = MagicMock()
    katrain.game_type = game_type
    katrain.get_sgf.return_value = "(;FF[4]SZ[19];B[pd])"
    katrain.get_state.return_value = {"end_result": None, "history": []}
    katrain.game.end_result = None
    session.katrain = katrain
    client.app.state.session_manager._sessions[session.session_id] = session
    return session


# ---------------------------------------------------------------- N21


def test_lobby_resign_is_decided_by_the_seat_of_the_player_who_pressed_it(client):
    black_id, _ = _make_user(client, "alice")
    white_id, white_name = _make_user(client, "bob")
    session = _inject_session(client, user_id=black_id, player_b_id=black_id, player_w_id=white_id)

    resp = client.post("/api/resign", json={"session_id": session.session_id}, headers=_login(client, white_name))

    assert resp.status_code == 200, resp.text
    session.katrain.assert_any_call("resign", "W")


def test_single_player_resign_leaves_the_loser_to_the_seats(client):
    """正对照:单机局不传认输方,交给 `_do_resign` 从座位推。"""
    session = _inject_session(client)

    resp = client.post("/api/resign", json={"session_id": session.session_id})

    assert resp.status_code == 200, resp.text
    session.katrain.assert_any_call("resign")
```

- [ ] **Step 2: 跑测试确认失败**

Run(两条命令,理由见 Global Constraints「不许同跑」):
```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
CI=true uv run pytest tests/test_play_ai_endgame.py tests/core/test_ai_commit_after_end.py -q
CI=true uv run pytest tests/web_ui/test_play_ai_endgame_api.py -q
```
Expected: 5 条 FAIL —— `test_resigning_while_the_ai_is_thinking…`(得到 `B+R`)、`test_an_explicit_loser…`(`TypeError: _do_resign() takes 1 positional argument`)、
两条「不落子」用例(`played` 非空)、`test_lobby_resign…`(实际调用是 `("resign",)`)。其余 PASS:`test_this_module_runs_against_the_real_interface`、
`test_resigning_on_the_humans_own_turn…` 与 `test_two_humans…`(旧代码在这两种情形下碰巧对,它们是改动后的回归护栏)、两条正对照。
**若 `test_this_module_runs_against_the_real_interface` 红,停下来** —— 说明拿到的是 conftest 的替身,这个文件的其余结论都不作数。

- [ ] **Step 3: 实现后端**

`katrain/web/interface.py`,把 `_do_resign`(`:1464-1465`)整段替换为:

```python
    def _do_resign(self, loser: Optional[str] = None):
        """认输。`loser` 是认输的那一方(`"B"`/`"W"`);不给时从这一局的座位推。

        从前写的是 `current_node.player + "+R"` —— 胜方 = **最后落子的一方**。人刚落子、AI 还在算时按认输,
        最后落子的正是人自己,于是这盘被记成人赢(N21)。判据改成「谁在认输」,不是「轮到谁」:
          · 恰好一方是 `player:human`(人机局):认输的一定是人;
          · 两方都是人(本地对局)或都不是(多人局的座位是裸 `human` 字面量):退回「轮到落子的一方」——
            多人局由 `/api/resign` 按请求者座位显式传 `loser`,不走这条回退。
        星阵(跨平台)局认输走平台网关,不经这里。
        """
        if loser not in ("B", "W"):
            humans = [bw for bw, info in self.players_info.items() if info.human]
            loser = humans[0] if len(humans) == 1 else self.game.current_node.next_player
        winner = "W" if loser == "B" else "B"
        self.game.current_node.end_state = f"{winner}+R"
```

`katrain/core/ai.py`,在 `_ladder_remote_terminal`(`:1849-1850`)之后加:

```python
def _game_already_ended(game) -> bool:
    """AI 开算之后这一局有没有被结束(认输 / 超时写在当前节点的 `end_state` 上)。

    生成一手可能要几秒到几分钟;这段时间里人按了认输,再把算出来的着法落下去会生出一个没有终局标记的
    新节点,盘面回到对局中(N21)。
    """
    return bool(getattr(getattr(game, "current_node", None), "end_state", None))
```

`generate_ai_move` 的落子段(`:1974-1981`)改成:

```python
    if ai_mode == AI_LADDER:
        commit_lock = getattr(getattr(game, "katrain", None), "ai_ladder_commit_lock", None)
        with commit_lock if commit_lock is not None else nullcontext():
            if _ladder_remote_terminal(game):
                raise LadderUnavailable("ranked game ended remotely before move commit")
            if _game_already_ended(game):
                return None
            played_node = game.play(move)
    else:
        if _game_already_ended(game):
            return None
        played_node = game.play(move)
```

`katrain/web/server.py` `/api/resign` 里非升降级分支的 `session.katrain("resign")`(`:1917-1918`)替换为:

```python
                else:
                    # N21:多人局按**请求者的座位**判负(`winner_id` 下面也是这么算的,两边必须一致);
                    # 单机局不传,交给 `_do_resign` 从座位推。
                    loser = None
                    if is_multiplayer and current_user is not None:
                        if current_user.id == session.player_b_id:
                            loser = "B"
                        elif current_user.id == session.player_w_id:
                            loser = "W"
                    if loser is None:
                        session.katrain("resign")
                    else:
                        session.katrain("resign", loser)
```

- [ ] **Step 4: 跑后端测试确认通过**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
uv run black -l 120 katrain/web/interface.py katrain/core/ai.py katrain/web/server.py tests/test_play_ai_endgame.py tests/core/test_ai_commit_after_end.py tests/web_ui/test_play_ai_endgame_api.py
CI=true uv run pytest tests/test_play_ai_endgame.py tests/core/test_ai_commit_after_end.py tests/core/test_ladder_strategy.py -q
CI=true uv run pytest tests/web_ui/test_play_ai_endgame_api.py tests/web_ui/test_game_termination_and_chat_identity.py tests/web_ui/test_ai_game_autosave.py -q
git status --short katrain/config.json   # 期望:空
```
Expected: 全 PASS。

- [ ] **Step 5: 写失败的前端测试(追加到 `GamePage.playAi.test.tsx` 末尾)**

```tsx
describe('N21 · 本地对局的认输框说出是哪一方', () => {
  it('两个人面对面、轮到白:标题是「白方认输？」', () => {
    sessionMock.gameState = makeState({
      game_type: 'pvp_local', player_to_move: 'W',
      players_info: { B: seat('player:human', '小明'), W: seat('player:human', '小红') },
    });
    renderPage();
    fireEvent.click(screen.getByText('MOCK_RESIGN'));
    expect(screen.getByText('白方认输？')).toBeInTheDocument();
  });

  it('人机局仍是「确认认输？」—— 认输的一定是人,不用点名', () => {
    sessionMock.gameState = makeState();
    renderPage();
    fireEvent.click(screen.getByText('MOCK_RESIGN'));
    expect(screen.getByText('确认认输？')).toBeInTheDocument();
  });
});
```

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui && npx vitest run src/kiosk/pages/GamePage.playAi.test.tsx`
Expected: 「白方认输？」那条 FAIL,其余 PASS。

- [ ] **Step 6: 实现前端**

`GamePage.tsx` 里 `const humanColor = deriveHumanColor(gameState);` 之后加:

```tsx
  // N21:两个人面对面下时,认输的是**轮到落子的那一方**(`interface.py` `_do_resign` 的回退)。
  // 确认框必须把这一方说出来 —— 否则按下去的人不知道自己替谁认了输。人机局认输的一定是人,不用点名。
  const bothHuman = gameState.players_info.B.player_type === 'player:human'
    && gameState.players_info.W.player_type === 'player:human';
  const resignSide = gameState.player_to_move === 'B' ? t('game:black_side', '黑方') : t('game:white_side', '白方');
  const resignTitle = bothHuman
    ? t('game:resign_confirm_side', '{side}认输？').replace('{side}', resignSide)
    : t('Confirm resign?', '确认认输？');
  const exitResignTitle = bothHuman
    ? t('game:exit_resign_confirm_side', '对局进行中，{side}认输并退出？').replace('{side}', resignSide)
    : t('Game in progress. Resign and exit?', '对局进行中，认输并退出？');
```

认输确认框的标题 `<DialogTitle sx={{ color: 'text.primary' }}>{t('Confirm resign?', '确认认输？')}</DialogTitle>` 改为
`<DialogTitle sx={{ color: 'text.primary' }}>{resignTitle}</DialogTitle>`;
退出确认框的 `<DialogTitle>{t('Game in progress. Resign and exit?', '对局进行中，认输并退出？')}</DialogTitle>` 改为 `<DialogTitle>{exitResignTitle}</DialogTitle>`。

- [ ] **Step 7: 验证并提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npx vitest run src/kiosk/pages/GamePage.playAi.test.tsx src/kiosk/pages/GamePage.test.tsx
npx tsc -b && echo TSC_OK
npx eslint src/kiosk/pages/GamePage.tsx
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
# 基线 diff(后端 + 前端,按 Task 0 Step 4 的写法),期望 comm -13 无输出
git add katrain/web/interface.py katrain/core/ai.py katrain/web/server.py katrain/web/ui/src/kiosk/pages/GamePage.tsx \
  katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx tests/test_play_ai_endgame.py tests/core/test_ai_commit_after_end.py tests/web_ui/test_play_ai_endgame_api.py
git diff --cached --stat
git commit -m "fix(play): AI 思考中认输被记成人赢,AI 那一手随后又落下 —— 认输按座位判,终局后不落子

N21(P1)。_do_resign 原来写「最后落子的一方胜」;人机局改判人输,多人局按请求者座位判,
本地对局确认框点名是哪一方;generate_ai_move 落子前对局已有 end_state 就不落。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: N23 数子门槛按路数缩放

**Files:**
- Modify: `katrain/web/interface.py:281-284`(`analysis_allowed` 之后加 `count_min_moves()`)、`:611`(`get_state` 的 `count_min_moves` 键)
- Modify: `katrain/web/server.py:2015-2019`(`/api/count/request` 的门槛)
- Test: `tests/test_play_ai_endgame.py`、`tests/web_ui/test_play_ai_endgame_api.py`(追加)

**Interfaces:**
- Consumes: Task 2 的测试夹具 `_web_katrain()`、`client`、`_inject_session()`
- Produces: `WebKaTrain.count_min_moves(self) -> int`;`get_state()["count_min_moves"]` 即它的值;`/api/count/request` 只读 `get_state()` 下发的这个值(前后端同源)

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_play_ai_endgame.py` 末尾:

```python
# ---------------------------------------------------------------- N23 数子门槛按路数


@pytest.mark.parametrize("size,expected", [(19, 100), (13, 46), (9, 22)])
def test_count_threshold_scales_with_board_size(size, expected):
    """配置里的 100 是 19 路的数;小棋盘按交叉点数等比缩小,和 AI 认输门槛(core/ai.py should_ai_resign)同一种缩放。"""
    w = _web_katrain()
    w._do_new_game(size=size)
    assert w.count_min_moves() == expected
    assert w.get_state()["count_min_moves"] == expected
```

追加到 `tests/web_ui/test_play_ai_endgame_api.py` 末尾:

```python
# ---------------------------------------------------------------- N23


def test_count_refuses_with_the_threshold_the_session_reports(client):
    """门槛只有一个来源:`get_state()` 下发的 `count_min_moves`(前端读的也是它)。"""
    session = _inject_session(client)
    session.katrain.get_state.return_value = {"end_result": None, "history": [{}] * 21, "count_min_moves": 22}

    resp = client.post("/api/count/request", json={"session_id": session.session_id})

    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"] == "Cannot count before 22 moves"
```

Run(分两条):`cd /Users/fan/Repositories/katrain-kiosk-go-play-ai && CI=true uv run pytest tests/test_play_ai_endgame.py -q -k "threshold"; CI=true uv run pytest tests/web_ui/test_play_ai_endgame_api.py -q -k "threshold"`
Expected: 13/9 路两条 FAIL(`AttributeError: 'WebKaTrain' object has no attribute 'count_min_moves'`,19 路那条同样 FAIL);API 那条 FAIL(detail 是 `…before 100 moves` 或 `MagicMock` 相关)。

- [ ] **Step 2: 实现**

`katrain/web/interface.py`,`analysis_allowed` 属性之后加:

```python
    def count_min_moves(self) -> int:
        """数子门槛(手数)。配置里的 `game/count_min_moves` 是 **19 路**的数;
        小棋盘按交叉点数等比缩小 —— 与 AI 认输门槛(`core/ai.py` `should_ai_resign`)同一种缩放。
        不缩放时 9 路盘 81 个交叉点、几十手就下完,数子键整局都是灰的(N23)。"""
        configured = self.config("game/count_min_moves", 100)
        if not self.game:
            return configured
        width, height = self.game.board_size
        return max(1, int(configured * width * height / 361))
```

`get_state` 里 `"count_min_moves": self.config("game/count_min_moves", 100),` 改为 `"count_min_moves": self.count_min_moves(),`。

`katrain/web/server.py` `/api/count/request` 里

```python
        state = session.katrain.get_state()
        count_min_moves = session.katrain.config("game/count_min_moves", 100)
```

改为

```python
        state = session.katrain.get_state()
        # 门槛认 get_state 下发的那个数(按路数缩放过,前端显示的也是它)。状态里没有这个键时回落到配置 ——
        # 不许回落成写死的 100:tests/web_ui/test_ai_ladder_api.py 的 FakeKaTrain 状态里没有这个键、
        # 配置给的是 0,`test_ranked_session_allows_human_turn_terminal_actions[/api/count/request]` 期望 200。
        count_min_moves = state.get("count_min_moves")
        if count_min_moves is None:
            count_min_moves = session.katrain.config("game/count_min_moves", 100)
```

- [ ] **Step 3: 跑测试确认通过**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
uv run black -l 120 katrain/web/interface.py katrain/web/server.py tests/test_play_ai_endgame.py tests/web_ui/test_play_ai_endgame_api.py
CI=true uv run pytest tests/test_play_ai_endgame.py -q
CI=true uv run pytest tests/web_ui/test_play_ai_endgame_api.py tests/web_ui/test_count_api.py tests/web_ui/test_ai_ladder_api.py -q
git status --short katrain/config.json   # 期望:空
```
Expected: 全 PASS(`test_ai_ladder_api.py` 里三条 `terminal_actions` 参数化用例是改 `/api/count/request` 最可能打红的地方)。前端无改动:`GameControlPanel.tsx:188` 读的就是 `gameState.count_min_moves`,「数子要下满 N 手」自动变成 22/46/100。

- [ ] **Step 4: 基线 diff 后提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git add katrain/web/interface.py katrain/web/server.py tests/test_play_ai_endgame.py tests/web_ui/test_play_ai_endgame_api.py
git diff --cached --stat
git commit -m "fix(play): 9 路与多数 13 路整局数不了子 —— 数子门槛按交叉点数缩放,前后端同源

N23(P2)。count_min_moves 固定 100 不分路数;改为 configured×w×h/361(19/13/9 路 = 100/46/22),
/api/count/request 只读 get_state 下发的同一个数。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: A12 数子前服务端补分;数子在途与失败原因说真话

**Files:**
- Modify: `katrain/web/interface.py`(`count_min_moves()` 之后加 `ENSURE_SCORE_TIMEOUT_S` 与 `ensure_current_score()`)
- Modify: `katrain/web/server.py:2067-2069`(`/api/count/request` 的 HvAI / pvp_local 分支,进锁之前补分)
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx:433-444`(`handleAction` 的 `count` 分支)+ 状态声明区 + 一个 `Snackbar`
- Test: `tests/test_play_ai_endgame.py`、`tests/web_ui/test_play_ai_endgame_api.py`、`katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx`(追加)
- Modify(测试替身): `tests/web_ui/test_ai_ladder_api.py` 的 `FakeKaTrain`(`:97` 起)补一个 `ensure_current_score` —— 端点新调的方法替身没有,
  `test_ranked_session_allows_human_turn_terminal_actions[/api/count/request]` 会从 200 变 500

**Interfaces:**
- Consumes: Task 3 的 `count_min_moves()`;Task 2 的测试夹具
- Produces: `WebKaTrain.ENSURE_SCORE_TIMEOUT_S: float = 15.0`;`WebKaTrain.ensure_current_score(self, timeout_s: Optional[float] = None) -> Optional[float]`
  (阻塞;升降级局与无引擎时不请求、立即返回已有值)。Task 5 复用它。

- [ ] **Step 1: 写失败的后端测试**

追加到 `tests/test_play_ai_endgame.py` 末尾:

```python
# ---------------------------------------------------------------- A12 数子前补分


class _InstantEngine:
    """一请求就同步回一份分析的假引擎 —— 只实现 GameNode.analyze 用到的那一个方法。"""

    def __init__(self, score):
        self.score = score
        self.requests = 0

    def request_analysis(self, node, callback, **kwargs):
        self.requests += 1
        callback({"rootInfo": {"scoreLead": self.score, "winrate": 0.6, "visits": 5}, "moveInfos": []}, False)


def _free_game_with_moves(engine):
    w = _web_katrain()
    _seat(w, human_colors={"B"})
    w.game.play(Move(coords=(3, 3), player="B"))
    w.game.play(Move(coords=(15, 15), player="W"))
    w.engine = engine  # 落子之后再换:game.play 用的是开局时的 NullEngine,不会先把分补上
    return w


def test_missing_score_is_filled_by_one_analysis():
    engine = _InstantEngine(score=3.5)
    w = _free_game_with_moves(engine)
    assert w.game.current_node.score is None
    assert w.ensure_current_score(timeout_s=1) == 3.5
    assert engine.requests == 1


def test_an_existing_score_is_not_requested_again():
    engine = _InstantEngine(score=-2.0)
    w = _free_game_with_moves(engine)
    w.ensure_current_score(timeout_s=1)
    w.ensure_current_score(timeout_s=1)
    assert engine.requests == 1


def test_ranked_games_are_never_analysed_for_a_score():
    """升降级终局怎么判目等 Fan 拍板(PRD §4 A12-R);在那之前一次都不许替它算。"""
    engine = _InstantEngine(score=3.5)
    w = _free_game_with_moves(engine)
    w.game_type = "ai_ladder_ranked"
    assert w.ensure_current_score(timeout_s=1) is None
    assert engine.requests == 0


def test_no_engine_returns_at_once_instead_of_waiting_out_the_timeout():
    import time

    w = _web_katrain()  # enable_engine=False ⇒ NullEngine,请求永远不会回来
    started = time.monotonic()
    assert w.ensure_current_score(timeout_s=5) is None
    assert time.monotonic() - started < 1
```

追加到 `tests/web_ui/test_play_ai_endgame_api.py` 末尾:

```python
# ---------------------------------------------------------------- A12


def _countable(session):
    session.katrain.get_state.return_value = {"end_result": None, "history": [{}] * 101, "count_min_moves": 100}
    session.katrain.game.current_node.score = None


def test_count_fills_the_missing_score_before_counting(client):
    session = _inject_session(client)
    _countable(session)

    def fill_score(*_args, **_kwargs):
        session.katrain.game.current_node.score = 2.5
        return 2.5

    session.katrain.ensure_current_score.side_effect = fill_score

    resp = client.post("/api/count/request", json={"session_id": session.session_id})

    assert resp.status_code == 200, resp.text
    assert resp.json()["result"] == "B+2.5"
    session.katrain.ensure_current_score.assert_called_once()


def test_count_still_says_why_when_no_score_can_be_had(client):
    """补不出来(升降级局 / 引擎不可用)时照旧 400,detail 原样 —— 前端靠它说对原因。"""
    session = _inject_session(client)
    _countable(session)
    session.katrain.ensure_current_score.return_value = None

    resp = client.post("/api/count/request", json={"session_id": session.session_id})

    assert resp.status_code == 400
    assert resp.json()["detail"].startswith("Analysis not available")
```

Run(分两条):`cd /Users/fan/Repositories/katrain-kiosk-go-play-ai && CI=true uv run pytest tests/test_play_ai_endgame.py -q; CI=true uv run pytest tests/web_ui/test_play_ai_endgame_api.py -q`
Expected: 四条 interface 用例 FAIL(`AttributeError: … 'ensure_current_score'`);`test_count_fills_the_missing_score_before_counting` FAIL(400,端点没调补分);`test_count_still_says_why…` PASS(现状就是 400)。

- [ ] **Step 2: 实现后端**

`katrain/web/interface.py`,`count_min_moves()` 之后加:

```python
    #: 数子 / 双停终局时服务端自己补一次形势分析,最多等这么久(秒)。
    ENSURE_SCORE_TIMEOUT_S = 15.0

    def ensure_current_score(self, timeout_s: Optional[float] = None) -> Optional[float]:
        """当前这一手的目差(`scoreLead`,正数黑领先);没有就补一次快速分析并**同步等它算完**。

        盒上逐手分析是关的(`should_suppress_auto_eval`),当前手常常没有分数;从前数子全靠前端「图表」开关每手补一次,
        游客、关了开关、分析没回来就点,一律 400(A12)。这里让判胜负不再依赖前端开关。

        · 只给允许分析的局补(`analysis_allowed`):升降级局原样返回已有值(通常是 None)——
          升降级终局怎么判目等 Fan 拍板(PRD §4 A12-R)。
        · 不走 `__call__` 的 ANALYSIS_ACTIONS 闸:这不是交付给玩家看的分析,是判胜负用的内部量;上一条就是它的闸。
        · 阻塞调用,**不许在事件循环线程里直接调** —— 服务端用 `asyncio.to_thread`。
        """
        timeout_s = self.ENSURE_SCORE_TIMEOUT_S if timeout_s is None else timeout_s
        if not self.game:
            return None
        node = self.game.current_node
        if node.analysis_complete and node.score is not None:
            return node.score
        if not self.analysis_allowed:
            return node.score
        try:
            engine = self.analysis_engine()
        except Exception:
            engine = self.engine
        if engine is None or isinstance(engine, NullEngine):
            return node.score
        if not node.analysis_exists:
            node.analyze(engine, analyze_fast=True)
        deadline = time.monotonic() + timeout_s
        while not node.analysis_complete and time.monotonic() < deadline:
            time.sleep(0.1)
        return node.score
```

`katrain/web/server.py` `/api/count/request` 的 `else:` 分支(`# HvAI / pvp_local: complete immediately` 下面、`with session.lock:` 之前)加一行:

```python
            # A12:当前手没有分数就先补一次分析再数。阻塞等待放线程里,不占事件循环;
            # 升降级局在 interface 里就不补,照旧走到 _complete_count 的 400。
            await asyncio.to_thread(session.katrain.ensure_current_score)
```

`tests/web_ui/test_ai_ladder_api.py` 的 `FakeKaTrain` 里 `def config(self, setting, default=None):` 之前加(替身要跟上真接口,不在端点里 `getattr` 迁就替身):

```python
    def ensure_current_score(self, timeout_s=None):
        # 真 WebKaTrain 对升降级局不补分析,原样返回当前手已有的分数(A12);替身的当前手本来就带 3.5。
        return self.game.current_node.score
```

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-play-ai && uv run black -l 120 katrain/web/interface.py katrain/web/server.py tests/test_play_ai_endgame.py tests/web_ui/test_play_ai_endgame_api.py tests/web_ui/test_ai_ladder_api.py && CI=true uv run pytest tests/test_play_ai_endgame.py -q && CI=true uv run pytest tests/web_ui/test_play_ai_endgame_api.py tests/web_ui/test_count_api.py tests/web_ui/test_ai_ladder_api.py -q && git status --short katrain/config.json`
Expected: 全 PASS;config.json 无改动。

- [ ] **Step 3: 写失败的前端测试(追加到 `GamePage.playAi.test.tsx` 末尾)**

```tsx
describe('A12 · 数子在途与失败原因', () => {
  const countable = () => makeState({
    history: Array.from({ length: 120 }, (_, i) => ({ node_id: i, score: null, winrate: null })) as GameState['history'],
  });
  const noScore = 'Request failed 400: {"detail":"Analysis not available yet. Please wait for KataGo analysis to complete."}';

  it('服务端说「分析没算出来」时照实说,不再说成手数不够', async () => {
    sessionMock.gameState = countable();
    vi.spyOn(API, 'requestCount').mockRejectedValue(new Error(noScore));
    renderPage();
    fireEvent.click(screen.getByText('MOCK_COUNT'));
    expect(await screen.findByText('形势分析没算出来，暂时数不了子，请稍后再试')).toBeInTheDocument();
    expect(screen.queryByText(/手数不足/)).toBeNull();
  });

  it('升降级局同一个 400 说「升降级对局现在数不了子」', async () => {
    sessionMock.gameState = { ...countable(), game_type: 'ai_ladder_ranked' };
    vi.spyOn(API, 'requestCount').mockRejectedValue(new Error(noScore));
    renderPage();
    fireEvent.click(screen.getByText('MOCK_COUNT'));
    expect(await screen.findByText('升降级对局现在数不了子（本局不做形势分析）')).toBeInTheDocument();
  });

  it('在途时说「正在数子…」,重复点击不发第二个请求', async () => {
    sessionMock.gameState = countable();
    let finish!: (v: unknown) => void;
    const spy = vi.spyOn(API, 'requestCount').mockImplementation(() => new Promise((r) => { finish = r; }));
    renderPage();
    fireEvent.click(screen.getByText('MOCK_COUNT'));
    fireEvent.click(screen.getByText('MOCK_COUNT'));
    expect(await screen.findByText('正在数子…')).toBeInTheDocument();
    expect(spy).toHaveBeenCalledTimes(1);
    finish({ state: sessionMock.gameState });
    await waitFor(() => expect(screen.queryByText('正在数子…')).toBeNull());
  });
});
```

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui && npx vitest run src/kiosk/pages/GamePage.playAi.test.tsx`
Expected: 三条 A12 用例 FAIL(文案仍是「暂时不能数子（对局手数不足或已结束）」、没有「正在数子…」、spy 被调两次)。

- [ ] **Step 4: 实现前端**

`GamePage.tsx` 状态声明区(`const [countError, setCountError] = useState<string | null>(null);` 之后)加:

```tsx
  // A12:数子可能要等几秒(当前手没有分数时服务端先补一次分析,上限 15 秒)。
  // ref 挡同一帧里的连点(state 要等下一次渲染才看得见),state 负责屏上那句「正在数子…」。
  const countingRef = useRef(false);
  const [counting, setCounting] = useState(false);
```

`const isRanked = isRankedGameType(gameState.game_type);` 之后加:

```tsx
  // A12:数子失败**按服务端给的原因**说话。从前一律「对局手数不足或已结束」,
  // 把盒上最常见的「这一手还没有分数」也说成了手数不够。
  const countFailureMessage = (message: string) =>
    message.includes('Cannot count before') ? t('game:count_too_early', '手数还不够，暂时不能数子')
    : message.includes('already over') ? t('game:count_game_over', '这一局已经结束了')
    : message.includes('only allowed on the human turn') ? t('game:count_not_your_turn', '轮到你落子时才能数子')
    : message.includes('Analysis not available') ? (isRanked
      ? t('game:count_ranked_unscored', '升降级对局现在数不了子（本局不做形势分析）')
      : t('game:count_no_score', '形势分析没算出来，暂时数不了子，请稍后再试'))
    : t('game:count_failed', '数子没有成功，请稍后再试');
```

`handleAction` 的 `count` 分支整段替换为:

```tsx
    if (action === 'count') {
      // 数子:人机 / 本地对局由服务端当场数完并结束对局(没有对手握手)。
      if (!sessionId || countingRef.current) return;
      countingRef.current = true;
      setCounting(true);
      try {
        const res = await API.requestCount(sessionId);
        if (res?.state) session.setGameState(res.state);
      } catch (e) {
        setCountError(countFailureMessage(e instanceof Error ? e.message : ''));
      } finally {
        countingRef.current = false;
        setCounting(false);
      }
      return;
    }
```

在 `{/* Count (数子) error toast */}` 那个 `Snackbar` 之前加:

```tsx
      {/* 数子在途 —— 服务端可能正在给这一手补分析,这几秒里屏上不能什么都不说 */}
      <Snackbar open={counting} anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
        <Alert severity="info">{t('game:counting', '正在数子…')}</Alert>
      </Snackbar>
```

- [ ] **Step 5: 验证并提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npx vitest run src/kiosk/pages/GamePage.playAi.test.tsx src/kiosk/pages/GamePage.test.tsx src/kiosk/__tests__/GamePageEngine.test.tsx
npx tsc -b && echo TSC_OK
npx eslint src/kiosk/pages/GamePage.tsx
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
# 基线 diff(后端 + 前端),期望 comm -13 无输出
git add katrain/web/interface.py katrain/web/server.py katrain/web/ui/src/kiosk/pages/GamePage.tsx \
  katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx tests/test_play_ai_endgame.py tests/web_ui/test_play_ai_endgame_api.py \
  tests/web_ui/test_ai_ladder_api.py
git diff --cached --stat
git commit -m "fix(play): 盒上数子几乎总是 400 且把原因说成手数不足 —— 服务端先补分再数,前端按真实原因说话

A12(P1)。board 模式不做逐手分析,数子原来全靠前端「图表」开关每手补分。新增 ensure_current_score
(升降级局不补,等 Fan 拍板),/api/count/request 放线程里等它;数子在途说「正在数子…」。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```
**必须上板**(记进 Task 12 清单):RK3562 上自由对弈关掉领地与图表,第 100 手后点数子,记录从点击到出结果的耗时。

---

### Task 5: N22 终局收尾一个函数:双停先补分再落账;AI 收尾的局也落账/进结算

**Files:**
- Modify: `katrain/web/interface.py`(`__init__` 加 `game_ended_callback`;`_do_ai_move_and_broadcast`(`:1084-1095`)在 AI 线程让对局由「没结束」变「结束」时调它一次)
- Modify: `katrain/web/session.py:6-8`(typing import)、`:15-33`(`WebSession` 加 `end_game_lock`)、`:36-45`(`SessionManager.__init__` 加 `on_game_ended`)、`create_session`(`:80-81`,装 `game_ended_callback`)+ 新方法 `_on_game_ended` / `_schedule_game_ended`。**`_on_state` 不动**(理由见 Step 2)
- Modify: `katrain/web/server.py:1955-1986`(`_complete_count` 抽出 `_apply_counted_result`)、`_complete_count` 之后 / `@app.post("/api/count/request")` 之前(新增 `_score_two_pass_end` / `_finish_ended_game` / `_on_game_ended_off_request` 并装到 `manager`)、`:996-1003`(`/api/move` 自然终局)
- Create: `tests/web_ui/test_game_end_hook.py`
- Test: `tests/test_play_ai_endgame.py`(追加)

**Interfaces:**
- Consumes: Task 4 的 `WebKaTrain.ensure_current_score()`;既有 `_record_ai_game(session, app, current_user, result)`(不改)
- Produces:
  - `WebSession.end_game_lock: asyncio.Lock`
  - `WebKaTrain.game_ended_callback: Optional[Callable[[], None]]`(**只有 AI 后台线程调**:`_do_ai_move_and_broadcast` 开始时对局没结束、结束时结束了)
  - `SessionManager.on_game_ended: Optional[Callable[[WebSession], Awaitable[None]]]`(server 装上;`create_session` 把 `katrain.game_ended_callback` 接到 `SessionManager._on_game_ended(session_id)`,后者置 `game_ended` 并对非研究模式的会话调度一次钩子)
  - server 闭包 `_apply_counted_result(session, score: float) -> tuple[str, str]`、`async _score_two_pass_end(session) -> Optional[str]`、
    `async _finish_ended_game(session, app, current_user) -> None`;测试钩子 `katrain.web.server._FINISH_ENDED_GAME_FN`

- [ ] **Step 1: 写失败的测试**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git ls-files tests/web_ui/test_game_end_hook.py; ls tests/web_ui/test_game_end_hook.py   # 期望:都没有
```

`tests/web_ui/test_game_end_hook.py`:

```python
"""N22:对局在**请求之外**结束(AI 后台线程下出双停第二手 / AI 认输)时,SessionManager 要把收尾交给事件循环。

从前 AI 线程结束对局时 `_on_state` 只置 `game_ended`,不落账:由 AI 收尾的局不进对局记录,升降级局不进结算、心跳停掉。

触发点是 `WebKaTrain.game_ended_callback`(只有 AI 线程调),**不是** `_on_state` 里「end_result 由无变有」——
后者在「对局会话里载入一份 SGF 再翻到双停终点」时同样成立(galaxy `ZenModeApp` 就用 play 会话 `loadSGF`),
会把一份不是在这里下的棋谱补分、再记成这个用户的对局。「每局只收尾一次」由 server 的 `_finish_ended_game` 保证。
"""

import asyncio
from unittest.mock import MagicMock

from katrain.web.session import SessionManager, WebSession


async def _manager_with_hook(session):
    manager = SessionManager(enable_engine=False)
    manager._sessions[session.session_id] = session
    manager.attach_loop(asyncio.get_running_loop())
    seen = []

    async def hook(s):
        seen.append(s.session_id)

    manager.on_game_ended = hook
    return manager, seen


async def test_the_ai_thread_ending_a_game_runs_the_hook():
    session = WebSession(session_id="s-ai-pass", katrain=MagicMock())
    manager, seen = await _manager_with_hook(session)
    # AI 线程就是从事件循环以外的线程回调的
    await asyncio.to_thread(manager._on_game_ended, session.session_id)
    await asyncio.sleep(0.05)
    assert seen == ["s-ai-pass"]
    assert session.game_ended is True


async def test_research_sessions_never_run_the_hook():
    """研究模式载入一份带结果的棋谱不是「下完了一局」,不许被当成对局记下来。"""
    session = WebSession(session_id="s-research", katrain=MagicMock(), mode="research")
    manager, seen = await _manager_with_hook(session)
    await asyncio.to_thread(manager._on_game_ended, session.session_id)
    await asyncio.sleep(0.05)
    assert seen == []


async def test_a_broadcast_that_merely_shows_an_ended_game_does_not_run_the_hook():
    """翻到载入棋谱的双停终点同样会推一帧带 end_result 的状态 —— 那不是在这里下完的一局。"""
    session = WebSession(session_id="s-nav", katrain=MagicMock())
    manager, seen = await _manager_with_hook(session)
    await asyncio.to_thread(manager._on_state, session.session_id, {"end_result": "B+R"})
    await asyncio.sleep(0.05)
    assert seen == []
    assert session.game_ended is True  # `_on_state` 原有语义不变(心跳靠它停)


def test_create_session_wires_the_ai_thread_callback(monkeypatch):
    """接线只有一行;漏了它,上面几条全绿而 N22 在真机上整条是死的。"""
    import katrain.web.session as session_module

    monkeypatch.setattr(session_module, "WebKaTrain", MagicMock())
    manager = SessionManager(enable_engine=False)
    session = manager.create_session(user_id=7)
    called = []
    monkeypatch.setattr(manager, "_on_game_ended", lambda sid: called.append(sid))
    session.katrain.game_ended_callback()
    assert called == [session.session_id]
```

追加到 `tests/test_play_ai_endgame.py` 末尾:

```python
# ---------------------------------------------------------------- N22 终局收尾


import asyncio  # noqa: E402
import threading  # noqa: E402
import types  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402


@pytest.fixture(scope="module")
def server_module():
    import katrain.web.server as server

    # `_FINISH_ENDED_GAME_FN` 是 create_app 里的闭包,建一次 app 才会挂到模块上(同 tests/test_local_play_recording.py)
    server.create_app(enable_engine=False)
    return server


class _Info:
    def __init__(self, human, name):
        self.human, self.ai, self.name = human, not human, name
        self.calculated_rank = None
        self.sgf_rank = None


def _ended_session(*, end_state=None, end_result="board-game-end", analysis_allowed=True):
    s = MagicMock()
    s.user_id = 42
    s.player_b_id = None
    s.player_w_id = None
    s._recorded = False  # 裸 MagicMock 的 `_recorded` 是真值 Mock,幂等闸会把每一次都当成「已记过」
    s.game_type = "free"
    s.lock = threading.Lock()
    s.katrain.analysis_allowed = analysis_allowed
    s.katrain.game.end_result = end_result
    s.katrain.game.current_node.end_state = end_state
    s.katrain.get_sgf.return_value = "(;GM[1])"
    s.katrain.get_state.return_value = {"board_size": [19, 19], "history": [1, 2, 3], "komi": 7.5, "ruleset": "chinese"}
    s.katrain.players_info = {"B": _Info(True, "小明"), "W": _Info(False, "")}
    return s


def _recording_app():
    app = MagicMock()
    app.state.repository_dispatcher.user_games_create = AsyncMock(return_value={"id": "g1"})
    return app


_USER = types.SimpleNamespace(id=42, username="小明")


def test_create_app_installs_the_off_request_hook(server_module):
    app = server_module.create_app(enable_engine=False)
    assert app.state.session_manager.on_game_ended is not None


def _ai_thread_game(monkeypatch, human_first, ai_reply):
    """真 WebKaTrain:人先下 `human_first`,AI 线程(`_do_ai_move_and_broadcast`)回 `ai_reply`。
    `generate_ai_move` 换成直接落子的桩;`update_state` 置空 —— 只证回调,不起下一条 AI 线程。"""
    import katrain.core.ai as core_ai

    w = _web_katrain()
    _seat(w, human_colors={"B"})
    w.game.play(Move(coords=human_first, player="B"))
    calls = []
    w.game_ended_callback = lambda: calls.append(w.game.end_result)
    w.update_state = lambda **_kwargs: None

    def fake_generate(game, mode, settings):
        move = Move(coords=ai_reply, player="W")
        return move, game.play(move)

    monkeypatch.setattr(core_ai, "generate_ai_move", fake_generate)
    w._do_ai_move_and_broadcast(w.game.current_node)
    return calls


def test_the_ai_thread_reports_a_game_it_ended(monkeypatch):
    """人先停一手、AI 跟停 —— 盒上最常见的收官。这条回调就是 N22 收尾在 AI 这条路上的唯一入口。"""
    calls = _ai_thread_game(monkeypatch, human_first=None, ai_reply=None)
    assert len(calls) == 1 and calls[0]


def test_an_ordinary_ai_move_reports_nothing(monkeypatch):
    """正对照:没结束就不叫 —— 否则上一条的「叫了一次」可能只是每手都叫。"""
    assert _ai_thread_game(monkeypatch, human_first=(3, 3), ai_reply=(15, 15)) == []


async def test_two_pass_end_is_scored_before_it_is_recorded(server_module):
    session = _ended_session()
    session.katrain.ensure_current_score.return_value = 2.5
    app = _recording_app()

    await server_module._FINISH_ENDED_GAME_FN(session, app, _USER)

    data = app.state.repository_dispatcher.user_games_create.await_args.kwargs["data"]
    assert data["result"] == "B+2.5"
    assert session.katrain.game.current_node.end_state == "B+2.5"
    session.katrain.update_state.assert_called_once()


async def test_games_that_forbid_analysis_are_recorded_without_a_score(server_module):
    """升降级局走的就是这一支:不补分,照旧按「终局」落账(无结论)—— 怎么判目等 Fan 拍板。"""
    session = _ended_session(analysis_allowed=False)
    app = _recording_app()

    await server_module._FINISH_ENDED_GAME_FN(session, app, _USER)

    session.katrain.ensure_current_score.assert_not_called()
    data = app.state.repository_dispatcher.user_games_create.await_args.kwargs["data"]
    assert data["result"] == "board-game-end"


async def test_a_resigned_game_is_recorded_as_is(server_module):
    session = _ended_session(end_state="W+R", end_result="W+R")
    app = _recording_app()

    await server_module._FINISH_ENDED_GAME_FN(session, app, _USER)

    session.katrain.ensure_current_score.assert_not_called()
    assert app.state.repository_dispatcher.user_games_create.await_args.kwargs["data"]["result"] == "W+R"


async def test_request_and_ai_thread_finishing_together_score_and_record_once(server_module):
    session = _ended_session()
    calls = {"n": 0}

    def score():
        calls["n"] += 1
        return 2.5

    session.katrain.ensure_current_score.side_effect = score
    app = _recording_app()

    await asyncio.gather(
        server_module._FINISH_ENDED_GAME_FN(session, app, _USER),
        server_module._FINISH_ENDED_GAME_FN(session, app, _USER),
    )

    assert calls["n"] == 1
    assert app.state.repository_dispatcher.user_games_create.await_count == 1


async def test_multiplayer_research_and_guest_games_are_not_recorded_here(server_module):
    lobby = _ended_session()
    lobby.player_b_id, lobby.player_w_id = 1, 2
    research = _ended_session()
    research.mode = "research"  # 研究模式里人按了两次停一手(/api/move),不是下完了一局
    guest = _ended_session()
    guest.user_id = None
    guest.katrain.ensure_current_score.return_value = 1.5
    app = _recording_app()

    await server_module._FINISH_ENDED_GAME_FN(lobby, app, _USER)
    await server_module._FINISH_ENDED_GAME_FN(research, app, _USER)
    await server_module._FINISH_ENDED_GAME_FN(guest, app, None)

    lobby.katrain.ensure_current_score.assert_not_called()
    research.katrain.ensure_current_score.assert_not_called()
    assert guest.katrain.game.current_node.end_state == "B+1.5"  # 游客的局照样分出胜负,只是不落账
    app.state.repository_dispatcher.user_games_create.assert_not_awaited()
```

Run(分两条):`cd /Users/fan/Repositories/katrain-kiosk-go-play-ai && CI=true uv run pytest tests/test_play_ai_endgame.py -q; CI=true uv run pytest tests/web_ui/test_game_end_hook.py -q`
Expected: hook 文件里 `test_the_ai_thread_ending_a_game_runs_the_hook`、`test_research_sessions_never_run_the_hook`(两条都是 `AttributeError: … '_on_game_ended'`)、
`test_create_session_wires_the_ai_thread_callback`(`called == []`)FAIL,`test_a_broadcast_that_merely_shows…` PASS(现状本来就不叫);
根目录文件里 N22 的 6 条 `_FINISH_ENDED_GAME_FN` / `on_game_ended` 用例 FAIL(`AttributeError`)、`test_the_ai_thread_reports_a_game_it_ended` FAIL(`calls == []`)、
`test_an_ordinary_ai_move_reports_nothing` PASS。

- [ ] **Step 2: 实现 `interface.py` 与 `session.py`**

**为什么触发点放在 AI 线程、不放在 `_on_state`**:`_on_state` 看到的是「这一帧状态带 `end_result`」,它分不出「这一局刚在这里下完」和
「有人把一份载入的 SGF 翻到了双停终点」(galaxy `ZenModeApp` 就是 play 会话 + `loadSGF`)。放在那里会把别人的棋谱补分、再记成这个用户的对局。
人发出的四条路(`/api/move` 双停、认输、超时、数子)各自在请求里收尾;缺的只有 AI 线程这一条,所以只补这一条。

`interface.py` `__init__` 里 `self.update_state_callback: Optional[Callable] = None` 之后加:

```python
        # N22:AI 后台线程让对局由「没结束」变「结束」(AI 跟停 / AI 认输)时调一次,SessionManager 装上。
        self.game_ended_callback: Optional[Callable[[], None]] = None
```

`_do_ai_move_and_broadcast` 整段替换为(`finally` 里原有那段注释照抄保留):

```python
    def _do_ai_move_and_broadcast(self, cn):
        """Background thread: generate AI move then broadcast state update."""
        game = self.game
        ended_before = bool(game is not None and game.end_result)
        try:
            self._do_ai_move(cn)
        except Exception as e:
            self.log(f"Error in AI move generation: {e}", OUTPUT_ERROR)
        finally:
            self._ai_move_pending = False
            # Use update_state() instead of bare callback — this both broadcasts
            # AND re-runs _do_update_state(), which re-triggers AI if the game
            # tree changed (e.g., user undid + replayed while this thread ran).
            self.update_state()
            # N22:这条线程让对局结束了 —— 告诉会话去收尾(补分、落账、进结算)。人发出的请求各自收尾,不经这里;
            # 两边(比如 AI 算的时候人按了认输)在 server 的 `_finish_ended_game` 里串行、只落一次账。
            callback = getattr(self, "game_ended_callback", None)
            if callback is not None and not ended_before and game is not None and self.game is game and game.end_result:
                try:
                    callback()
                except Exception as e:
                    self.log(f"Error in game-ended callback: {e}", OUTPUT_ERROR)
```

`session.py`:

typing import 行改为 `from typing import Awaitable, Callable, Dict, Optional, Set, List`。

`WebSession` 里 `record_game_lock` 那一行之后加:

```python
    # N22:终局收尾(先补分、再落账)的会话级串行锁。人发出的双停第二手和 AI 线程触发的收尾可能同时到,
    # 不串行的话先落账的那一方会把「终局」写进账,补出来的分数就再也进不去了(`_recorded` 已置)。
    end_game_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
```

`SessionManager.__init__` 末尾加:

```python
        #: N22:对局在**请求之外**结束(AI 后台线程下出双停第二手 / AI 认输)时调用的收尾函数,由 server.py 装上。
        #: 人发出的请求自己也调同一个函数;两边靠 `WebSession.end_game_lock` 与 `_record_ai_game` 的幂等只收尾一次。
        self.on_game_ended: Optional[Callable[[WebSession], Awaitable[None]]] = None
```

`create_session` 里 `session.katrain.message_callback = lambda …` 那一行之后加:

```python
        session.katrain.game_ended_callback = lambda sid=session_id: self._on_game_ended(sid)
```

**`_on_state` 不改**(它照旧置 `game_ended`,升降级心跳靠它停)。在 `_on_message` 之前加:

```python
    def _on_game_ended(self, session_id: str):
        """AI 后台线程让对局结束时由 `WebKaTrain.game_ended_callback` 调(N22)。只有这一个触发点 ——
        `_on_state` 分不出「刚在这里下完」和「翻到了一份载入棋谱的双停终点」。"""
        try:
            session = self.get_session(session_id)
        except KeyError:
            return
        session.game_ended = True
        self._schedule_game_ended(session)

    def _schedule_game_ended(self, session: WebSession):
        """把收尾交给事件循环。研究模式不收尾:那里下出的双停不是「下完了一局」。"""
        hook = self.on_game_ended
        if hook is None or session.mode == "research":
            return
        if not self._loop or not self._loop.is_running():
            return

        def _log_failure(fut):
            if fut.cancelled():
                return
            exc = fut.exception()
            if exc is not None:
                logging.getLogger("katrain_web").error("game-ended hook failed for %s: %s", session.session_id, exc)

        if threading.get_ident() == self._loop_thread_id:
            self._loop.create_task(hook(session)).add_done_callback(_log_failure)
        else:
            asyncio.run_coroutine_threadsafe(hook(session), self._loop).add_done_callback(_log_failure)
```

- [ ] **Step 3: 实现 `server.py`**

① `_complete_count` 之前加 `_apply_counted_result`,并把 `_complete_count` 里从 `# Format result: positive = Black leads` 到 `session.game_ended = True` 那一段(`:1971-1983`)替换为一行调用:

```python
    def _apply_counted_result(session, score):
        """把目差写成终局结果 —— 数子与双停补分共用同一种格式(正数黑领先)。返回 `(result, winner_color)`。
        `game.end_result` 读的是 `current_node.end_state`,所以写在节点上才算数。"""
        if score >= 0:
            result, winner_color = f"B+{abs(score):.1f}", "B"
        else:
            result, winner_color = f"W+{abs(score):.1f}", "W"
        session.katrain.game.game_result = result
        session.katrain.game.current_node.end_state = result
        session.game_ended = True
        return result, winner_color
```

```python
        result, winner_color = _apply_counted_result(session, score)
```

② `_complete_count` 函数结束之后(`@app.post("/api/count/request")` 之前)加:

```python
    async def _score_two_pass_end(session):
        """双方各停一手结束、还没有胜负的局:补一次分析,按数子的格式写上结果。返回写上的结果,没写返回 None。

        只管「双停」—— 认输 / 超时 / 数子已经把结果写在 `end_state` 上了。升降级局不补(`analysis_allowed` 为假,
        interface 的 `ensure_current_score` 也不补),照旧记「无结论」;升降级怎么判目等 Fan 拍板(PRD §4 A12-R)。"""
        game = getattr(session.katrain, "game", None)
        if game is None or not game.end_result or game.current_node.end_state:
            return None
        if not getattr(session.katrain, "analysis_allowed", False):
            return None
        node = game.current_node
        score = await asyncio.to_thread(session.katrain.ensure_current_score)
        if score is None:
            return None
        with session.lock:
            if session.katrain.game is not game or game.current_node is not node or node.end_state:
                return None  # 等分析的这几秒里局面变了(新开局 / 悔棋),这份分数不属于它
            result, _ = _apply_counted_result(session, score)
            session.last_state = session.katrain.get_state()
        session.katrain.update_state()  # 推给前端:结果从「终局」变成「黑+3.5」
        return result

    async def _finish_ended_game(session, app, current_user):
        """对局结束后的收尾 —— 人发出的请求(`/api/move`)和 AI 后台线程(`manager.on_game_ended`)共用这一个函数(N22)。

        顺序是承重的:**先补分,再落账**。`_record_ai_game` 落过一次就置 `_recorded`,之后补出的分数进不了账;
        所以两条路在 `end_game_lock` 下串行,且都先走补分。
        多人局 / 跨平台局在各自端点里落账并广播 `game_end`,不走这里;研究模式里按出的双停不是「下完了一局」(PRD N22 验收 3)。
        游客局照样补分出胜负,只是不落账。"""
        if session.player_b_id is not None or session.player_w_id is not None:
            return
        if getattr(session, "mode", "play") == "research":
            return
        lock = getattr(session, "end_game_lock", None)
        if not isinstance(lock, asyncio.Lock):
            lock = asyncio.Lock()
            session.end_game_lock = lock
        async with lock:
            scored = await _score_two_pass_end(session)
            result = scored or getattr(session.katrain.game, "end_result", None)
            if result and current_user is not None and session.user_id is not None:
                await _record_ai_game(session, app, current_user, result)

    globals()["_FINISH_ENDED_GAME_FN"] = _finish_ended_game

    async def _on_game_ended_off_request(session):
        """AI 后台线程让对局结束时没有请求可取 `current_user`,按会话主人从库里取(盒上是本机影子用户)。"""
        user = None
        if session.user_id is not None:
            repo = getattr(app.state, "user_repo", None)
            user_dict = repo.get_user_by_id(session.user_id) if repo is not None else None
            user = User(**user_dict) if user_dict else None
        await _finish_ended_game(session, app, user)

    manager.on_game_ended = _on_game_ended_off_request
```

③ `/api/move` 末尾(`:996-1003`)

```python
        # Natural (two-pass) game end never hits resign/count/timeout — record here so
        # local face-to-face games ending by both passing are still saved (end_result
        # auto-becomes truthy on two consecutive passes; requestCount then refuses).
        is_multiplayer = session.player_b_id is not None or session.player_w_id is not None
        if state.get("end_result") and not is_multiplayer and current_user and session.user_id:
            await _record_ai_game(session, app, current_user, state["end_result"])
        return {"session_id": session.session_id, "state": state}
```

替换为

```python
        # 自然终局(双停)不经过认输 / 数子 / 超时,在这里收尾:先补分出胜负,再落账(N22)。
        # AI 线程下出双停第二手时走的是 `manager.on_game_ended`,两条路是同一个函数、会话内串行。
        if state.get("end_result"):
            await _finish_ended_game(session, app, current_user)
            state = session.katrain.get_state()
            session.last_state = state
        return {"session_id": session.session_id, "state": state}
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
uv run black -l 120 katrain/web/interface.py katrain/web/session.py katrain/web/server.py tests/web_ui/test_game_end_hook.py tests/test_play_ai_endgame.py
# 根目录(真 WebKaTrain)与 tests/web_ui 分两条跑 —— 见 Global Constraints
CI=true uv run pytest tests/test_play_ai_endgame.py tests/test_local_play_recording.py tests/test_guest_free_play.py tests/web/test_session_cleanup_does_not_block.py -q
CI=true uv run pytest tests/web_ui/test_game_end_hook.py tests/web_ui/test_play_ai_endgame_api.py tests/web_ui/test_count_api.py tests/web_ui/test_ai_game_autosave.py \
  tests/web_ui/test_ai_ladder_api.py tests/web_ui/test_game_termination_and_chat_identity.py tests/web_ui/test_ladder_injection.py -q
git status --short katrain/config.json   # 期望:空
```
Expected: 全 PASS。`test_ai_ladder_api.py` 里 `test_ranked_session_still_allows_human_move_and_pass`、`test_ranked_natural_result_saves_once_then_settles_once` 必须仍绿 —— 它们守的是升降级账本只落一次。

- [ ] **Step 5: 基线 diff(全量后端)后提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
# Task 0 Step 4 的写法,期望 comm -13 无输出
git add katrain/web/interface.py katrain/web/session.py katrain/web/server.py tests/web_ui/test_game_end_hook.py tests/test_play_ai_endgame.py
git diff --cached --stat
git commit -m "fix(play): AI 收尾的局不落账、升降级不结算;双停只有「终局」没有胜负 —— 终局收尾合成一个函数

N22(P1)。AI 线程下出双停第二手或认输时只置 game_ended、不落账;AI 线程新增 game_ended_callback →
SessionManager.on_game_ended,与 /api/move 共用 _finish_ended_game:会话内串行,先补分(非升降级)再落账,每局一次。账本代码未改。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```
**必须上板**(记进 Task 12 清单):自由对弈人先停、AI 跟停 → 屏上出现胜负、「全部对局」里有这一局;升降级局双停后「继续」按钮消失、能开下一局。

---

### Task 6: A18 玩家卡倒计时 / 读秒 / 到点判超时

**Files:**
- Modify: `katrain/web/interface.py:205`(`__init__` 加 `timer_configured`)、`update_config`(`timer/` 分支)、`get_state` 的 `"timer"` 字典(`:593-599`)
- Modify: `katrain/web/ui/src/api.ts:63-75`(`timer` 类型加 `configured?: boolean`)—— **共享领地**
- Create: `katrain/web/ui/src/kiosk/components/game/goClock.ts`、`goClock.test.ts`、`GameControlPanel.playAi.test.tsx`
- Create: `katrain/web/ui/tests/kiosk-screen-05-play-ai.spec.ts`
- Modify: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx`(import、Props、`clockFor` 注释、两处 `<PlayerRow>` 换成 `<SeatRow>`)
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`(`handleClockExpired` 与传参)
- Test: `tests/test_play_ai_endgame.py`、`katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx`(追加)

**Interfaces:**
- Consumes: Task 2 的 `_game_already_ended` 守卫(超时后 AI 着法不复活);Task 1 测试文件的 `sessionMock` / `makeState` / `seat`
- Produces:
  - `get_state()["timer"]["configured"]: bool`;TS `GameState['timer']['configured']?: boolean`
  - `goClock.ts`:`interface GoClockReading { mainLeft: number; byoLeft: number | null; periodsLeft: number; expired: boolean }`、
    `readGoClock(input: GoClockInput): GoClockReading`、`isTimedGame(timer: GameState['timer']): boolean`、
    `useGoClock(gameState: GameState, color: 'B' | 'W', onExpired?: () => void): GoClockReading | null`
  - `GameControlPanel` 新 prop `onTimeout?: (color: 'B' | 'W') => void`(Task 9 同文件继续改)
  - `tests/kiosk-screen-05-play-ai.spec.ts` 的 `open(page, state)` / `baseState(over)` / `seat()` 供 Task 9 追加

- [ ] **Step 1: 后端判别位(测试 → 实现)**

追加到 `tests/test_play_ai_endgame.py` 末尾:

```python
# ---------------------------------------------------------------- A18 计时判别位


def test_timer_is_configured_only_after_a_setup_wrote_it():
    """星阵人机 / 大厅房间局没人设过时限,却继承 config.json 默认的 20 分 + 30 秒×5 且不暂停;
    前端必须能分出「这局的时限是开局设置定的」,否则星阵局会凭空倒计时、20 分钟后自己判负。"""
    w = _web_katrain()
    assert w.get_state()["timer"]["configured"] is False
    w.update_config("timer/main_time", 5)
    assert w.get_state()["timer"]["configured"] is True
```

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-play-ai && CI=true uv run pytest tests/test_play_ai_endgame.py -q -k timer_is_configured` → Expected: FAIL(`KeyError: 'configured'`)。

实现 —— `interface.py` `__init__` 里 `self.timer_paused = True` 之后加:

```python
        # A18:这一局的时限是不是**开局设置**写的(`/api/game/setup`、升降级 `/start` 都经 update_config("timer/…"))。
        # 没写过的局(星阵人机、大厅房间)继承 config.json 默认时限且不暂停,前端不许把它当计时局。
        self.timer_configured = False
```

`update_config` 里 `if setting == "timer/paused":` 之前加:

```python
        if setting.startswith("timer/"):
            self.timer_configured = True
```

`get_state` 的 `"timer": {` 字典里 `"settings": self.active_game_timer,` 之后加一行 `"configured": bool(getattr(self, "timer_configured", False)),`。

Run 同上 → Expected: PASS;`git status --short katrain/config.json` 为空。

- [ ] **Step 2: 计时纯函数(测试 → 实现)**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
for f in src/kiosk/components/game/goClock.ts src/kiosk/components/game/goClock.test.ts src/kiosk/components/game/GameControlPanel.playAi.test.tsx tests/kiosk-screen-05-play-ai.spec.ts; do git ls-files "$f"; ls "$f" 2>/dev/null; done   # 期望:无输出
```

`src/kiosk/components/game/goClock.test.ts`:

```ts
import { describe, expect, test } from 'vitest';
import { readGoClock, type GoClockInput } from './goClock';

const input = (over: Partial<GoClockInput> = {}): GoClockInput => ({
  mainTimeMin: 5, byoLength: 30, byoPeriods: 3, mainUsed: 0, periodsUsed: 0, nodeTimeUsed: 0, active: true, elapsed: 0, ...over,
});

describe('readGoClock —— 与 interface.py update_timer 同一套算法', () => {
  test('主时间里:只扣主时间,读秒还没开始', () => {
    expect(readGoClock(input({ mainUsed: 100, elapsed: 20 }))).toEqual({ mainLeft: 180, byoLeft: null, periodsLeft: 3, expired: false });
  });

  test('不轮到的一方不外推本地流逝', () => {
    expect(readGoClock(input({ mainUsed: 100, elapsed: 20, active: false })).mainLeft).toBe(200);
  });

  test('主时间在这一手里用完:超出的部分才进读秒', () => {
    // 这一手开始时还剩 10 秒主时间,已经想了 25 秒 ⇒ 读秒用掉 15 秒
    expect(readGoClock(input({ mainUsed: 290, elapsed: 25 }))).toEqual({ mainLeft: 0, byoLeft: 15, periodsLeft: 3, expired: false });
  });

  test('每满一次读秒长度记一次,次数用完即超时', () => {
    expect(readGoClock(input({ mainTimeMin: 0, elapsed: 65 }))).toEqual({ mainLeft: 0, byoLeft: 25, periodsLeft: 1, expired: false });
    expect(readGoClock(input({ mainTimeMin: 0, elapsed: 91 })).expired).toBe(true);
  });

  test('只有主时间、没有读秒:主时间用完即超时', () => {
    expect(readGoClock(input({ byoLength: 0, byoPeriods: 0, mainUsed: 300 })).expired).toBe(true);
  });
});
```

Run: `npx vitest run src/kiosk/components/game/goClock.test.ts` → Expected: FAIL(`Failed to resolve import "./goClock"`)。

`src/kiosk/components/game/goClock.ts`:

```ts
import { useEffect, useRef, useState } from 'react';
import type { GameState } from '../../../api';

/**
 * 对局屏玩家卡的时钟(A18)。
 *
 * 算法与服务端 `interface.py` `update_timer` 一致:主时间先扣;扣完之后,**这一手**里超出主时间的部分才进读秒,
 * 每满一次读秒长度记一次;次数用完即超时。服务端只在换手时结算,两次推送之间由这里按本地流逝时间外推
 * (galaxy `components/PlayerCard.tsx` 同一套 —— 那个文件是 galaxy 的 MUI 卡,kiosk 不引它,只对齐算法)。
 * 已知局限:刷新页面会把「这一手已想了多久」清零(服务端不在手中途结算),与 galaxy 相同。
 */
export interface GoClockReading {
  /** 主时间还剩几秒;用完或没有主时间时为 0。 */
  mainLeft: number;
  /** 本次读秒还剩几秒;还在主时间里时为 null。 */
  byoLeft: number | null;
  /** 还剩几次读秒。 */
  periodsLeft: number;
  expired: boolean;
}

export interface GoClockInput {
  /** 主时间,**分钟**(与 `timer.settings.main_time`、开局设置 `TIME_PRESETS` 同单位)。 */
  mainTimeMin: number;
  byoLength: number;
  byoPeriods: number;
  mainUsed: number;
  periodsUsed: number;
  /** 当前这一手已记的秒数(`timer.current_node_time_used`);只对轮到的一方有意义。 */
  nodeTimeUsed: number;
  active: boolean;
  /** 上一次计时基准变化之后本地流逝的秒数。 */
  elapsed: number;
}

export function readGoClock(i: GoClockInput): GoClockReading {
  const extra = i.active ? i.elapsed : 0;
  const mainTotal = Math.max(0, i.mainTimeMin) * 60;
  const periodsTotal = Math.max(0, i.byoPeriods);
  const mainLeft = Math.max(0, mainTotal - (i.mainUsed + extra));
  if (mainLeft > 0) {
    return { mainLeft, byoLeft: null, periodsLeft: Math.max(0, periodsTotal - i.periodsUsed), expired: false };
  }
  const byoLen = Math.max(0, i.byoLength);
  const mainAvailableAtNodeStart = Math.max(0, mainTotal - i.mainUsed);
  let overflow = Math.max(0, (i.active ? i.nodeTimeUsed : 0) + extra - mainAvailableAtNodeStart);
  let periodsUsed = i.periodsUsed;
  while (byoLen > 0 && overflow > byoLen && periodsUsed < periodsTotal) {
    overflow -= byoLen;
    periodsUsed += 1;
  }
  const periodsLeft = Math.max(0, periodsTotal - periodsUsed);
  if (byoLen <= 0 || periodsLeft <= 0) return { mainLeft: 0, byoLeft: 0, periodsLeft: 0, expired: true };
  return { mainLeft: 0, byoLeft: Math.max(0, byoLen - overflow), periodsLeft, expired: false };
}

/**
 * 这一局计不计时。**两段都要**:服务端说时限是开局设置写的(`configured`),且主时间或读秒至少一样非零。
 * 只看 `settings` 会把星阵 / 大厅局继承的默认「20 分 + 30 秒×5」当成真时限。
 */
export function isTimedGame(timer: GameState['timer']): boolean {
  const s = timer?.settings;
  return timer?.configured === true && !!s && (s.main_time > 0 || s.byo_length > 0);
}

const TICK_MS = 250;

/** 一方的时钟读数;不计时的局返回 null。轮到的一方耗尽时调一次 `onExpired`(由假变真那一刻)。 */
export function useGoClock(gameState: GameState, color: 'B' | 'W', onExpired?: () => void): GoClockReading | null {
  const timer = gameState.timer;
  const timed = isTimedGame(timer);
  const active = timed && timer?.paused === false && !gameState.end_result && gameState.player_to_move === color;
  const info = gameState.players_info[color];
  // 计时基准:服务端最近一次给的量。任何一个变了(换手、结算),本地流逝就从 0 重新数。
  const baseKey = `${active}|${info.main_time_used}|${info.periods_used}|${timer?.current_node_time_used ?? 0}|${gameState.current_node_id}`;
  const [tick, setTick] = useState({ key: baseKey, elapsed: 0 });

  useEffect(() => {
    if (!active) return undefined;
    const startedAt = Date.now();
    const id = window.setInterval(() => setTick({ key: baseKey, elapsed: (Date.now() - startedAt) / 1000 }), TICK_MS);
    return () => window.clearInterval(id);
  }, [active, baseKey]);

  const elapsed = tick.key === baseKey ? tick.elapsed : 0;
  const reading = timed && timer
    ? readGoClock({
      mainTimeMin: timer.settings.main_time,
      byoLength: timer.settings.byo_length,
      byoPeriods: timer.settings.byo_periods,
      mainUsed: info.main_time_used,
      periodsUsed: info.periods_used,
      nodeTimeUsed: timer.current_node_time_used,
      active,
      elapsed,
    })
    : null;

  const expired = active && !!reading?.expired;
  const onExpiredRef = useRef(onExpired);
  useEffect(() => { onExpiredRef.current = onExpired; }, [onExpired]);
  useEffect(() => { if (expired) onExpiredRef.current?.(); }, [expired]);
  return reading;
}
```

`api.ts` 的 `timer?: { … settings: {…}; };` 里 `settings` 之后加:

```ts
    /** 这一局的时限是开局设置写的(服务端 `timer_configured`)。星阵 / 大厅局没有,别把它们当计时局。 */
    configured?: boolean;
```

Run: `npx vitest run src/kiosk/components/game/goClock.test.ts` → Expected: 5 条 PASS。

- [ ] **Step 3: 玩家卡接时钟(测试 → 实现)**

`src/kiosk/components/game/GameControlPanel.playAi.test.tsx`:

```tsx
import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import GameControlPanel from './GameControlPanel';
import type { GameState } from '../../../api';

/** 对弈·AI/升降级赛道的右栏行为测试。只证 DOM 结构与文案;几何在 tests/kiosk-screen-05-play-ai.spec.ts。 */

const seat = (type: string, name: string, over: Record<string, number> = {}) => ({
  player_type: type, player_subtype: '', name, calculated_rank: null, periods_used: 0, main_time_used: 0, ...over,
});

const base = (over: Partial<GameState> = {}): GameState => ({
  game_id: 'g', board_size: [19, 19], komi: 7.5, handicap: 0, ruleset: 'chinese',
  current_node_id: 7, current_node_index: 7, history: [{ node_id: 0, score: null, winrate: null }],
  player_to_move: 'B', stones: [], last_move: null, prisoner_count: { B: 0, W: 0 }, analysis: null, commentary: '',
  is_root: false, is_pass: false, end_result: null, children: [], ghost_stones: [], note: '',
  game_type: 'free', count_min_moves: 100,
  ui_state: {
    show_children: false, show_dots: false, show_hints: false, show_policy: false,
    show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false,
  },
  players_info: { B: seat('player:human', '我'), W: seat('player:ai', 'KataGo') },
  ...over,
} as GameState);

const timer = (settings: { main_time: number; byo_length: number; byo_periods: number }, configured = true) => ({
  paused: false, main_time_used: 0, current_node_time_used: 0, next_player_periods_used: 0, configured,
  settings: { minimal_use: 0, sound: false, ...settings },
});

const panel = (gs: GameState, props: Record<string, unknown> = {}) => render(
  <GameControlPanel
    gameState={gs}
    onAction={() => {}}
    onNavigate={() => {}}
    analysisToggles={{}}
    onToggleAnalysis={() => {}}
    {...props}
  />,
);

const clockOf = (color: 'B' | 'W') => {
  const card = screen.getByTestId(`player-card-${color}`);
  return { value: card.querySelector('.clock b')?.textContent, label: card.querySelector('.clock span')?.textContent };
};

describe('A18 · 玩家卡时钟', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  test('主时间阶段:两张卡都写剩余,只有轮到的一方在走', () => {
    panel(base({
      timer: timer({ main_time: 5, byo_length: 30, byo_periods: 3 }),
      players_info: { B: seat('player:human', '我', { main_time_used: 12 }), W: seat('player:ai', 'KataGo', { main_time_used: 30 }) },
    }));
    expect(clockOf('B')).toEqual({ value: '4:48', label: '剩余' });
    expect(clockOf('W')).toEqual({ value: '4:30', label: '剩余' });
    act(() => { vi.advanceTimersByTime(2000); });
    expect(clockOf('B').value).toBe('4:46');
    expect(clockOf('W').value).toBe('4:30');
  });

  test('仅读秒:写本次读秒剩余与剩几次', () => {
    panel(base({
      timer: timer({ main_time: 0, byo_length: 30, byo_periods: 3 }),
      players_info: { B: seat('player:human', '我', { periods_used: 1 }), W: seat('player:ai', 'KataGo') },
    }));
    expect(clockOf('B')).toEqual({ value: '0:30', label: '读秒 · 剩 2 次' });
    expect(clockOf('W')).toEqual({ value: '0:30', label: '读秒 · 剩 3 次' });
  });

  test('耗尽:写「超时」,并对轮到的那一方回调一次 onTimeout', () => {
    const onTimeout = vi.fn();
    panel(base({ timer: timer({ main_time: 0, byo_length: 30, byo_periods: 1 }) }), { onTimeout });
    act(() => { vi.advanceTimersByTime(31_000); });
    expect(clockOf('B')).toEqual({ value: '0:00', label: '超时' });
    expect(onTimeout).toHaveBeenCalledTimes(1);
    expect(onTimeout).toHaveBeenCalledWith('B');
  });

  test('没配过时限的局(星阵 / 大厅)不倒计时,仍写「第 N 手 · 不限时」', () => {
    panel(base({ timer: timer({ main_time: 20, byo_length: 30, byo_periods: 5 }, false) }));
    expect(clockOf('B')).toEqual({ value: '第 8 手', label: '不限时' });
  });
});
```

Run: `npx vitest run src/kiosk/components/game/GameControlPanel.playAi.test.tsx` → Expected: 前三条 FAIL(时钟仍是「第 8 手 · 不限时」),第四条 PASS。

实现 —— `GameControlPanel.tsx`:

1. 第 1 行改为 `import { useCallback, useEffect, useRef } from 'react';`,并在 import 区加 `import { useGoClock } from './goClock';`。
2. `Props` 里 `hardwareFault?: string | null;` 之后加:

```tsx
  /**
   * A18:轮到的一方时间耗尽。GamePage 决定发不发 `/api/timeout`(升降级 AI 回合、引擎停摆时不发)。
   * 只在开局设置配过时限的局里会被调用(`timer.configured`)。
   */
  onTimeout?: (color: 'B' | 'W') => void;
```

3. 组件参数解构里加上 `onTimeout`(接在 `hardwareFault = null,` 之后)。
4. `formatTime` 之后、`PlayerRow` 之前加:

```tsx
/**
 * 一方的玩家卡 + 时钟(A18)。时钟跟着本地时间走,所以 hook 挂在每张卡自己身上 ——
 * 放在父组件里算,每 250ms 一次的重渲会把胜率图、棋谱一起带着重画。
 */
function SeatRow({ gameState, color, turn, state, untimed, lang, t, onTimeout }: {
  gameState: GameState;
  color: 'B' | 'W';
  turn: boolean;
  state: string;
  /** 这一局不计时时那一格写什么(原来的「第 N 手 · 不限时」/「本局已下」)。 */
  untimed: { value: string; label: string } | null;
  lang: string;
  t: (key: string, fallback?: string) => string;
  onTimeout?: (color: 'B' | 'W') => void;
}) {
  const onExpired = useCallback(() => onTimeout?.(color), [onTimeout, color]);
  const reading = useGoClock(gameState, color, onExpired);
  const clock = reading === null ? untimed
    : reading.expired ? { value: '0:00', label: t('game:time_up', '超时') }
    : reading.byoLeft === null ? { value: formatTime(reading.mainLeft), label: t('game:time_left', '剩余') }
    : {
      value: formatTime(reading.byoLeft),
      label: t('game:byo_left', '读秒 · 剩 {n} 次').replace('{n}', String(reading.periodsLeft)),
    };
  return (
    <PlayerRow
      color={color} info={gameState.players_info[color]} captures={gameState.prisoner_count[color]}
      turn={turn} state={state} clock={clock} lang={lang} t={t}
    />
  );
}
```

5. `clockFor` 上面那段注释开头的「kiosk 的局**不设时限**(开局设置里没有时间控件)」改为
   「**不计时的局**(开局选了「不限时」,或星阵 / 大厅这类没配过时限的局 —— 计时局由 `SeatRow` 的 `useGoClock` 接管)」,其余不动。
6. 返回值里两处 `<PlayerRow color="W" …/>`、`<PlayerRow color="B" …/>` 换成:

```tsx
      <SeatRow
        gameState={gameState} color="W" turn={toMove === 'W' && !isGameOver} state={stateWord('W')}
        untimed={clockFor('W')} lang={lang} t={t} onTimeout={onTimeout}
      />
      <SeatRow
        gameState={gameState} color="B" turn={toMove === 'B' && !isGameOver} state={stateWord('B')}
        untimed={clockFor('B')} lang={lang} t={t} onTimeout={onTimeout}
      />
```

Run: `npx vitest run src/kiosk/components/game/GameControlPanel.playAi.test.tsx src/kiosk/components/game/GameControlPanel.test.tsx` → Expected: 全 PASS。

- [ ] **Step 4: GamePage 发超时(测试 → 实现)**

追加到 `src/kiosk/pages/GamePage.playAi.test.tsx` 末尾:

```tsx
describe('A18 · 时间耗尽判超时', () => {
  it('轮到的一方耗尽 → 调一次 timeout,同一手不重复', () => {
    sessionMock.gameState = makeState({ player_to_move: 'B' });
    renderPage();
    fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
    fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
    expect(sessionMock.handleAction).toHaveBeenCalledTimes(1);
    expect(sessionMock.handleAction).toHaveBeenCalledWith('timeout');
  });

  it('升降级局 AI 回合耗尽不发(服务端在 AI 回合回 403)', () => {
    sessionMock.gameState = makeState({
      game_type: 'ai_ladder_ranked', player_to_move: 'B',
      players_info: { B: seat('player:ai', 'AI'), W: seat('player:human', '我') },
    });
    renderPage();
    fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
    expect(sessionMock.handleAction).not.toHaveBeenCalled();
  });

  it('升降级引擎停摆时不判超时 —— 那是一局没人下的棋', () => {
    sessionMock.gameState = makeState({ player_to_move: 'B', last_ladder_error: true });
    renderPage();
    fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
    expect(sessionMock.handleAction).not.toHaveBeenCalled();
  });
});
```

Run: `npx vitest run src/kiosk/pages/GamePage.playAi.test.tsx` → Expected: 第一条 FAIL(没调用),后两条 PASS(现状本来就不发)。

实现 —— `GamePage.tsx` 状态声明区(`countingRef` 之后)加:

```tsx
  // A18:同一手只发一次超时 —— 时钟每 250ms 重算一次,耗尽之后的每一帧都「耗尽」。
  const timeoutSentForNodeRef = useRef<number | null>(null);
```

`const humanColor = deriveHumanColor(gameState);` 之后(Task 2 加的 `bothHuman` 那段之前)加:

```tsx
  // A18:轮到的一方时间耗尽 → 判超时负。服务端不自己判(`/api/timeout` 由客户端触发),kiosk 从前一处都没调。
  const handleClockExpired = (color: 'B' | 'W') => {
    if (gameState.end_result || gameState.player_to_move !== color) return;
    // 升降级 AI 停摆时它的钟照样走完;判它超时负 = 把一局没人下的棋记成人赢(galaxy GamePage `handleTimeout` 同一条)。
    if (gameState.last_ladder_error) return;
    // 升降级局的超时只许在人的回合发(`guard_ai_ladder_ranked_human_action` 在 AI 回合回 403)。
    if (isRanked && humanColor !== color) return;
    if (timeoutSentForNodeRef.current === gameState.current_node_id) return;
    timeoutSentForNodeRef.current = gameState.current_node_id;
    void session.handleAction('timeout').catch(() => undefined);
  };
```

`<GameControlPanel … hardwareFault={hardwareFault} />` 里加一个 prop `onTimeout={handleClockExpired}`。

Run: `npx vitest run src/kiosk/pages/GamePage.playAi.test.tsx src/kiosk/pages/GamePage.test.tsx` → Expected: 全 PASS。

- [ ] **Step 5: 真实运行时证据(Playwright,打构建产物)**

`katrain/web/ui/tests/kiosk-screen-05-play-ai.spec.ts`:

```ts
import { expect, test, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * 对弈·AI/升降级赛道(superpowers/tracks/kiosk-go-play-ai)的真浏览器实测,1024×600,打构建产物。
 * 只放 jsdom 作不了证的东西:时钟真的在走、右栏承重链(Task 9 追加)。
 * 不改 kiosk-screen-05-game.spec.ts —— 那个文件跨平台赛道也在改。
 */
test.use({ viewport: { width: 1024, height: 600 } });

const SHOTS = resolve(process.cwd(), '../../../superpowers/tracks/kiosk-go-play-ai/visual');
mkdirSync(SHOTS, { recursive: true });

const seat = (name: string, type: string, over: Record<string, number> = {}) => ({
  player_type: type, player_subtype: '', name, calculated_rank: -4, periods_used: 0, main_time_used: 0, ...over,
});

const baseState = (over: Record<string, unknown> = {}) => ({
  game_id: 'play-ai', board_size: [19, 19], komi: 7.5, handicap: 0, ruleset: 'chinese',
  game_type: 'free', count_min_moves: 100, current_node_id: 0, current_node_index: 0,
  history: [{ node_id: 0, score: null, winrate: null, move: null, player: null }],
  player_to_move: 'B', stones: [], last_move: null, prisoner_count: { B: 0, W: 0 },
  analysis: null, commentary: '', is_root: true, is_pass: false, end_result: null, children: [], ghost_stones: [],
  players_info: { B: seat('访客（你）', 'player:human'), W: seat('KataGo', 'player:ai') },
  note: '',
  ui_state: {
    show_children: false, show_dots: false, show_hints: false, show_policy: false,
    show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false,
  },
  ...over,
});

const open = async (page: Page, state: Record<string, unknown>) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'play-ai');
    localStorage.setItem('katrain_language', 'cn');
  });
  // 造的 token 是假的,不接住 WS 屏上会盖一条「实时连接被拒绝」(那一态归 kiosk-screen-05-game.spec.ts 量)
  await page.routeWebSocket('**/ws/**', () => { /* 连上就行,不推任何东西 */ });
  await page.route('**/api/state**', (route) => route.fulfill({ json: { state } }));
  await page.route('**/api/analysis/current', (route) => route.fulfill({ json: { state } }));
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') return route.fulfill({ json: { id: 1, username: '访客', rank: '5段', credits: 0 } });
    if (path === '/api/v1/vision/status') {
      return route.fulfill({ json: { enabled: false, camera_connected: false, pose_locked: false,
        sync_state: 'unbound', recognition_ready: false, led_connected: null, bound_session_id: null } });
    }
    if (path === '/api/v1/geometry/status') return route.fulfill({ status: 404, json: { detail: 'geometry disabled' } });
    return route.fulfill({ json: {} });
  });
  await page.goto('/kiosk/play/ai/game/play-ai');
  await page.waitForSelector('[data-testid="game-board"] canvas');
};

test('A18 计时局:轮到的一方时钟真的在走,另一方停着,时钟格没被玩家卡裁掉', async ({ page }) => {
  await open(page, baseState({
    timer: {
      paused: false, main_time_used: 12, current_node_time_used: 0, next_player_periods_used: 0, configured: true,
      settings: { main_time: 5, byo_length: 30, byo_periods: 3, minimal_use: 0, sound: false },
    },
    players_info: {
      B: seat('访客（你）', 'player:human', { main_time_used: 12 }),
      W: seat('KataGo', 'player:ai', { main_time_used: 30 }),
    },
  }));
  const clock = (c: 'B' | 'W') => page.locator(`[data-testid="player-card-${c}"] .clock b`);
  await expect(page.locator('[data-testid="player-card-B"] .clock span')).toHaveText('剩余');
  const b0 = await clock('B').textContent();
  const w0 = await clock('W').textContent();
  await expect.poll(() => clock('B').textContent(), { timeout: 3000, message: '轮到的一方时钟没在走' }).not.toBe(b0);
  expect(await clock('W').textContent(), '没轮到的一方时钟在走').toBe(w0);

  const g = await page.evaluate(() => {
    const card = document.querySelector('[data-testid="player-card-B"]')!.getBoundingClientRect();
    const c = document.querySelector('[data-testid="player-card-B"] .clock')!.getBoundingClientRect();
    return { cardRight: Math.round(card.right), clockRight: Math.round(c.right) };
  });
  expect(g.clockRight, '时钟格溢出了玩家卡').toBeLessThanOrEqual(g.cardRight);
  await page.screenshot({ path: `${SHOTS}/a18-timed-game-1024x600.png` });
});
```

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npm run build
cp ~/.katrain/config.json /tmp/kgpa-katrain-config.json 2>/dev/null || true
lsof -nP -iTCP:8002 -sTCP:LISTEN   # 若被别的 worktree 占着,先协调,不要杀
npx playwright test tests/kiosk-screen-05-play-ai.spec.ts
cp /tmp/kgpa-katrain-config.json ~/.katrain/config.json 2>/dev/null || true
```
Expected: 1 passed;截图 `superpowers/tracks/kiosk-go-play-ai/visual/a18-timed-game-1024x600.png` 生成。**交 Fan 单图确认**(稿子没有计时态参考图)。

- [ ] **Step 6: 两套构建 + 四图 + 提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npx tsc -b && echo TSC_OK
npx eslint src/kiosk/components/game/goClock.ts src/kiosk/components/game/GameControlPanel.tsx src/kiosk/pages/GamePage.tsx src/api.ts
npm run build && npm run build:kiosk-2d          # api.ts 是共享领地:两套都要绿
lsof -nP -iTCP:5173 -sTCP:LISTEN
npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-05-game.fourup.spec.ts   # 只跑屏 05;`npm run fourup` 会跑全部 27 屏
git -C /Users/fan/Repositories/katrain-kiosk-go-play-ai status --short superpowers/tracks/kiosk-go-shell-align/visual/05-game
```
Expected: `TSC_OK`;两套构建绿;屏 05 的 fixture 没有 `timer` ⇒ 右栏时钟格文案不变,四图应只有抖动级差异(`<canvas>` 盘,地板约 4500 像素)——
跑第二次 diff 两次结果确认是抖动,**不提交**这一屏的图(`git checkout HEAD -- superpowers/tracks/kiosk-go-shell-align/visual/05-game`,之前先确认该目录没有你要留的未提交改动)。

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
# 基线 diff(后端 + 前端),期望 comm -13 无输出
git add katrain/web/interface.py katrain/web/ui/src/api.ts katrain/web/ui/src/kiosk/components/game/goClock.ts \
  katrain/web/ui/src/kiosk/components/game/goClock.test.ts katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx \
  katrain/web/ui/src/kiosk/components/game/GameControlPanel.playAi.test.tsx katrain/web/ui/src/kiosk/pages/GamePage.tsx \
  katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx katrain/web/ui/tests/kiosk-screen-05-play-ai.spec.ts \
  tests/test_play_ai_endgame.py superpowers/tracks/kiosk-go-play-ai/visual/a18-timed-game-1024x600.png
git diff --cached --stat
git commit -m "feat(kiosk): 开局选了用时,对局屏却不倒计时、不读秒、到点不判负 —— 玩家卡接上时钟

A18(P1)。08-22 重画屏 05 时按「kiosk 没有时间控件」的错误前提撤了计时。服务端新增 timer.configured
(星阵 / 大厅局继承默认时限但没人配过,不能当计时局);玩家卡按 update_timer 同一算法外推剩余与读秒,
轮到的一方耗尽调 /api/timeout(升降级 AI 回合与引擎停摆时不发)。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```
**必须上板**(记进 Task 12 清单):RK3562 上一局「仅读秒 30秒×3」让读秒走完,确认判负且结果落账。

---

### Task 7: A3 「实地」「厚势」开局 500;五个策略各有一句核过实现的说明

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx:32-46`(`AI_STRATEGY_HINT` 与其注释)、`:506-512`(策略选项的 `value`)
- Test: `katrain/web/ui/src/kiosk/pages/AiSetupPage.test.tsx`(**文件末尾追加一个顶层 `describe`**,复用文件里既有的桩 `gameSetup` / `renderPage`)

**Interfaces:**
- Consumes: 既有 `/api/game/setup`(`ai_strategy` 原样交给 `update_player(player_subtype=…)`,再由 `core/ai.py` `STRATEGY_REGISTRY` 与 `ai_rank_estimation` 查表)
- Produces: 开局设置送出的策略 id 集合 = `ai:human` / `ai:default` / `ai:p:territory` / `ai:p:influence` / `ai:policy`(全部是 `core/constants.py` 里真实存在的 id)

- [ ] **Step 1: 写失败的测试(追加到 `AiSetupPage.test.tsx` 末尾)**

```tsx
// ── A3 · AI 策略(kiosk-go-play-ai)──────────────────────────────────────────
// 2026-09-14 本机复现:「实地」「厚势」送的是 `ai:territory` / `ai:influence`,真实 id 是
// `ai:p:territory` / `ai:p:influence`(core/constants.py:50-51)。`update_player` → `ai_rank_estimation`
// → `AI_STRENGTH['ai:territory']` 抛 KeyError,开局 500。
describe('A3 · AI 策略', () => {
  beforeEach(() => {
    localStorage.removeItem(PLAY_ON_BOARD_KEY);
    createSession.mockClear();
    gameSetup.mockClear();
    mockNavigate.mockReset();
  });

  it.each([
    ['实地', 'ai:p:territory'],
    ['厚势', 'ai:p:influence'],
  ])('选「%s」开局,送出的是真实策略 id %s', async (name, id) => {
    renderPage('free');
    const user = userEvent.setup();
    await user.click(within(screen.getByTestId('setup-strategy')).getByRole('button', { name }));
    await user.click(screen.getByRole('button', { name: /开始对局|开始计分局/i }));
    await waitFor(() => expect(gameSetup).toHaveBeenCalledWith('s1', 'free', expect.objectContaining({ ai_strategy: id })));
  });

  it.each([
    ['拟人', '拟人:按所选棋力下出该水平的棋,包括那个水平会犯的错'],
    ['KataGo', 'KataGo:每手都下引擎搜索后的第一选择,不放水'],
    ['实地', '实地:偏爱三线及以下的低位,在随机抽出的一批候选里按这个偏好挑,不是全力'],
    ['厚势', '厚势:偏爱四线及以上的高位,在随机抽出的一批候选里按这个偏好挑,不是全力'],
    ['策略', '策略:不看搜索结果,直接下策略网络的第一直觉;开局前 22 手随机一些'],
  ])('选中「%s」时说明行说它真在干什么', async (name, hint) => {
    renderPage('free');
    const user = userEvent.setup();
    await user.click(within(screen.getByTestId('setup-strategy')).getByRole('button', { name }));
    expect(screen.getByText(hint)).toBeInTheDocument();
  });
});
```

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui && npx vitest run src/kiosk/pages/AiSetupPage.test.tsx -t "A3"`
Expected: 两条 id 用例 FAIL(收到 `ai:territory` / `ai:influence`);说明行除「拟人」外 4 条 FAIL。

- [ ] **Step 2: 实现**

`AiSetupPage.tsx` 把 `AI_STRATEGY_HINT` 上面那段注释与函数整段替换为:

```tsx
/**
 * `.kiosk-opthint` 写的是**当前选中项**的大白话(规范 §11 v1.21)。
 *
 * 每一句都是对产品行为的断言,所以每一句都对着 `core/ai.py` 核过(2026-09-14):
 *   · KataGo `ai:default` → `DefaultStrategy`:等分析完,下 `candidate_moves[0]`;
 *   · 实地 `ai:p:territory` → `TerritoryStrategy`:`generate_influence_territory_weights` 按离边距离加权,
 *     `threshold 3.5` ⇒ 三线及以内满权、往里衰减;走 `PickBasedStrategy`(`pick_n 5` + `pick_frac 0.3` 随机抽候选);
 *   · 厚势 `ai:p:influence` → `InfluenceStrategy`:同一个函数反过来,三线及以内按 `line_weight 10` 压权;
 *   · 策略 `ai:policy` → `PolicyStrategy`:照常等分析回来,但只取 `policy_ranking[0]`(不看搜索结果);`opening_moves 22` 手内改走 `WeightedStrategy`。
 * `.kiosk-opthint` 定高(`--opthint-h`),说明换一句不会让下面那些组跳。
 */
const AI_STRATEGY_HINT = (t: (en: string, zh: string) => string): Record<string, string> => ({
  'ai:human': t(
    'Human-like: plays at the chosen strength, mistakes of that level included',
    '拟人:按所选棋力下出该水平的棋,包括那个水平会犯的错',
  ),
  'ai:default': t('setup:strategy_hint_default', 'KataGo:每手都下引擎搜索后的第一选择,不放水'),
  'ai:p:territory': t('setup:strategy_hint_territory', '实地:偏爱三线及以下的低位,在随机抽出的一批候选里按这个偏好挑,不是全力'),
  'ai:p:influence': t('setup:strategy_hint_influence', '厚势:偏爱四线及以上的高位,在随机抽出的一批候选里按这个偏好挑,不是全力'),
  'ai:policy': t('setup:strategy_hint_policy', '策略:不看搜索结果,直接下策略网络的第一直觉;开局前 22 手随机一些'),
});
```

策略选项两行改为:

```tsx
                        // ⚠️ id 必须是 core/constants.py 里真实存在的那个:`ai:territory` 这种假 id 在
                        // update_player → ai_rank_estimation 里 KeyError,开局直接 500(A3,2026-09-14 复现)。
                        { value: 'ai:p:territory', label: t('setup:style_territory', '实地') },
                        { value: 'ai:p:influence', label: t('Influence', '厚势') },
```

- [ ] **Step 3: 验证**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npx vitest run src/kiosk/pages/AiSetupPage.test.tsx src/kiosk/__tests__/AiSetupPage.test.tsx
npx tsc -b && echo TSC_OK
npx eslint src/kiosk/pages/AiSetupPage.tsx
```
Expected: 全 PASS;`TSC_OK`。

真实运行时一张图(说明行定高、最长那句不溢出):`npm run dev -- --host 127.0.0.1 --port 5173`(先 `lsof` 看端口),`/browse` 打开 `http://127.0.0.1:5173/kiosk/play/ai/setup/free`,1024×600,点「实地」,
截图存 `superpowers/tracks/kiosk-go-play-ai/visual/a3-strategy-hint-territory-1024x600.png`。
Expected: 说明行一行或两行内放下,下面的组没有被推动。交 Fan 单图确认。屏 02 四图默认选中「拟人」,那一帧不变,不重跑。

- [ ] **Step 4: 基线 diff(前端)后提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git add katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx katrain/web/ui/src/kiosk/pages/AiSetupPage.test.tsx \
  superpowers/tracks/kiosk-go-play-ai/visual/a3-strategy-hint-territory-1024x600.png
git diff --cached --stat
git commit -m "fix(kiosk): 开局选「实地」「厚势」直接 500 —— 策略 id 用真实的 ai:p:*,五个策略各补一句核过实现的说明

A3(核实后升为 P1)。条目原写「四个策略都能选、能下」不成立:ai:territory / ai:influence 不存在,
update_player 查 AI_STRENGTH 抛 KeyError。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: A2(文案)+ A15 升降级 503 按原因说话

**Files:**
- Create: `katrain/web/ui/src/features/aiLadder/startErrors.ts`、`startErrors.test.ts` —— **共享领地**(不许 import kiosk/galaxy/pages)
- Modify: `katrain/web/ui/src/features/aiLadder/useAiLadderStatus.ts:16-22`(`aiLadderStatusErrorMessage` 的 503 分支)
- Modify: `katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx:178-182`(`handleStart` 的 503 分支)+ import
- Test: `katrain/web/ui/src/kiosk/pages/AiSetupPage.test.tsx`(末尾追加)

**Interfaces:**
- Consumes: `i18n.t(key, fallback)`(`src/i18n.ts`,与 `features/aiLadder/copy.ts` 同一用法);`AiLadderApiError.message` = 服务端 `detail` 原文(`features/aiLadder/api.ts:55-62`)
- Produces: `type AiLadderUnavailableReason = 'offline' | 'not_authoritative' | 'engine_cannot_serve' | 'cloud_unconfirmed' | 'unknown'`;
  `aiLadderUnavailableReason(detail: string): AiLadderUnavailableReason`;`aiLadderStatusUnavailableMessage(detail: string): string`;`aiLadderStartUnavailableMessage(detail: string): string`

- [ ] **Step 1: 写失败的测试**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
git ls-files src/features/aiLadder/startErrors.ts src/features/aiLadder/startErrors.test.ts; ls src/features/aiLadder/startErrors.ts 2>/dev/null   # 期望:无输出
```

`src/features/aiLadder/startErrors.test.ts`:

```ts
import { describe, expect, test } from 'vitest';
import {
  aiLadderStartUnavailableMessage,
  aiLadderStatusUnavailableMessage,
  aiLadderUnavailableReason,
} from './startErrors';

describe('升降级 503 按服务端 detail 分原因(A15 / A2)', () => {
  test.each([
    ['Remote server unavailable', 'offline'],
    ['Ranked AI ladder authority is unavailable on this node', 'not_authoritative'],
    ['Ranked engine cannot serve the seated rung', 'engine_cannot_serve'],
    ['Ranked game reservation is awaiting cloud expiry', 'cloud_unconfirmed'],
    ['Ranked game activation is awaiting cloud reconciliation', 'cloud_unconfirmed'],
    // kiosk 开局页的桩把整段 `Request failed 503: {...}` 塞进 message —— 包含判定对两种形状都成立
    ['Request failed 503: {"detail":"Ranked engine cannot serve the seated rung"}', 'engine_cannot_serve'],
    ['Could not create game session', 'unknown'],
  ])('%s → %s', (detail, reason) => {
    expect(aiLadderUnavailableReason(detail)).toBe(reason);
  });

  test('断网时状态接口不再说「本机不记升降级成绩」', () => {
    const msg = aiLadderStatusUnavailableMessage('Remote server unavailable');
    expect(msg).toContain('连不上云端');
    expect(msg).not.toContain('本机不记');
  });

  test('节点确实不记成绩时原句不变', () => {
    expect(aiLadderStatusUnavailableMessage('Ranked AI ladder authority is unavailable on this node'))
      .toBe('本机不记升降级成绩，暂时无法开始升降级对弈');
  });

  test('引擎带不动这一档:说没开局、段位没动,不叫人「稍后再试」—— 顶端 6 档在盒上不会自己好', () => {
    const msg = aiLadderStartUnavailableMessage('Ranked engine cannot serve the seated rung');
    expect(msg).toContain('本次没有开局');
    expect(msg).not.toContain('稍后再试');
  });

  test('云端未确认:不许说「本次没有开局」—— 那一局可能已经在云端开出来了', () => {
    expect(aiLadderStartUnavailableMessage('Ranked game activation is awaiting cloud reconciliation')).not.toContain('本次没有开局');
  });
});
```

追加到 `src/kiosk/pages/AiSetupPage.test.tsx` 末尾:

```tsx
// ── A15 · 升降级开局 503 分原因(kiosk-go-play-ai)────────────────────────────
describe('A15 · 升降级开局 503 分原因', () => {
  beforeEach(() => {
    startRanked.mockReset();
    mockNavigate.mockReset();
    // 必须清:排在前面的「升降级挡局面板」组最后一条把 blocking_game 设成 reserved 且不还原,
    // 带着它渲染 ranked,右栏是挡局面板、没有开始按钮,这条会因为找不到按钮而红(红得不对)。
    withBlocking(null);
  });

  it('盒子断网:说「连不上云端」,不说引擎不可用', async () => {
    const err: Error & { status?: number } = new Error('Remote server unavailable');
    err.status = 503;
    startRanked.mockRejectedValueOnce(err);
    renderPage('ranked');
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /开始对局|开始计分局/i }));
    expect(await screen.findByText(/连不上云端/)).toBeInTheDocument();
    expect(screen.queryByText(/升降级引擎暂时不可用/)).not.toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
```

Run: `npx vitest run src/features/aiLadder/startErrors.test.ts src/kiosk/pages/AiSetupPage.test.tsx -t "503|按服务端"`
Expected: `startErrors.test.ts` 整个 FAIL(模块不存在);A15 那条 FAIL(屏上是「升降级引擎暂时不可用…」)。

- [ ] **Step 2: 实现**

`src/features/aiLadder/startErrors.ts`:

```ts
import { i18n } from '../../i18n';

/**
 * 升降级的 503 按服务端 `detail` 分原因(A15 / A2)。
 *
 * 同一个 503 背着几件不同的事(`katrain/web/api/v1/endpoints/ai_ladder.py`):
 *   · `Remote server unavailable` —— 盒子连不上云端(`_remote`);
 *   · `Ranked AI ladder authority is unavailable on this node` —— 这个节点不记升降级成绩(`_require_authority`);
 *   · `Ranked engine cannot serve the seated rung` —— 本机引擎带不动这一档(`_preflight_ladder_engine`;
 *     顶端 6 个 b18 档在只宣告 b6c96 的盒子上必然如此,怎么修待 Fan 拍板);
 *   · `…awaiting cloud expiry` / `…awaiting cloud reconciliation` —— 云端还没确认这一局。
 * 从前一律翻成「本机不记成绩」或「引擎暂时不可用,请稍后再试」:断网的人以为这台盒子不支持升降级,
 * 顶端档位的人被叫去「稍后再试」一件永远不会自己好的事。
 * 判定用「包含」:真 `AiLadderApiError.message` 是 detail 原文,旧桩里是整段 `Request failed 503: {...}`。
 */
export type AiLadderUnavailableReason = 'offline' | 'not_authoritative' | 'engine_cannot_serve' | 'cloud_unconfirmed' | 'unknown';

export function aiLadderUnavailableReason(detail: string): AiLadderUnavailableReason {
  if (detail.includes('Remote server unavailable')) return 'offline';
  if (detail.includes('authority is unavailable')) return 'not_authoritative';
  if (detail.includes('cannot serve the seated rung')) return 'engine_cannot_serve';
  if (detail.includes('awaiting cloud')) return 'cloud_unconfirmed';
  return 'unknown';
}

/** `/ai-ladder/status` 503 时屏上那句话。 */
export function aiLadderStatusUnavailableMessage(detail: string): string {
  return aiLadderUnavailableReason(detail) === 'offline'
    ? i18n.t('ladder:status_offline', '连不上云端。升降级对弈要联网，检查网络后点「重试」')
    : i18n.t('ladder:load_error_not_authoritative', '本机不记升降级成绩，暂时无法开始升降级对弈');
}

/** `/ai-ladder/start` 503 时屏上那句话。除「云端未确认」外,每一句都说清局没开成、段位没动。 */
export function aiLadderStartUnavailableMessage(detail: string): string {
  switch (aiLadderUnavailableReason(detail)) {
    case 'offline':
      return i18n.t('ladder:start_offline', '连不上云端。升降级对弈要联网，本次没有开局，也不影响你的段位；检查网络后再试');
    case 'engine_cannot_serve':
      return i18n.t('ladder:start_engine_cannot_serve', '这台盒子的引擎现在带不动这一档对手。本次没有开局，也不影响你的段位');
    case 'cloud_unconfirmed':
      return i18n.t('ladder:start_cloud_unconfirmed', '云端还没确认这一局的状态，先别重复开局；回到这一屏会显示它的状态');
    case 'not_authoritative':
      return i18n.t('ladder:load_error_not_authoritative', '本机不记升降级成绩，暂时无法开始升降级对弈');
    default:
      return i18n.t('ladder:engine_unavailable_start', '升降级引擎暂时不可用，本次没有开局，也不影响你的段位。请稍后再试。');
  }
}
```

`useAiLadderStatus.ts`:import 区加 `import { aiLadderStatusUnavailableMessage } from './startErrors';`,
`if (error.status === 503) return AI_LADDER_COPY.loadErrorNotAuthoritative;` 改为
`if (error.status === 503) return aiLadderStatusUnavailableMessage(error.message);`。

`AiSetupPage.tsx`:import 区加 `import { aiLadderStartUnavailableMessage } from '../../features/aiLadder/startErrors';`,503 分支整段替换为:

```tsx
      } else if (status === 503 && isRanked) {
        /* 开局前的 503 背着几件不同的事(断网 / 引擎带不动这一档 / 云端未确认),按服务端 detail 分开说,
           见 features/aiLadder/startErrors.ts。 */
        setAuthPrompt('');
        setError(aiLadderStartUnavailableMessage(typeof e?.message === 'string' ? e.message : ''));
```

- [ ] **Step 3: 验证(共享领地 ⇒ 两套构建)并提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npx vitest run src/features/aiLadder/startErrors.test.ts src/features/aiLadder/useAiLadderStatus.test.tsx src/kiosk/pages/AiSetupPage.test.tsx src/galaxy/pages/AiSetupPage.test.tsx
npx tsc -b && echo TSC_OK
npx eslint src/features/aiLadder/startErrors.ts src/features/aiLadder/useAiLadderStatus.ts src/kiosk/pages/AiSetupPage.tsx
npm run build && npm run build:kiosk-2d
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
# 基线 diff(前端),期望 comm -13 无输出
git add katrain/web/ui/src/features/aiLadder/startErrors.ts katrain/web/ui/src/features/aiLadder/startErrors.test.ts \
  katrain/web/ui/src/features/aiLadder/useAiLadderStatus.ts katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx katrain/web/ui/src/kiosk/pages/AiSetupPage.test.tsx
git diff --cached --stat
git commit -m "fix(ladder): 升降级 503 一律说成「本机不记成绩 / 引擎暂时不可用」—— 按服务端 detail 分原因

A15(P2)+ A2 文案。断网说连不上云端;引擎带不动这一档不再叫人稍后再试(顶端 6 个 b18 档在盒上不会自己好,
怎么修待 Fan 拍板);云端未确认不说「本次没有开局」。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```
Expected: 全 PASS;`TSC_OK`;两套构建绿(`verify:kiosk-2d` exit 0)。

---

## Phase 2 · P2 / P3

### Task 9: N14 + A11(+ A9 与拍板无关的一半)右栏按对局类型摆对

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/game/gameKinds.ts`
- Modify: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx`(`TWO_HUMAN_GAME_TYPES` 常量移走、`freeVsAi`、`analysisActions`、`moveRows`、棋谱折叠块的渲染条件与注释)
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx:291`(`wantAnalysis`)
- Modify: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.test.tsx`(改一条已被 A11 推翻的用例:「棋谱只在星阵屏出现」)
- Test: `GameControlPanel.playAi.test.tsx`、`GamePage.playAi.test.tsx`、`tests/kiosk-screen-05-play-ai.spec.ts`(追加)

**Interfaces:**
- Consumes: Task 6 的 `SeatRow` 改动(同文件,先做 Task 6);Task 6 spec 的 `open` / `baseState` / `seat` / `SHOTS`
- Produces: `gameKinds.ts` 导出 `TWO_HUMAN_GAME_TYPES: Set<string>` 与
  `isFreeVsAi({ gameType, engineMode, isRanked }: { gameType: string | null | undefined; engineMode?: boolean; isRanked?: boolean }): boolean`

- [ ] **Step 1: 写失败的测试**

追加到 `src/kiosk/components/game/GameControlPanel.playAi.test.tsx` 末尾:

```tsx
describe('N14 + A11 · 右栏按对局类型', () => {
  const hist = [
    { node_id: 0, score: null, winrate: null, move: null, player: null },
    { node_id: 1, score: null, winrate: null, move: 'Q16', player: 'B' },
    { node_id: 2, score: null, winrate: null, move: 'D4', player: 'W' },
  ] as GameState['history'];
  const labels = () => Array.from(screen.getByTestId('game-actions').querySelectorAll('button'))
    .map((b) => b.textContent?.trim());

  test('升降级局:不渲染「领地」「AI支招」(规范 §8:禁的时候整块不渲染)', () => {
    panel(base({ game_type: 'ai_ladder_ranked' }), { isRanked: true });
    expect(labels()).toEqual(['数子', '停一手', '认输']);
  });

  test.each([
    ['升降级', { game_type: 'ai_ladder_ranked' }, { isRanked: true, analysisToggles: { score: true } }],
    ['本地对局', { game_type: 'pvp_local' }, { analysisToggles: { score: true } }],
    ['关掉图表的自由对弈', { game_type: 'free' }, { analysisToggles: { score: false } }],
  ])('%s:胜率块不在时,右栏中段是棋谱', (_name, over, props) => {
    panel(base({ ...(over as Partial<GameState>), history: hist, current_node_index: 2 }), props);
    expect(screen.getByTestId('game-moves-fold')).toBeInTheDocument();
    expect(document.querySelector('.kiosk-fold[data-fold="eval"]')).toBeNull();
  });

  test('开着图表的自由对弈:胜率块在、棋谱不在(屏 05 不变)', () => {
    panel(base({ history: hist, current_node_index: 2 }), { analysisToggles: { score: true } });
    expect(screen.queryByTestId('game-moves-fold')).toBeNull();
    expect(document.querySelector('.kiosk-fold[data-fold="eval"]')).not.toBeNull();
  });
});
```

追加到 `src/kiosk/pages/GamePage.playAi.test.tsx` 末尾:

```tsx
describe('A9(与拍板无关的一半)· 不渲染胜率块的局不白算分析', () => {
  it('本地对局:「图表」开关默认开着,也不请求按需分析', () => {
    const spy = vi.spyOn(API, 'analyzeCurrent').mockResolvedValue({});
    sessionMock.gameState = makeState({
      game_type: 'pvp_local',
      players_info: { B: seat('player:human', '小明'), W: seat('player:human', '小红') },
    });
    renderPage();
    expect(spy).not.toHaveBeenCalled();
  });

  it('人机自由对弈照旧请求(默认开还是关等 Fan 定,本轮不动)', () => {
    const spy = vi.spyOn(API, 'analyzeCurrent').mockResolvedValue({});
    sessionMock.gameState = makeState();
    renderPage();
    expect(spy).toHaveBeenCalledWith('play-ai-s1');
  });
});
```

`src/kiosk/components/game/GameControlPanel.test.tsx` 里把

```tsx
  test('棋谱只在星阵屏出现 —— 屏 05 那块地方归胜率图', () => {
    panel({ history: hist([['Q16', 'B'], ['D4', 'W']]) });
    expect(screen.queryByTestId('game-moves-fold')).toBeNull();
  });
```

改为

```tsx
  // A11(kiosk-go-play-ai,2026-09-14)推翻了「棋谱只在星阵屏」:scope §27 那条概念债说的就是
  // 「没有哪种对局原则上拿不到自己下过的手」。现在胜率块不在的局中段都是棋谱;只有胜率块开着时那块地方归胜率图。
  test('胜率块开着时棋谱不出现 —— 屏 05 那块地方归胜率图', () => {
    panel({ history: hist([['Q16', 'B'], ['D4', 'W']]) }, { analysisToggles: { score: true } });
    expect(screen.queryByTestId('game-moves-fold')).toBeNull();
  });
```

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui && npx vitest run src/kiosk/components/game/GameControlPanel.playAi.test.tsx src/kiosk/components/game/GameControlPanel.test.tsx src/kiosk/pages/GamePage.playAi.test.tsx`
Expected: N14 标签那条 FAIL(多了「领地」「AI支招」);三条「中段是棋谱」FAIL;「本地对局不请求」FAIL;其余 PASS。

- [ ] **Step 2: 实现**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
git ls-files src/kiosk/components/game/gameKinds.ts; ls src/kiosk/components/game/gameKinds.ts 2>/dev/null   # 期望:无输出
```

`src/kiosk/components/game/gameKinds.ts`:

```ts
import { isRankedGameType } from '../../../features/aiLadder/gameType';

/** 两个人面对面下的局:胜率图整块不渲染、没有悔棋(规范 §8「按对弈方式判」那张表)。 */
export const TWO_HUMAN_GAME_TYPES = new Set(['pvp_local', 'pvp_online']);

/**
 * 这一局是不是**人机自由对弈**。规范 §8 那张表只有一句话:自由对弈能用的,另外四种(升降级 / 本地两人 /
 * 在线大厅 / 星阵人机)一概不能。胜率块、悔棋、「图表」触发的按需分析都认这一个判据 —— 从前 GamePage 的按需分析
 * 只认开关、不认局,本地对局不渲染胜率块却每手照样请求一次(A9)。
 * 升降级两个操作数都读:`isRanked` 是调用方给的,`gameType` 是这一局自己带的 —— 少传一次 prop 不该把闸打开。
 */
export function isFreeVsAi({ gameType, engineMode = false, isRanked = false }: {
  gameType: string | null | undefined;
  engineMode?: boolean;
  isRanked?: boolean;
}): boolean {
  return !engineMode && !isRanked && !isRankedGameType(gameType) && !TWO_HUMAN_GAME_TYPES.has(gameType ?? 'free');
}
```

`GameControlPanel.tsx`:

1. 删掉文件里的 `const TWO_HUMAN_GAME_TYPES = new Set(['pvp_local', 'pvp_online']);`(连同它上面那行注释),import 区加 `import { isFreeVsAi } from './gameKinds';`。
2. `const freeVsAi = !engineMode && !rankedGame && !TWO_HUMAN_GAME_TYPES.has(gameState.game_type ?? 'free');` 改为
   `const freeVsAi = isFreeVsAi({ gameType: gameState.game_type, engineMode, isRanked: rankedGame });`。
3. `const moveRows = engineMode ? toMoveRows(gameState.history) : [];` 改为:

```tsx
  // A11:棋谱是**无条件**的 —— 没有哪种对局原则上拿不到自己下过的手(scope §27 那条概念债)。
  // 胜率块不在的局(星阵 / 升降级 / 本地对局 / 关掉图表),中段那块高度归棋谱;胜率块开着时归胜率块。
  const showMoves = engineMode || !showScore;
  const moveRows = showMoves ? toMoveRows(gameState.history) : [];
```

4. `const analysisActions: KioskAction[] = engineMode ? [] : [` 改为 `const analysisActions: KioskAction[] = engineMode || rankedGame ? [] : [`,并在这一行上面加注释:

```tsx
  // N14:升降级局**整块不渲染**「领地」「AI支招」(规范 §8;实体对弈 PRD「升降级:支招按钮不可见」)。
  // 从前领地能按亮、盘上永远不出色块 —— 按需分析对升降级是关的(GamePage 早退 + 服务端拒)。
```

5. 棋谱折叠块的 `{engineMode && (` 改为 `{showMoves && (`;它上面那段注释第一句「棋谱 —— 只有星阵屏有(稿子 `:1833`)」改为「棋谱 —— 胜率块不在的局都有(星阵屏稿子 `:1833`;A11 扩到升降级 / 本地对局 / 关掉图表)」。

`GamePage.tsx`:import 区加 `import { isFreeVsAi } from '../components/game/gameKinds';`,`const wantAnalysis = analysisToggles.ownership || analysisToggles.score;` 改为:

```tsx
  // 「图表」只在胜率块真的会渲染的局里触发按需分析 —— 本地对局等两人局不渲染胜率块,
  // 从前照样每手请求一次,结果无处显示、白占本机引擎(A9 与拍板无关的那一半;默认开还是关等 Fan 定)。
  const wantAnalysis = analysisToggles.ownership
    || (analysisToggles.score && isFreeVsAi({ gameType: session.gameState?.game_type, engineMode }));
```

Run: 同 Step 1 的命令 → Expected: 全 PASS。另跑 `npx vitest run src/kiosk/__tests__/GamePageLedBadge.test.tsx src/kiosk/__tests__/GamePageEngine.test.tsx src/kiosk/pages/GamePage.test.tsx` → 全 PASS。

- [ ] **Step 3: 承重实测(真浏览器)—— 追加到 `tests/kiosk-screen-05-play-ai.spec.ts` 末尾**

判据先写死:① 满态棋谱 body 自己溢出(数据造到装不下,否则这一轮的数不算);② 右栏不滚;③ 棋谱块不被右栏裁;
④ 动作区贴右栏底;⑤ **中段没有洞**:显示开关排的底 + 12(`--rail-gap`)= 动作区的顶(没有 `grow` 时洞就出在这两者之间,
这是 A11 要消灭的那块空白);⑥ 真滚轮拨得动。最空态(0 手)再量 ④⑤ —— 塌陷类缺陷只在最空状态下现形。

```ts
// ── Task 9 · N14 + A11:胜率块不在的局,右栏中段是棋谱 ───────────────────────────────
const COLS = 'ABCDEFGHJKLMNOPQRST';
const longHistory = (n: number) => [
  { node_id: 0, score: null, winrate: null, move: null, player: null },
  ...Array.from({ length: n }, (_, i) => ({
    node_id: i + 1, score: null, winrate: null,
    move: `${COLS[i % 19]}${(Math.floor(i / 19) % 19) + 1}`, player: i % 2 === 0 ? 'B' : 'W',
  })),
];

const railChain = (page: Page) => page.evaluate(() => {
  const rail = document.querySelector('.kiosk-rail') as HTMLElement;
  const fold = document.querySelector('[data-testid="game-moves-fold"]') as HTMLElement | null;
  const body = fold?.querySelector('.kiosk-fold__body') as HTMLElement | null;
  const toggles = document.querySelector('.kiosk-rail .gtoggles') as HTMLElement;
  const acts = document.querySelector('[data-testid="game-actions"]') as HTMLElement;
  const rb = rail.getBoundingClientRect();
  const fb = fold?.getBoundingClientRect();
  return {
    hasFold: !!fold,
    hasEval: !!document.querySelector('.kiosk-fold[data-fold="eval"]'),
    labels: Array.from(acts.querySelectorAll('button')).map((b) => b.textContent?.trim()),
    bodyOverflow: body ? body.scrollHeight - body.clientHeight : null,
    foldH: fb ? Math.round(fb.height) : null,
    foldInsideRail: fb ? fb.top >= rb.top - 0.5 && fb.bottom <= rb.bottom + 0.5 : null,
    railOverflow: rail.scrollHeight - rail.clientHeight,
    togglesBottom: Math.round(toggles.getBoundingClientRect().bottom),
    actionsTop: Math.round(acts.getBoundingClientRect().top),
    actionsBottom: Math.round(acts.getBoundingClientRect().bottom),
    railBottom: Math.round(rb.bottom),
    docScrollHeight: document.documentElement.scrollHeight,
    innerHeight: window.innerHeight,
  };
});

const KINDS = [
  ['ranked', { game_type: 'ai_ladder_ranked' }],
  ['pvp-local', { game_type: 'pvp_local', players_info: { B: seat('小明', 'player:human'), W: seat('小红', 'player:human') } }],
] as const;

for (const [kind, over] of KINDS) {
  test(`承重 · ${kind}:200 手时棋谱自己滚、右栏不滚、中段没有洞、动作区贴底`, async ({ page }) => {
    await open(page, baseState({ ...over, history: longHistory(200), current_node_id: 200, current_node_index: 200 }));
    await page.waitForSelector('[data-testid="game-moves-fold"] .mvrows .mv');
    const g = await railChain(page);
    console.log(`[play-ai/${kind}/full]`, JSON.stringify(g));

    expect(g.hasEval, '胜率块不该在').toBe(false);
    expect(g.hasFold, '棋谱块没出来').toBe(true);
    expect(g.bodyOverflow, '棋谱没溢出 —— 数据没造够,这一轮量出来的数一概不算').toBeGreaterThan(0);
    expect(g.railOverflow, '右栏被棋谱顶破了').toBeLessThanOrEqual(0);
    expect(g.foldInsideRail, '棋谱块被右栏裁掉一截').toBe(true);
    expect(g.actionsBottom, '动作区没贴右栏底').toBe(g.railBottom);
    expect(g.actionsTop - g.togglesBottom, '显示开关与动作区之间有洞 —— 棋谱没把中段吃满').toBeLessThanOrEqual(13);
    expect(g.docScrollHeight, '整页纵向溢出').toBeLessThanOrEqual(g.innerHeight);

    const body = page.locator('[data-testid="game-moves-fold"] .kiosk-fold__body');
    await body.evaluate((el) => { el.scrollTop = 0; });
    const box = (await body.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.wheel(0, 300);
    // Chromium 的滚轮滚动是异步的,派完立刻读 scrollTop 还是 0 —— 用 poll
    await expect.poll(() => body.evaluate((el) => el.scrollTop), { message: '真滚轮拨不动' }).toBeGreaterThan(0);
    await page.screenshot({ path: `${SHOTS}/n14-a11-${kind}-rail-1024x600.png` });
  });

  test(`承重 · ${kind}:0 手时空态说话、中段没有洞、动作区贴底`, async ({ page }) => {
    await open(page, baseState({ ...over }));
    await page.waitForSelector('[data-testid="game-moves-fold"]');
    const g = await railChain(page);
    console.log(`[play-ai/${kind}/empty]`, JSON.stringify(g));

    await expect(page.locator('[data-testid="game-moves-fold"] .kiosk-fold__body')).toHaveText('这一局还没有着法');
    expect(g.actionsBottom, '动作区没贴右栏底').toBe(g.railBottom);
    expect(g.actionsTop - g.togglesBottom, '最空态下中段塌出一个洞').toBeLessThanOrEqual(13);
    expect(g.railOverflow, '右栏溢出').toBeLessThanOrEqual(0);
  });
}

test('升降级局动作区:没有领地、AI支招、图表、悔棋', async ({ page }) => {
  await open(page, baseState({ game_type: 'ai_ladder_ranked' }));
  expect((await railChain(page)).labels).toEqual(['数子', '停一手', '认输']);
});
```

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npm run build
cp ~/.katrain/config.json /tmp/kgpa-katrain-config.json 2>/dev/null || true
lsof -nP -iTCP:8002 -sTCP:LISTEN
npx playwright test tests/kiosk-screen-05-play-ai.spec.ts tests/kiosk-screen-05-game.spec.ts
cp /tmp/kgpa-katrain-config.json ~/.katrain/config.json 2>/dev/null || true
```
Expected: 全 passed(含既有 `kiosk-screen-05-game.spec.ts` —— 屏 05 / 屏 10 的几何闸不许红)。
**变异自检(一次,不提交)**:把 `KioskFold fold="moves"` 的 `grow` 删掉、重新 build、只跑本 spec,预期「中段没有洞」两态都红;红了再恢复。没红说明判据选错了,停下来重想。

- [ ] **Step 4: 四图 + 视觉确认 + 提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npx tsc -b && echo TSC_OK
npx eslint src/kiosk/components/game/gameKinds.ts src/kiosk/components/game/GameControlPanel.tsx src/kiosk/pages/GamePage.tsx
lsof -nP -iTCP:5173 -sTCP:LISTEN
npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-05-game.fourup.spec.ts tests/kiosk-screen-10-platform-game.fourup.spec.ts
npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-05-game.fourup.spec.ts tests/kiosk-screen-10-platform-game.fourup.spec.ts   # 第二次:两次结果 diff 得本屏抖动地板
git -C /Users/fan/Repositories/katrain-kiosk-go-play-ai status --short superpowers/tracks/kiosk-go-shell-align/visual
```
Expected: 屏 05(开着图表的自由对弈)与屏 10(星阵)这两帧的内容不该变;两屏都是 `<canvas>` 盘,变化若是散在全图、与两次运行之间的差同量级(约 4500 像素)即抖动 ⇒
`git checkout HEAD -- superpowers/tracks/kiosk-go-shell-align/visual/05-game superpowers/tracks/kiosk-go-shell-align/visual/10-platform-game`(先确认这两个目录没有要留的未提交改动)。
若变化聚在右栏,停下来查,不要提交。

把 `superpowers/tracks/kiosk-go-play-ai/visual/n14-a11-ranked-rail-1024x600.png`、`n14-a11-pvp-local-rail-1024x600.png` 交 Fan 视觉确认(稿子没有这两态的参考图),**确认前本 Task 不算完成**。

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
# 基线 diff(前端),期望 comm -13 无输出
git add katrain/web/ui/src/kiosk/components/game/gameKinds.ts katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx \
  katrain/web/ui/src/kiosk/components/game/GameControlPanel.test.tsx katrain/web/ui/src/kiosk/components/game/GameControlPanel.playAi.test.tsx \
  katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx \
  katrain/web/ui/tests/kiosk-screen-05-play-ai.spec.ts \
  superpowers/tracks/kiosk-go-play-ai/visual/n14-a11-ranked-rail-1024x600.png superpowers/tracks/kiosk-go-play-ai/visual/n14-a11-pvp-local-rail-1024x600.png
git diff --cached --stat
git commit -m "fix(kiosk): 升降级局领地键按亮盘上不出色块;胜率块不在的局右栏中段空一块 —— 右栏按对局类型摆

N14(P2):升降级局整块不渲染领地 / AI支招。A11(P3):胜率块不在的局中段显示棋谱(承重实测:满态自滚、
最空态不塌、动作区贴底)。A9 与拍板无关的一半:本地对局不再每手白算一次分析。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: A20 + A21(前端部分)实体盘降级后关掉实体盘 UI;重标定弹层说真话、不在进局时闪

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx:204-208`(`physicalPlay`)、`:406`(`recalOpen`)、`:421-425`(`hardwareFault`)、`:840-845`(`<PhysicalSyncEscalationDialog>`)
- Modify: `katrain/web/ui/src/kiosk/components/physical/PhysicalSyncEscalationDialog.tsx`(`onScreenPlay` prop)
- Modify: `katrain/web/ui/src/kiosk/components/game/RecalibrationModal.tsx:63`(正文)
- Modify: `katrain/web/ui/src/kiosk/components/vision/VisionSyncOverlay.tsx:295`(「横幅中的重新定位」那一句)
- Test: `katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx`(追加)

**Interfaces:**
- Consumes: Task 1 测试文件的 `vision` / `sessionMock` / `pageTree` / `renderPage` / `makeState`
- Produces: `PhysicalSyncEscalationDialog` 新 prop `onScreenPlay?: () => void`;sessionStorage 键 `kiosk_screen_fallback:<sessionId>` = `'1'` 表示本局已降级为屏幕落子

- [ ] **Step 1: 写失败的测试(追加到 `GamePage.playAi.test.tsx` 末尾)**

```tsx
describe('A20 + A21 · 实体盘降级与重标定弹层', () => {
  const physical = () => {
    vision.enabled = true;
    localStorage.removeItem('kiosk_play_on_board');   // 偏好默认开(utils/playInput.ts)
    sessionMock.gameState = makeState();
  };

  it('进局头几秒还没锁定过位姿:不弹「棋盘可能被移动」', () => {
    physical();
    vision.poseLocked = false;
    renderPage();
    expect(screen.queryByText('棋盘可能被移动')).toBeNull();
  });

  it('锁定过之后又丢了才弹,而且说真话:要亮灯、要先清空棋盘', () => {
    physical();
    vision.poseLocked = true;
    const view = renderPage();
    vision.poseLocked = false;
    view.rerender(pageTree());
    expect(screen.getByText('棋盘可能被移动')).toBeInTheDocument();
    expect(screen.getByText(/要先把棋盘上的子全部拿走/)).toBeInTheDocument();
    expect(screen.queryByText(/无需 LED/)).toBeNull();
  });

  it('「改用屏幕落子」之后:解绑一次,实体盘那一串 UI 撤掉;同一局重挂载仍是屏幕模式', async () => {
    physical();
    sessionMock.physicalReminder = { kind: 'escalation', to_place: [], to_remove: [] };
    const unbind = vi.spyOn(API, 'visionUnbind').mockResolvedValue(undefined);
    const view = renderPage();
    // `hidden: true` 是承重的:升级弹窗开着时 MUI 给页面根挂 `aria-hidden`,默认的 ByRole 查不到页控条上的键 ——
    // 不加它,第一条会误红;后面几条 `toBeNull()` 会在弹窗退场期间「因为被藏了」而误绿。
    expect(screen.getByRole('button', { name: /重置识别/, hidden: true })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '改用屏幕落子' }));
    expect(unbind).toHaveBeenCalledTimes(1);
    vision.poseLocked = false;   // 解绑后识别状态机回到未绑定
    view.rerender(pageTree());

    await waitFor(() => expect(screen.queryByRole('button', { name: /重置识别/, hidden: true })).toBeNull());
    expect(screen.queryByText('棋盘可能被移动')).toBeNull();
    expect(sessionStorage.getItem('kiosk_screen_fallback:play-ai-s1')).toBe('1');

    view.unmount();
    sessionMock.physicalReminder = null;
    renderPage();
    expect(screen.queryByRole('button', { name: /重置识别/, hidden: true })).toBeNull();
  });
});
```

Run: `cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui && npx vitest run src/kiosk/pages/GamePage.playAi.test.tsx -t "A20"`
Expected: 第一条 FAIL(弹层出现了);第二条 FAIL(文案是「无需 LED,对齐外框即可」);第三条 FAIL(重置识别键还在)。

- [ ] **Step 2: 实现**

`PhysicalSyncEscalationDialog.tsx`:`Props` 里 `onClose: () => void;` 之后加

```tsx
  /**
   * A20:用户选了「改用屏幕落子」。GamePage 据此把**本局**降级为屏幕模式 —— 只调后端解绑的话,
   * 前端仍按挂载时读的偏好当自己在实体盘上,1–4 秒后弹「棋盘可能被移动」、常驻「标定丢失」。
   */
  onScreenPlay?: () => void;
```

组件参数解构加 `onScreenPlay`,`screenPlay` 改为:

```tsx
  const screenPlay = () => {
    API.visionUnbind().catch(() => undefined);
    onScreenPlay?.();
    onClose();
  };
```

`GamePage.tsx`,把

```tsx
  const [playOnBoard] = useState(readPlayOnBoard);
  const physicalPlay = isVisionEnabled
    && playOnBoard
    && (session.gameState?.board_size?.[0] ?? 19) === 19;
```

替换为

```tsx
  const [playOnBoard] = useState(readPlayOnBoard);
  // A20:本局已从实体盘降级为屏幕落子(`PhysicalSyncEscalationDialog` 的「改用屏幕落子」)。
  // 按 sessionId 记在 sessionStorage:同一局刷新 / 从「继续上一局」回来仍是屏幕模式,换一局不受影响。
  const screenFallbackKey = `kiosk_screen_fallback:${sessionId ?? ''}`;
  const [screenFallback, setScreenFallback] = useState(() => {
    try { return sessionStorage.getItem(screenFallbackKey) === '1'; } catch { return false; }
  });
  const fallBackToScreen = useCallback(() => {
    try { sessionStorage.setItem(screenFallbackKey, '1'); } catch { /* 隐私模式:本页照样降级,只是刷新后记不住 */ }
    setScreenFallback(true);
  }, [screenFallbackKey]);
  const physicalPlay = !screenFallback
    && isVisionEnabled
    && playOnBoard
    && (session.gameState?.board_size?.[0] ?? 19) === 19;
  // A21:「棋盘可能被移动」只在**本页锁定过位姿之后又丢了**时才算数。进局头几秒识别还没绑定 / 刚绑定,
  // `poseLocked` 本来就是假 —— 那不是棋盘被挪了。(渲染中按条件调整 state 的写法,不走 effect。)
  const [poseEverLocked, setPoseEverLocked] = useState(false);
  if (physicalPlay && visionStatus.poseLocked && !poseEverLocked) setPoseEverLocked(true);
```

`const recalOpen = physicalPlay && !visionStatus.poseLocked && !isGameOver;` 改为
`const recalOpen = physicalPlay && poseEverLocked && !visionStatus.poseLocked && !isGameOver;`。

`hardwareFault` 里 `: visionStatus.poseLocked === false ? t('vision:pose_lost', '标定丢失 · 请重新标定')` 改为
`: poseEverLocked && visionStatus.poseLocked === false ? t('vision:pose_lost', '标定丢失 · 请重新标定')`。

`<PhysicalSyncEscalationDialog` 那一段加一个 prop:`onScreenPlay={fallBackToScreen}`。

`RecalibrationModal.tsx` 第 63 行那句正文改为:

```tsx
          {/* A21:「重新标定」跑的是 LED 13 点标定(geometry_calibration_service.py 要 LED、
              led_geometry_calibrator.py 的空盘基线检查盘上有子即失败)。无 LED 外框重定位(V1)接进对局主链之前,
              这里只能说它真会做的事。 */}
          {t('game:recalibrate_needs_empty_board', '重新标定会亮灯，而且要先把棋盘上的子全部拿走；棋盘没被挪过的话，点「仍要继续」')}
```

`VisionSyncOverlay.tsx:295` 改为:

```tsx
            {t('vision:board_lost_hint', '看一下摄像头有没有被挡住、棋盘有没有被挪动；挪动过的话要重新标定')}
```

- [ ] **Step 3: 验证并提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npx vitest run src/kiosk/pages/GamePage.playAi.test.tsx src/kiosk/pages/GamePage.test.tsx src/kiosk/__tests__/GamePageLedBadge.test.tsx src/kiosk/__tests__/GamePage.test.tsx
npx tsc -b && echo TSC_OK
npx eslint src/kiosk/pages/GamePage.tsx src/kiosk/components/physical/PhysicalSyncEscalationDialog.tsx src/kiosk/components/game/RecalibrationModal.tsx src/kiosk/components/vision/VisionSyncOverlay.tsx
```
Expected:`GamePage.playAi.test.tsx` 全 PASS;`TSC_OK`;eslint 无新增 error(若 `if (…) setPoseEverLocked(true)` 被 `react-hooks` 规则判为 error,
先停下来在报告里说明,不要加 `eslint-disable`)。
**既有 `src/kiosk/pages/GamePage.test.tsx` 的 `State B — RecalibrationModal` 组里有两条会红,而且红得对**(它们从 `mockPoseLocked = false` 起步,
按 A21 的新判据「没锁定过就不是棋盘被挪」本就不该弹)。按下面改,其余不动:

`opens when pose is lost mid-game, and 重新标定 calls GeometryAPI.calibrate("manual")` 的开头

```tsx
      mockIsVisionEnabled = true;
      mockPoseLocked = false;
      mockGameState = makeGameState({ players_info: aiVsHuman, end_result: null });
      renderPage();
```

改为

```tsx
      mockIsVisionEnabled = true;
      // A21(kiosk-go-play-ai):先锁定过、再丢失,才算「棋盘可能被移动」。
      mockPoseLocked = true;
      mockGameState = makeGameState({ players_info: aiVsHuman, end_result: null });
      const view = renderPage();
      mockPoseLocked = false;
      view.rerender(pageTree());
```

`re-opens on a fresh pose-loss after being dismissed and the board regaining lock` 的开头

```tsx
      mockIsVisionEnabled = true;
      mockPoseLocked = false;
      mockGameState = makeGameState({ players_info: aiVsHuman, end_result: null });
      const view = renderPage();
```

改为

```tsx
      mockIsVisionEnabled = true;
      // A21(kiosk-go-play-ai):先锁定过、再丢失,才算「棋盘可能被移动」。
      mockPoseLocked = true;
      mockGameState = makeGameState({ players_info: aiVsHuman, end_result: null });
      const view = renderPage();
      mockPoseLocked = false;
      view.rerender(pageTree());
```

改完再跑一遍上面的 vitest 命令 → Expected: 全 PASS。

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
# 基线 diff(前端),期望 comm -13 无输出
git add katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx \
  katrain/web/ui/src/kiosk/components/physical/PhysicalSyncEscalationDialog.tsx katrain/web/ui/src/kiosk/components/game/RecalibrationModal.tsx \
  katrain/web/ui/src/kiosk/components/vision/VisionSyncOverlay.tsx
git add katrain/web/ui/src/kiosk/pages/GamePage.test.tsx
git diff --cached --stat
git commit -m "fix(kiosk): 改用屏幕落子后页面仍当自己在实体盘上;重标定弹层说「无需 LED」而实际要亮灯清盘

A20(P2):本局降级记在 sessionStorage,关掉识别绑定与整串实体盘 UI。A21 前端部分:弹层只在锁定过又丢失时出现,
文案改成它真会做的事;「棋盘检测异常」不再指向不存在的横幅。无 LED 外框重定位(V1)归视觉/标定模块。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```
**必须上板**(记进 Task 12 清单):RK3562 上实体盘对局制造一次长时间跟不上 → 「改用屏幕落子」→ 10 秒内无弹层、可继续屏幕落子。

---

### Task 11: N25 对局屏红条可关、不印后端原文;断线给盒上真能做的出口

**Files:**
- Modify: `katrain/web/ui/src/hooks/useGameSession.ts`(`connectionLost` 状态、`ws.onopen`、`ws.onclose` 两个分支、`clearError`、返回值)—— **共享领地,纯增量**
- Create: `katrain/web/ui/src/hooks/useGameSession.connection.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx:607-609`(那个 `Snackbar` 替换为两个)+ 一个状态
- Test: `katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx`(追加)

**Interfaces:**
- Consumes: Task 1 测试文件的 `sessionMock`(`connectionLost` 已按本 Task 的类型建好)
- Produces: `useGameSession()` 额外返回 `connectionLost: 'rejected' | 'dropped' | null`(1008 被拒 / 意外断开 / 连着)与 `clearError(): void`;`error` 的文案与写入时机不变

- [ ] **Step 1: 写失败的测试**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
git ls-files src/hooks/useGameSession.connection.test.tsx; ls src/hooks/useGameSession.connection.test.tsx 2>/dev/null   # 期望:无输出
```

`src/hooks/useGameSession.connection.test.tsx`:

```tsx
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useGameSession } from './useGameSession';

vi.mock('../api', () => ({
  API: {
    getState: vi.fn().mockResolvedValue({ session_id: 'session-123', state: {} }),
    undo: vi.fn().mockRejectedValue(new Error('Request failed 409: {"detail":"nope"}')),
  },
}));

const sockets: MockWebSocket[] = [];
class MockWebSocket {
  static OPEN = 1;
  readyState = MockWebSocket.OPEN;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onopen: (() => void) | null = null;
  onclose: ((event: { code: number; reason: string; wasClean: boolean }) => void) | null = null;
  close = vi.fn();
  send = vi.fn();
  constructor() { sockets.push(this); }
}

describe('useGameSession · 断线与一次性错误分开记(N25)', () => {
  beforeEach(() => {
    sockets.length = 0;
    vi.stubGlobal('WebSocket', MockWebSocket);
  });
  afterEach(() => { vi.unstubAllGlobals(); });

  const connected = async () => {
    const hook = renderHook(() => useGameSession());
    act(() => { hook.result.current.setSessionId('session-123'); });
    await waitFor(() => expect(sockets.length).toBe(1));
    return hook;
  };

  it('意外断开:connectionLost = dropped,error 文案不变(galaxy 照旧)', async () => {
    const { result } = await connected();
    act(() => { sockets[0].onclose?.({ code: 1006, reason: '', wasClean: false }); });
    expect(result.current.connectionLost).toBe('dropped');
    expect(result.current.error).toContain('实时连接已断开');
  });

  it('被服务端拒(1008):connectionLost = rejected', async () => {
    const { result } = await connected();
    act(() => { sockets[0].onclose?.({ code: 1008, reason: 'Invalid token', wasClean: true }); });
    expect(result.current.connectionLost).toBe('rejected');
  });

  it('一次性操作失败不算断线,clearError 能清掉', async () => {
    const { result } = await connected();
    await act(async () => { await result.current.handleAction('undo').catch(() => undefined); });
    expect(result.current.connectionLost).toBeNull();
    expect(result.current.error).toContain('409');
    act(() => { result.current.clearError(); });
    expect(result.current.error).toBeNull();
  });
});
```

追加到 `src/kiosk/pages/GamePage.playAi.test.tsx` 末尾:

```tsx
describe('N25 · 对局屏错误条', () => {
  it('一次性操作失败:一句人话,不印后端原文,× 能关', () => {
    sessionMock.gameState = makeState();
    sessionMock.error = 'Request failed 409: {"detail":"Not your turn"}';
    renderPage();
    expect(screen.getByText('这一步没有成功，请再试一次')).toBeInTheDocument();
    expect(screen.queryByText(/Request failed/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(sessionMock.clearError).toHaveBeenCalled();
  });

  it('连接意外断开:给盒上真能做的出口,不叫人「刷新页面」', () => {
    sessionMock.gameState = makeState();
    sessionMock.error = '实时连接已断开，棋盘不会自动更新，请刷新页面';
    sessionMock.connectionLost = 'dropped';
    renderPage();
    expect(screen.getByText(/再从「继续上一局」回来/)).toBeInTheDocument();
    expect(screen.queryByText(/请刷新页面/)).toBeNull();
  });

  it('被服务端拒:原句照旧(带原因与「请重新登录」,屏 05 几何闸认的就是它)', () => {
    sessionMock.gameState = makeState();
    sessionMock.error = '实时连接被拒绝（Invalid token），棋盘不会自动更新，请重新登录后重试';
    sessionMock.connectionLost = 'rejected';
    renderPage();
    expect(screen.getByText(/实时连接被拒绝/)).toBeInTheDocument();
  });
});
```

Run: `npx vitest run src/hooks/useGameSession.connection.test.tsx src/kiosk/pages/GamePage.playAi.test.tsx -t "N25|断线"`
Expected: hook 三条 FAIL(`connectionLost` 为 undefined / `clearError is not a function`);GamePage 前两条 FAIL(印的是原文),第三条 PASS。

- [ ] **Step 2: 实现**

`useGameSession.ts`:

1. `const [error, setError] = useState<string | null>(null);` 之后加:

```ts
    // N25:连接断了是**持续状态**(Fan 2026-08-21),与一次性操作失败分开记;调用方据此决定哪种自己消失、给什么出口。
    // 'rejected' = 服务端 1008 拒绝(凭据问题),'dropped' = 意外断开。只增不改:`error` 的写法与文案原样保留。
    const [connectionLost, setConnectionLost] = useState<'rejected' | 'dropped' | null>(null);
```

2. `wsRef.current = ws;` 之后加:

```ts
                    ws.onopen = () => { if (wsRef.current === ws) setConnectionLost(null); };
```

3. `ws.onclose` 里 1008 分支的 `setError(…)` 之前加 `setConnectionLost('rejected');`;`!event.wasClean` 分支的 `setError(…)` 之前加 `setConnectionLost('dropped');`。

4. `const initNewSession = useCallback(…)` 之前加:

```ts
    // N25:一次性错误由调用方在显示过之后清掉(kiosk 的错误条 6 秒自己走、× 可关)。
    const clearError = useCallback(() => setError(null), []);
```

5. 返回对象里 `error,` 之后加 `connectionLost, clearError,`。

`GamePage.tsx`:状态声明区(`resyncError` 之后)加:

```tsx
  // N25:断线提示被用户关掉之后,本页不再弹同一条(持续状态不自动消失,但可以手动关)。
  const [connectionNoticeDismissed, setConnectionNoticeDismissed] = useState(false);
```

把 `<Snackbar open={!!session.error} anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>…</Snackbar>`(连同它上面那段注释保留)整段替换为:

```tsx
      {/* N25:一次性操作失败 —— 一句人话,6 秒自己走,× 可关。后端原文(`Request failed 409: {...}`)不上屏:
          它说的是给运维看的事,盒上用户按不出任何东西。 */}
      <Snackbar
        open={!!session.error && !session.connectionLost}
        autoHideDuration={6000}
        onClose={() => session.clearError()}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert severity="error" onClose={() => session.clearError()}>
          {t('game:action_failed', '这一步没有成功，请再试一次')}
        </Alert>
      </Snackbar>

      {/* N25:连接断了是持续状态(Fan 2026-08-21)—— 不自动消失,× 可关。意外断开时盒上全屏 chromium 没有刷新键,
          给真能做的出口:退出对局,再从「继续上一局」回来就会重新建连。被拒(1008)照旧显示 hook 的原句
          (带原因与「请重新登录」;`kiosk-screen-05-game.spec.ts` 的几何闸量的就是那一态)。 */}
      <Snackbar
        open={!!session.connectionLost && !connectionNoticeDismissed}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert severity="error" onClose={() => setConnectionNoticeDismissed(true)}>
          {session.connectionLost === 'dropped'
            ? t('game:connection_dropped', '实时连接断了，棋盘不会自动更新。先退出对局，再从「继续上一局」回来就会重新连上')
            : session.error}
        </Alert>
      </Snackbar>
```

- [ ] **Step 3: 验证(共享领地 ⇒ 两套构建;e2e 几何闸)并提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
npx vitest run src/hooks/useGameSession.connection.test.tsx src/hooks/useGameSession.navigation.test.tsx src/kiosk/pages/GamePage.playAi.test.tsx src/kiosk/pages/GamePage.test.tsx src/galaxy/pages/GameRoomPage.test.tsx
npx tsc -b && echo TSC_OK
npx eslint src/hooks/useGameSession.ts src/kiosk/pages/GamePage.tsx
npm run build && npm run build:kiosk-2d
cp ~/.katrain/config.json /tmp/kgpa-katrain-config.json 2>/dev/null || true
lsof -nP -iTCP:8002 -sTCP:LISTEN
npx playwright test tests/kiosk-screen-05-game.spec.ts -g "布局 A 的外框"
cp /tmp/kgpa-katrain-config.json ~/.katrain/config.json 2>/dev/null || true
```
Expected: 全 PASS;`TSC_OK`;两套构建绿;「布局 A 的外框」那条仍绿(1008 那一态显示原句、不占流内高度)。

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
# 基线 diff(前端),期望 comm -13 无输出
git add katrain/web/ui/src/hooks/useGameSession.ts katrain/web/ui/src/hooks/useGameSession.connection.test.tsx \
  katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/pages/GamePage.playAi.test.tsx
git diff --cached --stat
git commit -m "fix(kiosk): 对局屏红条一出现就关不掉、印后端原文;断线让盒上用户「刷新页面」

N25(P3)。useGameSession 纯增量加 connectionLost / clearError:一次性失败说人话、6 秒自走、可关;
意外断开持续显示并给「退出后从继续上一局回来」的出口;1008 被拒仍显示原句。WS 自动重连不在本轮。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: 收尾验证与上板清单

**Files:**
- Create: `superpowers/tracks/kiosk-go-play-ai/board-checklist.md`(上板要验的项,给真机那一轮用)
- 无源码改动

**Interfaces:**
- Consumes: Task 1–11 的全部提交
- Produces: 一份可以直接照着上板的清单;本轮完成判据的证据(基线 diff、两套构建、四图/承重结论、Fan 视觉确认记录)

- [ ] **Step 1: 全量回归(基线 diff)**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git status --short        # 期望:只剩本赛道未提交的 prd.md / plan.md(Task 0 时就在);源码与测试不许有未提交改动
CI=true uv run pytest tests -q -rfE -p no:cacheprovider 2>&1 | tee /tmp/kgpa-final-pytest.log
grep -E '^(FAILED|ERROR) ' /tmp/kgpa-final-pytest.log | sed -E 's/ - .*//' | sort -u > /tmp/kgpa-final-pytest-failed.txt
comm -13 /tmp/kgpa-baseline/pytest-failed.txt /tmp/kgpa-final-pytest-failed.txt      # 期望:无输出
git status --short katrain/config.json                                              # 期望:空
cd katrain/web/ui
npx vitest run --reporter=verbose 2>&1 | tee /tmp/kgpa-final-vitest.log
grep -E '^\s+×' /tmp/kgpa-final-vitest.log | sed -E 's/^\s+×\s+//; s/ [0-9]+ms$//' | sort -u > /tmp/kgpa-final-vitest-failed.txt
comm -13 /tmp/kgpa-baseline/vitest-failed.txt /tmp/kgpa-final-vitest-failed.txt      # 期望:无输出
npx tsc -b && echo TSC_OK
npm run build && npm run build:kiosk-2d
```
Expected: 两个 `comm -13` 都无输出;`TSC_OK`;两套构建绿。有输出就逐条查:是本轮造的就修,是进程级共享状态污染(落在无关文件里)也算本轮造的。

- [ ] **Step 2: e2e(打构建产物)**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai/katrain/web/ui
cp ~/.katrain/config.json /tmp/kgpa-katrain-config.json 2>/dev/null || true
lsof -nP -iTCP:8002 -sTCP:LISTEN
npx playwright test tests/kiosk-screen-05-play-ai.spec.ts tests/kiosk-screen-05-game.spec.ts tests/kiosk-ai-ladder-blocking-panel.spec.ts
cp /tmp/kgpa-katrain-config.json ~/.katrain/config.json 2>/dev/null || true
```
Expected: 全 passed。

- [ ] **Step 3: 视觉确认记录**

确认以下截图都已交 Fan 且得到确认(没有确认的在报告里列为「待确认」,本轮不算完成):
`superpowers/tracks/kiosk-go-play-ai/visual/` 下 `n17-game-unavailable-1024x600.png`、`a18-timed-game-1024x600.png`、
`a3-strategy-hint-territory-1024x600.png`、`n14-a11-ranked-rail-1024x600.png`、`n14-a11-pvp-local-rail-1024x600.png`;
屏 05 / 屏 10 四图重跑结论(抖动级、未提交)。

- [ ] **Step 4: 写上板清单**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git ls-files superpowers/tracks/kiosk-go-play-ai/board-checklist.md; ls superpowers/tracks/kiosk-go-play-ai/board-checklist.md 2>/dev/null   # 期望:无输出
```

`superpowers/tracks/kiosk-go-play-ai/board-checklist.md`:

```markdown
# kiosk-go-play-ai · 上板清单(RK3562)

> 一次只跑一家(2G 内存)。盒子树可能落后本分支,先确认板上代码的提交号与本分支一致再验(板上没有 git:比对文件 `git hash-object`)。
> 每项记:日期、板上提交、结果、耗时/截图路径。

| # | 条目 | 步骤 | 通过判据 |
|---|---|---|---|
| 1 | A12 数子补分 | 自由对弈,关掉「领地」「图表」,下满 100 手后点「数子」 | 屏上先出「正在数子…」,15 秒内出 `黑+x`/`白+x` 结果卡;记录点击到出结果的秒数 |
| 2 | N22 AI 跟停 | 自由对弈(已登录),人先停一手、AI 跟停 | 结果卡是胜负而不是「终局」;屏 01「全部对局」里出现这一局 |
| 3 | N22 升降级双停 | 升降级局人先停、AI 跟停 | 对局结束;回升降级开局页没有挡局面板(「继续」按钮消失),能开下一局 |
| 4 | N21 AI 思考中认输 | 自由对弈人落子后立刻「退出对局 → 认输并退出」 | 「全部对局」里这一局记为 AI 胜;回到这一局不再出现 AI 新落的子 |
| 5 | A18 读秒判负 | 自由对弈选「仅读秒 30秒×3」,轮到自己时不下 | 时钟从「读秒 · 剩 3 次」数到「超时」,结果卡为对方超时胜 |
| 6 | A20 改用屏幕落子 | 实体盘对局,制造一次长时间跟不上(不摆 AI 的子)→ 弹层「改用屏幕落子」 | 10 秒内没有「棋盘可能被移动」弹层、开关排没有「标定丢失」;屏幕点子能继续下 |
| 7 | N17 失效的继续上一局 | 开一局后重启 katrain 服务,回屏 01 点「继续上一局」 | 对局屏显示「这一局已经打不开了」+「回到对弈」;回屏 01 后「继续上一局」消失 |
```

- [ ] **Step 5: 提交清单**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-play-ai
git add superpowers/tracks/kiosk-go-play-ai/board-checklist.md
git diff --cached --stat
git commit -m "docs(play-ai): 本轮上板清单 —— 数子补分、AI 跟停落账、认输判方、读秒判负、实体盘降级、失效续局

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage(PRD §3 逐条)**

| PRD 条目 | 任务 |
|---|---|
| N17 加载失败出口 + 清指针 | Task 1 |
| N21 认输判方 / 终局后不落子 / 本地对局确认框 / 大厅按座位 | Task 2 |
| N23 数子门槛按路数 | Task 3 |
| A12 数子补分 + 在途 + 原因 | Task 4 |
| N22 收尾函数 + AI 收尾落账 / 双停补分 / 串行 / 升降级不补 | Task 5 |
| A18 `timer.configured` + 时钟 + 超时 + 截图 | Task 6 |
| A3 策略 id + 五句说明 + 截图 | Task 7 |
| A2(文案)+ A15 503 分原因 | Task 8 |
| N14 + A11 + A9 一半 + 承重实测 + 截图 | Task 9 |
| A20 + A21 前端部分 | Task 10 |
| N25 错误条 + 断线出口 | Task 11 |
| §7 必须上板的四项(另加 N21/N17 两项) | Task 12 清单 |

PRD §4(A12-R、A2 修法、A9 默认值、A7、A14、A17、A19、Z6)与 §5 均未进任务 —— 符合「待拍板不进计划」。

**2. Placeholder scan**:全文无 TBD / TODO / 「类似 Task N」;每个改代码的步骤都给了代码;条件分支(eslint 若判 error)写明了停下来报告而非自由发挥。

**3. Type consistency**:
- `_do_resign(loser: Optional[str])` —— Task 2 定义,`/api/resign` 以位置参数传,测试以位置参数调用,一致。
- `ensure_current_score(timeout_s: Optional[float] = None) -> Optional[float]` —— Task 4 定义,Task 4 端点与 Task 5 `_score_two_pass_end` 均无参调用,一致。
- `_FINISH_ENDED_GAME_FN(session, app, current_user)` —— Task 5 定义与测试调用参数顺序一致;`manager.on_game_ended(session)` 单参,由 `_on_game_ended_off_request` 适配;
  `WebKaTrain.game_ended_callback()` 无参,由 `create_session` 的 `lambda sid=session_id: self._on_game_ended(sid)` 适配。
- `GameState['timer']['configured']` / `isTimedGame` / `useGoClock(gameState, color, onExpired)` / `GameControlPanel` 的 `onTimeout(color)` —— Task 6 内一致;Task 9 不改签名。
- `isFreeVsAi({ gameType, engineMode, isRanked })` —— Task 9 定义,`GameControlPanel` 与 `GamePage` 两处调用字段名一致。
- `useGameSession().connectionLost: 'rejected' | 'dropped' | null` —— Task 11 定义;Task 1 测试桩按此类型建、beforeEach 置 `null`。
- 测试共用件:`GamePage.playAi.test.tsx` 的 `sessionMock` / `vision` / `makeState` / `seat` / `pageTree` / `renderPage`(Task 1)被 Task 2/4/6/9/10/11 引用;
  `tests/test_play_ai_endgame.py` 的 `_web_katrain` / `_seat`(Task 2)被 Task 3/4/6 引用;`tests/web_ui/test_play_ai_endgame_api.py` 的 `client` / `_inject_session`(Task 2)被 Task 3/4 引用;
  `kiosk-screen-05-play-ai.spec.ts` 的 `open` / `baseState` / `seat` / `SHOTS`(Task 6)被 Task 9 引用。
