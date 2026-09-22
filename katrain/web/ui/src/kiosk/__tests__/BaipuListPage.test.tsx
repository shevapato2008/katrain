import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';

/**
 * 摆谱列表(`/kiosk/baipu`)原先**没有页控条**:它不在 Dock 上、没有主页键,进得来出不去
 * (2026-09-23 审计)。现在返回键去**打开它的那一页**,键名跟着去处 —— 入口两处:
 * 棋谱屏「摆到实体盘」、课程屏「去摆谱」;没写明来处(直接输 URL)就回棋谱。
 */

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const { getAlbums } = vi.hoisted(() => ({ getAlbums: vi.fn() }));
vi.mock('../../api/kifuApi', () => ({ KifuAPI: { getAlbums, getAlbum: vi.fn() } }));
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: null, isGuest: false, isLoading: false }),
}));

import BaipuListPage from '../pages/BaipuListPage';

const renderAt = (state: unknown) => render(
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter initialEntries={[{ pathname: '/kiosk/baipu', state }]}>
      <BaipuListPage />
    </MemoryRouter>
  </ThemeProvider>,
);

beforeEach(() => {
  vi.clearAllMocks();
  getAlbums.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
});

describe('摆谱列表 · 返回键去打开它的那一页', () => {
  it('从课程「去摆谱」进来:返回键叫「课程」,回课程', () => {
    renderAt({ backTo: '/kiosk/tutorial' });
    const back = screen.getByRole('button', { name: '课程' });
    expect(back).toHaveClass('kiosk-pagebar__back');
    fireEvent.click(back);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tutorial');
  });

  it('从棋谱「摆到实体盘」进来或没写明来处:返回键叫「棋谱」,回棋谱', () => {
    renderAt(null);
    const back = screen.getByRole('button', { name: '棋谱' });
    expect(back).toHaveClass('kiosk-pagebar__back');
    fireEvent.click(back);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/kifu');
    expect(mockNavigate).not.toHaveBeenCalledWith(-1);
  });

  it('「导入棋谱」搬进页控条的页级动作位,还在', () => {
    renderAt(null);
    // 导入入口搬进了页控条的页级动作位,还在、还能点
    expect(screen.getByRole('button', { name: '导入棋谱' })).toBeInTheDocument();
  });
});
