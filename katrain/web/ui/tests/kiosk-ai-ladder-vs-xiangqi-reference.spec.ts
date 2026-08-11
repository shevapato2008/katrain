import { test } from '@playwright/test';
import { mkdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * 跨棋类骨架对照:围棋挡局屏 ←→ 共享外壳的象棋样屏 `21-ranked-other-device-active.png`。
 *
 * ⚠️ **像素差异一个都不作数。** 象棋那屏是米黄浅色、1440 宽的样张,围棋是青毡深色 1024×600;
 * 拍板要的就是「骨架照象棋、配色用围棋」。这张图只回答一个问题:
 * **同一条骨架吗** —— seal + 衬线标题 + 小副题 / 状态条带字符前缀 / 两列事实格 /
 * 贴底并排等宽动作。看的是这五段在不在、顺序对不对,不是颜色和字号。
 *
 * 判据在别处:骨架的数由 `kiosk-ai-ladder-blocking-fourup.spec.ts` 对着**围棋常态右栏**量
 * (同 viewport、同盒子)。这条只产图给人看。
 */
const OUT_DIR = resolve(
  process.cwd(),
  '../../../superpowers/tracks/golaxy-ai-ladder-parity/visual/kiosk-blocking/vs-xiangqi-reference',
);
const XIANGQI_SHOT = resolve(
  process.cwd(),
  '../../../../smartbox-software-xiangqi-features/superpowers/shared/kiosk-shell'
  + '/sample-xiangqi/shots/21-ranked-other-device-active.png',
);
const GO_SHOT = resolve(
  process.cwd(),
  '../../../superpowers/tracks/golaxy-ai-ladder-parity/visual/kiosk-blocking/1024x600/04-active-other.png',
);

test('骨架对照:围棋挡局屏 ←→ 象棋样屏(像素不作数)', async ({ page }) => {
  mkdirSync(OUT_DIR, { recursive: true });
  const asDataUrl = (file: string) => `data:image/png;base64,${readFileSync(file).toString('base64')}`;

  await page.setViewportSize({ width: 1400, height: 900 });
  const size = await page.evaluate(async ({ left: leftSrc, right: rightSrc }) => {
    const load = (src: string) => new Promise<HTMLImageElement>((done, fail) => {
      const image = new Image();
      image.onload = () => done(image);
      image.onerror = () => fail(new Error('图片读不出来'));
      image.src = src;
    });
    const [left, right] = await Promise.all([load(leftSrc), load(rightSrc)]);
    // 等高缩放后并排 —— 两张原图尺寸不同(1440 样张 vs 1024 实屏),不缩放看不出骨架对应。
    const height = 620;
    const lw = Math.round(left.width * (height / left.height));
    const rw = Math.round(right.width * (height / right.height));
    const gap = 20;
    const band = 34;
    const canvas = document.createElement('canvas');
    canvas.width = lw + gap + rw;
    canvas.height = height + band;
    const ctx = canvas.getContext('2d')!;
    ctx.fillStyle = '#0f1416';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(left, 0, band, lw, height);
    ctx.drawImage(right, lw + gap, band, rw, height);
    ctx.fillStyle = '#93a49d';
    ctx.font = '600 15px system-ui, sans-serif';
    ctx.fillText('参考骨架：象棋样屏 21-ranked-other-device-active（像素不作数）', 4, 22);
    ctx.fillText('围棋实现：挡局屏 04-active-other @1024×600', lw + gap + 4, 22);
    document.body.innerHTML = '';
    document.body.style.margin = '0';
    canvas.id = 'side';
    document.body.append(canvas);
    return { width: canvas.width, height: canvas.height };
  }, { left: asDataUrl(XIANGQI_SHOT), right: asDataUrl(GO_SHOT) });

  await page.locator('#side').screenshot({ path: resolve(OUT_DIR, 'skeleton-side-by-side.png') });
  // eslint-disable-next-line no-console
  console.log(`[vs-xiangqi] ${JSON.stringify(size)}`);
});
