import type { AiLadderStatus } from './types';

export type AiLadderStartBlock =
  | 'not_ready'
  | 'pending_settlement'
  | 'no_opponent'
  | 'rung_not_certified';

/**
 * Why the 开始对弈 button is disabled, or null when it is not.
 *
 * Both setup pages spelled this out inline, which is how they came to disagree with the
 * server: a rung that is not certified normally cannot be seated, EXCEPT on a node that
 * has been switched into provisional play — and the client cannot infer that from the
 * rung, because the rung's own status is the same either way. The server says which it
 * is (`provisional_play_allowed`); this reads it rather than guessing.
 */
export const aiLadderStartBlock = (status: AiLadderStatus): AiLadderStartBlock | null => {
  if (status.view_state !== 'ready') return 'not_ready';
  if (status.pending_settlement) return 'pending_settlement';
  const opponent = status.current_opponent;
  if (!opponent) return 'no_opponent';
  const certified = opponent.certification_status === 'certified' && opponent.availability === 'available';
  if (!certified && !status.provisional_play_allowed) return 'rung_not_certified';
  return null;
};

export const canStartAiLadderGame = (status: AiLadderStatus): boolean => aiLadderStartBlock(status) === null;

/**
 * True when the game about to be played runs on a rung whose strength was never measured.
 * The game still counts — that is the point of the switch — so the UI has to say so.
 */
export const isProvisionalSeating = (status: AiLadderStatus): boolean => {
  if (status.view_state !== 'ready' || !status.provisional_play_allowed) return false;
  const opponent = status.current_opponent;
  if (!opponent) return false;
  return opponent.certification_status !== 'certified' || opponent.availability !== 'available';
};
