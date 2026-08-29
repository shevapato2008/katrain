import type { KeyboardEvent, ReactNode } from 'react';
import { Icon, type IconName } from './icons';

export interface PagebarSegment {
  value: string;
  /** `[value, label]`。最多 3 段 —— 再多就该换别的控件。 */
  options: readonly (readonly [string, string])[];
  onChange: (next: string) => void;
  ariaLabel?: string;
}

/**
 * §11 页控条:`[← 返回 36高] [标题 Serif] [英文副标 斜体] …auto… [页级图标键] [分段 32高]`。
 *
 * 顶栏在**所有层级**恒为品牌态,返回 / 视图切换 / 上下文标题一律下放到这里。
 * 位置写死:两种布局下**纵向位置完全相同**(y 70–114,高 44)——
 *   布局 A(有棋盘)在右栏顶部 x548–1008;布局 B(无棋盘)通栏 x16–1008。
 * 有盘页和无盘页来回切时这条控件带因此不会上下跳。
 *
 * **悔棋、认输、求和、提示一律不许放这里** —— 它们属于右栏下面的动作区。
 * 页面没有视图切换时右端就空着,**返回键的位置不变**(位置恒定是肌肉记忆)。
 */
export function KioskPagebar({ backLabel, onBack, backBusy = false, title, sub, status, segment, action, testId }: {
  backLabel?: ReactNode;
  onBack?: () => void;
  /** 返回正在进行中(要先存盘、先退出房间)。**保留位置与去向,如实标成忙碌** —— 不是把键藏了。 */
  backBusy?: boolean;
  title: ReactNode;
  /** 英文副标。不是新文案,是标题那句话的另一种语言。 */
  sub?: ReactNode;
  /**
   * 这一屏的**状态标**(直播中 / 已结束)。排在标题之后、图标键与分段之前。
   *
   * §11 那句「页控条只许放三类东西:① 返回 ② 视图切换 ③ 最多一个页级图标按钮」
   * 枚举的是**可交互的槽**,不是「这条上能出现的全部元素」—— 标题和 `sub` 也不在那三类里,
   * 而它们显然是允许的。紧接着那句禁令点名的是「**悔棋、认输、求和、提示这些业务动作**」,
   * 而状态标既不可点也不可聚焦,不在被禁的那一类。
   * 稿子屏 18 就是这么画的,而 `.kiosk-tag--live` 这个部件本仓早就为这三个字写好了。
   *
   * ⚠️ 它**不占流内高度**:直播屏的右栏六块正好摆满 516,一个像素的余量都没有;
   * 把它放到内容区顶上要 44,那 44 会从着法表里扣掉将近两行。
   */
  status?: ReactNode;
  segment?: PagebarSegment;
  /**
   * §11 允许的**最多一个**页级图标按钮。
   *
   * `state` 让这颗键**兼当一个状态点**:摆谱屏(屏 17)右上角那颗「重新点灯」正是
   * 「LED 通不通」的补救动作,把指示和补救合成一个控件,比另摆一颗只会变色的点省一格
   * ——而那一屏的右栏只剩 252px 给两个折叠块分。`bad` 走 `--bad`,不改几何。
   *
   * `pressed` 让这颗键当**开关**(屏 21 研究的「领地」):§11 举的两个例子
   * 「翻转棋盘 / 全屏」里,全屏本来就是个开关,所以开关不是这一槽的例外。
   * 给了值才渲染 `aria-pressed` —— 不给就还是按完弹回来的动作键,既有七处调用一个不受影响。
   */
  action?: {
    icon: IconName; label: string; onClick: () => void;
    state?: 'bad';
    pressed?: boolean;
  };
  testId?: string;
}) {
  if (segment && segment.options.length > 3) {
    // 静默截断会让第 4 段人间蒸发,谁也不知道它去哪了 —— 要响。
    throw new Error('§11:页控条的分段控件最多 3 段,再多就该换别的控件');
  }
  const switchByKey = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (!segment || (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight')) return;
    e.preventDefault();
    const i = segment.options.findIndex(([v]) => v === segment.value);
    const next = e.key === 'ArrowLeft'
      ? Math.max(0, i - 1)
      : Math.min(segment.options.length - 1, i + 1);
    segment.onChange(segment.options[next][0]);
  };
  return (
    <div className="kiosk-pagebar" data-testid={testId}>
      {onBack && (
        <button
          type="button"
          className="kiosk-pagebar__back"
          disabled={backBusy}
          aria-busy={backBusy || undefined}
          onClick={onBack}
        >
          <Icon name="arrow-left" />{backLabel}
        </button>
      )}
      {/* `<h2>` 不是 `<span>`:这是**这一屏的标题**,读屏的人靠标题层级跳转。
          稿子里是 span(静态 HTML 无所谓),真应用不能跟着丢语义。
          UA 给 h2 的上下 margin 由 `go-screens.css` 归零 —— 只归这一个类,不做全局归零。 */}
      <h2 className="kiosk-pagebar__title">
        {title}
        {sub ? <span className="kiosk-pagebar__sub">{sub}</span> : null}
      </h2>
      {/* 三者共用一个「把我推到右边去」的职责,所以 `__spacer` 只能挂在**第一个出现的**那个上。
          原来它写成「没有 segment 就挂 action」,加了 status 之后那条判断就不完整了。 */}
      {status && (
        <span className="kiosk-pagebar__status kiosk-pagebar__spacer">{status}</span>
      )}
      {action && (
        <button
          type="button"
          className={[
            'kiosk-pagebar__iconbtn',
            action.state === 'bad' && 'is-bad',
            !segment && !status && 'kiosk-pagebar__spacer',
          ].filter(Boolean).join(' ')}
          aria-label={action.label}
          aria-pressed={action.pressed}
          data-state={action.state}
          onClick={action.onClick}
        >
          <Icon name={action.icon} />
        </button>
      )}
      {segment && (
        <span
          className={`kiosk-seg${action || status ? '' : ' kiosk-pagebar__spacer'}`}
          role="radiogroup"
          aria-label={segment.ariaLabel ?? '视图'}
        >
          {segment.options.map(([value, label]) => (
            <button
              key={value}
              type="button"
              className="kiosk-seg__btn"
              role="radio"
              aria-checked={segment.value === value}
              // `aria-pressed` 不是重复:`tokens.css` 的选中态选择器认的是它
              // (`.kiosk-seg__btn[aria-pressed="true"]`),而 `aria-checked` 是 radio 的语义位。
              aria-pressed={segment.value === value}
              tabIndex={segment.value === value ? 0 : -1}
              onKeyDown={switchByKey}
              onClick={() => segment.onChange(value)}
            >{label}</button>
          ))}
        </span>
      )}
    </div>
  );
}
