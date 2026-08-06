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
    };

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
