import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import { KioskAuthProvider, useKioskAuth } from '../context/KioskAuthContext';
import KioskAuthGuard from '../components/guards/KioskAuthGuard';
import LoginPage from '../pages/LoginPage';

const renderWithProviders = (ui: React.ReactElement, route = '/kiosk/play') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[route]}>
        <KioskAuthProvider>{ui}</KioskAuthProvider>
      </MemoryRouter>
    </ThemeProvider>
  );

const AuthStatus = () => {
  const { isAuthenticated, user } = useKioskAuth();
  return <div data-testid="auth-status">{isAuthenticated ? user!.name : 'not-auth'}</div>;
};

describe('KioskAuth', () => {
  it('defaults to unauthenticated', () => {
    renderWithProviders(<AuthStatus />);
    expect(screen.getByTestId('auth-status')).toHaveTextContent('not-auth');
  });

  it('auth guard redirects to login when unauthenticated', () => {
    renderWithProviders(
      <Routes>
        <Route path="/kiosk/login" element={<div>LOGIN_PAGE</div>} />
        <Route element={<KioskAuthGuard />}>
          <Route path="/kiosk/play" element={<div>PLAY_PAGE</div>} />
        </Route>
      </Routes>
    );
    expect(screen.getByText('LOGIN_PAGE')).toBeInTheDocument();
    expect(screen.queryByText('PLAY_PAGE')).not.toBeInTheDocument();
  });

  it('login page renders username and PIN inputs', () => {
    renderWithProviders(
      <Routes>
        <Route path="/kiosk/play" element={<LoginPage />} />
      </Routes>,
      '/kiosk/play'
    );
    expect(screen.getByLabelText(/用户名/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/PIN/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /登录/i })).toBeInTheDocument();
  });
});
