import { describe, it, expect } from 'vitest';
import {
  RULES, HANDICAPS, MAX_HANDICAP, handicapKeysFor,
  resolveGameTerms, komiInStones, FREE_KOMI_VALUES,
  type HandicapKey,
} from './setupOptions';

/* 这一份测的是**契约**,不是实现细节:`resolveGameTerms()` 决定送给后端的
   `handicap` / `komi` 两个字段,而那两个字段直接决定 KataGo 怎么判这一局的胜负。

   写它的直接理由是一个真事故:改版前「让子」和「贴目」是两条独立的轨,
   前端在 handicap>0 时只把贴目那一组**从屏上换掉**,`komi` state 不动、照样发,
   于是中国规则让 2 子实际是「白 +2(KataGo 自动)+ 6.5 目」——
   补了两遍,而屏上那段说明正好写着「两样一起用会补两遍」。
   下面第一组断言就是那个缺陷的形状。 */

describe('让子局不许再贴目', () => {
  // KataGo 的 whiteHandicapBonusRule 已经按规则自动给白补偿:
  // chinese=WHB_N、japanese=WHB_ZERO、aga=WHB_N_MINUS_ONE
  // (KataGo/cpp/game/rules.cpp:273-350)。所以这里只能是 0。
  for (const rule of ['chinese', 'japanese', 'aga', 'button']) {
    for (const n of [2, 5, 9] as const) {
      it(`${rule} 让 ${n} 子 → komi 0`, () => {
        const t = resolveGameTerms(rule, String(n) as HandicapKey);
        expect(t).toEqual({ handicap: n, komi: 0 });
      });
    }
  }
});

describe('分先 / 让先 / 倒贴 —— 三档都不摆子,差别只在贴目', () => {
  it('分先按规则的默认贴目', () => {
    expect(resolveGameTerms('chinese', 'even')).toEqual({ handicap: 0, komi: 7.5 });
    expect(resolveGameTerms('japanese', 'even')).toEqual({ handicap: 0, komi: 6.5 });
    expect(resolveGameTerms('aga', 'even')).toEqual({ handicap: 0, komi: 7.5 });
    // 面积 + button 的 KataGo 默认是 7.0,不是 7.5(docs/Analysis_Engine.md:82)
    expect(resolveGameTerms('button', 'even')).toEqual({ handicap: 0, komi: 7.0 });
  });
  it('让先 = 不让子也不贴目', () => {
    expect(resolveGameTerms('chinese', 'sen')).toEqual({ handicap: 0, komi: 0 });
    expect(resolveGameTerms('japanese', 'sen')).toEqual({ handicap: 0, komi: 0 });
  });
  it('倒贴 = 白贴,负 komi', () => {
    expect(resolveGameTerms('chinese', 'rev')).toEqual({ handicap: 0, komi: -7.5 });
    expect(resolveGameTerms('japanese', 'rev')).toEqual({ handicap: 0, komi: -6.5 });
  });
});

describe('自定贴目', () => {
  it('取用户选的那个值,不摆子', () => {
    expect(resolveGameTerms('chinese', 'free', 3.5)).toEqual({ handicap: 0, komi: 3.5 });
  });
  it('15 档,0.5 – 7.5 半目一档', () => {
    expect(FREE_KOMI_VALUES).toHaveLength(15);
    expect(FREE_KOMI_VALUES[0]).toBe(0.5);
    expect(FREE_KOMI_VALUES[14]).toBe(7.5);
  });
});

describe('贴目不按棋盘路数变', () => {
  // KataGo 全仓没有 boardSize → komi 的代码(cpp/program/setup.cpp:947 只按规则分三档)。
  // 这条断言挡的是「有人照星阵给 9 路单开一档」——那会让 UI 的读数和引擎算的分成两套。
  it('三种路数走同一条路,拿到同一个贴目', () => {
    // 路数只进 `handicapKeysFor`(决定有哪些让子档),**不进 `resolveGameTerms`**。
    // 这里把三种路数都走一遍完整调用,证明换路数换不动贴目。
    for (const size of [19, 13, 9]) {
      expect(handicapKeysFor(size)).toContain('even');
      const komis = RULES.map((r) => resolveGameTerms(r.key, 'even').komi);
      expect(komis).toEqual([7.5, 6.5, 7.5, 7.0]);
    }
  });
});

describe('让子上限按星位数收', () => {
  it.each([[19, 9], [13, 5], [9, 4]])('%i 路最多让 %i 子', (size, max) => {
    const keys = handicapKeysFor(size);
    const stones = keys
      .map((k) => HANDICAPS.find((h) => h.key === k)!.stones)
      .filter((n) => n > 0);
    expect(Math.max(...stones)).toBe(max);
    expect(MAX_HANDICAP[size]).toBe(max);
  });
  it('9 路不给倒贴', () => {
    expect(handicapKeysFor(9)).not.toContain('rev');
    expect(handicapKeysFor(13)).toContain('rev');
  });
  it('自定贴目三种路数都有', () => {
    for (const s of [19, 13, 9]) expect(handicapKeysFor(s)).toContain('free');
  });
});

describe('目 → 子的读数', () => {
  it.each([
    [7.5, '3¾'], [7, '3½'], [6.5, '3¼'], [6, '3'],
    [0.5, '¼'], [1, '½'], [2, '1'], [0, '0'],
    [-7.5, '3¾'],   // 白贴多少子,正负由调用方写在「黑贴/白贴」上
  ])('%f 目 = %s 子', (points, want) => {
    expect(komiInStones(points)).toBe(want);
  });
});

describe('规则表', () => {
  it('韩国规则已撤 —— KataGo 里它和日本规则是同一个分支、逐字相同(rules.cpp:276)', () => {
    expect(RULES.map((r) => r.key)).toEqual(['chinese', 'japanese', 'aga', 'button']);
  });
  it('数子的规则写「子」,数目的写「目」', () => {
    expect(RULES.filter((r) => r.area).map((r) => r.key)).toEqual(['chinese', 'aga', 'button']);
  });
});
