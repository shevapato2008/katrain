import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAuth } from '../../../context/AuthContext';
import { SettingsProvider } from '../../../context/SettingsContext';
import { useGameNavigation } from '../../context/GameNavigationContext';
import type { GalaxySidebarState } from './useGalaxySidebar';
import GalaxySidebar from './GalaxySidebar';

vi.mock('../../../context/AuthContext', async (importOriginal) => ({ ...await importOriginal<object>(), useAuth: vi.fn() }));
vi.mock('../../../api', () => ({ API: { getTranslations: vi.fn().mockResolvedValue({ translations: {} }) } }));
vi.mock('../../context/GameNavigationContext', () => ({ useGameNavigation: vi.fn() }));
vi.mock('../../../hooks/useTranslation', () => ({ useTranslation: () => ({ t: (_key: string, fallback: string) => fallback }) }));

const state = (overrides: Partial<GalaxySidebarState> = {}): GalaxySidebarState => ({
  mode: 'wide-docked',
  dockedWidth: 240,
  dockedExpanded: true,
  overlayOpen: false,
  toggle: vi.fn(),
  closeOverlay: vi.fn(),
  toggleButtonRef: { current: null },
  ...overrides,
});

const renderSidebar = (sidebarState = state()) => render(
  <MemoryRouter><SettingsProvider><GalaxySidebar sidebarState={sidebarState} /></SettingsProvider></MemoryRouter>,
);

describe('GalaxySidebar', () => {
  const requestNavigation = vi.fn();

  beforeEach(() => {
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: { getItem: vi.fn(() => null), setItem: vi.fn(), removeItem: vi.fn(), clear: vi.fn() },
    });
    vi.mocked(useAuth).mockReturnValue({ user: null, login: vi.fn(), logout: vi.fn() } as never);
    vi.mocked(useGameNavigation).mockReturnValue({ requestNavigation } as never);
    requestNavigation.mockReset();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ translations: {} }) }));
  });

  it('shares Home and every existing destination with their MUI icons and guarded navigation', () => {
    renderSidebar();

    const icons = {
      Home: 'HomeIcon', Play: 'SportsEsportsIcon', Research: 'ScienceIcon', Tsumego: 'ExtensionIcon',
      Review: 'AssessmentIcon', Live: 'LiveTvIcon', Kifu: 'LibraryBooksIcon', Tutorials: 'MenuBookIcon',
    };
    for (const [label, icon] of Object.entries(icons)) {
      const item = screen.getByRole('button', { name: label });
      expect(item.querySelector(`[data-testid="${icon}"]`)).toBeInTheDocument();
    }
    fireEvent.click(screen.getByRole('button', { name: 'Research' }));
    expect(requestNavigation).toHaveBeenCalledWith('/galaxy/research');
  });

  it('has a zero-width collapsed wrapper and a native 44px translated expand button', () => {
    const sidebarState = state({ dockedWidth: 0, dockedExpanded: false });
    renderSidebar(sidebarState);

    expect(screen.getByTestId('galaxy-sidebar-wrapper')).toHaveStyle({ width: '0px' });
    const toggle = screen.getByRole('button', { name: 'Expand navigation' });
    expect(toggle.tagName).toBe('BUTTON');
    expect(toggle).toHaveStyle({ width: '44px', height: '44px' });
    fireEvent.click(toggle);
    expect(sidebarState.toggle).toHaveBeenCalled();
  });

  it('uses a temporary Drawer in overlay mode and exposes a native close control', () => {
    const sidebarState = state({ mode: 'narrow-overlay', dockedWidth: 0, overlayOpen: true });
    renderSidebar(sidebarState);

    expect(screen.getByRole('presentation')).toBeInTheDocument();
    const close = screen.getByRole('button', { name: 'Close navigation' });
    expect(close.tagName).toBe('BUTTON');
    expect(close).toHaveStyle({ width: '44px', height: '44px' });
    fireEvent.click(close);
    expect(sidebarState.closeOverlay).toHaveBeenCalled();
  });

  it('delegates Escape and scrim dismissal to the temporary Drawer close flow', () => {
    const sidebarState = state({ mode: 'narrow-overlay', dockedWidth: 0, overlayOpen: true });
    renderSidebar(sidebarState);

    fireEvent.keyDown(screen.getByRole('presentation'), { key: 'Escape' });
    expect(sidebarState.closeOverlay).toHaveBeenCalled();
    sidebarState.closeOverlay.mockClear();
    fireEvent.click(document.querySelector('.MuiBackdrop-root') as HTMLElement);
    expect(sidebarState.closeOverlay).toHaveBeenCalled();
  });

  it('unmounts the sidebar and toggle in mobile mode', () => {
    renderSidebar(state({ mode: 'mobile', dockedWidth: 0, dockedExpanded: false }));
    expect(screen.queryByTestId('galaxy-sidebar-wrapper')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Expand navigation' })).not.toBeInTheDocument();
  });

  it('keeps settings and account controls pinned below independently scrollable navigation', () => {
    renderSidebar();
    expect(screen.getByTestId('galaxy-sidebar-nav')).toHaveStyle({ overflowY: 'auto' });
    expect(screen.getByText('Settings')).toBeInTheDocument();
    expect(screen.getByText('Sign In')).toBeInTheDocument();
    expect(screen.queryByText('棋道导航者')).not.toBeInTheDocument();
  });
});
