/**
 * 光秃秃的分段控件 —— 只有 `.kiosk-optseg` 那一条，不带组标题。
 *
 * 从 `components/common/OptionChips` 里拆出来的，因为稿子上有**两种用法**：
 *   · 独立一组：组标题 + 分段 + 说明  → `OptionChips`（它现在由本组件拼出来）
 *   · 行内一格：`.igrow` 里 `<span class="iglab">落子</span>` + 分段，**没有组标题**
 * 后一种要是拿 `OptionChips` 硬套，就得给它加一个「标题不画」的开关 ——
 * 一个 prop 兼管两件事，调用方为了不画标题被迫传一个空标题。
 *
 * `aria-pressed` 不是装饰：`.kiosk-optseg button[aria-pressed="true"]` 那条选中态样式
 * 就挂在它上面，读屏也靠它。写成 `className={selected ? … : …}` 会让两者分家。
 */
interface KioskOptSegProps<T extends string | number> {
  options: { value: T; label: React.ReactNode }[];
  value: T;
  onChange: (value: T) => void;
  /** 读屏用的组名。行内用法里它是 `.iglab` 那几个字。 */
  ariaLabel: string;
  testId?: string;
}

export function KioskOptSeg<T extends string | number>({
  options, value, onChange, ariaLabel, testId,
}: KioskOptSegProps<T>) {
  return (
    <span className="kiosk-optseg" role="group" aria-label={ariaLabel} data-testid={testId}>
      {options.map((opt) => (
        <button
          key={String(opt.value)}
          type="button"
          aria-pressed={value === opt.value}
          onClick={() => onChange(opt.value)}
        >
          {opt.label}
        </button>
      ))}
    </span>
  );
}

export default KioskOptSeg;
