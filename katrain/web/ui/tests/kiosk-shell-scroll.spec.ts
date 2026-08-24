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
  const m = await page.evaluate((lastId) => {
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

  const m = await page.evaluate((lastId) => {
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

/* ══ 屏 15 棋谱:五块全长满时,右栏得滚得到最后一块 ═════════════════════════
 * 这一屏是 L1 里**最长的一条右栏**:问候 + 继续摆谱 + 名局棋谱(三张卡 + 搜索框 +
 * 六行结果 + 翻页)+ 最近摆过六行 + 职业直播四行。展开搜索是**唯一**会让它长一截的
 * 交互,所以造输入就造这一版 —— 收起态量出来的数字不算数。
 *
 * 判据不是「有没有滚动条」(那条别处已经守了),是**最后一块滚得到**:
 * 直播那几行如果永远落在视野外,等于 Task 4 把直播下 Dock 之后它就再也到不了了。
 */
const KIFU_ROWS = Array.from({ length: 6 }, (_, i) => ({
  id: i + 1, player_black: '柯洁', player_white: '申真谞',
  black_rank: '九段', white_rank: '九段',
  event: '第 29 届三星杯', result: 'B+R', move_count: 241,
  date_played: '2026-06-30', board_size: 19, handicap: 0,
  komi: 7.5, rules: 'chinese', round_name: '半决赛',
}));

const LIVE_ROWS = Array.from({ length: 4 }, (_, i) => ({
  id: `m${i}`, source: 'xingzhen', tournament: `第 ${29 - i} 届三星杯`, round_name: '八强',
  date: '2026-08-22T06:00:00Z', player_black: '柯洁', player_white: '申真谞',
  black_rank: '九段', white_rank: '九段', status: 'live', result: null, move_count: 118,
  current_winrate: .5, current_score: 0, last_updated: '', board_size: 19, komi: 7.5, rules: 'chinese',
}));

test('棋谱:展开搜索之后右栏自己滚,最后一块(职业直播)滚得到', async ({ page }) => {
  await page.addInitScript(() => {
    const now = Date.now();
    localStorage.setItem('baipu:recent', JSON.stringify(
      Array.from({ length: 6 }, (_, i) => ({ id: `kifu_${i}`, name: `名局 ${i}`, savedAt: now - i * 3600e3 })),
    ));
    for (let i = 0; i < 6; i += 1) {
      localStorage.setItem(`baipu:progress:kifu_${i}`, JSON.stringify({ k: 47, frames: 0, updatedAt: now, total: 241 }));
    }
  });
  await page.route('**/api/v1/kifu/albums*', (route) => route.fulfill({
    json: { items: KIFU_ROWS, total: 1234, page: 1, page_size: 6 },
  }));
  await page.route('**/live/matches*', (route) => route.fulfill({
    json: { matches: LIVE_ROWS, live_count: 4, total: 4 },
  }));
  await boot(page, '/kiosk/kifu');
  await page.waitForSelector('[data-testid="kifu-live"]');

  const railW = await page.evaluate(() =>
    Math.round(document.querySelector('.kiosk-side')!.getBoundingClientRect().width));
  expect(railW, '右栏不是 680 —— 后面量的滚动都建在错的宽度上').toBe(680);

  // 展开搜索:这是唯一会让这条栏长一截的交互。
  await page.getByRole('button', { name: /搜棋谱/ }).click();
  await page.waitForSelector('[data-testid="kifu-search"] .kiosk-row');

  const before = await overflowOf(page);
  expect(before, '没造出溢出 —— 下面那条断言是空的').toBeGreaterThan(100);

  // 滚到底,直播那一块的下缘必须进得了视野。**用真滚轮**,不是 scrollTop = n。
  const zone = page.locator('.kiosk-side__scroll');
  const zb = (await zone.boundingBox())!;
  await page.mouse.move(zb.x + zb.width / 2, zb.y + zb.height / 2);
  for (let i = 0; i < 12; i += 1) await page.mouse.wheel(0, 400);

  const m = await page.evaluate(() => {
    const el = document.querySelector('.kiosk-side__scroll') as HTMLElement;
    const live = document.querySelector('[data-testid="kifu-live"]') as HTMLElement;
    return {
      atEnd: el.scrollHeight - el.clientHeight - el.scrollTop,
      liveBottom: Math.round(live.getBoundingClientRect().bottom),
      zoneBottom: Math.round(el.getBoundingClientRect().bottom),
      horizontal: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });
  expect(m.atEnd, '滚不到底').toBeLessThanOrEqual(1);
  expect(m.liveBottom, '滚到底了,直播那一块的下缘还在视野外 —— 它就是到不了的').toBeLessThanOrEqual(m.zoneBottom);
  expect(m.horizontal, '页面横向溢出了').toBe(0);
});

/**
 * 屏 23 课程(L1-A,形态 1 整栏滚)。分类多到装不下时,**最后一块(一课长什么样)滚得到** ——
 * 这一屏三块加起来比 434 高,滚不动就等于那一块不存在。
 *
 * 造到会溢出:8 个分类 = 3 行卡。装得下的数据量下量出来的数字一概不算。
 */
test('课程:分类多到装不下时右栏自己滚,最后一块(一课长什么样)滚得到', async ({ page }) => {
  await page.route('**/api/v1/tutorials/categories', (route) => route.fulfill({
    json: Array.from({ length: 8 }, (_, i) => ({
      slug: `c${i}`, title: `分类 ${i + 1}`, summary: '接口给的说明', order: i + 1, book_count: i + 1,
    })),
  }));
  await boot(page, '/kiosk/tutorial');
  await page.waitForSelector('[data-testid="tutorial-categories"] .kiosk-card');

  const before = await page.evaluate(() => {
    const side = document.querySelector('.kiosk-side') as HTMLElement;
    const scroll = document.querySelector('.kiosk-side__scroll') as HTMLElement;
    return {
      sideW: Math.round(side.getBoundingClientRect().width),
      overflow: scroll.scrollHeight - scroll.clientHeight,
      at: side.getAttribute('data-at'),
    };
  });
  expect(before.sideW, '右栏不是 680').toBe(680);
  expect(before.overflow, '没造出「装不下」—— 下面那条断言是空的').toBeGreaterThan(80);
  expect(before.at, '一开始就该报 top').toBe('top');

  const scroll = page.locator('.kiosk-side__scroll');
  const bb = (await scroll.boundingBox())!;
  await page.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
  await page.mouse.wheel(0, 1200);
  await expect.poll(() => scroll.evaluate((el) => el.scrollTop),
    { message: '右栏滚不动 —— 最后一块到不了' }).toBeGreaterThan(0);

  const after = await page.evaluate(() => {
    const scrollEl = document.querySelector('.kiosk-side__scroll') as HTMLElement;
    const last = document.querySelector('[data-testid="tutorial-anatomy"]') as HTMLElement;
    const sb = scrollEl.getBoundingClientRect();
    const lb = last.getBoundingClientRect();
    return {
      at: document.querySelector('.kiosk-side')!.getAttribute('data-at'),
      lastVisible: lb.top < sb.bottom && lb.bottom > sb.top,
      thumb: Math.round((document.querySelector('.kiosk-scrollbar') as HTMLElement).getBoundingClientRect().height),
    };
  });
  expect(after.at, '滚过之后还报 top —— 渐隐说的是假话').not.toBe('top');
  expect(after.lastVisible, '滚到底也看不见「一课长什么样」').toBe(true);
  expect(after.thumb, '悬浮条拇指短于 24').toBeGreaterThanOrEqual(24);
});

/**
 * 屏 27 设置(L1-B,形态 1 整栏滚)。
 *
 * **高亮跟着真正在看的那一组走** —— 写死在某一项上而右边滚到了别处,**是在谎报你在哪儿**。
 * 所以这条不量「点了导航之后高亮对不对」(那是同一次点击自己设的),
 * 而是**用滚轮把右栏滚下去**,再看导航跟没跟上。
 */
test('设置:滚到第三组时,导航第三项高亮,其余都不是', async ({ page }) => {
  await boot(page, '/kiosk/settings');
  await page.waitForSelector('[data-testid="settings-nav"] button');

  const shape = await page.evaluate(() => {
    const rail = document.querySelector('.kiosk-console') as HTMLElement;
    const side = document.querySelector('.kiosk-side') as HTMLElement;
    const scroll = document.querySelector('.kiosk-side__scroll') as HTMLElement;
    return {
      railW: Math.round(rail.getBoundingClientRect().width),
      sideW: Math.round(side.getBoundingClientRect().width),
      navCount: document.querySelectorAll('[data-testid="settings-nav"] button').length,
      groupCount: document.querySelectorAll('[data-group]').length,
      overflow: scroll.scrollHeight - scroll.clientHeight,
      at: side.getAttribute('data-at'),
    };
  });
  // 规范 §12:左栏宽度和 L1-A 的镜像栏一样 —— 从对弈切到设置那条纵向接缝不动。
  expect(shape.railW, '左栏不是 296 —— 从对弈切过来那条纵向接缝会跳').toBe(296);
  expect(shape.sideW, '右栏不是 680').toBe(680);
  expect(shape.navCount, '导航项数和分组数对不上').toBe(shape.groupCount);
  expect(shape.overflow, '没造出「装不下」—— 下面那条断言是空的').toBeGreaterThan(80);
  expect(shape.at, '一开始就该报 top').toBe('top');

  // 滚到第三组的上缘。**用真滚轮**,不是调 scrollTop —— 高亮挂的是 scroll 事件。
  const target = await page.evaluate(() => {
    const scroll = document.querySelector('.kiosk-side__scroll') as HTMLElement;
    const third = document.querySelector('[data-group="move"]') as HTMLElement;
    return third.getBoundingClientRect().top - scroll.getBoundingClientRect().top;
  });
  const scroll = page.locator('.kiosk-side__scroll');
  const bb = (await scroll.boundingBox())!;
  await page.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
  await page.mouse.wheel(0, Math.round(target) + 4);

  await expect.poll(async () => page.evaluate(() => {
    const items = [...document.querySelectorAll('[data-testid="settings-nav"] button')];
    return items.map((b) => b.getAttribute('aria-current') === 'true');
  }), { message: '滚到第三组了,导航没跟上' }).toEqual([false, false, true, false]);
});

/**
 * 开局设置那几屏(L2 布局 A,右栏 460,形态 1 整栏滚)。
 *
 * **它们是这一轮才第一次能滚的。** 上一版右栏是 MUI 表单外面套一层 `overflow`
 * —— 屏 02 那一版是 `hidden`,装不下的后果是**裁掉**而不是滚。按稿子重画之后右栏是
 * 一叠 `.setgrp`,一定比 460 宽 × 约 400 高装得下的多,所以「能不能滚 / 拨不拨得动 /
 * 主行动键会不会被顶出去」三件事全是新成立的 —— 承重反查在这几屏上是**触发**的。
 *
 * **两屏各量一次,不是量一屏推另一屏。** 它们共用 `.setgrp` 那套类,但**骨架各自手写**
 * (两个不同的页面组件):屏 04 完全可能把主行动键写进滚动区里,而屏 02 的那条闸
 * 对此一无所知。同一条承重链上可以有不止一处断点 —— 判据能转,结论不能转。
 *
 * 造到会溢出:不用造 —— 屏 02 默认八组、屏 04 默认七组,下面第一条就是核这件事,
 * 溢出不到 100 就说明后面全是空的。
 *
 * 判据先写死再读数:
 *   · 该滚的是 `.kiosk-side__scroll`(**不是** `.kiosk-rail`,也不是页面)
 *   · 主行动键在滚动区**外面** ⇒ 怎么滚它都贴着右栏底,`bottom` 不随 scrollTop 变
 *   · 最后一组滚到底之后整个进得了视野 —— 到不了就等于它不存在
 *   · 页面不许横向溢出
 *
 * **变异记录**(2026-08-23,屏 04 那一支):把 `PvpLocalSetupPage` 的主行动键搬进
 * `<KioskScrollZone>` 里边 ⇒ 屏 04 那条当场红在「`ctaBottom` 没贴着右栏底」
 * (586 → 530),而**屏 02 那条照样绿** —— 这一支真的在量屏 04 自己的骨架,
 * 不是跟着屏 02 一起过的。
 */
const SETUP_SCREENS = [
  { name: '屏 02 自由对弈', path: '/kiosk/play/ai/setup/free', last: 'setup-clock', lastName: '用时' },
  { name: '屏 04 本地对局', path: '/kiosk/play/pvp/setup', last: 'setup-sound', lastName: '落子提示音' },
];

for (const screen of SETUP_SCREENS) {
test(`开局设置(${screen.name}):设置装不下时右栏自己滚,而「开始对局」怎么滚都还在`, async ({ page }) => {
  await page.route('**/api/v1/vision/status', (route) => route.fulfill({
    json: {
      enabled: false, camera_connected: false, pose_locked: false, sync_state: 'idle',
      bound_session_id: null, recognition_ready: false, led_connected: null,
    },
  }));
  await boot(page, screen.path);
  await page.waitForSelector(`[data-testid="${screen.last}"]`);

  const railW = await page.evaluate(() =>
    Math.round(document.querySelector('.kiosk-rail')!.getBoundingClientRect().width));
  expect(railW, '右栏不是 460 —— 布局 A 的宽度账先崩了,后面量的滚动都建在错的宽度上').toBe(460);

  const overflow = await overflowOf(page);
  expect(overflow, '没造出溢出 —— 那下面这几条断言都是空的').toBeGreaterThan(100);

  // 主行动键在滚动区外面:先记下它现在在哪。
  const ctaBefore = await page.evaluate(() =>
    Math.round(document.querySelector('.kiosk-primary-action')!.getBoundingClientRect().bottom));

  // **用真滚轮**,不是 `scrollTop = n` —— 程序化能滚 ≠ 手指拨得动。
  const zone = page.locator('.kiosk-side__scroll');
  const zb = (await zone.boundingBox())!;
  await page.mouse.move(zb.x + zb.width / 2, zb.y + zb.height / 2);
  for (let i = 0; i < 12; i += 1) await page.mouse.wheel(0, 400);

  const m = await page.evaluate((lastId) => {
    const el = document.querySelector('.kiosk-side__scroll') as HTMLElement;
    const rail = document.querySelector('.kiosk-rail') as HTMLElement;
    const cta = document.querySelector('.kiosk-primary-action') as HTMLElement;
    const last = document.querySelector(`[data-testid="${lastId}"]`) as HTMLElement;
    return {
      scrollTop: Math.round(el.scrollTop),
      atEnd: el.scrollHeight - el.clientHeight - el.scrollTop,
      railOverflow: rail.scrollHeight - rail.clientHeight,
      ctaBottom: Math.round(cta.getBoundingClientRect().bottom),
      railBottom: Math.round(rail.getBoundingClientRect().bottom),
      // 最后一组滚到底之后必须整个进得了视野 —— 到不了就等于它不存在。
      lastBottom: Math.round(last.parentElement!.getBoundingClientRect().bottom),
      zoneBottom: Math.round(el.getBoundingClientRect().bottom),
      horizontal: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  }, screen.last);

  expect(m.scrollTop, '拨了十二下滚轮,一格都没动 —— 程序化能滚不算数').toBeGreaterThan(0);
  expect(m.atEnd, '滚不到底').toBeLessThanOrEqual(1);
  expect(m.lastBottom, `滚到底了,最后一组「${screen.lastName}」的下缘还在视野外 —— 那一组就是到不了的`)
    .toBeLessThanOrEqual(m.zoneBottom);
  // 溢出必须由滚动区吃掉,**不能顶破右栏** —— 顶破了主行动键就被推出 516 之外。
  expect(m.railOverflow, '右栏自己被顶破了 —— 溢出该由滚动区吃掉').toBeLessThanOrEqual(0);
  expect(m.ctaBottom, '「开始对局」没贴着右栏底').toBe(m.railBottom);
  expect(m.ctaBottom, '滚过之后主行动键动了 —— 它在滚动区外面,不该跟着滚').toBe(ctaBefore);
  expect(m.horizontal, '页面横向溢出了').toBe(0);
});
}

/* ─────────────────────────────────────────────────────────────────────────
 * 屏 06 在线大厅:**两栏各自滚**
 *
 * 这一屏是这套外壳里第一处「同一屏上两个滚动区」。底座的悬浮拇指是
 * `position:absolute; right: var(--scrollbar-inset)`,而它的定位原点靠
 * `.kiosk-scrollzone{position:relative}` —— 那条隐含约定只在「唯一会滚的是最右那栏」时
 * 才看不出问题。这一屏左栏也要滚,**定位错了两条拇指会一起贴到整屏最右边**,
 * 而截图上它们只是两条 3px 宽的细线,四图对比看不出来。⇒ 归这一关,用机器量。
 *
 * 判据先写死再读数:
 *   · 该滚的是**两个** `.kiosk-side__scroll`,各自 scrollHeight > clientHeight
 *   · 在左栏上真拨滚轮 ⇒ **左栏动、右栏一格不动**(反之亦然)—— 这是「两栏独立」的全部内容
 *   · 左栏那条拇指的右缘必须落在**左栏**里(< 右栏左缘),右栏那条落在右栏里
 *   · 溢出由列表吃掉,**不许顶破栏** ⇒ `.lobbycol` 自己不溢出
 *   · 「开始匹配」高度仍是 48(名单一长它会被 flex 从 48 压成 24)、贴着栏底、滚过不动
 *   · 页面不许横向溢出
 *
 * 造输入:12 局 / 20 人。稿子那一帧(5 局 / 14 人)的左栏算出来正好 422 = 可用高度,
 * **一像素都不溢出** —— 拿它量等于什么都没量。
 *
 * **变异记录**(2026-08-24):
 *   · 给 `.gamelist.kiosk-scrollzone` 写上 `position: static` ⇒ 「左栏那条拇指跑到右栏去了」
 *     当场红,右缘从 < 548 变成 **1005**(整屏最右)。稿子警告的正是这一个,红分支跑过。
 *   · **一条没红的**:去掉稿子那条 `.kiosk-primary-action{flex:none}`,`cta.h === 48` 照样绿。
 *     所以那条 CSS 没有照抄(理由写在 `go-screens.css` 那一段);这里的高度断言留着,
 *     但它今天**没有红分支** —— 它挡的是「以后有人改栏结构把按钮挤扁」,不是眼下某个已知故障。
 *     余下三条(拨哪一栏动哪一栏 / 栏不许被顶破 / 按钮贴栏底且滚过不动)与屏 02/04 那一支
 *     同源,那边已有变异记录(把主行动键搬进滚动区)。
 * ────────────────────────────────────────────────────────────────────────── */

const LOBBY_GAMES = Array.from({ length: 12 }, (_, i) => ({
  session_id: `sess${String(i).padStart(4, '0')}`,
  player_b: `黑方${i}`, player_w: `白方${i}`,
  spectator_count: i % 3, move_count: 10 + i * 7,
}));
const LOBBY_USERS = Array.from({ length: 20 }, (_, i) => ({ id: i + 1, username: `棋手${i}` }));

const bootLobbyScroll = async (page: Page) => {
  await page.route('**/api/v1/users/online', (r) => r.fulfill({ json: LOBBY_USERS }));
  await page.route('**/api/v1/games/active/multiplayer', (r) => r.fulfill({ json: LOBBY_GAMES }));
  await page.route('**/api/v1/ai-ladder/status', (r) => r.fulfill({
    json: {
      view_state: 'ready',
      placement_state: { phase: 'placement', completed_games: 2, total_games: 5 },
      current_opponent: null, recent_ranked_results: [], net_score: 0, pending_settlement: false,
    },
  }));
  await boot(page, '/kiosk/play/pvp/lobby');
  await page.waitForSelector('[data-testid="lobby-start-match"]');
  await expect(page.locator('[data-testid="lobby-game"]')).toHaveCount(12);
  await expect(page.locator('[data-testid="lobby-player"]')).toHaveCount(20);
};

/** 两栏的滚动区、两条拇指、两栏外框,一次读齐。 */
const lobbyMetrics = (page: Page) => page.evaluate(() => {
  const zone = (sel: string) => document.querySelector(`${sel} .kiosk-side__scroll`) as HTMLElement;
  const bar = (sel: string) => document.querySelector(`${sel} .kiosk-scrollbar`) as HTMLElement;
  const col = (i: number) => document.querySelectorAll('.lobbycol')[i] as HTMLElement;
  const cta = document.querySelector('.kiosk-primary-action') as HTMLElement;
  const rd = (el: Element) => {
    const b = el.getBoundingClientRect();
    return { left: Math.round(b.left), right: Math.round(b.right), top: Math.round(b.top), bottom: Math.round(b.bottom), h: Math.round(b.height) };
  };
  const of = (el: HTMLElement) => ({
    overflow: el.scrollHeight - el.clientHeight,
    scrollTop: Math.round(el.scrollTop),
    at: (el.closest('.kiosk-scrollzone') as HTMLElement).dataset.at ?? null,
  });
  return {
    left: of(zone('.gamelist')), right: of(zone('.lobbylist')),
    leftBar: rd(bar('.gamelist')), rightBar: rd(bar('.lobbylist')),
    leftCol: rd(col(0)), rightCol: rd(col(1)),
    leftColOverflow: col(0).scrollHeight - col(0).clientHeight,
    rightColOverflow: col(1).scrollHeight - col(1).clientHeight,
    cta: rd(cta),
    horizontal: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  };
});

const wheelOver = async (page: Page, selector: string, times: number) => {
  const box = (await page.locator(selector).boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  for (let i = 0; i < times; i += 1) await page.mouse.wheel(0, 400);
};

test('在线大厅:左右两栏各自滚,拨哪一栏动哪一栏,两条拇指各回各栏', async ({ page }) => {
  await bootLobbyScroll(page);

  const before = await lobbyMetrics(page);
  // 前置:两边都真的溢出了。造不出来下面全是空的。
  expect(before.left.overflow, '左栏没造出溢出 —— 下面几条都是空的').toBeGreaterThan(100);
  expect(before.right.overflow, '右栏没造出溢出 —— 下面几条都是空的').toBeGreaterThan(100);
  expect(before.left.at, '左栏溢出了却没挂 data-at').toBe('top');
  expect(before.right.at, '右栏溢出了却没挂 data-at').toBe('top');

  // ① 两条拇指各回各栏。定位原点错了它们会**一起**贴到整屏最右边。
  expect(before.leftBar.right, '左栏那条拇指跑到右栏去了 —— 定位原点不是自己那一栏')
    .toBeLessThan(before.rightCol.left);
  expect(before.leftBar.right, '左栏拇指不在左栏里').toBeLessThanOrEqual(before.leftCol.right);
  expect(before.rightBar.right, '右栏拇指不在右栏里').toBeLessThanOrEqual(before.rightCol.right);

  // ② 在**左栏**上拨真滚轮:左栏动、右栏一格不动。
  await wheelOver(page, '.gamelist .kiosk-side__scroll', 12);
  const afterLeft = await lobbyMetrics(page);
  expect(afterLeft.left.scrollTop, '拨了十二下,左栏一格没动 —— 程序化能滚不算数').toBeGreaterThan(0);
  expect(afterLeft.right.scrollTop, '拨左栏把右栏也带着滚了 —— 两栏没有各自独立').toBe(0);
  expect(afterLeft.left.at, '左栏滚到底了 data-at 还不是 end').toBe('end');

  // ③ 反过来:在**右栏**上拨,右栏动、左栏停在刚才那儿。
  await wheelOver(page, '.lobbylist .kiosk-side__scroll', 12);
  const after = await lobbyMetrics(page);
  expect(after.right.scrollTop, '拨了十二下,右栏一格没动').toBeGreaterThan(0);
  expect(after.left.scrollTop, '拨右栏把左栏又带动了').toBe(afterLeft.left.scrollTop);
  expect(after.right.at, '右栏滚到底了 data-at 还不是 end').toBe('end');

  // ④ 溢出由列表吃掉,不许顶破栏 —— 顶破了底下三块会被推出 516 之外。
  expect(after.leftColOverflow, '左栏自己被顶破了').toBeLessThanOrEqual(0);
  expect(after.rightColOverflow, '右栏自己被顶破了').toBeLessThanOrEqual(0);

  // ⑤ 「开始匹配」:名单一长,`.kiosk-primary-action` 只有 margin-top:auto **没有 flex:none**,
  //    会被从 48 压成一条 24 的细边。它在滚动区外面,所以滚过也不该动。
  expect(after.cta.h, '「开始匹配」被名单挤扁了 —— 它缺 flex:none').toBe(48);
  expect(after.cta.bottom, '「开始匹配」没贴着右栏底').toBe(after.rightCol.bottom);
  expect(after.cta.bottom, '滚过之后主行动键动了 —— 它在滚动区外面').toBe(before.cta.bottom);

  expect(after.horizontal, '页面横向溢出了').toBe(0);
});

/**
 * 匹配中那个弹层**不许被画布裁掉**。
 *
 * `.cdlg{position:absolute; inset:0}` 找的是最近的**定位祖先**。`.kiosk-layout-a` 不定位的话
 * 它一路找到 `.kiosk-content` —— 那一层带 14px 上下内边距,于是弹层高 544 而中间区只有 516,
 * 底边 28px 落到画布外面。**截图上看不出来**(弹层是半透明的,底下那 14px 本来就是深色),
 * 所以这一条只能量。
 *
 * **变异记录**(2026-08-24):把 `.kiosk-layout-a.lobby-layout` 那条 `position: relative` 去掉,
 * 这一条当场红在「弹层比中间区高」——`cdlgH` 从 516 变 544、`bottom` 从 586 变 600 且
 * 落到 `content.bottom` 之外。红分支跑过。
 */
test('在线大厅:匹配中那个弹层的定位原点是布局根,不是带内边距的中间区', async ({ page }) => {
  await bootLobbyScroll(page);
  await page.click('[data-testid="lobby-start-match"]');
  await page.waitForSelector('[data-testid="lobby-matching"]');

  const m = await page.evaluate(() => {
    const rd = (sel: string) => {
      const b = document.querySelector(sel)!.getBoundingClientRect();
      return { top: Math.round(b.top), bottom: Math.round(b.bottom), h: Math.round(b.height) };
    };
    return {
      dlg: rd('.cdlg'), box: rd('.cdlg__box'),
      layout: rd('.kiosk-layout-a'), content: rd('.kiosk-content'),
      screenBottom: Math.round(document.querySelector('.kiosk-screen')!.getBoundingClientRect().bottom),
    };
  });

  expect(m.dlg.h, '弹层不是布局根那么高 —— 它的定位原点跑到别的层去了').toBe(m.layout.h);
  expect(m.dlg.top, '弹层上缘没对齐布局根').toBe(m.layout.top);
  expect(m.dlg.bottom, '弹层下缘超出了中间区 —— 底边会被画布裁掉')
    .toBeLessThanOrEqual(m.content.bottom);
  expect(m.dlg.bottom, '弹层被画布裁了').toBeLessThanOrEqual(m.screenBottom);
  // 盒子本身也得整个在里面 —— 弹层对了但盒子太高一样看不全。
  expect(m.box.top, '弹窗盒上缘在中间区外面').toBeGreaterThanOrEqual(m.content.top);
  expect(m.box.bottom, '弹窗盒下缘在中间区外面').toBeLessThanOrEqual(m.content.bottom);
});

/* ─────────────────────────────────────────────────────────────────────────
 * 屏 09 跨平台 · 人机开局:布局 A,右栏整栏滚,「开始对局」钉栏底
 *
 * 骨架和屏 02/04 是同一副,但**不能挂进上面那条 `SETUP_SCREENS` 循环** ——
 * 这一屏的内容要先从平台把 39 档棋力拉回来(`/platforms/:p/engine/levels`),
 * 那条循环的 `boot` 不喂它,拉不到就只剩一条错误提示,右栏根本不溢出 ⇒
 * 整组断言会以「没造出溢出」的姿态变红,或者更糟:量的是另一屏。
 * 「判据能转,结论不能转」——这里把判据搬过来,自己造自己的输入。
 *
 * 造输入:39 档全份。这一屏的右栏内容天然远超 460,不需要额外撑。
 * ────────────────────────────────────────────────────────────────────────── */
test('跨平台人机开局:设置装不下时右栏自己滚,而「开始对局」怎么滚都还在', async ({ page }) => {
  await page.route('**/api/v1/vision/status', (route) => route.fulfill({
    json: {
      enabled: false, camera_connected: false, pose_locked: false, sync_state: 'idle',
      bound_session_id: null, recognition_ready: false, led_connected: null,
    },
  }));
  await page.route('**/api/v1/platforms/golaxy/engine/levels', (route) => route.fulfill({
    json: {
      levels: Array.from({ length: 39 }, (_, i) => ({
        elo_score: 100 + i * 10, level_name: `第 ${i + 1} 档`, name: `星阵 ${i + 1}`,
        goal_difference: 0, timing: '', display_elo: 400 + i * 50, ref_rank: `业余 ${i + 1}`,
      })),
    },
  }));
  await boot(page, '/kiosk/play/cross-platform/engine/golaxy');
  await page.waitForSelector('[data-testid="setup-summary-line"]');

  const railW = await page.evaluate(() =>
    Math.round(document.querySelector('.kiosk-rail')!.getBoundingClientRect().width));
  expect(railW, '右栏不是 460 —— 布局 A 的宽度账先崩了').toBe(460);

  // 前置:棋力档真拉回来了。拉不到时这一屏只剩一条错误提示,右栏根本不溢出 ——
  // 下面整组会以「没造出溢出」的姿态红,而红的原因是 fixture 不是版式。
  await expect(page.locator('[data-testid="setup-opponent"] .catmeta')).toContainText('/ 39 档');

  const overflow = await overflowOf(page);
  expect(overflow, '没造出溢出 —— 那下面这几条断言都是空的').toBeGreaterThan(100);

  const ctaBefore = await page.evaluate(() =>
    Math.round(document.querySelector('.kiosk-primary-action')!.getBoundingClientRect().bottom));

  // **真滚轮**,不是 `scrollTop = n`。
  const zone = page.locator('.kiosk-side__scroll');
  const zb = (await zone.boundingBox())!;
  await page.mouse.move(zb.x + zb.width / 2, zb.y + zb.height / 2);
  for (let i = 0; i < 24; i += 1) await page.mouse.wheel(0, 400);

  const m = await page.evaluate(() => {
    const el = document.querySelector('.kiosk-side__scroll') as HTMLElement;
    const rail = document.querySelector('.kiosk-rail') as HTMLElement;
    const cta = document.querySelector('.kiosk-primary-action') as HTMLElement;
    const last = document.querySelector('[data-testid="setup-summary-line"]') as HTMLElement;
    return {
      scrollTop: Math.round(el.scrollTop),
      atEnd: el.scrollHeight - el.clientHeight - el.scrollTop,
      railOverflow: rail.scrollHeight - rail.clientHeight,
      ctaBottom: Math.round(cta.getBoundingClientRect().bottom),
      ctaHeight: Math.round(cta.getBoundingClientRect().height),
      railBottom: Math.round(rail.getBoundingClientRect().bottom),
      lastBottom: Math.round(last.parentElement!.getBoundingClientRect().bottom),
      zoneBottom: Math.round(el.getBoundingClientRect().bottom),
      horizontal: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });

  expect(m.scrollTop, '拨了二十四下滚轮,一格都没动 —— 程序化能滚不算数').toBeGreaterThan(0);
  expect(m.atEnd, '滚不到底').toBeLessThanOrEqual(1);
  expect(m.lastBottom, '滚到底了,「这一局会是」还在视野外 —— 那一段就是到不了的')
    .toBeLessThanOrEqual(m.zoneBottom);
  expect(m.railOverflow, '右栏自己被顶破了 —— 溢出该由滚动区吃掉').toBeLessThanOrEqual(0);
  expect(m.ctaHeight, '「开始对局」被上面几组挤扁了').toBe(48);
  expect(m.ctaBottom, '「开始对局」没贴着右栏底').toBe(m.railBottom);
  expect(m.ctaBottom, '滚过之后主行动键动了 —— 它在滚动区外面').toBe(ctaBefore);
  expect(m.horizontal, '页面横向溢出了').toBe(0);
});

/* ─────────────────────────────────────────────────────────────────────────
 * 屏 08 跨平台 · 大厅:布局 B,搜到的人多了整栏自己滚,底下两段滚得到
 *
 * 稿子那一帧只有三个人,**一屏装得下** —— 拿它量等于什么都没量。这里造 24 个,
 * 那才是「搜 a」在 OGS 上的常态。判据:
 *   · 该滚的是 `.kiosk-side__scroll`(布局 B 形态 1 整栏滚),**不是页面**
 *   · 滚到底之后「自动匹配」那一段整个进得了视野 —— 到不了就等于它不存在
 *   · 页面不许横向溢出;通栏仍是 992
 * ────────────────────────────────────────────────────────────────────────── */
test('跨平台大厅:搜到的人多到装不下时整栏自己滚,「自动匹配」那一段滚得到', async ({ page }) => {
  await page.route('**/api/v1/platforms/status', (route) => route.fulfill({
    json: {
      platforms: [{
        platform: 'ogs', connected: true, saved_username: 'me',
        supports_live_play: true, supports_automatch: true,
        supports_rooms: false, supports_seek_graph: true, supports_engine_play: false,
      }],
    },
  }));
  await page.route('**/api/v1/platforms/ogs/users*', (route) => route.fulfill({
    json: {
      users: Array.from({ length: 24 }, (_, i) => ({
        user_id: String(i), username: `player_${i}`, rank: `${i % 9 + 1}k`,
        status: i % 5 === 0 ? 'playing' : 'idle',
      })),
    },
  }));
  await boot(page, '/kiosk/play/cross-platform/lobby?platform=ogs');
  await page.waitForSelector('[data-testid="platform-automatch"]');
  expect(await page.locator('[data-testid="platform-user"]').count(), '24 个人没渲出来').toBe(24);

  const zoneW = await page.evaluate(() =>
    Math.round(document.querySelector('.kiosk-side__scroll')!.getBoundingClientRect().width));
  expect(zoneW, '布局 B 的滚动区不是通栏 992').toBe(992);

  const overflow = await overflowOf(page);
  expect(overflow, '没造出溢出 —— 下面的断言都是空的').toBeGreaterThan(100);

  const zone = page.locator('.kiosk-side__scroll');
  const zb = (await zone.boundingBox())!;
  await page.mouse.move(zb.x + zb.width / 2, zb.y + zb.height / 2);
  for (let i = 0; i < 16; i += 1) await page.mouse.wheel(0, 400);

  const m = await page.evaluate(() => {
    const el = document.querySelector('.kiosk-side__scroll') as HTMLElement;
    const auto = document.querySelector('[data-testid="platform-automatch"]') as HTMLElement;
    return {
      scrollTop: Math.round(el.scrollTop),
      atEnd: el.scrollHeight - el.clientHeight - el.scrollTop,
      autoBottom: Math.round(auto.getBoundingClientRect().bottom),
      zoneBottom: Math.round(el.getBoundingClientRect().bottom),
      pageScroll: Math.round(document.documentElement.scrollTop),
      horizontal: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });

  expect(m.scrollTop, '拨了十六下滚轮,一格都没动').toBeGreaterThan(0);
  expect(m.atEnd, '滚不到底').toBeLessThanOrEqual(1);
  expect(m.autoBottom, '滚到底了,「自动匹配」那一段还在视野外 —— 那一段就是到不了的')
    .toBeLessThanOrEqual(m.zoneBottom);
  // 滚的必须是那一栏,不是整页 —— 整页一滚,顶栏和 Dock 会跟着跑出去(规范 §5 防跳铁律 1)。
  expect(m.pageScroll, '滚的是整个页面,不是那一栏').toBe(0);
  expect(m.horizontal, '页面横向溢出了').toBe(0);
});

/* ─────────────────────────────────────────────────────────────────────────
 * 屏 07 跨平台 · 连接:**软键盘不许把正在输入的那一格压在底下**
 *
 * 这一屏的登录段排在第三段。真浏览器量出来:滚动区 clientH 460 / scrollH 610 ⇒
 * **maxScroll 只有 150**;而触屏键盘高 188、上缘落在 y=412 —— 两个输入框滚到底时
 * 都在 412 以下。键盘自己那句 `scrollIntoView({block:'center'})` 需要 scrollTop≈294,
 * 比 maxScroll 还大,**救不回来**:人看不见自己打的验证码。
 *
 * 修法是聚焦时给滚动区垫一段等于键盘高度的下内衬(`PlatformConnectPage` 里那个 effect),
 * **不动版式** —— 所以四图仍逐像素可比,而这一条只能在这儿量。
 *
 * ⚠️ 判据是**键盘上缘**,不是某个写死的 y:键盘带中文候选条时会长到 246,
 * 写死 412 的话候选条一出来这条闸就变成假绿。
 *
 * **变异记录**(2026-08-24):把 `PlatformConnectPage` 里那个 `paddingBottom` 的赋值删掉
 * ⇒ 这条当场红在**断言本身**:验证码那格底边 **525** > 键盘上缘 **412**(压掉 113px)。
 * (第一版把「内衬写进去了」当成前置等待,变异红在了那句 `waitForFunction` 上 ——
 * 那是红在被测机制自己身上,断言其实没跑过。改成等「输入框位置不再变」,修没修都成立。)
 * ────────────────────────────────────────────────────────────────────────── */
test('跨平台连接:聚焦验证码那一格时,它整个在软键盘上缘之上', async ({ page }) => {
  await page.route('**/api/v1/platforms/status', (route) => route.fulfill({
    json: {
      platforms: [
        { platform: 'ogs', connected: true, saved_username: 'me', supports_live_play: true,
          supports_automatch: true, supports_rooms: false, supports_seek_graph: true, supports_engine_play: false },
        { platform: 'golaxy', connected: false, supports_live_play: true,
          supports_automatch: false, supports_rooms: true, supports_seek_graph: false, supports_engine_play: true },
        { platform: 'fox', connected: false, supports_live_play: false,
          supports_automatch: false, supports_rooms: true, supports_seek_graph: false, supports_engine_play: false },
      ],
    },
  }));
  await boot(page, '/kiosk/play/cross-platform');
  await page.waitForSelector('[data-testid="platform-login-section"]');
  // 键盘是 index.html 在 load 之后异步塞进来的三个脚本 —— 不等它,量到的是「没有键盘」。
  await page.waitForSelector('.skbd', { state: 'attached' });

  // 前置:这一屏确实滚不到底就够不着 —— 造不出这个前置,下面那条断言是空的。
  const before = await page.evaluate(() => {
    const zone = document.querySelector('.kiosk-side__scroll') as HTMLElement;
    return { maxScroll: zone.scrollHeight - zone.clientHeight };
  });
  expect(before.maxScroll, '这一屏根本不溢出 —— 那这条闸没有被测对象').toBeGreaterThan(0);

  await page.locator('[data-testid="platform-login-pass"]').click();
  // ⚠️ 等的是**它真的滑上来了**,不是 `skbd-open` 这个类。类一加就为真,而 transform
  // 还在过渡 —— 那一刻量到的 `keyboardTop` 是 599(键盘还在屏幕外),
  // 「输入框在键盘上方」于是恒成立:**断言落在两种语义恰好同值的那一侧**,假绿。
  await page.waitForFunction(() => {
    const k = document.querySelector('.skbd') as HTMLElement | null;
    if (!k || !k.offsetHeight) return false;
    return k.getBoundingClientRect().top <= window.innerHeight - k.offsetHeight + 2;
  });
  // 等布局稳下来再量。⚠️ **等的不能是「内衬写进去了」** —— 那是被测的那个机制本身,
  // 拿它当前置的话,去掉内衬的变异会红在这句等待上而不是红在下面那条断言上,
  // 红分支就没被真正跑过。这里等的是**输入框的位置不再变**,修没修都成立。
  await page.waitForFunction(() => {
    const w = window as unknown as { __lastBottom?: number };
    const el = document.querySelector('[data-testid="platform-login-pass"]') as HTMLElement;
    const now = Math.round(el.getBoundingClientRect().bottom);
    const settled = w.__lastBottom === now;
    w.__lastBottom = now;
    return settled;
  }, undefined, { polling: 120 });

  const m = await page.evaluate(() => {
    const input = document.querySelector('[data-testid="platform-login-pass"]') as HTMLElement;
    const kbd = document.querySelector('.skbd') as HTMLElement;
    return {
      inputBottom: Math.round(input.getBoundingClientRect().bottom),
      keyboardTop: Math.round(kbd.getBoundingClientRect().top),
      keyboardH: Math.round(kbd.offsetHeight),
    };
  });
  console.log('[kbd-inset] inputBottom=%d keyboardTop=%d keyboardH=%d',
    m.inputBottom, m.keyboardTop, m.keyboardH);
  expect(m.keyboardH, '键盘没弹出来 —— 那这条闸量的不是被键盘挡住这件事').toBeGreaterThan(0);
  expect(m.inputBottom, '验证码那一格被软键盘压住了 —— 人看不见自己打的字')
    .toBeLessThanOrEqual(m.keyboardTop);
});

/* ─────────────────────────────────────────────────────────────────────────
 * 屏 24 课程 · 书目与章节:布局 B 整栏滚,而**摊开的那几节挂在一个新的包装 div 里**
 *
 * 这一屏是两屏合一新造的承重链,量的是三件事:
 *
 *  ① **该滚的是 `.kiosk-side__scroll`,不是整页。** 整页一滚,顶栏会跟着跑出去。
 *  ② **两种行的高是浏览器算出来的 52 / 44。** 44 是触摸靶子的下限(规范 §8),
 *     不是随手挑的一个比 52 小的数 —— 为了多塞两行把它调下去,这一条当场红。
 *  ③ **最后一章滚得到。** 摊开一章之后总高涨了一截,滚不到底就等于后面几章不存在。
 *
 * 造数据:6 章 × 6 节。稿子那一帧一节都没摊开、6 章刚好露五行半 —— 拿它量等于什么都没量。
 *
 * ## 变异实测(2026-08-24),含一条**被证伪的**担心
 *
 *  · `.secrow{height:36px}` ⇒ 红在「节行被压扁了:36/36/…」。②的红分支跑过。
 *  · `.kiosk-side__scroll{overflow-y:visible}` ⇒ 红在「拨了十六下滚轮,一格都没动」。①跑过。
 *  · `.secrows{position:absolute}` ⇒ 红在**前置**「没造出溢出」。那句话是准的:节那一段
 *    脱了流,整栏就不会因它变高,几节互相压着、谁也滚不到 —— 不是断言选错了地方。
 *  · ⚠️ **写这条闸时我担心的那个坑不成立。** 我原以为节那一段外面那个自己加的 `<div>`
 *    没有 `flex:none`,会像 `tokens.css:939` 记的 2026-07-29 那次一样被压扁(18 行压成 33px)。
 *    变异(给 `[data-testid="tutorial-chapter-rows"]` 加 `max-height:240px`)**照旧全绿** ——
 *    因为 `.kiosk-row` 自己带着 `height: var(--row-h)` **和** `flex:none`,包装 div 被压
 *    并不会传下去。理由留在这儿,免得下一个人照着一个假前提改结构。
 * ────────────────────────────────────────────────────────────────────────── */
const TUTORIAL_BOOKS = [
  { id: 1, category: '入门', subcategory: '', title: '围棋入门一本通', author: null, translator: null, slug: 'rumen', chapter_count: 6 },
];
const TUTORIAL_BOOK_DETAIL = {
  ...TUTORIAL_BOOKS[0],
  chapters: Array.from({ length: 6 }, (_, i) => ({
    id: 100 + i, book_id: 1, chapter_number: `第 ${i + 1} 章`, title: `第 ${i + 1} 章的名字`,
    order: i, section_count: 6,
  })),
};
const tutorialSections = (chapterId: number) => Array.from({ length: 6 }, (_, i) => ({
  id: chapterId * 100 + i, chapter_id: chapterId, section_number: String(i + 1),
  title: `第 ${i + 1} 节`, order: i, figure_count: 7, has_video: i === 0,
}));

const bootTutorialBooks = async (page: Page) => {
  await page.route('**/api/v1/tutorials/categories/*/books', (route) => route.fulfill({ json: TUTORIAL_BOOKS }));
  await page.route('**/api/v1/tutorials/books/1', (route) => route.fulfill({ json: TUTORIAL_BOOK_DETAIL }));
  await page.route('**/api/v1/tutorials/chapters/*/sections', (route) => {
    const id = Number(/chapters\/(\d+)\/sections/.exec(route.request().url())?.[1] ?? 100);
    route.fulfill({ json: tutorialSections(id) });
  });
  await boot(page, '/kiosk/tutorial/%E5%85%A5%E9%97%A8');
  await page.waitForSelector('[data-testid="tutorial-chapter-row"]');
};

test('课程书目:摊开一章之后整栏自己滚,行不许被压扁,最后一章滚得到', async ({ page }) => {
  await bootTutorialBooks(page);

  const zoneW = await page.evaluate(() =>
    Math.round(document.querySelector('.kiosk-side__scroll')!.getBoundingClientRect().width));
  expect(zoneW, '布局 B 的滚动区不是通栏 992').toBe(992);

  // 摊开第一章 —— 这一下才是这条闸要量的那个结构。
  await page.locator('[data-testid="tutorial-chapter-row"]').first().click();
  await page.waitForSelector('[data-testid="tutorial-section-row"]');
  expect(await page.locator('[data-testid="tutorial-section-row"]').count(), '六节没渲出来').toBe(6);

  const overflow = await overflowOf(page);
  expect(overflow, '没造出溢出 —— 下面的断言都是空的').toBeGreaterThan(100);

  // ② 行高:章 52 / 节 44。**先写死关系式再读数**,具体像素只作记录。
  const heights = await page.evaluate(() => {
    const h = (sel: string) => [...document.querySelectorAll(sel)]
      .map((el) => Math.round(el.getBoundingClientRect().height));
    return { chapters: h('[data-testid="tutorial-chapter-row"]'), sections: h('[data-testid="tutorial-section-row"]') };
  });
  expect(new Set(heights.chapters), `章行被压扁了:${heights.chapters.join('/')}`).toEqual(new Set([52]));
  expect(new Set(heights.sections), `节行被压扁了:${heights.sections.join('/')}`).toEqual(new Set([44]));

  // ③ 滚到底,最后一章进得了视野。
  const zb = (await page.locator('.kiosk-side__scroll').boundingBox())!;
  await page.mouse.move(zb.x + zb.width / 2, zb.y + zb.height / 2);
  for (let i = 0; i < 16; i += 1) await page.mouse.wheel(0, 400);

  const m = await page.evaluate(() => {
    const el = document.querySelector('.kiosk-side__scroll') as HTMLElement;
    const rows = document.querySelectorAll('[data-testid="tutorial-chapter-row"]');
    const last = rows[rows.length - 1] as HTMLElement;
    return {
      scrollTop: Math.round(el.scrollTop),
      atEnd: el.scrollHeight - el.clientHeight - el.scrollTop,
      lastBottom: Math.round(last.getBoundingClientRect().bottom),
      lastTop: Math.round(last.getBoundingClientRect().top),
      zoneBottom: Math.round(el.getBoundingClientRect().bottom),
      zoneTop: Math.round(el.getBoundingClientRect().top),
      pageScroll: Math.round(document.documentElement.scrollTop),
      horizontal: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });

  expect(m.scrollTop, '拨了十六下滚轮,一格都没动').toBeGreaterThan(0);
  expect(m.atEnd, '滚不到底').toBeLessThanOrEqual(1);
  expect(m.lastBottom, '滚到底了,最后一章还在视野外').toBeLessThanOrEqual(m.zoneBottom);
  expect(m.lastTop - m.zoneTop, '最后一章被卷出了视野顶部').toBeGreaterThanOrEqual(0);
  expect(m.pageScroll, '滚的是整个页面,不是那一栏').toBe(0);
  expect(m.horizontal, '页面横向溢出了').toBe(0);
});

/* ─────────────────────────────────────────────────────────────────────────
 * 屏 17 摆谱 · 进行中:**「确认落子」在任何一态下都得贴着右栏底**
 *
 * 这一屏是 27 屏里最不能让那颗键动的一屏 —— 一局 241 手要按它约 250 次,位置是肌肉记忆。
 * 而它贴底靠的是共享 `tokens.css` 的 `.kiosk-rail .kiosk-actions{margin-top:auto}`:
 * **右栏一旦自己溢出,那条 `auto` 就没有空间可让,键会被顶出画布**(还在 DOM 里,手指够不到)。
 *
 * 右栏的账是死的:页控条 44 + `.pcard` 60 + 两个折叠头 30×2 + 动作区 52 + 四条间隙 48 = 264,
 * **两个折叠块的 body 一共只剩 252**。所以这一屏所有「新增一块」的想法都被这个数否掉了 ——
 * 四条通栏横幅(拍照 / 待移除 / 几何漂移 / 采集失败)一条都没进右栏,各自找了别的落点。
 *
 * **造数据要造到会溢出**:241 手 ⇒ 121 行着法,`.mvrows` 装得下 6 行。
 * 装得下的数据量下量出来的数字一概不算。
 *
 * 四态逐个量,因为它们换的是**同一块 pcard 的内容**,而内容一长盒子就可能长高 ——
 * 「待移除」那一态标题最长(「请拿走被提的 N 子」+ 两行副文)。
 *
 * ## 变异实测(2026-08-24)—— **我预判的三条里有两条是错的,照实记**
 *
 * | 变异 | 我以为 | 实际 |
 * |---|---|---|
 * | 去掉 `.baipu-layout{position:relative}` | 遮罩那条红 | ✅ 红:`遮罩顶边 56 对不上布局根 70` |
 * | `.pcard` 的 `height:60px` → `min-height:60px` | 「贴底」红 | ❌ **全绿**:内容本来就装得下,`min-height` 不会让它长高 |
 * | `.pcard` 高度硬改成 **140** | ——(没想到) | ❌ **仍全绿**:着法那块带 `grow`(`flex:1;min-height:0`),多出来的 80 由它让出来 |
 * | `.pcard` 高度硬改成 **240** | —— | ✅ 红:`着法块只剩 16px,装不下三行` |
 * | 去掉着法那块的 `grow` | 「右栏不许溢出」红 | ✅ 红,而且**一次红三条**(含「遮罩没盖住那三颗键」——栏一溢出,键被顶出布局根) |
 *
 * 有价值的是中间那两行:**这条链上真正承重的不是「pcard 有多高」,是那块 `grow`。**
 * 只要它在,右栏就不会溢出、键就贴得住底,pcard 长高只是把着法表压薄;
 * 一旦它不在,三条断言同时倒。⇒ 这道闸的牙齿其实是**「着法块 ≥ 3 行」**那一条 ——
 * 它是「压薄」和「压没」之间唯一的分界线,前面几条(贴底 / 不溢出)在 `grow` 还在时杀不死。
 * ────────────────────────────────────────────────────────────────────────── */
const BAIPU_STEPS = (n: number) => ({
  board_size: 19,
  meta: { player_black: '申真谞', player_white: '柯洁', handicap: 0, komi: 7.5, ruleset: 'chinese' },
  steps: Array.from({ length: n }, (_, i) => ({
    kind: 'move', move_index: i, property: i % 2 === 0 ? 'B' : 'W',
    row: 3 + (i % 13), col: 3 + Math.floor(i / 13) % 13, color: i % 2 === 0 ? 'B' : 'W',
    // 第 3 手提两颗 —— 那一态的 pcard 文案最长,量的就是它。
    removed: i === 2 ? [{ row: 0, col: 0 }, { row: 0, col: 1 }] : [],
    board_hash: `h${i}`,
  })),
});

const bootBaipu = async (page: Page, opts: { capture?: 'ok' | 'fail' | 'hang' } = {}) => {
  await page.route('**/api/v1/baipu/load', (route) => route.fulfill({ json: BAIPU_STEPS(241) }));
  await page.route('**/api/v1/led/**', (route) => route.fulfill({
    json: { ok: true, connected: true, shown_at: null, errors: [] },
  }));
  await page.route('**/api/v1/baipu/capture', async (route) => {
    if (opts.capture === 'fail') return route.fulfill({ status: 500, json: { detail: 'camera unavailable' } });
    if (opts.capture === 'hang') return new Promise(() => {});     // 永不回 ⇒ 停在拍照遮罩上
    return route.fulfill({ json: { ok: true, path: '/c/frame_001.jpg' } });
  });
  // ⚠️ **不能用上面那个共享 `boot`**:它末尾等 `.kiosk-scrollzone`,而这一屏没有 ——
  // 它的右栏是两个 `KioskFold`(各自内滚),不是整栏滚的 `KioskScrollZone`。
  // 等一个永远不出现的选择器 = 30 秒超时,而且超时信息指向 helper、不指向真正的原因。
  await page.addInitScript(() => {
    localStorage.setItem('token', 'kiosk-shell-scroll');
    localStorage.setItem('katrain_language', 'cn');
    localStorage.setItem('baipu:sgf:g1', JSON.stringify({ id: 'g1', name: '三星杯半决赛', sgf: '(;SZ[19];B[pd])', savedAt: 1 }));
  });
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: 'tester', rank: '5段', credits: 0 },
  }));
  await page.goto('/kiosk/baipu/session/g1');
  await page.waitForSelector('[data-testid="baipu-pcard"]');
};

/** 右栏、动作区、着法块、画布,一次读齐。 */
const railOf = (page: Page) => page.evaluate(() => {
  const rail = document.querySelector('.kiosk-rail') as HTMLElement;
  const acts = document.querySelector('[data-testid="baipu-actions"]') as HTMLElement;
  const moves = document.querySelector('[data-testid="baipu-moves-fold"] .mvrows') as HTMLElement;
  const screen = document.querySelector('.kiosk-screen') as HTMLElement;
  const board = document.querySelector('[data-testid="baipu-board"]') as HTMLElement;
  const r = rail.getBoundingClientRect();
  const a = acts.getBoundingClientRect();
  const b = board.getBoundingClientRect();
  return {
    railH: Math.round(r.height),
    railBottom: Math.round(r.bottom),
    railOverflow: rail.scrollHeight - rail.clientHeight,
    actsBottom: Math.round(a.bottom),
    actsCount: acts.querySelectorAll('button').length,
    movesOverflow: moves.scrollHeight - moves.clientHeight,
    movesH: Math.round(moves.getBoundingClientRect().height),
    boardW: Math.round(b.width),
    boardH: Math.round(b.height),
    screenBottom: Math.round(screen.getBoundingClientRect().bottom),
  };
});

test('摆谱:241 手四态轮一遍,「确认落子」始终贴右栏底、盘恒 516', async ({ page }) => {
  await bootBaipu(page);

  const guiding = await railOf(page);
  expect(guiding.railH, '右栏不是 516 —— 布局 A 的高度账先崩了').toBe(516);
  expect(guiding.boardW, '盘不是 516 宽').toBe(516);
  expect(guiding.boardH, '盘不是 516 高').toBe(516);
  expect(guiding.actsCount, '动作区不是三格 —— 稿子那颗「虚手」不做').toBe(3);
  expect(guiding.movesOverflow, '241 手没造出溢出 —— 下面的断言都是空的').toBeGreaterThan(100);
  expect(guiding.railOverflow, '右栏自己被顶破了 —— 溢出该由着法那一块自己吃掉').toBeLessThanOrEqual(0);
  expect(guiding.actsBottom, '动作区没贴右栏底').toBe(guiding.railBottom);
  expect(guiding.actsBottom, '动作区被顶到画布外面了').toBeLessThanOrEqual(guiding.screenBottom);
  // 规范:固定部分之后至少留得下 3 行,否则右栏就得整栏滚 —— 而整栏一滚这颗键就不贴底了。
  expect(guiding.movesH, `着法块只剩 ${guiding.movesH}px,装不下三行`).toBeGreaterThanOrEqual(3 * 24);

  // ── 待移除:pcard 文案最长的那一态 ──
  await page.getByRole('button', { name: '确认落子' }).click();
  await page.getByRole('button', { name: '确认落子' }).click();
  await page.getByRole('button', { name: '确认落子' }).click();
  await expect(page.getByTestId('baipu-pcard')).toHaveAttribute('data-mood', 'removal');
  const removal = await railOf(page);
  expect(removal.railH, '待移除态右栏被撑破').toBe(516);
  expect(removal.railOverflow, '待移除态右栏自己溢出了').toBeLessThanOrEqual(0);
  expect(removal.actsBottom, '待移除态动作区没贴底').toBe(removal.railBottom);
});

test('摆谱:采集失败那一态,右栏照样不溢出、键照样贴底', async ({ page }) => {
  await bootBaipu(page, { capture: 'fail' });
  await page.getByRole('button', { name: '确认落子' }).click();
  await expect(page.getByTestId('baipu-pcard')).toHaveAttribute('data-mood', 'failed');

  const m = await railOf(page);
  expect(m.railH).toBe(516);
  expect(m.railOverflow, '失败态右栏自己溢出了 —— 那句话把栏顶破了').toBeLessThanOrEqual(0);
  expect(m.actsBottom, '失败态动作区没贴底').toBe(m.railBottom);
  expect(m.actsCount, '失败态动作区格数变了 —— 格子一变位置就跳').toBe(3);
});

/**
 * 拍照遮罩盖的是**整个布局根**,不只是盘 —— 它的第一职责是挡住第二次按下「确认落子」。
 * 判据照抄屏 06 那条(`:776`):`.cdlg{inset:0}` 找的是最近的**定位祖先**,
 * 布局根不定位的话它会一路找到带 14px 上下内边距的 `.kiosk-content`,
 * 于是 top 差 14、高多 28,底边被画布裁掉。
 */
test('摆谱:拍照遮罩的定位原点是布局根,而且真的盖住了那三颗键', async ({ page }) => {
  await bootBaipu(page, { capture: 'hang' });
  await page.getByRole('button', { name: '确认落子' }).click();
  await page.waitForSelector('[data-testid="baipu-capture-pending"]');

  const m = await page.evaluate(() => {
    const dlg = document.querySelector('[data-testid="baipu-capture-pending"]') as HTMLElement;
    const root = document.querySelector('.kiosk-layout-a.baipu-layout') as HTMLElement;
    const acts = document.querySelector('[data-testid="baipu-actions"]') as HTMLElement;
    const d = dlg.getBoundingClientRect();
    const r = root.getBoundingClientRect();
    const a = acts.getBoundingClientRect();
    return {
      dlg: { top: Math.round(d.top), left: Math.round(d.left), h: Math.round(d.height), w: Math.round(d.width) },
      root: { top: Math.round(r.top), left: Math.round(r.left), h: Math.round(r.height), w: Math.round(r.width) },
      // 遮罩的矩形要把动作区整个包住 —— 不然那三颗键就是「看着能按、按下去没反应」
      covers: d.top <= a.top && d.bottom >= a.bottom && d.left <= a.left && d.right >= a.right,
      zIndex: getComputedStyle(dlg).zIndex,
    };
  });

  expect(m.dlg.top, `遮罩顶边 ${m.dlg.top} 对不上布局根 ${m.root.top}`).toBe(m.root.top);
  expect(m.dlg.left).toBe(m.root.left);
  expect(m.dlg.h, `遮罩高 ${m.dlg.h} 对不上布局根 ${m.root.h}`).toBe(m.root.h);
  expect(m.dlg.w).toBe(m.root.w);
  expect(m.covers, '遮罩没盖住那三颗键 —— 拍照时还能按下第二次「确认落子」').toBe(true);
});
