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
});
