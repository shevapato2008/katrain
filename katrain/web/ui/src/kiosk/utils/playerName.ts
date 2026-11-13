import type { GameState } from '../../api';
import { aiOpponentName, type RankTranslation } from './playerRank';

/** Presentation only: engine color identifies the seats without changing their source names. */
export function seatName(
  state: GameState,
  color: 'B' | 'W',
  engineMode = false,
  currentUserName?: string,
  t: RankTranslation = (key, fallback) => fallback ?? key,
): string {
  const name = state.players_info[color].name;
  const engineColor = state.platform_engine_color;
  if (!engineMode || (engineColor !== 'B' && engineColor !== 'W')) return name;
  if (color !== engineColor) return currentUserName?.trim() || t('game:me', '我');
  const botName = name.trim().replace(/^\[golaxy\]\s*/i, '');
  const brand = t('Golaxy', '星阵');
  return botName ? `${brand}·${aiOpponentName(botName, t)}` : brand;
}
