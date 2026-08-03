import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import Dashboard from './Dashboard';

vi.mock('../../context/SettingsContext', () => ({ useSettings: () => ({}) }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ token: 'token', user: { username: 'fan' } }) }));
vi.mock('../../features/aiLadder/useAiLadderStatus', () => ({ useAiLadderStatus: () => ({ status: { view_state: 'ready', placement_state: { phase: 'placed', rung: { rung: 30, rank_name: '5段', certification_status: 'certified', availability: 'available', route: 'server' } }, current_opponent: { rung: 30, rank_name: '5段', certification_status: 'certified', availability: 'available', route: 'server' }, recent_ranked_results: ['win'], net_score: 1, pending_settlement: false }, retry: vi.fn() }) }));

describe('Dashboard AI ladder profile', () => {
  it('shows the authoritative ladder status card for the signed-in user', () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    expect(screen.getByRole('heading', { name: 'AI升降级对弈' })).toBeInTheDocument();
    expect(screen.getByText('当前段位：5段')).toBeInTheDocument();
    expect(screen.getByText('累计净胜分：+1')).toBeInTheDocument();
  });
});
