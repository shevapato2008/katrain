import { expect, test, type Page } from '@playwright/test';
import { mkdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { bootMembership, catalog, NOW } from './helpers/membership';
import type { BillingOrder, MembershipUsage } from '../src/features/membership/types';

// Isolated browser fixtures only. All billing and provider facts below are intercepted.
const OUT = resolve(process.cwd(), '../../../output/playwright/wechat-native-20261108');
const copy = JSON.parse(readFileSync(resolve(process.cwd(), '../../../scripts/membership_translations.json'), 'utf8')) as Record<string, Record<string, string>>;
const text = (key: string, lang: string) => copy[`membership:${key}`][lang];
const CODE_URL = 'weixin://wxpay/bizpayurl/up?pr=NwY5Mz9&groupid=00';
async function bootNative(page: Page, language = 'cn') {
  mkdirSync(OUT, { recursive: true });
  const base = await bootMembership(page, { language, autoPay: false });
  const nativeCatalog = { ...catalog, environment: 'production', payments_mode: 'live' };
  let usage: MembershipUsage = { catalog_version: catalog.catalog_version, server_now: NOW, environment: 'production', payments_mode: 'live', revision: 1, capabilities: catalog.capabilities, plan: { current: null, next: null }, term: null, week: null, free: null, wallet: { credits: 1000, display_points: '10.00' } };
  let order: BillingOrder | null = null;
  let cancels = 0;
  let usageGets = 0;
  const creates: Record<string, unknown>[] = [];
  await page.route('**/api/v1/billing/catalog', route => route.fulfill({ json: nativeCatalog }));
  await page.route('**/api/v1/billing/usage', route => { usageGets += 1; return route.fulfill({ json: usage }); });
  await page.route('**/api/v1/billing/orders', route => {
    if (route.request().method() === 'GET') return route.fulfill({ json: { orders: order ? [order] : [] } });
    const payload = route.request().postDataJSON(); creates.push(payload);
    const topup = catalog.topups.find(item => item.sku === payload.sku);
    const plan = catalog.plans.find(item => `membership_${item.code}` === payload.sku);
    order = { id: 'UI-NATIVE-ORDER-001', sku: payload.sku, kind: topup ? 'topup' : 'membership', status: 'pending', amount_fen: topup?.amount_fen ?? plan!.amount_fen, currency: 'CNY', payments_mode: 'live', provider: 'wechat', created_at: NOW, expires_at: '2026-11-01T04:15:00Z', server_now: NOW, paid_at: null, fulfillment: null, payment_url: CODE_URL, payment_state: 'ready', cancel_requested: false };
    return route.fulfill({ json: order });
  });
  await page.route('**/api/v1/billing/orders/UI-NATIVE-ORDER-001', route => route.fulfill({ json: order }));
  await page.route('**/api/v1/billing/orders/UI-NATIVE-ORDER-001/cancel', route => {
    cancels += 1;
    expect(route.request().postDataJSON()).toEqual({});
    order = { ...order!, status: 'cancelled', payment_state: 'closed', cancel_requested: true, payment_url: null };
    return route.fulfill({ json: order });
  });
  return { ...base, creates, usageGets: () => usageGets, cancels: () => cancels, pay: () => {
    const topup = catalog.topups.find(item => item.sku === order!.sku);
    order = { ...order!, status: 'paid', payment_state: 'paid', payment_url: null, paid_at: NOW, fulfillment: topup ? { credits: topup.credits } : { plan_code: 'plus', starts_at: NOW, ends_at: '2026-12-01T04:00:00Z' } };
    const plan = catalog.plans.find(item => `membership_${item.code}` === order!.sku);
    usage = { ...usage, revision: 2, ...(plan ? { plan: { current: { code: plan.code, name: plan.name, starts_at: NOW, ends_at: '2026-12-01T04:00:00Z' }, next: null }, term: { limit: plan.term_units, used: 0, reserved: 0, remaining: plan.term_units, percent: 100, reset_at: '2026-12-01T04:00:00Z' }, week: { limit: plan.week_units, used: 0, reserved: 0, remaining: plan.week_units, percent: 100, reset_at: '2026-11-01T16:00:00Z' } } : {}), wallet: { credits: 1000 + (topup?.credits ?? 0), display_points: ((1000 + (topup?.credits ?? 0)) / 100).toFixed(2) } };
  } };
}
const shot = (page: Page, name: string) => page.screenshot({ path: resolve(OUT, name), animations: 'disabled' });
const image = (page: Page) => page.getByRole('img', { name: '微信支付二维码' });

test('Galaxy desktop uses Native QR, history recovery and server-confirmed wallet refresh', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const backend = await bootNative(page);
  await page.goto('/membership?tab=recharge');
  await page.getByRole('button', { name: '充值 ¥30', exact: true }).click();
  expect(backend.creates).toHaveLength(0);
  await page.getByRole('button', { name: '微信支付', exact: true }).click();
  await expect(image(page)).toBeVisible();
  await expect(image(page)).toHaveAttribute('src', /^data:image\/svg\+xml/);
  await image(page).screenshot({ path: resolve(OUT, 'native-qr-224.png') });
  await shot(page, 'galaxy-pending-1440.png');
  await page.getByRole('button', { name: '关闭', exact: true }).click();
  expect(backend.cancels()).toBe(0);
  await page.getByRole('button', { name: '订单记录', exact: true }).click();
  await page.getByRole('button', { name: /UI-NATIVE-ORDER-001/ }).click();
  await expect(image(page)).toBeVisible();
  expect(backend.creates).toHaveLength(1);
  backend.pay();
  await expect(page.getByRole('dialog')).toContainText('微信支付成功', { timeout: 8000 });
  await expect(image(page)).toHaveCount(0);
  await page.getByRole('button', { name: '完成', exact: true }).click();
  await page.getByRole('tab', { name: '用量', exact: true }).click();
  await expect(page.getByTestId('membership-page')).toContainText('40.00');
  expect(backend.creates[0].provider).toBe('wechat');
  expect(backend.browserErrors).toEqual([]);
});

test('Galaxy 375 shows cross-screen instructions without horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await bootNative(page);
  await page.goto('/membership?tab=plans');
  await page.getByRole('button', { name: '选择 Plus', exact: true }).click();
  await expect(page.getByText('手机浏览时，请在另一块屏幕打开本页，再用手机微信扫码。')).toBeVisible();
  await page.getByRole('button', { name: '微信支付', exact: true }).click();
  await expect(image(page)).toBeVisible();
  await expect(page.getByText('手机浏览时，请在另一块屏幕打开本页，再用手机微信扫码。')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await shot(page, 'galaxy-pending-375.png');
});

test('Kiosk 1024x600 keeps QR/status in the canvas and cancellation separate from return', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 600 });
  const backend = await bootNative(page);
  await page.goto('/kiosk/membership');
  await page.getByRole('tab', { name: 'API充值', exact: true }).click();
  await page.getByRole('button', { name: '充值 ¥10', exact: true }).click();
  expect(backend.creates).toHaveLength(0);
  await page.getByRole('button', { name: '微信支付', exact: true }).click();
  await expect(image(page)).toBeVisible();
  const dialog = page.getByRole('dialog');
  expect(await dialog.evaluate(el => !!el.closest('.kiosk-screen'))).toBe(true);
  const bounds = (await dialog.boundingBox())!;
  expect(bounds.y + bounds.height).toBeLessThanOrEqual(600);
  await expect(dialog.getByRole('button', { name: '取消订单', exact: true })).toBeVisible();
  const timerBounds = (await page.getByText('二维码剩余 15:00').boundingBox())!;
  const footerBounds = (await dialog.locator('footer').boundingBox())!;
  expect(timerBounds.y + timerBounds.height).toBeLessThanOrEqual(footerBounds.y);
  const scrollBounds = (await dialog.locator('.kiosk-side__scroll').boundingBox())!;
  expect(timerBounds.y + timerBounds.height).toBeLessThanOrEqual(scrollBounds.y + scrollBounds.height - 8);
  await expect(page.getByText('二维码剩余 15:00')).toBeVisible();
  await shot(page, 'kiosk-pending-1024x600.png');
  await dialog.getByRole('button', { name: '取消订单', exact: true }).click();
  await expect(dialog).toContainText('订单已取消');
  await expect(image(page)).toHaveCount(0);
  await dialog.getByRole('button', { name: '返回选择', exact: true }).click();
  expect(backend.cancels()).toBe(1);
  expect(backend.browserErrors).toEqual([]);
});


test('Galaxy 375 English explains cross-screen payment before creating an order', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  const backend = await bootNative(page, 'en');
  await page.goto('/membership?tab=plans');
  await page.getByRole('button', { name: text('select_plan', 'en').replace('{plan}', 'Plus'), exact: true }).click();
  await expect(page.getByText(text('wechat_another_screen', 'en'))).toBeVisible();
  expect(backend.creates).toHaveLength(0);
  await shot(page, 'galaxy-confirmation-375-en.png');
  await page.getByRole('button', { name: text('wechat_pay', 'en'), exact: true }).click();
  await expect(page.getByRole('img', { name: text('wechat_qr_alt', 'en') })).toBeVisible();
  await expect(page.getByRole('button', { name: text('wechat_cancel', 'en'), exact: true })).toBeVisible();
  await shot(page, 'galaxy-pending-375-en.png');
});

test('Kiosk German keeps long translated payment text scrollable and footer actions reachable', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 600 });
  await bootNative(page, 'de');
  await page.goto('/kiosk/membership');
  await page.getByRole('tab', { name: text('api_topup', 'de'), exact: true }).click();
  await page.locator('.km-recharge > .km-primary').click();
  await page.getByRole('button', { name: text('wechat_pay', 'de'), exact: true }).click();
  await expect(page.getByRole('img', { name: text('wechat_qr_alt', 'de') })).toBeVisible();
  const dialog = page.getByRole('dialog');
  const footer = dialog.locator('footer');
  for (const button of [text('wechat_cancel', 'de'), text('kiosk_return_selection', 'de')]) {
    const action = footer.getByRole('button', { name: button, exact: true });
    await expect(action).toBeVisible();
    const bounds = (await action.boundingBox())!;
    expect(bounds.height).toBeGreaterThanOrEqual(44);
    expect(bounds.y + bounds.height).toBeLessThanOrEqual(600);
  }
  await shot(page, 'kiosk-pending-1024x600-de.png');
  await footer.getByRole('button', { name: text('wechat_cancel', 'de'), exact: true }).click();
  await expect(dialog).toContainText(text('order_cancelled', 'de'));
});

test('Kiosk membership payment refreshes the actual Plus account snapshot and quotas', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 600 });
  const backend = await bootNative(page);
  await page.goto('/kiosk/membership');
  await page.getByRole('tab', { name: '会员', exact: true }).click();
  await page.getByRole('button', { name: '选择 Plus', exact: true }).click();
  await page.getByRole('button', { name: '微信支付', exact: true }).click();
  await expect(image(page)).toBeVisible();
  backend.pay();
  await expect(page.getByRole('dialog')).toContainText('微信支付成功', { timeout: 8000 });
  await expect.poll(backend.usageGets).toBeGreaterThanOrEqual(2);
  await page.getByRole('button', { name: '返回用量', exact: true }).click();
  await expect(page.locator('.km-account strong')).toHaveText('Plus');
  await expect(page.getByRole('progressbar')).toHaveCount(2);
  await expect(page.getByRole('progressbar').first()).toHaveAttribute('aria-valuenow', '100');
  await expect(page.getByRole('progressbar').last()).toHaveAttribute('aria-valuenow', '100');
  expect(backend.creates).toHaveLength(1);
  expect(backend.creates[0]).toMatchObject({ sku: 'membership_plus', provider: 'wechat' });
});
