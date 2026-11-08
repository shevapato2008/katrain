import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { i18n } from '../i18n';
import { isStrictBoxKiosk } from '../kiosk/shell/boxUrls';

export type DeviceAppearance = {
  language: 'zh' | 'zh-TW' | 'en' | 'ja' | 'ko';
  font: 'wenkai' | 'kai' | 'daoli' | 'hei';
};
export const DEVICE_UI_LANGUAGE = { zh: 'cn', 'zh-TW': 'tw', en: 'en', ja: 'jp', ko: 'ko' } as const;
export const DEVICE_UI_FONT = { wenkai: 'wenkai', kai: 'kaiti', daoli: 'lishu', hei: 'heiti' } as const;
function isAppearance(value: unknown): value is DeviceAppearance {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Record<string, unknown>;
  return typeof candidate.language === 'string' && Object.hasOwn(DEVICE_UI_LANGUAGE, candidate.language)
    && typeof candidate.font === 'string' && Object.hasOwn(DEVICE_UI_FONT, candidate.font);
}

interface SettingsContextType {
  language: string;
  deviceAppearance: DeviceAppearance | null;
  appearanceLoading: boolean;
  appearanceError: boolean;
  refreshAppearance: () => void;
  setLanguage: (lang: string) => Promise<void>;
  languages: { code: string; name: string }[];
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined);

export const useSettings = () => {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error('useSettings must be used within a SettingsProvider');
  }
  return context;
};

export const languages = [
  { code: 'en', name: 'English' },
  { code: 'cn', name: '中文' },
  { code: 'tw', name: '繁體中文' },
  { code: 'jp', name: '日本語' },
  { code: 'ko', name: '한국어' },
  { code: 'de', name: 'Deutsch' },
  { code: 'es', name: 'Español' },
  { code: 'fr', name: 'Français' },
  { code: 'ru', name: 'Русский' },
  { code: 'tr', name: 'Türkçe' },
  { code: 'ua', name: 'Українська' },
];

// Map browser language codes to our supported language codes
const detectBrowserLanguage = (): string => {
  const browserLang = navigator.language || (navigator as { userLanguage?: string }).userLanguage || 'en';
  const langCode = browserLang.toLowerCase();

  // Map common browser language codes to our codes
  if (langCode.startsWith('zh-tw') || langCode.startsWith('zh-hant')) return 'tw';
  if (langCode.startsWith('zh')) return 'cn';
  if (langCode.startsWith('ja')) return 'jp';
  if (langCode.startsWith('ko')) return 'ko';
  if (langCode.startsWith('de')) return 'de';
  if (langCode.startsWith('es')) return 'es';
  if (langCode.startsWith('fr')) return 'fr';
  if (langCode.startsWith('ru')) return 'ru';
  if (langCode.startsWith('tr')) return 'tr';
  if (langCode.startsWith('uk')) return 'ua';

  // China-first product: English and unrecognized locales default to Chinese.
  // The kiosk relies on this default; the root app overrides it with the server
  // session language (ZenModeApp) so non-Chinese config users are unaffected.
  return 'cn';
};

const LANGUAGE_STORAGE_KEY = 'katrain_language';

export const SettingsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState('cn');
  const [deviceAppearance, setDeviceAppearance] = useState<DeviceAppearance | null>(null);
  const [appearanceLoading, setAppearanceLoading] = useState(isStrictBoxKiosk);
  const [appearanceError, setAppearanceError] = useState(false);
  const requestGeneration = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const [, setTick] = useState(0); // For forcing re-render on translation change

  const updateLanguage = useCallback(async (lang: string) => {
    if (isStrictBoxKiosk) return;
    try {
      if (await i18n.loadTranslations(lang) === false) return;
      setLanguageState(lang);
      // Save preference to localStorage
      localStorage.setItem(LANGUAGE_STORAGE_KEY, lang);
    } catch (error) {
      console.error('Failed to change language:', error);
    }
  }, []);

  const refreshAppearance = useCallback(() => {
    if (!isStrictBoxKiosk) return;
    const generation = ++requestGeneration.current;
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    setAppearanceLoading(true);
    void (async () => {
      try {
        const response = await fetch('/api/v1/kiosk-preferences/device', { cache: 'no-store', signal: abort.signal });
        if (!response.ok) throw new Error('Device appearance unavailable');
        const value: unknown = await response.json();
        if (!isAppearance(value)) throw new Error('Invalid device appearance');
        if (generation !== requestGeneration.current) return;
        if (await i18n.loadTranslations(DEVICE_UI_LANGUAGE[value.language], abort.signal) === false) {
          throw new Error('Language presentation unavailable');
        }
        if (generation !== requestGeneration.current) return;
        setLanguageState(DEVICE_UI_LANGUAGE[value.language]);
        setDeviceAppearance(value);
        setAppearanceError(false);
      } catch {
        if (generation === requestGeneration.current) setAppearanceError(true);
      } finally {
        if (generation === requestGeneration.current) setAppearanceLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (isStrictBoxKiosk) {
      refreshAppearance();
      const visible = () => { if (document.visibilityState === 'visible') refreshAppearance(); };
      window.addEventListener('focus', refreshAppearance);
      document.addEventListener('visibilitychange', visible);
      return () => {
        requestGeneration.current += 1;
        controller.current?.abort();
        window.removeEventListener('focus', refreshAppearance);
        document.removeEventListener('visibilitychange', visible);
      };
    }
    let active = true;
    void (async () => {
      const savedLang = localStorage.getItem(LANGUAGE_STORAGE_KEY);
      const currentLang = savedLang || detectBrowserLanguage();
      await i18n.loadTranslations(currentLang);
      if (active) setLanguageState(currentLang);
    })();
    return () => { active = false; };
  }, [refreshAppearance]);

  useEffect(() => i18n.subscribe(() => setTick(t => t + 1)), []);
  useEffect(() => {
    if (!isStrictBoxKiosk || !deviceAppearance) return;
    document.documentElement.lang = deviceAppearance.language;
    document.documentElement.dataset.smartboxFont = DEVICE_UI_FONT[deviceAppearance.font];
  }, [deviceAppearance]);

  return (
    <SettingsContext.Provider value={{ language, setLanguage: updateLanguage, languages, deviceAppearance, appearanceLoading, appearanceError, refreshAppearance }}>
      {children}
    </SettingsContext.Provider>
  );
};
