import { afterEach, expect, it, vi } from 'vitest';
import { API, ApiError } from './api';

afterEach(() => vi.unstubAllGlobals());

it('reads an opaque room snapshot with auth and preserves a failed HTTP status', async () => {
  const controller = new AbortController();
  const fetchMock = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ room_id: 'opaque/id' }), { status: 200 }))
    .mockResolvedValueOnce(new Response('', { status: 502 }));
  vi.stubGlobal('fetch', fetchMock);
  await API.platformRoomSnapshot('opaque/id', 'token', controller.signal);
  expect(fetchMock).toHaveBeenCalledWith('/api/v1/platforms/golaxy/rooms/opaque%2Fid/snapshot', {
    headers: { Authorization: 'Bearer token' },
    signal: controller.signal,
  });
  await expect(API.platformRoomSnapshot('opaque/id', 'token')).rejects.toBeInstanceOf(ApiError);
});
