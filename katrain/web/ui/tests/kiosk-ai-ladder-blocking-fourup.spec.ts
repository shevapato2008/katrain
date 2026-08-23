import { expect, test, type Page } from '@playwright/test';
import { mkdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * 四图对照,**同一个 1024×600 viewport**:参考 / 实现 / 并排 / 叠加差异。
 *
 * **参考图是 kiosk 自己常态下的右栏,不是 galaxy 那块屏。**
 *
 * 这块屏没有设计稿,所以判据只能是「新面板必须落在**已经验收过的那条骨架**上」——
 * 而那条骨架就在 kiosk 上:同一个 `[data-testid="ranked-settings-panel"]`,常态(没有挡局)
 * 下的样子,1024×600,已经验收过。参考图的作用是**给出判据**,不是给出像素;
 * 拿 galaxy 当参考会得到一张「亮区全是预期」的差异图,而那种图训练人忽略差异图。
 * (跨设备的语义对照仍然有,在 `kiosk-ai-ladder-cross-device-semantics.spec.ts`,
 * 那一条明说像素不作数。)
 *
 * 两张图取的是**同一个盒子**(整个右栏),所以差异图重新有牙齿:它该显示的是
 * 「换了内容之后,骨架有没有被带歪」—— 栏宽、内边距、`SubPageBar` 之下的起点、
 * 主按钮的尺寸与底边距。这些**恰恰是应该几乎不变的**,所以**亮区少才是对的**。
 *
 * 而真正的判据不交给眼睛:下面那组骨架断言把「不变」写成关系式,由浏览器算。
 * 差异图是给 Fan 看的,不是给 CI 判的。
 */

const VIEWPORT = { width: 1024, height: 600 };
const OUT_DIR = resolve(
  process.cwd(),
  '../../../superpowers/tracks/golaxy-ai-ladder-parity/visual/kiosk-blocking/fourup-1024x600',
);

const readyStatus = (blocking: Record<string, unknown> | null) => ({
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
    json: { lang: 'cn', translations: {} },
  }));
};

/** 骨架:换内容之后**应该一个都不变**的那几个数,全部由浏览器算。 */
const measureSkeleton = (page: Page, primaryButtonText: RegExp) => page.evaluate((pattern) => {
  const column = document.querySelector('[data-testid="ranked-settings-panel"]') as HTMLElement | null;
  if (!column) throw new Error('右栏不在 —— 这一屏根本没渲染出来');
  const rect = column.getBoundingClientRect();
  const style = getComputedStyle(column);
  const primary = Array.from(column.querySelectorAll('button'))
    .find((button) => new RegExp(pattern).test(button.textContent || ''));
  if (!primary) throw new Error(`右栏里找不到主按钮 /${pattern}/`);
  const primaryRect = primary.getBoundingClientRect();
  return {
    columnLeft: Math.round(rect.left),
    columnTop: Math.round(rect.top),
    columnWidth: Math.round(rect.width),
    columnHeight: Math.round(rect.height),
    columnPadding: `${style.paddingTop}/${style.paddingRight}/${style.paddingBottom}/${style.paddingLeft}`,
    primaryHeight: Math.round(primaryRect.height),
    primaryWidth: Math.round(primaryRect.width),
    // 主按钮底边到右栏底边 —— 「按钮离屏幕底多远」这条视觉节奏不该因为换了内容而变。
    primaryBottomInset: Math.round(rect.bottom - primaryRect.bottom),
    // 动作**行**的宽度。按钮个数按状态变(1 个或 2 个并排等宽),所以宽度不变式在行上,
    // 不在单个按钮上 —— 拿按钮去比,两个按钮那一格会红在一个不存在的缺陷上(实测 324 vs 656)。
    actionsRowWidth: (() => {
      const row = column.querySelector('[data-testid="kiosk-ladder-blocking-actions"]') as HTMLElement | null;
      const fallback = primary.parentElement as HTMLElement;
      return Math.round((row ?? fallback).getBoundingClientRect().width);
    })(),
  };
}, primaryButtonText.source);

const CASES: Array<{
  slug: string;
  title: string;
  blocking: Record<string, unknown>;
  primary: RegExp;
  /** 造错误态用:按一次认输并确认,让 `/end` 的 500 落到面板上。 */
  forceError?: true;
}> = [
  {
    slug: '01-reserved',
    title: '从没开起来 —— 让掉不记成绩',
    primary: /让掉它/,
    blocking: {
      game_id: 'g1', state: 'reserved', ownership: 'other_device',
      user_color: 'B', opponent_rank_name: '业余 3 段',
    },
  },
  {
    slug: '02-active-current-resumable',
    title: '局还在下,就在这台机器上',
    primary: /继续对局/,
    blocking: {
      game_id: 'g1', state: 'active', ownership: 'current_device', session_id: 'sess-1',
      user_color: 'B', opponent_rank_name: '业余 3 段',
    },
  },
  {
    slug: '03-active-other',
    title: '局在另一台设备上',
    primary: /认输那一局/,
    blocking: {
      game_id: 'g1', state: 'active', ownership: 'other_device',
      user_color: 'W', opponent_rank_name: '业余 3 段',
    },
  },
  {
    slug: '04-pending-retrying',
    title: '成绩还在送 —— 守卫 2 那一格',
    primary: /立即重试/,
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
    primary: /认输那一局/,
    blocking: {
      game_id: 'g1', state: 'pending_settlement', ownership: 'current_device',
      user_color: 'B', opponent_rank_name: '业余 3 段',
      sync: {
        state: 'refused', attempt: 1, max_attempts: 5, next_attempt_in_seconds: null,
        last_http_status: 422, last_error: 'HTTP 422: rung mismatch',
      },
    },
  },
  {
    // **只在出错时出现的那一格,取图必须专门造。** 它最容易漏(走顺利那条路永远撞不到),
    // 又往往最紧 —— 错误提示总是加在一块已经排满的屏上。四图里少了它,等于这块屏最挤的
    // 一帧从来没有人看过。
    slug: '06-error-state',
    title: '认输失败 —— 错误条 + 代价行 + 两个按钮同时在场',
    primary: /认输那一局/,
    forceError: true,
    blocking: {
      game_id: 'g1', state: 'pending_settlement', ownership: 'current_device',
      user_color: 'B', opponent_rank_name: '业余 3 段',
      sync: {
        state: 'exhausted', attempt: 5, max_attempts: 5, next_attempt_in_seconds: null,
        last_http_status: null, last_error: 'connection refused',
      },
    },
  },
];

test.beforeAll(() => mkdirSync(OUT_DIR, { recursive: true }));
// 合成那一步要读前两步刚写出来的 PNG,而 playwright.config 是 fullyParallel。
test.describe.configure({ mode: 'serial' });

for (const testCase of CASES) {
  test(`四图对照 ${testCase.slug} — ${testCase.title}`, async ({ page }) => {
    await page.setViewportSize(VIEWPORT);
    await stubShell(page);

    // ① 参考图:**kiosk 常态右栏**,同一个 viewport、同一个盒子。
    await page.route('**/api/v1/ai-ladder/status', (route) => route.fulfill({ json: readyStatus(null) }));
    await page.goto('/kiosk/play/ai/setup/ranked');
    await expect(page.getByRole('button', { name: /开始计分局/ })).toBeVisible();
    const reference = await measureSkeleton(page, /开始计分局/);
    await page.getByTestId('ranked-settings-panel')
      .screenshot({ path: resolve(OUT_DIR, `${testCase.slug}--reference-normal.png`) });

    // ② 实现图:同一个盒子,换成挡局面板。
    await page.unroute('**/api/v1/ai-ladder/status');
    await page.route('**/api/v1/ai-ladder/status', (route) => route.fulfill({
      json: readyStatus(testCase.blocking),
    }));
    if (testCase.forceError) {
      await page.route('**/api/v1/ai-ladder/games/*/end', (route) => route.fulfill({
        status: 500, json: { detail: 'boom' },
      }));
    }
    await page.reload();
    await expect(page.getByTestId('kiosk-ladder-blocking-panel')).toBeVisible();
    if (testCase.forceError) {
      await page.getByRole('button', { name: '认输那一局，在这里开新局' }).click();
      await page.getByRole('button', { name: '确认认输' }).click();
      await expect(page.getByRole('alert')).toBeVisible();
    }
    const implementation = await measureSkeleton(page, testCase.primary);
    await page.getByTestId('ranked-settings-panel')
      .screenshot({ path: resolve(OUT_DIR, `${testCase.slug}--implementation-blocking.png`) });

    // ③ 骨架断言 —— 判据在这里,不在差异图上。写成「相等」,具体像素只是记录。
    // 数先打出来再断言:断言一红,后面的 log 就不会执行,而那时最需要看的就是这两组数。
    // eslint-disable-next-line no-console
    console.log(`[skeleton] ${testCase.slug} reference=${JSON.stringify(reference)} implementation=${JSON.stringify(implementation)}`);
    expect(implementation.columnLeft, `${testCase.slug}:右栏左边界被带歪了`).toBe(reference.columnLeft);
    expect(implementation.columnTop, `${testCase.slug}:右栏在 SubPageBar 之下的起点变了`).toBe(reference.columnTop);
    expect(implementation.columnWidth, `${testCase.slug}:栏宽变了`).toBe(reference.columnWidth);
    expect(implementation.columnHeight, `${testCase.slug}:栏高变了`).toBe(reference.columnHeight);
    expect(implementation.columnPadding, `${testCase.slug}:内边距变了`).toBe(reference.columnPadding);
    // 高度钉的是**下限**不是相等:共享外壳的 `--btn-secondary-h` 是 38,而这一栏那个次级
    // 按钮是**认输/让掉**,是这块屏最重的一下 —— 38px 在七寸触屏上按不准,所以抬到 44
    // (外壳自己的 `--btn-primary-h` 也正是 44)。常态那个 48 是 katrain 自己的尺度,
    // **过渡期两套尺度并存**,拍板时就接受了。
    expect(
      implementation.primaryHeight,
      `${testCase.slug}:主按钮高 ${implementation.primaryHeight}px,掉破了 44px 触控下限 —— `
      + '七寸触屏上按钮高度就是可点面积',
    ).toBeGreaterThanOrEqual(44);
    // 这一版**没有外层卡片**了:挡局面板就是 `kiosk-side` 本身,卡是它里面那几个
    // `kiosk-section`。所以动作行与常态主按钮**同宽**(上一版是「减掉 34 的卡片内缩」——
    // 那条对上一版是对的,对这一版是错的:判据跟着盒子链走,链变了它就得变)。
    expect(
      implementation.actionsRowWidth,
      `${testCase.slug}:动作行没有撑满右栏内宽,常态主按钮 ${reference.primaryWidth},`
      + `实得 ${implementation.actionsRowWidth}`,
    ).toBe(reference.primaryWidth);

    // ④ 并排 + 叠加差异。同一个盒子、同一 viewport ⇒ **亮区少才是对的**。
    const asDataUrl = (file: string) => `data:image/png;base64,${readFileSync(resolve(OUT_DIR, file)).toString('base64')}`;
    const sizes = await page.evaluate(async ({ referenceUrl, implementationUrl }) => {
      const load = (src: string) => new Promise<HTMLImageElement>((done, fail) => {
        const image = new Image();
        image.onload = () => done(image);
        image.onerror = () => fail(new Error('图片读不出来'));
        image.src = src;
      });
      const [left, right] = await Promise.all([load(referenceUrl), load(implementationUrl)]);
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
      sideCtx.fillText('参考：kiosk 常态右栏（已验收骨架）1024x600', 4, 22);
      sideCtx.fillText('实现：同一个右栏，换成挡局面板 1024x600', left.width + gap + 4, 22);

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
        boxSize: [left.width, left.height],
        changedRatio: Number((changed / (overlapWidth * height)).toFixed(3)),
      };
    }, {
      referenceUrl: asDataUrl(`${testCase.slug}--reference-normal.png`),
      implementationUrl: asDataUrl(`${testCase.slug}--implementation-blocking.png`),
    });

    await page.locator('#side').screenshot({ path: resolve(OUT_DIR, `${testCase.slug}--side-by-side.png`) });
    await page.locator('#diff').screenshot({ path: resolve(OUT_DIR, `${testCase.slug}--diff.png`) });
    // 两张图取的是同一个盒子,尺寸必须逐像素相同 —— 不同就说明差异图在比两个不同的东西,
    // 那种图上的亮区没有意义。
    expect(sizes.boxSize, `${testCase.slug}:参考与实现的取图盒子尺寸不同,差异图无效`)
      .toEqual([implementation.columnWidth, implementation.columnHeight]);
    // eslint-disable-next-line no-console
    console.log(`[fourup] ${testCase.slug} ${JSON.stringify(sizes)}`);
  });
}
