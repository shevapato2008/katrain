import { useCallback, useEffect, useState } from 'react';

import { LiveAPI } from '../../api/live';
import type { UpcomingMatch } from '../../types/live';
import { useTranslation } from '../useTranslation';

interface Options {
  limit?: number;
  /** 0 关掉轮询。赛程是**按天变的东西**,默认 30 分钟一次,和 galaxy 的 `UpcomingList` 同一个数。 */
  pollIntervalMs?: number;
}

/**
 * 赛程(「即将开始」)。galaxy 的 `components/live/UpcomingList.tsx` 自己在组件里抓,
 * 那份**不动** —— 它带着 MUI 卡片和 `target="_blank"` 外链,盒上两样都不能要。
 * 这里只取数;怎么画由消费方决定。
 *
 * ⚠️ **失败时不清空上一批**:「拉不到」和「今天没有比赛」在屏上必须是两句话,
 * 把 `upcoming` 清成 `[]` 就等于替用户断言后者。
 */
export function useUpcomingMatches({ limit = 20, pollIntervalMs = 30 * 60 * 1000 }: Options = {}) {
  const { lang } = useTranslation();
  const [upcoming, setUpcoming] = useState<UpcomingMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchUpcoming = useCallback(async () => {
    try {
      const data = await LiveAPI.getUpcoming(limit, lang);
      setUpcoming(data.matches);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch upcoming'));
    } finally {
      setLoading(false);
    }
  }, [limit, lang]);

  useEffect(() => { void fetchUpcoming(); }, [fetchUpcoming]);

  useEffect(() => {
    if (pollIntervalMs <= 0) return;
    const timer = setInterval(() => { void fetchUpcoming(); }, pollIntervalMs);
    return () => clearInterval(timer);
  }, [fetchUpcoming, pollIntervalMs]);

  return { upcoming, loading, error, refresh: fetchUpcoming };
}
