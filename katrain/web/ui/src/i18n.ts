import { API } from './api';
import { LiveAPI } from './galaxy/api/live';

type TranslationCallback = () => void;

interface LiveTranslations {
  players: Record<string, string>;
  tournaments: Record<string, string>;
  rounds: Record<string, string>;
  rules: Record<string, string>;
}

class I18n {
  private translations: Record<string, string> = {};
  private liveTranslations: LiveTranslations | null = null;
  private currentLang: string = 'en';
  private callbacks: Set<TranslationCallback> = new Set();
  private liveTranslationsLoading: boolean = false;

  async loadTranslations(lang: string) {
    try {
      const data = await API.getTranslations(lang);
      this.translations = data.translations;
      this.currentLang = lang;
      // Also load live translations when language changes
      await this.loadLiveTranslations(lang);
      this.notify();
    } catch (error) {
      console.error(`Failed to load translations for ${lang}`, error);
    }
  }

  async loadLiveTranslations(lang: string) {
    if (this.liveTranslationsLoading) return;
    this.liveTranslationsLoading = true;
    try {
      const data = await LiveAPI.getTranslations(lang);
      this.liveTranslations = {
        players: data.players || {},
        tournaments: data.tournaments || {},
        rounds: data.rounds || {},
        rules: data.rules || {},
      };
    } catch (error) {
      console.error('Failed to load live translations', error);
      this.liveTranslations = null;
    } finally {
      this.liveTranslationsLoading = false;
    }
  }

  t(key: string, defaultText?: string): string {
    return this.translations[key] || defaultText || key;
  }

  /**
   * Translate a player name to the current language.
   * Falls back to the original name if no translation is found.
   */
  translatePlayer(name: string): string {
    if (!name) return name;
    return this.liveTranslations?.players[name] || name;
  }

  /**
   * Translate a tournament name to the current language.
   * Supports compound names by splitting and translating each part.
   * Falls back to the original name if no translation is found.
   */
  translateTournament(name: string): string {
    if (!name) return name;

    // Try exact match first
    if (this.liveTranslations?.tournaments[name]) {
      return this.liveTranslations.tournaments[name];
    }

    // Try compound name: split by space and translate each part
    const parts = name.split(/\s+/);
    if (parts.length > 1) {
      let anyTranslated = false;
      const translatedParts = parts.map(part => {
        // Try as tournament name
        if (this.liveTranslations?.tournaments[part]) {
          anyTranslated = true;
          return this.liveTranslations.tournaments[part];
        }
        // Try as round name
        if (this.liveTranslations?.rounds[part]) {
          anyTranslated = true;
          return this.liveTranslations.rounds[part];
        }
        return part;
      });
      if (anyTranslated) {
        return translatedParts.join(' ');
      }
    }

    return name;
  }

  /**
   * Translate a round name to the current language.
   * Falls back to the original name if no translation is found.
   */
  translateRound(name: string): string {
    if (!name) return name;
    return this.liveTranslations?.rounds[name] || name;
  }

  /**
   * Translate a rule name to the current language.
   * Falls back to the original name if no translation is found.
   */
  translateRules(rules: string): string {
    if (!rules) return rules;
    return this.liveTranslations?.rules[rules] || rules;
  }

  /**
   * Check if live translations are loaded.
   */
  get hasLiveTranslations(): boolean {
    return this.liveTranslations !== null;
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