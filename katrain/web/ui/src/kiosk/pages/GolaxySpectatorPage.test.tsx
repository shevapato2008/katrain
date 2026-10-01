import { useLayoutEffect } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { ApiError, type GolaxySpectatorSnapshot } from '../../api';
import GolaxySpectatorPage from './GolaxySpectatorPage';

const { platformStatus, platformRoomSnapshot, auth } = vi.hoisted(() => ({
  platformStatus: vi.fn(), platformRoomSnapshot: vi.fn(), auth: { token: 'test-token', isAuthenticated: true },
}));
vi.mock('../../api', async () => ({
  ...await vi.importActual('../../api'),
  API: { platformStatus, platformRoomSnapshot },
}));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => auth }));
vi.mock('../../hooks/useTranslation', () => ({ useTranslation: () => ({ t: (_key: string, fallback: string) => fallback }) }));

const snapshot: GolaxySpectatorSnapshot = {
  room_id: 'room-a', room_number: '8799', board_size: 19,
  black: { username: '测试黑方', rank: '7 段' }, white: { username: '测试白方', rank: '6 段' },
  black_stones: ['D16', 'K10'], white_stones: ['Q16', 'L10'], move_number: 48,
  phase: '进行中', result: null, room_type: '自由战', handicap: 0,
};
const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
const commits: { path: string; token: string; stone: string | null }[] = [];
const Location = () => {
  const location = useLocation();
  const navigate = useNavigate();
  useLayoutEffect(() => {
    commits.push({ path: location.pathname, token: auth.token, stone: document.querySelector('[data-stone]')?.getAttribute('data-at') ?? null });
  }, [location.pathname, auth.token]);
  return <><span data-testid="location">{location.pathname}</span><button onClick={() => navigate('/kiosk/play/cross-platform/golaxy/spectate/room-b')}>切换房间</button></>;
};
const App = () => <MemoryRouter initialEntries={['/kiosk/play/cross-platform/golaxy/spectate/room-a']}><Routes>
  <Route path="/kiosk/play/cross-platform/golaxy/spectate/:roomId" element={<><Location /><GolaxySpectatorPage /></>} />
  <Route path="/kiosk/play/cross-platform/golaxy" element={<Location />} />
</Routes></MemoryRouter>;
const open = () => render(<App />);
const openReadyWithFakeTimers = async () => {
  vi.useFakeTimers();
  const page = open();
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(screen.getByText('测试黑方')).toBeInTheDocument();
  return page;
};

beforeEach(() => {
  platformStatus.mockReset();
  platformRoomSnapshot.mockReset();
  commits.length = 0;
  auth.token = 'test-token';
  auth.isAuthenticated = true;
  platformStatus.mockResolvedValue({ platforms: [{ platform: 'golaxy', connected: true }] });
  platformRoomSnapshot.mockResolvedValue(snapshot);
});
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

describe('Golaxy spectator', () => {
  it('keeps the board absent while checking the connection and syncing, then renders only the server snapshot', async () => {
    const status = deferred<{ platforms: { platform: string; connected: boolean }[] }>();
    const remote = deferred<GolaxySpectatorSnapshot>();
    platformStatus.mockReturnValue(status.promise);
    platformRoomSnapshot.mockReturnValue(remote.promise);
    open();
    expect(screen.getByRole('status')).toHaveTextContent('正在检查星阵连接');
    expect(document.querySelector('.gob')).toBeNull();
    await act(async () => status.resolve({ platforms: [{ platform: 'golaxy', connected: true }] }));
    expect(screen.getByRole('status')).toHaveTextContent('正在同步星阵棋谱');
    expect(document.querySelector('.gob')).toBeNull();
    await act(async () => remote.resolve(snapshot));
    expect(platformRoomSnapshot).toHaveBeenCalledWith('room-a', 'test-token', expect.any(AbortSignal));
    expect(screen.getByText('8799 房 · 对局观战')).toBeInTheDocument();
    expect(screen.getByText('测试黑方')).toBeInTheDocument();
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('48 手');
    expect(document.querySelectorAll('[data-stone]')).toHaveLength(4);
    expect(document.querySelector('[data-stone="b"][data-at="D16"]')).not.toBeNull();
    expect(screen.queryByText(/已结束/)).not.toBeInTheDocument();
  });

  it('shows a failed snapshot honestly and retries without retaining a board', async () => {
    platformRoomSnapshot.mockRejectedValueOnce(new ApiError(502, 'upstream'));
    open();
    expect(await screen.findByText('没能同步星阵棋谱')).toBeInTheDocument();
    expect(document.querySelector('.gob')).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(await screen.findByText('测试黑方')).toBeInTheDocument();
    expect(platformRoomSnapshot).toHaveBeenCalledTimes(2);
  });

  it('rejects a mismatched room or unsupported board instead of drawing it', async () => {
    platformRoomSnapshot.mockResolvedValueOnce({ ...snapshot, room_id: 'another-room' });
    open();
    expect(await screen.findByText('棋谱内容与当前房间不一致')).toBeInTheDocument();
    expect(document.querySelector('.gob')).toBeNull();
  });

  it('leaves by the visible lobby button', async () => {
    open();
    await screen.findByText('测试黑方');
    await userEvent.click(screen.getByRole('button', { name: '返回对战大厅' }));
    expect(screen.getByTestId('location')).toHaveTextContent('/kiosk/play/cross-platform/golaxy');
  });

  it('does not commit room A stones under room B before effects run', async () => {
    const pending = deferred<GolaxySpectatorSnapshot>();
    open();
    await screen.findByText('测试黑方');
    platformRoomSnapshot.mockReturnValueOnce(pending.promise);
    await userEvent.click(screen.getByRole('button', { name: '切换房间' }));
    expect(commits.at(-1)).toEqual({ path: '/kiosk/play/cross-platform/golaxy/spectate/room-b', token: 'test-token', stone: null });
    expect(document.querySelector('.gob')).toBeNull();
  });

  it('does not commit the previous identity’s stones when the auth token changes', async () => {
    const pending = deferred<GolaxySpectatorSnapshot>();
    const page = open();
    await screen.findByText('测试黑方');
    platformRoomSnapshot.mockReturnValueOnce(pending.promise);
    auth.token = 'next-token';
    await act(async () => { page.rerender(<App />); await Promise.resolve(); });
    expect(commits.at(-1)).toEqual({ path: '/kiosk/play/cross-platform/golaxy/spectate/room-a', token: 'next-token', stone: null });
    expect(document.querySelector('.gob')).toBeNull();
  });

  it('polls a complete replacement after ten seconds without overlapping a pending request', async () => {
    await openReadyWithFakeTimers();
    const next = deferred<GolaxySpectatorSnapshot>();
    platformRoomSnapshot.mockReturnValueOnce(next.promise);
    await act(async () => { vi.advanceTimersByTime(10_000); await Promise.resolve(); });
    expect(platformRoomSnapshot).toHaveBeenCalledTimes(2);
    expect(screen.getByText('正在同步，当前为上次快照')).toBeInTheDocument();
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('48 手');
    await act(async () => { vi.advanceTimersByTime(30_000); await Promise.resolve(); });
    expect(platformRoomSnapshot).toHaveBeenCalledTimes(2);
    await act(async () => next.resolve({ ...snapshot, black_stones: ['Q4'], white_stones: [], move_number: 49 }));
    expect(document.querySelectorAll('[data-stone]')).toHaveLength(1);
    expect(document.querySelector('[data-stone="b"][data-at="Q4"]')).not.toBeNull();
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('49 手');
  });

  it('stops while hidden, syncs immediately when visible, and stops after unmount', async () => {
    const hidden = vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
    const page = await openReadyWithFakeTimers();
    hidden.mockReturnValue(true);
    await act(async () => document.dispatchEvent(new Event('visibilitychange')));
    await act(async () => { vi.advanceTimersByTime(20_000); await Promise.resolve(); });
    expect(platformRoomSnapshot).toHaveBeenCalledTimes(1);
    hidden.mockReturnValue(false);
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')); await Promise.resolve(); });
    expect(platformRoomSnapshot).toHaveBeenCalledTimes(2);
    page.unmount();
    await act(async () => { vi.advanceTimersByTime(20_000); await Promise.resolve(); });
    expect(platformRoomSnapshot).toHaveBeenCalledTimes(2);
  });

  it('keeps the last verified board while a visibility resync is pending', async () => {
    const hidden = vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
    open();
    await screen.findByText('测试黑方');
    const next = deferred<GolaxySpectatorSnapshot>();
    platformRoomSnapshot.mockReturnValueOnce(next.promise);
    hidden.mockReturnValue(true);
    await act(async () => document.dispatchEvent(new Event('visibilitychange')));
    hidden.mockReturnValue(false);
    await act(async () => document.dispatchEvent(new Event('visibilitychange')));
    expect(platformRoomSnapshot).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('48 手');
    expect(screen.getByText('正在同步，当前为上次快照')).toBeInTheDocument();
    await act(async () => next.resolve({ ...snapshot, move_number: 49 }));
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('49 手');
  });

  it('ignores a hidden request that resolves after the visible resync', async () => {
    const hidden = vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
    const old = deferred<GolaxySpectatorSnapshot>();
    platformRoomSnapshot.mockReturnValueOnce(old.promise)
      .mockResolvedValueOnce({ ...snapshot, black_stones: ['Q4'], white_stones: [], move_number: 49 });
    open();
    expect(await screen.findByText('正在同步星阵棋谱')).toBeInTheDocument();
    hidden.mockReturnValue(true);
    await act(async () => document.dispatchEvent(new Event('visibilitychange')));
    expect((platformRoomSnapshot.mock.calls[0][2] as AbortSignal).aborted).toBe(true);
    hidden.mockReturnValue(false);
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')); await Promise.resolve(); });
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('49 手');
    await act(async () => old.resolve(snapshot));
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('49 手');
  });

  it('ignores room A response after room B has synced', async () => {
    const old = deferred<GolaxySpectatorSnapshot>();
    platformRoomSnapshot.mockReturnValueOnce(old.promise)
      .mockResolvedValueOnce({ ...snapshot, room_id: 'room-b', move_number: 49 });
    open();
    await screen.findByText('正在同步星阵棋谱');
    await userEvent.click(screen.getByRole('button', { name: '切换房间' }));
    expect(await screen.findByText('测试黑方')).toBeInTheDocument();
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('49 手');
    await act(async () => old.resolve(snapshot));
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('49 手');
  });

  it('ignores an old token response after the new identity has synced', async () => {
    const old = deferred<GolaxySpectatorSnapshot>();
    platformRoomSnapshot.mockReturnValueOnce(old.promise)
      .mockResolvedValueOnce({ ...snapshot, move_number: 49 });
    const page = open();
    await screen.findByText('正在同步星阵棋谱');
    auth.token = 'next-token';
    await act(async () => { page.rerender(<App />); await Promise.resolve(); });
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('49 手');
    await act(async () => old.resolve(snapshot));
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('49 手');
  });

  it('states that an ended game has no reported result', async () => {
    platformRoomSnapshot.mockResolvedValueOnce({ ...snapshot, phase: '已结束', result: null });
    open();
    expect(await screen.findByText('胜负结果尚未返回')).toBeInTheDocument();
  });

  it.each([
    [401, '星阵登录已失效', '重新连接'],
    [422, '该局型暂不支持观战', '重试'],
    [502, '没能同步星阵棋谱', '重试'],
  ])('hides the prior board when a refresh returns %i', async (status, message, action) => {
    await openReadyWithFakeTimers();
    platformRoomSnapshot.mockRejectedValueOnce(new ApiError(status, 'remote'));
    await act(async () => { vi.advanceTimersByTime(10_000); await Promise.resolve(); });
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(document.querySelector('.gob')).toBeNull();
    expect(screen.getByRole('button', { name: action })).toBeInTheDocument();
  });

  it('keeps a 401 reconnect prompt after visibility returns', async () => {
    const hidden = vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
    await openReadyWithFakeTimers();
    platformRoomSnapshot.mockRejectedValueOnce(new ApiError(401, 'expired'));
    await act(async () => { vi.advanceTimersByTime(10_000); await Promise.resolve(); });
    hidden.mockReturnValue(true);
    await act(async () => document.dispatchEvent(new Event('visibilitychange')));
    hidden.mockReturnValue(false);
    await act(async () => document.dispatchEvent(new Event('visibilitychange')));
    expect(screen.getByText('星阵登录已失效')).toBeInTheDocument();
    expect(platformRoomSnapshot).toHaveBeenCalledTimes(2);
  });

  it('rejects malformed metadata from a refresh', async () => {
    await openReadyWithFakeTimers();
    platformRoomSnapshot.mockResolvedValueOnce({ ...snapshot, phase: {} } as unknown as GolaxySpectatorSnapshot);
    await act(async () => { vi.advanceTimersByTime(10_000); await Promise.resolve(); });
    expect(screen.getByText('星阵返回的棋谱内容不完整')).toBeInTheDocument();
    expect(document.querySelector('.gob')).toBeNull();
  });

  it('hides the prior board after a malformed refresh and retries with a fresh snapshot', async () => {
    await openReadyWithFakeTimers();
    platformRoomSnapshot.mockResolvedValueOnce({ ...snapshot, black_stones: ['D16', 'D16'] });
    await act(async () => { vi.advanceTimersByTime(10_000); await Promise.resolve(); });
    expect(screen.getByText('星阵返回的棋谱内容不完整')).toBeInTheDocument();
    expect(document.querySelector('.gob')).toBeNull();
    vi.useRealTimers();
    await userEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(await screen.findByText('测试黑方')).toBeInTheDocument();
  });
});
