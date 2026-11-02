import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import type { BaipuHistoryDetail } from '../../api/baipuHistoryApi';
const { auth, load, getHistory, openHistory, saveHistory, resolveHistory } = vi.hoisted(() => ({
  auth: { user: { uuid: 'u1' } as { uuid: string } | null, identityKey: 'u1' as string | null, isGuest: false, isLoading: false, token: 'token' },
  load: vi.fn(), getHistory: vi.fn(), openHistory: vi.fn(), saveHistory: vi.fn(), resolveHistory: vi.fn(),
}));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => auth }));
vi.mock('../../api/baipuApi', async original => {
  const actual = await original<typeof import('../../api/baipuApi')>();
  return { ...actual, BaipuAPI: { ...actual.BaipuAPI, load } };
});
vi.mock('../../api/baipuHistoryApi', async original => {
  const actual = await original<typeof import('../../api/baipuHistoryApi')>();
  return { ...actual, BaipuHistoryAPI: { get: getHistory, open: openHistory, save: saveHistory, resolve: resolveHistory } };
});
vi.mock('../../api/ledApi', () => ({ LedAPI: {
  point: vi.fn(async () => ({ connected: true })), points: vi.fn(async () => ({ connected: true })), clear: vi.fn(async () => ({ connected: true })),
} }));
vi.mock('../hooks/useVisionSync', () => ({ useVisionSync: () => ({ connected: false, syncEvents: [] }) }));
import BaipuSessionPage from '../pages/BaipuSessionPage';
const id = 'a'.repeat(64);
const sgf = '(;SZ[19];B[pd];W[dp])';
const record = (k = 1): BaipuHistoryDetail => ({ id, source_id: 'g1', name: 'Saved game', sgf_content: sgf, sgf_sha256: 'b'.repeat(64), replay_version: 2,
  k, total: 2, completed: k === 2, local_revision: 1, cloud_revision: 1, authority: 'cloud', sync_state: 'synced', updated_at: '', completed_at: null });
const loaded = { board_size: 19, meta: {}, steps: [
  { kind: 'move', move_index: 0, property: 'B', row: 3, col: 15, color: 'B', pre_removed: [], requires_placement: true, removed: [], board_hash: 'h0' },
  { kind: 'move', move_index: 1, property: 'W', row: 15, col: 3, color: 'W', pre_removed: [], requires_placement: true, removed: [], board_hash: 'h1' },
] };
function Page() { const location = useLocation(); return <><span data-testid="route">{location.search}</span><BaipuSessionPage collect={false} /></>; }
const at = (history = true) => <MemoryRouter initialEntries={[history ? `/kiosk/baipu/session/g1?history=${id}` : { pathname: '/kiosk/baipu/session/g1', state: { sgf, name: 'New game', baipuIdentity: 'u1' } }]}><Routes><Route path="/kiosk/baipu/session/:source" element={<Page />} /></Routes></MemoryRouter>;
beforeEach(() => {
  vi.clearAllMocks(); localStorage.clear(); auth.user = { uuid: 'u1' }; auth.identityKey = 'u1'; auth.isLoading = false;
  load.mockResolvedValue(loaded); getHistory.mockResolvedValue(record()); openHistory.mockResolvedValue(record());
  saveHistory.mockImplementation(async (_id, cursor) => ({ ...record(cursor.k), local_revision: 2 }));
});
describe('physical session with the real account-history hook', () => {
  it('reloads a durable history URL, resumes the saved board, then saves completion', async () => {
    render(at()); await screen.findByTestId('baipu-resume');
    expect(getHistory).toHaveBeenCalledWith(id, expect.objectContaining({ identityKey: 'u1' }));
    expect(load).toHaveBeenCalledWith({ sgf });
    fireEvent.click(screen.getByTestId('baipu-resume-continue'));
    fireEvent.click(await screen.findByRole('button', { name: '盘面已摆对' }));
    fireEvent.click(screen.getByRole('button', { name: '确认落子' }));
    await waitFor(() => expect(saveHistory).toHaveBeenCalledWith(id, expect.objectContaining({ k: 2 }), expect.objectContaining({ identityKey: 'u1' })));
    expect(screen.getByTestId('route')).toHaveTextContent(`?history=${id}`);
    expect(screen.getByTestId('baipu-pcard')).toHaveAttribute('data-mood', 'done');
  });
  it('adds a durable URL after successful load and restart persists zero', async () => {
    render(at(false)); await screen.findByTestId('baipu-resume');
    expect(openHistory).toHaveBeenCalledTimes(1); expect(load).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('route')).toHaveTextContent(`?history=${id}`);
    fireEvent.click(screen.getByTestId('baipu-resume-restart'));
    await waitFor(() => expect(saveHistory).toHaveBeenCalledWith(id, expect.objectContaining({ k: 0 }), expect.anything()));
  });
  it('logout invalidates a load before it can open or write history', async () => {
    let finish!: (value: typeof loaded) => void;
    load.mockImplementation(() => new Promise(r => { finish = r; }));
    const view = render(at()); await waitFor(() => expect(load).toHaveBeenCalledTimes(1));
    auth.user = null; auth.identityKey = null; view.rerender(at());
    await act(async () => { finish(loaded); });
    expect(openHistory).not.toHaveBeenCalled(); expect(saveHistory).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: '确认落子' })).toBeNull();
  });
});

it('keeps the real history save alive on exit and can retry a failed final cursor', async () => {
  let fail!: (error: Error) => void;
  saveHistory.mockImplementationOnce(() => new Promise((_resolve, reject) => { fail = reject; }));
  render(at()); await screen.findByTestId('baipu-resume');
  fireEvent.click(screen.getByTestId('baipu-resume-continue'));
  fireEvent.click(await screen.findByRole('button', { name: '盘面已摆对' }));
  fireEvent.click(screen.getByRole('button', { name: '确认落子' }));
  await waitFor(() => expect(saveHistory).toHaveBeenCalledTimes(1));
  const signal = saveHistory.mock.calls[0][2].signal as AbortSignal;
  fireEvent.click(screen.getByRole('button', { name: /返回棋谱/ }));
  expect(screen.getByTestId('baipu-exit-confirm-action')).toBeDisabled();
  expect(signal?.aborted ?? false).toBe(false);
  await act(async () => { fail(new Error('offline')); });
  await waitFor(() => expect(screen.getByTestId('baipu-exit-confirm-action')).toBeEnabled());
  expect(screen.getByTestId('baipu-exit-confirm-action')).toHaveTextContent('仍然退出');
  fireEvent.click(screen.getByRole('button', { name: '取消' }));
  fireEvent.click(screen.getByRole('button', { name: '重试' }));
  await waitFor(() => expect(saveHistory).toHaveBeenCalledTimes(2));
  expect(saveHistory.mock.calls[1][1]).toMatchObject({ k: 2, mutation_id: saveHistory.mock.calls[0][1].mutation_id });
});
