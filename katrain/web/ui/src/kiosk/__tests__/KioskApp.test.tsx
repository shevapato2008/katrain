import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

const mockUseAuth = vi.fn();
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}));

import KioskApp from '../KioskApp';

const renderApp = (route = '/kiosk/play') =>
  render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/kiosk/*" element={<KioskApp />} />
      </Routes>
    </MemoryRouter>
  );

describe('KioskApp', () => {
  it('renders login page when not authenticated', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      token: null,
    });
    renderApp('/kiosk/play');
    // Auth guard redirects to login
    expect(screen.getByRole('button', { name: /登录/i })).toBeInTheDocument();
  });

  it('renders nav rail on authenticated route', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: { id: 1, username: '张三', rank: '2D', credits: 0 },
      login: vi.fn(),
      logout: vi.fn(),
      token: 'mock-token',
    });
    renderApp('/kiosk/play');
    // After auth, nav rail visible
    expect(screen.getByText('对弈')).toBeInTheDocument();
    expect(screen.getByText('KaTrain')).toBeInTheDocument();
  });

  it('redirects /kiosk to /kiosk/play', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      token: null,
    });
    renderApp('/kiosk');
    // Should redirect to login (which then redirects to play after auth)
    expect(screen.getByRole('button', { name: /登录/i })).toBeInTheDocument();
  });
});
