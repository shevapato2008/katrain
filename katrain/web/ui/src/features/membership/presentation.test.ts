import { describe, expect, it } from 'vitest';
import { formatPoints, formatSavings, planReportCopy, usagePercent, createServerClock, remainingSeconds } from './presentation';

describe('membership presentation', () => {
  it('shows the existing integer wallet as points with two decimals', () => {
    expect(formatPoints(0)).toBe('0.00');
    expect(formatPoints(301)).toBe('3.01');
    expect(formatPoints(1204)).toBe('12.04');
    expect(formatPoints(null)).toBe('—');
    expect(formatPoints(undefined)).toBe('—');
  });

  it('uses service supplied savings and weekly report references', () => {
    expect([56.8, 63.5, 72.5].map(formatSavings)).toEqual(['56.8%', '63.5%', '72.5%']);
    expect([10, 30, 80].map(planReportCopy)).toEqual([
      '普通报告，每周最多约10盘', '普通报告，每周最多约30盘', '普通报告，每周最多约80盘',
    ]);
  });

  it('keeps the term and week percentages independent and unknown distinct from zero', () => {
    expect(usagePercent({ limit: 27090, used: 9030, reserved: 301, remaining: 17759, percent: 65.6 }, true)).toBe('65.6%');
    expect(usagePercent({ limit: 9030, used: 1505, reserved: 301, remaining: 7224, percent: 80 }, true)).toBe('80.0%');
    expect(usagePercent({ limit: 9030, used: 9030, reserved: 0, remaining: 0, percent: 0 }, true)).toBe('0.0%');
    expect(usagePercent(null, true)).toBe('—');
    expect(usagePercent({ percent: 0 }, false)).toBe('—');
    expect(usagePercent({ percent: Number.NaN }, true)).toBe('—');
  });

  it('uses monotonic elapsed time and stops at zero without issuing local quota', () => {
    const clock = createServerClock('2026-11-02T00:00:00Z', 100);
    expect(remainingSeconds('2026-11-02T00:00:10Z', clock, 1100)).toBe(9);
    expect(remainingSeconds('2026-11-02T00:00:10Z', clock, 11100)).toBe(0);
    expect(remainingSeconds(null, clock, 11100)).toBeNull();
  });
});
