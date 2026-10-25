import { formatRank } from '../../utils/rank';
import { translateResult } from '../../utils/resultTranslation';

type Translate = (key: string, fallback?: string) => string;
type Rank = string | number | null | undefined;
type Winner = 'B' | 'W';

const UNKNOWN_RANK = /^(?:unknown|no rank|null|undefined|等级未知|等級未知|未知|未记录|未記錄|unrecorded|rank not recorded|\?|—|-)$/i;
const RESIGNATION = /^R(?:esign(?:ation)?)?$/i;
const CHINESE_DIGITS = '零一二三四五六七八九';

function identityRank(value: Rank): { number: number; unit: 'p' | 'd' } | null {
  if (typeof value !== 'string') return null;
  const sgf = value.trim().match(/^(\d{1,2})\s*([pd])$/i);
  if (sgf) return { number: Number(sgf[1]), unit: sgf[2].toLowerCase() as 'p' | 'd' };
  const named = value.trim().match(/^(职业|職業|业余|業餘)\s*([一二三四五六七八九]|\d{1,2})段$/);
  if (!named) return null;
  return { number: /^\d/.test(named[2]) ? Number(named[2]) : CHINESE_DIGITS.indexOf(named[2]), unit: /职业|職業/.test(named[1]) ? 'p' : 'd' };
}

function chineseNumber(number: number): string {
  if (number < 10) return CHINESE_DIGITS[number];
  const tens = Math.floor(number / 10), ones = number % 10;
  return (tens === 1 ? '' : CHINESE_DIGITS[tens]) + '十' + (ones ? CHINESE_DIGITS[ones] : '');
}

/** Historical fields only: an absent display rank may use this record's raw rank. */
export function getListRank(displayRank: Rank, rawRank: Rank, t: Translate, lang = 'cn'): string | null {
  for (const rank of [displayRank, rawRank]) {
    const label = formatRank(rank, t);
    if (!label || UNKNOWN_RANK.test(label)) continue;
    if (lang !== 'cn' && lang !== 'tw') return label;
    let identity = identityRank(rank);
    // Qualify a bare display label only from an agreeing, typed same-record
    // raw value. Names and the current account never establish identity.
    const bare = label.match(/^([一二三四五六七八九]|\d{1,2})段$/);
    const rawIdentity = identityRank(rawRank);
    const number = bare ? (/^\d/.test(bare[1]) ? Number(bare[1]) : CHINESE_DIGITS.indexOf(bare[1])) : null;
    if (!identity && rawIdentity?.number === number) identity = rawIdentity;
    if (!identity) return label;
    return identity.unit === 'p'
      ? (lang === 'tw' ? '職業' : '职业') + chineseNumber(identity.number) + '段'
      : (lang === 'tw' ? '業餘' : '业余') + identity.number + '段';
  }
  return null;
}

const chineseSide = (side: string): Winner => side === '黑' ? 'B' : 'W';

function resignationWinner(raw: string): Winner | null {
  const sgf = raw.match(/^([BW])\+(.+)$/i);
  if (sgf && RESIGNATION.test(sgf[2])) return sgf[1].toUpperCase() as Winner;

  const win = raw.match(/^(黑|白)(?:棋)?(?:中[盘盤][胜勝]|[胜勝]中[盘盤])$/);
  if (win) return chineseSide(win[1]);
  const loser = raw.match(/^(黑|白)(?:棋)?[认認][输輸]$/);
  return loser ? loser[1] === '黑' ? 'W' : 'B' : null;
}

/** Recognize complete results, never just the first color in an arbitrary string. */
function otherWinner(raw: string): Winner | null {
  const sgf = raw.match(/^([BW])\+(?:T(?:ime)?|F(?:orfeit)?|\d+(?:\.\d+)?)$/i);
  if (sgf) return sgf[1].toUpperCase() as Winner;

  const win = raw.match(/^(黑|白)\s*[胜勝]$/);
  return win ? chineseSide(win[1]) : null;
}

/** List-only Chinese resignation wording; all other labels retain the shared formatter. */
export function listResult(
  raw: string | null | undefined,
  t: Translate,
  rules: string | null | undefined,
  lang: string,
): { label: string; winner: Winner | null } {
  const result = raw?.trim() ?? '';
  const resignedWinner = resignationWinner(result);
  if (resignedWinner && (lang === 'cn' || lang === 'tw')) {
    const color = resignedWinner === 'B' ? t('review:black', '黑') : t('review:white', '白');
    const by = t('review:by_resign', lang === 'tw' ? '中盤' : '中盘');
    const win = t('review:win', lang === 'tw' ? '勝' : '胜');
    return { label: `${color}${by}${win}`, winner: resignedWinner };
  }
  return { label: translateResult(raw, t, rules), winner: resignedWinner ?? otherWinner(result) };
}
