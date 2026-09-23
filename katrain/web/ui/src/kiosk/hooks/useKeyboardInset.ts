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
 *
 * ⚠️ **2026-09-23(Task 5)真浏览器量出来:`scrollIntoView` 对「字段旁边紧跟着一个按钮」这种
 * 布局是瞎的。** 登录页聚焦密码字段时,`scrollIntoView({block:'end'|'center'})` 判断字段本身
 * 相对 `zone.clientHeight`**已经可见**(键盘是屏幕上的浮层,不改变 `clientHeight`,浏览器
 * 不知道那层浮层的存在)⇒ 干脆不滚,于是紧跟在字段后面的提交键(`.xpgo`)仍然压在键盘底下
 * (实测:`goBottom 441 > kbTop 421.9`,而 `fieldBottom 371` 早就 < kbTop,`scrollIntoView`
 * 判定「不用动」)。⇒ 改成聚焦时直接把 zone 滚到刚撑出来的新底(`scrollHeight - clientHeight`
 * ——这个差值就是上面那行加的 padding,不会多滚一像素):字段和它后面的提交键在这种短表单里
 * 本来就同时装得下,滚到底只是把整段一起往上提一截,不会把正在输入的字段推出视野。
 *
 * ⚠️ **第二个坑,比上面那个更隐蔽:我们赋的 `scrollTop` 会被浏览器自己的原生行为撤销,
 * 而这个撤销不经过 JS 的 `scrollTop` setter。** 这不是我们代码里调用的 `scrollIntoView`,
 * 也不是任何一段能读到调用栈的脚本——**Chromium 对触摸聚焦的可编辑元素,会在其可滚动祖先上
 * 自己做一次「把焦点元素滚回可见」的合成器动画**。真浏览器逐帧量出来(20ms 一帧):我们把
 * `scrollTop` 设成 44 后,接下来 6 帧里它被平滑地拉回 0(`44→43→31→12→3→1→0`,~140ms 收敛),
 * 而**在 `scrollTop` 的属性描述符上打点从没抓到第二次 `set` 调用**——说明这不是哪段 JS 在写
 * `scrollTop`,是引擎内部直接改的合成层偏移,JS 层面完全看不见、拦不住。**逐帧纠正循环
 * (每帧把 `scrollTop` 按回目标值)、`focus({ preventScroll: true })` 重新聚焦、给目标元素
 * 设 `scroll-margin-bottom` 三种都实测无效**——都是在跟一个不经过 JS 的动画拔河,赢不了。
 *
 * ⇒ 唯一管用的做法是**不跟它拔河,等它自己停**:监听 zone 的原生 `scroll` 事件,每次触发就
 * 把「应用我们目标值」这件事往后推;停止收到 `scroll` 事件一小段时间(说明原生动画已经跑完,
 * 不是靠猜一个固定延时)之后,再把 `scrollTop` 设成目标值一次——这次没有动画在竞争,稳稳生效
 * (`debug_kb3` 已验证:原生动画结束后手动赋值会一直保持,不会再被撤销)。
 */
export function useKeyboardInset(zoneSelector: string): void {
  useEffect(() => {
    const zone = document.querySelector<HTMLElement>(zoneSelector);
    if (!zone) return undefined;
    const inZone = (el: EventTarget | null) =>
      el instanceof HTMLElement && el.tagName === 'INPUT' && zone.contains(el);

    let rafId = 0;
    let settleTimer = 0;
    let blurTimer = 0;
    let watching = false;

    const applyTarget = () => {
      const target = zone.scrollHeight - zone.clientHeight;
      if (zone.scrollTop !== target) zone.scrollTop = target;
    };

    // 原生动画每一帧都会触发 scroll 事件——用它做「动画还在跑」的信号,不用猜时长。
    const onScroll = () => {
      window.clearTimeout(settleTimer);
      settleTimer = window.setTimeout(() => {
        settleTimer = 0;
        watching = false;
        zone.removeEventListener('scroll', onScroll);
        applyTarget();
      }, 60);
    };

    const onFocus = (e: FocusEvent) => {
      if (!inZone(e.target)) return;
      // 键盘挂在 body 上、在**缩放画布外面**,所以它量出来的 px 是屏幕 px,
      // 而内衬要写进画布坐标 —— 得先除以画布的缩放比。
      rafId = requestAnimationFrame(() => {
        rafId = 0;
        const keyboardPx = document.querySelector<HTMLElement>('.skbd')?.offsetHeight ?? 0;
        const canvasW = document.querySelector<HTMLElement>('.kiosk-screen')?.getBoundingClientRect().width;
        const scale = canvasW && canvasW > 0 ? canvasW / 1024 : 1;
        zone.style.paddingBottom = `${Math.round(keyboardPx / scale)}px`;
        applyTarget();
        // 挂 scroll 监听,等浏览器自己的「滚回可见」动画(如果这次 focus 触发了它)跑完再补一次。
        if (!watching) {
          watching = true;
          zone.addEventListener('scroll', onScroll);
        }
        onScroll();
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
      zone.removeEventListener('scroll', onScroll);
      // **摘掉监听器不等于取消已经排上队的回调。** 这两个回调都会去摸 `document`,
      // 卸载之后再跑就是访问一个已经不存在的文档。在浏览器里这只是一次无害的写入,
      // 在 jsdom 里它是 `ReferenceError: document is not defined` —— 一条**未捕获异常**,
      // 于是 vitest 整批以非零退出码结束,而每一条用例都还是绿的
      // (2026-09-01 实测:1695 条全过、rc=1)。
      // 它是否触发只取决于测试调度,所以「今天没红」不代表没有这个洞。
      if (rafId) cancelAnimationFrame(rafId);
      if (settleTimer) window.clearTimeout(settleTimer);
      if (blurTimer) clearTimeout(blurTimer);
      zone.style.paddingBottom = '';
    };
  }, [zoneSelector]);
}

export default useKeyboardInset;
