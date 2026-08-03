import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import AccountSection from './AccountSection';

const { authState, statusHook, retry } = vi.hoisted(() => ({ authState: { current: { token: undefined, user: { username: 'fan' }, logout: vi.fn() } as any }, statusHook: vi.fn(), retry: vi.fn() }));
vi.mock('../../../context/AuthContext', () => ({ useAuth: () => authState.current }));
vi.mock('../../../features/aiLadder/useAiLadderStatus', () => ({ useAiLadderStatus: statusHook }));

describe('AccountSection ladder summary', () => {
  it('shows placement progress using cookie-compatible status', () => {
    statusHook.mockReturnValue({ status: { view_state: 'ready', placement_state: { phase: 'placement', completed_games: 3, total_games: 5 }, current_opponent: { rung: 12, rank_name: '9级', certification_status: 'certified', availability: 'available', route: 'server' }, recent_ranked_results: ['win', 'loss'], net_score: 1, pending_settlement: false }, retry });
    render(<MemoryRouter><AccountSection /></MemoryRouter>);
    expect(screen.getByText('定级进度 3/5')).toBeInTheDocument();
    expect(screen.getByText('累计净胜分：+1')).toBeInTheDocument();
    expect(screen.getByText('最近5盘仅供展示，升降段只看累计净胜分')).toBeInTheDocument();
    expect(screen.getByText('服务器对弈')).toBeInTheDocument();
    expect(screen.getByText('已认证')).toBeInTheDocument();
  });

  it('does not request or leave a loading ladder card for a guest', () => {
    authState.current = { token: undefined, user: null, logout: vi.fn() };
    statusHook.mockReturnValue({ status: { view_state: 'loading' }, retry });
    render(<MemoryRouter><AccountSection /></MemoryRouter>);
    expect(statusHook).toHaveBeenCalledWith(undefined, false);
    expect(screen.queryByText('正在加载AI段位…')).not.toBeInTheDocument();
  });
});
