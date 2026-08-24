/**
 * 悬浮滚动条的位置计算。
 *
 * 从 `KioskScrollZone` 里拆出来的,因为**第二个使用者出现了**:屏 21 研究的 AI 推荐表
 * 也要一条(稿子给那块 body 挂的正是 `data-scrollbar`),而它不是右栏整栏、也不是
 * 「组标题 + 列表」那两种形态里的任何一种 —— 它是折叠块的体。
 *
 * 拆成独立模块而不是从组件文件里 `export`:那样会踩 react-refresh
 * (「组件文件里只许导出组件」),本仓已为 `baipuDrift` 走过同一步。
 *
 * 规范 §5:`scrollbar-width:none` 必须留着(让原生条占宽度,516/460 的算术当场就崩),
 * 而零宽度的代价是**完全没有位置指示** —— 能滚看不出来、滚到哪也不知道。
 * 两个都要,就只能自己画一条浮在上面的。
 */

/** 拇指最短 24 —— 再短就成了一个点,读不出比例。 */
const MIN_THUMB = 24;

/**
 * 只管条子,不管渐隐。渐隐用的是 `var(--ink)`(页背景),而折叠块的体是 `var(--panel)`,
 * 直接套上去颜色是错的 —— 所以折叠块那一路只要条子。
 *
 * @param scroll 真正在滚的那个元素
 * @param bar    `.kiosk-scrollbar`,必须挂在一个 `position:relative` 的祖先里
 * @returns 是否溢出(调用方可据此决定别的东西)
 */
export function syncScrollbar(scroll: HTMLElement | null, bar: HTMLElement | null): boolean {
  if (!scroll) return false;
  const overflow = scroll.scrollHeight - scroll.clientHeight;
  if (overflow < 1) {
    // 不溢出就把条子撤掉。挂一条永远亮着的条,等于谎报下面还有东西。
    if (bar) bar.style.display = 'none';
    return false;
  }
  if (bar) {
    const height = Math.max(MIN_THUMB, (scroll.clientHeight / scroll.scrollHeight) * scroll.clientHeight);
    bar.style.display = '';
    bar.style.top = `${scroll.offsetTop}px`;
    bar.style.height = `${height}px`;
    bar.style.transform = `translateY(${(scroll.scrollTop / overflow) * (scroll.clientHeight - height)}px)`;
  }
  return true;
}

/** 整条 scrollzone:条子 + 上下渐隐的三态(`data-at` = top / mid / end)。 */
export function syncScrollZone(
  rail: HTMLElement | null, scroll: HTMLElement | null, bar: HTMLElement | null,
): void {
  if (!rail || !scroll) return;
  if (!syncScrollbar(scroll, bar)) {
    rail.removeAttribute('data-at');
    return;
  }
  const overflow = scroll.scrollHeight - scroll.clientHeight;
  const atTop = scroll.scrollTop < 1;
  const atEnd = scroll.scrollTop >= overflow - 1;
  rail.dataset.at = atTop ? 'top' : atEnd ? 'end' : 'mid';
}
