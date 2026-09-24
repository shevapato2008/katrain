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

  it('confirms reuse of the existing geometry for this session', async () => {
    const ready = {
      phase: 'ready',
      session_calibrated: true,
      last_valid: true,
      capabilities: { camera_ready: true, led_ready: true, geometry_ready: true },
    };
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(ready), { status: 200 }),
    );

    await expect(GeometryAPI.confirmExisting()).resolves.toEqual(ready);
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/geometry/confirm-existing', { method: 'POST' });
  });

  it('relocate 失败时把后端的 detail 带进错误信息(屏上靠它分辨「找不到外框」)', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'no_board_detected' }), { status: 400 }),
    );
    await expect(GeometryAPI.relocate()).rejects.toThrow(/400: no_board_detected/);
  });

  it('relocate 成功时回状态', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ phase: 'ready' }), { status: 200 }),
    );
    await expect(GeometryAPI.relocate()).resolves.toMatchObject({ phase: 'ready' });
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/geometry/relocate', { method: 'POST' });
  });
});
