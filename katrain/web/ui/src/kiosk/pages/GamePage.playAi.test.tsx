import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import { API, ApiError, type GameState } from '../../api';
import GamePage from './GamePage';

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
  onMove: vi.fn(),
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
    onMove: sessionMock.onMove,
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
