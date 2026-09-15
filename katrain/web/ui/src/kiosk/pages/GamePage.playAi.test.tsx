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
