import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import ResearchPage from './ResearchPage';
vi.mock('../../api/membershipApi', () => ({ membershipApi: paidApi }));
vi.mock('../../features/report/useReportTasks', () => ({ useReportTasks: () => ({ createReport, pendingQuote: null, quoteBusy: false, error: null }) }));
import { useAuth } from '../../context/AuthContext';
import { vi, describe, it, expect, beforeEach, Mock } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { API } from '../../api';
import { writeAudioPref } from '../../utils/audioPrefs';

const { language } = vi.hoisted(() => ({ language: { current: 'cn' } }));
vi.mock('../../hooks/useTranslation', () => ({
  useTranslation: () => ({ lang: language.current, t: (_key: string, fallback?: string) => fallback ?? _key }),
}));

vi.mock('../../api', () => ({ API: {
  quickAnalyze: vi.fn().mockResolvedValue({ turnInfos: [{ moveInfos: [] }] }),
  // 全盘扫描：深链那条用例拿它当绊线（导航不许触发计费的分析）。
  analysisScan: vi.fn().mockResolvedValue({}),
} }));

/* 「进入研究室」深链（`?user_game_id=`）走的是个人对局接口，与 `?kifu_id=` 的棋谱库
   不是同一个 id 空间。这里桩掉它，用例只关心 token/id 有没有原样传下去、
   取回来的 SGF 有没有装进棋盘。 */
const { getUserGame, saveUserGame, createReport, paidApi } = vi.hoisted(() => ({
  createReport: vi.fn(), saveUserGame: vi.fn(), paidApi: { getCatalog: vi.fn(), createQuote: vi.fn(), createPosition: vi.fn() },
  getUserGame: vi.fn().mockResolvedValue({
    id: 'g1',
    sgf_content: '(;FF[4]GM[1]SZ[19];B[pd];W[dp])',
  }),
}));
vi.mock('../api/userGamesApi', () => ({ UserGamesAPI: { get: getUserGame, create: saveUserGame } }));

/* `?kifu_id=` 那条深链走棋谱库（`KifuAPI.getAlbum`），与上面那条是两个 id 空间。
   `useResearchSession` 也要桩掉：这条用例要看的正是**递给 `createSession` 的那份 SGF**，
   不能让真的 hook 去连 WebSocket。桩件的形状照真 hook 的返回值抄，
   页面只读其中 9 个字段（session.createSession / destroySession / gameState /
   onMove / onPass / onNavigate / sessionId / toggleHints / toggleOwnership）。 */
const { getAlbum, createSession } = vi.hoisted(() => ({
  getAlbum: vi.fn(),
  createSession: vi.fn().mockResolvedValue('sess-1'),
}));
vi.mock('../../api/kifuApi', () => ({ KifuAPI: { getAlbum } }));
vi.mock('../../hooks/useResearchSession', () => ({
  useResearchSession: () => ({
    sessionId: null,
    gameState: null,
    error: null,
    isConnected: false,
    createSession,
    destroySession: vi.fn().mockResolvedValue(undefined),
    onMove: vi.fn(),
    onPass: vi.fn(),
    onNavigate: vi.fn(),
    handleNavAction: vi.fn(),
    toggleHints: vi.fn(),
    toggleOwnership: vi.fn(),
    toggleMoveNumbers: vi.fn(),
    toggleCoordinates: vi.fn(),
    analyzeGame: vi.fn(),
    analysisScan: vi.fn(),
  }),
}));

// Mock useAuth so authentication state can be toggled per test.
// The board stays available logged-out; private deep links require confirmed auth.
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
  default: ({ moves, onIntersectionClick }: { moves?: unknown[]; onIntersectionClick?: (x: number, y: number) => void }) => (
    <div data-testid="mock-live-board" data-moves={moves?.length ?? 0}><button onClick={() => onIntersectionClick?.(3, 3)}>摆 D4</button></div>
  ),
}));

// ResearchSetupPanel is the right-hand setup sidebar on the default (edit) path — stub it.
// 统一版式把「开始研究」拆成了同一个模块的具名导出（它归右栏动作区，不跟着滚），
// 所以这里两个导出都要给，否则页面渲染时 ResearchSetupActions 是 undefined。
vi.mock('../components/research/ResearchSetupPanel', () => ({
  default: ({ onToggleHints, playerBlack, onPlayerBlackChange }: { onToggleHints: () => void; playerBlack: string; onPlayerBlackChange: (name: string) => void }) => <div data-testid="mock-setup-panel"><button onClick={onToggleHints}>支招</button><input aria-label="黑方姓名" value={playerBlack} onChange={(event) => onPlayerBlackChange(event.target.value)} /></div>,
  ResearchSetupActions: ({ onStartAnalysis }: { onStartAnalysis: () => void }) => (
    <button data-testid="mock-start-analysis" onClick={onStartAnalysis}>开始研究</button>
  ),
}));

// Legacy Board (canvas) is only used in the L2 analysis-complete branch, not the default
// path exercised here. Stub it as harmless insurance so it never tries to paint a canvas.
vi.mock('../../components/Board', () => ({
  default: () => <div data-testid="mock-board">Board Component</div>,
}));

const pageElement = (path = '/research') => (
  <MemoryRouter initialEntries={[path]}>
    <ResearchPage />
  </MemoryRouter>
);
const renderPage = (path = '/research') => render(pageElement(path));

const KIFU_SGF = '(;FF[4]GM[1]SZ[19];B[pd];W[dp];B[pp];W[dd])';
const USER_GAME_SGF = '(;FF[4]GM[1]SZ[19];B[pd];W[dp])';
const confirmedAuth = {
  status: 'authenticated', identityKey: 'one', isAuthenticated: true,
  isLoading: false, isGuest: false, token: 'test-token',
};
const anonymousAuth = {
  status: 'guest', identityKey: null, isAuthenticated: false,
  isLoading: false, isGuest: false, token: null,
};

describe('ResearchPage', () => {
  // 有两条 `not.toHaveBeenCalled()`，调用记录必须逐条清零，否则前一条用例的调用会算到后一条头上。
  beforeEach(() => {
    vi.clearAllMocks();
    language.current = 'cn';
    writeAudioPref('sfx', true);
    paidApi.getCatalog.mockResolvedValue({ membership_mode: 'enabled', capabilities: { quotes: true, positions: true } });
    paidApi.createQuote.mockResolvedValue({ token: 'signed', kind: 'position', source: 'membership', profile: 'normal', wallet_max_display_points: '0.01' });
    paidApi.createPosition.mockResolvedValue({ state: 'succeeded', operation_id: 'op1', result: { ownership: Array(361).fill(0.2), moves: [{ move: 'D4', visits: 500, winrate: 0.6, score_lead: 2 }] } });
    saveUserGame.mockResolvedValue({ id: 'owned-game', move_count: 1 });
    createReport.mockResolvedValue(null);
    createSession.mockResolvedValue('sess-1');
    getUserGame.mockReset().mockResolvedValue({ id: 'g1', sgf_content: USER_GAME_SGF });
    getAlbum.mockResolvedValue({
      id: 42,
      sgf_content: KIFU_SGF,
      player_black: '棋谱黑',
      player_white: '棋谱白',
    });
    /* jsdom 没实现 `HTMLMediaElement.play()` —— 它返回 undefined 而不是 Promise，
       于是 `ResearchPage.tsx:78` 的 `.catch()` 会抛。产品代码没错（真浏览器里 play()
       就是返回 Promise），补的是 jsdom 的缺口。以前没人踩到，是因为在此之前没有一条
       用例真的让 `currentMove` 动过 —— 深链这条是第一个。 */
    vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined);
  });

  it('keeps an edited player name when the deep-linked kifu language changes', async () => {
    (useAuth as Mock).mockReturnValue(confirmedAuth);
    getAlbum.mockImplementation((_id: number, lang: string) => Promise.resolve({
      id: 42, sgf_content: KIFU_SGF,
      display_player_black: `${lang}-black`, display_player_white: `${lang}-white`,
    }));
    const view = renderPage('/research?kifu_id=42');
    const input = await screen.findByRole('textbox', { name: '黑方姓名' });
    await waitFor(() => expect(input).toHaveValue('cn-black'));
    fireEvent.change(input, { target: { value: 'Edited player' } });
    language.current = 'ru';
    view.rerender(<MemoryRouter initialEntries={['/research?kifu_id=42']}><ResearchPage /></MemoryRouter>);
    await waitFor(() => expect(getAlbum).toHaveBeenLastCalledWith(42, 'ru'));
    await waitFor(() => expect(input).toHaveValue('Edited player'));
  });

  it('loads a deep-linked game silently and plays one shared sound for an explicit stone navigation', async () => {
    (useAuth as Mock).mockReturnValue(anonymousAuth);
    renderPage('/research?kifu_id=42');
    await waitFor(() => expect(screen.getByTestId('mock-live-board')).toHaveAttribute('data-moves', '4'));
    expect(HTMLMediaElement.prototype.play).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '◀' }));
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: '⏮' }));
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalledTimes(1);
  });

  it('uses the shared SFX setting for accepted local placements', () => {
    (useAuth as Mock).mockReturnValue(anonymousAuth);
    renderPage();
    writeAudioPref('sfx', false);
    fireEvent.click(screen.getByRole('button', { name: '摆 D4' }));
    expect(screen.getByTestId('mock-live-board')).toHaveAttribute('data-moves', '1');
    expect(HTMLMediaElement.prototype.play).not.toHaveBeenCalled();
  });

  // Test A — research is intentionally available without login (no auth gate).
  it('renders the board and setup panel without requiring login', () => {
    (useAuth as Mock).mockReturnValue(anonymousAuth);

    renderPage();

    // The default edit-mode path renders the board + setup panel for everyone.
    expect(screen.getByTestId('mock-live-board')).toBeInTheDocument();
    expect(screen.getByTestId('mock-setup-panel')).toBeInTheDocument();
    // There is no login gate — proves research is un-gated by design.
    expect(screen.queryByText(/Login Required/i)).not.toBeInTheDocument();
  });

  // Test B — authenticated render still shows the same edit-mode board + setup panel.
  it('renders the board and setup panel when authenticated', () => {
    (useAuth as Mock).mockReturnValue(confirmedAuth);

    renderPage();

    expect(screen.getByTestId('mock-live-board')).toBeInTheDocument();
    expect(screen.getByTestId('mock-setup-panel')).toBeInTheDocument();
  });

  it('passes the confirmed identity credential to a quote without running raw analysis', async () => {
    (useAuth as Mock).mockReturnValue(confirmedAuth);
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: '支招' }));
    await waitFor(() => expect(paidApi.createQuote).toHaveBeenCalledWith(expect.objectContaining({ kind: 'position', sgf: expect.any(String) }), 'test-token'));
    expect(API.quickAnalyze).not.toHaveBeenCalled();
    expect(paidApi.createPosition).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '确认并开始' }));
    await waitFor(() => expect(paidApi.createPosition).toHaveBeenCalledTimes(1));
  });

  it('loads analyze=1 deep links without automatically authorizing consumption', async () => {
    (useAuth as Mock).mockReturnValue(confirmedAuth);
    renderPage('/research?kifu_id=42&analyze=1');
    await waitFor(() => expect(screen.getByTestId('mock-live-board')).toHaveAttribute('data-moves', '4'));
    expect(createSession).not.toHaveBeenCalled();
    expect(API.analysisScan).not.toHaveBeenCalled();
    expect(paidApi.createPosition).not.toHaveBeenCalled();
  });

  /** 不带 `analyze=1` 时只装棋盘、不开会话 —— 全盘扫描是计费动作。 */
  it('loads a public deep-linked kifu anonymously without opening an analysis session', async () => {
    (useAuth as Mock).mockReturnValue(anonymousAuth);

    renderPage('/research?kifu_id=42');

    await waitFor(() =>
      expect(screen.getByTestId('mock-live-board').getAttribute('data-moves')).toBe('4'));
    expect(createSession).not.toHaveBeenCalled();
    expect(API.analysisScan).not.toHaveBeenCalled();
  });

  // 复盘页「进入研究室」的落点（Fan 2026-08-22 点头补的深链）。
  it('loads the handed-off game from ?user_game_id', async () => {
    (useAuth as Mock).mockReturnValue(confirmedAuth);

    renderPage('/research?user_game_id=g1');

    await waitFor(() => expect(getUserGame).toHaveBeenCalledWith('test-token', 'g1'));
    // 两手棋真的进了棋盘，不是只发了个请求。
    await waitFor(() => expect(screen.getByTestId('mock-live-board')).toHaveAttribute('data-moves', '2'));
  });

  it.each(['checking', 'unavailable'])('does not fetch a private deep link with a retained token during %s', (status) => {
    (useAuth as Mock).mockReturnValue({ ...anonymousAuth, status, token: 'saved-token', isLoading: status === 'checking' });

    renderPage('/research?user_game_id=g1');

    expect(getUserGame).not.toHaveBeenCalled();
    expect(screen.getByTestId('mock-live-board')).toHaveAttribute('data-moves', '0');
  });

  it('waits for confirmed cookie identity before loading a private deep link', async () => {
    (useAuth as Mock).mockReturnValue({ ...anonymousAuth, status: 'checking', isLoading: true });
    const view = renderPage('/research?user_game_id=g1');
    expect(getUserGame).not.toHaveBeenCalled();

    (useAuth as Mock).mockReturnValue({ ...confirmedAuth, token: null });
    view.rerender(pageElement('/research?user_game_id=g1'));

    await waitFor(() => expect(getUserGame).toHaveBeenCalledWith(null, 'g1'));
    await waitFor(() => expect(screen.getByTestId('mock-live-board')).toHaveAttribute('data-moves', '2'));
  });

  it('does not load a private deep-link response after logout', async () => {
    let finish: (value: unknown) => void = () => {};
    getUserGame.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
    (useAuth as Mock).mockReturnValue(confirmedAuth);
    const view = renderPage('/research?user_game_id=g1');
    expect(getUserGame).toHaveBeenCalledWith('test-token', 'g1');

    (useAuth as Mock).mockReturnValue(anonymousAuth);
    view.rerender(pageElement('/research?user_game_id=g1'));
    await act(async () => { finish({ id: 'g1', sgf_content: USER_GAME_SGF }); });

    expect(screen.getByTestId('mock-live-board')).toHaveAttribute('data-moves', '0');
    expect(getUserGame).toHaveBeenCalledTimes(1);
  });

  it('loads only the current identity response after changing accounts', async () => {
    let finishOld: (value: unknown) => void = () => {};
    getUserGame.mockImplementationOnce(() => new Promise((resolve) => { finishOld = resolve; }));
    (useAuth as Mock).mockReturnValue(confirmedAuth);
    const view = renderPage('/research?user_game_id=g1');

    (useAuth as Mock).mockReturnValue({ ...confirmedAuth, identityKey: 'two', token: 'new-token' });
    getUserGame.mockResolvedValueOnce({ id: 'g1', sgf_content: KIFU_SGF });
    view.rerender(pageElement('/research?user_game_id=g1'));
    await waitFor(() => expect(getUserGame).toHaveBeenCalledWith('new-token', 'g1'));
    await waitFor(() => expect(screen.getByTestId('mock-live-board')).toHaveAttribute('data-moves', '4'));
    await act(async () => { finishOld({ id: 'g1', sgf_content: USER_GAME_SGF }); });

    expect(screen.getByTestId('mock-live-board')).toHaveAttribute('data-moves', '4');
  });

  // 没有这个参数时不许去打个人对局接口 —— 平时进研究室是空棋盘，那条路不该产生请求。
  it('does not fetch a user game without the deep-link param', async () => {
    (useAuth as Mock).mockReturnValue(confirmedAuth);

    renderPage();

    await waitFor(() => expect(screen.getByTestId('mock-live-board')).toHaveAttribute('data-moves', '0'));
    expect(getUserGame).not.toHaveBeenCalled();
  });

  /* 分析是计费动作，不该由一次导航触发。这条守的是「深链只装棋，不开扫描」——
     它同时也是「以后有人顺手给这条深链加 analyze=1」的绊线。 */
  it('does not start an analysis scan on the deep link', async () => {
    (useAuth as Mock).mockReturnValue(confirmedAuth);

    renderPage('/research?user_game_id=g1&analyze=1');

    await waitFor(() => expect(screen.getByTestId('mock-live-board')).toHaveAttribute('data-moves', '2'));
    expect(API.analysisScan).not.toHaveBeenCalled();
  });

  it('requires login before creating a report', async () => {
    (useAuth as Mock).mockReturnValue(anonymousAuth);
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: '创建复盘报告' }));
    expect(await screen.findByTestId('login-required-message')).toBeVisible();
    expect(saveUserGame).not.toHaveBeenCalled();
  });
  it('saves an owned SGF and starts the report quote journey instead of a scan', async () => {
    (useAuth as Mock).mockReturnValue(confirmedAuth);
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: '摆 D4' }));
    fireEvent.click(screen.getByRole('button', { name: '创建复盘报告' }));
    await waitFor(() => expect(createReport).toHaveBeenCalledWith({ userGameId: 'owned-game', totalMoves: 1 }));
    expect(saveUserGame.mock.calls[0][1].sgf_content).toContain('B[dp]');
    expect(API.analysisScan).not.toHaveBeenCalled();
  });
});
