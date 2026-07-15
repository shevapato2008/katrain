import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  ReportsAPI,
  isActiveReportStatus,
  isTerminalReportStatus,
  type ReportTaskSummary,
} from './reportApi';

const task: ReportTaskSummary = {
  id: 7,
  user_game_id: 'game-1',
  status: 'pending',
  report_type: 'normal',
  total_moves: 120,
  analyzed_moves: 0,
  requested_visits: 500,
};

const okJson = <T>(body: T) => ({
  ok: true,
  json: vi.fn().mockResolvedValue(body),
});

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('ReportsAPI', () => {
  it('lists reports with bearer authentication', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okJson([task])));

    await expect(ReportsAPI.list('token')).resolves.toEqual([task]);

    expect(fetch).toHaveBeenCalledWith('/api/v1/reports/', {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer token',
      },
    });
  });

  it('gets the queue summary from the existing endpoint', async () => {
    const summary = { pending: 1, running: 2, completed: 3, failed: 4 };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okJson(summary)));

    await expect(ReportsAPI.summary('token')).resolves.toEqual(summary);

    expect(fetch).toHaveBeenCalledWith('/api/v1/reports/summary', expect.objectContaining({
      headers: expect.objectContaining({ 'Authorization': 'Bearer token' }),
    }));
  });

  it('gets a report by numeric task id', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okJson(task)));

    await ReportsAPI.get('token', 7);

    expect(fetch).toHaveBeenCalledWith('/api/v1/reports/7', expect.objectContaining({
      headers: expect.objectContaining({ 'Authorization': 'Bearer token' }),
    }));
  });

  it('creates a normal report through the existing server endpoint', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okJson(task)));
    const params = { user_game_id: 'game-1', report_type: 'normal' as const, force: true };

    await ReportsAPI.create('token', params);

    expect(fetch).toHaveBeenCalledWith('/api/v1/reports/', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify(params),
      headers: expect.objectContaining({ 'Authorization': 'Bearer token' }),
    }));
  });

  it('creates a deep report through the existing server endpoint', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okJson(task)));

    await ReportsAPI.create('token', { user_game_id: 'game-1', report_type: 'deep' });

    expect(fetch).toHaveBeenCalledWith('/api/v1/reports/', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ user_game_id: 'game-1', report_type: 'deep' }),
      headers: expect.objectContaining({ 'Authorization': 'Bearer token' }),
    }));
  });

  it('retries a report through its retry endpoint', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okJson(task)));

    await ReportsAPI.retry('token', 7);

    expect(fetch).toHaveBeenCalledWith('/api/v1/reports/7/retry', expect.objectContaining({
      method: 'POST',
      headers: expect.objectContaining({ 'Authorization': 'Bearer token' }),
    }));
  });

  it('gets analyzed moves for a report', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okJson([])));

    await ReportsAPI.getMoves('token', 7);

    expect(fetch).toHaveBeenCalledWith('/api/v1/reports/7/moves', expect.objectContaining({
      headers: expect.objectContaining({ 'Authorization': 'Bearer token' }),
    }));
  });

  it('surfaces non-success response text', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      text: vi.fn().mockResolvedValue('report already exists'),
    }));

    await expect(ReportsAPI.create('token', { user_game_id: 'game-1' }))
      .rejects.toThrow('Request failed 409: report already exists');
  });
});

describe('report statuses', () => {
  it('keeps unknown server statuses renderable while narrowing known behavior', () => {
    const unknown: ReportTaskSummary = { ...task, status: 'cancelling' };

    expect(unknown.status).toBe('cancelling');
    expect(isActiveReportStatus('pending')).toBe(true);
    expect(isActiveReportStatus('running')).toBe(true);
    expect(isActiveReportStatus('completed')).toBe(false);
    expect(isTerminalReportStatus('completed')).toBe(true);
    expect(isTerminalReportStatus('failed')).toBe(true);
    expect(isTerminalReportStatus(unknown.status)).toBe(false);
  });
});
