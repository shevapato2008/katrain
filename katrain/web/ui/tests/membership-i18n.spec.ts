import { expect, test, type Locator, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { bootMembership } from './helpers/membership';
import { parsePo } from './helpers/po';

// Real React/Vite and PO catalogs; only the existing billing fixture is simulated.
const OUT = resolve(process.cwd(), '../../../output/playwright/membership-i18n-20261104');
const LANGUAGES = ['cn', 'en', 'de', 'tw', 'jp', 'ko', 'es', 'fr', 'ru', 'tr', 'ua'] as const;
const VISUAL_LANGUAGES = new Set(['cn', 'en', 'de']);
type Surface = 'galaxy' | 'kiosk';
const tables = new Map<string, Record<string, string>>();
const table = (lang: string) => {
  if (!tables.has(lang)) tables.set(lang, parsePo(resolve(process.cwd(), `../../i18n/locales/${lang}/LC_MESSAGES/katrain.po`)));
  return tables.get(lang)!;
};
const copy = (lang: string, key: string, values: Record<string, string | number> = {}) => {
  const message = table(lang)[`membership:${key}`];
  expect(message, `${lang}: membership:${key} must come from the real PO catalog`).toBeTruthy();
  return message.replace(/\{(\w+)\}/g, (placeholder, name: string) => Object.hasOwn(values, name) ? String(values[name]) : placeholder);
};
const module = (page: Page, surface: Surface) => page.getByTestId(surface === 'kiosk' ? 'kiosk-membership-page' : 'membership-page');
async function switchLanguage(page: Page, lang: string) {
  // The public runtime singleton is also the Settings provider's language loader.
  // It allows switching an open modal without closing or recreating that modal.
  await page.evaluate(async language => {
    await (window as unknown as { i18n: { loadTranslations: (lang: string) => Promise<void> } }).i18n.loadTranslations(language);
  }, lang);
}
async function translatedContent(root: Locator, lang: string) {
  const content = await root.evaluate(el => [
    el.textContent,
    ...Array.from(el.querySelectorAll('[aria-label], [title]')).map(node => `${node.getAttribute('aria-label') ?? ''} ${node.getAttribute('title') ?? ''}`),
  ].join('\n'));
  expect(content).not.toMatch(/membership:[\w_]+/);
  expect(content).not.toMatch(/\{[A-Za-z_]\w*\}/);
  if (!['cn', 'tw', 'jp'].includes(lang)) expect(content).not.toMatch(/[\u3400-\u9fff]/u);
  if (['tw', 'jp'].includes(lang)) expect(content).not.toMatch(/[员积报额认单时账询]/u);
}
async function geometry(page: Page, surface: Surface) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  if (surface === 'kiosk') {
    const small = await page.locator('.km-page button:visible').evaluateAll(elements => elements.filter(el => {
      const r = el.getBoundingClientRect();
      return r.width < 43.5 || r.height < 43.5;
    }).map(el => ({ text: el.textContent, width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height })));
    expect(small, 'Kiosk membership controls retain 44px touch targets').toEqual([]);
    const outsideCards = await page.locator('.km-plan').evaluateAll(cards => cards.filter(card => {
      const bounds = card.getBoundingClientRect(), button = card.querySelector('button')!.getBoundingClientRect();
      return button.bottom > bounds.bottom + 0.5 || button.top < bounds.top;
    }).map(card => card.querySelector('button')!.textContent));
    expect(outsideCards, 'Translated plan actions remain inside their cards').toEqual([]);
    const actionBottoms = await page.locator('.km-plan button').evaluateAll(buttons => buttons.map(button => button.getBoundingClientRect().bottom));
    if (actionBottoms.length) expect(Math.max(...actionBottoms) - Math.min(...actionBottoms), 'Plan actions remain aligned').toBeLessThanOrEqual(1);
  }
}
async function shot(page: Page, name: string) {
  mkdirSync(OUT, { recursive: true });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: resolve(OUT, `${name}.png`), animations: 'disabled' });
}
async function dialogGeometry(page: Page, surface: Surface) {
  if (surface !== 'kiosk') return;
  const bounds = (await page.getByRole('dialog').boundingBox())!;
  expect(bounds.x).toBeGreaterThanOrEqual(0);
  expect(bounds.y).toBeGreaterThanOrEqual(56);
  expect(bounds.x + bounds.width).toBeLessThanOrEqual(1024);
  expect(bounds.y + bounds.height).toBeLessThanOrEqual(600);
}
async function checkTab(page: Page, surface: Surface, lang: string, index: number) {
  const root = module(page, surface);
  const key = index === 0 ? 'usage' : index === 1 ? 'api_topup' : 'plans';
  await expect(root.getByRole('tab').nth(index)).toHaveText(copy(lang, key));
  await root.getByRole('tab').nth(index).click();
  await expect(root.getByRole('tab').nth(index)).toHaveAttribute('aria-selected', 'true');
  await translatedContent(root, lang);
  await geometry(page, surface);
  if (surface === 'galaxy') {
    const refresh = (await root.getByRole('button', { name: copy(lang, 'refresh'), exact: true }).boundingBox())!;
    expect(refresh.x + refresh.width, 'Translated refresh action fits the viewport').toBeLessThanOrEqual(page.viewportSize()!.width);
    const intro = (await root.getByText(copy(lang, 'galaxy_intro'), { exact: true }).boundingBox())!;
    const overlaps = Math.min(intro.x + intro.width, refresh.x + refresh.width) > Math.max(intro.x, refresh.x) + 0.5
      && Math.min(intro.y + intro.height, refresh.y + refresh.height) > Math.max(intro.y, refresh.y) + 0.5;
    expect(overlaps, 'Intro text and refresh action do not overlap').toBe(false);
    const selected = root.getByRole('tab').nth(index);
    await expect.poll(() => selected.evaluate(el => {
      const bounds = el.getBoundingClientRect();
      const range = document.createRange();
      range.selectNodeContents(el);
      const text = range.getBoundingClientRect();
      return bounds.left >= 0 && bounds.right <= innerWidth && text.left >= bounds.left - 1 && text.right <= bounds.right + 1;
    }), { message: 'Selected tab and its complete label remain reachable in the viewport' }).toBe(true);
  }
}

for (const surface of ['galaxy', 'kiosk'] as const) {
  test(`${surface}: all 11 PO catalogs resolve usage, plans and top-up at runtime`, async ({ page }) => {
    test.setTimeout(120_000);
    await page.setViewportSize(surface === 'kiosk' ? { width: 1024, height: 600 } : { width: 1440, height: 900 });
    const backend = await bootMembership(page);
    await page.goto(`/${surface}/membership`);
    await expect(page.getByRole('progressbar')).toHaveCount(2);
    for (const lang of LANGUAGES) {
      await switchLanguage(page, lang);
      for (const index of [0, 2, 1]) {
        await checkTab(page, surface, lang, index);
        if (VISUAL_LANGUAGES.has(lang)) {
          await shot(page, `${surface}-${lang}-${['usage', 'topup', 'plans'][index]}`);
          if (surface === 'kiosk' && index !== 0) {
            const footer = module(page, surface).locator(index === 2 ? '.km-plan-footer' : '.km-recharge > .km-footnote');
            await footer.scrollIntoViewIfNeeded();
            await expect(footer).toBeInViewport({ ratio: 1 });
            await shot(page, `${surface}-${lang}-${index === 2 ? 'plans' : 'topup'}-footer`);
          }
        }
      }
    }
    expect(backend.requests).toEqual([]);
    expect(backend.browserErrors).toEqual([]);
  });

  test(`${surface}: German decimal display preserves numeric progress values`, async ({ page }) => {
    await page.setViewportSize(surface === 'kiosk' ? { width: 1024, height: 600 } : { width: 1440, height: 900 });
    await bootMembership(page, { language: 'de' });
    await page.goto(`/${surface}/membership`);
    const progress = page.getByRole('progressbar').first();
    await expect(progress).toHaveAttribute('aria-valuenow', '65.6');
    await expect(module(page, surface)).toContainText('65,6');
    const width = await progress.evaluate((el, surface) => surface === 'kiosk'
      ? (el.querySelector('i') as HTMLElement).style.width
      : (el.querySelector('.MuiLinearProgress-bar') as HTMLElement).style.transform, surface);
    expect(width).not.toContain(',');
    expect(Number.parseFloat(width.replace('translateX(', ''))).toBeCloseTo(surface === 'kiosk' ? 65.6 : -34.4, 5);
  });

  test(`${surface}: open checkout, paid receipt and error translate without new orders`, async ({ page }) => {
    test.setTimeout(60_000);
    await page.setViewportSize(surface === 'kiosk' ? { width: 1024, height: 600 } : { width: 1440, height: 900 });
    const backend = await bootMembership(page, { language: 'en', autoPay: false });
    await page.goto(`/${surface}/membership`);
    await expect(page.getByRole('progressbar')).toHaveCount(2);
    await checkTab(page, surface, 'en', 1);
    const root = module(page, surface);
    // Select 30 CNY explicitly; no translated UI string becomes a request identifier.
    if (surface === 'kiosk') await root.locator('.km-amounts button').nth(1).click();
    else await root.getByRole('button', { name: copy('en', 'topup_option', { amount: 'CN¥30', points: '30.00' }), exact: true }).click();
    const selected = surface === 'kiosk' ? root.locator('.km-amounts button').nth(1) : root.getByRole('button', { name: copy('en', 'topup_option', { amount: 'CN¥30', points: '30.00' }), exact: true });
    await expect(selected).toHaveAttribute('aria-pressed', 'true');
    const purchase = surface === 'kiosk' ? root.locator('.km-recharge > .km-primary') : root.getByRole('button', { name: copy('en', 'topup_amount', { amount: 'CN¥30' }), exact: true });
    await purchase.click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await switchLanguage(page, 'de');
    await translatedContent(dialog, 'de');
    await expect(dialog).toContainText('30');
    expect(backend.requests).toHaveLength(surface === 'kiosk' ? 1 : 0);
    if (surface === 'galaxy') await dialog.getByRole('button', { name: copy('de', 'create_order'), exact: true }).click();
    await expect(dialog).toContainText('UI-TEST-ORDER-001');
    await dialogGeometry(page, surface);
    expect(backend.requests).toHaveLength(1);
    expect(backend.requests[0]).toMatchObject({ sku: 'topup_30', provider: 'mock' });
    await shot(page, `${surface}-de-checkout`);
    backend.setAutoPay(true);
    const paidKey = surface === 'kiosk' ? 'kiosk_order_server_paid' : 'order_paid';
    await expect(dialog).toContainText(copy('de', paidKey), { timeout: 8000 });
    await switchLanguage(page, 'en');
    await translatedContent(dialog, 'en');
    await expect(dialog).toContainText(copy('en', paidKey));
    await dialogGeometry(page, surface);
    await shot(page, `${surface}-en-receipt`);
    expect(backend.requests).toHaveLength(1);
    const closeKey = surface === 'kiosk' ? 'kiosk_return_usage' : 'done';
    await dialog.getByRole('button', { name: copy('en', closeKey), exact: true }).click();
    await checkTab(page, surface, 'en', 1);
    backend.setCreateError('payment_disabled');
    await purchase.click();
    if (surface === 'galaxy') await dialog.getByRole('button', { name: copy('en', 'create_order'), exact: true }).click();
    const errorKey = surface === 'kiosk' ? 'kiosk_order_uncertain' : 'order_result_unknown';
    await expect(dialog).toContainText(copy('en', errorKey));
    await switchLanguage(page, 'de');
    await expect(dialog).toContainText(copy('de', errorKey));
    await translatedContent(dialog, 'de');
    await dialogGeometry(page, surface);
    await shot(page, `${surface}-de-order-error`);
    expect(backend.requests).toHaveLength(2);
    expect(backend.browserErrors).toEqual([]);
  });
}

test('Galaxy 375px: Chinese, English and German plans and top-up stay usable', async ({ page }) => {
  test.setTimeout(90_000);
  await page.setViewportSize({ width: 375, height: 812 });
  await bootMembership(page);
  await page.goto('/galaxy/membership');
  await expect(page.getByRole('progressbar')).toHaveCount(2);
  for (const lang of ['cn', 'en', 'de']) {
    await switchLanguage(page, lang);
    for (const index of [2, 1]) {
      await checkTab(page, 'galaxy', lang, index);
      await module(page, 'galaxy').getByText(copy(lang, 'galaxy_title'), { exact: true }).scrollIntoViewIfNeeded();
      await shot(page, `galaxy-mobile-${lang}-${index === 2 ? 'plans' : 'topup'}`);
      if (index === 1) {
        const clippedAmounts = await module(page, 'galaxy').locator('button[aria-pressed][aria-label]').evaluateAll(buttons => buttons.filter(button => {
          const bounds = button.getBoundingClientRect();
          const amount = button.querySelector('.MuiTypography-root');
          if (!amount) return false;
          const range = document.createRange();
          range.selectNodeContents(amount);
          const text = range.getBoundingClientRect();
          return text.left < bounds.left || text.right > bounds.right;
        }).map(button => button.getAttribute('aria-label')));
        expect(clippedAmounts, 'Localized CNY amount labels fit inside each mobile top-up option').toEqual([]);
      }
      const amount = new Intl.NumberFormat(lang === 'cn' ? 'zh-CN' : lang === 'de' ? 'de-DE' : 'en-US', {
        style: 'currency', currency: 'CNY', currencyDisplay: 'symbol', minimumFractionDigits: 0, maximumFractionDigits: 2,
      }).format(30);
      const action = module(page, 'galaxy').getByRole('button', {
        name: index === 2 ? copy(lang, 'select_plan', { plan: 'Max' }) : copy(lang, 'topup_amount', { amount }), exact: true,
      });
      await action.scrollIntoViewIfNeeded();
      await expect(action).toBeEnabled();
      await expect(action).toBeInViewport({ ratio: 1 });
      if (lang === 'de') await shot(page, `galaxy-mobile-de-${index === 2 ? 'plans-max' : 'topup-action'}`);
    }
  }
});
