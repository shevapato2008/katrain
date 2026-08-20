import { expect, test, type Page } from '@playwright/test';

/**
 * 共享外壳的**承重闸**。量的是真浏览器算出来的布局结论,不是 CSS 里写了什么 ——
 * jsdom 没有布局引擎,对这些数字无权作证。
 *
 * 期望尽量写成**关系式**,具体像素只作记录:「中间区下缘停在 Dock 上沿」是判据,
 * 「504」只是它今天的值。带 px 的几条(1024×600 画布、外边距 16)是规范开头
 * 明写「全部用 px、任何人不要相对化」的那几个,它们就是判据本身。
 *
 * 本文件随外壳分层增长:
 *   Task 1 —— 画布 / `.kiosk` 作用域 / 中间区外框(本轮)
 *   Task 3 —— 顶栏逐像素
 *   Task 4 —— Dock 与层级
 */

const CANVAS = { width: 1024, height: 600 };

test.use({ viewport: CANVAS });

const boot = async (page: Page, path: string) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'kiosk-shell-geometry');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: 'tester', rank: '5段', credits: 0 },
  }));
  await page.goto(path);
  // `state: 'attached'` 不是 `'visible'`(默认):画布塌成 0×0 时元素照旧在 DOM 里,
  // 但 Playwright 判它不可见 —— 默认值会把「量出来是 0」变成一条 30 秒超时。
  await page.waitForSelector('.kiosk-screen', { state: 'attached' });
};

// 用 `page.evaluate` + `querySelector`,**不用 `locator.evaluate`**:后者会先等元素
// 「可见」。而本文件要防的头号故障(`.kiosk` 掉了 ⇒ `--kiosk-w/--kiosk-h` 求空 ⇒
// 画布 0×0)恰好会让元素变成不可见 —— 那时 locator 版会卡满 30 秒再报「hidden」,
// 把「量出来的数不对」糊成一条超时。querySelector 版当场把 0 摆出来。
const box = (page: Page, sel: string) => page.evaluate((s) => {
  const el = document.querySelector(s);
  if (!el) throw new Error(`没有这个元素: ${s}`);
  const r = el.getBoundingClientRect();
  return {
    x: Math.round(r.x), y: Math.round(r.y),
    w: Math.round(r.width), h: Math.round(r.height),
    right: Math.round(r.right), bottom: Math.round(r.bottom),
  };
}, sel);

test('画布固定 1024×600,视口正好等于它时不缩放', async ({ page }) => {
  await boot(page, '/kiosk/play');

  const screen = await box(page, '.kiosk-screen');
  expect(screen.w).toBe(CANVAS.width);
  expect(screen.h).toBe(CANVAS.height);
  // 视口 = 画布 ⇒ scale 恒为 1 ⇒ 居中之后正好铺满,原点在 (0,0)。
  // 这一条同时在证「translate(-50%,-50%) 的包含块是视口那一层」——
  // 中间多一个定位祖先的话,画布会被推到别处。
  expect(screen.x).toBe(0);
  expect(screen.y).toBe(0);
});

test('L1:中间区外框 x16–1008、上缘接顶栏下沿、下缘停在 Dock 上沿', async ({ page }) => {
  await boot(page, '/kiosk/play');

  const screen = await box(page, '.kiosk-screen');
  const content = await box(page, '.kiosk-content');

  expect(content.x - screen.x).toBe(16);                 // --content-x
  expect(screen.right - content.right).toBe(16);         // 左右对称,不是只钉左边
  expect(content.w).toBe(screen.w - 2 * 16);             // 992

  expect(content.y - screen.y).toBe(56);                 // --topbar-h
  expect(screen.bottom - content.bottom).toBe(82);       // --dock-h,L1 才有

  // ⚠️ 上面量的是**外框**(border-box),规范 §5 说的「内容从 y70 起、L1 停在 504」
  // 说的是**内沿** —— 差的正好是 `--content-pad-y` 上下各 14。两套数不矛盾,
  // 但混着读会以为对不上,所以这里把内沿也钉一次。
  const pad = await page.evaluate(() => {
    const cs = getComputedStyle(document.querySelector('.kiosk-content')!);
    return { top: cs.paddingTop, bottom: cs.paddingBottom };
  });
  expect(pad.top).toBe('14px');
  expect(pad.bottom).toBe('14px');
  expect(content.y + 14).toBe(70);
  expect(content.bottom - 14).toBe(504);

  console.log('[L1] content box =', content);
});

test('L2/L3:没有 Dock,中间区一路到画布下缘', async ({ page }) => {
  await boot(page, '/kiosk/settings');   // Task 4 之前 settings 仍是 L2

  const screen = await box(page, '.kiosk-screen');
  const content = await box(page, '.kiosk-content');

  await expect(page.locator('.kiosk-screen[data-level="1"]')).toHaveCount(0);
  expect(content.bottom).toBe(screen.bottom);
  expect(content.y - screen.y).toBe(56);
  console.log('[L2] content box =', content);
});

test('token 求得到值 —— .kiosk 作用域真的生效了', async ({ page }) => {
  await boot(page, '/kiosk/play');

  const vars = await page.evaluate(() => {
    const el = document.querySelector('.kiosk-screen');
    if (!el) throw new Error('没有 .kiosk-screen');
    const cs = getComputedStyle(el);
    return {
      railW: cs.getPropertyValue('--l1-rail-w').trim(),
      paper: cs.getPropertyValue('--paper').trim(),
      accent: cs.getPropertyValue('--accent').trim(),
      font: cs.fontFamily,
    };
  });

  // 空字符串 = var() 静默求空 = `.kiosk` 没生效。这一条就是为了把那种静默失败推红。
  // 四个值分别证明四件事:
  //   railW  —— tokens.css 进来了,且作用域覆盖到这里
  //   paper  —— go-tokens.css 也进来了(这个变量只有它有)
  //   accent —— go-tokens 排在 tokens 之后(否则会是象棋的琥珀 #e8a33d)
  //   font   —— fonts.css 的族名指得到
  expect(vars.railW).toBe('296px');
  expect(vars.paper).not.toBe('');
  expect(vars.accent.toUpperCase()).toBe('#58B57A');
  expect(vars.font).toContain('SmartBox');
});
