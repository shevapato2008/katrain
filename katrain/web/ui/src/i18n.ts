import { API } from './api';

class I18n {
  private translations: Record<string, string> = {};
  private currentLang: string = 'en';

  async loadTranslations(lang: string) {
    try {
      const data = await API.getTranslations(lang);
      this.translations = data.translations;
      this.currentLang = lang;
    } catch (error) {
      console.error(`Failed to load translations for ${lang}`, error);
    }
  }

  t(key: string, defaultText?: string): string {
    return this.translations[key] || defaultText || key;
  }

  get lang() {
    return this.currentLang;
  }
}

export const i18n = new I18n();
