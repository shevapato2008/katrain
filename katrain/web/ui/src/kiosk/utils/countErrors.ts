import { ApiError } from '../../api';

/**
 * 数子失败的**原因**(v2-design §3.4 / P6)。上一版一律说「手数不足或已结束」——
 * 盒上最常见的真实原因却是**分析还没回来**。说错原因比不说更坏:人会去数手数,该做的是等几秒。
 *
 *   analysis_pending  这一手的分数还没算出来(自动数子按这个退避重试)
 *   below_min_moves   手数没到门槛
 *   game_over         已经有结果了
 *   network           请求没到服务端(`fetch` 自己抛,不是 `ApiError`)
 *   http              到了,但被别的原因拒了(401/403/404/5xx,或 400 却不认识的 code)
 */
export type CountErrorCode = 'analysis_pending' | 'below_min_moves' | 'game_over' | 'network' | 'http';

const KNOWN_CODES: readonly CountErrorCode[] = ['analysis_pending', 'below_min_moves', 'game_over'];

/**
 * S2a 之前的后端,这三种 400 的 `detail` 是英文串(`server.py` 约 L1969 / L2019 / L2023)。
 * 盒上的服务比前端旧几天是常态,所以老串照认 —— 按前缀,不按全文。
 */
const LEGACY_PREFIXES: readonly (readonly [string, CountErrorCode])[] = [
  ['Analysis not available yet', 'analysis_pending'],
  ['Cannot count before', 'below_min_moves'],
  ['Game is already over', 'game_over'],
];

export function countErrorCode(err: unknown): CountErrorCode {
  if (!(err instanceof ApiError)) return 'network';
  const { detail } = err;
  if (detail && typeof detail === 'object' && 'code' in detail) {
    const code = (detail as { code: unknown }).code;
    const known = KNOWN_CODES.find((c) => c === code);
    if (known) return known;
  }
  if (typeof detail === 'string') {
    const hit = LEGACY_PREFIXES.find(([prefix]) => detail.startsWith(prefix));
    if (hit) return hit[1];
  }
  return 'http';
}

export function countErrorMessage(err: unknown, t: (key: string, fallback?: string) => string): string {
  switch (countErrorCode(err)) {
    case 'analysis_pending':
      return t('game:count_err_analysis_pending', '还在算这一手的形势，稍等再数');
    case 'below_min_moves':
      return t('game:count_err_below_min', '手数还不够，暂时不能数子');
    case 'game_over':
      return t('game:count_err_game_over', '这一局已经结束了');
    case 'network':
      return t('game:count_err_network', '分析服务连不上');
    default:
      return t('game:count_err_http', '数子失败（{status}），请重试')
        .replace('{status}', String((err as ApiError).status));
  }
}
