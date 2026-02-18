import { useState, useEffect, useCallback } from 'react';
import { LiveAPI } from '../../api/live';
import type { MatchSummary, MatchListResponse } from '../../types/live';
import { useTranslation } from '../useTranslation';

interface UseLiveMatchesOptions {
  status?: 'live' | 'finished';
  source?: 'xingzhen' | 'weiqi_org';
  limit?: number;
  pollInterval?: number; // ms, 0 to disable
}

interface UseLiveMatchesResult {
  matches: MatchSummary[];
  liveCount: number;
  total: number;
  loading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
}

export function useLiveMatches(options: UseLiveMatchesOptions = {}): UseLiveMatchesResult {
  const { status, source, limit = 50, pollInterval = 30000 } = options;
  const { lang } = useTranslation();

  const [matches, setMatches] = useState<MatchSummary[]>([]);
  const [liveCount, setLiveCount] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchMatches = useCallback(async () => {
    try {
      const data: MatchListResponse = await LiveAPI.getMatches({ status, source, limit, lang });
      setMatches(data.matches);
      setLiveCount(data.live_count);
      setTotal(data.total);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch matches'));
    } finally {
      setLoading(false);
    }
  }, [status, source, limit, lang]);

  // Initial fetch
  useEffect(() => {
    fetchMatches();
  }, [fetchMatches]);

  // Polling for live updates
  useEffect(() => {
    if (pollInterval <= 0) return;

    const interval = setInterval(fetchMatches, pollInterval);
    return () => clearInterval(interval);
  }, [fetchMatches, pollInterval]);

  return {
    matches,
    liveCount,
    total,
    loading,
    error,
    refresh: fetchMatches,
  };
}

export function useFeaturedMatch() {
  const { lang } = useTranslation();
  const [match, setMatch] = useState<MatchSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchFeatured = useCallback(async () => {
    try {
      const data = await LiveAPI.getFeaturedMatch(lang);
      setMatch(data.match);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch featured match'));
    } finally {
      setLoading(false);
    }
  }, [lang]);

  useEffect(() => {
    fetchFeatured();
  }, [fetchFeatured]);

  // Poll for updates
  useEffect(() => {
    const interval = setInterval(fetchFeatured, 10000);
    return () => clearInterval(interval);
  }, [fetchFeatured]);

  return { match, loading, error, refresh: fetchFeatured };
}
