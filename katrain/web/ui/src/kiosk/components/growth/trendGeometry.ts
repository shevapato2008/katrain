import type { GrowthTrendPoint } from '../../api/growthApi';

/** 画布坐标系(与国象样稿 `.spark` 的 viewBox 同形)。svg 用 `preserveAspectRatio="none"` 铺满容器。 */
export const TREND_W = 600;
export const TREND_H = 64;

export interface TrendGeometry {
  /** 折线的 path `d`。 */
  line: string;
  /** 折线下方的淡填充(闭合到底边)。 */
  area: string;
  points: { x: number; y: number; point: GrowthTrendPoint }[];
  /**
   * 末端点与最高点都用**百分比**给 —— 它们画成 HTML,不画进 svg:svg 是
   * `preserveAspectRatio="none"`,里面的圆会被横向拉成椭圆、字会被拉宽(屏 20 修过同一颗点)。
   */
  end: { xPct: number; yPct: number };
  peak: { xPct: number; yPct: number; point: GrowthTrendPoint; flip: boolean };
}

const DAY_MS = 86_400_000;
const dayNumber = (iso: string) => Date.parse(`${iso}T00:00:00Z`) / DAY_MS;

/**
 * 近 N 天档位折线。
 *
 * **横轴是那 N 天本身**:窗口最后一天(`endDate`,通常是今天)在最右边,往前 N−1 天在最左边。
 * 不按点的序号排,也不把首末两点拉满全宽 —— 十天没下棋屏上就是一段长横距,
 * 窗口前半段没下左边就是空的。按序号画会把「十天没下」画成「天天在下」。
 *
 * **纵轴是档位**(越大越强),上面比下面多留一点:最高点的标注要落在框里,不能贴着顶边。
 *
 * 窗口里少于两个点返回 `null`:**一个点不是趋势**,画出来是一条没有斜率的线,读者会读成「持平」。
 */
export function trendGeometry(
  points: GrowthTrendPoint[],
  { endDate, days }: { endDate: string; days: number },
): TrendGeometry | null {
  const end = dayNumber(endDate);
  const span = Math.max(1, days - 1);
  // 窗口外的点**丢掉,不夹到边上**:服务端时钟快一天、或者窗口比数据短时,
  // 夹过去会在最右 / 最左画出一根假的竖线。
  const inWindow = points.filter((p) => {
    const offset = end - dayNumber(p.date);
    return offset >= 0 && offset <= span;
  });
  if (inWindow.length < 2) return null;
  const rungs = inWindow.map((p) => p.rung);
  const lo = Math.min(...rungs) - 0.5;
  const hi = Math.max(...rungs) + 1; // 全程同一档时 hi − lo 仍是 1.5,不除以 0
  const xy = inWindow.map((p) => {
    const offset = end - dayNumber(p.date);
    return {
      x: ((span - offset) / span) * TREND_W,
      y: TREND_H - ((p.rung - lo) / (hi - lo)) * (TREND_H - 6) - 3,
      point: p,
    };
  });
  const line = xy.map((q, i) => `${i === 0 ? 'M' : 'L'}${q.x.toFixed(1)} ${q.y.toFixed(1)}`).join(' ');
  const first = xy[0];
  const last = xy[xy.length - 1];
  const area = `${line} L${last.x.toFixed(1)} ${TREND_H} L${first.x.toFixed(1)} ${TREND_H} Z`;

  // 最高档;并列时取**最近**那一次 —— 「最近还到过」比「很早到过一次」更该标。
  let peakIndex = 0;
  xy.forEach((q, i) => { if (q.point.rung >= xy[peakIndex].point.rung) peakIndex = i; });
  const peak = xy[peakIndex];
  const pctX = (x: number) => (x / TREND_W) * 100;
  const pctY = (y: number) => (y / TREND_H) * 100;
  return {
    line,
    area,
    points: xy,
    end: { xPct: pctX(last.x), yPct: pctY(last.y) },
    // 峰值横向过 55% 时标注翻到点的左边,否则会顶出画框(共享规范 §5)。
    peak: { xPct: pctX(peak.x), yPct: pctY(peak.y), point: peak.point, flip: pctX(peak.x) > 55 },
  };
}
