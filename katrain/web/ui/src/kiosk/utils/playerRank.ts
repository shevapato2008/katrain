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
  return typeof label === 'string' && /^(?:(?:(?:业余|职业)\s*)?准?(?:\d+\s*[kdp级級段]|[一二三四五六七八九十]+段)|职业|职业顶尖|超职业|KataGo中等)$/i.test(label.trim())
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

export type RankTranslation = (key: string, fallback?: string) => string;
const sourceText: RankTranslation = (key, fallback) => fallback ?? key;

/** Only canonical app rank labels are presentation data. Custom/SGF ranks pass through. */
export function rankLabel(value: string, t: RankTranslation = sourceText): string {
  const special: Record<string, [string, string]> = {
    '职业': ['rank:professional', '职业'],
    '职业顶尖': ['rank:top_professional', '职业顶尖'],
    '超职业': ['rank:super_professional', '超职业'],
    'KataGo中等': ['rank:katago_medium', 'KataGo中等'],
    '等级未知': ['rank:unknown', '等级未知'],
    '尚未定级': ['rank:unrated', '尚未定级'],
    '职业/野狐9D+': ['rank:pro_fox_reference', '职业/野狐9D+'],
    '野狐9D': ['rank:fox_reference', '野狐9D'],
  };
  const matchSpecial = Object.prototype.hasOwnProperty.call(special, value) ? special[value] : undefined;
  if (matchSpecial) return t(...matchSpecial);
  const star = value.match(/^星阵(\d+)星$/);
  if (star) return t('rank:golaxy_stars', '星阵{n}星').replace('{n}', star[1]);
  // Keep canonical source spelling/spacing when the active catalog uses source units.
  if (t('rank:kyu', '{n}级') === '{n}级' && t('rank:dan', '{n}段') === '{n}段') return value;
  const match = value.match(/^(业余\s*|职业\s*)?(准)?(\d+)\s*([kKdDpP级級段])$/);
  if (!match) return value;
  const [, scale, provisional, n, unit] = match;
  let rank = /[kK级級]/.test(unit)
    ? t('rank:kyu', '{n}级').replace('{n}', n)
    : /[pP]/.test(unit) ? t('rank:pro', '{n}职业段').replace('{n}', n)
      : t('rank:dan', '{n}段').replace('{n}', n);
  if (provisional) rank = t('rank:provisional', '准{rank}').replace('{rank}', rank);
  if (scale) rank = (scale.trim() === '业余' ? t('rank:amateur', '业余 {rank}') : t('rank:professional_rank', '职业 {rank}')).replace('{rank}', rank);
  return rank;
}

/** Translate at the render boundary; rank state and the source label stay unchanged. */
export function presentPlayerRank(rank: PlayerRank, t: RankTranslation): PlayerRank {
  const sources: Record<string, [string, string]> = {
    '账号等级': ['rank:account_source', '账号等级'],
    'AI 难度': ['rank:ai_source', 'AI 难度'],
    '平台等级': ['rank:platform_source', '平台等级'],
    'AI 估计难度': ['rank:ai_estimate', 'AI 估计难度'],
  };
  const owned = rank.title === '账号尚未定级' || Object.keys(sources).some((source) => rank.title === `${source} · ${rank.label}`);
  const label = owned || rank.label === UNKNOWN_RANK.label ? rankLabel(rank.label, t) : rank.label;
  if (rank.title === '账号尚未定级') return { label, title: t('rank:account_unrated', '账号尚未定级') };
  const source = Object.keys(sources).find((value) => rank.title === `${value} · ${rank.label}`);
  return { label, title: source ? `${t(...sources[source])} · ${label}` : rank.title === rank.label ? label : rank.title };
}

const GOLAXY_AI_NAMES = new Set([
  "星猛虎",
  "星雄狮",
  "星巨象",
  "星壮牛",
  "星蓝鲸",
  "星美鹿",
  "星孤狼",
  "星奇豚",
  "星萌猪",
  "星骏马",
  "星呆羊",
  "星跳鼠",
  "星云鹤",
  "星灵狐",
  "星白鹭",
  "星智狗",
  "星巧猫",
  "星皮猴",
  "星乖兔",
  "星树熊",
  "星长蛇",
  "星铠虾",
  "星夜鹰",
  "星憨鹅",
  "星刺头",
  "星黄鸭",
  "星轻燕",
  "星绿蛙",
  "星老龟",
  "星钳蟹",
  "星尾鱼",
  "星敏螳",
  "星鸣蝉",
  "星飞蜓",
  "星舞蝶",
  "星忙蜂",
  "星慢蜗",
  "星花虫",
  "星小蚁",
]);
export function aiOpponentName(value: string, t: RankTranslation): string {
  return GOLAXY_AI_NAMES.has(value) ? t(value, value) : value;
}
