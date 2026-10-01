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

/** "6k" / "3d" / professional "5p", case-insensitive. */
const SGF_RANK = /^\s*(\d{1,2})\s*([kdpKDP])\s*$/;
const CHINESE_DAN = /^\s*([一二三四五六七八九])段\s*$/;
const CHINESE_NUMERAL = '一二三四五六七八九';

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
export function formatRank(value: string | number | null | undefined, t: Translate): string {
  if (value === null || value === undefined || value === '') return '';

  const u = units(t);

  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return '';
    // Same split as katrain.core.lang.rank_key: >= 0.5 is dan, below is kyu.
    return value >= 0.5 ? `${Math.round(value)}${u.d}` : `${Math.round(1 - value)}${u.k}`;
  }

  const chinese = CHINESE_DAN.exec(value);
  if (chinese) {
    return u.d === '段' ? chinese[0].trim() : `${CHINESE_NUMERAL.indexOf(chinese[1]) + 1}${u.d}`;
  }

  const m = SGF_RANK.exec(value);
  if (!m) return value.trim();
  if (m[2].toLowerCase() === 'p') {
    return t('strength:professional_dan_format', '职业{rank}段').replace('{rank}', m[1]);
  }
  return `${m[1]}${m[2].toLowerCase() === 'd' ? u.d : u.k}`;
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
