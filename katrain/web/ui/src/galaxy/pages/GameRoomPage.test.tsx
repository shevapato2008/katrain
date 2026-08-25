/**
 * 对局室迁到统一版式后的守卫。
 *
 * 五条闸的**红分支都变异证过**（2026-08-22，逐条都是 6 条里恰好红 1 条，还原后 6 条全绿）：
 *   M1 `isRated={isRankedGameType(...)}` → `isRated={true}`  ⇒「自由对局不该说自己是升降级」红
 *   M2 翻手键去掉 `aria-label`                                ⇒「六个键各有名字」红
 *   M3 去掉 `isSpectator={!isPlayer}`                        ⇒「观战者那四个键置灰」红
 *   M4 棋盘退回写死的 `{coords:true,numbers:false}`           ⇒「坐标开关通到棋盘」红
 *   M5 `actions={null}`（翻手键留在滚动段）                    ⇒「六个键在动作区」红
 */
import { render, screen, within, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { GameState } from '../../api';
import GameRoomPage from './GameRoomPage';

const mocks = vi.hoisted(() => ({
  gameState: null as GameState | null,
  handleAction: vi.fn(),
  onMove: vi.fn(),
  getFollowing: vi.fn(),
}));

vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ token: 'tk', user: { id: 1, username: 'fan' } }) }));
vi.mock('../../context/SettingsContext', () => ({ useSettings: () => ({}) }));
vi.mock('../../hooks/useTranslation', () => ({ useTranslation: () => ({ t: (_key: string, zh?: string) => zh ?? _key, lang: 'cn' }) }));
vi.mock('../context/GameNavigationContext', () => ({
  useGameNavigation: () => ({ registerActiveGame: vi.fn(), unregisterActiveGame: vi.fn(), requestNavigation: vi.fn() }),
}));
vi.mock('../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api')>();
  return { ...actual, API: { getFollowing: mocks.getFollowing, leaveMultiplayerGame: vi.fn(), requestCount: vi.fn(), respondCount: vi.fn() } };
});

/* 棋盘桩件把拿到的开关**回读**出来 —— 坐标 / 手数那两个开关以前是死的
   （面板一个字面量、棋盘另一个字面量），只断言开关自己变了是证不到这一点的。 */
vi.mock('../../components/Board', () => ({
  default: ({ analysisToggles }: { analysisToggles: Record<string, boolean> }) => (
    <div data-testid="mock-board" data-coords={String(analysisToggles.coords)} data-numbers={String(analysisToggles.numbers)} />
  ),
}));
vi.mock('../../components/ScoreGraph', () => ({ default: () => <div data-testid="mock-score-graph" /> }));

vi.mock('../../hooks/useGameSession', () => ({
  useGameSession: () => ({
    sessionId: 's1', setSessionId: vi.fn(), gameState: mocks.gameState, error: null,
    onMove: mocks.onMove, onNavigate: vi.fn(), handleAction: mocks.handleAction, gameEndData: null,
  }),
}));

const makeState = (over: Partial<GameState> = {}): GameState => ({
  game_id: 'g1', board_size: [19, 19], komi: 7.5, handicap: 0, ruleset: 'chinese', current_node_id: 1,
  current_node_index: 1, history: [], player_to_move: 'B', stones: [], last_move: null,
  prisoner_count: { B: 0, W: 0 }, analysis: null, commentary: '', is_root: false, is_pass: false,
  end_result: null, children: [], ghost_stones: [], note: '', language: 'zh', game_type: 'free',
  sockets_count: 5,
  players_info: {
    B: { player_type: 'human', player_subtype: '', name: 'fan', calculated_rank: null, periods_used: 0, main_time_used: 0 },
    W: { player_type: 'human', player_subtype: '', name: 'cat', calculated_rank: null, periods_used: 0, main_time_used: 0 },
  },
  ui_state: { show_children: false, show_dots: false, show_hints: false, show_policy: false, show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false },
  ...over,
} as GameState);

const renderPage = () => render(
  <MemoryRouter initialEntries={['/galaxy/play/game/s1']}>
    <Routes><Route path="/galaxy/play/game/:sessionId" element={<GameRoomPage />} /></Routes>
  </MemoryRouter>
);

const NAV_NAMES = ['跳到开局', '后退 10 手', '后退一手', '前进一手', '前进 10 手', '跳到最后'];

describe('GameRoomPage 统一版式', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getFollowing.mockResolvedValue([]);
    mocks.gameState = makeState();
  });

  it('puts all six navigation keys in the non-scrolling actions band, each with a name', () => {
    renderPage();
    const actions = within(screen.getByTestId('board-rail-actions'));
    for (const name of NAV_NAMES) {
      expect(actions.getByRole('button', { name })).toBeInTheDocument();
    }
    // 它们**不在**滚动段里 —— 长盘时不该要滚到底才够得着。
    const scroll = within(screen.getByTestId('board-rail-scroll'));
    expect(scroll.queryByRole('button', { name: '跳到开局' })).not.toBeInTheDocument();
  });

  it('carries turn state on the module plate instead of a bar above the board', () => {
    renderPage();
    expect(within(screen.getByTestId('board-rail-module')).getByText('轮到你了')).toBeInTheDocument();
    // 棋盘那一格里只有棋盘：观众数和离开键都降到了右栏。
    const stage = screen.getByTestId('board-stage');
    expect(stage).toHaveTextContent('');
    // sockets_count 5 = 两名棋手 + 3 名观众
    expect(screen.getByTestId('board-rail-scroll')).toHaveTextContent('3 Spectators');
  });

  /* 这一条守的是那个 bug：以前对局室无条件传 isRated={true}，
     于是一局**自由**人人对弈也挂着升降级横幅。 */
  it('does not claim a free human-vs-human game is rated', () => {
    renderPage();
    expect(screen.queryByText('Rated Mode: Progressing')).not.toBeInTheDocument();
    // 但分析类道具照样锁死 —— 人人对弈没有引擎，这与算不算段位无关。
    expect(screen.getByRole('button', { name: 'Territory' })).toBeDisabled();
  });

  it('does show the rated banner when the room really hosts a ranked game', () => {
    mocks.gameState = makeState({ game_type: 'ranked' as GameState['game_type'] });
    renderPage();
    expect(screen.getByText('Rated Mode: Progressing')).toBeInTheDocument();
  });

  /* 观战者的悔棋 / 停一手 / 认输 / 数子今天仍然可按，但 onAction 被换成了空函数 ——
     点了没有任何反应，是账本意义上的空按钮。 */
  it('greys out the action keys for a spectator and offers stop-watching instead of leave', () => {
    mocks.gameState = makeState({
      players_info: {
        B: { player_type: 'human', player_subtype: '', name: 'bob', calculated_rank: null, periods_used: 0, main_time_used: 0 },
        W: { player_type: 'human', player_subtype: '', name: 'cat', calculated_rank: null, periods_used: 0, main_time_used: 0 },
      },
    } as Partial<GameState>);
    renderPage();
    for (const name of ['Undo', 'Pass', 'Resign', 'Count']) {
      expect(screen.getByRole('button', { name })).toBeDisabled();
    }
    expect(screen.getByRole('button', { name: '退出观战' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '离开对局' })).not.toBeInTheDocument();
  });

  /* 坐标开关以前是死的：面板照 `coords: true` 这个字面量渲染、onToggleChange 对它是空操作，
     棋盘拿的又是另一个写死的 `{coords: true}`。断言落在**棋盘收到的值**上。 */
  it('wires the coordinates switch through to the board', () => {
    renderPage();
    expect(screen.getByTestId('mock-board')).toHaveAttribute('data-coords', 'true');
    fireEvent.click(screen.getByRole('switch', { name: 'Coordinates' }));
    expect(screen.getByTestId('mock-board')).toHaveAttribute('data-coords', 'false');
  });
});
