import { describe, it, expect } from 'vitest';
import { trendGeometry, TREND_W } from './trendGeometry';

const pt = (date: string, rung: number) => ({ date, rung, rank_name: `${rung}档` });
const WINDOW = { endDate: '2026-09-30', days: 30 };

describe('trendGeometry', () => {
  it('两个点以上才画;一个点不画(**一个点不是趋势**)', () => {
    expect(trendGeometry([pt('2026-09-20', 10)], WINDOW)).toBeNull();
    expect(trendGeometry([], WINDOW)).toBeNull();
    expect(trendGeometry([pt('2026-09-20', 10), pt('2026-09-21', 11)], WINDOW)).not.toBeNull();
  });

  it('最高点标在最强那一档上(档位越大越强);并列时取最近那一次', () => {
    const out = trendGeometry([pt('2026-09-10', 14), pt('2026-09-20', 12), pt('2026-09-25', 14)], WINDOW)!;
    expect(out.peak.point.date).toBe('2026-09-25');
    expect(out.peak.point.rung).toBe(14);
  });

  it('全程同一档时也画得出来(不除以 0)', () => {
    const out = trendGeometry([pt('2026-09-20', 10), pt('2026-09-21', 10)], WINDOW)!;
    expect(out.line).toMatch(/^M/);
    expect(Number.isFinite(out.peak.yPct)).toBe(true);
  });

  // 横坐标按**日期**落在「近 30 天」这条轴上,不按点的序号、也不把首末两点拉满全宽:
  // 十天没下棋,屏上就该是一段长横距;窗口前半段没下,左边就该是空的。
  it('横坐标按日期落在 30 天窗口上,不按序号', () => {
    const out = trendGeometry([pt('2026-09-11', 10), pt('2026-09-21', 11), pt('2026-09-22', 12)], WINDOW)!;
    const xs = out.points.map((p) => p.x);
    expect(xs[1] - xs[0]).toBeGreaterThan(xs[2] - xs[1]);
    expect(xs[0]).toBeGreaterThan(0);                    // 9-11 不是窗口第一天 ⇒ 左边留空
    expect(xs[2]).toBeLessThan(TREND_W);                 // 9-22 不是窗口最后一天 ⇒ 右边也留空
  });

  it('窗口最后一天落在最右边', () => {
    const out = trendGeometry([pt('2026-09-01', 10), pt('2026-09-30', 11)], WINDOW)!;
    expect(out.points[0].x).toBeCloseTo(0, 5);
    expect(out.points[1].x).toBeCloseTo(TREND_W, 5);
  });

  // 最高点靠右时标注翻到点的左边,否则会顶出画框(共享规范 §5 的硬性)。
  it('最高点靠右时标注翻到左边', () => {
    expect(trendGeometry([pt('2026-09-02', 10), pt('2026-09-29', 12)], WINDOW)!.peak.flip).toBe(true);
    expect(trendGeometry([pt('2026-09-02', 12), pt('2026-09-29', 10)], WINDOW)!.peak.flip).toBe(false);
  });

  // 窗口外的点(服务端时钟快了一天、或者窗口比数据短)**丢掉,不夹到边上** ——
  // 夹到边上会在最右 / 最左画出一根假的竖线。
  it('窗口外的点丢掉,不夹到边上', () => {
    const out = trendGeometry([
      pt('2026-08-01', 9),   // 早于窗口第一天 9-01
      pt('2026-09-10', 10), pt('2026-09-20', 11),
      pt('2026-10-02', 15),  // 晚于窗口最后一天
    ], WINDOW)!;
    expect(out.points.map((p) => p.point.date)).toEqual(['2026-09-10', '2026-09-20']);
    expect(out.peak.point.rung).toBe(11);
    expect(trendGeometry([pt('2026-09-10', 10), pt('2026-10-02', 15)], WINDOW)).toBeNull();
  });
});
