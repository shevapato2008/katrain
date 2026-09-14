import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import { API, ApiError, type GameState } from '../../api';
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
// without a full GameControlPanel render. `onTimeExpired` is captured (S3-5: real edge-trigger
// logic lives in GameControlPanel itself, already covered by GameControlPanel.clock.test.tsx —
// here we only need to prove GamePage wires/omits the prop and reacts to it correctly) AND
// exposed via a button so tests can fire it like GameControlPanel's real edge-trigger effect would.
interface MockControlPanelProps {
  onAction: (action: string) => void;
  onTimeExpired?: () => void;
  statusSlot?: React.ReactNode;
}
const { capturedControlPanelProps } = vi.hoisted(() => ({
  capturedControlPanelProps: { current: null as MockControlPanelProps | null },
}));
vi.mock('../components/game/GameControlPanel', () => ({
  default: (props: MockControlPanelProps) => {
    capturedControlPanelProps.current = props;
    return (
      <div data-testid="game-control-panel">
        {/* F4: 状态条现在由 GamePage 经 statusSlot 传入、GameControlPanel 渲染 —— mock 照实转发,
            否则「auto-count-status」相关断言对 GamePage 完全不渲染它这个回归免疫。 */}
        {props.statusSlot}
        <button onClick={() => props.onAction('resign')}>MOCK_RESIGN</button>
        <button onClick={() => props.onAction('count')}>MOCK_COUNT</button>
        <button onClick={() => props.onTimeExpired?.()}>MOCK_TIMEOUT</button>
      </div>
    );
  },
}));

const { writeActiveSession, clearActiveSession } = vi.hoisted(() => ({
  writeActiveSession: vi.fn(),
  clearActiveSession: vi.fn(),
}));
// `readSessionPlayOnBoard`(泳道 B)从活动会话读开局那一刻定下的 onBoard;这里桩成「没有活动会话」,
// 走回落到偏好的那一支 —— 即合并前本文件各用例依赖的行为。
vi.mock('../utils/activeSession', () => ({ writeActiveSession, clearActiveSession, readActiveSession: () => null }));

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
const mockSetGameState = vi.fn();

let mockGameState: GameState;
let mockPhysicalReminder: { kind: 'reminder' | 'escalation'; to_place: number[][]; to_remove: number[][] } | null = null;

vi.mock('../../hooks/useGameSession', () => ({
  useGameSession: () => ({
    sessionId: 'test-session',
    setSessionId: mockSetSessionId,
    gameState: mockGameState,
    setGameState: mockSetGameState,
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
    // 新覆盖的「非本地对局认输成功」路径会调用它(GamePage.tsx 里未包在 try 里);
    // 缺了这一项此前从未被真调用过,加上后只是补全 mock、不改任何断言。
    clearPhysicalEngineError: vi.fn(),
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
    capturedControlPanelProps.current = null;
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

  describe('本地对局 v2:两个出口 + 数子', () => {
    const human = { ...basePlayer, name: '' };
    const localPair: GameState['players_info'] = {
      B: { ...human, player_type: 'player:human' }, W: { ...human, player_type: 'player:human' },
    };
    const local = (over: Partial<GameState> = {}) =>
      makeGameState({ players_info: localPair, game_type: 'pvp_local', ...over });

    it('认输先问谁认输,按「白方认输」⇒ handleAction 带 color=W', async () => {
      mockGameState = local();
      renderPage();
      fireEvent.click(screen.getByText('MOCK_RESIGN'));
      expect(screen.getByText('哪一方认输？')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '黑方认输' })).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: '白方认输' }));
      await waitFor(() => expect(mockHandleAction).toHaveBeenCalledWith('resign', { color: 'W' }));
    });

    it('认输框按「取消」⇒ 不发请求', () => {
      mockGameState = local();
      renderPage();
      fireEvent.click(screen.getByText('MOCK_RESIGN'));
      fireEvent.click(screen.getByRole('button', { name: '取消' }));
      expect(mockHandleAction).not.toHaveBeenCalled();
    });

    it('未终局退出 ⇒ 删会话、清活动会话、回对弈首页,绝不认输', async () => {
      mockGameState = local();
      const del = vi.spyOn(API, 'deleteSession').mockResolvedValue(undefined);
      try {
        renderPage();
        fireEvent.click(screen.getByText('退出对局'));
        expect(screen.getByText('退出这局？')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: '退出不保存' }));
        expect(await screen.findByText('PLAY_PAGE')).toBeInTheDocument();
        expect(del).toHaveBeenCalledWith('test-session');
        expect(clearActiveSession).toHaveBeenCalledWith('game');
        expect(mockHandleAction).not.toHaveBeenCalled();
      } finally { del.mockRestore(); }
    });

    it('删会话失败 ⇒ 不离开、说出来(不能装作已退出)', async () => {
      mockGameState = local();
      const del = vi.spyOn(API, 'deleteSession').mockRejectedValue(new ApiError(500, 'Request failed 500: boom'));
      try {
        renderPage();
        fireEvent.click(screen.getByText('退出对局'));
        fireEvent.click(screen.getByRole('button', { name: '退出不保存' }));
        expect(await screen.findByText('退出失败，请重试')).toBeInTheDocument();
        expect(screen.queryByText('PLAY_PAGE')).toBeNull();
        expect(clearActiveSession).not.toHaveBeenCalledWith('game');
      } finally { del.mockRestore(); }
    });

    it('已终局 ⇒ 直接离开,不弹框、不删会话', async () => {
      mockGameState = local({ end_result: 'W+R' });
      const del = vi.spyOn(API, 'deleteSession').mockResolvedValue(undefined);
      try {
        renderPage();
        fireEvent.click(screen.getByText('退出对局'));
        expect(await screen.findByText('PLAY_PAGE')).toBeInTheDocument();
        expect(del).not.toHaveBeenCalled();
      } finally { del.mockRestore(); }
    });

    it('手动数子失败按原因码说真话,不再一律「手数不足或已结束」', async () => {
      mockGameState = local();
      const rc = vi.spyOn(API, 'requestCount')
        .mockRejectedValue(new ApiError(400, 'x', { code: 'analysis_pending', message: 'x' }));
      try {
        renderPage();
        fireEvent.click(screen.getByText('MOCK_COUNT'));
        expect(await screen.findByText('还在算这一手的形势，稍等再数')).toBeInTheDocument();
      } finally { rc.mockRestore(); }
    });

    it('awaiting_count ⇒ 自动数子,屏上说「正在数子…」', async () => {
      // 后端真实行为(core/game.py):双 pass 后 end_result 一定非空(终局提示语或人工比分),
      // 同时带 awaiting_count=true;数子判据是「有没有 awaiting_count」,不是「有没有 end_result」——
      // fixture 照后端的形状写,否则这条测试对 F1 那个 bug 免疫(改之前也是绿的)。
      mockGameState = local({ awaiting_count: true, end_result: '终局' });
      const rc = vi.spyOn(API, 'requestCount').mockReturnValue(new Promise(() => {}));
      try {
        renderPage();
        expect(await screen.findByText('正在数子…')).toBeInTheDocument();
        expect(rc).toHaveBeenCalledWith('test-session');
      } finally { rc.mockRestore(); }
    });

    it('本地对局后台分析照跑(数子读这份分数)—— 不许把 pvp_local 排除出 analyzeCurrent', () => {
      mockGameState = local();
      const an = vi.spyOn(API, 'analyzeCurrent').mockResolvedValue({} as never);
      try {
        renderPage();
        expect(an).toHaveBeenCalledWith('test-session');
      } finally { an.mockRestore(); }
    });

    it('非本地对局的认输框逐字不变:确认后 handleAction 只带 action', async () => {
      mockGameState = makeGameState({ players_info: localPair, game_type: 'free' });
      renderPage();
      fireEvent.click(screen.getByText('MOCK_RESIGN'));
      fireEvent.click(screen.getByRole('button', { name: '认输' }));
      await waitFor(() => expect(mockHandleAction).toHaveBeenCalledWith('resign'));
    });
  });

  describe('超时判负 (S3-5)', () => {
    const human = { ...basePlayer, name: '' };
    const localPair: GameState['players_info'] = {
      B: { ...human, player_type: 'player:human' }, W: { ...human, player_type: 'player:human' },
    };
    const local = (over: Partial<GameState> = {}) =>
      makeGameState({ players_info: localPair, game_type: 'pvp_local', ...over });

    it('到点 ⇒ 调一次 API.timeout,成功用返回的 state', async () => {
      mockGameState = local();
      const newState = local({ current_node_id: 9 });
      const to = vi.spyOn(API, 'timeout').mockResolvedValue({ session_id: 'test-session', state: newState });
      try {
        renderPage();
        fireEvent.click(screen.getByText('MOCK_TIMEOUT'));
        await waitFor(() => expect(to).toHaveBeenCalledWith('test-session'));
        await waitFor(() => expect(mockSetGameState).toHaveBeenCalledWith(newState));
      } finally { to.mockRestore(); }
    });

    it('409 time_not_expired ⇒ 用附带的最新 state 重算,不弹错误', async () => {
      mockGameState = local();
      const newState = local({ current_node_id: 9 });
      const to = vi.spyOn(API, 'timeout')
        .mockRejectedValue(new ApiError(409, 'x', { code: 'time_not_expired', state: newState }));
      try {
        renderPage();
        fireEvent.click(screen.getByText('MOCK_TIMEOUT'));
        await waitFor(() => expect(mockSetGameState).toHaveBeenCalledWith(newState));
        expect(screen.queryByText('超时判定没有完成')).toBeNull();
      } finally { to.mockRestore(); }
    });

    it('非 409 错误 ⇒ 说「超时判定没有完成」,不崩', async () => {
      mockGameState = local();
      const to = vi.spyOn(API, 'timeout').mockRejectedValue(new Error('network down'));
      try {
        renderPage();
        fireEvent.click(screen.getByText('MOCK_TIMEOUT'));
        expect(await screen.findByText('超时判定没有完成')).toBeInTheDocument();
      } finally { to.mockRestore(); }
    });

    it('终局且 end_result 以 +T 结尾 ⇒ 右栏状态条写明谁超时负、谁胜、第几手,并有复盘本局键', () => {
      mockGameState = local({ end_result: 'W+T', current_node_index: 130 });
      renderPage();
      const bar = screen.getByTestId('auto-count-status');
      expect(bar).toHaveTextContent('黑方超时负');
      expect(bar).toHaveTextContent('白超时胜');
      expect(bar).toHaveTextContent('第 131 手');
      expect(bar).toHaveTextContent('已存进历史对局');
      expect(within(bar).getByRole('button', { name: '复盘本局' })).toBeInTheDocument();
      // 超时判负那一态由右栏状态条说完 —— 居中的终局卡不再重复一遍(见 GamePage.tsx 注释)。
      expect(screen.queryByTestId('endgame-card')).toBeNull();
    });

    it('非 pvp_local 局不传 onTimeExpired', () => {
      mockGameState = makeGameState({ players_info: aiVsHuman, end_result: null });
      renderPage();
      expect(capturedControlPanelProps.current?.onTimeExpired).toBeUndefined();
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
