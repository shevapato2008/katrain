import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import LoginPage from './LoginPage';

// R1-F12/R2-F2: in a strict box kiosk there is no local auth form at all — the
// box identity lives solely in the HttpOnly cookie set by the setup-wizard.
// Falling through to /kiosk/login means that cookie is absent/expired, so the
// page must redirect to the wizard's launcher gate instead of rendering a dead
// username/password form nobody can submit.
const mockLogin = vi.fn();
const mockUseAuth = vi.fn();
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}));

const renderLoginPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={['/kiosk/login']}>
        <Routes>
          <Route path="/kiosk/login" element={<LoginPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );

describe('LoginPage strict-box redirect (decision B)', () => {
  const originalLocation = window.location;

  beforeEach(() => {
    mockLogin.mockReset();
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...originalLocation, href: 'http://localhost/kiosk/login' },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: originalLocation,
    });
  });

  it('redirects to the setup-wizard launcher and renders a spinner instead of a dead form', () => {
    mockUseAuth.mockReturnValue({ login: mockLogin, isStrictBoxKiosk: true });
    renderLoginPage();

    expect(window.location.href).toBe('http://127.0.0.1:8080/launcher');
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.queryByLabelText(/用户名/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /登录/i })).not.toBeInTheDocument();
  });

  it('renders the normal login form (no redirect) outside strict box mode', () => {
    mockUseAuth.mockReturnValue({ login: mockLogin, isStrictBoxKiosk: false });
    renderLoginPage();

    expect(window.location.href).toBe('http://localhost/kiosk/login');
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    expect(screen.getByLabelText(/用户名/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /登录/i })).toBeInTheDocument();
  });
});
