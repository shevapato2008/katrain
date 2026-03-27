import { useState, useEffect, useCallback } from 'react';
import { LiveAPI } from '../../api/live';
import type { MatchDetail, MoveAnalysis } from '../../types/live';

interface UseLiveMatchOptions {
  pollInterval?: number; // ms, 0 to disable polling
  fetchDetail?: boolean; // Whether to fetch from source API
}

interface UseLiveMatchResult {
  match: MatchDetail | null;
  loading: boolean;
  error: Error | null;
  currentMove: number;
  setCurrentMove: (move: number) => void;
  analysis: Record<number, MoveAnalysis>;
  refresh: () => Promise<void>;
}

export function useLiveMatch(matchId: string | undefined, options: UseLiveMatchOptions = {}): UseLiveMatchResult {
  const { pollInterval = 5000, fetchDetail = true } = options;

  const [match, setMatch] = useState<MatchDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  // Use null to indicate "not yet initialized" vs 0 which is a valid move number
  const [currentMove, setCurrentMoveInternal] = useState<number | null>(null);
  const [analysis, setAnalysis] = useState<Record<number, MoveAnalysis>>({});

  // Wrap setCurrentMove to always set a number (not null)
  const setCurrentMove = useCallback((move: number) => {
    setCurrentMoveInternal(move);
  }, []);

  const fetchMatch = useCallback(async () => {
    if (!matchId) return;

    try {
      const data = await LiveAPI.getMatch(matchId, fetchDetail);
      setMatch(data);

      // Auto-set to latest move on initial load (when currentMove is null)
      if (currentMove === null) {
        setCurrentMoveInternal(data.move_count);
      }

      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch match'));
    } finally {
      setLoading(false);
    }
  }, [matchId, fetchDetail, currentMove]);

  const fetchAnalysis = useCallback(async (preload = false) => {
    if (!matchId) return;

    try {
      // Use preload on initial page load to boost priority of pending analysis
      const data = preload
        ? await LiveAPI.preloadAnalysis(matchId)
        : await LiveAPI.getMatchAnalysis(matchId);
      setAnalysis(data.analysis);
    } catch (err) {
      // Analysis may not be available yet, not critical
      console.warn('Failed to fetch analysis:', err);
    }
  }, [matchId]);

  // Reset state when matchId changes
  useEffect(() => {
    // Reset currentMove to null so it auto-sets to new match's move_count
    setCurrentMoveInternal(null);
    setAnalysis({});
  }, [matchId]);

  // Initial fetch with preload
  useEffect(() => {
    if (matchId) {
      setLoading(true);
      fetchMatch();
      fetchAnalysis(true); // Use preload on initial load to boost priority
    }
  // Only run on matchId change, not on every fetchMatch/fetchAnalysis change
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchId]);

  // Polling for live updates
  useEffect(() => {
    if (!matchId || pollInterval <= 0) return;
    if (match?.status !== 'live') return; // Only poll for live matches

    const interval = setInterval(() => {
      fetchMatch();
      fetchAnalysis(false); // Regular fetch for polling
    }, pollInterval);

    return () => clearInterval(interval);
  }, [matchId, pollInterval, match?.status, fetchMatch, fetchAnalysis]);

  const refresh = useCallback(async () => {
    await fetchMatch();
    await fetchAnalysis();
  }, [fetchMatch, fetchAnalysis]);

  // Return currentMove as number (default to move_count if null, or 0 if no match)
  const effectiveCurrentMove = currentMove ?? match?.move_count ?? 0;

  return {
    match,
    loading,
    error,
    currentMove: effectiveCurrentMove,
    setCurrentMove,
    analysis,
    refresh,
  };
}
