import type { GameState } from '../../api';

export interface PlayerRank { label: string; title: string }
export type PlayerRanks = Partial<Record<'B' | 'W', PlayerRank>>;
export const UNKNOWN_RANK: PlayerRank = { label: '等级未知', title: '等级未知' };

/** Labels from SGF/platform/catalog are already on their own scale. Never parseInt them. */
export function knownRank(value: unknown, source?: string): PlayerRank {
  if (typeof value !== 'string' || !value.trim() || /^(no rank|unknown|null|undefined|—|-)$/i.test(value.trim())) return UNKNOWN_RANK;
  const label = value.trim();
  return { label, title: source ? `${source} · ${label}` : label };
}

export function accountRank(value: unknown): PlayerRank {
  const placement = (value as { placement_state?: { phase?: string; rung?: { rank_name?: unknown } } } | null)?.placement_state;
  if (placement?.phase === 'placement') return { label: '尚未定级', title: '账号尚未定级' };
  if (placement?.phase !== 'placed') return UNKNOWN_RANK;
  const label = placement.rung?.rank_name;
  return typeof label === 'string' && /^(?:(?:业余|职业)\s*)?(?:\d+\s*[kdp级級段]|[一二三四五六七八九十]+段)$/i.test(label.trim())
    ? knownRank(label, '账号等级') : UNKNOWN_RANK;
}

export function seatRank(state: GameState, color: 'B' | 'W', engineMode = false, lang = 'cn'): PlayerRank {
  const platform = engineMode || state.game_type === 'pvp_online' || !!state.platform_engine_color || !!state.platform_my_color;
  if (platform) return knownRank(state.platform_player_ranks?.[color], color === state.platform_engine_color ? 'AI 难度' : '平台等级');
  const info = state.players_info[color];
  if (info?.player_type !== 'ai' && info?.player_type !== 'player:ai') return UNKNOWN_RANK;
  const catalog = knownRank(info.rank_display, 'AI 难度');
  if (catalog !== UNKNOWN_RANK) return catalog;
  const raw: unknown = info.calculated_rank;
  let label: string;
  if (typeof raw === 'number' || typeof raw === 'string' && /^-?\d+(?:\.\d+)?$/.test(raw.trim())) {
    const number = Number(raw);
    if (!Number.isFinite(number)) return UNKNOWN_RANK;
    label = number <= 0 ? `${1 - number}k` : `${number}d`;
  } else if (typeof raw === 'string') label = raw.trim();
  else return UNKNOWN_RANK;
  const match = label.match(/^(\d+)([kd])$/i);
  const units: Record<string, [string, string]> = { cn: ['级', '段'], tw: ['级', '段'], jp: ['級', '段'], ko: ['급', '단'] };
  if (match && units[lang]) label = `${match[1]}${units[lang][match[2].toLowerCase() === 'k' ? 0 : 1]}`;
  return knownRank(label, 'AI 估计难度');
}
