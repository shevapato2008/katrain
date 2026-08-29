import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import AiSetupPage from './AiSetupPage';
// mock 工厂把真的 ApiError 透传了出来（见下面的 vi.mock），所以这里拿到的就是页面
// `err instanceof ApiError` 判的那一个类，不是替身。
import { ApiError as ApiErrorReal } from '../../api';
import { AiLadderApiError } from '../../features/aiLadder/api';

// Task 11: 棋力阶梯 (strength ladder) 37-rung opponent selector on the galaxy AiSetupPage.
// Mirrors the Vitest/RTL pattern in kiosk/pages/PlatformEngineSetupPage.test.tsx: mock the
// API module (vi.hoisted so the mocked fns are reachable from assertions) and mock the
// auth/settings contexts (this page isn't wrapped in their Providers in isolation).
//
// This page's pre-existing Selects (Board Size / Ruleset / Your Color / AI Strategy) don't
// wire an MUI `labelId`, so `getByRole('combobox', { name })` can't resolve an accessible
// name for them (unlike kiosk/pages/AiSetupPage.tsx, which does). That's pre-existing,
// out-of-scope behavior — so tests locate a Select by its <label> text instead of relying
// on the accessible-name computation.

const mockNavigate = vi.fn();
const mockRequestNavigation = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../context/GameNavigationContext', () => ({
  useGameNavigation: () => ({ requestNavigation: mockRequestNavigation }),
}));

const { mockAiConstants, mockRungsResponse, mockCreateSession, mockNewGame, mockUpdateConfig, mockStartRanked, mockEndRanked, mockRetrySettlement, rankedState, authState, mockRetry, mockApplyBlockingSync } = vi.hoisted(() => ({
  mockAiConstants: {
    strategies: ['ai:human', 'ai:ladder'],
    options: {},
    key_properties: [],
    default_strategy: 'ai:human',
    strategy_defaults: {
      'ai:human': { human_kyu_rank: 0 },
      'ai:ladder': {},
    },
  },
  mockRungsResponse: {
    // 与 GET /api/ladder-rungs 的真实投影同形（五个字段）。第三条是**封档档位**：
    // 目录里有它、有配方，但 availability=unavailable ⇒ 谁也坐不上去，不该出现在下拉里。
    rungs: [
      { rung: 18, rank_name: '3K', certification_status: 'certified', availability: 'available', route: 'server' },
      { rung: 37, rank_name: 'KataGo中等', certification_status: 'certified', availability: 'available', route: 'server' },
      { rung: 21, rank_name: '准1段', certification_status: 'provisional', availability: 'unavailable', route: 'server' },
    ],
  },
  mockCreateSession: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
  mockNewGame: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
  mockUpdateConfig: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
  mockStartRanked: vi.fn().mockResolvedValue({ session_id: 'ranked-s1', game_id: 'g1' }),
  mockEndRanked: vi.fn(),
  mockRetrySettlement: vi.fn(),
  mockRetry: vi.fn(),
  mockApplyBlockingSync: vi.fn(),
  rankedState: { current: null as any },
  authState: { current: { token: 'test-token', user: { id: 1, username: 'test' }, isAuthenticated: true } as any },
}));

// `ApiError` 要用**真的那一个**:页面靠 `err instanceof ApiError` 把 401 与别的失败分开,
// mock 里少了它就不是「测不到」而是 `instanceof undefined` 当场 TypeError。
vi.mock('../../api', async () => ({
  ApiError: (await vi.importActual<typeof import('../../api')>('../../api')).ApiError,
  API: {
    createSession: mockCreateSession,
    getAIConstants: vi.fn().mockResolvedValue(mockAiConstants),
    getLadderRungs: vi.fn().mockResolvedValue(mockRungsResponse),
    newGame: mockNewGame,
    updateConfigBulk: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
    updatePlayer: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
    updateConfig: mockUpdateConfig,
    estimateRank: vi.fn().mockResolvedValue({ rank: '5k' }),
  },
}));

vi.mock('../../features/aiLadder/api', async () => {
  const actual = await vi.importActual<typeof import('../../features/aiLadder/api')>('../../features/aiLadder/api');
  return {
    ...actual,
    startAiLadderGame: mockStartRanked,
    endAiLadderGame: mockEndRanked,
    retryAiLadderSettlement: mockRetrySettlement,
  };
});
vi.mock('../../features/aiLadder/useAiLadderStatus', () => ({
  useAiLadderStatus: () => ({
    status: rankedState.current,
    retry: mockRetry,
    applyBlockingSync: mockApplyBlockingSync,
  }),
}));

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => authState.current,
}));

vi.mock('../../context/SettingsContext', () => ({
  useSettings: () => ({ language: 'cn', setLanguage: vi.fn(), languages: [] }),
}));

const renderPage = (mode = 'free') => {
  const params = new URLSearchParams({ mode });
  return render(
    <MemoryRouter initialEntries={[`/galaxy/play/ai/setup?${params.toString()}`]}>
      <Routes>
        <Route path="/galaxy/play/ai/setup" element={<AiSetupPage />} />
      </Routes>
    </MemoryRouter>
  );
};

const blockingGame = (
  state: 'reserved' | 'active' | 'pending_settlement' = 'active',
  ownership: 'current_device' | 'other_device' = 'current_device',
  sessionId: string | undefined = 'occupied-session',
) => ({
  game_id: 'occupied-game',
  state,
  ownership,
  ...(sessionId ? { session_id: sessionId } : {}),
  user_color: 'B' as const,
  opponent_rank_name: '4级',
});

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
};

// Locate a Select's combobox by its <label> text (no labelId wiring on this page's Selects,
// so getByRole('combobox', { name }) can't resolve; the label text also appears in the
// notched-outline <legend>, so filter to the actual <label> element).
const comboboxForLabel = (text: string): HTMLElement => {
  const label = screen.getAllByText(text).find((el) => el.tagName === 'LABEL');
  if (!label) throw new Error(`No <label> found with text "${text}"`);
  const formControl = label.closest('.MuiFormControl-root') as HTMLElement;
  return within(formControl).getByRole('combobox');
};

describe('AiSetupPage — 棋力阶梯 ladder opponent', () => {
  beforeEach(() => {
    sessionStorage.clear();
    mockNavigate.mockReset();
    mockRequestNavigation.mockReset();
    mockNewGame.mockClear();
    mockUpdateConfig.mockClear();
  });

  it('lists 棋力阶梯 in the AI Strategy dropdown', async () => {
    renderPage();
    await waitFor(() => expect(comboboxForLabel('AI Strategy')).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(comboboxForLabel('AI Strategy'));
    expect(screen.getByRole('option', { name: '棋力阶梯' })).toBeInTheDocument();
  });

  it('shows a rung selector (not the human-rank slider) once 棋力阶梯 is chosen', async () => {
    renderPage();
    await waitFor(() => expect(comboboxForLabel('AI Strategy')).toBeInTheDocument());
    const user = userEvent.setup();

    await user.click(comboboxForLabel('AI Strategy'));
    await user.click(screen.getByRole('option', { name: '棋力阶梯' }));

    // Default rung 18 (native HumanSL 3K) is pre-selected; label is rank_name only, no elo.
    await waitFor(() => {
      expect(screen.getByText('3K')).toBeInTheDocument(); // rank_name only, no elo
    });
    // The generic human-rank slider (visible for ai:human) must not be showing.
    expect(screen.queryByText('20k')).not.toBeInTheDocument();
  });

  it('omits sealed rungs from the selector — they exist in the catalog but seat nobody', async () => {
    // 目录里 12 档是封档的（`ladder._RETIRED_RUNGS`）。它们保留配方是为了让账本里已存的
    // rung 号仍可解释，但选中开局会 409 —— 用户看到的是「点了没反应」。
    renderPage();
    await waitFor(() => expect(comboboxForLabel('AI Strategy')).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(comboboxForLabel('AI Strategy'));
    await user.click(screen.getByRole('option', { name: '棋力阶梯' }));
    await waitFor(() => expect(screen.getByText('3K')).toBeInTheDocument());

    await user.click(comboboxForLabel('棋力等级'));
    // 正对照：可用的两档在；没有它，「封档档位不在」和「下拉整个是空的」分不开。
    expect(screen.getByRole('option', { name: '3K' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'KataGo中等' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: '准1段' })).toBeNull();
  });

  it('starts the game with ladder_rung and skips human_kyu_rank/strategySettings writes', async () => {
    renderPage();
    await waitFor(() => expect(comboboxForLabel('AI Strategy')).toBeInTheDocument());
    const user = userEvent.setup();

    await user.click(comboboxForLabel('AI Strategy'));
    await user.click(screen.getByRole('option', { name: '棋力阶梯' }));

    // Pick the strongest rung (37, KataGo中等) from the rung selector.
    await waitFor(() => expect(screen.getByText('3K')).toBeInTheDocument());
    await user.click(comboboxForLabel('棋力等级'));
    await user.click(screen.getByRole('option', { name: 'KataGo中等' }));

    await user.click(screen.getByRole('button', { name: /start game/i }));

    await waitFor(() => {
      expect(mockNewGame).toHaveBeenCalledWith(
        's1',
        expect.objectContaining({ ladder_rung: 37 }),
      );
    });

    // No ai:ladder config write (human_kyu_rank is only ever written for ai:human;
    // strategySettings for ai:ladder is always {} so updateConfig(`ai/ai:ladder`, ...)
    // must never fire).
    const ladderConfigCalls = mockUpdateConfig.mock.calls.filter(([, setting]) => setting === 'ai/ai:ladder');
    expect(ladderConfigCalls).toHaveLength(0);
  });
});

describe('AiSetupPage — rated AI ladder visual slice', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    mockStartRanked.mockClear();
    mockCreateSession.mockClear();
    mockNewGame.mockClear();
    mockRetry.mockClear();
    mockRetry.mockReset();
    mockEndRanked.mockReset();
    mockRetrySettlement.mockReset();
    mockApplyBlockingSync.mockReset();
    authState.current = { token: 'test-token', user: { id: 1, username: 'test' }, isAuthenticated: true };
    rankedState.current = {
      view_state: 'ready',
      placement_state: { phase: 'placement', completed_games: 3, total_games: 5 },
      current_opponent: { rung: 17, rank_name: '4级', certification_status: 'certified', availability: 'available', route: 'server' },
      recent_ranked_results: [], net_score: 0, pending_settlement: false,
    };
    mockStartRanked.mockResolvedValue({ session_id: 'ranked-s1', game_id: 'g1', status: rankedState.current });
  });

  it('replaces the rated HumanSL controls with the server-decided placement opponent', async () => {
    renderPage('rated');

    expect(await screen.findByRole('heading', { name: '升降级对弈' })).toBeInTheDocument();
    expect(screen.getByText('定级进度 3/5')).toBeInTheDocument();
    expect(screen.getByText('4级')).toBeInTheDocument();
    expect(screen.queryByText('20k')).not.toBeInTheDocument();
    expect(screen.queryByText('9d')).not.toBeInTheDocument();
    expect(screen.queryByText('Human-like')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '开始正式对局' })).toBeEnabled();
    expect(screen.queryByText('累计净胜分：0')).not.toBeInTheDocument();
  });

  it('shows the current public 41-rung rank without an internal rung number', async () => {
    rankedState.current = { ...rankedState.current, placement_state: { phase: 'placed', rung: { rung: 30, rank_name: '5段', certification_status: 'certified', availability: 'available', route: 'server' } } };
    renderPage('rated');

    expect(await screen.findByText('5段', { selector: '[data-testid="current-rank"]' })).toBeInTheDocument();
    expect(screen.queryByText('第30档')).not.toBeInTheDocument();
  });

  it('retries a failed ranked-status load inside the rated setup flow', async () => {
    const user = userEvent.setup();
    rankedState.current = { view_state: 'error', message: '服务暂时不可用' };
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '重试' }));

    expect(mockRetry).toHaveBeenCalledTimes(1);
  });

  it('starts rated play only through the authoritative endpoint', async () => {
    renderPage('rated');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: '开始正式对局' }));

    // Board size, ruleset, komi and handicap are server-owned (the calibration
    // conditions) and the request model forbids extras — the page sends seat + clock.
    await waitFor(() => expect(mockStartRanked).toHaveBeenCalledWith(expect.objectContaining({
      color: 'black',
    }), 'test-token'));
    const sent = mockStartRanked.mock.calls[0][0];
    expect(sent).not.toHaveProperty('board_size');
    expect(sent).not.toHaveProperty('rules');
    expect(sent).not.toHaveProperty('komi');
    expect(sent).not.toHaveProperty('handicap');
    expect(mockCreateSession).not.toHaveBeenCalled();
    expect(mockNewGame).not.toHaveBeenCalled();
    expect(mockNavigate).toHaveBeenCalledWith('/galaxy/play/game/ranked-s1?mode=rated&game_id=g1');
    expect(JSON.parse(sessionStorage.getItem('ai-ladder-before:ranked-s1')!)).toEqual(expect.objectContaining({
      game_id: 'g1',
    }));
  });

  it('does not mount ranked status in free play', async () => {
    renderPage('free');

    await waitFor(() => expect(comboboxForLabel('AI Strategy')).toBeInTheDocument());
    expect(screen.queryByRole('heading', { name: '升降级对弈' })).not.toBeInTheDocument();
  });

  it('continues the occupied rated game through its rated session route', async () => {
    const user = userEvent.setup();
    rankedState.current = { ...rankedState.current, blocking_game: blockingGame() };
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '继续对局' }));

    expect(mockNavigate).toHaveBeenCalledOnce();
    expect(mockNavigate).toHaveBeenCalledWith('/galaxy/play/game/occupied-session?mode=rated&game_id=occupied-game');
    expect(JSON.parse(sessionStorage.getItem('ai-ladder-before:occupied-session')!)).toEqual(expect.objectContaining({
      game_id: 'occupied-game',
    }));
  });

  it.each([
    ['active-other', blockingGame('active', 'other_device')],
    ['pending', blockingGame('pending_settlement')],
  ])('挡局面板不摆「刷新状态」:%s', async (_label, occupiedGame) => {
    // 它做的事(重问一次 /status)这块屏每 15 秒已经在自动做,所以它在每一格
    // 要么是别的按钮的真子集,要么什么都改不了。
    rankedState.current = { ...rankedState.current, blocking_game: occupiedGame };
    renderPage('rated');

    await screen.findByRole('button', { name: '认输那一局，在这里开新局' });
    expect(screen.queryByRole('button', { name: '刷新状态' })).not.toBeInTheDocument();
  });

  it('ends a confirmed occupied game through the authenticated lifecycle API', async () => {
    const user = userEvent.setup();
    rankedState.current = { ...rankedState.current, blocking_game: blockingGame() };
    mockEndRanked.mockResolvedValue({ state: 'pending_settlement', game_id: 'occupied-game' });
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '认输那一局，在这里开新局' }));
    await user.click(screen.getByRole('button', { name: '确认认输' }));

    await waitFor(() => expect(mockEndRanked).toHaveBeenCalledWith('occupied-game', 'test-token'));
  });

  it('让掉一个从没开起来的预约:屏上不说记负，服务端答 released 也不当成失败', async () => {
    // 页面这一层要证的是**两端接得上**:后端在这一格回的是 `released`(没有 receipt),
    // 而 `endGame` 的分支要认得它、走「只刷新状态」,不弹结算回执、不写「结束对局失败」。
    // 这个形状此前一度在解码器里被当成畸形响应,屏上写「结束对局失败，请重试」,
    // 而那一刻账号其实已经放开了。
    const user = userEvent.setup();
    rankedState.current = {
      ...rankedState.current,
      blocking_game: blockingGame('reserved', 'other_device', undefined),
    };
    mockEndRanked.mockResolvedValue({ state: 'released', game_id: 'occupied-game', counted: false });
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '让掉它，在这里开新局' }));
    expect(document.body.textContent).not.toMatch(/记为本局负|计为本局负|计入升降级/);
    await user.click(screen.getByRole('button', { name: '确认让掉' }));

    await waitFor(() => expect(mockEndRanked).toHaveBeenCalledWith('occupied-game', 'test-token'));
    await waitFor(() => expect(mockRetry).toHaveBeenCalledOnce());
    expect(screen.queryByText('结束对局失败，请重试')).not.toBeInTheDocument();
    expect(screen.queryByText('结算已完成')).not.toBeInTheDocument();
  });

  it('refreshes ranked status when ending enters pending settlement', async () => {
    const user = userEvent.setup();
    rankedState.current = { ...rankedState.current, blocking_game: blockingGame() };
    mockEndRanked.mockResolvedValue({ state: 'pending_settlement', game_id: 'occupied-game' });
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '认输那一局，在这里开新局' }));
    await user.click(screen.getByRole('button', { name: '确认认输' }));

    await waitFor(() => expect(mockRetry).toHaveBeenCalledOnce());
  });

  it('keeps a settled receipt visible after refreshed status removes the blocking game', async () => {
    const user = userEvent.setup();
    const refreshedStatus = { ...rankedState.current };
    rankedState.current = { ...rankedState.current, blocking_game: blockingGame() };
    mockEndRanked.mockResolvedValue({
      state: 'settled',
      game_id: 'occupied-game',
      receipt: { counted: true, reason: null },
    });
    mockRetry.mockImplementation(() => {
      rankedState.current = refreshedStatus;
    });
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '认输那一局，在这里开新局' }));
    await user.click(screen.getByRole('button', { name: '确认认输' }));

    expect(await screen.findByText('结算已完成')).toBeInTheDocument();
    expect(screen.getByText(/本局已计入升降级/)).toBeInTheDocument();
    expect(screen.queryByText('未完成对局')).not.toBeInTheDocument();
    expect(mockRetry).toHaveBeenCalledOnce();
  });

  it('preserves the occupied panel and shows an inline error when ending fails', async () => {
    const user = userEvent.setup();
    rankedState.current = { ...rankedState.current, blocking_game: blockingGame() };
    mockEndRanked.mockRejectedValue(new Error('gateway exploded'));
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '认输那一局，在这里开新局' }));
    await user.click(screen.getByRole('button', { name: '确认认输' }));

    expect(await screen.findByText('结束对局失败，请重试')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(screen.getByText('未完成对局')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '继续对局' })).toBeEnabled();
    expect(mockRetry).not.toHaveBeenCalled();
  });

  it('ignores an old end response after the account and blocking game change', async () => {
    const user = userEvent.setup();
    const oldEnd = deferred<any>();
    rankedState.current = { ...rankedState.current, blocking_game: blockingGame() };
    mockEndRanked.mockReturnValue(oldEnd.promise);
    const view = renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '认输那一局，在这里开新局' }));
    await user.click(screen.getByRole('button', { name: '确认认输' }));
    await waitFor(() => expect(mockEndRanked).toHaveBeenCalledOnce());

    authState.current = { token: 'new-token', user: { id: 2, username: 'new-user' }, isAuthenticated: true };
    rankedState.current = {
      ...rankedState.current,
      blocking_game: { ...blockingGame(), game_id: 'new-game', session_id: 'new-session' },
    };
    view.rerender(
      <MemoryRouter initialEntries={['/galaxy/play/ai/setup?mode=rated']}>
        <Routes><Route path="/galaxy/play/ai/setup" element={<AiSetupPage />} /></Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByRole('button', { name: '继续对局' })).toBeEnabled());

    await act(async () => {
      oldEnd.resolve({
        state: 'settled', game_id: 'occupied-game', receipt: { counted: true, reason: null },
      });
      await oldEnd.promise;
    });

    expect(screen.getByText('未完成对局')).toBeInTheDocument();
    expect(screen.queryByText('结算已完成')).not.toBeInTheDocument();
    expect(mockRetry).not.toHaveBeenCalled();
  });

  it('releases lifecycle pending when the same account moves from game A to game B', async () => {
    const user = userEvent.setup();
    const oldEnd = deferred<any>();
    rankedState.current = { ...rankedState.current, blocking_game: blockingGame() };
    mockEndRanked.mockReturnValue(oldEnd.promise);
    const view = renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '认输那一局，在这里开新局' }));
    await user.click(screen.getByRole('button', { name: '确认认输' }));
    await waitFor(() => expect(screen.getByRole('button', { name: '继续对局' })).toBeDisabled());

    rankedState.current = {
      ...rankedState.current,
      blocking_game: { ...blockingGame(), game_id: 'game-b', session_id: 'session-b' },
    };
    view.rerender(
      <MemoryRouter initialEntries={['/galaxy/play/ai/setup?mode=rated']}>
        <Routes><Route path="/galaxy/play/ai/setup" element={<AiSetupPage />} /></Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByRole('button', { name: '继续对局' })).toBeEnabled());
    await act(async () => {
      oldEnd.resolve({
        state: 'settled', game_id: 'occupied-game', receipt: { counted: true, reason: null },
      });
      await oldEnd.promise;
    });
    expect(screen.queryByText('结算已完成')).not.toBeInTheDocument();
    expect(mockRetry).not.toHaveBeenCalled();
  });

  it('「立即重试」送成之后，上一次失败留下的错误条不许还挂着', async () => {
    const user = userEvent.setup();
    const syncing = {
      ...blockingGame('pending_settlement'),
      sync: {
        state: 'waiting', attempt: 2, max_attempts: 5, next_attempt_in_seconds: 20,
        last_http_status: null, last_error: 'timeout',
      },
    };
    rankedState.current = { ...rankedState.current, blocking_game: syncing };
    mockEndRanked.mockRejectedValue(new Error('gateway exploded'));
    // 重试送成 → 那一局不再挡着新局,页面回到正常开局卡。
    mockRetrySettlement.mockResolvedValue({ game_id: 'occupied-game', sync: null });
    mockRetry.mockImplementation(() => {
      rankedState.current = { ...rankedState.current, blocking_game: null };
    });
    renderPage('rated');

    // 先制造一条陈旧错误:开新局失败。
    await user.click(await screen.findByRole('button', { name: '认输那一局，在这里开新局' }));
    await user.click(screen.getByRole('button', { name: '确认认输' }));
    expect(await screen.findByText('结束对局失败，请重试')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());

    await user.click(screen.getByRole('button', { name: '立即重试' }));

    expect(mockRetrySettlement).toHaveBeenCalledWith('occupied-game', 'test-token');
    // 无论成败都复查一次状态 —— 送成了这一局就不该再挡着新局。
    await waitFor(() => expect(mockRetry).toHaveBeenCalled());
    expect(screen.queryByText('结束对局失败，请重试')).not.toBeInTheDocument();
  });

  it('refreshes status without a stale error when the occupied game already vanished', async () => {
    const user = userEvent.setup();
    rankedState.current = { ...rankedState.current, blocking_game: blockingGame() };
    mockEndRanked.mockRejectedValue(new AiLadderApiError(404, 'not found'));
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '认输那一局，在这里开新局' }));
    await user.click(screen.getByRole('button', { name: '确认认输' }));

    await waitFor(() => expect(mockRetry).toHaveBeenCalledOnce());
    expect(screen.queryByText('结束对局失败，请重试')).not.toBeInTheDocument();
  });

  it.each([401, 403])('shows an expired-login message for lifecycle HTTP %s', async (status) => {
    const user = userEvent.setup();
    rankedState.current = { ...rankedState.current, blocking_game: blockingGame() };
    mockEndRanked.mockRejectedValue(new AiLadderApiError(status, 'operator detail'));
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '认输那一局，在这里开新局' }));
    await user.click(screen.getByRole('button', { name: '确认认输' }));

    expect(await screen.findByText('登录已失效，请重新登录后再试')).toBeInTheDocument();
    expect(screen.queryByText('operator detail')).not.toBeInTheDocument();
  });

  // ── 「立即重试」按下之后的每一条路 ──────────────────────────────────────────

  const syncingGame = (sync: Record<string, unknown>) => ({
    ...blockingGame('pending_settlement'),
    sync: {
      state: 'waiting', attempt: 2, max_attempts: 5, next_attempt_in_seconds: 252,
      last_http_status: null, last_error: null, ...sync,
    },
  });

  it('重试没送成时，绝不去打一次云端 —— 那正是这个按钮存在的场景', async () => {
    // `/status` 在盒子上是转发到云端的:断网即 503,而 `retry` 一失败就把整块面板换成
    // 「加载失败」。所以失败路径只贴 outbox 刚给的那份状态(它来自一次打到 127.0.0.1、
    // 确定收到过的响应),一步都不碰云端。
    const user = userEvent.setup();
    rankedState.current = { ...rankedState.current, blocking_game: syncingGame({}) };
    mockRetrySettlement.mockResolvedValue({
      game_id: 'occupied-game',
      sync: {
        state: 'waiting', attempt: 3, max_attempts: 5, next_attempt_in_seconds: 80,
        last_http_status: 503, last_error: 'HTTP 503', receipt: null,
      },
    });
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '立即重试' }));

    await waitFor(() => expect(mockApplyBlockingSync).toHaveBeenCalledWith(
      'occupied-game',
      expect.objectContaining({ state: 'waiting', attempt: 3, next_attempt_in_seconds: 80 }),
    ));
    expect(mockRetry).not.toHaveBeenCalled();
    expect(screen.queryByText('升降级对弈状态加载失败')).not.toBeInTheDocument();
  });

  it('被云端拒收也走同一条路:贴状态，不刷新', async () => {
    const user = userEvent.setup();
    rankedState.current = { ...rankedState.current, blocking_game: syncingGame({}) };
    mockRetrySettlement.mockResolvedValue({
      game_id: 'occupied-game',
      sync: {
        state: 'refused', attempt: 3, max_attempts: 5, next_attempt_in_seconds: null,
        last_http_status: 422, last_error: 'HTTP 422', receipt: null,
      },
    });
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '立即重试' }));

    await waitFor(() => expect(mockApplyBlockingSync).toHaveBeenCalledWith(
      'occupied-game', expect.objectContaining({ state: 'refused' }),
    ));
    expect(mockRetry).not.toHaveBeenCalled();
  });

  it('送成之后给出云端的裁决，而不是让面板悄悄消失', async () => {
    const user = userEvent.setup();
    rankedState.current = { ...rankedState.current, blocking_game: syncingGame({}) };
    mockRetrySettlement.mockResolvedValue({
      game_id: 'occupied-game',
      sync: {
        state: 'synced', attempt: 2, max_attempts: 5, next_attempt_in_seconds: null,
        last_http_status: 200, last_error: null,
        receipt: { counted: false, reason: 'opponent_not_eligible' },
      },
    });
    mockRetry.mockImplementation(() => {
      rankedState.current = { ...rankedState.current, blocking_game: null };
    });
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '立即重试' }));

    expect(await screen.findByText('结算已完成')).toBeInTheDocument();
    expect(screen.getByText('本局不计入升降级：本局对手尚未通过计分认证')).toBeInTheDocument();
    // 送成了才复查:那一刻网络刚被证明是通的,而且要换上新的段位。
    await waitFor(() => expect(mockRetry).toHaveBeenCalled());
    expect(mockApplyBlockingSync).not.toHaveBeenCalled();
  });

  it('送成了但拿不到回执:只刷新，不编一个结果出来', async () => {
    const user = userEvent.setup();
    rankedState.current = { ...rankedState.current, blocking_game: syncingGame({}) };
    mockRetrySettlement.mockResolvedValue({
      game_id: 'occupied-game',
      sync: {
        state: 'synced', attempt: 1, max_attempts: 5, next_attempt_in_seconds: null,
        last_http_status: 200, last_error: null, receipt: null,
      },
    });
    mockRetry.mockImplementation(() => {
      rankedState.current = { ...rankedState.current, blocking_game: null };
    });
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '立即重试' }));

    await waitFor(() => expect(mockRetry).toHaveBeenCalled());
    expect(screen.queryByText('结算已完成')).not.toBeInTheDocument();
  });

  it('云端会话过期时说清是登录问题，而不是留一句「正在送」', async () => {
    const user = userEvent.setup();
    rankedState.current = { ...rankedState.current, blocking_game: syncingGame({}) };
    mockRetrySettlement.mockRejectedValue(new AiLadderApiError(401, 'Cloud session needs to be renewed'));
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '立即重试' }));

    expect(await screen.findByText('登录已失效，请重新登录后再试')).toBeInTheDocument();
    expect(mockRetry).not.toHaveBeenCalled();
  });

  it('队列里已经没有这一局了(后台刚送成):这一条才去复查', async () => {
    const user = userEvent.setup();
    rankedState.current = { ...rankedState.current, blocking_game: syncingGame({}) };
    mockRetrySettlement.mockRejectedValue(new AiLadderApiError(404, 'No queued settlement for this game'));
    mockRetry.mockImplementation(() => {
      rankedState.current = { ...rankedState.current, blocking_game: null };
    });
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '立即重试' }));

    await waitFor(() => expect(mockRetry).toHaveBeenCalled());
    expect(screen.queryByText('重试失败，请稍后再试')).not.toBeInTheDocument();
  });

});


// --- 未登录（游客）---------------------------------------------------------------
//
// 自由对弈对游客开放，升降级对弈不开放 —— 后者要说清楚原因并给一个能按的入口，
// 而不是把服务端的 401 报文原样贴到屏上。

describe('AiSetupPage — 未登录访客', () => {
  const loggedIn = { token: 'test-token', user: { id: 1, username: 'test' }, isAuthenticated: true, isLoading: false };
  const guest = { token: null, user: null, isAuthenticated: false, isLoading: false };

  beforeEach(() => {
    mockNavigate.mockReset();
    mockCreateSession.mockClear();
    mockNewGame.mockClear();
    authState.current = guest;
  });

  afterEach(() => {
    authState.current = loggedIn;
    mockCreateSession.mockResolvedValue({ session_id: 's1', state: {} });
    mockNewGame.mockResolvedValue({ session_id: 's1', state: {} });
  });

  it('升降级对弈：说的是「需要登录」而不是「登录已失效」，并且当场能登录', async () => {
    renderPage('rated');
    expect(await screen.findByTestId('rated-login-required')).toHaveTextContent('需要登录');
    // 「重试」是给「加载失败」用的出口，对从未登录过的人按多少次都不会成功。
    expect(screen.queryByRole('button', { name: '重试' })).not.toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByTestId('rated-login-action'));
    // 断言的是「能当场填凭据的那个框」,不是「有个框」——换成再弹一次「需要登录」的
    // AuthRequiredDialog 也满足 findByRole('dialog'),而那样用户永远登不上去。
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getAllByRole('textbox').length).toBeGreaterThan(0);
    expect(dialog.querySelector('input[type="password"]')).not.toBeNull();
  });

  it('/me 探针还没回来时，既不说「需要登录」也不说「游客不保存」', async () => {
    // 挂载时 auth 是异步 bootstrap。不等它，已登录用户每次刷新都会先闪一下这两条。
    authState.current = { token: null, user: null, isAuthenticated: false, isLoading: true };
    renderPage('rated');
    await waitFor(() => expect(screen.queryByTestId('rated-login-required')).not.toBeInTheDocument());

    authState.current = { token: null, user: null, isAuthenticated: false, isLoading: true };
    renderPage('free');
    await waitFor(() => expect(screen.queryByTestId('free-guest-notice')).not.toBeInTheDocument());
  });

  it('自由对弈：已登录的人不该被告知本局不保存 —— 他的局会落库', async () => {
    authState.current = loggedIn;
    renderPage('free');
    await waitFor(() => expect(comboboxForLabel('AI Strategy')).toBeInTheDocument());
    expect(screen.queryByTestId('free-guest-notice')).not.toBeInTheDocument();
  });

  it('自由对弈：非鉴权失败仍然显示原始报错，不弹登录框', async () => {
    mockCreateSession.mockRejectedValueOnce(new ApiErrorReal(500, 'Request failed 500: boom'));
    renderPage('free');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Start Game' }));

    expect(await screen.findByText(/Request failed 500/)).toBeInTheDocument();
    expect(screen.queryByTestId('login-required-message')).not.toBeInTheDocument();
  });

  it('升降级：登录中途失效时点开始，弹的也是登录引导（AiLadderApiError 不是 ApiError 的子类）', async () => {
    // rated 走 `startAiLadderGame`，它抛的是 `AiLadderApiError extends Error`。
    // 判据只认 `instanceof ApiError` 时这一支是死代码：屏上会退回那串裸报文。
    authState.current = loggedIn;
    rankedState.current = {
      view_state: 'ready',
      placement_state: { phase: 'placement', completed_games: 3, total_games: 5 },
      current_opponent: { rung: 17, rank_name: '4级', certification_status: 'certified', availability: 'available', route: 'server' },
      recent_ranked_results: [], net_score: 0, pending_settlement: false,
    };
    mockStartRanked.mockRejectedValueOnce(new AiLadderApiError(401, 'Not authenticated'));
    renderPage('rated');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: '开始正式对局' }));

    expect(await screen.findByTestId('login-required-message')).toHaveTextContent('升降级对弈会记录段位');
  });

  it('升降级：引擎开局前就被判不可用时，说清「没开成、也没扣段位」', async () => {
    // 这条闸是新加的：从前局照开，第一手棋才弹「阶梯引擎不可用」，而那时定级名额已经
    // 押上去了。屏上只说「不可用」不够 —— 用户刚被坑过一次，必须明说这次没损失。
    authState.current = loggedIn;
    rankedState.current = {
      view_state: 'ready',
      placement_state: { phase: 'placement', completed_games: 0, total_games: 5 },
      current_opponent: { rung: 15, rank_name: '6级', certification_status: 'certified', availability: 'available', route: 'server' },
      recent_ranked_results: [], net_score: 0, pending_settlement: false,
    };
    mockStartRanked.mockRejectedValueOnce(
      new AiLadderApiError(503, 'Request failed 503: {"detail":"Ranked engine cannot serve the seated rung"}'),
    );
    renderPage('rated');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: '开始正式对局' }));

    expect(await screen.findByText(/本次没有开局/)).toBeInTheDocument();
    expect(screen.queryByText(/Ranked engine cannot serve/)).not.toBeInTheDocument();
    expect(screen.queryByTestId('login-required-message')).not.toBeInTheDocument();
  });

  it('已登录但有一局升降级没结算：说的是那件事，不是「需要登录」', async () => {
    authState.current = loggedIn;
    mockCreateSession.mockRejectedValueOnce(
      new ApiErrorReal(403, 'Request failed 403: {"detail":"session analysis is unavailable during a ranked AI game"}'),
    );
    renderPage('free');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Start Game' }));

    expect(await screen.findByText(/升降级对弈还没结算/)).toBeInTheDocument();
    expect(screen.queryByTestId('login-required-message')).not.toBeInTheDocument();
  });

  it('升降级对弈：给游客指出自由对弈这条不需要账号的路', async () => {
    renderPage('rated');
    const user = userEvent.setup();
    await user.click(await screen.findByTestId('rated-login-free-fallback'));
    expect(mockNavigate).toHaveBeenCalledWith('/galaxy/play/ai?mode=free');
  });

  it('自由对弈：让游客进，但开局前先说清楚这一局不会被保存', async () => {
    renderPage('free');
    expect(await screen.findByTestId('free-guest-notice')).toHaveTextContent('不会保存到棋谱库');
    expect(screen.queryByTestId('rated-login-required')).not.toBeInTheDocument();
  });

  it('自由对弈：万一服务端还是 401，弹的是登录引导，不是那串裸 JSON', async () => {
    mockCreateSession.mockRejectedValueOnce(
      new ApiErrorReal(401, 'Request failed 401: {"detail":"Not authenticated"}'),
    );
    renderPage('free');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Start Game' }));

    expect(await screen.findByTestId('login-required-message')).toBeInTheDocument();
    expect(screen.queryByText(/Request failed 401/)).not.toBeInTheDocument();
  });
});
