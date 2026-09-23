// 研究屏走的是这个 hook(useResearchSession → useSessionBase),不是 useGameSession ——
// 所以设置屏「落子音效」关掉之后,这里也得不响。桩的写法照搬 useGameSession.sound.test.tsx。
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { GameState } from '../api';
import { API } from '../api';
import { useSessionBase } from './useSessionBase';

vi.mock('../api', () => ({ API: { getState: vi.fn() } }));

const state = () => ({ game_id: 'g1', current_node_id: 1 }) as GameState;

const sockets: MockWebSocket[] = [];
class MockWebSocket {
  static OPEN = 1;
  readyState = MockWebSocket.OPEN;
  onmessage: ((event: MessageEvent) => void) | null = null;
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

const connect = async () => {
  const hook = renderHook(() => useSessionBase({ token: 'token' }));
  act(() => hook.result.current.setSessionId('session-1'));
  await waitFor(() => expect(sockets).toHaveLength(1));
  return sockets[0];
};

const sendStone = (socket: MockWebSocket) => {
  act(() => socket.onmessage?.({ data: JSON.stringify({ type: 'sound', data: { sound: 'stone' } }) } as MessageEvent));
};

describe('useSessionBase 的落子声认「落子音效」开关', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sockets.length = 0;
    played.length = 0;
    localStorage.removeItem('kiosk_audio_sfx');
    vi.mocked(API.getState).mockResolvedValue({ session_id: 'session-1', state: state() } as never);
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.stubGlobal('Audio', MockAudio);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.removeItem('kiosk_audio_sfx');
  });

  it('关掉之后不响', async () => {
    localStorage.setItem('kiosk_audio_sfx', 'false');
    sendStone(await connect());
    expect(played).toEqual([]);
  });

  it('从没设置过(缺键)时照响 —— 出厂是开的,galaxy 从不写这把键', async () => {
    sendStone(await connect());
    expect(played).toEqual(['stone.wav']);
  });
});
