import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useSetupPopoverHost } from './SetupPopoverHost';

export interface SetupOption {
  key: string;
  label: ReactNode;
  /** 这一档现在选不了 —— **暂时**选不了,不是永远没有。给理由,别只灰掉。 */
  disabled?: boolean;
  /** 灰掉的原因,一句话,显示在选项右端 */
  reason?: string;
}

interface Props {
  /** 键,显示在值的上面一行(路数 / 规则 / 让子 …) */
  label: string;
  value: string;
  options: SetupOption[];
  onChange: (key: string) => void;
  /** 弹层列数。11 档以上排两列,15 档排三列 —— 一列摆不下整条右栏。 */
  columns?: 1 | 2 | 3;
  testId?: string;
}

const CHEVRON = (
  <svg className="su-cell__c" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
    <path d="M2 4l3 3 3-3" />
  </svg>
);

/**
 * 一格 = 一个下拉。
 *
 * 为什么这一屏的枚举用下拉而不是原来的 `−/＋` 档位轨:**枚举用下拉,连续量用轨**。
 * 路数 3 / 规则 4 / 让子 11 / 落子 2 / 我执 3 / 用时 7 都是小枚举,下拉两下点到;
 * 只有棋力 29 档是连续量,那条留轨。
 *
 * **只剩一个可选项时整格禁用**(而不是让人点开看见一行)。禁用是「暂时」的信号 ——
 * 换个前提它就回来了,所以保留 chevron、只降透明度;永久没得选的那种走
 * `.su-cell--fixed`(虚线、无 chevron),两者不是一回事。
 */
export function SetupSelect({ label, value, options, onChange, columns = 1, testId }: Props) {
  const host = useSetupPopoverHost();
  const cellRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number; minWidth: number } | null>(null);

  const selectable = options.filter((o) => !o.disabled);
  const locked = selectable.length < 2;
  const current = options.find((o) => o.key === value);

  useLayoutEffect(() => {
    if (!open || !host || !cellRef.current || !popRef.current) return;
    const cr = cellRef.current.getBoundingClientRect();
    const hr = host.getBoundingClientRect();
    const ph = popRef.current.offsetHeight;
    const pw = popRef.current.offsetWidth;
    const below = cr.bottom - hr.top + 6;
    // 下面放不下就翻到上面;仍然放不下就贴着栏顶,**绝不伸到栏外**。
    const top = below + ph > hr.height ? Math.max(4, cr.top - hr.top - ph - 6) : below;
    // 右边放不下就贴着**触发格自己的右边缘**往左推,不是贴栏的右边缘 ——
    // 弹层要看得出是哪一格开的。
    let left = cr.left - hr.left;
    if (left + pw > hr.width - 2) left = cr.right - hr.left - pw;
    setPos({ top, left: Math.max(2, left), minWidth: cr.width });
  }, [open, host, columns, options.length]);

  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); setOpen(false); } };
    document.addEventListener('click', close);
    document.addEventListener('keydown', onKey, true);
    return () => { document.removeEventListener('click', close); document.removeEventListener('keydown', onKey, true); };
  }, [open]);

  const popClass = `su-pop${columns === 3 ? ' su-pop--3' : columns === 2 ? ' su-pop--2' : ''}`;

  return (
    <>
      <button
        type="button"
        ref={cellRef}
        className="su-cell"
        data-testid={testId}
        disabled={locked}
        aria-haspopup="listbox"
        aria-expanded={open || undefined}
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
      >
        <span className="su-cell__k">{label}</span>
        <span className="su-cell__v" data-testid={testId ? `${testId}-value` : undefined}>
          {current?.label ?? value}
        </span>
        {CHEVRON}
      </button>
      {open && host && createPortal(
        <div
          ref={popRef}
          className={popClass}
          role="listbox"
          data-open="true"
          data-testid={testId ? `${testId}-pop` : undefined}
          style={pos ? { top: pos.top, left: pos.left, minWidth: columns === 1 ? pos.minWidth : undefined } : { visibility: 'hidden' }}
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
              aria-checked={o.key === value || undefined}
              disabled={o.disabled}
              onClick={() => { onChange(o.key); setOpen(false); }}
            >
              {o.label}
              {o.disabled && o.reason ? <em>{o.reason}</em> : null}
            </button>
          ))}
        </div>,
        host,
      )}
    </>
  );
}

export default SetupSelect;
