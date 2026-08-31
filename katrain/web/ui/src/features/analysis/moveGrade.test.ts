import { describe, expect, it } from 'vitest';

import type { MoveAnalysis } from '../../types/live';
import {
  badnessRank,
  brillianceRank,
  buildHistogram,
  buildMatchRate,
  GRADE_TIERS,
  PER_SIDE_LIMIT,
  phaseOf,
  selectPerSide,
  type GradeId,
} from './moveGrade';

const move = (n: number, player: 'B' | 'W', grade: GradeId, extra: Partial<MoveAnalysis> = {}): MoveAnalysis => ({
  match_id: 'g',
  move_number: n,
  move: 'Q16',
  player,
  winrate: 0.5,
  score_lead: 0,
  top_moves: [],
  ownership: null,
  is_brilliant: false,
  is_mistake: false,
  is_questionable: false,
  delta_score: 0,
  delta_winrate: 0,
  grade,
  points_lost: 0,
  ...extra,
});

describe('phase boundaries', () => {
  it.each([
    [0, 'opening'],
    [59, 'opening'],
    [60, 'midgame'],
    [149, 'midgame'],
    [150, 'endgame'],
    [400, 'endgame'],
  ])('move %i is %s', (n, expected) => {
    expect(phaseOf(n)).toBe(expected);
  });
});

describe('per-side selection', () => {
  // 12 手黑棋失误 + 2 手白棋失误。整体取前 5 会把白棋两条全挤掉。
  const items = [
    ...Array.from({ length: 12 }, (_, i) =>
      move(i * 2 + 1, 'B', 'mistake', { points_lost: 10 - i * 0.1 }),
    ),
    move(40, 'W', 'mistake', { points_lost: 3 }),
    move(42, 'W', 'blunder', { points_lost: 9 }),
  ];

  it('keeps both sides visible instead of letting one side crowd the other out', () => {
    const sel = selectPerSide(items, badnessRank);
    expect(sel.shown.filter((m) => m.player === 'W')).toHaveLength(2);
    expect(sel.shown.filter((m) => m.player === 'B')).toHaveLength(PER_SIDE_LIMIT);
  });

  it('reports the pre-truncation total so the tab count can stay honest', () => {
    const sel = selectPerSide(items, badnessRank);
    expect(sel.total).toBe(14);
    expect(sel.shown).toHaveLength(PER_SIDE_LIMIT + 2);
    expect(sel.truncated).toBe(14 - (PER_SIDE_LIMIT + 2));
  });

  it('keeps the worst moves, not the earliest', () => {
    const sel = selectPerSide(items, badnessRank);
    const worst = Math.max(...sel.shown.filter((m) => m.player === 'B').map((m) => m.points_lost!));
    expect(worst).toBeCloseTo(10);
  });

  it('sorts the shown list back into move order', () => {
    const sel = selectPerSide(items, badnessRank);
    const numbers = sel.shown.map((m) => m.move_number);
    expect(numbers).toEqual([...numbers].sort((a, b) => a - b));
  });

  it('gives each phase its own fresh budget', () => {
    const spread = [
      ...Array.from({ length: 8 }, (_, i) => move(i + 1, 'B', 'mistake', { points_lost: 5 })),
      ...Array.from({ length: 8 }, (_, i) => move(70 + i, 'B', 'mistake', { points_lost: 5 })),
    ];
    expect(selectPerSide(spread, badnessRank).shown).toHaveLength(PER_SIDE_LIMIT);
    expect(selectPerSide(spread, badnessRank, { phase: 'opening' }).shown).toHaveLength(PER_SIDE_LIMIT);
    expect(selectPerSide(spread, badnessRank, { phase: 'midgame' }).shown).toHaveLength(PER_SIDE_LIMIT);
  });

  it('does not raise the total budget when one player is selected', () => {
    // 星阵在选单方时把上限翻倍，但另一方被清空，屏幕上总数不变。
    // 我们不翻倍：单方筛选就是单方的 5 条。
    const sel = selectPerSide(items, badnessRank, { player: 'B' });
    expect(sel.shown).toHaveLength(PER_SIDE_LIMIT);
    expect(sel.shown.every((m) => m.player === 'B')).toBe(true);
  });

  it('ranks brilliants by 妙度 first', () => {
    const brilliants = [
      move(3, 'B', 'brilliant', { brilliance: 1, top_prior: 0.09 }),
      move(5, 'B', 'brilliant', { brilliance: 5, top_prior: 0.005 }),
      move(7, 'B', 'brilliant', { brilliance: 3, top_prior: 0.02 }),
    ];
    const ranked = [...brilliants].sort((a, b) => brillianceRank(b) - brillianceRank(a));
    expect(ranked.map((m) => m.brilliance)).toEqual([5, 3, 1]);
  });
});

describe('performance histogram', () => {
  const moves = [
    move(1, 'B', 'best'),
    move(2, 'W', 'mistake', { points_lost: 4 }),
    move(3, 'B', 'best'),
    move(4, 'W', 'best'),
    move(5, 'B', 'blunder', { points_lost: 12 }),
    move(200, 'W', 'inaccuracy', { points_lost: 2 }),
  ];

  it('normalises each colour against its own rated move count', () => {
    const h = buildHistogram(moves);
    expect(h.blackTotal).toBe(3);
    expect(h.whiteTotal).toBe(3);
    const best = h.cells.find((c) => c.tier.id === 'best')!;
    expect(best.black).toBe(2);
    expect(best.blackRate).toBeCloseTo(2 / 3);
    expect(best.white).toBe(1);
    expect(best.whiteRate).toBeCloseTo(1 / 3);
  });

  it('counts unrated moves separately instead of shrinking the denominator silently', () => {
    const h = buildHistogram([...moves, move(9, 'B', 'unrated')]);
    expect(h.unrated).toBe(1);
    expect(h.blackTotal).toBe(3); // 未评级的手不进分母
  });

  it('restricts to the selected phase', () => {
    const h = buildHistogram(moves, 'endgame');
    expect(h.blackTotal).toBe(0);
    expect(h.whiteTotal).toBe(1);
  });

  it('always emits all seven tiers so the chart shape is stable', () => {
    const h = buildHistogram(moves);
    expect(h.cells.map((c) => c.tier.id)).toEqual(GRADE_TIERS.map((t) => t.id));
    expect(h.cells).toHaveLength(7);
  });
});

describe('AI match rate', () => {
  const cand = (...names: string[]) =>
    names.map((move) => ({ move, visits: 100, winrate: 0.5, score_lead: 0, prior: 0.1, pv: [], psv: 100 }));

  it('prefers the server-side is_top_move flag when it is present', () => {
    const h = buildMatchRate([
      move(1, 'B', 'best', { is_top_move: true }),
      move(2, 'W', 'inaccuracy', { is_top_move: false }),
      move(3, 'B', 'best', { is_top_move: true }),
    ]);
    const top1 = h.rows.find((r) => r.id === 'top1')!;
    expect(top1.black).toBe(2);
    expect(top1.blackTotal).toBe(2);
    expect(top1.blackRate).toBeCloseTo(1);
    expect(top1.white).toBe(0);
    expect(top1.whiteTotal).toBe(1);
  });

  it('falls back to the previous row candidates so the live page is not blank', () => {
    // 直播链路的 MoveAnalysis 根本没有 is_top_move；只有 top_moves。
    const h = buildMatchRate([
      move(0, 'B', 'unrated', { move: null, player: null, top_moves: cand('D4', 'Q16', 'K10') }),
      move(1, 'B', 'best', { move: 'D4', top_moves: cand('R4', 'C3', 'E17') }),
      move(2, 'W', 'best', { move: 'E17' }),
    ]);
    const top1 = h.rows.find((r) => r.id === 'top1')!;
    const top3 = h.rows.find((r) => r.id === 'top3')!;
    const off = h.rows.find((r) => r.id === 'offbook')!;
    expect(top1.black).toBe(1); // D4 是上一手候选表的第 0 位
    expect(top1.white).toBe(0); // E17 是第 2 位，不是一选
    expect(top3.white).toBe(1); // 但在前三里
    expect(off.white).toBe(0);
  });

  it('gives each row its own denominator instead of borrowing top1 的', () => {
    // 有 is_top_move、但上一手没有候选表 ⇒ 一选判得了，前三判不了。
    const h = buildMatchRate([move(1, 'B', 'best', { is_top_move: true })]);
    expect(h.rows.find((r) => r.id === 'top1')!.blackTotal).toBe(1);
    expect(h.rows.find((r) => r.id === 'top3')!.blackTotal).toBe(0);
    expect(h.rows.find((r) => r.id === 'offbook')!.blackTotal).toBe(0);
  });

  it('counts moves it cannot compare instead of silently shrinking the denominator', () => {
    const h = buildMatchRate([
      move(1, 'B', 'best', { is_top_move: true }),
      move(2, 'W', 'unrated'), // 既没有 flag 也没有上一手候选表
    ]);
    expect(h.undecidable).toBe(1);
    expect(h.blackDecided).toBe(1);
    expect(h.whiteDecided).toBe(0);
  });

  it('marks a move that is not in the candidate list at all', () => {
    const h = buildMatchRate([
      move(0, 'B', 'unrated', { move: null, player: null, top_moves: cand('D4', 'Q16') }),
      move(1, 'B', 'blunder', { move: 'A1' }),
    ]);
    expect(h.rows.find((r) => r.id === 'offbook')!.black).toBe(1);
    expect(h.rows.find((r) => r.id === 'top3')!.black).toBe(0);
  });

  it('restricts to the selected phase', () => {
    const h = buildMatchRate(
      [move(1, 'B', 'best', { is_top_move: true }), move(151, 'B', 'best', { is_top_move: true })],
      'endgame',
    );
    expect(h.rows.find((r) => r.id === 'top1')!.blackTotal).toBe(1);
  });
});
