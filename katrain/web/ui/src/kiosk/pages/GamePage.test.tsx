import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import type { GameState } from '../../api';
import GamePage, { deriveAiTurnState } from './GamePage';

// --- Mocks -----------------------------------------------------------------

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'mock-token', isAuthenticated: true, user: { id: 1, username: 'test' }, login: vi.fn(), logout: vi.fn() }),
}));

vi.mock('../../components/Board', () => ({
  default: () => <div data-testid="board">Board</div>,
}));

vi.mock('../components/game/GameControlPanel', () => ({
  default: () => <div data-testid="game-control-panel">GameControlPanel</div>,
}));

const { writeActiveSession, clearActiveSession } = vi.hoisted(() => ({
  writeActiveSession: vi.fn(),
  clearActiveSession: vi.fn(),
}));
vi.mock('../utils/activeSession', () => ({ writeActiveSession, clearActiveSession }));

let mockIsVisionEnabled = false;
vi.mock('../context/VisionContext', () => ({
  useVision: () => ({
    visionStatus: { enabled: mockIsVisionEnabled, cameraConnected: true, poseLocked: true, syncState: 'idle', boundSessionId: null, ledConnected: null },
    isVisionEnabled: mockIsVisionEnabled,
    refreshStatus: vi.fn(),
  }),
}));

let mockLatestEvent: { type: string; data: Record<string, unknown> } | null = null;
vi.mock('../hooks/useVisionSync', () => ({
  useVisionSync: () => ({ syncEvents: [], latestEvent: mockLatestEvent, setupProgress: null, isSetupComplete: false }),
}));

const mockSetSessionId = vi.fn();
const mockHandleAction = vi.fn();
const mockOnMove = vi.fn().mockResolvedValue(undefined);
const mockOnNavigate = vi.fn();

let mockGameState: GameState;

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
    physicalReminder: null,
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

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={['/kiosk/play/ai/game/test-session']}>
        <Routes>
          <Route path="/kiosk/play/ai/game/:sessionId" element={<GamePage />} />
          <Route path="/kiosk/play" element={<div>PLAY_PAGE</div>} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('GamePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsVisionEnabled = false;
    mockLatestEvent = null;
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

    it('no ai-thinking surface renders for PVP either (none exists yet — B1.4 will gate its surface on the same aiColor===null)', () => {
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
});
