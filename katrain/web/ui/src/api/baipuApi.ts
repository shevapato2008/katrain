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
// that read synchronously at first paint (e.g. BaipuListPage's `useState(() => listRecent())`
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
export type BaipuCaptureOutcome =
  | { kind: 'ok'; result: BaipuCaptureResult }
  | { kind: 'disabled' } // 404: capture/geometry not available
  | { kind: 'error'; message: string };

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
      return { kind: 'error', message: e instanceof Error ? e.message : 'network error' };
    }
    if (response.status === 404) return { kind: 'disabled' };
    if (response.ok) return { kind: 'ok', result: await response.json() };
    if (response.status === 409) {
      const body = await response.json().catch(() => ({}));
      const detail = body?.detail;
      const message = typeof detail === 'string' ? detail : detail?.message;
      return { kind: 'error', message: message ?? 'capture conflict' };
    }
    return { kind: 'error', message: `capture failed ${response.status}` };
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
// BaipuListPage's `listRecent()` initializer) should pass an explicit store instead of
// relying on the default — see BaipuListPage.tsx / BaipuSessionPage.tsx.

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
