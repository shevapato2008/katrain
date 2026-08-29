import { i18n } from '../../i18n';
import type {
  AiLadderCertificationStatus,
  AiLadderRankedOutcome,
  AiLadderRoute,
} from './types';

// Every string below is a getter, not a value: the module is imported once but the UI
// language can change at any time, so the lookup has to happen at render. Components that
// read these MUST also call useTranslation() — that hook is what re-renders them when
// i18n.notify() fires. The second argument is the Chinese source text, which doubles as the
// fallback whenever a locale has no entry (and as what the vitest suite sees).
export const AI_LADDER_COPY = {
  get title() { return i18n.t('ladder:title', 'AI升降级对弈'); },
  get setupTitle() { return i18n.t('ladder:setup_title', '41档升降级AI'); },
  get placementOpponentPrefix() { return i18n.t('ladder:placement_opponent_prefix', '定级对手：'); },
  get rankedOpponentPrefix() { return i18n.t('ladder:game_opponent_prefix', '本局对手：'); },
  get loading() { return i18n.t('ladder:loading_status', '正在加载升降级对弈状态…'); },
  get loadError() { return i18n.t('ladder:load_error', '升降级对弈状态加载失败'); },
  // The backend's `detail` is English and written for operators; it used to be rendered
  // verbatim on a Chinese kiosk. These say the same thing to the person holding the board.
  get loadErrorNotAuthoritative() { return i18n.t('ladder:load_error_not_authoritative', '本机不记升降级成绩，暂时无法开始升降级对弈'); },
  get loadErrorUnauthorized() { return i18n.t('ladder:load_error_unauthorized', '登录已失效，请重新登录后再试'); },
  get retry() { return i18n.t('ladder:retry', '重试'); },
  // Seating and scoring are separate decisions: this node will let you play an
  // uncertified rung, but a rank earned against unmeasured strength is not recorded
  // (the ledger's own CHECK constraint refuses it). Say so before the game, not after.
  get provisionalSeating() { return i18n.t('ladder:provisional_seating', '该档位尚未标定，可以试下，但本局不计入升降级'); },
  get currentOpponentPrefix() { return i18n.t('ladder:current_opponent_prefix', '当前对手：'); },
  // 屏 03 那句话:**为什么这一格不给挑**。稿子把它和「你是几级、配到第几档」写成一句 ——
  // 挑得动对手强弱的升降级不是升降级,这是规则本身,不是这台机器的限制。
  // 放在这里而不是那一屏里:升降级的词只许有一套(和平台名那次是同一条判据)。
  get boxPicksReason() { return i18n.t('ladder:box_picks_reason', '能挑对手强弱,升降级就不是升降级了'); },
  get currentRankPrefix() { return i18n.t('ladder:current_rank_prefix', '当前段位：'); },
  get available() { return i18n.t('ladder:available', '可挑战'); },
  get unavailable() { return i18n.t('ladder:unavailable_rung', '该档位暂不可挑战'); },
  get unavailableCta() { return i18n.t('ladder:unavailable_cta', '暂不可挑战'); },
  get continuePlacementCta() { return i18n.t('ladder:continue_placement_cta', '继续定级'); },
  get startRankedCta() { return i18n.t('ladder:start_ranked_cta', '开始升降级对弈'); },
  // 状态,不是进行时 —— 这块屏拿不到盒子的 outbox,`waiting`/`exhausted`/`refused`
  // 在它眼里一样,所以只能说在三种状态下**都为真**的那句话。被永久拒收的那一局,
  // 旧文案会让屏上永远写着「结算中」。(挡局面板另有 `sync` 那一行说得出实况。)
  get pendingSettlement() { return i18n.t('ladder:pending_settlement', '本盘成绩还没送到云端'); },
  get pendingSettlementCta() { return i18n.t('ladder:pending_settlement_cta', '成绩未送达'); },
  get recentResultsHeading() { return i18n.t('ladder:recent_heading', '最近5盘'); },
  get recentResults() { return i18n.t('ladder:recent_aria', '最近5盘升降级AI对局结果'); },
  get recentResultsNote() { return i18n.t('ladder:recent_display_note', '最近5盘仅供展示，升降段只看累计净胜分'); },
  get noRecentResults() { return i18n.t('ladder:recent_empty', '暂无升降级AI对局记录'); },
  get netScorePrefix() { return i18n.t('ladder:net_score_prefix', '累计净胜分：'); },
  get netScoreMeterLabel() { return i18n.t('ladder:net_score_aria', '累计净胜分，负值朝降段方向，正值朝升段方向'); },
  get demotionThreshold() { return i18n.t('ladder:demotion_threshold', '降段 -3'); },
  get promotionThreshold() { return i18n.t('ladder:promotion_threshold', '升段 +3'); },
  get route(): Record<AiLadderRoute, string> {
    return {
      local: i18n.t('ladder:route_local', '本机对弈'),
      server: i18n.t('ladder:route_server', '服务器对弈'),
    };
  },
  get certification(): Record<AiLadderCertificationStatus, string> {
    return {
      provisional: i18n.t('ladder:cert_provisional', '暂定'),
      certified: i18n.t('ladder:cert_certified', '已认证'),
    };
  },
  get outcome(): Record<AiLadderRankedOutcome, string> {
    return {
      win: i18n.t('ladder:win', '胜'),
      loss: i18n.t('ladder:loss', '负'),
    };
  },
};

// The frontend's own substitution is String.replace, which only replaces the FIRST
// occurrence — so every placeholder appears exactly once per string, in every language.
const fill = (text: string, values: Record<string, string | number>) =>
  Object.entries(values).reduce((acc, [key, value]) => acc.replace(`{${key}}`, String(value)), text);

export const formatPlacementProgress = (completed: number, total: number) =>
  fill(i18n.t('ladder:placement_progress_n', '定级进度 {n}/{total}'), { n: completed, total });

export const formatPlacementProgressLabel = (completed: number, total: number) =>
  fill(i18n.t('ladder:placement_progress_aria', '定级进度：已完成{n}盘，共{total}盘'), { n: completed, total });

export const formatNetScore = (score: number) => `${AI_LADDER_COPY.netScorePrefix}${score > 0 ? '+' : ''}${score}`;

export const formatNetScoreValueText = (score: number) => {
  if (score > 0) return fill(i18n.t('ladder:net_score_positive', '当前累计净胜分+{n}，正值朝升段方向，达到+3升段'), { n: score });
  if (score < 0) return fill(i18n.t('ladder:net_score_negative', '当前累计净胜分{n}，负值朝降段方向，达到-3降段'), { n: score });
  return i18n.t('ladder:net_score_zero', '当前累计净胜分0，达到+3升段，达到-3降段');
};

export const formatOutcomeLabel = (index: number, outcome: AiLadderRankedOutcome) =>
  fill(i18n.t('ladder:outcome_label', '第{n}盘：{result}'), { n: index + 1, result: AI_LADDER_COPY.outcome[outcome] });

// Settlement feedback is produced by a pure function (settlement.ts), so the strings live
// here with the rest of the ladder copy rather than being inlined at the call site.
export const settlementCopy = {
  authoritativeComplete: () => i18n.t('ladder:settled_generic', '升降级结算已完成，当前状态已更新'),
  placementComplete: (rank: string) =>
    fill(i18n.t('ladder:settled_placement_done', '定级完成：{rank}'), { rank }),
  placementProgress: (completed: number, total: number) =>
    fill(i18n.t('ladder:settled_placement_progress', '定级中 {n}/{total}'), { n: completed, total }),
  promotion: (rank: string) => fill(i18n.t('ladder:settled_promoted', '升级：{rank}'), { rank }),
  demotion: (rank: string) => fill(i18n.t('ladder:settled_demoted', '降级：{rank}'), { rank }),
  scoreChange: (score: string) => `${AI_LADDER_COPY.netScorePrefix}${score}`,
  noChange: (score: string) =>
    fill(i18n.t('ladder:settled_no_change', '段位未变化，累计净胜分：{score}'), { score }),
  pending: () => i18n.t('ladder:settled_pending', '升降级结算仍在处理中'),
  unavailable: () => i18n.t('ladder:settled_unavailable', '结算状态暂不可用'),
};
