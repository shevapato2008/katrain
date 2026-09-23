import type { ReportTaskMove } from '../../api/reportApi';
import type { MoveAnalysis } from '../../types/live';
import { gradedMoves, isBad, isBrilliant } from '../analysis/moveGrade';
import { toMoveAnalysisMap } from './reportModel';

/**
 * 从一份**已经跑完的报告**里算出复盘屏左栏那三格(准确率 / 失误 / 妙手)和胜率曲线的点。
 *
 * ## 数据在哪儿(2026-08-22 核实)
 *
 * `report_task_moves` 每一行 = **走完第 N 手之后**那个局面的分析
 * (`cron/jobs/report_analyze.py:304` 送进去的是 `moves[:move_number]`)。所以
 * **第 N 手的候选着法在第 N-1 行里** —— 那一行的 `top_moves` 是「该走第 N 手时
 * KataGo 给的十个候选」,每个带 `score_lead` / `winrate` / `prior`。
 * `GET /api/v1/reports/{task_id}/moves` 原样吐出来,旧报告缺 `grade` 时服务端按需补算。
 *
 * ## 失误 / 妙手:和屏 20 走同一条管线(2026-09-14 改,调研 R1)
 *
 * 以前这两格按 `delta_score`(两次独立搜索之差)自己数:≥2 算妙手、≤−3 算失误。
 * 那根轴上界卡在 0 附近,「妙手」基本只在搜索噪声上触发(`docs/move-grading/design.md` §1);
 * 而屏 20 的「妙 a · 坏 b」和妙手 / 失误 tab 早已改读服务端七档 ⇒ 同一局两屏数字对不上。
 *
 * 现在两格都经 `toMoveAnalysisMap → gradedMoves` 判级,**与屏 20 逐字同一条路**:
 *  - 失误 = `isBad`(小亏 / 失误 / 恶手),与屏 20「失误」tab 同一个桶;
 *  - 妙手 = `isBrilliant`;
 *  - 云端太旧、整份报告一手 grade 都没有时,退回规则只写在 `gradedMoves` 里,这里不另写。
 * 区别只有一个:这两格**只数视角那一方**(左栏写着是谁的视角),屏 20 折叠头是双方合计。
 * ⇒ 黑的格 + 白的格 = 屏 20 的数。`reportStats.test.ts` 钉着这条等式。
 *
 * ## 准确率没换轴
 *
 * 照搬 `katrain/core/ai.py:212-262` 的 `game_report()`:
 * `100 × 0.75^加权丢分`,权重是「这一手有多难」(候选着法按 policy 先验加权的平均丢分)。
 * **不自己发明公式** —— 桌面版和 web 版的对局报告显示的就是这个数,同一局在两处必须一样。
 * 它仍建在 `delta_score` 上;`ai.py` 换不换轴是 move-grading 登记的遗留,两边必须一起动。
 */

export interface ReportSummary {
  /** 0–100。**null = 一手都没算进来**(报告是空的 / 这个颜色没有落过子),不是 0。 */
  accuracy: number | null;
  mistakes: number;
  brilliants: number;
  /** 被算进**准确率**的手数(有 delta_score 的那些)。失误 / 妙手两格不看它 —— 它们走判级管线。 */
  counted: number;
}

interface Candidate {
  move?: string | null;
  score_lead?: number | null;
  prior?: number | null;
}

/**
 * `top_moves` 在接口上是 `TopMove[] | null`,但它来自 `JSON` 列 —— 真跑起来什么都可能是。
 * 只挑我们要的两个字段,缺了就当这条候选不存在。
 */
function candidatesOf(move: ReportTaskMove | undefined): Candidate[] {
  const raw = move?.top_moves;
  if (!Array.isArray(raw)) return [];
  return raw as unknown as Candidate[];
}

const sign = (player: 'B' | 'W'): number => (player === 'B' ? 1 : -1);

/**
 * 一手棋有多难 —— `ai.py:236-243` 那段。候选着法按 policy 先验加权的平均丢分:
 * 满盘只有一步不亏的时候这个数大,随便走都差不多的时候接近 0。
 *
 * 先验缺席时**退回 0**(= 这手不难),和 `ai.py` 的 `filtered_cands` 过滤一致 ——
 * 那边要求 `"prior" in d`,这里要求 `prior != null`(JSON 列里缺字段读出来是 undefined)。
 */
function complexityOf(prevRootScore: number, cands: Candidate[], player: 'B' | 'W'): number {
  const s = sign(player);
  let weighted = 0;
  let priors = 0;
  for (const c of cands) {
    if (c.prior == null || c.score_lead == null) continue;
    const candPointsLost = s * (prevRootScore - c.score_lead);
    weighted += Math.max(candPointsLost, 0) * c.prior;
    priors += c.prior;
  }
  if (priors <= 0) return 0;
  return Math.min(1, weighted / priors);
}

/**
 * 屏 20 用的就是这一条:`useReportDetail` 里 `toMoveAnalysisMap`,`MoveGradePanel` 里 `gradedMoves`。
 * 屏 19 拿同一份逐手数据再走一遍,两屏才不会各判各的。
 */
function gradedReportMoves(moves: readonly ReportTaskMove[]): MoveAnalysis[] {
  return gradedMoves(toMoveAnalysisMap([...moves], ''));
}

/**
 * @param moves  `GET /reports/{id}/moves` 的返回,**按 move_number 升序**(接口已经排好)
 * @param color  算谁的 —— 准确率是**分颜色**的,两个人的手混在一起算出来的数没有意义
 */
export function summarizeReportMoves(
  moves: readonly ReportTaskMove[],
  color: 'B' | 'W',
): ReportSummary {
  const byNumber = new Map<number, ReportTaskMove>();
  for (const m of moves) byNumber.set(m.move_number, m);

  let counted = 0;
  let lossSum = 0;
  let weightSum = 0;

  for (const move of moves) {
    if (move.actual_player !== color) continue;
    if (move.delta_score == null) continue;      // 第 0 行(空盘)和算失败的那些行
    counted += 1;

    // `ai.py:231` —— 亏分才计,赚的那些按 0 算(赚分不该把准确率抬到 100 以上)
    const pointsLost = Math.max(0, -move.delta_score);
    const prev = byNumber.get(move.move_number - 1);
    const complexity = prev?.score_lead == null
      ? 0
      : complexityOf(prev.score_lead, candidatesOf(prev), color);
    // `ai.py:244` —— 简单局面走错扣得狠,难局面走错网开一面;下界 0.05 让它永远有点权重
    const adjWeight = Math.max(0.05, Math.min(1, Math.max(complexity, pointsLost / 4)));
    lossSum += pointsLost * adjWeight;
    weightSum += adjWeight;
  }

  // 两格**不看 counted**:`counted` 只数有 delta_score 的手(准确率要它),而判级那条管线只要胜率与目差。
  // 服务端给了 grade、这一行没有 delta_score 时,屏 20 照样数它 —— 这里若跟着 counted 归零,等式就破了。
  const mine = gradedReportMoves(moves).filter((m) => m.player === color);
  const mistakes = mine.filter(isBad).length;
  const brilliants = mine.filter(isBrilliant).length;
  if (counted === 0) return { accuracy: null, mistakes, brilliants, counted: 0 };
  const weightedLoss = lossSum / (weightSum || 1e-6);
  return { accuracy: 100 * 0.75 ** weightedLoss, mistakes, brilliants, counted };
}

export interface WinratePoint {
  moveNumber: number;
  /** **黑方**胜率 0–1。cron 那条线固定 `reportAnalysisWinratesAs: "BLACK"`(`clients/katago.py:83`), 所以这个字段跟谁走子无关。 */
  winrate: number;
  /** 走出这个局面的那一手是谁下的 —— 红段(掉分的那一手)要靠它判方向。 */
  player: 'B' | 'W' | null;
  /**
   * 这一手是不是坏手(小亏 / 失误 / 恶手)。**与三格里的「失误」、屏 20 的失误 tab 同一个桶** ——
   * 红段只在这些手里挑,屏上标红的那一手才一定能在失误 tab 里找到。
   */
  bad: boolean;
}

/**
 * 曲线的点。**只取真算出来的那些行** —— 中间断掉的手数不补点、不插值:
 * 一条连起来的线会把「只算到第 40 手」画成「整局都算过了」。
 */
export function winrateSeries(moves: readonly ReportTaskMove[]): WinratePoint[] {
  const badMoves = new Set(gradedReportMoves(moves).filter(isBad).map((m) => m.move_number));
  const points: WinratePoint[] = [];
  for (const m of moves) {
    if (m.winrate == null) continue;
    points.push({
      moveNumber: m.move_number,
      winrate: m.winrate,
      player: m.actual_player === 'B' || m.actual_player === 'W' ? m.actual_player : null,
      bad: badMoves.has(m.move_number),
    });
  }
  return points;
}
