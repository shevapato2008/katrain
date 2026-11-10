import { useTranslation } from '../../hooks/useTranslation';
import { kioskText, type KioskMessageKey } from '../appearance/messages';

/** OGS catalog IDs differ from the Go UI and kifu locale IDs. */
export const OGS_COURSE_LANGUAGE: Record<string, string> = { cn: 'zh-cn', tw: 'zh-tw', en: 'en', jp: 'ja', ko: 'ko' };
export function useOgsLocale() {
  const { lang } = useTranslation();
  return {
    language: OGS_COURSE_LANGUAGE[lang] ?? 'en',
    text: (key: KioskMessageKey, params?: Record<string, string | number>) => kioskText(lang, key, params),
  };
}
