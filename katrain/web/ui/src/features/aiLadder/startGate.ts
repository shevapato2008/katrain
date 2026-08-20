import type { AiLadderBlockingGame, AiLadderStatus } from './types';

export type AiLadderStartBlock =
  | 'not_ready'
  | 'blocking_game'
  | 'pending_settlement'
  | 'no_opponent'
  | 'rung_not_certified';

/**
 * 那一局挡着新局的棋,或者 null。
 *
 * 只是把 `view_state` 那一层收窄搬到一处 —— 调用方不先收窄就读不到 `blocking_game`,
 * 而每个调用方各收窄一次,正是这个字段此前在 kiosk 上被整个漏掉的方式。
 */
export const aiLadderBlockingGame = (status: AiLadderStatus): AiLadderBlockingGame | null =>
  (status.view_state === 'ready' ? status.blocking_game : null) ?? null;

/**
 * 这个档位本身能不能坐上去 —— 与「此刻能不能开局」是两个问题。
 *
 * 分开命名是因为两个调用方(状态卡、对手卡)问的一直是这一个,它们从前拿
 * `aiLadderStartBlock(...) === 'rung_not_certified'` 当它用;等到「有一局挡着」也进了
 * 那个返回值,同一句写法就会在挡局时把「该档位暂不可挑战」整句吞掉 —— 一条与档位无关的
 * 原因,顺手改掉了一句关于档位的事实。
 */
export const isRungUnseatable = (status: AiLadderStatus): boolean => {
  if (status.view_state !== 'ready') return false;
  const opponent = status.current_opponent;
  if (!opponent) return false;
  const certified = opponent.certification_status === 'certified' && opponent.availability === 'available';
  return !certified && !status.provisional_play_allowed;
};

/**
 * Why the 开始对弈 button is disabled, or null when it is not.
 *
 * Both setup pages spelled this out inline, which is how they came to disagree with the
 * server: a rung that is not certified normally cannot be seated, EXCEPT on a node that
 * has been switched into provisional play — and the client cannot infer that from the
 * rung, because the rung's own status is the same either way. The server says which it
 * is (`provisional_play_allowed`); this reads it rather than guessing.
 *
 * `blocking_game` 排在 `pending_settlement` 之前,而且是这里**唯一**新增的一格。
 * 从前它一个字都不看:另一台设备正在下的时候,云端的 `pending_settlement` 是假的
 * (那个布尔只在「下完了、成绩在送」时为真),于是 kiosk 的开始按钮是可点的 —— 点下去
 * 才被服务端一个 409 顶回来。屏上先答应、服务端再否决,是这块屏最不该有的顺序。
 *
 * 两者同时成立时(挡着的那一局本身就是 `pending_settlement`)以前者为准:它带着**是哪一局**,
 * 调用方据此能摆出那一格真正的出路(立即重试 / 认输 / 让掉);那个布尔只够说一句「等着」。
 */
export const aiLadderStartBlock = (status: AiLadderStatus): AiLadderStartBlock | null => {
  if (status.view_state !== 'ready') return 'not_ready';
  if (aiLadderBlockingGame(status)) return 'blocking_game';
  if (status.pending_settlement) return 'pending_settlement';
  if (!status.current_opponent) return 'no_opponent';
  if (isRungUnseatable(status)) return 'rung_not_certified';
  return null;
};

export const canStartAiLadderGame = (status: AiLadderStatus): boolean => aiLadderStartBlock(status) === null;

/**
 * True when the game about to be played runs on a rung whose strength was never measured.
 *
 * The game is played and recorded but does NOT count: the switch decides whether an
 * uncertified rung may be SEATED, never whether its result may move a rank. The server
 * refuses to bank it (`opponent_not_eligible`, ai_ladder_ranked.py) and the ledger CHECK
 * constraint refuses to store a counted row against an uncertified opponent. So the UI has
 * to say so — see AI_LADDER_COPY.provisionalSeating, which is the honest wording.
 */
export const isProvisionalSeating = (status: AiLadderStatus): boolean => {
  if (status.view_state !== 'ready' || !status.provisional_play_allowed) return false;
  const opponent = status.current_opponent;
  if (!opponent) return false;
  return opponent.certification_status !== 'certified' || opponent.availability !== 'available';
};
