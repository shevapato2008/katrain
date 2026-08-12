import { test } from '@playwright/test';
import { mkdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * 布局 A 那一屏的**四图关卡**:参考图 / 实现截图 / 并排 / 差异,同一 viewport。
 *
 * ## 参考物为什么是 `02-setup` 而不是 `21-ranked-other-device-active`
 *
 * 协调方点的是后者。我换成了前者,理由是**参考物要和被参考的东西是同一类屏**:
 * `01-setup-my-black` 是**常态开局设置屏**,而 `21-ranked-…` 是象棋的**挡局屏**(那一类的
 * 参考已经在 `kiosk-ai-ladder-vs-xiangqi-reference.spec.ts` 里,对的就是围棋挡局屏)。
 * `sample-xiangqi/shots/02-setup.png` 是**象棋自己的 L2 布局 A 开局设置屏** ——
 * 同一个骨架、同一个层级、同一套控件规则,拿它对照才回答得了「这屏是不是那副骨架」。
 * 上一轮那次四图被打回,原因正是**参考物不对**;这次先说清换了什么、为什么换。
 *
 * ## 三张图各自答什么(说清楚才不会被读成别的)
 *
 * · **并排** —— 骨架五段在不在、顺序对不对:盘吃满左边 / 页控条在右栏顶(返回在最左)/
 *   分组标签 + 选择组 / 说明行 / 贴底满宽主按钮。
 * · **差异** —— 用**边缘图**比,不是像素比。两屏一个米黄浅色一个青毡深色,直接比亮度
 *   会整屏通红,那张图只会证明「两种棋类配色不同」,而这是**规范要求的**(各棋类保留基调)。
 *   边缘图把颜色去掉只留结构:**红 = 只有参考图有一条边,绿 = 只有实现有,白 = 两边都有**。
 * · **实现截图** —— 单看这一屏自己成不成立。
 *
 * ⚠️ **像素差异一个都不作数**,和挡局屏那条同一句。几何的判据在
 * `kiosk-ai-ladder-layout-a-geometry.spec.ts`(真浏览器量的 8 个数),不在这几张图上。
 */

const OUT_DIR = resolve(
  process.cwd(),
  '../../../superpowers/tracks/golaxy-ai-ladder-parity/visual/kiosk-layout-a/vs-xiangqi-setup',
);
const XIANGQI_SETUP = resolve(
  process.cwd(),
  '../../../../smartbox-software-xiangqi-features/superpowers/shared/kiosk-shell'
  + '/sample-xiangqi/shots/02-setup.png',
);

test('四图对照:围棋开局设置屏 ←→ 象棋 02-setup(同为 L2 布局 A)', async ({ page }) => {
  mkdirSync(OUT_DIR, { recursive: true });

  // ① 实现截图 —— 常态(没有挡局),执黑。
  await page.setViewportSize({ width: 1024, height: 600 });
  await page.addInitScript(() => {
    localStorage.setItem('token', 'kiosk-layout-a-fourup');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: 'tester', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/v1/ai-ladder/status', (route) => route.fulfill({
    json: {
      view_state: 'ready',
      placement_state: { phase: 'placed', rung: { rung: 30, rank_name: '5段', certification_status: 'certified', availability: 'available', route: 'server' } },
      current_opponent: { rung: 30, rank_name: '5段', certification_status: 'certified', availability: 'available', route: 'server' },
      recent_ranked_results: [], net_score: 0, pending_settlement: false, blocking_game: null,
    },
  }));
  await page.goto('/kiosk/play/ai/setup/ranked');
  await page.waitForSelector('[data-testid="kiosk-setup-board"]');
  const implementationPath = resolve(OUT_DIR, '01-setup--implementation.png');
  await page.screenshot({ path: implementationPath });

  // ② 合成。参考图是 2048×1202 的 2× 样张,等高缩放到实现图的高度再比。
  const asDataUrl = (file: string) => `data:image/png;base64,${readFileSync(file).toString('base64')}`;
  const result = await page.evaluate(async ({ refSrc, implSrc }) => {
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
      // 等比缩放到 1024 宽再顶端对齐裁到 600 —— 样张是 2048×1202(2× 的 1024×601)。
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
    sideCtx.fillText('参考骨架：象棋样屏 02-setup（同为 L2 布局 A · 像素与配色不作数）', 4, 21);
    // ⚠️ 这句必须写在**图里**,不是写在旁边的文档里:合成态一旦离开它的说明,
    // 「界面对不对」和「后端有没有」就混成一件事了 —— 会有人指着这张图说「认证链是通的」。
    sideCtx.fillText('围棋实现：开局设置屏 @1024×600 · 「已认证」是 fixture 造的态（_CERTIFIED_RUNGS 现为空集，真机不会出现）', W + gap + 4, 21);

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
    side.id = 'side';
    diff.id = 'diff';
    refCtx.canvas.id = 'ref';
    document.body.append(side, diff, refCtx.canvas);
    return { both, refOnly, implOnly };
  }, { refSrc: asDataUrl(XIANGQI_SETUP), implSrc: asDataUrl(implementationPath) });

  await page.locator('#ref').screenshot({ path: resolve(OUT_DIR, '01-setup--reference-xiangqi.png') });
  await page.locator('#side').screenshot({ path: resolve(OUT_DIR, '01-setup--side-by-side.png') });
  await page.locator('#diff').screenshot({ path: resolve(OUT_DIR, '01-setup--diff.png') });
  // eslint-disable-next-line no-console
  console.log(`[layout-a-fourup] 边缘像素 both=${result.both} refOnly=${result.refOnly} implOnly=${result.implOnly}`);
});
