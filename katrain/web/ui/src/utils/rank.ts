/**
 * Rank display.
 *
 * Ranks reach the UI in two shapes and both have to render as 级 / 段:
 *  - a stored SGF-style string, "6k" / "3d", written by the server (`black_rank`,
 *    `white_rank`) — language-neutral on purpose, because the server's i18n language is
 *    a process-global that any session can switch, so a localized string written into
 *    the database would record some other user's language and could never be re-localized;
 *  - KaTrain's numeric scale, where 6 kyu is -5 and 3 dan is 3 (`calculated_rank`).
 *
 * Professional SGF ranks ("5p") use a separate localized template. Anything else
 * is passed through untouched. Imported SGFs carry free-text ranks
 * ("业5", "5級", "amateur 3 dan", "?") that we must not mangle into something wrong.
 */

type Translate = (key: string, defaultText?: string) => string;
type Rank = string | number | null | undefined;

/** "6k" / "3d" / professional "5p", case-insensitive. */
const SGF_RANK = /^\s*(\d{1,2})\s*([kdpKDP])\s*$/;
const CHINESE_DAN = /^\s*([一二三四五六七八九]|\d{1,2})段\s*$/;
const CHINESE_NUMERAL = '一二三四五六七八九';
const NAMED_RANK = /^\s*(职业|職業|业余|業餘)\s*([一二三四五六七八九]|\d{1,2})段\s*$/;
const UNKNOWN_RANK = /^(?:unknown|no rank|null|undefined|等级未知|等級未知|未知|未记录|未記錄|unrecorded|rank not recorded|\?|—|-)$/i;

function rankNumber(value: string): number {
  return /^\d/.test(value) ? Number(value) : CHINESE_NUMERAL.indexOf(value) + 1;
}

function chineseNumber(number: number): string {
  if (number < 10) return CHINESE_NUMERAL[number - 1] ?? String(number);
  const tens = Math.floor(number / 10), ones = number % 10;
  return (tens === 1 ? '' : CHINESE_NUMERAL[tens - 1]) + '十' + (ones ? CHINESE_NUMERAL[ones - 1] : '');
}

function professionalRank(number: number, t: Translate): string {
  const template = t('strength:professional_dan_format', '职业{rank}段');
  return template.replace('{rank}', /职业|職業/.test(template) ? chineseNumber(number) : String(number));
}

const units = (t: Translate) => ({
  k: t('strength:kyu', '级'),
  d: t('strength:dan', '段'),
});

/**
 * Localized rank label, or '' when there is no rank to show.
 *
 * Callers decide what an empty result means — most render the name alone rather than
 * an empty separator. A rank is never invented: an unknown value renders as itself, and
 * a missing one renders as nothing.
 */
export function formatRank(value: Rank, t: Translate): string {
  if (value === null || value === undefined || value === '') return '';

  const u = units(t);

  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return '';
    // Same split as katrain.core.lang.rank_key: >= 0.5 is dan, below is kyu.
    return value >= 0.5 ? `${Math.round(value)}${u.d}` : `${Math.round(1 - value)}${u.k}`;
  }

  const chinese = CHINESE_DAN.exec(value);
  if (chinese) {
    return u.d === '段' ? chinese[0].trim() : `${rankNumber(chinese[1])}${u.d}`;
  }

  const named = NAMED_RANK.exec(value);
  if (named && /职业|職業/.test(named[1])) return professionalRank(rankNumber(named[2]), t);

  const m = SGF_RANK.exec(value);
  if (!m) return value.trim();
  if (m[2].toLowerCase() === 'p') {
    return professionalRank(Number(m[1]), t);
  }
  return `${m[1]}${m[2].toLowerCase() === 'd' ? u.d : u.k}`;
}

/** Validated API display ranks win; a raw legacy d fallback does not prove amateur status. */
export function formatKifuRank(displayRank: Rank, rawRank: Rank, t: Translate, lang = 'cn'): string | null {
  for (const [index, rank] of [displayRank, rawRank].entries()) {
    const label = formatRank(rank, t);
    if (!label || UNKNOWN_RANK.test(label)) continue;
    if (lang !== 'cn' && lang !== 'tw') return label;
    const named = typeof rank === 'string' ? NAMED_RANK.exec(rank) : null;
    const sgf = typeof rank === 'string' ? SGF_RANK.exec(rank) : null;
    const unit = named ? (/职业|職業/.test(named[1]) ? 'p' : 'd') : sgf?.[2].toLowerCase();
    const number = named ? rankNumber(named[2]) : sgf ? Number(sgf[1]) : null;
    if (number != null && unit === 'p') return chineseNumber(number) + '段';
    if (number != null && unit === 'd' && (index === 0 || named)) return (lang === 'tw' ? '業餘' : '业余') + number + '段';
    const bare = label.match(/^([一二三四五六七八九]|\d{1,2})段$/);
    if (index === 0 && bare) return chineseNumber(rankNumber(bare[1])) + '段';
    return label;
  }
  return null;
}

/**
 * "AI · 6级" style label. Returns the name alone when the rank is absent or unreadable,
 * never a dangling separator.
 */
export function withRank(
  name: string,
  rank: string | number | null | undefined,
  t: Translate,
  separator = ' · ',
): string {
  const label = formatRank(rank, t);
  return label ? `${name}${separator}${label}` : name;
}
