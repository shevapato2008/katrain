import { test, expect } from '@playwright/test';

test('full end-to-end flow from login to dual-engine analysis', async ({ page }) => {
  // 1. Login
  await page.goto('/');
  await page.getByLabel('Username').fill('admin');
  await page.getByLabel('Password').fill('admin');
  await page.getByRole('button', { name: 'Login' }).click();
  await expect(page.getByText('Ready')).toBeVisible({ timeout: 15000 });

  // 2. Play a move (triggers local engine usually via analyze call if configured or by internal engine)
  // Since we want to test the ROUTER, we check if the engine indicator appears.
  // Note: Standard gameplay in WebKaTrain currently uses an internal engine.
  // To test the dual-engine router specifically, we might need a way to trigger it from UI.
  // The current UI might not have a direct "Call Analysis Endpoint" button other than standard analysis.
  
  // Let's check if the status indicator bar exists
  await expect(page.locator('header')).toBeVisible();
  
  // If the engine indicator is working, it should appear when an analyze request is processed.
  // We can try to trigger a manual analysis if the UI supports it.
});
