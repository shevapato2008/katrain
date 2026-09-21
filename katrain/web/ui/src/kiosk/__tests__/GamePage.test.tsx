import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import type { GameState } from '../../api';
import { SESSION_GONE_MESSAGE } from '../../utils/websocketUrl';

const { boardProps, sessionOverrides } = vi.hoisted(() => ({
  boardProps: [] as Array<Record<string, unknown>>,
  sessionOverrides: {} as Record<string, unknown>,
}));

// `vi.hoisted` avoids a TDZ ReferenceError — vi.mock factories are hoisted above
// ordinary `const` declarations in this file (see GamePageEngine.test.tsx for the
// same note); the `../../api` mock below needs `mockApiTimeout` at factory-call time.
const { mockApiTimeout } = vi.hoisted(() => ({ mockApiTimeout: vi.fn() }));

const { mockClearActiveSession } = vi.hoisted(() => ({ mockClearActiveSession: vi.fn() }));
vi.mock('../utils/activeSession', () => ({
  readActiveSession: vi.fn(() => null),
  writeActiveSession: vi.fn(),
  clearActiveSession: mockClearActiveSession,
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

// Task 5: only API.timeout needs a stub (the bound auto-timeout path calls it directly,
// bypassing useGameSession.handleAction). Spread the real module so ApiError (imported
// below) and every other API method keep their real implementation.
vi.mock('../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api')>();
  return { ...actual, API: { ...actual.API, timeout: mockApiTimeout } };
});

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
const mockSetGameState = vi.fn();
const mockReportSessionGone = vi.fn();

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
    setGameState: mockSetGameState,
    error: null,
    connectionLost: null,
    reportSessionGone: mockReportSessionGone,
    clearPhysicalEngineError: vi.fn(),
    onMove: mockOnMove,
    onNavigate: mockOnNavigate,
    handleAction: mockHandleAction,
    initNewSession: vi.fn(),
    lastLog: null,
    chatMessages: [],
    sendChat: vi.fn(),
    gameEndData: null,
    ...sessionOverrides,
  }),
}));

// Pulled out so a test can `rerender(pageTree())` after mutating `sessionOverrides` mid-test
// (the component identity stays the same; only the mocked hook's return value changes).
const pageTree = () => (
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter initialEntries={['/kiosk/play/ai/game/test-session']}>
      <Routes>
        <Route path="/kiosk/play/ai/game/:sessionId" element={<GamePage />} />
        <Route path="/kiosk/play" element={<div>PLAY_PAGE</div>} />
      </Routes>
    </MemoryRouter>
  </ThemeProvider>
);

const renderPage = () => render(pageTree());

// Import after mocks
import GamePage from '../pages/GamePage';
import { ApiError } from '../../api';

beforeEach(() => {
  vi.clearAllMocks();
  boardProps.length = 0;
  for (const k of Object.keys(sessionOverrides)) delete sessionOverrides[k];
});

describe('GamePage', () => {
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

  /* --- 游客:服务端算了但不交付(develop 的 `analysis_delivered`) -------------------
     后端那半是共享的,kiosk 自动吃到;这两条守的是**接线**——
     只测组件的话,`GamePage` 忘了传那个 prop 照样全绿。 */
  describe('无人认领的会话', () => {
    afterEach(() => {
      delete (mockGameState as Record<string, unknown>).analysis_delivered;
    });

    it('三个分析键灰掉,并且在屏上说出为什么', async () => {
      (mockGameState as Record<string, unknown>).analysis_delivered = false;
      renderPage();
      expect(screen.getByRole('button', { name: /领地/ })).toBeDisabled();
      expect(screen.getByRole('button', { name: /AI支招/ })).toBeDisabled();
      // 屏上那一句 —— **7 寸触屏够不着 tooltip,所以 `title` 不算数**,
      // 必须落在开关排右端那格。
      expect(document.querySelector('.gtoggles .ghint')).toHaveTextContent('登录后可用');
    });

    it('交付时一切照旧(老服务端不带这个字段 ⇒ undefined ⇒ 不触发)', async () => {
      renderPage();
      expect(screen.getByRole('button', { name: /领地/ })).not.toBeDisabled();
      expect(document.querySelector('.gtoggles .ghint')).not.toHaveTextContent('登录后可用');
    });
  });
});

const stillLive = () => new ApiError(409, 'Request failed 409: {"detail": "not your turn"}');

function openExitDialog() {
  fireEvent.click(screen.getByRole('button', { name: '退出对局' }));
}

describe('leaving is unconditional (R1)', () => {
  // "我们需要保证这边可以退出棋局就可以了". Leaving without resigning is a purely local
  // act and is always legitimate - gating it on connectionLost trapped the user behind
  // any failure that kept the socket healthy, e.g. Golaxy's 409 (server.py:2094).

  it('offers leave-without-resigning even on a healthy connection', () => {
    renderPage();
    openExitDialog();
    expect(screen.getByTestId('exit-leave-keep')).toBeInTheDocument();
  });

  it('leaves without calling the server at all', async () => {
    renderPage();
    openExitDialog();
    fireEvent.click(screen.getByTestId('exit-leave-keep'));

    expect(await screen.findByText('PLAY_PAGE')).toBeInTheDocument();
    expect(mockHandleAction).not.toHaveBeenCalled();
  });

  it('still offers it after a 409 that leaves the game live', async () => {
    mockHandleAction.mockRejectedValueOnce(stillLive());
    renderPage();
    openExitDialog();
    fireEvent.click(screen.getByRole('button', { name: '退出' }));

    await screen.findByText('认输没成');
    expect(screen.getByTestId('exit-leave-keep')).toBeInTheDocument();
  });

  it('shows the way out and clears the resume pointer once the session is gone', async () => {
    sessionOverrides.connectionLost = 'gone';
    sessionOverrides.error = '这一局在服务器上已经没有了，可以离开这一页。';
    renderPage();

    expect(await screen.findByTestId('game-gone-leave')).toBeInTheDocument();
    expect(mockClearActiveSession).toHaveBeenCalledWith('game');
  });

  it('that way out actually leaves', async () => {
    sessionOverrides.connectionLost = 'gone';
    renderPage();

    fireEvent.click(await screen.findByTestId('game-gone-leave'));
    expect(await screen.findByText('PLAY_PAGE')).toBeInTheDocument();
  });

  it('leave-without-resigning keeps the resume pointer', () => {
    // The game may still be live on the remote side - 继续上一局 is how the user
    // comes back to it. Only the gone signal may clear it.
    renderPage();
    openExitDialog();
    fireEvent.click(screen.getByTestId('exit-leave-keep'));

    expect(mockClearActiveSession).not.toHaveBeenCalled();
  });
});

describe('no raw request errors on screen (R2)', () => {
  // requestFailureKind maps 409 to 'other', and failureLine renders the prefix alone
  // when the reason is unknown - so the expected text is exactly the prefix.

  it('shows a classified sentence, not the ApiError message, when resign fails', async () => {
    mockHandleAction.mockRejectedValueOnce(stillLive());
    renderPage();

    fireEvent.click(screen.getByText('认输'));
    fireEvent.click(await screen.findByRole('button', { name: '认输' }));

    expect(await screen.findByText('认输没成')).toBeInTheDocument();
    expect(screen.queryByText(/Request failed/)).toBeNull();
    expect(screen.queryByText(/"detail"/)).toBeNull();
  });

  it('never renders an exception message when the failure has no status', async () => {
    // fetch itself throws a bare Error offline; requestFailureKind returns 'other'
    // because it never guesses. That path used to print "TypeError: Failed to fetch".
    mockHandleAction.mockRejectedValueOnce(new Error('TypeError: Failed to fetch'));
    renderPage();

    fireEvent.click(screen.getByText('认输'));
    fireEvent.click(await screen.findByRole('button', { name: '认输' }));

    expect(await screen.findByText('认输没成')).toBeInTheDocument();
    expect(screen.queryByText(/Failed to fetch/)).toBeNull();
  });

  it('does not leak a raw error through the connection snackbar', () => {
    // THE regression the first draft missed: after a 1008 credential rejection,
    // connectionLost stays 'rejected' and a later failed action overwrites
    // session.error with the ApiError message, which the fallback rendered verbatim.
    sessionOverrides.connectionLost = 'rejected';
    sessionOverrides.error = 'Request failed 409: {"detail": "not your turn"}';
    renderPage();

    expect(screen.queryByText(/Request failed/)).toBeNull();
    expect(screen.queryByText(/"detail"/)).toBeNull();
  });
});

// A18's bound auto-timeout: GameControlPanel's SeatRow clock (goClock.ts) calls this
// page's `handleClockExpired` → `send()`, which calls API.timeout directly — bypassing
// useGameSession.handleAction entirely. Task 2 turned that endpoint's 404-on-unknown-
// session into a 200 {status:'session_gone'} with no `.state`; these two tests are the
// regression Task 5 closes: before Task 2, a 404 there eventually surfaced 超时判定没有
// 送达; after Task 2 and before this fix, the 200 fell straight through to
// setTimeoutError(null) — nothing on screen at all.
//
// GameControlPanel/goClock are NOT mocked here (mocking them would blind every other test
// in this file to the real seat-clock wiring). Instead the fixture's timer is crafted so
// the clock reads "already expired" on the very first render — no fake timers needed:
// main_time is fully used and there is no byoyomi, so goClock's `elapsed: 0` reading is
// already `expired: true` the instant the effect runs after mount.
describe('bound auto-timeout against a gone session (Task 5)', () => {
  const expiredClockGameState: GameState = {
    ...mockGameState,
    timer: {
      paused: false,
      main_time_used: 60,
      current_node_time_used: 0,
      next_player_periods_used: 0,
      configured: true,
      settings: { main_time: 1, byo_length: 0, byo_periods: 0, minimal_use: 0, sound: false },
    },
    players_info: {
      ...mockGameState.players_info,
      B: { ...mockGameState.players_info.B, main_time_used: 60, periods_used: 0 },
    },
  };

  it('does not silently swallow a timeout against a session that is gone', async () => {
    sessionOverrides.gameState = expiredClockGameState;
    mockApiTimeout.mockResolvedValueOnce({ session_id: 'test-session', status: 'session_gone' });
    // Mirrors what the real useGameSession.reportSessionGone does (Task 5 adds it) —
    // this mock hook has no real React state of its own, so the test drives the same
    // state transition the production callback would cause.
    mockReportSessionGone.mockImplementationOnce(() => {
      sessionOverrides.connectionLost = 'gone';
      sessionOverrides.error = SESSION_GONE_MESSAGE;
    });
    const { rerender } = renderPage();

    await waitFor(() => expect(mockApiTimeout).toHaveBeenCalled());
    // THE regression: pre-fix, nothing downstream of the 200 ever ran.
    await waitFor(() => expect(mockReportSessionGone).toHaveBeenCalled());
    rerender(pageTree());

    // The user is told something, in the kiosk's own words - never the raw HTTP body.
    expect(await screen.findByText(SESSION_GONE_MESSAGE)).toBeInTheDocument();
    expect(screen.queryByText(/Request failed/)).toBeNull();
    expect(screen.queryByText(/"detail"/)).toBeNull();
  });

  it('tells the page the session is gone rather than inventing a state', async () => {
    sessionOverrides.gameState = expiredClockGameState;
    mockApiTimeout.mockResolvedValueOnce({ session_id: 'test-session', status: 'session_gone' });
    mockReportSessionGone.mockImplementationOnce(() => {
      sessionOverrides.connectionLost = 'gone';
      sessionOverrides.error = SESSION_GONE_MESSAGE;
    });
    const { rerender } = renderPage();

    await waitFor(() => expect(mockReportSessionGone).toHaveBeenCalled());
    rerender(pageTree());

    // Task 4's single sessionGone effect is the one reaction to the one signal: it clears
    // the resume pointer and offers the way out. Both only fire once connectionLost
    // actually flips to 'gone' - neither happened under the pre-fix silent no-op.
    expect(await screen.findByTestId('game-gone-leave')).toBeInTheDocument();
    expect(mockClearActiveSession).toHaveBeenCalledWith('game');
    // A 200 with no `.state` must never be mistaken for a real state update.
    expect(mockSetGameState).not.toHaveBeenCalledWith(undefined);
  });
});
