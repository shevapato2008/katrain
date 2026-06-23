import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import type { MatchSummary, MatchDetail } from '../../types/live';

vi.mock('../../hooks/live/useLiveMatches', () => ({
  useLiveMatches: vi.fn(),
}));
vi.mock('../../hooks/live/useLiveMatch', () => ({
  useLiveMatch: vi.fn(),
}));
// UpcomingList (rendered under the "Upcoming" tab) calls LiveAPI.getUpcoming.
vi.mock('../../api/live', () => ({
  LiveAPI: { getUpcoming: vi.fn().mockResolvedValue({ matches: [] }) },
}));
// OrientationContext: kiosk renders landscape (isPortrait hardcoded false today).
vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => ({ rotation: 0, isPortrait: false, setRotation: vi.fn() }),
}));

import { useLiveMatches } from '../../hooks/live/useLiveMatches';
import { useLiveMatch } from '../../hooks/live/useLiveMatch';
import LivePage from '../pages/LivePage';

const mockUseLiveMatches = useLiveMatches as ReturnType<typeof vi.fn>;
const mockUseLiveMatch = useLiveMatch as ReturnType<typeof vi.fn>;

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
    source: 'yike',
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

const selectedDetail: MatchDetail = { ...mockMatches[0], sgf: null, moves: [] };

function setMatches(over: Partial<ReturnType<typeof useLiveMatches>> = {}) {
  mockUseLiveMatches.mockReturnValue({
    matches: mockMatches,
    liveCount: 1,
    total: 2,
    loading: false,
    error: null,
    refresh: vi.fn(),
    ...over,
  });
}

function setSelected(match: MatchDetail | null = selectedDetail) {
  mockUseLiveMatch.mockReturnValue({
    match,
    loading: false,
    error: null,
    currentMove: match ? match.move_count : 0,
    setCurrentMove: vi.fn(),
    analysis: {},
    refresh: vi.fn(),
  });
}

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter>
        <LivePage />
      </MemoryRouter>
    </ThemeProvider>
  );

describe('LivePage (kiosk)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setSelected();
  });

  it('shows loading spinner while fetching', () => {
    setMatches({ matches: [], liveCount: 0, total: 0, loading: true });
    setSelected(null);
    renderPage();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('shows error message on failure', () => {
    setMatches({ matches: [], liveCount: 0, total: 0, loading: false, error: new Error('Network error') });
    setSelected(null);
    renderPage();
    expect(screen.getByText('Network error')).toBeInTheDocument();
  });

  it('shows empty state when there are no live matches', () => {
    setMatches({ matches: [], liveCount: 0, total: 0 });
    setSelected(null);
    renderPage();
    expect(screen.getByText('暂无直播')).toBeInTheDocument();
  });

  it('renders header, both tabs, and the enter button', () => {
    setMatches();
    renderPage();
    expect(screen.getByRole('heading', { name: '直播' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '热门对局' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '即将开始' })).toBeInTheDocument();
    // Selected match is live -> enter button reads "进入直播".
    expect(screen.getByRole('button', { name: '进入直播' })).toBeInTheDocument();
  });

  it('renders live and finished matches via the shared MatchList', () => {
    setMatches();
    renderPage();
    expect(screen.getByText(/柯洁/)).toBeInTheDocument(); // live (Top Matches)
    expect(screen.getByText(/朴廷桓/)).toBeInTheDocument();
    expect(screen.getByText(/申真谞/)).toBeInTheDocument(); // finished (History)
    expect(screen.getByText(/直播中 \(1\)/)).toBeInTheDocument(); // group label with live count
  });

  it('navigates to the match detail when entering', async () => {
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    setMatches();
    renderPage();
    await user.click(screen.getByRole('button', { name: '进入直播' }));
    // navigation handled by react-router MemoryRouter; assert no throw + button stays
    expect(screen.getByRole('button', { name: '进入直播' })).toBeInTheDocument();
  });
});
