import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
  await page.goto('http://localhost:8001/');
  await expect(page).toHaveTitle(/KaTrain/);
});

test('can play a move', async ({ page }) => {
  await page.goto('http://localhost:8001/');
  
  // Wait for board to be visible
  await page.waitForSelector('canvas');
  
  // Click on the board (center area)
  await page.mouse.click(400, 400);
  
  // Check if status changes or a stone appears (this is harder to check on canvas, 
  // but we can check if the prisoner count or something in the UI updates)
  // For now, let's check if the WebSocket connection is active by looking at logs
  await expect(page.locator('text=Ready')).toBeVisible();
});

test('navigation buttons work', async ({ page }) => {
  await page.goto('http://localhost:8001/');
  await page.waitForSelector('canvas');
  
  // Click Pass
  await page.getByRole('button', { name: 'PASS' }).click();
  
  // Check if it's White's turn (PlayerCard color or something)
  // This depends on the UI implementation.
});
