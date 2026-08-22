import { expect, test, type Page } from '@playwright/test';

/**
 * 规范 §5.2 悬浮滚动区的**承重闸**。四条硬性,一条都不能靠 jsdom ——
 * jsdom 没有布局引擎,`scrollHeight` 恒等于 `clientHeight`,它对「溢没溢出」无权作证。
 *
 *   ① 不溢出就**没有** data-at、**不画**滚动条(挂一条永远亮着的渐隐 = 谎报下面还有东西)
 *   ② 溢出了就**必须有** data-at,拇指最短 24,且**绝对定位不占布局宽度**(占了 680 就不是 680)
 *   ③ 真的能滚 —— 用**真滚轮**。Chromium 不认未受信任的合成 WheelEvent,
 *      而 `scrollTop = n` 只证明「代码能写这个属性」,证明不了「用户能滚」
 *
 * 「内容多少」是**输入**,可以造;「data-at 是什么、拇指多高、栏还是不是 680」是**结论**,
 * 一律由真浏览器算。每条造完输入先断言前置状态真的成立 —— 造不出来就当场红,
 * 不许静默变成一条「从我这层往里通」的到达性测试。
 *
 * ⚠️ §5「露一半」那条**不在这里**:它量的是内容落点,而 `/kiosk/play` 的内容 Task 10 才定稿,
 * 现在测它只能靠调即将作废的内容变绿。已登记到 Task 10。
 */

const CANVAS = { width: 1024, height: 600 };
test.use({ viewport: CANVAS });

/**
 * 造输入的样式**必须在挂载之前**就位。事后 `addStyleTag` 是错的:组件只在 children 变化时
 * 重算(`ResizeObserver` 盯的是滚动容器自己的盒子,而它恒是 height:100%,内容长高时一动不动
 * —— 三家活样本一致),事后改样式没有任何信号能通知它,量到的会是上一帧的结论。
 * 这条本身就是 G11 第 10 条描述的那个机制,不是测试脚手架的将就。
 */
const boot = async (page: Page, path: string, css?: string) => {
  await page.addInitScript((injected) => {
    localStorage.setItem('token', 'kiosk-shell-scroll');
    localStorage.setItem('katrain_language', 'cn');
    if (!injected) return;
    const style = document.createElement('style');
    style.textContent = injected;
    const put = () => (document.head ?? document.documentElement).appendChild(style);
    if (document.head ?? document.documentElement) put();
    else document.addEventListener('readystatechange', put, { once: true });
  }, css ?? '');
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: 'tester', rank: '5段', credits: 0 },
  }));
  await page.goto(path);
  await page.waitForSelector('.kiosk-screen', { state: 'attached' });
  // 跨平台三张卡是 `/api/v1/platform/status` 回来之后才渲的 —— 不等它,量到的是没长齐的内容。
  await page.waitForSelector('.kiosk-scrollzone', { state: 'attached' });
};

/** 撑到明显溢出:在滚动内容末尾追加一块空白。不碰任何现有元素的几何。 */
const STUFF = '.kiosk-side__scroll::after { content:""; display:block; flex:none; height:300px; }';

/**
 * 内容极长。拇指下限 24 只在这种量级下才**看得出来**:STUFF(300) 那种量级算出来是 242,
 * 拿掉下限一样过关 —— 那条断言在那儿是睡着的。这里 434/20434*434 ≈ 9.2,下限才开始承重。
 */
const STUFF_HUGE = '.kiosk-side__scroll::after { content:""; display:block; flex:none; height:20000px; }';

/** 造到装得下:把靠后的几段藏掉。藏的是**输入**,量的还是浏览器算出来的结论。 */
// Task 10 之后各块是 `.kiosk-side__scroll` 的**直接**子元素(之前隔着一层 Box),
// 选择器跟着少一层。造不出「装得下」时下面那条前置断言会当场红,不会静默变绿。
const SHRINK = '.kiosk-side__scroll > :nth-child(n+4) { display:none !important; }';

/** 直接量 DOM,不用 locator.evaluate —— 后者要先等「可见」,而本文件防的故障恰好让元素不可见。 */
const overflowOf = (page: Page) => page.evaluate(() => {
  const el = document.querySelector('.kiosk-side__scroll') as HTMLElement | null;
  if (!el) throw new Error('没有 .kiosk-side__scroll');
  return el.scrollHeight - el.clientHeight;
});

test('不溢出时:没有 data-at,也不画滚动条', async ({ page }) => {
  await boot(page, '/kiosk/play', SHRINK);
  // 造出来的前置状态必须成立,否则这条闸没有被测对象。
  await expect.poll(() => overflowOf(page), { message: '没造出「装得下」的状态' })
    .toBeLessThan(1);

  const state = await page.evaluate(() => {
    const zone = document.querySelector('.kiosk-scrollzone') as HTMLElement;
    const bar = zone.querySelector('.kiosk-scrollbar') as HTMLElement;
    return { at: zone.getAttribute('data-at'), barDisplay: getComputedStyle(bar).display };
  });
  expect(state.at, '装得下却写了 data-at —— 渐隐会永远亮着,谎报下面还有东西').toBeNull();
  expect(state.barDisplay, '装得下却画了滚动条').toBe('none');
});

test('溢出时:data-at 从 top 走到 end,拇指 >=24 且不占布局宽度', async ({ page }) => {
  await boot(page, '/kiosk/play', STUFF);
  await expect.poll(() => overflowOf(page), { message: '没造出「装不下」的状态' })
    .toBeGreaterThan(200);

  const zone = page.locator('.kiosk-scrollzone').first();
  await expect(zone).toHaveAttribute('data-at', 'top');

  const geom = await page.evaluate(() => {
    const z = document.querySelector('.kiosk-scrollzone') as HTMLElement;
    const bar = z.querySelector('.kiosk-scrollbar') as HTMLElement;
    const b = bar.getBoundingClientRect();
    return {
      thumbH: b.height, thumbW: b.width,
      pos: getComputedStyle(bar).position,
      zoneW: Math.round(z.getBoundingClientRect().width),
    };
  });
  expect(geom.thumbH, '拇指短于 24 就成了一个点,读不出比例').toBeGreaterThanOrEqual(24);
  expect(geom.pos).toBe('absolute');
  expect(geom.zoneW, '滚动条占了布局宽度 —— 三列 220 的算术会当场崩').toBe(680);

  // **真滚轮**。合成 WheelEvent 不受信任,`scrollTop = n` 证明不了用户能滚。
  await page.mouse.move(700, 300);
  await page.mouse.wheel(0, 200);
  await expect.poll(() => page.evaluate(
    () => (document.querySelector('.kiosk-side__scroll') as HTMLElement).scrollTop)).toBeGreaterThan(0);
  await expect(zone).toHaveAttribute('data-at', 'mid');

  await page.mouse.wheel(0, 5000);
  await expect.poll(() => zone.getAttribute('data-at')).toBe('end');
});

test('内容极长时:拇指仍然有 24 —— 再短就成了一个点,读不出比例', async ({ page }) => {
  await boot(page, '/kiosk/play', STUFF_HUGE);
  const m = await page.evaluate(() => {
    const sc = document.querySelector('.kiosk-side__scroll') as HTMLElement;
    const bar = document.querySelector('.kiosk-scrollbar') as HTMLElement;
    return {
      overflow: sc.scrollHeight - sc.clientHeight,
      // 没有下限的话拇指会是这个数 —— 记录下来,让「下限在这条里是醒着的」有据可查
      unclamped: (sc.clientHeight / sc.scrollHeight) * sc.clientHeight,
      thumbH: bar.getBoundingClientRect().height,
    };
  });
  expect(m.overflow, '没造出「内容极长」的状态').toBeGreaterThan(15000);
  expect(m.unclamped, '这一批输入下不带下限也能过 24 —— 这条闸是睡着的').toBeLessThan(24);
  expect(m.thumbH).toBeGreaterThanOrEqual(24);
});

/* ══ 屏 11 训练营(Task 12)══════════════════════════════════════════════════
 *
 * 这一屏和 `/kiosk/play` 不同:**内容长短由接口说了算**(题库有几档、这一档有几类),
 * 所以造输入不用注 CSS —— 直接把 `/api/v1/tsumego/levels` 造成想要的形状,
 * 量到的是页面拿真数据算出来的结论。
 */

const LEVELS = (n: number, nCat = 6) => Array.from({ length: n }, (_, i) => ({
  level: `${15 - i}k`,
  categories: Object.fromEntries(
    ['life-death', 'tesuji', 'semeai', 'capturing', 'endgame', 'opening'].slice(0, nCat).map((c, j) => [c, 50 + j]),
  ),
  total: 300 + i,
}));

const bootTraining = async (page: Page, levels: ReturnType<typeof LEVELS>, resume: boolean) => {
  await page.addInitScript((withResume) => {
    localStorage.setItem('token', 'kiosk-shell-scroll');
    localStorage.setItem('katrain_language', 'cn');
    localStorage.setItem('kiosk_tsumego_last_level', '15k');
    if (withResume) {
      localStorage.setItem('kiosk_active_practice', JSON.stringify({
        kind: 'practice', label: '15 级 · 吃子 · 第 1 题', route: '/kiosk/tsumego/problem/x', ts: 1,
      }));
    }
  }, resume);
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') {
      return route.fulfill({ json: { id: 1, username: 'tester', rank: '5段', credits: 0 } });
    }
    if (path === '/api/v1/tsumego/levels') return route.fulfill({ json: levels });
    return route.fulfill({ json: {} });
  });
  await page.goto('/kiosk/tsumego');
  // 卡是接口回来之后才渲的 —— 等 `.kiosk-screen` 不够,量到的会是还没长齐的内容。
  // 空态那一支一张卡都没有,所以两个落点都等:等不到才是真的没渲完。
  await page.waitForSelector('.kiosk-cards .kiosk-card, .empty');
};

test('训练营:档数多到装不下时,右栏自己滚 —— data-at 走 top→mid→end,拇指 >=24,栏恒 680', async ({ page }) => {
  await bootTraining(page, LEVELS(12), true);
  await expect.poll(() => overflowOf(page), { message: '12 档还没造出「装不下」' }).toBeGreaterThan(200);

  const zone = page.locator('.kiosk-scrollzone').first();
  await expect(zone).toHaveAttribute('data-at', 'top');

  const geom = await page.evaluate(() => {
    const z = document.querySelector('.kiosk-scrollzone') as HTMLElement;
    const bar = z.querySelector('.kiosk-scrollbar') as HTMLElement;
    return {
      thumbH: bar.getBoundingClientRect().height,
      pos: getComputedStyle(bar).position,
      zoneW: Math.round(z.getBoundingClientRect().width),
    };
  });
  expect(geom.thumbH, '拇指短于 24 就成了一个点,读不出比例').toBeGreaterThanOrEqual(24);
  expect(geom.pos).toBe('absolute');
  expect(geom.zoneW, '滚动条占了布局宽度 —— 三列 220 的算术会当场崩').toBe(680);

  await page.mouse.move(700, 300);
  await page.mouse.wheel(0, 150);
  await expect(zone).toHaveAttribute('data-at', 'mid');
  await page.mouse.wheel(0, 5000);
  await expect.poll(() => zone.getAttribute('data-at')).toBe('end');
});

test('训练营:一档也读不到时不许挂渐隐 —— 空态那一块装得下', async ({ page }) => {
  await bootTraining(page, LEVELS(0), false);
  await page.waitForSelector('[data-testid="tsumego-empty"]');
  await expect.poll(() => overflowOf(page), { message: '空态反而溢出了?' }).toBeLessThan(1);
  const state = await page.evaluate(() => {
    const zone = document.querySelector('.kiosk-scrollzone') as HTMLElement;
    const bar = zone.querySelector('.kiosk-scrollbar') as HTMLElement;
    return { at: zone.getAttribute('data-at'), barDisplay: getComputedStyle(bar).display };
  });
  expect(state.at, '装得下却写了 data-at —— 渐隐会永远亮着,谎报下面还有东西').toBeNull();
  expect(state.barDisplay, '装得下却画了滚动条').toBe('none');
});

/**
 * ── §5「露一半」这里**没有闸**,是 2026-08-22 规范 v1.33 裁的,不是漏了 ─────────────
 *
 * 那条规矩(内容溢出时视口底边要切在一张卡中间,76 的卡是 [19, 57])从**硬性降成建议**,
 * 共享闸只打一条 `INFO` 行。三条理由,第三条是证据:
 *
 *   ① **切口位置不是设计能选的。** 它 = (问候行 56 + 继续条 60 + 组标题 20 + 间距 8/6
 *      + 卡 76 或行 52 …) 对卡距取模,而这些高度全是共享外壳钉死的节奏 ——
 *      想把落点挪进窗口只能去改壳的行高,那会同时波及四家。
 *   ② **这一层挑哪个 fixture 就等于挑结论。** 训练营实测两个真数据态:
 *        · 有「接着上次」→ 卡行 424..500,底边 504 落在两行之间那条 10px 的缝里(离上一张 4);
 *        · 没有        → 卡行 442..518,露 62 / 卡高 76。
 *      拿其中一个立闸 = 用输入决定判据,那不是闸。
 *   ③ **它原来的「全过」是散文撑的。** 把围棋稿剩下的 26 段旁注(按 G5 本来就不上线)
 *      收进 HTML 注释之后,稿子自己那道闸**六屏当场变红**
 *      (在线大厅 / 跨平台连接 / 训练营 / 棋谱 / 复盘 / 课程)。
 *      也就是说这条闸此前量的是「这一屏的解释文字有多长」。
 *
 * ⇒ 「下面还有」在这一层靠的是上面那三条:悬浮滚动条画不画、`data-at` 诚不诚实、拇指够不够高。
 *   **这三条在每个数据态下都成立**,与内容长短无关。不要把「露一半」加回来。
 */

/* ══ 屏 12 单元列表(Task 13)—— 布局 B,滚动区是**通栏 992** ═══════════════════
 * 和上面那几条不是重复:那些量的是 L1 右栏 680,这一条量的是无盘页的 992。
 * 「滚动条不占布局宽度」这条判据**带着宽度**,680 上成立不代表 992 上成立
 *  —— 原生滚动条一冒出来,992 就不是 992。
 */
test('单元列表(布局 B):单元多到装不下时,通栏 992 一分不少,滚动条仍然不占宽', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'kiosk-shell-scroll');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: 'tester', rank: '5段', credits: 0 },
  }));
  // 240 道题 = 12 个单元(四行),一定装不下 460。
  await page.route('**/api/v1/tsumego/levels/*/categories/*', (route) => route.fulfill({
    json: Array.from({ length: 240 }, (_, i) => ({ id: `q${i}` })),
  }));
  await page.goto('/kiosk/tsumego/15k/capturing');
  await page.waitForSelector('.kiosk-cards .kiosk-card');

  await expect.poll(() => overflowOf(page), { message: '12 个单元还没造出「装不下」' }).toBeGreaterThan(100);

  const zone = page.locator('.kiosk-scrollzone').first();
  await expect(zone).toHaveAttribute('data-at', 'top');
  const geom = await page.evaluate(() => {
    const z = document.querySelector('.kiosk-scrollzone') as HTMLElement;
    const sc = z.querySelector('.kiosk-side__scroll') as HTMLElement;
    const bar = z.querySelector('.kiosk-scrollbar') as HTMLElement;
    return {
      zoneW: Math.round(z.getBoundingClientRect().width),
      clientW: sc.clientWidth,
      thumbH: bar.getBoundingClientRect().height,
      pos: getComputedStyle(bar).position,
    };
  });
  expect(geom.zoneW, '通栏不是 992').toBe(992);
  expect(geom.clientW, '滚动条占了布局宽度 —— 992 就不是 992 了').toBe(992);
  expect(geom.thumbH, '拇指短于 24 就成了一个点,读不出比例').toBeGreaterThanOrEqual(24);
  expect(geom.pos).toBe('absolute');

  await page.mouse.move(500, 300);
  await page.mouse.wheel(0, 120);
  await expect(zone).toHaveAttribute('data-at', 'mid');
  await page.mouse.wheel(0, 5000);
  await expect.poll(() => zone.getAttribute('data-at')).toBe('end');
});

/* ══ 屏 13 题目列表(Task 13b)—— 20 格题号必须**一屏装得下** ═════════════════
 * 这一条不是「能不能滚」的重复,恰恰相反:**它断言这一屏不需要滚**。
 *
 * 为什么这是承重不是审美:`.qgrid` 的格高 76 是稿子 2026-08-21 从 58 调上来的,
 * 理由是「把散文清出设备之后底下露出一条 60px 空带」——**那次是拿空带换的格高**。
 * 再有人往上加(或者数据条 / 组标题变高),20 格就会把「换一批」那两行顶到视野之外,
 * 而那两行是这一屏**唯一**的两个出口(整级、错题)。滚动条会照常出现、`data-at` 照常诚实,
 * 三条通用闸**全绿**,人却看不见出口 —— 所以这件事只有在这里说得出来。
 *
 * 判据写成关系式:满编 20 格时滚动区**不溢出**,且最后那一行的下缘在视口内。
 * 具体空了多少 px 只记录、不作判据(稿子那 24 是它自己那份 HTML 的数;这边实测 48)。
 *
 * 变异实测(2026-08-22):把 `.qgrid button` 的 76 改成 110,这条当场红在
 * 「满编 20 格已经装不下了」。红分支跑过。
 */
test('题目列表:满编 20 格 + 换一批两行,一屏装得下 —— 出口不许被顶到视野之外', async ({ page }) => {
  await page.route('**/api/v1/tsumego/levels/*/categories/*', (route) => route.fulfill({
    json: Array.from({ length: 45 }, (_, i) => ({ id: `q${i}` })),
  }));
  await boot(page, '/kiosk/tsumego/15k/capturing/1');
  await page.waitForSelector('.qgrid button:nth-child(20)');

  const m = await page.evaluate(() => {
    const sc = document.querySelector('.kiosk-side__scroll') as HTMLElement;
    const cells = Array.from(document.querySelectorAll('.qgrid button')) as HTMLElement[];
    const rows = document.querySelectorAll('.kiosk-rows .kiosk-row');
    const last = rows[rows.length - 1] as HTMLElement;
    return {
      cells: cells.length,
      overflow: sc.scrollHeight - sc.clientHeight,
      lastRowBottom: Math.round(last.getBoundingClientRect().bottom),
      zoneBottom: Math.round(sc.getBoundingClientRect().bottom),
      exits: rows.length,
    };
  });

  expect(m.cells, '没造出满编的一个单元 —— 下面量的就不是「最挤的那一屏」').toBe(20);
  expect(m.exits, '换一批那两行没渲出来').toBe(2);
  expect(m.overflow, '满编 20 格已经装不下了 —— 「换一批」那两个出口被顶到视野之外').toBeLessThanOrEqual(0);
  expect(m.lastRowBottom, '最后一行的下缘越过了滚动视口').toBeLessThanOrEqual(m.zoneBottom);
  // ⚠️ 别拿 `clientHeight - scrollHeight` 当空带:`scrollHeight` 有 `clientHeight` 这个下界,
  // 那个差**永远是 0 或负**,写出来会是一条恒等于 0 的假读数。空带只能从最后一行的下缘量。
  console.log(`[qgrid] 满编 20 格之后底下还空 ${m.zoneBottom - m.lastRowBottom}px(只记录,不作判据)`);
});

/* ══ 屏 13 —— `.qgrid` 横向:10 列铺满通栏 992,一列不多一列不少 ════════════════
 * 横向溢出在截图上**看不出来**(格子会被裁掉一点点,或者整页能左右拖),
 * 而 §1 说画布是死的 1024 —— 页面本体永远不许横向滚。
 * 判据同样是关系式:第一行正好 10 格且四缘对齐通栏,不写死 92。
 *
 * 变异实测(2026-08-22):`repeat(10, 1fr)` 改成 `repeat(8, 1fr)`,这条当场红在
 * 「一行不是 10 格」;格高那条由上一个变异(76 → 110)红过。两条红分支都跑过。
 */
test('题目列表:.qgrid 十列铺满 992,行内不换行、页面不横向溢出', async ({ page }) => {
  await page.route('**/api/v1/tsumego/levels/*/categories/*', (route) => route.fulfill({
    json: Array.from({ length: 45 }, (_, i) => ({ id: `q${i}` })),
  }));
  await boot(page, '/kiosk/tsumego/15k/capturing/1');
  await page.waitForSelector('.qgrid button:nth-child(20)');

  const g = await page.evaluate(() => {
    const grid = document.querySelector('.qgrid') as HTMLElement;
    const sc = document.querySelector('.kiosk-side__scroll') as HTMLElement;
    const cells = (Array.from(grid.children) as HTMLElement[]).map((c) => c.getBoundingClientRect());
    const firstTop = Math.round(cells[0].top);
    return {
      gridW: Math.round(grid.getBoundingClientRect().width),
      clientW: sc.clientWidth,
      perRow: cells.filter((r) => Math.round(r.top) === firstTop).length,
      rowTops: [...new Set(cells.map((r) => Math.round(r.top)))].length,
      cellH: Math.round(cells[0].height),
      left: Math.round(cells[0].left),
      right: Math.round(cells[9].right),
      gridLeft: Math.round(grid.getBoundingClientRect().left),
      gridRight: Math.round(grid.getBoundingClientRect().right),
      docScrollW: document.documentElement.scrollWidth,
      docClientW: document.documentElement.clientWidth,
    };
  });

  expect(g.gridW, '题号格没铺满通栏 992').toBe(992);
  expect(g.gridW, '滚动条占了布局宽度').toBe(g.clientW);
  expect(g.perRow, '一行不是 10 格 —— 20 道题就不是整齐的两行').toBe(10);
  expect(g.rowTops, '20 格没排成两行').toBe(2);
  expect(g.cellH, '格高不是 76(稿子 2026-08-21 从 58 调上来的那个数)').toBe(76);
  expect(g.left, '第一格没贴左缘').toBe(g.gridLeft);
  expect(g.right, '第十格没贴右缘 —— 要么少算了缝,要么被裁掉了一点').toBe(g.gridRight);
  expect(g.docScrollW, '页面本体横向溢出了 —— 固定画布上这条永远不许发生').toBe(g.docClientW);
});
