import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { createAdminApi } from './client';

describe('admin API contract', () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    fetchMock.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('sends the admin bearer only to admin writes, never public tutorial reads', async () => {
    fetchMock.mockImplementation(async () => new Response(JSON.stringify([]), { status: 200 }));
    const api = createAdminApi(fetchMock, () => 'admin-session');
    await api.categories();
    await api.saveNarration(12, { narration: '讲解', expected_updated_at: '2026-09-24T08:00:00Z' });
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/tutorials/categories');
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).has('Authorization')).toBe(false);
    expect(fetchMock.mock.calls[1][0]).toBe('/api/admin/tutorials/figures/12/narration');
    expect(new Headers(fetchMock.mock.calls[1][1]?.headers).get('Authorization')).toBe('Bearer admin-session');
  });

  it('preserves conflict and auth status for the workbench to handle', async () => {
    fetchMock.mockResolvedValueOnce(new Response('{"detail":"Conflict"}', { status: 409 }));
    fetchMock.mockResolvedValueOnce(new Response('{"detail":"Unauthorized"}', { status: 401 }));
    const api = createAdminApi(fetchMock, () => 'admin-session');
    await expect(api.saveNarration(12, { narration: '讲解', expected_updated_at: null })).rejects.toMatchObject({ status: 409 });
    await expect(api.me()).rejects.toMatchObject({ status: 401, name: 'Error' });
  });

  it('reads cron jobs, queues, and bounded history with the admin bearer', async () => {
    fetchMock.mockImplementation(async () => new Response(JSON.stringify({ jobs: [], runs: [] }), { status: 200 }));
    const api = createAdminApi(fetchMock, () => 'admin-session');
    await api.cronJobs();
    await api.cronQueues();
    await api.cronRuns('fetch/upcoming', 200);
    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      '/api/admin/cron/jobs',
      '/api/admin/cron/queues',
      '/api/admin/cron/jobs/fetch%2Fupcoming/runs?limit=200',
    ]);
    expect(fetchMock.mock.calls.every(([, init]) => new Headers(init?.headers).get('Authorization') === 'Bearer admin-session')).toBe(true);
  });

  it('uses protected vision routes, exact confirmation bodies, and cancellable no-store reads', async () => {
    fetchMock.mockImplementation(async () => new Response('{}', { status: 200 }));
    const api = createAdminApi(fetchMock, () => 'admin-session');
    const signal = new AbortController().signal;
    await api.visionStatus(signal);
    await api.visionPreview(signal);
    await api.visionResumeSession('session/id', signal);
    await api.visionVerifyGeometry('session/id', 'frame-1', true, signal);
    await api.visionCapture({ game_id: 'session/id', move_index: -1, operator_confirmed: true, overwrite_existing: false }, signal);
    await api.visionReviewSample('session/id', 'frame/id', signal);
    await api.visionFreezeSession('session/id', {}, signal);
    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      '/api/admin/vision/status', '/api/admin/vision/preview',
      '/api/admin/vision/sessions/session%2Fid/resume', '/api/admin/vision/verify-geometry',
      '/api/admin/vision/capture', '/api/admin/vision/sessions/session%2Fid/frames/frame%2Fid/review',
      '/api/admin/vision/sessions/session%2Fid/freeze',
    ]);
    for (const [, init] of fetchMock.mock.calls) {
      expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer admin-session');
      expect(init?.signal).toBe(signal);
      expect(init?.cache).toBe('no-store');
    }
    expect(JSON.parse(fetchMock.mock.calls[3][1]?.body as string)).toEqual({ game_id: 'session/id', frame_id: 'frame-1', overlay_confirmed: true });
    expect(JSON.parse(fetchMock.mock.calls[4][1]?.body as string)).toEqual({ game_id: 'session/id', move_index: -1, operator_confirmed: true, overwrite_existing: false });
  });

  it('preserves cancellation rather than presenting it as a network failure', async () => {
    const controller = new AbortController();
    fetchMock.mockImplementation(async () => { controller.abort(); throw new DOMException('Aborted', 'AbortError'); });
    await expect(createAdminApi(fetchMock).visionStatus(controller.signal)).rejects.toMatchObject({ name: 'AbortError' });
  });

  it('uses the separate protected training routes with explicit confirmation and cancellable reads', async () => {
    fetchMock.mockImplementation(async () => new Response('{}', { status: 200 }));
    const api = createAdminApi(fetchMock, () => 'training-session');
    const signal = new AbortController().signal;
    await api.trainingStatus(signal);
    await api.trainingDatasets(signal);
    await api.trainingPresets(signal);
    await api.trainingRuns(signal);
    await api.trainingRun('run/id', signal);
    await api.trainingModels(signal);
    const input = { request_id: 'request-uuid', dataset_id: 'dataset-id', dataset_manifest_sha256: 'hash', weights_id: 'registered', augmentation: 'stones-standard' as const, gpu_id: '0', epochs: 2, batch: 4, imgsz: 640, seed: 0, confirmed: true as const };
    await api.trainingStart(input, signal);
    await api.trainingCancel('run/id', true, signal);
    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      '/api/admin/vision-training/status', '/api/admin/vision-training/datasets', '/api/admin/vision-training/presets',
      '/api/admin/vision-training/runs', '/api/admin/vision-training/runs/run%2Fid', '/api/admin/vision-training/models',
      '/api/admin/vision-training/runs', '/api/admin/vision-training/runs/run%2Fid/cancel',
    ]);
    for (const [, init] of fetchMock.mock.calls) {
      expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer training-session');
      expect(init?.signal).toBe(signal);
      expect(init?.cache).toBe('no-store');
    }
    expect(JSON.parse(fetchMock.mock.calls[6][1]?.body as string)).toEqual(input);
    expect(JSON.parse(fetchMock.mock.calls[7][1]?.body as string)).toEqual({ confirmed: true });
  });
});
