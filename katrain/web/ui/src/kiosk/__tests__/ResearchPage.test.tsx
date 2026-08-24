import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import type { GameState } from '../../api';

// Page no longer reads OrientationContext (portrait handling dropped in the kiosk port) —
// no mock needed for it.

vi.mock('../context/ImmersiveContext', () => ({
  useImmersive: () => ({ immersive: false, setImmersive: vi.fn() }),
}));

const { authState } = vi.hoisted(() => ({ authState: { current: { token: 'mock-token', isAuthenticated: true, user: { id: 1, username: 'test' }, login: vi.fn(), logout: vi.fn() } as any } }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => authState.current }));

vi.mock('../../api/userGamesApi', () => ({
  UserGamesAPI: { get: vi.fn(), list: vi.fn() },
}));

vi.mock('../../api', () => ({
  API: {
    quickAnalyze: vi.fn().mockResolvedValue({ turnInfos: [{ moveInfos: [], ownership: null }] }),
    analysisScan: vi.fn().mockResolvedValue({}),
    analysisProgress: vi.fn(),
  },
}));

vi.mock('../../api/kifuApi', () => ({
  KifuAPI: {
    getAlbum: vi.fn(),
    getAlbums: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 15 }),
  },
}));

const mockCreateSession = vi.fn().mockResolvedValue('session-123');
const mockDestroySession = vi.fn();
const mockOnMove = vi.fn();
const mockOnPass = vi.fn();
const mockOnNavigate = vi.fn();
const mockToggleHints = vi.fn();
const mockToggleOwnership = vi.fn();

// Settable across tests — the mocked hook reads this live on every render.
let mockGameState: GameState | null = null;

vi.mock('../../hooks/useResearchSession', () => ({
  useResearchSession: () => ({
    sessionId: 'session-123',
    gameState: mockGameState,
    error: null,
    isConnected: true,
    createSession: mockCreateSession,
    destroySession: mockDestroySession,
    onMove: mockOnMove,
    onPass: mockOnPass,
    onNavigate: mockOnNavigate,
    handleNavAction: vi.fn(),
    toggleHints: mockToggleHints,
    toggleOwnership: mockToggleOwnership,
    toggleMoveNumbers: vi.fn(),
    toggleCoordinates: vi.fn(),
    analyzeGame: vi.fn(),
    analysisScan: vi.fn(),
  }),
}));

// Import after mocks
import ResearchPage from '../pages/ResearchPage';
import { API } from '../../api';
import { KifuAPI } from '../../api/kifuApi';

function buildGameState(overrides: Partial<GameState> = {}): GameState {
  return {
    game_id: 'test-game',
    board_size: [19, 19],
    komi: 7.5,
    handicap: 0,
    ruleset: 'chinese',
    current_node_id: 2,
    current_node_index: 2,
    history: [
      { node_id: 0, score: 0, winrate: 0.5 },
      { node_id: 1, score: 1.2, winrate: 0.55 },
      { node_id: 2, score: 3.5, winrate: 0.632 },
    ],
    player_to_move: 'B',
    stones: [],
    last_move: null,
    prisoner_count: { B: 0, W: 0 },
    analysis: { winrate: 0.632, score: 3.5, moves: [] },
    commentary: '',
    is_root: false,
    is_pass: false,
    end_result: null,
    children: [],
    ghost_stones: [],
    players_info: {
      B: { player_type: 'human', player_subtype: '', name: 'fan', calculated_rank: null, periods_used: 0, main_time_used: 0 },
      W: { player_type: 'ai', player_subtype: 'katago', name: 'KataGo', calculated_rank: null, periods_used: 0, main_time_used: 0 },
    },
    note: '',
    ui_state: {
      show_children: false, show_dots: false, show_hints: false, show_policy: false,
      show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false,
    },
    language: 'zh',
    ...overrides,
  };
}

const renderPage = (initialEntries: string[] = ['/kiosk/research']) =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={initialEntries}>
        <ResearchPage />
      </MemoryRouter>
    </ThemeProvider>
  );

describe('ResearchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCreateSession.mockResolvedValue('session-123');
    mockGameState = null;
    vi.mocked(API.quickAnalyze).mockResolvedValue({ turnInfos: [{ moveInfos: [], ownership: null }] });
    vi.mocked(API.analysisScan).mockResolvedValue({});
    authState.current = { token: 'mock-token', isAuthenticated: true, user: { id: 1, username: 'test' }, login: vi.fn(), logout: vi.fn() };
  });

  it('keeps strict kiosk quick analysis on the cookie-only path when token is null', async () => {
    authState.current = { ...authState.current, token: null };
    renderPage();
    const user = userEvent.setup();
    await user.click(screen.getByText('支招').parentElement!);
    await waitFor(() => expect(API.quickAnalyze).toHaveBeenCalledWith(expect.any(Object), undefined));
  });

  // ── Step 2: L1 renders editable board + setup, no size picker ──
  describe('L1 edit view', () => {
    it('renders 对局信息 player fields', () => {
      renderPage();
      expect(screen.getByPlaceholderText('黑方')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('白方')).toBeInTheDocument();
    });

    it('renders the 编辑工具 grid (交替/摆黑/删除)', () => {
      renderPage();
      expect(screen.getByText('交替')).toBeInTheDocument();
      expect(screen.getByText('摆黑')).toBeInTheDocument();
      expect(screen.getByText('删除')).toBeInTheDocument();
    });

    it('renders the 开始研究 CTA', () => {
      renderPage();
      expect(screen.getByRole('button', { name: /开始研究/ })).toBeInTheDocument();
    });

    it('preserves the move-navigation testid', () => {
      renderPage();
      expect(screen.getByTestId('move-navigation')).toBeInTheDocument();
    });

    it('does not render a 棋盘大小 size picker', () => {
      renderPage();
      expect(screen.queryByText('棋盘大小')).not.toBeInTheDocument();
      expect(screen.queryByText('9×9')).not.toBeInTheDocument();
    });
  });

  // ── Step 3: start → analyzing ──
  it('transitions to the analyzing view on 开始研究 and starts the scan', async () => {
    vi.mocked(API.analysisProgress).mockResolvedValue({ analyzed: 10, total: 100 });
    renderPage();
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: /开始研究/ }));

    await waitFor(() => {
      expect(screen.getByText('正在分析全局')).toBeInTheDocument();
    });
    expect(API.analysisScan).toHaveBeenCalledWith(expect.any(String), 500);

    // Progress stats appear once the 1s poll tick resolves.
    await waitFor(() => {
      expect(screen.getByText('已分析手数')).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  // ── Step 4: complete → report ──
  it('transitions to the report view once analysis completes', async () => {
    mockGameState = buildGameState();
    vi.mocked(API.analysisProgress).mockResolvedValue({ analyzed: 100, total: 100 });
    const { container } = renderPage();
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: /开始研究/ }));

    await waitFor(() => {
      expect(screen.getByText('AI 推荐')).toBeInTheDocument();
    }, { timeout: 3000 });

    // Shared Board renders (canvas-based, no data-testid — query by tag).
    expect(container.querySelector('canvas')).toBeInTheDocument();

    // ResearchAnalysisPanel winrate marker (63.2%)
    expect(screen.getByText('63.2%')).toBeInTheDocument();
  });

  // ── Step 5: failure → retry, and 返回编辑 restores L1 ──
  it('shows the failure view after 5 consecutive poll failures and retries the scan', async () => {
    vi.mocked(API.analysisProgress).mockRejectedValue(new Error('engine down'));
    renderPage();
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: /开始研究/ }));

    await waitFor(() => {
      expect(screen.getByText('分析失败')).toBeInTheDocument();
    }, { timeout: 8000 });

    vi.mocked(API.analysisScan).mockClear();
    await user.click(screen.getByRole('button', { name: /重试分析/ }));

    await waitFor(() => {
      expect(API.analysisScan).toHaveBeenCalledWith(expect.any(String), 500);
    });
    // Retry does NOT destroy the session — it resumes the SAME live session.
    expect(mockDestroySession).not.toHaveBeenCalled();
  }, 12000);

  it('返回编辑 destroys the session and restores L1', async () => {
    mockGameState = buildGameState();
    vi.mocked(API.analysisProgress).mockResolvedValue({ analyzed: 100, total: 100 });
    renderPage();
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: /开始研究/ }));

    await waitFor(() => {
      expect(screen.getByText('AI 推荐')).toBeInTheDocument();
    }, { timeout: 3000 });

    await user.click(screen.getByRole('button', { name: /返回编辑/ }));

    await waitFor(() => {
      expect(mockDestroySession).toHaveBeenCalled();
    });
    expect(screen.getByRole('button', { name: /开始研究/ })).toBeInTheDocument();
  });

  // ── Step 5b: ?kifu_id deep-link passes the album SGF (not undefined) ──
  it('passes the fetched album SGF directly into createSession on ?kifu_id&analyze=1 deep link', async () => {
    const albumSgf = '(;GM[1]FF[4]SZ[19];B[pd];W[dp])';
    vi.mocked(KifuAPI.getAlbum).mockResolvedValue({ sgf_content: albumSgf });

    renderPage(['/kiosk/research?kifu_id=1&analyze=1']);

    await waitFor(() => {
      expect(KifuAPI.getAlbum).toHaveBeenCalledWith(1);
    });

    await waitFor(() => {
      expect(mockCreateSession).toHaveBeenCalledWith(
        expect.stringContaining('B[pd]'),
        expect.objectContaining({ skipAnalysis: true }),
      );
    });
    // Guards the Step 9 stale-board regression: never undefined.
    const firstArg = mockCreateSession.mock.calls[mockCreateSession.mock.calls.length - 1][0];
    expect(firstArg).not.toBeUndefined();
  });
});
