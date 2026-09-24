/**
 * 最小本地声明,只覆盖 `GolaxyScanPanel.tsx` 用到的那一个 API(`QRCode.toString`,
 * 渲染 SVG 字符串)。
 *
 * **不装 `@types/qrcode`**:那个包的 `index.d.ts` 开头有一行
 * `/// <reference types="node" />` —— 三斜线引用会强制把 `@types/node` 的全局声明
 * 拉进整个程序,哪怕 `tsconfig.app.json` 的 `"types"` 数组里没写 `"node"`(`types` 数组
 * 只挡「自动扫描 node_modules/@types 全量收编」那条路,挡不住某个包的 .d.ts 自己用
 * 三斜线显式引用)。拉进来之后,浏览器工程里 `window.setTimeout` 的返回类型会被
 * `@types/node` 的全局 `setTimeout` 重载污染成 `NodeJS.Timeout`,`EngineReadinessProvider.tsx`
 * 那种 `ReturnType<typeof window.setTimeout>` 就变成了 Node 类型,炸在跟这次改动完全
 * 无关的地方 —— 这正是本仓判例「不可变账本缺约束的代价不对称」的同类:依赖会通过
 * **传递的类型作用域**改变别处语义,「没改那份文件」不足以自证清白。
 */
declare module 'qrcode' {
  export interface QRCodeToStringOptions {
    type?: 'svg' | 'utf8' | 'terminal';
    margin?: number;
    errorCorrectionLevel?: 'low' | 'medium' | 'quartile' | 'high' | 'L' | 'M' | 'Q' | 'H';
  }

  const QRCode: {
    toString(text: string, options?: QRCodeToStringOptions): Promise<string>;
  };

  export default QRCode;
}
