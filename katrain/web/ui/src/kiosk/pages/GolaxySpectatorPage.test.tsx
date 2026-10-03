import { useLayoutEffect } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { ApiError, type GolaxySpectatorSnapshot } from '../../api';
import GolaxySpectatorPage from './GolaxySpectatorPage';

const { platformStatus, platformRoomSnapshot, playSound, auth } = vi.hoisted(() => ({
  platformStatus: vi.fn(), platformRoomSnapshot: vi.fn(), playSound: vi.fn(), auth: { token: 'test-token', isAuthenticated: true },
}));
vi.mock('../../api', async () => ({
  ...await vi.importActual('../../api'),
  API: { platformStatus, platformRoomSnapshot },
}));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => auth }));
vi.mock('../../hooks/useTranslation', () => ({ useTranslation: () => ({ t: (_key: string, fallback: string) => fallback }) }));
vi.mock('../../hooks/useSound', () => ({ useSound: () => ({ play: playSound }) }));

const snapshot: GolaxySpectatorSnapshot = {
  room_id: 'room-a', game_id: '441', room_number: '8799', board_size: 19,
  black: { username: '测试黑方', rank: '7 段' }, white: { username: '测试白方', rank: '6 段' },
  black_stones: ['D16', 'K10'], white_stones: ['Q16', 'L10'], move_number: 4,
  last_move: { color: 'W', coordinate: 'L10' },
  history: [
    { black_stones: [], white_stones: [], move_number: 0, last_move: null },
    { black_stones: ['D16'], white_stones: [], move_number: 1, last_move: { color: 'B', coordinate: 'D16' } },
    { black_stones: ['D16'], white_stones: ['Q16'], move_number: 2, last_move: { color: 'W', coordinate: 'Q16' } },
    { black_stones: ['D16', 'K10'], white_stones: ['Q16'], move_number: 3, last_move: { color: 'B', coordinate: 'K10' } },
    { black_stones: ['D16', 'K10'], white_stones: ['Q16', 'L10'], move_number: 4, last_move: { color: 'W', coordinate: 'L10' } },
  ],
  clocks: null, members: null,
  phase: '进行中', result: null, room_type: '自由战', handicap: 0,
};
const nextSnapshot: GolaxySpectatorSnapshot = {
  ...snapshot, black_stones: ['D16', 'K10', 'Q4'], move_number: 5,
  last_move: { color: 'B', coordinate: 'Q4' },
  history: [...snapshot.history, { black_stones: ['D16', 'K10', 'Q4'], white_stones: ['Q16', 'L10'],
    move_number: 5, last_move: { color: 'B', coordinate: 'Q4' } }],
};
const sixthSnapshot: GolaxySpectatorSnapshot = {
  ...nextSnapshot, white_stones: ['Q16', 'L10', 'R4'], move_number: 6,
  last_move: { color: 'W', coordinate: 'R4' },
  history: [...nextSnapshot.history, { black_stones: nextSnapshot.black_stones,
    white_stones: ['Q16', 'L10', 'R4'], move_number: 6,
    last_move: { color: 'W', coordinate: 'R4' } }],
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
  playSound.mockReset();
  commits.length = 0;
  auth.token = 'test-token';
  auth.isAuthenticated = true;
  localStorage.clear();
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
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('4 手');
    expect(document.querySelectorAll('[data-stone]')).toHaveLength(4);
    expect(document.querySelector('[data-stone="b"][data-at="D16"]')).not.toBeNull();
    expect(screen.queryByText(/已结束/)).not.toBeInTheDocument();
    expect(playSound).not.toHaveBeenCalled();
  });

  it.each([
    { history: snapshot.history.slice(1) },
    { history: snapshot.history.map((entry, i) => i === 2 ? { ...entry, move_number: 9 } : entry) },
    { history: snapshot.history.map((entry, i) => i === 4 ? { ...entry, black_stones: ['Q4'] } : entry) },
    { last_move: { color: 'B', coordinate: 'L10' } },
    { game_id: 'room-a' },
  ])('rejects an incomplete or inconsistent history and identity', async (invalid) => {
    platformRoomSnapshot.mockResolvedValueOnce({ ...snapshot, ...invalid });
    open();
    expect(await screen.findByText('星阵返回的棋谱内容不完整')).toBeInTheDocument();
    expect(document.querySelector('.gob')).toBeNull();
    expect(playSound).not.toHaveBeenCalled();
  });

  it('shows earlier validated positions and returns to the latest without replay sound', async () => {
    open();
    await screen.findByText('测试黑方');
    expect(document.querySelector('[data-stone="w"][data-at="L10"]')).not.toBeNull();
    await userEvent.click(screen.getByRole('button', { name: '上一手' }));
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('3 手');
    expect(document.querySelector('[data-stone="w"][data-at="L10"]')).toBeNull();
    expect(document.querySelector('[data-stone="b"][data-at="K10"]')).not.toBeNull();
    await userEvent.click(screen.getByRole('button', { name: '上一手' }));
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('2 手');
    expect(document.querySelector('[data-stone="b"][data-at="K10"]')).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: /回到最新/ }));
    expect(document.querySelector('[data-stone="w"][data-at="L10"]')).not.toBeNull();
    expect(playSound).not.toHaveBeenCalled();
  });

  it('keeps an earlier board while the latest snapshot advances without sounding on review or return', async () => {
    await openReadyWithFakeTimers();
    act(() => screen.getByRole('button', { name: '上一手' }).click());
    platformRoomSnapshot.mockResolvedValueOnce(nextSnapshot);
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('3 手');
    expect(screen.getByText(/最新：黑 Q4 · 第 5 手/)).toBeInTheDocument();
    expect(document.querySelector('[data-stone="b"][data-at="Q4"]')).toBeNull();
    expect(playSound).not.toHaveBeenCalled();
    act(() => screen.getByRole('button', { name: /回到最新/ }).click());
    expect(document.querySelector('[data-stone="b"][data-at="Q4"]')).not.toBeNull();
    expect(playSound).not.toHaveBeenCalled();
  });

  it('sounds once for a new visible stone, not for initial, duplicate, or local mute', async () => {
    await openReadyWithFakeTimers();
    expect(playSound).not.toHaveBeenCalled();
    platformRoomSnapshot.mockResolvedValueOnce(nextSnapshot);
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(playSound).toHaveBeenCalledExactlyOnceWith('stone');
    platformRoomSnapshot.mockResolvedValueOnce(nextSnapshot);
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(playSound).toHaveBeenCalledTimes(1);
    act(() => screen.getByRole('button', { name: '落子音：开' }).click());
    platformRoomSnapshot.mockResolvedValueOnce(sixthSnapshot);
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(playSound).toHaveBeenCalledTimes(1);
  });

  it('does not sound twice when an older same-game snapshot arrives between copies of move five', async () => {
    await openReadyWithFakeTimers();
    platformRoomSnapshot.mockResolvedValueOnce(nextSnapshot);
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(playSound).toHaveBeenCalledExactlyOnceWith('stone');
    platformRoomSnapshot.mockResolvedValueOnce(snapshot);
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    platformRoomSnapshot.mockResolvedValueOnce(nextSnapshot);
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(playSound).toHaveBeenCalledTimes(1);
    platformRoomSnapshot.mockResolvedValueOnce(sixthSnapshot);
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(playSound).toHaveBeenCalledTimes(2);
  });

  it('sounds once for each new stone in a validated two-move jump', async () => {
    await openReadyWithFakeTimers();
    platformRoomSnapshot.mockResolvedValueOnce(sixthSnapshot);
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(playSound).toHaveBeenCalledTimes(2);
    expect(playSound).toHaveBeenNthCalledWith(1, 'stone');
    expect(playSound).toHaveBeenNthCalledWith(2, 'stone');
  });

  it('skips a pass while sounding the later stone in a two-move jump', async () => {
    await openReadyWithFakeTimers();
    const passed = { ...snapshot, black_stones: snapshot.black_stones,
      white_stones: [...snapshot.white_stones, 'R4'], move_number: 6,
      last_move: { color: 'W' as const, coordinate: 'R4' },
      history: [...snapshot.history,
        { black_stones: snapshot.black_stones, white_stones: snapshot.white_stones,
          move_number: 5, last_move: { color: 'B' as const, coordinate: null } },
        { black_stones: snapshot.black_stones, white_stones: [...snapshot.white_stones, 'R4'],
          move_number: 6, last_move: { color: 'W' as const, coordinate: 'R4' } }],
    };
    platformRoomSnapshot.mockResolvedValueOnce(passed);
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(playSound).toHaveBeenCalledExactlyOnceWith('stone');
  });

  it('does not play a stone sound for a new pass', async () => {
    await openReadyWithFakeTimers();
    const passed = { ...snapshot, move_number: 5, last_move: { color: 'B' as const, coordinate: null },
      history: [...snapshot.history, { black_stones: snapshot.black_stones,
        white_stones: snapshot.white_stones, move_number: 5, last_move: { color: 'B' as const, coordinate: null } }] };
    platformRoomSnapshot.mockResolvedValueOnce(passed);
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(screen.getByText(/最新：黑 停一手 · 第 5 手/)).toBeInTheDocument();
    expect(playSound).not.toHaveBeenCalled();
  });

  it('slows polling after a failed snapshot and does not replay the recovered move', async () => {
    await openReadyWithFakeTimers();
    platformRoomSnapshot.mockRejectedValueOnce(new ApiError(502, 'offline'));
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(screen.getByText('没能同步星阵棋谱')).toBeInTheDocument();
    platformRoomSnapshot.mockResolvedValueOnce(nextSnapshot);
    await act(async () => { vi.advanceTimersByTime(9_999); await Promise.resolve(); });
    expect(platformRoomSnapshot).toHaveBeenCalledTimes(2);
    await act(async () => { vi.advanceTimersByTime(1); await Promise.resolve(); });
    expect(screen.getByText(/最新：黑 Q4 · 第 5 手/)).toBeInTheDocument();
    expect(playSound).not.toHaveBeenCalled();
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(platformRoomSnapshot).toHaveBeenCalledTimes(4);
  });

  it('resets replay without sound when the game ID changes or move count regresses', async () => {
    await openReadyWithFakeTimers();
    act(() => screen.getByRole('button', { name: '上一手' }).click());
    platformRoomSnapshot.mockResolvedValueOnce({ ...nextSnapshot, game_id: '442' });
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('5 手');
    expect(screen.getByRole('button', { name: /正在看最新/ })).toBeDisabled();
    expect(playSound).not.toHaveBeenCalled();

    act(() => screen.getByRole('button', { name: '上一手' }).click());
    const earlier = { ...snapshot, game_id: '442', ...snapshot.history[2],
      history: snapshot.history.slice(0, 3) };
    platformRoomSnapshot.mockResolvedValueOnce(earlier);
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('2 手');
    expect(screen.getByRole('button', { name: /正在看最新/ })).toBeDisabled();
    expect(playSound).not.toHaveBeenCalled();
  });

  it('uses history continuity when the verified game ID is unavailable', async () => {
    platformRoomSnapshot.mockResolvedValueOnce({ ...snapshot, game_id: null });
    await openReadyWithFakeTimers();
    platformRoomSnapshot.mockResolvedValueOnce({ ...nextSnapshot, game_id: null });
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(playSound).toHaveBeenCalledExactlyOnceWith('stone');
    act(() => screen.getByRole('button', { name: '上一手' }).click());
    platformRoomSnapshot.mockResolvedValueOnce({ ...snapshot, game_id: null });
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(screen.getByRole('button', { name: /正在看最新/ })).toBeDisabled();
    expect(playSound).toHaveBeenCalledTimes(1);
    platformRoomSnapshot.mockResolvedValueOnce({ ...nextSnapshot, game_id: null });
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(playSound).toHaveBeenCalledTimes(1);
  });

  it('does not sound for a move first seen after the page was hidden', async () => {
    const hidden = vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
    await openReadyWithFakeTimers();
    hidden.mockReturnValue(true);
    await act(async () => document.dispatchEvent(new Event('visibilitychange')));
    platformRoomSnapshot.mockResolvedValueOnce(nextSnapshot);
    hidden.mockReturnValue(false);
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')); await Promise.resolve(); });
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('5 手');
    expect(playSound).not.toHaveBeenCalled();
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

  it('polls a complete replacement after two seconds without overlapping a pending request', async () => {
    await openReadyWithFakeTimers();
    const next = deferred<GolaxySpectatorSnapshot>();
    platformRoomSnapshot.mockReturnValueOnce(next.promise);
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(platformRoomSnapshot).toHaveBeenCalledTimes(2);
    expect(screen.getByText('正在同步，当前为上次快照')).toBeInTheDocument();
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('4 手');
    await act(async () => { vi.advanceTimersByTime(6_000); await Promise.resolve(); });
    expect(platformRoomSnapshot).toHaveBeenCalledTimes(2);
    await act(async () => next.resolve(nextSnapshot));
    expect(document.querySelectorAll('[data-stone]')).toHaveLength(5);
    expect(document.querySelector('[data-stone="b"][data-at="Q4"]')).not.toBeNull();
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('5 手');
  });

  it('stops while hidden, syncs immediately when visible, and stops after unmount', async () => {
    const hidden = vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
    const page = await openReadyWithFakeTimers();
    hidden.mockReturnValue(true);
    await act(async () => document.dispatchEvent(new Event('visibilitychange')));
    await act(async () => { vi.advanceTimersByTime(6_000); await Promise.resolve(); });
    expect(platformRoomSnapshot).toHaveBeenCalledTimes(1);
    hidden.mockReturnValue(false);
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')); await Promise.resolve(); });
    expect(platformRoomSnapshot).toHaveBeenCalledTimes(2);
    page.unmount();
    await act(async () => { vi.advanceTimersByTime(6_000); await Promise.resolve(); });
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
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('4 手');
    expect(screen.getByText('正在同步，当前为上次快照')).toBeInTheDocument();
    await act(async () => next.resolve(nextSnapshot));
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('5 手');
  });

  it('ignores a hidden request that resolves after the visible resync', async () => {
    const hidden = vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
    const old = deferred<GolaxySpectatorSnapshot>();
    platformRoomSnapshot.mockReturnValueOnce(old.promise)
      .mockResolvedValueOnce(nextSnapshot);
    open();
    expect(await screen.findByText('正在同步星阵棋谱')).toBeInTheDocument();
    hidden.mockReturnValue(true);
    await act(async () => document.dispatchEvent(new Event('visibilitychange')));
    expect((platformRoomSnapshot.mock.calls[0][2] as AbortSignal).aborted).toBe(true);
    hidden.mockReturnValue(false);
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')); await Promise.resolve(); });
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('5 手');
    await act(async () => old.resolve(snapshot));
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('5 手');
  });

  it('ignores room A response after room B has synced', async () => {
    const old = deferred<GolaxySpectatorSnapshot>();
    platformRoomSnapshot.mockReturnValueOnce(old.promise)
      .mockResolvedValueOnce({ ...nextSnapshot, room_id: 'room-b', game_id: '442' });
    open();
    await screen.findByText('正在同步星阵棋谱');
    await userEvent.click(screen.getByRole('button', { name: '切换房间' }));
    expect(await screen.findByText('测试黑方')).toBeInTheDocument();
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('5 手');
    await act(async () => old.resolve(snapshot));
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('5 手');
  });

  it('ignores an old token response after the new identity has synced', async () => {
    const old = deferred<GolaxySpectatorSnapshot>();
    platformRoomSnapshot.mockReturnValueOnce(old.promise)
      .mockResolvedValueOnce(nextSnapshot);
    const page = open();
    await screen.findByText('正在同步星阵棋谱');
    auth.token = 'next-token';
    await act(async () => { page.rerender(<App />); await Promise.resolve(); });
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('5 手');
    await act(async () => old.resolve(snapshot));
    expect(screen.getByTestId('spectator-board').parentElement).toHaveTextContent('5 手');
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
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(document.querySelector('.gob')).toBeNull();
    expect(screen.getByRole('button', { name: action })).toBeInTheDocument();
  });

  it('keeps a 401 reconnect prompt after visibility returns', async () => {
    const hidden = vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
    await openReadyWithFakeTimers();
    platformRoomSnapshot.mockRejectedValueOnce(new ApiError(401, 'expired'));
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
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
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(screen.getByText('星阵返回的棋谱内容不完整')).toBeInTheDocument();
    expect(document.querySelector('.gob')).toBeNull();
  });

  it('hides the prior board after a malformed refresh and retries with a fresh snapshot', async () => {
    await openReadyWithFakeTimers();
    platformRoomSnapshot.mockResolvedValueOnce({ ...snapshot, black_stones: ['D16', 'D16'] });
    await act(async () => { vi.advanceTimersByTime(2_000); await Promise.resolve(); });
    expect(screen.getByText('星阵返回的棋谱内容不完整')).toBeInTheDocument();
    expect(document.querySelector('.gob')).toBeNull();
    vi.useRealTimers();
    await userEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(await screen.findByText('测试黑方')).toBeInTheDocument();
  });
});
