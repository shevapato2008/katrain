import { useTranslation } from '../../hooks/useTranslation';

export type MembershipTranslate = (key: string, defaultText: string, values?: Record<string, string | number>) => string;

const locales: Record<string, string> = {
  cn: 'zh-CN', tw: 'zh-TW', jp: 'ja-JP', ua: 'uk-UA', en: 'en-US',
  ko: 'ko-KR', de: 'de-DE', es: 'es-ES', fr: 'fr-FR', ru: 'ru-RU', tr: 'tr-TR',
};

/** Display only: never feed localized values back into quotas, prices or request identity. */
export function useMembershipI18n() {
  const { t: translate, lang } = useTranslation();
  const locale = locales[lang] ?? 'en-US';
  const t: MembershipTranslate = (key, defaultText, values) => translate(key, defaultText).replace(
    /\{(\w+)\}/g, (placeholder, name: string) => values && Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : placeholder,
  );
  const number = (value: number, options?: Intl.NumberFormatOptions) => new Intl.NumberFormat(locale, options).format(value);
  const date = (value?: string | null, full = false) => value && Number.isFinite(Date.parse(value))
    ? new Intl.DateTimeFormat(locale, {
      timeZone: 'Asia/Shanghai', year: full ? 'numeric' : undefined,
      month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
    }).format(new Date(value)) : t('membership:date_pending', '待确认');
  const countdown = (seconds: number | null) => {
    if (seconds === null) return t('membership:time_pending', '时间待确认');
    if (seconds <= 0) return t('membership:quota_refresh_pending', '正在确认最新额度');
    const days = Math.floor(seconds / 86400);
    const values = { days: number(days), hours: number(Math.floor(seconds % 86400 / 3600)), minutes: number(Math.floor(seconds % 3600 / 60)) };
    return days ? t('membership:countdown_days', '{days}天{hours}小时{minutes}分钟', values)
      : t('membership:countdown_hours', '{hours}小时{minutes}分钟', values);
  };
  const money = (fen: number) => number(fen / 100, { style: 'currency', currency: 'CNY', currencyDisplay: 'symbol', minimumFractionDigits: 0, maximumFractionDigits: 2 });
  return { t, lang, locale, date, countdown, money, number };
}
