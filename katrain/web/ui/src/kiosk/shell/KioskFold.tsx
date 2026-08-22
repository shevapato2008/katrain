import { useState, type ReactNode } from 'react';
import { Icon } from './icons';

/**
 * §11 折叠块 —— 标题行 30 高**本身就是开关**,收起后整块就剩这 30。
 *
 * 规范给了四条硬性,这里逐条对应:
 *
 * 1. **默认展开。** `defaultOpen = true`;调用方要收起得自己说。
 * 2. **收起的是明细,不是结论。** 标题行右端那个当前值(`value`)收起后**照旧显示** ——
 *    「胜率 · KataGo 原生通道 / 黑 37.4% · 白 +4.8 目」里,后半句是结论。
 *    把它一起藏掉,收起就从「少看点细节」变成「这块没了」。
 * 3. **腾出的空间归还给同栏里仍展开的那一块**(靠 `.kiosk-fold--grow` 的 `flex:1`,
 *    由调用方在需要的那一块上挂 `grow`)。
 * 4. **动作区永远贴右栏底**,两块都收起时空白落在它**上面** ——
 *    这条不在本组件里,在共享 `tokens.css` 的 `.kiosk-rail .kiosk-actions { margin-top:auto }`。
 *    悔棋 / 认输的位置是肌肉记忆,收个面板就把它挪走是「切模块不跳」的同类问题。
 *
 * 开合状态**由本组件自己拿着**:它是纯粹的视图偏好,没有任何别的东西依赖它。
 * 需要受控时再加 `open`/`onToggle`,现在没有第二个使用者,先不提前泛化。
 */
export function KioskFold({
  fold, title, value, defaultOpen = true, grow = false, bodyClassName, testId, children,
}: {
  /** `data-fold`。规范拿它当这一块的身份(`eval` / `moves` / `ledger`),取图和断言都认它。 */
  fold: string;
  title: ReactNode;
  /** 标题行右端的**当前值**。收起后仍然显示 —— 见上面第 2 条。 */
  value?: ReactNode;
  defaultOpen?: boolean;
  /** 这一块吃掉同栏里剩下的高度(`.kiosk-fold--grow`)。一栏里最多一块。 */
  grow?: boolean;
  bodyClassName?: string;
  testId?: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div
      className={grow ? 'kiosk-fold kiosk-fold--grow' : 'kiosk-fold'}
      data-open={open ? 'true' : 'false'}
      data-fold={fold}
      data-testid={testId}
    >
      <button
        type="button"
        className="kiosk-fold__head"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="kiosk-fold__toggle"><Icon name="caret-down" /></span>
        {title}
        {value !== undefined && <b>{value}</b>}
      </button>
      <div className={bodyClassName ? `kiosk-fold__body ${bodyClassName}` : 'kiosk-fold__body'}>
        {children}
      </div>
    </div>
  );
}
