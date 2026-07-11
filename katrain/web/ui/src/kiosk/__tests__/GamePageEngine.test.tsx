import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import { API } from '../../api';
import type { GameState } from '../../api';
// Real backend-generated contract fixture (Task 1/2): engine game, human=B,
// platform_engine_color="W", both players_info entries carry the bare "human"
// player_type literal used by the multiplayer/engine session path (session.py) —
// NOT the "player:human"/"player:ai" literals used by local kiosk HvAI (server.py).
// Cast via `unknown` since the fixture's JSON shape (e.g. `is_pass: null`) doesn't
// match GameState's stricter TS fields exactly; only the fields the helpers under
// test actually read (players_info, platform_engine_color, player_to_move,
// end_result, last_move, board_size) matter at runtime.
import engineFixtureRaw from './fixtures/engine_game_state.json';
const engineFixture = engineFixtureRaw as unknown as GameState;

// Single unified mock of the real api.ts. Spread the actual module so untouched exports keep
// their real impls, then override exactly what the two suites drive: platformEngineAnalysis/
// platformEngineItems (star阵 tunnel) as bare vi.fn spies, and requestCount/analyzeCurrent/
// hintDismiss/hint via `mock`-prefixed closures (hoist-safe; defined below, bound at call time).
vi.mock('../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api')>();
  return {
    ...actual,
    API: {
      ...actual.API,
      platformEngineAnalysis: vi.fn(),
      platformEngineItems: vi.fn(),
      requestCount: (...a: any[]) => mockRequestCount(...a),
      analyzeCurrent: (...a: any[]) => mockAnalyzeCurrent(...a),
      hintDismiss: (...a: any[]) => mockHintDismiss(...a),
      hint: (...a: any[]) => mockHint(...a),
    },
  };
});

vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => ({ rotation: 0, setRotation: vi.fn() }),
}));

// Mock vision context (GamePage reads visionStatus + isVisionEnabled directly).
// Mutable via `visionMock` so the G2 banner tests below can flip isVisionEnabled on
// for a single test without disturbing the rest of the suite (which needs it inert).
// `vi.hoisted` avoids a TDZ ReferenceError — vi.mock factories are hoisted above
// ordinary `const` declarations in this file.
const visionMock = vi.hoisted(() => ({
  isVisionEnabled: false,
  visionStatus: {
    cameraConnected: true,
    poseLocked: true,
    syncState: 'synced',
    ledConnected: true,
    boundSessionId: null as string | null,
    recognitionReady: true,
    enabled: false,
  },
}));
vi.mock('../context/VisionContext', () => ({
  useVision: () => ({
    isVisionEnabled: visionMock.isVisionEnabled,
    visionStatus: visionMock.visionStatus,
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
// API is mocked (below) so 数子 (count) and the on-demand analysis effect don't hit the network.
const mockRequestCount = vi.fn();
const mockAnalyzeCurrent = vi.fn();
const mockHintDismiss = vi.fn();
const mockHint = vi.fn();
// Task 9: physical engine-move (Golaxy 隧道) error recovery — mutable so individual
// tests can drive useGameSession's tracked state without a full WS round-trip.
let mockPhysicalEngineError: { col: number; row: number; attempts: number; detail: string; recovery_token: string } | null = null;
let mockAwaitingRemovalReminder: { row: number; col: number } | null = null;
const mockClearPhysicalEngineError = vi.fn();

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
    physicalEngineError: mockPhysicalEngineError,
    clearPhysicalEngineError: mockClearPhysicalEngineError,
    awaitingRemovalReminder: mockAwaitingRemovalReminder,
  }),
}));

// Import after mocks
import GamePage, { deriveAiTurnState, deriveHumanColor } from '../pages/GamePage';

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
    mockPhysicalEngineError = null;
    mockAwaitingRemovalReminder = null;
    mockRequestCount.mockResolvedValue({ state: mockGameState });
    mockAnalyzeCurrent.mockResolvedValue({});
    mockHintDismiss.mockResolvedValue({ ok: true });
    (API.platformEngineAnalysis as ReturnType<typeof vi.fn>).mockReset();
    // Default: the mount-time badge fetch resolves with three counts. Individual
    // tests override as needed.
    (API.platformEngineItems as ReturnType<typeof vi.fn>).mockReset();
    (API.platformEngineItems as ReturnType<typeof vi.fn>).mockResolvedValue({ area: 396, options: 398, variation: 3 });
  });

  afterEach(() => {
    // Some tests mutate mockGameState.current_node_id / .count_min_moves to simulate the
    // position advancing or clear the 数子 move-count gate — restore them so they don't
    // bleed into later tests.
    mockGameState.current_node_id = 42;
    mockGameState.count_min_moves = undefined;
  });

  it('停一手/认输 stay enabled in engineMode (galaxy-reference: no blunt engineMode disable)', async () => {
    renderPage(true);

    // 停一手 is available whenever the game is not over — including Golaxy 人机对弈 — and
    // routes through session.handleAction. (The galaxy web reference gates it on isGameOver
    // only; there is no engineMode disable.)
    fireEvent.click(screen.getByText('停一手'));
    expect(mockHandleAction).toHaveBeenCalledWith('pass');

    // 认输 also stays enabled (opens the confirm dialog, intercepted before session.handleAction).
    fireEvent.click(screen.getByText('认输'));
    expect(screen.getByText('确认认输？')).toBeInTheDocument();
  });

  it('数子 is disabled before count_min_moves — the button is gated, no count call fires', async () => {
    // Default mock has 2 moves < count_min_moves(100) → 数子 disabled (ItemToggle drops onClick),
    // matching the galaxy reference and the backend /api/count/request move-count guard.
    renderPage(false);

    fireEvent.click(screen.getByText('数子'));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(mockRequestCount).not.toHaveBeenCalled();
  });

  it('数子 enables at ≥ count_min_moves and counts immediately via requestCount (HvAI)', async () => {
    // Lower the threshold so the 2-move mock clears the gate (restored in afterEach).
    mockGameState.count_min_moves = 1;
    renderPage(false);

    // 数子 now routes to the count API directly (HvAI completes immediately), NOT session.handleAction.
    fireEvent.click(screen.getByText('数子'));
    await waitFor(() => expect(mockRequestCount).toHaveBeenCalledWith('test-session'));
    expect(mockHandleAction).not.toHaveBeenCalledWith('count');
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

    it('leaves the local 领地/AI支招/图表 controls in place without engineMode', () => {
      renderPage(false);

      expect(screen.getByText('领地')).toBeInTheDocument();
      // 建议 was renamed to AI支招 (a one-shot hint action, not a toggle) in local free-play.
      expect(screen.getByText('AI支招')).toBeInTheDocument();
      expect(screen.getByText('图表')).toBeInTheDocument();
    });

    it('shows remaining-uses badges from the mount fetch (领地396/支招398/变化图3)', async () => {
      renderPage(true);
      await waitFor(() => expect(API.platformEngineItems).toHaveBeenCalledWith('golaxy', 'mock-token'));
      const badges = await screen.findAllByTestId('item-badge');
      const texts = badges.map((b) => b.textContent);
      expect(texts).toContain('396');
      expect(texts).toContain('398');
      expect(texts).toContain('3');
    });

    it('renders a 0 badge (次数不足) when a count is exhausted', async () => {
      (API.platformEngineItems as ReturnType<typeof vi.fn>).mockResolvedValue({ area: 396, options: 0, variation: 3 });
      renderPage(true);
      await waitFor(() => {
        const texts = screen.getAllByTestId('item-badge').map((b) => b.textContent);
        expect(texts).toContain('0');
      });
    });

    it('refetches the counts after an analysis settles (badge resync)', async () => {
      (API.platformEngineAnalysis as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true, kind: 'options', data: { candidates: [] },
      });
      renderPage(true);
      await waitFor(() => expect(API.platformEngineItems).toHaveBeenCalledTimes(1)); // mount

      fireEvent.click(screen.getByText('支招'));
      await waitFor(() => expect(API.platformEngineItems).toHaveBeenCalledTimes(2)); // after analysis
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

  // G2: engine games (Golaxy 人机对弈 via the genmove tunnel) put a bare "human"
  // player_type literal on BOTH seats (session.py:80/82) — neither literal check in
  // the old humanColor/isAI derivation ('player:human' / 'player:ai' / 'ai') can tell
  // which seat is the AI. `platform_engine_color` (Task 1: WebKaTrain state field,
  // "B"|"W"|null = the ENGINE's color) is the authoritative signal for engine games;
  // absent/null in every other game shape (local HvAI, PVP, multiplayer) — regression
  // guarded below.
  describe('G2: engine-aware humanColor / aiTurn derivation (platform_engine_color)', () => {
    const ORIGINAL_PLAYERS_INFO = mockGameState.players_info;
    const ORIGINAL_LAST_MOVE = mockGameState.last_move;
    const ORIGINAL_PLAYER_TO_MOVE = mockGameState.player_to_move;

    afterEach(() => {
      mockGameState.players_info = ORIGINAL_PLAYERS_INFO;
      mockGameState.last_move = ORIGINAL_LAST_MOVE;
      mockGameState.player_to_move = ORIGINAL_PLAYER_TO_MOVE;
      delete (mockGameState as Partial<GameState>).platform_engine_color;
      visionMock.isVisionEnabled = false;
    });

    describe('deriveHumanColor (pure helper)', () => {
      it('engine game, human=B (contract fixture, platform_engine_color="W") -> B', () => {
        expect(deriveHumanColor(engineFixture)).toBe('B');
      });

      it('engine game, human=W (platform_engine_color="B") -> W', () => {
        expect(deriveHumanColor({ ...engineFixture, platform_engine_color: 'B' })).toBe('W');
      });

      it('non-regression: local HvAI (player:human/player:ai literals, no engine signal) -> B', () => {
        expect(deriveHumanColor(mockGameState)).toBe('B');
      });

      it('no engine signal and no player:human seat -> null (falls through to old derivation unchanged)', () => {
        const state = {
          ...mockGameState,
          players_info: {
            B: { ...mockGameState.players_info.B, player_type: 'ai' },
            W: { ...mockGameState.players_info.W, player_type: 'ai' },
          },
        };
        expect(deriveHumanColor(state)).toBeNull();
      });
    });

    describe('deriveAiTurnState (engine branch of isAI)', () => {
      it('engine fixture: aiColor is the ENGINE color (W) even though players_info literal is bare "human"', () => {
        const { aiColor } = deriveAiTurnState(engineFixture, null);
        expect(aiColor).toBe('W');
      });

      it('genmove-tunnel-wait snapshot (player_to_move still human=B, remote-first apply) -> aiThinking not lit, no flicker', () => {
        // engineFixture.player_to_move is "B" (human) — the human's own move is only
        // applied locally after the tunnel returns, so this snapshot must never light
        // the "AI 思考中" banner even though an aiColor now exists for this game.
        const { aiColor, aiThinking } = deriveAiTurnState(engineFixture, null);
        expect(aiColor).toBe('W');
        expect(aiThinking).toBe(false);
      });

      it('post-AI-reply snapshot (player_to_move back to human) -> aiThinking still not lit', () => {
        const { aiThinking } = deriveAiTurnState({ ...engineFixture, player_to_move: 'B' }, null);
        expect(aiThinking).toBe(false);
      });

      it('the brief window where state shows the engine to move -> aiThinking lit (sanity: not just always false)', () => {
        const { aiColor, aiThinking } = deriveAiTurnState({ ...engineFixture, player_to_move: 'W' }, null);
        expect(aiColor).toBe('W');
        expect(aiThinking).toBe(true);
      });

      it('non-regression: local HvAI (player:ai literal) aiColor/aiThinking unchanged', () => {
        const state = { ...mockGameState, player_to_move: 'W' as const };
        const { aiColor, aiThinking } = deriveAiTurnState(state, null);
        expect(aiColor).toBe('W');
        expect(aiThinking).toBe(true);
      });
    });

    describe('AI-move banner (render)', () => {
      it('engine game, human=W: banner shows the AI(B) move coordinate after AI plays', async () => {
        visionMock.isVisionEnabled = true;
        mockGameState.platform_engine_color = 'B'; // engine is Black -> human is White
        mockGameState.player_to_move = 'W'; // human's turn, right after AI(B) moved
        mockGameState.last_move = [3, 3]; // -> "D16" (col=A+3='D', row=19-3=16)
        renderPage(true);

        expect(await screen.findByTestId('ai-move-banner')).toHaveTextContent('D16');
      });

      it('non-regression: engine game, human=B still shows the AI(W) move coordinate', async () => {
        visionMock.isVisionEnabled = true;
        mockGameState.platform_engine_color = 'W'; // engine is White -> human is Black
        mockGameState.player_to_move = 'B';
        mockGameState.last_move = [3, 3];
        renderPage(true);

        expect(await screen.findByTestId('ai-move-banner')).toHaveTextContent('D16');
      });

      it('non-regression: local HvAI (player:ai literal, no platform_engine_color) still shows the banner', async () => {
        visionMock.isVisionEnabled = true;
        // mockGameState default shape: B=player:human, W=player:ai, player_to_move='B', last_move=[3,3].
        renderPage(false);

        expect(await screen.findByTestId('ai-move-banner')).toHaveTextContent('D16');
      });

      // Regression guard for the color-wording bug flagged in the task-3 report's
      // "Concerns" section: the banner body text was hard-coded to always say
      // "摆放白子" (place the WHITE stone) no matter which color the AI actually is.
      // In a human-plays-White engine game the AI is BLACK, so the physical-board
      // placement guidance was telling the player to place the wrong-color stone.
      it('engine game, human=W (AI=B): banner tells the player to place the BLACK stone, not white', async () => {
        visionMock.isVisionEnabled = true;
        mockGameState.platform_engine_color = 'B'; // engine is Black -> human is White
        mockGameState.player_to_move = 'W';
        mockGameState.last_move = [3, 3];
        renderPage(true);

        const banner = await screen.findByTestId('ai-move-banner');
        expect(banner).toHaveTextContent('D16');
        expect(banner).toHaveTextContent('黑');
        expect(banner).not.toHaveTextContent('白');
      });

      it('non-regression: engine game, human=B (AI=W): banner still tells the player to place the WHITE stone', async () => {
        visionMock.isVisionEnabled = true;
        mockGameState.platform_engine_color = 'W'; // engine is White -> human is Black
        mockGameState.player_to_move = 'B';
        mockGameState.last_move = [3, 3];
        renderPage(true);

        const banner = await screen.findByTestId('ai-move-banner');
        expect(banner).toHaveTextContent('D16');
        expect(banner).toHaveTextContent('白');
        expect(banner).not.toHaveTextContent('黑');
      });

      it('non-regression: local HvAI (player:ai literal on W, no platform_engine_color): banner says WHITE', async () => {
        visionMock.isVisionEnabled = true;
        // mockGameState default shape: B=player:human, W=player:ai -> AI is White.
        renderPage(false);

        const banner = await screen.findByTestId('ai-move-banner');
        expect(banner).toHaveTextContent('白');
        expect(banner).not.toHaveTextContent('黑');
      });
    });
  });

  // Task 9: EngineMoveErrorDialog mount gating. The dialog's own retry/cancel/resign
  // behavior is covered in EngineMoveErrorDialog.test.tsx; this suite only verifies
  // GamePage wires session.physicalEngineError through it correctly, and — critically —
  // that a pure-screen engine game (isVisionEnabled false) never sees it, leaving the
  // pre-existing engineErrorToast path (tested above) as the sole error surface there.
  describe('Task 9: physical engine-move error dialog (isVisionEnabled gating)', () => {
    afterEach(() => {
      visionMock.isVisionEnabled = false;
    });

    it('shows the dialog with the GTP coordinate + attempts when vision is enabled and a physical_engine_error is tracked', async () => {
      visionMock.isVisionEnabled = true;
      mockPhysicalEngineError = { col: 3, row: 3, attempts: 3, detail: 'genmove timeout', recovery_token: 'tok-1' };
      renderPage(true);

      expect(await screen.findByText('星阵连接出错')).toBeInTheDocument();
      const dialog = screen.getByRole('dialog');
      expect(within(dialog).getByText(/D16/)).toBeInTheDocument();
    });

    it('does NOT show the dialog when vision is disabled, even with a tracked physical_engine_error (toast path unaffected)', async () => {
      visionMock.isVisionEnabled = false;
      mockPhysicalEngineError = { col: 3, row: 3, attempts: 3, detail: 'genmove timeout', recovery_token: 'tok-1' };
      renderPage(true);

      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(screen.queryByText('星阵连接出错')).toBeNull();
    });

    it('resign from the dialog opens the same 确认认输？ confirm flow', async () => {
      visionMock.isVisionEnabled = true;
      mockPhysicalEngineError = { col: 3, row: 3, attempts: 3, detail: 'genmove timeout', recovery_token: 'tok-1' };
      renderPage(true);

      const dialog = await screen.findByRole('dialog');
      fireEvent.click(within(dialog).getByText('认输'));

      expect(screen.getByText('确认认输？')).toBeInTheDocument();
    });

    // Finding 2 (HIGH): 认输 must not dismiss the error dialog itself — only the CONFIRM
    // sub-dialog's own 认输 button (i.e. an actually-confirmed resign) may do that. Fat-
    // fingering 认输 on a 7" kiosk and then cancelling the confirm must leave the recovery
    // dialog fully intact (same token, still open, no resign fired).
    it('cancelling the resign confirm leaves the error dialog open and untouched', async () => {
      visionMock.isVisionEnabled = true;
      mockPhysicalEngineError = { col: 3, row: 3, attempts: 3, detail: 'genmove timeout', recovery_token: 'tok-1' };
      renderPage(true);

      const dialog = await screen.findByRole('dialog');
      fireEvent.click(within(dialog).getByText('认输'));
      expect(screen.getByText('确认认输？')).toBeInTheDocument();

      fireEvent.click(screen.getByText('取消'));
      await waitFor(() => expect(screen.queryByText('确认认输？')).toBeNull());

      // The error dialog is still there, resign never actually fired.
      expect(screen.getByText('星阵连接出错')).toBeInTheDocument();
      expect(mockHandleAction).not.toHaveBeenCalledWith('resign');
      expect(mockClearPhysicalEngineError).not.toHaveBeenCalled();
    });

    it('confirming resign from the error dialog fires the resign action AND closes the error dialog', async () => {
      visionMock.isVisionEnabled = true;
      mockPhysicalEngineError = { col: 3, row: 3, attempts: 3, detail: 'genmove timeout', recovery_token: 'tok-1' };
      renderPage(true);

      const dialog = await screen.findByRole('dialog');
      fireEvent.click(within(dialog).getByText('认输'));
      const confirmDialog = screen.getByText('确认认输？').closest('[role="dialog"]') as HTMLElement;
      fireEvent.click(within(confirmDialog).getByText('认输'));

      expect(mockHandleAction).toHaveBeenCalledWith('resign');
      expect(mockClearPhysicalEngineError).toHaveBeenCalledTimes(1);
    });
  });
});
