import { afterEach, describe, expect, it, vi } from 'vitest';
import { API } from './api';

describe('API.quickAnalyze authentication', () => {
  afterEach(() => vi.restoreAllMocks());

  it('sends Bearer when an access token is available', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 200 }));
    await API.quickAnalyze({ moves: [] }, 'access-token');
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/analysis/quick-analyze', expect.objectContaining({
      headers: expect.objectContaining({ Authorization: 'Bearer access-token' }),
    }));
  });

  it('omits Authorization for the cookie-only path', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 200 }));
    await API.quickAnalyze({ moves: [] }, undefined);
    const options = fetchMock.mock.calls[0][1] as RequestInit;
    expect(options.headers).not.toHaveProperty('Authorization');
  });
});
