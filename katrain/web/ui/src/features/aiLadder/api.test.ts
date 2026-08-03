import { afterEach, describe, expect, it, vi } from 'vitest';
import { getAiLadderStatus, startAiLadderGame, AiLadderApiError } from './api';

afterEach(() => vi.unstubAllGlobals());

describe('ai ladder API', () => {
  it('loads status with bearer authentication when a token exists', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ view_state: 'ready' }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await getAiLadderStatus('galaxy-token');

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/ai-ladder/status', expect.objectContaining({
      headers: { Authorization: 'Bearer galaxy-token' },
    }));
  });

  it('loads status cookie-only when no JavaScript token exists', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ view_state: 'ready' }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await getAiLadderStatus();

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/ai-ladder/status', expect.objectContaining({
      credentials: 'same-origin',
      headers: {},
    }));
  });

  it('preserves backend detail for an unavailable opponent', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'AI rung is provisional and unavailable' }),
      { status: 409, headers: { 'Content-Type': 'application/json' } },
    )));

    await expect(startAiLadderGame({ board_size: 19, rules: 'chinese', komi: 7.5, handicap: 0,
      color: 'black', time_enabled: false, main_time: 0, byo_length: 30, byo_periods: 3 }))
      .rejects.toEqual(expect.objectContaining<Partial<AiLadderApiError>>({
        status: 409,
        message: 'AI rung is provisional and unavailable',
      }));
  });
});
