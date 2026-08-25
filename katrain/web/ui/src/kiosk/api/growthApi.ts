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

export interface GrowthSummary {
  window_days: number;
  games_in_window: number;
  ranked_total: number;
  ranked_wins_in_window: number;
  ranked_losses_in_window: number;
  /** 只列**打过的**档,高档在前。没打过的档不会出现 —— 不摆一排 0 胜 0 负。 */
  by_opponent_rung: GrowthOpponentRung[];
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
