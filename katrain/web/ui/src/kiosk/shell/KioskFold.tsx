import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { Icon } from './icons';
import { syncScrollbar } from './scrollSync';

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
 * 开合状态默认**由本组件自己拿着**:它是纯粹的视图偏好,没有任何别的东西依赖它。
 *
 * 2026-09-02 加了**受控**那一支(`open` + `onToggle` 同时给才生效)。第二个使用者到了:
 * 屏 20 右栏里「AI 推荐」和「着手评价」两块**同一时刻只能开一块** —— 不是风格,是几何:
 * 44(页控条)+ 60(状态区)+ 2×30(两个折叠头)+ 40(显示开关)+ 36(翻手条)+ 5×12
 * = 300,展开那块的体只剩 216,而两块都展开要 380。手风琴的状态住在页面上,
 * 所以这里必须能受控。**只给了 `open` 不给 `onToggle` 仍走自持**(那种半受控写法
 * 会做出一个点不动的折叠头,比不支持更糟)。
 */
export function KioskFold({
  fold, title, value, defaultOpen = true, open: openProp, onToggle,
  grow = false, bodyClassName, scrollbar = false, testId, children,
}: {
  /** `data-fold`。规范拿它当这一块的身份(`eval` / `moves` / `ledger`),取图和断言都认它。 */
  fold: string;
  title: ReactNode;
  /** 标题行右端的**当前值**。收起后仍然显示 —— 见上面第 2 条。 */
  value?: ReactNode;
  defaultOpen?: boolean;
  /** 受控开合。**必须和 `onToggle` 成对给** —— 只给这个会做出一个点不动的折叠头。 */
  open?: boolean;
  onToggle?: () => void;
  /** 这一块吃掉同栏里剩下的高度(`.kiosk-fold--grow`)。一栏里最多一块。 */
  grow?: boolean;
  bodyClassName?: string;
  /**
   * 给这一块的体画一条**悬浮滚动条**(规范 §5.2)。**只在体自己会滚时才传。**
   *
   * 是 opt-in 而不是默认开:今天七个消费者里只有屏 21 研究的 AI 推荐表是「内容真的
   * 装不下、而且装不下是设计里就有的」那一种(稿子给那块 body 挂的正是 `data-scrollbar`)。
   * 其余六块要么装得下、要么已经有别的位置指示,默认打开等于给它们加一条永远不响的逻辑,
   * 还要把六屏的四图重取一遍。**它们该不该有,等各自那一轮再判。**
   *
   * 为什么非画不可:`scrollbar-width:none` 必须留着(让原生条占宽度,516/460 的算术当场崩),
   * 而零宽度的代价是屏上**一点位置指示都没有** —— 7 寸触摸屏没有 hover,
   * 表里第 9 行往后的内容就成了没人知道存在的东西。
   */
  scrollbar?: boolean;
  testId?: string;
  children: ReactNode;
}) {
  const [selfOpen, setSelfOpen] = useState(defaultOpen);
  const controlled = openProp !== undefined && onToggle !== undefined;
  const open = controlled ? openProp : selfOpen;
  const toggle = controlled ? onToggle : () => setSelfOpen((v) => !v);

  // callback ref + useState,**不能用 useRef + 空依赖 effect** —— 收起时体根本不在树上,
  // `useRef` 那种写法读到一次 null 就再也不重跑,展开回来条子永远不画。
  // (`KioskScrollZone` 的同一个坑,那儿的注释记着五子棋量到过「真的溢出 66px 却毫无指示」。)
  const [bodyEl, setBodyEl] = useState<HTMLDivElement | null>(null);
  const [barEl, setBarEl] = useState<HTMLElement | null>(null);
  const resync = useCallback(() => { if (scrollbar) syncScrollbar(bodyEl, barEl); }, [scrollbar, bodyEl, barEl]);
  // `children` 是信号:表是接口回来之后才渲出来的,那一刻必须重算。
  useEffect(() => { resync(); }, [children, open, resync]);

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
        onClick={toggle}
      >
        <span className="kiosk-fold__toggle"><Icon name="caret-down" /></span>
        {title}
        {value !== undefined && <b>{value}</b>}
      </button>
      <div
        className={bodyClassName ? `kiosk-fold__body ${bodyClassName}` : 'kiosk-fold__body'}
        ref={setBodyEl}
        onScroll={resync}
      >
        {children}
      </div>
      {/* `.kiosk-fold` 本来就带 `position:relative`,共享 CSS 那行的注释写的就是
          「悬浮滚动条挂在这儿」—— 这一槽是给它留好了的。 */}
      {scrollbar && open && <i className="kiosk-scrollbar" ref={setBarEl} />}
    </div>
  );
}
