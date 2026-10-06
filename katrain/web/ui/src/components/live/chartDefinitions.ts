import { GRADE_LADDER_POINTS } from '../../features/analysis/moveGrade';

export const TIER_DEF_TEXT = (t: (k: string, d: string) => string): Record<string, string> => {
  const L = GRADE_LADDER_POINTS;
  const lt = (n: number) => t('grade:def_points_lt', '目损 < {n} 目').replace('{n}', String(n));
  return {
    brilliant: t('grade:def_brilliant', '走出引擎首选，且连引擎自己都没想到（先验 < 10%）'),
    best: t('grade:def_best', '走出引擎首选'),
    very_good: lt(L.very_good),
    playable: lt(L.playable),
    inaccuracy: lt(L.inaccuracy),
    mistake: lt(L.mistake),
    blunder: t('grade:def_blunder', '目损 ≥ {n} 目').replace('{n}', String(L.mistake)),
    unrated: t('grade:def_unrated', '上一手没分析或搜索量不足，判不了'),
  };
};

export const BRILLIANCE_BANDS: readonly { level: number; band: string }[] = [
  { level: 1, band: '5% ≤ prior < 10%' },
  { level: 2, band: '3% ≤ prior < 5%' },
  { level: 3, band: '2% ≤ prior < 3%' },
  { level: 4, band: '1% ≤ prior < 2%' },
  { level: 5, band: 'prior < 1%' },
];
