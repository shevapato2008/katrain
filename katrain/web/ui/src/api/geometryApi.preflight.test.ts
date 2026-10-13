import { afterEach, describe, expect, it, vi } from 'vitest';
import { GeometryAPI } from './geometryApi';

const status = { phase: 'ready', session_calibrated: true, last_valid: true,
  capabilities: { camera_ready: true, geometry_ready: true, recognition_ready: false, model_ready: false } };
afterEach(() => vi.unstubAllGlobals());
describe('geometry preflight API', () => {
  it('posts a bounded check and preserves backend readiness instead of deriving it from phase', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ready: false, reason: 'model_not_ready', status })));
    vi.stubGlobal('fetch', fetch);
    expect(await GeometryAPI.preflight()).toEqual({ ready: false, reason: 'model_not_ready', status });
    expect(fetch).toHaveBeenCalledWith('/api/v1/geometry/preflight', expect.objectContaining({ method: 'POST', signal: expect.any(AbortSignal) }));
  });
  it('rejects a failed transport response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 503 })));
    await expect(GeometryAPI.preflight()).rejects.toThrow('503');
  });
});
