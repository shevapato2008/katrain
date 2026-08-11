import { expect, test, type Page } from '@playwright/test';
import { mkdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * **跨设备语义对照** —— 不是四图关卡。四图关卡在 `kiosk-ai-ladder-blocking-fourup.spec.ts`,
 * 那一条的参考图是 kiosk 自己常态下的右栏、同一个 1024×600 viewport。
 *
 * ⚠️ **这条里的像素差异一个都不作数。** 比的是两块**不同的**屏:1440×900 的双栏卡片,
 * 和 1024×600 的七寸触屏,后者是按拍板要求「视觉按 kiosk 重做」的,几何本来就不同。
 * 差异图里成片的亮区是预期 —— 而一张「亮区都是预期」的差异图比没有更坏,它训练人忽略
 * 差异图。所以这里的并排图只有一个用途:让人一眼看见同一格在两块屏上分别长什么样。
 *
 * 这条的全部价值在下面那组**语义断言**,它比的是两块屏在同一格里说的话:
 *   · 让位按钮的字必须逐字相同(它是那一格的价钱);
 *   · 代价行必须逐字相同;
 *   · 出路集合与顺序必须相同(继续 / 立即重试 / 让位)。
 * 文案共用 `features/aiLadder/blockingCopy`,所以这组断言真正守的是「有没有人在某一侧
 * 又抄了一份」—— 而 eslint 的 kiosk↛galaxy 边界保证了两边再也看不见彼此,抄了也没人发现。
 */

const GALAXY_VIEWPORT = { width: 1440, height: 900 };
const KIOSK_VIEWPORT = { width: 1024, height: 600 };
const OUT_DIR = resolve(
  process.cwd(),
  '../../../superpowers/tracks/golaxy-ai-ladder-parity/visual/kiosk-blocking/cross-device-semantics',
);

const readyStatus = (blocking: Record<string, unknown>) => ({
  view_state: 'ready',
  placement_state: {
    phase: 'placed',
    rung: { rung: 30, rank_name: '5段', certification_status: 'certified', availability: 'available', route: 'server' },
  },
  current_opponent: {
    rung: 30, rank_name: '5段', certification_status: 'certified', availability: 'available', route: 'server',
  },
  recent_ranked_results: ['win', 'loss', 'win', 'win', 'loss'],
  net_score: 1,
  pending_settlement: false,
  blocking_game: blocking,
});

const stubShell = async (page: Page) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup-token');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: 'tester', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/translations?lang=cn', (route) => route.fulfill({
    json: {
      lang: 'cn',
      translations: {
        Home: '首页', 'btn:Play': '对局', Research: '研究', Tsumego: '死活题',
        'analysis:report': '复盘', Live: '直播', 'kifu:library': '棋谱库', Tutorials: '教程',
        Settings: '设置', Logout: '退出登录',
      },
    },
  }));
  await page.route('**/api/v1/live/translations?lang=cn', (route) => route.fulfill({
    json: { players: {}, tournaments: {}, rounds: {}, rules: {} },
  }));
  await page.route('**/assets/img/logo-white.png', (route) => route.fulfill({
    path: resolve(process.cwd(), '../../../katrain/img/logo-white.png'),
  }));
};

/** 屏上真正说出来的话 —— 按钮按 DOM 顺序,因为顺序就是「先给用户看见哪一个」。 */
const readPanelSemantics = (page: Page, testId: string) => page.evaluate((id) => {
  const panel = document.querySelector(`[data-testid="${id}"]`) as HTMLElement | null;
  if (!panel) throw new Error(`找不到面板 ${id}`);
  const buttons = Array.from(panel.querySelectorAll('button'))
    .map((button) => (button.textContent || '').trim())
    .filter(Boolean);
  return { buttons, text: panel.innerText };
}, testId);

/** galaxy 的面板没有 data-testid,用它那句「未完成对局」定位到同一个容器。 */
const GALAXY_PANEL_INIT = () => {
  const heading = Array.from(document.querySelectorAll('p, span, div'))
    .find((node) => node.textContent?.trim() === '未完成对局');
  const panel = heading?.parentElement as HTMLElement | undefined;
  if (!panel) throw new Error('galaxy 面板没渲染出来');
  panel.setAttribute('data-testid', 'galaxy-ladder-blocking-panel');
};

const CASES: Array<{ slug: string; title: string; blocking: Record<string, unknown> }> = [
  {
    slug: '01-reserved',
    title: '从没开起来 —— 让掉不记成绩',
    blocking: {
      game_id: 'g1', state: 'reserved', ownership: 'other_device',
      user_color: 'B', opponent_rank_name: '业余 3 段',
    },
  },
  {
    slug: '02-active-current-resumable',
    title: '局还在下,就在这台机器上',
    blocking: {
      game_id: 'g1', state: 'active', ownership: 'current_device', session_id: 'sess-1',
      user_color: 'B', opponent_rank_name: '业余 3 段',
    },
  },
  {
    slug: '03-active-other',
    title: '局在另一台设备上',
    blocking: {
      game_id: 'g1', state: 'active', ownership: 'other_device',
      user_color: 'W', opponent_rank_name: '业余 3 段',
    },
  },
  {
    slug: '04-pending-retrying',
    title: '成绩还在送 —— 守卫 2 那一格',
    blocking: {
      game_id: 'g1', state: 'pending_settlement', ownership: 'current_device',
      user_color: 'B', opponent_rank_name: '业余 3 段',
      sync: {
        state: 'waiting', attempt: 2, max_attempts: 5, next_attempt_in_seconds: 252,
        last_http_status: null, last_error: 'timeout',
      },
    },
  },
  {
    slug: '05-pending-refused',
    title: '云端在事实上拒收',
    blocking: {
      game_id: 'g1', state: 'pending_settlement', ownership: 'current_device',
      user_color: 'B', opponent_rank_name: '业余 3 段',
      sync: {
        state: 'refused', attempt: 1, max_attempts: 5, next_attempt_in_seconds: null,
        last_http_status: 422, last_error: 'HTTP 422: rung mismatch',
      },
    },
  },
];

test.beforeAll(() => mkdirSync(OUT_DIR, { recursive: true }));
// 合成那一步要读前两步刚写出来的 PNG,而 playwright.config 是 fullyParallel。
test.describe.configure({ mode: 'serial' });

for (const testCase of CASES) {
  test(`跨设备语义对照 ${testCase.slug} — ${testCase.title}`, async ({ page }) => {
    await stubShell(page);
    await page.route('**/api/v1/ai-ladder/status', (route) => route.fulfill({
      json: readyStatus(testCase.blocking),
    }));

    // ① 参考图:galaxy 那块屏,在它自己的 viewport 下。
    await page.setViewportSize(GALAXY_VIEWPORT);
    await page.goto('/galaxy/play/ai?mode=rated');
    await expect(page.getByText('未完成对局')).toBeVisible();
    await page.evaluate(GALAXY_PANEL_INIT);
    const galaxy = await readPanelSemantics(page, 'galaxy-ladder-blocking-panel');
    await page.getByTestId('galaxy-ladder-blocking-panel')
      .screenshot({ path: resolve(OUT_DIR, `${testCase.slug}--reference-galaxy.png`) });

    // ② 实现图:kiosk 那块屏,在它自己的 viewport 下。
    await page.setViewportSize(KIOSK_VIEWPORT);
    await page.goto('/kiosk/play/ai/setup/ranked');
    await expect(page.getByTestId('kiosk-ladder-blocking-panel')).toBeVisible();
    const kiosk = await readPanelSemantics(page, 'kiosk-ladder-blocking-panel');
    await page.getByTestId('kiosk-ladder-blocking-panel')
      .screenshot({ path: resolve(OUT_DIR, `${testCase.slug}--implementation-kiosk.png`) });

    // ③ 语义断言 —— 这一条才是有牙齿的那个,像素差异一律不作数。
    expect(kiosk.buttons, `${testCase.slug}:两块屏给的出路不一样`).toEqual(galaxy.buttons);
    // 代价行:那一格的价钱,逐字相同。
    const cost = testCase.blocking.state === 'reserved'
      ? '那一局没能开起来，让掉它不记成绩'
      : testCase.blocking.state === 'active' && testCase.blocking.ownership === 'other_device'
        // 远端那格的代价多一句:云端看不见那台机器的发送队列,它可能已经下完了。
        ? '那一局会记为本局负；它若其实已下完，真实结果会被顶掉'
        : '那一局会记为本局负，并计入升降级';
    expect(galaxy.text).toContain(cost);
    expect(kiosk.text).toContain(cost);
    if (testCase.blocking.state === 'reserved') {
      // 硬要求:让掉什么都不记,两块屏都不许出现记负的说法。
      expect(galaxy.text).not.toMatch(/记为本局负|计为本局负|计入升降级/);
      expect(kiosk.text).not.toMatch(/记为本局负|计为本局负|计入升降级/);
    }
    // eslint-disable-next-line no-console
    console.log(`[semantics] ${testCase.slug} galaxy=${JSON.stringify(galaxy.buttons)} kiosk=${JSON.stringify(kiosk.buttons)}`);

    // ④ 并排 + 叠加差异,在画布里合成 —— 不引第三方图像依赖。
    const asDataUrl = (file: string) => `data:image/png;base64,${readFileSync(resolve(OUT_DIR, file)).toString('base64')}`;
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
      sideCtx.fillText('galaxy 1440x900 — 像素差异不作数', 4, 22);
      sideCtx.fillText('kiosk 1024x600 — 判据只有语义那张表', left.width + gap + 4, 22);

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
        referenceSize: [left.width, left.height],
        implementationSize: [right.width, right.height],
        changedRatio: Number((changed / (overlapWidth * height)).toFixed(3)),
      };
    }, {
      reference: asDataUrl(`${testCase.slug}--reference-galaxy.png`),
      implementation: asDataUrl(`${testCase.slug}--implementation-kiosk.png`),
    });

    await page.locator('#side').screenshot({ path: resolve(OUT_DIR, `${testCase.slug}--side-by-side.png`) });
    await page.locator('#diff').screenshot({ path: resolve(OUT_DIR, `${testCase.slug}--diff.png`) });
    // eslint-disable-next-line no-console
    console.log(`[fourup] ${testCase.slug} ${JSON.stringify(sizes)}`);
  });
}
