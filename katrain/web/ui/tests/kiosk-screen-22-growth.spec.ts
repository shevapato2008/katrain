import { expect, test, type Page } from '@playwright/test';

/**
 * 屏 22 · 成长(§5 **L1 两栏**)—— 真浏览器 1024×600 实测。
 *
 * **这一关是「量」不是「看」。** 四图对比看得见「有没有这几块」,看不见:
 *   · 打过的档一多,那张表**自己能不能滚**(被 `overflow` 裁掉的行在截图上根本不存在);
 *   · 两块诊断会不会把右栏顶破;
 *   · 左栏底下那两格还贴不贴底。
 *
 * 清单先写死关系式再读数:
 *   · L1 外框:左栏 296、右栏 680、中间区 434(一级页有 Dock ⇒ 434,不是 516)
 *   · 该滚的是 `.grungs` **它自己**,不是 `.gcol`(右栏),更不是整页
 *   · 能滚:自己 scrollHeight > clientHeight;**真滚轮**拨得动
 *   · 没被裁:`.gdiag` 的 border box 完整落在中间区裁切框内
 *   · 整屏不滚:`documentElement.scrollHeight <= 600`
 *   · 左栏两格贴底(`.gsec .kiosk-status { margin-top: auto }`)
 *
 * **先把数据造到会溢出** —— 20 档打过的战绩灌进那块一百来像素的面板里。
 * 装得下的数据量下量出来的滚动数字一概不算。
 *
 * **变异记录**(2026-08-25,逐个改坏逐个跑):
 *   M22-a `.grungs` 去掉 `overflow-y: auto`      → 红「右栏被档位表顶破了」
 *   M22-b `.gdiag` 去掉 `flex: 1`                 → 红「两块诊断塌了」
 *   M22-c 左栏两格不再 `margin-top: auto`         → 红「左栏那两格没贴底」
 *   M22-d `DOCK_TABS` 里的路径写错一个字          → 红「中间区不是 434」
 *
 * ⚠️ **M22-a 红的不是我以为的那一条。** 我以为会红在「真滚轮拨不动」上,实际先红在
 * 「右栏被顶破」——不给 `overflow-y` 的话那张表**根本不是滚动容器**,它直接把右栏撑长了,
 * 所以更早的那条断言先命中。滚轮那条守的是另一种坏法(祖先上一个 `touch-action`
 * 就能让它「能滚但拨不动」),两条不重复。
 */

test.use({ viewport: { width: 1024, height: 600 } });

const LADDER_PLACED = {
  view_state: 'ready',
  placement_state: {
    phase: 'placed',
    rung: { rung: 18, rank_name: '3级', certification_status: 'certified', availability: 'available', route: 'local' },
  },
  current_opponent: null,
  recent_ranked_results: ['win', 'loss'],
  net_score: 1,
  pending_settlement: false,
  blocking_game: null,
  provisional_play_allowed: false,
};

/** 20 档战绩 —— 造来会溢出的。档名照 `katrain/core/ladder.py` 的真名字。 */
const MANY_RUNGS = Array.from({ length: 20 }, (_, i) => ({
  rung: 20 - i,
  rank_name: `${i + 1}级`,
  wins: (i * 3) % 7,
  losses: (i * 5) % 4,
}));

const summary = (over: Record<string, unknown> = {}) => ({
  window_days: 30,
  games_in_window: 42,
  ranked_total: 31,
  ranked_wins_in_window: 9,
  ranked_losses_in_window: 5,
  by_opponent_rung: [],
  authority: 'this_node',
  ...over,
});

/**
 * 诊断块**最满**的那一态:三段都有、最弱那段带标记、样本量那句带「另有 N 份没算进来」、
 * 底下还多一句「样本还少」—— 这一块能长出来的每一行都在。
 */
const FULL_DIAGNOSIS = {
  window_days: 90,
  reports: 2,
  skipped_without_color: 3,
  graded_moves: 120,
  phases: [
    { phase: 'opening', graded: 40, bad: 4 },
    { phase: 'midgame', graded: 50, bad: 19 },
    { phase: 'endgame', graded: 30, bad: 5 },
  ],
  authority: 'cloud',
};

/**
 * 诊断块在**盒子离线**时的样子:报告只在云端,本机库里没有逐手数据 ⇒ 退回本机时一定是 0 份,
 * 屏上是「这会儿读不到云端的报告」那个短空态。**所以「本机记录」那句和满载的诊断不会同时出现**
 * —— 这一条决定了右栏真实可达的最满态只有下面 `FULLEST` 那两种。
 */
const OFFLINE_DIAGNOSIS = {
  window_days: 90, reports: 0, skipped_without_color: 0, graded_moves: 0, phases: [], authority: 'local_cache',
};

/** 日历**最满**的那一态:近一年天天都练、而且天天 10 次以上(最深那一档)。日期从今天往前数。 */
const FULL_ACTIVITY = {
  window_days: 365,
  authority: 'local_cache',
  days: Array.from({ length: 365 }, (_, i) => {
    const d = new Date(Date.now() - i * 86_400_000);
    const date = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    return { date, games: 4, solved: 8 };
  }),
};
const EMPTY_ACTIVITY = { window_days: 365, days: [], authority: 'this_node' };

/** 诊断块**最空**的那一态:一份报告都没有。 */
const EMPTY_DIAGNOSIS = {
  window_days: 90, reports: 0, skipped_without_color: 0, graded_moves: 0, phases: [], authority: 'this_node',
};

/**
 * 30 天、天天有一个点的档位走势 —— 左栏能长出来的最长那一版。
 * 日期**从今天往前数**:这份 spec 不冻时钟,而窗口外的点会被丢掉(不画)。
 */
const FULL_TREND = Array.from({ length: 30 }, (_, i) => ({
  date: new Date(Date.now() - (29 - i) * 86_400_000).toISOString().slice(0, 10),
  rung: 16 + (i % 4),
  rank_name: `${5 - (i % 4)}级`,
}));

const stub = async (
  page: Page,
  growth: Record<string, unknown>,
  diagnosis: Record<string, unknown> = EMPTY_DIAGNOSIS,
  activity: Record<string, unknown> = EMPTY_ACTIVITY,
) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'screen-22');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') {
      return route.fulfill({ json: { id: 1, username: '访客', rank: '5段', credits: 0 } });
    }
    if (path === '/api/v1/ai-ladder/status') return route.fulfill({ json: LADDER_PLACED });
    if (path === '/api/v1/growth/summary') return route.fulfill({ json: growth });
    if (path === '/api/v1/growth/diagnosis') return route.fulfill({ json: diagnosis });
    if (path === '/api/v1/growth/activity') return route.fulfill({ json: activity });
    if (path === '/api/v1/tsumego/progress') {
      return route.fulfill({ json: { p1: { problemId: 'p1', completed: true, attempts: 1 } } });
    }
    // 取图机器上没有摄像头 —— 实体识别整条关掉。
    if (path === '/api/v1/vision/status') {
      return route.fulfill({ json: { enabled: false, camera_connected: false, pose_locked: false,
        sync_state: 'unbound', recognition_ready: false, led_connected: null, bound_session_id: null } });
    }
    if (path === '/api/v1/geometry/status') return route.fulfill({ status: 404, json: { detail: 'disabled' } });
    return route.fulfill({ json: {} });
  });
};

const open = async (
  page: Page,
  growth = summary(),
  diagnosis?: Record<string, unknown>,
  activity?: Record<string, unknown>,
) => {
  await stub(page, growth, diagnosis, activity);
  await page.goto('/kiosk/growth');
  await page.waitForSelector('[data-testid="growth-page"]');
  await page.waitForSelector('[data-testid="growth-stats"] .kiosk-stat');
};

test('L1 外框:左栏 296 · 右栏 680 · 中间区 434(有 Dock 的一级页)', async ({ page }) => {
  await open(page);

  const g = await page.evaluate(() => {
    const box = (sel: string) => {
      const r = document.querySelector(sel)!.getBoundingClientRect();
      return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
    };
    return {
      layout: box('[data-testid="growth-page"]'),
      rank: box('[data-testid="growth-rank"]'),
      side: box('.gcol'),
      docScrollHeight: document.documentElement.scrollHeight,
      dockItems: document.querySelectorAll('.kiosk-dock__item').length,
    };
  });
  console.log('[22-growth/geometry]', JSON.stringify(g));

  expect(g.rank.w, '左栏不是 296').toBe(296);
  expect(g.side.w, '右栏不是 680').toBe(680);
  // 一级页有 Dock ⇒ 中间区 434。判成 L2 的话这里会是 516,而 Dock 会被顶出画布。
  expect(g.layout.h, '中间区不是 434 —— 这一屏被判成二级页了').toBe(434);
  expect(g.dockItems, 'Dock 不是七项').toBe(7);
  expect(g.docScrollHeight, '整屏溢出').toBeLessThanOrEqual(600);
});

/**
 * 右栏**真实可达**的两种最满态(在受限高度里加节点,要在它们都在的那一态量):
 *  · 在线:胜率那句提示 + 一年天天练的日历 + 满载的诊断(三段 + 「另有 N 份」+「样本还少」)。
 *  · 离线:两句提示(「本机记录」+ 胜率)+ 本机那份日历 + 诊断的离线空态(见 `OFFLINE_DIAGNOSIS`)。
 * 左栏两态都造到最满:30 天走势块在「升降的规矩」上面,左栏是固定高度的一栏。
 *
 * 2026-09-22 日历加进右栏后,第一次量「最满」(当时把「本机记录」和满载诊断造在了一起)实测
 * 右栏溢出 94px、诊断块最后一句被裁 ⇒ 诊断行距 12→8、样本量三句并成一段、日历本机态只写四个字。
 */
const FULLEST = [
  {
    name: '在线',
    authority: 'cloud',
    diagnosis: FULL_DIAGNOSIS,
    activity: { ...FULL_ACTIVITY, authority: 'cloud' },
    mustShow: ['growth-unknown-seat', 'diag-thin'],
  },
  {
    name: '离线',
    authority: 'local_cache',
    diagnosis: OFFLINE_DIAGNOSIS,
    activity: FULL_ACTIVITY,
    mustShow: ['growth-local-note', 'growth-unknown-seat', 'diag-offline'],
  },
];

for (const c of FULLEST) test(`打过的档一多(${c.name}最满):滚的是那张表自己,右栏不被顶破,两格照旧贴底`, async ({ page }) => {
  await open(page, summary({
    by_opponent_rung: MANY_RUNGS,
    authority: c.authority,
    decided_games_in_window: 30,
    wins_in_window: 17,
    losses_in_window: 13,
    rung_trend: FULL_TREND,
  }), c.diagnosis, c.activity);
  await page.waitForSelector('[data-testid="growth-by-rung"] .grung');
  for (const id of c.mustShow) {
    await expect(page.getByTestId(id), `${c.name}最满那一态没造出来 —— 少了 ${id}`).toBeVisible();
  }
  await expect(page.getByTestId('growth-trend'), '最满那一态没造出来 —— 左栏没画走势').toBeVisible();
  await expect(page.getByTestId('growth-cal-days'), '最满那一态没造出来 —— 日历不是一年天天都练')
    .toHaveText('365');

  const g = await page.evaluate(() => {
    const rungs = document.querySelector('.grungs') as HTMLElement;
    const diag = document.querySelector('.gdiag')!.getBoundingClientRect();
    const layout = document.querySelector('[data-testid="growth-page"]')!.getBoundingClientRect();
    const cells = document.querySelector('.gsec .kiosk-status')!.getBoundingClientRect();
    const rank = document.querySelector('[data-testid="growth-rank"]')!.getBoundingClientRect();
    const side = document.querySelector('.gcol') as HTMLElement;
    return {
      rows: rungs.querySelectorAll('.grung').length,
      overflow: rungs.scrollHeight - rungs.clientHeight,
      sideOverflow: side.scrollHeight - side.clientHeight,
      diagInside: diag.bottom <= layout.bottom + 0.5 && diag.top >= layout.top - 0.5,
      // ⚠️ **不写死数字。**「贴底」的关系式是「两格底 == 左栏**内容框**底」,而
      //   内容框底 = 边框盒底 − padding-bottom − **border-bottom**。
      // 第一版写死 14(只算了 padding),实测 15 —— 差的那 1px 是 `.panel` 自己的边框。
      // **同一个坑屏 26 踩过一次**(折叠块的高度关系式漏了它自己的两条 1px 边框),
      // 所以这两个数都从 `getComputedStyle` 读,不从眼睛读。
      cellsGap: rank.bottom - cells.bottom,
      panelBottomInset: (() => {
        const cs = getComputedStyle(document.querySelector('[data-testid="growth-rank"]') as HTMLElement);
        return parseFloat(cs.paddingBottom) + parseFloat(cs.borderBottomWidth);
      })(),
      docScrollHeight: document.documentElement.scrollHeight,
      // 诊断块:它自己不许被内容撑破,最后一个孩子(在线态是那段样本量、离线态是空态卡)完整落在框里
      diagPanelOverflow: (() => {
        const el = document.querySelector('[data-testid="growth-diagnosis"]') as HTMLElement;
        return el.scrollHeight - el.clientHeight;
      })(),
      diagLastInside: (() => {
        const el = document.querySelector('[data-testid="growth-diagnosis"]') as HTMLElement;
        const panel = el.getBoundingClientRect();
        const last = el.lastElementChild!.getBoundingClientRect();
        return last.bottom <= panel.bottom - parseFloat(getComputedStyle(el).paddingBottom) + 0.5;
      })(),
      // 左栏:走势块加进来之后,整栏不许溢出,「升降的规矩」最后一行要完整落在两格上面
      rankOverflow: (() => {
        const el = document.querySelector('[data-testid="growth-rank"]') as HTMLElement;
        return el.scrollHeight - el.clientHeight;
      })(),
      rulesBottom: document.querySelector('.grules')!.getBoundingClientRect().bottom,
      cellsTop: cells.top,
      trendH: Math.round(document.querySelector('[data-testid="growth-trend"]')!.getBoundingClientRect().height),
      // 日历:整块不被挤扁(它是 flex:none 的 .panel),格子区完整落在日历块的内容框里
      cal: (() => {
        const box = document.querySelector('[data-testid="growth-cal"]') as HTMLElement;
        const grid = box.querySelector('.gcal__grid')!.getBoundingClientRect();
        const b = box.getBoundingClientRect();
        return {
          h: Math.round(b.height),
          overflow: box.scrollHeight - box.clientHeight,
          gridInside: grid.left >= b.left && grid.right <= b.right && grid.top >= b.top && grid.bottom <= b.bottom,
          cols: box.querySelectorAll('.gcal__grid > i').length / 7,
        };
      })(),
    };
  });
  console.log('[22-growth/overflow]', JSON.stringify(g));

  expect(g.rows, '20 档没全渲染出来').toBe(20);
  // ① 该滚的是它自己,而且真的装不下
  expect(g.overflow, '档位表没溢出 —— 数据没造够,这一轮量出来的数一概不算').toBeGreaterThan(0);
  // ② 右栏不许被顶破:会长的那一块吃掉的是**自己**的高度
  expect(g.sideOverflow, '右栏被档位表顶破了').toBeLessThanOrEqual(0);
  // ③ 没被裁
  expect(g.diagInside, '两块诊断被中间区裁掉了一截').toBe(true);
  // ④ 左栏两格贴底 —— 靠 `.gsec .kiosk-status { margin-top: auto }`。
  expect(g.cellsGap, '左栏那两格没贴底').toBeCloseTo(g.panelBottomInset, 1);
  expect(g.docScrollHeight, '整屏溢出').toBeLessThanOrEqual(600);
  // ⑥ 诊断块最满时不被撑破,最后一句完整在框里
  expect(g.diagPanelOverflow, '诊断块被内容撑破了').toBeLessThanOrEqual(0);
  expect(g.diagLastInside, '诊断块最后那一句被裁掉了').toBe(true);
  // ⑧ 日历:53 列不被右栏裁掉、块本身不溢出
  expect(g.cal.overflow, '日历块被内容撑破了').toBeLessThanOrEqual(0);
  expect(g.cal.gridInside, '日历的格子区被裁掉了一截').toBe(true);
  // ⑦ 左栏加了走势之后不溢出,规矩最后一行在两格之上
  expect(g.rankOverflow, '左栏被走势块撑破了').toBeLessThanOrEqual(0);
  expect(g.rulesBottom, '「升降的规矩」被挤到两格下面去了').toBeLessThanOrEqual(g.cellsTop);

  // ⑤ 程序化能滚
  const wrote = await page.evaluate(() => {
    const r = document.querySelector('.grungs') as HTMLElement;
    r.scrollTop = 9999;
    return r.scrollTop;
  });
  expect(wrote, '写了 scrollTop 读回来还是 0 —— 这块不是滚动容器').toBeGreaterThan(0);

  // ⑥ **手指拨得动** —— 程序化能滚 ≠ 拨得动。
  // `expect.poll` 不是保险起见:Chromium 的滚轮滚动是异步的,派完立刻读拿到的还是旧值。
  await page.evaluate(() => { (document.querySelector('.grungs') as HTMLElement).scrollTop = 0; });
  const rungs = page.locator('.grungs');
  const bb = (await rungs.boundingBox())!;
  await page.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
  await page.mouse.wheel(0, 300);
  await expect.poll(() => rungs.evaluate((el) => el.scrollTop),
    { message: '档位表真滚轮拨不动 —— 后面几档翻不到' }).toBeGreaterThan(0);
});

/**
 * 最空的那一态。**这一次先算过自由空间再写断言**(上一屏的教训:右栏只剩 2px 时,
 * 任何断言都分不出东西来)。右栏 434 高,数据条 72 + 缝 12 + 日历约 109 + 缝 12 是固定的 ⇒
 * `.gdiag` 拿得到 **230** 左右,塌成内容高(一句话 + 一颗按钮)是一百出头,分得开。
 * 2026-09-22 日历加进来之前这里写死「> 300」—— 那是没有日历时的数,**闸跟着布局过期了**;
 * 改成关系式:诊断吃掉「日历底到中间区底」的全部高度。
 */
test('一档都没打过:空态说话,两块诊断照旧吃掉右栏剩下的高度', async ({ page }) => {
  await open(page);

  // 诊断块也取最空那一态(一份报告都没有 ⇒ 只有一句话 + 一颗「去复盘」)。
  await expect(page.getByTestId('diag-empty')).toBeVisible();

  const g = await page.evaluate(() => {
    const diag = document.querySelector('.gdiag')!.getBoundingClientRect();
    const layout = document.querySelector('[data-testid="growth-page"]')!.getBoundingClientRect();
    const [a, b] = Array.from(document.querySelectorAll('.gdiag > .panel'))
      .map((el) => Math.round(el.getBoundingClientRect().height));
    const cal = document.querySelector('[data-testid="growth-cal"]')!.getBoundingClientRect();
    return {
      diagPanels: [a, b],
      calBottom: cal.bottom,
      gap: parseFloat(getComputedStyle(document.querySelector('.gcol') as HTMLElement).rowGap),
      text: document.querySelector('[data-testid="growth-by-rung"]')!.textContent ?? '',
      diagH: Math.round(diag.height),
      diagBottom: Math.round(diag.bottom),
      layoutBottom: Math.round(layout.bottom),
      docScrollHeight: document.documentElement.scrollHeight,
    };
  });
  console.log('[22-growth/empty]', JSON.stringify(g));

  expect(g.text, '一档没打过时那块是白的 —— 空态得自己说话').toContain('还没有战绩');
  // 关系式:`.gdiag` 要吃掉右栏在日历之下的**全部**剩余高度。
  expect(g.diagH, '两块诊断塌了 —— flex:1 没生效').toBeCloseTo(g.layoutBottom - g.calBottom - g.gap, 0);
  expect(g.diagBottom, '两块诊断没贴到中间区底').toBe(g.layoutBottom);
  // 内容最少的诊断块照样吃满那一行 —— 塌成内容高时两块会一高一矮。
  expect(Math.abs(g.diagPanels[0] - g.diagPanels[1]), '诊断块塌成了内容高').toBeLessThanOrEqual(1);
  expect(g.docScrollHeight, '整屏溢出').toBeLessThanOrEqual(600);
});
