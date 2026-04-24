import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ReportsPage from './ReportsPage';

const mockUserGamesList = vi.fn();
const mockUserGamesGet = vi.fn();
const mockUserGamesCreate = vi.fn();
const mockUserGamesDelete = vi.fn();
const mockReportsList = vi.fn();
const mockReportsCreate = vi.fn();
const mockReportsRetry = vi.fn();
const mockReportsSummary = vi.fn();
const mockKifuGetAlbums = vi.fn();
const mockKifuGetAlbum = vi.fn();

vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => ({
    token: 'token',
    isAuthenticated: true,
    user: { id: 1, username: 'reporter' },
  }),
}));

vi.mock('../../api/userGamesApi', () => ({
  UserGamesAPI: {
    list: (...args: unknown[]) => mockUserGamesList(...args),
    get: (...args: unknown[]) => mockUserGamesGet(...args),
    create: (...args: unknown[]) => mockUserGamesCreate(...args),
    delete: (...args: unknown[]) => mockUserGamesDelete(...args),
  },
}));

vi.mock('../../api/reportApi', () => ({
  ReportsAPI: {
    list: (...args: unknown[]) => mockReportsList(...args),
    create: (...args: unknown[]) => mockReportsCreate(...args),
    retry: (...args: unknown[]) => mockReportsRetry(...args),
    summary: (...args: unknown[]) => mockReportsSummary(...args),
  },
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

vi.mock('../../components/live/PlaybackBar', () => ({
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

describe('ReportsPage', () => {
  beforeEach(() => {
    mockUserGamesList.mockReset();
    mockUserGamesGet.mockReset();
    mockUserGamesCreate.mockReset();
    mockUserGamesDelete.mockReset();
    mockReportsList.mockReset();
    mockReportsCreate.mockReset();
    mockReportsRetry.mockReset();
    mockReportsSummary.mockReset();
    mockKifuGetAlbums.mockReset();
    mockKifuGetAlbum.mockReset();

    mockUserGamesList.mockResolvedValue({
      items: [gameSummary],
      total: 1,
      page: 1,
      page_size: 12,
    });
    mockUserGamesGet.mockResolvedValue(gameDetail);
    mockReportsList.mockResolvedValue([]);
    mockReportsSummary.mockResolvedValue({ pending: 0, running: 0, completed: 0, failed: 0 });
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
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
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
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
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
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
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
    mockReportsCreate.mockResolvedValue({
      id: 11,
      user_game_id: 'game-2',
      status: 'pending',
      report_type: 'normal',
      total_moves: 2,
      analyzed_moves: 0,
      requested_visits: 500,
    });

    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
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
      expect(mockReportsCreate).toHaveBeenCalledTimes(1);
    });

    expect(mockReportsCreate).toHaveBeenCalledWith('token', {
      user_game_id: 'game-2',
      report_type: 'normal',
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
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
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

  it('keeps polling active report tasks so progress updates without refresh', async () => {
    vi.useFakeTimers();
    mockReportsList
      .mockResolvedValueOnce([
        {
          id: 11,
          user_game_id: 'game-1',
          status: 'running',
          report_type: 'normal',
          total_moves: 2,
          analyzed_moves: 0,
          requested_visits: 500,
        },
      ])
      .mockResolvedValueOnce([
        {
          id: 11,
          user_game_id: 'game-1',
          status: 'running',
          report_type: 'normal',
          total_moves: 2,
          analyzed_moves: 1,
          requested_visits: 500,
        },
      ])
      .mockResolvedValueOnce([
        {
          id: 11,
          user_game_id: 'game-1',
          status: 'running',
          report_type: 'normal',
          total_moves: 2,
          analyzed_moves: 2,
          requested_visits: 500,
        },
      ]);

    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    );

    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText('0/2')).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2100);
    });

    expect(screen.getByText('1/2')).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2100);
    });

    expect(screen.getByText('2/2')).toBeInTheDocument();
  });

  it('does not show a completed badge when the same report type is still running', async () => {
    mockReportsList.mockResolvedValue([
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
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Normal Generating')).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: 'Normal' })).not.toBeInTheDocument();
  });

  it('shows pending wording when a report is queued behind concurrency limit', async () => {
    mockReportsList.mockResolvedValue([
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
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
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
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
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
  });

  it('shows retry button for failed tasks and retries on click', async () => {
    mockReportsList.mockResolvedValue([
      {
        id: 15,
        user_game_id: 'game-1',
        status: 'failed',
        report_type: 'normal',
        total_moves: 2,
        analyzed_moves: 1,
        requested_visits: 500,
      },
    ]);
    mockReportsSummary.mockResolvedValue({ pending: 0, running: 0, completed: 0, failed: 1 });
    mockReportsRetry.mockResolvedValue({
      id: 15,
      user_game_id: 'game-1',
      status: 'pending',
      report_type: 'normal',
      total_moves: 2,
      analyzed_moves: 1,
      requested_visits: 500,
    });

    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Retry normal' })).toBeInTheDocument();
    });

    expect(screen.getByText('1 failed')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Retry normal' }));

    await waitFor(() => {
      expect(mockReportsRetry).toHaveBeenCalledWith('token', 15);
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
    mockReportsList.mockResolvedValue([
      { id: 20, user_game_id: 'game-1', status: 'running', report_type: 'normal', total_moves: 10, analyzed_moves: 5, requested_visits: 500 },
      { id: 21, user_game_id: 'game-2', status: 'pending', report_type: 'deep', total_moves: 0, analyzed_moves: 0, requested_visits: 2000 },
      { id: 22, user_game_id: 'game-3', status: 'failed', report_type: 'normal', total_moves: 8, analyzed_moves: 3, requested_visits: 500 },
      { id: 23, user_game_id: 'game-3', status: 'completed', report_type: 'deep', total_moves: 8, analyzed_moves: 8, requested_visits: 2000 },
    ]);
    mockReportsSummary.mockResolvedValue({ pending: 1, running: 1, completed: 1, failed: 1 });

    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
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
});
