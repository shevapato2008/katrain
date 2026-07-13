import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import KioskAuthGuard from '../components/guards/KioskAuthGuard';

// Mutable auth state the mocked useAuth reads (name must start with `mock`
// so vitest allows it inside the hoisted vi.mock factory).
const mockAuth: { isAuthenticated: boolean; isLoading: boolean } = {
  isAuthenticated: false,
  isLoading: false,
};

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

const Tree = () => (
  <MemoryRouter initialEntries={['/kiosk/play']}>
    <Routes>
      <Route element={<KioskAuthGuard />}>
        <Route path="/kiosk/play" element={<div>PROTECTED</div>} />
      </Route>
      <Route path="/kiosk/login" element={<div>LOGIN_PAGE</div>} />
    </Routes>
  </MemoryRouter>
);

describe('KioskAuthGuard — auth bootstrap race (SSO)', () => {
  beforeEach(() => {
    mockAuth.isAuthenticated = false;
    mockAuth.isLoading = false;
  });

  it('while auth is still loading, does NOT bounce to /kiosk/login', () => {
    // The exact "re-enter 围棋" fresh-mount window: token/cookie not yet validated.
    mockAuth.isLoading = true;
    mockAuth.isAuthenticated = false;
    render(<Tree />);
    expect(screen.queryByText('LOGIN_PAGE')).not.toBeInTheDocument();
    expect(screen.queryByText('PROTECTED')).not.toBeInTheDocument();
  });

  it('once loaded and authenticated, renders the protected outlet', () => {
    mockAuth.isLoading = false;
    mockAuth.isAuthenticated = true;
    render(<Tree />);
    expect(screen.getByText('PROTECTED')).toBeInTheDocument();
    expect(screen.queryByText('LOGIN_PAGE')).not.toBeInTheDocument();
  });

  it('once loaded and NOT authenticated, redirects to /kiosk/login', () => {
    mockAuth.isLoading = false;
    mockAuth.isAuthenticated = false;
    render(<Tree />);
    expect(screen.getByText('LOGIN_PAGE')).toBeInTheDocument();
  });

  it('a valid persisted session (loading → authenticated) never flashes the login page', () => {
    mockAuth.isLoading = true;
    mockAuth.isAuthenticated = false;
    const { rerender } = render(<Tree />);
    expect(screen.queryByText('LOGIN_PAGE')).not.toBeInTheDocument();

    // /me resolves against the persisted token/cookie → authenticated.
    mockAuth.isLoading = false;
    mockAuth.isAuthenticated = true;
    rerender(<Tree />);
    expect(screen.getByText('PROTECTED')).toBeInTheDocument();
    expect(screen.queryByText('LOGIN_PAGE')).not.toBeInTheDocument();
  });
});
