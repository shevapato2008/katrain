import { expect, test, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import type { BillingOrder, MembershipCatalog, MembershipUsage } from '../src/features/membership/types';
import { freezeClock, stubBackendStatics } from './helpers/fourup';
import { kioskMeJson } from './helpers/kioskIdentity';

// Browser-only fixtures: no production module imports or real billing/payment/GPU calls.
const OUT = resolve(process.cwd(), '../../../output/playwright/membership-max-clarity-20261102');
const NOW = '2026-11-01T04:00:00Z';
const capabilities = { membership: true, usage: true, quotes: true, positions: true, orders: true, can_claim_free_report: false };
const catalog: MembershipCatalog = {
  catalog_version: 'ui-runtime-final-week', server_now: NOW, environment: 'TEST', membership_mode: 'enabled',
  capabilities, payments_mode: 'mock',
  plans: [
    { code: 'plus', name: 'Plus', amount_fen: 3900, term_days: 30, term_units: 9030, week_units: 3010, term_report_reference: 30, week_report_reference: 10, full_use_savings_percent: 56.8, sale_enabled: true },
    { code: 'pro', name: 'Pro', amount_fen: 9900, term_days: 30, term_units: 27090, week_units: 9030, term_report_reference: 90, week_report_reference: 30, full_use_savings_percent: 63.5, sale_enabled: true },
    { code: 'max', name: 'Max', amount_fen: 19900, term_days: 30, term_units: 72240, week_units: 24080, term_report_reference: 240, week_report_reference: 80, full_use_savings_percent: 72.5, sale_enabled: true },
  ],
  topups: [10, 30, 100].map(amount => ({ sku: `topup_${amount}`, amount_fen: amount * 100, credits: amount * 100, display_points: amount.toFixed(2) })),
  profiles: { normal: { visits: 500, credits_per_position: 1, display_points_per_position: '0.01' }, advanced: { visits: 2000, credits_per_position: 4, display_points_per_position: '0.04' } },
};
const initialUsage: MembershipUsage = {
  catalog_version: catalog.catalog_version, server_now: NOW, revision: 1, environment: 'TEST', capabilities, payments_mode: 'mock',
  plan: { current: { code: 'pro', name: 'Pro', starts_at: NOW, ends_at: '2026-12-01T04:00:00Z' }, next: null },
  term: { limit: 27090, used: 9030, reserved: 301, remaining: 17759, percent: 65.6, reset_at: '2026-12-01T04:00:00Z' },
  week: { limit: 9030, used: 1505, reserved: 301, remaining: 7224, percent: 80, reset_at: '2026-11-01T16:00:00Z' },
  wallet: { credits: 1000, display_points: '10.00' }, free: { eligible: false, remaining: 0, limit: 1, reset_at: '2026-11-01T16:00:00Z', reason: 'paid_membership' },
};

async function boot(page: Page) {
  mkdirSync(OUT, { recursive: true });
  page.on('pageerror', error => console.log(`[membership browser error] ${error.message}`));
  let usage = structuredClone(initialUsage);
  let order: BillingOrder | null = null;
  let polls = 0;
  const requests: Array<Record<string, unknown>> = [];
  await page.route('**/assets/sounds/**', route => route.fulfill({ status: 204, body: '' }));
  await freezeClock(page, NOW);
  await page.addInitScript(() => { localStorage.setItem('token', 'membership-runtime-fixture'); localStorage.setItem('katrain_language', 'cn'); });
  // Fail closed for endpoints outside this focused, isolated UI preview.
  await page.route('**/api/v1/**', route => route.fulfill({ status: 404, json: { detail: 'UI preview: endpoint not mocked' } }));
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', route => route.fulfill({ json: kioskMeJson({ username: 'fan', credits: 1000 }) }));
  await page.route('**/api/v1/health', route => route.fulfill({ json: { status: 'ok', engines: { local: 'reachable', cloud: 'reachable' } } }));
  await page.route('**/api/v1/geometry/status', route => route.fulfill({ json: { phase: 'disabled', session_calibrated: false, last_error: null, capabilities: { camera_ready: false, led_ready: false, geometry_ready: false, recognition_ready: false } } }));
  await page.route('**/api/v1/vision/status', route => route.fulfill({ json: { enabled: false, camera_connected: false, pose_locked: false, sync_state: 'idle', bound_session_id: null, recognition_ready: false, led_connected: false } }));
  await page.route('**/api/v1/billing/catalog', route => route.fulfill({ json: catalog }));
  await page.route('**/api/v1/billing/usage', route => route.fulfill({ json: usage }));
  await page.route('**/api/v1/billing/orders', async route => {
    if (route.request().method() === 'GET') return route.fulfill({ json: { orders: order ? [order] : [] } });
    const payload = route.request().postDataJSON();
    requests.push(payload);
    const topup = catalog.topups.find(item => item.sku === payload.sku);
    const plan = catalog.plans.find(item => `membership_${item.code}` === payload.sku);
    order = { id: 'UI-TEST-ORDER-001', sku: payload.sku, kind: topup ? 'topup' : 'membership', status: 'pending', amount_fen: topup?.amount_fen ?? plan!.amount_fen, currency: 'CNY', payments_mode: 'mock', provider: 'mock', created_at: NOW, expires_at: '2026-11-01T04:15:00Z', paid_at: null, fulfillment: null };
    return route.fulfill({ json: order });
  });
  await page.route('**/api/v1/billing/orders/UI-TEST-ORDER-001', route => {
    polls += 1;
    // Only a mocked server poll confirms payment; no page control grants local money.
    if (order && polls >= 1) {
      const credits = catalog.topups.find(item => item.sku === order!.sku)?.credits ?? 0;
      order = { ...order, status: 'paid', paid_at: NOW, fulfillment: { credits, display_points: (credits / 100).toFixed(2) } };
      usage = { ...usage, revision: 2, wallet: { credits: 1000 + credits, display_points: ((1000 + credits) / 100).toFixed(2) } };
    }
    return route.fulfill({ json: order });
  });
  return { requests, polls: () => polls };
}

const shot = (page: Page, name: string) => page.screenshot({ path: resolve(OUT, name), animations: 'disabled' });
const noHorizontalOverflow = async (page: Page) => expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
async function noInternalUnits(page: Page) {
  await expect(page.getByTestId('membership-page').or(page.getByTestId('kiosk-membership-page'))).not.toContainText(/标准单位|会员积分|日均/);
}
async function galaxyReference(page: Page, tab: string, name: string) {
  const reference = await page.context().newPage();
  await reference.setViewportSize(page.viewportSize()!);
  await reference.goto(`http://127.0.0.1:8876/docs/design/membership-recharge-2026-10-31/index.html?tab=${tab}&capture=1&revision=final-week`);
  await reference.evaluate(() => document.fonts.ready);
  await shot(reference, name);
  await reference.close();
}

async function kioskReference(page: Page, tab: string, name: string) {
  const reference = await page.context().newPage();
  await reference.setViewportSize({ width: 1600, height: 1100 });
  await reference.goto(`http://127.0.0.1:8876/docs/design/kiosk-current-based-redesign-2026-10-14.html?design=final-week#membership-${tab}`);
  await expect(reference.locator('#stage')).toContainText('会员与充值');
  await reference.evaluate(() => document.fonts.ready);
  await reference.locator('#stage').screenshot({ path: resolve(OUT, name), animations: 'disabled' });
  await reference.close();
}

test('Galaxy 1440: usage, plans, recharge and server-confirmed order refresh', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const backend = await boot(page);
  await page.goto('/galaxy/membership');
  await expect(page.getByRole('progressbar')).toHaveCount(2);
  await expect(page.getByRole('progressbar').first()).toHaveAttribute('aria-valuenow', '65.6');
  await expect(page.getByRole('progressbar').last()).toHaveAttribute('aria-valuenow', '80');
  await noInternalUnits(page); await noHorizontalOverflow(page);
  await shot(page, 'galaxy-usage-1440.png');
  await galaxyReference(page, 'usage', 'galaxy-usage-reference-1440.png');
  await page.getByRole('tab', { name: '会员', exact: true }).click();
  await expect(page.getByRole('button', { name: '选择 Max' })).toBeEnabled();
  for (const n of [10, 30, 80]) await expect(page.getByText(`普通报告，每周最多约${n}盘`)).toBeVisible();
  await shot(page, 'galaxy-plans-1440.png');
  await galaxyReference(page, 'plans', 'galaxy-plans-reference-1440.png');
  await page.getByRole('button', { name: '续费 Pro', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('在已有会员到期后顺延');
  await page.getByRole('dialog').getByRole('button', { name: '关闭', exact: true }).click();
  await page.getByRole('tab', { name: 'API 充值', exact: true }).click();
  await expect(page.getByRole('heading', { name: '3.01积分' })).toBeVisible();
  await page.getByRole('button', { name: '高级', exact: true }).click();
  await expect(page.getByRole('heading', { name: '12.04积分' })).toBeVisible();
  await shot(page, 'galaxy-recharge-1440.png');
  await page.getByRole('button', { name: '10 元，到账 10.00 积分', exact: true }).click();
  await page.getByRole('button', { name: '充值 10 元', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('TEST 模拟订单，不会真实收款');
  await page.getByRole('dialog').getByRole('button', { name: '创建订单', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('等待付款');
  await shot(page, 'galaxy-order-pending-1440.png');
  await expect(page.getByRole('dialog')).toContainText('实际到账 10.00 积分', { timeout: 8000 });
  expect(backend.polls()).toBeGreaterThan(0);
  expect(backend.requests).toHaveLength(1);
  expect(backend.requests[0]).toMatchObject({ sku: 'topup_10', provider: 'mock' });
  await page.getByRole('dialog').getByRole('button', { name: '完成', exact: true }).click();
  await expect(page.getByTestId('membership-page')).toContainText('20.00');
});

test('Kiosk 1024×600: usage, plans, pricing and in-canvas order/dialog', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 600 });
  const backend = await boot(page);
  await page.goto('/kiosk/membership');
  await expect(page.getByRole('progressbar')).toHaveCount(2);
  await expect(page.locator('.kiosk-dock')).toHaveCount(0);
  await noInternalUnits(page); await noHorizontalOverflow(page);
  await shot(page, 'kiosk-usage-1024.png');
  await kioskReference(page, 'usage', 'kiosk-usage-reference-1024.png');
  const usageScroll = page.locator('.km-scroll > .kiosk-side__scroll');
  if (await usageScroll.evaluate(el => el.scrollHeight > el.clientHeight + 1)) {
    const area = (await usageScroll.boundingBox())!;
    await page.mouse.move(area.x + area.width / 2, area.y + area.height / 2);
    await page.mouse.wheel(0, 300);
    await expect.poll(() => usageScroll.evaluate(el => el.scrollTop)).toBeGreaterThan(0);
  }
  await page.getByRole('tab', { name: '会员', exact: true }).click();
  await expect(page.getByRole('button', { name: '选择 Max' })).toBeEnabled();
  await shot(page, 'kiosk-plans-1024.png');
  await kioskReference(page, 'plans', 'kiosk-plans-reference-1024.png');
  await page.getByRole('button', { name: '会员额度与优惠说明' }).click();
  await expect(page.getByRole('dialog')).toContainText('本期普通报告参考');
  expect(await page.getByRole('dialog').evaluate(el => !!el.closest('.kiosk-screen'))).toBe(true);
  await shot(page, 'kiosk-quota-dialog-1024.png');
  await page.getByRole('button', { name: '知道了', exact: true }).click();
  await page.getByRole('tab', { name: 'API充值', exact: true }).click();
  await expect(page.locator('.km-report-quote')).toContainText('3.01');
  await expect(page.locator('.km-report-quote')).toContainText('12.04');
  await shot(page, 'kiosk-recharge-1024.png');
  await page.getByRole('button', { name: /^充值 ¥\s*10\.00$/ }).click();
  await expect(page.getByRole('dialog')).toContainText('TEST模拟订单 · 不会真实收款');
  const bounds = await page.getByRole('dialog').boundingBox();
  expect(bounds!.x).toBeGreaterThanOrEqual(0); expect(bounds!.y).toBeGreaterThanOrEqual(56);
  expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(600);
  await expect(page.getByRole('dialog')).toContainText('服务端已确认支付', { timeout: 8000 });
  expect(backend.requests).toHaveLength(1);
  await page.getByRole('button', { name: '返回用量', exact: true }).click();
  await expect(page.locator('.km-wallet')).toContainText('20.00');
  const smallButtons = await page.locator('.km-page button:visible').evaluateAll(elements => elements.filter(el => { const r = el.getBoundingClientRect(); return r.width < 43.5 || r.height < 43.5; }).map(el => el.textContent));
  expect(smallButtons).toEqual([]);
});

test('Galaxy 375: main membership page has no horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await boot(page);
  await page.goto('/galaxy/membership?tab=plans');
  await expect(page.getByRole('button', { name: '选择 Plus', exact: true })).toBeVisible();
  await noHorizontalOverflow(page); await noInternalUnits(page);
  await shot(page, 'galaxy-plans-375.png');
  await galaxyReference(page, 'plans', 'galaxy-plans-reference-375.png');
  await page.getByRole('button', { name: '选择 Max' }).scrollIntoViewIfNeeded();
  await expect(page.getByRole('button', { name: '选择 Max' })).toBeEnabled();
  await noHorizontalOverflow(page);
});

async function consumptionBackend(page: Page, source: 'membership' | 'wallet' = 'membership') {
  const positionRequests: Array<Record<string, unknown>> = [];
  const reportRequests: Array<Record<string, unknown>> = [];
  const quoteRequests: Array<Record<string, unknown>> = [];
  let report: Record<string, unknown> | null = null;
  const game = { id: 'runtime-game', user_id: 1, title: '研究测试对局', player_black: '黑方', player_white: '白方',
    board_size: 19, komi: 7.5, rules: 'chinese', move_count: 2, source: 'research', category: 'game', game_type: 'free',
    created_at: NOW, sgf_content: '(;FF[4]GM[1]SZ[19]KM[7.5]RU[chinese];B[pd];W[dp])' };
  await page.route('**/api/v1/user-games/**', route => route.fulfill({ json: game }));
  await page.route('**/api/v1/user-games', route => route.fulfill({ json: route.request().method() === 'POST' ? game : { items: [game], total: 1, page: 1, page_size: 20, authority: 'cloud' } }));
  await page.route('**/api/v1/billing/quotes', route => {
    const payload = route.request().postDataJSON();
    quoteRequests.push(payload);
    return route.fulfill({ json: { token: `signed-${payload.kind}-${quoteRequests.length}`, catalog_version: catalog.catalog_version,
      environment: 'TEST', kind: payload.kind, profile: payload.profile, units: payload.kind === 'report' ? 3 : 1,
      wallet_max_credits: payload.kind === 'report' ? 301 : 1, wallet_max_display_points: payload.kind === 'report' ? '3.01' : '0.01',
      source_policy: 'membership_then_wallet', source, expires_at: '2026-11-01T04:15:00Z', server_now: NOW, fingerprint: 'full-history-position' } });
  });
  await page.route('**/api/v1/analysis/positions', route => {
    positionRequests.push(route.request().postDataJSON());
    return route.fulfill({ json: { operation_id: 'runtime-position', state: 'succeeded', source: 'membership', profile: 'normal', units: 1,
      wallet_credits: 0, catalog_version: catalog.catalog_version, result: { ownership: Array(361).fill(0.2),
        moves: [{ move: 'D4', visits: 500, winrate: 0.61, score_lead: 2.3, pv: ['D4'] }], rootInfo: { visits: 500, winrate: 0.61, scoreLead: 2.3 } } } });
  });
  await page.route('**/api/v1/reports/**', route => {
    if (route.request().url().endsWith('/summary')) return route.fulfill({ json: { pending: report ? 1 : 0, running: 0, completed: 0, failed: 0 } });
    if (route.request().method() === 'POST') {
      reportRequests.push(route.request().postDataJSON());
      report = { id: 77, user_game_id: game.id, status: 'pending', report_type: 'normal', total_moves: 2, analyzed_moves: 0,
        requested_visits: 500, started_at: null, completed_at: null, operation_id: 'runtime-report', source: 'membership', wallet_credits: 0 };
      return route.fulfill({ json: report });
    }
    return route.fulfill({ json: report ? [report] : [] });
  });
  return { positionRequests, reportRequests, quoteRequests };
}

for (const surface of ['galaxy', 'kiosk'] as const) {
  test(`Max and clarity: ${surface} catalog plans and wallet confirmation`, async ({ page }) => {
    await page.setViewportSize(surface === 'kiosk' ? { width: 1024, height: 600 } : { width: 1440, height: 900 });
    const backend = await boot(page);
    const consumption = await consumptionBackend(page, 'wallet');
    await page.goto(`/${surface}/membership?tab=plans`);
    if (surface === 'kiosk') await page.getByRole('tab', { name: '会员', exact: true }).click();
    const membershipPage = page.getByTestId(surface === 'kiosk' ? 'kiosk-membership-page' : 'membership-page');
    for (const count of [30, 90, 240]) await expect(membershipPage).toContainText(`30天共约${count}盘`);
    await expect(page.getByRole('button', { name: '选择 Max', exact: true })).toBeEnabled();
    await noInternalUnits(page); await noHorizontalOverflow(page);
    if (surface === 'kiosk') {
      expect(await page.locator('.km-scroll > .kiosk-side__scroll').evaluate(el => el.scrollHeight <= el.clientHeight + 1)).toBe(true);
      expect(await page.locator('.km-plan').evaluateAll(plans => plans.every(plan => {
        const card = plan.getBoundingClientRect(), button = plan.querySelector('button')!.getBoundingClientRect();
        return button.bottom <= card.bottom && button.top >= card.top;
      }))).toBe(true);
    }
    await shot(page, `${surface}-max-plans.png`);
    await page.getByRole('button', { name: '选择 Max', exact: true }).click();
    await expect(page.getByRole('dialog')).toContainText(surface === 'kiosk' ? '199.00' : '¥199');
    if (surface === 'kiosk') {
      expect(backend.requests[0]).toMatchObject({ sku: 'membership_max', provider: 'mock' });
    } else {
      expect(backend.requests).toHaveLength(0);
    }
    await page.goto(`/${surface}/research?user_game_id=runtime-game&analyze=1`);
    await page.getByRole('button', { name: '领地', exact: true }).click();
    const dialog = page.getByTestId('consumption-quote');
    const confirm = dialog.getByRole('button', { name: '使用API积分，最多扣0.01', exact: true });
    await expect(confirm).toBeVisible();
    expect(consumption.positionRequests).toHaveLength(0);
    const bounds = (await confirm.boundingBox())!;
    expect(bounds.x).toBeGreaterThanOrEqual(0); expect(bounds.y).toBeGreaterThanOrEqual(0);
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(page.viewportSize()!.width);
    expect(bounds.y + bounds.height).toBeLessThanOrEqual(page.viewportSize()!.height);
    await shot(page, `${surface}-wallet-confirmation.png`);
    await dialog.getByRole('button', { name: '取消', exact: true }).click();
    expect(consumption.positionRequests).toHaveLength(0);
  });
}

for (const surface of ['galaxy', 'kiosk'] as const) {
  test(`${surface}: explicit consumption quote, cancellation, shared position result and report authorization`, async ({ page }) => {
    await page.setViewportSize(surface === 'kiosk' ? { width: 1024, height: 600 } : { width: 1440, height: 900 });
    await boot(page);
    const backend = await consumptionBackend(page);
    const rawRequests: string[] = [];
    page.on('request', request => { if (/\/api\/(analysis\/(quick|scan|current)|hint)(?:[/?]|$)/.test(request.url())) rawRequests.push(request.url()); });
    await page.goto(`/${surface}/research?user_game_id=runtime-game&analyze=1`);
    await page.getByRole('button', { name: '领地', exact: true }).click();
    const dialog = page.getByTestId('consumption-quote');
    await expect(dialog).toContainText('最多 0.01 积分');
    expect(backend.positionRequests).toHaveLength(0);
    if (surface === 'kiosk') expect(await dialog.evaluate(element => !!element.closest('.kiosk-screen'))).toBe(true);
    await shot(page, `${surface}-consumption-quote.png`);
    await dialog.getByRole('button', { name: '取消', exact: true }).click();
    expect(backend.positionRequests).toHaveLength(0);
    await page.getByRole('button', { name: '支招', exact: true }).click();
    await dialog.getByRole('button', { name: '确认并开始', exact: true }).click();
    await expect(dialog).toHaveCount(0);
    expect(backend.positionRequests).toHaveLength(1);
    expect(backend.positionRequests[0]).toMatchObject({ quote_token: expect.stringMatching(/^signed-position/), idempotency_key: expect.any(String), sgf: expect.stringContaining('B[pd]') });
    await page.getByRole('button', { name: '领地', exact: true }).click();
    expect(backend.positionRequests).toHaveLength(1);
    await page.getByRole('button', { name: '创建复盘报告', exact: true }).click();
    await expect(dialog).toContainText('最多 3.01 积分');
    expect(backend.reportRequests).toHaveLength(0);
    await dialog.getByRole('button', { name: '确认并开始', exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/${surface}/report$`));
    expect(backend.reportRequests).toHaveLength(1);
    expect(backend.reportRequests[0]).toMatchObject({ user_game_id: 'runtime-game', quote_token: expect.stringMatching(/^signed-report/), idempotency_key: expect.any(String) });
    expect(rawRequests).toEqual([]);
  });
}
