import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from 'react';
import { useSetupPopoverHost } from './SetupPopoverHost';

/**
 * 开局设置那两种弹层(下拉格、自定贴目条)共用的开合与定位。
 *
 * 提成 hook 而不是让两个组件各抄一份,是因为**定位那几行就是这一版的设计约束本身**:
 * 弹层必须留在右栏里(盖不到左边那块盘)、下面放不下要翻上去、右边放不下要贴着
 * 触发件自己的右边缘往左推(看得出是哪一格开的)。抄两份就是两条会各自漂的实现。
 *
 * **位置直接写进 DOM,不过 state。** 先量后定位天然要两步(渲染出来才量得到),
 * 走 state 就是「effect 里 setState」—— 多一次渲染,而且那一帧位置是错的。
 * 所以弹层先以 `visibility: hidden` 渲染,量完在同一个 layout effect 里落位并显形:
 * 用户永远看不到中间那一帧。
 */
export function useSetupPopover(anchorRef: RefObject<HTMLElement | null>) {
  const host = useSetupPopoverHost();
  const popRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  useLayoutEffect(() => {
    const anchor = anchorRef.current;
    const pop = popRef.current;
    if (!open || !host || !anchor || !pop) return;
    const ar = anchor.getBoundingClientRect();
    const hr = host.getBoundingClientRect();
    // 单列的弹层跟着触发件的宽度走;两列三列自己撑(CSS 里的 `min-width`)。
    if (!pop.classList.contains('su-pop--2') && !pop.classList.contains('su-pop--3')) {
      pop.style.minWidth = `${ar.width}px`;
    }
    const ph = pop.offsetHeight;
    const pw = pop.offsetWidth;
    const below = ar.bottom - hr.top + 6;
    // 下面放不下就翻上去;再放不下就贴栏顶。**绝不伸到栏外** —— 伸出去就盖到盘上了。
    const top = below + ph > hr.height ? Math.max(4, ar.top - hr.top - ph - 6) : below;
    // 右边放不下就贴着**触发件自己的右边缘**往左推,不是贴栏的右边缘。
    let left = ar.left - hr.left;
    if (left + pw > hr.width - 2) left = ar.right - hr.left - pw;
    pop.style.top = `${top}px`;
    pop.style.left = `${Math.max(2, left)}px`;
    pop.style.visibility = 'visible';
  }, [open, host, anchorRef]);

  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); setOpen(false); } };
    document.addEventListener('click', close);
    document.addEventListener('keydown', onKey, true);
    return () => { document.removeEventListener('click', close); document.removeEventListener('keydown', onKey, true); };
  }, [open]);

  return { host, open, setOpen, popRef } as const;
}
