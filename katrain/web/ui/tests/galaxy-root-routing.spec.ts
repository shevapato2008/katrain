import { expect, test, type Page } from '@playwright/test';
import { resolve } from 'node:path';

// Read-only fixtures keep this routing journey independent of live accounts,
// engines and records. Unexpected writes are blocked and fail the journey.
async function readOnlyPreview(page: Page) {
  const writes: string[] = [];
  const libraryRequests: URL[] = [];
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.addInitScript(() => {
    localStorage.clear();
    localStorage.setItem('katrain_language', 'en');
  });
  for (const name of ['logo-white.png', 'board.png']) {
    await page.route(`**/assets/img/${name}`, route => route.fulfill({
      path: resolve(process.cwd(), '../../img', name), contentType: 'image/png',
    }));
  }
  await page.route('**/assets/sounds/**', route => route.fulfill({ status: 204, body: '' }));
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (request.method() !== 'GET') {
      writes.push(`${request.method()} ${url.pathname}`);
      return route.abort('blockedbyclient');
    }
    switch (url.pathname) {
      case '/api/v1/auth/me':
        return route.fulfill({ status: 401, json: { detail: 'Not authenticated' } });
      case '/api/translations':
      case '/api/v1/live/translations':
        return route.fulfill({ json: { lang: url.searchParams.get('lang'), translations: {} } });
      case '/api/v1/kifu/albums':
        libraryRequests.push(url);
        return route.fulfill({ json: { items: [], total: 0, page: Number(url.searchParams.get('page') || 1), page_size: 20 } });
      case '/api/v1/kiosk-preferences/typography':
        return route.fulfill({ json: { font: 'wenkai', size: 'large' } });
      case '/api/v1/health':
        return route.fulfill({ json: { status: 'ok', engines: { local: 'reachable', cloud: 'reachable' } } });
      case '/api/v1/geometry/status':
        return route.fulfill({ json: { phase: 'disabled', session_calibrated: false, capabilities: {} } });
      case '/api/v1/vision/status':
        return route.fulfill({ json: { enabled: false, camera_connected: false, pose_locked: false, sync_state: 'idle', recognition_ready: false, led_connected: false } });
      default:
        return route.fulfill({ status: 404, json: { detail: 'Read-only routing preview: endpoint not mocked' } });
    }
  });
  return { writes, libraryRequests };
}

test('root opens Galaxy without a redirect or Zen session, and play survives refresh and home return', async ({ page }) => {
  const { writes } = await readOnlyPreview(page);
  const response = await page.goto('/');
  expect(response?.request().redirectedFrom()).toBeNull();
  await expect(page).toHaveURL('/');
  await expect(page.locator('.galaxy-root[data-language="en"]')).toBeVisible();
  await expect(page.getByTestId('galaxy-main').getByText('欢迎使用智星盒', { exact: true })).toBeVisible();
  await expect(page.getByTestId('kiosk-viewport')).toHaveCount(0);

  await page.getByTestId('galaxy-sidebar-nav').getByRole('button', { name: 'Play', exact: true }).click();
  await expect(page).toHaveURL('/play');
  await expect(page.getByText('Choose your game mode', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page).toHaveURL('/play');
  await expect(page.getByText('Choose your game mode', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '回到首页', exact: true }).click();
  await expect(page).toHaveURL('/');
  await expect(page.getByTestId('galaxy-main').getByText('欢迎使用智星盒', { exact: true })).toBeVisible();
  expect(writes, 'Root navigation must not create the legacy POST /api/session').toEqual([]);
});

test('root kifu deep link preserves search and page through refresh', async ({ page }) => {
  const { writes, libraryRequests } = await readOnlyPreview(page);
  const path = '/kifu/?q=Lee+Changho&page=3';
  await page.goto(path);
  await expect(page).toHaveURL(path);
  await expect(page.getByPlaceholder('Search by player, event, date...')).toHaveValue('Lee Changho');
  await expect(page.getByText('No records found', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page).toHaveURL(path);
  await expect(page.getByPlaceholder('Search by player, event, date...')).toHaveValue('Lee Changho');
  await expect(page.getByText('No records found', { exact: true })).toBeVisible();
  expect(libraryRequests.length).toBeGreaterThanOrEqual(2);
  for (const url of libraryRequests) {
    expect(url.searchParams.get('q')).toBe('Lee Changho');
    expect(url.searchParams.get('page')).toBe('3');
    expect(url.searchParams.get('page_size')).toBe('20');
  }
  expect(libraryRequests.some(url => url.searchParams.get('lang') === 'en')).toBe(true);
  expect(writes).toEqual([]);
});

test('retired Galaxy URLs keep a 404 view and kiosk retains its own surface', async ({ page }) => {
  const { writes } = await readOnlyPreview(page);
  // Vite's SPA fallback may answer HTTP 200. These assertions cover the client
  // view only; backend tests and deployed HTTP checks enforce the real 404.
  for (const path of ['/galaxy', '/galaxy/play', '/galaxy/kifu?q=Lee', '/unknown-root-page']) {
    await page.goto(path);
    await expect(page).toHaveURL(path);
    await expect(page.getByRole('heading', { name: '404', exact: true })).toBeVisible();
    await expect(page.getByTestId('galaxy-main').getByText('欢迎使用智星盒', { exact: true })).toHaveCount(0);
  }
  await page.goto('/galaxy/play');
  await page.reload();
  await expect(page).toHaveURL('/galaxy/play');
  await expect(page.getByRole('heading', { name: '404', exact: true })).toBeVisible();

  await page.goto('/kiosk');
  await expect(page).toHaveURL('/kiosk/play');
  await expect(page.getByTestId('kiosk-viewport')).toBeVisible();
  await expect(page.getByTestId('galaxy-main')).toHaveCount(0);
  expect(writes).toEqual([]);
});
