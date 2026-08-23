import { KioskSecLabel } from './KioskSecLabel';

/**
 * 档位轨 —— `−` / 一排点 / `＋`，下面一行读数（`sample-go` 稿子的 `.catpick` + `.catmeta`）。
 *
 * ## 为什么不是下拉，也不是分段控件
 *
 * 开局设置里有三种档位：棋力 **29 档**、让子 **10 档**、贴目 **8 档**、用时 **7 档**。
 * `.kiosk-optseg` 规范上最多三段，摆不下；而原来那版用的 MUI `Select`
 * 在 7″ 触屏上要点两次才看得见选项，且弹层盖住左边那块盘 —— 而那块盘画的正是
 * 「按下开始之后会出现的局面」，调让子时它是唯一的反馈。
 *
 * ## 点是**位置**不是刻度值
 *
 * `count` 个点均分在轨上，第 `index` 个是 `now`，它左边的是 `on`。
 * 读数那一行（`label` / `meta`）由调用方给 —— 同样一条轨，棋力要写「第 15 档 · 6 级」，
 * 让子要写「让 2 子」，不变式只有「点的个数 = 档的个数」。
 *
 * ⚠️ **两头的键要禁用，不是回绕。** 让子从 0 再按 `−` 绕到 9 子，是把一次误触
 * 变成一局完全不同的棋 —— 而这一屏的每一项都写着「开局后不可改」。
 */
interface KioskStepTrackProps {
  /**
   * 组名（中文）。**不传就整行不画** —— 贴目那一组的标题由父段自己画，
   * 因为它要在让子 > 0 时把右端换成「本局不适用」，而那一态下这条轨根本不渲染。
   */
  label?: string;
  /** 英文副标，稿子上写了才传。 */
  en?: string;
  /** 组标题右端那句话。 */
  secval?: React.ReactNode;
  /** 一共几档。 */
  count: number;
  /** 当前在第几档，0 起。 */
  index: number;
  onChange: (index: number) => void;
  /** 读数左半：当前这一档叫什么（「第 15 档 · 6 级」）。 */
  value: React.ReactNode;
  /** 读数右半：这条轨的范围（「共 29 档 · 20k – 9d」）。不传就不画。 */
  meta?: React.ReactNode;
  /** `−` / `＋` 的读屏名。两头都要 —— 「加」「减」在只念按钮名的读屏里指不出加的是什么。 */
  decLabel: string;
  incLabel: string;
  /** 轨下面那行说明。 */
  hint?: React.ReactNode;
  testId?: string;
}

export function KioskStepTrack({
  label, en, secval, count, index, onChange, value, meta, decLabel, incLabel, hint, testId,
}: KioskStepTrackProps) {
  const clamped = Math.min(Math.max(index, 0), Math.max(count - 1, 0));
  return (
    <>
      {label ? <KioskSecLabel zh={label} en={en} value={secval} /> : null}
      <div className="catpick" data-testid={testId}>
        <button
          type="button" className="catstep" aria-label={decLabel}
          disabled={clamped <= 0} onClick={() => onChange(clamped - 1)}
        >
          −
        </button>
        {/* 轨本身不可点:29 个点摊在 ~330px 上,一个点 11px 宽 —— 手指点不准,
            而点错一下就是换了一档对手。加减键各 44,那才是能点的尺寸。 */}
        <div className="cattrack">
          <div className="catticks">
            {Array.from({ length: count }, (_, i) => (
              <i key={i} className={i === clamped ? 'now' : i < clamped ? 'on' : undefined} />
            ))}
          </div>
        </div>
        <button
          type="button" className="catstep" aria-label={incLabel}
          disabled={clamped >= count - 1} onClick={() => onChange(clamped + 1)}
        >
          ＋
        </button>
      </div>
      <p className="catmeta">
        <b>{value}</b>
        {meta ? <span>{meta}</span> : null}
      </p>
      {hint ? <p className="kiosk-opthint">{hint}</p> : null}
    </>
  );
}

export default KioskStepTrack;
