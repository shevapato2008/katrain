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
  // ⚠️ 这里原来用的是 `/kiosk/settings`。Task 4 把「设置」放进了 Dock(规范 §1),
  // 它现在是 **L1** —— 拿它当 L2 的样本会证反。换成对弈设置页,那是货真价实的二级页。
  await boot(page, '/kiosk/play/ai/setup/free');

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

test('§6 顶栏:通栏贴顶恒 56 高、左簇顺序与间距、右簇贴右缘', async ({ page }) => {
  await boot(page, '/kiosk/play');

  const screen = await box(page, '.kiosk-screen');
  const topbar = await box(page, '.kiosk-topbar');

  // 这三条**替换**了原 `__tests__/Header.test.tsx` 里那条 jsdom 的
  // `toHaveStyle({height:'56px'})` —— 那个数是 jsdom 照着内联样式回读的,
  // 对布局无权作证。同一件事在这里由浏览器量。
  expect(topbar.x).toBe(screen.x);              // 通栏贴边,不留左右外边距
  expect(topbar.y).toBe(screen.y);
  expect(topbar.w).toBe(screen.w);
  expect(topbar.h).toBe(56);                    // --topbar-h

  const logo = await box(page, '.kiosk-topbar__logo');
  const zh = await box(page, '.kiosk-topbar__brand-zh');
  const en = await box(page, '.kiosk-topbar__brand-en');
  const rule = await box(page, '.kiosk-topbar__rule');
  const game = await box(page, '.kiosk-topbar__game');
  const avatar = await box(page, '.kiosk-topbar__avatar');
  const clock = await box(page, '.kiosk-topbar__clock');

  expect(logo.x - screen.x).toBe(24);           // --topbar-pad-x
  expect(logo.w).toBe(32);                      // --topbar-logo
  expect(logo.h).toBe(32);
  expect(Math.round(zh.x - logo.right)).toBe(10);   // --topbar-gap-logo-brand
  expect(Math.round(en.x - zh.right)).toBe(6);      // --topbar-gap-zh-en
  expect(rule.w).toBe(1);
  expect(rule.h).toBe(20);                      // --topbar-rule-h
  expect(avatar.w).toBe(26);                    // --topbar-avatar
  expect(avatar.h).toBe(26);

  // 左簇顺序不可调 —— 间距对了但顺序反了,上面每一条仍会过。
  expect(logo.x).toBeLessThan(zh.x);
  expect(zh.x).toBeLessThan(en.x);
  expect(en.x).toBeLessThan(rule.x);
  expect(rule.x).toBeLessThan(game.x);

  // 右簇贴右缘,和左簇同一个内边距
  expect(Math.round(screen.right - clock.right)).toBe(24);
});

test('§6 主页键只在 L1 出现 —— 二级页要退的是这一屏,不是回智星盒主页', async ({ page }) => {
  await boot(page, '/kiosk/play');
  await expect(page.locator('[data-testid="kiosk-home-action"]')).toHaveCount(1);

  // 同上:settings 自 Task 4 起是 L1,不能再拿它当二级页的例子。
  await boot(page, '/kiosk/play/ai/setup/free');
  await expect(page.locator('[data-testid="kiosk-home-action"]')).toHaveCount(0);

  // 但**身份位不许跟着消失**(防跳铁律 2:右簇位置恒定)。
  const screen = await box(page, '.kiosk-screen');
  const clock = await box(page, '.kiosk-topbar__clock');
  expect(Math.round(screen.right - clock.right)).toBe(24);
});

test('§2 品牌字「智星盒」跑的是龙藏行楷,而且三个字都是', async ({ page }) => {
  await boot(page, '/kiosk/play');
  // 字体真没真跑起来只有浏览器自己知道:CSS 里写了字族 ≠ 那个面被选中。
  // 上一版就是「字体文件在、@font-face 在、import 也在,只有消费点没接」——
  // 屏上跑的是霞鹜文楷,而任何读 CSS 的断言都会说它是对的。
  const client = await page.context().newCDPSession(page);
  await client.send('DOM.enable');
  await client.send('CSS.enable');
  const { root } = await client.send('DOM.getDocument');
  const { nodeId } = await client.send('DOM.querySelector', {
    nodeId: root.nodeId, selector: '[data-testid="kiosk-brand-zh"]',
  });
  const { fonts } = await client.send('CSS.getPlatformFontsForNode', { nodeId });

  // §17.1:任何「不许超过 N」的断言都要问一句「0 是不是最优解」。是的话它就没有下界,
  // 而下界通常才是真正要的那件事。这里的下界钉在「首位是龙藏 **且** 覆盖 3 个字」——
  // 只钉首位的话,掉出去两个字它还是首位。
  //
  // 变异记录(2026-08-20,Task 3 Step 9),**两支各演示一次**:
  //   ① 把 className 从 `kiosk-topbar__brand-zh` 改成 `kiosk-topbar__brand`
  //      ⇒ 红,Received "LXGW WenKai"(正是上一版屏上真跑的那个面)。
  //   ② 把文案从「智星盒」改成「智星」⇒ 红,Expected 3 / Received 2。
  //      —— 这一支专门证明下界那半条不是摆设。
  expect(fonts[0].familyName).toContain('Long Cang');
  expect(fonts[0].glyphCount).toBe(3);
});

/* ─────────────────────────── Task 4:Dock 与层级 ───────────────────────────
 *
 * 变异记录(2026-08-20,Task 4 Step 8),**四支各演示一次**:
 *   ① 拆掉 `KioskDock` 的 `aria-current` ⇒「选中态位移」红(上移的项 1 → 0)
 *      **且**「图标翻色」红(两种 fill → 一种)。
 *   ② 把 `<Icon name=… />` 换成空 `<span className="kiosk-icon" />`
 *      ⇒「?raw 内联成立」红(svg 6 → 0)。这一支就是「构建绿但图标其实没进包」长的样子。
 *   ③ `dockLevelOf` 恒返回 1 ⇒「L2 没有 Dock」红(.kiosk-dock 0 → 1)。
 *   ④ 词典删掉「设置」一项 ⇒「六项」红(6 → 5)。
 * 实测值一并记在这里(只作记录、不作判据):项高 65,未选中项 y=527、选中项 y=525。
 */

test('§7 Dock:六项、通栏贴底、等宽、项高 65、选中态位移 −2px', async ({ page }) => {
  await boot(page, '/kiosk/play');

  const screen = await box(page, '.kiosk-screen');
  const dock = await box(page, '.kiosk-dock');
  // 通栏贴底:左右各到画布边、下缘就是画布下缘。Dock 是**盖在**中间区下面那 82px 上的,
  // 不是被中间区的 16px 外边距框住的 —— 这一条和 `--content-x` 是两回事。
  expect(dock.x).toBe(screen.x);
  expect(dock.right).toBe(screen.right);
  expect(dock.bottom).toBe(screen.bottom);

  const items = await page.evaluate(() =>
    [...document.querySelectorAll('.kiosk-dock__item')].map((el) => {
      const r = el.getBoundingClientRect();
      return { x: r.x, y: r.y, w: r.width, h: r.height };
    }));
  expect(items).toHaveLength(6);   // D8:六项。五子棋自己也是 6 项,「四家项数相等」不是规矩

  // 等宽:最宽和最窄差不到 1px(亚像素)。grid-auto-columns: 1fr 说的就是这件事,
  // 但说了不等于算出来是 —— 中间任何一个元素给自己一个 min-width 都会破它。
  expect(Math.max(...items.map((b) => b.w)) - Math.min(...items.map((b) => b.w))).toBeLessThan(1);

  // 项高 = Dock 高 − 1(顶部描边)− 2×8(上下内边距)。写成关系式,不写字面量 65。
  expect(Math.round(items[0].h)).toBe(dock.h - 1 - 2 * 8);

  // 选中项上移 2 —— 而且**只有一个**上移。两个一起动就说明高亮认了不止一项。
  const base = Math.max(...items.map((b) => b.y));
  const raised = items.filter((b) => b.y < base - 1);
  expect(raised).toHaveLength(1);
  expect(Math.round(base - raised[0].y)).toBe(2);
});

test('§10 Dock 图标真的画出来了 —— ?raw 内联在生产链路上成立', async ({ page }) => {
  await boot(page, '/kiosk/play');
  // 这一条是给 `import.meta.glob(..., "?raw")` 兜底的:单测在 vitest 里跑,
  // 构建绿也只说明没报错。要证「82 个 svg 真的进了包、真的渲染成了有面积的图形」,
  // 只有真浏览器量得出来。
  const icons = await page.evaluate(() =>
    [...document.querySelectorAll('.kiosk-dock__item svg')].map((el) => {
      const r = el.getBoundingClientRect();
      return { w: Math.round(r.width), h: Math.round(r.height), paths: el.querySelectorAll('path').length };
    }));
  expect(icons).toHaveLength(6);
  for (const i of icons) {
    expect(i.w).toBe(24);            // --dock-icon
    expect(i.h).toBe(24);
    expect(i.paths).toBeGreaterThan(0);   // 有 <path> 才是真图标,不是个空 svg 壳
  }

  // 选中那一项的图标跟着容器翻成 --ink(深色),没选中的是 --dim。
  // `<img src>` 版本跟不了 currentColor,这一条正是那条规矩的实测面。
  const fills = await page.evaluate(() =>
    [...document.querySelectorAll('.kiosk-dock__item')].map((el) =>
      getComputedStyle(el.querySelector('svg')!).fill));
  expect(new Set(fills).size).toBe(2);      // 选中 1 个 + 没选中 5 个 = 两种颜色
});

test('层级:L2 没有 Dock,中间区因此长到画布底;对局屏是 L2 但顶栏在', async ({ page }) => {
  await boot(page, '/kiosk/tsumego/problem/1');

  const screen = await box(page, '.kiosk-screen');
  const content = await box(page, '.kiosk-content');
  expect(await page.evaluate(() => document.querySelectorAll('.kiosk-dock').length)).toBe(0);
  // L2 把 Dock 那 82px 整个还给中间区:下缘就是画布下缘,没有底部留白。
  expect(content.bottom).toBe(screen.bottom);
  // 关系式:L2 的中间区正好比 L1 高出一个 Dock。这一条才是「因为没 Dock」本身。
  expect(content.h).toBe(screen.h - 56);

  // 对局屏 Task 4 挪进了 KioskLayout。挪之前它在 KioskLayout **外面** ——
  // 连顶栏都没有,撞规范 §5 防跳铁律 1「顶栏任何层级都不隐藏」。
  await boot(page, '/kiosk/play/ai/game/nonexistent');
  const topbar = await box(page, '.kiosk-topbar');
  expect(topbar.h).toBe(56);
  expect(topbar.y).toBe(screen.y);
  expect(await page.evaluate(() => document.querySelectorAll('.kiosk-dock').length)).toBe(0);
});
