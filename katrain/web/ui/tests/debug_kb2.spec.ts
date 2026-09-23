import { test } from '@playwright/test';
import { freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT, hasTouch: true });

test('debug2', async ({ page }) => {
  page.on('console', (m) => console.log('[page console]', m.text()));
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'geom');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubBackendStatics(page, 'cn');
  await page.route('**/api/v1/auth/me', (r) => r.fulfill({ json: { id: 1, username: '访客', rank: '20k', credits: 0 } }));
  await page.goto('/kiosk/play/cross-platform/login/golaxy');
  await page.waitForSelector('[data-testid="login-submit"]');
  await page.waitForLoadState('networkidle');

  await page.evaluate(() => {
    const kb = document.createElement('div');
    kb.className = 'skbd';
    Object.assign(kb.style, { position: 'fixed', left: '0', right: '0', bottom: '0', height: '260px', zIndex: '999' });
    document.body.appendChild(kb);
  });

  // manual sanity: can we scroll the zone at all?
  const manual = await page.evaluate(() => {
    const zone = document.querySelector('[data-testid="platform-login-page"] .xplogin__main') as HTMLElement;
    zone.scrollTop = 30;
    return { after: zone.scrollTop };
  });
  console.log('[manual scroll test]', JSON.stringify(manual));

  await page.click('[data-testid="login-field-password"]');
  await page.waitForTimeout(300);
  const info = await page.evaluate(() => {
    const zone = document.querySelector('[data-testid="platform-login-page"] .xplogin__main') as HTMLElement;
    return { scrollTop: zone.scrollTop, scrollHeight: zone.scrollHeight, clientHeight: zone.clientHeight, padding: getComputedStyle(zone).paddingBottom };
  });
  console.log('[after click]', JSON.stringify(info));
});
