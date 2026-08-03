import { fireEvent, render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { describe, expect, it, vi } from 'vitest';
import { zenTheme } from '../../theme';
import AiLadderSetupOpponent from './AiLadderSetupOpponent';
import type { AiLadderReadyStatus } from './types';

const placement: AiLadderReadyStatus = {
  view_state: 'ready',
  placement_state: { phase: 'placement', completed_games: 3, total_games: 5 },
  current_opponent: {
    rung: 17,
    rank_name: '4级',
    certification_status: 'certified',
    availability: 'available',
    route: 'server',
  },
  recent_ranked_results: ['win', 'loss', 'win'],
  net_score: 0,
  pending_settlement: false,
};

const renderSummary = (status = placement, onRetry?: () => void) =>
  render(
    <ThemeProvider theme={zenTheme}>
      <AiLadderSetupOpponent status={status} onRetry={onRetry} />
    </ThemeProvider>,
  );

describe('AiLadderSetupOpponent', () => {
  it('shows the server-decided placement opponent and progress compactly', () => {
    renderSummary();

    expect(screen.getByRole('heading', { name: '41档升降级AI' })).toBeInTheDocument();
    expect(screen.getByText('定级对手：4级')).toBeInTheDocument();
    expect(screen.getByText('定级进度 3/5')).toBeInTheDocument();
    expect(screen.getByText('已认证')).toBeInTheDocument();
    expect(screen.getByText('服务器对弈')).toBeInTheDocument();
    expect(screen.queryByText(/累计净胜分/)).not.toBeInTheDocument();
  });

  it('shows the current ranked opponent without exposing the internal rung', () => {
    renderSummary({
      ...placement,
      placement_state: {
        phase: 'placed',
        rung: { ...placement.current_opponent!, rung: 30, rank_name: '5段' },
      },
      current_opponent: null,
      net_score: 2,
    });

    expect(screen.getByText('本局对手：5段')).toBeInTheDocument();
    expect(screen.queryByText('第30档')).not.toBeInTheDocument();
  });

  it('fails closed for provisional or unavailable opponents', () => {
    renderSummary({
      ...placement,
      current_opponent: {
        ...placement.current_opponent!,
        certification_status: 'provisional',
        availability: 'unavailable',
      },
    });

    expect(screen.getByText('暂定')).toBeInTheDocument();
    expect(screen.getByText('该档位暂不可挑战')).toBeInTheDocument();
  });

  it('shows pending settlement, loading, and retry states without a game action', () => {
    const { rerender } = renderSummary({ ...placement, pending_settlement: true });
    expect(screen.getByRole('status')).toHaveTextContent('本盘成绩结算中');

    rerender(
      <ThemeProvider theme={zenTheme}>
        <AiLadderSetupOpponent status={{ view_state: 'loading' }} />
      </ThemeProvider>,
    );
    expect(screen.getByRole('status')).toHaveTextContent('正在加载升降级对弈状态…');

    const onRetry = vi.fn();
    rerender(
      <ThemeProvider theme={zenTheme}>
        <AiLadderSetupOpponent status={{ view_state: 'error' }} onRetry={onRetry} />
      </ThemeProvider>,
    );
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
