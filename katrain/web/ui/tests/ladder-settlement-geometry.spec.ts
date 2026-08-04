import { test, expect } from '@playwright/test';

/**
 * Real-browser geometry gate for the 升降级 settlement dialog.
 *
 * The dialog is the last thing a rated game shows, and its only exit is the
 * dismiss button. On a viewport shorter than the card that button starts below
 * the fold — reaching it depends entirely on the paper being the scroll
 * container, which is a browser-computed fact jsdom cannot testify to.
 *
 * The network responses below are fabricated INPUTS. Every assertion is on a
 * number Chromium computed: scrollHeight/clientHeight, a scrollTop read back
 * after a REAL wheel (not a synthetic WheelEvent, which Chrome ignores), and the
 * button's box against the paper's clip rect once scrolled.
 */

import { readFileSync } from 'node:fs';

// A real WebKaTrain.get_state() dump (engine off, ai:ladder seated, resigned),
// so the page renders against the shape the server actually sends rather than a
// hand-written subset that drifts. Only end_result/game_type were stamped in.
const SESSION = 'geomtest';
const ladderGameState = JSON.parse(
    readFileSync(new URL('./fixtures/ladder_game_state.json', import.meta.url), 'utf8'),
);
const LADDER_STATE = { session_id: SESSION, state: ladderGameState };

// The tallest of the six settlement states, so the card genuinely overflows a
// short viewport. A state that fits proves nothing.
const SETTLEMENT = {
    settled: true,
    won: false,
    is_placement: true,
    net_wins_before: 0,
    net_wins_after: 0,
    threshold: 3,
    rung_before: null,
    rung_after: null,
    moved: 0,
    placement: { games_done: 3, games_total: 5 },
};

test('the settlement dialog stays scrollable and its dismiss button reachable on a short viewport', async ({ page }) => {
    await page.route('**/api/state?**', (route) =>
        route.fulfill({ json: LADDER_STATE }),
    );
    await page.route('**/api/ladder/session-result/**', (route) =>
        route.fulfill({ json: SETTLEMENT }),
    );
    await page.route('**/api/v1/auth/me', (route) =>
        route.fulfill({ json: { id: 1, username: 'tester', rank: '20k', is_admin: false } }),
    );
    page.on('console', (m) => console.log('PAGE:', m.text()));
    page.on('pageerror', (e) => console.log('PAGEERR:', e.message));

    await page.addInitScript(() => localStorage.setItem('token', 'test-token'));
    await page.setViewportSize({ width: 1440, height: 200 });
    await page.goto(`/galaxy/play/game/${SESSION}?mode=rated`);

    const paper = page.locator('.MuiDialog-paper');
    await expect(paper).toBeVisible({ timeout: 15000 });

    // 1. The card really is taller than the space it has — otherwise this test
    //    would pass on a card that never needed to scroll.
    const box = await paper.evaluate((el) => ({
        scrollHeight: el.scrollHeight,
        clientHeight: el.clientHeight,
    }));
    expect(box.scrollHeight).toBeGreaterThan(box.clientHeight);

    // 2. The paper itself is the scroller (not an ancestor that does not exist).
    await paper.evaluate((el) => { el.scrollTop = 0; });
    // A real wheel over the card, not a synthetic WheelEvent and not a scrollTop
    // write: a container can be programmatically scrollable and still be dead
    // under the user's finger.
    const pb = (await paper.boundingBox())!;
    await page.mouse.move(pb.x + pb.width / 2, pb.y + pb.height / 2);
    await page.mouse.wheel(0, 600);
    await expect
        .poll(async () => paper.evaluate((el) => el.scrollTop))
        .toBe(box.scrollHeight - box.clientHeight);

    // 3. Scrolled to the bottom, the dismiss button is inside the clip rect.
    //    Any negative value here is the original defect coming back.
    const inside = await paper.evaluate((el) => {
        const btn = el.querySelectorAll('button');
        const b = btn[btn.length - 1].getBoundingClientRect();
        const p = el.getBoundingClientRect();
        return { belowTop: Math.round(b.top - p.top), aboveBottom: Math.round(p.bottom - b.bottom) };
    });
    expect(inside.belowTop).toBeGreaterThanOrEqual(0);
    expect(inside.aboveBottom).toBeGreaterThanOrEqual(0);
});
