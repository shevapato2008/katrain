import { beforeEach, expect, it, vi } from 'vitest';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import HvHLobbyPage from './HvHLobbyPage';

const navigate = vi.fn();
const { getAiLadderStatus } = vi.hoisted(() => ({ getAiLadderStatus: vi.fn() }));
vi.mock('react-router-dom', async () => ({ ...(await vi.importActual('react-router-dom')), useNavigate: () => navigate }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ user: { id: 1, username: '我' }, token: 'tok' }) }));
vi.mock('../../context/SettingsContext', () => ({ useSettings: () => ({}) }));
vi.mock('../../features/aiLadder/api', () => ({ getAiLadderStatus }));
vi.mock('../context/GameNavigationContext', () => ({ useGameNavigation: () => ({ requestNavigation: navigate }) }));
vi.mock('../components/FriendsPanel', () => ({ default: () => <div /> }));

const sent: string[] = [];
let push: (message: unknown) => void = () => {};
class FakeWS {
  static OPEN = 1;
  readyState = 1;
  onmessage: ((event: { data: string }) => void) | null = null;
  onopen: (() => void) | null = null;
  constructor() { push = (message) => this.onmessage?.({ data: JSON.stringify(message) }); queueMicrotask(() => this.onopen?.()); }
  send(value: string) { sent.push(value); }
  close() {}
}
beforeEach(() => {
  sent.length = 0;
  navigate.mockClear();
  vi.stubGlobal('WebSocket', FakeWS);
  vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve({ ok: true, json: () => Promise.resolve(url.includes('online') ? [
    { id: 1, username: '我', ladder_rung: 12, rank_label: '业余 2 段', presence: 'idle' },
    { id: 2, username: '同段', ladder_rung: 12, rank_label: '业余 2 段', presence: 'idle', kind: 'bot' },
    { id: 3, username: '异段', ladder_rung: 13, rank_label: '业余 3 段', presence: 'idle' },
  ] : [{ session_id: 'own', player_b: '别人', player_w: '我', player_b_id: 9, player_w_id: 1, move_count: 7 }]) })));
  getAiLadderStatus.mockResolvedValue({ placement_state: { phase: 'placed', rung: { rung: 12, rank_name: '业余 2 段' } } });
});
it('offers one unranked match and filters by canonical rung without bot markers', async () => {
  render(<MemoryRouter><HvHLobbyPage /></MemoryRouter>);
  await screen.findByText('同段');
  await screen.findByText('已定级');
  expect(screen.getAllByRole('button', { name: /快速匹配/ })).toHaveLength(1);
  await userEvent.click(screen.getByRole('tab', { name: '同段位' }));
  expect(screen.queryByText('异段')).not.toBeInTheDocument();
  expect(screen.queryByText(/机器人|bot/i)).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: /快速匹配/ }));
  expect(JSON.parse(sent.at(-1)!)).toEqual({ type: 'start_matchmaking' });
});
it('returns to own room and cancels the queue', async () => {
  render(<MemoryRouter><HvHLobbyPage /></MemoryRouter>);
  await screen.findByText('同段');
  await screen.findByText('已定级');
  await userEvent.click(screen.getByTestId('lobby-game'));
  expect(navigate).toHaveBeenCalledWith('/galaxy/play/human/room/own');
  await userEvent.click(screen.getByRole('button', { name: /快速匹配/ }));
  await userEvent.click(screen.getByRole('button', { name: '取消匹配' }));
  expect(JSON.parse(sent.at(-1)!)).toEqual({ type: 'stop_matchmaking' });
});
it('opens another pair\'s ongoing game from a keyboard accessible card', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve({ ok: true, json: () => Promise.resolve(url.includes('multiplayer')
    ? [{ session_id: 'watch', player_b: '松风', player_w: '小舟', player_b_id: -1, player_w_id: -2, move_count: 8 }] : []) })));
  render(<MemoryRouter><HvHLobbyPage /></MemoryRouter>);
  const game = await screen.findByTestId('lobby-game');
  expect(game.tagName).toBe('BUTTON');
  expect(game).toHaveAccessibleName('观战 松风 对 小舟');
  expect(within(game).queryByRole('button')).not.toBeInTheDocument();
  game.focus();
  await userEvent.keyboard('{Enter}');
  expect(navigate).toHaveBeenCalledWith('/galaxy/play/human/room/watch');
});
it('shows placement dialog only for matching and allows invitation when unplaced', async () => {
  getAiLadderStatus.mockResolvedValue({ placement_state: { phase: 'placement', total_games: 5, completed_games: 2 } });
  render(<MemoryRouter><HvHLobbyPage /></MemoryRouter>);
  await screen.findByText('同段');
  await screen.findByText('未定级');
  await userEvent.click(screen.getByRole('button', { name: /快速匹配/ }));
  expect(screen.getByRole('dialog')).toHaveTextContent('定级');
  expect(sent).toHaveLength(0);
  await userEvent.click(screen.getByRole('button', { name: '返回大厅' }));
  await userEvent.click(within(screen.getByTestId('lobby-player-2')).getByRole('button', { name: '邀请' }));
  expect(JSON.parse(sent.at(-1)!)).toEqual({ type: 'invite', target_id: 2 });
  await userEvent.click(within(screen.getByTestId('lobby-player-3')).getByRole('button', { name: '邀请' }));
  expect(JSON.parse(sent.at(-1)!)).toEqual({ type: 'invite', target_id: 3 });
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});
it('closes matching and shows a non-placement queue rejection', async () => {
  render(<MemoryRouter><HvHLobbyPage /></MemoryRouter>);
  await screen.findByText('已定级');
  await userEvent.click(screen.getByRole('button', { name: /快速匹配/ }));
  expect(screen.getByRole('dialog')).toHaveTextContent('正在寻找');
  act(() => push({ type: 'error', code: 'QUEUE_FULL', message: '队列暂不可用' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent('队列暂不可用');
});
it('shows rank load error and retries instead of claiming the player is unplaced', async () => {
  getAiLadderStatus.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ placement_state: { phase: 'placed', rung: { rung: 12, rank_name: '业余 2 段' } } });
  render(<MemoryRouter><HvHLobbyPage /></MemoryRouter>);
  expect(await screen.findByText('段位读取失败')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /快速匹配/ })).toBeDisabled();
  expect(screen.queryByText('未定级')).not.toBeInTheDocument();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: '重试段位' }));
  expect(await screen.findByText('已定级')).toBeInTheDocument();
});
it('removes old lobby rows when a refresh fails', async () => {
  render(<MemoryRouter><HvHLobbyPage /></MemoryRouter>);
  await screen.findByTestId('lobby-player-2');
  expect(screen.getByTestId('lobby-game')).toBeInTheDocument();
  vi.mocked(fetch).mockResolvedValue({ ok: false } as Response);
  act(() => push({ type: 'lobby_update' }));
  await screen.findByText(/大厅暂时无法连接/);
  await waitFor(() => expect(screen.queryByTestId('lobby-player-2')).not.toBeInTheDocument());
  expect(screen.queryByTestId('lobby-game')).not.toBeInTheDocument();
  expect(screen.queryByText('当前没有进行中的对局。')).not.toBeInTheDocument();
});
