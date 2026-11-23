// 摆谱的快门声是 WebAudio 直接发声,不经 `Audio` 缓存 —— 所以单独钉一条:
// 它归「落子音效」那把开关(语音那把关的是七句引导语,不是这一声)。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { playShutter } from '../utils/baipuShutter';

const createOscillator = vi.fn(() => ({
  frequency: { value: 0 },
  connect: () => ({ connect: () => undefined }),
  start: vi.fn(),
  stop: vi.fn(),
  onended: null,
}));

const setValueAtTime = vi.fn();
const exponentialRampToValueAtTime = vi.fn();
class MockAudioContext {
  currentTime = 0;
  destination = {};
  createOscillator = createOscillator;
  createGain = () => ({
    gain: { setValueAtTime, exponentialRampToValueAtTime },
    connect: () => ({ connect: () => undefined }),
  });
  close = vi.fn();
}

describe('摆谱快门声认「落子音效」开关', () => {
  beforeEach(() => {
    localStorage.removeItem('kiosk_audio_sfx');
    createOscillator.mockClear();
    setValueAtTime.mockClear();
    exponentialRampToValueAtTime.mockClear();
    vi.stubGlobal('AudioContext', MockAudioContext);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.removeItem('kiosk_audio_sfx');
  });

  it('关掉之后不发声', () => {
    localStorage.setItem('kiosk_audio_sfx', 'false');
    playShutter();
    expect(createOscillator).not.toHaveBeenCalled();
  });

  it('开着(缺键即出厂)时发声并限制增益峰值至 0.08', () => {
    playShutter();
    expect(createOscillator).toHaveBeenCalledTimes(1);
    expect(exponentialRampToValueAtTime).toHaveBeenNthCalledWith(1, 0.08, 0.005);
  });
});
