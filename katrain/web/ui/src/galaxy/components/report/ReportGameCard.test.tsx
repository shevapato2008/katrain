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
    expect(card.querySelector('button')).toBeNull();
    expect(within(card).queryByRole('progressbar')).toBeNull();
    expect(within(card).queryByText(/Generating|53\/120/)).toBeNull();
    expect(screen.getAllByRole('progressbar').map(bar => bar.getAttribute('aria-valuenow'))).toEqual(['100', '44']);
    fireEvent.click(within(card).getByRole('button'));
    expect(onSelect).toHaveBeenCalledOnce();
  });

  it('keeps running 100% readonly with no embedded old completed action', () => {
    render(<ReportGameCard game={game} reportState={{ completedNormal: task(), activeNormal: task({ id: 3, status: 'running' }) }} onSelect={vi.fn()} />);
    expect(screen.getByTestId('report-game-card').querySelector('button')).toBeNull();
    expect(document.querySelector('[data-tier="normal"]')).toHaveAttribute('data-status', 'running');
    expect(document.querySelector('[data-tier="normal"]')).toHaveAttribute('aria-valuenow', '100');
  });

  it('keeps failed semantics without embedding retry or continuation controls', () => {
    render(<ReportGameCard game={game} reportState={{ failedNormal: task({ status: 'failed', analyzed_moves: 53, billing_version: 'v1' }) }} onSelect={vi.fn()} />);
    expect(screen.getByTestId('report-game-card').querySelector('button')).toBeNull();
    expect(screen.getByText('Analysis failed')).toBeInTheDocument();
    expect(screen.queryByText(/retry|continue/i)).toBeNull();
  });
});
