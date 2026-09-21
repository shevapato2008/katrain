import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useUpcomingMatches } from './useUpcomingMatches';
import { LiveAPI } from '../../api/live';

vi.mock('../useTranslation', () => ({ useTranslation: () => ({ t: (_k: string, d: string) => d, lang: 'cn' }) }));

const row = (id: string) => ({
  id, tournament: '名人战', round_name: '第 3 局', scheduled_time: '2026-09-21T11:00:00Z',
  player_black: '申真谞', player_white: '柯洁', source: 'foxwq' as const, source_url: 'https://example.com/x',
});

describe('useUpcomingMatches', () => {
  beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
  afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

  it('取到赛程后 loading 落下、数据出来', async () => {
    vi.spyOn(LiveAPI, 'getUpcoming').mockResolvedValue({ matches: [row('u1')] });
    const { result } = renderHook(() => useUpcomingMatches({ limit: 20 }));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.upcoming.map((m) => m.id)).toEqual(['u1']);
    expect(result.current.error).toBeNull();
  });

  it('失败时留下 error,并且不把 upcoming 改成空数组冒充「没有比赛」', async () => {
    vi.spyOn(LiveAPI, 'getUpcoming')
      .mockResolvedValueOnce({ matches: [row('u1')] })
      .mockRejectedValueOnce(new Error('boom'));
    const { result } = renderHook(() => useUpcomingMatches({ limit: 20, pollIntervalMs: 1000 }));
    await waitFor(() => expect(result.current.upcoming).toHaveLength(1));
    await vi.advanceTimersByTimeAsync(1100);
    await waitFor(() => expect(result.current.error).toBeInstanceOf(Error));
    expect(result.current.upcoming).toHaveLength(1); // 上一批还在,没有被清空
  });
});
