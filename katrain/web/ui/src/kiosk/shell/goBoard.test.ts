import { describe, expect, test } from 'vitest';
import {
  GO_COLS, GO_MARGIN, STARS_19, boardExtent, colsFor, coordToXY, labelFor, lineAt, rowsFor, starsFor,
} from './goBoard';

describe('围棋坐标 —— 记法是绝对的,四棋类里只有围棋这套', () => {
  test('列名跳 I,A–T 正好 19 个', () => {
    expect(GO_COLS).toBe('ABCDEFGHJKLMNOPQRST');
    expect(GO_COLS.length).toBe(19);
    expect(GO_COLS).not.toContain('I');
  });

  test('行号 1 在最下、19 在最上', () => {
    expect(coordToXY('A1').y).toBe(18);
    expect(coordToXY('A19').y).toBe(0);
  });

  test('九星在第 4 / 10 / 16 条线上(0 起算 3 / 9 / 15)', () => {
    expect(STARS_19).toEqual([
      [3, 3], [3, 9], [3, 15], [9, 3], [9, 9], [9, 15], [15, 3], [15, 9], [15, 15],
    ]);
  });

  test('Q16 是右上星位那一带 —— 拿一个真坐标钉住方向', () => {
    expect(coordToXY('Q16')).toEqual({ x: 15, y: 3 });
  });

  test('刻度四条带都写字,上下 A–T、左右 19–1', () => {
    expect(labelFor('top', 0)).toBe('A');
    expect(labelFor('top', 18)).toBe('T');
    expect(labelFor('left', 0)).toBe('19');
    expect(labelFor('left', 18)).toBe('1');
  });
});

describe('小盘不是大盘缩放 —— 星位换位置,跳 I 照旧', () => {
  test('9 路的星在 3-3(0 起算 2),中央天元 4-4', () => {
    expect(starsFor(9)).toEqual([[2, 2], [2, 6], [6, 2], [6, 6], [4, 4]]);
  });

  test('9 路的列名还是跳 I —— 取前 9 个,H 之后直接 J', () => {
    expect(colsFor(9).join('')).toBe('ABCDEFGHJ');
  });

  test('没这个路数就是空数组,不拿 19 路的星顶上', () => {
    expect(starsFor(17)).toEqual([]);
  });

  test('行号从上往下读是 size…1', () => {
    expect(rowsFor(9)).toEqual([9, 8, 7, 6, 5, 4, 3, 2, 1]);
  });
});

describe('留白 0.5 格 —— 字心与线逐条对齐的充要条件', () => {
  test('第 i 条线在 (0.5+i)/(N-1+1) 上,与刻度第 i 格的中心 (i+0.5)/N 重合', () => {
    const size = 19;
    const extent = boardExtent(size);        // (18 + 1) × 100 = 1900
    expect(extent).toBe(1900);
    for (let i = 0; i < size; i += 1) {
      // 线的归一化位置
      const line = lineAt(i) / extent;
      // 刻度带把 19 格均分在同一条边上,第 i 格的中心
      const label = (i + 0.5) / size;
      expect(line).toBeCloseTo(label, 12);
    }
  });

  test('留白换成 1.5 这个等式就不成立 —— 这个数不是随手取的', () => {
    const wrong = 1.5;
    const size = 19;
    const extent = (size - 1 + 2 * wrong) * 100;
    const line = (wrong + 0) * 100 / extent;
    expect(line).not.toBeCloseTo(0.5 / size, 3);
    expect(GO_MARGIN).toBe(0.5);
  });
});
