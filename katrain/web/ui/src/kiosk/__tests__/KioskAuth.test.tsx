import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import LoginPage from '../pages/LoginPage';

const mockLogin = vi.fn();
const mockLogout = vi.fn();

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: false,
    user: null,
    login: mockLogin,
    logout: mockLogout,
    token: null,
  }),
}));

const renderLoginPage = (route = '/kiosk/login') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/kiosk/login" element={<LoginPage />} />
          <Route path="/kiosk/play" element={<div>PLAY_PAGE</div>} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('LoginPage (shared auth)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLogin.mockResolvedValue(undefined);
  });

  it('renders username and password inputs', () => {
    renderLoginPage();
    expect(screen.getByLabelText(/用户名/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/密码/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /登录/i })).toBeInTheDocument();
  });

  it('login button is disabled when username is empty', () => {
    renderLoginPage();
    expect(screen.getByRole('button', { name: /登录/i })).toBeDisabled();
  });

  it('calls login with username and password on submit', async () => {
    renderLoginPage();
    fireEvent.change(screen.getByLabelText(/用户名/i), { target: { value: 'testuser' } });
    fireEvent.change(screen.getByLabelText(/密码/i), { target: { value: 'testpass' } });
    fireEvent.click(screen.getByRole('button', { name: /登录/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('testuser', 'testpass');
    });
  });

  it('navigates to /kiosk/play on successful login', async () => {
    renderLoginPage();
    fireEvent.change(screen.getByLabelText(/用户名/i), { target: { value: 'testuser' } });
    fireEvent.change(screen.getByLabelText(/密码/i), { target: { value: 'pass123' } });
    fireEvent.click(screen.getByRole('button', { name: /登录/i }));

    await waitFor(() => {
      expect(screen.getByText('PLAY_PAGE')).toBeInTheDocument();
    });
  });

  it('displays error message on login failure', async () => {
    mockLogin.mockRejectedValueOnce(new Error('Invalid credentials'));
    renderLoginPage();
    fireEvent.change(screen.getByLabelText(/用户名/i), { target: { value: 'baduser' } });
    fireEvent.change(screen.getByLabelText(/密码/i), { target: { value: 'badpass' } });
    fireEvent.click(screen.getByRole('button', { name: /登录/i }));

    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
    });
  });
});
