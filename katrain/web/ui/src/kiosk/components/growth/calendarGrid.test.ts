import { describe, it, expect } from 'vitest';
import { activityLevel, calendarGrid } from './calendarGrid';

const day = (date: string, games = 0, solved = 0) => ({ date, games, solved });
// 2026-09-22 是周二
const END = { endDate: '2026-09-22', windowDays: 365 };

describe('activityLevel —— Fan 2026-09-22 定的固定五档', () => {
  it.each([[0, 0], [1, 1], [2, 1], [3, 2], [5, 2], [6, 3], [9, 3], [10, 4], [40, 4]])('%i 次 → 第 %i 档', (n, lv) => {
    expect(activityLevel(n)).toBe(lv);
  });
});

describe('calendarGrid', () => {
  it('一年 53 列、每列 7 格、周一在最上;最后一格就是今天,今天之后不画', () => {
    const g = calendarGrid([], END);
    expect(g.columns).toBe(53);
    expect(g.cells).toHaveLength(52 * 7 + 2); // 最后一列只到周二
    const last = g.cells[g.cells.length - 1];
    expect(last).toMatchObject({ date: '2026-09-22', today: true, void: false });
    // 第一列从 2025-09-22(周一)开始,窗口第一天是 2025-09-23 —— 周一那格在窗口外
    expect(g.cells[0]).toMatchObject({ date: '2025-09-22', void: true });
    expect(g.cells[1]).toMatchObject({ date: '2025-09-23', void: false });
  });

  it('每格 = 当天下完的对局 + 新解出的题;活跃天数只数窗口里的', () => {
    const g = calendarGrid([
      day('2026-09-20', 2, 1),
      day('2026-09-21', 0, 7),
      day('2025-09-01', 5, 5), // 窗口外:不画、不算
    ], END);
    const at = (d: string) => g.cells.find((c) => c.date === d)!;
    expect(at('2026-09-20')).toMatchObject({ count: 3, level: 2 });
    expect(at('2026-09-21')).toMatchObject({ count: 7, level: 3 });
    expect(g.activeDays).toBe(2);
  });

  it('月份标在这个月第一天所在的那一列,挨得太近的不标(不压字)', () => {
    const g = calendarGrid([], END);
    expect(g.months.map((m) => m.month)).toEqual([10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
    g.months.slice(1).forEach((m, i) => expect(m.col - g.months[i].col).toBeGreaterThanOrEqual(3));
  });
});
