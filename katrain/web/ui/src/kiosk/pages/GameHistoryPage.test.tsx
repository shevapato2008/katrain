import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ token: 'tok' }) }));
const { list, get } = vi.hoisted(() => ({
  list: vi.fn().mockResolvedValue({ items: [
    { id: 'g1', source: 'play_local', player_black: '小明', player_white: '小红', result: 'B+3.5', move_count: 180, board_size: 19, game_type: 'pvp_local', game_date: '2026-07-12', created_at: '2026-07-12T10:00:00Z' },
  ], total: 1, page: 1, page_size: 20 }),
  get: vi.fn().mockResolvedValue({ id: 'g1', sgf_content: '(;GM[1])', player_black: '小明', player_white: '小红', result: 'B+3.5', move_count: 180, board_size: 19, komi: 7.5, rules: 'chinese', source: 'play_local', game_type: 'pvp_local', game_date: '2026-07-12', created_at: '2026-07-12T10:00:00Z' }),
}));
vi.mock('../../api/userGamesApi', () => ({ UserGamesAPI: { list, get } }));

import GameHistoryPage from './GameHistoryPage';

beforeEach(() => vi.clearAllMocks());
const renderPage = () =>
  render(<ThemeProvider theme={kioskTheme}><MemoryRouter><GameHistoryPage /></MemoryRouter></ThemeProvider>);

describe('GameHistoryPage', () => {
  it('lists local games and 复盘 navigates to research with user_game_id', async () => {
    renderPage();
    await waitFor(() => expect(list).toHaveBeenCalledWith('tok', expect.objectContaining({ source: 'play_local' })));
    await screen.findByText('小明');
    await userEvent.click(screen.getByText('小明'));
    await waitFor(() => expect(get).toHaveBeenCalledWith('tok', 'g1'));
    await userEvent.click(screen.getByRole('button', { name: /复盘|Review/ }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/research?user_game_id=g1&analyze=1');
  });
});
