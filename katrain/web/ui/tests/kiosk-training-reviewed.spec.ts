import { test, expect } from '@playwright/test';
import { freezeClock, stubBackendStatics } from './helpers/fourup';
import { kioskMeJson } from './helpers/kioskIdentity';

test.use({ viewport: { width: 1024, height: 600 } });
test('training carousel snaps after dragging and retains real category counts', async ({ page }) => {
  await freezeClock(page);
  await stubBackendStatics(page);
  await page.addInitScript(() => { localStorage.setItem('token', 'training-review'); localStorage.setItem('katrain_language', 'cn'); });
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') return route.fulfill({ json: kioskMeJson() });
    if (path === '/api/v1/tsumego/levels') return route.fulfill({ json: [{ level: '15k', total: 30, categories: { capturing: 20, life_death: 10 } }, { level: '14k', total: 12, categories: { capturing: 12 } }] });
    return route.fulfill({ json: {} });
  });
  await page.goto('/kiosk/tsumego');
  await expect(page.locator('.u-train-carousel-card.is-center')).toContainText('15 级');
  await expect(page.locator('.u-train-carousel-card.is-center')).toContainText('66.7%');
  const beforeDragX = await page.locator('.u-train-carousel-card.is-center').evaluate(card => card.getBoundingClientRect().x);
  await page.mouse.move(650, 250); await page.mouse.down(); await page.mouse.move(470, 250, { steps: 8 });
  const duringDragX = await page.locator('.u-train-carousel-card.is-center').evaluate(card => card.getBoundingClientRect().x);
  expect(duringDragX).toBeLessThan(beforeDragX);
  await page.mouse.up();
  await expect(page).toHaveURL(/\/kiosk\/tsumego$/);
  await expect(page.locator('.u-train-carousel-card.is-center')).toContainText('14 级');
  await page.waitForTimeout(280);
  await page.screenshot({ path: '/tmp/training-reviewed-carousel.png' });
  await page.getByRole('button', { name: '上一棋力' }).click();
  await expect(page.locator('.u-train-carousel-card.is-center')).toContainText('15 级');
  await page.getByRole('button', { name: '进入 15 级 题型' }).click();
  await expect(page).toHaveURL(/\/kiosk\/tsumego\/15k$/);
});

test('wrong tab filters the current unit and shows attempts and last duration', async ({ page }) => {
  await freezeClock(page); await stubBackendStatics(page);
  await page.addInitScript(() => { localStorage.setItem('token', 'training-review'); localStorage.setItem('katrain_language', 'cn'); if (!sessionStorage.getItem('emptyWrong')) localStorage.setItem('tsumego_progress:u1', JSON.stringify({ p1: { completed: false, attempts: 3, lastDuration: 12 }, p2: { completed: true, attempts: 2, lastDuration: 9 } })); });
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') return route.fulfill({ json: kioskMeJson() });
    if (path.includes('/categories/')) return route.fulfill({ json: [{ id: 'p1' }, { id: 'p2' }, { id: 'p3' }] });
    if (path.includes('/problems/')) return route.fulfill({ json: { id: path.split('/').pop(), boardSize: 19, initialBlack: [], initialWhite: [], level: '15k', category: 'capturing', hint: '黑先', sgfContent: '' } });
    return route.fulfill({ json: {} });
  });
  await page.goto('/kiosk/tsumego/15k/capturing/1');
  await expect(page.locator('.qgrid button')).toHaveCount(3);
  await expect(page.locator('.qgrid button').nth(1)).toContainText('3 次');
  await page.screenshot({ path: '/tmp/training-reviewed-attempts.png' });
  await page.getByRole('tab', { name: '错题', exact: true }).click();
  await expect(page.locator('.qgrid button')).toHaveCount(1);
  await expect(page.locator('.qgrid button')).toContainText('3 次');
  await expect(page.locator('.qgrid button')).toContainText('12 秒');
  await page.screenshot({ path: '/tmp/training-reviewed-wrong.png' });
  await page.getByTestId('problem-enter').click();
  await expect(page).toHaveURL(/\/problem\/p1\?set=wrong$/);
  await expect(page.getByTestId('puzzle-actions')).toBeVisible();
  const bounds = await page.getByTestId('puzzle-actions').locator('button').evaluateAll(buttons => buttons.map(button => { const r = button.getBoundingClientRect(); return { right: r.right, bottom: r.bottom }; }));
  expect(bounds.every(r => r.right <= 1008 && r.bottom <= 586)).toBe(true);
  await page.screenshot({ path: '/tmp/training-reviewed-puzzle.png' });
  await page.goto('/kiosk/tsumego/15k/capturing');
  await page.getByRole('tab', { name: '单元', exact: true }).waitFor();
  await page.screenshot({ path: '/tmp/training-reviewed-units.png' });
  await page.getByRole('tab', { name: '错题', exact: true }).click();
  await expect(page.getByRole('button', { name: /错题簿/ })).toBeVisible();
  await expect(page.locator('.qgrid button')).toHaveCount(0);
  await page.screenshot({ path: '/tmp/training-reviewed-book-entry.png' });
  await page.getByRole('button', { name: /错题簿/ }).click();
  await expect(page).toHaveURL(/\/kiosk\/tsumego\/15k\/capturing\/wrong$/);
  await page.goto('/kiosk/tsumego/15k/capturing/1');
  await page.evaluate(() => { sessionStorage.setItem('emptyWrong', '1'); localStorage.setItem('tsumego_progress:u1', '{}'); });
  await page.reload();
  await page.getByRole('tab', { name: '错题', exact: true }).click();
  await expect(page.getByTestId('problem-preview-board')).toContainText('本单元现在没有做错过的题');
  await expect(page.getByTestId('problem-selection')).toHaveCount(0);
  await expect(page.getByTestId('problem-enter')).toBeDisabled();
  await expect(page.locator('body')).not.toContainText('第 00 题');
  await page.screenshot({ path: '/tmp/training-reviewed-empty-wrong.png' });

});

test('mixed training wrong book keeps the mixed set across problems', async ({ page }) => {
  await freezeClock(page); await stubBackendStatics(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'training-review');
    localStorage.setItem('katrain_language', 'cn');
    localStorage.setItem('tsumego_progress:u1', JSON.stringify({
      p1: { completed: false, attempts: 1, lastDuration: 12 },
      p2: { completed: false, attempts: 2, lastDuration: 15 },
    }));
  });
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') return route.fulfill({ json: kioskMeJson() });
    if (path.endsWith('/levels/15k/problems')) return route.fulfill({ json: { items: [{ id: 'p1' }, { id: 'p2' }, { id: 'p3' }], total: 3, page: 1, page_size: 200 } });
    if (path.includes('/categories/')) return route.fulfill({ json: [{ id: 'p1' }, { id: 'p2' }, { id: 'p3' }] });
    if (path.includes('/problems/')) {
      const id = path.split('/').pop();
      return route.fulfill({ json: { id, boardSize: 19, initialBlack: [], initialWhite: [], level: '15k', category: id === 'p2' ? 'tesuji' : 'capturing', hint: '黑先', sgfContent: '' } });
    }
    return route.fulfill({ json: {} });
  });
  await page.goto('/kiosk/tsumego/15k/all');
  await page.getByRole('tab', { name: '错题', exact: true }).click();
  await page.getByRole('button', { name: /错题簿/ }).click();
  await expect(page.getByTestId('problems-grid').locator('button')).toHaveCount(2);
  await page.getByTestId('problems-grid').locator('button').first().click();
  await expect(page).toHaveURL(/\/problem\/p1\?set=wrong&scope=all$/);
  await expect(page.getByTestId('puzzle-pagebar')).toContainText('错题 第 1 / 2 道');
  await expect(page.getByRole('button', { name: '上一题' })).toBeDisabled();
  await expect(page.getByRole('button', { name: '下一题' })).toBeEnabled();
  await expect(page.getByRole('button', { name: '返回错题' })).toHaveCount(0);
  await page.screenshot({ path: 'output/playwright/page14-navigation-first-proposed.png' });
  await page.getByRole('button', { name: '下一题' }).click();
  await expect(page).toHaveURL(/\/problem\/p2\?set=wrong&scope=all$/);
  await expect(page.getByTestId('puzzle-pagebar')).toContainText('错题 第 2 / 2 道');
  await expect(page.getByRole('button', { name: '上一题' })).toBeEnabled();
  await expect(page.getByRole('button', { name: '下一题' })).toBeDisabled();
  await expect(page.getByRole('button', { name: '下一题' })).toHaveAttribute('title', '这是最后一题');
  await page.screenshot({ path: 'output/playwright/page14-navigation-last-proposed.png' });
  await page.getByRole('button', { name: '上一题' }).click();
  await expect(page).toHaveURL(/\/problem\/p1\?set=wrong&scope=all$/);
  await expect(page.getByRole('button', { name: '上一题' })).toBeDisabled();
  await page.getByTestId('puzzle-pagebar').getByRole('button', { name: '错题', exact: true }).click();
  await expect(page).toHaveURL(/\/15k\/all\/wrong$/);
});
