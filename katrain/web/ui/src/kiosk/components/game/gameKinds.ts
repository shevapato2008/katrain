import { isRankedGameType } from '../../../features/aiLadder/gameType';

/** 两人对局:胜率图整块不渲染、没有悔棋(规范 §8「按对弈方式判」那张表)。 */
export const TWO_HUMAN_GAME_TYPES = new Set(['pvp_local', 'pvp_online']);

/** 胜率块、悔棋与「图表」触发的按需分析共用人机自由对弈判据。 */
export function isFreeVsAi({ gameType, engineMode = false, isRanked = false }: {
  gameType: string | null | undefined;
  engineMode?: boolean;
  isRanked?: boolean;
}): boolean {
  // 同时读调用方标志与局型,避免少传 isRanked 时放开升降级的闸。
  return !engineMode && !isRanked && !isRankedGameType(gameType) && !TWO_HUMAN_GAME_TYPES.has(gameType ?? 'free');
}
