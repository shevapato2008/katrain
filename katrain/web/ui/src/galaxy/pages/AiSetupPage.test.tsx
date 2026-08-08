import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import AiSetupPage from './AiSetupPage';
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

const { mockAiConstants, mockRungsResponse, mockCreateSession, mockNewGame, mockUpdateConfig, mockStartRanked, mockEndRanked, rankedState, authState, mockRetry } = vi.hoisted(() => ({
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
    rungs: [
      { rung: 18, rank_name: '3K' },
      { rung: 37, rank_name: 'KataGo中等' },
    ],
  },
  mockCreateSession: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
  mockNewGame: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
  mockUpdateConfig: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
  mockStartRanked: vi.fn().mockResolvedValue({ session_id: 'ranked-s1', game_id: 'g1' }),
  mockEndRanked: vi.fn(),
  mockRetry: vi.fn(),
  rankedState: { current: null as any },
  authState: { current: { token: 'test-token', user: { id: 1, username: 'test' }, isAuthenticated: true } as any },
}));

vi.mock('../../api', () => ({
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
  return { ...actual, startAiLadderGame: mockStartRanked, endAiLadderGame: mockEndRanked };
});
vi.mock('../../features/aiLadder/useAiLadderStatus', () => ({
  useAiLadderStatus: () => ({ status: rankedState.current, retry: mockRetry }),
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
  state: 'active' | 'pending_settlement' = 'active',
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
    mockEndRanked.mockReset();
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
    expect(mockNavigate).toHaveBeenCalledWith('/galaxy/play/game/ranked-s1?mode=rated');
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
    expect(mockNavigate).toHaveBeenCalledWith('/galaxy/play/game/occupied-session?mode=rated');
  });

  it.each([
    ['等待结算', blockingGame('active', 'other_device')],
    ['刷新状态', blockingGame('pending_settlement')],
  ])('uses ranked-status retry for %s', async (buttonName, occupiedGame) => {
    const user = userEvent.setup();
    rankedState.current = { ...rankedState.current, blocking_game: occupiedGame };
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: buttonName }));

    expect(mockRetry).toHaveBeenCalledOnce();
  });

  it('ends a confirmed occupied game through the authenticated lifecycle API', async () => {
    const user = userEvent.setup();
    rankedState.current = { ...rankedState.current, blocking_game: blockingGame() };
    mockEndRanked.mockResolvedValue({ state: 'pending_settlement', game_id: 'occupied-game' });
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '结束该对局' }));
    await user.click(screen.getByRole('button', { name: '确认结束' }));

    await waitFor(() => expect(mockEndRanked).toHaveBeenCalledWith('occupied-game', 'test-token'));
  });

  it('refreshes ranked status when ending enters pending settlement', async () => {
    const user = userEvent.setup();
    rankedState.current = { ...rankedState.current, blocking_game: blockingGame() };
    mockEndRanked.mockResolvedValue({ state: 'pending_settlement', game_id: 'occupied-game' });
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '结束该对局' }));
    await user.click(screen.getByRole('button', { name: '确认结束' }));

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

    await user.click(await screen.findByRole('button', { name: '结束该对局' }));
    await user.click(screen.getByRole('button', { name: '确认结束' }));

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

    await user.click(await screen.findByRole('button', { name: '结束该对局' }));
    await user.click(screen.getByRole('button', { name: '确认结束' }));

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

    await user.click(await screen.findByRole('button', { name: '结束该对局' }));
    await user.click(screen.getByRole('button', { name: '确认结束' }));
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

    await user.click(await screen.findByRole('button', { name: '结束该对局' }));
    await user.click(screen.getByRole('button', { name: '确认结束' }));
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

  it('clears a lifecycle error before refreshing into pending settlement', async () => {
    const user = userEvent.setup();
    rankedState.current = {
      ...rankedState.current,
      blocking_game: blockingGame('active', 'other_device'),
    };
    mockEndRanked.mockRejectedValue(new Error('gateway exploded'));
    mockRetry.mockImplementation(() => {
      rankedState.current = {
        ...rankedState.current,
        blocking_game: blockingGame('pending_settlement', 'other_device'),
      };
    });
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '结束该对局' }));
    await user.click(screen.getByRole('button', { name: '确认结束' }));
    expect(await screen.findByText('结束对局失败，请重试')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());

    await user.click(screen.getByRole('button', { name: '等待结算' }));

    await waitFor(() => expect(screen.getByRole('button', { name: '刷新状态' })).toBeInTheDocument());
    expect(screen.queryByText('结束对局失败，请重试')).not.toBeInTheDocument();
    expect(mockRetry).toHaveBeenCalledOnce();
  });

  it('refreshes status without a stale error when the occupied game already vanished', async () => {
    const user = userEvent.setup();
    rankedState.current = { ...rankedState.current, blocking_game: blockingGame() };
    mockEndRanked.mockRejectedValue(new AiLadderApiError(404, 'not found'));
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '结束该对局' }));
    await user.click(screen.getByRole('button', { name: '确认结束' }));

    await waitFor(() => expect(mockRetry).toHaveBeenCalledOnce());
    expect(screen.queryByText('结束对局失败，请重试')).not.toBeInTheDocument();
  });

  it.each([401, 403])('shows an expired-login message for lifecycle HTTP %s', async (status) => {
    const user = userEvent.setup();
    rankedState.current = { ...rankedState.current, blocking_game: blockingGame() };
    mockEndRanked.mockRejectedValue(new AiLadderApiError(status, 'operator detail'));
    renderPage('rated');

    await user.click(await screen.findByRole('button', { name: '结束该对局' }));
    await user.click(screen.getByRole('button', { name: '确认结束' }));

    expect(await screen.findByText('登录已失效，请重新登录后再试')).toBeInTheDocument();
    expect(screen.queryByText('operator detail')).not.toBeInTheDocument();
  });
});
