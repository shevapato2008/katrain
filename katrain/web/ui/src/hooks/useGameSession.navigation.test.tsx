import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { API } from '../api';
import { useGameSession } from './useGameSession';

vi.mock('../api', () => ({
  API: {
    getState: vi.fn().mockResolvedValue({ session_id: 'session-123', state: {} }),
    navigate: vi.fn().mockResolvedValue({ session_id: 'session-123', state: {} }),
  },
}));

class MockWebSocket {
  static OPEN = 1;
  readyState = MockWebSocket.OPEN;
  onmessage: ((event: MessageEvent) => void) | null = null;
  close = vi.fn();
  send = vi.fn();
}

describe('useGameSession navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('WebSocket', MockWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('authenticates navigation with the game token', async () => {
    const { result } = renderHook(() => useGameSession({ token: 'auth-token' }));

    act(() => {
      result.current.setSessionId('session-123');
    });

    await act(async () => {
      await result.current.onNavigate(42);
    });

    expect(API.navigate).toHaveBeenCalledWith('session-123', 42, 'auth-token');
  });
});
