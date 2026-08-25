import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

import { readAudioPref, writeAudioPref, subscribeAudioPref } from './audioPrefs';
import { useSound } from '../hooks/useSound';
import { useVoice } from '../kiosk/hooks/useVoice';

/**
 * 声音开关。挡的是三件事,每一件都真发生过或差一点发生:
 *
 * ① **关不掉的静音**。原来 `useSound` 导出的 `setEnabled` 写在 `useRef` 里 ——
 *    每个 hook 实例各一份,而音频缓存是模块级的。A 组件静音,B 组件照响。
 *    它零调用点,所以从来没人发现;接到设置开关上的那天才会炸。
 * ② **两把混成一把**。落子音效和实体盘引导语不是一件事。
 * ③ **读不出来就静音**。默认必须是**开** —— 隐私模式下 localStorage 抛异常,
 *    「抛了就当关」会让一台好盒子悄悄变哑,而且屏上写着「开」。
 */

const played: string[] = [];

class FakeAudio {
  src: string;
  volume = 1;
  preload = '';
  constructor(src = '') { this.src = src; }
  play() { played.push(this.src); return Promise.resolve(); }
  pause() { /* no-op */ }
  cloneNode() { return new FakeAudio(this.src); }
}

beforeEach(() => {
  played.length = 0;
  localStorage.clear();
  vi.stubGlobal('Audio', FakeAudio);
});
afterEach(() => vi.unstubAllGlobals());

describe('audioPrefs —— 出厂是开的,读不出来也是开的', () => {
  it('没存过 ⇒ 两把都开', () => {
    expect(readAudioPref('sfx')).toBe(true);
    expect(readAudioPref('voice')).toBe(true);
  });

  it('存过就照存的来,而且两把互不影响', () => {
    writeAudioPref('sfx', false);
    expect(readAudioPref('sfx')).toBe(false);
    expect(readAudioPref('voice')).toBe(true);
  });

  it('值认不出来 ⇒ 当开', () => {
    localStorage.setItem('kiosk_audio_sfx', 'yes-please');
    expect(readAudioPref('sfx')).toBe(true);
  });

  it('localStorage 整个抛异常(隐私模式)⇒ 当开,不是当关', () => {
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('denied');
    });
    expect(readAudioPref('sfx')).toBe(true);
    spy.mockRestore();
  });

  it('存不下也要让本次会话生效 —— 照样通知订阅者', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('quota');
    });
    const seen = vi.fn();
    const off = subscribeAudioPref(seen);
    writeAudioPref('sfx', false);
    expect(seen).toHaveBeenCalled();
    off();
    spy.mockRestore();
  });

  it('退订之后不再收到通知', () => {
    const seen = vi.fn();
    subscribeAudioPref(seen)();
    writeAudioPref('voice', false);
    expect(seen).not.toHaveBeenCalled();
  });
});

describe('播放那一侧真的读它 —— 判据不落在键名上', () => {
  it('音效关掉之后 play 一声不响', () => {
    const { result } = renderHook(() => useSound());
    act(() => result.current.play('stone'));
    expect(played).toHaveLength(1);

    act(() => writeAudioPref('sfx', false));
    act(() => result.current.play('stone'));
    expect(played).toHaveLength(1);   // 没多出来
  });

  // ① 那条 bug 的判据:**在别处静音,这里也要哑**。
  // 老实现里 `enabledRef` 每个实例一份 ⇒ 这一条必红。
  it('一处关掉,另一处也哑 —— 静音是全局的,不是每个组件各一份', () => {
    const a = renderHook(() => useSound());
    const b = renderHook(() => useSound());
    act(() => writeAudioPref('sfx', false));
    act(() => a.result.current.play('stone'));
    act(() => b.result.current.play('capture'));
    expect(played).toEqual([]);
  });

  it('开关是**现读**的 —— 设置屏可以在任意一屏开着的时候改', () => {
    const { result } = renderHook(() => useSound());
    act(() => writeAudioPref('sfx', false));
    act(() => result.current.play('stone'));
    act(() => writeAudioPref('sfx', true));
    act(() => result.current.play('stone'));
    expect(played).toHaveLength(1);
  });

  it('语音关掉之后 speak 一声不响,而且不影响音效', () => {
    const voice = renderHook(() => useVoice());
    const sound = renderHook(() => useSound());
    act(() => writeAudioPref('voice', false));

    act(() => voice.result.current.speak('place_black'));
    expect(played).toEqual([]);

    act(() => sound.result.current.play('stone'));
    expect(played).toHaveLength(1);   // 另一把没被连累
  });
});
