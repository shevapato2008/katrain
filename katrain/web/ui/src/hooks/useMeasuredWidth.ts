import { useCallback, useEffect, useRef, useState } from 'react';

/** 还没量到宽度时先用的值。取 420 是因为四张图在此之前都写死 420，
 *  用它当起手值可以让「量到之前那一帧」和改造前逐像素一致，不闪。 */
export const FALLBACK_CHART_WIDTH = 420;

/**
 * 量出容器的实际渲染宽度，用来驱动 SVG 的 `viewBox` 宽度。
 *
 * **为什么需要它。** 仓里四张矢量图（`ScoreGraph` / `TrendChart` 的走势与棒棒糖 /
 * `ResearchAnalysisPanel`）原本都写死 `viewBox="0 0 420 H"` + `preserveAspectRatio="xMidYMid meet"`。
 * 右栏实宽小于 420 时整张图被等比缩小（320 档实测缩到 0.79），于是：
 *
 *  - 坐标轴文字跟着一起缩，`fontSize="11"` 屏上只有 8.7px —— 这正是 Fan 说的「文字太小」；
 *  - 右栏一旦宽过 420，图**不再变大**，多出来的宽度全变成图框内的死区。
 *    规范 §2.5 把这条记成「已知未解」，也是右栏顶档卡在 520 的直接原因。
 *
 * 让 `viewBox` 宽度 == 元素的 CSS 像素宽度，缩放比就恒为 1：绘图区随栏宽伸缩，
 * 而字号、线宽、圆点半径都按写下的数值原样呈现。
 *
 * **不要用 `aspect-ratio` 代替。** 规范 §2.5 记着：2026-08-30 试过让高度按比例长，
 * 结果在 <900 的堆叠态把 SVG 里的坐标轴文字一起放大到 27px、页面高出 188px，已撤回。
 * 要放大的是绘图区，不是字。
 *
 * **返回的是 callback ref，不是对象 ref。** 这些图挂在**条件渲染**的节点上
 * （棒棒糖图只在妙手/失误两个 tab 里存在）。用 `useRef` + `useEffect([])` 的话，
 * 效应在组件挂载时就跑完了，那时候节点还不存在、`ref.current` 是 null，
 * 之后切到那个 tab 节点才挂上来 —— 效应不会再跑，于是**永远量不到**。
 * callback ref 在节点挂载/卸载的那一刻被调用，正好对上。
 *
 * **兜底是有意的，也有代价。** jsdom 里 `test/setup.ts` 的 ResizeObserver 是空实现
 * （`observe()` 什么都不做），回调永不触发；没有兜底的话所有 jsdom 用例里这些图会整个消失。
 * 所以量到 0 时返回 `FALLBACK_CHART_WIDTH`。代价要说清：**jsdom 用例因此永远看到 420，
 * 对「宽度没传下去」这类缺陷是全盲的**（jsdom 本来就没有布局引擎，对布局事实无权作证）。
 * 真正的判据在真浏览器里量 —— 见 `tests/galaxy-report-tabs-visual.spec.ts` 里
 * 「图表宽度跟随右栏」那一组断言。
 */
export function useMeasuredWidth(
  fallback: number = FALLBACK_CHART_WIDTH,
): readonly [(el: Element | null) => void, number] {
  const [measured, setMeasured] = useState(0);
  const observerRef = useRef<ResizeObserver | null>(null);

  // 形参是 `Element` 不是 `HTMLElement`：ref 直接挂在 `<svg>` 上，而 `SVGSVGElement`
  // 不是 `HTMLElement` 的子类型。`getBoundingClientRect` 和 `ResizeObserver.observe`
  // 都只要求 `Element`，放宽到这一层刚好够用。
  const ref = useCallback((el: Element | null) => {
    observerRef.current?.disconnect();
    observerRef.current = null;
    if (!el) return;

    const read = () => {
      const w = Math.round(el.getBoundingClientRect().width);
      // 只在真的变了的时候 setState：ResizeObserver 会因为父级任何一次重排回调，
      // 每次都 setState 会把「量 → 渲染 → 量」变成一个稳定但白烧的循环。
      setMeasured((prev) => (prev === w ? prev : w));
    };

    read();
    const RO = typeof window !== 'undefined' ? window.ResizeObserver : undefined;
    if (!RO) return;
    const ro = new RO(read);
    ro.observe(el);
    observerRef.current = ro;
  }, []);

  useEffect(() => () => observerRef.current?.disconnect(), []);

  return [ref, measured > 0 ? measured : fallback] as const;
}

export default useMeasuredWidth;
