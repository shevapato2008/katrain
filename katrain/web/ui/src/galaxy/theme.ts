import { createTheme } from '@mui/material/styles';
import { zenTheme } from '../theme';
import { type ChineseFontId, normalizeChineseFontId } from '../components/board/stoneAppearance';

export const SYSTEM_UI_FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif";
// Galaxy's WenKai subsets contain CJK only; the shared WenKai face supplies Latin/digits.
export const CHINESE_UI_FONT = `'LXGW WenKai', "SmartBox Kai", "Kaiti SC", serif`;

export const CHINESE_FONT_STACKS: Readonly<Record<ChineseFontId, string>> = {
  wenkai: CHINESE_UI_FONT,
  kaiti: `"SmartBox CNS Kai", "Kaiti SC", "STKaiti", serif`,
  lishu: `"SmartBox DaoLi", "LiSu", "STLiti", serif`,
  heiti: `"SmartBox Noto Sans CJK", "PingFang SC", "Microsoft YaHei", sans-serif`,
};

export const getChineseFontStack = (chineseFont: ChineseFontId = 'wenkai'): string =>
  CHINESE_FONT_STACKS[normalizeChineseFontId(chineseFont)];

export const createGalaxyTheme = (language: string = 'zh', chineseFont: ChineseFontId = 'wenkai') => {
  const isChinese = language === 'cn' || language === 'tw' || language.toLowerCase().startsWith('zh');
  const fontFamily = isChinese ? getChineseFontStack(chineseFont) : SYSTEM_UI_FONT;

  return createTheme(zenTheme, {
    typography: {
      fontFamily,
      h1: { fontFamily },
      h2: { fontFamily },
      h3: { fontFamily },
      h4: { fontFamily },
      h5: { fontFamily },
      h6: { fontFamily },
      subtitle1: { fontFamily },
      subtitle2: { fontFamily },
      body1: { fontFamily },
      body2: { fontFamily },
      button: { fontFamily },
      caption: { fontFamily },
      overline: { fontFamily },
    },
  });
};
