import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { GameState } from '../api';
import { API } from '../api';
import { writeAudioPref } from '../utils/audioPrefs';
import { useGameSession } from './useGameSession';

vi.mock('../api', () => ({
  API: { getState: vi.fn() },
}));

const state = (currentNodeId: number, gameId = 'game-1') => ({
  game_id: gameId,
  current_node_id: currentNodeId,
}) as GameState;

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

const played: string[] = [];
class MockAudio {
  currentTime = 0;
  constructor(readonly src: string) {}
  play = vi.fn(() => {
    played.push(this.src.split('/').at(-1) ?? this.src);
    return Promise.resolve();
  });
}

let nextRafId = 1;
let rafCallbacks = new Map<number, FrameRequestCallback>();
const requestAnimationFrameMock = vi.fn((callback: FrameRequestCallback) => {
  const id = nextRafId++;
  rafCallbacks.set(id, callback);
  return id;
});
const cancelAnimationFrameMock = vi.fn((id: number) => {
  rafCallbacks.delete(id);
});

const runNextRaf = () => {
  const next = rafCallbacks.entries().next().value as [number, FrameRequestCallback] | undefined;
  expect(next).toBeTruthy();
  const [id, callback] = next!;
  rafCallbacks.delete(id);
  act(() => callback(0));
};

const send = (socket: MockWebSocket, message: unknown) => {
  act(() => socket.onmessage?.({ data: JSON.stringify(message) } as MessageEvent));
};

const sendState = (socket: MockWebSocket, currentNodeId: number, gameId = 'game-1') => {
  send(socket, { type: 'game_update', state: state(currentNodeId, gameId) });
};

const sendSound = (socket: MockWebSocket, sound: string, afterNodeId?: number) => {
  send(socket, {
    type: 'sound',
    data: afterNodeId === undefined ? { sound } : { sound, after_node_id: afterNodeId },
  });
};

const connect = async (sessionId = 'session-1') => {
  const hook = renderHook(() => useGameSession({ token: 'token' }));
  act(() => hook.result.current.setSessionId(sessionId));
  await waitFor(() => expect(sockets).toHaveLength(1));
  return { ...hook, socket: sockets[0] };
};

describe('useGameSession sound synchronization', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sockets.length = 0;
    played.length = 0;
    nextRafId = 1;
    rafCallbacks = new Map();
    localStorage.removeItem('kiosk_audio_sfx');
    localStorage.removeItem('kioskPlaySound');
    vi.mocked(API.getState).mockResolvedValue({ session_id: 'session-1', state: state(11) });
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.stubGlobal('Audio', MockAudio);
    vi.stubGlobal('requestAnimationFrame', requestAnimationFrameMock);
    vi.stubGlobal('cancelAnimationFrame', cancelAnimationFrameMock);
  });

  afterEach(() => vi.unstubAllGlobals());

  it('holds a node-associated sound until the matching state commits and two frames paint', async () => {
    const { socket } = await connect();

    sendSound(socket, 'stone1', 12);
    expect(played).toEqual([]);
    expect(requestAnimationFrameMock).not.toHaveBeenCalled();

    sendState(socket, 12);
    expect(played).toEqual([]);
    expect(requestAnimationFrameMock).toHaveBeenCalledTimes(1);
    runNextRaf();
    expect(played).toEqual([]);
    expect(requestAnimationFrameMock).toHaveBeenCalledTimes(2);
    runNextRaf();
    expect(played).toEqual(['stone1.wav']);
  });

  it('uses the same two-frame delay when the matching state arrives before the sound', async () => {
    const { socket } = await connect();

    sendState(socket, 12);
    sendSound(socket, 'capturing', 12);
    expect(played).toEqual([]);

    runNextRaf();
    expect(played).toEqual([]);
    runNextRaf();
    expect(played).toEqual(['capturing.wav']);
  });

  it('preserves FIFO order for node-associated sounds', async () => {
    const { socket } = await connect();

    sendSound(socket, 'stone1', 12);
    sendSound(socket, 'capturing', 13);
    sendState(socket, 12);
    runNextRaf();
    runNextRaf();
    expect(played).toEqual(['stone1.wav']);

    sendState(socket, 13);
    runNextRaf();
    runNextRaf();
    expect(played).toEqual(['stone1.wav', 'capturing.wav']);
  });

  it('drops a stale sound if the committed node advances between the two paint frames', async () => {
    const { socket } = await connect();
    sendState(socket, 12);
    sendSound(socket, 'stone1', 12);
    runNextRaf();

    sendState(socket, 13);
    sendSound(socket, 'capturing', 13);
    runNextRaf();

    expect(played).toEqual([]);
    runNextRaf();
    runNextRaf();
    expect(played).toEqual(['capturing.wav']);
  });

  it('plays legacy sounds without after_node_id immediately', async () => {
    const { socket } = await connect();

    sendSound(socket, 'stone1');

    expect(played).toEqual(['stone1.wav']);
    expect(requestAnimationFrameMock).not.toHaveBeenCalled();
  });

  it('cancels scheduled playback when the session changes', async () => {
    const hook = await connect();
    sendState(hook.socket, 12);
    sendSound(hook.socket, 'stone1', 12);
    expect(rafCallbacks).toHaveLength(1);

    act(() => hook.result.current.setSessionId('session-2'));

    expect(cancelAnimationFrameMock).toHaveBeenCalled();
    expect(rafCallbacks).toHaveLength(0);
    expect(played).toEqual([]);
  });

  it('cancels scheduled playback when the game changes', async () => {
    const { socket } = await connect();
    sendState(socket, 12);
    sendSound(socket, 'stone1', 12);
    expect(rafCallbacks).toHaveLength(1);

    sendState(socket, 12, 'game-2');

    expect(cancelAnimationFrameMock).toHaveBeenCalled();
    expect(rafCallbacks).toHaveLength(0);
    expect(played).toEqual([]);
  });

  it('cancels scheduled playback when the socket closes', async () => {
    const { socket } = await connect();
    sendState(socket, 12);
    sendSound(socket, 'stone1', 12);
    expect(rafCallbacks).toHaveLength(1);

    act(() => socket.onclose?.({ code: 1000, reason: '', wasClean: true }));

    expect(cancelAnimationFrameMock).toHaveBeenCalled();
    expect(rafCallbacks).toHaveLength(0);
    expect(played).toEqual([]);
  });

  it('cancels scheduled playback on unmount', async () => {
    const hook = await connect();
    sendState(hook.socket, 12);
    sendSound(hook.socket, 'stone1', 12);
    expect(rafCallbacks).toHaveLength(1);

    hook.unmount();

    expect(cancelAnimationFrameMock).toHaveBeenCalled();
    expect(rafCallbacks).toHaveLength(0);
    expect(played).toEqual([]);
  });

  it('ignores a previous session getState result that resolves after cleanup', async () => {
    let resolveOld!: (value: { session_id: string; state: GameState }) => void;
    vi.mocked(API.getState)
      .mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }))
      .mockResolvedValueOnce({ session_id: 'session-2', state: state(22, 'game-2') });
    const hook = renderHook(() => useGameSession({ token: 'token' }));
    act(() => hook.result.current.setSessionId('session-1'));
    await waitFor(() => expect(API.getState).toHaveBeenCalledTimes(1));

    act(() => hook.result.current.setSessionId('session-2'));
    await waitFor(() => expect(sockets).toHaveLength(1));
    expect(sockets[0].url).toContain('/ws/session-2');
    expect(hook.result.current.gameState?.game_id).toBe('game-2');

    await act(async () => {
      resolveOld({ session_id: 'session-1', state: state(12, 'game-1') });
      await Promise.resolve();
    });

    expect(sockets).toHaveLength(1);
    expect(hook.result.current.gameState?.game_id).toBe('game-2');
  });

  it('honors the shared sound-effect preference for legacy sounds', async () => {
    writeAudioPref('sfx', false);
    const { socket } = await connect();
    sendSound(socket, 'stone1');
    expect(played).toEqual([]);
  });

  it('ignores the retired kioskPlaySound key', async () => {
    writeAudioPref('sfx', true);
    localStorage.setItem('kioskPlaySound', '0');
    const { socket } = await connect();
    sendSound(socket, 'stone1');
    expect(played).toEqual(['stone1.wav']);
  });
});
