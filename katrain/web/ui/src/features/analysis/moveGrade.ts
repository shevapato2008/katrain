/**
 * 着手评价的前端侧共享逻辑。
 *
 * 判级本身在服务端做（阈值真源是 katrain/core/move_grade.yaml），前端只负责
 * 查表、筛选和统计。档位表由 `python -m katrain.core.move_grade --emit-ts`
 * 生成到 ./gradeTiers.generated.ts。
 *
 * 这个文件在 src/features/ 下，galaxy 与 kiosk 两个构建都会用到它。
 * 注意 eslint.config.js 目前对 src/features/** 没有边界规则，所以这里
 * **不要** import 任何 src/galaxy/** 或 src/kiosk/** 的东西 —— 会同时打进两个产物。
 */
import type { MoveAnalysis } from '../../types/live';
import {
  GRADE_BY_ID,
  GRADE_LADDER_POINTS,
  GRADE_PHASES,
  GRADE_TIERS,
  PER_SIDE_LIMIT,
  type GradeId,
  type GradeTier,
} from './gradeTiers.generated';

export { GRADE_TIERS, GRADE_BY_ID, GRADE_LADDER_POINTS, GRADE_PHASES, PER_SIDE_LIMIT };
export type { GradeId, GradeTier };

/** 未评级：上一手没分析、visits 不够、或旧数据。要显示成「未评级」，不能当作「没问题」。 */
export const UNRATED: GradeId = 'unrated';

export type PhaseId = 'all' | 'opening' | 'midgame' | 'endgame';
export type PlayerFilter = 'both' | 'B' | 'W';

export function gradeOf(a: Pick<MoveAnalysis, 'grade'>): GradeId {
  return (a.grade as GradeId) ?? UNRATED;
}

export function tierOf(a: Pick<MoveAnalysis, 'grade'>): GradeTier | null {
  return GRADE_BY_ID[gradeOf(a)] ?? null;
}

export function isBad(a: Pick<MoveAnalysis, 'grade'>): boolean {
  return tierOf(a)?.bad ?? false;
}

export function isBrilliant(a: Pick<MoveAnalysis, 'grade'>): boolean {
  return gradeOf(a) === 'brilliant';
}

/** 手数 → 阶段。区间来自 yaml（布局 0-59 / 中盘 60-149 / 官子 150-end）。 */
export function phaseOf(moveNumber: number): Exclude<PhaseId, 'all'> {
  for (const p of GRADE_PHASES) {
    if (moveNumber >= p.from && (p.to === null || moveNumber <= p.to)) {
      return p.id as Exclude<PhaseId, 'all'>;
    }
  }
  return 'endgame';
}

export function inPhase(moveNumber: number, phase: PhaseId): boolean {
  return phase === 'all' || phaseOf(moveNumber) === phase;
}

export interface SelectOptions {
  phase?: PhaseId;
  player?: PlayerFilter;
  limit?: number;
}

export interface Selection<T> {
  /** 截断后实际显示的那些（两方合并，按手数升序）。 */
  shown: T[];
  /** 当前筛选下**符合条件的总数**，截断前。tab 上要显示 `shown/total`。 */
  total: number;
  /** 被截掉了多少。> 0 时界面必须说出来，否则用户会以为只有这些。 */
  truncated: number;
}

/**
 * 每方各取前 N 条，然后合并、按手数升序。
 *
 * 星阵与 OGS 都是这么做的（星阵每方 5 条、OGS 每方 3 条）。分两方各自截断，
 * 而不是整体取前 N —— 否则一方发挥很差时会把另一方的条目整个挤掉。
 */
export function selectPerSide<T extends { move_number: number; player: string | null }>(
  items: T[],
  rank: (a: T) => number,
  { phase = 'all', player = 'both', limit = PER_SIDE_LIMIT }: SelectOptions = {},
): Selection<T> {
  const eligible = items.filter(
    (m) => inPhase(m.move_number, phase) && (player === 'both' || m.player === player),
  );
  const byColor: Record<string, T[]> = { B: [], W: [] };
  for (const m of eligible) {
    if (m.player === 'B' || m.player === 'W') byColor[m.player].push(m);
  }
  const shown: T[] = [];
  for (const color of ['B', 'W'] as const) {
    byColor[color].sort((a, b) => rank(b) - rank(a));
    shown.push(...byColor[color].slice(0, limit));
  }
  shown.sort((a, b) => a.move_number - b.move_number);
  return { shown, total: eligible.length, truncated: eligible.length - shown.length };
}

/** 问题手按亏的目数排序；旧数据没有 points_lost 时退回 -delta_score。 */
export function badnessRank(a: MoveAnalysis): number {
  return a.points_lost ?? -(a.delta_score ?? 0);
}

/** 妙手按妙度排序，同级再按越难想到（prior 越低）越靠前。 */
export function brillianceRank(a: MoveAnalysis): number {
  return (a.brilliance ?? 1) * 1000 + (1 - (a.top_prior ?? 1)) * 100;
}

export type MatchRateId = 'top1' | 'top3' | 'offbook';

export interface MatchRateRow {
  id: MatchRateId;
  i18nKey: string;
  zh: string;
  color: string;
  black: number;
  white: number;
  /** 该行**自己的**分母：这一方有多少手能判定这件事。两行的分母可以不同。 */
  blackTotal: number;
  whiteTotal: number;
  blackRate: number;
  whiteRate: number;
}

export interface MatchRate {
  rows: MatchRateRow[];
  /** 至少能判定「是不是一选」的手数。 */
  blackDecided: number;
  whiteDecided: number;
  /** 落在本阶段、但连一选都判不了的手数（上一手没分析 / visits 不够 / 旧数据）。 */
  undecidable: number;
}

const MATCH_ROWS: { id: MatchRateId; i18nKey: string; zh: string; color: string }[] = [
  { id: 'top1', i18nKey: 'grade:match_top1', zh: '走中 AI 一选', color: '#2E8B57' },
  { id: 'top3', i18nKey: 'grade:match_top3', zh: '走进 AI 前三', color: '#4DBE46' },
  // 「完全没考虑」名不副实：report_analyze 只存前 10 个候选（move_infos[:10]），
  // 排第 11 的手会被算进这一行。分子分母自洽，但文案必须说清是「前十选」。
  { id: 'offbook', i18nKey: 'grade:match_offbook', zh: '不在 AI 前十选', color: '#CF6B09' },
];

/** 实战手在上一手候选表里的名次；-1 = 不在表内；null = 判不了（没有候选表）。 */
function rankInCandidates(prev: MoveAnalysis | undefined, played: string | null): number | null {
  if (!played) return null;
  const candidates = prev?.top_moves;
  if (!candidates || candidates.length === 0) return null;
  return candidates.findIndex((c) => c.move === played);
}

/**
 * AI 一致率：实战手与引擎候选表的重合程度。
 *
 * 判定基准分两条路，缺一不可：
 *  - 报告链路有服务端算好的 `is_top_move`（`move_grade_core.py` 判的），优先用它；
 *  - 直播链路的 MoveAnalysis 根本没有这个字段，退回「上一手 top_moves[0] == 实战手」现算，
 *    否则直播观战页这一屏会整块空掉。
 *
 * 「前三」与「完全没考虑」只能靠上一手的候选表算，所以它们**各有各的分母** ——
 * 一条能判、另一条判不了的手不能混进同一个分母里，否则两个百分比会打架。
 *
 * 注意「一选」的定义：`top_moves[0]` 是按 KataGo 的 playSelectionValue 排的，
 * 不等于目数最优的那个候选（实测 17.7%–34.4% 的局面两者不同）。界面上要说清楚。
 */
export function buildMatchRate(moves: MoveAnalysis[], phase: PhaseId = 'all'): MatchRate {
  const byNumber = new Map<number, MoveAnalysis>();
  for (const m of moves) byNumber.set(m.move_number, m);

  const hit: Record<MatchRateId, { B: number; W: number }> = {
    top1: { B: 0, W: 0 },
    top3: { B: 0, W: 0 },
    offbook: { B: 0, W: 0 },
  };
  const denom: Record<MatchRateId, { B: number; W: number }> = {
    top1: { B: 0, W: 0 },
    top3: { B: 0, W: 0 },
    offbook: { B: 0, W: 0 },
  };
  let undecidable = 0;

  for (const m of moves) {
    if (!inPhase(m.move_number, phase)) continue;
    if (m.player !== 'B' && m.player !== 'W') continue;
    const side = m.player;
    const rank = rankInCandidates(byNumber.get(m.move_number - 1), m.move);

    const top1: boolean | null = m.is_top_move ?? (rank === null ? null : rank === 0);
    if (top1 === null) {
      undecidable += 1;
      continue;
    }
    denom.top1[side] += 1;
    if (top1) hit.top1[side] += 1;

    if (rank !== null) {
      denom.top3[side] += 1;
      if (rank >= 0 && rank < 3) hit.top3[side] += 1;
      denom.offbook[side] += 1;
      if (rank < 0) hit.offbook[side] += 1;
    }
  }

  const rate = (n: number, d: number) => (d ? n / d : 0);

  return {
    rows: MATCH_ROWS.map((r) => ({
      ...r,
      black: hit[r.id].B,
      white: hit[r.id].W,
      blackTotal: denom[r.id].B,
      whiteTotal: denom[r.id].W,
      blackRate: rate(hit[r.id].B, denom[r.id].B),
      whiteRate: rate(hit[r.id].W, denom[r.id].W),
    })),
    blackDecided: denom.top1.B,
    whiteDecided: denom.top1.W,
    undecidable,
  };
}

export interface HistogramCell {
  tier: GradeTier;
  black: number;
  white: number;
  /** 占该方在当前阶段内**被评级手数**的比例，0..1。两方各自归一。 */
  blackRate: number;
  whiteRate: number;
}

export interface Histogram {
  cells: HistogramCell[];
  blackTotal: number;
  whiteTotal: number;
  /** 该阶段内因 visits 不足或缺上一手分析而未评级的手数。要显示出来。 */
  unrated: number;
}

/**
 * 发挥水准：七档 × 黑白 的分布。
 *
 * 分母是**该方自己在所选阶段内被评级的手数**，两方各自归一 —— 与星阵口径一致。
 * 未评级的手不进分母，但单独报出来，免得「分母悄悄变小」把发挥吹高。
 */
export function buildHistogram(moves: MoveAnalysis[], phase: PhaseId = 'all'): Histogram {
  const counts = new Map<GradeId, { B: number; W: number }>();
  for (const t of GRADE_TIERS) counts.set(t.id, { B: 0, W: 0 });
  let blackTotal = 0;
  let whiteTotal = 0;
  let unrated = 0;

  for (const m of moves) {
    if (!inPhase(m.move_number, phase)) continue;
    if (m.player !== 'B' && m.player !== 'W') continue;
    const g = gradeOf(m);
    const cell = counts.get(g);
    if (!cell) {
      unrated += 1;
      continue;
    }
    cell[m.player] += 1;
    if (m.player === 'B') blackTotal += 1;
    else whiteTotal += 1;
  }

  return {
    cells: GRADE_TIERS.map((tier) => {
      const c = counts.get(tier.id)!;
      return {
        tier,
        black: c.B,
        white: c.W,
        blackRate: blackTotal ? c.B / blackTotal : 0,
        whiteRate: whiteTotal ? c.W / whiteTotal : 0,
      };
    }),
    blackTotal,
    whiteTotal,
    unrated,
  };
}

export type MatchBand = 'top1' | 'top3' | 'mid' | 'off' | 'unknown';

export interface MatchTimelineEntry {
  move_number: number;
  player: 'B' | 'W';
  band: MatchBand;
}

/**
 * 逐手的 AI 吻合档，按手数升序 —— 「AI吻合度 · 分布」那条带的数据源。
 *
 * 与 `buildMatchRate` 的关系：那个函数把同样的判定**汇总成三行比率**，
 * 这个函数把它**摊平成时间线**。判定基准必须与它逐字相同，否则同一 tab 的
 * 两个视图会给出互相打架的结论（统计说命中 50 手、带子上数出来 47 个格）。
 * 所以两者共用同一个 `rankInCandidates`，并且都优先信服务端的 `is_top_move`。
 *
 * `band` 五档，**与 `buildMatchRate` 的三行逐字同义**：
 *   top1    走中上一手候选表的第一名                      → 统计的「走中 AI 一选」
 *   top3    进了前三但不是第一                            → 统计的「走进 AI 前三」减去 top1
 *   mid     在候选表里但排在前三之外（名次 3..9）
 *   off     **根本不在候选表里**                          → 统计的「不在 AI 前十选」
 *   unknown 判不了 —— 上一手没分析 / visits 不够 / 旧数据
 *
 * `mid` 这一档是 2026-09-01 加的，加它的原因是一条测试抓到的真分叉：起初把
 * 「名次 ≥ 3」和「不在表内」一起画成 `off`，而统计里的 `offbook` 只算 `rank < 0`。
 * 于是同一手在统计里不计、在带子上却被算成「没命中」—— 同一个 tab 自相矛盾。
 * 画图时 `mid` / `off` / `unknown` 都落到底色，看着一样；但**语义必须分开**，
 * 否则下一个人照着带子去改统计就会改错。
 *
 * `unknown` 尤其**不能当作 off**：那会把「不知道」画成「没命中」，凭空造出难看的段落。
 *
 * 阶段筛选在这里做而不是在调用方：`phase` 之外的手直接不进结果，
 * 于是带子的横轴范围随阶段收窄，与上面的统计口径一致。
 */
export function buildMatchTimeline(moves: MoveAnalysis[], phase: PhaseId = 'all'): MatchTimelineEntry[] {
  const byNumber = new Map<number, MoveAnalysis>();
  for (const m of moves) byNumber.set(m.move_number, m);

  const out: MatchTimelineEntry[] = [];
  for (const m of moves) {
    if (!inPhase(m.move_number, phase)) continue;
    if (m.player !== 'B' && m.player !== 'W') continue;
    const rank = rankInCandidates(byNumber.get(m.move_number - 1), m.move);
    const top1: boolean | null = m.is_top_move ?? (rank === null ? null : rank === 0);

    let band: MatchBand;
    if (top1 === null) band = 'unknown';
    else if (top1) band = 'top1';
    else if (rank === null) band = 'unknown';
    else if (rank < 0) band = 'off';
    else if (rank < 3) band = 'top3';
    else band = 'mid';

    out.push({ move_number: m.move_number, player: m.player, band });
  }
  out.sort((a, b) => a.move_number - b.move_number);
  return out;
}

/** 某一方最长的连续「走中一选」段；没有则返回 null。用于在分布图上直接把话说出来。 */
export function longestTop1Run(
  timeline: MatchTimelineEntry[],
  side: 'B' | 'W',
): { from: number; to: number; length: number } | null {
  let best: { from: number; to: number; length: number } | null = null;
  let curFrom = 0;
  let curLen = 0;
  let curTo = 0;
  for (const e of timeline) {
    if (e.player !== side) continue;
    if (e.band === 'top1') {
      if (curLen === 0) curFrom = e.move_number;
      curLen += 1;
      curTo = e.move_number;
      if (!best || curLen > best.length) best = { from: curFrom, to: curTo, length: curLen };
    } else {
      curLen = 0;
    }
  }
  return best;
}
