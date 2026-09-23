import type { RefObject } from 'react';
import { createPortal } from 'react-dom';
import type { SetupOption } from './SetupSelect';

interface Props {
  host: HTMLElement;
  popRef: RefObject<HTMLDivElement | null>;
  columns: 1 | 2 | 3;
  options: SetupOption[];
  value: string;
  onPick: (key: string) => void;
  testId?: string;
}

/** 弹层本体。列内按**列**排(`grid-auto-flow: column`)——
 *  按行排会把让子那三档特殊项(倒贴/分先/让先)和让 N 子拆到两列里去。 */
export function SetupPopover({ host, popRef, columns, options, value, onPick, testId }: Props) {
  return createPortal(
    <div
      ref={popRef}
      className={`su-pop${columns === 3 ? ' su-pop--3' : columns === 2 ? ' su-pop--2' : ''}`}
      role="listbox"
      data-open="true"
      data-testid={testId}
      /* 先隐身渲染 —— 位置要量过才知道。`useSetupPopover` 的 layout effect 量完
         直接写 `top/left` 并显形,用户看不到中间那一帧。 */
      style={{ visibility: 'hidden' }}
      onClick={(e) => e.stopPropagation()}
    >
      {options.map((o) => (
        <button
          key={o.key}
          type="button"
          role="option"
          className="su-pop__i"
          data-k={o.key}
          aria-selected={o.key === value}
          disabled={o.disabled}
          onClick={() => onPick(o.key)}
        >
          {o.label}
          {o.disabled && o.reason ? <em>{o.reason}</em> : null}
        </button>
      ))}
    </div>,
    host,
  );
}

export default SetupPopover;
