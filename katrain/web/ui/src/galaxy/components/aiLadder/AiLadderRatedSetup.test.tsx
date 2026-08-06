import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import AiLadderRatedSetup from './AiLadderRatedSetup';
import type { AiLadderReadyStatus } from '../../../features/aiLadder/types';

const readyStatus: AiLadderReadyStatus = {
  view_state: 'ready',
  placement_state: {
    phase: 'placed',
    rung: { rung: 30, rank_name: '5段', certification_status: 'certified', availability: 'available', route: 'server' },
  },
  current_opponent: { rung: 30, rank_name: '5段', certification_status: 'certified', availability: 'available', route: 'server' },
  recent_ranked_results: ['win', 'loss', 'win', 'win', 'loss'],
  net_score: 1,
  pending_settlement: false,
};

describe('AiLadderRatedSetup', () => {
  it('shows the ready ranked journey without exposing the internal rung', () => {
    render(
      <AiLadderRatedSetup
        status={readyStatus}
        color="B"
        mainTime={10}
        byoLength={30}
        byoPeriods={3}
        startPending={false}
        onColorChange={vi.fn()}
        onRetry={vi.fn()}
        onStart={vi.fn()}
      />,
    );

    expect(screen.getByText('5段', { selector: '[data-testid="current-rank"]' })).toBeInTheDocument();
    expect(screen.getAllByText('+1').length).toBeGreaterThan(0);
    expect(screen.getByText('胜 负 胜 胜 负')).toBeInTheDocument();
    expect(screen.getByText('19路')).toBeInTheDocument();
    expect(screen.getByText('中国规则')).toBeInTheDocument();
    expect(screen.getByText('贴目 7.5')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '开始正式对局' })).toBeEnabled();
    expect(screen.queryByText('30')).not.toBeInTheDocument();
  });
});
