import { API } from './api';

type TranslationCallback = () => void;

class I18n {
  private translations: Record<string, string> = {};
  private currentLang: string = 'en';
  private callbacks: Set<TranslationCallback> = new Set();

  async loadTranslations(lang: string) {
    try {
      const data = await API.getTranslations(lang);
      this.translations = data.translations;
      this.currentLang = lang;
      this.notify();
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

  subscribe(callback: TranslationCallback) {
    this.callbacks.add(callback);
    return () => { this.callbacks.delete(callback); };
  }

  private notify() {
    this.callbacks.forEach(cb => cb());
  }
}

export const i18n = new I18n();
(window as any).i18n = i18n;