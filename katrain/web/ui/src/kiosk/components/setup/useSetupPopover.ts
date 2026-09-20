import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from 'react';
import { useSetupPopoverHost } from './SetupPopoverHost';

/**
 * 开局设置那两种弹层(下拉格、自定贴目条)共用的开合与定位。
 *
 * 提成 hook 而不是让两个组件各抄一份,是因为**定位那几行就是这一版的设计约束本身**:
 * 弹层必须留在右栏里(盖不到左边那块盘)、下面放不下要翻上去、右边放不下要贴着
 * 触发件自己的右边缘往左推(看得出是哪一格开的)。抄两份就是两条会各自漂的实现。
 */
export function useSetupPopover(anchorRef: RefObject<HTMLElement | null>) {
  const host = useSetupPopoverHost();
  const popRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [style, setStyle] = useState<{ top: number; left: number } | null>(null);

  useLayoutEffect(() => {
    if (!open || !host || !anchorRef.current || !popRef.current) return;
    const ar = anchorRef.current.getBoundingClientRect();
    const hr = host.getBoundingClientRect();
    const ph = popRef.current.offsetHeight;
    const pw = popRef.current.offsetWidth;
    const below = ar.bottom - hr.top + 6;
    // 下面放不下就翻上去;再放不下就贴栏顶。**绝不伸到栏外** —— 伸出去就盖到盘上了。
    const top = below + ph > hr.height ? Math.max(4, ar.top - hr.top - ph - 6) : below;
    // 右边放不下就贴着**触发件自己的右边缘**往左推,不是贴栏的右边缘。
    let left = ar.left - hr.left;
    if (left + pw > hr.width - 2) left = ar.right - hr.left - pw;
    setStyle({ top, left: Math.max(2, left) });
  }, [open, host, anchorRef]);

  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); setOpen(false); } };
    document.addEventListener('click', close);
    document.addEventListener('keydown', onKey, true);
    return () => { document.removeEventListener('click', close); document.removeEventListener('keydown', onKey, true); };
  }, [open]);

  useEffect(() => { if (!open) setStyle(null); }, [open]);

  return { host, open, setOpen, popRef, style } as const;
}
