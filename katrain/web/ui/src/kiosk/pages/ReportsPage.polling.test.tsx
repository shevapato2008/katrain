import { act, fireEvent, render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ReportTaskSummary } from '../../api/reportApi';
import { kioskTheme } from '../theme';
import ReportsPage from './ReportsPage';

const mocks = vi.hoisted(() => ({
  reportList: vi.fn(), reportSummary: vi.fn(), reportCreate: vi.fn(), reportRetry: vi.fn(),
  gameList: vi.fn(), gameGet: vi.fn(),
}));

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'token', isAuthenticated: true }),
}));
vi.mock('../../api/reportApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/reportApi')>();
  return {
    ...actual,
    ReportsAPI: {
      ...actual.ReportsAPI,
      list: mocks.reportList,
      summary: mocks.reportSummary,
      create: mocks.reportCreate,
      retry: mocks.reportRetry,
    },
  };
});
vi.mock('../../api/userGamesApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/userGamesApi')>();
  return {
    ...actual,
    UserGamesAPI: {
      ...actual.UserGamesAPI,
      list: mocks.gameList,
      get: mocks.gameGet,
      create: vi.fn(),
      delete: vi.fn(),
    },
  };
});
vi.mock('../../components/live/LiveBoard', () => ({ default: () => <div data-testid="live-board" /> }));

const game = {
  id: 'game-1', user_id: 1, title: '测试棋局', player_black: '黑方', player_white: '白方',
  black_rank: null, white_rank: null, result: 'B+R', board_size: 19, rules: 'chinese',
  komi: 7.5, move_count: 3, source: 'import', category: 'game', game_type: null,
  event: '轮询测试', round_name: null, game_date: '2026-07-15', created_at: '2026-07-15', updated_at: null,
};
const task = (status: ReportTaskSummary['status'], analyzedMoves: number, id = 1): ReportTaskSummary => ({
  id, user_game_id: game.id, status, report_type: 'normal', total_moves: 3,
  analyzed_moves: analyzedMoves, requested_visits: 500,
});

function renderPage() {
  return render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter><ReportsPage /></MemoryRouter>
    </ThemeProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.gameList.mockResolvedValue({ items: [game], total: 1, page: 1, page_size: 12 });
  mocks.gameGet.mockResolvedValue({ ...game, sgf_content: '(;SZ[19];B[aa];W[bb];B[cc])' });
  mocks.reportSummary.mockResolvedValue({ pending: 0, running: 0, completed: 0, failed: 0 });
  mocks.reportRetry.mockResolvedValue(task('pending', 0));
});

afterEach(() => vi.useRealTimers());

describe('ReportsPage with the real report task hook', () => {
  it('renders optimistic creation immediately and reconciles it to the returned server task', async () => {
    let resolveCreate!: (value: ReportTaskSummary) => void;
    mocks.reportList.mockResolvedValue([]);
    mocks.reportCreate.mockReturnValue(new Promise<ReportTaskSummary>((resolve) => { resolveCreate = resolve; }));
    renderPage();

    await screen.findByRole('button', { name: /选择棋局.*轮询测试/ });
    fireEvent.click(screen.getByRole('button', { name: '更多复盘操作' }));
    fireEvent.click(screen.getByRole('menuitem', { name: '生成普通复盘' }));
    expect(await screen.findByText('普通复盘 · 排队中')).toBeInTheDocument();
    expect(mocks.reportCreate).toHaveBeenCalledWith('token', { user_game_id: 'game-1', report_type: 'normal' });

    await act(async () => resolveCreate(task('running', 1, 41)));
    expect(await screen.findByText('普通复盘 · 生成中')).toBeInTheDocument();
    expect(screen.getByText('1 / 3 手')).toBeInTheDocument();
  });

  it('polls active progress every two seconds and stops after the terminal snapshot', async () => {
    vi.useFakeTimers();
    mocks.reportList
      .mockResolvedValueOnce([task('pending', 0)])
      .mockResolvedValueOnce([task('running', 1)])
      .mockResolvedValueOnce([task('completed', 3)]);
    mocks.reportSummary
      .mockResolvedValueOnce({ pending: 1, running: 0, completed: 0, failed: 0 })
      .mockResolvedValueOnce({ pending: 0, running: 1, completed: 0, failed: 0 })
      .mockResolvedValueOnce({ pending: 0, running: 0, completed: 1, failed: 0 });
    renderPage();

    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.getByText('普通复盘 · 排队中')).toBeInTheDocument();
    expect(mocks.reportList).toHaveBeenCalledTimes(1);

    await act(async () => { await vi.advanceTimersByTimeAsync(1999); });
    expect(mocks.reportList).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(screen.getByText('普通复盘 · 生成中')).toBeInTheDocument();
    expect(screen.getByText('1 / 3 手')).toBeInTheDocument();
    expect(mocks.reportList).toHaveBeenCalledTimes(2);

    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    expect(screen.getByText('普通复盘 · 已完成')).toBeInTheDocument();
    expect(mocks.reportList).toHaveBeenCalledTimes(3);
    await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
    expect(mocks.reportList).toHaveBeenCalledTimes(3);
  });
});
