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
  { key: 'byoOnly', label: t('Byoyomi only 30s x3', '仅读秒 30秒×3'), enabled: true, main: 0, byo: 30, periods: 3 },
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
  korean: t('Korean rules count territory, same as Japanese with different komi practice', '韩国规则数目:和日本规则同一种算法,贴目习惯不同'),
  aga: t('AGA rules count area but pass stones keep the count equal to territory scoring', 'AGA 规则数子,但停一手要交一子 —— 算出来和数目同分'),
});
