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
  it('keeps platform primary and report progress outside the information card', () => {
    const onSelect = vi.fn();
    render(<ReportGameCard game={game} reportState={{ completedNormal: task(), activeDeep: task({ id: 2, report_type: 'deep', status: 'running', analyzed_moves: 53 }) }} onSelect={onSelect} onDelete={vi.fn()} />);
    expect(screen.getByText('Cross-platform · Golaxy')).toBeInTheDocument();
    expect(screen.getByText('Evening game')).toBeInTheDocument();
    const card = screen.getByTestId('report-game-card');
    expect(screen.getByTestId('report-game-row')).toHaveAttribute('data-has-running-report', 'true');
    expect(within(card).getByRole('button', { name: 'Delete game' })).toBeVisible();
    expect(within(card).queryByRole('progressbar')).toBeNull();
    expect(within(card).getByText('Advanced report 53/120')).toBeVisible();
    expect(within(card).queryByText(/Generating/)).toBeNull();
    expect(screen.getAllByRole('progressbar').map(bar => bar.getAttribute('aria-valuenow'))).toEqual(['44']);
    fireEvent.click(within(card).getByRole('button', { pressed: false }));
    expect(onSelect).toHaveBeenCalledOnce();
  });

  it('deletes from a separate card control without selecting the game', () => {
    const onSelect = vi.fn();
    const onDelete = vi.fn();
    render(<ReportGameCard game={game} reportState={{}} onSelect={onSelect} onDelete={onDelete} />);
    const card = screen.getByTestId('report-game-card');
    const remove = within(card).getByRole('button', { name: 'Delete game' });
    const select = within(card).getByRole('button', { pressed: false });
    expect(select).not.toContainElement(remove);
    expect(remove.closest('[role="button"]')).toBeNull();
    fireEvent.click(remove);
    expect(onDelete).toHaveBeenCalledOnce();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('hides deletion for protected library games even when supplied a callback', () => {
    render(<ReportGameCard game={{ ...game, source: 'kifu_library' }} reportState={{}} onSelect={vi.fn()} onDelete={vi.fn()} />);
    expect(screen.queryByRole('button', { name: 'Delete game' })).toBeNull();
  });

  it('shows each active tier hand frontier as visible, noninteractive metadata', () => {
    render(<ReportGameCard game={game} reportState={{
      activeNormal: task({ status: 'running', analyzed_moves: 31 }),
      activeDeep: task({ id: 2, report_type: 'deep', status: 'running', analyzed_moves: 53 }),
    }} onSelect={vi.fn()} onDelete={vi.fn()} />);
    const card = screen.getByTestId('report-game-card');
    expect(within(card).getByText('Normal report 31/120')).toBeVisible();
    expect(within(card).getByText('Advanced report 53/120')).toBeVisible();
    expect(within(card).queryByRole('progressbar')).toBeNull();
    expect(within(card).getAllByRole('button')).toHaveLength(2);
    expect(screen.getAllByRole('progressbar').map(bar => bar.getAttribute('aria-valuenow'))).toEqual(['26', '44']);
  });

  it('keeps running 100% readonly with no embedded old completed action', () => {
    render(<ReportGameCard game={game} reportState={{ completedNormal: task(), activeNormal: task({ id: 3, status: 'running' }) }} onSelect={vi.fn()} onDelete={vi.fn()} />);
    expect(within(screen.getByTestId('report-game-card')).getByRole('button', { name: 'Delete game' })).toBeVisible();
    expect(document.querySelector('[data-tier="normal"]')).toHaveAttribute('data-status', 'running');
    expect(document.querySelector('[data-tier="normal"]')).toHaveAttribute('aria-valuenow', '100');
  });

  it('places players on either side of the result and moves, preserving full names and keyboard selection', () => {
    const black = 'A very long black player name';
    const white = 'A very long white player name';
    const onSelect = vi.fn();
    render(<ReportGameCard game={{ ...game, player_black: black, player_white: white, result: 'B+R',
      black_rank: '1d', white_rank: '2d', game_date: '2026-11-14' }} selected reportState={{}} onSelect={onSelect} onDelete={vi.fn()} />);
    const blackName = screen.getByTitle(black);
    const whiteName = screen.getByTitle(white);
    const match = blackName.parentElement!.parentElement!;
    expect(match.children).toHaveLength(3);
    expect(match.children[0]).toContainElement(blackName);
    expect(match.children[1]).toHaveTextContent('120 moves');
    expect(match.children[1]).toHaveTextContent('B+R');
    expect(match.children[2]).toContainElement(whiteName);
    expect(screen.getByText('2026-11-14')).toBeVisible();
    const select = screen.getByRole('button', { pressed: true });
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
    render(<ReportGameCard game={game} reportState={reportState} onSelect={vi.fn()} onDelete={vi.fn()} />);
    expect(screen.getByTestId('report-game-row')).toHaveAttribute('data-has-running-report', 'false');
    expect(screen.queryByRole('progressbar')).toBeNull();
  });

  it('keeps pending reports visibly queued in the card', () => {
    render(<ReportGameCard game={game} reportState={{ activeNormal: task({ status: 'pending', analyzed_moves: 0 }) }} onSelect={vi.fn()} onDelete={vi.fn()} />);
    expect(within(screen.getByTestId('report-game-card')).getByText('Normal report Queued')).toBeVisible();
  });

  it('keeps failed semantics without embedding retry or continuation controls', () => {
    render(<ReportGameCard game={game} reportState={{ failedNormal: task({ status: 'failed', analyzed_moves: 53, billing_version: 'v1' }) }} onSelect={vi.fn()} onDelete={vi.fn()} />);
    expect(within(screen.getByTestId('report-game-card')).getByRole('button', { name: 'Delete game' })).toBeVisible();
    expect(screen.getByText('Analysis failed')).toBeInTheDocument();
    expect(screen.queryByText(/retry|continue/i)).toBeNull();
  });
});

it('shows server-resolved historical public names without rendering internal handles', () => {
  render(<ReportGameCard game={{ ...game, platform: null, player_black: 'u_0123456789abcdefabcd', display_player_black: '公开棋手' } as UserGameSummary} reportState={{}} onSelect={vi.fn()} onDelete={vi.fn()} />);
  expect(screen.getByText('公开棋手')).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent('u_0123456789abcdefabcd');
});
