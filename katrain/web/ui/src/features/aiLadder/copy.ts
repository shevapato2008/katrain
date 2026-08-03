import type {
  AiLadderCertificationStatus,
  AiLadderRankedOutcome,
  AiLadderRoute,
} from './types';

export const AI_LADDER_COPY = {
  title: 'AI升降级对弈',
  loading: '正在加载升降级对弈状态…',
  loadError: '升降级对弈状态加载失败',
  retry: '重试',
  currentOpponentPrefix: '当前对手：',
  currentRankPrefix: '当前段位：',
  available: '可挑战',
  unavailable: '该档位暂不可挑战',
  unavailableCta: '暂不可挑战',
  continuePlacementCta: '继续定级',
  startRankedCta: '开始升降级对弈',
  pendingSettlement: '本盘成绩结算中',
  pendingSettlementCta: '成绩结算中',
  recentResultsHeading: '最近5盘',
  recentResults: '最近5盘升降级AI对局结果',
  recentResultsNote: '最近5盘仅供展示，升降段只看累计净胜分',
  noRecentResults: '暂无升降级AI对局记录',
  netScorePrefix: '累计净胜分：',
  netScoreMeterLabel: '累计净胜分，负值朝降段方向，正值朝升段方向',
  demotionThreshold: '降段 -3',
  promotionThreshold: '升段 +3',
  route: {
    local: '本机对弈',
    server: '服务器对弈',
  } satisfies Record<AiLadderRoute, string>,
  certification: {
    provisional: '暂定',
    certified: '已认证',
  } satisfies Record<AiLadderCertificationStatus, string>,
  outcome: {
    win: '胜',
    loss: '负',
  } satisfies Record<AiLadderRankedOutcome, string>,
} as const;

export const formatPlacementProgress = (completed: number, total: number) => `定级进度 ${completed}/${total}`;

export const formatPlacementProgressLabel = (completed: number, total: number) =>
  `定级进度：已完成${completed}盘，共${total}盘`;

export const formatNetScore = (score: number) => `${AI_LADDER_COPY.netScorePrefix}${score > 0 ? '+' : ''}${score}`;

export const formatNetScoreValueText = (score: number) => {
  if (score > 0) return `当前累计净胜分+${score}，正值朝升段方向，达到+3升段`;
  if (score < 0) return `当前累计净胜分${score}，负值朝降段方向，达到-3降段`;
  return '当前累计净胜分0，达到+3升段，达到-3降段';
};

export const formatOutcomeLabel = (index: number, outcome: AiLadderRankedOutcome) =>
  `第${index + 1}盘：${AI_LADDER_COPY.outcome[outcome]}`;
