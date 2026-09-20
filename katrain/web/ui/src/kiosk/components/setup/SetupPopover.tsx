import type { RefObject } from 'react';
import { createPortal } from 'react-dom';
import type { SetupOption } from './SetupSelect';

interface Props {
  host: HTMLElement;
  popRef: RefObject<HTMLDivElement | null>;
  style: { top: number; left: number } | null;
  /** 只有一列时跟着触发件的宽度走;两列三列自己撑 */
  minWidth?: number;
  columns: 1 | 2 | 3;
  options: SetupOption[];
  value: string;
  onPick: (key: string) => void;
  testId?: string;
}

/** 弹层本体。列内按**列**排(`grid-auto-flow: column`)——
 *  按行排会把让子那三档特殊项(倒贴/分先/让先)和让 N 子拆到两列里去。 */
export function SetupPopover({ host, popRef, style, minWidth, columns, options, value, onPick, testId }: Props) {
  return createPortal(
    <div
      ref={popRef}
      className={`su-pop${columns === 3 ? ' su-pop--3' : columns === 2 ? ' su-pop--2' : ''}`}
      role="listbox"
      data-open="true"
      data-testid={testId}
      style={style ? { top: style.top, left: style.left, minWidth: columns === 1 ? minWidth : undefined } : { visibility: 'hidden' }}
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
