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
});
