/**
 * 「今天 15:40 / 昨天 / 前天 / 08-19」。**跨的是日历天不是 24 小时** ——
 * 23:50 存的谱,第二天 00:10 回来时说「今天」是错的。
 *
 * 两个消费者:屏 15 棋谱的「最近摆过」、屏 19 复盘的「历史对局」。
 * key 仍是 `kifu:*` —— 它们是屏 15 铸的、已经在闸的基线里,改名等于把两屏的文案一起动一次。
 */
export function whenLabel(ts: number, t: (k: string, d: string) => string): string {
  const then = new Date(ts);
  const midnight = new Date();
  midnight.setHours(0, 0, 0, 0);
  const days = Math.floor((midnight.getTime() - new Date(then).setHours(0, 0, 0, 0)) / 86400000);
  const hhmm = `${String(then.getHours()).padStart(2, '0')}:${String(then.getMinutes()).padStart(2, '0')}`;
  if (days <= 0) return `${t('kifu:today', '今天')} ${hhmm}`;
  if (days === 1) return t('kifu:yesterday', '昨天');
  if (days === 2) return t('kifu:day_before', '前天');
  return `${String(then.getMonth() + 1).padStart(2, '0')}-${String(then.getDate()).padStart(2, '0')}`;
}
