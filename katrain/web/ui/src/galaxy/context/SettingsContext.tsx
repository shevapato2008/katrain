import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { API } from '../../api';
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

export const SettingsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState(i18n.lang || 'cn');
  const [, setTick] = useState(0); // For forcing re-render on translation change

  const updateLanguage = useCallback(async (lang: string) => {
    try {
      await i18n.loadTranslations(lang);
      setLanguageState(lang);
    } catch (error) {
      console.error('Failed to change language:', error);
    }
  }, []);

  useEffect(() => {
    // Initial load
    const initLang = async () => {
        const currentLang = i18n.lang || 'cn';
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
