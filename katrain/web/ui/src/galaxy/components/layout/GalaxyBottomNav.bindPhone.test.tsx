import type { ReactNode } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAuth } from '../../../context/AuthContext';
import { useGameNavigation } from '../../context/GameNavigationContext';
import GalaxyBottomNav from './GalaxyBottomNav';
import MainLayout from './MainLayout';

/* 夹具形状照抄同目录 GalaxySidebar.bindPhone.test.tsx:10-21，连那条「有意少抄一条」
   一起照抄：**不能** `vi.mock('../../../api', ...)` —— 本文件要在同一棵树里挂
   BindPhoneDialog，它 `import { API }`，把整个 api 模块换成假对象会让
   API.sendPhoneCode 变成 undefined。本文件只开对话框、不点发码，用真 API 反而安全。 */
vi.mock('../../../context/AuthContext', async (importOriginal) => ({
  ...await importOriginal<object>(), useAuth: vi.fn(),
}));
vi.mock('../../context/GameNavigationContext', () => ({
  useGameNavigation: vi.fn(),
  GameNavigationProvider: ({ children }: { children: ReactNode }) => children,
}));
vi.mock('../../../hooks/useTranslation', () => ({
  useTranslation: () => ({ t: (_key: string, fallback: string) => fallback }),
}));
vi.mock('./GalaxyTopBar', () => ({ default: () => <header>TOP</header> }));
vi.mock('./GalaxySidebar', () => ({ default: () => <aside>SIDEBAR</aside> }));
let sidebarMode = 'mobile';
vi.mock('./useGalaxySidebar', () => ({ useGalaxySidebar: () => ({ mode: sidebarMode }) }));

const asUser = (phoneBound: boolean) => vi.mocked(useAuth).mockReturnValue({
  user: { id: 1, username: 'u', rank: '5k', credits: 0, phone_bound: phoneBound },
  logout: vi.fn(), refreshUser: vi.fn(),
} as never);

const renderNav = () => render(<MemoryRouter><GalaxyBottomNav /></MemoryRouter>);

/* 触发器是 GalaxyBottomNav.tsx 里那颗 MoreHorizIcon 的 BottomNavigationAction，
   可访问名来自它的 aria-label `t('More', 'More')`；上面那条 useTranslation mock
   让 t 返回 fallback ⇒ 名字就是 'More'。它是侧栏「设置」菜单在移动档的对应物。 */
const openMore = () => fireEvent.click(screen.getByRole('button', { name: 'More' }));

describe('GalaxyBottomNav 账号入口（移动档唯一的那一处）', () => {
  beforeEach(() => {
    sidebarMode = 'mobile';
    vi.mocked(useGameNavigation).mockReturnValue({ requestNavigation: vi.fn() } as never);
  });

  it('已登录未绑号：「更多」里有「绑定手机号」，点开出绑定对话框', () => {
    asUser(false);
    renderNav();
    openMore();
    fireEvent.click(screen.getByRole('menuitem', { name: '绑定手机号' }));
    expect(screen.getByRole('dialog', { name: '绑定手机号' })).toBeInTheDocument();
  });

  it('已登录：「更多」里有「修改密码」，点开出改密码对话框', () => {
    asUser(true);
    renderNav();
    openMore();
    fireEvent.click(screen.getByRole('menuitem', { name: '修改密码' }));
    expect(screen.getByRole('dialog', { name: '修改密码' })).toBeInTheDocument();
  });

  /* 下面两条量的是**显示条件与侧栏逐条一致**（GalaxySidebar.tsx:117 / :126）：
     已绑号不再给绑定入口（本轮不做换绑/解绑），未登录两项都没有。
     条件抄漏 = 给用户一个点了没用的菜单项。 */
  it('已绑号：不再给绑定入口 —— 同侧栏，本轮不做换绑/解绑', () => {
    asUser(true);
    renderNav();
    openMore();
    expect(screen.queryByRole('menuitem', { name: '绑定手机号' })).toBeNull();
  });

  it('未登录：两项都没有 —— 没有账号就没有可绑的对象、也没有可改的密码', () => {
    vi.mocked(useAuth).mockReturnValue({ user: null, logout: vi.fn(), refreshUser: vi.fn() } as never);
    renderNav();
    openMore();
    expect(screen.queryByRole('menuitem', { name: '绑定手机号' })).toBeNull();
    expect(screen.queryByRole('menuitem', { name: '修改密码' })).toBeNull();
    // 导航那几项与账号无关，仍在 —— 证明菜单确实开着，上面两条不是「菜单没开」的假绿。
    expect(screen.getByRole('menuitem', { name: 'Live' })).toBeInTheDocument();
  });
});

/* 反向不是「宽屏下这两项也在」—— 宽屏下 GalaxyBottomNav **整个不挂**
   （MainLayout.tsx:44 `{mobile && …}`），那边的入口归侧栏。
   这一条量的就是这个挂载条件本身：底栏只在移动档存在。 */
describe('GalaxyBottomNav 的挂载条件', () => {
  const renderLayout = () => render(
    <MemoryRouter>
      <Routes>
        <Route element={<MainLayout />}>
          <Route path="/" element={<span>PAGE</span>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );

  beforeEach(() => {
    vi.mocked(useGameNavigation).mockReturnValue({ requestNavigation: vi.fn() } as never);
    asUser(false);
  });

  it('移动档：底栏在，账号入口跟着在', () => {
    sidebarMode = 'mobile';
    renderLayout();
    expect(screen.getByTestId('galaxy-bottom-nav')).toBeInTheDocument();
    openMore();
    expect(screen.getByRole('menuitem', { name: '绑定手机号' })).toBeInTheDocument();
  });

  it('宽屏档：底栏根本不渲染 —— 那一档的入口归侧栏', () => {
    sidebarMode = 'wide-docked';
    renderLayout();
    expect(screen.queryByTestId('galaxy-bottom-nav')).toBeNull();
    expect(screen.queryByRole('button', { name: 'More' })).toBeNull();
  });
});
