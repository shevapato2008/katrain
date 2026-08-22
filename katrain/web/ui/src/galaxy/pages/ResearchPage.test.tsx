import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ResearchPage from './ResearchPage';
import { useAuth } from '../../context/AuthContext';
import { vi, describe, it, expect, beforeEach, Mock } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { API } from '../../api';

vi.mock('../../api', () => ({ API: {
  quickAnalyze: vi.fn().mockResolvedValue({ turnInfos: [{ moveInfos: [] }] }),
  // 全盘扫描：深链那条用例拿它当绊线（导航不许触发计费的分析）。
  analysisScan: vi.fn().mockResolvedValue({}),
} }));

/* 「进入研究室」深链（`?user_game_id=`）走的是个人对局接口，与 `?kifu_id=` 的棋谱库
   不是同一个 id 空间。这里桩掉它，用例只关心 token/id 有没有原样传下去、
   取回来的 SGF 有没有装进棋盘。 */
const { getUserGame } = vi.hoisted(() => ({
  getUserGame: vi.fn().mockResolvedValue({
    id: 'g1',
    sgf_content: '(;FF[4]GM[1]SZ[19];B[pd];W[dp])',
  }),
}));
vi.mock('../api/userGamesApi', () => ({ UserGamesAPI: { get: getUserGame } }));

// Mock useAuth so authentication state can be toggled per test.
// NOTE: ResearchPage only reads `token` from useAuth (for cloud-save); it does NOT
// gate rendering on auth — the board is available logged-out by design.
vi.mock('../../context/AuthContext', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useAuth: vi.fn(),
  };
});

// ResearchPage calls useGameNavigation() and reads registerActiveGame/unregisterActiveGame.
// Without a provider the hook throws, so stub it (matches the file's vi.mock style).
vi.mock('../context/GameNavigationContext', () => ({
  useGameNavigation: () => ({
    registerActiveGame: vi.fn(),
    unregisterActiveGame: vi.fn(),
  }),
}));

// LiveBoard paints to a <canvas>, which jsdom cannot render — stub it to a testid div.
// This is the board shown on the default (edit) path, regardless of auth.
// 桩件把 `moves.length` 回读出来：深链那条用例要证的是「棋子真的进了棋盘」，
// 光断言 fetch 调过只证明我发出了请求，证不到棋局被装上。
vi.mock('../../components/live/LiveBoard', () => ({
  default: ({ moves }: { moves?: unknown[] }) => (
    <div data-testid="mock-live-board" data-moves={moves?.length ?? 0}>Live Board</div>
  ),
}));

// ResearchSetupPanel is the right-hand setup sidebar on the default (edit) path — stub it.
// 统一版式把「开始研究」拆成了同一个模块的具名导出（它归右栏动作区，不跟着滚），
// 所以这里两个导出都要给，否则页面渲染时 ResearchSetupActions 是 undefined。
vi.mock('../components/research/ResearchSetupPanel', () => ({
  default: ({ onToggleHints }: { onToggleHints: () => void }) => <div data-testid="mock-setup-panel"><button onClick={onToggleHints}>建议</button></div>,
  ResearchSetupActions: ({ onStartAnalysis }: { onStartAnalysis: () => void }) => (
    <button data-testid="mock-start-analysis" onClick={onStartAnalysis}>开始研究</button>
  ),
}));

// Legacy Board (canvas) is only used in the L2 analysis-complete branch, not the default
// path exercised here. Stub it as harmless insurance so it never tries to paint a canvas.
vi.mock('../../components/Board', () => ({
  default: () => <div data-testid="mock-board">Board Component</div>,
}));

const renderPage = (path = '/galaxy/research') =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <ResearchPage />
    </MemoryRouter>
  );

describe('ResearchPage', () => {
  // 有两条 `not.toHaveBeenCalled()`，调用记录必须逐条清零，否则前一条用例的调用会算到后一条头上。
  beforeEach(() => {
    vi.clearAllMocks();
    /* jsdom 没实现 `HTMLMediaElement.play()` —— 它返回 undefined 而不是 Promise，
       于是 `ResearchPage.tsx:78` 的 `.catch()` 会抛。产品代码没错（真浏览器里 play()
       就是返回 Promise），补的是 jsdom 的缺口。以前没人踩到，是因为在此之前没有一条
       用例真的让 `currentMove` 动过 —— 深链这条是第一个。 */
    vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined);
  });

  // Test A — research is intentionally available without login (no auth gate).
  it('renders the board and setup panel without requiring login', () => {
    (useAuth as Mock).mockReturnValue({ isAuthenticated: false, token: null });

    renderPage();

    // The default edit-mode path renders the board + setup panel for everyone.
    expect(screen.getByTestId('mock-live-board')).toBeInTheDocument();
    expect(screen.getByTestId('mock-setup-panel')).toBeInTheDocument();
    // There is no login gate — proves research is un-gated by design.
    expect(screen.queryByText(/Login Required/i)).not.toBeInTheDocument();
  });

  // Test B — authenticated render still shows the same edit-mode board + setup panel.
  it('renders the board and setup panel when authenticated', () => {
    (useAuth as Mock).mockReturnValue({ isAuthenticated: true, token: 'test-token' });

    renderPage();

    expect(screen.getByTestId('mock-live-board')).toBeInTheDocument();
    expect(screen.getByTestId('mock-setup-panel')).toBeInTheDocument();
  });

  it('passes the Galaxy access token to quick analysis', async () => {
    (useAuth as Mock).mockReturnValue({ isAuthenticated: true, token: 'test-token' });
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: '建议' }));
    await waitFor(() => expect(API.quickAnalyze).toHaveBeenCalledWith(expect.any(Object), 'test-token'));
  });

  // 复盘页「进入研究室」的落点（Fan 2026-08-22 点头补的深链）。
  it('loads the handed-off game from ?user_game_id', async () => {
    (useAuth as Mock).mockReturnValue({ isAuthenticated: true, token: 'test-token' });

    renderPage('/galaxy/research?user_game_id=g1');

    await waitFor(() => expect(getUserGame).toHaveBeenCalledWith('test-token', 'g1'));
    // 两手棋真的进了棋盘，不是只发了个请求。
    await waitFor(() => expect(screen.getByTestId('mock-live-board')).toHaveAttribute('data-moves', '2'));
  });

  // 没有这个参数时不许去打个人对局接口 —— 平时进研究室是空棋盘，那条路不该产生请求。
  it('does not fetch a user game without the deep-link param', async () => {
    (useAuth as Mock).mockReturnValue({ isAuthenticated: true, token: 'test-token' });

    renderPage();

    await waitFor(() => expect(screen.getByTestId('mock-live-board')).toHaveAttribute('data-moves', '0'));
    expect(getUserGame).not.toHaveBeenCalled();
  });

  /* 分析是计费动作，不该由一次导航触发。这条守的是「深链只装棋，不开扫描」——
     它同时也是「以后有人顺手给这条深链加 analyze=1」的绊线。 */
  it('does not start an analysis scan on the deep link', async () => {
    (useAuth as Mock).mockReturnValue({ isAuthenticated: true, token: 'test-token' });

    renderPage('/galaxy/research?user_game_id=g1&analyze=1');

    await waitFor(() => expect(screen.getByTestId('mock-live-board')).toHaveAttribute('data-moves', '2'));
    expect(API.analysisScan).not.toHaveBeenCalled();
  });
});
