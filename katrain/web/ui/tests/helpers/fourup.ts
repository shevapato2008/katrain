import type { Page } from '@playwright/test';
import { mkdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

export const KIOSK_VIEWPORT = { width: 1024, height: 600 } as const;

export interface FourUpOptions {
  page: Page;
  /** 参考图绝对路径,sample-go/shots/NN-*.png */
  referencePng: string;
  /** 产物目录,superpowers/tracks/kiosk-go-shell-align/visual/NN-*\/1024x600/ */
  outDir: string;
  /** 文件名前缀,如 '01-play' */
  slug: string;
  /** 画在并排图左半标签带上的一句话 */
  referenceCaption: string;
  /** 画在并排图右半标签带上的一句话 —— 预期差异必须写在图里 */
  implementationCaption: string;
}

export interface FourUpResult {
  /** 两边都有边的像素数。**它是「参考图真的读进来了」的证据**,不是相似度分。 */
  both: number;
  /** 只有参考图有边 */
  refOnly: number;
  /** 只有实现有边 */
  implOnly: number;
}

/**
 * 四图对比:参考 / 实现 / 并排 / 叠加+差异,同一 viewport 1024×600。
 *
 * ## 差异图为什么是**边缘图**不是像素比
 *
 * 稿子里有 26 处 `.note` 旁注(「围棋原来那张稿把它做成一张并列卡,是错的」这一类),
 * 它们是写给读稿人的,不上线 —— 已对齐的三家一处都没搬。像素比会把这些整块报成回归。
 * 边缘图去掉颜色只留结构:**红 = 只有参考有边,绿 = 只有实现有,白 = 两边都有**。
 *
 * ⚠️ **像素差异一个都不作数。** 几何的判据在 `kiosk-shell-geometry.spec.ts`(真浏览器
 * 量出来的数),不在这几张图上。这几张图答的是「构图 / 分块顺序 / 组件层级对不对」,
 * 而且**最终判据是 Fan 的眼睛**,不是返回的这三个数。
 *
 * 合成部分逐字节取自 `kiosk-layout-a-vs-xiangqi-setup.spec.ts:66-160` —— 那一份是
 * 上一轮验证过的,只把两个写死的路径和两句标签带提成参数。抽的判据是**消费者数**
 * (本轮 9 个),不是「看起来通用」。
 */
export async function captureFourUp(o: FourUpOptions): Promise<FourUpResult> {
  mkdirSync(o.outDir, { recursive: true });
  const implementationPath = resolve(o.outDir, `${o.slug}--implementation.png`);
  await o.page.screenshot({ path: implementationPath });

  const asDataUrl = (file: string) => `data:image/png;base64,${readFileSync(file).toString('base64')}`;

  const result = await o.page.evaluate(async ({ refSrc, implSrc, refCap, implCap }) => {
    const load = (src: string) => new Promise<HTMLImageElement>((done, fail) => {
      const image = new Image();
      image.onload = () => done(image);
      image.onerror = () => fail(new Error('图片读不出来'));
      image.src = src;
    });
    const [reference, implementation] = await Promise.all([load(refSrc), load(implSrc)]);

    const W = 1024;
    const H = 600;
    const draw = (image: HTMLImageElement) => {
      const canvas = document.createElement('canvas');
      canvas.width = W;
      canvas.height = H;
      const ctx = canvas.getContext('2d')!;
      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, W, H);
      // 等比缩到 1024 宽再顶端对齐裁到 600 —— 样张是 2048×1202(2× 的 1024×601)。
      const scale = W / image.width;
      ctx.drawImage(image, 0, 0, W, Math.round(image.height * scale));
      return ctx;
    };
    const refCtx = draw(reference);
    const implCtx = draw(implementation);

    // 边缘图:亮度对右邻和下邻的梯度。**去掉颜色只留结构** —— 两屏基调不同是规范要求的,
    // 直接比亮度会整屏通红,那张图证明不了任何关于骨架的事。
    const edges = (ctx: CanvasRenderingContext2D) => {
      const d = ctx.getImageData(0, 0, W, H).data;
      const lum = new Float32Array(W * H);
      for (let i = 0; i < W * H; i += 1) {
        lum[i] = 0.299 * d[i * 4] + 0.587 * d[i * 4 + 1] + 0.114 * d[i * 4 + 2];
      }
      const out = new Uint8Array(W * H);
      for (let y = 0; y < H - 1; y += 1) {
        for (let x = 0; x < W - 1; x += 1) {
          const i = y * W + x;
          const g = Math.abs(lum[i] - lum[i + 1]) + Math.abs(lum[i] - lum[i + W]);
          out[i] = g > 28 ? 1 : 0;
        }
      }
      return out;
    };
    const refEdges = edges(refCtx);
    const implEdges = edges(implCtx);

    const band = 34;
    const gap = 20;
    const side = document.createElement('canvas');
    side.width = W * 2 + gap;
    side.height = H + band;
    const sideCtx = side.getContext('2d')!;
    sideCtx.fillStyle = '#0f1416';
    sideCtx.fillRect(0, 0, side.width, side.height);
    sideCtx.drawImage(refCtx.canvas, 0, band);
    sideCtx.drawImage(implCtx.canvas, W + gap, band);
    sideCtx.fillStyle = '#93a49d';
    sideCtx.font = '600 14px system-ui, sans-serif';
    // ⚠️ 说明必须写在**图里**,不是写在旁边的文档里:图一旦离开它的说明,
    // 「界面对不对」和「稿子上那段旁注为什么没有」就混成一件事了。
    sideCtx.fillText(refCap, 4, 21);
    sideCtx.fillText(implCap, W + gap + 4, 21);

    const diff = document.createElement('canvas');
    diff.width = W;
    diff.height = H;
    const diffCtx = diff.getContext('2d')!;
    const out = diffCtx.createImageData(W, H);
    let both = 0;
    let refOnly = 0;
    let implOnly = 0;
    for (let i = 0; i < W * H; i += 1) {
      const a = refEdges[i];
      const b = implEdges[i];
      const p = i * 4;
      out.data[p + 3] = 255;
      if (a && b) { out.data[p] = 235; out.data[p + 1] = 235; out.data[p + 2] = 235; both += 1; }
      else if (a) { out.data[p] = 226; out.data[p + 1] = 104; out.data[p + 2] = 92; refOnly += 1; }
      else if (b) { out.data[p] = 88; out.data[p + 1] = 181; out.data[p + 2] = 122; implOnly += 1; }
    }
    diffCtx.putImageData(out, 0, 0);

    document.body.innerHTML = '';
    document.body.style.margin = '0';
    side.id = 'fourup-side';
    diff.id = 'fourup-diff';
    refCtx.canvas.id = 'fourup-ref';
    document.body.append(side, diff, refCtx.canvas);
    return { both, refOnly, implOnly };
  }, {
    refSrc: asDataUrl(o.referencePng),
    implSrc: asDataUrl(implementationPath),
    refCap: o.referenceCaption,
    implCap: o.implementationCaption,
  });

  await o.page.locator('#fourup-ref').screenshot({ path: resolve(o.outDir, `${o.slug}--reference.png`) });
  await o.page.locator('#fourup-side').screenshot({ path: resolve(o.outDir, `${o.slug}--side-by-side.png`) });
  await o.page.locator('#fourup-diff').screenshot({ path: resolve(o.outDir, `${o.slug}--diff.png`) });

  // `both === 0 && refOnly === 0` = 参考图读成了空图,**不是「实现全对」**。
  // 这是「0 是不是最优解」那条通则的实例:refOnly 小看着像好事,为 0 却是没加载。
  //
  // 变异记录(2026-08-20,Task 2 Step 4):把 referencePng 换成一张 8×8 纯黑 PNG,
  // 这一条当场红 ——「参考图没有任何边:/tmp/all-black.png 读成了空图」。
  // 正常那一支同一天用 sample-go/shots/01-play.png 跑通(both=7702)。**两支都执行过。**
  if (result.both === 0 && result.refOnly === 0) {
    throw new Error(`参考图没有任何边:${o.referencePng} 读成了空图,不是实现全对`);
  }
  return result;
}

/**
 * `waitForSelector` / `toBeVisible()` 只证明**元素在**,证明不了**画完了**。
 * 判据是**非黑采样点**:在元素上取 9 个点,全黑就是还没画。
 *
 * ⚠️ 这条判据的**边界**:它分的是「一笔没画」和「画了」,分不出「画了一半」。
 * 用在 `LiveBoard` 那种**整段绘制被 imagesLoaded 挡住**的失败上是够的
 * (`components/live/LiveBoard.tsx:339-358`:5 张 PNG 全部 onload 才置标志,
 * 标志为假时一笔都不画;实测 `/kiosk/play` 连开 6 次,元素出现那一刻 4 次全空)。
 *
 * **别拿它当通用的「画对了」。** `components/Board.tsx` 那种「先画底和格线、图到齐
 * 再覆盖」的组件上它**永远不会红** —— 上一轮给 6 个资产各塞 12 秒延迟实测过,
 * 六个 handler 全部命中而 spec 仍 5.2 秒通过。那一次的结论是把这段**删掉**
 * (`600b31f0`,标题写着「演示的结果是它在那屏装不上」):**挂一段结构上不可能生效
 * 的闸,比不挂更坏** —— 下一个人会把它读成「这屏有保护」。
 *
 * ⇒ 只在真会全黑的地方用。全仓今天渲染 `LiveBoard` 的路由只有 `/kiosk/play`。
 */
export async function waitForRealPixels(page: Page, selector: string) {
  await page.waitForSelector(selector);
  await page.waitForFunction((sel) => {
    const el = document.querySelector(sel);
    if (!el) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 8) return false;
    // canvas 元素直接采样;非 canvas 的(内联 SVG)只要有子节点即可 —— 它们不走图片预加载。
    if (!(el instanceof HTMLCanvasElement)) return el.childElementCount > 0;
    const canvas = document.createElement('canvas');
    canvas.width = 3;
    canvas.height = 3;
    const ctx = canvas.getContext('2d')!;
    ctx.drawImage(el, 0, 0, 3, 3);
    const d = ctx.getImageData(0, 0, 3, 3).data;
    for (let i = 0; i < 9; i += 1) {
      if (d[i * 4] > 12 || d[i * 4 + 1] > 12 || d[i * 4 + 2] > 12) return true;
    }
    return false;
  }, selector, { timeout: 10_000 });
}

/**
 * 把页面时间冻在参考图那一刻(16:40)。两件事一起解决:
 *   ① 四图产物变成**字节稳定**的 —— 顶栏渲染的是真时钟,否则每次重跑都会 dirty
 *      一批 PNG(哪怕代码一个字没改),「重跑零字节变化」这条本来能用的信号就没了;
 *   ② 顶栏时钟和参考图对得上,差异图里少一处注定的红。
 *
 * 必须在 `page.goto` 之前调 —— `addInitScript` 只对之后加载的文档生效。
 */
export async function freezeClock(page: Page, iso = '2026-08-20T16:40:00') {
  await page.addInitScript((frozen) => {
    const fixed = new Date(frozen).getTime();
    const RealDate = Date;
    // 只钉「现在」:带参数的 new Date(x) 仍按原样走,否则日期格式化会一起坏掉。
    class FrozenDate extends RealDate {
      constructor(...args: unknown[]) {
        if (args.length === 0) super(fixed);
        else super(...(args as ConstructorParameters<typeof RealDate>));
      }

      static now() { return fixed; }
    }
    (globalThis as unknown as { Date: DateConstructor }).Date = FrozenDate as unknown as DateConstructor;
  }, iso);
}

/**
 * 外壳上那些**从后端拿的静态件**。四图跑的是 vite dev server,它把 `/assets/**` 代理到
 * Python(:8001);后端没起的时候 logo 会 502,取出来的实现图左上角是一个**碎图标**。
 *
 * 2026-08-23 实测撞上:同一份代码,后端起着取出来的图和没起时取出来的**不是一张图** ——
 * 「重跑零字节变化」这条验收(Task 20 Step 3)因此证明不了任何事。
 * 这里把它钉在仓里那份真字节上,四图从此不依赖另一个进程在不在。
 */
/**
 * `/assets/img/*` 由 vite 代理到 **:8001**(Python 后端)。视觉这一套跑的是
 * `playwright.visual.config.ts`,它**不起后端** —— 那些请求全是 ECONNREFUSED。
 *
 * 只 stub logo 的时候,后果只在 canvas 棋盘那几屏上看得见,而且**看不出是坏的**:
 * `components/Board` 拿不到 `B_stone.png` / `W_stone.png` / `board.png` 就画出一块
 * **空盘**(木纹和子全没了),四图闸照样跑完、照样打印三个计数、照样报绿。
 * 2026-08-23 量出来:屏 05 对局的实现图和存档差 **212952 / 614400 像素(34.66%)**,
 * 而那 34% 全是「后端在不在」的差,不是代码的差。
 *
 * ⇒ 五张图一起从仓里喂进去。**判据是 scope §9.2 自己写下的那句**:
 * 「后端起着就绿、一停就红的东西不叫闸」—— 取图同理,
 * **一张随后端在不在而变的实现图,不是这一屏的实现图。**
 */
const SHELL_IMAGES = ['logo-white.png', 'B_stone.png', 'W_stone.png', 'board.png', 'inner.png', 'topmove.png'];

export async function stubShellAssets(page: Page) {
  for (const name of SHELL_IMAGES) {
    const file = resolve(process.cwd(), '../../img/', name);
    await page.route(`**/assets/img/${name}`, (route) => route.fulfill({
      path: file, contentType: 'image/png',
    }));
  }
}
