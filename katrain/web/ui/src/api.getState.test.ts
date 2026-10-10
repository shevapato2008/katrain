import { afterEach, describe, expect, it, vi } from 'vitest';
import { API, ApiError } from './api';

describe('API.getState', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('retains HTTP 503 so a box room can distinguish central outage', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }));
    await expect(API.getState('local-room')).rejects.toMatchObject({
      name: ApiError.name, status: 503, message: 'Failed to get state',
    });
  });
});
