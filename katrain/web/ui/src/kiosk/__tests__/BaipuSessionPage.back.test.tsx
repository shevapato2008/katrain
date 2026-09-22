import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';

/**
 * 摆谱会话屏的返回键原先一律 `navigate('/kiosk/baipu')`(摆谱列表),键名却写「棋谱」
 * (2026-09-23 审计)。现在去**打开这一屏的那一页**,键名跟着去处。
 * 在「读不到棋谱」那一态上验:那一态最好渲染,而三颗页控条返回键用的是同一对 `back` / `backLabel`。
 */

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: null, isGuest: false, isLoading: false }),
}));

import BaipuSessionPage from '../pages/BaipuSessionPage';

const renderAt = (state: unknown) => render(
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter initialEntries={[{ pathname: '/kiosk/baipu/session/nothing-cached', state }]}>
      <Routes>
        <Route path="/kiosk/baipu/session/:source" element={<BaipuSessionPage />} />
      </Routes>
    </MemoryRouter>
  </ThemeProvider>,
);

beforeEach(() => { vi.clearAllMocks(); localStorage.clear(); });

describe('摆谱会话 · 返回键去打开它的那一页', () => {
  it('从棋谱详情「摆到实体盘」进来:返回键叫「棋谱」,回那一局的详情', () => {
    renderAt({ backTo: '/kiosk/kifu/7' });
    fireEvent.click(screen.getByRole('button', { name: '棋谱' }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/kifu/7');
  });

  it('从摆谱列表进来或没写明来处:返回键叫「摆谱」,回摆谱列表', () => {
    renderAt(null);
    fireEvent.click(screen.getByRole('button', { name: '摆谱' }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/baipu');
    expect(screen.queryByRole('button', { name: '棋谱' })).toBeNull();
  });
});
