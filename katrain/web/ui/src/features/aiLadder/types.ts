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

/**
 * outbox 对这一局成绩的据实交代 —— 「重试 2/5 · 下次 0:18 后」那一行的全部数据来源。
 *
 * **只有盒子会发。** 云端只知道「成绩还没到」,它无从知道是在排队、在退避、试完了
 * 还是被拒了,而这恰好是用户唯一想问的那件事。键不在 = 这台机器上没有 outbox
 * (网页直连云端),不是「没有重试」。
 */
export interface AiLadderSettlementSync {
  /** `exhausted`(网络坏了一阵)和 `refused`(云端在事实上拒收)必须分开:只有前者值得再按一次。 */
  state: 'sending' | 'waiting' | 'exhausted' | 'refused' | 'synced';
  /** 已经失败了几次 / 一共试几次 —— 「重试 2/5」里的那两个数。 */
  attempt: number;
  max_attempts: number;
  /**
   * 距下一次自动重试还有多少秒,只在 `waiting` 时是数。
   *
   * **是时长,不是时刻。** 拿服务端给的时刻去减本机的钟,差多少钟倒计时就错多少,
   * 而常年离线、没有可靠 NTP 的一体机正是钟偏最大的那一台。时长是差值,对钟偏免疫。
   */
  next_attempt_in_seconds: number | null;
  /** 排错用。屏上只在「被拒收」那一格露一次,因为那时用户需要一个能报给客服的东西。 */
  last_http_status: number | null;
  last_error: string | null;
  /**
   * 送达之后云端对这一局的裁决,只在 `synced` 时有。
   *
   * 拿不到它(盒子中途重启过、内存里那份没了)是允许的,**但不许编一个** ——
   * 那时就只刷新状态,面板消失、段位更新,少一句确认而已。
   */
  receipt?: { counted: boolean; reason: AiLadderCountingReason | null } | null;
}

export interface AiLadderBlockingGame {
  game_id: string;
  /**
   * `reserved` 和另外两个的区别不是进度,是**代价**:那一格云端登记了、盒子从没激活它,
   * 两端都还没有人拿到这盘棋,所以让位不记成绩;另外两格都要记一场负。
   * 屏上必须分得开,否则「会记为本局负」就是一句关于后果的假话。
   */
  state: 'reserved' | 'active' | 'pending_settlement';
  ownership: 'current_device' | 'other_device';
  session_id?: string;
  user_color: 'B' | 'W';
  opponent_rank_name: string;
  /** 只有 `state: 'pending_settlement'` 且这台机器有 outbox 时才有。 */
  sync?: AiLadderSettlementSync;
  /**
   * 屏上那两格诊断数,都是**时长**不是时刻(一体机的钟偏最大,时刻减本机钟差多少就错多少)。
   *
   * `null` = **那件事还没发生过**,不是「0 秒前」——「从没收到过心跳」和「刚刚收到」
   * 在屏上是相反的两件事。
   *
   * ⚠️ **它们不是判据。** 心跳早已不换取任何权限(接管窗口那一整套已删),这两个数只让
   * 屏上说得出「那台设备多久没消息了」「成绩压了多久」。拿它们当闸 = 把删掉的那套
   * 从 UI 里长回来。
   */
  heartbeat_age_seconds?: number | null;
  pending_since_seconds?: number | null;
}

export type AiLadderGameLifecycle =
  | { state: 'active'; game_id: string }
  | { state: 'pending_settlement'; game_id: string }
  /**
   * 让掉一个从没开始的预约。**没有 receipt,因为没有裁决** —— 不是「结算了但不计入」,
   * 是这一局根本没发生过。`counted` 写死 `false` 是为了让它和 `settled` 在读的时候
   * 一眼分得开,而不是靠 `receipt` 在不在。
   */
  | { state: 'released'; game_id: string; counted: false }
  | {
      state: 'settled';
      game_id: string;
      receipt: {
        counted: boolean;
        reason: AiLadderCountingReason | null;
      };
    }
  ;

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
