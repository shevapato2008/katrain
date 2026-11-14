import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { ReportTaskSummary } from '../../../api/reportApi';
import type { UserGameSummary } from '../../../api/userGamesApi';
import ReportGameCard from './ReportGameCard';

vi.mock('../../../hooks/useTranslation', () => ({ useTranslation: () => ({ t: (_key: string, fallback?: string) => fallback ?? _key }) }));
const game = { id: 'game', source: 'play_ai', platform: 'golaxy', game_type: 'free', move_count: 120,
  event: 'Evening game', title: 'A title', player_black: 'B', player_white: 'W' } as UserGameSummary;
const task = (over: Partial<ReportTaskSummary> = {}): ReportTaskSummary => ({
  id: 1, user_game_id: 'game', report_type: 'normal', status: 'completed', total_moves: 120,
  analyzed_moves: 120, requested_visits: 500, started_at: null, completed_at: null, ...over,
});

describe('Galaxy compact report card', () => {
  it('keeps platform primary and all report controls outside the information card', () => {
    const onSelect = vi.fn();
    render(<ReportGameCard game={game} reportState={{ completedNormal: task(), activeDeep: task({ id: 2, report_type: 'deep', status: 'running', analyzed_moves: 53 }) }} onSelect={onSelect} />);
    expect(screen.getByText('Cross-platform · Golaxy')).toBeInTheDocument();
    expect(screen.getByText('Evening game')).toBeInTheDocument();
    const card = screen.getByTestId('report-game-card');
    expect(screen.getByTestId('report-game-row')).toHaveAttribute('data-has-running-report', 'true');
    expect(card.querySelector('button')).toBeNull();
    expect(within(card).queryByRole('progressbar')).toBeNull();
    expect(within(card).getByText('Advanced report 53/120')).toBeVisible();
    expect(within(card).queryByText(/Generating/)).toBeNull();
    expect(screen.getAllByRole('progressbar').map(bar => bar.getAttribute('aria-valuenow'))).toEqual(['44']);
    fireEvent.click(within(card).getByRole('button'));
    expect(onSelect).toHaveBeenCalledOnce();
  });

  it('shows each active tier hand frontier as visible, noninteractive metadata', () => {
    render(<ReportGameCard game={game} reportState={{
      activeNormal: task({ status: 'running', analyzed_moves: 31 }),
      activeDeep: task({ id: 2, report_type: 'deep', status: 'running', analyzed_moves: 53 }),
    }} onSelect={vi.fn()} />);
    const card = screen.getByTestId('report-game-card');
    expect(within(card).getByText('Normal report 31/120')).toBeVisible();
    expect(within(card).getByText('Advanced report 53/120')).toBeVisible();
    expect(card.querySelector('button, [role="progressbar"]')).toBeNull();
    expect(screen.getAllByRole('progressbar').map(bar => bar.getAttribute('aria-valuenow'))).toEqual(['26', '44']);
  });

  it('keeps running 100% readonly with no embedded old completed action', () => {
    render(<ReportGameCard game={game} reportState={{ completedNormal: task(), activeNormal: task({ id: 3, status: 'running' }) }} onSelect={vi.fn()} />);
    expect(screen.getByTestId('report-game-card').querySelector('button')).toBeNull();
    expect(document.querySelector('[data-tier="normal"]')).toHaveAttribute('data-status', 'running');
    expect(document.querySelector('[data-tier="normal"]')).toHaveAttribute('aria-valuenow', '100');
  });

  it('places players on either side of the result and moves, preserving full names and keyboard selection', () => {
    const black = 'A very long black player name';
    const white = 'A very long white player name';
    const onSelect = vi.fn();
    render(<ReportGameCard game={{ ...game, player_black: black, player_white: white, result: 'B+R',
      black_rank: '1d', white_rank: '2d', game_date: '2026-11-14' }} selected reportState={{}} onSelect={onSelect} />);
    const blackName = screen.getByTitle(black);
    const whiteName = screen.getByTitle(white);
    const match = blackName.parentElement!.parentElement!;
    expect(match.children).toHaveLength(3);
    expect(match.children[0]).toContainElement(blackName);
    expect(match.children[1]).toHaveTextContent('120 moves');
    expect(match.children[1]).toHaveTextContent('B+R');
    expect(match.children[2]).toContainElement(whiteName);
    expect(screen.getByText('2026-11-14')).toBeVisible();
    const select = screen.getByRole('button');
    expect(select).toHaveAttribute('aria-pressed', 'true');
    fireEvent.keyDown(select, { key: 'Enter' });
    fireEvent.keyDown(select, { key: ' ' });
    expect(onSelect).toHaveBeenCalledTimes(2);
  });

  it.each([
    {},
    { completedNormal: task() },
    { failedNormal: task({ status: 'failed' }) },
    { activeNormal: task({ status: 'pending', analyzed_moves: 0 }) },
  ])('uses a full-width card without running reports: %j', reportState => {
    render(<ReportGameCard game={game} reportState={reportState} onSelect={vi.fn()} />);
    expect(screen.getByTestId('report-game-row')).toHaveAttribute('data-has-running-report', 'false');
    expect(screen.queryByRole('progressbar')).toBeNull();
  });

  it('keeps pending reports visibly queued in the card', () => {
    render(<ReportGameCard game={game} reportState={{ activeNormal: task({ status: 'pending', analyzed_moves: 0 }) }} onSelect={vi.fn()} />);
    expect(within(screen.getByTestId('report-game-card')).getByText('Normal report Queued')).toBeVisible();
  });

  it('keeps failed semantics without embedding retry or continuation controls', () => {
    render(<ReportGameCard game={game} reportState={{ failedNormal: task({ status: 'failed', analyzed_moves: 53, billing_version: 'v1' }) }} onSelect={vi.fn()} />);
    expect(screen.getByTestId('report-game-card').querySelector('button')).toBeNull();
    expect(screen.getByText('Analysis failed')).toBeInTheDocument();
    expect(screen.queryByText(/retry|continue/i)).toBeNull();
  });
});
