import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import MatchCard from '../../../components/live/MatchCard';
import type { MatchSummary } from '../../../types/live';

const match: MatchSummary = {
  id: 'match-42', source: 'yike', tournament: 'Galaxy Cup', round_name: null,
  date: '2026-11-01T12:00:00Z', player_black: 'Alpha', player_white: 'Beta',
  black_rank: null, white_rank: null, status: 'live', result: null, move_count: 42,
  current_winrate: 0.5, current_score: 0, last_updated: '2026-11-01T12:01:00Z',
  board_size: 19, komi: 7.5, rules: 'chinese',
};

function CurrentLocation() {
  const location = useLocation();
  return <output data-testid="current-location">{location.pathname}</output>;
}

it.each([false, true])('opens a match at the root live route without an onSelect callback (compact=%s)', (compact) => {
  render(<MemoryRouter initialEntries={['/live']}>
    <MatchCard match={match} compact={compact} />
    <CurrentLocation />
  </MemoryRouter>);
  fireEvent.click(screen.getByRole('button'));
  expect(screen.getByTestId('current-location').textContent).toBe('/live/match-42');
});

it('selects a preview without navigating when an onSelect callback is provided', () => {
  const onSelect = vi.fn();
  render(<MemoryRouter initialEntries={['/kiosk/live']}>
    <MatchCard match={match} onSelect={onSelect} />
    <CurrentLocation />
  </MemoryRouter>);
  fireEvent.click(screen.getByRole('button'));
  expect(onSelect).toHaveBeenCalledExactlyOnceWith(match);
  expect(screen.getByTestId('current-location').textContent).toBe('/kiosk/live');
});
