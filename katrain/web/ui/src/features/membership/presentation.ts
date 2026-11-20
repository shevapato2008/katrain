import type { MembershipTranslate } from './useMembershipI18n';

export const formatPoints = (credits: number | null | undefined): string =>
  typeof credits === 'number' && Number.isSafeInteger(credits) && credits >= 0 ? (credits / 100).toFixed(2) : '—';

export const formatSavings = (percent: number): string => `${percent.toFixed(1)}%`;
export const planReportCopy = (weeklyReports: number, t?: MembershipTranslate, number: (value: number) => string = String): string =>
  t ? t('membership:weekly_report_reference', '普通报告，每周最多约{reports}盘', { reports: number(weeklyReports) })
    : `普通报告，每周最多约${weeklyReports}盘`;

export type MembershipErrorCode = 'insufficient' | 'quote_expired' | 'service_paused' | 'service_unavailable'
  | 'verification_required' | 'operation_running' | 'busy' | 'result_expired' | 'quote_failed'
  | 'position_failed' | 'position_refunded' | 'position_unavailable' | 'position_changed' | 'analysis_login_required'
  | 'report_login_required' | 'report_failed' | 'report_missing';

/** Read only known billing codes; arbitrary server exception messages are never UI copy. */
export function membershipErrorCode(error: unknown, fallback: MembershipErrorCode): MembershipErrorCode {
  const carrier = (error && typeof error === 'object' ? error : {}) as { status?: number; detail?: unknown; body?: unknown; message?: unknown };
  let detail = carrier.detail;
  if (!detail && typeof carrier.body === 'string') {
    try { detail = (JSON.parse(carrier.body) as { detail?: unknown })?.detail; } catch { /* A gateway may return HTML. */ }
  }
  const code = typeof detail === 'string' ? detail : detail && typeof detail === 'object' && 'code' in detail ? detail.code : carrier.message;
  switch (code) {
    case 'position_changed': return 'position_changed';
    case 'insufficient_credits': case 'wallet_cap_exceeded': return 'insufficient';
    case 'invalid_or_expired_quote': case 'quote_mismatch': case 'quote_and_idempotency_required': return 'quote_expired';
    case 'membership_paused': return 'service_paused';
    case 'membership_legacy': case 'membership_disabled': case 'need_online_billing': return 'service_unavailable';
    case 'verification_required': return 'verification_required';
    case 'operation_in_progress': case 'legacy_report_in_progress': return 'operation_running';
    case 'queue_full': case 'rate_limited': return 'busy';
    case 'result_expired': case 'owned_result_unavailable': case 'report_result_unavailable': return 'result_expired';
    default:
      if (carrier.status === 402) return 'insufficient';
      if (carrier.status === 401) return 'verification_required';
      if (carrier.status === 429) return 'busy';
      if (carrier.status === 502 || carrier.status === 503 || carrier.status === 504) return 'service_unavailable';
      return fallback;
  }
}

export function membershipErrorText(code: MembershipErrorCode, t: MembershipTranslate): string {
  switch (code) {
    case 'position_changed': return t('membership:error_position_changed', '局面已变化，请重新点击分析并确认报价');
    case 'insufficient': return t('membership:error_insufficient', '会员额度和API积分不足，请前往会员页查看');
    case 'quote_expired': return t('membership:error_quote_expired', '报价已过期或与当前请求不一致，请确认最新报价后重试');
    case 'service_paused': return t('membership:error_service_paused', '分析服务暂停，请稍后重试');
    case 'service_unavailable': return t('membership:error_service_unavailable', '分析服务暂不可用，请稍后重试');
    case 'verification_required': return t('membership:error_verification_required', '请先完成登录验证后重试');
    case 'operation_running': return t('membership:error_operation_running', '分析仍在进行，请稍后重试查询');
    case 'busy': return t('membership:error_service_busy', '当前请求较多，请稍后重试');
    case 'result_expired': return t('membership:error_result_expired', '分析结果已过期或暂不可用，请重新分析');
    case 'quote_failed': return t('membership:error_quote_failed', '报价失败，请重试');
    case 'position_failed': return t('membership:error_position_failed', '分析未完成，请重试');
    case 'position_refunded': return t('membership:error_position_refunded', '分析未完成，已退还本次消耗，请重试');
    case 'position_unavailable': return t('membership:error_position_unavailable', '当前服务未开放单局面分析');
    case 'analysis_login_required': return t('membership:error_analysis_login_required', '请先登录后使用分析');
    case 'report_login_required': return t('membership:error_report_login_required', '请先登录后创建报告');
    case 'report_failed': return t('membership:error_report_failed', '创建报告失败，请重试');
    case 'report_missing': return t('membership:error_report_missing', '报告不存在，请刷新后重试');
  }
}

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
