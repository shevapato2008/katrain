import type { GameState } from '../../api';
import { aiOpponentName, type RankTranslation } from './playerRank';

/** Presentation only: engine color identifies the seats without changing their source names. */
export function seatName(
  state: GameState,
  color: 'B' | 'W',
  engineMode = false,
  t: RankTranslation = (key, fallback) => fallback ?? key,
): string {
  const name = state.players_info[color].name;
  const engineColor = state.platform_engine_color;
  if (!engineMode || (engineColor !== 'B' && engineColor !== 'W')) return name;
  const trimmedName = name.trim();
  if (color !== engineColor) return trimmedName && trimmedName !== 'Me' ? trimmedName : t('星阵用户', '星阵用户');
  const botName = trimmedName.replace(/^\[golaxy\]\s*/i, '');
  const brand = t('Golaxy', '星阵');
  return botName ? `${brand}·${aiOpponentName(botName, t)}` : brand;
}
