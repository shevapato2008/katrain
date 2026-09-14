import { expect, test } from '@playwright/test';

/**
 * 错题页(T1)的承重闸。
 *
 * 屏 13 本来那一支断言的是「满编 20 格一屏装得下、**不滚**」(`kiosk-shell-scroll.spec.ts`)。
 * 错题页复用同一副骨架,但格子数是「这一类里试过、还没做对的」**全部**题 —— 可以远多于 20
 * ⇒ 这一支**必须能滚**,而且滚到底最后一格在视口里。
 *
 * 「能不能滚」只认真浏览器 + 真滚轮(jsdom 没有布局引擎;`scrollTop = n` 证明不了用户能滚)。
 * 60 道错题是**造的输入**;溢不溢出、data-at、最后一格在哪,是浏览器算的**结论**。
 * 先断言前置状态成立 —— 造不出「装不下」,这条闸就没有被测对象,必须当场红。
 *
 * 变异:WRONG 取 5 道 ⇒ 红在 `expect(pre.cells, '没造出 60 道错题 —— 下面量的就不是「装不下」那一态').toBe(60)`
 * 这一行,报的就是这句消息(5 !== 60)——**不是** `waitForSelector` 的 30 秒 TimeoutError
 * (那是 2026-09-15 复审前的坑:等第 60 格出现,格子不够 60 时这一等就直接死等到超时,
 * 下面这条真正说得清「为什么」的断言反而永远不会被跑到)。
 */
test.use({ viewport: { width: 1024, height: 600 } });

const IDS = Array.from({ length: 90 }, (_, i) => `w${i}`);
const WRONG = IDS.slice(0, 60);

test('错题页:60 道装不下时通栏自己滚,真滚轮滚得到最后一格,滚动条不占宽', async ({ page }) => {
  await page.addInitScript((wrong) => {
    localStorage.setItem('token', 'kiosk-tsumego-wrong');
    localStorage.setItem('katrain_language', 'cn');
    // 进度钥匙分人(`tsumego_progress:u<id>`),下面 auth/me 回 id=1。
    localStorage.setItem('tsumego_progress:u1', JSON.stringify(
      Object.fromEntries(wrong.map((id) => [id, { completed: false, attempts: 1 }])),
    ));
  }, WRONG);
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') {
      return route.fulfill({ json: { id: 1, username: 'tester', rank: '5段', credits: 0 } });
    }
    if (path.startsWith('/api/v1/tsumego/levels/') && path.includes('/categories/')) {
      return route.fulfill({ json: IDS.map((id) => ({ id })) });
    }
    return route.fulfill({ json: {} });
  });
  await page.goto('/kiosk/tsumego/15k/capturing/wrong');
  // ⚠️ 只等**格子先出现**,不等第 60 格:等第 60 格的话,格子不够 60 时这一行自己先拿一个
  // 30 秒的 TimeoutError 死等,下面两条真正说得清「为什么」的断言反而**永远不会被执行到**——
  // Step 9 变异(WRONG 60→5)实测过这个坑(2026-09-15 team-lead 复审 Important)。
  await page.waitForSelector('.qgrid button');

  const pre = await page.evaluate(() => {
    const sc = document.querySelector('.kiosk-side__scroll') as HTMLElement;
    return { cells: document.querySelectorAll('.qgrid button').length, overflow: sc.scrollHeight - sc.clientHeight };
  });
  expect(pre.cells, '没造出 60 道错题 —— 下面量的就不是「装不下」那一态').toBe(60);
  expect(pre.overflow, '60 道还装得下 —— 前置状态没造出来,这条闸没有被测对象').toBeGreaterThan(100);

  const zone = page.locator('.kiosk-scrollzone').first();
  await expect(zone).toHaveAttribute('data-at', 'top');
  const geom = await page.evaluate(() => {
    const z = document.querySelector('.kiosk-scrollzone') as HTMLElement;
    const sc = z.querySelector('.kiosk-side__scroll') as HTMLElement;
    return { zoneW: Math.round(z.getBoundingClientRect().width), clientW: sc.clientWidth };
  });
  expect(geom.zoneW, '通栏不是 992').toBe(992);
  expect(geom.clientW, '滚动条占了布局宽度 —— 992 就不是 992 了').toBe(992);

  // **真滚轮**。
  await page.mouse.move(500, 300);
  await page.mouse.wheel(0, 5000);
  await expect.poll(() => zone.getAttribute('data-at')).toBe('end');

  const last = await page.evaluate(() => {
    const sc = document.querySelector('.kiosk-side__scroll') as HTMLElement;
    const cells = document.querySelectorAll('.qgrid button');
    const cell = cells[cells.length - 1] as HTMLElement;
    return {
      cellBottom: Math.round(cell.getBoundingClientRect().bottom),
      zoneBottom: Math.round(sc.getBoundingClientRect().bottom),
    };
  });
  expect(last.cellBottom, '滚到底了最后一格还在视口外').toBeLessThanOrEqual(last.zoneBottom);
  console.log(`[wrong-list] 溢出 ${pre.overflow}px(只记录,不作判据)`);
});
