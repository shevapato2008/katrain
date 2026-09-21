import { describe, it, expect } from 'vitest';
import { scheduleLabel } from './scheduleLabel';

const t = (_k: string, d: string) => d;
const at = (iso: string) => new Date(iso).getTime();

describe('scheduleLabel', () => {
  const now = at('2026-09-20T20:00:00');

  it('同一日历天写「今天 HH:mm」', () => {
    expect(scheduleLabel(at('2026-09-20T23:30:00'), t, now)).toBe('今天 23:30');
  });

  // 跨的是**日历天**不是 24 小时:23:50 看的赛程,次日 00:10 开赛要写「明天」。
  it('下一个日历天写「明天 HH:mm」,哪怕只差 20 分钟', () => {
    expect(scheduleLabel(at('2026-09-21T00:10:00'), t, at('2026-09-20T23:50:00'))).toBe('明天 00:10');
  });

  it('更远的写「MM-DD HH:mm」', () => {
    expect(scheduleLabel(at('2026-09-23T11:00:00'), t, now)).toBe('09-23 11:00');
  });

  it('已经过去的时刻照实写日期,不写「今天」冒充还没开始', () => {
    expect(scheduleLabel(at('2026-09-18T11:00:00'), t, now)).toBe('09-18 11:00');
    expect(scheduleLabel(at('2026-09-20T09:00:00'), t, now)).toBe('09-20 09:00');
  });
});
