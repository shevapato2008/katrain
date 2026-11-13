import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import AppRouter from './AppRouter';

vi.mock('./context/AuthContext', () => ({ AuthProvider: ({ children }: { children: ReactNode }) => children }));
vi.mock('./context/SettingsContext', () => ({ SettingsProvider: ({ children }: { children: ReactNode }) => children }));
vi.mock('./features/auth/AuthNotice', () => ({ default: () => null }));
vi.mock('./hooks/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string, fallback: string) => key === 'startup:loading' ? 'Loading…' : fallback }),
}));
vi.mock('./kiosk/KioskApp', () => ({
  default: () => { throw new Promise(() => {}); },
}));

afterEach(cleanup);

it('shows a localized loading status while the application is suspended', () => {
  window.history.replaceState({}, '', '/kiosk');
  render(<AppRouter />);
  expect(screen.getByRole('status')).toHaveTextContent('Loading…');
});
