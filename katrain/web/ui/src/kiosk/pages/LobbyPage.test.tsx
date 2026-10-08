import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import LobbyPage from './LobbyPage';

const nav = vi.fn();
const { ladder, box } = vi.hoisted(() => ({ ladder: vi.fn(), box: { strict: false } }));
vi.mock('react-router-dom', async () => ({ ...(await vi.importActual('react-router-dom')), useNavigate: () => nav }));
const auth = { token: 'tok' as string | null, user: { id: 1, username: '我' }, isAuthenticated: true };
vi.mock('../../context/AuthContext', () => ({ useAuth: () => auth }));
vi.mock('../../features/aiLadder/api', () => ({ getAiLadderStatus: ladder }));
vi.mock('../shell/boxUrls', () => ({ get isStrictBoxKiosk() { return box.strict; } }));
const sent: string[] = [];
let socketCount = 0;
let push: (message: unknown) => void;
class FakeWS {
  static OPEN = 1;
  readyState = 1;
  onmessage: ((event: { data: string }) => void) | null = null;
  onopen: (() => void) | null = null;
  constructor() { socketCount++; push = (m) => this.onmessage?.({ data: JSON.stringify(m) }); queueMicrotask(() => this.onopen?.()); }
  send(value: string) { sent.push(value); }
  close() {}
}
const games = [{ session_id: 'own', player_b: '他', player_w: '我', player_b_id: 9, player_w_id: 1, move_count: 10, player_b_rank_label: '业余 2 段', player_w_rank_label: '业余 2 段' }];
const people = [{ id: 1, username: '我', ladder_rung: 12, rank_label: '业余 2 段', presence: 'playing' }, { id: 2, username: '同段', ladder_rung: 12, rank_label: '业余 2 段', presence: 'idle', kind: 'bot' }, { id: 3, username: '异段', ladder_rung: 13, rank_label: '业余 3 段', presence: 'idle' }];
const page = () => render(<ThemeProvider theme={kioskTheme}><MemoryRouter><LobbyPage /></MemoryRouter></ThemeProvider>);
beforeEach(() => {
  sent.length = 0; socketCount = 0; nav.mockClear(); ladder.mockReset(); box.strict = false; auth.token = 'tok'; auth.user = { id: 1, username: '我' }; auth.isAuthenticated = true;
  vi.stubGlobal('WebSocket', FakeWS);
  vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve({ ok: true, json: () => Promise.resolve(url.includes('/pvp/identity') ? { user_id: 42 } : url.includes('/users/online') ? people : games) })));
  ladder.mockResolvedValue({ placement_state: { phase: 'placed', rung: { rung: 12, rank_name: '业余 2 段' } } });
});
afterEach(() => vi.unstubAllGlobals());
it('shows one unranked match, same-rung filter, own-room return, and no bot/watch affordance', async () => {
  page(); await screen.findByText('同段'); await screen.findByText('我的段位');
  expect(screen.getAllByRole('button', { name: /快速匹配/ })).toHaveLength(1);
  await userEvent.click(screen.getByRole('tab', { name: '同段位' }));
  expect(screen.queryByText('异段')).not.toBeInTheDocument();
  expect(screen.queryByText(/机器人|bot|观战/i)).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: /快速匹配/ }));
  expect(JSON.parse(sent.at(-1)!)).toEqual({ type: 'start_matchmaking' });
  await userEvent.click(screen.getByRole('button', { name: '取消匹配' }));
  expect(JSON.parse(sent.at(-1)!)).toEqual({ type: 'stop_matchmaking' });
  await userEvent.click(screen.getByTestId('lobby-game'));
  expect(nav).toHaveBeenCalledWith('/kiosk/play/pvp/room/own', { state: { backTo: '/kiosk/play/pvp/lobby' } });
});
it('requires placement only for matching and keeps invitations available', async () => {
  ladder.mockResolvedValue({ placement_state: { phase: 'placement', completed_games: 2, total_games: 5 } });
  page(); await screen.findByText('同段'); await screen.findByText('我的段位');
  expect(screen.getByRole('tab', { name: '同段位' })).toBeDisabled();
  await userEvent.click(screen.getByRole('button', { name: /快速匹配/ }));
  expect(screen.getByRole('dialog')).toHaveTextContent('定级');
  expect(sent).toHaveLength(0);
  await userEvent.click(screen.getByRole('button', { name: '稍后再说' }));
  await userEvent.click(within(screen.getByTestId('lobby-player-2')).getByRole('button', { name: '邀请' }));
  expect(JSON.parse(sent.at(-1)!)).toEqual({ type: 'invite', target_id: 2 });
});
it('uses central identity and proxied central rank in strict box mode even when the local shadow differs', async () => {
  box.strict = true; auth.token = null;
  ladder.mockResolvedValue({ placement_state: { phase: 'placed', rung: { rung: 13, rank_name: '业余 3 段' } } });
  vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve({ ok: true, json: () => Promise.resolve(url.includes('/pvp/identity') ? { user_id: 42 } : url.includes('/users/online') ? [
    ...people, { id: 42, username: '中央的我', ladder_rung: 13, rank_label: '业余 3 段', presence: 'playing' },
  ] : [{ ...games[0], session_id: 'local-mirror-room', player_w_id: 42 }]) })));
  page(); await screen.findByText('同段');
  expect(fetch).toHaveBeenCalledWith('/api/pvp/identity', expect.anything());
  expect(within(screen.getByTestId('lobby-player-1')).queryByText('这是你')).not.toBeInTheDocument();
  expect(within(await screen.findByTestId('lobby-player-42')).getByText('这是你')).toBeInTheDocument();
  expect(ladder).toHaveBeenCalled();
  expect(screen.getByText('我的段位').parentElement).toHaveTextContent('业余 3 段');
  await userEvent.click(screen.getByRole('tab', { name: '同段位' }));
  expect(screen.getByTestId('lobby-player-42')).toBeInTheDocument();
  expect(screen.queryByTestId('lobby-player-2')).not.toBeInTheDocument();
  await userEvent.click(screen.getByTestId('lobby-game'));
  expect(nav).toHaveBeenCalledWith('/kiosk/play/pvp/room/local-mirror-room', { state: { backTo: '/kiosk/play/pvp/lobby' } });
});
it('keeps invitations disabled while central identity is unknown and retries identity plus socket', async () => {
  box.strict = true; auth.token = null;
  let identities = 0;
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (url.includes('/pvp/identity')) {
      identities++;
      return Promise.resolve(identities === 1
        ? { ok: false, json: () => Promise.resolve({}) }
        : { ok: true, json: () => Promise.resolve({ user_id: 42 }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(url.includes('/users/online')
      ? [{ id: 1, username: '本地影子', ladder_rung: 12, rank_label: '业余 2 段', presence: 'idle' }, ...people.slice(1)]
      : games) });
  }));
  page();
  const shadow = await screen.findByTestId('lobby-player-1');
  expect(within(shadow).getByRole('button', { name: '邀请' })).toBeDisabled();
  expect(await screen.findByText('无法确认中央账号身份，请重试。')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: '重试' }));
  await waitFor(() => expect(identities).toBe(2));
  await waitFor(() => expect(socketCount).toBe(2));
  await waitFor(() => expect(within(screen.getByTestId('lobby-player-1')).getByRole('button', { name: '邀请' })).toBeEnabled());
  expect(ladder).toHaveBeenCalled();
  expect(screen.getByText('我的段位').parentElement).toHaveTextContent('业余 2 段');
});
it.each([false, true])('shows rank load error and retries instead of claiming the player is unplaced (strict=%s)', async (strict) => {
  box.strict = strict;
  ladder.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ placement_state: { phase: 'placed', rung: { rung: 12, rank_name: '业余 2 段' } } });
  page();
  expect(await screen.findByText('段位读取失败')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /快速匹配/ })).toBeDisabled();
  expect(screen.queryByText('尚未定级')).not.toBeInTheDocument();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: '重试段位' }));
  await waitFor(() => expect(screen.getByText('我的段位').parentElement).toHaveTextContent('业余 2 段'));
});
it('preserves guest gate and incoming invitations', async () => {
  auth.isAuthenticated = false; page();
  expect(screen.getByTestId('lobby-guest')).toHaveTextContent('登录后进在线大厅');
  auth.isAuthenticated = true;
});
it('accepts an incoming invitation without a placement requirement', async () => {
  ladder.mockResolvedValue({ placement_state: { phase: 'placement', completed_games: 0, total_games: 5 } });
  page(); await screen.findByText('同段');
  act(() => push({ type: 'invitation', from_id: 2, from_name: '同段' }));
  await userEvent.click(await screen.findByRole('button', { name: '接受并开局' }));
  expect(JSON.parse(sent.at(-1)!)).toEqual({ type: 'accept_invite', target_id: 2 });
});
it('removes old lobby rows when a refresh fails', async () => {
  page();
  await screen.findByTestId('lobby-player-2');
  expect(screen.getByTestId('lobby-game')).toBeInTheDocument();
  vi.mocked(fetch).mockResolvedValue({ ok: false } as Response);
  act(() => push({ type: 'lobby_update' }));
  await screen.findByText('大厅数据读取失败。');
  await waitFor(() => expect(screen.queryByTestId('lobby-player-2')).not.toBeInTheDocument());
  expect(screen.queryByTestId('lobby-game')).not.toBeInTheDocument();
  expect(screen.queryByText('当前没有进行中的对局。')).not.toBeInTheDocument();
});
