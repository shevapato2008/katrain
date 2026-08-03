import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAiLadderStatus } from './useAiLadderStatus';

const { getStatus } = vi.hoisted(() => ({ getStatus: vi.fn() }));
vi.mock('./api', () => ({ getAiLadderStatus: getStatus }));

describe('useAiLadderStatus', () => {
  beforeEach(() => getStatus.mockReset());

  it('moves from loading to the authoritative ready status', async () => {
    getStatus.mockResolvedValue({ view_state: 'ready', placement_state: { phase: 'placement', completed_games: 0, total_games: 5 }, current_opponent: null, recent_ranked_results: [], net_score: 0, pending_settlement: false });
    const { result } = renderHook(() => useAiLadderStatus('token', true));
    expect(result.current.status).toEqual({ view_state: 'loading' });
    await waitFor(() => expect(result.current.status.view_state).toBe('ready'));
  });

  it('keeps backend detail and retries after an error', async () => {
    getStatus.mockRejectedValueOnce(new Error('Ranked authority is unavailable'))
      .mockResolvedValueOnce({ view_state: 'ready', placement_state: { phase: 'placement', completed_games: 0, total_games: 5 }, current_opponent: null, recent_ranked_results: [], net_score: 0, pending_settlement: false });
    const { result } = renderHook(() => useAiLadderStatus(undefined, true));
    await waitFor(() => expect(result.current.status).toEqual({ view_state: 'error', message: 'Ranked authority is unavailable' }));
    result.current.retry();
    await waitFor(() => expect(result.current.status.view_state).toBe('ready'));
  });

  it('does not call the ranked endpoint for free play', () => {
    renderHook(() => useAiLadderStatus('token', false));
    expect(getStatus).not.toHaveBeenCalled();
  });

  it('does not let an older token response overwrite the current user', async () => {
    let resolveOld!: (value: any) => void;
    const oldRequest = new Promise((resolve) => { resolveOld = resolve; });
    const fresh = { view_state: 'ready', placement_state: { phase: 'placed', rung: { rung: 2, rank_name: '19级', certification_status: 'certified', availability: 'available', route: 'server' } }, current_opponent: null, recent_ranked_results: [], net_score: 0, pending_settlement: false };
    getStatus.mockReturnValueOnce(oldRequest).mockResolvedValueOnce(fresh);
    const { result, rerender } = renderHook(({ token }) => useAiLadderStatus(token, true), { initialProps: { token: 'old' } });
    rerender({ token: 'new' });
    await waitFor(() => expect(result.current.status).toEqual(fresh));
    resolveOld({ ...fresh, placement_state: { phase: 'placed', rung: { ...fresh.placement_state.rung, rank_name: '错误旧用户' } } });
    await Promise.resolve();
    expect(result.current.status).toEqual(fresh);
    expect(getStatus.mock.calls[0][1]).toBeInstanceOf(AbortSignal);
    expect(getStatus.mock.calls[0][1].aborted).toBe(true);
  });
});
