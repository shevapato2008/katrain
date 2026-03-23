import { test, expect } from '@playwright/test';

async function login(page: Parameters<typeof test>[1]['page']) {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  const loginVisible = await page.getByText('Login').isVisible().catch(() => false);
  if (loginVisible) {
    await page.getByLabel('Username').fill('admin');
    await page.getByLabel('Password').fill('admin');
    await page.getByRole('button', { name: 'Login' }).click();
    await page.waitForLoadState('networkidle');
  }
}

test.describe('Tutorial Module', () => {
  test.beforeEach(async ({ page }) => { await login(page); });

  test('Tutorial link appears in sidebar', async ({ page }) => {
    await page.goto('/galaxy');
    await expect(page.getByText('教程')).toBeVisible({ timeout: 10000 });
  });

  test('Tutorial landing page shows category cards', async ({ page }) => {
    await page.goto('/galaxy/tutorials');
    await expect(page.getByText('布局', { exact: true })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/围棋布局的基本原则/)).toBeVisible();
  });

  test('Clicking category navigates to topic list', async ({ page }) => {
    await page.goto('/galaxy/tutorials');
    await page.getByText('布局', { exact: true }).click();
    await expect(page.getByText('角的战略价值')).toBeVisible({ timeout: 10000 });
  });

  test('Clicking topic navigates to topic detail with example list', async ({ page }) => {
    await page.goto('/galaxy/tutorials/opening');
    await page.getByText('角的战略价值').click();
    await expect(page.getByText('角部的效率优势')).toBeVisible({ timeout: 10000 });
  });

  test('Clicking example from topic detail opens playback page', async ({ page }) => {
    await page.goto('/galaxy/tutorials/topic/topic_opening_001');
    await page.getByText('角部的效率优势').click();
    await expect(page.getByText('第 1 / 2 步')).toBeVisible({ timeout: 10000 });
  });

  test('Example page shows step narration text', async ({ page }) => {
    await page.goto('/galaxy/tutorials/example/ex_opening_001');
    await expect(page.getByText(/角部是棋盘上效率最高/)).toBeVisible({ timeout: 10000 });
  });

  test('Example page shows step image (board_mode=image renders image_asset)', async ({ page }) => {
    await page.goto('/galaxy/tutorials/example/ex_opening_001');
    const img = page.locator('img[alt^="Step"]');
    await expect(img).toBeVisible({ timeout: 10000 });
    const loaded = await img.evaluate((el: HTMLImageElement) => el.naturalWidth > 0);
    expect(loaded).toBe(true);
    // Verify the image src points to the asset API (board_mode=image uses image_asset)
    const src = await img.getAttribute('src');
    expect(src).toContain('/api/v1/tutorials/assets/images');
  });

  test('Example page has audio element pointing to asset API', async ({ page }) => {
    await page.goto('/galaxy/tutorials/example/ex_opening_001');
    await page.waitForSelector('audio', { state: 'attached', timeout: 10000 });
    const src = await page.locator('audio').getAttribute('src');
    expect(src).toContain('/api/v1/tutorials/assets/audio');
  });

  test('Next button advances to step 2', async ({ page }) => {
    await page.goto('/galaxy/tutorials/example/ex_opening_001');
    await expect(page.getByText('第 1 / 2 步')).toBeVisible({ timeout: 10000 });
    await page.getByRole('button', { name: '下一步' }).click();
    await expect(page.getByText('第 2 / 2 步')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/优先占据四角/)).toBeVisible();
  });

  test('Back button is disabled on step 1', async ({ page }) => {
    await page.goto('/galaxy/tutorials/example/ex_opening_001');
    await expect(page.getByRole('button', { name: '上一步' })).toBeDisabled({ timeout: 10000 });
  });

  test('Finish button marks example as completed', async ({ page }) => {
    await page.goto('/galaxy/tutorials/example/ex_opening_001');
    await page.getByRole('button', { name: '下一步' }).click();
    await expect(page.getByRole('button', { name: '完成' })).toBeVisible({ timeout: 5000 });
    await page.getByRole('button', { name: '完成' }).click();
    await expect(page.getByText('已完成')).toBeVisible({ timeout: 5000 });
  });

  test('Re-entering a completed example starts from step 1', async ({ page }) => {
    // Complete the example
    await page.goto('/galaxy/tutorials/example/ex_opening_001');
    await page.getByRole('button', { name: '下一步' }).click();
    await page.getByRole('button', { name: '完成' }).click();
    await expect(page.getByText('已完成')).toBeVisible({ timeout: 5000 });

    // Navigate away then back
    await page.goto('/galaxy/tutorials');
    await page.goto('/galaxy/tutorials/example/ex_opening_001');

    // Should start at step 1 (completed badge may or may not show — progress not restored in phase 1)
    await expect(page.getByText('第 1 / 2 步')).toBeVisible({ timeout: 10000 });
  });
});
