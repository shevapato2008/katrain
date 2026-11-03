import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { i18n } from '../../i18n';
import { API } from '../../api';
import { useMembershipI18n } from './useMembershipI18n';

async function language(lang: string, translations: Record<string, string> = {}) {
  vi.spyOn(API, 'getTranslations').mockResolvedValue({ translations });
  vi.spyOn(i18n, 'loadLiveTranslations').mockResolvedValue(undefined);
  await act(async () => { await i18n.loadTranslations(lang); });
}

afterEach(() => vi.restoreAllMocks());
describe('membership i18n presentation', () => {
  it('updates named templates and locale formatting after a language change', async () => {
    await language('cn');
    const { result } = renderHook(useMembershipI18n);
    expect(result.current.t('membership:test', '{points} 积分，共 {points}', { points: '3.01' })).toBe('3.01 积分，共 3.01');
    expect(result.current.countdown(561600)).toBe('6天12小时0分钟');
    await language('de', { 'membership:test': '{points} Punkte, insgesamt {points}', 'membership:countdown_days': '{days} Tage {hours} Std. {minutes} Min.' });
    expect(result.current.locale).toBe('de-DE');
    expect(result.current.t('membership:test', 'fallback', { points: '3,01' })).toBe('3,01 Punkte, insgesamt 3,01');
    expect(result.current.number(65.6, { minimumFractionDigits: 1 })).toBe('65,6');
    expect(result.current.countdown(561600)).toBe('6 Tage 12 Std. 0 Min.');
    expect(result.current.money(1204)).toContain('12,04');
    expect(result.current.money(1204)).toMatch(/[¥￥]/);
  });
  it('uses selected locales and Beijing time without changing source values', async () => {
    for (const [lang, locale] of [['cn', 'zh-CN'], ['tw', 'zh-TW'], ['jp', 'ja-JP'], ['ua', 'uk-UA']]) {
      await language(lang);
      const { result, unmount } = renderHook(useMembershipI18n);
      expect(result.current.locale).toBe(locale);
      expect(result.current.date('2026-11-03T18:05:00Z', true)).toBe(new Intl.DateTimeFormat(locale, { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date('2026-11-03T18:05:00Z')));
      unmount();
    }
  });
  it('identifies Chinese yuan instead of displaying an ambiguous yen symbol', async () => {
    await language('en');
    const { result } = renderHook(useMembershipI18n);
    expect(result.current.money(3000)).toBe('CN¥30');
    await language('jp');
    expect(result.current.money(3000)).toMatch(/元.*30/);
    expect(result.current.money(3000)).not.toMatch(/[¥￥]/);
  });
});
