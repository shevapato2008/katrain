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

const { useEngineReadinessMock } = vi.hoisted(() => ({ useEngineReadinessMock: vi.fn() }));
vi.mock('../context/EngineReadinessContext', () => ({ useEngineReadiness: useEngineReadinessMock }));

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

// 顺序 = 稿子的顺序:能用的排前面,「即将上线」的野狐排**最后**。
// 下面 `expectPlatformOrder` 断言的就是这个顺序,所以这三行不是随手写的。
const platformButtons = () => [
  screen.getByRole('button', { name: /OGS/ }),
  screen.getByRole('button', { name: /星阵围棋/ }),
  screen.getByRole('button', { name: /野狐围棋/ }),
];

/**
 * 「三家都没连上」长什么样。**野狐和另外两家不是同一种「没连上」**:
 * 它在 `PLATFORM_META` 里就带着 `comingSoon`,连接页早就把它的按钮禁掉、写「即将上线」——
 * 而上一版首页却请人「点击登录连接」一个连不上的平台。同一个事实,两处口径必须一致。
 */
const expectAllDisconnected = () => {
  const [ogs, golaxy, fox] = platformButtons();
  expect(ogs).toHaveTextContent('点击登录');
  expect(golaxy).toHaveTextContent('点击登录');
  expect(fox).toHaveTextContent('接口还没通');
  expect(fox).toHaveTextContent('暂不能对弈');
  expect(fox).not.toHaveTextContent('即将上线');
  expect(fox).toBeDisabled();
};

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
    useEngineReadinessMock.mockReset();
    useEngineReadinessMock.mockReturnValue('ready');
    platformStatusMock.mockReset();
    platformStatusMock.mockResolvedValue({ platforms: [] });
  });

  it('四张模式卡完全等样式 —— 稿子里没有「主推」那一张', () => {
    renderPage();
    const modeCardLabels = ['自由对弈', '升降级对弈', '本地对局', '在线大厅'];
    const buttons = modeCardLabels.map((label) => screen.getByText(label).closest('button'));
    expect(buttons.every(Boolean)).toBe(true);
    expect(new Set(buttons)).toHaveLength(4);

    // 上一版把「自由对弈」做成 jade 渐变的 primary 卡(testid `mode-card-primary`)。
    // 稿子四张一模一样 —— 差别由**内容**表达,不由卡的等级表达:
    // 把一张卡做成主推,等于替用户决定他该下哪一种。
    for (const b of buttons) expect(b!.className).toBe('kiosk-card');
  });

  it.each([
    ['warming', 'AI 引擎准备中，稍后即可开始'],
    ['unavailable', 'AI 引擎暂未就绪，请稍后重试'],
  ])('disables only AI modes while engine readiness is %s', (readiness, subtitle) => {
    useEngineReadinessMock.mockReturnValue(readiness);
    renderPage();

    expect(screen.getByText('自由对弈').closest('button')).toBeDisabled();
    expect(screen.getByText('升降级对弈').closest('button')).toBeDisabled();
    expect(screen.getByText('本地对局').closest('button')).toBeEnabled();
    expect(screen.getByText('在线大厅').closest('button')).toBeEnabled();
    expect(screen.getAllByText(subtitle)).toHaveLength(2);
  });

  it('restores AI mode subtitles and navigation when the engine is ready', () => {
    useEngineReadinessMock.mockReturnValue('ready');
    renderPage();

    const free = screen.getByText('自由对弈').closest('button')!;
    const ranked = screen.getByText('升降级对弈').closest('button')!;
    expect(free).toBeEnabled();
    expect(ranked).toBeEnabled();
    expect(free).toHaveTextContent('自己挑强度 · 可以看形势判断');
    expect(ranked).toHaveTextContent('按棋力自动配档 · 全程封分析');

    fireEvent.click(free);
    fireEvent.click(ranked);
    expect(mockNavigate.mock.calls).toEqual([
      ['/kiosk/play/ai/setup/free'],
      ['/kiosk/play/ai/setup/ranked'],
    ]);
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

    // 按稿子,整条不是按钮 —— 右端那颗「恢复」药丸才是。上一版把整条做成 ButtonBase,
    // 触点更大,但药丸就成了一个按不动的装饰(条上再嵌按钮是非法 HTML)。
    fireEvent.click(screen.getByRole('button', { name: '恢复' }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/ai/game/abc');
  });

  it('「全部对局」落到复盘首页 —— 不再是那个没有返回入口的死胡同屏', () => {
    renderPage();

    // 2026-08-21 Fan 裁定:对局历史收成一张普通卡,落点改**复盘首页**;
    // 原来的 `/kiosk/play/pvp/history` 是个死胡同(没有任何返回入口,Dock 也不出)。
    fireEvent.click(screen.getByText('全部对局').closest('button')!);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/report');
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
    expectAllDisconnected();
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
    expectAllDisconnected();
  });

  it('merges one connected platform without changing the other platform labels or routes', async () => {
    useAuthMock.mockReturnValue({ user: { username: '友' }, isAuthenticated: true, token: 't' });
    platformStatusMock.mockResolvedValue({
      platforms: [{ platform: 'golaxy', connected: true, saved_username: '13800000000', supports_engine_play: true }],
    });

    renderPage();

    await waitFor(() => expect(platformButtons()[1]).toHaveTextContent('已连接'));   // [1] = 星阵
    const [ogs, golaxy, fox] = platformButtons();
    expect(ogs).toHaveTextContent('点击登录');
    expect(fox).toHaveTextContent('接口还没通');
    expect(golaxy).toHaveTextContent('已连接');

    fireEvent.click(ogs);
    fireEvent.click(fox);            // 禁用的,点了不该有任何去向
    fireEvent.click(golaxy);
    expect(mockNavigate.mock.calls).toEqual([
      ['/kiosk/play/cross-platform'],
      ['/kiosk/play/cross-platform/engine/golaxy'],
    ]);
  });

  it('routes a connected non-engine platform to its lobby', async () => {
    useAuthMock.mockReturnValue({ user: { username: '友' }, isAuthenticated: true, token: 't' });
    platformStatusMock.mockResolvedValue({ platforms: [platformRecord('ogs')] });

    renderPage();

    const ogs = await screen.findByRole('button', { name: /^OGS，已连接/ });
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
    await screen.findByRole('button', { name: /^星阵围棋，已连接/ });

    auth = { ...auth, token: 'B' };
    view.rerender(pageElement());

    expectAllDisconnected();
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
    expect(platformButtons()[1]).toHaveTextContent('点击登录');   // [1] = 星阵,不是野狐
  });

  it('本地对局卡片未登录时说要先登录', () => {
    useAuthMock.mockReturnValue({ user: null, isAuthenticated: false, token: null });
    renderPage();

    const card = screen.getByText('本地对局').closest('button')!;
    expect(card).toHaveTextContent('要先登录 · 下完自动存谱');
    expect(card).not.toHaveTextContent('两人在同一块实体盘上下');
  });

  it('本地对局卡片已登录时仍说两人在同一块实体盘上下', () => {
    useAuthMock.mockReturnValue({ user: { username: 'fan' }, isAuthenticated: true, token: null });
    renderPage();

    const card = screen.getByText('本地对局').closest('button')!;
    expect(card).toHaveTextContent('两人在同一块实体盘上下');
    expect(card).not.toHaveTextContent('要先登录');
  });

  it('keeps disconnected defaults after logout when an older request resolves', async () => {
    let auth = {
      user: { username: '友' } as { username: string } | null,
      isAuthenticated: true,
      token: 'A' as string | null,
    };
    const requestA = deferred<{ platforms: PlatformInfo[] }>();
    useAuthMock.mockImplementation(() => auth);
    platformStatusMock.mockReturnValue(requestA.promise);
    const view = renderPage();

    // 登出 = user 和 token 一起清掉(`AuthContext.logout` 就是这么做的)。
    // 只清 token、人还登录着 —— 那是严格盒端 SSO 的**常态**,不是登出(见下一条)。
    auth = { user: null, isAuthenticated: false, token: null };
    view.rerender(pageElement());
    expectAllDisconnected();

    await act(async () => {
      requestA.resolve({ platforms: [platformRecord('golaxy', true)] });
      await requestA.promise;
    });
    expectAllDisconnected();
  });

  /**
   * 回归钉子(P16):严格盒端 SSO 里 `token` 恒为 null,身份在 HttpOnly cookie 里。
   * 原来的 `if (token)` 让盒上**已登录**的人永远只看到兜底状态 ——
   * 而 `/api/v1/platforms/status` 认 cookie,请求发出去本来就会成功。
   */
  it('盒上 token 恒为 null 但已登录:照常请求平台状态,连上的平台照实显示', async () => {
    useAuthMock.mockReturnValue({ user: { username: 'fan' }, isAuthenticated: true, token: null });
    platformStatusMock.mockResolvedValue({ platforms: [platformRecord('golaxy', true)] });
    renderPage();
    await waitFor(() => expect(platformStatusMock).toHaveBeenCalledWith(null));
    await waitFor(() => expect(platformButtons()[1]).toHaveTextContent('已连接'));   // [1] = 星阵
  });

  it('游客不请求平台状态 —— 那个端点要登录,发了也是 401', () => {
    useAuthMock.mockReturnValue({ user: null, isAuthenticated: false, token: null });
    renderPage();
    expect(platformStatusMock).not.toHaveBeenCalled();
    expectAllDisconnected();
  });

  it('盒端已登录且 token=null 时拉取状态并直达星阵人机开局', async () => {
    useAuthMock.mockReturnValue({ user: { username: '友' }, isAuthenticated: true, token: null });
    platformStatusMock.mockResolvedValue({ platforms: [platformRecord('golaxy', true)] });

    renderPage();

    const golaxy = await screen.findByRole('button', { name: /^星阵围棋，已连接/ });
    expect(platformStatusMock).toHaveBeenCalledWith(null);
    fireEvent.click(golaxy);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/engine/golaxy');
  });
});
