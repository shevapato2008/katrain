import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAuth } from '../../../context/AuthContext';
import { SettingsProvider } from '../../../context/SettingsContext';
import { useGameNavigation } from '../../context/GameNavigationContext';
import type { GalaxySidebarState } from './useGalaxySidebar';
import GalaxySidebar from './GalaxySidebar';

/* 夹具形状照抄同目录 GalaxySidebar.test.tsx:10-24（同一组 vi.mock + state() 工厂）。
   **有意少抄一条**：那边 :11 有 `vi.mock('../../../api', () => ({ API: { getTranslations } }))`，
   这里不能要 —— 本文件要在同一棵树里挂 BindPhoneDialog，它 `import { API }`，
   把整个 api 模块换成只有 getTranslations 的假对象会让 API.sendPhoneCode 变成 undefined。
   本文件只开对话框、不点发码，所以用真 API 反而安全。 */
vi.mock('../../../context/AuthContext', async (importOriginal) => ({
  ...await importOriginal<object>(), useAuth: vi.fn(),
}));
vi.mock('../../context/GameNavigationContext', () => ({ useGameNavigation: vi.fn() }));
vi.mock('../../../hooks/useTranslation', () => ({
  useTranslation: () => ({ t: (_key: string, fallback: string) => fallback }),
}));

const state = (): GalaxySidebarState => ({
  mode: 'wide-docked', dockedWidth: 240, dockedExpanded: true, overlayOpen: false,
  toggle: vi.fn(), closeOverlay: vi.fn(), toggleButtonRef: { current: null },
});

const renderSidebar = () => render(
  <MemoryRouter><SettingsProvider><GalaxySidebar sidebarState={state()} /></SettingsProvider></MemoryRouter>,
);

/* 触发器是 GalaxySidebar.tsx:94-97 的 ListItemButton（role=button），
   可访问名来自 :96 `<ListItemText primary={t('Settings', 'Settings')} />`；
   上面那条 useTranslation mock 让 t 返回 fallback ⇒ 名字就是 'Settings'。
   galaxy **没有设置页**（ls src/galaxy/pages 可查），这个菜单就是"设置"在本产品里的实体。 */
const openSettings = () => fireEvent.click(screen.getByRole('button', { name: 'Settings' }));

describe('GalaxySidebar 绑定手机入口', () => {
  beforeEach(() => {
    vi.mocked(useGameNavigation).mockReturnValue({ requestNavigation: vi.fn() } as never);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ translations: {} }) }));
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: { getItem: vi.fn(() => null), setItem: vi.fn(), removeItem: vi.fn(), clear: vi.fn() },
    });
  });

  it('已登录未绑号：设置菜单里有「绑定手机号」，点开出绑定对话框', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { id: 1, username: 'u', rank: '5k', credits: 0, phone_bound: false },
      logout: vi.fn(), refreshUser: vi.fn(),
    } as never);
    renderSidebar();
    openSettings();
    fireEvent.click(screen.getByRole('menuitem', { name: '绑定手机号' }));
    expect(screen.getByRole('dialog', { name: '绑定手机号' })).toBeInTheDocument();
  });

  it('已绑号：只报状态、不再给绑定入口（本轮不做换绑/解绑）', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { id: 1, username: 'u', rank: '5k', credits: 0, phone_bound: true },
      logout: vi.fn(), refreshUser: vi.fn(),
    } as never);
    renderSidebar();
    openSettings();
    expect(screen.getByText('手机号已绑定')).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: '绑定手机号' })).toBeNull();
  });

  it('未登录：设置菜单里根本没有这一项 —— 没有账号就没有可绑的对象', () => {
    vi.mocked(useAuth).mockReturnValue({ user: null, logout: vi.fn(), refreshUser: vi.fn() } as never);
    renderSidebar();
    openSettings();
    expect(screen.queryByRole('menuitem', { name: '绑定手机号' })).toBeNull();
    expect(screen.queryByText('手机号已绑定')).toBeNull();
  });
});
