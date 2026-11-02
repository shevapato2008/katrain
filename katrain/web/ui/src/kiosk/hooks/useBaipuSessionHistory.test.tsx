import { StrictMode } from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { useBaipuSessionHistory } from './useBaipuSessionHistory';
import { BaipuHistoryError } from '../../api/baipuHistoryApi';
import { __resetKioskActivityStorageForTests } from '../storage/kioskActivityStorage';
const f = vi.hoisted(() => ({ auth: { identityKey: 'owner-a' as string | null, isGuest: false, isLoading: false, token: 'token-a', status: 'authenticated' }, get: vi.fn(), open: vi.fn(), save: vi.fn(), resolve: vi.fn() }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => f.auth }));
vi.mock('../../api/baipuHistoryApi', async original => ({ ...await original<object>(), BaipuHistoryAPI: { get: f.get, open: f.open, save: f.save, resolve: f.resolve } }));
const id = 'a'.repeat(64);
const detail = (over = {}) => ({ id, source_id: 'kifu_1', name: 'Original', sgf_content: '(;SZ[19];B[dd];W[pp])', k: 1, total: 2, replay_version: 2, local_revision: 4, completed: false, sync_state: 'synced', authority: 'cloud', ...over });
const navigation = { sgf: '(;SZ[19];B[dd];W[pp])', name: 'Original', baipuIdentity: 'owner-a' };
const mount = (nav: typeof navigation | null = navigation, history = '') => renderHook(() => ({ ...useBaipuSessionHistory({ source: 'kifu_1', navigation: nav }), location: useLocation() }), { wrapper: ({ children }) => <MemoryRouter initialEntries={[`/kiosk/baipu/session/kifu_1${history}`]}>{children}</MemoryRouter> });
afterEach(() => { vi.unstubAllGlobals(); });
beforeEach(() => { vi.clearAllMocks(); __resetKioskActivityStorageForTests(); Object.assign(f.auth, { identityKey: 'owner-a', isGuest: false, isLoading: false, token: 'token-a', status: 'authenticated' }); f.get.mockResolvedValue(detail()); f.open.mockResolvedValue(detail()); f.save.mockImplementation(async (_id, data) => detail({ k: data.k, local_revision: data.expected_local_revision + 1, completed: data.k === 2 })); });
it('reloads exact SGF from a durable history URL and waits to open until explicitly called', async () => {
  const { result } = mount(null, `?history=${id}`);
  await waitFor(() => expect(result.current.sgf).toBe(detail().sgf_content));
  expect(f.get).toHaveBeenCalledWith(id, expect.objectContaining({ identityKey: 'owner-a', token: 'token-a' }));
  expect(f.open).not.toHaveBeenCalled();
  let progress: unknown; await act(async () => { progress = await result.current.open(2); });
  expect(progress).toEqual({ k: 1, total: 2 }); expect(f.save).not.toHaveBeenCalled();
  expect(f.open).toHaveBeenCalledWith(expect.objectContaining({ source_id: 'kifu_1', sgf_content: detail().sgf_content }), expect.anything());
});
it('opens existing progress without resetting and makes the URL durable without changing its source', async () => {
  const { result } = mount(); await waitFor(() => expect(result.current.loading).toBe(false));
  const open = result.current.open;
  await act(async () => { expect(await open(2)).toEqual({ k: 1, total: 2 }); });
  expect(f.save).not.toHaveBeenCalled(); expect(result.current.location.pathname).toBe('/kiosk/baipu/session/kifu_1');
  expect(result.current.location.search).toBe(`?history=${id}`); expect(result.current.open).toBe(open);
});
it('keeps the in-flight completion immutable and coalesces only unsent undo/restart updates', async () => {
  const { result } = mount(); await act(async () => { await result.current.open(2); });
  let finish!: (value: unknown) => void; f.save.mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
  let a!: Promise<void>, b!: Promise<void>, c!: Promise<void>;
  act(() => { a = result.current.save(2); });
  await waitFor(() => expect(f.save).toHaveBeenCalledTimes(1));
  act(() => { b = result.current.save(1); c = result.current.save(0); });
  await act(async () => { finish(detail({ k: 2, local_revision: 5, completed: true })); await Promise.all([a, b, c]); });
  expect(f.save.mock.calls.map(call => call[1])).toEqual([expect.objectContaining({ k: 2, expected_local_revision: 4 }), expect.objectContaining({ k: 0, expected_local_revision: 5 })]);
  expect(result.current.record?.k).toBe(0);
});
it('rejects prior-owner and legacy navigation rather than creating history', async () => {
  const { result } = mount({ ...navigation, baipuIdentity: 'owner-b' });
  await waitFor(() => expect(result.current.error).toBeTruthy());
  expect(result.current.sgf).toBeNull(); await act(async () => { await result.current.open(2); }); expect(f.open).not.toHaveBeenCalled();
});
it('invalidates queued saves immediately on account switch and never rebinds credentials', async () => {
  const view = mount(); await act(async () => { await view.result.current.open(2); });
  let finish!: (value: unknown) => void; f.save.mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
  let first!: Promise<void>, next!: Promise<void>;
  act(() => { first = view.result.current.save(2); next = view.result.current.save(0); });
  await waitFor(() => expect(f.save).toHaveBeenCalledTimes(1));
  f.get.mockReturnValue(new Promise(() => {}));
  f.auth.identityKey = 'owner-b'; f.auth.token = 'token-b'; view.rerender();
  await act(async () => { finish(detail({ k: 2, local_revision: 5 })); await Promise.all([first, next]); });
  expect(f.save).toHaveBeenCalledTimes(1); expect(view.result.current.record).toBeNull(); expect(view.result.current.sgf).toBeNull();
});
it('keeps guests in memory without API or disk writes', async () => {
  Object.assign(f.auth, { identityKey: null, isGuest: true, token: null });
  const disk = vi.spyOn(Storage.prototype, 'setItem');
  const { result } = mount({ ...navigation, baipuIdentity: 'guest' });
  await act(async () => { expect(await result.current.open(2)).toEqual({ k: 0, total: 2 }); await result.current.save(2); });
  expect(f.open).not.toHaveBeenCalled(); expect(f.save).not.toHaveBeenCalled(); expect(disk).not.toHaveBeenCalled(); disk.mockRestore();
});
it('exposes save conflicts and never repeats a stale resolution choice', async () => {
  const { result } = mount(); await act(async () => { await result.current.open(2); });
  f.save.mockRejectedValueOnce(new BaipuHistoryError(409, { code: 'stale_local_revision', current: detail({ local_revision: 5, sync_state: 'conflict' }) }));
  await act(async () => { await result.current.save(0); }); expect(result.current.saveError).toBeTruthy();
  f.resolve.mockRejectedValueOnce(new BaipuHistoryError(409, { code: 'stale_local_revision', current: detail({ k: 2, local_revision: 6 }) }));
  await act(async () => { expect(await result.current.resolve('use_cloud')).toBeNull(); });
  expect(f.resolve).toHaveBeenCalledTimes(1);
});
it('rejects mismatched replay totals before saving a cursor', async () => {
  const { result } = mount(); await act(async () => { expect(await result.current.open(9)).toBeNull(); });
  expect(result.current.error).toBeTruthy(); expect(f.save).not.toHaveBeenCalled();
});

it('opens again with the latest saved cursor and permits an explicit retry after a failed save', async () => {
  const { result } = mount(); await act(async () => { await result.current.open(2); });
  f.save.mockRejectedValueOnce(new Error('offline'));
  await act(async () => { await result.current.save(2); });
  await act(async () => { await result.current.save(0); });
  expect(f.save).toHaveBeenCalledTimes(2);
  await act(async () => { expect(await result.current.open(2)).toEqual({ k: 0, total: 2 }); });
});

it('survives StrictMode lifecycle replay and keeps its load generation usable', async () => {
  const { result } = renderHook(() => useBaipuSessionHistory({ source: 'kifu_1', navigation }), { wrapper: ({ children }) => <StrictMode><MemoryRouter>{children}</MemoryRouter></StrictMode> });
  await waitFor(() => expect(result.current.sgf).toBe(navigation.sgf));
  await act(async () => { expect(await result.current.open(2)).toEqual({ k: 1, total: 2 }); });
});
it('reports an unavailable resolved identity without an endless loading state', async () => {
  Object.assign(f.auth, { identityKey: null, status: 'unavailable' });
  const { result } = mount();
  expect(result.current.loading).toBe(false); expect(result.current.error).toBeTruthy();
  expect(f.open).not.toHaveBeenCalled();
});
it('retains completion and permits explicit lower cursors without deleting history', async () => {
  const { result } = mount(); await act(async () => { await result.current.open(2); });
  await act(async () => { await result.current.save(2); }); expect(result.current.record?.completed).toBe(true);
  await act(async () => { await result.current.save(1); }); expect(result.current.record?.k).toBe(1);
  await act(async () => { await result.current.save(0); }); expect(result.current.record?.k).toBe(0);
  expect(result.current.historyId).toBe(id);
});
it('does not move a physical cursor from a resolution response superseded by a new completed step', async () => {
  const { result } = mount(); await act(async () => { await result.current.open(2); });
  let finish!: (value: unknown) => void;
  f.resolve.mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
  let resolution!: Promise<unknown>, save!: Promise<void>;
  act(() => { resolution = result.current.resolve('use_cloud'); });
  await waitFor(() => expect(f.resolve).toHaveBeenCalledTimes(1));
  act(() => { save = result.current.save(2); });
  await act(async () => { finish(detail({ k: 0, local_revision: 5 })); expect(await resolution).toBeNull(); await save; });
  expect(result.current.record?.k).toBe(2);
  expect(f.save).toHaveBeenLastCalledWith(id, expect.objectContaining({ k: 2, expected_local_revision: 5 }), expect.anything());
});
it('reuses the mutation identity when explicitly retrying an uncertain completed save', async () => {
  const { result } = mount(); await act(async () => { await result.current.open(2); });
  f.save.mockRejectedValueOnce(new Error('response lost'));
  await act(async () => { await result.current.save(2); });
  await act(async () => { await result.current.save(2); });
  expect(f.save.mock.calls[1][1]).toEqual(f.save.mock.calls[0][1]);
});

it('lets an already-dispatched owner-bound keepalive save finish after unmount while cancelling unsent work', async () => {
  const actual = await vi.importActual<typeof import('../../api/baipuHistoryApi')>('../../api/baipuHistoryApi');
  f.save.mockImplementation(actual.BaipuHistoryAPI.save);
  let finish!: () => void;
  let sent!: RequestInit;
  const fetcher = vi.fn((_url: string, init: RequestInit) => {
    sent = init;
    return new Promise((resolve, reject) => {
      finish = () => resolve({ ok: true, json: async () => detail({ k: 2, local_revision: 5, completed: true }) });
      init.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
    });
  });
  vi.stubGlobal('fetch', fetcher);
  const view = mount();
  await act(async () => { await view.result.current.open(2); });
  let dispatched!: Promise<void>, queued!: Promise<void>;
  act(() => { dispatched = view.result.current.save(2); });
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
  act(() => { queued = view.result.current.save(0); });
  view.unmount();
  const abortedByUnmount = sent.signal?.aborted;
  Object.assign(f.auth, { identityKey: 'owner-b', token: 'token-b' });
  await act(async () => { finish(); await Promise.all([dispatched, queued]); });
  expect(abortedByUnmount).toBe(false);
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(sent).toMatchObject({ keepalive: true, credentials: 'same-origin', headers: {
    Authorization: 'Bearer token-a', 'X-Katrain-Expected-Identity': 'owner-a',
  } });
  expect(JSON.parse(sent.body as string)).toMatchObject({ k: 2, expected_local_revision: 4 });
});
