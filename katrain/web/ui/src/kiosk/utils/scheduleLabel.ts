/**
 * 赛程时刻的标签:「今天 19:00 / 明天 11:00 / 09-23 11:00」。说的是**将来** ——
 * 说过去的是 `whenLabel.ts`(今天 / 昨天 / 前天 / MM-DD),方向相反,不共用。
 *
 * **跨的是日历天,不是 24 小时** —— 23:50 看到的、次日 00:10 开赛的那一场,
 * 说「今天」是错的(`whenLabel.ts` 为过去的那一半写过同一条理由)。
 * 已经过去的时刻一律落到日期格式:说「今天」会让人以为还没开始。
 */
export function scheduleLabel(ts: number, t: (k: string, d: string) => string, now = Date.now()): string {
  const then = new Date(ts);
  const hhmm = `${String(then.getHours()).padStart(2, '0')}:${String(then.getMinutes()).padStart(2, '0')}`;
  const mmdd = `${String(then.getMonth() + 1).padStart(2, '0')}-${String(then.getDate()).padStart(2, '0')}`;
  // round 不是 floor:跨夏令时那天两个零点之间差 23 或 25 小时。
  const days = Math.round(
    (new Date(ts).setHours(0, 0, 0, 0) - new Date(now).setHours(0, 0, 0, 0)) / 86400000,
  );
  if (days === 0 && ts >= now) return `${t('live:today', '今天')} ${hhmm}`;
  if (days === 1) return `${t('live:tomorrow', '明天')} ${hhmm}`;
  return `${mmdd} ${hhmm}`;
}
