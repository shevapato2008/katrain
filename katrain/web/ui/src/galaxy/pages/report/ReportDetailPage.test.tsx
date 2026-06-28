import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ReportDetailPage from './ReportDetailPage';

const mockReportsGet = vi.fn();
const mockReportsGetMoves = vi.fn();
const mockUserGamesGet = vi.fn();

vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => ({
    token: 'token',
    isAuthenticated: true,
    user: { id: 1, username: 'reporter' },
  }),
}));

vi.mock('../../api/reportApi', () => ({
  ReportsAPI: {
    get: (...args: unknown[]) => mockReportsGet(...args),
    getMoves: (...args: unknown[]) => mockReportsGetMoves(...args),
  },
}));

vi.mock('../../api/userGamesApi', () => ({
  UserGamesAPI: {
    get: (...args: unknown[]) => mockUserGamesGet(...args),
  },
}));

vi.mock('../../../hooks/useSound', () => ({
  useSound: () => ({ play: vi.fn() }),
}));

vi.mock('../../../components/live/LiveBoard', () => ({
  default: () => <div data-testid="mock-live-board">Live Board</div>,
}));

vi.mock('../../../components/live/PlaybackBar', () => ({
  default: ({ currentMove, totalMoves }: { currentMove: number; totalMoves: number }) => (
    <div data-testid="mock-playback-bar">{currentMove}/{totalMoves}</div>
  ),
}));

vi.mock('../../../components/live/TrendChart', () => ({
  default: () => <div data-testid="mock-trend-chart">Trend Chart</div>,
}));

describe('ReportDetailPage', () => {
  beforeEach(() => {
    mockReportsGet.mockReset();
    mockReportsGetMoves.mockReset();
    mockUserGamesGet.mockReset();

    mockReportsGet.mockResolvedValue({
      id: 7,
      user_game_id: 'game-1',
      status: 'completed',
      report_type: 'normal',
      total_moves: 2,
      analyzed_moves: 2,
      requested_visits: 500,
    });
    mockReportsGetMoves.mockResolvedValue([
      {
        id: 1,
        task_id: 7,
        move_number: 1,
        status: 'success',
        winrate: 0.55,
        score_lead: 1.2,
        visits: 500,
        top_moves: [{ move: 'Q16', visits: 500, winrate: 0.56, score_lead: 1.5, prior: 0.2, pv: ['Q16'] }],
        ownership: null,
        actual_move: 'Q16',
        actual_player: 'B',
        delta_score: 2.5,
        delta_winrate: 0.04,
      },
      {
        id: 2,
        task_id: 7,
        move_number: 2,
        status: 'success',
        winrate: 0.48,
        score_lead: -1.7,
        visits: 500,
        top_moves: [{ move: 'D4', visits: 500, winrate: 0.5, score_lead: -0.5, prior: 0.3, pv: ['D4'] }],
        ownership: null,
        actual_move: 'D4',
        actual_player: 'W',
        delta_score: -3.4,
        delta_winrate: -0.07,
      },
    ]);
    mockUserGamesGet.mockResolvedValue({
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
      sgf_content: '(;FF[4]SZ[19]PB[Black]PW[White];B[pd];W[dp])',
    });
  });

  it('renders a live-aligned detail shell', async () => {
    render(
      <MemoryRouter initialEntries={['/galaxy/report/7']}>
        <Routes>
          <Route path="/galaxy/report/:taskId" element={<ReportDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Black vs White')).toBeInTheDocument();
    });

    expect(screen.getByTestId('mock-live-board')).toBeInTheDocument();
    expect(screen.getByTestId('mock-playback-bar')).toBeInTheDocument();
    expect(screen.getByTestId('mock-trend-chart')).toBeInTheDocument();
    expect(screen.getByText('AI Recommendations')).toBeInTheDocument();
    expect(screen.getByText('Try')).toBeInTheDocument();
    expect(screen.queryByText('报告摘要')).not.toBeInTheDocument();
    expect(screen.queryByText('精彩手')).not.toBeInTheDocument();
    expect(screen.queryByText('失误手')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open in Research' })).toBeInTheDocument();
  });
});
