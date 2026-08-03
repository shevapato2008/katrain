import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import AccountSection from './AccountSection';

vi.mock('../../../context/AuthContext', () => ({ useAuth: () => ({ token: undefined, user: { username: 'fan' }, logout: vi.fn() }) }));
vi.mock('../../../features/aiLadder/useAiLadderStatus', () => ({ useAiLadderStatus: () => ({ status: { view_state: 'ready', placement_state: { phase: 'placement', completed_games: 3, total_games: 5 }, current_opponent: { rung: 12, rank_name: '9级', certification_status: 'certified', availability: 'available', route: 'server' }, recent_ranked_results: [], net_score: 0, pending_settlement: false }, retry: vi.fn() }) }));

describe('AccountSection ladder summary', () => {
  it('shows placement progress using cookie-compatible status', () => {
    render(<MemoryRouter><AccountSection /></MemoryRouter>);
    expect(screen.getByText('定级中 3/5')).toBeInTheDocument();
    expect(screen.getByText('当前对手 9级')).toBeInTheDocument();
  });
});
