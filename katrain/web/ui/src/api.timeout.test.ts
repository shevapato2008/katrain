import { afterEach, describe, expect, it, vi } from 'vitest';
import { API } from './api';

describe('API.timeout request binding', () => {
  afterEach(() => vi.restoreAllMocks());

  it('posts the expected game, node and color on the cookie-only path', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 200 }));
    const binding = { expected_game_id: 'g', expected_node_id: 5, color: 'B' as const };
    await API.timeout('s', undefined, binding);
    expect(fetchMock).toHaveBeenCalledWith('/api/timeout', expect.objectContaining({
      method: 'POST', body: JSON.stringify({ session_id: 's', ...binding }),
    }));
  });

  it('keeps the legacy request body when no binding is provided', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 200 }));
    await API.timeout('s');
    expect(fetchMock).toHaveBeenCalledWith('/api/timeout', expect.objectContaining({
      method: 'POST', body: JSON.stringify({ session_id: 's' }),
    }));
  });
});
