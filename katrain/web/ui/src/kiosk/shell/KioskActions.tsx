import { Icon, type IconName } from './icons';

export interface KioskAction {
  key: string;
  icon: IconName;
  label: string;
  onClick: () => void;
  /**
   * 开关键(领地 / 图表)。给了值就渲染 `aria-pressed`,**按下去留在按下的状态**;
   * 不给就是动作键,按完弹回来。两者格子一样大 —— 见下面那段。
   */
  pressed?: boolean;
  disabled?: boolean;
  /** 不可撤销的那一个(认输 / 弃权):描边 + 字色走 `--bad`,**不用实心红**。 */
  danger?: boolean;
  /**
   * 灰掉的原因。**灰而不说原因是这份稿子在别处专门骂过的事** ——
   * 「数子」在 100 手之前一律灰(后端 `/api/count/request` 直接拒),
   * 所以它旁边要写明还差什么。挂在 `title` + `aria-description` 上,
   * 屏上那句由调用方摆在开关排右端(`.ghint`)—— 那是版式,不是本组件的事。
   */
  reason?: string;
}

/**
 * §11 动作区 —— 右栏底部那一排。
 *
 * **永远贴右栏底**:上面的折叠块收起时,腾出的空白落在它**上面**,按钮不许跟着上移。
 * 那条靠共享 `tokens.css` 的 `.kiosk-rail .kiosk-actions { margin-top: auto }`,不在这里。
 *
 * 一行还是两行由 `className` 决定(围棋自由对弈屏七个键 ⇒ `gacts` = 4 列 × 2 行);
 * **格子高、图标、字号、圆角一律走共享 `.kiosk-actions button`,不许按屏改** ——
 * 「七个键必须一模一样大」是 Fan 2026-08-22 的原话。上一版稿子把前三个降级成矮一档、
 * 还不给图标的药丸键,等于把「开关」和「道具」两种别的东西的样子安在了它们头上。
 *
 * `<button>` 不是 `<div onClick>`:原来的 `ItemToggle` 是个 MUI `Box`,
 * 键盘上根本 tab 不到、回车也按不动,`disabled` 也只是把 `onClick` 换成 `undefined`
 * (读屏软件读不出「不可用」)。
 */
export function KioskActions({ actions, className, ariaLabel, testId }: {
  actions: readonly KioskAction[];
  /** 追加类,例如围棋对局屏的 `gacts`(4 列 × 2 行)。 */
  className?: string;
  ariaLabel?: string;
  testId?: string;
}) {
  return (
    <div
      className={className ? `kiosk-actions ${className}` : 'kiosk-actions'}
      role="group"
      aria-label={ariaLabel}
      data-testid={testId}
    >
      {actions.map((a) => (
        <button
          key={a.key}
          type="button"
          className={a.danger ? 'danger' : undefined}
          aria-pressed={a.pressed}
          disabled={a.disabled}
          title={a.disabled ? a.reason : undefined}
          onClick={a.onClick}
        >
          <Icon name={a.icon} />
          {a.label}
        </button>
      ))}
    </div>
  );
}
