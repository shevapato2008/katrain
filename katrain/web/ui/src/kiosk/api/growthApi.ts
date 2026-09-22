/**
 * 成长屏(屏 22)那几个数。后端 `GET /api/v1/growth/summary`。
 *
 * **为什么不拿对局列表自己数**:RK3562 是 2G 内存,为渲染四个数字把整个对局库拉到浏览器里
 * 再 filter,和被否掉的「每手轮询 SGF」是同一类错。
 */
import type { DataAuthority } from '../../api/userGamesApi';

const AUTHORITIES: readonly DataAuthority[] = ['this_node', 'cloud', 'local_cache'];

export interface GrowthOpponentRung {
  rung: number;
  rank_name: string | null;
  wins: number;
  losses: number;
}

/** 近 N 天档位走势的一个点:**一天一个**(那天最后一局时的档位)。没下升降级的那天不出现。 */
export interface GrowthTrendPoint {
  /** `YYYY-MM-DD`(服务端按 UTC 切的天)。 */
  date: string;
  rung: number;
  rank_name: string | null;
}

export interface GrowthSummary {
  window_days: number;
  games_in_window: number;
  ranked_total: number;
  ranked_wins_in_window: number;
  ranked_losses_in_window: number;
  /** 只列**打过的**档,高档在前。没打过的档不会出现 —— 不摆一排 0 胜 0 负。 */
  by_opponent_rung: GrowthOpponentRung[];
  /**
   * 「算得出胜负的局」——记下了这个用户执黑还是执白、且 `result` 判得出赢家的那些。
   * 与 `games_in_window` **口径不同**:那个数的是下了多少局。
   * **可选**:云端可能还没部署到这一版,那时胜率退回升降级口径(见 `winrateCell`)。
   * 所以 `isGrowthSummary` 不查它们 —— 查了就等于把老云端的正常响应判成坏 payload。
   */
  decided_games_in_window?: number;
  wins_in_window?: number;
  losses_in_window?: number;
  /**
   * 近 N 天档位走势(定级之后的升降级局,一天一个点)。**可选**:老云端不回它,
   * 那时左栏整块不画 —— 不画,不是画一条空轴。读它走 `trendPoints`,别直接读。
   */
  rung_trend?: GrowthTrendPoint[];
  /**
   * 这几个数是谁数出来的。口径见 `api/userGamesApi.ts` 的 `DataAuthority` ——
   * **一个概念只许有一套词**,复盘列表那句「本机 N 局 / 共 N 局」用的是同一格。
   *
   * 2026-08-26 补了 `cloud`:在此之前盒子上**从来不问云端**,永远数本机、永远标
   * `local_cache` ⇒ 同一台盒子上复盘屏那张列表来自云端、成长屏那几个数来自本机,
   * **两屏对不上,而两边都没说自己从哪儿数的**。
   */
  authority: DataAuthority;
}

export class GrowthApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'GrowthApiError';
    this.status = status;
  }
}

/**
 * ⚠️ **返回体是解析出来的 JSON,不是有类型的值。** 老服务端、答 200 却给了别的东西的网关、
 * 半截 payload,到这儿全都会因为一句 `as GrowthSummary` 变成「合法的 GrowthSummary」——
 * 然后在渲染 `by_opponent_rung.map` 时抛,而它上面没有 error boundary。
 * (阶梯那边 `isAiLadderReadyStatus` 就是为同一件事写的,注释里记着它当初白屏过。)
 */
export const isGrowthSummary = (value: unknown): value is GrowthSummary => {
  if (!value || typeof value !== 'object') return false;
  const v = value as Partial<GrowthSummary>;
  return typeof v.window_days === 'number'
    && typeof v.games_in_window === 'number'
    && typeof v.ranked_total === 'number'
    && typeof v.ranked_wins_in_window === 'number'
    && typeof v.ranked_losses_in_window === 'number'
    && Array.isArray(v.by_opponent_rung)
    && v.by_opponent_rung.every((r) => r && typeof r.rung === 'number'
      && typeof r.wins === 'number' && typeof r.losses === 'number')
    && AUTHORITIES.includes(v.authority as DataAuthority);
};

export const getGrowthSummary = async (token?: string, signal?: AbortSignal): Promise<GrowthSummary> => {
  const response = await fetch('/api/v1/growth/summary', {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal,
  });
  if (!response.ok) {
    throw new GrowthApiError(response.status, `growth summary failed: ${response.status}`);
  }
  const body: unknown = await response.json();
  if (!isGrowthSummary(body)) {
    throw new GrowthApiError(response.status, 'growth summary payload not recognised');
  }
  return body;
};

/**
 * 升降级胜率。**分母是 0 就返回 null,不返回 0%** —— 「一局没下」和「全输了」
 * 在屏上必须是两句话。
 */
export const rankedWinrate = (s: GrowthSummary): number | null => {
  const decided = s.ranked_wins_in_window + s.ranked_losses_in_window;
  return decided === 0 ? null : s.ranked_wins_in_window / decided;
};

/**
 * 屏上胜率那一格该显示什么。**标签跟着数走** —— 显示一个口径、算另一个,是这一屏最容易犯的错。
 *
 * · 云端给了新字段 ⇒ `scope: 'all'`,分母是所有算得出执色的局。
 * · 没给(老云端)⇒ 退回升降级口径,`scope: 'ranked'`,屏上的标签也退回「升降级胜率」。
 * · 分母是 0 ⇒ `value: null`,屏上写 `—`。**不返回 0%**:「一局没下」和「全输了」是两句话。
 *
 * `unknownGames` 是「下了但没算进胜率」的局数(新字段存在时才有意义),屏上那句
 * 「有 N 局没算进胜率」就是它。老口径下这个差额的意思是「不是升降级局」,不是「没记执色」,
 * 所以那时恒为 0 —— 不把一句在老口径下不成立的话说出来。
 */
export const winrateCell = (s: GrowthSummary): {
  value: number | null; scope: 'all' | 'ranked'; unknownGames: number;
} => {
  if (typeof s.decided_games_in_window === 'number') {
    const decided = s.decided_games_in_window;
    const unknownGames = Math.max(0, s.games_in_window - decided);
    if (decided === 0) return { value: null, scope: 'all', unknownGames };
    return { value: (s.wins_in_window ?? 0) / decided, scope: 'all', unknownGames };
  }
  return { value: rankedWinrate(s), scope: 'ranked', unknownGames: 0 };
};

// ── 能力诊断(G1)─────────────────────────────────────────────────────────
// 后端 `GET /api/v1/growth/diagnosis`:最近 N 份**已完成**报告里,**本用户执的那一方**的手,
// 按布局 / 中盘 / 官子三段(与复盘屏同一份 `move_grade.yaml` 边界)数评过级的手和其中的问题手。

export type DiagnosisPhase = 'opening' | 'midgame' | 'endgame';

const DIAGNOSIS_PHASES: readonly DiagnosisPhase[] = ['opening', 'midgame', 'endgame'];

export interface GrowthDiagnosisPhase {
  phase: DiagnosisPhase;
  /** 这一段**评过级**的手数。没评级(`grade` 为空 / unrated)的手不在这里 —— 那是「不知道」。 */
  graded: number;
  /** 其中问题手(报告七档里的小亏 · 失误 · 恶手)的手数。 */
  bad: number;
}

export interface GrowthDiagnosis {
  window_days: number;
  /** 算进来的报告份数(对局记下了你执哪一方的那些)。 */
  reports: number;
  /**
   * 有报告、但那一局没记下你执黑还是执白,**整份没算**的份数。
   * 它把「一份报告都没有」和「有报告但算不出」分成两句话 —— 后者说成前者就是在撒谎。
   */
  skipped_without_color: number;
  graded_moves: number;
  /** 只列有评过级的手的那几段。 */
  phases: GrowthDiagnosisPhase[];
  authority: DataAuthority;
}

/** 样本门槛。低于它照样显示,但要**明说结论会抖** —— 藏起来等于不承认自己在猜。 */
export const DIAGNOSIS_THIN_MOVES = 200;
export const DIAGNOSIS_THIN_REPORTS = 3;

/** 最弱那段要比第二弱的高出这么多(失误率的绝对差)才标 —— 差一个百分点就下结论是拿噪声给人判。 */
export const DIAGNOSIS_WEAKEST_GAP = 0.03;

export const isGrowthDiagnosis = (value: unknown): value is GrowthDiagnosis => {
  if (!value || typeof value !== 'object') return false;
  const v = value as Partial<GrowthDiagnosis>;
  return typeof v.reports === 'number'
    && typeof v.graded_moves === 'number'
    && typeof v.skipped_without_color === 'number'
    && Array.isArray(v.phases)
    && v.phases.every((p) => p && typeof p.graded === 'number' && typeof p.bad === 'number'
      && DIAGNOSIS_PHASES.includes(p.phase))
    && AUTHORITIES.includes(v.authority as DataAuthority);
};

export const getGrowthDiagnosis = async (token?: string, signal?: AbortSignal): Promise<GrowthDiagnosis> => {
  const response = await fetch('/api/v1/growth/diagnosis', {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal,
  });
  if (!response.ok) {
    throw new GrowthApiError(response.status, `growth diagnosis failed: ${response.status}`);
  }
  const body: unknown = await response.json();
  if (!isGrowthDiagnosis(body)) {
    throw new GrowthApiError(response.status, 'growth diagnosis payload not recognised');
  }
  return body;
};

export interface DiagnosisLine extends GrowthDiagnosisPhase {
  /** 问题手占评过级的手的比例,0…1。 */
  rate: number;
  weakest: boolean;
}

/**
 * 三段各一行,**按布局 → 中盘 → 官子排**(不按后端给的顺序,也不按严重度 —— 读者找的是那一段)。
 * 最弱只在它比第二弱的高出 `DIAGNOSIS_WEAKEST_GAP` 时才标;只有一段时没有「最弱」可言。
 */
export const diagnosisLines = (d: GrowthDiagnosis): DiagnosisLine[] => {
  const rows = DIAGNOSIS_PHASES
    .map((phase) => d.phases.find((p) => p.phase === phase))
    .filter((p): p is GrowthDiagnosisPhase => p !== undefined && p.graded > 0)
    .map((p) => ({ ...p, rate: p.bad / p.graded, weakest: false }));
  const sorted = [...rows].sort((a, b) => b.rate - a.rate);
  if (sorted.length >= 2 && sorted[0].rate - sorted[1].rate >= DIAGNOSIS_WEAKEST_GAP) {
    sorted[0].weakest = true;
  }
  return rows;
};

/**
 * 走势的点,**只在形状对时**才给。`rung_trend` 是可选字段,`isGrowthSummary` 故意不查它
 * (查了等于为了一块走势把整组数判成坏 payload、四个数一起变 `—`);所以形状不对时
 * 在这里丢掉的只是走势这一块,返回 `null` ⇒ 屏上不画。
 */
export const trendPoints = (s: GrowthSummary): GrowthTrendPoint[] | null => {
  const raw: unknown = s.rung_trend;
  if (!Array.isArray(raw)) return null;
  const ok = raw.every((p) => p && typeof p === 'object'
    && typeof (p as GrowthTrendPoint).date === 'string'
    && /^\d{4}-\d{2}-\d{2}$/.test((p as GrowthTrendPoint).date)
    && typeof (p as GrowthTrendPoint).rung === 'number');
  return ok ? (raw as GrowthTrendPoint[]) : null;
};
