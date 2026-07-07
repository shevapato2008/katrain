import { afterEach, describe, it, expect, vi } from 'vitest';
import { BaipuAPI, canonToBoard, canonToGtp } from './baipuApi';

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
