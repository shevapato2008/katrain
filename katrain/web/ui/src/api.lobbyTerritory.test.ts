import { afterEach, expect, it, vi } from 'vitest';
import { API, ApiError } from './api';
afterEach(() => vi.unstubAllGlobals());
it('posts private lobby territory using the shared authenticated transport', async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ stale: false }) });
  vi.stubGlobal('fetch', fetch);
  await API.lobbyTerritory('lobby-session', 'participant-token');
  expect(fetch).toHaveBeenCalledWith('/api/pvp/territory', expect.objectContaining({ method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: 'Bearer participant-token' },
    body: JSON.stringify({ session_id: 'lobby-session' }) }));
});
it('preserves a denied participant response as a failure', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 403, text: async () => '{"detail":"Forbidden"}' }));
  await expect(API.lobbyTerritory('s')).rejects.toBeInstanceOf(ApiError);
});
