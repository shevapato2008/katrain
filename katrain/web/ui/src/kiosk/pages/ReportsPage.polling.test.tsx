import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ReportTaskSummary } from '../../api/reportApi';
import { kioskTheme } from '../theme';
import ReportsPage from './ReportsPage';

/**
 * 这一份**不 mock `useReportTasks`** —— 它跑的是真钩子,守的是「屏上那行状态跟得上后端」:
 * 乐观建任务先亮出来、两秒一轮、拿到终态就停。
 * 屏 19 的行只用一个状态标表达这一切,所以标错了这里就红。
 */

const mocks = vi.hoisted(() => ({
  reportList: vi.fn(), reportSummary: vi.fn(), reportCreate: vi.fn(), reportRetry: vi.fn(),
  reportMoves: vi.fn(), gameList: vi.fn(), gameGet: vi.fn(), baipuLoad: vi.fn(),
}));

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'token', isAuthenticated: true, user: { username: '阿福' } }),
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
      getMoves: mocks.reportMoves,
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
vi.mock('../../api/baipuApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/baipuApi')>();
  return { ...actual, BaipuAPI: { ...actual.BaipuAPI, load: mocks.baipuLoad } };
});

const game = {
  id: 'game-1', user_id: 1, title: '测试棋局', player_black: '阿福', player_white: 'KataGo',
  black_rank: null, white_rank: '6 级', result: 'B+R', board_size: 19, rules: 'chinese',
  komi: 7.5, move_count: 3, source: 'play_ai', category: 'game', game_type: 'free',
  event: null, round_name: null, game_date: '2026-07-15',
  created_at: '2026-07-15T15:12:00', updated_at: null,
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
  mocks.baipuLoad.mockResolvedValue({ board_size: 19, steps: [], meta: {} });
  mocks.reportMoves.mockResolvedValue([]);
  mocks.reportSummary.mockResolvedValue({ pending: 0, running: 0, completed: 0, failed: 0 });
  mocks.reportRetry.mockResolvedValue(task('pending', 0));
});

afterEach(() => vi.useRealTimers());

describe('屏 19 接真的报告任务钩子', () => {
  it('点「标准」立刻亮出排队中,服务端回来之后对齐成真任务', async () => {
    let resolveCreate!: (value: ReportTaskSummary) => void;
    mocks.reportList.mockResolvedValue([]);
    mocks.reportCreate.mockReturnValue(new Promise<ReportTaskSummary>((resolve) => { resolveCreate = resolve; }));
    renderPage();

    await waitFor(() => expect(screen.getByTestId('review-row')).toHaveAttribute('data-selected', 'true'));
    fireEvent.click(screen.getByRole('button', { name: /标准/ }));
    expect(await screen.findByText('正在分析 0/3')).toBeInTheDocument();
    expect(mocks.reportCreate).toHaveBeenCalledWith('token', { user_game_id: 'game-1', report_type: 'normal' });

    await act(async () => resolveCreate(task('running', 1, 41)));
    expect(await screen.findByText('正在分析 1/3')).toBeInTheDocument();
  });

  it('两秒一轮跟进度,拿到终态就停', async () => {
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
    expect(screen.getByText('正在分析 0/3')).toBeInTheDocument();
    expect(mocks.reportList).toHaveBeenCalledTimes(1);

    await act(async () => { await vi.advanceTimersByTimeAsync(1999); });
    expect(mocks.reportList).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(screen.getByText('正在分析 1/3')).toBeInTheDocument();
    expect(mocks.reportList).toHaveBeenCalledTimes(2);

    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    expect(screen.getByText('已分析')).toBeInTheDocument();
    expect(mocks.reportList).toHaveBeenCalledTimes(3);
    // 算完了才去读逐手 —— 没算完的时候读一份半截报告,画出来的曲线会短一截却看不出为什么。
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(mocks.reportMoves).toHaveBeenCalledWith('token', 1);

    await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
    expect(mocks.reportList).toHaveBeenCalledTimes(3);
  });
});
