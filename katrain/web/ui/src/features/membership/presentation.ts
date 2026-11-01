export const formatPoints = (credits: number | null | undefined): string =>
  typeof credits === 'number' && Number.isSafeInteger(credits) && credits >= 0 ? (credits / 100).toFixed(2) : '—';

export const formatSavings = (percent: number): string => `${percent.toFixed(1)}%`;
export const planReportCopy = (weeklyReports: number): string => `普通报告，每周最多约${weeklyReports}盘`;

export const usagePercent = (period: { percent: number } | null | undefined, enabled: boolean): string =>
  enabled && period && Number.isFinite(period.percent) && period.percent >= 0 && period.percent <= 100
    ? `${period.percent.toFixed(1)}%` : '—';

export interface ServerClock { epochMs: number; monotonicMs: number }
export const createServerClock = (serverNow: string, monotonicMs = performance.now()): ServerClock =>
  ({ epochMs: Date.parse(serverNow), monotonicMs });

/** Wall-clock changes never move an accepted server snapshot backwards. */
export const remainingSeconds = (resetAt: string | null | undefined, clock: ServerClock, monotonicMs = performance.now()): number | null => {
  if (!resetAt || !Number.isFinite(clock.epochMs)) return null;
  const deadline = Date.parse(resetAt);
  if (!Number.isFinite(deadline)) return null;
  return Math.max(0, Math.ceil((deadline - clock.epochMs - Math.max(0, monotonicMs - clock.monotonicMs)) / 1000));
};
