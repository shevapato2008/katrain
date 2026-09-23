import { type ReactNode } from 'react';

/**
 * ⚠️ **整棵 kiosk 树的视口盒子 —— 它是承重的,不是排版留白。**
 *
 * 它原来是屏幕旋转那一层包裹。旋转 2026-07-08 按「硬件不再旋转」删了入口(合并 `2bebfd5e`),
 * 旋转机器 2026-09 也清掉了,可那一层即使在不旋转时也渲染这只
 * `fixed / 100vw / 100vh / overflow:hidden` 的盒子,而它同时是:
 *  · `.kiosk` 画布的**包含块** —— `KioskFrame` 按 `absolute; top/left:50%` 居中,原点就是它;
 *  · 登录页的**高度来源** —— `LoginPage` 在 `KioskLayout` 外面,写的是 `height:100%`;
 *  · 整棵树的**裁切边界**。
 * ⇒ 删的是旋转,不是视口。几何一个像素都不许变(`tests/kiosk-viewport-geometry.spec.ts` 守这条)。
 *
 * `100vw/100vh` 在这里是对的:它在 1024×600 画布**外面**,职责就是铺满视口 ——
 * `kiosk-shell-contract.spec.ts` 闸一因此永久豁免这一个文件(原先豁免的是那一层旋转包裹)。
 */
function KioskViewport({ children }: { children: ReactNode }) {
  return (
    <div
      className="kiosk-viewport"
      data-testid="kiosk-viewport"
      style={{
        position: 'fixed', top: 0, left: 0,
        width: '100vw', height: '100vh', overflow: 'hidden', transformOrigin: 'top left',
      }}
    >
      {children}
    </div>
  );
}

export default KioskViewport;
