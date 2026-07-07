import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import { API } from '../../api';
import type { GameState } from '../../api';

// Mock only `platformEngineAnalysis` on the real api.ts module — everything else (incl.
// hintDismiss, called on unmount) keeps its real (fetch-based, caught-and-ignored) impl,
// matching this test file's pre-existing baseline behavior.
vi.mock('../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api')>();
  return { ...actual, API: { ...actual.API, platformEngineAnalysis: vi.fn() } };
});

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
// would be far heavier than exercising the onMove error path needs. Also surfaces the
// `engineOverlay` prop as data attributes so tests can assert the decoded overlay
// GamePage hands to Board without fighting jsdom canvas.
vi.mock('../../components/Board', () => ({
  default: (props: any) => (
    <div
      data-testid="board"
      data-active-kind={props.engineOverlay?.kind ?? ''}
      data-overlay={JSON.stringify(props.engineOverlay ?? null)}
    >
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

// Import after mocks
import GamePage from '../pages/GamePage';

const renderTree = (engineMode: boolean) => (
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter initialEntries={['/kiosk/play/cross-platform/engine/game/test-session']}>
      <Routes>
        <Route path="/kiosk/play/cross-platform/engine/game/:sessionId" element={<GamePage engineMode={engineMode} />} />
      </Routes>
    </MemoryRouter>
  </ThemeProvider>
);

const renderPage = (engineMode: boolean) => render(renderTree(engineMode));

describe('GamePage engine mode', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockOnMove.mockReset();
    (API.platformEngineAnalysis as ReturnType<typeof vi.fn>).mockReset();
  });

  afterEach(() => {
    // Some tests mutate mockGameState.current_node_id to simulate the position
    // advancing — restore it so it doesn't bleed into later tests.
    mockGameState.current_node_id = 42;
  });

  it('disables Pass and Score when engineMode, but keeps Resign enabled', () => {
    renderPage(true);

    // Clicking a disabled ItemToggle must not reach session.handleAction (via GamePage's
    // handleAction wrapper) — ItemToggle sets onClick to undefined when disabled.
    fireEvent.click(screen.getByText('停一手'));
    fireEvent.click(screen.getByText('数子'));
    expect(mockHandleAction).not.toHaveBeenCalled();

    // Resign must stay enabled — clicking it should still open the confirm dialog
    // (GamePage's handleAction intercepts 'resign' before calling session.handleAction).
    fireEvent.click(screen.getByText('认输'));
    expect(screen.getByText('确认认输？')).toBeInTheDocument();
  });

  it('leaves Pass and Score enabled without engineMode (baseline)', () => {
    renderPage(false);

    fireEvent.click(screen.getByText('停一手'));
    expect(mockHandleAction).toHaveBeenCalledWith('pass');

    fireEvent.click(screen.getByText('数子'));
    expect(mockHandleAction).toHaveBeenCalledWith('count');
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

  describe('星阵隧道分析 (领地/支招/变化图)', () => {
    it('renders the three engine buttons and hides local 建议/图表/形势 + ScoreGraph in engineMode', () => {
      renderPage(true);

      expect(screen.getByText('领地')).toBeInTheDocument();
      expect(screen.getByText('支招')).toBeInTheDocument();
      expect(screen.getByText('变化图')).toBeInTheDocument();

      // No local KataGo analysis controls and no winrate chart — golaxy 人机对弈 has neither.
      expect(screen.queryByText('建议')).not.toBeInTheDocument();
      expect(screen.queryByText('图表')).not.toBeInTheDocument();
      expect(screen.queryByText('形势')).not.toBeInTheDocument();
      expect(screen.queryByTestId('score-graph')).not.toBeInTheDocument();
      expect(screen.queryByTestId('score-graph-component')).not.toBeInTheDocument();
    });

    it('leaves the local 领地/建议/图表 toggles in place (unchanged) without engineMode', () => {
      renderPage(false);

      expect(screen.getByText('领地')).toBeInTheDocument();
      expect(screen.getByText('建议')).toBeInTheDocument();
      expect(screen.getByText('图表')).toBeInTheDocument();
    });

    it('clicking 支招 calls API.platformEngineAnalysis(golaxy, sessionId, options, token)', async () => {
      (API.platformEngineAnalysis as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: false, reason: 'insufficient', kind: 'options',
      });
      renderPage(true);

      fireEvent.click(screen.getByText('支招'));

      await waitFor(() => {
        expect(API.platformEngineAnalysis).toHaveBeenCalledWith('golaxy', 'test-session', 'options', 'mock-token');
      });
    });

    it('ok:true sets activeEngineKind and passes the decoded overlay through to Board (options)', async () => {
      const candidates = [
        { col: 3, row: 3, prob: 0.6, winrate: 0.55, delta: -1.2 },
        { col: 15, row: 15, prob: 0.3, winrate: 0.5, delta: -2.1 },
      ];
      (API.platformEngineAnalysis as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true, kind: 'options', data: { candidates },
      });
      renderPage(true);

      fireEvent.click(screen.getByText('支招'));

      await waitFor(() => {
        expect(screen.getByTestId('board')).toHaveAttribute('data-active-kind', 'options');
      });
      const overlay = JSON.parse(screen.getByTestId('board').getAttribute('data-overlay')!);
      expect(overlay).toEqual({ kind: 'options', candidates });
    });

    it('clicking the same active kind again toggles the overlay off (no re-fetch)', async () => {
      (API.platformEngineAnalysis as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true, kind: 'area', data: { ownership: [{ col: 3, row: 3, value: 0.9 }], winrate: 0.6, delta: 1 },
      });
      renderPage(true);

      fireEvent.click(screen.getByText('领地'));
      await waitFor(() => expect(screen.getByTestId('board')).toHaveAttribute('data-active-kind', 'area'));

      fireEvent.click(screen.getByText('领地'));
      await waitFor(() => expect(screen.getByTestId('board')).toHaveAttribute('data-active-kind', ''));
      expect(API.platformEngineAnalysis).toHaveBeenCalledTimes(1);
    });

    it('clicking a DIFFERENT kind replaces the active overlay (mutual exclusion)', async () => {
      (API.platformEngineAnalysis as ReturnType<typeof vi.fn>)
        .mockResolvedValueOnce({ ok: true, kind: 'area', data: { ownership: [{ col: 3, row: 3, value: 0.9 }], winrate: 0.6, delta: 1 } })
        .mockResolvedValueOnce({ ok: true, kind: 'variation', data: { sequence: [{ col: 3, row: 3 }, { col: 4, row: 4 }], winrate: 0.5, delta: 0 } });
      renderPage(true);

      fireEvent.click(screen.getByText('领地'));
      await waitFor(() => expect(screen.getByTestId('board')).toHaveAttribute('data-active-kind', 'area'));

      fireEvent.click(screen.getByText('变化图'));
      await waitFor(() => expect(screen.getByTestId('board')).toHaveAttribute('data-active-kind', 'variation'));
    });

    it('ok:false insufficient shows the 充值 modal and leaves the current overlay untouched', async () => {
      (API.platformEngineAnalysis as ReturnType<typeof vi.fn>)
        .mockResolvedValueOnce({ ok: true, kind: 'area', data: { ownership: [{ col: 3, row: 3, value: 0.9 }], winrate: 0.6, delta: 1 } })
        .mockResolvedValueOnce({ ok: false, reason: 'insufficient', kind: 'options' });
      renderPage(true);

      fireEvent.click(screen.getByText('领地'));
      await waitFor(() => expect(screen.getByTestId('board')).toHaveAttribute('data-active-kind', 'area'));

      fireEvent.click(screen.getByText('支招'));

      expect(await screen.findByText(/请在星阵.*充值/)).toBeInTheDocument();
      expect(screen.getByText(/本终端不代充/)).toBeInTheDocument();
      // The insufficient response must not disturb the already-active 领地 overlay.
      expect(screen.getByTestId('board')).toHaveAttribute('data-active-kind', 'area');
    });

    it('closes the 充值 modal on 关闭 without touching the active overlay', async () => {
      (API.platformEngineAnalysis as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: false, reason: 'insufficient', kind: 'variation',
      });
      renderPage(true);

      fireEvent.click(screen.getByText('变化图'));
      expect(await screen.findByText(/变化图.*已用尽/)).toBeInTheDocument();

      fireEvent.click(screen.getByText('关闭'));
      await waitFor(() => {
        expect(screen.queryByText(/请在星阵.*充值/)).not.toBeInTheDocument();
      });
    });

    it('clears the overlay + active kind when the board position changes (stale-overlay fix)', async () => {
      (API.platformEngineAnalysis as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true, kind: 'area', data: { ownership: [{ col: 3, row: 3, value: 0.9 }], winrate: 0.6, delta: 1 },
      });
      const { rerender } = renderPage(true);

      fireEvent.click(screen.getByText('领地'));
      await waitFor(() => expect(screen.getByTestId('board')).toHaveAttribute('data-active-kind', 'area'));

      // Simulate the position advancing (a move played, human or AI) by mutating the
      // mocked session's current_node_id and re-rendering, the way React would after
      // useGameSession's underlying state updates.
      mockGameState.current_node_id = 43;
      rerender(renderTree(true));

      await waitFor(() => expect(screen.getByTestId('board')).toHaveAttribute('data-active-kind', ''));
      expect(screen.getByTestId('board').getAttribute('data-overlay')).toBe('null');
    });

    it('does NOT clear the overlay on an unrelated re-render (same current_node_id)', async () => {
      (API.platformEngineAnalysis as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true, kind: 'area', data: { ownership: [{ col: 3, row: 3, value: 0.9 }], winrate: 0.6, delta: 1 },
      });
      const { rerender } = renderPage(true);

      fireEvent.click(screen.getByText('领地'));
      await waitFor(() => expect(screen.getByTestId('board')).toHaveAttribute('data-active-kind', 'area'));

      // Re-render with the same current_node_id (unrelated re-render) — overlay must survive.
      rerender(renderTree(true));

      expect(screen.getByTestId('board')).toHaveAttribute('data-active-kind', 'area');
    });

    it('shows the engine error toast when platformEngineAnalysis rejects, leaving overlay/active kind unchanged', async () => {
      (API.platformEngineAnalysis as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('network fail'));
      renderPage(true);

      fireEvent.click(screen.getByText('支招'));

      expect(await screen.findByText(/AI 连接出错/)).toBeInTheDocument();
      expect(screen.getByTestId('board')).toHaveAttribute('data-active-kind', '');
      expect(screen.getByTestId('board').getAttribute('data-overlay')).toBe('null');
    });

    it('discards a stale ok:true response that resolves after the position has advanced (race fix)', async () => {
      let resolveAnalysis: (value: unknown) => void = () => {};
      (API.platformEngineAnalysis as ReturnType<typeof vi.fn>).mockImplementationOnce(
        () => new Promise((resolve) => { resolveAnalysis = resolve; })
      );
      const { rerender } = renderPage(true);

      fireEvent.click(screen.getByText('支招'));
      await waitFor(() => expect(API.platformEngineAnalysis).toHaveBeenCalledTimes(1));

      // Position advances (a move played) while the request is still in flight.
      mockGameState.current_node_id = 43;
      rerender(renderTree(true));
      await waitFor(() => expect(screen.getByTestId('board')).toHaveAttribute('data-active-kind', ''));

      // The stale request now finally resolves ok:true, computed for the OLD position.
      resolveAnalysis({ ok: true, kind: 'options', data: { candidates: [{ col: 3, row: 3, prob: 0.6, winrate: 0.55, delta: -1.2 }] } });

      // Give the resolved promise's continuation a tick to run, then assert the stale
      // overlay was NOT resurrected — Board still sees no active overlay.
      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(screen.getByTestId('board')).toHaveAttribute('data-active-kind', '');
      expect(screen.getByTestId('board').getAttribute('data-overlay')).toBe('null');
    });

    it('a second click while a request is in-flight does not trigger a second platformEngineAnalysis call (quota guard)', async () => {
      let resolveFirst: (value: unknown) => void = () => {};
      (API.platformEngineAnalysis as ReturnType<typeof vi.fn>).mockImplementationOnce(
        () => new Promise((resolve) => { resolveFirst = resolve; })
      );
      renderPage(true);

      fireEvent.click(screen.getByText('支招'));
      fireEvent.click(screen.getByText('支招'));
      fireEvent.click(screen.getByText('领地'));

      expect(API.platformEngineAnalysis).toHaveBeenCalledTimes(1);

      resolveFirst({ ok: true, kind: 'options', data: { candidates: [] } });
      await waitFor(() => expect(screen.getByTestId('board')).toHaveAttribute('data-active-kind', 'options'));

      // Once the in-flight request resolves, the guard must release — a further click works.
      (API.platformEngineAnalysis as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true, kind: 'area', data: { ownership: [], winrate: 0.5, delta: 0 },
      });
      fireEvent.click(screen.getByText('领地'));
      await waitFor(() => expect(API.platformEngineAnalysis).toHaveBeenCalledTimes(2));
    });
  });
});
