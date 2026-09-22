import { expect, test, type Page } from '@playwright/test';
import { KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';
import { kioskMeJson } from './helpers/kioskIdentity';

/**
 * 屏 27 设置 · AI 段位详情**就地展开**之后的承重实测(设置赛道 ST4 / ST3-关于)。
 *
 * 展开是「会长的东西」:它往右栏那条受限高度的滚动列里一次多塞三五行。jsdom 没有布局引擎,
 * 下面每一条都只能在真浏览器里量。判据先写死再读数(具体像素只记录,不作判据):
 *  · 该滚的是 `.kiosk-side__scroll` 自己(不是页面,也不是 `.kiosk-side`);
 *  · 展开后它**自己**能滚到底(写大 scrollTop 读回 = scrollHeight − clientHeight),
 *    真滚轮也拨得动;
 *  · 展开那几行一行都不被压扁(= `--row-h` 52)—— 行的容器是 flex 列,少了 flex:none
 *    会先被压扁再滚(tokens.css 那条注释 2026-07-29 量出来过 33px);
 *  · 滚到最后一行时它整行落在滚动区的可视框里,不被裁;
 *  · 页面不横向 / 纵向溢出;
 *  · 展开之后点导航,落点在视口顶 0–8px(负值 = 被卷出顶部),高亮就是被点的那一项 ——
 *    导航用 `getBoundingClientRect` 相减算滚动量,两边原点同是视口,**坐标系一致**;
 *    展开改变的是它上面那几组的高度,这一条量的就是「展开之后还跳得准」。
 */

test.use({ viewport: KIOSK_VIEWPORT });

// 造到**最满**的那一态:定级中(多一行「当前对手」)+ 成绩在途(多一行提醒)+ 五盘记录。
const LADDER = {
  view_state: 'ready',
  placement_state: { phase: 'placement', completed_games: 3, total_games: 5 },
  current_opponent: { rung: 17, rank_name: '4级', certification_status: 'provisional', availability: 'available', route: 'server' },
  recent_ranked_results: ['win', 'loss', 'win', 'win', 'loss'],
  net_score: 1,
  pending_settlement: true,
};

async function boot(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'kiosk-settings-expand');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({ json: kioskMeJson() }));
  await page.route('**/api/v1/ai-ladder/**', (route) => route.fulfill({ json: LADDER }));
  await page.route('**/api/v1/health', (route) => route.fulfill({
    json: { status: 'ok', version: '1.17.1', engines: { local: 'reachable', cloud: 'error_502' } },
  }));
  await page.goto('/kiosk/settings');
  await page.waitForSelector('[data-testid="ai-ladder-account-summary"]');
}

const highlighted = (page: Page) => page.evaluate(() =>
  [...document.querySelectorAll('[data-testid="settings-nav"] button')]
    .filter((b) => b.getAttribute('aria-current') === 'true').map((b) => b.textContent));

/** 被点的那一组的上缘 − 滚动区可视框上缘。 */
const landing = (page: Page, group: string) => page.evaluate((g) => {
  const scroll = document.querySelector('.kiosk-side__scroll') as HTMLElement;
  const el = document.querySelector(`[data-group="${g}"]`) as HTMLElement;
  return el.getBoundingClientRect().top - scroll.getBoundingClientRect().top;
}, group);

test('展开 AI 段位详情:右栏自己能滚到底、行不被压扁、不被裁、页面不溢出', async ({ page }) => {
  await boot(page);
  const before = await page.evaluate(() => (document.querySelector('.kiosk-side__scroll') as HTMLElement).scrollHeight);
  await page.getByRole('button', { name: '查看AI段位详情' }).click();
  await page.waitForSelector('[data-testid="ladder-detail"]');

  const m = await page.evaluate(() => {
    const scroll = document.querySelector('.kiosk-side__scroll') as HTMLElement;
    const rowH = parseFloat(getComputedStyle(document.querySelector('.kiosk') as HTMLElement).getPropertyValue('--row-h'));
    const detailRows = [...document.querySelectorAll('[data-testid="ladder-detail"] .kiosk-row')] as HTMLElement[];
    const last = detailRows[detailRows.length - 1];
    // 把最后一行滚进来(和导航同一种算法),再看它落没落在可视框里。
    scroll.scrollTop += last.getBoundingClientRect().bottom - scroll.getBoundingClientRect().bottom;
    const sb = scroll.getBoundingClientRect();
    const lb = last.getBoundingClientRect();
    const out = {
      rowH,
      heights: detailRows.map((r) => r.getBoundingClientRect().height),
      lastInside: lb.top >= sb.top - 0.5 && lb.bottom <= sb.bottom + 0.5,
      sh: scroll.scrollHeight, ch: scroll.clientHeight,
      doc: { sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,
        sh: document.documentElement.scrollHeight, ch: document.documentElement.clientHeight },
      top: 0,
    };
    scroll.scrollTop = 1e6;
    out.top = scroll.scrollTop;
    return out;
  });
  console.log('[settings-expand]', JSON.stringify({ before, ...m }));

  expect(m.heights.length, '展开之后一行都没有 —— 这条量的是空的').toBeGreaterThanOrEqual(4);
  expect(m.sh, '展开没有让右栏变长').toBeGreaterThan(before);
  for (const h of m.heights) expect(h, '展开那几行被压扁了').toBe(m.rowH);
  expect(m.lastInside, '最后一行滚进来之后仍被裁掉').toBe(true);
  expect(Math.abs(m.top - (m.sh - m.ch)), '右栏滚不到底').toBeLessThanOrEqual(1);
  expect(m.doc.sw).toBeLessThanOrEqual(m.doc.cw);
  expect(m.doc.sh).toBeLessThanOrEqual(m.doc.ch);

  // 程序能滚 ≠ 手指拨得动。
  await page.evaluate(() => { (document.querySelector('.kiosk-side__scroll') as HTMLElement).scrollTop = 0; });
  const bb = (await page.locator('.kiosk-side__scroll').boundingBox())!;
  await page.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
  await page.mouse.wheel(0, 300);
  await expect.poll(() => page.locator('.kiosk-side__scroll').evaluate((el) => el.scrollTop),
    { message: '真滚轮拨不动右栏' }).toBeGreaterThan(0);
});

for (const expanded of [false, true]) {
  test(`${expanded ? '展开之后' : '收起时'}点导航:落点在视口顶、高亮就是被点的那一项(含最后一项「关于」)`, async ({ page }) => {
    await boot(page);
    if (expanded) {
      await page.getByRole('button', { name: '查看AI段位详情' }).click();
      await page.waitForSelector('[data-testid="ladder-detail"]');
    }
    for (const [label, group] of [['声音', 'sound'], ['关于', 'about'], ['实体棋盘', 'board']] as const) {
      await page.getByTestId('settings-nav').getByRole('button', { name: label }).click();
      const dy = await landing(page, group);
      expect(dy, `${label}:落点被卷出顶部`).toBeGreaterThanOrEqual(-0.5);
      expect(dy, `${label}:没滚到视口顶`).toBeLessThanOrEqual(8);
      // 高亮挂在 scroll 事件上 —— 等事件跑完再看它有没有被弹回前一项(尾部留白不够时会这样)。
      await expect.poll(() => highlighted(page), { message: `${label}:高亮被弹走了` }).toEqual([label]);
    }
  });
}
