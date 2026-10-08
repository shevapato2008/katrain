import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { AdminApiError, createAdminApi } from '../api/client';
import LobbyPage from './LobbyPage';
import type { LobbyOverview, ParticipantPage } from './types';

const ranks = Array.from({ length: 29 }, (_, i) => ({ rung: i + 1, rank_label: `${i + 1}级`, idle_target: 2, idle_now: 2, playing_now: 0 }));
const overview: LobbyOverview = { config: { version: 1, enabled: true, bot_game_limit: 3, idle_targets: Object.fromEntries(ranks.map(({ rung }) => [rung, 2])) }, config_revision: 4, runtime: { reported_at: new Date().toISOString(), applied_config_revision: 4, stale: false, active_bot_games: 1, engine_errors: 0, rungs: ranks } };
const participants: ParticipantPage = { items: [
  { id: 8, username: '青石', kind: 'human', ladder_rung: 3, rank_label: '3级', presence: 'idle' },
  { id: -7, username: '棋友甲', kind: 'bot', ladder_rung: 3, rank_label: '3级', presence: 'playing' },
], total: 2, page: 1, page_size: 30 };
const makeApi = () => {
  const api = createAdminApi();
  api.pvpLobby = vi.fn(async () => overview);
  api.pvpParticipants = vi.fn(async () => participants);
  api.savePvpLobby = vi.fn(async () => ({ ...overview, config_revision: 5 }));
  return api;
};

describe('admin PvP lobby', () => {
  it('keeps draft targets separate from current counts and saves with revision', async () => {
    const api = makeApi(); const user = userEvent.setup();
    render(<LobbyPage api={api} onUnauthorized={vi.fn()} />);
    const row = (await screen.findByRole('button', { name: '增加 1级 空闲目标' })).closest('[role="row"]') as HTMLElement;
    expect(within(row).getByText('2 空闲 / 0 对局中')).toBeInTheDocument();
    await user.click(within(row).getByRole('button', { name: '增加 1级 空闲目标' }));
    expect(within(row).getByText('3')).toBeInTheDocument();
    expect(within(row).getByText('2 空闲 / 0 对局中')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '保存设置' }));
    await waitFor(() => expect(api.savePvpLobby).toHaveBeenCalledWith({ expected_revision: 4, config: expect.objectContaining({ idle_targets: expect.objectContaining({ '1': 3 }) }) }));
    expect(await screen.findByText('设置已保存，等待服务端应用。')).toBeInTheDocument();
  });

  it('shows stale runtime and prevents writes until refreshed', async () => {
    const api = makeApi(); const user = userEvent.setup();
    api.pvpLobby = vi.fn().mockResolvedValueOnce({ ...overview, runtime: { ...overview.runtime, stale: true } }).mockResolvedValueOnce(overview);
    render(<LobbyPage api={api} onUnauthorized={vi.fn()} />);
    expect(await screen.findByText('运行状态已过期')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '增加互战上限' }));
    expect(screen.getByRole('button', { name: '保存设置' })).toBeDisabled();
    expect(screen.getAllByText(/当前数量暂不可用/).length).toBeGreaterThan(0);
    expect(screen.getByText('运行状态已过期，无法判断当前在线参与者。')).toBeInTheDocument();
    expect(screen.queryByText('青石')).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText('在线状态'), 'all');
    expect(await screen.findByText('青石')).toBeInTheDocument();
    expect(screen.getAllByText('状态未知').length).toBeGreaterThan(0);
    await user.click(screen.getByRole('button', { name: '刷新状态' }));
    await waitFor(() => expect(screen.getByRole('button', { name: '保存设置' })).toBeEnabled());
  });

  it('preserves a conflicting draft, reloads the server config, and paginates filtered roster', async () => {
    const api = makeApi(); const user = userEvent.setup();
    api.savePvpLobby = vi.fn().mockRejectedValueOnce(new AdminApiError(409, '配置冲突')).mockResolvedValueOnce({ ...overview, config_revision: 6 });
    api.pvpLobby = vi.fn().mockResolvedValueOnce(overview).mockResolvedValueOnce({ ...overview, config_revision: 5, config: { ...overview.config, bot_game_limit: 5 } });
    api.pvpParticipants = vi.fn().mockResolvedValue({ ...participants, total: 31 });
    render(<LobbyPage api={api} onUnauthorized={vi.fn()} />);
    await screen.findByText('棋友甲');
    await user.click(screen.getByRole('button', { name: '增加互战上限' }));
    await user.click(screen.getByRole('button', { name: '保存设置' }));
    expect(await screen.findByText(/服务器设置已变化/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '读取服务器设置' }));
    await waitFor(() => expect(api.pvpLobby).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/草稿已保留/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '保存设置' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: '保存设置' }));
    await waitFor(() => expect(api.savePvpLobby).toHaveBeenLastCalledWith({ expected_revision: 5, config: expect.objectContaining({ bot_game_limit: 4 }) }));
    await user.selectOptions(screen.getByLabelText('身份类型'), 'bot');
    await waitFor(() => expect(api.pvpParticipants).toHaveBeenCalledWith(expect.objectContaining({ kind: 'bot', page: 1 }), expect.anything()));
    expect(within(screen.getByRole('region', { name: '参与者名单' })).getAllByText('机器人').length).toBeGreaterThan(0);
    await user.click(screen.getByRole('button', { name: '下一页' }));
    await waitFor(() => expect(api.pvpParticipants).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }), expect.anything()));
  });

  it('offers retry after load failure', async () => {
    const api = makeApi(); const user = userEvent.setup();
    api.pvpLobby = vi.fn().mockRejectedValueOnce(new Error('暂时不可用')).mockResolvedValueOnce(overview);
    render(<LobbyPage api={api} onUnauthorized={vi.fn()} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('暂时不可用');
    await user.click(screen.getByRole('button', { name: '重试' }));
    expect(await screen.findByText('逐段位投放')).toBeInTheDocument();
  });

  it('clears previous roster rows while a filter request is loading', async () => {
    const api = makeApi(); const user = userEvent.setup();
    let resolveBots!: (page: ParticipantPage) => void;
    api.pvpParticipants = vi.fn((query) => query.kind === 'bot'
      ? new Promise<ParticipantPage>((resolve) => { resolveBots = resolve; })
      : Promise.resolve(participants));
    render(<LobbyPage api={api} onUnauthorized={vi.fn()} />);
    expect(await screen.findByText('青石')).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText('身份类型'), 'bot');
    expect(screen.queryByText('青石')).not.toBeInTheDocument();
    expect(screen.getByText('正在读取参与者…')).toBeInTheDocument();
    resolveBots({ ...participants, items: [participants.items[1]], total: 31 });
    expect(await screen.findByText('棋友甲')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '下一页' }));
    expect(screen.queryByText('棋友甲')).not.toBeInTheDocument();
    expect(screen.getByText('正在读取参与者…')).toBeInTheDocument();
  });

  it('describes saved disabled config as off rather than healthy', async () => {
    const api = makeApi();
    api.pvpLobby = vi.fn(async () => ({ ...overview, config: { ...overview.config, enabled: false } }));
    render(<LobbyPage api={api} onUnauthorized={vi.fn()} />);
    expect(await screen.findByText('机器人投放已关闭')).toBeInTheDocument();
    expect(screen.queryByText('服务端投放正常')).not.toBeInTheDocument();
  });
});
