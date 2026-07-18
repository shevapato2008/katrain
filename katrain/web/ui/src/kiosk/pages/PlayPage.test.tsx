import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import type { ActiveSession } from '../utils/activeSession';
import type { PlatformInfo } from '../../api';
import PlayPage from './PlayPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const { readActiveSession } = vi.hoisted(() => ({ readActiveSession: vi.fn() }));
vi.mock('../utils/activeSession', () => ({ readActiveSession }));

// PlayPage reads the username for the greeting and the token to fetch platform status;
// stub AuthContext (no provider in tests). Overridable per-test via mockReturnValue.
const { useAuthMock } = vi.hoisted(() => ({ useAuthMock: vi.fn() }));
vi.mock('../../context/AuthContext', () => ({ useAuth: useAuthMock }));

// 跨平台对弈 section fetches API.platformStatus(token); stub it per-test.
const { platformStatusMock } = vi.hoisted(() => ({ platformStatusMock: vi.fn() }));
vi.mock('../../api', () => ({ API: { platformStatus: platformStatusMock } }));

const pageElement = () => (
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter>
      <PlayPage />
    </MemoryRouter>
  </ThemeProvider>
);

const renderPage = () => render(pageElement());

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
};

const platformRecord = (platform: string, supportsEnginePlay = false): PlatformInfo => ({
  platform,
  connected: true,
  supports_live_play: false,
  supports_automatch: false,
  supports_rooms: false,
  supports_seek_graph: false,
  supports_engine_play: supportsEnginePlay,
});

const platformButtons = () => [
  screen.getByRole('button', { name: /OGS/ }),
  screen.getByRole('button', { name: /野狐围棋/ }),
  screen.getByRole('button', { name: /星阵围棋/ }),
];

const expectPlatformOrder = () => {
  const buttons = platformButtons();
  expect(buttons[0].compareDocumentPosition(buttons[1]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(buttons[1].compareDocumentPosition(buttons[2]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
};

describe('PlayPage', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    readActiveSession.mockReset();
    readActiveSession.mockReturnValue(null);
    useAuthMock.mockReset();
    useAuthMock.mockReturnValue({ user: { username: 'fan' }, isAuthenticated: true, token: null });
    platformStatusMock.mockReset();
    platformStatusMock.mockResolvedValue({ platforms: [] });
  });

  it('renders four equal ModeCards with exactly one primary (jade) card', () => {
    renderPage();
    const modeCardLabels = ['自由对弈', '升降级对弈', '本地对局', '在线大厅'];
    const buttons = modeCardLabels.map((label) => screen.getByText(label).closest('button'));
    expect(buttons.every(Boolean)).toBe(true);
    expect(new Set(buttons)).toHaveLength(4);

    const primaryCards = screen.getAllByTestId('mode-card-primary');
    expect(primaryCards).toHaveLength(1);
    expect(primaryCards[0]).toHaveTextContent('自由对弈');
  });

  it('hides the resume bar when there is no active session', () => {
    readActiveSession.mockReturnValue(null);
    renderPage();

    expect(screen.queryByTestId('resume-game-bar')).toBeNull();
  });

  it('shows the resume bar and navigates to the session route on click', () => {
    const session: ActiveSession = {
      kind: 'game',
      label: '自由对弈 · 执黑',
      route: '/kiosk/play/ai/game/abc',
      ts: 1_720_000_000_000,
    };
    readActiveSession.mockReturnValue(session);
    renderPage();

    const bar = screen.getByTestId('resume-game-bar');
    expect(bar).toHaveTextContent('自由对弈 · 执黑');

    fireEvent.click(bar);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/ai/game/abc');
  });

  it('navigates to game history on entry click', () => {
    renderPage();

    const entry = screen.getByTestId('game-history-entry');
    fireEvent.click(entry);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/pvp/history');
  });

  it('renders three sibling sections including 跨平台对弈', async () => {
    useAuthMock.mockReturnValue({ user: { username: '友' }, isAuthenticated: true, token: 't' });
    platformStatusMock.mockResolvedValue({
      platforms: [{ platform: 'golaxy', connected: true, saved_username: '13800000000', supports_engine_play: true }],
    });
    renderPage();
    expect(screen.getByText('人机对弈')).toBeInTheDocument();
    expect(screen.getByText('人人对弈')).toBeInTheDocument();
    expect(screen.getByText('跨平台对弈')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('星阵围棋')).toBeInTheDocument());
  });

  it('does not render a duplicate 跨平台 mode card under 人机/人人', () => {
    renderPage();
    // The old duplicate ModeCard title. Platform cards use platform names, not this.
    expect(screen.queryByText('连接 OGS、野狐等平台')).not.toBeInTheDocument();
  });

  it('keeps OGS, 野狐围棋, and 星阵围棋 in stable order when the API returns no platforms', async () => {
    const request = deferred<{ platforms: PlatformInfo[] }>();
    useAuthMock.mockReturnValue({ user: { username: '友' }, isAuthenticated: true, token: 't' });
    platformStatusMock.mockReturnValue(request.promise);

    renderPage();

    await waitFor(() => expect(platformStatusMock).toHaveBeenCalledWith('t'));
    await act(async () => {
      request.resolve({ platforms: [] });
      await request.promise;
    });
    expectPlatformOrder();
    platformButtons().forEach((button) => expect(button).toHaveTextContent('点击登录连接'));
  });

  it('keeps OGS, 野狐围棋, and 星阵围棋 in stable order when the API rejects', async () => {
    const request = deferred<{ platforms: PlatformInfo[] }>();
    useAuthMock.mockReturnValue({ user: { username: '友' }, isAuthenticated: true, token: 't' });
    platformStatusMock.mockReturnValue(request.promise);

    renderPage();

    await waitFor(() => expect(platformStatusMock).toHaveBeenCalledWith('t'));
    await act(async () => {
      request.reject(new Error('offline'));
      await request.promise.catch(() => undefined);
    });
    expectPlatformOrder();
    platformButtons().forEach((button) => expect(button).toHaveTextContent('点击登录连接'));
  });

  it('merges one connected platform without changing the other platform labels or routes', async () => {
    useAuthMock.mockReturnValue({ user: { username: '友' }, isAuthenticated: true, token: 't' });
    platformStatusMock.mockResolvedValue({
      platforms: [{ platform: 'golaxy', connected: true, saved_username: '13800000000', supports_engine_play: true }],
    });

    renderPage();

    await waitFor(() => expect(platformButtons()[2]).toHaveTextContent('已连接'));
    const [ogs, fox, golaxy] = platformButtons();
    expect(ogs).toHaveTextContent('点击登录连接');
    expect(fox).toHaveTextContent('点击登录连接');
    expect(golaxy).toHaveTextContent('已连接');

    fireEvent.click(ogs);
    fireEvent.click(fox);
    fireEvent.click(golaxy);
    expect(mockNavigate.mock.calls).toEqual([
      ['/kiosk/play/cross-platform'],
      ['/kiosk/play/cross-platform'],
      ['/kiosk/play/cross-platform/engine/golaxy'],
    ]);
  });

  it('routes a connected non-engine platform to its lobby', async () => {
    useAuthMock.mockReturnValue({ user: { username: '友' }, isAuthenticated: true, token: 't' });
    platformStatusMock.mockResolvedValue({ platforms: [platformRecord('ogs')] });

    renderPage();

    const ogs = await screen.findByRole('button', { name: /OGS 已连接/ });
    fireEvent.click(ogs);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/lobby?platform=ogs');
  });

  it('resets to disconnected defaults immediately when the token changes', async () => {
    let auth = { user: { username: '友' }, isAuthenticated: true, token: 'A' as string | null };
    const requestB = deferred<{ platforms: PlatformInfo[] }>();
    useAuthMock.mockImplementation(() => auth);
    platformStatusMock
      .mockResolvedValueOnce({ platforms: [platformRecord('golaxy', true)] })
      .mockReturnValueOnce(requestB.promise);
    const view = renderPage();
    await screen.findByRole('button', { name: /星阵围棋 已连接/ });

    auth = { ...auth, token: 'B' };
    view.rerender(pageElement());

    platformButtons().forEach((button) => expect(button).toHaveTextContent('点击登录连接'));
  });

  it('keeps the newer token response when the older request resolves last', async () => {
    let auth = { user: { username: '友' }, isAuthenticated: true, token: 'A' as string | null };
    const requestA = deferred<{ platforms: PlatformInfo[] }>();
    const requestB = deferred<{ platforms: PlatformInfo[] }>();
    useAuthMock.mockImplementation(() => auth);
    platformStatusMock.mockReturnValueOnce(requestA.promise).mockReturnValueOnce(requestB.promise);
    const view = renderPage();

    auth = { ...auth, token: 'B' };
    view.rerender(pageElement());
    await act(async () => {
      requestB.resolve({ platforms: [platformRecord('ogs')] });
      await requestB.promise;
    });
    expect(platformButtons()[0]).toHaveTextContent('已连接');

    await act(async () => {
      requestA.resolve({ platforms: [platformRecord('golaxy', true)] });
      await requestA.promise;
    });
    expect(platformButtons()[0]).toHaveTextContent('已连接');
    expect(platformButtons()[2]).toHaveTextContent('点击登录连接');
  });

  it('keeps disconnected defaults after logout when an older request resolves', async () => {
    let auth = { user: { username: '友' }, isAuthenticated: true, token: 'A' as string | null };
    const requestA = deferred<{ platforms: PlatformInfo[] }>();
    useAuthMock.mockImplementation(() => auth);
    platformStatusMock.mockReturnValue(requestA.promise);
    const view = renderPage();

    auth = { ...auth, token: null };
    view.rerender(pageElement());
    platformButtons().forEach((button) => expect(button).toHaveTextContent('点击登录连接'));

    await act(async () => {
      requestA.resolve({ platforms: [platformRecord('golaxy', true)] });
      await requestA.promise;
    });
    platformButtons().forEach((button) => expect(button).toHaveTextContent('点击登录连接'));
  });
});
