import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route, Link } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import { API, ApiError, type GameState } from '../../api';
import GamePage from './GamePage';
import { clearActiveSession, readActiveSession, writeActiveSession } from '../utils/activeSession';

/**
 * 对弈·AI/升降级赛道(superpowers/tracks/kiosk-go-play-ai)的 GamePage 行为测试。
 * 只证行为与文案(jsdom 没有布局引擎);右栏几何在 tests/kiosk-screen-05-play-ai.spec.ts 里用真浏览器量。
 * 身份按盒上口径桩:`token: null`、`isAuthenticated: true`。
 */

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: null, isAuthenticated: true, user: { id: 1, username: 'box-user' } }),
}));
// 棋盘桩是一颗按钮:点它 = 在 (3,3) 落子。Task 2 用它证「终局之后点盘不发落子」。
vi.mock('../../components/Board', () => ({
  default: (p: { onMove?: (x: number, y: number) => void }) => (
    <button type="button" data-testid="board" onClick={() => p.onMove?.(3, 3)} />
  ),
}));

interface MockPanelProps { onAction: (a: string) => void; onTimeout?: (c: 'B' | 'W') => void; isGameOver?: boolean }
vi.mock('../components/game/GameControlPanel', () => ({
  default: (p: MockPanelProps) => (
    <div data-testid="game-control-panel">
      <button onClick={() => p.onAction('resign')}>MOCK_RESIGN</button>
      <button onClick={() => p.onAction('count')}>MOCK_COUNT</button>
      <button onClick={() => p.onTimeout?.('B')}>MOCK_TIMEOUT_B</button>
      {/* Task 2:右栏拿到的「本局已结束」 */}
      <span data-testid="panel-over">{String(p.isGameOver)}</span>
    </div>
  ),
}));

vi.mock('../utils/activeSession', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../utils/activeSession')>();
  return {
    ...actual,
    readActiveSession: vi.fn(actual.readActiveSession),
    writeActiveSession: vi.fn(actual.writeActiveSession),
    clearActiveSession: vi.fn(actual.clearActiveSession),
  };
});
vi.mock('../../api/geometryApi', () => ({ GeometryAPI: { calibrate: vi.fn().mockResolvedValue({}) } }));
vi.mock('../../features/aiLadder/api', () => ({ getAiLadderStatus: vi.fn() }));

const vision = vi.hoisted(() => ({ enabled: false, poseLocked: true, realSync: false }));
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
vi.mock('../hooks/useVisionSync', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../hooks/useVisionSync')>();
  return {
    useVisionSync: (sessionId: string | null) => vision.realSync
      ? actual.useVisionSync(sessionId)
      : { syncEvents: [], latestEvent: null, setupProgress: null, isSetupComplete: false },
  };
});

const sessionMock = vi.hoisted(() => ({
  gameState: null as unknown,
  error: null as string | null,
  connectionLost: null as 'rejected' | 'dropped' | null,
  physicalReminder: null as unknown,
  handleAction: vi.fn(),
  onMove: vi.fn(),
  setGameState: vi.fn(),
  setSessionId: vi.fn(),
  clearError: vi.fn(),
  clearPhysicalEngineError: vi.fn(),
}));
vi.mock('../../hooks/useGameSession', () => ({
  useGameSession: () => ({
    sessionId: 'play-ai-s1',
    setSessionId: sessionMock.setSessionId,
    gameState: sessionMock.gameState,
    setGameState: sessionMock.setGameState,
    error: sessionMock.error,
    connectionLost: sessionMock.connectionLost,
    clearError: sessionMock.clearError,
    onMove: sessionMock.onMove,
    onNavigate: vi.fn(),
    handleAction: sessionMock.handleAction,
    physicalReminder: sessionMock.physicalReminder,
    physicalEngineError: null,
    clearPhysicalEngineError: sessionMock.clearPhysicalEngineError,
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

function PlayPageStub() {
  const active = readActiveSession('game');
  return <div>PLAY_PAGE{active && <Link to={active.route}>继续上一局</Link>}</div>;
}

// 单独拎出来,是为了 `rerender(pageTree())` 能用同一棵树:改完桩的值再重渲,组件身份不变。
const pageTree = (sessionLinks = false) => (
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter initialEntries={['/kiosk/play/ai/game/play-ai-s1']}>
      {sessionLinks && <>
        <Link to="/kiosk/play/ai/game/play-ai-s1">SESSION_1</Link>
        <Link to="/kiosk/play/ai/game/play-ai-s2">SESSION_2</Link>
      </>}
      <Routes>
        <Route path="/kiosk/play/ai/game/:sessionId" element={<GamePage />} />
        <Route path="/kiosk/play" element={<PlayPageStub />} />
      </Routes>
    </MemoryRouter>
  </ThemeProvider>
);

const renderPage = () => render(pageTree());

describe('N25 · 对局屏错误条与断线出口', () => {
  it('一次性操作失败说人话，不印后端原文，× 能关', () => {
    sessionMock.gameState = makeState();
    sessionMock.error = 'Request failed 409: {"detail":"Not your turn"}';
    renderPage();
    expect(screen.getByText('这一步没有成功，请再试一次')).toBeInTheDocument();
    expect(screen.queryByText(/Request failed/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(sessionMock.clearError).toHaveBeenCalledOnce();
  });

  it('一次性错误 6 秒后调用清除，之前保持可见', () => {
    vi.useFakeTimers();
    sessionMock.gameState = makeState();
    sessionMock.error = 'Request failed 409';
    const view = renderPage();
    try {
      act(() => { vi.advanceTimersByTime(5999); });
      expect(sessionMock.clearError).not.toHaveBeenCalled();
      act(() => { vi.advanceTimersByTime(1); });
      expect(sessionMock.clearError).toHaveBeenCalledOnce();
    } finally { view.unmount(); vi.useRealTimers(); }
  });

  it('意外断开持续显示实际出口，超过 6 秒不消失，可以手动关', () => {
    vi.useFakeTimers();
    sessionMock.gameState = makeState();
    sessionMock.error = '实时连接已断开，棋盘不会自动更新，请刷新页面';
    sessionMock.connectionLost = 'dropped';
    const view = renderPage();
    try {
      const copy = /点「退出对局」→「先离开，不认输」，再从「继续上一局」回来/;
      expect(screen.getByText(copy)).toBeInTheDocument();
      expect(screen.queryByText(/请刷新页面/)).toBeNull();
      act(() => { vi.advanceTimersByTime(10000); });
      expect(screen.getByText(copy)).toBeInTheDocument();
      expect(sessionMock.clearError).not.toHaveBeenCalled();
      fireEvent.click(screen.getByRole('button', { name: /close/i }));
      act(() => { vi.advanceTimersByTime(1000); });
      expect(screen.queryByText(copy)).toBeNull();
      expect(sessionMock.connectionLost).toBe('dropped');
    } finally { view.unmount(); vi.useRealTimers(); }
  });

  it('被服务端拒绝仍显示原句，保留原因与重新登录提示', () => {
    sessionMock.gameState = makeState();
    sessionMock.error = '实时连接被拒绝（Invalid token），棋盘不会自动更新，请重新登录后重试';
    sessionMock.connectionLost = 'rejected';
    renderPage();
    expect(screen.getByText(sessionMock.error)).toBeInTheDocument();
  });

  it.each(['dropped', 'rejected'] as const)('断线 %s：先离开不认输，真实继续指针返回同一局', (reason) => {
    const original = makeState();
    sessionMock.gameState = original;
    sessionMock.connectionLost = reason;
    sessionMock.error = reason === 'dropped' ? '连接已断开' : '连接被拒绝';
    const resign = vi.spyOn(API, 'resign').mockResolvedValue({ state: original });
    const newGame = vi.spyOn(API, 'newGame').mockResolvedValue({ state: original });
    const createSession = vi.spyOn(API, 'createSession').mockResolvedValue({ session_id: 'unexpected' });
    renderPage();
    const saved = readActiveSession('game');
    expect(saved?.route).toBe('/kiosk/play/ai/game/play-ai-s1');
    fireEvent.click(screen.getByRole('button', { name: '退出对局' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '先离开，不认输' }));
    expect(screen.getByText('PLAY_PAGE')).toBeInTheDocument();
    expect(clearActiveSession).not.toHaveBeenCalled();
    expect(readActiveSession('game')).toEqual(saved);
    sessionMock.setSessionId.mockClear();
    fireEvent.click(screen.getByRole('link', { name: '继续上一局' }));
    expect(sessionMock.setSessionId).toHaveBeenCalledExactlyOnceWith('play-ai-s1');
    expect(screen.getByTestId('game-control-panel')).toBeInTheDocument();
    expect(sessionMock.gameState).toBe(original);
    expect(sessionMock.handleAction).not.toHaveBeenCalled();
    expect(sessionMock.clearPhysicalEngineError).not.toHaveBeenCalled();
    expect(resign).not.toHaveBeenCalled();
    expect(newGame).not.toHaveBeenCalled();
    expect(createSession).not.toHaveBeenCalled();
  });

  it('连着时退出框没有先离开', () => {
    sessionMock.gameState = makeState();
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: '退出对局' }));
    expect(within(screen.getByRole('dialog')).queryByText('先离开，不认输')).toBeNull();
  });
});

beforeEach(() => {
  vi.clearAllMocks();
  sessionMock.gameState = null;
  sessionMock.error = null;
  sessionMock.connectionLost = null;
  sessionMock.physicalReminder = null;
  vision.enabled = false;
  vision.realSync = false;
  vision.poseLocked = true;
  localStorage.clear();
  sessionStorage.clear();
  // MemoryRouter 不改真实 location；产品用它记录继续路由，测试也须提供真实页面路径。
  window.history.replaceState(null, '', '/kiosk/play/ai/game/play-ai-s1');
  sessionMock.handleAction.mockResolvedValue(undefined);
  sessionMock.onMove.mockResolvedValue(undefined);
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

describe('N21 · 本地对局的认输框说出是哪一方', () => {
  it('两个人面对面时先问哪一方认输，不能拿轮次猜认输方', () => {
    sessionMock.gameState = makeState({
      game_type: 'pvp_local', player_to_move: 'W',
      players_info: { B: seat('player:human', '小明'), W: seat('player:human', '小红') },
    });
    renderPage();
    fireEvent.click(screen.getByText('MOCK_RESIGN'));
    expect(screen.getByText('哪一方认输？')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '黑方认输' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '白方认输' })).toBeInTheDocument();
  });

  it('人机局仍是「确认认输？」—— 认输的一定是人,不用点名', () => {
    sessionMock.gameState = makeState();
    renderPage();
    fireEvent.click(screen.getByText('MOCK_RESIGN'));
    expect(screen.getByText('确认认输？')).toBeInTheDocument();
  });
});

describe('S1(r1)· 「本局已结束」认服务端的终局事实,翻手看棋不回退', () => {
  // 终局之后按了「上一手」:游标上的 end_result 变回 null,但这一局的终局事实还在。
  const steppedBack = () => makeState({ end_result: null, terminal_result: 'W+R', children: [['W', [3, 3]]] });

  it('终局后退到前一手:右栏与终局卡仍是终局,「继续上一局」照样清掉、不写回来', async () => {
    sessionMock.gameState = steppedBack();
    renderPage();
    expect(screen.getByTestId('panel-over').textContent).toBe('true');
    expect(screen.getByTestId('endgame-card')).toBeInTheDocument();
    await waitFor(() => expect(clearActiveSession).toHaveBeenCalledWith('game'));
    expect(writeActiveSession).not.toHaveBeenCalled();
  });

  it('终局之后点棋盘不发落子 —— 服务端只冻住终局那一手之后,翻回去的局面它照样收', () => {
    sessionMock.gameState = steppedBack();
    renderPage();
    fireEvent.click(screen.getByTestId('board'));
    expect(sessionMock.onMove).not.toHaveBeenCalled();
  });
});

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

  it('失败后重试在途时清掉旧错误，只显示正在数子', async () => {
    sessionMock.gameState = countable();
    let finish!: (v: unknown) => void;
    const spy = vi.spyOn(API, 'requestCount')
      .mockRejectedValueOnce(new Error(noScore))
      .mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
    renderPage();
    fireEvent.click(screen.getByText('MOCK_COUNT'));
    expect(await screen.findByText('形势分析没算出来，暂时数不了子，请稍后再试')).toBeInTheDocument();

    fireEvent.click(screen.getByText('MOCK_COUNT'));
    expect(screen.queryByText('形势分析没算出来，暂时数不了子，请稍后再试')).toBeNull();
    expect(screen.getByText('正在数子…')).toBeInTheDocument();
    expect(spy).toHaveBeenCalledTimes(2);
    finish({ state: sessionMock.gameState });
    await waitFor(() => expect(screen.queryByText('正在数子…')).toBeNull());
  });

  it('r1 C2:等分析的这几秒里局面变了 → 说「局面变了，请重新数子」', async () => {
    sessionMock.gameState = countable();
    vi.spyOn(API, 'requestCount').mockRejectedValue(new Error('Request failed 409: {"detail":"Position changed while counting"}'));
    renderPage();
    fireEvent.click(screen.getByText('MOCK_COUNT'));
    expect(await screen.findByText('数子这几秒里局面变了，请重新数子')).toBeInTheDocument();
  });
});

describe('A18 · 时间耗尽判超时', () => {
  beforeEach(() => {
    vi.spyOn(API, 'timeout').mockResolvedValue({ state: makeState({ terminal_result: 'W+T' }) });
    vi.spyOn(API, 'getState').mockResolvedValue({ state: makeState() });
  });

  it('到点带局/手/方；同一帧回调两次只发一次；盒上 token 为 null 仍发', () => {
    sessionMock.gameState = makeState();
    renderPage();
    fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
    fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
    expect(API.timeout).toHaveBeenCalledExactlyOnceWith('play-ai-s1', undefined, {
      expected_game_id: 'g', expected_node_id: 5, color: 'B',
    });
    expect(sessionMock.handleAction).not.toHaveBeenCalled();
  });

  it.each([[409, 'stale_turn'], [409, 'already_ended'], [403, 'only allowed on the human turn']] as const)('%s %s 只重同步，不上红条', async (status, reason) => {
    vi.mocked(API.timeout).mockRejectedValue(new ApiError(status, `timeout rejected: ${reason}`));
    const fresh = makeState({ current_node_id: 6 });
    vi.mocked(API.getState).mockResolvedValue({ state: fresh });
    sessionMock.gameState = makeState();
    renderPage();
    fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
    await waitFor(() => expect(sessionMock.setGameState).toHaveBeenCalledWith(fresh));
    expect(API.getState).toHaveBeenCalledWith('play-ai-s1', undefined);
    fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
    expect(API.timeout).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/超时判定没有送达|Request failed/)).toBeNull();
  });

  it('clock_not_expired 重同步后同一手只再核一次，不依赖时钟再次从假变真', async () => {
    vi.useFakeTimers();
    try {
      vi.mocked(API.timeout).mockRejectedValue(new ApiError(409, 'timeout rejected: clock_not_expired'));
      sessionMock.gameState = makeState();
      renderPage();
      fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
      await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
      expect(API.timeout).toHaveBeenCalledTimes(2);
      fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
      await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
      expect(API.timeout).toHaveBeenCalledTimes(2);
    } finally { vi.useRealTimers(); }
  });

  it.each([
    { children: [['W', [3, 3]]] },
    { terminal_result: 'W+R' },
    { player_to_move: 'W' },
    { last_ladder_error: true },
    { game_type: 'ai_ladder_ranked', players_info: { B: seat('player:ai', 'AI'), W: seat('player:human', '我') } },
  ])('翻手/终局/非回合/引擎停摆/升降级 AI 回合不发超时 %j', (over) => {
    sessionMock.gameState = makeState(over as Partial<GameState>);
    renderPage();
    fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
    expect(API.timeout).not.toHaveBeenCalled();
  });

  it('503 等失败按 2/5/10 秒退避，三次重发后显示未送达', async () => {
    vi.useFakeTimers();
    try {
      vi.mocked(API.timeout).mockRejectedValue(new ApiError(503, 'unavailable'));
      sessionMock.gameState = makeState();
      renderPage();
      fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
      await act(async () => { await vi.advanceTimersByTimeAsync(1999); });
      expect(API.timeout).toHaveBeenCalledTimes(1);
      for (const [ms, count] of [[1, 2], [5000, 3], [10000, 4]]) {
        await act(async () => { await vi.advanceTimersByTimeAsync(ms); });
        expect(API.timeout).toHaveBeenCalledTimes(count);
      }
      expect(screen.getByText('超时判定没有送达，请检查连接后重新进入这一局')).toBeInTheDocument();
      await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
      expect(API.timeout).toHaveBeenCalledTimes(4);
    } finally { vi.useRealTimers(); }
  });

  it.each([new ApiError(401, 'unauthorized'), new TypeError('Failed to fetch')])('401/网络错误有限退避且提示可关闭: %s', async (error) => {
    vi.useFakeTimers();
    try {
      vi.mocked(API.timeout).mockRejectedValue(error);
      sessionMock.gameState = makeState();
      renderPage();
      fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
      await act(async () => { await vi.advanceTimersByTimeAsync(17_000); });
      expect(API.timeout).toHaveBeenCalledTimes(4);
      const message = '超时判定没有送达，请检查连接后重新进入这一局';
      const alert = screen.getByText(message).closest('[role="alert"]')!;
      fireEvent.click(alert.querySelector('button')!);
      await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
      expect(screen.queryByText(message)).toBeNull();
      expect(API.timeout).toHaveBeenCalledTimes(4);
    } finally { vi.useRealTimers(); }
  });

  it('第一次发送失败后恢复：退避重发结果交回会话，不显示未送达', async () => {
    vi.useFakeTimers();
    try {
      const fresh = makeState({ terminal_result: 'W+T' });
      vi.mocked(API.timeout).mockRejectedValueOnce(new ApiError(503, 'unavailable')).mockResolvedValue({ state: fresh });
      sessionMock.gameState = makeState();
      renderPage();
      fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
      await act(async () => { await vi.advanceTimersByTimeAsync(20_000); });
      expect(API.timeout).toHaveBeenCalledTimes(2);
      expect(sessionMock.setGameState).toHaveBeenCalledWith(fresh);
      expect(screen.queryByText(/超时判定没有送达/)).toBeNull();
    } finally { vi.useRealTimers(); }
  });

  it('未送达提示随旧轮次结束；下一手恢复成功不会保留旧提示', async () => {
    vi.useFakeTimers();
    try {
      vi.mocked(API.timeout).mockRejectedValue(new ApiError(503, 'unavailable'));
      sessionMock.gameState = makeState();
      const { rerender } = renderPage();
      fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
      await act(async () => { await vi.advanceTimersByTimeAsync(17_000); });
      expect(screen.getByText(/超时判定没有送达/)).toBeInTheDocument();
      sessionMock.gameState = makeState({ current_node_id: 7 });
      rerender(pageTree());
      const fresh = makeState({ current_node_id: 7, terminal_result: 'W+T' });
      vi.mocked(API.timeout).mockResolvedValue({ state: fresh });
      fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
      await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
      expect(API.timeout).toHaveBeenCalledTimes(5);
      expect(sessionMock.setGameState).toHaveBeenCalledWith(fresh);
      expect(screen.queryByText(/超时判定没有送达/)).toBeNull();
    } finally { vi.useRealTimers(); }
  });

  it.each([
    { current_node_id: 6 }, { game_id: 'new-game' }, { player_to_move: 'W' },
    { end_result: 'W+R' }, { terminal_result: 'W+R' }, { children: [['W', [3, 3]]] },
    { last_ladder_error: true },
    { game_type: 'ai_ladder_ranked', players_info: { B: seat('player:ai', 'AI'), W: seat('player:human', '我') } },
  ])('旧轮次失败之后状态变化清理重试: %j', async (over) => {
    vi.useFakeTimers();
    try {
      vi.mocked(API.timeout).mockRejectedValue(new ApiError(503, 'unavailable'));
      sessionMock.gameState = makeState();
      const { rerender } = renderPage();
      fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
      await act(async () => { await vi.advanceTimersByTimeAsync(100); });
      sessionMock.gameState = makeState(over as Partial<GameState>);
      rerender(pageTree());
      await act(async () => { await vi.advanceTimersByTimeAsync(20_000); });
      expect(API.timeout).toHaveBeenCalledTimes(1);
      expect(screen.queryByText(/超时判定没有送达/)).toBeNull();
    } finally { vi.useRealTimers(); }
  });

  it('卸载取消重试，换局也不接受旧请求晚到的结果', async () => {
    vi.useFakeTimers();
    try {
      vi.mocked(API.timeout).mockRejectedValue(new ApiError(503, 'unavailable'));
      sessionMock.gameState = makeState();
      const first = renderPage();
      fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
      await act(async () => { await vi.advanceTimersByTimeAsync(100); });
      first.unmount();
      await act(async () => { await vi.advanceTimersByTimeAsync(20_000); });
      expect(API.timeout).toHaveBeenCalledTimes(1);

      let finish!: (result: { state: GameState }) => void;
      vi.mocked(API.timeout).mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
      const second = renderPage();
      fireEvent.click(screen.getByText('MOCK_TIMEOUT_B'));
      sessionMock.gameState = makeState({ game_id: 'new-game' });
      second.rerender(pageTree());
      await act(async () => { finish({ state: makeState({ terminal_result: 'W+T' }) }); });
      expect(sessionMock.setGameState).not.toHaveBeenCalled();
    } finally { vi.useRealTimers(); }
  });

});

describe('A9 · 对局分析按实际用途请求', () => {
  it('本地对局不显示胜率块，但继续请求后台分析供数子使用', () => {
    const spy = vi.spyOn(API, 'analyzeCurrent').mockResolvedValue({});
    sessionMock.gameState = makeState({
      game_type: 'pvp_local',
      players_info: { B: seat('player:human', '小明'), W: seat('player:human', '小红') },
    });
    renderPage();
    expect(spy).toHaveBeenCalledWith('play-ai-s1');
  });

  it('人机自由对弈照旧请求(默认开还是关等 Fan 定,本轮不动)', () => {
    const spy = vi.spyOn(API, 'analyzeCurrent').mockResolvedValue({});
    sessionMock.gameState = makeState();
    renderPage();
    expect(spy).toHaveBeenCalledWith('play-ai-s1');
  });
});


describe('A20 + A21 · 实体盘降级与重标定弹层', () => {
  const physical = () => {
    vision.enabled = true;
    localStorage.removeItem('kiosk_play_on_board');
    sessionMock.gameState = makeState();
  };

  it('进局还没锁定过位姿:不弹移动警告', () => {
    physical();
    vision.poseLocked = false;
    renderPage();
    expect(screen.queryByText('棋盘可能被移动')).toBeNull();
  });

  it('锁定后丢失才提示，而且说明亮灯和清空棋盘', () => {
    physical();
    const view = renderPage();
    vision.poseLocked = false;
    view.rerender(pageTree());
    expect(screen.getByText('棋盘可能被移动')).toBeInTheDocument();
    expect(screen.getByText(/重新标定会亮灯.*要先把棋盘上的子全部拿走/)).toBeInTheDocument();
    expect(screen.queryByText(/无需 LED/)).toBeNull();
  });

  it('降级撤掉实体盘 UI，同局重挂载仍可在屏幕落子', async () => {
    physical();
    sessionMock.physicalReminder = { kind: 'escalation', to_place: [], to_remove: [] };
    const view = renderPage();
    // MUI 弹框为页面加 aria-hidden；否定断言也必须包含隐藏元素，不能因过渡期被藏而误绿。
    expect(screen.getByRole('button', { name: /重置识别/, hidden: true })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '改用屏幕落子' }));
    vision.poseLocked = false;
    view.rerender(pageTree());
    await waitFor(() => expect(screen.queryByRole('button', { name: /重置识别/, hidden: true })).toBeNull());
    expect(screen.queryByText('棋盘可能被移动')).toBeNull();
    expect(sessionStorage.getItem('kiosk_screen_fallback:play-ai-s1')).toBe('1');
    // 解绑前已排队的旧实体盘通知不能把提示重新打开。
    sessionMock.physicalReminder = { kind: 'reminder', to_place: [[3, 3]], to_remove: [] };
    view.rerender(pageTree());
    expect(screen.queryByText('请先将 AI 棋子摆到棋盘亮灯处')).toBeNull();
    sessionMock.physicalReminder = { kind: 'escalation', to_place: [[3, 3]], to_remove: [] };
    view.rerender(pageTree());
    await waitFor(() => expect(screen.queryByRole('button', { name: '改用屏幕落子', hidden: true })).toBeNull());
    fireEvent.click(screen.getByTestId('board'));
    expect(sessionMock.onMove).toHaveBeenCalledWith(3, 3);

    view.unmount();
    sessionMock.physicalReminder = null;
    renderPage();
    expect(screen.queryByRole('button', { name: /重置识别/, hidden: true })).toBeNull();
    expect(screen.queryByText('棋盘可能被移动')).toBeNull();
  });

  it('同一组件切换 session 时，各局只读自己的降级记录', () => {
    physical();
    sessionStorage.setItem('kiosk_screen_fallback:play-ai-s2', '1');
    render(pageTree(true));
    expect(screen.getByRole('button', { name: /重置识别/, hidden: true })).toBeInTheDocument();
    fireEvent.click(screen.getByText('SESSION_2'));
    expect(screen.queryByRole('button', { name: /重置识别/, hidden: true })).toBeNull();
    fireEvent.click(screen.getByText('SESSION_1'));
    expect(screen.getByRole('button', { name: /重置识别/, hidden: true })).toBeInTheDocument();
    expect(sessionStorage.getItem('kiosk_screen_fallback:play-ai-s1')).toBeNull();
  });

  it('上一局锁定过的位姿历史不会让新局首次未锁定误报移动', () => {
    physical();
    const view = render(pageTree(true));
    vision.poseLocked = false;
    fireEvent.click(screen.getByText('SESSION_2'));
    expect(screen.queryByText('棋盘可能被移动')).toBeNull();
    // 同一新局锁定后再丢失仍须提示，不能通过永久禁用弹层使上面的断言变绿。
    vision.poseLocked = true;
    view.rerender(pageTree(true));
    vision.poseLocked = false;
    view.rerender(pageTree(true));
    expect(screen.getByText('棋盘可能被移动')).toBeInTheDocument();
  });

  it('真实 useVisionSync 生命周期:绑定一次，屏幕降级只解绑一次', async () => {
    physical();
    vision.realSync = true;
    sessionMock.physicalReminder = { kind: 'escalation', to_place: [], to_remove: [] };
    const bind = vi.spyOn(API, 'visionBind').mockResolvedValue(undefined);
    const unbind = vi.spyOn(API, 'visionUnbind').mockResolvedValue(undefined);
    vi.stubGlobal('WebSocket', class { close = vi.fn(); });
    const view = renderPage();
    try {
      await waitFor(() => expect(bind).toHaveBeenCalledWith('play-ai-s1'));
      fireEvent.click(screen.getByRole('button', { name: '改用屏幕落子' }));
      await waitFor(() => expect(screen.queryByRole('button', { name: /重置识别/, hidden: true })).toBeNull());
      expect(bind).toHaveBeenCalledTimes(1);
      expect(unbind).toHaveBeenCalledTimes(1);
      view.unmount();
      expect(unbind).toHaveBeenCalledTimes(1);
    } finally {
      view.unmount();
      vi.unstubAllGlobals();
    }
  });
});
