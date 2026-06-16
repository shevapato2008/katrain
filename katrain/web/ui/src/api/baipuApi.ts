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

const API_BASE = '/api/v1/baipu';

export type BaipuStepKind = 'setup' | 'move' | 'pass';

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

export function cacheSgf(id: string, name: string, sgf: string): void {
  const entry: BaipuCachedSgf = { id, name, sgf, savedAt: Date.now() };
  try {
    localStorage.setItem(SGF_KEY(id), JSON.stringify(entry));
    const recent = (safeParse<BaipuRecentEntry[]>(localStorage.getItem(RECENT_KEY)) ?? []).filter((e) => e.id !== id);
    recent.unshift({ id, name, savedAt: entry.savedAt });
    localStorage.setItem(RECENT_KEY, JSON.stringify(recent.slice(0, 30)));
  } catch {
    // localStorage may be full/unavailable; the in-memory navigation state still works.
  }
}

export function getCachedSgf(id: string): BaipuCachedSgf | null {
  return safeParse<BaipuCachedSgf>(localStorage.getItem(SGF_KEY(id)));
}

export function listRecent(): BaipuRecentEntry[] {
  return safeParse<BaipuRecentEntry[]>(localStorage.getItem(RECENT_KEY)) ?? [];
}

export function saveProgress(id: string, progress: BaipuProgress): void {
  try {
    localStorage.setItem(PROGRESS_KEY(id), JSON.stringify(progress));
  } catch {
    // ignore
  }
}

export function getProgress(id: string): BaipuProgress | null {
  return safeParse<BaipuProgress>(localStorage.getItem(PROGRESS_KEY(id)));
}

export function clearProgress(id: string): void {
  try {
    localStorage.removeItem(PROGRESS_KEY(id));
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
