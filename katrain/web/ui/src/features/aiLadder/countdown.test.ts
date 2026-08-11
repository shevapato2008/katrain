import { describe, expect, it } from 'vitest';
import { formatCountdown } from './countdown';

describe('formatCountdown', () => {
  it.each([
    [252_000, '4:12'],
    [59_000, '0:59'],
    [9_000, '0:09'],
    [0, '0:00'],
    [-5_000, '0:00'],
    [3_800_000, '1:03:20'],
  ])('%i 毫秒 → %s', (ms, text) => {
    expect(formatCountdown(ms)).toBe(text);
  });

  it('向上取整,好让最后一秒显示 0:01 而不是 0:00', () => {
    // 显示 0:00 却还按不动,是这块屏最不该出现的那一句。
    expect(formatCountdown(1)).toBe('0:01');
  });
});
