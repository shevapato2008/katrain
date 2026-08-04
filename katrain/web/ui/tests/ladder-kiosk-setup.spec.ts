import { readFileSync } from 'node:fs';
import { expect, test, type Page, type Route } from '@playwright/test';

/**
 * 升降级对弈 · kiosk setup page — real-browser geometry gate at the 7" target
 * viewport, plus the screenshots the visual comparison is done from.
 *
 * The gate exists because this page's whole shell hangs off a chain jsdom cannot
 * evaluate: KioskLayout's <main> is `flex:1; overflow:auto`, the page root is
 * `height:100%` inside it, and the start button sits on `margin-top:auto` inside
 * a nested `overflow:auto` column. Whether the button is reachable at 1024x600 in
 * the tallest state (uncertified + placed + 5 recent games) is a fact only a real
 * layout engine knows.
 *
 * Relationships asserted (written down before any number was read):
 *   R1  the element that scrolls is `ladder-setup-scroll`, not the shell
 *   R2  the shell itself never scrolls: documentElement.scrollHeight === 600
 *   R3  in the tallest state the start button's border box is fully inside the
 *       scroll container's clip rect after scrolling to the bottom
 *   R4  if the content overflows, a real wheel over the container moves it
 *
 * Measured 2026-08-05 at 1024x600, tallest state: content box 481px. Before the
 * band padding was cut from 16px to 12px the content was 524px -- 43px of
 * overflow that put the start button below the fold on a touch screen. It is now
 * 481px exactly (the button sits on margin-top:auto, so the column fills the box
 * and scrollHeight === clientHeight when it fits). R4 stays in the spec because
 * that margin is one long translation wide.
 */

const VIEWPORT = { width: 1024, height: 600 };

const fulfillJson = (route: Route, body: unknown) =>
  route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

const tier = (rung: number, rank_name: string) => ({ rung, rank_name });

const GAME_SETUP = { size: 19, rules: 'chinese', komi: 7.5 };

/** Placed, playable, mid-climb. */
const PLACED = {
  game_setup: GAME_SETUP,
  rung: 30,
  rank_name: '5段',
  rung_above: tier(31, '6段'),
  rung_below: tier(29, '4段'),
  net_wins: 2,
  threshold: 3,
  placement: null,
  recent: [
    { won: false, opponent_rung: 30, opponent_rank_name: '5段' },
    { won: true, opponent_rung: 30, opponent_rank_name: '5段' },
    { won: false, opponent_rung: 30, opponent_rank_name: '5段' },
    { won: true, opponent_rung: 30, opponent_rank_name: '5段' },
    { won: true, opponent_rung: 30, opponent_rank_name: '5段' },
  ],
  next_opponent: { ...tier(30, '5段'), certification_status: 'certified', availability: 'available', route: 'local' },
  playable: true,
  blocked_reason: null,
};

/** Mid-placement: no rank yet, 5-game binary search under way. */
const PLACING = {
  ...PLACED,
  rung: null,
  rank_name: null,
  rung_above: null,
  rung_below: null,
  net_wins: 0,
  placement: { games_done: 2, games_total: 5, lo: 1, hi: 31 },
  recent: [],
  next_opponent: { ...tier(20, '2段'), certification_status: 'certified', availability: 'available', route: 'local' },
};

/**
 * The tallest state: placed (so the rail, the bar AND recent form all render),
 * negative net wins, and an uncertified opponent so the blocked note is on screen
 * too. This is the layout the geometry gate is measured against.
 */
const BLOCKED = {
  ...PLACED,
  net_wins: -1,
  next_opponent: { ...tier(30, '5段'), certification_status: 'provisional', availability: 'available', route: 'local' },
  playable: false,
  blocked_reason: 'not_certified',
};

async function openSetup(page: Page, me: unknown) {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'ladder-e2e-token');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/translations**', (route) => fulfillJson(route, { language: 'cn', translations: {} }));
  await page.route('**/api/v1/auth/me', (route) =>
    fulfillJson(route, { id: 1, username: '触屏测试用户', rank: '5D', credits: 0 }),
  );
  await page.route('**/api/v1/**', (route) => fulfillJson(route, {}));
  await page.route('**/api/ladder/me', (route) => fulfillJson(route, me));

  await page.setViewportSize(VIEWPORT);
  await page.goto('/kiosk/play/ai/setup/ranked');
  await expect(page.getByTestId('ladder-start-button')).toBeVisible();
}

test.describe('kiosk 升降级对弈 setup at 1024x600', () => {
  test('the start button is reachable in the tallest state, and the shell never scrolls', async ({ page }) => {
    await openSetup(page, BLOCKED);
    await expect(page.getByTestId('ladder-blocked-note')).toBeVisible();

    // R2: the shell absorbs everything; the document itself must not grow.
    const docScroll = await page.evaluate(() => ({
      scrollHeight: document.documentElement.scrollHeight,
      clientHeight: document.documentElement.clientHeight,
    }));
    expect(docScroll.scrollHeight).toBe(VIEWPORT.height);
    expect(docScroll.clientHeight).toBe(VIEWPORT.height);

    // R1 + R3 + R4, measured on the real boxes.
    const geom = await page.evaluate(() => {
      const scroller = document.querySelector('[data-testid="ladder-setup-scroll"]') as HTMLElement;
      const button = document.querySelector('[data-testid="ladder-start-button"]') as HTMLElement;
      const main = scroller.closest('main') as HTMLElement;
      return {
        scrollerScrollHeight: scroller.scrollHeight,
        scrollerClientHeight: scroller.clientHeight,
        mainOverflows: main.scrollHeight > main.clientHeight,
        buttonBottom: button.getBoundingClientRect().bottom,
        buttonTop: button.getBoundingClientRect().top,
        clipBottom: scroller.getBoundingClientRect().bottom,
        clipTop: scroller.getBoundingClientRect().top,
      };
    });

    // R1: whatever overflow exists belongs to the page's own scroller, never to
    // the layout shell — an overflowing <main> would scroll the SubPageBar away.
    expect(geom.mainOverflows).toBe(false);

    if (geom.scrollerScrollHeight > geom.scrollerClientHeight) {
      // R4: a real wheel, not a programmatic scrollTop write. Chromium applies the
      // scroll asynchronously, so poll rather than reading straight after the event
      // -- an immediate read returns 0 on a container that scrolls perfectly well.
      await page.getByTestId('ladder-setup-scroll').hover();
      await page.mouse.wheel(0, 600);
      await expect
        .poll(() =>
          page.evaluate(
            () => (document.querySelector('[data-testid="ladder-setup-scroll"]') as HTMLElement).scrollTop,
          ),
        )
        .toBeGreaterThan(0);
    }

    // R3: after scrolling to the end, the button's whole border box is inside the
    // clip rect. `-0.5` absorbs sub-pixel rounding only.
    await page.evaluate(() => {
      const s = document.querySelector('[data-testid="ladder-setup-scroll"]') as HTMLElement;
      s.scrollTop = s.scrollHeight;
    });
    const final = await page.evaluate(() => {
      const scroller = document.querySelector('[data-testid="ladder-setup-scroll"]') as HTMLElement;
      const button = document.querySelector('[data-testid="ladder-start-button"]') as HTMLElement;
      const b = button.getBoundingClientRect();
      const c = scroller.getBoundingClientRect();
      return { top: b.top - c.top, bottom: c.bottom - b.bottom };
    });
    expect(final.top).toBeGreaterThan(-0.5);
    expect(final.bottom).toBeGreaterThan(-0.5);
  });

  test('the start button is disabled exactly when the ladder says it is not playable', async ({ page }) => {
    await openSetup(page, BLOCKED);
    await expect(page.getByTestId('ladder-start-button')).toBeDisabled();
    // No fallback to a weaker AI: the opponent named on screen is the blocked one.
    await expect(page.getByTestId('ladder-opponent-band')).toContainText('未标定');
  });

  test('screenshots: placed / placing / blocked', async ({ page }, testInfo) => {
    for (const [name, me] of [['placed', PLACED], ['placing', PLACING], ['blocked', BLOCKED]] as const) {
      await openSetup(page, me);
      await page.screenshot({ path: testInfo.outputPath(`kiosk-ladder-${name}.png`) });
      await page.context().clearCookies();
    }
  });

  /**
   * The settlement strip lives INSIDE the endgame card, which is absolutely
   * positioned at top:12 over the immersive board view. Making that card taller
   * is exactly the kind of change that pushes 确认终局 off a 600px screen, and the
   * card has no scroll container of its own to save it.
   *
   * R5  the endgame card's bottom edge stays inside the 600px viewport
   * R6  the settlement strip is actually rendered (otherwise R5 is vacuous)
   */
  test('the endgame card still fits at 1024x600 with the settlement strip', async ({ page }, testInfo) => {
    const base = JSON.parse(
      readFileSync(new URL('../src/kiosk/__tests__/fixtures/engine_game_state.json', import.meta.url), 'utf8'),
    );
    const state = {
      ...base,
      game_type: 'ai_ladder_ranked',
      end_result: 'B+R',
      platform_engine_color: null,
      players_info: {
        B: { ...base.players_info.B, player_type: 'player:human', name: '触屏测试用户' },
        W: { ...base.players_info.W, player_type: 'player:ai', player_subtype: 'ai:ladder', name: 'AI 5段' },
      },
    };

    await page.addInitScript(() => {
      localStorage.setItem('token', 'ladder-e2e-token');
      localStorage.setItem('katrain_language', 'cn');
    });
    await page.route('**/api/translations**', (route) => fulfillJson(route, { language: 'cn', translations: {} }));
    await page.route('**/api/v1/auth/me', (route) =>
      fulfillJson(route, { id: 1, username: '触屏测试用户', rank: '5D', credits: 0 }),
    );
    // phase 'disabled' lets PhysicalBoardGuard through without a calibrated camera.
    await page.route('**/api/v1/geometry/status', (route) =>
      fulfillJson(route, {
        phase: 'disabled',
        session_calibrated: false,
        last_valid: false,
        capabilities: { camera_ready: false, led_ready: false, geometry_ready: false, recognition_ready: false },
      }),
    );
    await page.route('**/api/v1/**', (route) => fulfillJson(route, {}));
    await page.route('**/api/state?**', (route) => fulfillJson(route, { session_id: 'ladder-sess', state }));
    // A promotion: the tallest settlement shape that also carries a note line.
    await page.route('**/api/ladder/session-result/**', (route) =>
      fulfillJson(route, {
        settled: true,
        won: true,
        is_placement: false,
        net_wins_before: 2,
        net_wins_after: 0,
        threshold: 3,
        rung_before: tier(30, '5段'),
        rung_after: tier(31, '6段'),
        moved: 1,
        placement: null,
      }),
    );

    await page.setViewportSize(VIEWPORT);
    await page.goto('/kiosk/play/ai/game/ladder-sess');

    // R6 first: an absent strip would make R5 pass for the wrong reason.
    await expect(page.getByTestId('ladder-settlement-note')).toBeVisible();
    await expect(page.getByTestId('ladder-settlement-note')).toContainText('升段');

    // R5: measured on the real card, not on an assumed height.
    const card = await page.getByTestId('endgame-card').boundingBox();
    expect(card).not.toBeNull();
    expect(card!.y + card!.height).toBeLessThanOrEqual(VIEWPORT.height);
    // ...and the buttons inside it are reachable, which is the point of R5.
    const confirm = await page.getByRole('button', { name: /确认终局/ }).boundingBox();
    expect(confirm).not.toBeNull();
    expect(confirm!.y + confirm!.height).toBeLessThanOrEqual(VIEWPORT.height);

    await page.screenshot({ path: testInfo.outputPath('kiosk-ladder-endgame.png') });
  });
});
