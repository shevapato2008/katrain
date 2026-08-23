/**
 * 一段时长 →「6分12秒」/「45秒」。
 *
 * 两个 msgid 是**已经在 PO 里的**（`research:time_min_sec` = `{min}分{sec}秒`、
 * `research:time_sec` = `{sec}秒`），占位符名字照旧 —— 不新铸键，也不给旧键换一套
 * 占位符约定（那条坑写在 [[interpolate]] 的注释里：`t()` 是「翻译表赢」，
 * 换了约定就会把数字连同占位符一起吞掉）。
 *
 * 满一分钟时秒补两位（`6分02秒`），不满一分钟时不补（`8秒`）—— 前者是在读一个跨位的数，
 * 后者补零只会让人以为还有分位。这就是 galaxy 研究屏用了很久的那套写法，
 * 本文件把它从 `kiosk/pages/ResearchPage.tsx` 抽出来，屏 20 是第二个消费者。
 *
 * 入参是**秒**，调用方自己把毫秒收成秒 —— 谁在做那次除法应当在调用处看得见。
 */
export function durationLabel(seconds: number, t: (key: string, fallback: string) => string): string {
  const whole = Math.max(0, Math.floor(seconds));
  if (whole >= 60) {
    return t('research:time_min_sec', '{min}分{sec}秒')
      .replace('{min}', String(Math.floor(whole / 60)))
      .replace('{sec}', String(whole % 60).padStart(2, '0'));
  }
  return t('research:time_sec', '{sec}秒').replace('{sec}', String(whole));
}

/**
 * 一对 ISO 时间戳 → 秒数；**任何一头缺、解析不出、或者算出负数都返回 `null`**。
 *
 * 负数不是「收成 0」而是没有答案：那意味着两个章的时钟对不上（迁移过的行、
 * 换过机器的部署），这时候屏上写「用了 0 秒」是编的。返回 `null` 让调用方退回
 * 那句本来就真的话。
 *
 * 两个值出自同一列，所以「带不带时区」两边一致，差值不受影响
 * （SQLite 上都不带、PG 上都带）。
 */
export function elapsedSeconds(startedAt: string | null, completedAt: string | null): number | null {
  if (!startedAt || !completedAt) return null;
  const start = new Date(startedAt).getTime();
  const end = new Date(completedAt).getTime();
  if (Number.isNaN(start) || Number.isNaN(end)) return null;
  const seconds = (end - start) / 1000;
  return seconds < 0 ? null : seconds;
}
