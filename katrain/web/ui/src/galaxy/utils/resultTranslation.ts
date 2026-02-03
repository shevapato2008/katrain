/**
 * Translate SGF game result strings into localized text.
 *
 * Handles:
 *   Standard SGF: B+R, W+R, B+T, W+T, B+F, W+F, B+2.5, W+0.5, Draw
 *   Chinese:      黑中盘胜, 白中盘胜, 黑胜2又3/4子, 白胜1/4子, 黑胜2.5, etc.
 *
 * The `rules` parameter determines the points unit:
 *   "chinese"  → 子 (area scoring, 1子 ≈ 2目)
 *   "japanese" / "korean" → 目 (territory scoring)
 *   null/unknown → no unit suffix
 */

type TFn = (key: string, fallback?: string) => string;

/** Parse Chinese fractional notation like "2又3/4" → 2.75, "1/4" → 0.25 */
function parseChinese(numStr: string): number | null {
  // "2又3/4" style
  const mixedFrac = numStr.match(/^(\d+)又(\d+)\/(\d+)/);
  if (mixedFrac) {
    return Number(mixedFrac[1]) + Number(mixedFrac[2]) / Number(mixedFrac[3]);
  }

  // Pure fraction "3/4"
  const frac = numStr.match(/^(\d+)\/(\d+)/);
  if (frac) {
    return Number(frac[1]) / Number(frac[2]);
  }

  // Chinese full-text fraction "四分之一"
  const zhFrac = numStr.match(/^([一二三四五六七八九十]+)分之([一二三四五六七八九十]+)/);
  if (zhFrac) {
    const denom = zhDigit(zhFrac[1]);
    const numer = zhDigit(zhFrac[2]);
    if (denom && numer) return numer / denom;
  }

  // Mixed "二又四分之一"
  const zhMixed = numStr.match(/^([一二三四五六七八九十]+)又([一二三四五六七八九十]+)分之([一二三四五六七八九十]+)/);
  if (zhMixed) {
    const whole = zhDigit(zhMixed[1]);
    const denom = zhDigit(zhMixed[2]);
    const numer = zhDigit(zhMixed[3]);
    if (whole != null && denom && numer) return whole + numer / denom;
  }

  // "3目半" → 3.5
  const moban = numStr.match(/^(\d+)目半/);
  if (moban) {
    return Number(moban[1]) + 0.5;
  }

  // Decimal "2.5"
  const decimal = numStr.match(/^(\d+(?:\.\d+)?)/);
  if (decimal) {
    return Number(decimal[1]);
  }

  return null;
}

function zhDigit(s: string): number | null {
  const map: Record<string, number> = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
  };
  return map[s] ?? null;
}

/**
 * Detect the original unit from a Chinese result string.
 * Returns 'zi', 'moku', or null if no explicit unit found.
 */
function detectChineseUnit(s: string): 'zi' | 'moku' | null {
  if (/子/.test(s)) return 'zi';
  if (/目/.test(s)) return 'moku';
  if (/点/.test(s)) return 'moku'; // 点 is used like 目 in some sources
  return null;
}

/**
 * Get the points unit suffix based on rules and/or the original unit from data.
 *
 * Priority:
 * 1. If the original data had an explicit unit (子/目), trust it
 * 2. Otherwise use rules: chinese → zi, japanese/korean → moku
 * 3. If rules unknown, no unit suffix
 */
function pointsUnit(t: TFn, rules: string | null | undefined, originalUnit: 'zi' | 'moku' | null): string {
  const unit = originalUnit ?? rulesUnit(rules);
  if (unit === 'zi') return t('result:points_zi', '');
  if (unit === 'moku') return t('result:points_moku', '');
  return '';
}

function rulesUnit(rules: string | null | undefined): 'zi' | 'moku' | null {
  if (!rules) return null;
  const r = rules.toLowerCase();
  if (r === 'chinese' || r === 'cn') return 'zi';
  if (r === 'japanese' || r === 'jp' || r === 'korean' || r === 'ko') return 'moku';
  return null;
}

export function translateResult(
  result: string | null | undefined,
  t: TFn,
  rules?: string | null,
): string {
  if (!result) return '?';

  const r = result.trim();

  // ── Standard SGF format: "B+R", "W+2.5", etc. ──
  const sgfMatch = r.match(/^([BW])\+(.+)$/i);
  if (sgfMatch) {
    const side = sgfMatch[1].toUpperCase();
    const detail = sgfMatch[2];
    const winner = side === 'B' ? t('result:black_win', 'B+') : t('result:white_win', 'W+');

    if (/^R(esign(ation)?)?$/i.test(detail)) return `${winner}${t('result:resign', 'R')}`;
    if (/^T(ime)?$/i.test(detail)) return `${winner}${t('result:time', 'T')}`;
    if (/^F(orfeit)?$/i.test(detail)) return `${winner}${t('result:forfeit', 'F')}`;

    const pts = parseFloat(detail);
    if (!isNaN(pts)) {
      const unit = pointsUnit(t, rules, null);
      return `${winner}${pts}${unit}`;
    }

    return r;
  }

  // ── Chinese resignation: "黑中盘胜", "白中盘胜" ──
  const zhResign = r.match(/^(黑|白)中盘胜$/);
  if (zhResign) {
    const winner = zhResign[1] === '黑' ? t('result:black_win', 'B+') : t('result:white_win', 'W+');
    return `${winner}${t('result:resign', 'R')}`;
  }

  // ── Chinese timeout: "白超时，黑胜", "黑胜-白超时" ──
  if (/超时/.test(r)) {
    const blackWins = /黑胜/.test(r) || /白超时/.test(r);
    const winner = blackWins ? t('result:black_win', 'B+') : t('result:white_win', 'W+');
    return `${winner}${t('result:time', 'T')}`;
  }

  // ── Chinese no-count win: "白不计点胜" ──
  if (/不计点胜/.test(r)) {
    const winner = r.startsWith('黑') ? t('result:black_win', 'B+') : t('result:white_win', 'W+');
    return `${winner}${t('result:forfeit', 'F')}`;
  }

  // ── Chinese points: "黑胜2又3/4子", "白胜1/4子", "黑胜2.5", "白胜3目半" etc. ──
  const zhPoints = r.match(/^(黑|白)\s*胜[：:]?\s*(.+?)$/);
  if (zhPoints) {
    const winner = zhPoints[1] === '黑' ? t('result:black_win', 'B+') : t('result:white_win', 'W+');
    const originalUnit = detectChineseUnit(zhPoints[2]);
    const pts = parseChinese(zhPoints[2]);
    if (pts != null) {
      const unit = pointsUnit(t, rules, originalUnit);
      return `${winner}${pts}${unit}`;
    }
  }

  // ── Bare "黑 胜" (black wins, no detail) ──
  if (/^黑\s*胜$/.test(r)) return t('result:black_win', 'B+').replace(/\+$/, '');
  if (/^白\s*胜$/.test(r)) return t('result:white_win', 'W+').replace(/\+$/, '');

  // ── Draw variants ──
  if (/^(0|Draw|Jigo|和棋)$/i.test(r)) return t('result:draw', 'Draw');

  // ── "无胜负" (no result) ──
  if (r === '无胜负' || r === 'Void' || r === '?') return '?';

  // Unrecognized — pass through as-is
  return r;
}
