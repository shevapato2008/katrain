import { expect, type Page } from '@playwright/test';

/**
 * 等一块 `<canvas>` **真的画上了东西**再往下走。
 *
 * ## 为什么需要它
 *
 * `waitForSelector('canvas')` 和 `expect(canvas).toBeVisible()` 都只证明**元素在**。
 * 而 `LiveBoard`(`components/live/LiveBoard.tsx:339-358`)先 `Promise.all` 预加载
 * **5 张 PNG**(board / B_stone / W_stone / inner / topmove),全部 `onload` 之后才
 * `setImagesLoaded(true)`,而绘制那个 effect 挂在这个标志上 —— **图没到齐之前一笔都不画**。
 *
 * 实测(`/kiosk/play`,同一份代码连开 6 次):元素出现那一刻 **4 次是空的、2 次已画**;
 * 1200ms 之后 6 次全部已画。canvas 尺寸每次都对(400×400 / CSS 274)。
 * ⇒ **约六七成的截图会是空盘**,而空盘和「盘真的坏了」在图上长得一模一样。
 *
 * 上一轮就是这么栽的:`92cfaae9` 的图有盘、`1a211a25` 的没有,被当成了字体改动引起的回归 ——
 * 而**一张空白截图不携带「谁让它空的」**,两种解释(真回归 / 撞上竞态)长得完全一样。
 *
 * ## 判据
 *
 * 数**非黑采样点**,不看元素状态。阈值取得很松(> 0 即可):这条闸要分的是
 * 「一笔没画」和「画了」,不是「画得对不对」——画得对不对归人眼和四图。
 *
 * ⚠️ **凡是截图里会出现 canvas 棋盘的 spec,按快门之前都要过这一关。**
 * 现在的消费者只有 galaxy 那条结算图(kiosk 侧的开局设置屏改布局 A 之后左栏是**内联 SVG**,
 * 没有图片加载、没有这个竞态)。B 块给 `/kiosk/play` 取图时会是第二个。
 */
export const waitForCanvasPainted = async (page: Page, selector = 'canvas', timeout = 10_000) => {
  await page.waitForFunction(
    (sel) => {
      const canvas = document.querySelector(sel) as HTMLCanvasElement | null;
      if (!canvas || canvas.width === 0 || canvas.height === 0) return false;
      const ctx = canvas.getContext('2d');
      if (!ctx) return false;
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      // 每 97 个像素采一次 —— 质数步长,避免和棋盘的周期性格线共振采样到同一类点上。
      for (let i = 0; i < data.length; i += 4 * 97) {
        if (data[i] > 40 || data[i + 1] > 40 || data[i + 2] > 40) return true;
      }
      return false;
    },
    selector,
    { timeout },
  );
  // 到这儿一定过了,写一条 expect 只为让失败信息说人话而不是抛 TimeoutError。
  expect(true, `${selector} 一直没画上东西`).toBe(true);
};
