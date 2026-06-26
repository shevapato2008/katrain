import { useState, useEffect, useCallback, useRef } from 'react';
import { LiveAPI } from '../../api/live';
import type { MatchDetail, MoveAnalysis } from '../../types/live';

interface UseLiveMatchOptions {
  pollInterval?: number; // ms, 0 to disable polling
  fetchDetail?: boolean; // Whether to fetch from source API
  // Analysis fetching strategy:
  //  - 'poll'    (default): preload on entry + freshness-gated polling (detail page)
  //  - 'preload': preload once, never poll analysis
  //  - 'none'   : never fetch analysis (board preview only needs moves/playback)
  analysisMode?: 'none' | 'preload' | 'poll';
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

const NO_PROGRESS_LIMIT = 6; // ~30s at 5s poll: stop hammering a permanently-FAILED position

export function useLiveMatch(matchId: string | undefined, options: UseLiveMatchOptions = {}): UseLiveMatchResult {
  const { pollInterval = 5000, fetchDetail = true, analysisMode = 'poll' } = options;

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

  // Stable across move navigation: auto-set the latest move via a functional update
  // (no `currentMove` dependency), so the polling interval isn't torn down every move.
  const fetchMatch = useCallback(async () => {
    if (!matchId) return;

    try {
      const data = await LiveAPI.getMatch(matchId, fetchDetail);
      setMatch(data);
      setCurrentMoveInternal((prev) => (prev === null ? data.move_count : prev));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch match'));
    } finally {
      setLoading(false);
    }
  }, [matchId, fetchDetail]);

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

  // The effective (never-null) current move, used both for return value and the gate.
  const effectiveCurrentMove = currentMove ?? match?.move_count ?? 0;

  // Mirror the latest render state so the polling setInterval reads fresh values
  // without re-subscribing (avoids stale closures and interval churn).
  const liveRef = useRef({ analysis, match, currentMove: effectiveCurrentMove });
  useEffect(() => {
    liveRef.current = { analysis, match, currentMove: effectiveCurrentMove };
  });
  // no-progress backstop: stop polling analysis when behind but nothing new arrives.
  const staleRef = useRef({ keyCount: -1, moveCount: -1, viewed: -1, streak: 0 });

  // Reset state when matchId changes
  useEffect(() => {
    setCurrentMoveInternal(null);
    setAnalysis({});
    staleRef.current = { keyCount: -1, moveCount: -1, viewed: -1, streak: 0 };
  }, [matchId]);

  // Initial fetch (+ preload unless analysis is disabled)
  useEffect(() => {
    if (matchId) {
      setLoading(true);
      fetchMatch();
      if (analysisMode !== 'none') {
        fetchAnalysis(true); // preload on entry to boost priority
      }
    }
    // Only run on matchId change, not on every fetchMatch/fetchAnalysis change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchId, analysisMode]);

  // Polling for live updates. Always refreshes match while live; the heavy analysis
  // fetch is gated to "tip or viewed move not yet analyzed" (position-aware), so the
  // steady state issues zero analysis requests.
  useEffect(() => {
    if (!matchId || pollInterval <= 0) return;

    const id = setInterval(() => {
      const { analysis: a, match: m, currentMove: cm } = liveRef.current;
      if (!m || m.status !== 'live') return; // checked at runtime so deps stay stable

      fetchMatch(); // detail / move_count / source winrate stay fresh every tick

      if (analysisMode !== 'poll') return; // preview / preload-only: never poll analysis

      const mc = m.move_count;
      const behind = a[mc] == null || a[cm] == null; // tip or viewed move not analyzed
      const keyCount = Object.keys(a).length;
      const s = staleRef.current;
      // Reset the no-progress streak whenever coverage grows OR the tip/viewed move changes.
      if (keyCount !== s.keyCount || mc !== s.moveCount || cm !== s.viewed) {
        staleRef.current = { keyCount, moveCount: mc, viewed: cm, streak: 0 };
      }
      if (behind && staleRef.current.streak < NO_PROGRESS_LIMIT) {
        staleRef.current.streak += 1;
        fetchAnalysis(false);
      }
    }, pollInterval);

    return () => clearInterval(id);
  }, [matchId, pollInterval, analysisMode, fetchMatch, fetchAnalysis]);

  // On live -> finished transition, do one final catch-up so a finishing match
  // doesn't freeze with incomplete analysis (polling stops once not live).
  const prevStatusRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    const st = match?.status;
    if (prevStatusRef.current === 'live' && st === 'finished' && analysisMode === 'poll') {
      fetchAnalysis(false);
    }
    prevStatusRef.current = st;
  }, [match?.status, analysisMode, fetchAnalysis]);

  const refresh = useCallback(async () => {
    await fetchMatch();
    if (analysisMode !== 'none') {
      await fetchAnalysis();
    }
  }, [fetchMatch, fetchAnalysis, analysisMode]);

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
