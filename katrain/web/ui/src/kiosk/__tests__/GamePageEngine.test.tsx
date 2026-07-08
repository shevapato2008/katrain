import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import type { GameState } from '../../api';

vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => ({ rotation: 0, isPortrait: false, setRotation: vi.fn() }),
}));

// Mock vision context (GamePage reads visionStatus + isVisionEnabled directly).
// Disabled vision keeps all vision branches (overlay, toasts, useVisionSync) inert.
vi.mock('../context/VisionContext', () => ({
  useVision: () => ({
    isVisionEnabled: false,
    visionStatus: { cameraConnected: true },
    refreshStatus: vi.fn(),
  }),
}));

// Mock auth
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'mock-token', isAuthenticated: true, user: { id: 1, username: 'test' }, login: vi.fn(), logout: vi.fn() }),
}));

// Mock Board with a lightweight stub that exposes a button to trigger onMove(3, 3) —
// the real Board is canvas-based and can't render in jsdom, and wiring the real thing
// would be far heavier than exercising the onMove error path needs.
vi.mock('../../components/Board', () => ({
  default: (props: any) => (
    <div data-testid="board">
      <button onClick={() => props.onMove(3, 3)}>trigger-move</button>
    </div>
  ),
}));

// Mock PlayerCard (uses translations)
vi.mock('../../components/PlayerCard', () => ({
  default: (props: any) => <div data-testid={`player-card-${props.player}`}>{props.info.name}</div>,
}));

// Mock ScoreGraph (SVG-heavy)
vi.mock('../../components/ScoreGraph', () => ({
  default: () => <div data-testid="score-graph-component">ScoreGraph</div>,
}));

const mockSetSessionId = vi.fn();
const mockHandleAction = vi.fn();
const mockOnMove = vi.fn();
const mockOnNavigate = vi.fn();
// API is mocked (below) so 数子 (count) and the on-demand analysis effect don't hit the network.
const mockRequestCount = vi.fn();
const mockAnalyzeCurrent = vi.fn();
const mockHintDismiss = vi.fn();
const mockHint = vi.fn();

const mockGameState: GameState = {
  game_id: 'test-game',
  board_size: [19, 19],
  komi: 6.5,
  handicap: 0,
  ruleset: '日本',
  current_node_id: 42,
  current_node_index: 42,
  history: [
    { node_id: 0, score: 0, winrate: 0.5 },
    { node_id: 1, score: 0.3, winrate: 0.52 },
  ],
  player_to_move: 'B',
  stones: [],
  last_move: [3, 3],
  prisoner_count: { B: 3, W: 5 },
  analysis: null,
  commentary: '',
  is_root: false,
  is_pass: false,
  end_result: null,
  children: [],
  ghost_stones: [],
  players_info: {
    B: { player_type: 'player:human', player_subtype: '', name: '张三', calculated_rank: '2D', periods_used: 0, main_time_used: 0 },
    W: { player_type: 'player:ai', player_subtype: 'golaxy', name: '星阵', calculated_rank: '9D', periods_used: 0, main_time_used: 0 },
  },
  note: '',
  ui_state: {
    show_children: false, show_dots: false, show_hints: false, show_policy: false,
    show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false,
  },
  language: 'zh',
} as GameState;

vi.mock('../../hooks/useGameSession', () => ({
  useGameSession: () => ({
    sessionId: 'test-session',
    setSessionId: mockSetSessionId,
    gameState: mockGameState,
    setGameState: vi.fn(),
    error: null,
    onMove: mockOnMove,
    onNavigate: mockOnNavigate,
    handleAction: mockHandleAction,
    initNewSession: vi.fn(),
    lastLog: null,
    chatMessages: [],
    sendChat: vi.fn(),
    gameEndData: null,
  }),
}));

// Mock the API (数子 → requestCount; the 领地/图表 effect → analyzeCurrent). `mock`-prefixed
// names are hoist-safe inside a vi.mock factory.
vi.mock('../../api', () => ({
  API: {
    requestCount: (...a: any[]) => mockRequestCount(...a),
    analyzeCurrent: (...a: any[]) => mockAnalyzeCurrent(...a),
    hintDismiss: (...a: any[]) => mockHintDismiss(...a),
    hint: (...a: any[]) => mockHint(...a),
  },
}));

// Import after mocks
import GamePage from '../pages/GamePage';

const renderPage = (engineMode: boolean) =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={['/kiosk/play/cross-platform/engine/game/test-session']}>
        <Routes>
          <Route path="/kiosk/play/cross-platform/engine/game/:sessionId" element={<GamePage engineMode={engineMode} />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('GamePage engine mode', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockOnMove.mockReset();
    mockRequestCount.mockResolvedValue({ state: mockGameState });
    mockAnalyzeCurrent.mockResolvedValue({});
    mockHintDismiss.mockResolvedValue({ ok: true });
  });

  it('keeps Pass/Score/Resign usable in engineMode (special actions no longer disabled)', async () => {
    renderPage(true);

    // 停一手 is now enabled during AI play → routes through session.handleAction.
    fireEvent.click(screen.getByText('停一手'));
    expect(mockHandleAction).toHaveBeenCalledWith('pass');

    // 数子 is now enabled → GamePage counts directly via the count API (HvAI completes
    // immediately), NOT via session.handleAction.
    fireEvent.click(screen.getByText('数子'));
    await waitFor(() => expect(mockRequestCount).toHaveBeenCalledWith('test-session'));
    expect(mockHandleAction).not.toHaveBeenCalledWith('count');

    // Resign still opens the confirm dialog (intercepted before session.handleAction).
    fireEvent.click(screen.getByText('认输'));
    expect(screen.getByText('确认认输？')).toBeInTheDocument();
  });

  it('routes Pass to handleAction and Score to the count API (baseline)', async () => {
    renderPage(false);

    fireEvent.click(screen.getByText('停一手'));
    expect(mockHandleAction).toHaveBeenCalledWith('pass');

    fireEvent.click(screen.getByText('数子'));
    await waitFor(() => expect(mockRequestCount).toHaveBeenCalledWith('test-session'));
  });

  it('shows the engine error toast when a move fails in engineMode', async () => {
    mockOnMove.mockRejectedValueOnce(new Error('engine unreachable'));
    renderPage(true);

    fireEvent.click(screen.getByText('trigger-move'));

    expect(await screen.findByText(/AI 连接出错/)).toBeInTheDocument();
  });

  it('does NOT show the engine error toast when a move fails without engineMode', async () => {
    mockOnMove.mockRejectedValueOnce(new Error('engine unreachable'));
    renderPage(false);

    fireEvent.click(screen.getByText('trigger-move'));

    // Let the rejected promise's microtask settle before asserting absence.
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByText(/AI 连接出错/)).not.toBeInTheDocument();
  });
});
