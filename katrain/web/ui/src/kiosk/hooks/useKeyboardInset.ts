import { useEffect } from 'react';

/**
 * ⚠️ **软键盘会把聚焦的字段压在底下,而滚动区往往已经滚不动了。**
 *
 * 真浏览器量出来(屏 07 连接页那次):滚动区 clientH 460 / scrollH 610 ⇒ maxScroll 只有 150;
 * 而键盘高 188、上缘落在 y=412(带中文候选条时 246 / 上缘 354)——两个输入框滚到底时都在
 * 412 以下。键盘自己那句 `scrollIntoView` 需要 scrollTop≈294,比 maxScroll 还大,救不回来。
 *
 * ⇒ 聚焦时给滚动容器垫一段等于键盘高度的下内衬,**不动版式**:不重排段序、不改任何画出来的
 * 元素,四图仍然逐像素可比。键盘没加载(`.skbd` 不存在)时垫 0 —— 那就是没有键盘。
 *
 * **滚动容器是参数,不是写死的选择器。** 从 `PlatformConnectPage` 里提出来的时候,原逻辑
 * 写死了 `.kiosk-layout-b .kiosk-side__scroll` —— 登录页(`PlatformLoginPage`)没有那个滚动区,
 * 它自己的滚动容器是 `.xplogin__main`。照搬写死的选择器会得到一个「跑了、不报错、没效果」的 hook。
 */
export function useKeyboardInset(zoneSelector: string): void {
  useEffect(() => {
    const zone = document.querySelector<HTMLElement>(zoneSelector);
    if (!zone) return undefined;
    const inZone = (el: EventTarget | null) =>
      el instanceof HTMLElement && el.tagName === 'INPUT' && zone.contains(el);

    let rafId = 0;
    let blurTimer = 0;
    const onFocus = (e: FocusEvent) => {
      if (!inZone(e.target)) return;
      const el = e.target as HTMLElement;
      // 键盘挂在 body 上、在**缩放画布外面**,所以它量出来的 px 是屏幕 px,
      // 而内衬要写进画布坐标 —— 得先除以画布的缩放比。
      rafId = requestAnimationFrame(() => {
        rafId = 0;
        const keyboardPx = document.querySelector<HTMLElement>('.skbd')?.offsetHeight ?? 0;
        const canvasW = document.querySelector<HTMLElement>('.kiosk-screen')?.getBoundingClientRect().width;
        const scale = canvasW && canvasW > 0 ? canvasW / 1024 : 1;
        zone.style.paddingBottom = `${Math.round(keyboardPx / scale)}px`;
        el.scrollIntoView({ block: 'center' });
      });
    };
    const onBlur = (e: FocusEvent) => {
      if (!inZone(e.target)) return;
      blurTimer = window.setTimeout(() => {
        blurTimer = 0;
        if (!inZone(document.activeElement)) zone.style.paddingBottom = '';
      }, 150);
    };
    zone.addEventListener('focusin', onFocus);
    zone.addEventListener('focusout', onBlur);
    return () => {
      zone.removeEventListener('focusin', onFocus);
      zone.removeEventListener('focusout', onBlur);
      // **摘掉监听器不等于取消已经排上队的回调。** 这两个回调都会去摸 `document`,
      // 卸载之后再跑就是访问一个已经不存在的文档。在浏览器里这只是一次无害的写入,
      // 在 jsdom 里它是 `ReferenceError: document is not defined` —— 一条**未捕获异常**,
      // 于是 vitest 整批以非零退出码结束,而每一条用例都还是绿的
      // (2026-09-01 实测:1695 条全过、rc=1)。
      // 它是否触发只取决于测试调度,所以「今天没红」不代表没有这个洞。
      if (rafId) cancelAnimationFrame(rafId);
      if (blurTimer) clearTimeout(blurTimer);
      zone.style.paddingBottom = '';
    };
  }, [zoneSelector]);
}

export default useKeyboardInset;
