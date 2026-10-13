import { afterEach, describe, expect, it, vi } from 'vitest';
import { API, ApiError } from './api';

afterEach(() => vi.unstubAllGlobals());

describe('Golaxy lobby API errors', () => {
  it.each([
    ['rooms', () => API.platformRooms('golaxy', 'token'), 401],
    ['users', () => API.platformUsers('golaxy', 'token'), 502],
  ] as const)('%s preserves HTTP status in ApiError', async (_list, request, status) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"detail":"upstream failed"}', { status })));
    await expect(request()).rejects.toMatchObject({ status, name: 'ApiError' });
    await expect(request()).rejects.toBeInstanceOf(ApiError);
  });
});
