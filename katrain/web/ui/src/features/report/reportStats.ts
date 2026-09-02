import type { ReportTaskMove } from '../../api/reportApi';

/**
 * 从一份**已经跑完的报告**里算出复盘屏左栏那三格:准确率 / 失误 / 妙手。
 *
 * ## 数据在哪儿(2026-08-22 核实,这就是计划 D4 那一步)
 *
 * `report_task_moves` 每一行 = **走完第 N 手之后**那个局面的分析
 * (`cron/jobs/report_analyze.py:304` 送进去的是 `moves[:move_number]`)。所以
 * **第 N 手的候选着法在第 N-1 行里** —— 那一行的 `top_moves` 是「该走第 N 手时
 * KataGo 给的十个候选」,每个带 `score_lead` / `winrate` / `prior`。
 * `GET /api/v1/reports/{task_id}/moves` 原样吐出来(`endpoints/reports.py:85`)。
 *
 * ⇒ **「第二名着法的评分」在**,所以稿子那格写「妙手」立得住,不用退成国象的「漏着」。
 *   国象 2026-07-28 把妙手撤掉是因为**它的分析跑在盒子自己身上**(单线程 12 万节点、
 *   13–16 层、同一局面能摆 45cp),噪声吃掉了判据。围棋这条线不是:报告是 cron 离线跑的,
 *   每手 500 或 2000 次计算,跟盒子的算力无关。**转判据不转结论**。
 *
 * ## 三个数各自的判据
 *
 * 妙手 / 失误 **不用** `top_moves`,用 `delta_score` 就够,而且这个仓里已经有一份口径:
 * `reportModel.ts:192` 把同一批 `ReportTaskMove` 映射成 `is_brilliant: delta_score >= 2`
 * / `is_mistake: delta_score <= -3`,后端 `cron/analysis_repo.py:185` 和
 * `live/models.py:67` 也是这两个数。**这里复用它,不另立一套** ——
 * 同一局在复盘列表和报告详情里出现两个「失误 N 手」是这类页面最容易犯的错。
 *
 * ⚠️ 仓里还有**第二套阈值**:`web/interface.py:1337` 用的是丢分 `-0.5 / 1.0`,
 * 那是对局中实时那条线(`sum_stats` 那套)。两套不一致是既有问题,本轮不动它 ——
 * 但这一屏读的是 `report_task_moves`,跟它同族的写方是 cron,所以取 cron 那套。
 *
 * 准确率照搬 `katrain/core/ai.py:212-262` 的 `game_report()`:
 * `100 × 0.75^加权丢分`,权重是「这一手有多难」(候选着法按 policy 先验加权的平均丢分)。
 * **不自己发明公式** —— 桌面版和 web 版的对局报告显示的就是这个数,同一局在两处必须一样。
 */

/** 丢分 ≥ 这个数算妙手。与 `reportModel.ts:192` / `cron/analysis_repo.py:185` 同一个数。 */
export const BRILLIANT_SCORE_GAIN = 2;
/** 丢分 ≤ 这个数算失误。同上。 */
export const MISTAKE_SCORE_LOSS = -3;

export interface ReportSummary {
  /** 0–100。**null = 一手都没算进来**(报告是空的 / 这个颜色没有落过子),不是 0。 */
  accuracy: number | null;
  mistakes: number;
  brilliants: number;
  /** 被算进去的手数 —— 判断上面三个数值不值得信,只有这一个来源。 */
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
 * @param moves  `GET /reports/{id}/moves` 的返回,**按 move_number 升序**(接口已经排好)
 * @param color  算谁的 —— 准确率是**分颜色**的,两个人的手混在一起算出来的数没有意义
 */
export function summarizeReportMoves(
  moves: readonly ReportTaskMove[],
  color: 'B' | 'W',
): ReportSummary {
  const byNumber = new Map<number, ReportTaskMove>();
  for (const m of moves) byNumber.set(m.move_number, m);

  let mistakes = 0;
  let brilliants = 0;
  let counted = 0;
  let lossSum = 0;
  let weightSum = 0;

  for (const move of moves) {
    if (move.actual_player !== color) continue;
    if (move.delta_score == null) continue;      // 第 0 行(空盘)和算失败的那些行

    if (move.delta_score >= BRILLIANT_SCORE_GAIN) brilliants += 1;
    if (move.delta_score <= MISTAKE_SCORE_LOSS) mistakes += 1;
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

  if (counted === 0) return { accuracy: null, mistakes: 0, brilliants: 0, counted: 0 };
  const weightedLoss = lossSum / (weightSum || 1e-6);
  return { accuracy: 100 * 0.75 ** weightedLoss, mistakes, brilliants, counted };
}

export interface WinratePoint {
  moveNumber: number;
  /** **黑方**胜率 0–1。cron 那条线固定 `reportAnalysisWinratesAs: "BLACK"`(`clients/katago.py:83`), 所以这个字段跟谁走子无关。 */
  winrate: number;
  /** 走出这个局面的那一手是谁下的 —— 红段(掉分的那一手)要靠它判方向。 */
  player: 'B' | 'W' | null;
  /** 这一手的得失(走子方视角)。`null` = 第 0 行或算失败。 */
  deltaScore: number | null;
}

/**
 * 曲线的点。**只取真算出来的那些行** —— 中间断掉的手数不补点、不插值:
 * 一条连起来的线会把「只算到第 40 手」画成「整局都算过了」。
 */
export function winrateSeries(moves: readonly ReportTaskMove[]): WinratePoint[] {
  const points: WinratePoint[] = [];
  for (const m of moves) {
    if (m.winrate == null) continue;
    points.push({
      moveNumber: m.move_number,
      winrate: m.winrate,
      player: m.actual_player === 'B' || m.actual_player === 'W' ? m.actual_player : null,
      deltaScore: m.delta_score,
    });
  }
  return points;
}

/**
 * ⚠️ **2026-09-02 起 `keyMoves` 在产品代码里没有消费者了。**
 * 屏 20 那张「重点手」列表按 Fan 的裁定还原成了 galaxy 的「妙手 / 失误」两个 tab,
 * 判据也从「胜率掉点」换成了服务端判好的七档 + 目损(`features/analysis/moveGrade`)。
 *
 * 没删是因为它是**另一套口径**而不是错的口径:按胜率跌幅挑重点手在「只想看形势拐点」
 * 这个问题上仍然成立,屏 19 复盘列表将来若要在行尾写一句「掉得最狠的一手」就是它。
 * 但**它现在只被自己的单测覆盖** —— 一份只有测试在跑的代码给的是假的信心,
 * 所以这条注写在这儿:再过一轮还没有消费者,就该删掉它和那 5 条单测。
 * (同文件的 `winrateSeries` / `MISTAKE_SCORE_LOSS` 仍在用,别一起删。)
 */
export interface KeyMove {
  moveNumber: number;
  player: 'B' | 'W';
  /** 走子方**自己**视角的胜率(0–100),走之前 / 走之后。 */
  beforePct: number;
  afterPct: number;
  /** 掉了多少个百分点(走子方视角)。恒为正 —— 只有掉的才进这张表。 */
  dropPct: number;
  /** KataGo 在那个局面下的首选着法。`null` = 上一行没存候选(算失败或旧数据)。 */
  bestMove: string | null;
  /** 这一手实际走的地方。 */
  playedMove: string | null;
}

/**
 * 「重点手」—— **只列掉得最多的那几手**。
 *
 * 排序按**走子方自己视角**的胜率跌幅,不按黑方胜率的绝对变化:白走坏的时候黑方胜率是**涨**的,
 * 按绝对值排会把白的失误排成「黑的好手」。
 *
 * 「该走 X」取的是**上一行**的 `top_moves[0]` —— 那一行分析的正是「该走第 N 手」的局面
 * (`cron/jobs/report_analyze.py:304` 送进去的是 `moves[:move_number]`)。取本行的是错的:
 * 本行已经是走完之后的局面,它的首选说的是「下一手该走哪儿」。
 *
 * 门槛借的是仓里已有的失误线(`delta_score <= -3`),不另立一个「掉多少算掉」——
 * 屏上列出来的这几手,和三格里数进「失误」的那些手必须是同一批。
 */
export function keyMoves(moves: readonly ReportTaskMove[], limit = 3): KeyMove[] {
  const byNumber = new Map<number, ReportTaskMove>();
  for (const m of moves) byNumber.set(m.move_number, m);

  const out: KeyMove[] = [];
  for (const move of moves) {
    const player = move.actual_player;
    if (player !== 'B' && player !== 'W') continue;
    if (move.delta_score == null || move.delta_score > MISTAKE_SCORE_LOSS) continue;
    const prev = byNumber.get(move.move_number - 1);
    if (prev?.winrate == null || move.winrate == null) continue;

    const own = (blackWinrate: number) => (player === 'B' ? blackWinrate : 1 - blackWinrate);
    const beforePct = own(prev.winrate) * 100;
    const afterPct = own(move.winrate) * 100;
    const dropPct = beforePct - afterPct;
    if (dropPct <= 0) continue;              // 丢了目却没丢胜率的手不进这张表

    const cands = Array.isArray(prev.top_moves) ? (prev.top_moves as { move?: string | null }[]) : [];
    out.push({
      moveNumber: move.move_number,
      player,
      beforePct,
      afterPct,
      dropPct,
      bestMove: cands[0]?.move ?? null,
      playedMove: move.actual_move,
    });
  }
  out.sort((a, b) => b.dropPct - a.dropPct);
  return out.slice(0, limit);
}
