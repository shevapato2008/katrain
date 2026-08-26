import type { Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, resolve } from 'node:path';

import { parsePo } from './po';
import PINNED from './reference-shots.json' with { type: 'json' };

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
  // 参考图那一半住在**另一个仓**,按登记的指纹取 —— 见 `resolveReferenceShot`。
  const referencePng = resolveReferenceShot(o.referencePng);
  mkdirSync(o.outDir, { recursive: true });
  const implementationPath = resolve(o.outDir, `${o.slug}--implementation.png`);
  /**
   * `animations: 'disabled'` —— 把有限时长的 CSS 过渡**快进到终值**再拍。
   *
   * 不加它时,屏 27 的实现图在两个状态之间来回,连跑两次差 12017 像素:滚动区底部那道
   * 渐隐(`tokens.css` 的 `.kiosk-scrollzone::after`)带 `transition: opacity .12s`,
   * 而截图正撞在这 120 毫秒里 —— 两态**几何完全相同**,只有渐变中段的透明度不同。
   * 那不是产品缺陷,是取图撞上了动画;代价是这一屏的存档在 12000 像素以下什么都判不了。
   *
   * 快进到终值也比「等它 120ms」对:终值是用户最终看到的那一帧,而等多久是另一个
   * 随机数。参考图那半是静态 PNG,本来就没有这个问题。
   */
  await o.page.screenshot({ path: implementationPath, animations: 'disabled' });

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
    refSrc: asDataUrl(referencePng),
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
    throw new Error(`参考图没有任何边:${referencePng} 读成了空图,不是实现全对`);
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

/**
 * ## 第二样:翻译表
 *
 * `i18n.ts` 开机拉 `/api/translations?lang=cn`,拉不到就**每一句都回落到代码里那个默认串**。
 * 后端没起的时候屏上写的是 `chinese` 和 `2d`,而设备上写的是「中国」和「2 段」——
 * **同一份代码,两句不同的话**。2026-08-26 在屏 10 上肉眼撞见:存档里是中文,重跑出来是英文键。
 * (同一件事 2026-08-26 之前已经在屏 20 上发生过一次并被误判成「实现改了」。)
 *
 * 表从**仓里那份 `.po`** 生成,不是 `.mo`:`.mo` 在 `.gitignore` 里,
 * 拿它当输入等于「闸的绿取决于本机跑过没跑过 `i18n.py`」。
 * 实测:`.po` 解析出来和后端 `/api/translations` 吐的**976 条一字不差**。
 */
export async function stubTranslations(page: Page, lang = 'cn') {
  const table = parsePo(resolve(process.cwd(), `../../i18n/locales/${lang}/LC_MESSAGES/katrain.po`));
  await page.route('**/api/translations*', (route) => route.fulfill({
    json: { lang, translations: table },
  }));
}

/**
 * 后端那几样**静态件**一次性钉住:图片 + 翻译表。
 *
 * 名字从 `stubShellAssets` 改过来 —— 它现在管的不只是图片,
 * 而是「这一屏的样子里有多少取决于另一个进程在不在」这一整类。
 */
export async function stubBackendStatics(page: Page, lang = 'cn') {
  for (const name of SHELL_IMAGES) {
    const file = resolve(process.cwd(), '../../img/', name);
    await page.route(`**/assets/img/${name}`, (route) => route.fulfill({
      path: file, contentType: 'image/png',
    }));
  }
  await stubTranslations(page, lang);

  /**
   * 直播那张**人名 / 赛事名**对照表(`/api/v1/live/translations`,盒子上走
   * `/api/v1/board/live/...` 的代理)。它和上面那张不是一回事:
   * 上面那张的正本在仓里(`.po`),**这一张没有** —— 它是每套部署自己的远端数据。
   *
   * ⇒ 这里钉成**空表**,并接受它的后果:`i18n.translatePlayer(name)` 是
   * `players[name] || name`,空表 ⇒ 名字原样上屏。
   * **所以四图的 fixture 里,人名和赛事名必须写成「屏上最终该长的样子」**,
   * 不能指望这张表把它们翻过去 —— 那张表在取图这台机器上永远是空的。
   *
   * 不钉的话它每次 502,而 `liveTranslations` 变成 `null`(同样是原样上屏)——
   * 结果碰巧一样,但那是「另一个进程恰好不在」换来的,不是判据。
   */
  await page.route('**/live/translations*', (route) => route.fulfill({
    json: { lang, players: {}, tournaments: {}, rounds: {}, rules: {} },
  }));
}

const DESIGN_REPO = resolve(process.cwd(), '../../../../smartbox-software');
const SHOT_PATH = 'superpowers/shared/kiosk-shell/sample-go/shots';
const SHOT_CACHE = resolve(tmpdir(), 'kiosk-go-shots');

const sha256 = (buf: Buffer | string) => createHash('sha256').update(buf).digest('hex');

/**
 * 拿到**这一屏的存档当时照的那份稿子**,返回一个能读的绝对路径。
 *
 * ## 为什么不能直接用设计仓工作树里那份
 *
 * 四图的**输入有一半在另一个仓**,而那个仓有自己的分支,还同时被好几个会话切来切去。
 * 2026-08-26 实测撞上:本赛道后半程 25 张稿子的新版本全在
 * `feat/kiosk-go-lobby-2026-08-24` 上,**没并进 main**;那个仓切回 main 之后重跑四图,
 * 九屏的参考图**悄悄换成了旧稿**,而闸照样全绿、三个计数照样打印 ——
 * 它们比的已经不是同一件东西了。
 *
 * 「参考图读进来了」(`both === 0 && refOnly === 0` 那条)挡不住这个:
 * **读进来的确实是一张真图,只是不是那一张。** ⇒ 判据落在**字节**上。
 * `reference-shots.json` 记的是每一屏该照的那份稿子的 sha256 和它所在的分支 ——
 * 那正是「Fan 那次是照着这张确认的」里隐含的那个前提,现在它被写下来了。
 *
 * 对不上就**从 git 里按登记的分支取**(只读,不碰那个仓的工作树),缓存到临时目录。
 * 判据和 `stubBackendStatics` 是同一条,只是又往外走了一层:
 * **一张随「另一个仓停在哪条分支」而变的参考图,不是这一屏的参考图。**
 *
 * 稿子**真的更新了**的时候这里会抛 —— 那是对的:重取之前先看清稿子哪儿变了,
 * 然后把新图和新指纹放进同一次提交。
 */
export function resolveReferenceShot(referencePng: string): string {
  const name = basename(referencePng);
  const pin = (PINNED as Record<string, { sha256: string; shotFrom: string }>)[name];
  if (!pin) {
    throw new Error(`参考图 ${name} 没有登记指纹 —— 新增一屏时要写进 tests/helpers/reference-shots.json`);
  }

  if (existsSync(referencePng) && sha256(readFileSync(referencePng)) === pin.sha256) return referencePng;

  const cached = resolve(SHOT_CACHE, `${pin.sha256}-${name}`);
  if (existsSync(cached)) return cached;

  let blob: Buffer;
  try {
    blob = execFileSync('git', ['-C', DESIGN_REPO, 'show', `${pin.shotFrom}:${SHOT_PATH}/${name}`],
      { maxBuffer: 64 * 1024 * 1024 });
  } catch {
    throw new Error(
      `参考图 ${name} 取不到:工作树那份和登记的指纹对不上,`
      + `而设计仓里也没有 \`${pin.shotFrom}\` 这条引用。\n`
      + '  要么去 smartbox 那边把那条分支取回来,要么稿子真的改了 —— 那就重取四图并更新指纹。',
    );
  }
  if (sha256(blob) !== pin.sha256) {
    throw new Error(
      `参考图 ${name} 变了:\`${pin.shotFrom}\` 上现在那份和登记的指纹对不上。\n`
      + `  登记 ${pin.sha256.slice(0, 16)}… / 那条分支上现在是 ${sha256(blob).slice(0, 16)}…\n`
      + '  稿子改了 ⇒ 先看清哪儿变了,再重取四图,新图和新指纹放进同一次提交。',
    );
  }
  mkdirSync(SHOT_CACHE, { recursive: true });
  writeFileSync(cached, blob);
  return cached;
}

/** 参考图这一半有没有问题;没问题返回 `null`。给 `test.skip(...)` 做前置检查用。 */
export function shotProblem(referencePng: string): string | null {
  try {
    resolveReferenceShot(referencePng);
    return null;
  } catch (error) {
    return error instanceof Error ? error.message : String(error);
  }
}
