/**
 * 人类倾向（KataGo human SL 模型）的展示口径。
 *
 * 存的是 `top_moves[].human_prior` —— 某一档人类棋手在这个局面下这一点的概率，
 * 与 `prior`（KataGo 自己的 policy 先验）**是两张网的输出**，不要混。
 *
 * 展示上刻意做了三件事：
 *
 * 1. **用「每 100 人里 N 人」而不是百分号。** 同一行里「推荐度」已经是百分比了，
 *    两列都印 % 会被扫读成一对。换成计数字形，差异落在字形层，不依赖颜色。
 * 2. **有显式下限档 `<1人`，绝不印 0%。** 候选点里概率不足 0.5% 的格子占比很高，
 *    四舍五入成 0 会让整列没信息量，而且「0」在中文里读起来像「绝对没人下」。
 * 3. **不做候选集内归一化。** 实测三个候选点的 human_prior 之和最低能到 0.012，
 *    归一化后会印成 34%/33%/33% —— 把「几乎没人会这么下」造成「三个都很常见」。
 *    那是造假不是简化。
 *
 * 这个文件在 src/features/ 下，galaxy 与 kiosk 两个构建都可能用到，
 * 所以**不要** import 任何 src/galaxy/** 或 src/kiosk/** 的东西。
 */

/** 没有数据时统一显示这个，不要用 0 或空字符串顶替。 */
export const HUMAN_TENDENCY_EMPTY = '—';

/**
 * profile 串 → 人看的档位名。
 *
 * KataGo 的合法档只有 29 个（rank_20k..rank_1k, rank_1d..rank_9d），另有 preaz_*
 * （同棋力、不同年代的布局风格）与 proyear_*（rank 槽写死 9d，变的是年代与棋谱来源，
 * **不是第二条棋力轴**）。认不出来的一律返回 null，让调用方退到不带档位的说法，
 * 而不是瞎猜一个档印在屏幕上。
 */
export function rankLabel(profile: string | null | undefined): string | null {
  if (!profile) return null;
  const m = /^(?:rank|preaz)_(\d+)([dk])$/.exec(profile);
  if (m) return `${m[1]}${m[2] === 'd' ? '段' : '级'}`;
  if (/^proyear_\d{4}$/.test(profile)) return '职业';
  return null;
}

/**
 * 概率 → 「每 100 人里 N 人」。
 *
 * 0 与 null 是两回事：null 是「这份数据里没有这个数」（旧报告、直播链路、引擎没开
 * 人类模型），必须显示成「—」；真的算出来的极小值显示成「<1人」。
 */
export function formatHumanPickRate(prior: number | null | undefined): string {
  if (prior == null || !Number.isFinite(prior) || prior < 0) return HUMAN_TENDENCY_EMPTY;
  const perHundred = prior * 100;
  if (perHundred < 0.5) return '<1人';
  return `${Math.round(perHundred)}人`;
}

/** 微条占轨道的比例，0..1。**绝对刻度**（0-100 人），不随同屏其它行变化。 */
export function humanPickBarRatio(prior: number | null | undefined): number {
  if (prior == null || !Number.isFinite(prior) || prior <= 0) return 0;
  return Math.min(1, prior);
}

/** 一组候选点里用的是哪一档；混档或全无时返回 null。 */
export function dominantProfile(
  moves: { human_profile?: string | null }[],
): string | null {
  const seen = new Set<string>();
  for (const m of moves) if (m.human_profile) seen.add(m.human_profile);
  return seen.size === 1 ? [...seen][0] : null;
}
