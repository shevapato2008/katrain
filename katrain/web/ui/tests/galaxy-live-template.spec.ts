import { expect, test, type Locator, type Page } from '@playwright/test';

const matchId = process.env.GALAXY_LIVE_MATCH_ID ?? 'yike_184016';
const livePath = `/galaxy/live/${matchId}`;

const targets = [
  { width: 1535, height: 900, rail: 340, sidebar: 216, mode: 'horizontal' },
  { width: 1536, height: 900, rail: 380, sidebar: 240, mode: 'horizontal' },
  { width: 1537, height: 900, rail: 380, sidebar: 240, mode: 'horizontal' },
  { width: 1440, height: 900, rail: 340, sidebar: 216, mode: 'horizontal' },
  { width: 1201, height: 800, rail: 340, sidebar: 216, mode: 'horizontal' },
  { width: 1200, height: 800, rail: 340, sidebar: 216, mode: 'horizontal' },
  { width: 1199, height: 800, rail: 320, sidebar: 0, mode: 'horizontal' },
  { width: 1024, height: 768, rail: 320, sidebar: 0, mode: 'horizontal' },
  { width: 901, height: 700, rail: 320, sidebar: 0, mode: 'horizontal' },
  { width: 900, height: 700, rail: 320, sidebar: 0, mode: 'horizontal' },
  { width: 899, height: 700, rail: null, sidebar: 0, mode: 'vertical' },
  { width: 430, height: 880, rail: null, sidebar: 0, mode: 'vertical' },
] as const;

const rect = async (locator: Locator) => {
  const value = await locator.boundingBox();
  expect(value).not.toBeNull();
  return {
    ...value!,
    left: value!.x,
    top: value!.y,
    right: value!.x + value!.width,
    bottom: value!.y + value!.height,
  };
};

async function openLive(page: Page, width: number, height: number) {
  await page.setViewportSize({ width, height });
  await page.goto(livePath);
  await expect(page.getByTestId('board-page-shell')).toBeVisible({ timeout: 30_000 });
  const canvas = page.getByTestId('board-stage').locator('canvas');
  await expect(canvas).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(250);
  return canvas;
}

async function useChinese(page: Page) {
  await page.addInitScript(() => localStorage.setItem('katrain_language', 'cn'));
}

test.describe('Galaxy live template breakpoint geometry', () => {
  for (const target of targets) {
    test(`${target.width}x${target.height}`, async ({ page }) => {
      const canvas = await openLive(page, target.width, target.height);
      const topBar = page.getByTestId('galaxy-top-bar');
      const shell = page.getByTestId('board-page-shell');
      const stage = page.getByTestId('board-stage');
      const rail = page.getByTestId('board-right-rail');
      const module = page.getByTestId('board-rail-module');
      const scroll = page.getByTestId('board-rail-scroll');
      const actions = page.getByTestId('board-rail-actions');
      const sidebar = page.getByTestId('galaxy-sidebar-wrapper');

      expect((await rect(topBar)).height).toBe(52);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);

      const [canvasRect, stageRect] = await Promise.all([rect(canvas), rect(stage)]);
      expect(Math.abs(canvasRect.width - canvasRect.height)).toBeLessThanOrEqual(1);
      expect(canvasRect.left).toBeGreaterThanOrEqual(stageRect.left - 1);
      expect(canvasRect.top).toBeGreaterThanOrEqual(stageRect.top - 1);
      expect(canvasRect.right).toBeLessThanOrEqual(stageRect.right + 1);
      expect(canvasRect.bottom).toBeLessThanOrEqual(stageRect.bottom + 1);
      expect(canvasRect.left).toBeGreaterThanOrEqual(0);
      expect(canvasRect.right).toBeLessThanOrEqual(target.width + 1);

      const offenders = await stage.locator('h1,h2,h3,h4,h5,h6,button,[role="button"]').evaluateAll(
        (elements, canvasBox) => elements.filter((element) => {
          const box = element.getBoundingClientRect();
          const style = getComputedStyle(element);
          return box.width > 0 && box.height > 0 && box.bottom <= canvasBox.top + 1 &&
            style.display !== 'none' && style.visibility !== 'hidden';
        }).map((element) => element.textContent?.trim() || element.getAttribute('aria-label')),
        canvasRect,
      );
      expect(offenders).toEqual([]);

      await expect(topBar.locator('img')).toHaveAttribute('src', '/assets/img/logo-white.png');
      expect(await sidebar.count() ? (await rect(sidebar)).width : 0).toBe(target.sidebar);

      if (target.mode === 'horizontal') {
        const [railRect, moduleRect, scrollRect, actionRect] = await Promise.all([
          rect(rail), rect(module), rect(scroll), rect(actions),
        ]);
        expect(Math.abs(railRect.width - target.rail!)).toBeLessThanOrEqual(1);
        expect(moduleRect.top).toBeGreaterThanOrEqual(52);
        expect(moduleRect.top).toBeLessThan(target.height);
        expect(actionRect.bottom).toBeLessThanOrEqual(target.height + 1);
        expect(actionRect.bottom).toBeGreaterThan(52);
        expect(scrollRect.top).toBeGreaterThanOrEqual(moduleRect.bottom - 1);
        expect(scrollRect.bottom).toBeLessThanOrEqual(actionRect.top + 1);
        const overflow = await Promise.all([module, scroll, actions].map((part) => part.evaluate((element) => ({
          x: getComputedStyle(element).overflowX,
          y: getComputedStyle(element).overflowY,
        }))));
        expect(overflow[0].y).not.toBe('auto');
        expect(overflow[1].y).toBe('auto');
        expect(overflow[2].y).not.toBe('auto');

        const trend = page.getByTestId('live-match-trend-region');
        const controls = page.getByTestId('live-match-display-controls-grid');
        const [trendRect, controlsRect] = await Promise.all([rect(trend), rect(controls)]);
        expect(trendRect.bottom).toBeLessThanOrEqual(controlsRect.top + 1);
        const scrollMetrics = await scroll.evaluate((element) => ({
          clientHeight: element.clientHeight,
          scrollHeight: element.scrollHeight,
          overflowY: getComputedStyle(element).overflowY,
        }));
        expect(scrollMetrics.overflowY).toBe('auto');
        expect(scrollMetrics.scrollHeight).toBeGreaterThan(scrollMetrics.clientHeight);
        await trend.evaluate((element) => element.scrollIntoView({ block: 'start' }));
        await expect.poll(async () => scroll.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
        const [scrolledTrendRect, scrolledRailRect] = await Promise.all([rect(trend), rect(scroll)]);
        expect(scrolledTrendRect.top).toBeGreaterThanOrEqual(scrolledRailRect.top - 1);
        expect(scrolledTrendRect.top).toBeLessThan(scrolledRailRect.bottom);

        const moveCounter = actions.getByTestId('playback-move-counter');
        const moveCounterRect = await rect(moveCounter);
        expect(moveCounterRect.left).toBeGreaterThanOrEqual(actionRect.left - 1);
        expect(moveCounterRect.right).toBeLessThanOrEqual(actionRect.right + 1);
        expect(moveCounterRect.top).toBeGreaterThanOrEqual(actionRect.top - 1);
        expect(moveCounterRect.bottom).toBeLessThanOrEqual(actionRect.bottom + 1);
        const counterText = await moveCounter.evaluate((element) => ({
          clientWidth: element.clientWidth,
          scrollWidth: element.scrollWidth,
          textOverflow: getComputedStyle(element).textOverflow,
        }));
        expect(counterText.scrollWidth).toBeLessThanOrEqual(counterText.clientWidth);
        if (target.rail! <= 340) expect(counterText.textOverflow).not.toBe('ellipsis');
      } else {
        const [moduleRect, scrollRect, actionRect] = await Promise.all([rect(module), rect(scroll), rect(actions)]);
        expect(moduleRect.top).toBeGreaterThanOrEqual(canvasRect.bottom - 1);
        expect(scrollRect.top).toBeGreaterThanOrEqual(moduleRect.bottom - 1);
        expect(actionRect.top).toBeGreaterThanOrEqual(scrollRect.bottom - 1);
        await shell.evaluate((element) => { element.scrollTop = element.scrollHeight; });
        await expect.poll(async () => (await rect(actions)).bottom).toBeLessThanOrEqual(target.height - 63 + 1);
      }

      if (target.width === 1440) {
        expect(canvasRect.width).toBeGreaterThanOrEqual(826);
        expect(canvasRect.width).toBeLessThanOrEqual(830);
      }
      if (target.width === 430) {
        await expect(page.getByTestId('galaxy-bottom-nav')).toBeVisible();
        await expect(page.getByTestId('live-coordinate-toggle')).toHaveAttribute('aria-pressed', 'false');
      }
    });
  }
});

test.describe('Galaxy live template Chinese labels', () => {
  test('desktop has no English navigation or coordinate residue', async ({ page }) => {
    await useChinese(page);
    await openLive(page, 1200, 800);

    const sidebar = page.getByTestId('galaxy-sidebar-nav');
    await expect(sidebar.getByRole('button', { name: '首页' })).toBeVisible();
    await expect(sidebar.getByRole('button', { name: '教程' })).toBeVisible();
    await expect(page.getByRole('button', { name: '坐标' })).toBeVisible();
    await expect(sidebar.getByRole('button', { name: 'Home' })).toHaveCount(0);
    await expect(sidebar.getByRole('button', { name: 'Tutorials' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Coordinates' })).toHaveCount(0);
  });

  test('mobile has no English bottom navigation, menu, or coordinate residue', async ({ page }) => {
    await useChinese(page);
    await openLive(page, 430, 880);

    const bottomNav = page.getByTestId('galaxy-bottom-nav');
    await expect(bottomNav.getByRole('button', { name: '首页' })).toBeVisible();
    await expect(bottomNav.getByRole('button', { name: '更多' })).toBeVisible();
    await expect(page.getByRole('button', { name: '坐标' })).toBeVisible();
    await bottomNav.getByRole('button', { name: '更多' }).click();
    await expect(page.getByRole('menuitem', { name: '教程' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Home' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'More' })).toHaveCount(0);
    await expect(page.getByRole('menuitem', { name: 'Tutorials' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Coordinates' })).toHaveCount(0);
  });
});

test.describe('Galaxy sidebar journeys', () => {
  test('docked preference persists and board keeps its rail contract', async ({ page }) => {
    await openLive(page, 1536, 900);
    const canvasBefore = await rect(page.getByTestId('board-stage').locator('canvas'));
    await page.getByTestId('galaxy-sidebar-toggle').click();
    await expect.poll(async () => (await rect(page.getByTestId('galaxy-sidebar-wrapper'))).width).toBe(0);
    expect((await rect(page.getByTestId('board-right-rail'))).width).toBe(380);
    expect((await rect(page.getByTestId('board-stage').locator('canvas'))).width).toBeGreaterThanOrEqual(canvasBefore.width);
    expect((await rect(page.getByTestId('galaxy-sidebar-toggle'))).width).toBeGreaterThanOrEqual(44);

    await page.setViewportSize({ width: 1200, height: 800 });
    await page.reload();
    await expect.poll(async () => (await rect(page.getByTestId('galaxy-sidebar-wrapper'))).width).toBe(0);
  });

  test('narrow overlay leaves board unchanged, traps focus, closes with Escape and restores focus', async ({ page }) => {
    await page.setViewportSize({ width: 1199, height: 800 });
    await page.goto(livePath);
    await expect(page.getByTestId('board-page-shell')).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId('galaxy-sidebar-overlay')).toHaveCount(0);
    expect(await page.evaluate(() => localStorage.getItem('galaxy.sidebar.docked.expanded.v1'))).toBeNull();
    const before = await rect(page.getByTestId('board-stage'));
    const trigger = page.getByTestId('galaxy-sidebar-toggle');
    await trigger.click();
    const overlay = page.getByTestId('galaxy-sidebar-overlay');
    await expect(overlay).toBeVisible();
    const after = await rect(page.getByTestId('board-stage'));
    expect(after).toEqual(before);
    expect(await page.evaluate(() => getComputedStyle(document.body).overflow)).toBe('hidden');
    await page.keyboard.press('Tab');
    expect(await page.evaluate(() => document.activeElement?.closest('[data-testid="galaxy-sidebar-overlay"]') !== null)).toBe(true);
    await page.keyboard.press('Escape');
    await expect(overlay).toHaveCount(0);
    await expect(trigger).toBeFocused();
  });

  test('route and breakpoint transitions close or unmount the overlay', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('galaxy.sidebar.docked.expanded.v1', 'false'));
    await openLive(page, 1199, 800);
    const trigger = page.getByTestId('galaxy-sidebar-toggle');
    await trigger.click();
    await page.getByTestId('galaxy-sidebar-nav').getByRole('button').first().click();
    await expect(page).toHaveURL(/\/galaxy\/?$/);
    await expect(page.getByTestId('galaxy-sidebar-overlay')).toHaveCount(0);

    await page.goto(livePath);
    await trigger.click();
    await page.setViewportSize({ width: 899, height: 700 });
    await expect(page.getByTestId('galaxy-sidebar-overlay')).toHaveCount(0);
    await expect(page.getByTestId('galaxy-bottom-nav')).toBeVisible();

    await page.setViewportSize({ width: 1200, height: 800 });
    await expect.poll(async () => (await rect(page.getByTestId('galaxy-sidebar-wrapper'))).width).toBe(0);

    await page.setViewportSize({ width: 1199, height: 800 });
    await expect(page.getByTestId('galaxy-sidebar-overlay')).toHaveCount(0);
  });
});
