import type { Page } from '@playwright/test';
import { resolve } from 'node:path';
import type { BillingOrder, MembershipCatalog, MembershipUsage } from '../../src/features/membership/types';
import { freezeClock, stubBackendStatics } from './fourup';
import { kioskMeJson } from './kioskIdentity';
import { parsePo } from './po';

// Shared browser-only membership fixture. Every request stays in this isolated page;
// no real billing, payment, GPU or server-state writes are made.
export const NOW = '2026-11-01T04:00:00Z';
const capabilities = { membership: true, usage: true, quotes: true, positions: true, orders: true, can_claim_free_report: false };
export const catalog: MembershipCatalog = {
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

export async function bootMembership(page: Page, options: { language?: string; autoPay?: boolean } = {}) {
  const language = options.language ?? 'cn';
  let autoPay = options.autoPay ?? true;
  let createError: string | null = null;
  const browserErrors: string[] = [];
  page.on('pageerror', error => {
    browserErrors.push(error.message);
    console.log(`[membership browser error] ${error.message}`);
  });
  let usage = structuredClone(initialUsage);
  let order: BillingOrder | null = null;
  let polls = 0;
  const requests: Array<Record<string, unknown>> = [];
  await page.route('**/assets/sounds/**', route => route.fulfill({ status: 204, body: '' }));
  await freezeClock(page, NOW);
  await page.addInitScript(lang => { localStorage.setItem('token', 'membership-runtime-fixture'); localStorage.setItem('katrain_language', lang); }, language);
  // Fail closed for endpoints outside this focused, isolated UI preview.
  await page.route('**/api/v1/**', route => route.fulfill({ status: 404, json: { detail: 'UI preview: endpoint not mocked' } }));
  await stubBackendStatics(page, language);
  const translations = new Map<string, Record<string, string>>();
  await page.route('**/api/translations*', route => {
    const lang = new URL(route.request().url()).searchParams.get('lang') ?? language;
    if (!translations.has(lang)) translations.set(lang, parsePo(resolve(process.cwd(), `../../i18n/locales/${lang}/LC_MESSAGES/katrain.po`)));
    return route.fulfill({ json: { lang, translations: translations.get(lang) } });
  });
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
    if (createError) return route.fulfill({ status: 503, json: { detail: { reason: createError } } });
    const topup = catalog.topups.find(item => item.sku === payload.sku);
    const plan = catalog.plans.find(item => `membership_${item.code}` === payload.sku);
    order = { id: 'UI-TEST-ORDER-001', sku: payload.sku, kind: topup ? 'topup' : 'membership', status: 'pending', amount_fen: topup?.amount_fen ?? plan!.amount_fen, currency: 'CNY', payments_mode: 'mock', provider: 'mock', created_at: NOW, expires_at: '2026-11-01T04:15:00Z', paid_at: null, fulfillment: null };
    return route.fulfill({ json: order });
  });
  await page.route('**/api/v1/billing/orders/UI-TEST-ORDER-001', route => {
    polls += 1;
    // Only a mocked server poll confirms payment; no page control grants local money.
    if (order && autoPay && polls >= 1) {
      const credits = catalog.topups.find(item => item.sku === order!.sku)?.credits ?? 0;
      order = { ...order, status: 'paid', paid_at: NOW, fulfillment: { credits, display_points: (credits / 100).toFixed(2) } };
      usage = { ...usage, revision: 2, wallet: { credits: 1000 + credits, display_points: ((1000 + credits) / 100).toFixed(2) } };
    }
    return route.fulfill({ json: order });
  });
  return { requests, browserErrors, polls: () => polls, setAutoPay: (value: boolean) => { autoPay = value; }, setCreateError: (value: string | null) => { createError = value; } };
}

