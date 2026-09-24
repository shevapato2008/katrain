import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import PlayPage from '../pages/PlayPage';
import { PLATFORM_MARKS } from '../constants/platformMarks';

// PlayPage reads the username for the greeting; stub AuthContext (no provider in tests).
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: { username: 'fan' }, isAuthenticated: true }),
}));

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter>
        <PlayPage />
      </MemoryRouter>
    </ThemeProvider>
  );

describe('PlayPage', () => {
  it('renders all 4 play mode cards', () => {
    renderPage();
    expect(screen.getByText('自由对弈')).toBeInTheDocument();
    expect(screen.getByText('升降级对弈')).toBeInTheDocument();
    expect(screen.getByText('本地对局')).toBeInTheDocument();
    expect(screen.getByText('在线大厅')).toBeInTheDocument();
  });

  it('三张跨平台卡各戴自己的品牌标记 —— 包括还没接通的野狐', () => {
    // 野狐走的是 `meta.comingSoon` 那条**单独的 JSX 分支**,和另两家不是同一处调用。
    // 只测「能连的那两家」会让这一支悄悄退回绿色地球而没人发现。
    const { container } = renderPage();
    const marks = [...container.querySelectorAll('.kiosk-card__mark')]
      .map((el) => el.getAttribute('src'));
    expect(marks).toHaveLength(3);
    expect(new Set(marks)).toEqual(
      new Set([PLATFORM_MARKS.golaxy.src, PLATFORM_MARKS.ogs.src, PLATFORM_MARKS.fox.src]),
    );
  });

  it('separates AI and PvP sections with headers', () => {
    renderPage();
    expect(screen.getByText('人机对弈')).toBeInTheDocument();
    expect(screen.getByText('人人对弈')).toBeInTheDocument();
  });
});
