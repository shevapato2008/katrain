import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import { API, type GameState } from '../../api';
import GamePage, { deriveAiTurnState } from './GamePage';

// --- Mocks -----------------------------------------------------------------

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'mock-token', isAuthenticated: true, user: { id: 1, username: 'test' }, login: vi.fn(), logout: vi.fn() }),
}));

interface MockBoardProps { analysisToggles?: Record<string, boolean>; playerColor?: 'B' | 'W' | null }
const { capturedBoardProps } = vi.hoisted(() => ({
  capturedBoardProps: { current: null as { analysisToggles?: Record<string, boolean> } | null },
}));
vi.mock('../../components/Board', () => ({
  default: (props: MockBoardProps) => { capturedBoardProps.current = props; return <div data-testid="board">Board</div>; },
}));

// Exposes onAction so state-D (resign) tests can drive the real GamePage resign flow
// without a full GameControlPanel render.
interface MockControlPanelProps { onAction: (action: string) => void }
vi.mock('../components/game/GameControlPanel', () => ({
  default: (props: MockControlPanelProps) => (
    <div data-testid="game-control-panel">
      <button onClick={() => props.onAction('resign')}>MOCK_RESIGN</button>
    </div>
  ),
}));

const { writeActiveSession, clearActiveSession } = vi.hoisted(() => ({
  writeActiveSession: vi.fn(),
  clearActiveSession: vi.fn(),
}));
vi.mock('../utils/activeSession', () => ({ writeActiveSession, clearActiveSession }));

const { mockCalibrate } = vi.hoisted(() => ({ mockCalibrate: vi.fn().mockResolvedValue({}) }));
vi.mock('../../api/geometryApi', () => ({ GeometryAPI: { calibrate: (...a: unknown[]) => mockCalibrate(...a) } }));
const { mockLadderStatus } = vi.hoisted(() => ({ mockLadderStatus: vi.fn() }));
vi.mock('../../features/aiLadder/api', () => ({ getAiLadderStatus: mockLadderStatus }));

let mockIsVisionEnabled = false;
let mockPoseLocked = true;
vi.mock('../context/VisionContext', () => ({
  useVision: () => ({
    visionStatus: { enabled: mockIsVisionEnabled, cameraConnected: true, poseLocked: mockPoseLocked, syncState: 'idle', boundSessionId: null, ledConnected: null },
    isVisionEnabled: mockIsVisionEnabled,
    refreshStatus: vi.fn(),
  }),
}));

let mockLatestEvent: { type: string; data: Record<string, unknown> } | null = null;
let mockSyncEvents: { type: string; data: Record<string, unknown> }[] = [];
vi.mock('../hooks/useVisionSync', () => ({
  useVisionSync: () => ({ syncEvents: mockSyncEvents, latestEvent: mockLatestEvent, setupProgress: null, isSetupComplete: false }),
}));

const mockSetSessionId = vi.fn();
const mockHandleAction = vi.fn();
const mockOnMove = vi.fn().mockResolvedValue(undefined);
const mockOnNavigate = vi.fn();

let mockGameState: GameState;
let mockPhysicalReminder: { kind: 'reminder' | 'escalation'; to_place: number[][]; to_remove: number[][] } | null = null;

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
    physicalReminder: mockPhysicalReminder,
  }),
}));

// --- Fixtures ----------------------------------------------------------------

const basePlayer = { player_subtype: '', calculated_rank: null, periods_used: 0, main_time_used: 0 };

const makeGameState = (overrides: Partial<GameState> & { players_info: GameState['players_info'] }): GameState => ({
  game_id: 'test-game',
  board_size: [19, 19],
  komi: 6.5,
  handicap: 0,
  ruleset: '日本',
  current_node_id: 5,
  current_node_index: 5,
  history: [],
  player_to_move: 'B',
  stones: [],
  last_move: null,
  prisoner_count: { B: 0, W: 0 },
  analysis: null,
  commentary: '',
  is_root: false,
  is_pass: false,
  end_result: null,
  children: [],
  ghost_stones: [],
  note: '',
  ui_state: {
    show_children: false, show_dots: false, show_hints: false, show_policy: false,
    show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false,
  },
  language: 'zh',
  ...overrides,
});

// Factored out (not just inlined in renderPage) so the dismiss→reopen cycle test below can
// call `rerender(pageTree())` with the identical element tree after mutating a mock value —
// same container, same component identity, only the mocked hook return values change.
const pageTree = () => (
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter initialEntries={['/kiosk/play/ai/game/test-session']}>
      <Routes>
        <Route path="/kiosk/play/ai/game/:sessionId" element={<GamePage />} />
        <Route path="/kiosk/play" element={<div>PLAY_PAGE</div>} />
        <Route path="/kiosk/research" element={<div>RESEARCH_PAGE</div>} />
      </Routes>
    </MemoryRouter>
  </ThemeProvider>
);

const renderPage = () => render(pageTree());

describe('GamePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsVisionEnabled = false;
    mockLatestEvent = null;
    mockSyncEvents = [];
    mockPoseLocked = true;
    mockPhysicalReminder = null;
    capturedBoardProps.current = null;
    mockCalibrate.mockClear().mockResolvedValue({});
    sessionStorage.clear();
    localStorage.clear();
    mockLadderStatus.mockReset();
  });

  it('renders authoritative ranked settlement feedback after end_result', async () => {
    const status = (rung: number) => ({
      view_state: 'ready' as const,
      placement_state: { phase: 'placed' as const, rung: { rung, rank_name: `${rung}级`, certification_status: 'certified' as const, availability: 'available' as const, route: 'server' as const } },
      current_opponent: null, recent_ranked_results: ['win' as const], net_score: 0 as const, pending_settlement: false,
    });
    sessionStorage.setItem('ai-ladder-before:test-session', JSON.stringify({ identity: '1', status: status(17) }));
    mockLadderStatus.mockResolvedValue(status(18));
    mockGameState = makeGameState({
      game_type: 'ai_ladder_ranked', end_result: 'B+R',
      players_info: { B: { ...basePlayer, player_type: 'player:human', name: '张三' }, W: { ...basePlayer, player_type: 'player:ai', name: 'AI' } },
    });
    renderPage();
    expect(await screen.findByText('升级：18级')).toBeInTheDocument();
    expect(mockLadderStatus).toHaveBeenCalledWith('mock-token', expect.any(AbortSignal));
  });

  it('never renders the TEMP DEBUG vision-stream <img>', () => {
    mockIsVisionEnabled = true;
    mockGameState = makeGameState({
      players_info: {
        B: { ...basePlayer, player_type: 'player:human', name: '张三' },
        W: { ...basePlayer, player_type: 'player:ai', name: 'KataGo' },
      },
    });
    renderPage();
    expect(document.querySelector('img[src="/api/v1/vision/stream"]')).toBeNull();
  });

  describe('AI game — persistent amber banner (both player_type literals)', () => {
    it('shows ai-move-banner when the AI seat is the "player:ai" literal and it is the human turn after an AI move', () => {
      mockIsVisionEnabled = true;
      mockGameState = makeGameState({
        players_info: {
          B: { ...basePlayer, player_type: 'player:human', name: '张三' },
          W: { ...basePlayer, player_type: 'player:ai', name: 'KataGo' },
        },
        player_to_move: 'B',
        last_move: [3, 3],
        end_result: null,
      });
      renderPage();
      expect(screen.getByTestId('ai-move-banner')).toBeInTheDocument();
    });

    it('shows ai-move-banner when the AI seat uses the bare "ai" literal', () => {
      mockIsVisionEnabled = true;
      mockGameState = makeGameState({
        players_info: {
          B: { ...basePlayer, player_type: 'player:human', name: '张三' },
          W: { ...basePlayer, player_type: 'ai', name: 'KataGo' },
        },
        player_to_move: 'B',
        last_move: [3, 3],
        end_result: null,
      });
      renderPage();
      expect(screen.getByTestId('ai-move-banner')).toBeInTheDocument();
    });

    it('does not show the banner when vision is disabled, even with an AI seat and a pending last move', () => {
      mockIsVisionEnabled = false;
      mockGameState = makeGameState({
        players_info: {
          B: { ...basePlayer, player_type: 'player:human', name: '张三' },
          W: { ...basePlayer, player_type: 'player:ai', name: 'KataGo' },
        },
        player_to_move: 'B',
        last_move: [3, 3],
        end_result: null,
      });
      renderPage();
      expect(screen.queryByTestId('ai-move-banner')).toBeNull();
    });
  });

  describe('both-human PVP — aiColor===null suppresses every AI surface', () => {
    it('renders no ai-move-banner even when vision is enabled and a last move exists', () => {
      mockIsVisionEnabled = true;
      mockGameState = makeGameState({
        players_info: {
          B: { ...basePlayer, player_type: 'player:human', name: '张三' },
          W: { ...basePlayer, player_type: 'player:human', name: '李四' },
        },
        player_to_move: 'B',
        last_move: [3, 3],
        end_result: null,
      });
      renderPage();
      // The coordinate-hint effect fires (B is 'player:human' and it's B's turn), so
      // aiMoveBanner itself would be non-null — proving suppression is the render-time
      // `aiColor !== null` gate, not merely an absent banner label.
      expect(screen.queryByTestId('ai-move-banner')).toBeNull();
    });

    it('no ai-thinking surface renders for PVP either (B1.4 gates the state-A surface on the same aiColor===null / showThinking===false)', () => {
      mockIsVisionEnabled = true;
      mockGameState = makeGameState({
        players_info: {
          B: { ...basePlayer, player_type: 'human', name: '张三' },
          W: { ...basePlayer, player_type: 'human', name: '李四' },
        },
        player_to_move: 'W',
        last_move: [3, 3],
        end_result: null,
      });
      renderPage();
      expect(screen.queryByTestId('ai-thinking')).toBeNull();
      expect(screen.queryByTestId('ai-move-banner')).toBeNull();
    });

    it('passes playerColor=null to Board when both players are human (HvH) — touchscreen fallback must work for BOTH colors', () => {
      mockGameState = makeGameState({
        players_info: {
          B: { ...basePlayer, player_type: 'player:human', name: '张三' },
          W: { ...basePlayer, player_type: 'player:human', name: '李四' },
        },
        player_to_move: 'W',
        end_result: null,
      });
      renderPage();
      expect(capturedBoardProps.current?.playerColor).toBeNull();
    });
  });

  describe('deriveAiTurnState — single-owner AI-turn arbitration (unit)', () => {
    const aiGameState = makeGameState({
      players_info: {
        B: { ...basePlayer, player_type: 'player:human', name: '张三' },
        W: { ...basePlayer, player_type: 'player:ai', name: 'KataGo' },
      },
      player_to_move: 'W',
      end_result: null,
    });

    it('aiColor accepts the "player:ai" literal', () => {
      expect(deriveAiTurnState(aiGameState, null).aiColor).toBe('W');
    });

    it('aiColor accepts the bare "ai" literal', () => {
      const gs = makeGameState({
        players_info: {
          B: { ...basePlayer, player_type: 'human', name: '张三' },
          W: { ...basePlayer, player_type: 'ai', name: 'KataGo' },
        },
        player_to_move: 'W',
      });
      expect(deriveAiTurnState(gs, null).aiColor).toBe('W');
    });

    it('both-human PVP yields aiColor===null and aiThinking/showThinking are always false', () => {
      const pvp = makeGameState({
        players_info: {
          B: { ...basePlayer, player_type: 'human', name: '张三' },
          W: { ...basePlayer, player_type: 'human', name: '李四' },
        },
        player_to_move: 'W',
      });
      const state = deriveAiTurnState(pvp, null);
      expect(state.aiColor).toBeNull();
      expect(state.aiThinking).toBe(false);
      expect(state.showThinking).toBe(false);
    });

    it('aiThinking is true on the AI turn with no move_pending event', () => {
      const state = deriveAiTurnState(aiGameState, null);
      expect(state.aiThinking).toBe(true);
      expect(state.showThinking).toBe(true);
    });

    it('showThinking is suppressed while the physical layer is confirming (move_pending), even though aiThinking stays true', () => {
      const state = deriveAiTurnState(aiGameState, 'move_pending');
      expect(state.aiThinking).toBe(true);
      expect(state.physicalConfirming).toBe(true);
      expect(state.showThinking).toBe(false);
    });

    it('aiThinking is false once the game has ended', () => {
      const ended = { ...aiGameState, end_result: 'B+4.5' };
      const state = deriveAiTurnState(ended, null);
      expect(state.aiThinking).toBe(false);
      expect(state.showThinking).toBe(false);
    });
  });

  describe('activeSession write-on-load / clear-on-end', () => {
    it('writes the active session with kind "game" for a live game', () => {
      mockGameState = makeGameState({
        players_info: {
          B: { ...basePlayer, player_type: 'player:human', name: '张三' },
          W: { ...basePlayer, player_type: 'player:ai', name: 'KataGo' },
        },
        end_result: null,
      });
      renderPage();
      expect(writeActiveSession).toHaveBeenCalledWith(
        expect.objectContaining({ kind: 'game', label: '张三 vs KataGo' })
      );
      expect(clearActiveSession).not.toHaveBeenCalled();
    });

    it('clears the active session when the game has ended', () => {
      mockGameState = makeGameState({
        players_info: {
          B: { ...basePlayer, player_type: 'player:human', name: '张三' },
          W: { ...basePlayer, player_type: 'player:ai', name: 'KataGo' },
        },
        end_result: 'B+4.5',
      });
      renderPage();
      expect(clearActiveSession).toHaveBeenCalledWith('game');
      expect(writeActiveSession).not.toHaveBeenCalled();
    });
  });

  // --- B1.4: four GamePage states + consolidated board-loss surfaces ---------------

  const aiVsHuman = {
    B: { ...basePlayer, player_type: 'player:human', name: '张三' },
    W: { ...basePlayer, player_type: 'player:ai', name: 'KataGo' },
  };

  describe('State A — AI 思考中 (B1.4)', () => {
    it('shows ai-thinking when it is the AI turn with no move_pending event', () => {
      mockGameState = makeGameState({ players_info: aiVsHuman, player_to_move: 'W', end_result: null });
      renderPage();
      expect(screen.getByTestId('ai-thinking')).toBeInTheDocument();
    });

    it('hides ai-thinking while the physical layer is confirming (move_pending), per B1.3 showThinking', () => {
      mockLatestEvent = { type: 'move_pending', data: {} };
      mockGameState = makeGameState({ players_info: aiVsHuman, player_to_move: 'W', end_result: null });
      renderPage();
      expect(screen.queryByTestId('ai-thinking')).toBeNull();
    });
  });

  describe('State B — RecalibrationModal (B1.4)', () => {
    it('opens when pose is lost mid-game, and 重新标定 calls GeometryAPI.calibrate("manual")', async () => {
      mockIsVisionEnabled = true;
      mockPoseLocked = false;
      mockGameState = makeGameState({ players_info: aiVsHuman, end_result: null });
      renderPage();
      expect(screen.getByText('棋盘可能被移动')).toBeInTheDocument();
      fireEvent.click(screen.getByText('重新标定'));
      await waitFor(() => expect(mockCalibrate).toHaveBeenCalledWith('manual'));
    });

    it('is suppressed while the escalation dialog is open (escalation > recalibration)', () => {
      mockIsVisionEnabled = true;
      mockPoseLocked = false;
      mockPhysicalReminder = { kind: 'escalation', to_place: [[3, 3]], to_remove: [] };
      mockGameState = makeGameState({ players_info: aiVsHuman, end_result: null });
      renderPage();
      expect(screen.queryByText('棋盘可能被移动')).toBeNull();
    });

    // Review follow-up: guards the dismiss→reopen safety cycle. RecalibrationModal owns a
    // local `dismissed` flag (仍要继续 / Escape / backdrop) and GamePage remounts it via
    // `key={String(visionStatus.poseLocked)}` so a FRESH pose-loss always re-warns the
    // operator. Without this test, a future refactor that drops the `key` remount would
    // silently ship a "dismiss-forever" bug: the operator would never be re-warned after
    // the board moves again.
    it('re-opens on a fresh pose-loss after being dismissed and the board regaining lock', async () => {
      mockIsVisionEnabled = true;
      mockPoseLocked = false;
      mockGameState = makeGameState({ players_info: aiVsHuman, end_result: null });
      const view = renderPage();

      // 1. Initial pose-loss opens the modal.
      expect(screen.getByText('棋盘可能被移动')).toBeInTheDocument();

      // 2. Operator dismisses it (仍要继续) → closes.
      fireEvent.click(screen.getByText('仍要继续'));
      await waitFor(() => expect(screen.queryByText('棋盘可能被移动')).toBeNull());

      // 3. Board regains pose lock (poseLocked: false → true) → stays closed. This also
      // flips the remount `key` ("false" → "true"), so RecalibrationModal is torn down
      // and a fresh instance (dismissed=false) is mounted — but `open` is false here too,
      // so nothing should render.
      mockPoseLocked = true;
      view.rerender(pageTree());
      expect(screen.queryByText('棋盘可能被移动')).toBeNull();

      // 4. A NEW pose-loss (poseLocked: true → false) → key flips back to "false", forcing
      // another fresh remount whose local `dismissed` starts at false again. This MUST
      // reopen the modal — that's the safety property under test.
      mockPoseLocked = false;
      view.rerender(pageTree());
      expect(screen.getByText('棋盘可能被移动')).toBeInTheDocument();
    });
  });

  describe('Board-loss consolidation — escalation + board_lost never both render (B1.4)', () => {
    it('suppresses the VisionSyncOverlay board-lost modal while the escalation dialog is up', async () => {
      vi.useFakeTimers();
      try {
        mockIsVisionEnabled = true;
        mockSyncEvents = [{ type: 'board_lost', data: {} }];
        mockPhysicalReminder = { kind: 'escalation', to_place: [[3, 3]], to_remove: [] };
        mockGameState = makeGameState({ players_info: aiVsHuman, end_result: null });
        renderPage();
        await act(async () => { vi.advanceTimersByTime(10_000); });
        expect(screen.queryByText('棋盘检测异常')).toBeNull();
        expect(screen.getByText('物理棋盘长时间未跟上对局')).toBeInTheDocument();
      } finally {
        vi.useRealTimers();
      }
    });
  });

  describe('State C — 终局数子 (B1.4)', () => {
    it('renders endgame-card + result-badge and forces Board analysisToggles.ownership=true', () => {
      mockGameState = makeGameState({ players_info: aiVsHuman, end_result: 'B+4.5' });
      renderPage();
      expect(screen.getByTestId('endgame-card')).toBeInTheDocument();
      expect(screen.getByTestId('result-badge')).toBeInTheDocument();
      expect(capturedBoardProps.current?.analysisToggles?.ownership).toBe(true);
    });

    it('继续对弈 hides the endgame-card locally and does NOT call session.handleAction (game stays ended)', () => {
      mockGameState = makeGameState({ players_info: aiVsHuman, end_result: 'B+4.5' });
      renderPage();
      fireEvent.click(screen.getByText('继续对弈'));
      expect(screen.queryByTestId('endgame-card')).toBeNull();
      expect(mockHandleAction).not.toHaveBeenCalled();
    });

    it('复盘本局 saves the LIVE sgf (no persisted user_games id is available at endgame), stashes it, and navigates to research', async () => {
      mockGameState = makeGameState({ players_info: aiVsHuman, end_result: 'B+4.5' });
      const saveSGFSpy = vi.spyOn(API, 'saveSGF').mockResolvedValue({ sgf: '(;GM[1]FF[4]SZ[19])' });
      try {
        renderPage();
        fireEvent.click(screen.getByText('复盘本局'));
        expect(await screen.findByText('RESEARCH_PAGE')).toBeInTheDocument();
        expect(saveSGFSpy).toHaveBeenCalledWith('test-session');
        expect(sessionStorage.getItem('kioskReviewSgf')).toBe('(;GM[1]FF[4]SZ[19])');
      } finally {
        saveSGFSpy.mockRestore();
      }
    });
  });

  describe('State D — 认输 error-red modal (B1.4)', () => {
    it('resign confirm button has color=error', () => {
      mockGameState = makeGameState({ players_info: aiVsHuman, end_result: null });
      renderPage();
      fireEvent.click(screen.getByText('MOCK_RESIGN'));
      const confirmBtn = screen.getByRole('button', { name: '认输' });
      expect(confirmBtn.className).toMatch(/error/i);
    });

    it('keeps the dialog open and reports a failed authoritative resign', async () => {
      mockHandleAction.mockRejectedValueOnce(new Error('认输请求失败'));
      mockGameState = makeGameState({ players_info: aiVsHuman, end_result: null, game_type: 'ai_ladder_ranked' });
      renderPage();
      fireEvent.click(screen.getByText('MOCK_RESIGN'));
      fireEvent.click(screen.getByRole('button', { name: '认输' }));
      expect(await screen.findByText('认输请求失败')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '认输' })).toBeInTheDocument();
    });
  });

  // --- 3D board removed from kiosk (2026-07-13) -------------------------------------
  // The 3D Go board was dropped to free ~321MB of Mali GPU memory contending with KataGo's
  // OpenCL on the RK3562. Guard against reintroduction: only the 2D Board ever renders.
  describe('3D board removed', () => {
    it('renders only the 2D Board and never a 3D board', () => {
      mockGameState = makeGameState({ players_info: aiVsHuman, end_result: null });
      renderPage();
      expect(screen.getByTestId('board')).toBeInTheDocument();
      expect(screen.queryByTestId('board3d')).toBeNull();
    });
  });
});
