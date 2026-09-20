import { useRef, type ReactNode } from 'react';
import { useSetupPopover } from './useSetupPopover';
import { SetupPopover } from './SetupPopover';

export interface SetupOption {
  key: string;
  label: ReactNode;
  /** 这一档现在选不了。**给理由,别只灰掉。** */
  disabled?: boolean;
  reason?: string;
}

interface Props {
  /** 键,显示在值上面一行(路数 / 规则 / 让子 …) */
  label: string;
  value: string;
  options: SetupOption[];
  onChange: (key: string) => void;
  /** 弹层列数。11 档排两列、15 档排三列 —— 一列比整条右栏还高。 */
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
 * 为什么这一屏的枚举用下拉而不是改版前的 `−/＋` 档位轨:**枚举用下拉,连续量用轨**。
 * 路数 3 / 规则 4 / 让子 11 / 落子 2 / 我执 3 / 用时 7 都是小枚举,下拉两下点到;
 * 只有棋力 29 档是连续量,那条留轨(`SetupStepper`)。
 *
 * **整格禁用的判据是「一个选项都没有」,不是「只剩一个能选」。**
 * 一开始写成了后者,结果没标定摄像头时「落子」整格点不开 ——
 * 而「实体盘为什么用不了」那句话恰恰写在打不开的那个弹层里。
 * 灰掉的选项得让人看得见,否则灰掉等于什么都没说。
 *
 * 禁用是「暂时」的信号(换个前提它就回来),所以保留 chevron、只降透明度;
 * 永久没得选的那种走 `SetupFixed`(虚线、无 chevron),两者不是一回事。
 */
export function SetupSelect({ label, value, options, onChange, columns = 1, testId }: Props) {
  const cellRef = useRef<HTMLButtonElement>(null);
  const { host, open, setOpen, popRef } = useSetupPopover(cellRef);

  const locked = options.length < 2;
  const current = options.find((o) => o.key === value);

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
        onClick={(e) => { e.stopPropagation(); setOpen(!open); }}
      >
        <span className="su-cell__k">{label}</span>
        <span className="su-cell__v" data-testid={testId ? `${testId}-value` : undefined}>
          {current?.label ?? value}
        </span>
        {CHEVRON}
      </button>
      {open && host && (
        <SetupPopover
          host={host}
          popRef={popRef}
          columns={columns}
          options={options}
          value={value}
          onPick={(k) => { onChange(k); setOpen(false); }}
          testId={testId ? `${testId}-pop` : undefined}
        />
      )}
    </>
  );
}

export default SetupSelect;
