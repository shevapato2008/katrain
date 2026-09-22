import type { ReactNode } from 'react';
import { interpolate } from '../../utils/interpolate';
import { RULES, komiInStones, resolveGameTerms, type HandicapKey } from '../../utils/setupOptions';

type Translate = (en: string, zh: string) => string;

/**
 * 推导条里那句读数。屏 02 和屏 04 两处用,所以收在一处 ——
 * **两屏说同一件事却各写一句,迟早会说得不一样**,而这句话说的是这一局怎么判胜负。
 *
 * 单位跟着规则走:数子的规则(中国 / AGA / AI 赛)写「子」并附上目数,
 * 数目的规则(日本)只写「目」。1 子 = 2 目。
 */
export function komiReadout(
  t: Translate,
  ruleKey: string,
  handicapKey: HandicapKey,
  freeKomi: number,
): ReactNode {
  const rule = RULES.find((r) => r.key === ruleKey) ?? RULES[0];
  const { handicap, komi } = resolveGameTerms(ruleKey, handicapKey, freeKomi);

  if (handicap > 0) {
    // 让子局的补偿由 KataGo 按规则自动加(chinese=WHB_N 等),所以这里没有贴目可说。
    return (
      <>
        {t('setup:komi_none', '不贴目')}
        {' · '}
        {interpolate(t('setup:komi_handicap', '黑先摆 {n} 子'), { n: handicap })}
      </>
    );
  }
  if (komi === 0) {
    return <>{t('setup:komi_none', '不贴目')} · {t('setup:komi_sente', '黑先行')}</>;
  }
  const side = komi > 0 ? t('setup:komi_black_pays', '黑贴') : t('setup:komi_white_pays', '白贴');
  const points = Math.abs(komi);
  if (rule.area) {
    return (
      <>
        {side} <i>{komiInStones(points)}</i> {t('setup:unit_stones', '子')}
        {' · '}
        {interpolate(t('setup:komi_points', '{n} 目'), { n: points })}
      </>
    );
  }
  return <>{side} <i>{points}</i> {t('setup:unit_points', '目')}</>;
}
