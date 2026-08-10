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

    expect(main).toHaveStyle({ paddingBottom: 0 });
    expect(main).not.toHaveStyle({ overflowY: 'auto' });
    expect(shell).toHaveStyle({
      overflow: 'hidden',
      overflowY: 'auto',
      paddingBottom: 'calc(64px + env(safe-area-inset-bottom))',
    });
  });
});
