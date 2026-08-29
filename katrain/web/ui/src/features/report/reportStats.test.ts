import { describe, expect, it } from 'vitest';

import type { ReportTaskMove } from '../../api/reportApi';
import type { TopMove } from '../../types/live';
import {
  BRILLIANT_SCORE_GAIN,
  keyMoves,
  MISTAKE_SCORE_LOSS,
  summarizeReportMoves,
  winrateSeries,
} from './reportStats';

/**
 * 准确率那条**期望值是手算的**,不是把实现跑一遍抄下来的 —— 抄下来的期望值
 * 只能证明「代码没变」,证不了「代码算对了」。算式见 `reportStats.ts` 的注释,
 * 正本在 `katrain/core/ai.py:212-262`。
 */

const move = (over: Partial<ReportTaskMove>): ReportTaskMove => ({
  id: over.move_number ?? 0, task_id: 1, move_number: 0, status: 'success',
  winrate: null, score_lead: null, visits: 500, top_moves: null, ownership: null,
  actual_move: null, actual_player: null, delta_score: null, delta_winrate: null,
  ...over,
});

const cands = (list: { score_lead: number; prior: number }[]) =>
  list.map((c, i) => ({
    move: `M${i}`, visits: 100, winrate: 0.5, prior: c.prior, pv: [],
    score_lead: c.score_lead,
  })) as unknown as TopMove[];

// 一局三手。第 0 行是空盘(没有 actual_player,不该被算进任何一边)。
//   1 手 黑:目差 0 → -1     丢 1.0 分,而 0 行的候选说明这手不好走(复杂度 0.6)
//   2 手 白:目差 -1 → +1    白丢 2.0 分,没到失误线(-3)
//   3 手 黑:目差 1 → +4     黑赚 3.0 分 → 妙手
const GAME: ReportTaskMove[] = [
  move({ move_number: 0, winrate: 0.5, score_lead: 0, top_moves: cands([
    { score_lead: 0.5, prior: 0.6 },    // 黑视角丢 -0.5 → 记 0
    { score_lead: -1.5, prior: 0.4 },   // 黑视角丢 1.5
  ]) }),
  move({ move_number: 1, winrate: 0.46, score_lead: -1, actual_move: 'Q16', actual_player: 'B', delta_score: -1 }),
  move({ move_number: 2, winrate: 0.55, score_lead: 1, actual_move: 'D4', actual_player: 'W', delta_score: -2 }),
  move({ move_number: 3, winrate: 0.72, score_lead: 4, actual_move: 'C3', actual_player: 'B', delta_score: 3 }),
];

describe('summarizeReportMoves —— 三格指标', () => {
  it('黑方:准确率按加权丢分算,妙手那一手数进来了', () => {
    const s = summarizeReportMoves(GAME, 'B');
    expect(s.counted).toBe(2);
    expect(s.brilliants).toBe(1);
    expect(s.mistakes).toBe(0);
    // 复杂度 = (0×0.6 + 1.5×0.4) / 1.0 = 0.6;权重 = max(.05, min(1, max(.6, 1/4))) = 0.6
    // 第 3 手赚分 ⇒ 丢分记 0、复杂度无候选记 0 ⇒ 权重取下界 0.05
    // 加权丢分 = (1.0×0.6 + 0×0.05) / 0.65 = 0.923077 ⇒ 100 × 0.75^0.923077
    expect(s.accuracy).toBeCloseTo(76.678, 3);
  });

  it('白方:只算白走的那一手,和黑方互不影响', () => {
    const s = summarizeReportMoves(GAME, 'W');
    expect(s.counted).toBe(1);
    expect(s.brilliants).toBe(0);
    expect(s.mistakes).toBe(0);
    // 丢 2.0 分、上一行没候选 ⇒ 复杂度 0、权重 = max(.05, min(1, 0.5)) = 0.5
    // 加权丢分 = 2.0 ⇒ 100 × 0.75² = 56.25
    expect(s.accuracy).toBeCloseTo(56.25, 6);
  });

  // **准确率的 null 和 0 是两件事**:一个说「没算过」,一个说「算过了,一塌糊涂」。
  // 屏上那格拿它分「未分析」和「0%」—— 混了就是把没算过伪装成算过了。
  it('一手都没有的时候准确率是 null,不是 0', () => {
    expect(summarizeReportMoves([], 'B')).toEqual({ accuracy: null, mistakes: 0, brilliants: 0, counted: 0 });
    // 报告只跑了空盘那一行 —— 有数据,但没有任何一手可评
    expect(summarizeReportMoves([GAME[0]], 'B').accuracy).toBeNull();
  });

  it('算失败的行(delta_score 缺席)不参与,也不把它当成 0 分丢', () => {
    const withHole = [...GAME, move({ move_number: 4, status: 'failed', actual_player: 'W' })];
    expect(summarizeReportMoves(withHole, 'W').counted).toBe(1);
  });

  it('阈值就是仓里已有的那两个数 —— 换了就和报告详情对不上', () => {
    expect(BRILLIANT_SCORE_GAIN).toBe(2);
    expect(MISTAKE_SCORE_LOSS).toBe(-3);
    const edge = [
      move({ move_number: 0, score_lead: 0, winrate: 0.5 }),
      move({ move_number: 1, actual_player: 'B', delta_score: 2, score_lead: 2, winrate: 0.6 }),
      move({ move_number: 2, actual_player: 'B', delta_score: -3, score_lead: -1, winrate: 0.4 }),
      move({ move_number: 3, actual_player: 'B', delta_score: 1.99, score_lead: 1, winrate: 0.5 }),
      move({ move_number: 4, actual_player: 'B', delta_score: -2.99, score_lead: -2, winrate: 0.4 }),
    ];
    const s = summarizeReportMoves(edge, 'B');
    expect(s.brilliants).toBe(1);   // 正好 2 算,1.99 不算
    expect(s.mistakes).toBe(1);     // 正好 -3 算,-2.99 不算
  });

  it('先验缺席时复杂度退回 0,不整条崩掉', () => {
    const noPrior = [
      move({ move_number: 0, score_lead: 0, winrate: 0.5, top_moves: [{ move: 'A', score_lead: 2 }] as unknown as TopMove[] }),
      move({ move_number: 1, actual_player: 'B', delta_score: -2, score_lead: -2, winrate: 0.4 }),
    ];
    // 复杂度 0 ⇒ 权重 = max(.05, min(1, 2/4)) = 0.5 ⇒ 加权丢分 2 ⇒ 56.25
    expect(summarizeReportMoves(noPrior, 'B').accuracy).toBeCloseTo(56.25, 6);
  });
});

describe('winrateSeries —— 曲线的点', () => {
  it('黑方胜率原样带出来,谁走的那一手也带着', () => {
    expect(winrateSeries(GAME)).toEqual([
      { moveNumber: 0, winrate: 0.5, player: null, deltaScore: null },
      { moveNumber: 1, winrate: 0.46, player: 'B', deltaScore: -1 },
      { moveNumber: 2, winrate: 0.55, player: 'W', deltaScore: -2 },
      { moveNumber: 3, winrate: 0.72, player: 'B', deltaScore: 3 },
    ]);
  });

  // 断掉的手数**不补点**。补了就等于说「这一段也算过」——「只算到第 40 手」的报告
  // 会被画成一条完整的曲线。
  it('没算出来的那些手直接不在序列里,不插值', () => {
    const partial = [
      move({ move_number: 0, winrate: 0.5 }),
      move({ move_number: 1, winrate: 0.4, actual_player: 'B' }),
      move({ move_number: 2, status: 'failed', actual_player: 'W' }),
      move({ move_number: 3, winrate: 0.3, actual_player: 'B' }),
    ];
    expect(winrateSeries(partial).map((p) => p.moveNumber)).toEqual([0, 1, 3]);
  });
});

describe('keyMoves —— 重点手', () => {
  // 白走坏的时候**黑方胜率是涨的**。按黑方胜率的绝对变化排,会把白的失误排成「黑的好手」,
  // 而且方向反了还看不出来 —— 屏上照样是一行通顺的中文。
  it('按走子方自己视角的跌幅排,黑白各按各的算', () => {
    const rows = [
      move({ move_number: 0, winrate: 0.5, score_lead: 0 }),
      // 黑走坏:黑胜率 50 → 30,掉 20
      move({ move_number: 1, actual_player: 'B', winrate: 0.3, score_lead: -6, delta_score: -6 }),
      // 白走坏:黑胜率 30 → 65 ⇒ 白自己 70 → 35,掉 35
      move({ move_number: 2, actual_player: 'W', winrate: 0.65, score_lead: 4, delta_score: -10 }),
    ];
    const k = keyMoves(rows);
    expect(k.map((x) => x.moveNumber)).toEqual([2, 1]);
    expect(k[0].player).toBe('W');
    expect(k[0].beforePct).toBeCloseTo(70, 6);
    expect(k[0].afterPct).toBeCloseTo(35, 6);
    expect(k[0].dropPct).toBeCloseTo(35, 6);
    expect(k[1].dropPct).toBeCloseTo(20, 6);
  });

  // 「该走 X」在**上一行**里 —— 本行已经是走完之后的局面,它的首选说的是「下一手该走哪儿」。
  it('「该走 X」取上一行的首选,不是本行的', () => {
    const cand = (m: string) => [{ move: m, visits: 1, winrate: 0.5, prior: 0.9, pv: [m], score_lead: 0 }] as unknown as TopMove[];
    const rows = [
      move({ move_number: 0, winrate: 0.5, score_lead: 0, top_moves: cand('R11') }),
      move({ move_number: 1, actual_player: 'B', winrate: 0.2, score_lead: -8, delta_score: -8, actual_move: 'C3', top_moves: cand('S8') }),
    ];
    expect(keyMoves(rows)[0]).toMatchObject({ bestMove: 'R11', playedMove: 'C3' });
  });

  it('上一行没存候选时说「没有」,不拿本行的顶替', () => {
    const rows = [
      move({ move_number: 0, winrate: 0.5, score_lead: 0 }),
      move({ move_number: 1, actual_player: 'B', winrate: 0.2, score_lead: -8, delta_score: -8 }),
    ];
    expect(keyMoves(rows)[0].bestMove).toBeNull();
  });

  it('门槛就是失误线 —— 屏上列的这几手和三格里数的那些手是同一批', () => {
    const rows = [
      move({ move_number: 0, winrate: 0.5, score_lead: 0 }),
      move({ move_number: 1, actual_player: 'B', winrate: 0.4, score_lead: -3, delta_score: MISTAKE_SCORE_LOSS }),
      move({ move_number: 2, actual_player: 'W', winrate: 0.45, score_lead: -2, delta_score: -2.99 }),
    ];
    expect(keyMoves(rows).map((k) => k.moveNumber)).toEqual([1]);
  });

  it('丢了目却没丢胜率的手不进这张表', () => {
    const rows = [
      move({ move_number: 0, winrate: 0.5, score_lead: 0 }),
      move({ move_number: 1, actual_player: 'B', winrate: 0.52, score_lead: -9, delta_score: -9 }),
    ];
    expect(keyMoves(rows)).toEqual([]);
  });

  it('最多只列 limit 条', () => {
    const rows = [move({ move_number: 0, winrate: 0.9, score_lead: 0 })];
    for (let n = 1; n <= 6; n += 1) {
      rows.push(move({
        move_number: n, actual_player: 'B',
        winrate: 0.9 - n * 0.1, score_lead: -n * 4, delta_score: -4 - n,
      }));
    }
    expect(keyMoves(rows, 3)).toHaveLength(3);
  });
});
