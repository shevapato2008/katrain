import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import type { MatchSummary } from '../../types/live';

vi.mock('../../hooks/live/useLiveMatches', () => ({
  useLiveMatches: vi.fn(),
}));

import { useLiveMatches } from '../../hooks/live/useLiveMatches';
import LivePage from '../pages/LivePage';

const mockUseLiveMatches = useLiveMatches as ReturnType<typeof vi.fn>;

const mockMatches: MatchSummary[] = [
  {
    id: 'live-1',
    source: 'xingzhen',
    tournament: '春兰杯半决赛',
    round_name: null,
    date: '2025-06-01',
    player_black: '柯洁 九段',
    player_white: '朴廷桓 九段',
    black_rank: '九段',
    white_rank: '九段',
    status: 'live',
    result: null,
    move_count: 127,
    current_winrate: 0.55,
    current_score: 2.3,
    last_updated: '2025-06-01T12:00:00Z',
    board_size: 19,
    komi: 7.5,
    rules: 'chinese',
  },
  {
    id: 'live-2',
    source: 'weiqi_org',
    tournament: '应氏杯',
    round_name: '四分之一决赛',
    date: '2025-06-01',
    player_black: '申真谞 九段',
    player_white: '芝野虎丸 九段',
    black_rank: '九段',
    white_rank: '九段',
    status: 'finished',
    result: 'B+R',
    move_count: 211,
    current_winrate: 0.85,
    current_score: 12.5,
    last_updated: '2025-06-01T14:00:00Z',
    board_size: 19,
    komi: 7.5,
    rules: 'chinese',
  },
];

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter>
        <LivePage />
      </MemoryRouter>
    </ThemeProvider>
  );

describe('LivePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading spinner while fetching', () => {
    mockUseLiveMatches.mockReturnValue({
      matches: [],
      liveCount: 0,
      total: 0,
      loading: true,
      error: null,
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('shows error message on failure', () => {
    mockUseLiveMatches.mockReturnValue({
      matches: [],
      liveCount: 0,
      total: 0,
      loading: false,
      error: new Error('Network error'),
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.getByText('Network error')).toBeInTheDocument();
  });

  it('shows empty state when no matches', () => {
    mockUseLiveMatches.mockReturnValue({
      matches: [],
      liveCount: 0,
      total: 0,
      loading: false,
      error: null,
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.getByText('暂无直播')).toBeInTheDocument();
  });

  it('renders match list with player names and tournaments', () => {
    mockUseLiveMatches.mockReturnValue({
      matches: mockMatches,
      liveCount: 1,
      total: 2,
      loading: false,
      error: null,
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.getByRole('heading', { name: /直播/i })).toBeInTheDocument();
    expect(screen.getByText(/柯洁/)).toBeInTheDocument();
    expect(screen.getByText(/朴廷桓/)).toBeInTheDocument();
    expect(screen.getByText(/春兰杯/)).toBeInTheDocument();
    expect(screen.getByText(/申真谞/)).toBeInTheDocument();
  });

  it('shows live count when there are live matches', () => {
    mockUseLiveMatches.mockReturnValue({
      matches: mockMatches,
      liveCount: 1,
      total: 2,
      loading: false,
      error: null,
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.getByText('1 场正在直播')).toBeInTheDocument();
  });

  it('shows move count for live matches and status chips', () => {
    mockUseLiveMatches.mockReturnValue({
      matches: mockMatches,
      liveCount: 1,
      total: 2,
      loading: false,
      error: null,
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.getByText('第127手')).toBeInTheDocument();
    expect(screen.getByText('直播中')).toBeInTheDocument();
    expect(screen.getByText('已结束')).toBeInTheDocument();
  });
});
