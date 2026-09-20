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
const finishedState = (): GameState => ({ game_id: 'g1', current_node_id: 9, end_result: 'B+R' }) as GameState;
const nextGameState = (): GameState => ({ game_id: 'g2', current_node_id: 1 }) as GameState;
const update = (state: GameState) => ({ data: JSON.stringify({ type: 'game_update', state }) } as MessageEvent);

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

  it('says nothing when the server closes normally after ending a game on purpose', async () => {
    // 服务端有意收尾(离开判负 / 登出判负 / 删除会话)走 1000 正常关闭,见 session.py 的
    // SOCKET_CLOSE_SESSION_CLOSED。那种关闭必须**穿过三个分支什么也不设** —— 一旦它被
    // 当成 gone,赢的那一方会在「你赢了」之后几毫秒被顶成「这一局没了」。
    vi.mocked(API.getState).mockResolvedValue({ session_id: 'session-1', state: minimalState() });
    vi.stubGlobal('WebSocket', MockWebSocket);
    const { result } = renderHook(() => useGameSession({ token: 'token-1' }));
    act(() => result.current.setSessionId('session-1'));
    await waitFor(() => expect(sockets).toHaveLength(1));

    act(() => sockets[0].onclose?.({ code: 1000, reason: 'session_closed', wasClean: true }));

    expect(result.current.connectionLost).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('does not replace a finished game\'s result with "this game is gone"', async () => {
    // 兜底那一条(服务端侧已经不会这么关了,但终局卡还在屏上时会话可能被**闲置回收**):
    // 那时 session_gone 是真的,可用户要看的是结果,不是「这一局没了」。
    vi.mocked(API.getState).mockResolvedValue({ session_id: 'session-1', state: minimalState() });
    vi.stubGlobal('WebSocket', MockWebSocket);
    const { result } = renderHook(() => useGameSession({ token: 'token-1' }));
    act(() => result.current.setSessionId('session-1'));
    await waitFor(() => expect(sockets).toHaveLength(1));

    act(() => sockets[0].onmessage?.(update(finishedState())));
    act(() => sockets[0].onclose?.({ code: 1008, reason: 'session_gone', wasClean: true }));

    expect(result.current.gameState?.end_result).toBe('B+R');
    expect(result.current.connectionLost).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('flags gone again once a NEW game is under way on the same hook', async () => {
    // 上一条的反面,也是「有结果了」这个标志必须**能回到 false** 的理由:galaxy 的
    // GameRoomPage 在同一个挂载的 hook 上换 sessionId,页内再来一局之后,新这一局真正
    // 被回收了就必须照常报警。标志取自 state 的 end_result ⇒ 新局的 state 不带它,自己归零。
    vi.mocked(API.getState).mockResolvedValue({ session_id: 'session-1', state: minimalState() });
    vi.stubGlobal('WebSocket', MockWebSocket);
    const { result } = renderHook(() => useGameSession({ token: 'token-1' }));
    act(() => result.current.setSessionId('session-1'));
    await waitFor(() => expect(sockets).toHaveLength(1));

    act(() => sockets[0].onmessage?.(update(finishedState())));
    act(() => sockets[0].onmessage?.(update(nextGameState())));
    act(() => sockets[0].onclose?.({ code: 1008, reason: 'session_gone', wasClean: true }));

    expect(result.current.connectionLost).toBe('gone');
  });
});
