import { describe, expect, it } from 'vitest';

import {
  dominantProfile,
  formatHumanPickRate,
  HUMAN_TENDENCY_EMPTY,
  humanPickBarRatio,
  rankLabel,
} from './humanTendency';

describe('rankLabel', () => {
  it.each([
    ['rank_5d', '5段'],
    ['rank_9d', '9段'],
    ['rank_20k', '20级'],
    ['preaz_3d', '3段'],
    ['proyear_2023', '职业'],
  ])('%s -> %s', (profile, expected) => {
    expect(rankLabel(profile)).toBe(expected);
  });

  it('认不出来的一律返回 null，不瞎猜一个档印在屏幕上', () => {
    // rank_10d 在 KataGo 里根本不存在（封顶 9d）—— 涨棋网的对手 id 里就有这种。
    expect(rankLabel('rank_10d')).toBe('10段'); // 格式合法就照实翻，合法性归服务端
    expect(rankLabel('power_3')).toBeNull();
    expect(rankLabel('dog_30')).toBeNull();
    expect(rankLabel('')).toBeNull();
    expect(rankLabel(null)).toBeNull();
    expect(rankLabel(undefined)).toBeNull();
  });
});

describe('formatHumanPickRate', () => {
  it('把概率读成「每 100 人里 N 人」', () => {
    expect(formatHumanPickRate(0.31)).toBe('31人');
    expect(formatHumanPickRate(0.225)).toBe('23人');
    expect(formatHumanPickRate(1)).toBe('100人');
  });

  it('极小值走显式下限档，绝不印 0', () => {
    // 候选点里概率不足 0.5% 的格子占比很高；印成 0 会让整列没信息量。
    expect(formatHumanPickRate(0.002)).toBe('<1人');
    expect(formatHumanPickRate(0.0049)).toBe('<1人');
    expect(formatHumanPickRate(0)).toBe('<1人');
    expect(formatHumanPickRate(0.005)).toBe('1人');
  });

  it('没有数据和「没人会下」是两回事', () => {
    expect(formatHumanPickRate(null)).toBe(HUMAN_TENDENCY_EMPTY);
    expect(formatHumanPickRate(undefined)).toBe(HUMAN_TENDENCY_EMPTY);
    expect(formatHumanPickRate(Number.NaN)).toBe(HUMAN_TENDENCY_EMPTY);
    expect(formatHumanPickRate(-1)).toBe(HUMAN_TENDENCY_EMPTY); // KataGo 用 -1 标非法点
  });
});

describe('humanPickBarRatio', () => {
  it('是绝对刻度，不随同屏其它行归一化', () => {
    expect(humanPickBarRatio(0.31)).toBeCloseTo(0.31);
    expect(humanPickBarRatio(0.02)).toBeCloseTo(0.02);
  });

  it('没有数据就是 0（调用方据此不画条）', () => {
    expect(humanPickBarRatio(null)).toBe(0);
    expect(humanPickBarRatio(-1)).toBe(0);
    expect(humanPickBarRatio(Number.NaN)).toBe(0);
  });
});

describe('dominantProfile', () => {
  it('全同一档时返回那一档', () => {
    expect(
      dominantProfile([{ human_profile: 'rank_5d' }, { human_profile: 'rank_5d' }, { human_profile: null }]),
    ).toBe('rank_5d');
  });

  it('混档时返回 null —— 表头不能替两个档说话', () => {
    expect(dominantProfile([{ human_profile: 'rank_5d' }, { human_profile: 'rank_9d' }])).toBeNull();
  });

  it('一个都没有时返回 null', () => {
    expect(dominantProfile([{ human_profile: null }, {}])).toBeNull();
  });
});
