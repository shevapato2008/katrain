import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import type { PlatformChallenge } from '../../api';
import PlatformLobbyPage from './PlatformLobbyPage';

const { platformStatus, platformUsers, platformSendChallenge, platformDeclineChallenge, platformChallenges, platformAcceptChallenge, platformActiveGame, getState, writeActiveSession } = vi.hoisted(() => ({
  platformStatus: vi.fn(), platformUsers: vi.fn(), platformSendChallenge: vi.fn(), platformChallenges: vi.fn(),
  platformDeclineChallenge: vi.fn(), platformAcceptChallenge: vi.fn(), platformActiveGame: vi.fn(), getState: vi.fn(), writeActiveSession: vi.fn(),
}));
vi.mock('../../api', () => ({ API: { platformStatus, platformUsers, platformSendChallenge, platformDeclineChallenge, platformChallenges, platformAcceptChallenge, platformActiveGame, getState } }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ token: 'tok', isAuthenticated: true }) }));
vi.mock('../context/VisionContext', () => ({ useVision: () => ({ isVisionEnabled: true }) }));
vi.mock('../utils/activeSession', () => ({ writeActiveSession, readActiveSession: () => null }));
const navigate = vi.fn();
vi.mock('react-router-dom', async () => ({
  ...await vi.importActual('react-router-dom'), useNavigate: () => navigate,
}));

const platformHomeChallenges: PlatformChallenge[] = [
  { platform: 'ogs', challenge_id: 'sample-1', from_user: { platform: 'ogs', user_id: '1', username: 'stone_walker', rank: '4d', rank_numeric: 34, status: 'idle' }, board_size: 19, time_control: { system: 'byoyomi', main_time: 600, period_time: 30, periods: 5 }, rules: 'chinese', ranked: true, handicap: 0, komi: null },
  { platform: 'ogs', challenge_id: 'sample-2', from_user: { platform: 'ogs', user_id: '2', username: 'kosumi', rank: '8k', rank_numeric: 22, status: 'idle' }, board_size: 19, time_control: { system: 'byoyomi', main_time: 1200, period_time: 30, periods: 5 }, rules: 'chinese', ranked: false, handicap: -1, komi: null },
  { platform: 'ogs', challenge_id: 'sample-3', from_user: { platform: 'ogs', user_id: '3', username: 'tenuki_now', rank: '2d', rank_numeric: 32, status: 'idle' }, board_size: 13, time_control: { system: 'absolute', main_time: 180 }, rules: 'chinese', ranked: false, handicap: 0, komi: null },
];

const renderPage = () => render(
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter initialEntries={['/kiosk/play/cross-platform/ogs']}>
      <PlatformLobbyPage />
    </MemoryRouter>
  </ThemeProvider>,
);

beforeEach(() => {
  vi.clearAllMocks();
  platformStatus.mockResolvedValue({ platforms: [{ platform: 'ogs', connected: true, saved_username: 'my_ogs_account', supports_automatch: true }] });
  platformUsers.mockResolvedValue({ users: [{ user_id: '1', username: 'stone_walker', rank: '4d', status: 'idle' }] });
  platformSendChallenge.mockResolvedValue({ challenge_id: 'direct-4' });
  platformDeclineChallenge.mockResolvedValue({ status: 'declined' });
  platformChallenges.mockResolvedValue({ challenges: [] });
  platformAcceptChallenge.mockResolvedValue({ session_id: 'ogs-s1', game: {} });
  platformActiveGame.mockResolvedValue({ session_id: null });
  getState.mockResolvedValue({ state: { board_size: [19, 19] } });
  localStorage.clear();
});
afterEach(() => vi.restoreAllMocks());

describe('OGS 专属页', () => {
  it('treats a connected account with no saved username as connected', async () => {
    platformStatus.mockResolvedValue({ platforms: [{ platform: 'ogs', connected: true }] });
    renderPage();
    expect(await screen.findByText('账号名未返回')).toBeInTheDocument();
    expect(screen.getByTestId('platform-lobby-page')).toHaveTextContent('已连接');
    expect(screen.queryByText('OGS 尚未连接。请先连接账号。')).not.toBeInTheDocument();
  });

  it('shows an explicit disconnected state after a disconnected response', async () => {
    platformStatus.mockResolvedValue({ platforms: [{ platform: 'ogs', connected: false, saved_username: 'old_name' }] });
    renderPage();
    expect(await screen.findByText('OGS 尚未连接。请先连接账号。')).toBeInTheDocument();
    expect(screen.queryByText('old_name')).not.toBeInTheDocument();
    expect(screen.queryByText('正在读取账号')).not.toBeInTheDocument();
  });

  it('keeps status loading distinct from disconnected while the request is pending', () => {
    platformStatus.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText('正在读取账号')).toBeInTheDocument();
    expect(screen.queryByText('OGS 尚未连接。请先连接账号。')).not.toBeInTheDocument();
  });

  it('shows the account, input choice, and three mode cards with honest availability', async () => {
    renderPage();
    expect(await screen.findByText('my_ogs_account')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /返回对弈/ })).toBeInTheDocument();
    expect(screen.getByRole('group', { name: '落子方式' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '快速匹配' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '发起挑战' })).toBeDisabled();
    expect(screen.getAllByText('盒上尚未接通')).toHaveLength(2);
    expect(screen.getByRole('button', { name: '找人下' })).toBeEnabled();
    expect(screen.queryByText('按 OGS 段位匹配')).not.toBeInTheDocument();
  });

  it('renders typed challenge rows and only supported filters', async () => {
    platformChallenges.mockResolvedValue({ challenges: platformHomeChallenges });
    renderPage();
    expect(await screen.findByTestId('platform-challenge-sample-1')).toHaveTextContent('stone_walker');
    expect(screen.getAllByTestId(/^platform-challenge-sample-/)).toHaveLength(3);
    expect(screen.getByRole('button', { name: '全部实时局' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: '19 路' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: '同级别' })).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText('搜索用户名或对局')).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText('搜索用户名')).toBeInTheDocument();
    expect(within(screen.getByTestId('platform-challenge-sample-3')).getByText('实体盘只下 19 路')).toBeInTheDocument();
    expect(within(screen.getByTestId('platform-challenge-sample-1')).getByRole('button', { name: '接受' })).toBeEnabled();
    await userEvent.click(screen.getByRole('button', { name: '19 路' }));
    expect(screen.getAllByTestId(/^platform-challenge-sample-/)).toHaveLength(2);
    await userEvent.type(screen.getByPlaceholderText('搜索用户名'), 'kosumi');
    expect(screen.getAllByTestId(/^platform-challenge-sample-/)).toHaveLength(1);
  });

  it('loads only actual OGS open challenges in production mode', async () => {
    platformChallenges.mockResolvedValue({ challenges: [platformHomeChallenges[0]] });
    renderPage();
    expect(await screen.findByTestId('platform-challenge-sample-1')).toHaveTextContent('stone_walker');
    expect(platformChallenges).toHaveBeenCalledWith('ogs', 'tok');
    expect(screen.queryByText('kosumi')).not.toBeInTheDocument();
    expect(screen.queryByTestId('platform-challenge-sample-2')).not.toBeInTheDocument();
  });

  it('distinguishes a real empty list from an upstream error and can retry', async () => {
    platformChallenges.mockRejectedValueOnce(new Error('upstream 502')).mockResolvedValueOnce({ challenges: [] });
    renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent('没能取回公开挑战');
    expect(screen.queryByText('暂无公开挑战')).not.toBeInTheDocument();
    await userEvent.click(within(screen.getByRole('alert')).getByRole('button', { name: '重试' }));
    expect(await screen.findByText('暂无公开挑战')).toBeInTheDocument();
    expect(platformChallenges).toHaveBeenCalledTimes(2);
  });

  it('lets the user refresh a list that was already loaded', async () => {
    platformChallenges.mockResolvedValueOnce({ challenges: [platformHomeChallenges[0]] })
      .mockResolvedValueOnce({ challenges: [platformHomeChallenges[1]] });
    renderPage();
    expect(await screen.findByTestId('platform-challenge-sample-1')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '刷新公开挑战' }));
    expect(await screen.findByTestId('platform-challenge-sample-2')).toBeInTheDocument();
    expect(screen.queryByTestId('platform-challenge-sample-1')).not.toBeInTheDocument();
    expect(platformChallenges).toHaveBeenCalledTimes(2);
  });

  it('accepts a 19路 challenge after confirmation and records the physical board session', async () => {
    platformChallenges.mockResolvedValue({ challenges: platformHomeChallenges });
    renderPage();
    const row = await screen.findByTestId('platform-challenge-sample-1');
    await userEvent.click(within(row).getByRole('button', { name: '接受' }));
    expect(platformAcceptChallenge).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: '确认接受' }));
    await waitFor(() => expect(platformAcceptChallenge).toHaveBeenCalledWith('ogs', 'sample-1', 'tok'));
    expect(writeActiveSession).toHaveBeenCalledWith(expect.objectContaining({
      kind: 'game', route: '/kiosk/play/cross-platform/game/ogs-s1', onBoard: true,
    }));
    expect(navigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/game/ogs-s1', expect.anything());
  });

  it('keeps 13路 unavailable on the physical board but accepts it in screen mode', async () => {
    platformChallenges.mockResolvedValue({ challenges: platformHomeChallenges });
    renderPage();
    const row = await screen.findByTestId('platform-challenge-sample-3');
    expect(within(row).getByText('实体盘只下 19 路')).toBeInTheDocument();
    expect(within(row).queryByRole('button', { name: '接受' })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '屏幕' }));
    await userEvent.click(within(row).getByRole('button', { name: '接受' }));
    await userEvent.click(screen.getByRole('button', { name: '确认接受' }));
    await waitFor(() => expect(writeActiveSession).toHaveBeenCalledWith(expect.objectContaining({ onBoard: false })));
  });

  it('guards duplicate accepts while pending, then leaves the dialog open for retry on failure', async () => {
    platformChallenges.mockResolvedValue({ challenges: [platformHomeChallenges[0]] });
    let rejectFirst!: (error: Error) => void;
    platformAcceptChallenge.mockReturnValueOnce(new Promise((_, reject) => { rejectFirst = reject; }))
      .mockResolvedValueOnce({ session_id: 'ogs-s2' });
    renderPage();
    await userEvent.click(within(await screen.findByTestId('platform-challenge-sample-1')).getByRole('button', { name: '接受' }));
    const confirm = screen.getByRole('button', { name: '确认接受' });
    await userEvent.click(confirm);
    expect(confirm).toBeDisabled();
    expect(platformAcceptChallenge).toHaveBeenCalledTimes(1);
    rejectFirst(new Error('OGS unavailable'));
    expect(await screen.findByRole('alert')).toHaveTextContent('OGS unavailable');
    expect(navigate).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: '重试接受' }));
    await waitFor(() => expect(platformAcceptChallenge).toHaveBeenCalledTimes(2));
    expect(navigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/game/ogs-s2', expect.anything());
  });

  it('offers a deliberate Continue action for an active OGS game without auto-navigation', async () => {
    platformActiveGame.mockResolvedValue({ session_id: 'ongoing-1' });
    renderPage();
    const continueButton = await screen.findByRole('button', { name: '继续对局' });
    expect(navigate).not.toHaveBeenCalled();
    await userEvent.click(continueButton);
    expect(getState).toHaveBeenCalledWith('ongoing-1', 'tok');
    expect(writeActiveSession).toHaveBeenCalledWith(expect.objectContaining({
      route: '/kiosk/play/cross-platform/game/ongoing-1', onBoard: true,
    }));
    expect(navigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/game/ongoing-1', expect.anything());
  });

  it('resumes a 13-road OGS game on screen even when physical play was selected', async () => {
    platformActiveGame.mockResolvedValue({ session_id: 'ongoing-13' });
    getState.mockResolvedValue({ state: { board_size: [13, 13] } });
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: '继续对局' }));
    expect(writeActiveSession).toHaveBeenCalledWith(expect.objectContaining({ onBoard: false }));
  });

  it('shows an error and does not enter when the authoritative board size is unavailable', async () => {
    platformActiveGame.mockResolvedValue({ session_id: 'ongoing-unknown' });
    getState.mockRejectedValue(new Error('502'));
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: '继续对局' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('没能确认这局的棋盘路数');
    expect(writeActiveSession).not.toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
  });

  it('shows an active-game request error distinctly and can retry', async () => {
    platformActiveGame.mockRejectedValueOnce(new Error('upstream')).mockResolvedValueOnce({ session_id: 'ongoing-2' });
    renderPage();
    const error = await screen.findByText('没能读取进行中的 OGS 对局');
    await userEvent.click(within(error.parentElement as HTMLElement).getByRole('button', { name: '重试' }));
    expect(await screen.findByRole('button', { name: '继续对局' })).toBeInTheDocument();
    expect(platformActiveGame).toHaveBeenCalledTimes(2);
  });

  it('keeps the existing username challenge confirmation and only searches on Enter', async () => {
    let pending = false;
    platformActiveGame.mockImplementation(async () => ({ session_id: null, pending_challenge_id: pending ? 'direct-4' : null }));
    platformSendChallenge.mockImplementation(async () => { pending = true; return { challenge_id: 'direct-4' }; });
    platformDeclineChallenge.mockImplementation(async () => { pending = false; return { status: 'declined' }; });
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: '找人下' }));
    const input = screen.getByTestId('platform-search');
    await waitFor(() => expect(screen.getByTestId('platform-user')).toBeInTheDocument());
    const calls = platformUsers.mock.calls.length;
    await userEvent.type(input, 'stone');
    expect(platformUsers).toHaveBeenCalledTimes(calls);
    await userEvent.keyboard('{Enter}');
    await waitFor(() => expect(platformUsers).toHaveBeenLastCalledWith('ogs', 'tok', 'stone'));
    await userEvent.click(within(screen.getByTestId('platform-user')).getByRole('button', { name: '挑战' }));
    expect(platformSendChallenge).not.toHaveBeenCalled();
    await userEvent.click(within(screen.getByTestId('platform-challenge-confirm')).getByRole('button', { name: '发出挑战' }));
    await waitFor(() => expect(platformSendChallenge).toHaveBeenCalledWith('ogs', { user_id: '1', board_size: 19, rules: 'chinese', ranked: true }, 'tok'));
    expect(await screen.findByText('等待 stone_walker 接受挑战')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '取消约战' }));
    await waitFor(() => expect(platformDeclineChallenge).toHaveBeenCalledWith('ogs', 'direct-4', 'tok'));
    expect(screen.queryByText('等待 stone_walker 接受挑战')).not.toBeInTheDocument();
  });

  it('restores an outgoing invitation on return and clears it after remote rejection', async () => {
    let poll!: () => void;
    vi.spyOn(window, 'setInterval').mockImplementation((handler, timeout) => {
      if (timeout === 15000) poll = handler as () => void;
      return 1;
    });
    platformActiveGame.mockResolvedValueOnce({ session_id: null, pending_challenge_id: 'direct-4' })
      .mockResolvedValue({ session_id: null, pending_challenge_id: null });
    renderPage();
    expect(await screen.findByText('等待对方接受挑战')).toBeInTheDocument();
    await act(async () => { poll(); });
    await waitFor(() => expect(screen.queryByText('等待对方接受挑战')).not.toBeInTheDocument());
    expect(screen.queryByRole('button', { name: '取消约战' })).not.toBeInTheDocument();
  });
});
