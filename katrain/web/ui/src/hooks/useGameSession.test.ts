import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { API } from '../api';
import { useGameSession } from './useGameSession';

vi.mock('../api', () => ({ API: {
  getState: vi.fn(() => new Promise(() => {})),
  resign: vi.fn(),
} }));

describe('useGameSession action failures', () => {
  beforeEach(() => vi.clearAllMocks());

  it('records and rethrows an authoritative resign failure', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    vi.mocked(API.resign).mockRejectedValue(new Error('resign denied'));
    const { result } = renderHook(() => useGameSession({ token: 'token-1' }));
    act(() => result.current.setSessionId('session-1'));
    await waitFor(() => expect(result.current.sessionId).toBe('session-1'));

    let thrown: unknown;
    await act(async () => {
      try { await result.current.handleAction('resign'); } catch (error) { thrown = error; }
    });
    expect(thrown).toEqual(new Error('resign denied'));
    expect(result.current.error).toBe('resign denied');
    expect(API.resign).toHaveBeenCalledWith('session-1', 'token-1');
  });
});
