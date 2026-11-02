import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { useBaipuHistory } from './useBaipuHistory';
import { cacheSgf, saveProgress } from '../../api/baipuApi';
import { __resetKioskActivityStorageForTests, kioskActivityStorage } from '../storage/kioskActivityStorage';
const f = vi.hoisted(() => ({ auth: { isGuest: false, isLoading: false, identityKey: 'owner-a' as string | null, token: null, status: 'authenticated' }, list: vi.fn() }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => f.auth }));
vi.mock('../../api/baipuHistoryApi', () => ({ BaipuHistoryAPI: { list: f.list } }));
beforeEach(() => { vi.clearAllMocks(); __resetKioskActivityStorageForTests(); Object.assign(f.auth, { isGuest: false, isLoading: false, identityKey: 'owner-a', status: 'authenticated' }); f.list.mockResolvedValue({ items: [], authority: 'cloud' }); });
it('ignores real-account browser cursor caches instead of migrating unknown replay versions', async () => {
  const store = kioskActivityStorage('owner-a', false);
  cacheSgf('old', 'Old cache', '(;SZ[19];B[dd])', store);
  saveProgress('old', { k: 10, frames: 0, updatedAt: 1 }, store);
  const { result } = renderHook(() => useBaipuHistory());
  await waitFor(() => expect(result.current.loading).toBe(false));
  expect(result.current.items).toEqual([]); expect(f.list).toHaveBeenCalled();
});
it('reads guest memory while leaving account APIs and disk storage untouched', async () => {
  Object.assign(f.auth, { isGuest: true, identityKey: null, status: 'guest' });
  const store = kioskActivityStorage(null, true);
  cacheSgf('guest_game', 'Guest game', '(;SZ[19];B[dd])', store);
  const read = vi.spyOn(Storage.prototype, 'getItem'); const write = vi.spyOn(Storage.prototype, 'setItem');
  const { result } = renderHook(() => useBaipuHistory());
  expect(result.current.items[0]?.name).toBe('Guest game');
  await act(async () => { result.current.refresh(); });
  expect(f.list).not.toHaveBeenCalled(); expect(read).not.toHaveBeenCalled(); expect(write).not.toHaveBeenCalled();
  read.mockRestore(); write.mockRestore();
});
