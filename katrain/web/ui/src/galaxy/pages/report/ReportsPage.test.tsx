import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { GameNavigationProvider } from '../../context/GameNavigationContext';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ReportQueueSummary, ReportTaskSummary } from '../../../api/reportApi';
import { buildReportStatesByGame } from '../../../features/report/reportModel';

import ReportsPage from './ReportsPage';

const mockUserGamesList = vi.fn();
const mockUserGamesGet = vi.fn();
const mockUserGamesCreate = vi.fn();
const mockUserGamesDelete = vi.fn();
const mockCreateReport = vi.fn();
const mockRetryReport = vi.fn();
const mockTaskRefresh = vi.fn();
const mockClearTaskError = vi.fn();
const mockKifuGetAlbums = vi.fn();
const mockKifuGetAlbum = vi.fn();

vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => ({
    token: 'token',
    isAuthenticated: true,
    user: { id: 1, username: 'reporter' },
  }),
}));

vi.mock('../../../api/userGamesApi', () => ({
  UserGamesAPI: {
    list: (...args: unknown[]) => mockUserGamesList(...args),
    get: (...args: unknown[]) => mockUserGamesGet(...args),
    create: (...args: unknown[]) => mockUserGamesCreate(...args),
    delete: (...args: unknown[]) => mockUserGamesDelete(...args),
  },
}));

let reportTasksFixture: {
  tasks: ReportTaskSummary[];
  queueSummary: ReportQueueSummary | null;
  reportStatesByGame: ReturnType<typeof buildReportStatesByGame>;
  loading: boolean;
  error: string | null;
};

function setReportTasks(tasks: ReportTaskSummary[], queueSummary: ReportQueueSummary | null = null) {
  reportTasksFixture = {
    tasks,
    queueSummary,
    reportStatesByGame: buildReportStatesByGame(tasks),
    loading: false,
    error: null,
  };
}

vi.mock('../../../features/report/useReportTasks', () => ({
  useReportTasks: () => ({
    ...reportTasksFixture,
    createReport: mockCreateReport,
    retryReport: mockRetryReport,
    refresh: mockTaskRefresh,
    clearError: mockClearTaskError,
  }),
}));

vi.mock('../../../api/kifuApi', () => ({
  KifuAPI: {
    getAlbums: (...args: unknown[]) => mockKifuGetAlbums(...args),
    getAlbum: (...args: unknown[]) => mockKifuGetAlbum(...args),
  },
}));

vi.mock('../../../components/live/LiveBoard', () => ({
  default: () => <div data-testid="mock-live-board">Live Board</div>,
}));

vi.mock('../../../components/live/PlaybackBar', () => ({
  default: () => <div data-testid="mock-playback-bar">Playback Bar</div>,
}));

const gameSummary = {
  id: 'game-1',
  user_id: 1,
  title: 'Report Game',
  player_black: 'Black',
  player_white: 'White',
  result: null,
  board_size: 19,
  rules: 'chinese',
  komi: 7.5,
  move_count: 2,
  source: 'import',
  category: 'game',
  game_type: null,
  event: null,
  game_date: null,
  created_at: null,
  updated_at: null,
};

const gameDetail = {
  ...gameSummary,
  sgf_content: '(;FF[4]SZ[19]PB[Black]PW[White];B[pd];W[dp])',
};

// 页头改用共享的 `ContentPageHeader`（spec §2.4：左上角箭头图标键 + 标题），它经由
// `ModulePlate` 读 `GameNavigationContext`。生产里 provider 挂在 `MainLayout` 上、
// 覆盖全部 galaxy 路由，所以这里补的是**测试的装配**，不是生产缺口。
describe('ReportsPage', () => {
  beforeEach(() => {
    mockUserGamesList.mockReset();
    mockUserGamesGet.mockReset();
    mockUserGamesCreate.mockReset();
    mockUserGamesDelete.mockReset();
    mockCreateReport.mockReset();
    mockRetryReport.mockReset();
    mockTaskRefresh.mockReset();
    mockClearTaskError.mockReset();
    mockKifuGetAlbums.mockReset();
    mockKifuGetAlbum.mockReset();

    mockUserGamesList.mockResolvedValue({
      items: [gameSummary],
      total: 1,
      page: 1,
      page_size: 12,
    });
    mockUserGamesGet.mockResolvedValue(gameDetail);
    setReportTasks([], { pending: 0, running: 0, completed: 0, failed: 0 });
    mockCreateReport.mockResolvedValue(undefined);
    mockRetryReport.mockResolvedValue(undefined);
    mockTaskRefresh.mockResolvedValue(undefined);
    mockKifuGetAlbums.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 10,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders report list and preview shell', async () => {
    render(
      <MemoryRouter><GameNavigationProvider>
        <ReportsPage />
      </GameNavigationProvider></MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Review')).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByTestId('mock-live-board')).toBeInTheDocument();
    });

    expect(screen.getAllByText('Report Game').length).toBeGreaterThan(0);
    expect(screen.getByTestId('mock-playback-bar')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Import game' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Generate report' })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Search by player, title, or event')).toBeInTheDocument();
  });

  it('opens local import dialog from the import menu', async () => {
    render(
      <MemoryRouter><GameNavigationProvider>
        <ReportsPage />
      </GameNavigationProvider></MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Import game' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Import game' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Import local SGF' }));

    expect(screen.getByRole('dialog', { name: 'Import local SGF' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Import only' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Import & generate normal report' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Import & generate deep report' })).toBeInTheDocument();
  });

  it('opens report-type menu from a game card', async () => {
    render(
      <MemoryRouter><GameNavigationProvider>
        <ReportsPage />
      </GameNavigationProvider></MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Generate report' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Generate report' }));

    expect(screen.getByRole('menuitem', { name: 'Normal' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Deep' })).toBeInTheDocument();
  });

  it('imports sgf and immediately creates a normal report', async () => {
    mockUserGamesCreate.mockResolvedValue({
      ...gameDetail,
      id: 'game-2',
      title: 'Imported Game',
    });
    mockCreateReport.mockResolvedValue({
      id: 11,
      user_game_id: 'game-2',
      status: 'pending',
      report_type: 'normal',
      total_moves: 2,
      analyzed_moves: 0,
      requested_visits: 500,
    });

    render(
      <MemoryRouter><GameNavigationProvider>
        <ReportsPage />
      </GameNavigationProvider></MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Import game' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Import game' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Import local SGF' }));
    fireEvent.change(screen.getByLabelText('Title'), {
      target: { value: 'Imported Game' },
    });
    fireEvent.change(screen.getByLabelText('SGF Content'), {
      target: { value: '(;FF[4]SZ[19]PB[Black]PW[White];B[pd];W[dp])' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Import & generate normal report' }));

    await waitFor(() => {
      expect(mockUserGamesCreate).toHaveBeenCalledTimes(1);
      expect(mockCreateReport).toHaveBeenCalledTimes(1);
    });

    expect(mockCreateReport).toHaveBeenCalledWith({
      userGameId: 'game-2',
      reportType: 'normal',
      totalMoves: 2,
    });
  });

  it('imports a game from the kifu library', async () => {
    mockKifuGetAlbums.mockResolvedValue({
      items: [
        {
          id: 9,
          player_black: 'Alpha',
          player_white: 'Beta',
          black_rank: null,
          white_rank: null,
          event: 'Library Cup',
          result: 'B+R',
          rules: 'chinese',
          date_played: '2026-04-10',
          komi: 7.5,
          handicap: 0,
          board_size: 19,
          round_name: null,
          move_count: 2,
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    });
    mockKifuGetAlbum.mockResolvedValue({
      id: 9,
      player_black: 'Alpha',
      player_white: 'Beta',
      black_rank: null,
      white_rank: null,
      event: 'Library Cup',
      result: 'B+R',
      rules: 'chinese',
      date_played: '2026-04-10',
      komi: 7.5,
      handicap: 0,
      board_size: 19,
      round_name: null,
      move_count: 2,
      place: null,
      source: 'library',
      sgf_content: '(;FF[4]SZ[19]PB[Alpha]PW[Beta];B[pd];W[dp])',
    });
    mockUserGamesCreate.mockResolvedValue({
      ...gameDetail,
      id: 'game-3',
      title: 'Library Cup',
      player_black: 'Alpha',
      player_white: 'Beta',
      event: 'Library Cup',
      game_date: '2026-04-10',
      sgf_content: '(;FF[4]SZ[19]PB[Alpha]PW[Beta];B[pd];W[dp])',
    });

    render(
      <MemoryRouter><GameNavigationProvider>
        <ReportsPage />
      </GameNavigationProvider></MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Import game' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Import game' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Import from library' }));

    await waitFor(() => {
      expect(screen.getByText('Library Cup')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Import only' }));

    await waitFor(() => {
      expect(mockKifuGetAlbum).toHaveBeenCalledWith(9);
      expect(mockUserGamesCreate).toHaveBeenCalledTimes(1);
    });

    expect(mockUserGamesCreate).toHaveBeenCalledWith('token', expect.objectContaining({
      source: 'kifu_library',
      event: 'Library Cup',
      player_black: 'Alpha',
      player_white: 'Beta',
    }));
  });

  it('renders progressive task snapshots supplied by the shared hook', async () => {
    const runningTask: ReportTaskSummary = {
      id: 11,
      user_game_id: 'game-1',
      status: 'running',
      report_type: 'normal',
      total_moves: 2,
      analyzed_moves: 0,
      requested_visits: 500,
    };
    setReportTasks([runningTask]);

    const { rerender } = render(
      <MemoryRouter><GameNavigationProvider>
        <ReportsPage />
      </GameNavigationProvider></MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('0/2')).toBeInTheDocument());

    setReportTasks([{ ...runningTask, analyzed_moves: 1 }]);
    rerender(<MemoryRouter><GameNavigationProvider><ReportsPage /></GameNavigationProvider></MemoryRouter>);
    expect(screen.getByText('1/2')).toBeInTheDocument();

    setReportTasks([{ ...runningTask, analyzed_moves: 2 }]);
    rerender(<MemoryRouter><GameNavigationProvider><ReportsPage /></GameNavigationProvider></MemoryRouter>);
    expect(screen.getByText('2/2')).toBeInTheDocument();
  });

  it('does not show a completed badge when the same report type is still running', async () => {
    setReportTasks([
      {
        id: 7,
        user_game_id: 'game-1',
        status: 'completed',
        report_type: 'normal',
        total_moves: 2,
        analyzed_moves: 2,
        requested_visits: 500,
      },
      {
        id: 8,
        user_game_id: 'game-1',
        status: 'running',
        report_type: 'normal',
        total_moves: 2,
        analyzed_moves: 1,
        requested_visits: 500,
      },
    ]);

    render(
      <MemoryRouter><GameNavigationProvider>
        <ReportsPage />
      </GameNavigationProvider></MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Normal Generating')).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: 'Normal' })).not.toBeInTheDocument();
  });

  it('shows pending wording when a report is queued behind concurrency limit', async () => {
    setReportTasks([
      {
        id: 9,
        user_game_id: 'game-1',
        status: 'pending',
        report_type: 'deep',
        total_moves: 0,
        analyzed_moves: 0,
        requested_visits: 2000,
      },
    ]);

    render(
      <MemoryRouter><GameNavigationProvider>
        <ReportsPage />
      </GameNavigationProvider></MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Deep Queued')).toBeInTheDocument();
    });

    expect(screen.queryByText('Deep Generating')).not.toBeInTheDocument();
    expect(screen.getByText('0/2')).toBeInTheDocument();
  });

  it('deletes a game after confirmation and refreshes the list', async () => {
    mockUserGamesDelete.mockResolvedValue({ status: 'ok' });

    render(
      <MemoryRouter><GameNavigationProvider>
        <ReportsPage />
      </GameNavigationProvider></MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Delete game' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Delete game' }));

    expect(screen.getByText('Confirm deletion')).toBeInTheDocument();
    expect(screen.getByText('This will permanently delete the game and all associated analysis data. Are you sure?')).toBeInTheDocument();

    const callsBefore = mockUserGamesList.mock.calls.length;

    mockUserGamesList.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 12,
    });

    fireEvent.click(screen.getByRole('button', { name: 'Delete game' }));

    await waitFor(() => {
      expect(mockUserGamesDelete).toHaveBeenCalledWith('token', 'game-1');
    });

    await waitFor(() => {
      expect(mockUserGamesList.mock.calls.length).toBeGreaterThan(callsBefore);
    });
    expect(mockTaskRefresh).toHaveBeenCalled();
  });

  it('shows retry button for failed tasks and retries on click', async () => {
    setReportTasks([
      {
        id: 15,
        user_game_id: 'game-1',
        status: 'failed',
        report_type: 'normal',
        total_moves: 2,
        analyzed_moves: 1,
        requested_visits: 500,
      },
    ], { pending: 0, running: 0, completed: 0, failed: 1 });

    render(
      <MemoryRouter><GameNavigationProvider>
        <ReportsPage />
      </GameNavigationProvider></MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Retry normal' })).toBeInTheDocument();
    });

    expect(screen.getByText('1 failed')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Retry normal' }));

    await waitFor(() => {
      expect(mockRetryReport).toHaveBeenCalledWith(15);
    });
  });

  it('displays queue summary chips and multiple task states simultaneously', async () => {
    const game2 = { ...gameSummary, id: 'game-2', title: 'Game Two' };
    const game3 = { ...gameSummary, id: 'game-3', title: 'Game Three' };
    mockUserGamesList.mockResolvedValue({
      items: [gameSummary, game2, game3],
      total: 3,
      page: 1,
      page_size: 12,
    });
    setReportTasks([
      { id: 20, user_game_id: 'game-1', status: 'running', report_type: 'normal', total_moves: 10, analyzed_moves: 5, requested_visits: 500 },
      { id: 21, user_game_id: 'game-2', status: 'pending', report_type: 'deep', total_moves: 0, analyzed_moves: 0, requested_visits: 2000 },
      { id: 22, user_game_id: 'game-3', status: 'failed', report_type: 'normal', total_moves: 8, analyzed_moves: 3, requested_visits: 500 },
      { id: 23, user_game_id: 'game-3', status: 'completed', report_type: 'deep', total_moves: 8, analyzed_moves: 8, requested_visits: 2000 },
    ], { pending: 1, running: 1, completed: 1, failed: 1 });

    render(
      <MemoryRouter><GameNavigationProvider>
        <ReportsPage />
      </GameNavigationProvider></MemoryRouter>,
    );

    // Queue summary chips
    await waitFor(() => {
      expect(screen.getByText('1 running')).toBeInTheDocument();
    });
    expect(screen.getByText('1 queued')).toBeInTheDocument();
    expect(screen.getByText('1 failed')).toBeInTheDocument();

    // Game 1: running progress
    expect(screen.getByText('Normal Generating')).toBeInTheDocument();
    expect(screen.getByText('5/10')).toBeInTheDocument();

    // Game 2: pending
    expect(screen.getByText('Deep Queued')).toBeInTheDocument();

    // Game 3: failed normal + completed deep
    expect(screen.getByRole('button', { name: 'Retry normal' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Deep' })).toBeInTheDocument();
  });

  it('reads search and pagination from the URL and preserves search while paging', async () => {
    mockUserGamesList.mockResolvedValue({ items: [gameSummary], total: 25, page: 2, page_size: 12 });

    render(
      <MemoryRouter initialEntries={['/galaxy/report?q=Alpha&page=2']}><GameNavigationProvider>
        <ReportsPage />
      </GameNavigationProvider></MemoryRouter>,
    );

    await waitFor(() => {
      expect(mockUserGamesList).toHaveBeenCalledWith('token', expect.objectContaining({
        page: 2,
        q: 'Alpha',
      }));
    });
    expect(screen.getByPlaceholderText('Search by player, title, or event')).toHaveValue('Alpha');

    fireEvent.click(screen.getByRole('button', { name: 'Go to page 3' }));
    await waitFor(() => {
      expect(mockUserGamesList).toHaveBeenCalledWith('token', expect.objectContaining({
        page: 3,
        q: 'Alpha',
      }));
    });
  });

  it('creates a deep report with the selected game adapter arguments', async () => {
    render(<MemoryRouter><GameNavigationProvider><ReportsPage /></GameNavigationProvider></MemoryRouter>);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Generate report' })).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Generate report' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Deep' }));
    await waitFor(() => expect(mockCreateReport).toHaveBeenCalledWith({
      userGameId: 'game-1', reportType: 'deep', totalMoves: 2,
    }));
  });

  it('removes a create failure alert when the shared hook recovers', async () => {
    mockCreateReport.mockRejectedValue(new Error('Create failed'));
    const { rerender } = render(<MemoryRouter><GameNavigationProvider><ReportsPage /></GameNavigationProvider></MemoryRouter>);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Generate report' })).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Generate report' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Normal' }));
    await waitFor(() => expect(mockCreateReport).toHaveBeenCalled());

    reportTasksFixture = { ...reportTasksFixture, error: 'Create failed' };
    rerender(<MemoryRouter><GameNavigationProvider><ReportsPage /></GameNavigationProvider></MemoryRouter>);
    expect(screen.getByText('Create failed')).toBeInTheDocument();

    reportTasksFixture = { ...reportTasksFixture, error: null };
    rerender(<MemoryRouter><GameNavigationProvider><ReportsPage /></GameNavigationProvider></MemoryRouter>);
    expect(screen.queryByText('Create failed')).not.toBeInTheDocument();
  });

  it('shows an optimistic queued report until creation reconciles with the server task', async () => {
    const { rerender } = render(<MemoryRouter><GameNavigationProvider><ReportsPage /></GameNavigationProvider></MemoryRouter>);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Generate report' })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Generate report' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Normal' }));

    expect(mockCreateReport).toHaveBeenCalledWith({
      userGameId: 'game-1', reportType: 'normal', totalMoves: 2,
    });
    setReportTasks([{
      id: -1, user_game_id: 'game-1', status: 'pending', report_type: 'normal',
      total_moves: 2, analyzed_moves: 0, requested_visits: 500,
    }]);
    rerender(<MemoryRouter><GameNavigationProvider><ReportsPage /></GameNavigationProvider></MemoryRouter>);
    expect(screen.getByText('Normal Queued')).toBeInTheDocument();

    setReportTasks([{
      id: 41, user_game_id: 'game-1', status: 'running', report_type: 'normal',
      total_moves: 2, analyzed_moves: 1, requested_visits: 500,
    }]);
    rerender(<MemoryRouter><GameNavigationProvider><ReportsPage /></GameNavigationProvider></MemoryRouter>);
    expect(screen.getByText('Normal Generating')).toBeInTheDocument();
  });

  it('surfaces a delete rejection and keeps the game visible', async () => {
    mockUserGamesDelete.mockRejectedValue(new Error('Delete denied'));
    render(<MemoryRouter><GameNavigationProvider><ReportsPage /></GameNavigationProvider></MemoryRouter>);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Delete game' })).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Delete game' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete game' }));

    expect(await screen.findByText('Delete denied')).toBeInTheDocument();
    expect(screen.getAllByText('Report Game').length).toBeGreaterThan(0);
  });

  it('dismisses shared hook errors through the supported hook boundary', async () => {
    reportTasksFixture = { ...reportTasksFixture, error: 'Task service unavailable' };
    render(<MemoryRouter><GameNavigationProvider><ReportsPage /></GameNavigationProvider></MemoryRouter>);

    expect(await screen.findByText('Task service unavailable')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));

    expect(mockClearTaskError).toHaveBeenCalledTimes(1);
  });

  it('removes a retry failure alert when the shared hook recovers', async () => {
    setReportTasks([{
      id: 15, user_game_id: 'game-1', status: 'failed', report_type: 'normal',
      total_moves: 2, analyzed_moves: 1, requested_visits: 500,
    }]);
    mockRetryReport.mockRejectedValue(new Error('Retry failed'));
    const { rerender } = render(<MemoryRouter><GameNavigationProvider><ReportsPage /></GameNavigationProvider></MemoryRouter>);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Retry normal' })).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Retry normal' }));
    await waitFor(() => expect(mockRetryReport).toHaveBeenCalledWith(15));

    reportTasksFixture = { ...reportTasksFixture, error: 'Retry failed' };
    rerender(<MemoryRouter><GameNavigationProvider><ReportsPage /></GameNavigationProvider></MemoryRouter>);
    expect(screen.getByText('Retry failed')).toBeInTheDocument();

    reportTasksFixture = { ...reportTasksFixture, error: null };
    rerender(<MemoryRouter><GameNavigationProvider><ReportsPage /></GameNavigationProvider></MemoryRouter>);
    expect(screen.queryByText('Retry failed')).not.toBeInTheDocument();
  });
});
