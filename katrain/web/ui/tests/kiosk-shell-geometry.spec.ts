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
test('§5 屏 19:渐隐从组标题下缘开始,展开搜索之后跟着往下挪', async ({ page }) => {
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

  await page.click('button[aria-label="搜历史对局"]');
  await page.waitForSelector('[data-testid="review-search"]');
  const open = await page.evaluate(() => {
    const sec = document.querySelector('.kiosk-section--grow') as HTMLElement;
    const scroll = document.querySelector('.kiosk-section--grow .kiosk-side__scroll') as HTMLElement;
    return {
      fade: parseFloat(getComputedStyle(sec, '::before').top),
      headH: Math.round(scroll.getBoundingClientRect().top - sec.getBoundingClientRect().top),
    };
  });
  expect(open.headH, '展开搜索没把头撑高 54(44 的框 + 10 的空)').toBe(closed.headH + 54);
  expect(open.fade, '展开搜索之后渐隐没跟着挪 —— 它压在搜索框上').toBe(open.headH);
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

/** 逐手分析:每四手来一次大跌,保证「重点手」列得满三行。 */
const reportMoveRows = () => Array.from({ length: 41 }, (_, n) => ({
  id: n, task_id: 7, move_number: n, status: 'success',
  winrate: 0.5 - n * 0.008, score_lead: -n * 0.4, visits: 500,
  top_moves: n % 2 === 0
    ? [{ move: 'R11', visits: 400, winrate: 0.6, score_lead: 2, prior: 0.6, pv: ['R11'], psv: 1 }]
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
 * 右栏纵向账:页控条 + 题头 + 曲线 + **重点手(吃掉剩下的)** + 四个开关 + 四个翻手键 = 516。
 * 翻手键是这一屏的肌肉记忆位置,**任何一块长高都不许把它顶出画布**。
 */
test('§11 复盘报告:重点手再多,翻手键也贴着右栏底,列表自己滚', async ({ page }) => {
  await bootReportDetail(page);

  const m = await page.evaluate(() => {
    const rail = document.querySelector('.kiosk-rail') as HTMLElement;
    const nav = document.querySelector('[data-testid="report-detail-movenav"]') as HTMLElement;
    const toggles = document.querySelector('[data-testid="report-detail-toggles"]') as HTMLElement;
    const rows = document.querySelector('.kiosk-fold__body.foldrows') as HTMLElement;
    const screenEl = document.querySelector('.kiosk-screen') as HTMLElement;
    const r = rail.getBoundingClientRect();
    return {
      railH: Math.round(r.height),
      railBottom: Math.round(r.bottom),
      navBottom: Math.round(nav.getBoundingClientRect().bottom),
      navCount: nav.querySelectorAll('button').length,
      toggleCount: toggles.querySelectorAll('button').length,
      keyRows: document.querySelectorAll('[data-testid="report-detail-key-row"]').length,
      railOverflow: rail.scrollHeight - rail.clientHeight,
      rowsOverflow: rows.scrollHeight - rows.clientHeight,
      screenBottom: Math.round(screenEl.getBoundingClientRect().bottom),
      plot: document.querySelector('[data-testid="review-winrate-plot"]')!.getAttribute('data-state'),
    };
  });

  expect(m.railH, '右栏不是 516 —— 布局 A 的高度账先崩了').toBe(516);
  expect(m.navCount, '翻手键不是四个').toBe(4);
  expect(m.toggleCount, '显示开关不是四个(形势 / 手数 / AI 推荐 / 试下)').toBe(4);
  expect(m.keyRows, '造的数据没让重点手列出三行 —— 下面的断言是空的').toBe(3);
  expect(m.plot, '曲线没画出来 —— 这一屏的胜率是真数据,画不出来就不该判几何').toBe('plotted');
  expect(m.railOverflow, '右栏自己被顶破了 —— 溢出该由重点手那一块吃掉').toBeLessThanOrEqual(0);
  expect(m.navBottom, '翻手键没贴右栏底').toBe(m.railBottom);
  expect(m.navBottom, '翻手键被顶到画布外面了').toBeLessThanOrEqual(m.screenBottom);
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
