import { expect, test, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

type BlockingState = 'active' | 'pending_settlement';
type Ownership = 'current_device' | 'other_device';

const repositoryRoot = resolve(process.cwd(), '../../..');
const evidenceRoot = resolve(
  repositoryRoot,
  'superpowers/tracks/galaxy-ai-ladder-journey/visual/active-game',
);
const referenceHtml = resolve(evidenceRoot, 'reference.html');
const logoPath = resolve(repositoryRoot, 'katrain/img/logo-white.png');

const statusFor = (state: BlockingState, ownership: Ownership) => ({
  view_state: 'ready',
  placement_state: {
    phase: 'placed',
    rung: {
      rung: 30,
      rank_name: '5段',
      certification_status: 'certified',
      availability: 'available',
      route: 'server',
    },
  },
  current_opponent: {
    rung: 17,
    rank_name: '4级',
    certification_status: 'certified',
    availability: 'available',
    route: 'server',
  },
  recent_ranked_results: ['win', 'loss', 'win', 'win', 'loss'],
  net_score: 1,
  pending_settlement: state === 'pending_settlement',
  blocking_game: {
    game_id: 'occupied-game',
    state,
    ownership,
    ...(state === 'active' && ownership === 'current_device' ? { session_id: 'occupied-session' } : {}),
    user_color: 'B',
    opponent_rank_name: '4级',
  },
});

const routeGalaxyRuntime = async (page: Page, state: BlockingState, ownership: Ownership) => {
  const endRequests: unknown[] = [];
  let currentState = state;
  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: 'tester', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/translations?lang=cn', (route) => route.fulfill({ json: {
    lang: 'cn',
    translations: {
      Home: '首页', 'btn:Play': '对局', Research: '研究', Tsumego: '死活题',
      'analysis:report': '复盘', Live: '直播', 'kifu:library': '棋谱库', Tutorials: '教程',
      Settings: '设置', Logout: '退出登录', More: '更多',
    },
  } }));
  await page.route('**/api/v1/live/translations?lang=cn', (route) => route.fulfill({
    json: { players: {}, tournaments: {}, rounds: {}, rules: {} },
  }));
  await page.route('**/assets/img/logo-white.png', (route) => route.fulfill({ path: logoPath }));
  await page.route('**/api/v1/ai-ladder/status', (route) => route.fulfill({ json: statusFor(currentState, ownership) }));
  await page.route('**/api/v1/ai-ladder/games/occupied-game/end', async (route) => {
    endRequests.push(route.request().postDataJSON());
    currentState = 'pending_settlement';
    await route.fulfill({
      json: { state: 'pending_settlement', game_id: 'occupied-game' },
    });
  });
  return endRequests;
};

const activeGameScrollerMetrics = async (page: Page, scrollToEnd = false) => {
  const heading = page.getByRole('heading', { name: '升降级对弈' });
  return heading.evaluate((element, shouldScroll) => {
    let candidate = element.parentElement;
    while (candidate) {
      const overflowY = getComputedStyle(candidate).overflowY;
      if (['auto', 'scroll'].includes(overflowY)) break;
      candidate = candidate.parentElement;
    }
    if (!candidate) throw new Error('Galaxy active-game content scroller was not found from the page heading');
    if (shouldScroll) candidate.scrollTop = candidate.scrollHeight;
    return {
      clientWidth: candidate.clientWidth,
      scrollWidth: candidate.scrollWidth,
    };
  }, scrollToEnd);
};

const expectActiveGameScrollerNoHorizontalOverflow = async (page: Page) => {
  const metrics = await activeGameScrollerMetrics(page);
  expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.clientWidth);
};

const scrollActiveGameToActions = async (page: Page) => {
  await activeGameScrollerMetrics(page, true);
  await page.waitForTimeout(100);
};

const expectActionReachable = async (page: Page, buttonName: string) => {
  const action = page.getByRole('button', { name: buttonName });
  const actionBox = await action.boundingBox();
  expect(actionBox).not.toBeNull();
  expect(actionBox!.y).toBeGreaterThanOrEqual(0);
  expect(actionBox!.y + actionBox!.height).toBeLessThanOrEqual(page.viewportSize()!.height);

  const bottomNav = page.getByTestId('galaxy-bottom-nav');
  if (await bottomNav.count()) {
    const navBox = await bottomNav.boundingBox();
    expect(navBox).not.toBeNull();
    expect(actionBox!.y + actionBox!.height).toBeLessThanOrEqual(navBox!.y);
  }
};

const createComposite = async (
  page: Page,
  referencePath: string,
  implementationPath: string,
  outputPath: string,
  mode: 'comparison' | 'overlay',
  viewport: { width: number; height: number },
) => {
  const [reference, implementation] = await Promise.all([
    readFile(referencePath, 'base64'),
    readFile(implementationPath, 'base64'),
  ]);
  const width = mode === 'comparison' ? viewport.width * 2 : viewport.width;
  await page.setViewportSize({ width, height: viewport.height });
  await page.setContent(`<!doctype html><html><head><style>
    * { box-sizing: border-box } html,body { margin:0; width:100%; height:100%; overflow:hidden; background:#090909 }
    .frame { position:absolute; inset:0; width:${viewport.width}px; height:${viewport.height}px }
    img { display:block; width:${viewport.width}px; height:${viewport.height}px; object-fit:contain }
    .right { left:${viewport.width}px }
    .overlay { opacity:.5 }
  </style></head><body>
    <div class="frame"><img src="data:image/png;base64,${reference}" /></div>
    <div class="frame ${mode === 'comparison' ? 'right' : 'overlay'}"><img src="data:image/png;base64,${implementation}" /></div>
  </body></html>`);
  await page.evaluate(() => Promise.all([...document.images].map((img) => img.decode())));
  await page.screenshot({ path: outputPath });
};

for (const scenario of [
  { viewport: { width: 1440, height: 900 }, ownership: 'other_device' as const, primary: '等待结算' },
  { viewport: { width: 430, height: 880 }, ownership: 'current_device' as const, primary: '继续对局' },
]) {
  test(`Galaxy 未完成升降级对局 ${scenario.viewport.width}x${scenario.viewport.height}`, async ({ page }) => {
    const sizeName = `${scenario.viewport.width}x${scenario.viewport.height}`;
    const targetDir = resolve(evidenceRoot, sizeName);
    const referencePath = resolve(targetDir, 'reference.png');
    const implementationPath = resolve(targetDir, 'implementation.png');
    const endRequests = await routeGalaxyRuntime(page, 'active', scenario.ownership);

    await page.setViewportSize(scenario.viewport);
    await page.route('**/__active-game-reference**', (route) => route.fulfill({
      path: referenceHtml,
      contentType: 'text/html; charset=utf-8',
    }));
    await page.goto(`/__active-game-reference?state=${scenario.ownership}`);
    await page.waitForFunction(() => document.documentElement.dataset.ready === 'true');
    await page.evaluate(() => document.fonts.ready);
    await expectActiveGameScrollerNoHorizontalOverflow(page);
    if (scenario.viewport.width < 600) await scrollActiveGameToActions(page);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: referencePath });

    await page.goto('/galaxy/play/ai?mode=rated');
    await page.evaluate(() => document.fonts.ready);
    await expect(page.getByRole('heading', { name: '升降级对弈' })).toBeVisible();
    await expect(page.getByRole('button', { name: '返回对局' })).toBeVisible();
    await expect(page.getByAltText('智星盒 StellaBox')).toBeVisible();
    await expect(page.getByText(scenario.ownership === 'current_device' ? '当前设备' : '其他设备', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: scenario.primary })).toBeVisible();
    await expect(page.getByRole('button', { name: '结束该对局' })).toBeVisible();
    if (scenario.ownership === 'current_device') {
      await expect(page.getByText('你有一局正式对局尚未结束。')).toBeVisible();
    }
    await expectActiveGameScrollerNoHorizontalOverflow(page);
    if (scenario.viewport.width < 600) await scrollActiveGameToActions(page);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const endButton = page.getByRole('button', { name: '结束该对局' });
    expect((await endButton.boundingBox())?.height).toBeGreaterThanOrEqual(44);
    if (scenario.viewport.width < 600) {
      await expectActionReachable(page, scenario.primary);
      await expectActionReachable(page, '结束该对局');
    }
    await page.screenshot({ path: implementationPath });

    await endButton.click();
    const dialog = page.getByRole('dialog', { name: '结束该对局？' });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText('结束后将按你认输处理，并计为本局负。此操作不可撤销。', { exact: true })).toBeVisible();
    await dialog.getByRole('button', { name: '确认结束' }).click();
    await expect.poll(() => endRequests).toEqual([{ reason: 'user_resigned' }]);
    await expect(page.getByRole('button', { name: '刷新状态' })).toBeVisible();
    await expect(page.getByRole('button', { name: '结束该对局' })).toHaveCount(0);

    await createComposite(page, referencePath, implementationPath, resolve(targetDir, 'comparison.png'), 'comparison', scenario.viewport);
    await createComposite(page, referencePath, implementationPath, resolve(targetDir, 'overlay.png'), 'overlay', scenario.viewport);
  });
}

test('Galaxy 待结算状态仅允许刷新', async ({ page }) => {
  await page.setViewportSize({ width: 430, height: 880 });
  await routeGalaxyRuntime(page, 'pending_settlement', 'current_device');
  await page.goto('/galaxy/play/ai?mode=rated');
  await expect(page.getByRole('heading', { name: '升降级对弈' })).toBeVisible();
  await expect(page.getByRole('button', { name: '返回对局' })).toBeVisible();
  await expect(page.getByText('本局已结束，成绩正在结算中。')).toBeVisible();
  await expect(page.getByRole('button', { name: '刷新状态' })).toBeVisible();
  await expect(page.getByRole('button', { name: '结束该对局' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '继续对局' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '等待结算' })).toHaveCount(0);
  await expectActiveGameScrollerNoHorizontalOverflow(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
