import { createContext, useContext } from 'react';

/**
 * 开局设置三屏的下拉弹层**挂在右栏(`.kiosk-rail`)上**,不挂在它里面那个滚动盒里。
 *
 * 两个理由,都是实测出来的:
 *  · 滚动盒是 `overflow-y:auto`(`.kiosk-side__scroll`),伸出去的绝对定位层会被裁掉 ——
 *    而弹层比一格高得多,裁掉就只剩顶上一行。
 *  · 挂在 rail 上顺带保证了弹层**永远盖不到左边那块盘**。原版设计稿拒绝下拉的理由
 *    就是「弹层正好盖住左边那块盘」,而那块盘画的正是「按下开始之后会出现的局面」——
 *    调让子时它是唯一的反馈,盖住它等于把反馈挡了。
 *
 * 所以这里给一个宿主元素,`SetupSelect` 用 portal 送进去。
 */
export const SetupPopoverHost = createContext<HTMLElement | null>(null);

export function useSetupPopoverHost(): HTMLElement | null {
  return useContext(SetupPopoverHost);
}
