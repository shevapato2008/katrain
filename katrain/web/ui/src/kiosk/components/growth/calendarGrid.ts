/**
 * 近一年练棋日历(屏 22,Fan 2026-09-22 提 —— 类似 GitHub profile 的贡献图)。
 *
 * **每格 = 当天下完的对局 + 当天新解出的题**(Fan 2026-09-22 按推荐拍板)。做题表只记每道题的
 * 首次解出时间,「哪天做了几次」历史上数不出来,所以只数「新解出」。
 *
 * **固定五档**(同日拍板):0 / 1–2 / 3–5 / 6–9 / 10+。不按个人分位数分档 —— 那样一周只下一局
 * 的人也会被涂成满格,颜色就不再说「练了多少」。
 */

export interface ActivityDay {
  /** `YYYY-MM-DD`,按客户端时区切的天(见 `getGrowthActivity` 的 `tzOffset`)。 */
  date: string;
  games: number;
  solved: number;
}

export interface CalendarCell {
  date: string;
  count: number;
  level: 0 | 1 | 2 | 3 | 4;
  today: boolean;
  /** 第一列里、窗口开始之前的那几天:占位不画(列要从周一对齐)。 */
  void: boolean;
}

export interface CalendarGrid {
  /** 按列排:每列 7 格,周一在最上。最后一格是今天,今天之后不画。 */
  cells: CalendarCell[];
  columns: number;
  months: { col: number; month: number }[];
  /** 窗口里有活动的天数 —— 屏上那个大数,和格子必须对得上。 */
  activeDays: number;
}

export const activityLevel = (n: number): CalendarCell['level'] =>
  n <= 0 ? 0 : n <= 2 ? 1 : n <= 5 ? 2 : n <= 9 ? 3 : 4;

const DAY = 86_400_000;
const parse = (iso: string) => Date.parse(`${iso}T00:00:00Z`);
const fmt = (t: number) => new Date(t).toISOString().slice(0, 10);
/** 周一 = 0 … 周日 = 6(中国的一周从周一开始,GitHub 那张从周日开始)。 */
const weekday = (t: number) => (new Date(t).getUTCDay() + 6) % 7;

export function calendarGrid(
  days: ActivityDay[],
  { endDate, windowDays = 365 }: { endDate: string; windowDays?: number },
): CalendarGrid {
  const end = parse(endDate);
  const first = end - (windowDays - 1) * DAY;
  const start = first - weekday(first) * DAY;
  const counts = new Map(days.map((d) => [d.date, (d.games || 0) + (d.solved || 0)]));

  const cells: CalendarCell[] = [];
  const monthStarts: { col: number; month: number }[] = [];
  let activeDays = 0;
  for (let t = start, i = 0; t <= end; t += DAY, i += 1) {
    const date = fmt(t);
    if (t < first) {
      cells.push({ date, count: 0, level: 0, today: false, void: true });
      continue;
    }
    const count = counts.get(date) ?? 0;
    if (count > 0) activeDays += 1;
    const d = new Date(t);
    if (d.getUTCDate() === 1 || t === first) monthStarts.push({ col: Math.floor(i / 7), month: d.getUTCMonth() + 1 });
    cells.push({ date, count, level: activityLevel(count), today: t === end, void: false });
  }

  // 月份标在「这个月第一天所在的那一列」上;离上一个标签不到 3 列就不标(两个字会压在一起)。
  // 第一列那个残缺的月份若紧挨着下一个月,丢的是它 —— 不是下一个月。
  if (monthStarts.length > 1 && monthStarts[1].col - monthStarts[0].col < 3) monthStarts.shift();
  const months: { col: number; month: number }[] = [];
  for (const m of monthStarts) {
    if (months.length === 0 || m.col - months[months.length - 1].col >= 3) months.push(m);
  }

  return { cells, columns: Math.ceil(cells.length / 7), months, activeDays };
}
