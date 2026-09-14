import { afterEach, describe, it, expect, vi } from 'vitest';
import { BAIPU_MODE_TIMEOUT_MS, BaipuAPI, canonToBoard, canonToGtp } from './baipuApi';

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
      const asked = BaipuAPI.mode();
      await vi.advanceTimersByTimeAsync(BAIPU_MODE_TIMEOUT_MS);
      // 迟到的「拍」不许在摆谱途中把页面切到采集态:mode() 只 settle 一次,这一次已经是「不拍」。
      late(new Response(JSON.stringify({ collect: true }), { status: 200 }));
      await expect(asked).resolves.toEqual({ collect: false });
    } finally {
      vi.useRealTimers();
    }
  });

  it('回包头到了、body 一直不结束:超时同样覆盖读 body 那一段', async () => {
    vi.useFakeTimers();
    try {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: () => new Promise(() => {}) }));
      const asked = BaipuAPI.mode();
      await vi.advanceTimersByTimeAsync(BAIPU_MODE_TIMEOUT_MS);
      await expect(asked).resolves.toEqual({ collect: false });
    } finally {
      vi.useRealTimers();
    }
  });
});
