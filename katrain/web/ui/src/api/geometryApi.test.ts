import { describe, expect, it, vi, afterEach } from 'vitest';
import { GeometryAPI } from './geometryApi';

describe('GeometryAPI', () => {
  afterEach(() => vi.restoreAllMocks());

  it('starts automatic LED calibration with empty-board confirmation', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ phase: 'waiting_empty' }), { status: 202 }),
    );

    await GeometryAPI.calibrate('auto');

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/geometry/calibrate', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ trigger: 'auto', empty_confirmed: true }),
    }));
  });

  it('loads the current camera-space geometry layout', async () => {
    const layout = {
      revision: 3,
      phase: 'ready',
      stale: false,
      frame: { width: 1920, height: 1080 },
      out_size: 950,
      corners: [],
      points: [],
    };
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(layout), { status: 200 }),
    );

    await expect(GeometryAPI.layout()).resolves.toEqual(layout);
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/geometry/layout');
  });
});
