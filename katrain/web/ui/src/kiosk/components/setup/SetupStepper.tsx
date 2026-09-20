import type { ReactNode } from 'react';

interface Props {
  count: number;
  index: number;
  onChange: (index: number) => void;
  /** 读数左半 */
  value: ReactNode;
  /** 读数右半:这条轨的范围 */
  meta?: ReactNode;
  decLabel: string;
  incLabel: string;
  testId?: string;
}

/* ± 画成 SVG,**不用字形**。
   改版前这两颗键是文本 `−`(U+2212)和 `＋`(U+FF0B),一个半角一个全角 ——
   在真浏览器里量出来:字形宽 11.31px vs 20px,各自被推离按钮中心 5.66px 和 10px,
   所以两颗键永远对不齐,也各自不居中。
   根因有两层,第二层才是主因:
     ① 两个字形宽度差 8.7px,还会随中文字体回退再变一次;
     ② `src/index.css:41` 的 `button{padding:.6em 1.2em}`(Vite 模板自带)命中了这颗键——
        20px 字号下左右各 24px,挤进 44px 的 border-box,内容盒被压到 2px,
        字形整个溢出后居中,于是各被推出自己宽度的一半,按钮也被撑成 50px。
   所以这里既画 SVG,也把 `padding:0` 写死在 `.su-step` 上。 */
const MINUS = (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
    <path d="M4 9h10" />
  </svg>
);
const PLUS = (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
    <path d="M4 9h10M9 4v10" />
  </svg>
);

/**
 * 档位轨。**两头的键是禁用,不是回绕** —— 从 0 再按 `−` 绕到最大档,
 * 是把一次误触变成一局完全不同的棋,而这一屏每一项都写着「开局后不可改」。
 */
export function SetupStepper({ count, index, onChange, value, meta, decLabel, incLabel, testId }: Props) {
  const clamped = Math.min(Math.max(index, 0), Math.max(count - 1, 0));
  return (
    <>
      <div className="catpick" data-testid={testId}>
        <button
          type="button" className="su-step" aria-label={decLabel}
          disabled={clamped <= 0} onClick={() => onChange(clamped - 1)}
        >{MINUS}</button>
        <div className="cattrack">
          <div className="catticks">
            {Array.from({ length: count }, (_, i) => (
              <i key={i} className={i === clamped ? 'now' : i < clamped ? 'on' : undefined} />
            ))}
          </div>
        </div>
        <button
          type="button" className="su-step" aria-label={incLabel}
          disabled={clamped >= count - 1} onClick={() => onChange(clamped + 1)}
        >{PLUS}</button>
      </div>
      <p className="catmeta">
        <b data-testid={testId ? `${testId}-value` : undefined}>{value}</b>
        {meta ? <span>{meta}</span> : null}
      </p>
    </>
  );
}

export default SetupStepper;
