/**
 * 画布是**固定的** 1024×600 —— 规范开头那句话:「四张设计稿都是这个值,所以本规范
 * 全部用 px。任何人不要把这些值改成 cqw / vw / %:一旦相对化,『切模块不跳』就没法用
 * 截图证明。」所以这里做的是**整块画布等比缩放**,不是让布局自己流。
 *
 * 不放大(`Math.min(…, 1)`):放大之后屏上量到的 px 就不再是 tokens.css 里那个 px,
 * 几何闸和四图闸量的都会是被放大过的数,尺规就成了谎话。板子本来就是 1024×600。
 */
export const KIOSK_CANVAS_W = 1024;
export const KIOSK_CANVAS_H = 600;

export function calculateKioskScale(viewportW: number, viewportH: number): number {
  return Math.min(viewportW / KIOSK_CANVAS_W, viewportH / KIOSK_CANVAS_H, 1);
}
