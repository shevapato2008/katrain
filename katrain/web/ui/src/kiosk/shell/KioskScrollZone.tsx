import { type ReactNode, useCallback, useEffect, useState } from 'react';

/**
 * 规范 §5.2:右栏视口写死 680×434,内容可以更高 —— 右栏**可滚**,且必须自己画一条悬浮滚动条。
 *
 * 共享包(`tokens.css` §5 那一段)只给**几何、渐隐和条子的画法**;
 * **状态机和条子的位置全是消费方的活** —— 那一段的注释自己写着这句。
 *
 * 两种形态:
 *   形态 1 整栏滚  —— `.kiosk-side` 自己就是 scrollzone(对弈 / 训练营首页 / 棋谱 / 课程 / 设置)
 *   形态 2 头尾固定 —— 只有中间那条会长的列表滚,组标题和底下的卡不动(复盘)。传 `grow`。
 */

function sync(rail: HTMLElement | null, scroll: HTMLElement | null, bar: HTMLElement | null): void {
  if (!rail || !scroll) return;
  const overflow = scroll.scrollHeight - scroll.clientHeight;
  if (overflow < 1) {
    // 不溢出:两条都撤掉。挂一条永远亮着的渐隐,等于谎报下面还有东西 —— G8 诚实态那条。
    rail.removeAttribute('data-at');
    if (bar) bar.style.display = 'none';
    return;
  }
  const atTop = scroll.scrollTop < 1;
  const atEnd = scroll.scrollTop >= overflow - 1;
  rail.dataset.at = atTop ? 'top' : atEnd ? 'end' : 'mid';
  if (bar) {
    // 拇指最短 24 —— 再短就成了一个点,读不出比例。
    const height = Math.max(24, (scroll.clientHeight / scroll.scrollHeight) * scroll.clientHeight);
    bar.style.display = '';
    // 形态 2 下 `offsetTop` 量的正是组标题占掉的那一截 = 滚动视口的起点
    // (`.kiosk-scrollzone` 带 position:relative,offsetParent 就是它)。
    bar.style.top = `${scroll.offsetTop}px`;
    bar.style.height = `${height}px`;
    bar.style.transform = `translateY(${(scroll.scrollTop / overflow) * (scroll.clientHeight - height)}px)`;
  }
}

interface KioskScrollZoneProps {
  children: ReactNode;
  /** 形态 2:整栏不滚,只有这一段会长的列表滚。不传就是形态 1。 */
  grow?: boolean;
  /** 形态 2 专用:不参与滚动的组标题。它留在 scrollzone 里,是为了让渐隐能避开它。 */
  head?: ReactNode;
  /**
   * 换了一批内容就回到顶部。**不是锦上添花**:滚动容器是同一个 DOM 节点,React 只换里面的行,
   * `scrollTop` 会原样留着 —— 翻到第 2 页时列表还停在第 1 页滚到的位置,前几行在视野之外。
   * 国象在真浏览器里量到过 **558px**(棋谱库翻页),静态截图看不出来。
   * 规范 §5 防跳铁律 4 也要求切 L1 模块时归零。
   */
  resetKey?: string | number;
  /**
   * 挂在 scrollzone 根上的额外类。**只为一件事存在**:形态 2 的顶部渐隐位置
   * (`tokens.css:555`)按「头 = 一条组标题」写死了,头里多放东西的屏得自己把它挪下去。
   * 复盘屏展开搜索时用 `has-search`。不是给屏级配色/几何开的口子。
   */
  className?: string;
}

export function KioskScrollZone({ children, grow, head, resetKey, className }: KioskScrollZoneProps) {
  // callback ref + useState,**不能用 useRef + 空依赖 effect** —— 滚动节点首帧不一定存在
  // (复盘详情拿不到棋谱时整条右栏是另一棵树),`useRef` 那种写法读到一次 null 就再也不重跑,
  // 悬浮条永远不画。五子棋量到过:列表真的溢出 66px,屏上一条位置指示都没有。
  const [rail, setRail] = useState<HTMLElement | null>(null);
  const [scroll, setScroll] = useState<HTMLDivElement | null>(null);
  const [bar, setBar] = useState<HTMLElement | null>(null);
  const resync = useCallback(() => sync(rail, scroll, bar), [rail, scroll, bar]);

  // `ResizeObserver` 在这儿**不会触发**:`tokens.css` 把 `.kiosk-side__scroll` 钉成
  // `height:100%`,子元素长高时盒子一动不动,回调一次都不响。所以只能靠 children 变化
  // 这个信号手动重算 —— 列表是接口回来之后才渲出来的,那一刻必须重算。
  useEffect(() => { resync(); }, [children, resync]);

  useEffect(() => {
    if (resetKey === undefined || !scroll) return;
    scroll.scrollTop = 0;
    resync();                        // 回到顶部之后渐隐和条子也要跟着回 top 态
  }, [resetKey, scroll, resync]);

  const inner = (
    <>
      {head}
      <div className="kiosk-side__scroll" ref={setScroll} onScroll={resync}>{children}</div>
      <i className="kiosk-scrollbar" ref={setBar} />
    </>
  );

  const extra = className ? ` ${className}` : '';
  return grow ? (
    <section className={`kiosk-section kiosk-section--grow kiosk-scrollzone${extra}`} ref={setRail}>{inner}</section>
  ) : (
    <div className={`kiosk-side kiosk-scrollzone${extra}`} ref={setRail}>{inner}</div>
  );
}
