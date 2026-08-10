import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { MatchDetail, MoveAnalysis } from '../../types/live';
import MatchInfo from './MatchInfo';

const match: MatchDetail = {
  id: 'live-9',
  source: 'yike',
  tournament: 'Galaxy Cup',
  round_name: 'Final',
  date: '2026-08-06T12:00:00Z',
  player_black: 'Alpha',
  player_white: 'Beta',
  black_rank: '九段',
  white_rank: '八段',
  status: 'live',
  result: null,
  move_count: 3,
  current_winrate: 0.51,
  current_score: 0.8,
  last_updated: '2026-08-06T12:01:00Z',
  board_size: 19,
  komi: 7.5,
  rules: 'chinese',
  sgf: null,
  moves: ['D4', 'Q16', 'C3'],
};

const analysis: MoveAnalysis = {
  match_id: match.id,
  move_number: 3,
  move: 'C3',
  player: 'B',
  winrate: 0.625,
  score_lead: 4.2,
  top_moves: [],
  ownership: null,
  is_brilliant: false,
  is_mistake: false,
  is_questionable: false,
  delta_score: 0,
  delta_winrate: 0,
};

describe('MatchInfo', () => {
  it('keeps the full heading composition by default', () => {
    render(<MatchInfo match={match} analysis={analysis} />);

    expect(screen.getByText('live:status_live')).toBeInTheDocument();
    expect(screen.getByText('Galaxy Cup · Final')).toBeInTheDocument();
  });

  it('metadata-only hides duplicated headings while preserving all match metadata', () => {
    render(<MatchInfo match={match} analysis={analysis} headingMode="metadata-only" />);

    expect(screen.queryByText('live:status_live')).not.toBeInTheDocument();
    expect(screen.queryByText('Galaxy Cup · Final')).not.toBeInTheDocument();
    expect(screen.getByText(/2026/)).toBeInTheDocument();
    expect(screen.getByText('弈客')).toBeInTheDocument();
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
    expect(screen.getByText('九段')).toBeInTheDocument();
    expect(screen.getByText('八段')).toBeInTheDocument();
    expect(screen.getByText('62.5%')).toBeInTheDocument();
    expect(screen.getByText('37.5%')).toBeInTheDocument();
    expect(screen.getByText('+4.2 live:pts')).toBeInTheDocument();
    expect(screen.getByText('live:rules_chinese')).toBeInTheDocument();
    expect(screen.getByText('live:komi 7.5')).toBeInTheDocument();

    const panel = screen.getByText('Alpha').closest('.MuiBox-root')?.parentElement?.parentElement;
    expect(panel).not.toBeNull();
    expect(within(panel as HTMLElement).getByText('Beta')).toBeInTheDocument();
  });
});
