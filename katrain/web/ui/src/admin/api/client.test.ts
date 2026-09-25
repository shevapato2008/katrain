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
});
