import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import type { MatchDetail } from '../../types/live';

vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => ({ rotation: 0, setRotation: vi.fn() }),
}));

vi.mock('../context/ImmersiveContext', () => ({
  useImmersive: () => ({ immersive: false, setImmersive: vi.fn() }),
}));

vi.mock('../../hooks/live/useLiveMatch', () => ({
  useLiveMatch: vi.fn(),
}));

// Stub the sound hook so jsdom doesn't try to construct Audio.
vi.mock('../../hooks/useSound', () => ({
  useSound: () => ({ play: vi.fn() }),
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

function setMatch(over: Partial<ReturnType<typeof useLiveMatch>> = {}) {
  mockUseLiveMatch.mockReturnValue({
    match: mockMatch,
    loading: false,
    error: null,
    currentMove: 156,
    setCurrentMove: vi.fn(),
    analysis: {},
    refresh: vi.fn(),
    ...over,
  });
}

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

describe('LiveMatchPage (kiosk)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading spinner while fetching', () => {
    setMatch({ match: null, loading: true });
    renderPage();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('shows error message with back button on failure', () => {
    setMatch({ match: null, loading: false, error: new Error('Match not found') });
    renderPage();
    expect(screen.getByText('Match not found')).toBeInTheDocument();
    expect(screen.getByText('返回')).toBeInTheDocument();
  });

  it('renders tournament, players, and live status', () => {
    setMatch();
    renderPage();
    expect(screen.getByText(/LG杯决赛/)).toBeInTheDocument(); // MatchInfo (tournament · round)
    expect(screen.getAllByText(/柯洁/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/申真谞/).length).toBeGreaterThan(0);
    expect(screen.getByText('直播中')).toBeInTheDocument(); // header status chip
  });

  it('renders the board canvas', () => {
    setMatch();
    const { container } = renderPage();
    expect(container.querySelector('canvas')).toBeInTheDocument();
  });

  it('renders the four feature toggles', () => {
    setMatch();
    renderPage();
    expect(screen.getByText('试下')).toBeInTheDocument();
    expect(screen.getByText('形势')).toBeInTheDocument();
    expect(screen.getByText('手数')).toBeInTheDocument();
  });

  it('shows finished status chip for a finished match', () => {
    setMatch({ match: { ...mockMatch, status: 'finished', result: 'B+2.5' }, currentMove: 280 });
    renderPage();
    expect(screen.getByText('已结束')).toBeInTheDocument();
  });

  it('shows a back affordance when the match is null without an explicit error', () => {
    setMatch({ match: null, loading: false, error: null });
    renderPage();
    // Galaxy-aligned: null match renders the error block (not a blank page).
    expect(screen.getByText('返回')).toBeInTheDocument();
  });
});
