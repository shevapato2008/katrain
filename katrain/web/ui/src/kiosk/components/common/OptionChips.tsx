interface OptionChipsProps<T extends string | number> {
  label: string;
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
}

/**
 * 「从 N 项里选一项」的选择组 —— 走共享外壳的 `.kiosk-optseg`(`tokens.css:691`)。
 *
 * 原来这里自绘了两颗独立圆角按钮 + 一道缝。外壳里**本来就有这个构件**,而规范 `:541` 立它的
 * 理由正是这一条:「一屏之内所有选择组必须用同一种控件…一屏三套选择手势,用户每组都要重新认一遍」。
 * 这和上一轮 `.kiosk-status__*` 是**同一个形状**:类抄进来了,页面又自己造了一个 ——
 * **「导入了」不携带「用上了」。**
 *
 * 两个决定,都是判断不是遗漏:
 *
 * 1. **改的是这个共享组件,不是只改升降级那一屏。** 它的另一个消费者
 *    `PvpLocalSetupPage` 自陈「mirrors AiSetupPage's canonical kiosk setup skeleton」——
 *    两屏本来就该是同一副样子,只改一屏等于把不统一固化下来。
 * 2. **根节点自己挂 `.kiosk`。** `tokens.css` 整份定义在 `.kiosk {}` 里,不在这个类下面
 *    `var()` 会**静默求空**(国象踩过)。挂在自己身上就不依赖调用方的祖先链;
 *    嵌套在另一个 `.kiosk` 里也无害 —— 重复声明同一组自定义属性而已。
 *
 * **没有用 `.kiosk-opthint`**(`tokens.css:705`)。它是给「分段格塞不下副标题、但说明不能丢」
 * 的那种组用的;这里两个选项本来就没有副标题(「● 黑」/「○ 白」自明),
 * 补一行等于**新写文案**,而本轮文案冻结。哪天某个选项真需要说明,再挂它。
 */
function OptionChips<T extends string | number>({
  label,
  options,
  value,
  onChange,
}: OptionChipsProps<T>) {
  // 不挂 `.kiosk` —— 它现在由 `shell/KioskFrame` 挂在 kiosk 应用根上(Task 1)。
  // 这里再挂一次是嵌套同一个作用域,无害但会让「谁提供 token」变成两个答案。
  return (
    <div>
      {/* 样稿里这一行是 `<h2>中文</h2><em>English</em><span class="rule">`
          (`sample-xiangqi:602`)。**这里没有 `<em>`**:`label` 只有中文一侧,
          现编一个英文副标就是新写文案,而本轮文案冻结。 */}
      <div className="kiosk-seclabel">
        <h2>{label}</h2>
        <span className="rule" />
      </div>
      {/* `aria-pressed` 不是装饰:`.kiosk-optseg button[aria-pressed="true"]` 那条选中态样式
          就挂在它上面,而读屏也靠它。写成 `className={selected ? … : …}` 会让两者分家。 */}
      <div className="kiosk-optseg" role="group" aria-label={label}>
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
      </div>
    </div>
  );
}

export default OptionChips;
