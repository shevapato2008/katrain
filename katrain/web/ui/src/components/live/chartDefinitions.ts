import { GRADE_LADDER_POINTS } from '../../features/analysis/moveGrade';

export const TIER_DEF_TEXT = (t: (k: string, d: string) => string): Record<string, string> => {
  const L = GRADE_LADDER_POINTS;
  const lt = (n: number) => t('grade:def_points_lt', '目损 < {n} 目').replace('{n}', String(n));
  return {
    brilliant: t('grade:def_brilliant', '走出AI深入计算后的首选，且AI初选概率低于10%（官子低于6%）'),
    best: t('grade:def_best', '走出引擎首选'),
    very_good: lt(L.very_good),
    playable: lt(L.playable),
    inaccuracy: lt(L.inaccuracy),
    mistake: lt(L.mistake),
    blunder: t('grade:def_blunder', '目损 ≥ {n} 目').replace('{n}', String(L.mistake)),
    unrated: t('grade:def_unrated', '上一手没分析或搜索量不足，判不了'),
  };
};

export const BRILLIANCE_HELP_TEXT = (t: (k: string, d: string) => string) => ({
  entry: t('grade:brilliance_entry', '妙手需满足：实战走出AI深入计算后的首选；AI初选概率低于10%（官子低于6%）；局面胜负尚未确定。'),
  probability: t('grade:initial_probability_help', 'AI初选概率指AI深入计算前对这步棋的选择概率，不是胜率，也不是人类落子概率。初选概率很低的招法，也可能在深入计算后成为首选。'),
});

export const BRILLIANCE_BANDS: readonly { level: number; band: string }[] = [
  { level: 1, band: '5%–<10%' },
  { level: 2, band: '3%–<5%' },
  { level: 3, band: '2%–<3%' },
  { level: 4, band: '1%–<2%' },
  { level: 5, band: '<1%' },
];
