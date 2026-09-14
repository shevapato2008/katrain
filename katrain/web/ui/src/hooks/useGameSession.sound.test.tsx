import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useGameSession } from './useGameSession';
import { writeAudioPref } from '../utils/audioPrefs';

vi.mock('../api', () => ({
  API: { getState: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }) },
}));

/**
 * 提示音只留一把(v2 §4.1 / P9):对局里的落子声读 `audioPrefs` 的 `sfx` ——
 * 和设置屏「落子音效」、屏 04「落子提示音」是同一把。以前读的是另一把 `kioskPlaySound`,
 * 设置里关了、对局照样响。
 */
let lastWs: { onmessage: ((e: MessageEvent) => void) | null } | null = null;
class MockWebSocket {
  static OPEN = 1;
  readyState = 1;
  onmessage: ((event: MessageEvent) => void) | null = null;
  close = vi.fn();
  send = vi.fn();
  constructor() { lastWs = this; }
}
const play = vi.fn(() => Promise.resolve());
class MockAudio { currentTime = 0; play = play; }

async function sendSoundFrame() {
  const { result } = renderHook(() => useGameSession({ token: 't' }));
  act(() => result.current.setSessionId('s1'));
  await waitFor(() => expect(lastWs?.onmessage).toBeTruthy());
  act(() => lastWs!.onmessage!({ data: JSON.stringify({ type: 'sound', data: { sound: 'stone1' } }) } as MessageEvent));
}

describe('useGameSession 落子声读全局 sfx 开关', () => {
  beforeEach(() => {
    vi.clearAllMocks(); lastWs = null;
    localStorage.removeItem('kiosk_audio_sfx'); localStorage.removeItem('kioskPlaySound');
    vi.stubGlobal('WebSocket', MockWebSocket); vi.stubGlobal('Audio', MockAudio);
  });
  afterEach(() => vi.unstubAllGlobals());

  it('设置里把音效关了:对局不出声', async () => {
    writeAudioPref('sfx', false);
    await sendSoundFrame();
    expect(play).not.toHaveBeenCalled();
  });

  it('音效开着:旧键 kioskPlaySound=0 残留也不再静音(那把键已删)', async () => {
    writeAudioPref('sfx', true);
    localStorage.setItem('kioskPlaySound', '0');
    await sendSoundFrame();
    expect(play).toHaveBeenCalledTimes(1);
  });
});
