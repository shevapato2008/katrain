/**
 * 开局设置三屏(02 自由 / 03 升降级 / 04 本地)共用的两张选项表。
 *
 * 提出来的理由**不是「看着通用」,是它们是契约**:用时那七档每一档写死了送给后端的
 * 四个字段(`time_enabled` / `main_time` / `byo_length` / `byo_periods`),
 * 各屏各抄一份的话,改一档就要记得改三处 —— 而漏改的那一处不会红,
 * 只会让某一屏悄悄送出另一套时限。
 *
 * 2026-08-23(屏 04)从 `pages/AiSetupPage.tsx` 原样搬出来,一个值都没动。
 */

import { interpolate } from './interpolate';

/**
 * 「AI 赛规则」送给引擎的规则串。**D1 待定** —— 见本轮裁定,定下来之前先用
 * KataGo 的具名预设占位,它是 `cpp/game/rules.cpp` 里唯一带 button 的具名规则。
 */
export const RULE_WIRE_BUTTON = 'aga-button';

export interface TimePreset {
  key: string;
  label: string;
  enabled: boolean;
  main: number;
  byo: number;
  periods: number;
}

type Translate = (en: string, zh: string) => string;

export const TIME_PRESETS = (t: Translate): TimePreset[] => [
  { key: 'untimed', label: t('Untimed', '不限时'), enabled: false, main: 0, byo: 30, periods: 3 },
  { key: 'byoOnly', label: t('setup:time_byo_only', '仅读秒 30秒×3'), enabled: true, main: 0, byo: 30, periods: 3 },
  { key: '5', label: t('5 min + 3x30s', '5分+3×30秒'), enabled: true, main: 5, byo: 30, periods: 3 },
  { key: '10', label: t('10 min + 3x30s', '10分+3×30秒'), enabled: true, main: 10, byo: 30, periods: 3 },
  { key: '20', label: t('20 min + 3x30s', '20分+3×30秒'), enabled: true, main: 20, byo: 30, periods: 3 },
  { key: '30', label: t('30 min + 3x30s', '30分+3×30秒'), enabled: true, main: 30, byo: 30, periods: 3 },
  { key: '60', label: t('60 min + 3x30s', '60分+3×30秒'), enabled: true, main: 60, byo: 30, periods: 3 },
];

/**
 * 档位轨上的顺序:**按时长从短到长**,「不限时」在最右端。
 *
 * 和 `TIME_PRESETS` 的数组顺序**故意不同** —— 那一份的第一项是 `untimed`,因为它是
 * 自由对弈和本地对局的默认值。而一条 −/＋ 轨的语义是「越往右越多」,照默认值的顺序画,
 * 「不限时」会落在最左端。**默认值是哪一个、它在轨上排第几,不该共用一个数组顺序。**
 */
export const TIME_TRACK_ORDER = ['byoOnly', '5', '10', '20', '30', '60', 'untimed'] as const;

/**
 * 规则那四条**不是编的**,是围棋常识 —— 而且这是个教棋的产品,终局怎么算是开局前
 * 必须讲清的那件事。稿子给了中国规则那一条,其余三条同一个口径写下来。
 */
export const RULES_HINT = (t: Translate): Record<string, string> => ({
  chinese: t('Chinese rules count area: territory plus stones on the board', '中国规则数子:终局按占地算,活棋在自己空里落子不损目'),
  japanese: t('Japanese rules count territory: filling your own territory costs a point', '日本规则数目:只算围住的空,在自己空里落子要损一目'),
  aga: t('AGA rules count area but pass stones keep the count equal to territory scoring', 'AGA 规则数子,但停一手要交一子 —— 算出来和数目同分'),
  button: t('setup:rules_button_hint', 'AI 赛规则:数子 + 先停一手的一方多得半目 —— 把数子法那半目的奇偶差抹平'),
});

/* ══════════════════════════════════════════════════════════════════════════
   开局条件模型(r2,2026-09-21)—— 路数 · 规则 · 让子 ⇒ 贴目
   ══════════════════════════════════════════════════════════════════════════

   **贴目不是设置项,是上面三个的结果。** 这一段是那条推导的唯一出处:三屏都从这里取,
   送给后端的 `handicap` / `komi` 两个字段也都由 `resolveGameTerms()` 算。

   为什么必须收在一处:旧版让子和贴目是两条各自独立的轨,而它们的关系只写在一段说明里
   ——那段说明写着「让子和贴目两样一起用会补两遍」,**而实现真的补了两遍**:
   `handicap > 0` 时前端把贴目那一组换成说明,但 `komi` state 不动(缺省 6.5)且照样发出去。
   中国规则让 2 子于是变成「白 +2(KataGo 自动)+ 6.5 目贴目」。
   关系写在说明里而不是写在代码里,就是这么坏掉的。

   判胜负的是 KataGo,不是我们:`server.py:_count_result()` 拿的是 `node.score`
   (KataGo 的 `scoreLead`),而 KataGo 的终局分是
   `boardScore + whiteBonusScore + whiteHandicapBonusScore + rules.komi`
   (`KataGo/cpp/game/boardhistory.cpp:700`)。其中 `whiteHandicapBonusScore`
   **由规则自动给**:chinese = `WHB_N`(让 N 子白自动 +N)、japanese = `WHB_ZERO`(不补)、
   aga = `WHB_N_MINUS_ONE`(`KataGo/cpp/game/rules.cpp:273-350`)。
   ⇒ **让子局的 komi 只能是 0** —— 补偿引擎已经加过了。 */

/** 分先贴目,单位**目**。取自 KataGo 自己的默认值(`docs/Analysis_Engine.md:82`、
 *  `cpp/program/setup.cpp:947`):面积 7.5 / 领地 6.5 / 面积+button 7.0。
 *  **不按棋盘路数变** —— KataGo 全仓没有 `boardSize → komi` 的代码,我们也不加:
 *  引擎的判定不按路数变,UI 的读数就不该按路数变,否则迟早分成两套。 */
export interface RuleDef {
  key: string;
  /** 送给后端、写进 SGF `RU[]` 的值 */
  wire: string;
  /** 数子(面积)还是数目(领地) —— 决定读数写「子」还是「目」 */
  area: boolean;
  /** 分先贴目(目) */
  evenKomi: number;
}

export const RULES: RuleDef[] = [
  { key: 'chinese', wire: 'chinese', area: true, evenKomi: 7.5 },
  { key: 'japanese', wire: 'japanese', area: false, evenKomi: 6.5 },
  { key: 'aga', wire: 'aga', area: true, evenKomi: 7.5 },
  { key: 'button', wire: RULE_WIRE_BUTTON, area: true, evenKomi: 7.0 },
];

export const RULE_LABEL = (t: Translate): Record<string, string> => ({
  chinese: t('Chinese rules', '中国规则'),
  japanese: t('Japanese rules', '日本规则'),
  aga: t('AGA rules', 'AGA 规则'),
  button: t('setup:rules_button', 'AI 赛规则'),
});

/** 让子档。**倒贴 / 分先 / 让先 三档的 handicap 都是 0,差别只在贴目** ——
 *  旧版把让子和贴目拆成两条轨,于是「让先」(不让子也不贴目)根本表达不出来。 */
export type HandicapKey = 'rev' | 'even' | 'sen' | 'free' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9';

export interface HandicapDef {
  key: HandicapKey;
  /** 盘上真的摆几颗子(送给后端的 `handicap`) */
  stones: number;
}

export const HANDICAPS: HandicapDef[] = [
  { key: 'rev', stones: 0 },
  { key: 'even', stones: 0 },
  { key: 'sen', stones: 0 },
  ...([2, 3, 4, 5, 6, 7, 8, 9] as const).map((n) => ({ key: String(n) as HandicapKey, stones: n })),
  { key: 'free', stones: 0 },
];

export const HANDICAP_LABEL = (t: Translate): Record<string, string> => ({
  rev: t('setup:ha_reverse', '倒贴'),
  even: t('setup:ha_even', '分先'),
  sen: t('setup:ha_sente', '让先'),
  free: t('setup:ha_free', '自定贴目'),
  ...Object.fromEntries([2, 3, 4, 5, 6, 7, 8, 9].map((n) => [
    String(n), interpolate(t('setup:ha_stones', '让 {n} 子'), { n }),
  ])),
});

/** 让子上限按**星位数**收:19 路 9 颗、13 路 5 颗、9 路 4 颗。
 *  9 路另外不给「倒贴」—— 9 路上倒贴 7.5 目是一整块角。与星阵实测的上限一致。 */
export const MAX_HANDICAP: Record<number, number> = { 19: 9, 13: 5, 9: 4 };

export function handicapKeysFor(size: number): HandicapKey[] {
  const max = MAX_HANDICAP[size] ?? 9;
  return HANDICAPS
    .filter((h) => h.stones <= max && !(h.key === 'rev' && size === 9))
    .map((h) => h.key);
}

/** 「自定贴目」那一档的取值:0.5 – 7.5 目,半目一档,15 档。
 *  范围沿用改版前那条贴目轨(`KOMI_MIN=0.5` / `KOMI_STEP=0.5`)——
 *  对改版前的能力是**严格超集**:0 目归「让先」、负贴目归「倒贴」,那条轨本来也够不着。
 *  不抄星阵的 ±100 目 101 档:那是研究用的量,不是 7″ 触屏上给人点的。 */
export const FREE_KOMI_MIN = 0.5;
export const FREE_KOMI_MAX = 7.5;
export const FREE_KOMI_STEP = 0.5;
export const FREE_KOMI_VALUES: number[] = Array.from(
  { length: Math.round((FREE_KOMI_MAX - FREE_KOMI_MIN) / FREE_KOMI_STEP) + 1 },
  (_, i) => +(FREE_KOMI_MIN + i * FREE_KOMI_STEP).toFixed(1),
);

export interface GameTerms {
  /** 送给后端的 `handicap` */
  handicap: number;
  /** 送给后端的 `komi`,单位目。正数=黑贴,负数=白贴 */
  komi: number;
}

/**
 * 三个输入 ⇒ 两个字段。**这是整条链上唯一算 komi 的地方。**
 *
 * · 分先  → 规则的默认贴目
 * · 让先  → 0(不让子也不贴目)
 * · 倒贴  → 负的默认贴目(白贴)
 * · 让 N 子 → handicap=N、**komi=0**(白的补偿由 KataGo 按规则自动加)
 * · 自定贴目 → handicap=0、komi 取用户选的那个
 */
export function resolveGameTerms(
  ruleKey: string,
  handicapKey: HandicapKey,
  freeKomi: number = FREE_KOMI_MAX,
): GameTerms {
  const rule = RULES.find((r) => r.key === ruleKey) ?? RULES[0];
  const ha = HANDICAPS.find((h) => h.key === handicapKey) ?? HANDICAPS[1];
  if (ha.stones > 0) return { handicap: ha.stones, komi: 0 };
  switch (handicapKey) {
    case 'sen': return { handicap: 0, komi: 0 };
    case 'rev': return { handicap: 0, komi: -rule.evenKomi };
    case 'free': return { handicap: 0, komi: freeKomi };
    default: return { handicap: 0, komi: rule.evenKomi };
  }
}

/** 目 → 子,写成带分数(7.5 目 = 3¾ 子)。数子规则的读数用它。 */
const QUARTER = ['', '\u00bc', '\u00bd', '\u00be'];
export function komiInStones(komiPoints: number): string {
  /* 1 子 = 2 目,所以半目一档在子上就是四分之一子一档 —— 四种分数刚好够。 */
  const quarters = Math.round((Math.abs(komiPoints) / 2) * 4);
  const whole = Math.floor(quarters / 4);
  const frac = QUARTER[quarters % 4];
  if (!frac) return String(whole);
  return (whole ? String(whole) : '') + frac;
}
