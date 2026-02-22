import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import type { MatchDetail } from '../../types/live';

vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => ({ rotation: 0, isPortrait: false, setRotation: vi.fn() }),
}));

vi.mock('../../hooks/live/useLiveMatch', () => ({
  useLiveMatch: vi.fn(),
}));

import { useLiveMatch } from '../../hooks/live/useLiveMatch';
import LiveMatchPage from '../pages/LiveMatchPage';

const mockUseLiveMatch = useLiveMatch as ReturnType<typeof vi.fn>;

const mockMatch: MatchDetail = {
  id: 'match-1',
  source: 'xingzhen',
  tournament: 'LG杯决赛',
  round_name: '第一局',
  date: '2025-06-15',
  player_black: '柯洁',
  player_white: '申真谞',
  black_rank: '九段',
  white_rank: '九段',
  status: 'live',
  result: null,
  move_count: 156,
  current_winrate: 0.62,
  current_score: 3.8,
  last_updated: '2025-06-15T10:00:00Z',
  board_size: 19,
  komi: 7.5,
  rules: 'chinese',
  sgf: null,
  moves: [],
};

const renderPage = (matchId = 'match-1') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[`/kiosk/live/${matchId}`]}>
        <Routes>
          <Route path="/kiosk/live/:matchId" element={<LiveMatchPage />} />
          <Route path="/kiosk/live" element={<div>LIVE_LIST</div>} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('LiveMatchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading spinner while fetching', () => {
    mockUseLiveMatch.mockReturnValue({
      match: null,
      loading: true,
      error: null,
      currentMove: 0,
      setCurrentMove: vi.fn(),
      analysis: {},
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('shows error message with back button on failure', () => {
    mockUseLiveMatch.mockReturnValue({
      match: null,
      loading: false,
      error: new Error('Match not found'),
      currentMove: 0,
      setCurrentMove: vi.fn(),
      analysis: {},
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.getByText('Match not found')).toBeInTheDocument();
    expect(screen.getByText('返回')).toBeInTheDocument();
  });

  it('renders match details with player names and tournament', () => {
    mockUseLiveMatch.mockReturnValue({
      match: mockMatch,
      loading: false,
      error: null,
      currentMove: 156,
      setCurrentMove: vi.fn(),
      analysis: {},
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.getByText('LG杯决赛')).toBeInTheDocument();
    expect(screen.getByText(/柯洁/)).toBeInTheDocument();
    expect(screen.getByText(/申真谞/)).toBeInTheDocument();
    expect(screen.getByText('直播中')).toBeInTheDocument();
  });

  it('shows current move and total moves', () => {
    mockUseLiveMatch.mockReturnValue({
      match: mockMatch,
      loading: false,
      error: null,
      currentMove: 100,
      setCurrentMove: vi.fn(),
      analysis: {},
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.getByText('第100手 / 156手')).toBeInTheDocument();
  });

  it('shows result when match is finished', () => {
    const finishedMatch: MatchDetail = {
      ...mockMatch,
      status: 'finished',
      result: 'B+2.5',
    };
    mockUseLiveMatch.mockReturnValue({
      match: finishedMatch,
      loading: false,
      error: null,
      currentMove: 280,
      setCurrentMove: vi.fn(),
      analysis: {},
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.getByText('已结束')).toBeInTheDocument();
    expect(screen.getByText('结果: B+2.5')).toBeInTheDocument();
  });

  it('renders board canvas', () => {
    mockUseLiveMatch.mockReturnValue({
      match: mockMatch,
      loading: false,
      error: null,
      currentMove: 156,
      setCurrentMove: vi.fn(),
      analysis: {},
      refresh: vi.fn(),
    });
    const { container } = renderPage();
    expect(container.querySelector('canvas')).toBeInTheDocument();
  });

  it('shows player ranks when available', () => {
    mockUseLiveMatch.mockReturnValue({
      match: mockMatch,
      loading: false,
      error: null,
      currentMove: 156,
      setCurrentMove: vi.fn(),
      analysis: {},
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.getByText(/\(九段\)/)).toBeInTheDocument();
  });

  it('returns null when match is null and not loading/error', () => {
    mockUseLiveMatch.mockReturnValue({
      match: null,
      loading: false,
      error: null,
      currentMove: 0,
      setCurrentMove: vi.fn(),
      analysis: {},
      refresh: vi.fn(),
    });
    const { container } = renderPage();
    // Should render essentially nothing (just the router container)
    expect(container.querySelector('.MuiBox-root')).toBeNull();
  });
});
