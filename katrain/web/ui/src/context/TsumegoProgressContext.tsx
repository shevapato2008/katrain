/**
 * TsumegoProgressContext — unified, account-scoped tsumego progress source (shared zone).
 *
 * Single READ source for every layer (level / category / unit / card): the provider loads
 * localStorage('tsumego_progress') synchronously on mount, then (if logged in) merges the
 * server's GET /progress field-by-field. All aggregate counts are computed locally from this
 * one map — no per-page fetch, no backend aggregation endpoint.
 *
 * WRITE: markProgress() does an immediate field-level localStorage merge (live UI cache) and,
 * when a token is present, fires TsumegoAPI.saveProgress fire-and-forget (offline is handled
 * server-side via local-write + sync queue in board mode).
 *
 * R3 safety: the DEFAULT context value (rendered WITHOUT a Provider, e.g. in tests) still
 * performs the localStorage field-merge in markProgress via the shared pure helper, but skips
 * in-memory state + server. This guarantees localStorage persistence is never lost even when
 * the Provider is absent, and the consuming hook never crashes for lack of a Provider.
 */

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useMemo,
  useRef,
  useEffect,
  type ReactNode,
} from 'react';
import { useAuth } from './AuthContext';
import { TsumegoAPI, type TsumegoProgressEntry } from '../api/tsumegoApi';

export type { TsumegoProgressEntry } from '../api/tsumegoApi';

export type TsumegoProgressMap = Record<string, TsumegoProgressEntry>;

/** Input shape for a single progress write. */
export interface MarkProgressInput {
  completed: boolean;
  attempts: number;
  lastDuration?: number;
}

const STORAGE_KEY = 'tsumego_progress';

// ============ Pure field-merge helpers (shared by default + provider) ============

/**
 * Field-level merge of two progress entries. Invariants:
 *   completed         = existing OR incoming   (monotonic, never regresses)
 *   attempts          = max(existing, incoming)
 *   lastDuration      = incoming if defined, else existing (latest wins)
 *   lastAttemptAt     = latest (incoming if defined, else existing)
 *   firstCompletedAt  = earliest defined value
 */
export function mergeProgressEntry(
  existing: TsumegoProgressEntry | undefined,
  incoming: TsumegoProgressEntry,
): TsumegoProgressEntry {
  if (!existing) return { ...incoming };

  const completed = existing.completed || incoming.completed;

  // earliest firstCompletedAt
  let firstCompletedAt: string | undefined;
  const candidates = [existing.firstCompletedAt, incoming.firstCompletedAt].filter(
    (v): v is string => !!v,
  );
  if (candidates.length > 0) {
    firstCompletedAt = candidates.reduce((a, b) => (a < b ? a : b));
  }

  return {
    completed,
    attempts: Math.max(existing.attempts ?? 0, incoming.attempts ?? 0),
    lastDuration: incoming.lastDuration ?? existing.lastDuration,
    lastAttemptAt: incoming.lastAttemptAt ?? existing.lastAttemptAt,
    firstCompletedAt,
  };
}

/** Read the full progress map from localStorage (safe — never throws). */
export function readLocalProgress(): TsumegoProgressMap {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return {};
    const parsed = JSON.parse(stored);
    return parsed && typeof parsed === 'object' ? (parsed as TsumegoProgressMap) : {};
  } catch {
    return {};
  }
}

/**
 * Field-merge one entry into the localStorage map and persist it.
 * Returns the merged entry (so the caller can also update in-memory state).
 * This is the pure write used by BOTH the default context and the provider.
 */
export function writeLocalProgress(id: string, incoming: TsumegoProgressEntry): TsumegoProgressEntry {
  const map = readLocalProgress();
  const merged = mergeProgressEntry(map[id], incoming);
  map[id] = merged;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    // best-effort cache; ignore quota/serialization failures
  }
  return merged;
}

/** Field-merge a whole server map into a base map (used on mount). */
export function mergeProgressMaps(
  base: TsumegoProgressMap,
  incoming: TsumegoProgressMap,
): TsumegoProgressMap {
  const result: TsumegoProgressMap = { ...base };
  for (const [id, entry] of Object.entries(incoming)) {
    result[id] = mergeProgressEntry(result[id], entry);
  }
  return result;
}

/** Build a TsumegoProgressEntry from a markProgress() call, stamping timestamps. */
function entryFromMark(input: MarkProgressInput): TsumegoProgressEntry {
  const now = new Date().toISOString();
  return {
    completed: input.completed,
    attempts: input.attempts,
    lastDuration: input.lastDuration,
    lastAttemptAt: now,
    firstCompletedAt: input.completed ? now : undefined,
  };
}

// ============ Context shape ============

export interface TsumegoProgressContextValue {
  progress: TsumegoProgressMap;
  /** Write progress for one problem: localStorage always, in-memory + server only under Provider. */
  markProgress: (id: string, input: MarkProgressInput) => void;
  isCompleted: (id: string) => boolean;
  unitProgress: (ids: string[]) => { completed: number; total: number };
  categoryProgress: (ids: string[]) => { completed: number; total: number };
  refresh: () => void;
}

/**
 * DEFAULT value (no Provider). markProgress still persists to localStorage via the shared
 * pure helper, but does NOT touch in-memory state or the server. Aggregates read live from
 * localStorage so they remain correct without a Provider.
 */
const defaultContextValue: TsumegoProgressContextValue = {
  progress: {},
  markProgress: (id, input) => {
    // R3 safety: localStorage persistence must survive even without a Provider.
    writeLocalProgress(id, entryFromMark(input));
  },
  isCompleted: (id) => !!readLocalProgress()[id]?.completed,
  unitProgress: (ids) => {
    const map = readLocalProgress();
    return { completed: ids.filter((id) => map[id]?.completed).length, total: ids.length };
  },
  categoryProgress: (ids) => {
    const map = readLocalProgress();
    return { completed: ids.filter((id) => map[id]?.completed).length, total: ids.length };
  },
  refresh: () => {},
};

const TsumegoProgressContext = createContext<TsumegoProgressContextValue>(defaultContextValue);

// ============ Provider ============

export const TsumegoProgressProvider = ({ children }: { children: ReactNode }) => {
  const { token } = useAuth();

  // Synchronous initial load from localStorage (so first paint already has cached progress).
  const [progress, setProgress] = useState<TsumegoProgressMap>(() => readLocalProgress());

  // Guard against double server-fetch (e.g. React StrictMode) for the same token.
  const fetchedTokenRef = useRef<string | null>(null);

  const fetchAndMerge = useCallback((authToken: string) => {
    TsumegoAPI.getProgress(authToken)
      .then((serverMap) => {
        setProgress((prev) => {
          const merged = mergeProgressMaps(prev, serverMap);
          try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
          } catch {
            // best-effort cache
          }
          return merged;
        });
      })
      .catch(() => {
        // offline / unauthorized — keep localStorage-only progress
      });
  }, []);

  useEffect(() => {
    if (!token) {
      fetchedTokenRef.current = null;
      return;
    }
    if (fetchedTokenRef.current === token) return;
    fetchedTokenRef.current = token;
    fetchAndMerge(token);
  }, [token, fetchAndMerge]);

  const markProgress = useCallback(
    (id: string, input: MarkProgressInput) => {
      const incoming = entryFromMark(input);
      // 1) localStorage live write (field-merge) — immediate cache for UI/offline.
      const merged = writeLocalProgress(id, incoming);
      // 2) in-memory state update with the same merged entry.
      setProgress((prev) => ({ ...prev, [id]: merged }));
      // 3) server fire-and-forget (only when authenticated). Offline handled server-side.
      if (token) {
        TsumegoAPI.saveProgress(
          id,
          { completed: input.completed, attempts: input.attempts, lastDuration: input.lastDuration },
          token,
        ).catch(() => {
          // swallow — offline/queued server-side; localStorage already holds the truth
        });
      }
    },
    [token],
  );

  const refresh = useCallback(() => {
    // Re-sync from localStorage + server.
    setProgress((prev) => mergeProgressMaps(prev, readLocalProgress()));
    if (token) fetchAndMerge(token);
  }, [token, fetchAndMerge]);

  const isCompleted = useCallback((id: string) => !!progress[id]?.completed, [progress]);

  const unitProgress = useCallback(
    (ids: string[]) => ({
      completed: ids.filter((id) => progress[id]?.completed).length,
      total: ids.length,
    }),
    [progress],
  );

  const categoryProgress = useCallback(
    (ids: string[]) => ({
      completed: ids.filter((id) => progress[id]?.completed).length,
      total: ids.length,
    }),
    [progress],
  );

  const value = useMemo<TsumegoProgressContextValue>(
    () => ({ progress, markProgress, isCompleted, unitProgress, categoryProgress, refresh }),
    [progress, markProgress, isCompleted, unitProgress, categoryProgress, refresh],
  );

  return (
    <TsumegoProgressContext.Provider value={value}>{children}</TsumegoProgressContext.Provider>
  );
};

/**
 * Consume the unified progress source. Returns the safe default when no Provider is mounted
 * (markProgress still persists to localStorage; in-memory/server are skipped).
 */
export const useTsumegoProgress = (): TsumegoProgressContextValue =>
  useContext(TsumegoProgressContext);
