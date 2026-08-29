import type { ReactNode } from 'react';

/**
 * 组标题行:中文 12.5px Sans 700 .12em + 英文 11px Serif 斜体 `--dim` + 渐隐横线
 * + 右端可选的值(`.secval`)。容器几何在 tokens.css:563-566,四个子元素在 seclabel.css。
 *
 * 右端那个值是**数据**(「本机 5 局」「两档:500 / 2000 次计算」),不是旁注。
 * 稿子里的解释性段落(`.note`)是给读稿人看的,不进这里,也不上线 —— 见 G5。
 *
 * `action` 是**这一组自己的开关**(今天只有复盘屏的搜索用它)。它排在 `value` 之后,
 * 因为值是这一组的读数、开关是对这一组的动作 —— 读在前、做在后。
 * 靶子的尺寸归调用方的样式管(`.kiosk-seclabel__act`),这里只留位置。
 */
export function KioskSecLabel({ zh, en, value, action }: {
  zh: string;
  /**
   * 英文副标。**2026-08-23(屏 02/03/04)放宽成可选** —— 在那之前四个消费者个个都有,
   * 所以写成必填也没人疼;开局设置屏把选择组(`OptionChips`)也接到这一行上,
   * 而它的调用点里有几组稿子只给了中文。**要么留空,要么现编一个英文词** ——
   * 后者是新写文案。留空:`<em>` 整个不渲染,那条渐变线自己顶上来,行还是那一行。
   */
  en?: string;
  value?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="kiosk-seclabel">
      <h2>{zh}</h2>
      {en ? <em>{en}</em> : null}
      <span className="rule" />
      {value && <b className="secval">{value}</b>}
      {action}
    </div>
  );
}
