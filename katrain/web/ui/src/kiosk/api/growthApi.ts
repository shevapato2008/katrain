/**
 * 成长屏(屏 22)那几个数。后端 `GET /api/v1/growth/summary`。
 *
 * **为什么不拿对局列表自己数**:RK3562 是 2G 内存,为渲染四个数字把整个对局库拉到浏览器里
 * 再 filter,和被否掉的「每手轮询 SGF」是同一类错。
 */

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
   * 这几个数是谁数出来的。
   *
   * `this_node` = 这台机器就是权威(普通服务端)。
   * `local_cache` = 盒子,权威在云端,本机库只是缓存 ⇒ **数可能偏小**。
   * 「一个数」在屏上天然读作「全部」,所以这一格必须上屏(写成「本机记录」),
   * 不许悄悄拿缓存冒充完整账本。
   */
  authority: 'this_node' | 'local_cache';
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
    && (v.authority === 'this_node' || v.authority === 'local_cache');
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
