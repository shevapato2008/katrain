import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AiLadderApiError } from './api';
import { AI_LADDER_COPY } from './copy';
import { useAiLadderStatus } from './useAiLadderStatus';

const { getStatus } = vi.hoisted(() => ({ getStatus: vi.fn() }));
vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  getAiLadderStatus: getStatus,
}));

describe('useAiLadderStatus', () => {
  beforeEach(() => getStatus.mockReset());

  it('moves from loading to the authoritative ready status', async () => {
    getStatus.mockResolvedValue({ view_state: 'ready', placement_state: { phase: 'placement', completed_games: 0, total_games: 5 }, current_opponent: null, recent_ranked_results: [], net_score: 0, pending_settlement: false });
    const { result } = renderHook(() => useAiLadderStatus('token', true));
    expect(result.current.status).toEqual({ view_state: 'loading' });
    await waitFor(() => expect(result.current.status.view_state).toBe('ready'));
  });

  it('shows a readable message instead of the operator-facing detail, and retries', async () => {
    // The server's 503 detail is "Ranked AI ladder authority is unavailable on this node"
    // — English, written for whoever runs the box, and it was reaching the kiosk screen.
    getStatus.mockRejectedValueOnce(new AiLadderApiError(503, 'Ranked AI ladder authority is unavailable on this node'))
      .mockResolvedValueOnce({ view_state: 'ready', placement_state: { phase: 'placement', completed_games: 0, total_games: 5 }, current_opponent: null, recent_ranked_results: [], net_score: 0, pending_settlement: false });
    const { result } = renderHook(() => useAiLadderStatus(undefined, true));
    await waitFor(() => expect(result.current.status).toEqual({
      view_state: 'error',
      message: AI_LADDER_COPY.loadErrorNotAuthoritative,
    }));
    expect(JSON.stringify(result.current.status)).not.toContain('authority is unavailable');
    result.current.retry();
    await waitFor(() => expect(result.current.status.view_state).toBe('ready'));
  });

  it('tells an expired login apart from a node that does not keep scores', async () => {
    getStatus.mockRejectedValueOnce(new AiLadderApiError(401, 'Not authenticated'));
    const { result } = renderHook(() => useAiLadderStatus(undefined, true));
    await waitFor(() => expect(result.current.status).toEqual({
      view_state: 'error',
      message: AI_LADDER_COPY.loadErrorUnauthorized,
    }));
  });

  it('falls back to a generic message for an error it cannot classify', async () => {
    getStatus.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    const { result } = renderHook(() => useAiLadderStatus(undefined, true));
    await waitFor(() => expect(result.current.status).toEqual({
      view_state: 'error',
      message: AI_LADDER_COPY.loadError,
    }));
  });

  // A 200 whose body is not a ready status used to be handed straight to the card, which
  // read `placement_state.phase` off undefined and threw. There is no error boundary above
  // it, so React unmounted the whole app: a blank screen where "failed to load" belongs.
  it.each([
    ['an empty body', {}],
    ['a ready status with no placement_state', { view_state: 'ready', net_score: 0, recent_ranked_results: [], pending_settlement: false }],
    ['a placed status with no rung', { view_state: 'ready', placement_state: { phase: 'placed' }, net_score: 0, recent_ranked_results: [], pending_settlement: false }],
    ['null', null],
  ])('treats %s as a load failure instead of passing it on', async (_label, body) => {
    getStatus.mockResolvedValue(body);
    const { result } = renderHook(() => useAiLadderStatus('token', true));
    await waitFor(() => expect(result.current.status).toEqual({
      view_state: 'error',
      message: AI_LADDER_COPY.loadError,
    }));
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
