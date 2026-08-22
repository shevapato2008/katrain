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
