/**
 * The client's half of the `game_type` vocabulary.
 *
 * Mirrors `WebKaTrain.GAME_TYPES` / `SCORING_GAME_TYPES` / `RANK_MOVING_GAME_TYPES`
 * in katrain/web/interface.py. Kept in one place because the checks that read it
 * are anti-cheat gates: a scoring game must not show live analysis or offer undo,
 * and every one of those gates used to spell the list out inline. Adding
 * `ai_ladder_ranked` meant editing four of them, and missing one would have put a
 * live win-rate bar on a rank-moving game.
 *
 * Shared territory: both the galaxy and the kiosk bundles import this.
 */

/** Server-issued for 升降级对弈 (katrain/web/core/ladder_repo.py). The ONLY rank-moving type. */
export const LADDER_GAME_TYPE = 'ai_ladder_ranked';

/**
 * Games that count: no analysis, no undo. `rated` and `ranked` are the legacy
 * human-vs-human and pre-ladder AI values, still present in stored rows.
 */
const SCORING_GAME_TYPES: readonly string[] = [LADDER_GAME_TYPE, 'rated', 'ranked'];

export const isScoringGame = (gameType: string | null | undefined): boolean =>
    !!gameType && SCORING_GAME_TYPES.includes(gameType);

export const isLadderGame = (gameType: string | null | undefined): boolean => gameType === LADDER_GAME_TYPE;
