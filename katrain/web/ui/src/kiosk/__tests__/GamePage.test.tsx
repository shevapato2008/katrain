import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import type { GameState } from '../../api';

const { boardProps } = vi.hoisted(() => ({
  boardProps: [] as Array<Record<string, unknown>>,
}));

vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => ({ rotation: 0, setRotation: vi.fn() }),
}));

// Mock vision context (GamePage reads visionStatus + isVisionEnabled directly).
// Disabled vision keeps all vision branches (overlay, toasts, useVisionSync) inert.
vi.mock('../context/VisionContext', () => ({
  useVision: () => ({
    visionStatus: {
      enabled: false,
      cameraConnected: false,
      poseLocked: false,
      syncState: 'idle',
      boundSessionId: null,
    },
    isVisionEnabled: false,
    refreshStatus: vi.fn(),
  }),
}));

// Mock auth
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'mock-token', isAuthenticated: true, user: { id: 1, username: 'test' }, login: vi.fn(), logout: vi.fn() }),
}));

// Mock Board component (canvas-based, can't render in jsdom)
vi.mock('../../components/Board', () => ({
  default: (props: Record<string, unknown>) => {
    boardProps.push(props);
    return <div data-testid="board">Board</div>;
  },
}));

// Mock PlayerCard (uses translations)
vi.mock('../../components/PlayerCard', () => ({
  default: (props: any) => <div data-testid={`player-card-${props.player}`}>{props.info.name} ({props.info.calculated_rank})</div>,
}));

// Mock ScoreGraph (SVG-heavy)
vi.mock('../../components/ScoreGraph', () => ({
  default: (props: any) => <div data-testid="score-graph-component">ScoreGraph</div>,
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
    B: { player_type: 'human', player_subtype: '', name: '张三', calculated_rank: '2D', periods_used: 0, main_time_used: 0 },
    W: { player_type: 'ai', player_subtype: 'katago', name: 'KataGo', calculated_rank: '5D', periods_used: 0, main_time_used: 0 },
  },
  note: '',
  ui_state: {
    show_children: false, show_dots: false, show_hints: false, show_policy: false,
    show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false,
  },
  language: 'zh',
};

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

// Import after mocks
import GamePage from '../pages/GamePage';

describe('GamePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    boardProps.length = 0;
  });

  it('renders Board component', () => {
    renderPage();
    expect(screen.getByTestId('board')).toBeInTheDocument();
  });

  it('does not enable stone navigation on the live board', () => {
    renderPage();
    expect(boardProps).toHaveLength(1);
    expect(boardProps[0]).not.toHaveProperty('onNavigate');
  });

  it('renders player cards with names and ranks', () => {
    renderPage();
    expect(screen.getByTestId('player-card-B')).toHaveTextContent('张三');
    expect(screen.getByTestId('player-card-W')).toHaveTextContent('KataGo');
  });

  // 上一版这几条是右栏里一整条 `Game info bar`。规则和贴目是**这一局开局时定死的**,
  // 不是过程量 —— Task 11 起它们并进页控条副标,占 0 高度(右栏 516 装下胜率块靠的就是这个)。
  it('页控条副标写着这一局的开局条件:路数 / 规则 / 贴目 / 让子', () => {
    renderPage();
    const sub = document.querySelector('.kiosk-pagebar__sub');
    expect(sub).toHaveTextContent('19 路');
    expect(sub).toHaveTextContent('日本 规则');
    expect(sub).toHaveTextContent('贴目 6.5');
    expect(sub).toHaveTextContent('不让子');
  });

  it('renders all 7 ItemToggles', () => {
    renderPage();
    expect(screen.getByText('领地')).toBeInTheDocument();
    expect(screen.getByText('AI支招')).toBeInTheDocument();
    expect(screen.getByText('图表')).toBeInTheDocument();
    expect(screen.getByText('悔棋')).toBeInTheDocument();
    expect(screen.getByText('停一手')).toBeInTheDocument();
    expect(screen.getByText('认输')).toBeInTheDocument();
    expect(screen.getByText('数子')).toBeInTheDocument();
  });

  // 着法导航整排原来 `disabled={!isGameOver}` —— 对局中全程是灰的。
  // 稿子的判词:「要画就得先加那一屏,不是在这一屏塞一排点不动的键」。⇒ 对局中整组不渲染。
  // 终局那一态在 `GamePage.test.tsx`(pages/)里有 `end_result` 的用例,这里只守「对局中没有」。
  it('对局中不渲染着法导航 —— 它整排要到终局才活', () => {
    renderPage();
    expect(screen.queryByTestId('nav-controls')).toBeNull();
  });

  // 标题 = **这一局是哪种对弈**,不是「张三 vs KataGo」:名字在玩家卡里各占一行
  // (还带段位、执色、提子),标题再写一遍是把 460 宽的一行花在已经看得见的东西上。
  it('页控条写的是对弈方式和退出对局,名字留给玩家卡', () => {
    renderPage();
    expect(screen.getByText('自由对弈')).toBeInTheDocument();
    expect(screen.getByText('退出对局')).toBeInTheDocument();
    expect(screen.queryByText('张三 vs KataGo')).toBeNull();
  });

  it('does NOT render navigation rail (fullscreen)', () => {
    renderPage();
    expect(screen.queryByText('对弈')).not.toBeInTheDocument();
    expect(screen.queryByText('死活')).not.toBeInTheDocument();
  });

  it('calls handleAction when action buttons are clicked', () => {
    renderPage();
    fireEvent.click(screen.getByText('悔棋'));
    expect(mockHandleAction).toHaveBeenCalledWith('undo');
  });
});
