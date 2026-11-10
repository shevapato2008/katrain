import { expect, test } from '@playwright/test';

test.use({ viewport: { width: 1024, height: 600 },
  ...(process.env.KIOSK_FONT_TEST_CHROME ? { channel: 'chrome' as const } : {}),
});

test('kiosk changes Chinese faces while Latin, mono, and brand remain fixed', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'typography-test');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/auth/me', route => route.fulfill({ json: { id: 1, username: '张三', rank: '5段', credits: 0 } }));
  await page.route('**/api/v1/kiosk-preferences/typography', route => route.fulfill({ json: { font: 'wenkai', size: 'large' } }));
  await page.goto('/kiosk/play');
  await page.locator('.kiosk').waitFor();
  await page.evaluate(() => {
    const root = document.querySelector('.kiosk')!;
    for (const [id, value, family] of [
      ['cjk-probe', '中文设置，棋谱。', 'var(--font-serif)'],
      ['latin-probe', 'StellaBox AI 123', 'var(--font-serif)'],
      ['mono-probe', 'R12 123', 'var(--font-mono)'],
    ]) {
      const span = document.createElement('span');
      span.id = id;
      span.textContent = value;
      span.style.fontFamily = family;
      span.style.position = 'absolute';
      span.style.top = `${120 + root.querySelectorAll('[id$="-probe"]').length * 30}px`;
      span.style.left = '20px';
      span.style.zIndex = '9999';
      root.appendChild(span);
    }
    const time = document.createElement('time');
    time.id = 'time-probe';
    time.textContent = '18:01';
    root.appendChild(time);
    const detail = document.createElement('dd');
    detail.id = 'detail-probe';
    detail.textContent = '—';
    root.appendChild(detail);
  });
  await expect(page.locator('#time-probe')).toHaveAttribute('data-kiosk-base-size', '');
  await page.locator('#detail-probe').evaluate(el => { el.firstChild!.textContent = '47.1'; });
  await expect(page.locator('#detail-probe')).toHaveAttribute('data-kiosk-base-size', '');

  const cdp = await page.context().newCDPSession(page);
  await cdp.send('DOM.enable');
  await cdp.send('CSS.enable');
  const family = async (selector: string) => {
    await page.evaluate(() => document.fonts.ready);
    const { root } = await cdp.send('DOM.getDocument', { depth: -1 });
    const { nodeId } = await cdp.send('DOM.querySelector', { nodeId: root.nodeId, selector });
    const { fonts } = await cdp.send('CSS.getPlatformFontsForNode', { nodeId });
    return (fonts as { familyName: string; glyphCount: number }[]).map(font => font.familyName).join(',');
  };

  const latin = await family('#latin-probe');
  const mono = await family('#mono-probe');
  const brand = await family('.kiosk-topbar__brand-zh');
  expect(latin).toMatch(/Newsreader|Geist/);
  expect(mono).toMatch(/IBM Plex Mono|JetBrains Mono/);
  expect(brand).toMatch(/Long Cang/);

  const choices = [
    ['"SmartBox Kai"', /LXGW WenKai/],
    ['"SmartBox CNS Kai"', /TW.Kai/],
    ['"SmartBox DaoLi"', /Alimama|DaoLi/],
    ['"SmartBox Noto Sans CJK"', /Noto Sans CJK/],
  ] as const;
  for (const [face, expected] of choices) {
    await page.evaluate(value => document.body.style.setProperty('--kiosk-cjk-font', value), face);
    const chinese = await family('#cjk-probe');
    expect(chinese, `face ${face} rendered with ${chinese}`).toMatch(expected);
    expect(await family('#latin-probe')).toBe(latin);
    expect(await family('#mono-probe')).toBe(mono);
    expect(await family('.kiosk-topbar__brand-zh')).toBe(brand);
  }

  // A text node added after the route rendered must receive its unscaled base
  // size, while the brand's designed size remains fixed.
  await expect(page.locator('#cjk-probe')).toHaveAttribute('data-kiosk-base-size', '');
  const baseSize = await page.locator('#cjk-probe').evaluate(el => parseFloat(getComputedStyle(el).fontSize));
  const brandSize = await page.locator('.kiosk-topbar__brand-zh').evaluate(el => getComputedStyle(el).fontSize);
  await page.evaluate(() => {
    document.body.style.setProperty('--kiosk-size-step', '4px');
    document.body.setAttribute('data-kiosk-font-size', 'small');
  });
  await expect.poll(() => page.locator('#cjk-probe').evaluate(el => parseFloat(getComputedStyle(el).fontSize)))
    .toBe(Math.max(12, baseSize - 4));
  expect(await page.locator('.kiosk-topbar__brand-zh').evaluate(el => getComputedStyle(el).fontSize)).toBe(brandSize);
});
