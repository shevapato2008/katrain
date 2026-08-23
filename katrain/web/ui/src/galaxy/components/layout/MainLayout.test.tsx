import type { ReactNode } from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import BoardPageShell from '../board/BoardPageShell';
import MainLayout from './MainLayout';

vi.mock('./GalaxyTopBar', () => ({ default: () => <header>TOP</header> }));
vi.mock('./GalaxyBottomNav', () => ({
  default: () => <nav>BOTTOM</nav>,
  GALAXY_BOTTOM_NAV_HEIGHT: 64,
}));
vi.mock('./GalaxySidebar', () => ({ default: () => <aside>SIDEBAR</aside> }));
vi.mock('./useGalaxySidebar', () => ({
  useGalaxySidebar: () => ({ mode: 'mobile' }),
}));
vi.mock('../../context/GameNavigationContext', () => ({
  GameNavigationProvider: ({ children }: { children: ReactNode }) => children,
}));

/* 2026-08-23 修订。原来这里断言 `expect(main).not.toHaveStyle({ overflowY: 'auto' })`。
 *
 * 用例名说的是**结果**：「底部导航的留白和垂直滚动都归 BoardPageShell」——
 * 也就是棋盘页在窄档下**只能有一个滚动条**、只留一份 64px。断言选的却是**机制**：
 * 「main 不许是 overflowY:auto」。两者不等价，而这次正好撞上：
 *   `galaxy-root` 是 `height:100dvh; overflow:hidden`，main 原来没有 overflow ⇒ `visible`，
 *   于是「自己不管滚动」的**内容页**一旦比视口高就被外壳静默裁掉、滚轮推不动
 *   （实测死活题难度页 1702/848，三次滚轮纹丝不动；430 档 /galaxy/play 946/828 同病）。
 *   修法是给 main 补 `overflowY:auto` —— 机制变了，结果没变：
 *   shell 是 `height:100%` + `boxSizing:border-box`，正好等于 main 的内高，main 永不溢出。
 *   真浏览器 430 档实测：/galaxy/live 与 /galaxy/report 上 main 828/828 不溢出、
 *   shell 2486/828 溢出，**滚动条数 = 1**。
 *
 * 所以这里改成断言机制的**当前形状**（两边各自该有的 overflow 声明都在），
 * 「到底有几个滚动条」那个结果归真浏览器：
 * `loadbearing_live_list.js` / `loadbearing_reports_list.js` 的 R15。
 * jsdom 没有布局引擎，scrollHeight 恒等于 clientHeight，它对这个结果无权作证。 */
describe('MainLayout mobile board pages', () => {
  it('leaves the single bottom-nav reservation and vertical scrolling to BoardPageShell', () => {
    render(
      <MemoryRouter>
        <Routes>
          <Route element={<MainLayout />}>
            <Route
              path="/"
              element={
                <BoardPageShell
                  board={<span>BOARD</span>}
                  modulePlate={<span>MODULE</span>}
                  railBody={<span>BODY</span>}
                  actions={<span>ACTIONS</span>}
                />
              }
            />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    const main = screen.getByTestId('galaxy-main');
    const shell = screen.getByTestId('board-page-shell');

    // 底部导航那 64px 只留一份，且留在 shell 上 —— main 不许再留一份。
    expect(main).toHaveStyle({ paddingBottom: 0 });
    // main 自己是滚动容器（内容页要靠它），但它装的是 height:100% 的 shell，永不溢出。
    expect(main).toHaveStyle({ overflowY: 'auto' });
    expect(shell).toHaveStyle({
      overflow: 'hidden',
      overflowY: 'auto',
      paddingBottom: 'calc(64px + env(safe-area-inset-bottom))',
    });
  });
});
