import { test } from '@playwright/test';
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

/**
 * 四图对照的后两张:并排图和叠加差异图。
 *
 * 前两张已经有了 —— 参考图从 mockup 里取(那是 Fan 拍板的那份),实现截图从上一条 spec 取。
 * 这条只负责把它们摆到一起,并且**摆的是同一个东西的两个版本**:两边都只有那块面板,
 * 不含侧边栏和段位区。整页截图里 90% 的像素两边都没有,拿它们做差异只会把真差别淹掉。
 *
 * 叠加差异这张要读的是**几何**:同一行文字/按钮在两版里落点差多少。因为参考图是结构稿
 * (字体是系统中文字、行高不同),**颜色差异一律不作数** —— 判据只有「元素有没有跑位、
 * 层级有没有换、该有的有没有少」。差异图里成片的亮区说明结构对不上,零星边缘是字体差异。
 */

const OUT_DIR = resolve(
  process.cwd(),
  '../../../superpowers/tracks/golaxy-ai-ladder-parity/visual/blocking-exits/1440x900',
);
const MOCKUP = resolve(
  process.cwd(),
  '../../../superpowers/tracks/golaxy-ai-ladder-parity/visual/blocking-exits/mockup.html',
);

// mockup 里第 N 个案例的「建议」面板 ←→ 实现的第 N 格。顺序就是 mockup 上的 01..06。
const PAIRS = [
  '01-active-current-resumable',
  '02-active-current-interrupted',
  '03-active-other-waiting',
  '04-active-other-takeable',
  '05-pending-waiting',
  '06-pending-releasable',
];

// ⚠️ 这条**读**另一条 spec 写出来的面板图,而 playwright.config 是 `fullyParallel: true`。
// 两条一起跑时它可能读到上一轮的旧图,于是合成出一张「实现没变」的并排图 —— 而源码、
// 产物、面板图三处都是新的。踩过一次:跑法必须是先取图、再合成两次调用。
test.describe.configure({ mode: 'serial' });

test('四图对照:参考 / 实现 / 并排 / 叠加差异', async ({ page }) => {
  mkdirSync(OUT_DIR, { recursive: true });
  test.skip(!existsSync(MOCKUP), `参考稿不在:${MOCKUP}`);

  // ① 参考图:mockup 每个案例的「建议」那一栏。
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(pathToFileURL(MOCKUP).href);
  const proposed = page.locator('.case .pair > div:nth-child(2) .panel');
  const count = await proposed.count();
  if (count < PAIRS.length) throw new Error(`参考稿只有 ${count} 个建议面板,需要 ${PAIRS.length}`);
  for (const [index, slug] of PAIRS.entries()) {
    await proposed.nth(index).screenshot({ path: resolve(OUT_DIR, `${slug}--reference.png`) });
  }

  // ② 并排 + 叠加差异,在画布里合成 —— 不引第三方图像依赖。
  const asDataUrl = (file: string) => `data:image/png;base64,${readFileSync(resolve(OUT_DIR, file)).toString('base64')}`;
  for (const slug of PAIRS) {
    const pair = {
      slug,
      reference: asDataUrl(`${slug}--reference.png`),
      implementation: asDataUrl(`${slug}--panel.png`),
    };

    const sizes = await page.evaluate(async ({ reference, implementation }) => {
      const load = (src: string) => new Promise<HTMLImageElement>((done, fail) => {
        const image = new Image();
        image.onload = () => done(image);
        image.onerror = () => fail(new Error('图片读不出来'));
        image.src = src;
      });
      const [left, right] = await Promise.all([load(reference), load(implementation)]);
      const gap = 24;
      const labelBand = 34;
      const height = Math.max(left.height, right.height);

      const side = document.createElement('canvas');
      side.width = left.width + gap + right.width;
      side.height = height + labelBand;
      const sideCtx = side.getContext('2d')!;
      sideCtx.fillStyle = '#0f0f0f';
      sideCtx.fillRect(0, 0, side.width, side.height);
      sideCtx.drawImage(left, 0, labelBand);
      sideCtx.drawImage(right, left.width + gap, labelBand);
      sideCtx.fillStyle = '#b8b5b0';
      sideCtx.font = '600 15px system-ui, sans-serif';
      sideCtx.fillText('参考稿（Fan 已拍板）', 4, 22);
      sideCtx.fillText('实现（1440x900 真浏览器）', left.width + gap + 4, 22);

      // 叠加差异:两边左上角对齐,按亮度取绝对差。颜色差异不作数,读的是几何。
      const overlapWidth = Math.min(left.width, right.width);
      const diff = document.createElement('canvas');
      diff.width = overlapWidth;
      diff.height = height;
      const diffCtx = diff.getContext('2d')!;
      const grab = (image: HTMLImageElement) => {
        const scratch = document.createElement('canvas');
        scratch.width = overlapWidth;
        scratch.height = height;
        const ctx = scratch.getContext('2d')!;
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, overlapWidth, height);
        ctx.drawImage(image, 0, 0);
        return ctx.getImageData(0, 0, overlapWidth, height);
      };
      const a = grab(left);
      const b = grab(right);
      const out = diffCtx.createImageData(overlapWidth, height);
      let changed = 0;
      for (let i = 0; i < out.data.length; i += 4) {
        const lumA = 0.299 * a.data[i] + 0.587 * a.data[i + 1] + 0.114 * a.data[i + 2];
        const lumB = 0.299 * b.data[i] + 0.587 * b.data[i + 1] + 0.114 * b.data[i + 2];
        const delta = Math.abs(lumA - lumB);
        if (delta > 40) changed += 1;
        out.data[i] = delta > 40 ? 255 : 0;
        out.data[i + 1] = delta > 40 ? Math.max(0, 200 - delta) : 0;
        out.data[i + 2] = 0;
        out.data[i + 3] = 255;
      }
      diffCtx.putImageData(out, 0, 0);

      document.body.innerHTML = '';
      document.body.style.margin = '0';
      document.body.append(side, diff);
      side.id = 'side';
      diff.id = 'diff';
      return {
        sideWidth: side.width,
        sideHeight: side.height,
        diffWidth: diff.width,
        diffHeight: diff.height,
        changedRatio: changed / (overlapWidth * height),
        referenceHeight: left.height,
        implementationHeight: right.height,
      };
    }, pair);

    await page.locator('#side').screenshot({ path: resolve(OUT_DIR, `${slug}--side-by-side.png`) });
    await page.locator('#diff').screenshot({ path: resolve(OUT_DIR, `${slug}--diff.png`) });
    // eslint-disable-next-line no-console
    console.log(`[fourup] ${slug} ${JSON.stringify(sizes)}`);
    await page.goto(pathToFileURL(MOCKUP).href);
  }
});
