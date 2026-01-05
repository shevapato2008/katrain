import { useState, useEffect } from 'react';
import { i18n } from '../i18n';

export const useTranslation = () => {
  const [lang, setLang] = useState(i18n.lang);

  useEffect(() => {
    return i18n.subscribe(() => {
      setLang(i18n.lang);
    });
  }, []);

  return { t: (key: string, defaultText?: string) => i18n.t(key, defaultText), lang };
};
