import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { i18n } from '../../i18n';

interface SettingsContextType {
  language: string;
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
  if (langCode.startsWith('en')) return 'en';

  return 'en'; // Default to English
};

const LANGUAGE_STORAGE_KEY = 'katrain_language';

export const SettingsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState('en');
  const [, setTick] = useState(0); // For forcing re-render on translation change

  const updateLanguage = useCallback(async (lang: string) => {
    try {
      await i18n.loadTranslations(lang);
      setLanguageState(lang);
      // Save preference to localStorage
      localStorage.setItem(LANGUAGE_STORAGE_KEY, lang);
    } catch (error) {
      console.error('Failed to change language:', error);
    }
  }, []);

  useEffect(() => {
    // Initial load - check localStorage first, then detect browser language
    const initLang = async () => {
      const savedLang = localStorage.getItem(LANGUAGE_STORAGE_KEY);
      const currentLang = savedLang || detectBrowserLanguage();
      await i18n.loadTranslations(currentLang);
      setLanguageState(currentLang);
    };
    initLang();

    // Subscribe to i18n changes
    const unsubscribe = i18n.subscribe(() => {
      setTick(t => t + 1);
    });
    return unsubscribe;
  }, []);

  return (
    <SettingsContext.Provider value={{ language, setLanguage: updateLanguage, languages }}>
      {children}
    </SettingsContext.Provider>
  );
};
