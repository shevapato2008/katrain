import { cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const deferred = () => {
  let resolve!: () => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<void>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
class FakeAudio {
  static instances: FakeAudio[] = [];
  volume = 0.5;
  currentTime = 0;
  preload = '';
  constructor(public src = '') { FakeAudio.instances.push(this); }
  play = vi.fn(() => Promise.resolve());
  pause = vi.fn();
  cloneNode() { return new FakeAudio(this.src); }
}
let useSound: typeof import('./useSound').useSound;
const countdown = () => FakeAudio.instances.find(a => a.src.endsWith('countdownbeep.wav'))!;
beforeEach(async () => {
  vi.resetModules();
  localStorage.clear();
  FakeAudio.instances = [];
  vi.stubGlobal('Audio', FakeAudio);
  ({ useSound } = await import('./useSound'));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('useSound actual media attempts', () => {
  it('reports rejection as false and only resolved playback as true', async () => {
    const { result } = renderHook(useSound);
    countdown().play.mockRejectedValueOnce(new DOMException('blocked', 'NotAllowedError'));
    expect(await result.current.play('countdownbeep')).toBe(false);
    const pending = deferred();
    countdown().play.mockReturnValueOnce(pending.promise);
    let finished = false;
    const attempt = result.current.play('countdownbeep').then(ok => { finished = true; return ok; });
    await Promise.resolve();
    expect(finished).toBe(false);
    pending.resolve();
    expect(await attempt).toBe(true);
  });
  it('uses one cached countdown with an offset; stone and capture still overlap', async () => {
    const { result } = renderHook(useSound);
    await result.current.play('countdownbeep', { offsetSeconds: 2 });
    expect(countdown().currentTime).toBe(2);
    await result.current.play('countdownbeep');
    expect(FakeAudio.instances.filter(a => a.src.endsWith('countdownbeep.wav'))).toHaveLength(1);
    await result.current.play('stone');
    await result.current.play('stone');
    await result.current.play('capture');
    expect(FakeAudio.instances.filter(a => a.src.endsWith('stone1.wav'))).toHaveLength(3);
    expect(FakeAudio.instances.filter(a => a.src.endsWith('capturing.wav'))).toHaveLength(2);
  });
  it('does not play or prime when the existing global preference is muted', async () => {
    const { result } = renderHook(useSound);
    localStorage.setItem('kiosk_audio_sfx', 'false');
    expect(await result.current.play('countdownbeep')).toBe(false);
    expect(await result.current.unlock()).toBe(false);
    expect(countdown().play).not.toHaveBeenCalled();
  });
  it('stop invalidates a pending attempt and a late resolve cannot resurrect it', async () => {
    const { result } = renderHook(useSound);
    const pending = deferred();
    countdown().play.mockReturnValueOnce(pending.promise);
    const attempt = result.current.play('countdownbeep');
    result.current.stop('countdownbeep');
    expect(countdown().pause).toHaveBeenCalled();
    expect(countdown().currentTime).toBe(0);
    pending.resolve();
    expect(await attempt).toBe(false);
  });
  it('an old owner stop or late completion cannot stop the new owner', async () => {
    const old = renderHook(useSound);
    const next = renderHook(useSound);
    const pending = deferred();
    countdown().play.mockReturnValueOnce(pending.promise);
    const attempt = old.result.current.play('countdownbeep');
    expect(await next.result.current.play('countdownbeep', { offsetSeconds: 2 })).toBe(true);
    const pauses = countdown().pause.mock.calls.length;
    old.result.current.stop('countdownbeep');
    old.unmount();
    pending.resolve();
    expect(await attempt).toBe(false);
    expect(countdown().pause).toHaveBeenCalledTimes(pauses);
    expect(countdown().currentTime).toBe(2);
  });
  it('primes the same element silently and restores the normal volume', async () => {
    const { result } = renderHook(useSound);
    const pending = deferred();
    countdown().play.mockReturnValueOnce(pending.promise);
    const prime = result.current.unlock();
    expect(countdown().volume).toBe(0);
    pending.resolve();
    expect(await prime).toBe(true);
    expect(countdown().currentTime).toBe(0);
    expect(countdown().volume).toBe(0.5);
    expect(countdown().pause).toHaveBeenCalled();
  });
  it('a late prime cannot pause or mute a real countdown', async () => {
    const { result } = renderHook(useSound);
    const pending = deferred();
    countdown().play.mockReturnValueOnce(pending.promise);
    const prime = result.current.unlock();
    await result.current.play('countdownbeep', { offsetSeconds: 2 });
    const pauses = countdown().pause.mock.calls.length;
    pending.resolve();
    expect(await prime).toBe(false);
    expect(countdown().pause).toHaveBeenCalledTimes(pauses);
    expect(countdown().volume).toBe(0.5);
    expect(countdown().currentTime).toBe(2);
  });
  it('unmount stops an owned pending singleton', async () => {
    const { result, unmount } = renderHook(useSound);
    const pending = deferred();
    countdown().play.mockReturnValueOnce(pending.promise);
    const attempt = result.current.play('countdownbeep');
    unmount();
    pending.resolve();
    expect(await attempt).toBe(false);
  });
});
