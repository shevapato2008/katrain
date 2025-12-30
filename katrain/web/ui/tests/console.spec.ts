import { test, expect } from '@playwright/test';

test('check for frontend console errors', async ({ page }) => {
  const errors: string[] = [];
  
  // Listen for console errors
  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log(`Console Error: "${msg.text()}"`);
      errors.push(msg.text());
    }
  });

  // Navigate to the app
  await page.goto('/');

  // Wait for the app to likely load (e.g. check for a specific element or just wait a bit)
  // Waiting for network to be idle is a good proxy for "initial load complete"
  await page.waitForLoadState('networkidle');

  // Verify the page title or content to ensure it actually loaded
  // The default Vite app usually has a specific title, but we can just check body exists
  await expect(page.locator('body')).toBeVisible();

  // Assert no errors were found
  expect(errors.length, `Found ${errors.length} console errors`).toBe(0);
});
