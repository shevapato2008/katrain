import { afterEach, expect, it, vi } from 'vitest';
import { BaipuHistoryAPI, BaipuHistoryError } from './baipuHistoryApi';
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });
it('captures bearer and identity preconditions and explicitly allows same-origin cookies', async () => {
  const fetcher = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ items: [], authority: 'cloud' }) });
  vi.stubGlobal('fetch', fetcher);
  await BaipuHistoryAPI.list({ identityKey: 'a', token: 'secret' });
  expect(fetcher).toHaveBeenCalledWith('/api/v1/baipu/history?limit=30', expect.objectContaining({ credentials: 'same-origin', headers: expect.objectContaining({ Authorization: 'Bearer secret', 'X-Katrain-Expected-Identity': 'a' }) }));
  await BaipuHistoryAPI.list({ identityKey: 'b', token: null });
  expect(fetcher.mock.calls[1][1].headers).not.toHaveProperty('Authorization');
});
it('refuses unresolved identities before making a request', async () => {
  const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
  await expect(BaipuHistoryAPI.list({ identityKey: '', token: null })).rejects.toThrow();
  expect(fetcher).not.toHaveBeenCalled();
});
it('preserves structured stale-revision errors without retry', async () => {
  const fetcher = vi.fn().mockResolvedValue({ ok: false, status: 409, json: () => Promise.resolve({ detail: { code: 'stale_local_revision', current: { k: 2 } } }) });
  vi.stubGlobal('fetch', fetcher);
  await expect(BaipuHistoryAPI.save('a'.repeat(64), { k: 0, expected_local_revision: 1, mutation_id: 'one' }, { identityKey: 'a', token: null })).rejects.toMatchObject({ code: 'stale_local_revision', status: 409 });
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(BaipuHistoryError).toBeDefined();
});
it('bounds a stalled response body as well as fetch', async () => {
  vi.useFakeTimers(); vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: () => new Promise(() => {}) }));
  const pending = expect(BaipuHistoryAPI.list({ identityKey: 'a', token: null })).rejects.toThrow('timed out');
  await vi.advanceTimersByTimeAsync(10001); await pending;
});
