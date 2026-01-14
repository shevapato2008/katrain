import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.message));
});

test('login flow', async ({ page }) => {
  await page.goto('/');

  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: 'test-results/before_login.png' });
  
  const content = await page.content();
  console.log('Page content length:', content.length);
  if (content.includes('Initializing KaTrain')) {
      console.log('App is in initializing state');
  }

  // Should see login dialog
  await expect(page.getByText('Login to KaTrain')).toBeVisible({ timeout: 10000 });

  // Fill credentials
  await page.getByLabel('Username').fill('admin');
  await page.getByLabel('Password').fill('admin');

  // Click login
  await page.getByRole('button', { name: 'Login' }).click();

  // Dialog should close
  await expect(page.getByText('Login to KaTrain')).not.toBeVisible();
  
  // Check if session initialized
  await expect(page.getByText('Ready')).toBeVisible({ timeout: 15000 });
});

test('login persistence', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Username').fill('admin');
  await page.getByLabel('Password').fill('admin');
  await page.getByRole('button', { name: 'Login' }).click();
  await expect(page.getByText('Ready')).toBeVisible({ timeout: 15000 });

  await page.reload();
  await expect(page.getByText('Login to KaTrain')).not.toBeVisible();
  await expect(page.getByText('Ready')).toBeVisible({ timeout: 15000 });
});
