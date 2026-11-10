import type { ReactNode } from 'react';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AppRouter from './AppRouter';

vi.mock('./context/AuthContext', () => ({
  AuthProvider: ({ children }: { children: ReactNode }) => children,
}));
vi.mock('./context/SettingsContext', () => ({
  SettingsProvider: ({ children }: { children: ReactNode }) => children,
  useSettings: () => ({ language: 'en' }),
}));
vi.mock('./context/TsumegoProgressContext', () => ({
  TsumegoProgressProvider: ({ children }: { children: ReactNode }) => children,
}));
vi.mock('./galaxy/components/guards/AuthGuard', () => ({
  AuthGuard: ({ children }: { children: ReactNode }) => children,
}));
vi.mock('./galaxy/components/layout/MainLayout', async () => {
  const { Outlet } = await import('react-router-dom');
  return { default: () => <main data-testid="galaxy-shell"><Outlet /></main> };
});
vi.mock('./galaxy/pages/Dashboard', () => ({ default: () => <h1>Galaxy home</h1> }));
vi.mock('./galaxy/pages/PlayMenu', () => ({ default: () => <h1>Galaxy play</h1> }));
vi.mock('./galaxy/pages/ResearchPage', () => ({ default: () => <h1>Galaxy research</h1> }));
vi.mock('./galaxy/pages/GamePage', () => ({ default: () => <h1>Galaxy game</h1> }));
vi.mock('./galaxy/pages/tutorials/TutorialFigurePage', () => ({ default: () => <h1>Galaxy tutorial</h1> }));
vi.mock('./galaxy/pages/KifuLibraryPage', () => ({ default: () => <h1>Galaxy kifu</h1> }));
vi.mock('./kiosk/KioskApp', () => ({ default: () => <h1>Kiosk app</h1> }));
vi.mock('./pages/VideoRecorderPage', () => ({ default: () => <h1>Video recorder</h1> }));
vi.mock('./ZenModeApp', () => ({ default: () => <h1>Zen app</h1> }));

const open = (url: string) => {
  window.history.replaceState({}, '', url);
  return render(<AppRouter />);
};

beforeEach(() => window.history.replaceState({}, '', '/'));

describe.skipIf(__KIOSK_2D_ONLY__)('full application routes', () => {
  it('opens Galaxy as the root homepage', async () => {
    open('/');
    expect(await screen.findByRole('heading', { name: 'Galaxy home' })).toBeInTheDocument();
    expect(screen.getByTestId('galaxy-shell')).toBeInTheDocument();
    expect(screen.queryByText('Zen app')).not.toBeInTheDocument();
    expect(window.location.pathname).toBe('/');
  });

  it.each([
    ['/research?record=123', 'Galaxy research'],
    ['/play/game/session-1', 'Galaxy game'],
    ['/tutorials/section/section-1', 'Galaxy tutorial'],
  ])('opens the root deep link %s without changing its URL', async (url, heading) => {
    open(url);
    expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument();
    expect(window.location.pathname + window.location.search).toBe(url);
  });

  it.each(['/galaxy', '/galaxy/', '/galaxy/play', '/galaxy/research?record=123', '/missing-page'])
    ('shows 404 for %s without redirecting', async (url) => {
      open(url);
      expect(await screen.findByRole('heading', { name: '404' })).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: 'Galaxy home' })).not.toBeInTheDocument();
      expect(window.location.pathname + window.location.search).toBe(url);
    });

  it('keeps the video recorder at /record', async () => {
    open('/record');
    expect(await screen.findByRole('heading', { name: 'Video recorder' })).toBeInTheDocument();
    expect(screen.queryByTestId('galaxy-shell')).not.toBeInTheDocument();
    expect(window.location.pathname).toBe('/record');
  });
});

describe.skipIf(!__KIOSK_2D_ONLY__)('kiosk-only application routes', () => {
  it.each(['/', '/research', '/galaxy/play', '/record'])('sends %s to the kiosk fallback', async (url) => {
    open(url);
    expect(await screen.findByRole('heading', { name: 'Kiosk app' })).toBeInTheDocument();
    expect(screen.queryByTestId('galaxy-shell')).not.toBeInTheDocument();
    expect(screen.queryByText('Zen app')).not.toBeInTheDocument();
    expect(window.location.pathname).toBe('/kiosk');
  });
});

it.each(['/kiosk', '/kiosk/play'])('keeps the kiosk app at %s in every build', async (url) => {
  open(url);
  expect(await screen.findByRole('heading', { name: 'Kiosk app' })).toBeInTheDocument();
  expect(screen.queryByTestId('galaxy-shell')).not.toBeInTheDocument();
  expect(window.location.pathname).toBe(url);
});
