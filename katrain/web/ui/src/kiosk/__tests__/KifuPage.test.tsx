import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import KifuPage from '../pages/KifuPage';

const mockAlbums = [
  {
    id: 1, player_black: '柯洁', player_white: '申真谞',
    black_rank: '九段', white_rank: '九段',
    event: '2024 LG杯决赛', result: 'W+R', move_count: 211,
    date_played: '2024-12-15', board_size: 19, handicap: 0,
    komi: 6.5, rules: 'chinese', round_name: null,
  },
  {
    id: 2, player_black: '张三', player_white: 'KataGo',
    black_rank: '2D', white_rank: '5D',
    event: '自由对弈', result: 'W+12.5', move_count: 184,
    date_played: '2025-01-05', board_size: 19, handicap: 0,
    komi: 6.5, rules: 'chinese', round_name: null,
  },
];

const mockResponse = { items: mockAlbums, total: 2, page: 1, page_size: 20 };

beforeEach(() => {
  vi.restoreAllMocks();
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(mockResponse),
  }) as any;
});

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter>
        <KifuPage />
      </MemoryRouter>
    </ThemeProvider>
  );

describe('KifuPage', () => {
  it('renders the title "棋谱库"', () => {
    renderPage();
    expect(screen.getByText('棋谱库')).toBeInTheDocument();
  });

  it('renders the search box', () => {
    renderPage();
    expect(screen.getByPlaceholderText('搜索棋手、赛事...')).toBeInTheDocument();
  });

  it('shows loading spinner initially', () => {
    renderPage();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('fetches and renders kifu cards with player names and events', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('柯洁')).toBeInTheDocument();
      expect(screen.getByText('申真谞')).toBeInTheDocument();
      expect(screen.getByText('张三')).toBeInTheDocument();
      expect(screen.getByText(/LG杯/)).toBeInTheDocument();
    });
  });

  it('renders ResultBadge for each kifu', async () => {
    renderPage();
    await waitFor(() => {
      const badges = screen.getAllByTestId('result-badge');
      expect(badges.length).toBe(2);
    });
  });

  it('shows total count from API response', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('2 局')).toBeInTheDocument();
    });
  });

  it('shows preview area with navigation when a card is selected', async () => {
    renderPage();
    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('柯洁')).toBeInTheDocument();
    });

    // Initially shows placeholder
    expect(screen.getByText('选择一局棋谱预览')).toBeInTheDocument();

    // Click first card
    fireEvent.click(screen.getByText('柯洁'));

    // Placeholder gone
    expect(screen.queryByText('选择一局棋谱预览')).not.toBeInTheDocument();
    // Navigation controls and "在研究中打开" button appear
    expect(screen.getByTestId('kifu-preview-nav')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /在研究中打开/ })).toBeInTheDocument();
  });

  it('shows error message on fetch failure', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 500,
      text: () => Promise.resolve('Internal Server Error'),
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Request failed 500/)).toBeInTheDocument();
    });
  });
});
