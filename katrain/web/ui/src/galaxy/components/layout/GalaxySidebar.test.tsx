import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  BOARD_STYLE_STORAGE_KEY,
  CHINESE_FONT_STORAGE_KEY,
  STONE_STYLE_STORAGE_KEY,
  getActiveBoardStyle,
  getActiveStoneStyle,
  setActiveBoardStyle,
  setActiveStoneStyle,
} from '../../../components/board/stoneAppearance';
import { readStoneSoundPref, writeStoneSoundPref } from '../../../utils/audioPrefs';
import { useAuth } from '../../../context/AuthContext';
import { SettingsProvider } from '../../../context/SettingsContext';
import { useGameNavigation } from '../../context/GameNavigationContext';
import type { GalaxySidebarState } from './useGalaxySidebar';
import GalaxySidebar from './GalaxySidebar';

vi.mock('../../../context/AuthContext', async (importOriginal) => ({ ...await importOriginal<object>(), useAuth: vi.fn() }));
vi.mock('../../../api', () => ({ API: { getTranslations: vi.fn().mockResolvedValue({ translations: {} }), phoneStatus: vi.fn().mockResolvedValue({ bound: false }) } }));
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
    const store = new Map<string, string>();
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: vi.fn((key: string) => store.get(key) ?? null),
        setItem: vi.fn((key: string, val: string) => { store.set(key, String(val)); }),
        removeItem: vi.fn((key: string) => { store.delete(key); }),
        clear: vi.fn(() => { store.clear(); }),
      },
    });
    setActiveBoardStyle('kaya');
    setActiveStoneStyle('clamshell-slate');
    writeStoneSoundPref('random');
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
    fireEvent.click(screen.getByRole('button', { name: 'Home' }));
    expect(requestNavigation).toHaveBeenCalledWith('/');
    fireEvent.click(screen.getByRole('button', { name: 'Research' }));
    expect(requestNavigation).toHaveBeenCalledWith('/research');
  });

  it('keeps the native 44px toggle centered on the sidebar edge when collapsed', () => {
    const sidebarState = state({ dockedWidth: 0, dockedExpanded: false });
    renderSidebar(sidebarState);

    expect(screen.getByTestId('galaxy-sidebar-wrapper')).toHaveStyle({ width: '0px' });
    const toggle = screen.getByRole('button', { name: 'Expand navigation' });
    expect(toggle.tagName).toBe('BUTTON');
    expect(toggle).toHaveStyle({
      width: '44px',
      height: '44px',
      left: '0px',
      top: '50%',
      transform: 'translateY(-50%)',
    });
    fireEvent.click(toggle);
    expect(sidebarState.toggle).toHaveBeenCalled();
  });

  it('keeps the toggle centered on the sidebar edge when expanded', () => {
    renderSidebar();

    expect(screen.getByRole('button', { name: 'Collapse navigation' })).toHaveStyle({
      left: '218px',
      top: '50%',
      transform: 'translateY(-50%)',
    });
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
  it('offers an eligible signed-in account the shared phone binding form', async () => {
    vi.mocked(useAuth).mockReturnValue({ user: { username: 'existing-player', rank: '1d' }, token: 'captured-token', identityKey: 'account-a', isGuest: false, logout: vi.fn() } as never);
    renderSidebar();
    fireEvent.click(await screen.findByRole('button', { name: '绑定手机号' }));
    expect(await screen.findByLabelText('当前账号密码')).toBeInTheDocument();
  });

  it('opens Level 1 settings menu showing categories and their active summary labels', () => {
    renderSidebar();

    fireEvent.click(screen.getByRole('button', { name: '设置' }));

    expect(screen.getByText('设置')).toBeInTheDocument();
    expect(screen.getByText('语言')).toBeInTheDocument();
    expect(screen.getByText('中文')).toBeInTheDocument();
    expect(screen.getByText('棋盘样式')).toBeInTheDocument();
    expect(screen.getByText('日式本榧')).toBeInTheDocument();
    expect(screen.getByText('棋子样式')).toBeInTheDocument();
    expect(screen.getByText('蛤碁石')).toBeInTheDocument();
    expect(screen.getByTestId('galaxy-settings-item-stoneSound')).toBeInTheDocument();
    expect(screen.getByText('落子音效')).toBeInTheDocument();
    expect(screen.getByText('随机自然')).toBeInTheDocument();
    expect(screen.getByText('中文字体')).toBeInTheDocument();
    expect(screen.getByText('霞鹜楷体')).toBeInTheDocument();
  });

  it('transitions to Level 2 stone sound submenu with 7 options and updates readStoneSoundPref on click', () => {
    renderSidebar();

    fireEvent.click(screen.getByRole('button', { name: '设置' }));
    fireEvent.click(screen.getByTestId('galaxy-settings-item-stoneSound'));

    expect(screen.getByText('返回设置')).toBeInTheDocument();
    for (const label of ['随机自然', '清脆本榧', '温润蛤石', '沉稳云子', '脆响竹盘', '醇厚木韵', '静音']) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }

    fireEvent.click(screen.getByText('温润蛤石'));
    expect(readStoneSoundPref()).toBe('stone2');

    fireEvent.click(screen.getByText('静音'));
    expect(readStoneSoundPref()).toBe('off');
  });

  it('transitions to Level 2 stone style submenu with strictly 4 styles and updates stoneStyle on click', () => {
    renderSidebar();

    fireEvent.click(screen.getByRole('button', { name: '设置' }));
    fireEvent.click(screen.getByText('棋子样式'));

    expect(screen.getByText('返回设置')).toBeInTheDocument();
    expect(screen.getByText('蛤碁石')).toBeInTheDocument();
    expect(screen.getByText('云子')).toBeInTheDocument();
    expect(screen.getByText('玉石玛瑙')).toBeInTheDocument();
    expect(screen.getByText('简约')).toBeInTheDocument();
    expect(screen.queryByText('石材')).not.toBeInTheDocument();
    expect(screen.queryByText('星河')).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('玉石玛瑙'));
    expect(getActiveStoneStyle()).toBe('jade-agate');
    expect(window.localStorage.getItem(STONE_STYLE_STORAGE_KEY)).toBe('jade-agate');
  });

  it('transitions to Level 2 board style submenu with 4 wood styles and updates boardStyle on click', () => {
    renderSidebar();

    fireEvent.click(screen.getByRole('button', { name: '设置' }));
    fireEvent.click(screen.getByText('棋盘样式'));

    expect(screen.getByText('返回设置')).toBeInTheDocument();
    expect(screen.getByText('日式本榧')).toBeInTheDocument();
    expect(screen.getByText('新榧云杉')).toBeInTheDocument();
    expect(screen.getByText('碳化楠竹')).toBeInTheDocument();
    expect(screen.getByText('胡桃沉香')).toBeInTheDocument();

    fireEvent.click(screen.getByText('胡桃沉香'));
    expect(getActiveBoardStyle()).toBe('walnut');
    expect(window.localStorage.getItem(BOARD_STYLE_STORAGE_KEY)).toBe('walnut');
  });

  it('transitions to Level 2 Chinese font submenu with 4 fonts and updates chineseFont on click', () => {
    renderSidebar();

    fireEvent.click(screen.getByRole('button', { name: '设置' }));
    fireEvent.click(screen.getByText('中文字体'));

    expect(screen.getByText('返回设置')).toBeInTheDocument();
    expect(screen.getByText('霞鹜楷体')).toBeInTheDocument();
    expect(screen.getByText('楷体')).toBeInTheDocument();
    expect(screen.getByText('隶书')).toBeInTheDocument();
    expect(screen.getByText('黑体')).toBeInTheDocument();

    fireEvent.click(screen.getByText('隶书'));
    expect(window.localStorage.getItem(CHINESE_FONT_STORAGE_KEY)).toBe('lishu');

    fireEvent.click(screen.getByText('返回设置'));
    expect(screen.getByText('隶书')).toBeInTheDocument();
  });

  it('transitions to Level 2 language submenu, returns to Level 1 via 返回设置, and resets submenu on close', () => {
    renderSidebar();

    fireEvent.click(screen.getByRole('button', { name: '设置' }));
    fireEvent.click(screen.getByText('语言'));

    expect(screen.getByText('返回设置')).toBeInTheDocument();
    expect(screen.getByText('English')).toBeInTheDocument();
    expect(screen.getByText('中文')).toBeInTheDocument();
    expect(screen.getByText('日本語')).toBeInTheDocument();

    fireEvent.click(screen.getByText('返回设置'));
    expect(screen.queryByText('返回设置')).not.toBeInTheDocument();
    expect(screen.getByText('棋盘样式')).toBeInTheDocument();
    expect(screen.getByText('棋子样式')).toBeInTheDocument();

    // Enter a submenu, close the menu, and verify reopening starts at Level 1
    fireEvent.click(screen.getByText('棋子样式'));
    expect(screen.getByText('返回设置')).toBeInTheDocument();
    fireEvent.keyDown(screen.getByRole('menu'), { key: 'Escape' });

    fireEvent.click(screen.getByRole('button', { name: '设置' }));
    expect(screen.queryByText('返回设置')).not.toBeInTheDocument();
    expect(screen.getByText('棋盘样式')).toBeInTheDocument();
  });
});
