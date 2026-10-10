import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { KioskRoutes } from './KioskApp';

const auth = vi.hoisted(() => ({ authenticated: true }));
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: auth.authenticated ? { username: 'u' } : null, isAuthenticated: auth.authenticated, isLoading: false, status: auth.authenticated ? 'authenticated' : 'guest', isGuest: false, identityKey: 'u' }),
}));
vi.mock('../hooks/useTranslation', () => ({ useTranslation: () => ({ t: (_key: string, fallback: string) => fallback }) }));
vi.mock('./components/layout/KioskLayout', () => ({ default: Outlet }));
vi.mock('./components/vision/PlayInputGuard', () => ({ default: ({ children }: { children: React.ReactNode }) => children }));
vi.mock('./pages/PlayPage', () => ({ default: () => <div data-testid="play-page" /> }));
vi.mock('./pages/PlatformLobbyPage', () => ({ default: () => <div data-testid="ogs-home-page" /> }));
vi.mock('./pages/GolaxyPregameSetupPage', () => ({ default: () => <div data-testid="golaxy-pregame-page" /> }));
vi.mock('./pages/GolaxySpectatorPage', () => ({ default: () => <div data-testid="golaxy-spectator-page" /> }));
vi.mock('./pages/GolaxyHomePage', () => ({ default: () => <div data-testid="golaxy-home-page" /> }));
vi.mock('./pages/GamePage', () => ({ default: ({ engineMode = false }: { engineMode?: boolean }) =>
  <div data-testid="platform-game" data-engine-mode={String(engineMode)} /> }));

const LocationProbe = () => {
  const location = useLocation();
  return <span data-testid="route-location">{location.pathname}{location.search}</span>;
};

const open = (url: string) => render(<MemoryRouter initialEntries={[url]}><Routes>
  <Route path="/kiosk/*" element={<><LocationProbe /><KioskRoutes /></>} />
</Routes></MemoryRouter>);

describe('dedicated platform routes', () => {
  beforeEach(() => { auth.authenticated = true; });

  it('redirects the removed selection page to Play', async () => {
    open('/kiosk/play/cross-platform');
    expect(await screen.findByTestId('play-page')).toBeInTheDocument();
    expect(screen.getByTestId('route-location')).toHaveTextContent('/kiosk/play');
  });

  it('lets a guest open the removed selection bookmark at public Play', async () => {
    auth.authenticated = false;
    open('/kiosk/play/cross-platform');
    expect(await screen.findByTestId('play-page')).toBeInTheDocument();
    expect(screen.getByTestId('route-location')).toHaveTextContent('/kiosk/play');
  });

  it('redirects the old OGS lobby bookmark to the OGS home', async () => {
    open('/kiosk/play/cross-platform/lobby?platform=ogs');
    expect(await screen.findByTestId('ogs-home-page')).toBeInTheDocument();
    expect(screen.getByTestId('route-location')).toHaveTextContent('/kiosk/play/cross-platform/ogs');
  });

  it.each([
    ['/kiosk/play/cross-platform/golaxy', 'golaxy-home-page'],
    ['/kiosk/play/cross-platform/ogs', 'ogs-home-page'],
    ['/kiosk/play/cross-platform/golaxy/setup/quick', 'golaxy-pregame-page'],
    ['/kiosk/play/cross-platform/golaxy/setup/room', 'golaxy-pregame-page'],
    ['/kiosk/play/cross-platform/golaxy/spectate/opaque-room', 'golaxy-spectator-page'],
  ])('directly opens %s after refresh', async (url, testId) => {
    open(url);
    expect(await screen.findByTestId(testId)).toBeInTheDocument();
  });

  it('opens an OGS session with ordinary online game mode', async () => {
    open('/kiosk/play/cross-platform/game/ogs-session');
    expect(await screen.findByTestId('platform-game')).toHaveAttribute('data-engine-mode', 'false');
  });
});
