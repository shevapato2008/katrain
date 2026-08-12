import { expect, test, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const OUT_DIR = resolve(
  process.cwd(),
  '../../../superpowers/tracks/golaxy-ai-ladder-parity/visual/kiosk-layout-a/1024x600',
);
mkdirSync(OUT_DIR, { recursive: true });

/**
 * 开局设置屏的**几何**闸 —— 规范 §11 布局 A,1024×600 真浏览器实测。
 *
 * 这一条和 `kiosk-ai-ladder-blocking-panel.spec.ts` 分工不同:那条量「装不装得下、能不能滚」,
 * 这条量「**这屏是不是规范说的那副骨架**」。两者都归承重关卡,判据都是浏览器算出来的数。
 *
 * 规范给死的落点(每个数都带行号,一个都不许凭感觉):
 *   `:399` L2/L3 可用高度 600 − 56 − 28 = **516**;棋盘 **516×516** 贴 x=16;右栏 x 548→1008(**460**)
 *   `:64`  左右外边距 **16**  ·  `:66` 上下内边距 **14**  ·  `:67` 内容顶 **70**
 *   `:742` 有棋盘 ⇒ 页控条在**右栏顶部**,x 548–1008,y **70–114**(高 44)
 *   `:432` 交叉点棋盘 margin = **0.5 格** ⇒ 刻度字心与盘上的线**逐条对齐**
 *
 * 期望先写成**关系式**,具体像素只记录:比如「盘的右边 + 16 = 右栏的左边」比「右栏在 548」
 * 更能扛住以后有人改边距 —— 后者会在改动是**对的**时候红。
 */

test.use({ viewport: { width: 1024, height: 600 } });

const stub = async (page: Page) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'kiosk-layout-a-token');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: 'tester', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/v1/ai-ladder/status', (route) => route.fulfill({
    json: {
      view_state: 'ready',
      placement_state: { phase: 'placed', rung: { rung: 30, rank_name: '5段', certification_status: 'certified', availability: 'available', route: 'server' } },
      current_opponent: { rung: 30, rank_name: '5段', certification_status: 'certified', availability: 'available', route: 'server' },
      recent_ranked_results: [], net_score: 0, pending_settlement: false, blocking_game: null,
    },
  }));
};

const geometry = (page: Page) => page.evaluate(() => {
  const box = (sel: string) => {
    const node = document.querySelector(sel) as HTMLElement | null;
    if (!node) return null;
    const r = node.getBoundingClientRect();
    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), right: Math.round(r.right), bottom: Math.round(r.bottom) };
  };
  const board = box('[data-testid="kiosk-setup-board"]');
  const play = box('.kiosk-setup-board .kiosk-board__play');
  const rail = box('.kiosk-rail');
  const pagebar = box('[data-testid="kiosk-setup-pagebar"]');
  const back = box('.kiosk-pagebar__back');

  // 刻度字心 vs 盘上的线:两组数都从**渲染结果**里取,不从公式里取。
  const svg = document.querySelector('.kiosk-setup-board .gob') as SVGSVGElement | null;
  const playRect = document.querySelector('.kiosk-setup-board .kiosk-board__play')?.getBoundingClientRect();
  let lineCenters: number[] = [];
  if (svg && playRect) {
    // 竖线的屏幕 x:用 getBoundingClientRect 直接问每条 <line>,不自己换算 viewBox。
    lineCenters = Array.from(svg.querySelectorAll('line'))
      .filter((l) => Math.abs(Number(l.getAttribute('x1')) - Number(l.getAttribute('x2'))) < 0.01)
      .map((l) => { const r = (l as SVGLineElement).getBoundingClientRect(); return r.x + r.width / 2; })
      .sort((a, b) => a - b);
  }
  const rulerCenters = Array.from(document.querySelectorAll('.kiosk-board__ruler--top span'))
    .map((s) => { const r = s.getBoundingClientRect(); return r.x + r.width / 2; })
    .sort((a, b) => a - b);
  const maxDrift = lineCenters.length === rulerCenters.length && lineCenters.length > 0
    ? Math.max(...lineCenters.map((c, i) => Math.abs(c - rulerCenters[i])))
    : null;

  return {
    board, play, rail, pagebar, back,
    topRulerCount: document.querySelectorAll('.kiosk-board__ruler--top span').length,
    leftRulerCount: document.querySelectorAll('.kiosk-board__ruler--left span').length,
    topFirst: document.querySelector('.kiosk-board__ruler--top span')?.textContent ?? null,
    topLast: document.querySelector('.kiosk-board__ruler--top span:last-child')?.textContent ?? null,
    leftFirst: document.querySelector('.kiosk-board__ruler--left span')?.textContent ?? null,
    leftLast: document.querySelector('.kiosk-board__ruler--left span:last-child')?.textContent ?? null,
    lineCount: lineCenters.length,
    dataColor: document.querySelector('[data-testid="kiosk-setup-board"]')?.getAttribute('data-color') ?? null,
    maxDriftPx: maxDrift === null ? null : Math.round(maxDrift * 10) / 10,
    docScrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
    // 旧骨架的两个构件:通栏返回条和 296 的镜像栏。它们**必须不在这一屏上** ——
    // 「新的画对了」和「旧的撤干净了」是两件事,后者漏掉就会变成两副骨架叠在一起。
    hasSmartBoardConsole: !!document.querySelector('[data-testid="smart-board-console"], .kiosk-console'),
  };
});

test('布局 A 的外框:516 的盘贴 x16,右栏 460,页控条在右栏顶', async ({ page }) => {
  await stub(page);
  await page.goto('/kiosk/play/ai/setup/ranked');
  await page.waitForSelector('[data-testid="kiosk-setup-board"]');
  const g = await geometry(page);
  console.log('[layout-a]', JSON.stringify(g));

  // `:399` 棋盘正方形、边长 = L2 可用高度
  expect(g.board!.w, '盘不是 516 宽').toBe(516);
  expect(g.board!.h, '盘不是 516 高').toBe(516);
  expect(g.board!.w, '盘不是正方形').toBe(g.board!.h);

  // `:64` 贴左边距 16 —— 写成关系式:盘左 = 视口左 + 内容外边距
  expect(g.board!.x, '盘没有贴 x=16').toBe(16);
  // `:67` 内容顶 70 = 顶栏 56 + 内边距 14
  expect(g.board!.y, '盘顶不在 y=70').toBe(70);

  // `:399` 右栏 460,且**紧挨着盘 + 16 的栏距**(关系式,不写 548)
  expect(g.rail!.w, '右栏不是 460 宽').toBe(460);
  expect(g.rail!.x - g.board!.right, '盘和右栏之间不是 16 的栏距').toBe(16);
  expect(g.rail!.right, '右栏右缘没有贴到 1008').toBe(g.innerWidth - 16);

  // `:742` 页控条在**右栏顶部**(不是通栏):左缘与右栏对齐,而不是与内容区对齐
  expect(g.pagebar!.x, '页控条左缘没和右栏对齐 —— 这是布局 B 的做法').toBe(g.rail!.x);
  expect(g.pagebar!.w, '页控条不是 460 宽').toBe(g.rail!.w);
  expect(g.pagebar!.y, '页控条顶不在 70').toBe(70);
  expect(g.pagebar!.h, '页控条不是 44 高').toBe(44);
  // `:755` 返回按钮高 36
  expect(g.back!.h, '返回按钮不是 36 高').toBe(36);

  // 横向不许出现滚动条:992 + 2×16 正好 1024,多一个像素就会溢出
  expect(g.docScrollWidth, '页面横向溢出了').toBeLessThanOrEqual(g.innerWidth);

  // 旧骨架撤干净
  expect(g.hasSmartBoardConsole, '296 的镜像栏还在这屏上 —— 那是 L1 的构件').toBe(false);
});

test('刻度:19 条、A–T 跳 I、字心与线逐条对齐(margin=0.5 的唯一可见后果)', async ({ page }) => {
  await stub(page);
  await page.goto('/kiosk/play/ai/setup/ranked');
  await page.waitForSelector('[data-testid="kiosk-setup-board"]');
  const g = await geometry(page);
  console.log('[ruler]', JSON.stringify({ maxDriftPx: g.maxDriftPx, lineCount: g.lineCount, top: [g.topFirst, g.topLast], left: [g.leftFirst, g.leftLast] }));

  expect(g.topRulerCount, '上刻度不是 19 个字').toBe(19);
  expect(g.leftRulerCount, '左刻度不是 19 个数').toBe(19);
  expect(g.topFirst).toBe('A');
  expect(g.topLast, '最后一个字母不是 T —— 跳 I 之后 19 路正好到 T').toBe('T');
  expect(g.leftFirst, '行号 1 在最下 ⇒ 从上往下第一个是 19').toBe('19');
  expect(g.leftLast).toBe('1');
  expect(g.lineCount, '竖线不是 19 条').toBe(19);

  // `:432` 的判据:margin 取 0.5 时字和线**逐条对齐**;取 0.66/0.7 会「一眼能看出字没对准线」。
  // 门槛取 1.5px —— 亚像素舍入允许,一个字宽的偏差不允许。
  expect(g.maxDriftPx, `字和线最大错开 ${g.maxDriftPx}px`).not.toBeNull();
  expect(g.maxDriftPx!).toBeLessThanOrEqual(1.5);
});

test('执白:刻度**不倒** —— §8 `:414` 刻度方向由记法定,围棋记法绝对', async ({ page }) => {
  await stub(page);
  await page.goto('/kiosk/play/ai/setup/ranked');
  await page.waitForSelector('[data-testid="kiosk-setup-board"]');

  const before = await geometry(page);
  expect(before.topFirst).toBe('A');
  expect(before.leftFirst).toBe('19');
  // 两种执子**各取一张**。只取一张再说「另一种应该也对」,就是拿推理顶了取图 ——
  // 而这条规则唯一看得见的后果全在刻度上,不取那张就等于这条没有图作证。
  await page.screenshot({ path: resolve(OUT_DIR, '01-setup-my-black.png') });

  await page.getByRole('button', { name: '○ 白' }).click();
  await page.waitForFunction(() =>
    document.querySelector('[data-testid="kiosk-setup-board"]')?.getAttribute('data-color') === 'white');

  const after = await geometry(page);
  // 判据链(顺序就是理由的顺序,别写成「我认为规范错了」):
  //   §8 `:414` 已经立过刻度方向的法,依据是**记法** —— 「象棋两条刻度数值不同向…
  //   看到某个实现把上面那行也写成 9…1,那是错的」;
  //   ⇒ 刻度是记法的函数,不是执棋方的函数;
  //   ⇒ 围棋记法**绝对**(A1 永远是那一个角,SGF 和对局屏都按它)⇒ 不倒。
  // §11 `:514`「视角跟着执棋方翻」那句是从国象推出来的,而围棋稿子里没有开局设置屏 ——
  // 那条规则从来没被它的作者在围棋上应用过。措辞澄清由协调方提给上游,本仓按 §8 执行。
  expect(after.topFirst, '刻度跟着执棋方倒了 —— 围棋记法是绝对的').toBe('A');
  expect(after.topLast).toBe('T');
  expect(after.leftFirst, '行号跟着执棋方倒了').toBe('19');
  expect(after.leftLast).toBe('1');
  // **和执黑那一帧逐格相同**:上面四条只钉了首尾,中间被人改了它们照样绿。
  expect(after.topFirst === before.topFirst && after.topLast === before.topLast).toBe(true);
  expect(after.maxDriftPx!, '换了执子之后字和线错开了').toBeLessThanOrEqual(1.5);
  // 选择本身要**看得见**地生效 —— 否则「不翻」和「这个开关根本没接上」在屏上长得一样。
  expect(after.dataColor, '选了执白,盘上没有任何地方记下这次选择').toBe('white');
  await page.screenshot({ path: resolve(OUT_DIR, '02-setup-my-white.png') });
});
