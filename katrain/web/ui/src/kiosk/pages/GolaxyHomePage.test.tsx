import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ApiError } from '../../api';
import GolaxyHomePage from './GolaxyHomePage';

const { platformStatus, platformRooms, platformUsers, platformLogout, platformPlayerProfile, platformPlayerGames, platformFollowPlayer, navigate, vision, auth } = vi.hoisted(() => ({
  platformStatus: vi.fn(),
  platformRooms: vi.fn(), platformUsers: vi.fn(), platformLogout: vi.fn(),
  platformPlayerProfile: vi.fn(), platformPlayerGames: vi.fn(), platformFollowPlayer: vi.fn(),
  navigate: vi.fn(),
  vision: { enabled: true },
  auth: { token: 'token', isAuthenticated: true },
}));
vi.mock('../../api', async () => ({ ...await vi.importActual('../../api'), API: { platformStatus, platformRooms, platformUsers, platformLogout, platformPlayerProfile, platformPlayerGames, platformFollowPlayer } }));
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => auth,
}));
vi.mock('../context/VisionContext', () => ({
  useVision: () => ({ isVisionEnabled: vision.enabled }),
}));
vi.mock('react-router-dom', async () => ({
  ...await vi.importActual('react-router-dom'),
  useNavigate: () => navigate,
}));

const connected = (saved_username?: string) => ({
  platforms: [{ platform: 'golaxy', connected: true, saved_username }],
});
const renderPage = () => render(<MemoryRouter><GolaxyHomePage /></MemoryRouter>);
const room = (number: string) => ({
  room_id: `opaque-${number}`, room_number: number, room_type: null, handicap: null,
  black: null, white: null, phase: '12手', spectator_count: null,
});
const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};

beforeEach(() => {
  vi.resetAllMocks();
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  vision.enabled = true;
  auth.token = 'token';
  auth.isAuthenticated = true;
  localStorage.clear();
  platformStatus.mockResolvedValue(connected('真实账号'));
  platformRooms.mockResolvedValue({ rooms: [] });
  platformUsers.mockResolvedValue({ users: [] });
  platformLogout.mockResolvedValue({ status: 'disconnected', platform: 'golaxy' });
  platformPlayerProfile.mockResolvedValue({ profile: { followed: null } });
  platformPlayerGames.mockResolvedValue({ total: 0, games: [] });
  platformFollowPlayer.mockResolvedValue({ profile: { followed: true } });
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
});

describe('Golaxy home', () => {
  it('shows loading, then the real connected account and the engine entry', async () => {
    let finish!: (value: unknown) => void;
    platformStatus.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    renderPage();
    expect(screen.getByText('正在读取星阵连接')).toBeInTheDocument();
    finish(connected('真实账号'));
    expect(await screen.findByText(/真实账号/)).toBeInTheDocument();
    expect(screen.queryByText('秋水长天')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /人机对弈/ }));
    expect(navigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/engine/golaxy');
  });

  it('does not label a connected scan account as 当前星阵账号 when its nickname is missing', async () => {
    platformStatus.mockResolvedValue(connected());
    renderPage();
    expect(await screen.findByText('昵称未获取')).toBeInTheDocument();
    expect(screen.queryByText('当前星阵账号')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /当前账号/ }));
    expect(screen.getByText('星阵账号 · 昵称未获取')).toBeInTheDocument();
  });

  it('shows the invitation preference when the upstream presence is unknown', async () => {
    platformUsers.mockResolvedValue({ users: [
      { user_id: 'u1', username: '棋友甲', rank: '3段', status: null, invite_able: true },
      { user_id: 'u2', username: '棋友乙', rank: '2段', status: null, invite_able: false },
    ] });
    renderPage();
    await screen.findByText(/真实账号/);
    await userEvent.click(screen.getByRole('tab', { name: '在线棋友' }));
    expect(await screen.findByRole('button', { name: '查看棋友甲的个人资料' })).toHaveTextContent('允许邀请');
    expect(screen.getByRole('button', { name: '查看棋友乙的个人资料' })).toHaveTextContent('拒绝邀请');
  });

  it('shows a login route when the account is disconnected', async () => {
    platformStatus.mockResolvedValue({ platforms: [{ platform: 'golaxy', connected: false }] });
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: '连接星阵' }));
    expect(navigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/login/golaxy');
    expect(screen.queryByRole('button', { name: /人机对弈/ })).not.toBeInTheDocument();
  });

  it('offers retry after a status request fails', async () => {
    platformStatus.mockRejectedValueOnce(new Error('offline'));
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: '重试' }));
    expect(await screen.findByText(/真实账号/)).toBeInTheDocument();
    expect(platformStatus).toHaveBeenCalledTimes(2);
  });

  it('opens pregame routes without touching the input preference', async () => {
    localStorage.setItem('kiosk_play_on_board', 'true');
    renderPage();
    await screen.findByText(/真实账号/);
    expect(screen.queryByText('落子')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /快速匹配/ }));
    expect(navigate).toHaveBeenLastCalledWith('/kiosk/play/cross-platform/golaxy/setup/quick');
    await userEvent.click(screen.getByRole('button', { name: /^房间/ }));
    expect(navigate).toHaveBeenLastCalledWith('/kiosk/play/cross-platform/golaxy/setup/room');
    expect(localStorage.getItem('kiosk_play_on_board')).toBe('true');
  });

  it('renders room facts and opens the read-only spectator route, then switches to players', async () => {
    platformRooms.mockResolvedValue({ rooms: [{ room_id: 'r1', room_number: '1234', room_type: '普通对局', handicap: 0, black: { user_id: 'a', username: '测试黑方', rank: '3段' }, white: { user_id: 'b', username: '测试白方', rank: '2段' }, phase: '进行中', room_user_count: 8, spectator_count: null }] });
    platformUsers.mockResolvedValue({ users: [{ user_id: 'p1', username: '测试棋友', rank: '1段', status: '空闲' }] });
    renderPage();
    const room = await screen.findByRole('button', { name: /1234/ });
    for (const text of ['普通对局', '分先', '测试黑方', '测试白方', '3段', '2段', '进行中', '8 人在房间']) expect(screen.getByText(text)).toBeInTheDocument();
    await userEvent.click(room);
    expect(navigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/golaxy/spectate/r1');
    expect(screen.queryByTestId('kiosk-setup-board')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('tab', { name: '在线棋友' }));
    expect(await screen.findByText('测试棋友')).toBeInTheDocument();
  });

  it('shows verified room users and player avatar, while hiding absent profile facts', async () => {
    platformRooms.mockResolvedValue({ rooms: [{ ...room('1234'), room_user_count: 8 }] });
    platformUsers.mockResolvedValue({ users: [{ user_id: 'u1', username: '棋友甲', rank: '3段', status: null,
      wins: null, losses: null, invite_able: null, avatar_url: 'https://assets.19x19.com/photo/one.png' }] });
    renderPage();
    expect(await screen.findByText('8 人在房间')).toBeInTheDocument();
    expect(screen.queryByText(/人观战/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('tab', { name: '在线棋友' }));
    expect(await screen.findByRole('button', { name: '查看棋友甲的个人资料' })).toHaveTextContent('状态未返回');
    await userEvent.click(await screen.findByRole('button', { name: '查看棋友甲的个人资料' }));
    const dialog = screen.getByRole('dialog');
    expect(dialog.querySelector('img[src="https://assets.19x19.com/photo/one.png"]')).not.toBeNull();
    expect(screen.getByText('u1')).toBeInTheDocument();
    expect(screen.queryByText('地区')).not.toBeInTheDocument();
    expect(screen.queryByText('对弈战绩')).not.toBeInTheDocument();
    expect(screen.queryByText('邀请状态')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '邀请对局' })).toBeDisabled();
  });

  it('opens verified player history and shows the empty state or returned games', async () => {
    platformUsers.mockResolvedValue({ users: [{ user_id: 'u1', username: '棋友甲', status: '空闲', invite_able: true }] });
    platformPlayerGames.mockResolvedValue({ total: 1, games: [{ game_id: '314', black: '黑棋甲', white: '白棋乙', move_number: 145, result: 'B+R', board_size: 19 }] });
    renderPage();
    await screen.findByText(/真实账号/);
    await userEvent.click(screen.getByRole('tab', { name: '在线棋友' }));
    await userEvent.click(await screen.findByRole('button', { name: '查看棋友甲的个人资料' }));
    await userEvent.click(screen.getByRole('button', { name: '查看棋谱' }));
    expect(platformPlayerGames).toHaveBeenCalledWith('golaxy', 'u1', 'token', 0);
    expect(await screen.findByText(/黑棋甲.*白棋乙/)).toBeInTheDocument();
    expect(screen.getByText(/145 手/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '返回资料' }));
    expect(screen.getByRole('button', { name: '查看棋谱' })).toBeInTheDocument();
  });

  it('loads older history pages when the verified total exceeds the first page', async () => {
    platformUsers.mockResolvedValue({ users: [{ user_id: 'u1', username: '棋友甲', status: '空闲' }] });
    const firstPage = Array.from({ length: 10 }, (_, index) => ({ game_id: String(index), black: `黑方${index}`, white: '白方', move_number: 10, result: null, board_size: 19 }));
    platformPlayerGames.mockResolvedValueOnce({ total: 11, games: firstPage })
      .mockResolvedValueOnce({ total: 11, games: [{ game_id: '10', black: '末页黑方', white: '白方', move_number: 11, result: null, board_size: 19 }] });
    renderPage();
    await screen.findByText(/真实账号/);
    await userEvent.click(screen.getByRole('tab', { name: '在线棋友' }));
    await userEvent.click(await screen.findByRole('button', { name: '查看棋友甲的个人资料' }));
    await userEvent.click(screen.getByRole('button', { name: '查看棋谱' }));
    await userEvent.click(await screen.findByRole('button', { name: '加载更多' }));
    expect(platformPlayerGames).toHaveBeenLastCalledWith('golaxy', 'u1', 'token', 1);
    expect(await screen.findByText(/末页黑方/)).toBeInTheDocument();
    expect(screen.getByText(/黑方0/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '加载更多' })).not.toBeInTheDocument();
  });

  it('confirms follow state from Golaxy and changes it through the selected owner', async () => {
    platformUsers.mockResolvedValue({ users: [{ user_id: 'u1', username: '棋友甲', status: '空闲', invite_able: true }] });
    platformPlayerProfile.mockResolvedValue({ profile: { followed: false } });
    renderPage();
    await screen.findByText(/真实账号/);
    await userEvent.click(screen.getByRole('tab', { name: '在线棋友' }));
    await userEvent.click(await screen.findByRole('button', { name: '查看棋友甲的个人资料' }));
    await userEvent.click(await screen.findByRole('button', { name: '添加关注' }));
    expect(platformFollowPlayer).toHaveBeenCalledWith('golaxy', 'u1', true, 'token');
    expect(await screen.findByRole('button', { name: '取消关注' })).toBeInTheDocument();
  });

  it('re-reads follow state after an ambiguous write failure instead of repeating the write', async () => {
    platformUsers.mockResolvedValue({ users: [{ user_id: 'u1', username: '棋友甲', status: '空闲' }] });
    platformPlayerProfile.mockResolvedValueOnce({ profile: { followed: false } })
      .mockResolvedValueOnce({ profile: { followed: true } });
    platformFollowPlayer.mockRejectedValueOnce(new Error('confirmation lost'));
    renderPage();
    await screen.findByText(/真实账号/);
    await userEvent.click(screen.getByRole('tab', { name: '在线棋友' }));
    await userEvent.click(await screen.findByRole('button', { name: '查看棋友甲的个人资料' }));
    await userEvent.click(await screen.findByRole('button', { name: '添加关注' }));
    expect(await screen.findByRole('button', { name: '重新读取关注状态' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '添加关注' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: '重新读取关注状态' }));
    expect(await screen.findByRole('button', { name: '取消关注' })).toBeEnabled();
    expect(platformFollowPlayer).toHaveBeenCalledTimes(1);
  });

  it('keeps the selected player through a refresh and updates only that identity', async () => {
    platformUsers.mockResolvedValueOnce({ users: [{ user_id: 'u1', username: '棋友甲', rank: '3段', status: '空闲', wins: 1, losses: 2, invite_able: true }] })
      .mockResolvedValueOnce({ users: [{ user_id: 'u1', username: '棋友甲', rank: '4段', status: '观战', wins: 2, losses: 2, invite_able: false },
        { user_id: 'u2', username: '棋友乙', rank: '2段', status: '空闲' }] });
    vi.useFakeTimers();
    renderPage();
    await act(async () => { await Promise.resolve(); });
    act(() => screen.getByRole('tab', { name: '在线棋友' }).click());
    act(() => screen.getByRole('button', { name: '查看棋友甲的个人资料' }).click());
    expect(screen.getByRole('dialog')).toHaveTextContent('1 胜 · 2 负');
    await act(async () => vi.advanceTimersByTime(30_000));
    expect(screen.getByRole('dialog')).toHaveTextContent('棋友甲');
    expect(screen.getByRole('dialog')).toHaveTextContent('2 胜 · 2 负');
    expect(screen.getByRole('dialog')).not.toHaveTextContent('棋友乙');
  });

  it.each(['switch', 'logout'] as const)('waits for owner logout before %s', async (intent) => {
    const pending = deferred<{ status: string; platform: string }>();
    platformLogout.mockReturnValue(pending.promise);
    renderPage();
    await screen.findByText(/真实账号/);
    await userEvent.click(screen.getByRole('button', { name: /当前账号/ }));
    await userEvent.click(screen.getByRole('button', { name: intent === 'switch' ? '切换账号' : '退出星阵' }));
    await userEvent.click(screen.getByRole('button', { name: '确认' }));
    expect(platformLogout).toHaveBeenCalledWith('golaxy', 'token');
    expect(screen.getByRole('button', { name: '正在断开' })).toBeDisabled();
    expect(screen.getByRole('button', { name: /当前账号.*真实账号/ })).toBeInTheDocument();
    expect(navigate).not.toHaveBeenCalled();
    await act(async () => pending.resolve({ status: 'disconnected', platform: 'golaxy' }));
    if (intent === 'switch') expect(navigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/login/golaxy');
    else expect(screen.getByRole('button', { name: '连接星阵' })).toBeInTheDocument();
    expect(screen.queryByText(/真实账号/)).not.toBeInTheDocument();
  });

  it('keeps the account and offers retry when logout fails', async () => {
    platformLogout.mockRejectedValueOnce(new Error('offline'));
    renderPage();
    await screen.findByText(/真实账号/);
    await userEvent.click(screen.getByRole('button', { name: /当前账号/ }));
    await userEvent.click(screen.getByRole('button', { name: '切换账号' }));
    await userEvent.click(screen.getByRole('button', { name: '确认' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('没能断开星阵账号');
    expect(screen.getByRole('button', { name: /当前账号.*真实账号/ })).toBeInTheDocument();
    expect(navigate).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: '重试断开' }));
    await waitFor(() => expect(platformLogout).toHaveBeenCalledTimes(2));
    expect(navigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/login/golaxy');
  });

  it('opens each room by its opaque id without leaking a fixture room number into the URL', async () => {
    platformRooms.mockResolvedValue({ rooms: [room('1234'), room('5678'), room('9011')] });
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: /1234 房/ }));
    expect(navigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/golaxy/spectate/opaque-1234');
    await userEvent.click(screen.getByRole('tab', { name: '在线棋友' }));
    await userEvent.click(screen.getByRole('tab', { name: '全部对局' }));
    await userEvent.click(screen.getByRole('button', { name: /5678 房/ }));
    expect(navigate).toHaveBeenLastCalledWith('/kiosk/play/cross-platform/golaxy/spectate/opaque-5678');
  });

  it('distinguishes list failure from empty and supports retry', async () => {
    platformRooms.mockRejectedValueOnce(new Error('offline'));
    renderPage();
    expect(await screen.findByText('没能读取星阵对局')).toBeInTheDocument();
    expect(screen.queryByText('暂无对局')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(await screen.findByText('暂无对局')).toBeInTheDocument();
  });
  it.each(['rooms', 'users'] as const)('retries failed %s independently and preserves the other list', async (failed) => {
    if (failed === 'rooms') {
      platformRooms.mockRejectedValueOnce(new Error('offline'));
      platformUsers.mockResolvedValue({ users: [{ user_id: 'kept', username: '保留棋友', rank: null, status: null }] });
    } else {
      platformUsers.mockRejectedValueOnce(new Error('offline'));
      platformRooms.mockResolvedValue({ rooms: [{ room_id: 'kept', room_number: '5678', room_type: null, handicap: null, black: null, white: null, phase: null, spectator_count: null }] });
    }
    renderPage();
    await screen.findByText(/真实账号/);
    if (failed === 'users') await userEvent.click(screen.getByRole('tab', { name: '在线棋友' }));
    await screen.findByText(failed === 'rooms' ? '没能读取星阵对局' : '没能读取在线棋友');
    await userEvent.click(screen.getByRole('button', { name: '重试' }));
    await screen.findByText(failed === 'rooms' ? '暂无对局' : '暂无在线棋友');
    expect(failed === 'rooms' ? platformRooms : platformUsers).toHaveBeenCalledTimes(2);
    expect(failed === 'rooms' ? platformUsers : platformRooms).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole('tab', { name: failed === 'rooms' ? '在线棋友' : '全部对局' }));
    expect(screen.getByText(failed === 'rooms' ? '保留棋友' : '5678 房')).toBeInTheDocument();
  });

  it.each(['rooms', 'users'] as const)('shows reconnect on %s 401 and hides lobby rows', async (failed) => {
    platformRooms.mockResolvedValue({ rooms: [room('1234')] });
    platformUsers.mockResolvedValue({ users: [{ user_id: 'u', username: '棋友甲', rank: null, status: null }] });
    const target = failed === 'rooms' ? platformRooms : platformUsers;
    const authFailure = deferred<never>();
    target.mockReturnValueOnce(authFailure.promise);
    renderPage();
    await screen.findByText(/真实账号/);
    await waitFor(() => expect(target).toHaveBeenCalledTimes(1));
    await act(async () => authFailure.reject(new ApiError(401, 'expired')));
    const reconnect = await screen.findByRole('button', { name: '星阵登录已失效，重新连接' });
    expect(screen.queryByText('暂无对局')).not.toBeInTheDocument();
    expect(screen.queryByText('1234 房')).not.toBeInTheDocument();
    expect(screen.queryByText('棋友甲')).not.toBeInTheDocument();
    await userEvent.click(reconnect);
    expect(navigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/login/golaxy');
  });

  it('refreshes both lists after 30 seconds, keeps rows during refresh, and ignores a stale response', async () => {
    platformRooms.mockResolvedValueOnce({ rooms: [room('1234')] });
    platformUsers.mockResolvedValue({ users: [] });
    vi.useFakeTimers();
    renderPage();
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByText('1234 房')).toBeInTheDocument();
    act(() => screen.getByRole('tab', { name: '在线棋友' }).click());
    act(() => screen.getByRole('tab', { name: '全部对局' }).click());
    expect(platformRooms).toHaveBeenCalledTimes(1);
    expect(platformUsers).toHaveBeenCalledTimes(1);

    const older = deferred<{ rooms: ReturnType<typeof room>[] }>();
    const newer = deferred<{ rooms: ReturnType<typeof room>[] }>();
    platformRooms.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);
    await act(async () => vi.advanceTimersByTime(30_000));
    expect(platformRooms).toHaveBeenCalledTimes(2);
    expect(platformUsers).toHaveBeenCalledTimes(2);
    expect(screen.getByText('1234 房')).toBeInTheDocument();

    Object.defineProperty(document, 'hidden', { configurable: true, value: true });
    act(() => document.dispatchEvent(new Event('visibilitychange')));
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    act(() => document.dispatchEvent(new Event('visibilitychange')));
    expect(platformRooms).toHaveBeenCalledTimes(3);
    await act(async () => newer.resolve({ rooms: [room('5678')] }));
    expect(screen.getByText('5678 房')).toBeInTheDocument();
    await act(async () => older.resolve({ rooms: [room('9999')] }));
    expect(screen.queryByText('9999 房')).not.toBeInTheDocument();
    expect(screen.getByText('5678 房')).toBeInTheDocument();
  });

  it('preserves the focused invite mode when the lobby refreshes', async () => {
    platformUsers.mockResolvedValue({ users: [{ user_id: 'invitable', username: '可邀棋友', rank: '6段', status: '空闲', invite_able: true }] });
    vi.useFakeTimers();
    renderPage();
    await act(async () => { await Promise.resolve(); });
    act(() => screen.getByRole('tab', { name: '在线棋友' }).click());
    const opener = screen.getByRole('button', { name: '查看可邀棋友的个人资料' });
    act(() => { opener.focus(); opener.click(); });
    act(() => screen.getByRole('button', { name: '邀请对局', exact: true }).click());
    const physicalMode = screen.getByRole('button', { name: '实体棋盘' });
    act(() => { physicalMode.focus(); physicalMode.click(); });
    expect(physicalMode).toHaveFocus();
    expect(physicalMode).toHaveAttribute('aria-pressed', 'true');

    await act(async () => vi.advanceTimersByTime(30_000));
    expect(platformUsers).toHaveBeenCalledTimes(2);
    expect(physicalMode).toHaveFocus();
    expect(physicalMode).toHaveAttribute('aria-pressed', 'true');
    act(() => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });

  it('stops polling while hidden and after unmount', async () => {
    vi.useFakeTimers();
    const page = renderPage();
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByText('暂无对局')).toBeInTheDocument();
    Object.defineProperty(document, 'hidden', { configurable: true, value: true });
    act(() => document.dispatchEvent(new Event('visibilitychange')));
    await act(async () => vi.advanceTimersByTime(90_000));
    expect(platformRooms).toHaveBeenCalledTimes(1);
    expect(platformUsers).toHaveBeenCalledTimes(1);
    page.unmount();
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    act(() => document.dispatchEvent(new Event('visibilitychange')));
    await act(async () => vi.advanceTimersByTime(90_000));
    expect(platformRooms).toHaveBeenCalledTimes(1);
    expect(platformUsers).toHaveBeenCalledTimes(1);
  });

  it('ignores a list response from a previous connection', async () => {
    const oldRooms = deferred<{ rooms: ReturnType<typeof room>[] }>();
    platformRooms.mockReturnValueOnce(oldRooms.promise).mockResolvedValueOnce({ rooms: [room('5678')] });
    const view = renderPage();
    await screen.findByText(/真实账号/);
    await waitFor(() => expect(platformRooms).toHaveBeenCalledTimes(1));
    auth.token = 'next-token';
    view.rerender(<MemoryRouter><GolaxyHomePage /></MemoryRouter>);
    expect(await screen.findByText('5678 房')).toBeInTheDocument();
    await act(async () => oldRooms.resolve({ rooms: [room('1234')] }));
    expect(screen.getByText('5678 房')).toBeInTheDocument();
    expect(screen.queryByText('1234 房')).not.toBeInTheDocument();
  });

  it('shows a retry after a 502 refresh instead of showing stale rows or an empty list', async () => {
    platformRooms.mockResolvedValueOnce({ rooms: [room('1234')] }).mockRejectedValueOnce(new ApiError(502, 'upstream'));
    vi.useFakeTimers();
    renderPage();
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByText('1234 房')).toBeInTheDocument();
    await act(async () => vi.advanceTimersByTime(30_000));
    expect(screen.getByText('没能读取星阵对局')).toBeInTheDocument();
    expect(screen.queryByText('1234 房')).not.toBeInTheDocument();
    expect(screen.queryByText('暂无对局')).not.toBeInTheDocument();
    act(() => screen.getByRole('button', { name: '重试' }).click());
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByText('暂无对局')).toBeInTheDocument();
  });

  it('appends scroll pages, stops at an empty page and retains loaded pages on refresh', async () => {
    platformRooms.mockImplementation((_platform, _token, page) => Promise.resolve({ rooms: page === 0 ? [room('1234')] : page === 1 ? [room('5678')] : [] }));
    vi.useFakeTimers();
    renderPage();
    await act(async () => { await Promise.resolve(); });
    const list = document.querySelector('.golaxy-home__list-body')!;
    fireEvent.scroll(list);
    await act(async () => { await Promise.resolve(); });
    expect(platformRooms).toHaveBeenLastCalledWith('golaxy', 'token', 1);
    expect(screen.getByText('1234 房')).toBeInTheDocument();
    expect(screen.getByText('5678 房')).toBeInTheDocument();
    await act(async () => vi.advanceTimersByTime(30_000));
    expect(screen.getByText('5678 房')).toBeInTheDocument();
    fireEvent.scroll(list);
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByText('没有更多了')).toBeInTheDocument();
    const count = platformRooms.mock.calls.length;
    fireEvent.scroll(list);
    expect(platformRooms).toHaveBeenCalledTimes(count);
  });

  it('resets filter pages and ignores an old filter response', async () => {
    const pending = deferred<{ users: { user_id: string; username: string }[] }>();
    platformUsers.mockResolvedValueOnce({ users: [{ user_id: 'a', username: '全部棋友甲' }] })
      .mockReturnValueOnce(pending.promise).mockResolvedValueOnce({ users: [{ user_id: 'f', username: '关注棋友' }] });
    renderPage();
    await screen.findByText(/真实账号/);
    await userEvent.click(screen.getByRole('tab', { name: '在线棋友' }));
    await userEvent.click(screen.getByRole('button', { name: '同级别' }));
    expect(platformUsers).toHaveBeenLastCalledWith('golaxy', 'token', undefined, { page: 0, filter: 'same_level' });
    await userEvent.click(screen.getByRole('button', { name: '我的关注' }));
    expect(await screen.findByText('关注棋友')).toBeInTheDocument();
    await act(async () => pending.resolve({ users: [{ user_id: 's', username: '过期同级棋友' }] }));
    expect(screen.queryByText('过期同级棋友')).not.toBeInTheDocument();
    expect(screen.queryByText('全部棋友甲')).not.toBeInTheDocument();
  });

  it('does not offer another page for a short following list', async () => {
    platformUsers.mockResolvedValue({ users: [{ user_id: 'fan', username: 'fan', status: '空闲' }] });
    renderPage();
    await userEvent.click(await screen.findByRole('tab', { name: '在线棋友' }));
    await userEvent.click(screen.getByRole('button', { name: '我的关注' }));
    expect(await screen.findByRole('button', { name: '查看fan的个人资料' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '加载更多棋友' })).not.toBeInTheDocument();
  });

  it('retains rows when loading another page fails and retries that page', async () => {
    platformRooms.mockResolvedValueOnce({ rooms: [room('1234')] }).mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ rooms: [room('5678')] });
    renderPage();
    await screen.findByText('1234 房');
    fireEvent.scroll(document.querySelector('.golaxy-home__list-body')!);
    expect(await screen.findByText('没能读取更多，请重试')).toBeInTheDocument();
    expect(screen.getByText('1234 房')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '重试加载更多' }));
    expect(await screen.findByText('5678 房')).toBeInTheDocument();
    expect(platformRooms).toHaveBeenLastCalledWith('golaxy', 'token', 1);
  });

  it('hides invitation and follow actions for the verified self even with the same nickname', async () => {
    platformUsers.mockResolvedValue({ users: [{ user_id: 'owner', username: '本人', invite_able: true, is_self: true }] });
    platformPlayerProfile.mockResolvedValue({ profile: { followed: false, is_self: true } });
    renderPage();
    await screen.findByText(/真实账号/);
    await userEvent.click(screen.getByRole('tab', { name: '在线棋友' }));
    await userEvent.click(await screen.findByRole('button', { name: '查看本人的个人资料' }));
    expect(screen.queryByRole('button', { name: '邀请对局' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '添加关注' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '查看棋谱' })).toBeInTheDocument();
  });

});
