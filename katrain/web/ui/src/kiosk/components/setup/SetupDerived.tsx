import type { ReactNode } from 'react';

interface Props {
  label: string;
  /** 推导出来的读数。强调的那个数用 `<i>` 包,它会走强调色。 */
  children: ReactNode;
  /** 右端那句话:说清它为什么不是控件 */
  note: string;
  /** 只有「自定贴目」那一档才点得动 */
  onPick?: () => void;
  testId?: string;
}

/**
 * 推导条 —— 上面那一行三格加起来等于什么。
 *
 * **它不是控件。** 没有 chevron、底色是 `--panel` 而不是 `--raise`、点不动。
 * 这一点是故意和星阵反着做的:星阵把贴目画成下拉,但那个下拉里永远只有一项 ——
 * 一个点开只有一行的下拉,是对控件的谎。
 *
 * 唯一的例外是「自定贴目」那一档:那时贴目**真的**是个可选项,于是它才长出边框和
 * chevron 变回控件。`disabled` 不许降透明度 —— 平时它不是「被禁用的按钮」,它就是一行字。
 */
export function SetupDerived({ label, children, note, onPick, testId }: Props) {
  const pick = !!onPick;
  return (
    <button
      type="button"
      className={`su-out${pick ? ' su-out--pick' : ''}`}
      disabled={!pick}
      data-testid={testId}
      onClick={pick ? (e) => { e.stopPropagation(); onPick!(); } : undefined}
    >
      <span className="su-out__k">{label}</span>
      <b className="su-out__v" data-testid={testId ? `${testId}-value` : undefined}>{children}</b>
      <span className="su-out__n">{note}</span>
      {pick ? (
        <svg className="su-cell__c" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <path d="M2 4l3 3 3-3" />
        </svg>
      ) : null}
    </button>
  );
}

interface FixedProps { label: string; value: ReactNode; testId?: string }

/**
 * 锁死的一格。**不是灰掉的控件,是一个读数。**
 * 灰掉说的是「你现在不能改」(换个前提就回来),虚线说的是「这条路本来就没得选」——
 * 升降级那三格属于后者:盘面条件在服务端写死,客户端连发都不许发
 * (`api/v1/endpoints/ai_ladder.py` 的 `LADDER_*` + `extra="forbid"`)。
 */
export function SetupFixed({ label, value, testId }: FixedProps) {
  return (
    <span className="su-cell su-cell--fixed" data-testid={testId}>
      <span className="su-cell__k">{label}</span>
      <span className="su-cell__v">{value}</span>
    </span>
  );
}

export default SetupDerived;
