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
  GRADE_PHASES,
  GRADE_TIERS,
  PER_SIDE_LIMIT,
  type GradeId,
  type GradeTier,
} from './gradeTiers.generated';

export { GRADE_TIERS, GRADE_BY_ID, GRADE_PHASES, PER_SIDE_LIMIT };
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

/** 妙手按玄妙指数排序，同级再按越难想到（prior 越低）越靠前。 */
export function brillianceRank(a: MoveAnalysis): number {
  return (a.brilliance ?? 1) * 1000 + (1 - (a.top_prior ?? 1)) * 100;
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
