export type AiLadderCertificationStatus = 'provisional' | 'certified';

export type AiLadderAvailability = 'available' | 'unavailable';

export type AiLadderRoute = 'local' | 'server';

export type AiLadderCountingReason =
  | 'invalid_game_type'
  | 'engine_unavailable'
  | 'inconclusive'
  | 'opponent_not_eligible'
  | 'opponent_rung_mismatch';

export type AiLadderSettlementReceipt =
  | { state: 'pending' }
  | {
      state: 'settled';
      game_id: string;
      counted: boolean;
      reason: AiLadderCountingReason | null;
    };

export interface AiLadderCatalogEntry {
  rung: number;
  rank_name: string;
  certification_status: AiLadderCertificationStatus;
  availability: AiLadderAvailability;
  route: AiLadderRoute;
  counting_eligibility?: 'eligible' | 'ineligible';
  counting_reason?: AiLadderCountingReason;
}

export interface AiLadderPlacementInProgress {
  phase: 'placement';
  completed_games: number;
  total_games: 5;
}

export interface AiLadderPlacedRung {
  phase: 'placed';
  rung: AiLadderCatalogEntry;
}

export type AiLadderPlacementState = AiLadderPlacementInProgress | AiLadderPlacedRung;

export type AiLadderRankedOutcome = 'win' | 'loss';

export type AiLadderNetScore = -2 | -1 | 0 | 1 | 2;

export interface AiLadderBlockingGame {
  game_id: string;
  state: 'active' | 'pending_settlement';
  ownership: 'current_device' | 'other_device';
  session_id?: string;
  user_color: 'B' | 'W';
  opponent_rank_name: string;
}

export type AiLadderGameLifecycle =
  | { state: 'active'; game_id: string }
  | { state: 'pending_settlement'; game_id: string }
  | {
      state: 'settled';
      game_id: string;
      receipt: {
        counted: boolean;
        reason: AiLadderCountingReason | null;
      };
    }
  // 放弃等待一个送不到的结果。**没有 receipt,而且没有是对的**:账本记的是裁决,
  // 而「那台盒子再没回来」不是裁决。所以这一支不带 receipt,`counted` 恒为 false ——
  // 它只说「这个占位放开了」,不说这局谁赢了。
  | { state: 'released'; game_id: string; counted: false };

export interface AiLadderLoadingStatus {
  view_state: 'loading';
}

export interface AiLadderErrorStatus {
  view_state: 'error';
  message?: string;
}

// Seat and clock only. Board size, ruleset, komi and handicap are fixed server-side
// at the conditions every rung was calibrated under (19x19, Chinese, 7.5, no handicap
// — katrain/web/api/v1/endpoints/ai_ladder.py). The request model forbids extras, so
// sending them is a 422 rather than a silently-ignored field.
export interface AiLadderStartPreferences {
  color: 'black' | 'white';
  time_enabled: boolean;
  main_time: number;
  byo_length: number;
  byo_periods: number;
}

export interface AiLadderStartResponse {
  session_id: string;
  game_id: string;
  opponent: AiLadderCatalogEntry;
  status: AiLadderReadyStatus;
}

export interface AiLadderReadyStatus {
  view_state: 'ready';
  placement_state: AiLadderPlacementState;
  current_opponent: AiLadderCatalogEntry | null;
  recent_ranked_results: AiLadderRankedOutcome[];
  net_score: AiLadderNetScore;
  pending_settlement: boolean;
  blocking_game?: AiLadderBlockingGame | null;
  // Whether THIS node will seat an uncertified rung (KATRAIN_LADDER_ALLOW_PROVISIONAL).
  // The rung keeps reporting its own real certification_status/availability; this says
  // what the server will do about it. Optional so a node that predates the field reads
  // as "will not", which is the safe direction.
  provisional_play_allowed?: boolean;
}

export type AiLadderStatus = AiLadderLoadingStatus | AiLadderErrorStatus | AiLadderReadyStatus;

/**
 * The status endpoint's body is parsed JSON, not a typed value — an older server, a
 * gateway that answers 200 with something else, or a partial payload all arrive here as
 * `AiLadderReadyStatus` because that is what the cast says. Rendering one of those used to
 * throw inside AiLadderStatusCard on `placement_state.phase`, and with no error boundary
 * above it that unmounts the entire app: a blank screen instead of "failed to load".
 * Anything that does not satisfy this guard is treated as a load failure.
 */
export const isAiLadderReadyStatus = (value: unknown): value is AiLadderReadyStatus => {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<AiLadderReadyStatus>;
  const placement = candidate.placement_state;
  return candidate.view_state === 'ready'
    && typeof candidate.net_score === 'number'
    && Array.isArray(candidate.recent_ranked_results)
    && typeof candidate.pending_settlement === 'boolean'
    && !!placement && typeof placement === 'object'
    && (placement.phase === 'placement'
      ? typeof placement.completed_games === 'number' && placement.total_games === 5
      : placement.phase === 'placed'
        && typeof placement.rung?.rung === 'number'
        && typeof placement.rung.rank_name === 'string');
};
