import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../../theme';
import AccountSection from './AccountSection';

// Decision B (logout-then-register): a guest never triggers a fetch to the
// cross-origin auth endpoints from this component — the register/login button
// does a top-level browser navigation instead. Mock useAuth directly, same
// idiom as src/kiosk/__tests__/SettingsPage.test.tsx.
const mockLogout = vi.fn();
const mockUseAuth = vi.fn();
vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}));

const LocationProbe = () => {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}</output>;
};

const renderSection = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={['/kiosk/settings']}>
        <Routes>
          <Route path="/kiosk/settings" element={<AccountSection />} />
          <Route path="/kiosk/login" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );

describe('AccountSection', () => {
  const originalLocation = window.location;

  beforeEach(() => {
    mockLogout.mockReset();
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...originalLocation, href: 'http://localhost/kiosk/settings' },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: originalLocation,
    });
  });

  it('shows a guest chip and a register/sign-in button, and hides sign-out, for the shared guest account', () => {
    mockUseAuth.mockReturnValue({
      user: { id: 0, username: 'guest', rank: '', credits: 0 },
      logout: mockLogout,
      isGuest: true,
    });
    renderSection();

    expect(screen.getByTestId('account-guest-chip')).toHaveTextContent('访客');
    expect(screen.getByTestId('account-register-login')).toBeInTheDocument();
    expect(screen.queryByTestId('settings-logout')).not.toBeInTheDocument();
  });

  it('navigates the top-level browser to the setup-wizard register/login gate (decision B) without calling logout()', () => {
    mockUseAuth.mockReturnValue({
      user: { id: 0, username: 'guest', rank: '', credits: 0 },
      logout: mockLogout,
      isGuest: true,
    });
    renderSection();

    fireEvent.click(screen.getByTestId('account-register-login'));

    expect(window.location.href).toBe('http://127.0.0.1:8080/launcher?logout=1&authmode=register');
    expect(mockLogout).not.toHaveBeenCalled();
  });

  it('shows the username and the sign-out control for an authenticated (non-guest) account', () => {
    mockUseAuth.mockReturnValue({
      user: { id: 1, username: '张三', rank: '2D', credits: 0 },
      logout: mockLogout,
      isGuest: false,
    });
    renderSection();

    expect(screen.getByText('张三')).toBeInTheDocument();
    expect(screen.getByTestId('settings-logout')).toBeInTheDocument();
    expect(screen.queryByTestId('account-register-login')).not.toBeInTheDocument();
    expect(screen.queryByTestId('account-guest-chip')).not.toBeInTheDocument();
  });

  it('signs out and returns to the login route for a non-guest account', async () => {
    mockLogout.mockResolvedValue(undefined);
    mockUseAuth.mockReturnValue({
      user: { id: 1, username: '张三', rank: '2D', credits: 0 },
      logout: mockLogout,
      isGuest: false,
    });
    renderSection();

    fireEvent.click(screen.getByTestId('settings-logout'));

    expect(await screen.findByTestId('location')).toHaveTextContent('/kiosk/login');
    expect(mockLogout).toHaveBeenCalledTimes(1);
  });
});
