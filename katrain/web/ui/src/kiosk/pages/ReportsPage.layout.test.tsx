import { render, screen, waitFor } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { kioskTheme } from '../theme';
import ReportsPage from './ReportsPage';

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'token', isAuthenticated: true }),
}));
vi.mock('../../features/report/useReportTasks', () => ({
  useReportTasks: () => ({
    tasks: [], queueSummary: null, reportStatesByGame: {}, loading: false, error: null,
    clearError: vi.fn(), refresh: vi.fn().mockResolvedValue(undefined),
    createReport: vi.fn(), retryReport: vi.fn(),
  }),
}));
vi.mock('../../api/userGamesApi', () => ({
  UserGamesAPI: {
    list: vi.fn().mockResolvedValue({
      items: [{
        id: 'compact', user_id: 1, title: '紧凑棋盘', player_black: '黑', player_white: '白',
        black_rank: null, white_rank: null, result: null, board_size: 19, rules: 'chinese',
        komi: 7.5, move_count: 1, source: 'import', category: 'game', game_type: null,
        event: null, round_name: null, game_date: null, created_at: null, updated_at: null,
      }], total: 1, page: 1, page_size: 12,
    }),
    get: vi.fn().mockResolvedValue({
      id: 'compact', user_id: 1, title: '紧凑棋盘', player_black: '黑', player_white: '白',
      black_rank: null, white_rank: null, result: null, board_size: 19, rules: 'chinese',
      komi: 7.5, move_count: 1, source: 'import', category: 'game', game_type: null,
      event: null, round_name: null, game_date: null, created_at: null, updated_at: null,
      sgf_content: '(;SZ[19];B[aa])',
    }),
    create: vi.fn(), delete: vi.fn(),
  },
}));

describe('ReportsPage real LiveBoard layout at the 1024×600 kiosk viewport', () => {
  it('removes the 400px board floor and reserves playback inside the 464px content shell', async () => {
    render(
      <ThemeProvider theme={kioskTheme}>
        <MemoryRouter>
          <div data-testid="kiosk-content-viewport" style={{ width: 1024, height: 464, overflow: 'hidden' }}>
            <ReportsPage />
          </div>
        </MemoryRouter>
      </ThemeProvider>,
    );

    const page = screen.getByTestId('report-list-page');
    const boardRegion = screen.getByTestId('report-preview-region');
    const playback = screen.getByTestId('report-playback');
    const canvas = await waitFor(() => {
      const found = page.querySelector('canvas');
      expect(found).not.toBeNull();
      return found!;
    });
    const liveBoardContainer = canvas.parentElement!;

    expect(screen.getByTestId('kiosk-content-viewport')).toHaveStyle({ width: '1024px', height: '464px', overflow: 'hidden' });
    expect(page).toHaveStyle({ height: '100%', overflow: 'hidden' });
    expect(boardRegion).toHaveStyle({ flex: '1', minHeight: '0', overflow: 'hidden' });
    expect(playback).toHaveStyle({ flexShrink: '0' });
    expect(liveBoardContainer).toHaveStyle({ minHeight: '0', width: '100%', height: '100%' });
    expect(canvas).toHaveStyle({ maxWidth: '100%', maxHeight: '100%' });
  });
});
