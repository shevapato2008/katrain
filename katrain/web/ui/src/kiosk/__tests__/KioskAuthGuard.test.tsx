import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import KioskAuthGuard from '../components/guards/KioskAuthGuard';

// Mutable auth state the mocked useAuth reads (name must start with `mock`
// so vitest allows it inside the hoisted vi.mock factory).
const mockAuth: any = {
  isAuthenticated: false,
  isLoading: false,
};

const launcher = vi.hoisted(() => ({ leave: vi.fn() }));
vi.mock('../shell/boxUrls', () => ({ LAUNCHER_LOGIN_URL: 'http://127.0.0.1:8080/launcher?authmode=login', leaveToLauncher: launcher.leave }));

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

const Tree = () => (
  <MemoryRouter initialEntries={['/kiosk/play/pvp/lobby']}>
    <Routes>
      <Route element={<KioskAuthGuard />}>
        <Route path="/kiosk/play/pvp/lobby" element={<div>PROTECTED</div>} />
      </Route>
      <Route path="/kiosk/login" element={<div>LOGIN_PAGE</div>} /><Route path="/kiosk/play" element={<div>PUBLIC_PLAY</div>} />
    </Routes>
  </MemoryRouter>
);

describe('KioskAuthGuard — auth bootstrap race (SSO)', () => {
  beforeEach(() => {
    mockAuth.isAuthenticated = false;
    mockAuth.isLoading = false;
    mockAuth.status = 'guest';
    mockAuth.isStrictBoxKiosk = false;
    launcher.leave.mockClear();
    mockAuth.user = null;
    mockAuth.isGuest = false;
    mockAuth.retry = vi.fn();
  });

  it('while auth is still loading, does NOT bounce to /kiosk/login', () => {
    // The exact "re-enter 围棋" fresh-mount window: token/cookie not yet validated.
    mockAuth.status = 'checking';
    mockAuth.isLoading = true;
    mockAuth.isAuthenticated = false;
    render(<Tree />);
    expect(screen.queryByText('LOGIN_PAGE')).not.toBeInTheDocument();
    expect(screen.queryByText('PROTECTED')).not.toBeInTheDocument();
  });

  it('once loaded and authenticated, renders the protected outlet', () => {
    mockAuth.isLoading = false;
    mockAuth.status = 'authenticated';
    mockAuth.isAuthenticated = true;
    mockAuth.user = { id: 1, username: 'one' };
    mockAuth.identityKey = 'one';
    render(<Tree />);
    expect(screen.getByText('PROTECTED')).toBeInTheDocument();
    expect(screen.queryByText('LOGIN_PAGE')).not.toBeInTheDocument();
  });

  it('once loaded and NOT authenticated, shows in-place guidance', () => {
    mockAuth.isLoading = false;
    mockAuth.isAuthenticated = false;
    render(<Tree />);
    expect(screen.queryByText('LOGIN_PAGE')).not.toBeInTheDocument();
    expect(screen.getByRole('dialog', { name: '登录后进入在线大厅' })).toBeInTheDocument();
  });

  it('a valid persisted session (loading → authenticated) never flashes the login page', () => {
    mockAuth.status = 'checking';
    mockAuth.isLoading = true;
    mockAuth.isAuthenticated = false;
    const { rerender } = render(<Tree />);
    expect(screen.queryByText('LOGIN_PAGE')).not.toBeInTheDocument();

    // /me resolves against the persisted token/cookie → authenticated.
    mockAuth.isLoading = false;
    mockAuth.status = 'authenticated';
    mockAuth.isAuthenticated = true;
    mockAuth.user = { id: 1, username: 'one' };
    mockAuth.identityKey = 'one';
    rerender(<Tree />);
    expect(screen.getByText('PROTECTED')).toBeInTheDocument();
    expect(screen.queryByText('LOGIN_PAGE')).not.toBeInTheDocument();
  });
  it('guest cannot enter the hall, but can return to public play', () => {
    mockAuth.isAuthenticated = true;
    mockAuth.isGuest = true;
    mockAuth.user = { id: 0, username: 'guest' };
    render(<Tree />);
    expect(screen.queryByText('PROTECTED')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '返回对弈' }));
    expect(screen.getByText('PUBLIC_PLAY')).toBeInTheDocument();
  });

  it('strict box primary uses the existing launcher login URL', () => {
    mockAuth.isStrictBoxKiosk = true;
    render(<Tree />);
    fireEvent.click(screen.getByRole('button', { name: '去盒子主页登录' }));
    expect(launcher.leave).toHaveBeenCalledWith('http://127.0.0.1:8080/launcher?authmode=login');
    expect(screen.getByRole('dialog')).toHaveTextContent('再从围棋入口回到此模块');
  });
  it.each(['/kiosk/report', '/kiosk/growth', '/kiosk/kifu', '/kiosk/tutorial', '/kiosk/research', '/kiosk/play/cross-platform/golaxy'])('preserves technical guest reads on %s', (path) => {
    mockAuth.isAuthenticated = true;
    mockAuth.isGuest = true;
    mockAuth.user = { id: 0, username: 'guest' };
    render(<MemoryRouter initialEntries={[path]}><Routes><Route element={<KioskAuthGuard />}><Route path={path} element={<div>ALLOWED READ</div>} /></Route></Routes></MemoryRouter>);
    expect(screen.getByText('ALLOWED READ')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

});
