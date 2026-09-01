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
  // ⚠️ **这条不是装饰,是这份闸能不能自己站住的前提。**
  // `tsumego/problem/:id` / `baipu/session/:id` 等路由外面套着 `PhysicalBoardGuard`,
  // 它读 `GeometryContext`;而 `GeometryProvider` 只在**接口 404** 时才落到 `disabled`,
  // 接口连不上(vite 代理到 :8001,后端没起 ⇒ 502)时 phase 停在 `required` ⇒ 整屏被换成标定台。
  // 2026-08-23 实测:后端起着的时候这两条做题屏的闸是绿的,后端一停就 30 秒超时 ——
  // **闸绿不绿取决于另一个进程在不在**,那不叫闸。这里把它钉成「这台盒子没有摄像头」。
  await page.route('**/api/v1/geometry/status', (route) => route.fulfill({
    json: {
      phase: 'disabled', session_calibrated: false, last_error: null,
      capabilities: { camera_ready: false, led_ready: false, geometry_ready: false, recognition_ready: false },
    },
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
const box = async (page: Page, sel: string) => {
  // `boot()` 只等到 `.kiosk-screen`(外壳),而这些数量的都是**路由里面**的元素 ——
  // 并发跑满时路由组件可能还没挂上,于是偶发一条「没有这个元素: .kiosk-pagebar」。
  // 2026-08-22 实测撞到过一次(41 条里红 1 条,单独重跑就绿)。
  // 仍然用 `state: 'attached'` 而不是默认的 `'visible'`:画布塌成 0×0 时元素照旧在 DOM 里,
  // 默认值会把「量出来是 0」糊成一条 30 秒超时 —— 那正是这个文件要防的头号故障。
  await page.waitForSelector(sel, { state: 'attached', timeout: 5000 });
  return page.evaluate((s) => {
  const el = document.querySelector(s);
  if (!el) throw new Error(`没有这个元素: ${s}`);
  const r = el.getBoundingClientRect();
  return {
    x: Math.round(r.x), y: Math.round(r.y),
    w: Math.round(r.width), h: Math.round(r.height),
    right: Math.round(r.right), bottom: Math.round(r.bottom),
  };
  }, sel);
};

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

/**
 * §5 防跳铁律 1:「顶栏永远占 y 0–56,**任何层级、任何模块**都不变高、不隐藏」。
 *
 * 上面那条只在 `/kiosk/play` 一屏上量 —— 而漏掉的恰恰是**别的屏**:屏 14 做题
 * 靠一个 `setImmersive(true)` 把顶栏整块不渲染,四图存档里那一屏顶上是一条空黑带,
 * 而顶栏那条逐像素闸**从头到尾是绿的**,因为它量的不是那一屏。
 * (那个开关连一个像素都没换来:`.kiosk-content` 的 `top` 是无条件的
 * `var(--topbar-h)`,抽掉顶栏不会把 56px 还给内容。2026-08-26 已整个删除。)
 *
 * ⇒ 这一条把判据从「顶栏长什么样」换成「**每一屏上它都在,而且没被盖住**」。
 * 「没被盖住」是 jsdom 说不出来的那一半:`KioskLayout.test.tsx` 能证明它**渲染了**,
 * 证明不了某一屏用一块 `position:fixed` 的遮罩把它压在下面。
 */
const TOPBAR_ROUTES: readonly [string, string][] = [
  ['/kiosk/play',                     'L1 · 屏 01 对弈(带镜像栏)'],
  ['/kiosk/report',                   'L1 · 屏 19 复盘(自带 L1 布局)'],
  ['/kiosk/settings',                 'L1 · 屏 27 设置(自带 L1 布局)'],
  ['/kiosk/play/ai/setup/free',       'L2 · 屏 02 开局设置'],
  ['/kiosk/tsumego/15k/capturing/1',  'L2 · 屏 14 做题 —— 就是漏掉顶栏的那一屏'],
  ['/kiosk/report/41',                'L2 · 屏 20 报告'],
  ['/kiosk/baipu/session/s1',         'L2 · 屏 17 摆谱'],
  ['/kiosk/live/m1',                  'L2 · 屏 18 直播'],
];

for (const [route, label] of TOPBAR_ROUTES) {
  test(`§5 顶栏在每一屏上都在、都是 56、都没被盖住 —— ${label}`, async ({ page }) => {
    await boot(page, route);

    const screen = await box(page, '.kiosk-screen');
    const topbar = await box(page, '.kiosk-topbar');
    expect(topbar.y).toBe(screen.y);
    expect(topbar.h).toBe(56);
    expect(topbar.w).toBe(screen.w);

    // 盖没盖住:在顶栏正中取一点,问浏览器那一点上**最上面**的元素是谁。
    // 元素在 DOM 里、盒子也量得出来,却被一层遮罩压着 —— 上面三条一条都不会红。
    const hitsTopbar = await page.evaluate(() => {
      const bar = document.querySelector('.kiosk-topbar') as HTMLElement | null;
      if (!bar) return false;
      const r = bar.getBoundingClientRect();
      const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
      return Boolean(top && bar.contains(top));
    });
    expect(hitsTopbar, '顶栏被别的东西盖住了').toBe(true);
  });
}

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
 *      ⇒「?raw 内联成立」红(svg 7 → 0)。这一支就是「构建绿但图标其实没进包」长的样子。
 *   ③ `dockLevelOf` 恒返回 1 ⇒「L2 没有 Dock」红(.kiosk-dock 0 → 1)。
 *   ④ 词典删掉「设置」一项 ⇒「七项」红(7 → 6)。
 * 实测值一并记在这里(只作记录、不作判据):项高 65,未选中项 y=527、选中项 y=525。
 *
 * ⚠️ **2026-08-25:六项 → 七项**(补了「成长」,屏 22)。这一条**当场红了**,
 * 是它自己把 6 → 7 逮住的 —— 也就是这个闸在守的东西没变,只是词典变了。
 * 等宽那条同批复核:960 / 7 = **137.14**,最宽最窄差 < 1px,`grid-auto-columns: 1fr` 照旧成立。
 */

test('§7 Dock:七项、通栏贴底、等宽、项高 65、选中态位移 −2px', async ({ page }) => {
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
  // D8。**「四家项数相等」不是规矩** —— 五子棋自己是 6 项,围棋 2026-08-25 起是 7 项
  // (补了「成长」)。数字跟着本仓的 `DOCK_TABS` 走,共享上限是 `--dock-max-items` = 7。
  expect(items).toHaveLength(7);

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
  // 七项 ⇒ 七个图标(2026-08-25 补了「成长」,用 `trend-up`)。
  expect(icons).toHaveLength(7);
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

/* ───────────────────── Task 5:L1 两栏与镜像栏（承重） ─────────────────────
 *
 * 变异记录(2026-08-20,Task 5),**三支各演示一次**:
 *   ① 去掉 `status.css` 的 `.kiosk-status__cell { min-width: 0 }`
 *      ⇒「承重」红:`scrollWidth 4200` 不再 > `clientWidth`(格子被内容撑成 4200,
 *      不是内容被格子裁到 62)。这正是「grid 子项 min-width:auto 拒绝收缩」那条。
 *   ② 给 `.kiosk-console__frame` 加回 `flex: 1; height: auto`
 *      ⇒「严丝合缝」红:同步行压到 0 之后框吃掉了腾出来的 32,272 → 304。
 *      ⚠️ **第一次这支变异是绿的。** 今天 410 − (20+32+56) − 3×10 = 272,和框写死的 272
 *      **恰好同值** —— `flex:1` 和 `flex:none` 在这份数据下画出来一模一样,断言落在了
 *      两个语义正好同值的那一侧。补上「动一动兄弟的高再看框跟不跟着变」才分得开。
 *   ③ 往左栏里塞一个 `overflow-y:auto` 且内容溢出的块 ⇒「永不滚动」红。
 */

test('§5 L1 两栏:296 + 16 + 680,左栏纵向 20+10+272+10+32+10+56=410 严丝合缝', async ({ page }) => {
  await boot(page, '/kiosk/play');

  const content = await box(page, '.kiosk-content');
  const rail = await box(page, '.kiosk-console');
  const side = await box(page, '.kiosk-layout-l1 > *:nth-child(2)');

  // 横向:此前是 322 + 2×20 外边距 = 362 占位、右边只剩 662。
  expect(rail.w).toBe(296);
  expect(side.w).toBe(680);
  expect(side.x - (rail.x + rail.w)).toBe(16);
  expect(rail.x).toBe(content.x);
  expect(side.right).toBe(content.right);

  const title  = await box(page, '.kiosk-console__title');
  const frame  = await box(page, '.kiosk-console__frame');
  const mini   = await box(page, '.kiosk-mini-board');
  const sync   = await box(page, '.kiosk-console__sync');
  const status = await box(page, '.kiosk-status');

  // 每一块都不许被 flex 压扁(全部 flex:none),四段间距都是 10。
  // 这串曾经算错过 2px —— 横向算了 1px 描边、纵向漏了,而标题行和状态格当时没写 flex:none,
  // 被各压 1px,**肉眼看不出来**。
  expect(title.h).toBe(20);
  expect(sync.h).toBe(32);
  expect(status.h).toBe(56);
  expect(frame.y - (title.y + title.h)).toBe(10);
  expect(sync.y - (frame.y + frame.h)).toBe(10);
  expect(status.y - (sync.y + sync.h)).toBe(10);
  // 纵向恰好用完,不多不少:最后一块的下缘 = 栏的内容盒下缘(434 − 1 描边 − 11 内边距)
  expect(status.bottom).toBe(rail.bottom - 1 - 11);
  // 左栏本身恒为中间区的**内容盒**高 —— 它不长也不缩。
  // ⚠️ `getBoundingClientRect` 给的是**边框盒**:`.kiosk-content` 有 `padding: 14px 0`
  // (tokens.css:421),所以它量出来是 462 而不是 434。第一次写成 `rail.h === content.h`
  // 就红在这儿 —— 434 是对的,462 也是对的,错的是把两个盒混为一谈。
  const contentPad = await page.evaluate(() => {
    const cs = getComputedStyle(document.querySelector('.kiosk-content')!);
    return { top: parseFloat(cs.paddingTop), bottom: parseFloat(cs.paddingBottom) };
  });
  expect(rail.h).toBe(content.h - contentPad.top - contentPad.bottom);
  expect(rail.y).toBe(content.y + contentPad.top);

  // 镜像框是**正方形**,不许吃剩余空间(早先写 flex:1 → 272×312,上下各空 32、左右只有 12)
  expect(frame.w).toBe(frame.h);
  expect(mini.w).toBe(mini.h);
  expect(mini.w).toBe(frame.w - 2 * 12);   // 248 = 272 − 2×12

  // ⚠️ 上面三条**证不了**「不吃剩余空间」这句话:今天 410 − (20+32+56) − 3×10 = 272,
  // 和框自己写死的 272 **恰好同值** —— `flex:1` 与 `flex:none` 在这份数据下画出来一模一样
  // (实测:把 `flex:1; height:auto` 加回去,上面三条全绿)。断言落在了两个语义正好同值的那一侧。
  // 要分开它们,得**动一动兄弟的高**再看框跟不跟着变:同步行压到 0,框必须还是 272。
  const frameWhenSlack = await page.evaluate(() => {
    const rail = document.querySelector('.kiosk-console') as HTMLElement;
    rail.style.setProperty('--l1-sync-h', '0px');
    const h = (document.querySelector('.kiosk-console__frame') as HTMLElement).getBoundingClientRect().height;
    rail.style.removeProperty('--l1-sync-h');
    return Math.round(h);
  });
  expect(frameWhenSlack, '框把腾出来的空间吃掉了 —— 它是 flex:1,不是 flex:none').toBe(frame.h);
});

test('§5 左栏永不滚动 —— 滚动只属于右栏', async ({ page }) => {
  await boot(page, '/kiosk/play');
  const scrollable = await page.evaluate(() => {
    const walk = (n: Element): boolean => {
      const cs = getComputedStyle(n);
      if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') && n.scrollHeight > n.clientHeight) return true;
      return Array.from(n.children).some(walk);
    };
    return walk(document.querySelector('.kiosk-console')!);
  });
  expect(scrollable, '左栏里有东西在滚 —— 它必须恒为 434 固定高').toBe(false);
});

test('§5 承重:把三格的值撑到会溢出,外框 296×434 一动不动', async ({ page }) => {
  await boot(page, '/kiosk/play');

  // 铁律:**装得下的数据量下量出来的数字一概不算。** 上面两条量的都是「刚好装得下」,
  // 证不了「装不下的时候谁让步」。这里把值撑成 300 个字再量一次。
  const before = await box(page, '.kiosk-console');
  await page.evaluate(() => {
    document.querySelectorAll('.kiosk-status__v').forEach((el) => { el.textContent = '已连接'.repeat(100); });
    document.querySelectorAll('.kiosk-console__sync span').forEach((el) => { el.textContent = '盘面与屏幕一致'.repeat(50); });
  });

  const after = await box(page, '.kiosk-console');
  const status = await box(page, '.kiosk-status');
  const sync = await box(page, '.kiosk-console__sync');
  const content = await box(page, '.kiosk-content');
  const side = await box(page, '.kiosk-layout-l1 > *:nth-child(2)');

  // 外框、状态格、同步行、右栏 —— 一个都不许被撑
  expect({ w: after.w, h: after.h }).toEqual({ w: before.w, h: before.h });
  expect(status.h).toBe(56);
  expect(sync.h).toBe(32);
  expect(side.w).toBe(680);
  expect(status.bottom).toBe(after.bottom - 1 - 11);
  // 撑长之后**整块中间区**也不许变 —— 溢出没有往上传导。
  // 比的是中间区的**内容盒**(减掉自己的 14px 上下内边距)对上左栏的边框盒。
  const contentPad = await page.evaluate(() => {
    const cs = getComputedStyle(document.querySelector('.kiosk-content')!);
    return { top: parseFloat(cs.paddingTop), bottom: parseFloat(cs.paddingBottom) };
  });
  expect(content.h - contentPad.top - contentPad.bottom).toBe(before.h);

  // 撑不开就必须**看得出被截断了**:格子的内容宽 > 可视宽 = 出了省略号。
  // grid 子项默认 `min-width: auto` 会拒绝收缩到内容宽度以下 —— 实测把值撑到 3900px 宽、
  // 视口才 1024、**一个省略号都没有**。所以这一条要正面量,不能只量外框没变。
  const truncated = await page.evaluate(() =>
    [...document.querySelectorAll('.kiosk-status__v')].map((el) => ({
      scroll: el.scrollWidth, client: el.clientWidth, ellipsis: getComputedStyle(el).textOverflow,
    })));
  for (const t of truncated) {
    expect(t.scroll).toBeGreaterThan(t.client);
    expect(t.ellipsis).toBe('ellipsis');
  }
});

// ── Task 8 —— §11 页控条 ────────────────────────────────────────────────
// 顶栏在所有层级恒为品牌态,返回 / 视图切换 / 上下文标题全部下放到这条控件带。
// 位置写死是**判据本身**:两种布局下纵向位置完全相同,有盘页和无盘页来回切时不上下跳。

test('§11 布局 B:页控条通栏 x16–1008、y70–114、高 44,返回键高 36', async ({ page }) => {
  await boot(page, '/kiosk/play/cross-platform');
  const screen = await box(page, '.kiosk-screen');
  const bar = await box(page, '.kiosk-pagebar');
  const back = await box(page, '.kiosk-pagebar__back');
  expect(bar.x - screen.x).toBe(16);          // --content-x
  expect(bar.w).toBe(992);                    // 1024 − 2×16
  expect(bar.y - screen.y).toBe(70);          // --topbar-h 56 + --content-pad-y 14
  expect(bar.h).toBe(44);                     // --pagebar-h
  expect(back.h).toBe(36);                    // --pagebar-back-h
  // 返回键贴左缘 —— 触点位置在每一屏都一样,这是肌肉记忆
  expect(back.x).toBe(bar.x);
});

test('§11 有盘页与无盘页来回切,页控条的纵向位置一模一样', async ({ page }) => {
  await boot(page, '/kiosk/play/cross-platform');           // 布局 B
  const b = await box(page, '.kiosk-pagebar');
  await boot(page, '/kiosk/play/ai/setup/free');            // 布局 A
  const a = await box(page, '.kiosk-pagebar');
  expect(a.y).toBe(b.y);                      // 这条就是「切模块不跳」本身
  expect(a.h).toBe(b.h);
  expect(a.x).toBe(548);                      // 布局 A 在右栏顶:16 + 516(盘) + 16
  expect(a.w).toBe(460);
});

test('§11 长标题不许把返回键挤成两行 —— 触点位置在每一屏都一样', async ({ page }) => {
  await boot(page, '/kiosk/play/cross-platform');
  const shortBack = await box(page, '.kiosk-pagebar__back');
  const shortBar = await box(page, '.kiosk-pagebar');
  // 把数据造到会溢出 —— 装得下的长度下量出来的数一概不算
  await page.evaluate(() => {
    document.querySelector('.kiosk-pagebar__title')!.textContent = '很长的标题'.repeat(40);
  });
  const longBack = await box(page, '.kiosk-pagebar__back');
  const longBar = await box(page, '.kiosk-pagebar');
  expect(longBack.h, '返回键被长标题挤高了').toBe(shortBack.h);
  expect(longBack.x, '返回键被长标题推走了').toBe(shortBack.x);
  // **宽度才是这条闸的承重点**:这条带子不换行(没有 flex-wrap),所以「挤成两行」在这儿
  // 根本发生不了 —— 真实的失效是返回键被**压窄**(实测 82 → 68,字和图标跟着挤)。
  // 只断言高和 x 的话,`flex: none` 拿掉照样全绿。
  expect(longBack.w, '返回键被长标题压窄了').toBe(shortBack.w);
  expect(longBar.h, '整条控件带被长标题撑高了').toBe(shortBar.h);
  expect(longBar.w, '整条控件带被长标题撑宽了').toBe(shortBar.w);
  // **判据要跟着轴走**:横向截断验 scrollWidth > clientWidth。
  // 换成纵向那两个数会同时是 20,红在一个不存在的缺陷上(上一轮实测过)。
  const title = await page.evaluate(() => {
    const el = document.querySelector('.kiosk-pagebar__title') as HTMLElement;
    const cs = getComputedStyle(el);
    return { scroll: el.scrollWidth, client: el.clientWidth, ellipsis: cs.textOverflow, overflow: cs.overflowX };
  });
  expect(title.scroll, '长标题没有被截断,它把整条撑开了').toBeGreaterThan(title.client);
  // 下面两条断言的是 CSS 计算值,不是布局结论 —— **这是有意的**:
  // 「装不下」是布局(上一条已经量了),而「装不下之后是裁掉加省略号、还是溢出去糊在
  // 旁边」是**绘制**,布局盒子在两种情况下逐像素相同(实测:两种状态下 title 都是 912 宽、
  // scrollWidth 都是 3000)。真浏览器量不出绘制差异,就如实用计算值断言,不假装量到了。
  expect(title.overflow, '溢出没有被裁掉 —— 长标题会糊到控件带外面').toBe('hidden');
  expect(title.ellipsis).toBe('ellipsis');
});

/* ── Task 13 —— §11 布局 B 的**纵向账** ──────────────────────────────────────
 * 上面那条布局 B 量的是页控条自己(x/y/高);这条量的是它下面那块内容区,
 * 也就是**这条账有没有第二个来源**:
 *     70(内容区上缘) + 44(页控条) + 12(gap) + 460(滚动区) = 586(内容区下缘)
 * `.kiosk-layout-b` 里**没写死任何高度** —— 滚动区吃剩余空间。要是哪天有人给它补一个
 * `height: 460`,这条账就有了两个来源,而两个来源必然有一天不一致(那天会是改 `--pagebar-h`)。
 * 判据因此写成**关系式**:滚动区上缘 = 页控条下缘 + 12,下缘 = 内容区下缘。
 *
 * ⚠️ 屏 12 是本仓第一个真的走 `.kiosk-layout-b` 的屏(跨平台那几屏还是手搓的 Box),
 * 所以这条闸落在它身上。
 */
test('§11 布局 B 的纵向账:页控条 44 + 12 + 滚动区 460 = 516,且滚动区通栏 992', async ({ page }) => {
  await page.route('**/api/v1/tsumego/levels/*/categories/*', (route) => route.fulfill({
    json: Array.from({ length: 45 }, (_, i) => ({ id: `q${i}` })),
  }));
  await boot(page, '/kiosk/tsumego/15k/capturing');
  // ⚠️ 量的是 `.kiosk-content` 的**内边**(padding box),不是 border box:
  // 它的 border box 一路到画布下缘 600,上下各 14 的内边距才是内容真正能用的 70..586。
  // 第一版拿 border box 比,红在 `600 ≠ 586` —— **闸量错了对象**,不是页面错。
  const content = await page.evaluate(() => {
    const el = document.querySelector('.kiosk-content') as HTMLElement;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      innerTop: Math.round(r.top + parseFloat(cs.paddingTop)),
      innerBottom: Math.round(r.bottom - parseFloat(cs.paddingBottom)),
    };
  });
  const bar = await box(page, '.kiosk-pagebar');
  const zone = await box(page, '.kiosk-side.kiosk-scrollzone');
  const screen = await box(page, '.kiosk-screen');

  expect(bar.x - screen.x, '页控条没贴中间区左缘').toBe(16);
  expect(bar.w, '页控条不是通栏').toBe(992);
  expect(zone.x, '滚动区没和页控条左对齐').toBe(bar.x);
  expect(zone.w, '滚动区不是通栏 —— 无盘页的内容区就是整条 992').toBe(992);
  expect(zone.y - bar.bottom, '页控条与内容区之间不是 12').toBe(12);
  expect(bar.y, '页控条没贴内容区上缘').toBe(content.innerTop);
  expect(zone.bottom, '滚动区没停在内容区下缘 —— 要么溢出到画布外,要么白空一条').toBe(content.innerBottom);
  expect(content.innerBottom - content.innerTop, '无盘页的内容区总高不是 516').toBe(516);
  expect(zone.h, '460 = 516 − 44 − 12,这个数是算出来的不是写死的').toBe(460);
});

/* ══ 屏 14 做题屏 —— 刻度带的节距必须**等于盘的线节距** ═══════════════════════
 * `go-screens.css` 把这条写成了不变式,而且写明了**判据是屏上那条线的横坐标**,
 * 不是「字心应该落在 (i+0.5)/N」那个版式规则 —— 象棋第一版探针拿后者当判据,
 * 量出「最大错开 26px」,数字漂亮、结论全假。
 *
 * 这一屏是它第一次**真的失效**:`TsumegoBoard` 原来按 1.5 格边距画(那是给盘面里
 * 自己那圈坐标留的位置),而 kiosk 布局 A 的坐标交给外壳画 ⇒ 线的节距 W/(N−1+3)、
 * 刻度带 W/N,**两者不等**。四图对比一眼看出来「字和线错开」,而当时没有任何一条闸会红。
 *
 * 线画在 canvas 上,DOM 里问不出来 ⇒ **直接读像素**:横切一条,找最暗的那些列 = 竖线。
 */
test('§8 做题屏:盘上第一条和最后一条竖线,正对刻度带头尾两个字', async ({ page }) => {
  await page.route('**/api/v1/tsumego/problems/*', (route) => route.fulfill({
    json: {
      id: 'g1', level: '15k', category: 'capturing', hint: '黑先', boardSize: 19,
      initialBlack: [], initialWhite: [], sgfContent: '',
    },
  }));
  await page.route('**/api/v1/tsumego/levels/*/categories/*', (route) => route.fulfill({
    json: Array.from({ length: 20 }, (_, i) => ({ id: `g${i + 1}` })),
  }));
  await boot(page, '/kiosk/tsumego/problem/g1');
  await page.waitForSelector('.kiosk-board canvas');
  // canvas 是图片加载完之后才画的 —— 早一步读到的是一张空白。
  await page.waitForFunction(() => {
    const c = document.querySelector('.kiosk-board canvas') as HTMLCanvasElement | null;
    if (!c) return false;
    const d = c.getContext('2d')!.getImageData(0, Math.floor(c.height / 2), c.width, 1).data;
    for (let i = 0; i < d.length; i += 4) if (d[i] > 40) return true;   // 有木色了
    return false;
  });

  const m = await page.evaluate(() => {
    const canvas = document.querySelector('.kiosk-board canvas') as HTMLCanvasElement;
    const cr = canvas.getBoundingClientRect();
    const ctx = canvas.getContext('2d')!;
    // 横切一条(避开星位那几行),按列取平均亮度;竖线 = 明显比木色暗的那些列。
    const y = Math.floor(canvas.height * 0.28);
    const row = ctx.getImageData(0, y, canvas.width, 1).data;
    const lum: number[] = [];
    for (let x = 0; x < canvas.width; x += 1) lum.push((row[x * 4] + row[x * 4 + 1] + row[x * 4 + 2]) / 3);
    const wood = [...lum].sort((a, b) => a - b)[Math.floor(lum.length * 0.75)];
    // 木底没铺满整个 canvas(盘宽按格数取整,两侧各余 2px 暗边)——
    // 那两条暗边不是棋盘线,先按「木色区间」把它们排除掉,不然会多数出两条。
    let woodL = 0;
    while (woodL < lum.length && lum[woodL] < wood * 0.5) woodL += 1;
    let woodR = lum.length - 1;
    while (woodR > woodL && lum[woodR] < wood * 0.5) woodR -= 1;
    const dark: number[] = [];
    for (let x = woodL + 1; x < woodR; x += 1) if (lum[x] < wood * 0.72) dark.push(x);
    // 把相邻的暗列并成一条线,取中点。
    const lines: number[] = [];
    let run: number[] = [];
    for (const x of dark) {
      if (run.length === 0 || x - run[run.length - 1] <= 1) run.push(x);
      else { lines.push(run.reduce((a, b) => a + b, 0) / run.length); run = [x]; }
    }
    if (run.length) lines.push(run.reduce((a, b) => a + b, 0) / run.length);
    // canvas 的内部像素 → 屏幕坐标(canvas 被 CSS 缩放过)。
    const toScreen = (px: number) => cr.left + (px / canvas.width) * cr.width;
    const labels = Array.from(document.querySelectorAll('.kiosk-board__ruler--top span'))
      .map((s) => { const r = s.getBoundingClientRect(); return r.left + r.width / 2; });
    return {
      lines: lines.length,
      labels: labels.length,
      firstLine: toScreen(lines[0]),
      lastLine: toScreen(lines[lines.length - 1]),
      firstLabel: labels[0],
      lastLabel: labels[labels.length - 1],
    };
  });

  expect(m.labels, '刻度带不是 19 个字 —— 下面比的就不是头尾两条线').toBe(19);
  expect(m.lines, '从像素里没读出 19 条竖线 —— 阈值挑坏了,后面的数都不算').toBe(19);
  // 判据是**关系式**:头对头、尾对尾。1.5px 的余量给的是抗锯齿和取整,不是给错位留的。
  expect(Math.abs(m.firstLine - m.firstLabel),
    `第一条线 ${m.firstLine.toFixed(1)} 和第一个字 ${m.firstLabel.toFixed(1)} 对不上`).toBeLessThanOrEqual(1.5);
  expect(Math.abs(m.lastLine - m.lastLabel),
    `最后一条线 ${m.lastLine.toFixed(1)} 和最后一个字 ${m.lastLabel.toFixed(1)} 对不上`).toBeLessThanOrEqual(1.5);
});

/* ══ 屏 14 —— 右栏五块必须装进 516,而且动作区**贴底** ══════════════════════
 * 这一屏的右栏比对局屏还挤:页控条 44 + 这一题 + 你的走法(flex:1)+ 一排开关 40
 * + 第 N 单元 + 动作区 52。实体模式的引导块是**换掉**「你的走法」的内容而不是加一块 ——
 * 加一块就会把动作区顶出右栏,而它贴底靠的是 `margin-top:auto`,顶出去就在画布外面、点不到。
 * 所以造数据时要把两种模式下最挤的那一版都造出来。
 */
test('§11 做题屏:着法再多,动作区也贴着右栏底,一个键都不许被挤出画布', async ({ page }) => {
  await page.route('**/api/v1/tsumego/problems/*', (route) => route.fulfill({
    json: {
      id: 'g1', level: '15k', category: 'capturing', hint: '黑先', boardSize: 19,
      initialBlack: [], initialWhite: [], sgfContent: '',
    },
  }));
  await page.route('**/api/v1/tsumego/levels/*/categories/*', (route) => route.fulfill({
    json: Array.from({ length: 20 }, (_, i) => ({ id: `g${i + 1}` })),
  }));
  await boot(page, '/kiosk/tsumego/problem/g1');
  await page.waitForSelector('[data-testid="puzzle-actions"] button');

  // 造到会溢出:往着法表里塞 40 行(一道死活题不可能这么多,正因为如此才是**上界**)。
  await page.addStyleTag({
    content: '.mvrows::after { content:""; display:block; height:600px; grid-column:1/-1; }',
  });

  const m = await page.evaluate(() => {
    const rail = document.querySelector('.kiosk-rail') as HTMLElement;
    const acts = document.querySelector('[data-testid="puzzle-actions"]') as HTMLElement;
    const body = document.querySelector('.railsec__body') as HTMLElement;
    const screen = document.querySelector('.kiosk-screen') as HTMLElement;
    const r = rail.getBoundingClientRect();
    const a = acts.getBoundingClientRect();
    return {
      railH: Math.round(r.height),
      railBottom: Math.round(r.bottom),
      actsBottom: Math.round(a.bottom),
      actsCount: acts.querySelectorAll('button').length,
      overflowInBody: body.scrollHeight - body.clientHeight,
      railOverflow: rail.scrollHeight - rail.clientHeight,
      screenBottom: Math.round(screen.getBoundingClientRect().bottom),
    };
  });

  expect(m.railH, '右栏不是 516 —— 布局 A 的高度账先崩了').toBe(516);
  expect(m.actsCount, '动作区不是五个键').toBe(5);
  expect(m.overflowInBody, '没造出「着法装不下」—— 下面那条断言是空的').toBeGreaterThan(100);
  expect(m.railOverflow, '右栏自己被顶破了 —— 溢出该由着法那一块自己吃掉').toBeLessThanOrEqual(0);
  expect(m.actsBottom, '动作区没贴右栏底').toBe(m.railBottom);
  expect(m.actsBottom, '动作区被顶到画布外面了 —— 键还在 DOM 里,但手指够不到').toBeLessThanOrEqual(m.screenBottom);

  // 上面那几条只证明「盒子没被顶动」。**溢出到底是被这一块自己吃掉了,还是糊到了下面那排开关上**,
  // 盒子的矩形分不出来(`overflow:visible` 下每个盒子的 rect 一模一样)——
  // 只有「它自己能不能滚」分得出来。用**真滚轮**:合成事件 Chromium 不认,
  // 而 `scrollTop = n` 只证明这个属性可写。
  // 变异实测(2026-08-22):把 `.railsec__body` 的 `overflow-y:auto` 改成 `visible`,
  // 上面四条**全绿**,只有下面这条红。
  const body = page.locator('.railsec__body');
  const bb = (await body.boundingBox())!;
  await page.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
  await page.mouse.wheel(0, 200);
  await expect.poll(() => body.evaluate((el) => el.scrollTop),
    { message: '着法那一块自己滚不动 —— 溢出会糊到下面那排开关上' }).toBeGreaterThan(0);
});

/* ══ 屏 16 棋谱详情 ════════════════════════════════════════════════════════
 * 造数据的两个接口:`/api/v1/kifu/albums/:id`(元数据 + SGF)和
 * `/api/v1/baipu/load`(逐步表,**提子由它给**)。坐标是 canonical:row=0 在上。
 */
const KIFU_ALBUM = {
  id: 7,
  player_black: '申真谞', player_white: '柯洁',
  black_rank: '九段', white_rank: '九段',
  event: '第 29 届三星杯', round_name: '半决赛',
  result: 'B+R', move_count: 241,
  date_played: '2026-06-30', board_size: 19, handicap: 0,
  komi: 7.5, rules: 'chinese', place: null, source: null,
  sgf_content: '(;FF[4]GM[1]SZ[19];B[pd])',
};

/** n 手谱。前四手照稿子那张图的头四手,再往后按行铺开凑数(只为把着法表撑到会溢出)。 */
const kifuSteps = (n: number) => Array.from({ length: n }, (_, i) => ({
  kind: 'move', move_index: i, property: i % 2 === 0 ? 'B' : 'W',
  row: 3 + Math.floor(i / 15), col: 3 + (i % 15),
  color: i % 2 === 0 ? 'B' : 'W', removed: [], board_hash: '',
}));

const bootKifuDetail = async (page: Page, moves: number) => {
  await page.route('**/api/v1/kifu/albums/*', (route) => route.fulfill({ json: KIFU_ALBUM }));
  await page.route('**/api/v1/baipu/load', (route) => route.fulfill({
    json: { board_size: 19, steps: kifuSteps(moves), meta: {} },
  }));
  await boot(page, '/kiosk/kifu/7');
  await page.waitForSelector('[data-testid="kifu-detail-actions"] button');
};

/**
 * 和上面做题屏那条是**同一条不变式的另一条实现路径**:做题屏的盘是 canvas(要能点),
 * 这一屏的盘是 `GoBoardSvg`(只看不点)。SVG 的线在 DOM 里问得出来,不必读像素 ——
 * 但**判据一个字不改**:屏上第一条 / 最后一条竖线的横坐标,要正对刻度带头尾两个字心。
 *
 * `GoBoardSvg` 的 0.5 格边距是由构造保证的(`goBoard.ts` 那段推导),所以这条闸守的
 * 不是它自己算错,而是**外面那层**:`.kiosk-board__play` 的内边距、`preserveAspectRatio`
 * 造成的居中留白、将来有人给盘加一圈边框 —— 任何一样都会让两者错开,而 SVG 内部数值照旧对。
 */
test('§8 棋谱详情:SVG 盘的头尾两条竖线,正对刻度带头尾两个字', async ({ page }) => {
  await bootKifuDetail(page, 8);
  const m = await page.evaluate(() => {
    const svg = document.querySelector('.kiosk-board__play svg.gob') as SVGSVGElement;
    const lines = [...svg.querySelectorAll('line.ln')]
      .filter((l) => l.getAttribute('x1') === l.getAttribute('x2'));   // 竖线
    const xOf = (el: Element) => { const r = el.getBoundingClientRect(); return r.left + r.width / 2; };
    const labels = [...document.querySelectorAll('.kiosk-board__ruler--top span')].map(xOf);
    return {
      lines: lines.length,
      labels: labels.length,
      firstLine: xOf(lines[0]),
      lastLine: xOf(lines[lines.length - 1]),
      firstLabel: labels[0],
      lastLabel: labels[labels.length - 1],
    };
  });
  expect(m.labels, '刻度带不是 19 个字').toBe(19);
  expect(m.lines, 'SVG 上不是 19 条竖线').toBe(19);
  expect(Math.abs(m.firstLine - m.firstLabel),
    `第一条线 ${m.firstLine.toFixed(1)} 和第一个字 ${m.firstLabel.toFixed(1)} 对不上`).toBeLessThanOrEqual(1.5);
  expect(Math.abs(m.lastLine - m.lastLabel),
    `最后一条线 ${m.lastLine.toFixed(1)} 和最后一个字 ${m.lastLabel.toFixed(1)} 对不上`).toBeLessThanOrEqual(1.5);
});

/**
 * 右栏:页控条 44 + 题头 + 谱(`flex:1`)+ 四个翻手键 + 两个动作键 = 516。
 * **造数据要造到会溢出** —— 241 手的谱,四十几行,`.kiosk-fold__body` 装不下。
 * 装得下的数据量下量出来的数字一概不算。
 */
test('§11 棋谱详情:谱再长,动作区也贴着右栏底,谱自己滚', async ({ page }) => {
  await bootKifuDetail(page, 240);

  const m = await page.evaluate(() => {
    const rail = document.querySelector('.kiosk-rail') as HTMLElement;
    const acts = document.querySelector('[data-testid="kifu-detail-actions"]') as HTMLElement;
    const nav = document.querySelector('[data-testid="kifu-detail-movenav"]') as HTMLElement;
    const body = document.querySelector('.kiosk-fold__body.mvrows') as HTMLElement;
    const screen = document.querySelector('.kiosk-screen') as HTMLElement;
    const r = rail.getBoundingClientRect();
    return {
      railH: Math.round(r.height),
      railBottom: Math.round(r.bottom),
      actsBottom: Math.round(acts.getBoundingClientRect().bottom),
      actsCount: acts.querySelectorAll('button').length,
      navCount: nav.querySelectorAll('button').length,
      overflowInBody: body.scrollHeight - body.clientHeight,
      railOverflow: rail.scrollHeight - rail.clientHeight,
      screenBottom: Math.round(screen.getBoundingClientRect().bottom),
    };
  });

  expect(m.railH, '右栏不是 516 —— 布局 A 的高度账先崩了').toBe(516);
  expect(m.navCount, '翻手键不是四个').toBe(4);
  expect(m.actsCount, '动作区不是两个键(摆到实体盘 / 去研究)').toBe(2);
  expect(m.overflowInBody, '没造出「谱装不下」—— 下面那条断言是空的').toBeGreaterThan(100);
  expect(m.railOverflow, '右栏自己被顶破了 —— 溢出该由谱那一块吃掉').toBeLessThanOrEqual(0);
  expect(m.actsBottom, '动作区没贴右栏底').toBe(m.railBottom);
  expect(m.actsBottom, '动作区被顶到画布外面了').toBeLessThanOrEqual(m.screenBottom);

  // 同屏 14 那条:盒子的矩形对 `overflow:visible` 免疫,分得出来的只有「它自己能不能滚」。
  // 变异实测(2026-08-22):把 `.kiosk-fold__body.mvrows` 的 `overflow-y:auto` 去掉
  // (回落到共享 `.kiosk-fold__body` 的 `overflow:hidden`),上面六条**全绿**,只有下面这条红。
  const body = page.locator('.kiosk-fold__body.mvrows');
  const bb = (await body.boundingBox())!;
  await page.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
  await page.mouse.wheel(0, 300);
  await expect.poll(() => body.evaluate((el) => el.scrollTop),
    { message: '谱那一块自己滚不动 —— 翻不到后面的手' }).toBeGreaterThan(0);
});

// ── 屏 19 复盘:形态 2(头尾固定,只有中间那条会长的列表滚)──────────────────

const reviewGames = (n: number) => Array.from({ length: n }, (_, i) => ({
  id: `g${i}`, user_id: 1, title: null, player_black: 'tester', player_white: 'KataGo',
  black_rank: null, white_rank: '6 级', result: i % 3 === 0 ? 'B+R' : 'W+2.5',
  board_size: 19, rules: 'chinese', komi: 7.5, move_count: 100 + i,
  source: 'play_ai', category: 'game', game_type: 'free',
  event: null, round_name: null, game_date: '2026-08-20',
  created_at: '2026-08-20T15:12:00', updated_at: null,
}));

/** **造到会溢出**:30 局塞进 168 高的视口。装得下的数据量下量出来的数字一概不算。 */
const bootReview = async (page: Page, n: number) => {
  await page.route('**/api/v1/user-games/*', (route) => route.fulfill({
    json: { ...reviewGames(1)[0], id: 'g0', sgf_content: '(;FF[4]GM[1]SZ[19];B[pd];W[dd])' },
  }));
  await page.route('**/api/v1/user-games**', (route) => route.fulfill({
    json: { items: reviewGames(n), total: n, page: 1, page_size: 12 },
  }));
  await page.route('**/api/v1/reports/summary', (route) => route.fulfill({
    json: { pending: 0, running: 0, completed: 0, failed: 0 },
  }));
  // 第一局**两档报告都跑完**,而且它是默认选中的那一行 —— 于是行尾最挤的那一种在这儿:
  // 状态标 + 「标准」+「精读」+「删除」四个元素。行宽装不下的话下面那条会红。
  await page.route('**/api/v1/reports/', (route) => route.fulfill({
    json: [
      { id: 1, user_game_id: 'g0', status: 'completed', report_type: 'normal', total_moves: 100, analyzed_moves: 100, requested_visits: 500 },
      { id: 2, user_game_id: 'g0', status: 'completed', report_type: 'deep', total_moves: 100, analyzed_moves: 100, requested_visits: 2000 },
    ],
  }));
  await page.route('**/api/v1/baipu/load', (route) => route.fulfill({
    json: {
      board_size: 19,
      steps: [
        { kind: 'move', move_index: 0, property: 'B', row: 3, col: 15, color: 'B', removed: [], board_hash: '' },
        { kind: 'move', move_index: 1, property: 'W', row: 15, col: 3, color: 'W', removed: [], board_hash: '' },
      ],
      meta: {},
    },
  }));
  await boot(page, '/kiosk/report');
  await page.waitForSelector('[data-testid="review-rows"] .kiosk-row', { state: 'attached' });
};

/**
 * 纵向账:胜率(20+6+96=122)+ 8 + 历史对局(吃剩下的)+ 8 + 生成报告(20+6+76=102)= 434。
 * **写成关系式**:三块加两条 gap 等于右栏高,中间那块是被挤出来的。
 * 具体像素(122 / 194 / 102)只作记录。
 */
test('§5 屏 19 形态 2:头尾两块定高,中间那块吃掉剩下的,合起来正好是右栏', async ({ page }) => {
  await bootReview(page, 30);
  const m = await page.evaluate(() => {
    const r = (s: string) => {
      const el = document.querySelector(s);
      if (!el) throw new Error(`没有这个元素: ${s}`);
      const b = el.getBoundingClientRect();
      return { y: Math.round(b.y), h: Math.round(b.height), bottom: Math.round(b.bottom) };
    };
    const side = document.querySelector('.kiosk-side') as HTMLElement;
    const sections = [...document.querySelectorAll('.kiosk-side__fixed > *')];
    return {
      side: r('.kiosk-side'),
      sideOverflow: side.scrollHeight - side.clientHeight,
      blocks: sections.map((el) => {
        const b = el.getBoundingClientRect();
        return { y: Math.round(b.y), h: Math.round(b.height) };
      }),
    };
  });
  expect(m.side.h, '右栏不是 434 —— L1 的高度账先崩了').toBe(434);
  expect(m.blocks.length, '右栏不是三块').toBe(3);
  const [wr, grow, cards] = m.blocks;
  expect(wr.h + 8 + grow.h + 8 + cards.h, '三块加两条 gap 对不上右栏高').toBe(m.side.h);
  expect(grow.h, '中间那块没吃到剩余空间').toBeGreaterThan(wr.h);
  // 形态 2 的定义:**整栏不滚**。整栏能滚 = 把生成报告那三张常驻入口也一起滚走了。
  expect(m.sideOverflow, '整条右栏自己滚起来了 —— 那就不是形态 2 了').toBeLessThanOrEqual(0);
});

/**
 * **只有中间那块滚。** 判据不是「有没有 overflow」,是滚完之后头尾两块的位置一动不动 ——
 * 生成报告那三张卡是常驻入口,跟着列表滚走就找不着了。
 *
 * 变异实测(2026-08-23):把 `.kiosk-side__fixed` 换成 `.kiosk-side.kiosk-scrollzone`(形态 1),
 * 上面那条「三块加两条 gap = 434」照旧绿,只有这条红。
 */
test('§5 屏 19 承重:列表滚起来的时候,胜率曲线和生成报告一个像素都不动', async ({ page }) => {
  await bootReview(page, 30);
  const before = await page.evaluate(() => ({
    wr: Math.round(document.querySelector('.wrbox')!.getBoundingClientRect().y),
    cards: Math.round(document.querySelector('[data-testid="review-cards"]')!.getBoundingClientRect().y),
  }));

  const scroll = page.locator('.kiosk-section--grow .kiosk-side__scroll');
  const bb = (await scroll.boundingBox())!;
  await page.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
  await page.mouse.wheel(0, 400);
  await expect.poll(() => scroll.evaluate((el) => el.scrollTop),
    { message: '列表自己滚不动 —— 后面那些局到不了' }).toBeGreaterThan(0);

  const after = await page.evaluate(() => ({
    wr: Math.round(document.querySelector('.wrbox')!.getBoundingClientRect().y),
    cards: Math.round(document.querySelector('[data-testid="review-cards"]')!.getBoundingClientRect().y),
    at: document.querySelector('.kiosk-section--grow')!.getAttribute('data-at'),
    thumb: Math.round((document.querySelector('.kiosk-scrollbar') as HTMLElement).getBoundingClientRect().height),
  }));
  expect(after.wr, '胜率曲线跟着列表滚走了').toBe(before.wr);
  expect(after.cards, '生成报告那三张卡跟着列表滚走了').toBe(before.cards);
  expect(after.at, '滚过之后还报 top —— 渐隐说的是假话').not.toBe('top');
  expect(after.thumb, '悬浮条拇指短于 24,读不出比例').toBeGreaterThanOrEqual(24);
});

/**
 * 渐隐钉在**真正滚的那一块**上,从组标题下缘开始 —— 盖住组标题的话,
 * 「历史对局」四个字会随滚动忽明忽暗。
 * 收起搜索时头就是一条组标题(20+6=26);展开时多一条 44 的框 + 10 的空(再 +54)。
 */
test('§5 屏 19:渐隐从组标题下缘开始,展开「筛 + 搜」之后跟着往下挪', async ({ page }) => {
  await bootReview(page, 30);
  const closed = await page.evaluate(() => {
    const sec = document.querySelector('.kiosk-section--grow') as HTMLElement;
    const label = document.querySelector('.kiosk-section--grow .kiosk-seclabel') as HTMLElement;
    const scroll = document.querySelector('.kiosk-section--grow .kiosk-side__scroll') as HTMLElement;
    return {
      fade: parseFloat(getComputedStyle(sec, '::before').top),
      headH: Math.round(scroll.getBoundingClientRect().top - sec.getBoundingClientRect().top),
      labelH: Math.round(label.getBoundingClientRect().height),
    };
  });
  expect(closed.fade, '渐隐没落在滚动区的起点上 —— 它盖住组标题了').toBe(closed.headH);
  expect(closed.headH, '收起时头不止一条组标题').toBe(closed.labelH + 6);

  await page.click('button[aria-label="筛选和搜索历史对局"]');
  await page.waitForSelector('[data-testid="review-search"]');
  const open = await page.evaluate(() => {
    const sec = document.querySelector('.kiosk-section--grow') as HTMLElement;
    const scroll = document.querySelector('.kiosk-section--grow .kiosk-side__scroll') as HTMLElement;
    const r = (sel: string) => document.querySelector(sel)!.getBoundingClientRect();
    return {
      fade: parseFloat(getComputedStyle(sec, '::before').top),
      headH: Math.round(scroll.getBoundingClientRect().top - sec.getBoundingClientRect().top),
      labelH: Math.round(r('.kiosk-section--grow .kiosk-seclabel').height),
      segRight: Math.round(r('.rvfind .kiosk-optseg').right),
      inputLeft: Math.round(r('.rvsearch').left),
      inputRight: Math.round(r('.rvsearch').right),
      secRight: Math.round(r('.kiosk-section--grow').right),
      docScrollW: document.documentElement.scrollWidth,
    };
  });
  expect(open.headH, '展开「筛 + 搜」没把头撑高 54(44 的框 + 10 的空)').toBe(closed.headH + 54);
  expect(open.fade, '展开之后渐隐没跟着挪 —— 它压在那条带子上').toBe(open.headH);

  /*
   * 2026-08-26 那条带子里多了一个来源筛选(Fan 裁定要补)。
   * **它没有别处可去**:组标题行只有 20 高(`--l1-sec-label-h`),连 26 高的药丸都塞不进去;
   * 单开一条常驻的筛选行又要再从列表里扣 54 —— 而列表是这一屏唯一会长的东西。
   * 所以它和搜索框同住这一条 44 的带子,上面那个 +54 因此**一分不变**。
   */
  expect(open.labelH, '筛选把组标题行撑高了 —— 那一行只有 20').toBe(closed.labelH);
  expect(open.segRight, '筛选和搜索框叠在一起了').toBeLessThanOrEqual(open.inputLeft);
  expect(open.inputRight, '搜索框出了这一组的右缘').toBe(open.secRight);
  expect(open.docScrollW, '整页横向溢出了').toBeLessThanOrEqual(1024);
});

/**
 * §5「露一半」:视口下缘必须切在**某一行的内部**。切在行与行的空隙里,
 * 屏上就是一条干干净净的下边界 —— 看不出下面还有二十几局。
 * 今天的值:第三行 52 高、露 48。**判据是「切在行内」,48 只是记录。**
 */
test('§5 屏 19:视口下缘切在一行的中间,不落在行与行的空隙里', async ({ page }) => {
  await bootReview(page, 30);
  const m = await page.evaluate(() => {
    const scroll = document.querySelector('.kiosk-section--grow .kiosk-side__scroll') as HTMLElement;
    const sb = scroll.getBoundingClientRect();
    const rows = [...document.querySelectorAll('[data-testid="review-rows"] .kiosk-row')].map((el) => {
      const b = el.getBoundingClientRect();
      return { top: b.top - sb.top, bottom: b.bottom - sb.top, h: b.height };
    });
    const cut = scroll.clientHeight;
    const straddling = rows.find((r) => r.top < cut && r.bottom > cut);
    return {
      overflow: scroll.scrollHeight - scroll.clientHeight,
      cut,
      shown: straddling ? Math.round(cut - straddling.top) : null,
      rowH: straddling ? Math.round(straddling.h) : null,
    };
  });
  expect(m.overflow, '没造出「装不下」—— 下面那条断言是空的').toBeGreaterThan(100);
  expect(m.shown, '视口下缘落在两行之间,看不出下面还有').not.toBeNull();
  expect(m.shown!).toBeGreaterThan(0);
  expect(m.shown!).toBeLessThan(m.rowH!);
});

// ── 屏 20 复盘 · 报告(L2 布局 A:盘 516 + 16 + 右栏 460)────────────────────

const REPORT_GAME = {
  id: 'g1', user_id: 1, title: null, player_black: 'tester', player_white: 'KataGo',
  black_rank: null, white_rank: '6 级', result: 'W+R', board_size: 19, rules: 'chinese',
  komi: 7.5, move_count: 40, source: 'play_ai', category: 'game', game_type: 'free',
  event: null, round_name: null, game_date: '2026-08-20',
  created_at: '2026-08-20T15:12:00', updated_at: null,
  // 40 手谱 —— 造到「重点手」和曲线都有东西可画。
  sgf_content: `(;FF[4]GM[1]SZ[19]${Array.from({ length: 40 }, (_, i) => {
    const col = String.fromCharCode(97 + (i % 19));
    const row = String.fromCharCode(97 + Math.floor(i / 19) * 3);
    return `;${i % 2 === 0 ? 'B' : 'W'}[${col}${row}]`;
  }).join('')})`,
};

/**
 * 逐手分析。每四手来一次大跌。
 *
 * 2026-09-02 补上**七档字段**:屏 20 的五个 tab 读的是服务端判好的 `grade` / `points_lost`,
 * 不再是 `delta_score`。不补的话四个 tab 全落进空态,「把数据造到会溢出」这一步就没做到,
 * 下面那些几何断言量的是一屏空图。
 *
 * `top_moves` 给满十个:AI 推荐那张表是这一屏**最高的那一块**(体装不下、要自己滚),
 * 最坏那一档就在它身上。
 */
const reportMoveRows = () => Array.from({ length: 41 }, (_, n) => ({
  id: n, task_id: 7, move_number: n, status: 'success',
  winrate: 0.5 - n * 0.008, score_lead: -n * 0.4, visits: 500,
  grade: n === 0 ? null : (n % 4 === 1 ? 'blunder' : (n % 7 === 3 ? 'brilliant' : 'best')),
  points_lost: n === 0 ? null : (n % 4 === 1 ? 6 : 0),
  points_lost_source: n === 0 ? null : 'in_search',
  is_top_move: n % 4 !== 1,
  top_prior: n % 7 === 3 ? 0.016 : 0.5,
  brilliance: n % 7 === 3 ? 3 : null,
  top_moves: n % 2 === 0
    ? Array.from({ length: 10 }, (_, k) => ({
      move: `R${11 + k}`, visits: 400 - k * 30, winrate: 0.6 - k * 0.02,
      score_lead: 2 - k * 0.5, prior: 0.6 - k * 0.05, pv: [`R${11 + k}`], psv: 1,
    }))
    : null,
  ownership: null,
  actual_move: n === 0 ? null : 'C3',
  actual_player: n === 0 ? null : (n % 2 === 1 ? 'B' : 'W'),
  delta_score: n === 0 ? null : (n % 4 === 1 ? -6 : -0.4),
  delta_winrate: null,
}));

const bootReportDetail = async (page: Page) => {
  await page.route('**/api/v1/reports/7/moves', (route) => route.fulfill({ json: reportMoveRows() }));
  await page.route('**/api/v1/reports/7', (route) => route.fulfill({
    json: {
      id: 7, user_game_id: 'g1', status: 'completed', report_type: 'deep',
      total_moves: 40, analyzed_moves: 40, requested_visits: 2000,
      // **这两个章在这里是「把数据造到会溢出」那一步**,不是为了好看。
      // 接上耗时之后 `.rhead` 的副行从「每手算 2000 次 · 40 手」变成
      // 「每手算 2000 次 · 用了 128分36秒」—— 它一换行,`.rhead` 就长高,
      // 下面那块自己滚的重点手列表可用高度当场变。所以这里造的是**最坏那一档**
      // (深度复盘 + 长局,分位到三位数),不是稿子里那个 6 分 12 秒。
      // 稿子那一档在四图闸里(`kiosk-screen-20-report.fourup.spec.ts`)—— 那一关看
      // 静止一帧对不对,这一关量交互之后对不对,两边造的数据本来就该不一样。
      started_at: '2026-08-23T01:00:00+08:00', completed_at: '2026-08-23T03:08:36+08:00',
    },
  }));
  await page.route('**/api/v1/user-games/g1', (route) => route.fulfill({ json: REPORT_GAME }));
  await boot(page, '/kiosk/report/7');
  await page.waitForSelector('[data-testid="report-detail-movenav"] button', { state: 'attached' });
  // canvas 是图片加载完之后才画的 —— 早一步读到的是一张空白。
  await page.waitForFunction(() => {
    const c = document.querySelector('.kiosk-board__play canvas') as HTMLCanvasElement | null;
    if (!c || !c.width) return false;
    const d = c.getContext('2d')!.getImageData(0, Math.floor(c.height / 2), c.width, 1).data;
    for (let i = 0; i < d.length; i += 4) if (d[i] > 40) return true;   // 有木色了
    return false;
  });
};

/**
 * 和做题屏那条是**同一条不变式的第三条实现路径**。
 *
 * `LiveBoard` 原来永远按 1.5 格边距画(那是给盘面里自己那圈坐标留的位置),而布局 A 的
 * 坐标交给外壳 ⇒ 线的节距 W/(N−1+3)、刻度带的节距 W/N,**两者不等**。
 * 本轮给 `calculateBoardLayout` 加了 `margin` 参数、`LiveBoard` 在
 * `showCoordinates=false` 时传 0.5 —— 这条闸守的正是那个参数别被人改回去。
 *
 * 变异实测(2026-08-23):把 `showCoordinates ? 1.5 : 0.5` 改回常数 1.5,这条当场红
 * (头尾两条线各偏 11 像素以上),而同文件里别的 25 条一条都不动。
 */
test('§8 复盘报告:盘上第一条和最后一条竖线,正对刻度带头尾两个字', async ({ page }) => {
  await bootReportDetail(page);

  const m = await page.evaluate(() => {
    const canvas = document.querySelector('.kiosk-board__play canvas') as HTMLCanvasElement;
    const cr = canvas.getBoundingClientRect();
    const ctx = canvas.getContext('2d')!;
    const y = Math.floor(canvas.height * 0.28);
    const row = ctx.getImageData(0, y, canvas.width, 1).data;
    const lum: number[] = [];
    for (let x = 0; x < canvas.width; x += 1) lum.push((row[x * 4] + row[x * 4 + 1] + row[x * 4 + 2]) / 3);
    const wood = [...lum].sort((a, b) => a - b)[Math.floor(lum.length * 0.75)];
    let woodL = 0;
    while (woodL < lum.length && lum[woodL] < wood * 0.5) woodL += 1;
    let woodR = lum.length - 1;
    while (woodR > woodL && lum[woodR] < wood * 0.5) woodR -= 1;
    const dark: number[] = [];
    for (let x = woodL + 1; x < woodR; x += 1) if (lum[x] < wood * 0.72) dark.push(x);
    const lines: number[] = [];
    let run = [dark[0]];
    for (let i = 1; i < dark.length; i += 1) {
      if (dark[i] - dark[i - 1] <= 2) run.push(dark[i]);
      else { lines.push(run.reduce((a, b) => a + b, 0) / run.length); run = [dark[i]]; }
    }
    if (run.length) lines.push(run.reduce((a, b) => a + b, 0) / run.length);
    const toPage = (px: number) => cr.left + (px / canvas.width) * cr.width;
    const xOf = (el: Element) => { const r = el.getBoundingClientRect(); return r.left + r.width / 2; };
    const labels = [...document.querySelectorAll('.kiosk-board__ruler--top span')].map(xOf);
    return {
      lines: lines.length,
      labels: labels.length,
      firstLine: toPage(lines[0]),
      lastLine: toPage(lines[lines.length - 1]),
      firstLabel: labels[0],
      lastLabel: labels[labels.length - 1],
    };
  });

  expect(m.labels, '刻度带不是 19 个字').toBe(19);
  expect(m.lines, '像素里数出来的竖线不是 19 条 —— 阈值或取样行选歪了,下面两条不作数').toBe(19);
  expect(Math.abs(m.firstLine - m.firstLabel),
    `第一条线 ${m.firstLine.toFixed(1)} 和第一个字 ${m.firstLabel.toFixed(1)} 对不上`).toBeLessThanOrEqual(1.5);
  expect(Math.abs(m.lastLine - m.lastLabel),
    `最后一条线 ${m.lastLine.toFixed(1)} 和最后一个字 ${m.lastLabel.toFixed(1)} 对不上`).toBeLessThanOrEqual(1.5);
});

/**
 * 右栏纵向账:页控条 44 + 题头 60 + **两个折叠头 2×30** + 四个开关 40 + 四个翻手键 36
 * + 5×12(rail-gap)= 300 ⇒ 展开那一块的体 216。翻手键是这一屏的肌肉记忆位置,
 * **任何一块长高都不许把它顶出画布**。
 *
 * 2026-09-02 重写:上一版量的是「重点手」那张列表,而那一块**整个不存在了** ——
 * 屏 20 换成了 galaxy 那五个 tab(走势/妙手/失误/发挥水准/AI吻合度)加一张 AI 推荐表,
 * 两块折叠**同一时刻只开一块**。闸不是失效,是断言的对象换了:
 * 守的仍然是「右栏 516、溢出由展开那一块自己吃掉、翻手键贴底」。
 *
 * **两个状态都要量** —— 单开手风琴有两种版式,只量一种等于放过另一种:
 *   ① 默认态:AI 推荐展开(十个候选装不下 ⇒ 表自己滚);
 *   ② 点开着手评价:五个 tab 里最高的那一个(AI吻合度·统计,三行 + 两句脚注)。
 */
test('§11 复盘报告:两块折叠各自展开时,右栏都是 516、翻手键都贴底、溢出都由折叠体自己吃', async ({ page }) => {
  await bootReportDetail(page);

  const measure = () => page.evaluate(() => {
    const rail = document.querySelector('.kiosk-rail') as HTMLElement;
    const nav = document.querySelector('[data-testid="report-detail-movenav"]') as HTMLElement;
    const toggles = document.querySelector('[data-testid="report-detail-toggles"]') as HTMLElement;
    const openBody = document.querySelector('.kiosk-fold[data-open="true"] .kiosk-fold__body') as HTMLElement;
    const screenEl = document.querySelector('.kiosk-screen') as HTMLElement;
    const r = rail.getBoundingClientRect();
    return {
      railH: Math.round(r.height),
      railBottom: Math.round(r.bottom),
      navBottom: Math.round(nav.getBoundingClientRect().bottom),
      navCount: nav.querySelectorAll('button').length,
      toggleNames: [...toggles.querySelectorAll('button')].map((b) => b.textContent),
      progressText: (document.querySelector('[data-testid="report-detail-progress"]') as HTMLElement).textContent,
      rheadH: Math.round((document.querySelector('[data-testid="report-detail-rhead"]') as HTMLElement)
        .getBoundingClientRect().height),
      railOverflow: rail.scrollHeight - rail.clientHeight,
      bodyOverflow: openBody.scrollHeight - openBody.clientHeight,
      bodyH: Math.round(openBody.getBoundingClientRect().height),
      screenBottom: Math.round(screenEl.getBoundingClientRect().bottom),
    };
  });

  // **这一条守的是「量的是不是最坏那一档」,不是版式本身。** 没有它,谁把 fixture 里
  // 那两个章删掉,下面整组几何断言就悄悄退回去量那条短行,而且照样全绿。
  const first = await measure();
  console.log('[report-rhead] rheadH=%d text=%s', first.rheadH, first.progressText);
  expect(first.progressText, '副行没写成耗时 —— 那这条闸量的不是接上耗时之后的版式')
    .toContain('用了 128分36秒');

  // ① 默认态:AI 推荐展开。十个候选装不下 ⇒ **表自己滚**,右栏不许被顶破。
  expect(await page.locator('[data-testid="report-detail-ai"]').getAttribute('data-open')).toBe('true');
  expect(first.railH, '右栏不是 516 —— 布局 A 的高度账先崩了').toBe(516);
  expect(first.navCount, '翻手键不是四个').toBe(4);
  // 名字与顺序都是判据:两端左起第一颗都得是「试下」,不然「一眼对应上」这句话不成立。
  expect(first.toggleNames, '显示开关没按 galaxy 的名字与顺序排')
    .toEqual(['试下', '领地', '手数', '支招']);
  expect(first.bodyOverflow, 'AI 推荐表没溢出 —— 那这一条量的不是「装不下」那一档').toBeGreaterThan(0);
  expect(first.railOverflow, '右栏自己被顶破了 —— 溢出该由折叠体吃掉').toBeLessThanOrEqual(0);
  expect(first.navBottom, '翻手键没贴右栏底').toBe(first.railBottom);
  expect(first.navBottom, '翻手键被顶到画布外面了').toBeLessThanOrEqual(first.screenBottom);

  // ② 点开着手评价 —— AI 推荐必须跟着收起(单开),而账要照样平。
  await page.getByRole('button', { name: /着手评价/ }).click();
  expect(await page.locator('[data-testid="report-detail-ai"]').getAttribute('data-open')).toBe('false');
  await expect(page.getByTestId('review-winrate-plot')).toHaveAttribute('data-state', 'plotted');

  // 五个 tab 逐个量:每一个都不许把折叠体撑破,右栏都得是 516、翻手键都得贴底。
  for (const tab of ['走势', '妙手', '失误', '发挥水准', 'AI吻合度']) {
    await page.getByRole('button', { name: tab, exact: true }).click();
    const m = await measure();
    expect(m.railH, `${tab}:右栏不是 516`).toBe(516);
    expect(m.railOverflow, `${tab}:右栏被顶破`).toBeLessThanOrEqual(0);
    expect(m.bodyOverflow, `${tab}:折叠体内容被裁 ${m.bodyOverflow}px`).toBeLessThanOrEqual(0);
    expect(m.navBottom, `${tab}:翻手键没贴右栏底`).toBe(m.railBottom);
  }
  // AI吻合度 的两个视图版式不同,分布那一支也得量。
  await page.getByRole('button', { name: '分布', exact: true }).click();
  const dist = await measure();
  expect(dist.bodyOverflow, `分布视图:折叠体内容被裁 ${dist.bodyOverflow}px`).toBeLessThanOrEqual(0);
  expect(dist.navBottom, '分布视图:翻手键没贴右栏底').toBe(dist.railBottom);
});

// ── D2 稿外五屏:只接壳,不推导版式 ──────────────────────────────────────

/**
 * 摆谱 / 直播 / 研究 / 跨平台 / 标定 —— 稿子没画这五屏。**没有参照物就没有四图闸**,
 * 所以它们的验收只有这一条:**共享外壳这一层是对的,切模块的时候不跳**。
 *
 * 三条判据合起来就是「切模块不跳」在这五屏上的全部要求:
 *   ① 顶栏 1024×56 贴在 (0,0) —— 规范 §5 防跳铁律 1
 *   ② 内容区左缘 x16、通栏 992 —— 外边距 16 是规范开头明写「全部用 px」的那几个之一
 *   ③ 这五屏都不是 Dock 项 ⇒ `dockLevelOf` 判 2 ⇒ 没有 Dock ⇒ 内容区下缘贴画布底 600
 *
 * ⚠️ ③ **不是 bug**:Task 4 把摆谱和直播下了 Dock(规范 §3 只许一个棋种专属项),
 * 它们因此不再是 L1。内容区从 434 变成 516 是那条裁定的后果,别去「纠正」。
 */
const D2_SCREENS: readonly [string, string][] = [
  ['/kiosk/baipu', '摆谱'],
  ['/kiosk/live', '直播'],
  ['/kiosk/research', '研究'],
  ['/kiosk/play/cross-platform', '跨平台'],
  ['/kiosk/vision/setup', '标定'],
];

for (const [path, name] of D2_SCREENS) {
  test(`D2 ${name}(${path}):顶栏 1024×56@(0,0)、内容区 x16 宽 992、无 Dock 时下缘贴 600`, async ({ page }) => {
    await page.route('**/api/v1/kifu/albums*', (route) => route.fulfill({
      json: { items: [], total: 0, page: 1, page_size: 12 },
    }));
    await page.route('**/live/matches*', (route) => route.fulfill({
      json: { matches: [], live_count: 0, total: 0 },
    }));
    await boot(page, path);

    const topbar = await box(page, '.kiosk-topbar');
    expect(topbar.x, '顶栏没贴左缘').toBe(0);
    expect(topbar.y, '顶栏没贴顶').toBe(0);
    expect(topbar.w, '顶栏不通栏').toBe(1024);
    expect(topbar.h, '顶栏不是 56 —— 防跳铁律 1 是它不变高').toBe(56);

    const content = await box(page, '.kiosk-content');
    expect(content.x, '内容区左缘不是 16').toBe(16);
    expect(content.w, '内容区不是通栏 992').toBe(992);
    // 量的是**外框**(border-box);规范 §5 说的「内容从 y70 起」说的是内沿 ——
    // 差的正好是 `--content-pad-y` 的 14。两套数不矛盾,别混着读。
    expect(content.y, '内容区上缘没接顶栏下沿').toBe(topbar.h);

    // 这五屏都不在 Dock 词典里 ⇒ L2 ⇒ 没有 Dock ⇒ 内容区一路到画布下缘。
    const dock = await page.evaluate(() => document.querySelectorAll('.kiosk-dock').length);
    expect(dock, `${name} 出了 Dock —— 它不在 Dock 词典里`).toBe(0);
    expect(content.bottom, '没有 Dock,内容区下缘就该贴画布底 600').toBe(600);
  });
}

/**
 * 行尾最挤的那一种:**两档报告都跑完 + 这一行还是选中的** ⇒
 * 状态标 +「标准」+「精读」+「删除」四个元素。
 *
 * 稿子的行尾只有一个状态标,所以这条没有参照物可比 —— 判据只能是**装不装得下**:
 * 行不许横向溢出,行尾也不许压到左半那块文字上。
 * (为什么会有两个报告键:`taskId` 是**按档**发的,同一局可以同时挂标准和精读两份;
 *  一个「查看报告」指不了两个 id。)
 */
test('§9 屏 19:两档都跑完又正好选中的那一行,行尾四个元素装得下', async ({ page }) => {
  await bootReview(page, 30);
  await page.waitForSelector('[data-testid="review-row"] .kiosk-row__end button');

  const m = await page.evaluate(() => {
    const row = document.querySelector('[data-testid="review-row"]') as HTMLElement;
    const pick = row.querySelector('.rvpick') as HTMLElement;
    const end = row.querySelector('.kiosk-row__end') as HTMLElement;
    const rb = row.getBoundingClientRect();
    const pb = pick.getBoundingClientRect();
    const eb = end.getBoundingClientRect();
    return {
      selected: row.getAttribute('data-selected'),
      state: row.getAttribute('data-state'),
      endButtons: [...end.querySelectorAll('button')].map((b) => b.textContent),
      rowOverflow: row.scrollWidth - row.clientWidth,
      endRight: Math.round(eb.right),
      rowInnerRight: Math.round(rb.right - 12),      // .kiosk-row 的右内边距是 12
      gap: Math.round(eb.left - pb.right),
      textClipped: pick.scrollWidth - pick.clientWidth,
    };
  });

  expect(m.selected, '第一行不是选中态 —— 那就造不出最挤的那一种').toBe('true');
  expect(m.state, '第一行不是「已分析」—— 两档报告的 fixture 没生效').toBe('analyzed');
  expect(m.endButtons, '行尾不是「标准 / 精读 / 删除」三个键').toEqual(['标准', '精读', '删除']);
  expect(m.rowOverflow, '行横向溢出了').toBeLessThanOrEqual(0);
  expect(m.endRight, '行尾越过了行的右内边界').toBeLessThanOrEqual(m.rowInnerRight);
  expect(m.gap, '行尾贴上了左半那块文字').toBeGreaterThanOrEqual(0);
  // 左半那块文字**允许**被省略号截掉(标题可以很长),但不许被挤到零宽。
  expect(m.textClipped, '左半那块文字被挤没了').toBeLessThan(400);
});

/* ══ 屏 25 课程 · 小节讲解 —— 只看一角时,刻度带的节距要跟着窗口走 ══════════════
 *
 * 这一屏的盘和别的布局 A 屏**不是同一个形状**:教程图可以只画棋盘一角,
 * 而后端 `viewport.py:31` 产的窗口有两种量级 —— 10×10 的方窗,和 19×10 / 10×19 的**半盘**。
 *
 * 判据一个字不改,还是那条不变式:**屏上第一条 / 最后一条线的坐标,要正对刻度带头尾两个字心**
 * (`.gob` 的 0.5 格边距由构造保证,这条闸守的是外面那层:刻度带的轨道尺寸、
 * `preserveAspectRatio` 造成的居中留白)。变的只是「几个字、几条线」不再恒是 19。
 *
 * ⚠️ **两轴都要量。** 半盘 19×10 下横轴 19 轨、纵轴 10 轨,而共享包那条补丁给的是 `1fr`
 * (均分整条带)—— 纵轴那 10 个字会被摊到 460 上,而盘按 `xMidYMid meet` 只占 242。
 * 只量横轴的话它是绿的:19 轨均分 460 和「节距 460/19」恰好同值。
 * **量通一条不等于整条链是对的**,这一屏正是那句话的实例。
 *
 * 造数据:方窗那一档量出来的数**证明不了**非方那一档,所以半盘的 payload 是手造的
 * (`preview.db` 里 `tutorial_figures` 是 0 行,本机没有真图)。
 *
 * 变异实测(2026-08-24)—— **第二条我先写错了,记在这儿**:
 *   · 撤掉 `.figure-board` 那条 `grid-auto-rows`(退回共享包的 `1fr`)
 *     ⇒ **上下半盘 19×10 的纵向断言红**(第一条横线 219.1 vs 第一个左字 121.0),横向全绿。
 *   · 撤掉 `grid-auto-columns` ⇒ 我原以为方窗那条会红,**跑下来三条全绿**。
 *     原因:`1fr` 是「均分整条带」,而带宽恰好就是落子区 —— **长轴上两者永远同值**。
 *     方窗两轴都是长轴,19×10 的长轴是横轴 ⇒ 这两种形状都杀不死它。
 *     ⇒ 补了**左右半盘 10×19** 那一条(`viewport.py:75` 真的会产这个形状),
 *     它的短轴是横轴;再跑同一个变异 ⇒ **它的横向断言红**。
 *     两条补丁各由一种半盘守着,方窗那两条是退化情形。
 *
 * 这条弯路本身值得留下:一条**挡不住任何东西的规则比没有更坏**,而「看起来对称所以
 * 两条都需要」是推不出来的 —— 得让每一条各自被一次变异杀死过。
 * ────────────────────────────────────────────────────────────────────────── */

/** 一张教程图。`viewport` 由调用方给 —— 它就是这条闸的自变量。 */
const figurePayload = (viewport: Record<string, number> | null) => ({
  id: 1, section_id: 10, page: 1, figure_label: '图 1',
  book_text: null, page_context_text: null, bbox: null, page_image_path: null,
  board_payload: {
    size: 19,
    // 子摆在窗口内,免得「窗口外的子不该出现」这件事混进来 —— 这条闸只量刻度带。
    stones: { B: [[1, 14], [2, 15]], W: [[4, 15]] },
    labels: { '2,15': '1', '4,15': '2' },
    viewport,
  },
  recognition_debug: null, narration: '量刻度带用的图。', audio_asset: null, video_asset: null,
  video_duration_ms: null, video_size_bytes: null, order: 0, updated_at: null,
});

const bootFigure = async (page: Page, viewport: Record<string, number> | null) => {
  await page.route('**/api/v1/tutorials/sections/10', (route) => route.fulfill({
    json: {
      id: 10, chapter_id: 11, section_number: '1', title: '量刻度带', order: 0,
      figure_count: 1, has_video: false, figures: [figurePayload(viewport)],
    },
  }));
  await boot(page, '/kiosk/tutorial/section/10');
  await page.waitForSelector('[data-testid="tutorial-figure-board"] svg.gob');
};

/** 两轴一起读:线的中心坐标、字的中心坐标,各取头尾。 */
const rulerVsLines = (page: Page) => page.evaluate(() => {
  const svg = document.querySelector('.kiosk-board__play svg.gob') as SVGSVGElement;
  const all = [...svg.querySelectorAll('line.ln')];
  const cx = (el: Element) => { const r = el.getBoundingClientRect(); return r.left + r.width / 2; };
  const cy = (el: Element) => { const r = el.getBoundingClientRect(); return r.top + r.height / 2; };
  // 竖线 x1===x2;横线 y1===y2。**屏上看得见的那些**才算 —— 线照全盘画、由 viewBox 裁,
  // 窗口外那些的 rect 落在盘外面,拿去和刻度带比就是拿看不见的东西比。
  //
  // ⚠️ 判「看不看得见」只能看**它自己那根轴**:横线是整幅宽的,窗口一裁它左右两头必然
  // 伸到盘外,拿「整个 rect 都在框内」去判会把每一条线都判成不可见(第一版就是这么写的,
  // 结果 `vert[0]` 是 undefined —— 闸当场炸,而不是悄悄绿掉)。
  //
  // ⚠️ 而「框」是 **viewBox 映射出来的那一块**,不是 `<svg>` 元素的盒子。非方窗下
  // `xMidYMid meet` 会上下(或左右)留白:19×10 在 460 的方框里只占 242 高,居中。
  // 拿元素盒子当框,窗口外那几条横线**照样落在 460 之内**(它们只是被 SVG 根裁掉了,
  // rect 还在)—— 第二版就是这么错的,量出 15 条横线而不是 10 条。
  // 这里问浏览器要 `getScreenCTM()`,**不自己算一遍缩放** —— 自己算就成了「用我的模型
  // 去核我的模型」。
  const ctm = svg.getScreenCTM()!;
  const vb = svg.viewBox.baseVal;
  const map = (x: number, y: number) => {
    const pt = new DOMPoint(x, y).matrixTransform(ctm);
    return { x: pt.x, y: pt.y };
  };
  const tl = map(vb.x, vb.y);
  const br = map(vb.x + vb.width, vb.y + vb.height);
  const box = { left: tl.x, right: br.x, top: tl.y, bottom: br.y };
  const inX = (el: Element) => {
    const r = el.getBoundingClientRect();
    return r.left >= box.left - 1 && r.right <= box.right + 1;
  };
  const inY = (el: Element) => {
    const r = el.getBoundingClientRect();
    return r.top >= box.top - 1 && r.bottom <= box.bottom + 1;
  };
  const vert = all.filter((l) => l.getAttribute('x1') === l.getAttribute('x2')).filter(inX);
  const horiz = all.filter((l) => l.getAttribute('y1') === l.getAttribute('y2')).filter(inY);
  const top = [...document.querySelectorAll('.kiosk-board__ruler--top span')];
  const left = [...document.querySelectorAll('.kiosk-board__ruler--left span')];
  return {
    verts: vert.length, horizs: horiz.length,
    topN: top.length, leftN: left.length,
    firstVert: cx(vert[0]), lastVert: cx(vert[vert.length - 1]),
    firstTop: cx(top[0]), lastTop: cx(top[top.length - 1]),
    firstHoriz: cy(horiz[0]), lastHoriz: cy(horiz[horiz.length - 1]),
    firstLeft: cy(left[0]), lastLeft: cy(left[left.length - 1]),
  };
});

test('§8 课程小节:10×10 方窗 —— 两轴的头尾线都正对头尾两个字', async ({ page }) => {
  await bootFigure(page, { col: 0, row: 9, size: 10 });
  const m = await rulerVsLines(page);

  expect(m.topN, '上带不是 10 个字').toBe(10);
  expect(m.leftN, '左带不是 10 个字').toBe(10);
  expect(m.verts, '窗口里看得见的不是 10 条竖线').toBe(10);
  expect(m.horizs, '窗口里看得见的不是 10 条横线').toBe(10);
  expect(Math.abs(m.firstVert - m.firstTop),
    `第一条竖线 ${m.firstVert.toFixed(1)} 和第一个上字 ${m.firstTop.toFixed(1)} 对不上`).toBeLessThanOrEqual(1.5);
  expect(Math.abs(m.lastVert - m.lastTop),
    `最后一条竖线 ${m.lastVert.toFixed(1)} 和最后一个上字 ${m.lastTop.toFixed(1)} 对不上`).toBeLessThanOrEqual(1.5);
  expect(Math.abs(m.firstHoriz - m.firstLeft),
    `第一条横线 ${m.firstHoriz.toFixed(1)} 和第一个左字 ${m.firstLeft.toFixed(1)} 对不上`).toBeLessThanOrEqual(1.5);
  expect(Math.abs(m.lastHoriz - m.lastLeft),
    `最后一条横线 ${m.lastHoriz.toFixed(1)} 和最后一个左字 ${m.lastLeft.toFixed(1)} 对不上`).toBeLessThanOrEqual(1.5);
});

test('§8 课程小节:19×10 半盘 —— 非方窗下短轴那条带要居中,不许摊满', async ({ page }) => {
  await bootFigure(page, { col: 0, row: 9, cols: 19, rows: 10 });
  const m = await rulerVsLines(page);

  expect(m.topN, '上带不是 19 个字').toBe(19);
  expect(m.leftN, '左带不是 10 个字').toBe(10);
  expect(m.verts, '窗口里看得见的不是 19 条竖线').toBe(19);
  expect(m.horizs, '窗口里看得见的不是 10 条横线').toBe(10);
  expect(Math.abs(m.firstVert - m.firstTop),
    `第一条竖线 ${m.firstVert.toFixed(1)} 和第一个上字 ${m.firstTop.toFixed(1)} 对不上`).toBeLessThanOrEqual(1.5);
  expect(Math.abs(m.lastVert - m.lastTop),
    `最后一条竖线 ${m.lastVert.toFixed(1)} 和最后一个上字 ${m.lastTop.toFixed(1)} 对不上`).toBeLessThanOrEqual(1.5);
  // ↓ 这两条才是这一屏新造出来的那半条链 —— 共享包的 `1fr` 在这儿是错的。
  expect(Math.abs(m.firstHoriz - m.firstLeft),
    `第一条横线 ${m.firstHoriz.toFixed(1)} 和第一个左字 ${m.firstLeft.toFixed(1)} 对不上`).toBeLessThanOrEqual(1.5);
  expect(Math.abs(m.lastHoriz - m.lastLeft),
    `最后一条横线 ${m.lastHoriz.toFixed(1)} 和最后一个左字 ${m.lastLeft.toFixed(1)} 对不上`).toBeLessThanOrEqual(1.5);
});

test('§8 课程小节:10×19 左半盘 —— 短轴换成横轴,守的是另一条补丁', async ({ page }) => {
  await bootFigure(page, { col: 0, row: 0, cols: 10, rows: 19 });
  const m = await rulerVsLines(page);

  expect(m.topN, '上带不是 10 个字').toBe(10);
  expect(m.leftN, '左带不是 19 个字').toBe(19);
  expect(m.verts, '窗口里看得见的不是 10 条竖线').toBe(10);
  expect(m.horizs, '窗口里看得见的不是 19 条横线').toBe(19);
  // ↓ 这两条是 `grid-auto-columns` 唯一的守卫:19×10 和方窗都杀不死它(长轴上 `1fr` 同值)。
  expect(Math.abs(m.firstVert - m.firstTop),
    `第一条竖线 ${m.firstVert.toFixed(1)} 和第一个上字 ${m.firstTop.toFixed(1)} 对不上`).toBeLessThanOrEqual(1.5);
  expect(Math.abs(m.lastVert - m.lastTop),
    `最后一条竖线 ${m.lastVert.toFixed(1)} 和最后一个上字 ${m.lastTop.toFixed(1)} 对不上`).toBeLessThanOrEqual(1.5);
  expect(Math.abs(m.firstHoriz - m.firstLeft),
    `第一条横线 ${m.firstHoriz.toFixed(1)} 和第一个左字 ${m.firstLeft.toFixed(1)} 对不上`).toBeLessThanOrEqual(1.5);
  expect(Math.abs(m.lastHoriz - m.lastLeft),
    `最后一条横线 ${m.lastHoriz.toFixed(1)} 和最后一个左字 ${m.lastLeft.toFixed(1)} 对不上`).toBeLessThanOrEqual(1.5);
});

test('§8 课程小节:切到全盘 —— 19 个字、19 条线,退回和棋谱详情同一个形状', async ({ page }) => {
  await bootFigure(page, { col: 0, row: 9, size: 10 });
  await page.getByRole('radio', { name: '全盘' }).click();
  const m = await rulerVsLines(page);

  expect(m.topN).toBe(19);
  expect(m.leftN).toBe(19);
  expect(m.verts).toBe(19);
  expect(Math.abs(m.firstVert - m.firstTop)).toBeLessThanOrEqual(1.5);
  expect(Math.abs(m.lastVert - m.lastTop)).toBeLessThanOrEqual(1.5);
  expect(Math.abs(m.firstHoriz - m.firstLeft)).toBeLessThanOrEqual(1.5);
  expect(Math.abs(m.lastHoriz - m.lastLeft)).toBeLessThanOrEqual(1.5);
});

/* ══ 屏 21 研究 —— AI 推荐表装不下时,该滚的是**表自己** ═══════════════════════
 * 这一屏右栏六块:页控条 44 + 分段 48 + 提示行 16(另有 margin-top 7)+ AI 折叠块(grow)
 * + 翻手条 36 + 动作区 52,五个 12 的间隙 ⇒ **折叠块 253,减掉 30 的折叠头,表体 223**。
 * 稿子给的表是 10 行而 223 只露得出表头 + 8 行 —— 参考图 `21-research.png` 就是这样
 * (K3 那行被横切)。**所以「装不下」是设计里就有的,不是意外。**
 *
 * 这一关量的是那个「装不下」有没有出路:`.aitab` 的 `overflow-y:auto` 是**压在**共享
 * `.kiosk-fold__body { overflow: hidden }` 上面的(靠 `go-screens.css` 在
 * `KioskApp.tsx:24` 最后导入),层叠一旦反过来,第 9 行往后就静默不见、手指也够不到。
 * 那种失败在四图上**看不见** —— 被裁掉的内容在截图里根本不存在。
 *
 * 变异实测(2026-08-24)两发,**其中一发推翻了我事先的预测**:
 *
 * ① 拿掉 `.aitab` 的 `overflow-y:auto`(⇒ 共享那条 `overflow:hidden` 说了算):
 *    我预测「表自己溢出」和「真滚轮滚得动」两条会红。**只红了后一条。**
 *    因为 `scrollHeight − clientHeight > 0` 量的是**内容有没有超出**,
 *    而 `overflow:hidden` 的容器内容照样超出 —— 它只是没有出路。
 *    ⇒ **「有溢出」不等于「滚得动」**,能把「静默裁掉」和「能翻到」分开的**只有真滚轮那一条**。
 *    其余六条(516 / 四段 / 四颗 / 五键 / 不顶破 / 贴底 / 表体高)对这个故障**全部免疫**。
 * ② 把夹具从 24 个候选缩到 3 个(装得下):只有「造到会溢出」那条红。
 *    ⇒ 那条不是凑数的,它守的是「下面那条滚动断言不是空转」。
 * ③ 把 `KioskFold` 的 `scrollbar` opt-in 撤掉:只有「没有悬浮滚动条」那条红,
 *    **能不能滚照旧全绿** —— 滚得动和看不看得出能滚是两件独立的事,各要一条。
 *
 * 结论和屏 14 那条一样,而且这回是量出来的:**盒子的矩形对这一类故障免疫。**
 */
test('§11 研究屏:AI 推荐表装不下时,滚的是表自己,动作区照旧贴底', async ({ page }) => {
  // 造到会溢出:给 24 个候选,而表体只露得出 8 行。**装得下的数据量下量出来的数不算数。**
  await page.route('**/api/v1/analysis/quick-analyze', (route) => route.fulfill({
    json: {
      turnInfos: [{
        moveInfos: Array.from({ length: 24 }, (_, i) => ({
          move: `${'ABCDEFGHJKLMNOPQRST'[i % 19]}${i + 1}`,
          visits: 500 - i * 15, winrate: 0.6 - i * 0.01, scoreLead: 3 - i * 0.4,
        })),
        ownership: null,
      }],
    },
  }));
  await boot(page, '/kiosk/research');
  // ⚠️ 等的是**一个真有盒子的格子**,不是 `[data-testid="research-ai-row"]` ——
  // 那层行包装是 `display:contents`(它的四个格子要直接落进 `.aitab` 的网格),
  // 而 `display:contents` 的元素**没有盒子**,Playwright 默认的 `'visible'` 判它不可见,
  // 于是「表画出来了」会被糊成一条 30 秒超时。
  await page.waitForSelector('.aitab .best');

  const m = await page.evaluate(() => {
    const q = (s: string) => document.querySelector(s) as HTMLElement;
    const rail = q('.kiosk-rail');
    const fold = q('.kiosk-fold--grow');
    const tab = q('.aitab');
    const acts = q('[data-testid="research-actions"]');
    const r = rail.getBoundingClientRect();
    return {
      railH: Math.round(r.height),
      railBottom: Math.round(r.bottom),
      railOverflow: rail.scrollHeight - rail.clientHeight,
      foldH: Math.round(fold.getBoundingClientRect().height),
      headH: Math.round(q('.kiosk-fold__head').getBoundingClientRect().height),
      // 折叠块自己那圈 1px 边框也吃高度 —— 关系式里少算它就会差 2。**读出来,不写死。**
      foldBorder: Math.round(
        parseFloat(getComputedStyle(fold).borderTopWidth) + parseFloat(getComputedStyle(fold).borderBottomWidth),
      ),
      tabH: Math.round(tab.getBoundingClientRect().height),
      tabTop: Math.round(tab.getBoundingClientRect().top),
      tabBottom: Math.round(tab.getBoundingClientRect().bottom),
      tabOverflow: tab.scrollHeight - tab.clientHeight,
      actsBottom: Math.round(acts.getBoundingClientRect().bottom),
      actsCount: acts.querySelectorAll('button').length,
      // 分段和翻手条在不在,决定上面那本高度账是不是这一屏真的这本
      segCount: document.querySelectorAll('[data-testid="research-tools"] button').length,
      navCount: document.querySelectorAll('[data-testid="research-movenav"] button').length,
      grows: document.querySelectorAll('.kiosk-fold--grow').length,
      // 悬浮滚动条(规范 §5.2)。`scrollbar-width:none` 必须留着(原生条一占宽度,
      // 460 就不是 460),而零宽度的代价是**屏上一点位置指示都没有** ——
      // 7 寸触摸屏没有 hover,第 9 行往后就成了没人知道存在的东西。
      bar: (() => {
        const b = document.querySelector('.kiosk-scrollbar') as HTMLElement | null;
        if (!b) return null;
        const br = b.getBoundingClientRect();
        return { h: Math.round(br.height), w: Math.round(br.width), top: Math.round(br.top) };
      })(),
    };
  });

  // ── 关系式(先写死,再读数)──
  expect(m.railH, '右栏不是 516 —— 布局 A 的高度账先崩了').toBe(516);
  expect(m.segCount, '分段不是四段').toBe(4);
  expect(m.navCount, '翻手条不是四颗').toBe(4);
  expect(m.actsCount, '动作区不是五个键').toBe(5);
  expect(m.grows, '一栏里只许有一块 grow —— 多一块两块就都拿不到确定高度').toBe(1);

  expect(m.railOverflow, '右栏自己被顶破了 —— 溢出该由 AI 表自己吃掉').toBeLessThanOrEqual(0);
  expect(m.actsBottom, '动作区没贴右栏底').toBe(m.railBottom);
  // 表体 = 折叠块 − 折叠头 − 折叠块自己那圈边框。中间**不许**再有别的东西 ——
  // 多一个 8px 的 margin,表就少露一行(屏 18 的 `.setnote` 正是这么偷走 8px 的)。
  expect(m.tabH, '表体 ≠ 折叠块 − 折叠头 − 边框:中间多出了别的东西,那本高度账就不成立了')
    .toBe(m.foldH - m.headH - m.foldBorder);
  expect(m.tabBottom, '表体的下缘越过了右栏 —— 被裁掉的行在截图上根本不存在')
    .toBeLessThanOrEqual(m.railBottom);
  expect(m.tabTop, '表体的上缘跑到右栏外面去了').toBeGreaterThanOrEqual(Math.round(m.railBottom - m.railH));

  // ── 造出来的溢出是真的吗 ──
  expect(m.tabOverflow, '24 个候选没把表撑到溢出 —— 下面那条滚动断言是空的')
    .toBeGreaterThan(100);

  // 条子要真的画出来,而且**比例得是算过的**:视口/内容 × 视口高,下限 24。
  expect(m.bar, '没有悬浮滚动条 —— 装不下这件事屏上一点指示都没有').not.toBeNull();
  expect(m.bar!.w, '条子宽度是 0 —— 等于没画').toBeGreaterThan(0);
  expect(m.bar!.h, '拇指比视口还长 —— 那说明它根本没按比例算').toBeLessThan(m.tabH);
  expect(m.bar!.h, '拇指短于下限 24,就成了一个点、读不出比例').toBeGreaterThanOrEqual(24);

  // ── 唯一分得出「有没有出路」的那一条:**真滚轮**。
  //    合成事件 Chromium 不认,`scrollTop = n` 只证明这个属性可写。
  const tab = page.locator('.aitab');
  const bb = (await tab.boundingBox())!;
  await page.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
  await page.mouse.wheel(0, 240);
  await expect.poll(() => tab.evaluate((el) => el.scrollTop),
    { message: 'AI 推荐表自己滚不动 —— 第 9 行往后手指够不到' }).toBeGreaterThan(0);

  // 条子得**跟着**滚。不动的条子比没有更糟:它谎报「你在顶上」。
  const barTop = await page.locator('.kiosk-scrollbar').evaluate((el) => el.getBoundingClientRect().top);
  expect(barTop, '滚了之后拇指没往下走 —— 一条不动的位置指示是在说假话')
    .toBeGreaterThan(m.bar!.top);
});

/* ══ 屏 26 标定 —— 头尾钉死,失败时中段自己滚 ═════════════════════════════════
 * 稿子那五块按共享 token 算是 **462 / 460** —— 差 2px 就装不下,而且那本账**只在它画的
 * 那一个状态下**勉强平:失败时要多一张诊断卡,当场顶破。
 *
 * ⇒ 结构改成头(三格 56)尾(按钮 44)固定、中间那块滚。这样账本只依赖四个共享 token
 * (56 / 44 / 两个 8),中段是多少都顶不破。删掉稿子那个不存在的第 2 步又还回 60。
 *
 * 这一关量三件事,**第三件是这里唯一分得出真假的那件**:
 *  ① 五段加起来正好 460(关系式,不是硬编码);
 *  ② 四行步骤各 52 —— `.kiosk-row` 的 `flex:none` 在一个**会滚的**容器里必须还在。
 *     那条注释警告过:不写死的话 flex 会先把行压扁再滚(2026-07-29 量到 18 行被压成 33)。
 *     而这四行现在**真的**住在会滚的容器里,正是它描述的场景。
 *  ③ **失败态**下中段真的滚得动,而按钮**没有被顶出右栏**。
 *
 * 变异实测(2026-08-24)两发,**两条预测都被推翻了**,而且推翻的方式各自都有教训:
 *
 * ① 去掉 `.calib-body` 的 `flex:1`。我预测两条测试全红。
 *    **实际只红了上面那条(常态)** —— 下面那条(失败态)照旧全绿,量出来 rail 仍是 460。
 *    原因:这一格没有 `flex:1` 时按**内容**定高,而失败态的内容(多一张 117 高的诊断卡)
 *    正好把它撑回 460 上下;常态内容少,当场塌下去。
 *    ⇒ **内容多的那个状态把这个缺陷盖住了。** 平时说「造到会溢出才算数」,这里是反过来的
 *    同一件事:**塌陷类的缺陷要在内容最少的状态下量**,内容一多它自己就撑住了。
 *    所以这两条测试**不是一条的两个例子**,常态那条是唯一逮得住塌陷的。
 *
 * ② 去掉 `.calib-rail .setnote{margin-bottom:0}`。我预测常态那条会差 8 变红。
 *    **实际两条全绿。** 原因:`.setnote` 住在**会滚的那个容器里**,那 8px 只是让滚动内容
 *    高 8,不进外层那本账。屏 18 上它是承重的,因为那儿 `.setnote` 是 flex 栏的**直接子节点**。
 *    ⇒ **同一条规则在两种结构里不是同一件事**;从屏 18 转过来的是结论,不是判据。
 *    那行 CSS 留着(省掉 8px 没必要的滚动内容),但**它不承重**,注释已照实改写。
 */
const CALIB_ANCHORS = [[0, 0], [0, 18], [18, 18], [18, 0], [3, 3], [3, 9]].map(([row, col], i) => ({
  row, col, x: 120 + col * 17, y: 110 + row * 15 + i, color: 'green',
}));

const bootCalib = async (page: Page, over: Record<string, unknown>) => {
  await page.route('**/api/v1/geometry/layout', (route) => route.fulfill({ status: 409, json: {} }));
  // ⚠️ **顺序是承重的**:`boot()` 自己也注册 `**/api/v1/geometry/status`(钉成
  // 「这台盒子没有摄像头」),而 Playwright 的路由是**后注册的先匹配**。
  // 先注册这条就会被 boot 那条盖掉 ⇒ 拿到 `disabled`、整屏换成一句「没配摄像头」、
  // 一行步骤都没有。必须 boot 之后再注册,然后重新加载。
  await boot(page, '/kiosk/vision/setup');
  await page.route('**/api/v1/geometry/status', (route) => route.fulfill({
    json: {
      phase: 'required', session_calibrated: false, last_valid: false, error: null,
      detected_anchors: CALIB_ANCHORS,
      capabilities: { camera_ready: true, led_ready: true, geometry_ready: false, recognition_ready: false },
      ...over,
    },
  }));
  await page.reload();
  await page.waitForSelector('[data-testid="calib-step"]');
};

const calibBoxes = (page: Page) => page.evaluate(() => {
  const q = (s: string) => document.querySelector(s) as HTMLElement;
  const r = (s: string) => { const e = q(s); const b = e.getBoundingClientRect();
    return { top: Math.round(b.top), bottom: Math.round(b.bottom), h: Math.round(b.height) }; };
  const scroll = q('.calib-scroll .kiosk-side__scroll');
  return {
    rail: r('.calib-rail'), status: r('.kiosk-status'), zone: r('.calib-scroll'), acts: r('.calib-acts'),
    body: r('.calib-body'), cam: r('.camview'),
    rows: Array.from(document.querySelectorAll('[data-testid="calib-step"]'))
      .map((e) => Math.round(e.getBoundingClientRect().height)),
    overflow: scroll.scrollHeight - scroll.clientHeight,
  };
});

test('§11 标定屏:头尾钉死、四行不被压扁,右栏总高正好 460', async ({ page }) => {
  await bootCalib(page, {});
  const m = await calibBoxes(page);

  // ── 关系式:五段拼满,一个像素不多不少 ──
  expect(m.rail.h, '右栏不是 460 —— 布局 B 内容区 516 减去页控条 44 和那 12 的间隙').toBe(460);
  expect(m.body.h, '左右两格不等高').toBe(m.rail.h);
  expect(m.cam.h, '摄像头画面没有跟右栏一样高').toBe(m.rail.h);
  expect(m.status.bottom + 8, '三格与中段之间不是 8').toBe(m.zone.top);
  expect(m.zone.bottom + 8, '中段与按钮行之间不是 8').toBe(m.acts.top);
  expect(m.acts.bottom, '按钮行没贴右栏底 —— 它是固定尾,不靠 margin-top:auto').toBe(m.rail.bottom);
  expect(m.status.h + m.zone.h + m.acts.h + 16, '五段加起来 ≠ 右栏高度').toBe(m.rail.h);

  // ── 四行不许被压扁 ──
  expect(m.rows, '步骤行被压扁了 —— `.kiosk-row` 的 flex:none 掉了').toEqual([52, 52, 52, 52]);
  // 常态装得下 ⇒ **不许**有 data-at(挂一条永远亮着的渐隐等于谎报下面还有东西)
  expect(m.overflow, '常态就溢出了 —— 那本账已经不对了').toBeLessThanOrEqual(0);
});

test('§11 标定屏:失败时多一张诊断卡,中段自己滚,按钮一颗都不许被顶出去', async ({ page }) => {
  // 造到会溢出:失败态比常态多一整张诊断卡。**装得下的状态下量出来的数不作数。**
  await bootCalib(page, { phase: 'failed', error: 'anchor_not_found:3,15', last_valid: true });
  await page.waitForSelector('[data-testid="geometry-diagnostic-card"]');
  const m = await calibBoxes(page);

  expect(m.rail.h, '右栏高度被诊断卡顶变了').toBe(460);
  expect(m.acts.bottom, '按钮被顶出右栏了 —— 键还在 DOM 里,但手指够不到').toBe(m.rail.bottom);
  expect(m.rows, '失败态下步骤行被压扁了').toEqual([52, 52, 52, 52]);
  expect(m.overflow, '诊断卡没把中段撑到溢出 —— 下面那条滚动断言是空的').toBeGreaterThan(0);

  // 唯一分得出「有没有出路」的那一条:**真滚轮**。合成事件 Chromium 不认,
  // 而 `scrollTop = n` 只证明这个属性可写。
  const zone = page.locator('.calib-scroll .kiosk-side__scroll');
  const bb = (await zone.boundingBox())!;
  await page.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
  await page.mouse.wheel(0, 200);
  await expect.poll(() => zone.evaluate((el) => el.scrollTop),
    { message: '中段自己滚不动 —— 诊断卡下面那几步就看不到了' }).toBeGreaterThan(0);
});
