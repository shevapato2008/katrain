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

  // ── 两条出路,以及各自什么时候能走 ────────────────────────────────────────
  //
  // 全部可选:服务端只在**这扇门能承载一个答案**的时候才发(见 `_blocking_payload`)。
  // 所以「键不在」的意思是「这一格没有这扇门」,不是「这扇门关着」——关着是 `false`。
  // 前端必须靠值判断而不是靠键在不在,否则一个旧服务端和一扇关着的门会长得一样。

  // 认输 / 接管:记一场负、动段位。
  // `takeover_eligible_at` 为 null 有两种含义,由 `can_force_resign` 区分:
  //   can_force_resign=true  + null → **此刻就能按**,没什么可等的;
  //   can_force_resign=false + null → 等也没用(这扇门对这一格不适用)。
  // 只有 false + 一个时刻,才该在屏上走倒计时。
  can_force_resign?: boolean;
  // **走秒读这个**,不读下面那个时刻。拿服务端的时刻去减本机的钟,差多少钟倒计时就错多少,
  // 而常年离线、没有可靠 NTP 的一体机正是钟偏最大的那一台。时长是差值,对钟偏免疫——
  // 本机只需要知道「这份响应到手多久了」,那个它自己量得准。
  takeover_eligible_in_seconds?: number | null;
  /** 只作展示/排错。**任何走秒的东西都不许从它算起。** */
  takeover_eligible_at?: string | null;
  takeover_threshold_seconds?: number;
  takeover_threshold_version?: number;

  // 放弃等待:**什么都不记**,段位不变。只对「成绩送不出去」那一格有意义。
  can_release_abandoned_settlement?: boolean;
  abandoned_settlement_eligible_in_seconds?: number | null;
  /** 同上:展示用,不承重。 */
  abandoned_settlement_eligible_at?: string | null;
  abandoned_settlement_threshold_seconds?: number;
  abandoned_settlement_threshold_version?: number;
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
