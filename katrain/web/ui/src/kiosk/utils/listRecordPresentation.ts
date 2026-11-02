import { formatKifuRank } from '../../utils/rank';
import { translateResult } from '../../utils/resultTranslation';

type Translate = (key: string, fallback?: string) => string;
type Rank = string | number | null | undefined;
type Winner = 'B' | 'W';

const RESIGNATION = /^R(?:esign(?:ation)?)?$/i;

/** Saved user-game d ranks retain their established amateur meaning. */
export function getListRank(displayRank: Rank, rawRank: Rank, t: Translate, lang = 'cn'): string | null {
  return formatKifuRank(displayRank ?? rawRank, rawRank, t, lang);
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
  const sgf = raw.match(/^([BW])\+(?:T(?:ime)?|F(?:orfeit)?|\d+(?:\.\d+)?)?$/i);
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
