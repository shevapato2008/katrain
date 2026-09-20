import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { GameState } from '../api';
import { API, ApiError } from '../api';
import { useGameSession } from './useGameSession';

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>();
  return {
    ...actual,
    API: {
      getState: vi.fn(() => new Promise(() => {})),
      resign: vi.fn(),
    },
  };
});

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

// Minimal WebSocket double, only for the two tests below that need the hook to reach
// `new WebSocket(...)`. The default mocked `API.getState` never resolves (see the
// module mock above), so today's harness never constructs a socket at all — these two
// tests are the first in this file to make `getState` resolve and drive `onclose`.
const sockets: MockWebSocket[] = [];
class MockWebSocket {
  static OPEN = 1;
  readyState = MockWebSocket.OPEN;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onopen: (() => void) | null = null;
  onclose: ((event: { code: number; reason: string; wasClean: boolean }) => void) | null = null;
  close = vi.fn();
  send = vi.fn();
  constructor(readonly url: string) { sockets.push(this); }
}

const minimalState = (): GameState => ({ game_id: 'g1', current_node_id: 1 }) as GameState;

describe('the session-is-gone signal', () => {
  // The session can be discovered gone three different ways. A fix that handles one
  // leaves the others broken - the 200 body is the sneakiest, because handleAction
  // otherwise treats it as a silent success.

  beforeEach(() => {
    vi.clearAllMocks();
    sockets.length = 0;
    // Restore the hanging default (any earlier test in this describe may have
    // overridden it) so tests that don't touch the socket stay socket-free.
    vi.mocked(API.getState).mockImplementation(() => new Promise(() => {}));
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
  });

  afterEach(() => vi.unstubAllGlobals());

  it('flags gone when a game action 404s', async () => {
    vi.mocked(API.resign).mockRejectedValue(
      new ApiError(404, 'Request failed 404: {"detail":"Session not found"}')
    );
    const { result } = renderHook(() => useGameSession({ token: 'token-1' }));
    act(() => result.current.setSessionId('session-1'));
    await waitFor(() => expect(result.current.sessionId).toBe('session-1'));

    await act(async () => {
      await result.current.handleAction('resign').catch(() => undefined);
    });

    expect(result.current.connectionLost).toBe('gone');
    // galaxy's only channel - null would leave it silent.
    expect(typeof result.current.error).toBe('string');
    expect((result.current.error ?? '').length).toBeGreaterThan(0);
    expect(/Request failed/.test(result.current.error ?? '')).toBe(false);
  });

  it('flags gone when a game action returns a session_gone body', async () => {
    vi.mocked(API.resign).mockResolvedValue({ session_id: 's', status: 'session_gone' } as never);
    const { result } = renderHook(() => useGameSession({ token: 'token-1' }));
    act(() => result.current.setSessionId('session-1'));
    await waitFor(() => expect(result.current.sessionId).toBe('session-1'));

    await act(async () => {
      await result.current.handleAction('resign');
    });

    expect(result.current.connectionLost).toBe('gone');
    // No invented result - the 200 body carries no state to apply.
    expect(result.current.gameState).toBeNull();
  });

  it('flags gone when the socket closes with 1008 session_gone', async () => {
    vi.mocked(API.getState).mockResolvedValue({ session_id: 'session-1', state: minimalState() });
    vi.stubGlobal('WebSocket', MockWebSocket);
    const { result } = renderHook(() => useGameSession({ token: 'token-1' }));
    act(() => result.current.setSessionId('session-1'));
    await waitFor(() => expect(sockets).toHaveLength(1));

    act(() => sockets[0].onclose?.({ code: 1008, reason: 'session_gone', wasClean: true }));

    expect(result.current.connectionLost).toBe('gone');
    expect(/重新登录/.test(result.current.error ?? '')).toBe(false);
  });

  it('still says re-login for a genuine 1008 credential rejection', async () => {
    vi.mocked(API.getState).mockResolvedValue({ session_id: 'session-1', state: minimalState() });
    vi.stubGlobal('WebSocket', MockWebSocket);
    const { result } = renderHook(() => useGameSession({ token: 'token-1' }));
    act(() => result.current.setSessionId('session-1'));
    await waitFor(() => expect(sockets).toHaveLength(1));

    act(() => sockets[0].onclose?.({ code: 1008, reason: 'Invalid token', wasClean: true }));

    // The two must not be conflated - re-login cannot fix an evicted session, and
    // telling the user to try is a lie.
    expect(result.current.connectionLost).toBe('rejected');
  });
});
