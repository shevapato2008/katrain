import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import PlayerCard from './PlayerCard';

// NB: PlayerInfo.calculated_rank is typed string|null (pre-existing quirk — do NOT pass a raw
// number here or tsc fails). rank_display is optional. Keep fixtures type-valid.
const ladderInfo = {
  player_type: 'player:ai', player_subtype: 'ai:ladder', name: 'AI (棋力阶梯)',
  calculated_rank: null, rank_display: '超越职业', periods_used: 0, main_time_used: 0,
};
const humanInfo = {
  player_type: 'human', player_subtype: '', name: 'User',
  calculated_rank: null, periods_used: 0, main_time_used: 0,  // rank_display omitted (optional)
};

describe('PlayerCard rank_display', () => {
  it('shows rank_display 段位 when present (ladder AI)', () => {
    render(<PlayerCard player="W" info={ladderInfo} captures={0} active={false} />);
    expect(screen.getByText('超越职业')).toBeInTheDocument();
    expect(screen.getByText('AI (棋力阶梯)')).toBeInTheDocument();
  });

  it('falls back to the calculated-rank path when rank_display is absent', () => {
    render(<PlayerCard player="B" info={humanInfo} captures={0} active={false} />);
    // rank_display absent + calculated_rank null -> "No Rank": proves `??` falls through, no 段位 leak
    expect(screen.getByText('No Rank')).toBeInTheDocument();
    expect(screen.queryByText('超越职业')).not.toBeInTheDocument();
  });
});
