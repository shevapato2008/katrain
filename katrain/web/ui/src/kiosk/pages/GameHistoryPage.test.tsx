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
    // `&from=history`:研究屏靠它才知道返回键该回对局历史(见屏 21 页头注)
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/research?user_game_id=g1&analyze=1&from=history');
  });

  it('切换到 全部 re-queries the list without the play_local source filter', async () => {
    renderPage();
    await waitFor(() => expect(list).toHaveBeenCalledWith('tok', expect.objectContaining({ source: 'play_local' })));

    await userEvent.click(screen.getByText('全部'));

    await waitFor(() => expect(list).toHaveBeenCalledTimes(2));
    const secondCallArgs = list.mock.calls[1][1];
    expect(secondCallArgs).not.toHaveProperty('source');
  });

  it('switching selection before the first detail fetch resolves keeps the later pick (no stale overwrite)', async () => {
    let resolveFirst: (v: unknown) => void = () => {};
    const firstDetail = { id: 'g1', sgf_content: '(;GM[1])', result: 'B+3.5', rules: 'chinese' };
    const secondDetail = { id: 'g2', sgf_content: '(;GM[1])', result: 'W+5.5', rules: 'chinese' };
    list.mockResolvedValueOnce({
      items: [
        { id: 'g1', source: 'play_local', player_black: '小明', player_white: '小红', result: 'B+3.5', move_count: 180, board_size: 19, game_type: 'pvp_local', game_date: '2026-07-12', created_at: '2026-07-12T10:00:00Z' },
        { id: 'g2', source: 'play_local', player_black: '小刚', player_white: '小美', result: 'W+5.5', move_count: 120, board_size: 19, game_type: 'pvp_local', game_date: '2026-07-11', created_at: '2026-07-11T10:00:00Z' },
      ], total: 2, page: 1, page_size: 20,
    });
    get.mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }));
    get.mockResolvedValueOnce(secondDetail);

    renderPage();
    await screen.findByText('小明');
    await userEvent.click(screen.getByText('小明'));
    await userEvent.click(screen.getByText('小刚'));
    await waitFor(() => expect(get).toHaveBeenCalledWith('tok', 'g2'));
    // secondDetail resolves promptly (mockResolvedValueOnce); wait for the Review
    // button to enable, which only happens once `detail` is populated.
    const reviewButton = await screen.findByRole('button', { name: /复盘|Review/ });
    await waitFor(() => expect(reviewButton).toBeEnabled());

    // Stale first fetch resolves AFTER the second selection was made — its cleanup
    // should have already flipped `cancelled`, so this must NOT clobber `detail`.
    resolveFirst(firstDetail);
    await Promise.resolve();
    await Promise.resolve();

    await userEvent.click(reviewButton);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/research?user_game_id=g2&analyze=1&from=history');
  });
});
