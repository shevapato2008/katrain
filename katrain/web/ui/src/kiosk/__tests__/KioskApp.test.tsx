import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import KioskApp from '../KioskApp';

// KioskApp uses relative routes, needs parent /kiosk/* context (same as AppRouter)
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
    renderApp('/kiosk/play');
    // Auth guard redirects to login
    expect(screen.getByRole('button', { name: /登录/i })).toBeInTheDocument();
  });

  it('renders nav rail on authenticated route', () => {
    renderApp('/kiosk/play');
    // Login first
    const usernameInput = screen.getByLabelText(/用户名/i);
    const loginBtn = screen.getByRole('button', { name: /登录/i });
    fireEvent.change(usernameInput, { target: { value: '张三' } });
    fireEvent.click(loginBtn);
    // After login, nav rail visible
    expect(screen.getByText('对弈')).toBeInTheDocument();
    expect(screen.getByText('KaTrain')).toBeInTheDocument();
  });

  it('redirects /kiosk to /kiosk/play', () => {
    renderApp('/kiosk');
    // Should redirect to login (which then redirects to play after auth)
    expect(screen.getByRole('button', { name: /登录/i })).toBeInTheDocument();
  });
});
