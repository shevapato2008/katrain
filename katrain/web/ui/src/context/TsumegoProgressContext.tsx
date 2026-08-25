/**
 * TsumegoProgressContext — unified, account-scoped tsumego progress source (shared zone).
 *
 * Single READ source for every layer (level / category / unit / card): the provider loads
 * localStorage(`tsumego_progress:u<id>`) on mount, then (if signed in) merges the server's
 * GET /progress field-by-field. All aggregate counts are computed locally from this one map —
 * no per-page fetch, no backend aggregation endpoint.
 *
 * WRITE: markProgress() does an immediate field-level localStorage merge (live UI cache) and,
 * when there is an account, fires TsumegoAPI.saveProgress fire-and-forget (offline is handled
 * server-side via local-write + sync queue in board mode).
 *
 * ⚠️ **两条 2026-08-25 修掉的东西,改这个文件之前先读:**
 *  ① 钥匙**按账号分**。不分人的那把会在共享盒子上把甲的进度算进乙的账,
 *    而 `completed` 的合并是单调的 ⇒ 算错了退不回去。见 `progressStorageKey`。
 *  ② 服务端同步的闸是 **`user` 不是 `token`**。出厂盒子里 token 恒为 null、
 *    身份走 cookie ⇒ 用 `if (token)` 会让盒子上从不拉也从不写,而本机开发全绿。
 *    见 Provider 里那段注释。
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

/**
 * **每个账号一把钥匙。** 盒子是多人轮流用的共享设备 —— 一把不分人的
 * `tsumego_progress` 会把甲解过的题算进乙的账,而 `mergeProgressEntry` 里
 * `completed = existing || incoming` 是**单调的**,一旦算错就再也退不回去。
 *
 * 同一条理由本 track 在屏 24 课程进度上用过一次(scope.md §20 D1:「按机器存会把
 * 甲的进度显示成乙的 —— 那是关于一个人的假话,比不显示更坏」),做题这边一直没照做。
 */
const STORAGE_PREFIX = 'tsumego_progress';

/** 2026-08-25 之前那把不分人的旧钥匙。**不迁移**,理由见 `dropLegacyUnscopedProgress`。 */
const LEGACY_UNSCOPED_KEY = 'tsumego_progress';

export function progressStorageKey(userId: number | string | null | undefined): string {
  return userId === null || userId === undefined
    ? `${STORAGE_PREFIX}:anon`
    : `${STORAGE_PREFIX}:u${userId}`;
}

/**
 * 当前账号的存储作用域。**模块级是有意的,不是图省事:**
 *  · 它描述的本来就是「这个标签页此刻登录的是谁」,天然只有一份;
 *  · `writeLocalProgress` 有一个**不在 Provider 里**的调用方
 *    (`hooks/useTsumegoProblem.ts` 的 `cacheLocalProgress`),而无 Provider 的默认
 *    context 连 hook 都不能调 ⇒ 身份没法顺着参数传下去。
 * Provider 在 `user` 变化时设置它;没设置过就是 anon。
 */
let activeScopeKey = progressStorageKey(null);

/** 只给 Provider(和测试)用。幂等。 */
export function setProgressScope(userId: number | string | null | undefined): void {
  activeScopeKey = progressStorageKey(userId);
}

/**
 * 删掉旧的不分人 blob。**不迁移给任何账号** —— 它没有主人,
 * 把它记到「下一个登录的人」头上,正是这次要修的那个缺陷本身。
 * 登录用户的真进度在服务端,换钥匙之后第一次 `getProgress` 就会拉回来。
 */
export function dropLegacyUnscopedProgress(): void {
  try {
    localStorage.removeItem(LEGACY_UNSCOPED_KEY);
  } catch {
    // 隐私模式下 localStorage 会抛
  }
}

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
    const stored = localStorage.getItem(activeScopeKey);
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
    localStorage.setItem(activeScopeKey, JSON.stringify(map));
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
  /**
   * 服务端那一次读**失败了吗**。
   *
   * 为什么要有它:`progress` 空着有两种意思 —— 「这个人一题没做过」和「没读到」。
   * 前者写 0 是事实,后者写 0 是**编**。屏 22 那四格明令一个都不许写 0
   * (`GrowthPage` 头上那段:「拿不到就写 —,并说一句」),而不区分这两者的话
   * 一个刚断网的老用户会看到「累计已解题 0」。
   * 只在**本地也是空的**时候才有分别:本地有数就至少是个下界,照常显示。
   */
  serverLoadFailed: boolean;
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
  // 没有 Provider 就没人去读服务端 ⇒ 谈不上失败。
  serverLoadFailed: false,
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
  /**
   * ⚠️ **判别位是 `user`,不是 `token`。**
   * 出厂盒子(`VITE_BOX_SSO_STRICT`)里 `token` **恒为 `null`**
   * (`AuthContext.tsx:34` 初值写死 null;`:71` 的 `setToken(usedToken)` 里
   * `usedToken` 也是 null,因为 `:52` 的 `stored` 在严格模式下就是 null)——
   * 身份走的是 127.0.0.1 上的共享 cookie。
   * 而后端 `GET/POST /tsumego/progress` 是 `Depends(get_current_user)`,
   * 它经 `box_sso.resolve_http_token` 在严格模式下**只认 cookie、完全无视请求头**
   * ⇒ **服务端一直是通的,是前端自己用 `if (token)` 把门关上了**:
   * 盒子上从不拉、也从不写,进度只活在本机 localStorage 里。
   */
  const { user, token } = useAuth();
  const userId = user?.id ?? null;

  // 作用域必须在**第一次读之前**就位。用惰性初始化跑一次:它先于任何子组件的 render。
  const [progress, setProgress] = useState<TsumegoProgressMap>(() => {
    dropLegacyUnscopedProgress();
    setProgressScope(userId);
    return readLocalProgress();
  });

  /**
   * 账号一变(含登出 → null)就**整份换掉,不是合并** —— 别人的进度不许流进来。
   * 在 render 期间调整,不放 effect:同一帧里子组件的 `cacheLocalProgress`
   * (`useTsumegoProblem.ts`)会直接写 localStorage,effect 太晚,那一下会落到上一个人的钥匙上。
   */
  const [serverLoadFailed, setServerLoadFailed] = useState(false);
  const [scopedUser, setScopedUser] = useState<number | string | null>(userId);
  if (scopedUser !== userId) {
    setScopedUser(userId);
    setProgressScope(userId);
    setProgress(readLocalProgress());
    // 换人了,上一个人那次读失败与否与这个人无关。
    setServerLoadFailed(false);
  }

  // Guard against double server-fetch (e.g. React StrictMode) for the same account.
  const fetchedUserRef = useRef<number | string | null>(null);

  const fetchAndMerge = useCallback((authToken?: string) => {
    setServerLoadFailed(false);
    TsumegoAPI.getProgress(authToken)
      .then((serverMap) => {
        setProgress((prev) => {
          const merged = mergeProgressMaps(prev, serverMap);
          try {
            localStorage.setItem(activeScopeKey, JSON.stringify(merged));
          } catch {
            // best-effort cache
          }
          return merged;
        });
      })
      .catch(() => {
        // offline / unauthorized — keep localStorage-only progress，但**要说出去**:
        // 吞掉的话下游分不清「一题没做」和「没读到」。
        setServerLoadFailed(true);
      });
  }, []);

  useEffect(() => {
    if (userId === null) {
      fetchedUserRef.current = null;
      return;
    }
    if (fetchedUserRef.current === userId) return;
    fetchedUserRef.current = userId;
    fetchAndMerge(token ?? undefined);
  }, [userId, token, fetchAndMerge]);

  const markProgress = useCallback(
    (id: string, input: MarkProgressInput) => {
      const incoming = entryFromMark(input);
      // 1) localStorage live write (field-merge) — immediate cache for UI/offline.
      const merged = writeLocalProgress(id, incoming);
      // 2) in-memory state update with the same merged entry.
      setProgress((prev) => ({ ...prev, [id]: merged }));
      // 3) server fire-and-forget —— 闸是**有没有账号**,不是有没有 Bearer。
      //    盒子上 token 恒为 null 而 cookie 有效,`authHeaders()` 会自己处理这两种情形。
      if (user) {
        TsumegoAPI.saveProgress(
          id,
          { completed: input.completed, attempts: input.attempts, lastDuration: input.lastDuration },
          token ?? undefined,
        ).catch(() => {
          // swallow — offline/queued server-side; localStorage already holds the truth
        });
      }
    },
    [user, token],
  );

  const refresh = useCallback(() => {
    // Re-sync from localStorage + server. 闸同样是 `user` 不是 `token`(见上)。
    setProgress((prev) => mergeProgressMaps(prev, readLocalProgress()));
    if (user) fetchAndMerge(token ?? undefined);
  }, [user, token, fetchAndMerge]);

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
    () => ({ progress, serverLoadFailed, markProgress, isCompleted, unitProgress, categoryProgress, refresh }),
    [progress, serverLoadFailed, markProgress, isCompleted, unitProgress, categoryProgress, refresh],
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
