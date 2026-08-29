import { KioskOptSeg } from '../../shell/KioskOptSeg';
import { KioskSecLabel } from '../../shell/KioskSecLabel';

interface OptionChipsProps<T extends string | number> {
  label: string;
  options: { value: T; label: React.ReactNode }[];
  value: T;
  onChange: (value: T) => void;
  /**
   * 英文副标。**只在稿子上写了的组才传** —— 现编一个英文词就是新写文案。
   * 2026-08-23 之前这个 prop 不存在，注释里的理由是「稿子只给了中文一侧」；
   * 8-21 那轮稿子扩到 27 屏时把英文副标一并写了（Input / Strength / Style / Side …），
   * 所以现在传的是**稿子上的字**，不是编的。
   */
  en?: string;
  /** 组标题右端那句话（「开局后不可改」）。 */
  secval?: React.ReactNode;
  /** 分段下面那行说明。写的是**当前选中项**的说明，不是这一组的说明。 */
  hint?: React.ReactNode;
  testId?: string;
}

/**
 * 「从 N 项里选一项」的选择组 —— 组标题 + `.kiosk-optseg` + 可选的一行说明。
 *
 * 走共享外壳的 `.kiosk-optseg`（`tokens.css:691`）。原来这里自绘了两颗独立圆角按钮 +
 * 一道缝；外壳里**本来就有这个构件**，而规范 `:541` 立它的理由正是这一条：
 * 「一屏之内所有选择组必须用同一种控件…一屏三套选择手势，用户每组都要重新认一遍」。
 * 这和 `.kiosk-status__*` 是**同一个形状**：类抄进来了，页面又自己造了一个 ——
 * **「导入了」不携带「用上了」。**
 *
 * 2026-08-23（屏 02/03/04）起，标题和分段各自拆成了 `KioskSecLabel` / `KioskOptSeg`：
 * 稿子里分段还有一种**行内**用法（`.igrow` 里配 `.iglab`，没有组标题），
 * 那一种直接用 `KioskOptSeg`，不必给这里加一个「标题不画」的开关。
 *
 * **根节点不挂 `.kiosk`** —— 它由 `shell/KioskFrame` 挂在 kiosk 应用根上（Task 1）。
 * 再挂一次是嵌套同一个作用域，无害，但会让「谁提供 token」变成两个答案。
 */
function OptionChips<T extends string | number>({
  label, options, value, onChange, en, secval, hint, testId,
}: OptionChipsProps<T>) {
  return (
    <div>
      <KioskSecLabel zh={label} en={en} value={secval} />
      <KioskOptSeg options={options} value={value} onChange={onChange} ariaLabel={label} testId={testId} />
      {hint ? <p className="kiosk-opthint">{hint}</p> : null}
    </div>
  );
}

export default OptionChips;
