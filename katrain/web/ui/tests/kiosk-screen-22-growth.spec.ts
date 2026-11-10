import { expect, test, type Page } from '@playwright/test';

/** 1024×600 的真实浏览器检查：概览、能力诊断、对手三标签各自占用同一右栏。 */

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

test('概览: 53×7 日历、今天的位置与栏内几何', async ({ page }) => {
  await open(page, summary({ rung_trend: FULL_TREND }), FULL_DIAGNOSIS,
    { ...FULL_ACTIVITY, authority: 'cloud' });
  await expect(page.getByTestId('growth-cal-days')).toHaveText('365');

  const g = await page.evaluate(() => {
    const rank = document.querySelector('[data-testid="growth-rank"]') as HTMLElement;
    const cal = document.querySelector('[data-testid="growth-cal"]') as HTMLElement;
    const grid = cal.querySelector('.gcal__grid') as HTMLElement;
    const cells = Array.from(grid.children);
    const date = new Date();
    const today = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    const index = cells.findIndex((cell) => cell.getAttribute('data-date') === today);
    const calRect = cal.getBoundingClientRect();
    const gridRect = grid.getBoundingClientRect();
    const footer = rank.querySelector('.kiosk-status')!.getBoundingClientRect();
    const rankRect = rank.getBoundingClientRect();
    const rankStyle = getComputedStyle(rank);
    return {
      cells: cells.length,
      todayIndex: index,
      weekday: (date.getDay() + 6) % 7,
      todayMarked: index >= 0 && cells[index].classList.contains('is-today'),
      futureVoids: cells.slice(index + 1).every((cell) => cell.classList.contains('is-void')),
      monthColumns: Array.from(cal.querySelectorAll('.gcal__months > [data-week]'))
        .map((node) => Number(node.getAttribute('data-week'))),
      gridInside: gridRect.left >= calRect.left && gridRect.right <= calRect.right && gridRect.bottom <= calRect.bottom,
      calOverflow: cal.scrollHeight - cal.clientHeight,
      rankOverflow: rank.scrollHeight - rank.clientHeight,
      footerGap: rankRect.bottom - footer.bottom,
      expectedFooterGap: parseFloat(rankStyle.paddingBottom) + parseFloat(rankStyle.borderBottomWidth),
      documentHeight: document.documentElement.scrollHeight,
    };
  });
  expect(g.cells).toBe(53 * 7);
  expect(g.todayIndex).toBe(52 * 7 + g.weekday);
  expect(g.todayMarked).toBe(true);
  expect(g.futureVoids).toBe(true);
  expect(g.monthColumns.length).toBeGreaterThanOrEqual(11);
  expect(g.monthColumns).toEqual([...g.monthColumns].sort((a, b) => a - b));
  expect(g.gridInside).toBe(true);
  expect(g.calOverflow).toBeLessThanOrEqual(0);
  expect(g.rankOverflow).toBeLessThanOrEqual(0);
  expect(g.footerGap).toBeCloseTo(g.expectedFooterGap, 1);
  expect(g.documentHeight).toBeLessThanOrEqual(600);
});

test('概览本机缓存与未计胜率同时出现时，两条说明都在可见区域', async ({ page }) => {
  await open(page, summary({
    authority: 'local_cache',
    games_in_window: 42,
    decided_games_in_window: 30,
    wins_in_window: 17,
    losses_in_window: 13,
    rung_trend: FULL_TREND,
  }), OFFLINE_DIAGNOSIS, FULL_ACTIVITY);
  await expect(page.getByTestId('growth-local-note')).toContainText('本机记录');
  await expect(page.getByTestId('growth-unknown-seat')).toContainText('12');
  const visible = await page.evaluate(() => {
    const notes = document.querySelector('.growth-overview-notes')!.getBoundingClientRect();
    const local = document.querySelector('[data-testid="growth-local-note"]')!.getBoundingClientRect();
    const unknown = document.querySelector('[data-testid="growth-unknown-seat"]')!.getBoundingClientRect();
    const help = document.querySelector('[data-testid="growth-unknown-seat"] .growth-help')!.getBoundingClientRect();
    return local.top >= notes.top && unknown.bottom <= notes.bottom && help.top >= notes.top
      && help.bottom <= notes.bottom && help.left >= local.right + 8;
  });
  expect(visible).toBe(true);
});

test('旧版摘要的升降级胜率标签完整留在统计卡里', async ({ page }) => {
  await open(page, summary());
  const label = page.getByTestId('growth-stats').locator('.kiosk-stat__k').nth(1);
  await expect(label).toContainText('升降级胜率 · 近 30 天');
  const fits = await label.evaluate((element) => {
    const card = element.closest('.kiosk-stat')!.getBoundingClientRect();
    const rect = element.getBoundingClientRect();
    return rect.right <= card.right && rect.bottom <= card.bottom
      && element.scrollWidth <= element.clientWidth;
  });
  expect(fits).toBe(true);
});

test('能力诊断: 三段与样本量只在所选标签显示', async ({ page }) => {
  await open(page, summary(), FULL_DIAGNOSIS);
  await page.getByRole('tab', { name: '能力诊断' }).click();
  await expect(page.getByTestId('growth-diagnosis')).toBeVisible();
  await expect(page.getByTestId('diag-row')).toHaveCount(3);
  await expect(page.getByTestId('diag-sample')).toContainText('120');
  await expect(page.getByTestId('growth-cal')).toHaveCount(0);
  const inside = await page.evaluate(() => {
    const rail = document.querySelector('.gcol')!.getBoundingClientRect();
    const panel = document.querySelector('[data-testid="growth-diagnosis"]')!.getBoundingClientRect();
    return panel.top >= rail.top && panel.bottom <= rail.bottom && panel.right <= rail.right;
  });
  expect(inside).toBe(true);
});

for (const authority of ['cloud', 'local_cache'] as const) {
  test(`对手标签 (${authority}): 20 档只在列表内滚动`, async ({ page }) => {
    await open(page, summary({
      authority,
      by_opponent_rung: MANY_RUNGS,
      rung_trend: FULL_TREND,
    }), authority === 'cloud' ? FULL_DIAGNOSIS : OFFLINE_DIAGNOSIS);
    await page.getByRole('tab', { name: '对手' }).click();
    await expect(page.locator('.grung')).toHaveCount(20);
    await expect(page.getByTestId('growth-cal')).toHaveCount(0);
    if (authority === 'local_cache') {
      await expect(page.getByTestId('growth-opponents-local')).toContainText('本机记录');
      await expect(page.getByTestId('growth-opponents-local')).toContainText('可能还有几局');
    } else {
      await expect(page.getByTestId('growth-opponents-local')).toHaveCount(0);
    }

    const g = await page.evaluate(() => {
      const list = document.querySelector('.grungs') as HTMLElement;
      const rail = document.querySelector('.gcol') as HTMLElement;
      const panel = document.querySelector('[data-testid="growth-by-rung"]')!.getBoundingClientRect();
      const railRect = rail.getBoundingClientRect();
      return {
        listOverflow: list.scrollHeight - list.clientHeight,
        railOverflow: rail.scrollHeight - rail.clientHeight,
        panelInside: panel.top >= railRect.top && panel.bottom <= railRect.bottom,
        documentHeight: document.documentElement.scrollHeight,
      };
    });
    expect(g.listOverflow).toBeGreaterThan(0);
    expect(g.railOverflow).toBeLessThanOrEqual(0);
    expect(g.panelInside).toBe(true);
    expect(g.documentHeight).toBeLessThanOrEqual(600);

    const list = page.locator('.grungs');
    const box = (await list.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.wheel(0, 300);
    await expect.poll(() => list.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
  });
}

test('本机缓存无对手战绩时说明云端可能还有', async ({ page }) => {
  await open(page, summary({ authority: 'local_cache', by_opponent_rung: [] }));
  await page.getByRole('tab', { name: '对手' }).click();
  await expect(page.getByTestId('growth-rung-local-empty')).toContainText('本机暂无战绩');
  await expect(page.getByTestId('growth-rung-local-empty')).toContainText('云端可能还有');
  await expect(page.getByText('还没有战绩')).toHaveCount(0);
});
