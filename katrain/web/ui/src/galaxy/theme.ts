import { createTheme } from '@mui/material/styles';
import { zenTheme } from '../theme';

export const SYSTEM_UI_FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif";
export const CHINESE_UI_FONT = `'LXGW WenKai', ${SYSTEM_UI_FONT}`;

export const createGalaxyTheme = (language: string) => {
  const fontFamily = language === 'cn' || language === 'tw' ? CHINESE_UI_FONT : SYSTEM_UI_FONT;

  return createTheme(zenTheme, {
    typography: {
      fontFamily,
      h1: { fontFamily },
      h2: { fontFamily },
      h3: { fontFamily },
      h4: { fontFamily },
      h5: { fontFamily },
      h6: { fontFamily },
      body1: { fontFamily },
      body2: { fontFamily },
      button: { fontFamily },
    },
  });
};
