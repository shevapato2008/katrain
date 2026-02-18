import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import KioskApp from '../KioskApp';

const renderApp = (route = '/kiosk') =>
  render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/kiosk/*" element={<KioskApp />} />
      </Routes>
    </MemoryRouter>
  );

const loginFirst = () => {
  const usernameInput = screen.getByLabelText(/用户名/i);
  fireEvent.change(usernameInput, { target: { value: '张三' } });
  fireEvent.click(screen.getByRole('button', { name: /登录/i }));
};

describe('Kiosk navigation integration', () => {
  it('unauthenticated user is redirected to login for any route', () => {
    renderApp('/kiosk/tsumego');
    expect(screen.getByRole('button', { name: /登录/i })).toBeInTheDocument();
  });

  it('login → redirects to play page with nav rail', () => {
    renderApp('/kiosk/play');
    loginFirst();
    expect(screen.getByText('对弈')).toBeInTheDocument();
    expect(screen.getByText('人机对弈')).toBeInTheDocument();
  });

  it('nav rail items navigate correctly', () => {
    renderApp('/kiosk/play');
    loginFirst();
    fireEvent.click(screen.getByText('死活'));
    expect(screen.getByText('选择难度级别')).toBeInTheDocument();
  });

  it('/kiosk redirects to /kiosk/play', () => {
    renderApp('/kiosk');
    loginFirst();
    expect(screen.getByText('人机对弈')).toBeInTheDocument();
  });

  it('unknown kiosk routes redirect to play', () => {
    renderApp('/kiosk/nonexistent');
    loginFirst();
    expect(screen.getByText('人机对弈')).toBeInTheDocument();
  });
});
