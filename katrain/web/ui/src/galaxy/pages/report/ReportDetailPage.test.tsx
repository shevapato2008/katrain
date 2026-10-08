import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { computeAccessibleName } from 'dom-accessibility-api';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { UseReportDetailResult } from '../../../features/report/useReportDetail';
// 迁统一版式后页头是 ModulePlate，它的返回键走 useGameNavigation()（无 Provider 直接 throw）。
// 用**真**的 Provider 而不是 stub —— 返回键的行为正是这一页要守的东西之一。
// 同一写法见 live/LiveMatchPage.test.tsx:6,67。
import { GameNavigationProvider } from '../../context/GameNavigationContext';

import ReportDetailPage from './ReportDetailPage';

const playSound = vi.hoisted(() => vi.fn());
const mockSetCurrentMove = vi.fn();
const mockDetailRefresh = vi.fn();
let reportDetailFixture: UseReportDetailResult;
const mockUseReportDetail = vi.fn((token?: unknown, taskId?: unknown) => {
  void token;
  void taskId;
  return reportDetailFixture;
});

vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => ({
    token: 'token',
    isAuthenticated: true,
    user: { id: 1, username: 'reporter' },
  }),
}));

vi.mock('../../../features/report/useReportDetail', () => ({
  useReportDetail: (...args: unknown[]) => mockUseReportDetail(...args),
}));

vi.mock('../../../hooks/useSound', () => ({
  useSound: () => ({ play: playSound }),
}));

vi.mock('../../../components/live/LiveBoard', () => ({
  default: () => <div data-testid="mock-live-board">Live Board</div>,
}));

vi.mock('../../../components/live/PlaybackBar', () => ({
  default: ({ currentMove, totalMoves, onMoveChange }: { currentMove: number; totalMoves: number; onMoveChange: (move: number) => void }) => (
    <div data-testid="mock-playback-bar">
      {currentMove}/{totalMoves}
      <button onClick={() => onMoveChange(1)}>Move 1</button>
    </div>
  ),
}));

vi.mock('../../../components/live/TrendChart', () => ({
  default: () => <div data-testid="mock-trend-chart">Trend Chart</div>,
}));

describe('ReportDetailPage', () => {
  beforeEach(() => {
    playSound.mockClear();
    mockSetCurrentMove.mockReset();
    mockDetailRefresh.mockReset();
    mockUseReportDetail.mockClear();
    mockDetailRefresh.mockResolvedValue(undefined);
    reportDetailFixture = {
      task: {
      id: 7,
      user_game_id: 'game-1',
      status: 'completed',
      report_type: 'normal',
      total_moves: 2,
      analyzed_moves: 2,
      requested_visits: 500,
      },
      game: {
        id: 'game-1', user_id: 1, title: 'Report Game', player_black: 'Black',
        player_white: 'White', result: null, board_size: 19, rules: 'chinese', komi: 7.5,
        move_count: 2, source: 'import', category: 'game', game_type: null, event: null,
        game_date: null, created_at: null, updated_at: null,
        sgf_content: '(;FF[4]SZ[19]PB[Black]PW[White];B[pd];W[dp])',
      },
      moves: [],
      analysisByMove: {
        1: {
        match_id: 'game-1', move_number: 1, move: 'Q16', player: 'B',
        winrate: 0.55,
        score_lead: 1.2,
        top_moves: [{ move: 'Q16', visits: 500, winrate: 0.56, score_lead: 1.5, prior: 0.2, pv: ['Q16'] }],
        ownership: undefined, is_brilliant: true, is_mistake: false, is_questionable: false,
        delta_score: 2.5, delta_winrate: 0.04,
      },
        2: {
        match_id: 'game-1', move_number: 2, move: 'D4', player: 'W',
        winrate: 0.48,
        score_lead: -1.7,
        top_moves: [{ move: 'D4', visits: 500, winrate: 0.5, score_lead: -0.5, prior: 0.3, pv: ['D4'] }],
        ownership: undefined, is_brilliant: false, is_mistake: true, is_questionable: true,
        delta_score: -3.4, delta_winrate: -0.07,
      },
      },
      currentMove: 2,
      setCurrentMove: mockSetCurrentMove,
      loading: false,
      error: null,
      refresh: mockDetailRefresh,
    };
  });

  it('keeps asynchronous first load silent, then sounds exactly once for a replay cursor change', () => {
    const loaded = reportDetailFixture;
    reportDetailFixture = { ...loaded, game: null, task: null, currentMove: 0, loading: true };
    const page = () => <MemoryRouter initialEntries={['/galaxy/report/7']}><GameNavigationProvider><Routes><Route path="/galaxy/report/:taskId" element={<ReportDetailPage />} /></Routes></GameNavigationProvider></MemoryRouter>;
    const view = render(page());
    reportDetailFixture = loaded;
    view.rerender(page());
    expect(playSound).not.toHaveBeenCalled();
    reportDetailFixture = { ...loaded, currentMove: 1 };
    view.rerender(page());
    expect(playSound).toHaveBeenCalledExactlyOnceWith('stone');
    view.rerender(page());
    expect(playSound).toHaveBeenCalledTimes(1);
  });

  /**
   * 早退形态里不许有没有名字的控件。
   *
   * 2026-08-22 全站控件账本量到：这一页正常数据下 14 控件 / 0 无名，但 task 不存在时
   * 进错误态，右栏那 4 个工具格占位 + 1 个动作占位都是 `<Button disabled><Skeleton/></Button>`,
   * 既没有可见文字也没有 `aria-label` —— 读屏用户会听到五个没有名字的按钮。
   * **错误态是真状态**，不是「测不到就不算」的边角。
   *
   * 判据落在**每个按钮都有可及名**上，不落在按钮个数上：数目断言对「换一种实现、
   * 仍然没有名字」免疫，而这一页的历史正是抄了直播页那份实现。可及名用
   * `dom-accessibility-api` 真算（testing-library 内部同一份），不用 textContent 近似。
   *
   * 两条各守一半，缺一不可：
   *   - 错误态那条守**槽位**（错误态不再挂 `displayControls`/`actions`）
   *   - 加载态那条守**占位实现**（占位不再做成 `<Button>`）
   * 只写错误态那条的话，把 `LoadingControls` 改回按钮实现它是绿的 —— 因为错误态
   * 已经不渲染它了，而加载态会。
   *
   * 变异记录（2026-08-22 实跑，见提交信息）：把本页对这两处的改动整体撤回 →
   * 加载态那条红（5 个无名），错误态那条红（5 个无名）。
   */
  it('leaves no unnamed control in the error state', async () => {
    reportDetailFixture = { ...reportDetailFixture, task: null, game: null, error: 'Report task not found' };

    render(
      <MemoryRouter initialEntries={['/galaxy/report/404']}><GameNavigationProvider>
        <Routes>
          <Route path="/galaxy/report/:taskId" element={<ReportDetailPage />} />
        </Routes>
      </GameNavigationProvider></MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Report task not found')).toBeInTheDocument();
    });

    const unnamed = screen
      .getAllByRole('button')
      .filter((el) => computeAccessibleName(el).trim() === '');
    expect(unnamed).toEqual([]);

    // 而且错误态根本不该画加载骨架 —— 脉动的骨架在说「东西还在路上」，这一屏已经失败了。
    expect(screen.queryByTestId('board-loading-skeleton')).not.toBeInTheDocument();
  });

  it('leaves no unnamed control while loading', async () => {
    reportDetailFixture = { ...reportDetailFixture, loading: true };

    render(
      <MemoryRouter initialEntries={['/galaxy/report/7']}><GameNavigationProvider>
        <Routes>
          <Route path="/galaxy/report/:taskId" element={<ReportDetailPage />} />
        </Routes>
      </GameNavigationProvider></MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('board-loading-skeleton')).toBeInTheDocument();
    });

    const unnamed = screen
      .getAllByRole('button')
      .filter((el) => computeAccessibleName(el).trim() === '');
    expect(unnamed).toEqual([]);
  });

  it('renders a live-aligned detail shell', async () => {
    render(
      <MemoryRouter initialEntries={['/galaxy/report/7']}><GameNavigationProvider>
        <Routes>
          <Route path="/galaxy/report/:taskId" element={<ReportDetailPage />} />
        </Routes>
      </GameNavigationProvider></MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Black')).toBeInTheDocument();
      expect(screen.getByText('White')).toBeInTheDocument();
    });

    expect(screen.getByTestId('mock-live-board')).toBeInTheDocument();
    expect(screen.getByTestId('mock-playback-bar')).toBeInTheDocument();
    expect(screen.getByTestId('mock-trend-chart')).toBeInTheDocument();
    expect(screen.getByText(/AI Recommendations/)).toBeInTheDocument();
    // 显示开关改成复用直播页那一组共享件（工具格），所以文案走的是 live:* 而不是
    // 原来手抄的 report:*。十个共享 key 在 11 种语言里都齐，不构成 i18n 回归。
    expect(screen.getByTestId('report-analysis-layout')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '试下' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Territory' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '手数' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '支招' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '坐标' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '3D' })).toBeInTheDocument();
    expect(screen.queryByText('报告摘要')).not.toBeInTheDocument();
    expect(screen.queryByText('精彩手')).not.toBeInTheDocument();
    expect(screen.queryByText('失误手')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '进入研究' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '重算' })).not.toBeInTheDocument();
    expect(mockUseReportDetail).toHaveBeenCalledWith('token', '7', true);
  });

  it('refreshes a progressive report while preserving a historical cursor', async () => {
    reportDetailFixture = {
      ...reportDetailFixture,
      task: { ...reportDetailFixture.task!, status: 'running', total_moves: 3 },
    };

    const { rerender } = render(
      <MemoryRouter initialEntries={['/galaxy/report/7']}><GameNavigationProvider>
        <Routes><Route path="/galaxy/report/:taskId" element={<ReportDetailPage />} /></Routes>
      </GameNavigationProvider></MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByTestId('mock-playback-bar')).toHaveTextContent('2/2'));
    fireEvent.click(screen.getByRole('button', { name: 'Move 1' }));
    expect(mockSetCurrentMove).toHaveBeenCalledWith(1);

    reportDetailFixture = {
      ...reportDetailFixture,
      task: { ...reportDetailFixture.task!, analyzed_moves: 3 },
      currentMove: 1,
    };
    rerender(
      <MemoryRouter initialEntries={['/galaxy/report/7']}><GameNavigationProvider>
        <Routes><Route path="/galaxy/report/:taskId" element={<ReportDetailPage />} /></Routes>
      </GameNavigationProvider></MemoryRouter>,
    );
    expect(screen.getByTestId('mock-playback-bar')).toHaveTextContent('1/2');
    expect(mockDetailRefresh).not.toHaveBeenCalled();
  });
});
