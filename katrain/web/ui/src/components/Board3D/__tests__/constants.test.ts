import { describe, it, expect } from 'vitest';
import {
  gridToWorld,
  worldToGrid,
  getBoardDimensions,
  getEvalColor,
  EVAL_COLORS,
  BOARD_SURFACE_Y,
} from '../constants';

describe('getBoardDimensions', () => {
  it('calculates correct dimensions for 19x19', () => {
    const dims = getBoardDimensions(19);
    expect(dims.boardSize).toBe(19);
    expect(dims.gridSpacing).toBe(1.0);
    expect(dims.boardExtent).toBe(18.0);
    expect(dims.boardWidth).toBeCloseTo(19.6);
  });

  it('calculates correct dimensions for 9x9', () => {
    const dims = getBoardDimensions(9);
    expect(dims.boardSize).toBe(9);
    expect(dims.boardExtent).toBe(8.0);
  });

  it('calculates correct dimensions for 13x13', () => {
    const dims = getBoardDimensions(13);
    expect(dims.boardSize).toBe(13);
    expect(dims.boardExtent).toBe(12.0);
  });
});

describe('gridToWorld', () => {
  it('converts grid (0,0) to correct world position for 19x19', () => {
    const pos = gridToWorld(0, 0, 19);
    // col=0 → x = -9, row=0 → z = +9 (near camera, Z inverted)
    expect(pos[0]).toBeCloseTo(-9);
    expect(pos[2]).toBeCloseTo(9);
    expect(pos[1]).toBeCloseTo(1.20 + 0.22);
  });

  it('converts grid center to origin for 19x19', () => {
    const pos = gridToWorld(9, 9, 19);
    expect(pos[0]).toBeCloseTo(0);
    expect(pos[2]).toBeCloseTo(0);
  });

  it('converts grid (18,18) to far corner for 19x19', () => {
    const pos = gridToWorld(18, 18, 19);
    // col=18 → x = +9, row=18 → z = -9 (far from camera)
    expect(pos[0]).toBeCloseTo(9);
    expect(pos[2]).toBeCloseTo(-9);
  });

  it('works for 9x9 board', () => {
    const pos = gridToWorld(4, 4, 9);
    expect(pos[0]).toBeCloseTo(0);
    expect(pos[2]).toBeCloseTo(0);
  });
});

describe('worldToGrid', () => {
  it('round-trips with gridToWorld for 19x19', () => {
    // gridToWorld(col, row) -> worldToGrid returns { col, row }
    for (const [col, row] of [[0, 0], [3, 3], [9, 9], [15, 15], [18, 18]]) {
      const world = gridToWorld(col, row, 19);
      const grid = worldToGrid(world[0], world[2], 19);
      expect(grid).toEqual({ col, row });
    }
  });

  it('returns null for out-of-bounds positions', () => {
    expect(worldToGrid(-20, -20, 19)).toBeNull();
    expect(worldToGrid(20, 20, 19)).toBeNull();
  });
});

describe('getEvalColor', () => {
  it('returns purple (index 0) for blunders (>12)', () => {
    expect(getEvalColor(15)).toBe(EVAL_COLORS[0]);
  });

  it('returns jade green (index 5) for excellent (<=0.5)', () => {
    expect(getEvalColor(0.2)).toBe(EVAL_COLORS[5]);
  });

  it('returns yellow (index 3) for inaccuracy (>1.5)', () => {
    expect(getEvalColor(2.0)).toBe(EVAL_COLORS[3]);
  });
});

// Suppress unused import warning — BOARD_SURFACE_Y is used in gridToWorld test assertions
void BOARD_SURFACE_Y;
