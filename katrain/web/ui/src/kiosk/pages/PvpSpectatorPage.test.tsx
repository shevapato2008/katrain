import { useLayoutEffect } from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import PvpSpectatorPage from './PvpSpectatorPage';
import { KioskRoutes } from '../KioskApp';

const { auth } = vi.hoisted(() => ({ auth: { user: { id: 1 }, token: 'tok' as string | null, isAuthenticated: true } }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => auth }));
vi.mock('../components/layout/KioskLayout', () => ({ default: Outlet }));
vi.mock('../components/vision/PlayInputGuard', () => ({ default: () => { throw new Error('Spectators must never need physical input'); } }));
vi.mock('./LoginPage', () => ({ default: () => <div>需要登录</div> }));
const snapshot = {
  session_id: 'room-a', public_lobby: true, game_ended: false,
  player_b: '黑方棋友', player_w: '白方棋友', player_b_id: 2, player_w_id: -3,
  player_b_rank_label: '业余 2 段', player_w_rank_label: '业余 3 段',
  state: { board_size: [19, 19], stones: [['B', [3, 15], null, 1], ['W', [15, 15], null, 2]],
    last_move: [15, 15], current_node_index: 2, player_to_move: 'B', end_result: null as string | null,
    terminal_result: null, awaiting_count: false },
};
const reply = (data: unknown = snapshot, status = 200) => ({ ok: status === 200, status, json: async () => data }) as Response;
const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((yes) => { resolve = yes; });
  return { promise, resolve };
};
const commits: { path: string; stone: string | null }[] = [];
const Location = () => {
  const location = useLocation();
  const navigate = useNavigate();
  useLayoutEffect(() => {
    commits.push({ path: location.pathname, stone: document.querySelector('[data-stone]')?.getAttribute('data-at') ?? null });
  }, [location.pathname, auth.user.id, auth.token]);
  return <><span data-testid="location">{location.pathname}</span><button onClick={() => navigate('/kiosk/play/pvp/watch/room-b')}>切换房间</button></>;
};
const App = () => <MemoryRouter initialEntries={['/kiosk/play/pvp/watch/room-a']}><Routes>
  <Route path="/kiosk/play/pvp/watch/:sessionId" element={<><Location /><PvpSpectatorPage /></>} />
  <Route path="/kiosk/play/pvp/lobby" element={<span>已返回大厅</span>} />
</Routes></MemoryRouter>;
const settle = async () => { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); };
const open = async () => { const view = render(<App />); await settle(); return view; };
beforeEach(() => {
  vi.useFakeTimers(); auth.user = { id: 1 }; auth.token = 'tok'; auth.isAuthenticated = true; commits.length = 0;
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply()));
  vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible');
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it('renders true metadata and core coordinates using the existing readonly spectator skeleton', async () => {
  await open();
  expect(screen.getByTestId('pvp-spectator-page')).toHaveClass('golaxy-spectator');
  for (const text of ['黑方棋友', '白方棋友', '业余 2 段', '业余 3 段']) expect(screen.getByText(text)).toBeInTheDocument();
  expect(screen.getByText(/第 2 手/)).toBeInTheDocument();
  expect(document.querySelector('[data-stone="b"][data-at="D16"]')).not.toBeNull();
  expect(document.querySelector('[data-stone="w"][data-at="Q16"]')).not.toBeNull();
  expect(screen.getByRole('img', { name: '大厅观战棋盘' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /认输|停一手|悔棋|上一手|分析|实体盘/ })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /返回大厅/ }));
  expect(screen.getByText('已返回大厅')).toBeInTheDocument();
  await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch).toHaveBeenCalledWith('/api/pvp/spectate/room-a', expect.objectContaining({
    method: 'GET', credentials: 'same-origin', headers: { Authorization: 'Bearer tok' }, signal: expect.any(AbortSignal),
  }));
});

it('updates the board every two seconds with serial requests', async () => {
  await open();
  const pending = deferred<Response>(); vi.mocked(fetch).mockReturnValueOnce(pending.promise);
  await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
  expect(fetch).toHaveBeenCalledTimes(2);
  await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
  expect(fetch).toHaveBeenCalledTimes(2);
  pending.resolve(reply({ ...snapshot, state: { ...snapshot.state, stones: [...snapshot.state.stones, ['B', [15, 3], null, 3]],
    last_move: [15, 3], current_node_index: 3, player_to_move: 'W' } }));
  await settle();
  expect(document.querySelector('[data-stone="b"][data-at="Q4"]')).not.toBeNull();
  expect(screen.getByText(/第 3 手/)).toBeInTheDocument();
});

it('clears the previous room immediately and ignores its late response', async () => {
  const pending = deferred<Response>();
  await open();
  vi.mocked(fetch).mockReturnValueOnce(pending.promise).mockResolvedValueOnce(reply({ ...snapshot, session_id: 'room-b',
    player_b: '另一局黑方', state: { ...snapshot.state, stones: [] } }));
  await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
  const firstSignal = vi.mocked(fetch).mock.calls[1][1]?.signal;
  expect(document.querySelector('[data-stone]')).not.toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '切换房间' })); await settle();
  expect(firstSignal?.aborted).toBe(true);
  expect(screen.getByText('另一局黑方')).toBeInTheDocument();
  pending.resolve(reply()); await settle();
  expect(screen.queryByText('黑方棋友')).not.toBeInTheDocument();
  expect(document.querySelector('[data-stone]')).toBeNull();
  expect(commits.find((entry) => entry.path.endsWith('room-b'))?.stone).toBeNull();
});

it.each(['account', 'token'])('resets data and rejects pending requests on %s change', async (change) => {
  const view = await open(); const old = deferred<Response>(); vi.mocked(fetch).mockReturnValueOnce(old.promise);
  await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
  const fresh = deferred<Response>(); vi.mocked(fetch).mockReturnValueOnce(fresh.promise);
  if (change === 'account') auth.user = { id: 7 }; else auth.token = 'new-token';
  view.rerender(<App />);
  expect(document.querySelector('[data-stone]')).toBeNull();
  expect(screen.queryByText('黑方棋友')).not.toBeInTheDocument();
  old.resolve(reply()); await settle(); expect(document.querySelector('[data-stone]')).toBeNull();
  fresh.resolve(reply({ ...snapshot, player_b: '新身份同步' })); await settle();
  expect(screen.getByText('新身份同步')).toBeInTheDocument();
});

it('pauses while hidden, cancels pending data and resyncs on visibility restore', async () => {
  await open(); const pending = deferred<Response>(); vi.mocked(fetch).mockReturnValueOnce(pending.promise);
  await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
  const signal = vi.mocked(fetch).mock.calls[1][1]?.signal;
  vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden'); fireEvent(document, new Event('visibilitychange'));
  expect(signal?.aborted).toBe(true); expect(screen.getByText('已暂停同步')).toBeInTheDocument();
  await act(async () => { await vi.advanceTimersByTimeAsync(10000); }); expect(fetch).toHaveBeenCalledTimes(2);
  pending.resolve(reply({ ...snapshot, player_b: '隐藏期间旧响应' })); await settle();
  expect(screen.queryByText('隐藏期间旧响应')).not.toBeInTheDocument();
  vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible'); fireEvent(document, new Event('visibilitychange')); await settle();
  expect(fetch).toHaveBeenCalledTimes(3); expect(screen.getByText('实时快照')).toBeInTheDocument();
});

it('marks failed refreshes as stale and exposes retry', async () => {
  await open(); vi.mocked(fetch).mockResolvedValueOnce(reply(snapshot, 503));
  await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
  expect(screen.getByRole('alert')).toHaveTextContent('当前不是实时态');
  expect(document.querySelector('[data-stone="b"][data-at="D16"]')).not.toBeNull();
  expect(screen.queryByText('实时快照')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '重试' })); await settle();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument(); expect(screen.getByText('实时快照')).toBeInTheDocument();
});

it('preserves the known terminal board after 404 and shows the result', async () => {
  vi.mocked(fetch).mockResolvedValueOnce(reply({ ...snapshot, game_ended: true,
    state: { ...snapshot.state, end_result: 'W+R' } })).mockResolvedValueOnce(reply(snapshot, 404));
  await open(); await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
  expect(screen.getByText('已结束 · W+R')).toBeInTheDocument();
  expect(document.querySelector('[data-stone="b"][data-at="D16"]')).not.toBeNull();
  expect(screen.getByRole('alert')).toHaveTextContent('已保留最后终局');
});

it('reports nonexistent or finished games when no terminal snapshot is available', async () => {
  vi.mocked(fetch).mockResolvedValue(reply(snapshot, 404)); await open();
  expect(screen.getByRole('alert')).toHaveTextContent('对局不存在或已结束'); expect(document.querySelector('[data-stone]')).toBeNull();
});

it('aborts pending reads on exit and sends no player action', async () => {
  const pending = deferred<Response>(); vi.mocked(fetch).mockReturnValueOnce(pending.promise); const view = await open();
  const signal = vi.mocked(fetch).mock.calls[0][1]?.signal; view.unmount(); expect(signal?.aborted).toBe(true);
  pending.resolve(reply()); await settle(); await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
  expect(fetch).toHaveBeenCalledTimes(1);
});

it('rejects another room snapshot rather than drawing it', async () => {
  vi.mocked(fetch).mockResolvedValue(reply({ ...snapshot, session_id: 'wrong-room' })); await open();
  expect(screen.getByRole('alert')).toHaveTextContent('观战快照内容不完整'); expect(document.querySelector('[data-stone]')).toBeNull();
});


it.each([true, false])('uses the actual auth-guarded route without a play/camera guard (authenticated=%s)', async (authenticated) => {
  auth.isAuthenticated = authenticated;
  render(<MemoryRouter initialEntries={['/kiosk/play/pvp/watch/room-a']}><Routes>
    <Route path="/kiosk/*" element={<KioskRoutes />} />
  </Routes></MemoryRouter>);
  // The routed page is lazy loaded; real timers permit its import to complete.
  vi.useRealTimers();
  expect(await screen.findByText(authenticated ? '黑方棋友' : '需要登录')).toBeInTheDocument();
  if (!authenticated) expect(fetch).not.toHaveBeenCalled();
});


it('shows settlement without presenting either player as ready to place a move', async () => {
  vi.mocked(fetch).mockResolvedValue(reply({ ...snapshot, game_ended: true,
    state: { ...snapshot.state, awaiting_count: true, end_result: 'W+R' } }));
  await open();
  expect(screen.getByText('结算中')).toBeInTheDocument();
  expect(screen.queryByText('轮到落子')).not.toBeInTheDocument();
  expect(document.querySelector('.golaxy-spectator__clock-card.is-turn')).toBeNull();
});


it.each([undefined, null, -1, 1.5, '3'])('shows unknown membership for snapshot spectator_count %s', async (count) => {
  vi.mocked(fetch).mockResolvedValue(reply({ ...snapshot, spectator_count: count }));
  await open();
  expect(screen.getByText('观战人数未返回')).toBeInTheDocument();
  expect(screen.getByRole('img', { name: '大厅观战棋盘' })).toBeInTheDocument();
});

it('shows the verified spectator count returned with the public snapshot', async () => {
  vi.mocked(fetch).mockResolvedValue(reply({ ...snapshot, spectator_count: 0 }));
  await open();
  expect(screen.getByText('0 人观战')).toBeInTheDocument();
});
