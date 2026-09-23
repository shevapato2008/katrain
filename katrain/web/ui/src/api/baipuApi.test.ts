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

    // 这一支**必须是 `other`**:把它归成「几何」会让屏上叫人去重新标定棋盘 ——
    // 一件跟 qa mismatch 毫无关系的事。(第一版就是这么写的,被这条用例当场逮住。)
    expect(outcome).toEqual({ kind: 'error', message: 'capture conflict', reason: 'other' });
  });

  /**
   * 409 的两种**可分辨**形状,对站在盘前的人意味着完全不同的事:
   *  · 几何没锁 → 再按一次永远是同一个 409,人得去重新标定;
   *  · 灯不可用 → 再按一次有可能成。
   * 混成一句「再按一次」会让几何坏掉的人一直按下去。
   * 判别位是 `detail` 的**形状**不是关键词 —— 字符串内容是会被改的文案。
   */
  it('几何没锁那一种认得出来(detail 是纯字符串)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: 'Geometry not locked; run /geometry/lock first',
    }), { status: 409, headers: { 'Content-Type': 'application/json' } })));

    const outcome = await BaipuAPI.capture({ game_id: 'k', move_index: 0, sgf: '(;B[pd])' });
    expect(outcome).toEqual({
      kind: 'error',
      message: 'Geometry not locked; run /geometry/lock first',
      reason: 'geometry',
    });
  });

  it('灯不可用那一种认得出来(detail 是 {error:led_unavailable})', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: { error: 'led_unavailable', message: 'LED bus down' },
    }), { status: 409, headers: { 'Content-Type': 'application/json' } })));

    const outcome = await BaipuAPI.capture({ game_id: 'k', move_index: 0, sgf: '(;B[pd])' });
    expect(outcome).toEqual({ kind: 'error', message: 'LED bus down', reason: 'led' });
  });
});

describe('摆谱拍不拍照:BaipuAPI.mode()', () => {
  it('后端明说 collect:true 才是采集态', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ collect: true }), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    })));
    expect(await BaipuAPI.mode()).toEqual({ collect: true });
  });

  // 猜成「拍」的代价:盒上每一手都可能被几何 / 灯的 409 卡住;猜成「不拍」的代价:
  // 采数据的人一眼看见屏上没有「已采集 N 帧」。所以问不到一律当「不拍」。
  it('问不到一律当不拍:旧后端 404 / 网络错 / 不认识的回包', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"detail":"Not Found"}', { status: 404 })));
    expect(await BaipuAPI.mode()).toEqual({ collect: false });
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    expect(await BaipuAPI.mode()).toEqual({ collect: false });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ collect: 'yes' }), { status: 200 })));
    expect(await BaipuAPI.mode()).toEqual({ collect: false });
  });

  // 后端卡住(事件循环被别的同步调用堵着)时 fetch 既不 reject 也不 resolve —— 光有 catch 兜不住,
  // 摆谱入口会一直停在「正在读这份谱」,缓存谱和导入的 SGF 都进不去。
  it('问了不回:到点当不拍;超时之后才回来的 collect:true 也不改判', async () => {
    vi.useFakeTimers();
    try {
      let late!: (r: Response) => void;
      vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((resolve) => { late = resolve; })));
      const settled = vi.fn();
      const asked = BaipuAPI.mode().then(settled);
      // 独立锁定 PRD 的 3 秒,不能跟着实现的超时常量一起变成 30 秒还全绿。
      await vi.advanceTimersByTimeAsync(2999);
      expect(settled).not.toHaveBeenCalled();
      await vi.advanceTimersByTimeAsync(1);
      expect(settled).toHaveBeenCalledExactlyOnceWith({ collect: false });
      // 迟到的「拍」不许在摆谱途中把页面切到采集态:mode() 只 settle 一次,这一次已经是「不拍」。
      late(new Response(JSON.stringify({ collect: true }), { status: 200 }));
      await asked;
      expect(settled).toHaveBeenCalledExactlyOnceWith({ collect: false });
    } finally {
      vi.useRealTimers();
    }
  });

  it('回包头到了、body 一直不结束:超时同样覆盖读 body 那一段', async () => {
    vi.useFakeTimers();
    try {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: () => new Promise(() => {}) }));
      const asked = BaipuAPI.mode();
      await vi.advanceTimersByTimeAsync(3000);
      await expect(asked).resolves.toEqual({ collect: false });
    } finally {
      vi.useRealTimers();
    }
  });

  it('超时触发真实 signal 的 abort 后 fetch 才 reject，也只返回一次不拍照', async () => {
    vi.useFakeTimers();
    try {
      let rejected = false;
      const aborted = vi.fn();
      vi.stubGlobal('fetch', vi.fn((_url: string, { signal }: RequestInit) => new Promise<Response>((_resolve, reject) => {
        signal!.addEventListener('abort', () => {
          aborted();
          setTimeout(() => { rejected = true; reject(new DOMException('Aborted', 'AbortError')); }, 1);
        }, { once: true });
      })));
      const settled = vi.fn();
      const asked = BaipuAPI.mode().then(settled);
      await vi.advanceTimersByTimeAsync(3000);
      expect(aborted).toHaveBeenCalledOnce();
      expect(rejected).toBe(false);
      expect(settled).toHaveBeenCalledExactlyOnceWith({ collect: false });
      await vi.advanceTimersByTimeAsync(1);
      await asked;
      expect(rejected).toBe(true);
      expect(settled).toHaveBeenCalledExactlyOnceWith({ collect: false });
    } finally {
      vi.useRealTimers();
    }
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
