const RANKED_GAME_TYPES = new Set(['ranked', 'rated', 'ai_ladder_ranked']);

export const isRankedGameType = (gameType?: string | null): boolean =>
  gameType != null && RANKED_GAME_TYPES.has(gameType);
