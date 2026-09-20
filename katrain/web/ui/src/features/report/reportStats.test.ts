import { describe, expect, it } from 'vitest';

import type { ReportTaskMove } from '../../api/reportApi';
import type { TopMove } from '../../types/live';
import { gradedMoves, isBad, isBrilliant } from '../analysis/moveGrade';
import { toMoveAnalysisMap } from './reportModel';
import { summarizeReportMoves, winrateSeries } from './reportStats';

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

/**
 * R1 回归夹具(2026-09-14 调研):grade 与 delta_score **故意打架**,而且打架的方式让
 * 「旧口径的黑 + 白」与「屏 20 的双方合计」**两个数都不相等** —— 否则等式那条改前也是绿的。
 *   旧口径(delta ≥2 妙 / ≤−3 失误):黑 妙1 失1,白 妙1 失0 ⇒ 合计 妙2 失1
 *   七档(isBrilliant / isBad):     黑 妙0 失1,白 妙1 失1 ⇒ 合计 妙1 失2
 */
const FIGHTING: ReportTaskMove[] = [
  move({ move_number: 0, winrate: 0.5, score_lead: 0 }),
  // 黑:两次搜索之差 +3(旧口径妙手),服务端判「最佳」
  move({ move_number: 1, winrate: 0.6, score_lead: 3, actual_player: 'B', delta_score: 3, grade: 'best' }),
  // 白:旧口径 −1(不算失误),服务端判「小亏」
  move({ move_number: 2, winrate: 0.62, score_lead: 4, actual_player: 'W', delta_score: -1, grade: 'inaccuracy' }),
  // 黑:旧口径 −4(失误),服务端在同一次搜索里只算亏 1 目,判「尚可」
  move({ move_number: 3, winrate: 0.45, score_lead: 0, actual_player: 'B', delta_score: -4, grade: 'playable' }),
  // 白:旧口径 +2.5(妙手),服务端也判「妙手」
  move({ move_number: 4, winrate: 0.4, score_lead: -1, actual_player: 'W', delta_score: 2.5, grade: 'brilliant' }),
  // 黑:两次搜索之差只有 −2(旧口径不算),服务端同一次搜索里算亏 7 目,判「恶手」
  move({ move_number: 5, winrate: 0.2, score_lead: -8, actual_player: 'B', delta_score: -2, grade: 'blunder' }),
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
    // 夹具不带 grade ⇒ 走 gradedMoves 的退回规则:亏 2 目 ≤ −1.5 是「小亏」,与屏 20「失误」tab 同桶。
    expect(s.mistakes).toBe(1);
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

  // 云端太旧、整份报告一手 grade 都没有时,退回规则**只在 gradedMoves 一处** —— 这里不另写一份。
  it('整份报告都没有 grade 时,退回规则和屏 20 是同一条', () => {
    const edge = [
      move({ move_number: 0, score_lead: 0, winrate: 0.5 }),
      move({ move_number: 1, actual_player: 'B', delta_score: 2, score_lead: 2, winrate: 0.6 }),
      move({ move_number: 2, actual_player: 'B', delta_score: -3, score_lead: -1, winrate: 0.4 }),
      move({ move_number: 3, actual_player: 'B', delta_score: 1.99, score_lead: 1, winrate: 0.5 }),
      move({ move_number: 4, actual_player: 'B', delta_score: -1.49, score_lead: -2, winrate: 0.4 }),
    ];
    const s = summarizeReportMoves(edge, 'B');
    const screen20 = gradedMoves(toMoveAnalysisMap(edge, 'g'));
    expect(s.brilliants).toBe(screen20.filter(isBrilliant).length);
    expect(s.mistakes).toBe(screen20.filter(isBad).length);
    expect(s.brilliants).toBe(1);   // 正好 2 算,1.99 不算
    expect(s.mistakes).toBe(1);     // 正好 -3 算,-1.49 不到小亏线
  });

  it('先验缺席时复杂度退回 0,不整条崩掉', () => {
    const noPrior = [
      move({ move_number: 0, score_lead: 0, winrate: 0.5, top_moves: [{ move: 'A', score_lead: 2 }] as unknown as TopMove[] }),
      move({ move_number: 1, actual_player: 'B', delta_score: -2, score_lead: -2, winrate: 0.4 }),
    ];
    // 复杂度 0 ⇒ 权重 = max(.05, min(1, 2/4)) = 0.5 ⇒ 加权丢分 2 ⇒ 56.25
    expect(summarizeReportMoves(noPrior, 'B').accuracy).toBeCloseTo(56.25, 6);
  });

  // R1 回归钉子。变异验证:把 summarizeReportMoves 退回按 delta_score 阈值数,这两条都红。
  it('失误 / 妙手按服务端七档数,不按两次搜索之差', () => {
    expect(summarizeReportMoves(FIGHTING, 'B')).toMatchObject({ brilliants: 0, mistakes: 1 });
    expect(summarizeReportMoves(FIGHTING, 'W')).toMatchObject({ brilliants: 1, mistakes: 1 });
  });

  it('黑的格 + 白的格 = 屏 20 折叠头「妙 a · 坏 b」那两个数', () => {
    const screen20 = gradedMoves(toMoveAnalysisMap(FIGHTING, 'g'));
    const black = summarizeReportMoves(FIGHTING, 'B');
    const white = summarizeReportMoves(FIGHTING, 'W');
    expect(black.brilliants + white.brilliants).toBe(screen20.filter(isBrilliant).length);
    expect(black.mistakes + white.mistakes).toBe(screen20.filter(isBad).length);
  });

  // 服务端给了 grade、这一行却没有 delta_score(`toMoveAnalysisMap` 只要胜率与目差就收这一手,
  // `_moves_with_grades` 只补 grade 不补 delta_score):屏 20 照样把它数进「坏」。
  // 准确率要 delta_score、算不了是它自己的事,两格不许跟着归零。
  // 变异验证:把「counted === 0 就整体返回 0」那种提前返回放回去,这条红。
  it('grade 有值而 delta_score 为 null:准确率是 null,失误照数,与屏 20、红段一致', () => {
    const noDelta = [
      move({ move_number: 0, winrate: 0.5, score_lead: 0 }),
      move({ move_number: 1, winrate: 0.2, score_lead: -8, actual_player: 'B', delta_score: null, grade: 'blunder' }),
    ];
    const s = summarizeReportMoves(noDelta, 'B');
    expect(s).toMatchObject({ accuracy: null, counted: 0, mistakes: 1, brilliants: 0 });
    expect(s.mistakes).toBe(gradedMoves(toMoveAnalysisMap(noDelta, 'g')).filter(isBad).length);
    expect(winrateSeries(noDelta).find((p) => p.moveNumber === 1)?.bad).toBe(true);
  });
});

describe('winrateSeries —— 曲线的点', () => {
  it('黑方胜率原样带出来,谁走的那一手也带着;坏手标记走七档的退回规则', () => {
    expect(winrateSeries(GAME)).toEqual([
      { moveNumber: 0, winrate: 0.5, player: null, bad: false },
      { moveNumber: 1, winrate: 0.46, player: 'B', bad: false },
      { moveNumber: 2, winrate: 0.55, player: 'W', bad: true },    // 亏 2 目 ⇒ 小亏
      { moveNumber: 3, winrate: 0.72, player: 'B', bad: false },
    ]);
  });

  it('红段候选(bad)与三格里的「失误」是同一个桶 —— 按 grade,不按 delta_score', () => {
    expect(winrateSeries(FIGHTING).filter((p) => p.bad).map((p) => p.moveNumber)).toEqual([2, 5]);
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
