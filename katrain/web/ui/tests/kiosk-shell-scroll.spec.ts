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

/** 视口底边切在哪张卡上、露出多少。找不到被切的那一张 = 正好切在缝上,那是最坏的一种。 */
const peekCut = (page: Page) => page.evaluate(() => {
  const sc = document.querySelector('.kiosk-side__scroll') as HTMLElement;
  const vb = sc.getBoundingClientRect().bottom;
  const items = [...document.querySelectorAll('.kiosk-card')] as HTMLElement[];
  const cut = items.map(el => el.getBoundingClientRect())
    .find(b => b.top < vb - 0.5 && b.bottom > vb + 0.5);
  if (!cut) {
    const above = items.map(e => e.getBoundingClientRect().bottom).filter(b => b <= vb);
    return { none: true as const, gap: above.length ? +(vb - Math.max(...above)).toFixed(1) : null };
  }
  return { none: false as const, h: +cut.height.toFixed(1), peek: +(vb - cut.top).toFixed(1) };
});

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
 * ⚠️ **已知不合规,根因在设计稿,不在这份实现** —— 所以标 `test.fail()`:
 * 它现在必须红(=body 抛),等哪天真修好了,这条会**反过来变红**,提醒把标记删掉。
 *
 * 规范 §5「露一半」:内容溢出时视口底边必须切在一张卡中间,`max(16,.25h) ≤ 露出 ≤ h−max(12,.25h)`
 * —— 76 的模式卡就是 **[19, 57]**;「正好切在缝上」被规范点名为**最坏的一种**。
 *
 * 实测两个数据态都不合规(1024×600,`.kiosk-side__scroll` 底边 y=504):
 *   · 有「接着上次」  → 卡行 424..500,底边落在 500..510 那条 10px 的缝里(离上一张 **4**)
 *   · 没有「接着上次」→ 卡行 442..518,**露 62** / 卡高 76(上界 57)
 *
 * **根因是量出来的,不是推出来的**:稿子 `data-screen="training"` 那两段 `.note`(分类标签的
 * 来源、环里为什么写「—」)一共 **41px**,把「按级别」整段往下顶了 41 —— 稿子自己的
 * `peek` 因此是 39,恰好落在 [19,57] 里。而 `.note` 是写给读稿人的旁注,**按 G5 一律不上线**。
 * 把这两段 `hidden` 掉重跑稿子自己的闸(`sample-go/gate.mjs`),它当场报:
 *   `FAIL [training] §5 露一半 ← 正好切在缝上,底下那条完全没露(离上一张 4)`
 * ⇒ **这一屏的合规是靠一段永远不会上线的散文撑着的。**
 *
 * 修它要往那条带里放**真东西**(43–63px 才能让两个数据态同时落进 [19,57] —— 两态相差 18,
 * 而窗口宽 39,所以确实同时装得下)。规范 §5 给训练营留的那一块正是**每日一题**,
 * 围棋稿没画、围棋也没有第二个题源。⇒ 放什么是产品决定,交 Fan。
 */
test('训练营 §5 露一半:两个数据态都不合规 —— 稿子靠 41px 旁注撑着(已知,待 Fan 裁)', async ({ page }) => {
  // ⚠️ `test.fail()` 必须写在**用例体里**。写在文件作用域会套住这个文件里**后面每一条**,
  //    实测:三条 `/kiosk/play` 的闸连同两条训练营的闸一起被标成「预期失败」,
  //    于是五条真闸全红、整份文件只剩这一条「过」—— 一条注解把整道闸关掉了。
  test.fail();
  await bootTraining(page, LEVELS(12), true);
  await expect.poll(() => overflowOf(page)).toBeGreaterThan(0);
  const cut = await peekCut(page);
  expect(cut.none, `正好切在缝上,底下那条完全没露(离上一张 ${cut.none ? cut.gap : ''})`).toBe(false);
  if (!cut.none) {
    expect(cut.peek).toBeGreaterThanOrEqual(Math.max(16, cut.h * 0.25));
    expect(cut.peek).toBeLessThanOrEqual(cut.h - Math.max(12, cut.h * 0.25));
  }
});
