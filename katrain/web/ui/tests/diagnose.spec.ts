import { test, expect } from '@playwright/test';

test('verify board and analysis rendering', async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', err => consoleErrors.push(err.message));

  await page.goto('http://localhost:8001');
  await page.waitForLoadState('networkidle');

  const board = page.locator('canvas');
  await expect(board).toBeVisible();

  console.log('Placing stone...');
  const box = await board.boundingBox();
  if (!box) throw "No board";
  await board.click({ position: { x: box.width / 2, y: box.height / 2 } });

  // Wait for analysis to arrive and visits to be > 0
  console.log('Waiting for AI analysis...');
  await page.waitForFunction(() => {
    const el = Array.from(document.querySelectorAll('p, span')).find(e => e.textContent?.includes('Visits'));
    if (el && el.nextElementSibling) {
      return parseInt(el.nextElementSibling.textContent || '0') > 10;
    }
    return false;
  }, { timeout: 15000 });

  console.log('Analysis confirmed. Checking for page stability...');
  await page.waitForTimeout(2000);

  // Ensure the page didn't go blank
  const bodySize = await page.evaluate(() => document.body.innerText.length);
  console.log('Body text length:', bodySize);
  expect(bodySize).toBeGreaterThan(100);
  
  // Ensure no React crashes
  expect(consoleErrors).toEqual([]);
});
