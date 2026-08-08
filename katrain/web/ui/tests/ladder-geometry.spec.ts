/**
 * Real-browser load-bearing gates for the 升降级对弈 setup pages.
 *
 * These replace `ladder-kiosk-setup.spec.ts` (S4) and `ladder-settlement-geometry.spec.ts`
 * (S2), both of which were deleted together with the implementation they guarded when the
 * feature was reconciled onto develop's `features/aiLadder/*` components on 2026-08-05.
 * The behaviours they measured are still load-bearing; the components under them changed.
 *
 * What is faked here is INPUT (the ladder status payload). Every assertion is on a number
 * Chromium computed — scrollHeight/clientHeight, a scrollTop read back after a real wheel
 * event, and bounding boxes against the nearest clipping ancestor. Nothing in this file
 * would pass in jsdom, which is the point.
 *
 * The two pages carry OPPOSITE load-bearing contracts and each needs its own gate:
 *   - kiosk: the ranked panel is `overflow: hidden` by design (no scrollbar on a 7" panel),
 *     so the content MUST fit. This assertion has failed for real: at band padding 16px the
 *     content measured 524 into a 481 box and pushed the start button below the fold.
 *   - galaxy: the content is taller than a short desktop viewport and MAIN is the scroller,
 *     so the CTA must be genuinely reachable — programmatically AND by wheel.
 */

import { expect, test, type Page, type Route } from '@playwright/test';

const SHORT_VIEWPORT = { width: 1024, height: 600 };

const fulfillJson = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

/** Worst case for height: placed + the longest rank name in the catalog + the provisional
 *  note (the tallest of the three seating notes) + a full recent-form row. */
const TALLEST_STATUS = {
  view_state: 'ready',
  placement_state: {
    phase: 'placed',
    rung: {
      rung: 41,
      rank_name: '超越人类',
      certification_status: 'provisional',
      availability: 'unavailable',
      route: 'server',
    },
  },
  current_opponent: {
    rung: 41,
    rank_name: '超越人类',
    certification_status: 'provisional',
    availability: 'unavailable',
    route: 'server',
  },
  recent_ranked_results: ['win', 'loss', 'win', 'win', 'loss'],
  net_score: 2,
  pending_settlement: false,
  provisional_play_allowed: true,
};

async function stubLadder(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'ladder-geometry-token');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/translations**', (route) =>
    fulfillJson(route, { language: 'cn', translations: {} }),
  );
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/ai-ladder/status') return fulfillJson(route, TALLEST_STATUS);
    if (path === '/api/v1/auth/me') {
      return fulfillJson(route, { id: 1, username: '几何闸用户', rank: '20k', credits: 100 });
    }
    if (path === '/api/v1/geometry/status') {
      return fulfillJson(route, {
        phase: 'ready',
        session_calibrated: true,
        last_valid: true,
        capabilities: { camera_ready: true, led_ready: true, geometry_ready: true },
      });
    }
    if (path === '/api/v1/vision/status') {
      return fulfillJson(route, {
        enabled: false,
        camera_connected: false,
        pose_locked: false,
        sync_state: 'idle',
        bound_session_id: null,
        recognition_ready: false,
        led_connected: false,
      });
    }
    return fulfillJson(route, {});
  });
}

/** Nearest ancestor that actually clips, plus its clip box — measured, not assumed. */
const clipBox = (el: Element) => {
  let node = el.parentElement;
  while (node) {
    const style = getComputedStyle(node);
    if (style.overflowY !== 'visible' || style.overflowX !== 'visible') {
      const box = node.getBoundingClientRect();
      return { tag: node.tagName, overflowY: style.overflowY, top: box.top, bottom: box.bottom };
    }
    node = node.parentElement;
  }
  return null;
};

/** Nearest ancestor that is both scrollable and actually overflowing. */
const scrollerOf = (el: Element) => {
  let node = el.parentElement;
  while (node) {
    const overflowY = getComputedStyle(node).overflowY;
    if ((overflowY === 'auto' || overflowY === 'scroll') && node.scrollHeight > node.clientHeight) {
      return node.tagName;
    }
    node = node.parentElement;
  }
  return null;
};

test.describe('kiosk 升降级设置页 @1024×600 — 面板不可滚，所以内容必须装得下', () => {
  test.use({ viewport: SHORT_VIEWPORT });

  test('最高态下 ranked 面板不溢出，开始按钮完整落在裁切框内', async ({ page }) => {
    await stubLadder(page);
    await page.goto('/kiosk/play/ai/setup/ranked');

    const panel = page.getByTestId('ranked-settings-panel');
    await expect(panel).toBeVisible();
    // The status has to have landed, or we would be measuring the loading state.
    await expect(page.getByText('超越人类').first()).toBeVisible();

    const panelMetrics = await panel.evaluate((el) => ({
      overflowY: getComputedStyle(el).overflowY,
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight,
    }));

    // Expectation written before reading: this panel is deliberately unscrollable...
    expect(panelMetrics.overflowY).toBe('hidden');
    // ...therefore anything taller than the box is content the user can never reach.
    expect(
      panelMetrics.scrollHeight,
      `ranked panel overflows its own no-scroll box: ${panelMetrics.scrollHeight} > ${panelMetrics.clientHeight}`,
    ).toBeLessThanOrEqual(panelMetrics.clientHeight);

    const action = page.getByTestId('ranked-start-action');
    const actionBox = await action.boundingBox();
    const clip = await action.evaluate(clipBox);
    expect(actionBox).toBeTruthy();
    expect(clip, 'the ranked panel must have a clipping ancestor for this gate to mean anything').toBeTruthy();
    // Recorded, never asserted on: the relations above are the judgement, the pixels are evidence.
    test.info().annotations.push({
      type: 'measured',
      description: `panel ${panelMetrics.scrollHeight}/${panelMetrics.clientHeight}; `
        + `start-action ${Math.round(actionBox!.y)}..${Math.round(actionBox!.y + actionBox!.height)} `
        + `inside ${clip!.tag} ${Math.round(clip!.top)}..${Math.round(clip!.bottom)}`,
    });
    // Relation, not a pixel: the start action sits entirely inside whatever clips it.
    expect(actionBox!.y).toBeGreaterThanOrEqual(clip!.top - 1);
    expect(actionBox!.y + actionBox!.height).toBeLessThanOrEqual(clip!.bottom + 1);
  });
});

test.describe('galaxy 升降级设置页 @1024×600 — 内容溢出，CTA 必须真能滚到', () => {
  test.use({ viewport: SHORT_VIEWPORT });

  test('MAIN 是滚动容器，真滚轮拨得动，滚到底后开局按钮不被裁', async ({ page }) => {
    await stubLadder(page);
    await page.goto('/galaxy/play/ai?mode=rated');

    // Matched by test id, not by label: the CTA's text is language-dependent and this gate
    // is about geometry, not copy.
    const cta = page.getByTestId('ranked-start-action');
    await expect(cta).toBeAttached();
    await expect(page.getByText('超越人类').first()).toBeVisible();

    // Which element is the scroller? Answer from the DOM, do not assume it is <main>.
    expect(await cta.evaluate(scrollerOf)).toBe('MAIN');

    const main = page.locator('main');
    const before = await main.evaluate((el) => ({ sh: el.scrollHeight, ch: el.clientHeight, top: el.scrollTop }));
    // The fixture has to actually overflow, or the rest of this test proves nothing.
    expect(before.sh, `content ${before.sh} must exceed the box ${before.ch} for this gate to mean anything`)
      .toBeGreaterThan(before.ch);
    expect(before.top).toBe(0);

    // A real wheel event, not element.scrollTop = n. Untrusted synthetic WheelEvents do not
    // scroll in Chromium, so "it scrolls programmatically" is not evidence a finger works.
    await main.hover();
    await page.mouse.wheel(0, 400);
    await expect
      .poll(async () => main.evaluate((el) => el.scrollTop), { timeout: 2000 })
      .toBeGreaterThan(0);
    const afterWheel = await main.evaluate((el) => el.scrollTop);

    // Scroll to the end, then check the CTA against its clipper from a non-zero scrollTop.
    await main.evaluate((el) => { el.scrollTop = el.scrollHeight; });
    await expect.poll(async () => main.evaluate((el) => el.scrollTop), { timeout: 2000 }).toBeGreaterThan(0);

    const ctaBox = await cta.boundingBox();
    const clip = await cta.evaluate(clipBox);
    expect(ctaBox).toBeTruthy();
    expect(clip).toBeTruthy();
    expect(clip!.overflowY).toBe('auto');
    // Any negative gap at the top means the button was rolled out past the fold.
    expect(ctaBox!.y - clip!.top).toBeGreaterThanOrEqual(0);
    expect(clip!.bottom - (ctaBox!.y + ctaBox!.height)).toBeGreaterThanOrEqual(0);
    test.info().annotations.push({
      type: 'measured',
      description: `main ${before.sh}/${before.ch}; wheel(400) -> scrollTop ${afterWheel}; `
        + `cta ${Math.round(ctaBox!.y)}..${Math.round(ctaBox!.y + ctaBox!.height)} `
        + `inside ${clip!.tag} ${Math.round(clip!.top)}..${Math.round(clip!.bottom)}`,
    });
  });
});
