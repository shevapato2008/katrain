import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import ResearchPage from './ResearchPage';
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
const { getUserGame } = vi.hoisted(() => ({
  getUserGame: vi.fn().mockResolvedValue({
    id: 'g1',
    sgf_content: '(;FF[4]GM[1]SZ[19];B[pd];W[dp])',
  }),
}));
vi.mock('../api/userGamesApi', () => ({ UserGamesAPI: { get: getUserGame } }));

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

const pageElement = (path = '/galaxy/research') => (
  <MemoryRouter initialEntries={[path]}>
    <ResearchPage />
  </MemoryRouter>
);
const renderPage = (path = '/galaxy/research') => render(pageElement(path));

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
    const view = renderPage('/galaxy/research?kifu_id=42');
    const input = await screen.findByRole('textbox', { name: '黑方姓名' });
    await waitFor(() => expect(input).toHaveValue('cn-black'));
    fireEvent.change(input, { target: { value: 'Edited player' } });
    language.current = 'ru';
    view.rerender(<MemoryRouter initialEntries={['/galaxy/research?kifu_id=42']}><ResearchPage /></MemoryRouter>);
    await waitFor(() => expect(getAlbum).toHaveBeenLastCalledWith(42, 'ru'));
    await waitFor(() => expect(input).toHaveValue('Edited player'));
  });

  it('loads a deep-linked game silently and plays one shared sound for an explicit stone navigation', async () => {
    (useAuth as Mock).mockReturnValue(anonymousAuth);
    renderPage('/galaxy/research?kifu_id=42');
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

  it('passes the Galaxy access token to quick analysis', async () => {
    (useAuth as Mock).mockReturnValue(confirmedAuth);
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: '支招' }));
    await waitFor(() => expect(API.quickAnalyze).toHaveBeenCalledWith(expect.any(Object), 'test-token'));
  });

  /**
   * `?kifu_id=<id>&analyze=1` 必须拿**这局棋**去开分析会话，不是拿一张空棋盘。
   *
   * 改之前这条深链是 `setTimeout(() => handleStartAnalysis(), 100)`。它闭包捕获的是
   * **effect 那一帧**的 `handleStartAnalysis`，而那一帧的 `board.moves` 还是空的
   * （`loadFromSGF` 走的是 `useState`，同一段 async 续体里还没冲刷）。于是
   * `handleStartAnalysis` 里那行 `board.moves.length > 0 ? sgf : undefined` 取到
   * `undefined`，会话建成一张**空棋盘**，紧跟着的 `analysisScan(500)` 扫的也是空棋盘 ——
   * 用户点「在研究中打开并分析」，等来的是一局空的。100ms 不够长不是重点：
   * 再长也没用，**闭包捕获的那个函数本身就是旧的**。
   *
   * 判据落在「递给 `createSession` 的第一个参数是不是这局的 SGF」上，
   * 不落在「`loadFromSGF` 调过没有」——后者两种实现下都绿。
   *
   * 变异实跑（2026-08-22）：把这一处改回 `setTimeout(() => handleStartAnalysis(), 100)`
   * → 本条红，实得 `createSession(undefined, …)`。
   */
  it('analyzes the deep-linked kifu itself, not a blank board', async () => {
    (useAuth as Mock).mockReturnValue(confirmedAuth);

    renderPage('/galaxy/research?kifu_id=42&analyze=1');

    await waitFor(() => expect(createSession).toHaveBeenCalled());

    const [sgfArg, opts] = createSession.mock.calls[0];
    expect(sgfArg).toBeTypeOf('string');
    expect(sgfArg).toContain('B[pd]');
    expect(sgfArg).toContain('W[dd]');
    expect(opts).toMatchObject({ skipAnalysis: true });

    // 棋子也确实进了棋盘（不是「只把 SGF 转手递出去」）。
    await waitFor(() =>
      expect(screen.getByTestId('mock-live-board').getAttribute('data-moves')).toBe('4'));
  });

  /** 不带 `analyze=1` 时只装棋盘、不开会话 —— 全盘扫描是计费动作。 */
  it('loads a public deep-linked kifu anonymously without opening an analysis session', async () => {
    (useAuth as Mock).mockReturnValue(anonymousAuth);

    renderPage('/galaxy/research?kifu_id=42');

    await waitFor(() =>
      expect(screen.getByTestId('mock-live-board').getAttribute('data-moves')).toBe('4'));
    expect(createSession).not.toHaveBeenCalled();
    expect(API.analysisScan).not.toHaveBeenCalled();
  });

  // 复盘页「进入研究室」的落点（Fan 2026-08-22 点头补的深链）。
  it('loads the handed-off game from ?user_game_id', async () => {
    (useAuth as Mock).mockReturnValue(confirmedAuth);

    renderPage('/galaxy/research?user_game_id=g1');

    await waitFor(() => expect(getUserGame).toHaveBeenCalledWith('test-token', 'g1'));
    // 两手棋真的进了棋盘，不是只发了个请求。
    await waitFor(() => expect(screen.getByTestId('mock-live-board')).toHaveAttribute('data-moves', '2'));
  });

  it.each(['checking', 'unavailable'])('does not fetch a private deep link with a retained token during %s', (status) => {
    (useAuth as Mock).mockReturnValue({ ...anonymousAuth, status, token: 'saved-token', isLoading: status === 'checking' });

    renderPage('/galaxy/research?user_game_id=g1');

    expect(getUserGame).not.toHaveBeenCalled();
    expect(screen.getByTestId('mock-live-board')).toHaveAttribute('data-moves', '0');
  });

  it('waits for confirmed cookie identity before loading a private deep link', async () => {
    (useAuth as Mock).mockReturnValue({ ...anonymousAuth, status: 'checking', isLoading: true });
    const view = renderPage('/galaxy/research?user_game_id=g1');
    expect(getUserGame).not.toHaveBeenCalled();

    (useAuth as Mock).mockReturnValue({ ...confirmedAuth, token: null });
    view.rerender(pageElement('/galaxy/research?user_game_id=g1'));

    await waitFor(() => expect(getUserGame).toHaveBeenCalledWith(null, 'g1'));
    await waitFor(() => expect(screen.getByTestId('mock-live-board')).toHaveAttribute('data-moves', '2'));
  });

  it('does not load a private deep-link response after logout', async () => {
    let finish: (value: unknown) => void = () => {};
    getUserGame.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
    (useAuth as Mock).mockReturnValue(confirmedAuth);
    const view = renderPage('/galaxy/research?user_game_id=g1');
    expect(getUserGame).toHaveBeenCalledWith('test-token', 'g1');

    (useAuth as Mock).mockReturnValue(anonymousAuth);
    view.rerender(pageElement('/galaxy/research?user_game_id=g1'));
    await act(async () => { finish({ id: 'g1', sgf_content: USER_GAME_SGF }); });

    expect(screen.getByTestId('mock-live-board')).toHaveAttribute('data-moves', '0');
    expect(getUserGame).toHaveBeenCalledTimes(1);
  });

  it('loads only the current identity response after changing accounts', async () => {
    let finishOld: (value: unknown) => void = () => {};
    getUserGame.mockImplementationOnce(() => new Promise((resolve) => { finishOld = resolve; }));
    (useAuth as Mock).mockReturnValue(confirmedAuth);
    const view = renderPage('/galaxy/research?user_game_id=g1');

    (useAuth as Mock).mockReturnValue({ ...confirmedAuth, identityKey: 'two', token: 'new-token' });
    getUserGame.mockResolvedValueOnce({ id: 'g1', sgf_content: KIFU_SGF });
    view.rerender(pageElement('/galaxy/research?user_game_id=g1'));
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

    renderPage('/galaxy/research?user_game_id=g1&analyze=1');

    await waitFor(() => expect(screen.getByTestId('mock-live-board')).toHaveAttribute('data-moves', '2'));
    expect(API.analysisScan).not.toHaveBeenCalled();
  });

  // 未登录点「开始研究」——全盘分析要登录（`/api/analysis/scan` 与 `/progress` 都是
  // 必需的 `get_current_user`）。闸必须在**进 L2 之前**：一旦进去，屏上会是「正在分析
  // 棋局」加一个永远不会成功的「重试」，而且还会在服务端留下一个白建的会话壳。
  it('未登录点开始研究：说需要登录，且一个会话壳都不建', async () => {
    (useAuth as Mock).mockReturnValue(anonymousAuth);

    renderPage();
    fireEvent.click(screen.getByTestId('mock-start-analysis'));

    expect(await screen.findByTestId('login-required-message')).toHaveTextContent('全盘分析');
    expect(createSession).not.toHaveBeenCalled();
    expect(API.analysisScan).not.toHaveBeenCalled();
  });

  it('/me 探针还没回来时不误挡：不弹「需要登录」', async () => {
    (useAuth as Mock).mockReturnValue({ ...anonymousAuth, status: 'checking', isLoading: true });

    renderPage();
    fireEvent.click(screen.getByTestId('mock-start-analysis'));

    await waitFor(() => expect(createSession).toHaveBeenCalled());
    expect(screen.queryByTestId('login-required-message')).not.toBeInTheDocument();
  });

  it('已登录照常进 L2', async () => {
    (useAuth as Mock).mockReturnValue({ ...confirmedAuth, token: 'tok' });

    renderPage();
    fireEvent.click(screen.getByTestId('mock-start-analysis'));

    await waitFor(() => expect(createSession).toHaveBeenCalled());
    expect(screen.queryByTestId('login-required-message')).not.toBeInTheDocument();
  });
});
