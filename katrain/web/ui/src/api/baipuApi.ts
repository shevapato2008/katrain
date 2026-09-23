// API + local-cache helpers for the 摆谱 (baipu / stone-placement guidance) module.
//
// `/api/v1/baipu/load` is the backend-authoritative per-step truth source
// (decision ②): the frontend is a DUMB player of `steps[]` and never recomputes
// captures. All coordinates are canonical: row=0 TOP, col=0 LEFT (the LED LUT
// convention). BaipuSessionPage converts to LiveBoard's y=0-bottom convention at
// the rendering boundary.
//
// Offline (decision (b)): selected SGF text is cached in localStorage so the
// capture floor never depends on the remote kifu repository (which is online-only).
//
// Box-SSO guest mode (client-side zero-persistence, 4th layer, R9-F1): every cache read/
// write below is routed through kioskActivityStorage, identity-scoped by `user.uuid`. A
// guest (or any unresolved identity) gets an in-memory-only namespace — nothing it reads can
// be a prior real user's cached SGF/progress, nothing it writes ever reaches disk. Callers
// that read synchronously at first paint (e.g. a `useState(() => listRecent())`
// initializer) MUST pass an explicit `store` computed from their own `useAuth()` call, gated
// on `isLoading`, rather than relying on the default (which falls back to the
// kioskActivityStorage resolved-identity singleton — safe, but updated by an effect and so
// not itself race-proof for a synchronous first-paint read).

import { getCurrentKioskActivityStorage, type KioskActivityStorage } from '../kiosk/storage/kioskActivityStorage';

const API_BASE = '/api/v1/baipu';

export type BaipuStepKind = 'setup' | 'move' | 'pass' | 'clear';

export interface BaipuPoint {
  row: number; // 0 = top
  col: number; // 0 = left
}

export interface BaipuStep {
  kind: BaipuStepKind;
  move_index: number;
  property: string; // AB | AW | B | W
  row: number | null;
  col: number | null;
  color: 'B' | 'W' | null;
  removed: BaipuPoint[];
  board_hash: string;
}

export interface BaipuMeta {
  player_black: string;
  player_white: string;
  handicap: number;
  komi: number;
  ruleset: string;
}

export interface BaipuLoadResponse {
  board_size: number;
  steps: BaipuStep[];
  meta: BaipuMeta;
}

export interface BaipuGeometryCorrection {
  status: 'corrected' | 'stale' | 'frozen' | 'off';
  source?: string;
  drift?: { median_cells?: number; over_threshold?: boolean };
}

export interface BaipuCaptureResult {
  ok: boolean;
  idempotent?: boolean;
  overwritten?: boolean;
  path?: string;
  qa_status?: string;
  frame_kind?: string;
  next_guided_move_index?: number | null;
  geometry_correction?: BaipuGeometryCorrection;
}

// Discriminated outcome so the UI can fall back when capture isn't enabled
// (404 = dev/screen-only mode). Hardware/storage failures remain blocking.
/**
 * 采集失败的原因。**409 有两种可分辨的形状,而它们对站在盘前的人意味着完全不同的事:**
 *  · `geometry` —— 几何没锁/失效(`endpoints/baipu.py:109`,`detail` 是**纯字符串**)。
 *    这一种**再按一次永远是同一个 409**,人得去重新标定棋盘。
 *  · `led` —— 灯不可用(`:140`,`detail` 是 `{error:'led_unavailable', …}`)。
 *    这一种再按一次是有可能成的。
 * 混成一句「再按一次」会让几何坏掉的人一直按下去。
 */
export type BaipuCaptureErrorReason = 'geometry' | 'led' | 'other';

export type BaipuCaptureOutcome =
  | { kind: 'ok'; result: BaipuCaptureResult }
  | { kind: 'disabled' } // 404: capture/geometry not available
  | { kind: 'error'; message: string; reason: BaipuCaptureErrorReason };

/** 这台机器摆谱时拍不拍照。见 `BaipuAPI.mode`。 */
export interface BaipuMode {
  collect: boolean;
}

/**
 * `BaipuAPI.mode` 最多等多久(毫秒,**含读 body**)。到点当「不拍」。
 * 这一问在盒上打的是本机后端、回的是一个布尔,正常几十毫秒;等满 3 秒说明后端卡住了,
 * 而摆谱入口在问到之前只有一块「正在读这份谱」—— 不能让它无限转圈。
 */
export const BAIPU_MODE_TIMEOUT_MS = 3000;

export const BaipuAPI = {
  load: async (req: { sgf?: string; kifu_id?: number }): Promise<BaipuLoadResponse> => {
    const response = await fetch(`${API_BASE}/load`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!response.ok) {
      const body = await response.text();
      throw new Error(`baipu/load failed ${response.status}: ${body}`);
    }
    return response.json();
  },

  capture: async (req: {
    game_id: string;
    move_index: number;
    sgf: string;
    capture_condition?: Record<string, unknown>;
    overwrite_existing?: boolean;
  }): Promise<BaipuCaptureOutcome> => {
    let response: Response;
    try {
      response = await fetch(`${API_BASE}/capture`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
      });
    } catch (e) {
      return { kind: 'error', message: e instanceof Error ? e.message : 'network error', reason: 'other' };
    }
    if (response.status === 404) return { kind: 'disabled' };
    if (response.ok) return { kind: 'ok', result: await response.json() };
    if (response.status === 409) {
      const body = await response.json().catch(() => ({}));
      const detail = body?.detail;
      // 判别位是 `detail` 的**形状**,不是拿 message 去匹配关键词 ——
      // 字符串的内容是会被改的文案,而形状是契约。
      //   · 纯字符串  → 几何(`endpoints/baipu.py:109` 是 409 里**唯一**给字符串的那处)
      //   · {error:'led_unavailable'} → 灯(`:140`)
      //   · 其它对象  → other。**必须留这一支**:409 还有第三种形状
      //     (遗留的 `{qa:'mismatch', diffs:[…]}`),把它归成「几何」会让屏上
      //     叫人去重新标定棋盘 —— 一件跟它毫无关系的事。
      const reason: BaipuCaptureErrorReason =
        typeof detail === 'string' ? 'geometry'
          : (typeof detail === 'object' && detail !== null && detail.error === 'led_unavailable') ? 'led'
            : 'other';
      const message = typeof detail === 'string' ? detail : detail?.message;
      return { kind: 'error', message: message ?? 'capture conflict', reason };
    }
    return { kind: 'error', message: `capture failed ${response.status}`, reason: 'other' };
  },

  /**
   * 摆谱拍不拍照(`GET /baipu/mode`)。拍照只为采 YOLO 训练数据,上线版不拍(Fan 2026-09-14)。
   * **问不到一律当「不拍」**:旧后端没这个端点(404)、网络错、回包不认识、`BAIPU_MODE_TIMEOUT_MS`
   * 内没问完(连接挂着或 body 读不完),全落到上线态。
   * 猜成「拍」的代价是盒上每一手都可能被几何 / 灯的 409 卡住;猜成「不拍」的代价是
   * 采数据的人一眼看见屏上没有「已采集 N 帧」。
   * **只 settle 一次**:超时之后才回来的结果被丢掉 —— 调用方拿到「不拍」就进了摆谱,
   * 迟到的「拍」不许在摆谱途中把页面切到采集态。
   * ⚠️ 不要拿 `/capture` 回不回 404 去猜:盒子为了几何标定总是带着 `--capture-camera` 起。
   */
  mode: async (): Promise<BaipuMode> => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    // 超时靠 race 兜底,不靠 abort:abort 只是顺手释放连接,测试里被桩掉的 fetch 根本不认 signal。
    const timedOut = new Promise<BaipuMode>((resolve) => {
      timer = setTimeout(() => { controller.abort(); resolve({ collect: false }); }, BAIPU_MODE_TIMEOUT_MS);
    });
    const asked = (async (): Promise<BaipuMode> => {
      try {
        const response = await fetch(`${API_BASE}/mode`, { signal: controller.signal });
        if (!response.ok) return { collect: false };
        const body = await response.json().catch(() => null);
        return { collect: body?.collect === true };
      } catch {
        return { collect: false };
      }
    })();
    try {
      return await Promise.race([asked, timedOut]);
    } finally {
      clearTimeout(timer);
    }
  },
};

// --------------------------------------------------------------------------- //
// Local SGF cache (offline-safe source for the session page)
// --------------------------------------------------------------------------- //

const SGF_KEY = (id: string) => `baipu:sgf:${id}`;
const RECENT_KEY = 'baipu:recent';
const PROGRESS_KEY = (id: string) => `baipu:progress:${id}`;

export interface BaipuCachedSgf {
  id: string;
  name: string;
  sgf: string;
  savedAt: number;
}

export interface BaipuRecentEntry {
  id: string;
  name: string;
  savedAt: number;
}

export interface BaipuProgress {
  k: number; // number of steps applied to the physical board
  frames: number; // captured frames so far (disk manifest is the source of truth in P4)
  updatedAt: number;
  /**
   * 这份谱一共多少步。**可选,而且必须留成可选** —— 2026-08-22 之前写下的进度里没有它,
   * 读到 `undefined` 的正确反应是「不知道摆完没有」,不是「没摆完」。
   * 棋谱屏(屏 15)那句「已摆完」只在 `total != null && k >= total` 时才敢说。
   */
  total?: number;
}

function safeParse<T>(raw: string | null): T | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

// Every function below defaults `store` to the kioskActivityStorage resolved-identity
// singleton (see top-of-file doc): guest/unresolved -> in-memory only, real user ->
// localStorage namespaced by `user.uuid`. Callers with a synchronous first-paint read (e.g.
// a `listRecent()` state initializer) should pass an explicit store instead of
// relying on the default — see BaipuSessionPage.tsx.

export function cacheSgf(
  id: string,
  name: string,
  sgf: string,
  store: KioskActivityStorage = getCurrentKioskActivityStorage(),
): void {
  const entry: BaipuCachedSgf = { id, name, sgf, savedAt: Date.now() };
  try {
    store.setItem(SGF_KEY(id), JSON.stringify(entry));
    const recent = (safeParse<BaipuRecentEntry[]>(store.getItem(RECENT_KEY)) ?? []).filter((e) => e.id !== id);
    recent.unshift({ id, name, savedAt: entry.savedAt });
    store.setItem(RECENT_KEY, JSON.stringify(recent.slice(0, 30)));
  } catch {
    // storage may be full/unavailable; the in-memory navigation state still works.
  }
}

export function getCachedSgf(
  id: string,
  store: KioskActivityStorage = getCurrentKioskActivityStorage(),
): BaipuCachedSgf | null {
  return safeParse<BaipuCachedSgf>(store.getItem(SGF_KEY(id)));
}

export function listRecent(
  store: KioskActivityStorage = getCurrentKioskActivityStorage(),
): BaipuRecentEntry[] {
  return safeParse<BaipuRecentEntry[]>(store.getItem(RECENT_KEY)) ?? [];
}

export function saveProgress(
  id: string,
  progress: BaipuProgress,
  store: KioskActivityStorage = getCurrentKioskActivityStorage(),
): void {
  try {
    store.setItem(PROGRESS_KEY(id), JSON.stringify(progress));
  } catch {
    // ignore
  }
}

export function getProgress(
  id: string,
  store: KioskActivityStorage = getCurrentKioskActivityStorage(),
): BaipuProgress | null {
  return safeParse<BaipuProgress>(store.getItem(PROGRESS_KEY(id)));
}

export function clearProgress(
  id: string,
  store: KioskActivityStorage = getCurrentKioskActivityStorage(),
): void {
  try {
    store.removeItem(PROGRESS_KEY(id));
  } catch {
    // ignore
  }
}

/**
 * 把一份谱从「最近摆过」、本地缓存和进度里整份拿掉。
 * 只给「这份谱摆不了」那一种用(K2:非 19 路)—— 留着它,棋谱屏会给一颗点了还是摆不了的「接着摆」。
 */
export function forgetSgf(
  id: string,
  store: KioskActivityStorage = getCurrentKioskActivityStorage(),
): void {
  try {
    store.removeItem(SGF_KEY(id));
    store.removeItem(PROGRESS_KEY(id));
    const recent = (safeParse<BaipuRecentEntry[]>(store.getItem(RECENT_KEY)) ?? []).filter((e) => e.id !== id);
    store.setItem(RECENT_KEY, JSON.stringify(recent));
  } catch {
    // 存储不可用时没有东西可删
  }
}

// --------------------------------------------------------------------------- //
// Coordinate conversion: canonical (row=0 top) <-> LiveBoard (y=0 bottom)
// --------------------------------------------------------------------------- //

/** Canonical (row=0 top, col=0 left) -> LiveBoard grid {x, y} (y=0 bottom). */
export function canonToBoard(row: number, col: number, boardSize: number): { x: number; y: number } {
  return { x: col, y: boardSize - 1 - row };
}

const GTP_LETTERS = 'ABCDEFGHJKLMNOPQRSTUVWXYZ'; // skips I

/** Canonical (row=0 top, col=0 left) -> GTP-style move string consumed by LiveBoard. */
export function canonToGtp(row: number, col: number, boardSize: number): string {
  return `${GTP_LETTERS[col]}${boardSize - row}`;
}
