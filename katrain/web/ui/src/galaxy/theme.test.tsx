import { render, screen } from '@testing-library/react';
import { useTheme } from '@mui/material/styles';
import { MemoryRouter, Outlet } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import GalaxyApp from '../GalaxyApp';
import { zenTheme } from '../theme';
import { CHINESE_UI_FONT, createGalaxyTheme, SYSTEM_UI_FONT } from './theme';

const settings = vi.hoisted(() => ({ language: 'cn' }));

vi.mock('../context/SettingsContext', () => ({
  useSettings: () => settings,
}));

vi.mock('../context/TsumegoProgressContext', () => ({
  TsumegoProgressProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock('./components/layout/MainLayout', () => ({
  default: () => {
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
  it.each(['cn', 'tw'])('uses LXGW WenKai for the %s locale', language => {
    const theme = createGalaxyTheme(language);

    expect(theme.typography.fontFamily).toBe(CHINESE_UI_FONT);
    expect(theme.typography.fontFamily).toContain('LXGW WenKai');
  });

  it.each(['en', 'jp', 'ko', 'de'])('uses the system font stack for the %s locale', language => {
    const theme = createGalaxyTheme(language);

    expect(theme.typography.fontFamily).toBe(SYSTEM_UI_FONT);
  });

  it('keeps Manrope out of the system stack and replaces inherited variant fonts', () => {
    const theme = createGalaxyTheme('en');

    expect(SYSTEM_UI_FONT).not.toContain('Manrope');
    expect(theme.typography.h1.fontFamily).toBe(SYSTEM_UI_FONT);
    expect(theme.typography.h6.fontFamily).toBe(SYSTEM_UI_FONT);
    expect(theme.typography.body1.fontFamily).toBe(SYSTEM_UI_FONT);
    expect(theme.typography.body2.fontFamily).toBe(SYSTEM_UI_FONT);
    expect(theme.typography.button.fontFamily).toBe(SYSTEM_UI_FONT);
    expect(zenTheme.typography.fontFamily).toContain('Manrope');
  });
});

describe('GalaxyApp', () => {
  it('marks the Galaxy root language and supplies its locale theme to routes', () => {
    settings.language = 'cn';

    const { container } = render(
      <MemoryRouter>
        <GalaxyApp />
      </MemoryRouter>,
    );

    expect(container.querySelector('.galaxy-root')).toHaveAttribute('data-language', 'cn');
    expect(screen.getByTestId('theme-probe')).toHaveAttribute('data-font-family', CHINESE_UI_FONT);
  });
});
