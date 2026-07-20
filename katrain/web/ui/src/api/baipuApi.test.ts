import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest';
import {
  BaipuAPI, canonToBoard, canonToGtp,
  cacheSgf, getCachedSgf, listRecent, saveProgress, getProgress, clearProgress,
} from './baipuApi';
import {
  kioskActivityStorage,
  setKioskIdentity,
  getCurrentKioskActivityStorage,
  __resetKioskActivityStorageForTests,
} from '../kiosk/storage/kioskActivityStorage';

afterEach(() => {
  vi.unstubAllGlobals();
});

// Mirror of LiveBoard.parseMove (the consumer): GTP string -> [x, y] with y=0 BOTTOM.
function parseGtp(move: string): { x: number; y: number } {
  const col = move[0].toUpperCase();
  const row = parseInt(move.slice(1), 10);
  let x = col.charCodeAt(0) - 'A'.charCodeAt(0);
  if (col > 'I') x -= 1;
  return { x, y: row - 1 };
}

describe('baipu coordinate conversion (canonical row=0 top <-> LiveBoard y=0 bottom)', () => {
  it('maps the four corners on 19x19', () => {
    expect(canonToBoard(0, 0, 19)).toEqual({ x: 0, y: 18 }); // top-left
    expect(canonToBoard(0, 18, 19)).toEqual({ x: 18, y: 18 }); // top-right
    expect(canonToBoard(18, 0, 19)).toEqual({ x: 0, y: 0 }); // bottom-left
    expect(canonToBoard(18, 18, 19)).toEqual({ x: 18, y: 0 }); // bottom-right
  });

  it('maps known points to GTP', () => {
    expect(canonToGtp(3, 15, 19)).toBe('Q16'); // upper-right 4-4
    expect(canonToGtp(15, 3, 19)).toBe('D4'); // lower-left 4-4
    expect(canonToGtp(0, 0, 19)).toBe('A19'); // top-left corner
    expect(canonToGtp(18, 18, 19)).toBe('T1'); // bottom-right corner
  });

  it('round-trips canonToGtp -> parseGtp == canonToBoard (no vertical inversion)', () => {
    const boards = [9, 13, 19];
    for (const bs of boards) {
      for (let row = 0; row < bs; row++) {
        for (let col = 0; col < bs; col++) {
          const gtp = canonToGtp(row, col, bs);
          expect(parseGtp(gtp)).toEqual(canonToBoard(row, col, bs));
        }
      }
    }
  });

  it('handles small boards', () => {
    expect(canonToBoard(2, 2, 9)).toEqual({ x: 2, y: 6 });
    expect(canonToGtp(0, 0, 13)).toBe('A13');
  });
});

describe('operator-trusted capture API', () => {
  it('treats a legacy placement mismatch as a regular capture error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: {
        qa: 'mismatch',
        move_index: 0,
        diffs: [{ row: 3, col: 15, expected: 'B', actual: 'empty', reason: 'missing' }],
      },
    }), { status: 409, headers: { 'Content-Type': 'application/json' } })));

    const outcome = await BaipuAPI.capture({ game_id: 'kifu_24171', move_index: 0, sgf: '(;B[pd])' });

    expect(outcome).toEqual({ kind: 'error', message: 'capture conflict' });
  });
});

// ============ Box-SSO guest mode: local cache isolation (4th zero-persistence layer) ============

const ALICE = 'alice-uuid';
const BOB = 'bob-uuid';

beforeEach(() => {
  localStorage.clear();
  __resetKioskActivityStorageForTests();
});

describe('cacheSgf / getCachedSgf / listRecent — identity-scoped via an explicit store', () => {
  it('a real user (Alice) namespaces baipu:sgf and baipu:recent under her uuid', () => {
    const alice = kioskActivityStorage(ALICE, false);
    cacheSgf('kifu_1', 'Alice vs Bob', '(;B[pd])', alice);

    expect(localStorage.getItem('baipu:sgf:kifu_1')).toBeNull();
    expect(localStorage.getItem('baipu:sgf:kifu_1:alice-uuid')).not.toBeNull();
    expect(localStorage.getItem('baipu:recent:alice-uuid')).not.toBeNull();
    expect(localStorage.getItem('baipu:recent')).toBeNull();

    expect(getCachedSgf('kifu_1', alice)?.sgf).toBe('(;B[pd])');
    expect(listRecent(alice)).toHaveLength(1);
  });

  it('a different uuid (Bob) reads empty even though Alice has cached SGFs', () => {
    const alice = kioskActivityStorage(ALICE, false);
    cacheSgf('kifu_1', 'Alice vs Bob', '(;B[pd])', alice);

    const bob = kioskActivityStorage(BOB, false);
    expect(getCachedSgf('kifu_1', bob)).toBeNull();
    expect(listRecent(bob)).toEqual([]);
  });

  it('a guest never touches localStorage: cacheSgf lands only in the in-memory store', () => {
    const guest = kioskActivityStorage(null, true);
    cacheSgf('kifu_1', 'Guest game', '(;B[pd])', guest);

    expect(getCachedSgf('kifu_1', guest)?.sgf).toBe('(;B[pd])');
    expect(listRecent(guest)).toHaveLength(1);
    // Nothing under any baipu:* key reached real localStorage.
    for (let i = 0; i < localStorage.length; i++) {
      expect(localStorage.key(i)!.startsWith('baipu:')).toBe(false);
    }
  });

  it('a guest does not read a prior real user cached SGF (same logical id)', () => {
    const alice = kioskActivityStorage(ALICE, false);
    cacheSgf('kifu_1', 'Alice vs Bob', '(;B[pd])', alice);

    const guest = kioskActivityStorage(null, true);
    expect(getCachedSgf('kifu_1', guest)).toBeNull();
    expect(listRecent(guest)).toEqual([]);
  });
});

describe('saveProgress / getProgress / clearProgress — identity-scoped via an explicit store', () => {
  it('namespaces baipu:progress under the real user uuid, and clearProgress only clears that namespace', () => {
    const alice = kioskActivityStorage(ALICE, false);
    saveProgress('kifu_1', { k: 5, frames: 2, updatedAt: 123 }, alice);

    expect(localStorage.getItem('baipu:progress:kifu_1')).toBeNull();
    expect(localStorage.getItem('baipu:progress:kifu_1:alice-uuid')).not.toBeNull();
    expect(getProgress('kifu_1', alice)).toEqual({ k: 5, frames: 2, updatedAt: 123 });

    clearProgress('kifu_1', alice);
    expect(getProgress('kifu_1', alice)).toBeNull();
  });

  it('a guest never persists progress to localStorage', () => {
    const guest = kioskActivityStorage(null, true);
    saveProgress('kifu_1', { k: 5, frames: 0, updatedAt: 1 }, guest);
    expect(getProgress('kifu_1', guest)).toEqual({ k: 5, frames: 0, updatedAt: 1 });
    expect(localStorage.getItem('baipu:progress:kifu_1')).toBeNull();
  });
});

describe('default store parameter — resolved-identity singleton', () => {
  it('defaults to the safe ephemeral store before any identity is resolved', () => {
    localStorage.setItem('baipu:recent', JSON.stringify([{ id: 'x', name: 'x', savedAt: 1 }]));
    expect(listRecent()).toEqual([]);
  });

  it('once AuthContext resolves a real identity via setKioskIdentity, the default param picks it up', () => {
    setKioskIdentity(ALICE, false);
    cacheSgf('kifu_9', 'Resolved Alice', '(;B[pd])');
    expect(localStorage.getItem('baipu:sgf:kifu_9:alice-uuid')).not.toBeNull();
    expect(getCachedSgf('kifu_9')?.sgf).toBe('(;B[pd])');
    expect(getCurrentKioskActivityStorage()).not.toBeNull();
  });
});
