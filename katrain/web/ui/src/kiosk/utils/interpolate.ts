/**
 * 把 `{name}` 占位符替换掉。**没有匹配到的占位符原样留在屏上** —— 那是故意的:
 * 静默吞掉会让「拿错了 msgid」变成一句读起来通顺的假话,而留着 `{start}` 一眼就看得见。
 *
 * ⚠️ **不许拿一个已有的 msgid 套一份新的占位符约定。** 2026-08-22(Task 13)栽过一次:
 * 新写的卡片用 `t('tsumego:unit', '第 {n} 单元')`,而 `tsumego:unit` 在 cn PO 里是 `单元`
 * (galaxy 三处在用)——`t()` 是 `translations[key] || defaultText`,**翻译表赢**,
 * 于是 `.replace('{n}', …)` 找不到东西可换,数字连同占位符一起没了。
 * 同一次的另一半:`t('tsumego:problemRange', '第 {a} – {b} 题')` —— PO 里那条叫
 * `{start}/{end}`,于是花括号原样上了屏。
 *
 * 两条闸各守一半(都在 `tests/` 里):
 *   · 花括号留在屏上 → `kiosk-copy-placeholders.spec.ts`(真浏览器 + 真翻译表扫 innerText)
 *   · 数字连同占位符消失 → `kiosk-shell-contract.spec.ts` 里那条比 PO 的
 * **单测抓不到这一类**:jsdom 里翻译表没加载,`t()` 恒返回默认值,断的是「我自己和我自己一致」。
 */
export const interpolate = (template: string, values: Record<string, string | number>): string =>
  template.replace(/\{(\w+)\}/g, (whole, k: string) => (k in values ? String(values[k]) : whole));
