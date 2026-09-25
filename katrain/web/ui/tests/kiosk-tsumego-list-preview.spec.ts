import { expect, test } from '@playwright/test';
import { freezeClock, stubBackendStatics } from './helpers/fourup';
import { kioskMeJson } from './helpers/kioskIdentity';

test.use({ viewport: { width: 1024, height: 600 } });

const ids = Array.from({ length: 20 }, (_, i) => `preview-${i + 1}`);
const problems = Object.fromEntries(ids.map((id, i) => [id, {
  id,
  level: '15k',
  category: 'capturing',
  hint: '黑先',
  boardSize: i === 1 ? 9 : 19,
  initialBlack: [i === 0 ? 'co' : i === 1 ? 'dd' : 'bp'],
  initialWhite: [i === 0 ? 'cp' : i === 1 ? 'ee' : 'cq'],
  sgfContent: '',
}]));

test('题目列表选择一道题时预览真实棋形，并从底部按钮进入所选题', async ({ page }) => {
  await freezeClock(page);
  await stubBackendStatics(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'preview-test');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') return route.fulfill({ json: kioskMeJson() });
    if (path === '/api/v1/tsumego/progress') return route.fulfill({ json: {} });
    if (path.startsWith('/api/v1/tsumego/levels/') && path.includes('/categories/')) {
      return route.fulfill({ json: ids.map((id) => ({ id })) });
    }
    const id = path.split('/api/v1/tsumego/problems/')[1];
    if (id && problems[id]) return route.fulfill({ json: problems[id] });
    return route.fulfill({ json: {} });
  });

  await page.goto('/kiosk/tsumego/15k/capturing/1');
  const preview = page.getByTestId('problem-preview-board');
  await expect(preview.locator('[data-stone="b"][data-at="C5"]')).toBeVisible();
  await page.getByRole('button', { name: /第 2 题/ }).click();
  await expect(preview.locator('[data-stone="b"][data-at="D6"]')).toBeVisible();
  await expect(preview.locator('[data-stone="b"][data-at="C5"]')).toHaveCount(0);
  await expect(preview.locator('.kiosk-board__ruler--top span')).toHaveCount(9);
  await expect(page.getByTestId('problem-selection')).toContainText('第 02 题');

  const geometry = await page.evaluate(() => ({
    width: document.documentElement.scrollWidth,
    height: document.documentElement.scrollHeight,
    boardWidth: Math.round(document.querySelector('[data-testid="problem-preview-board"]')!.getBoundingClientRect().width),
    buttonBottom: Math.round(document.querySelector('[data-testid="problem-enter"]')!.getBoundingClientRect().bottom),
  }));
  expect(geometry).toEqual({ width: 1024, height: 600, boardWidth: 516, buttonBottom: 586 });

  await page.getByTestId('problem-enter').click();
  await expect(page).toHaveURL(/\/kiosk\/tsumego\/problem\/preview-2$/);
});
