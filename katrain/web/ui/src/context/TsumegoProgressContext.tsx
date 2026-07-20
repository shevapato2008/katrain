/**
 * TsumegoProgressContext — unified, IDENTITY-SCOPED tsumego progress source (shared zone).
 *
 * Single READ source for every layer (level / category / unit / card): the provider loads
 * the current identity's cache synchronously on mount, then (if logged in) merges the
 * server's GET /progress field-by-field. All aggregate counts are computed locally from this
 * one map — no per-page fetch, no backend aggregation endpoint.
 *
 * WRITE: markProgress() does an immediate field-level cache merge (live UI cache) and, when a
 * token is present, fires TsumegoAPI.saveProgress fire-and-forget (offline is handled
 * server-side via local-write + sync queue in board mode).
 *
 * Client-side zero-persistence (box-SSO guest mode, 4th layer, R9-F1): the cache is no longer
 * a single global `localStorage['tsumego_progress']` key. It is routed through
 * `kioskActivityStorage`, identity-scoped by `user.uuid`:
 *   - a guest (or any UNRESOLVED identity — see below) gets an in-memory-only namespace:
 *     nothing it reads can be a prior real user's data, nothing it writes ever reaches disk.
 *   - a real user gets `localStorage` under `tsumego_progress:${user.uuid}`.
 *
 * THE FIRST-PAINT RACE: this provider's `useState` initializer runs SYNCHRONOUSLY at mount
 * (so first paint already has cached progress), but AuthContext resolves identity
 * ASYNCHRONOUSLY (`isLoading` starts true, flips false only after the `/me` probe settles).
 * The initializer therefore MUST NOT read any real localStorage key while `isLoading` is
 * still true — doing so would let a guest's first paint observe whatever the PREVIOUS
 * identity (or the legacy unscoped key) last wrote, since decision-B guest entry only
 * navigates the browser rather than restarting the chromium process. The fix: the
 * initializer returns `{}` unconditionally while `isLoading`, and a resolution effect
 * (re)hydrates — and, for a real user, migrates the legacy unscoped key exactly once — the
 * moment identity settles (or changes, e.g. Alice -> guest -> Alice).
 *
 * R3 safety: the DEFAULT context value (rendered WITHOUT a Provider, e.g. in tests) still
 * performs the cache field-merge in markProgress via the shared pure helper (routed through
 * the kioskActivityStorage resolved-identity singleton, which defaults to the same safe
 * ephemeral store until AuthContext explicitly resolves a real identity), but skips
 * in-memory state + server. This guarantees the consuming hook never crashes for lack of a
 * Provider, and never leaks/persists before identity is known either.
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
import {
  kioskActivityStorage,
  getCurrentKioskActivityStorage,
  migrateLegacyActivityKey,
  type KioskActivityStorage,
} from '../kiosk/storage/kioskActivityStorage';

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

/**
 * Read the full progress map from the given identity-scoped store (safe — never throws).
 * Defaults to the kioskActivityStorage resolved-identity singleton, which is itself safe by
 * default (ephemeral, in-memory) until AuthContext explicitly resolves a real identity — see
 * module doc. Pass an explicit `store` (as the Provider below does) when the caller already
 * knows the current identity synchronously and cannot wait for the singleton to catch up.
 */
export function readLocalProgress(
  store: KioskActivityStorage = getCurrentKioskActivityStorage(),
): TsumegoProgressMap {
  try {
    const stored = store.getItem(STORAGE_KEY);
    if (!stored) return {};
    const parsed = JSON.parse(stored);
    return parsed && typeof parsed === 'object' ? (parsed as TsumegoProgressMap) : {};
  } catch {
    return {};
  }
}

/**
 * Field-merge one entry into the identity-scoped map and persist it.
 * Returns the merged entry (so the caller can also update in-memory state).
 * This is the pure write used by BOTH the default context and the provider.
 */
export function writeLocalProgress(
  id: string,
  incoming: TsumegoProgressEntry,
  store: KioskActivityStorage = getCurrentKioskActivityStorage(),
): TsumegoProgressEntry {
  const map = readLocalProgress(store);
  const merged = mergeProgressEntry(map[id], incoming);
  map[id] = merged;
  try {
    store.setItem(STORAGE_KEY, JSON.stringify(map));
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
  /** Write progress for one problem: cache always, in-memory + server only under Provider. */
  markProgress: (id: string, input: MarkProgressInput) => void;
  isCompleted: (id: string) => boolean;
  unitProgress: (ids: string[]) => { completed: number; total: number };
  categoryProgress: (ids: string[]) => { completed: number; total: number };
  refresh: () => void;
}

/**
 * DEFAULT value (no Provider). markProgress still persists via the shared pure helper (routed
 * through the resolved-identity singleton — safe/ephemeral until AuthContext resolves a real
 * identity), but does NOT touch in-memory state or the server. Aggregates read live from the
 * current identity's cache so they remain correct without a Provider.
 */
const defaultContextValue: TsumegoProgressContextValue = {
  progress: {},
  markProgress: (id, input) => {
    // R3 safety: cache persistence must survive even without a Provider — but never before
    // (or across) identity resolution; see the resolved-identity singleton in
    // kioskActivityStorage.ts.
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
  const { token, user, isGuest, isLoading } = useAuth();
  const identityKey = user?.uuid ?? null;

  // "Resolved identity" signature — null while genuinely unresolved (isLoading, or no
  // identity at all). Only ever changes when the ACTUAL resolved identity changes (guest vs
  // "user:<uuid>"), so effects below don't re-fire on every unrelated re-render.
  const signature = isLoading ? null : isGuest ? 'guest' : identityKey ? `user:${identityKey}` : null;

  // Synchronous first-paint init: MUST be empty while identity is unresolved (isLoading) —
  // this is the load-bearing race guard described in the module doc. Passing
  // identityKey=null whenever isLoading forces kioskActivityStorage's ephemeral branch
  // regardless of what identityKey/isGuest eventually resolve to, so the very first render
  // can never surface a prior real user's (or the legacy unscoped) data.
  const [progress, setProgress] = useState<TsumegoProgressMap>(() =>
    isLoading ? {} : readLocalProgress(kioskActivityStorage(isGuest ? null : identityKey, isGuest)),
  );

  // The store backing the CURRENT resolved identity. Starts on the same safe ephemeral
  // default as the useState initializer above; only ever replaced by the resolution effect.
  const storeRef = useRef<KioskActivityStorage>(kioskActivityStorage(null, false));
  const resolvedSignatureRef = useRef<string | null>(null);

  // Guard against double server-fetch (e.g. React StrictMode) for the same token.
  const fetchedTokenRef = useRef<string | null>(null);

  const fetchAndMerge = useCallback((authToken: string, store: KioskActivityStorage) => {
    TsumegoAPI.getProgress(authToken)
      .then((serverMap) => {
        setProgress((prev) => {
          const merged = mergeProgressMaps(prev, serverMap);
          try {
            store.setItem(STORAGE_KEY, JSON.stringify(merged));
          } catch {
            // best-effort cache
          }
          return merged;
        });
      })
      .catch(() => {
        // offline / unauthorized — keep the local-only progress
      });
  }, []);

  // Resolve / (re)hydrate / migrate exactly once per identity signature change, and refetch
  // whenever the token changes under a resolved identity. Never runs while `signature` is
  // null (i.e. while isLoading, or with no identity at all) — that is what keeps the
  // first-paint window empty: `progress` simply stays at the `{}` the initializer produced.
  useEffect(() => {
    if (signature === null) return;

    let store = storeRef.current;
    if (resolvedSignatureRef.current !== signature) {
      resolvedSignatureRef.current = signature;
      store = kioskActivityStorage(isGuest ? null : identityKey, isGuest);
      storeRef.current = store;

      // Legacy migration — real, resolved identity ONLY. Guests must never migrate: they
      // must not read, consume, or delete the legacy unscoped key.
      if (!isGuest && identityKey) {
        migrateLegacyActivityKey(store, STORAGE_KEY);
      }

      // Synchronizing React state with an external store (identity-scoped storage) on an
      // identity change is exactly what this effect is for — there is no render-time
      // equivalent, since `store` itself is only known once identity resolves.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setProgress(readLocalProgress(store));
      fetchedTokenRef.current = null; // force a refetch under the (possibly new) store below
    }

    if (!token) {
      fetchedTokenRef.current = null;
      return;
    }
    if (fetchedTokenRef.current === token) return;
    fetchedTokenRef.current = token;
    fetchAndMerge(token, store);
  }, [signature, isGuest, identityKey, token, fetchAndMerge]);

  const markProgress = useCallback(
    (id: string, input: MarkProgressInput) => {
      const incoming = entryFromMark(input);
      // 1) identity-scoped cache write (field-merge) — immediate cache for UI/offline.
      const merged = writeLocalProgress(id, incoming, storeRef.current);
      // 2) in-memory state update with the same merged entry.
      setProgress((prev) => ({ ...prev, [id]: merged }));
      // 3) server fire-and-forget (only when authenticated). Offline handled server-side.
      if (token) {
        TsumegoAPI.saveProgress(
          id,
          { completed: input.completed, attempts: input.attempts, lastDuration: input.lastDuration },
          token,
        ).catch(() => {
          // swallow — offline/queued server-side; the cache already holds the truth
        });
      }
    },
    [token],
  );

  const refresh = useCallback(() => {
    // Re-sync from the identity-scoped cache + server.
    setProgress((prev) => mergeProgressMaps(prev, readLocalProgress(storeRef.current)));
    if (token) fetchAndMerge(token, storeRef.current);
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
 * (markProgress still persists via the resolved-identity singleton; in-memory/server are
 * skipped).
 */
export const useTsumegoProgress = (): TsumegoProgressContextValue =>
  useContext(TsumegoProgressContext);
