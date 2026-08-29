import { describe, expect, test } from 'vitest';
import {
  GO_COLS, GO_MARGIN, STARS_19, boardExtent, colsFor, coordToXY, labelFor, lineAt, rowsFor, starsFor,
  windowViewBox, xyToCoord,
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

/**
 * 2026-08-24(屏 25 课程 · 小节讲解)加的两样。教程图用的是 `[col,row]` 数对,
 * 而这块盘从第一天起收的就是 `"Q16"` —— 换算只许有这一份,
 * 因为跳 I 和「行号 1 在最下」正是最容易各抄错一半的两条。
 */
describe('教程图:数对 ←→ 坐标串,以及「只看一角」的 viewBox', () => {
  test('xyToCoord 是 coordToXY 的反函数 —— 19 路上逐点对上', () => {
    for (let x = 0; x < 19; x += 1) {
      for (let y = 0; y < 19; y += 1) {
        expect(coordToXY(xyToCoord(x, y))).toEqual({ x, y });
      }
    }
  });

  test('9 路上也成立 —— 行号是按 size 数的,不是恒 19', () => {
    expect(xyToCoord(0, 8, 9)).toBe('A1');
    expect(xyToCoord(8, 0, 9)).toBe('J9');       // 跳 I:第 9 列是 J
    expect(coordToXY('J9', 9)).toEqual({ x: 8, y: 0 });
  });

  test('全盘窗口 = boardExtent —— 窗口是它的推广,不是另一套', () => {
    expect(windowViewBox({ col: 0, row: 0, cols: 19, rows: 19 }))
      .toBe(`0 0 ${boardExtent(19)} ${boardExtent(19)}`);
  });

  /**
   * 窗口两边各留半格 —— **和 `lineAt` 是同一条式子**。右下角那个 10×10 方窗:
   * 第 9 条线在 (0.5+9)·100 = 950,窗口左边界 900 ⇒ 线离边 50 = 半格。✓
   */
  test('右下角 10×10 方窗:左上角落在 900,边长 1000', () => {
    expect(windowViewBox({ col: 9, row: 9, cols: 10, rows: 10 })).toBe('900 900 1000 1000');
    expect(lineAt(9)).toBe(950);
    expect(lineAt(18)).toBe(1850);               // 最后一条线离右边界 1900 也是半格
  });

  /** 后端 `viewport.py` 唯一的非方形状:上下半盘 19×10、左右半盘 10×19。 */
  test('上半盘 19×10 和右半盘 10×19', () => {
    expect(windowViewBox({ col: 0, row: 0, cols: 19, rows: 10 })).toBe('0 0 1900 1000');
    expect(windowViewBox({ col: 9, row: 0, cols: 10, rows: 19 })).toBe('900 0 1000 1900');
  });
});
