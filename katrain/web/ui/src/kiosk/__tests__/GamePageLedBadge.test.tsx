import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import type { GameState } from '../../api';

vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => ({ rotation: 0, setRotation: vi.fn() }),
}));

// Mock vision context — enabled with LED reported down (red badge scenario).
vi.mock('../context/VisionContext', () => ({
  useVision: () => ({
    visionStatus: {
      enabled: true,
      cameraConnected: true,
      poseLocked: true,
      syncState: 'synced',
      boundSessionId: 's1',
      ledConnected: false,
    },
    isVisionEnabled: true,
    refreshStatus: vi.fn(),
  }),
}));

// useVisionSync also needs a mock — empty event stream, no real WS connection in jsdom.
vi.mock('../hooks/useVisionSync', () => ({
  useVisionSync: () => ({ syncEvents: [], latestEvent: null, setupProgress: null, isSetupComplete: false }),
}));

// Mock auth
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'mock-token', isAuthenticated: true, user: { id: 1, username: 'test' }, login: vi.fn(), logout: vi.fn() }),
}));

// Mock Board component (canvas-based, can't render in jsdom)
vi.mock('../../components/Board', () => ({
  default: (props: any) => <div data-testid="board">Board</div>,
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

const renderGamePage = () =>
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

describe('GamePage 硬件故障', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // 上一版这里断言顶条上有一颗 MUI `LightbulbIcon`。那三颗**常亮**的状态灯
  // (摄像头 / 标定 / LED)Task 11 撤了 —— §5 说状态显示归 L1 镜像栏,L3 上没它们的位置。
  //
  // **但撤灯不能等于撤信号**:LED 掉线在这一屏原来只有那颗灯说得出来。
  // 现在改成「只在真出故障时说一句」,落在显示开关排右端那格 `.ghint`
  // (它本来就是用来解释「为什么那个键是灰的」的位置),平时不占地方。
  it('LED 掉线时,开关排右端把它说出来', () => {
    renderGamePage();
    expect(screen.getByText('LED 未连接 · 不再亮灯引导')).toBeInTheDocument();
    // 落在那一格,不是随便找个地方冒出来的
    expect(document.querySelector('.gtoggles .ghint')).toHaveTextContent('LED 未连接');
  });

  // 同一格还兼着「数子还差几手」。**故障优先** —— 差几手是常态提示,LED 掉了是坏了。
  it('故障压过「数子要下满 100 手」那句', () => {
    renderGamePage();
    expect(screen.queryByText(/数子要下满/)).toBeNull();
  });
});
