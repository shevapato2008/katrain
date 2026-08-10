import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, useTheme } from '@mui/material/styles';
import { MemoryRouter, Outlet } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import GalaxyApp from '../GalaxyApp';
import { zenTheme } from '../theme';
import { CHINESE_UI_FONT, createGalaxyTheme, SYSTEM_UI_FONT } from './theme';

const settings = vi.hoisted(() => ({ language: 'cn' }));
const typographyVariants = [
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'subtitle1',
  'subtitle2',
  'body1',
  'body2',
  'button',
  'caption',
  'overline',
] as const;

vi.mock('../context/SettingsContext', () => ({
  useSettings: () => settings,
}));

vi.mock('../context/TsumegoProgressContext', () => ({
  TsumegoProgressProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock('./components/layout/MainLayout', () => ({
  default: function MainLayoutMock() {
    const theme = useTheme();
    return (
      <div data-testid="theme-probe" data-font-family={theme.typography.fontFamily}>
        <Outlet />
      </div>
    );
  },
}));

vi.mock('./pages/Dashboard', () => ({ default: () => <div>Dashboard</div> }));

describe('createGalaxyTheme', () => {
  it('uses the WenKai family registered by the Galaxy font CSS', () => {
    const fontCssUrl = new URL('src/galaxy/assets/fonts/galaxy-fonts.css', pathToFileURL(`${process.cwd()}/`));
    const fontCss = readFileSync(fontCssUrl, 'utf8');
    const registeredFamilies = [...fontCss.matchAll(/font-family: "([^"]+)";[\s\S]*?wenkai-/g)].map(match => match[1]);
    const preferredThemeFamily = CHINESE_UI_FONT.split(',')[0].replaceAll("'", '');

    expect(new Set(registeredFamilies)).toEqual(new Set(['LXGW WenKai']));
    expect(preferredThemeFamily).toBe('LXGW WenKai');
  });

  it.each(['cn', 'tw'])('uses LXGW WenKai for the %s locale', language => {
    const theme = createGalaxyTheme(language);

    expect(theme.typography.fontFamily).toBe(CHINESE_UI_FONT);
    expect(theme.typography.fontFamily).toContain('LXGW WenKai');
    typographyVariants.forEach(variant => {
      expect(theme.typography[variant].fontFamily).toBe(CHINESE_UI_FONT);
    });
  });

  it.each(['en', 'jp', 'ko', 'de'])('uses the system font stack for the %s locale', language => {
    const theme = createGalaxyTheme(language);

    expect(theme.typography.fontFamily).toBe(SYSTEM_UI_FONT);
    typographyVariants.forEach(variant => {
      expect(theme.typography[variant].fontFamily).toBe(SYSTEM_UI_FONT);
    });
  });

  it('keeps Manrope out of the system stack and replaces inherited variant fonts', () => {
    const theme = createGalaxyTheme('en');

    expect(SYSTEM_UI_FONT).not.toContain('Manrope');
    expect(zenTheme.typography.fontFamily).toContain('Manrope');
    typographyVariants.forEach(variant => {
      expect(theme.typography[variant].fontFamily).toBe(SYSTEM_UI_FONT);
    });
  });
});

describe('GalaxyApp', () => {
  it('marks the Galaxy root language and supplies its locale theme to routes', () => {
    settings.language = 'cn';

    const { container } = render(
      <ThemeProvider theme={zenTheme}>
        <MemoryRouter>
          <GalaxyApp />
        </MemoryRouter>
      </ThemeProvider>,
    );

    expect(container.querySelector('.galaxy-root')).toHaveAttribute('data-language', 'cn');
    expect(zenTheme.typography.fontFamily).toContain('Manrope');
    expect(screen.getByTestId('theme-probe')).toHaveAttribute('data-font-family', CHINESE_UI_FONT);
  });
});
