import { test, expect, type Page } from '@playwright/test';

/**
 * E2E for the 摆谱 (baipu) session flow. Mocks /baipu/load (no engine needed) and
 * seeds the local SGF cache, then drives the dumb-player state machine:
 * guiding → confirm → (capture → await_removal → removed) → done, plus undo.
 *
 * Runs against the Playwright webServer (see playwright.config.ts). It does NOT
 * require the LED board or camera — only the web app + a mocked backend.
 */

const STEPS = {
  board_size: 19,
  meta: { player_black: 'Lee', player_white: 'AlphaGo', handicap: 0, komi: 6.5, ruleset: 'japanese' },
  steps: [
    { kind: 'move', move_index: 0, property: 'B', row: 3, col: 15, color: 'B', removed: [], board_hash: 'h0' },
    { kind: 'move', move_index: 1, property: 'W', row: 15, col: 3, color: 'W', removed: [], board_hash: 'h1' },
    { kind: 'move', move_index: 2, property: 'B', row: 0, col: 0, color: 'B', removed: [{ row: 0, col: 1 }], board_hash: 'h2' },
  ],
};

async function setupSession(page: Page) {
  // Authenticate (isAuthenticated = !!user) and seed the offline SGF cache.
  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token');
    localStorage.setItem(
      'baipu:sgf:test1',
      JSON.stringify({ id: 'test1', name: 'Lee vs AlphaGo', sgf: '(;SZ[19];B[pd])', savedAt: 1 }),
    );
  });
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({ json: { id: 1, username: 'tester', email: 't@example.com' } }),
  );
  await page.route('**/api/v1/baipu/load', (route) => route.fulfill({ json: STEPS }));
  // LED is advisory in the UI; ack everything.
  await page.route('**/api/v1/led/**', (route) =>
    route.fulfill({ json: { ok: true, connected: true, shown_at: null, errors: [] } }),
  );
}

// Capture disabled (dev/screen-only): /baipu/capture 404s → the UI falls back to a
// plain advance. This keeps the screen-only flow deterministic without hardware.
async function captureDisabled(page: Page) {
  await page.route('**/api/v1/baipu/capture', (route) =>
    route.fulfill({ status: 404, json: { detail: 'Capture service not enabled' } }),
  );
}

test.describe('baipu session', () => {
  test('guides through moves, removal, and completion', async ({ page }) => {
    await setupSession(page);
    await captureDisabled(page);
    await page.goto('/kiosk/baipu/session/test1');

    // Status bar + first guidance (black to place = red LED).
    await expect(page.getByTestId('baipu-status-bar')).toBeVisible();
    await expect(page.getByTestId('baipu-next-chip')).toContainText('黑');
    await expect(page.getByTestId('baipu-player-B')).toHaveAttribute('data-active', 'true');

    // Confirm move 0 (no capture) → advances to white.
    await page.getByTestId('baipu-confirm').click();
    await expect(page.getByTestId('baipu-next-chip')).toContainText('白');
    await expect(page.getByTestId('baipu-player-W')).toHaveAttribute('data-active', 'true');

    // Confirm move 1 → black again (the capturing move).
    await page.getByTestId('baipu-confirm').click();
    await expect(page.getByTestId('baipu-next-chip')).toContainText('黑');

    // Confirm move 2 → capture → removal mode (independent banner).
    await page.getByTestId('baipu-confirm').click();
    await expect(page.getByTestId('baipu-removal-banner')).toBeVisible();
    await page.getByTestId('baipu-removed').click();

    // Done.
    await expect(page.getByTestId('baipu-done-back')).toBeVisible();
  });

  test('undo steps back one move', async ({ page }) => {
    await setupSession(page);
    await captureDisabled(page);
    await page.goto('/kiosk/baipu/session/test1');

    await page.getByTestId('baipu-confirm').click(); // now at move 1 (white)
    await expect(page.getByTestId('baipu-next-chip')).toContainText('白');

    await page.getByTestId('baipu-undo').click();
    await page.getByRole('button', { name: '已撤回' }).click();
    await expect(page.getByTestId('baipu-next-chip')).toContainText('黑');
  });

  test('L2 QA mismatch blocks, override continues', async ({ page }) => {
    await setupSession(page);
    // Capture enabled: move 0 reports a QA mismatch unless overridden.
    await page.route('**/api/v1/baipu/capture', async (route) => {
      const body = route.request().postDataJSON();
      if (body.move_index === 0 && !body.override) {
        return route.fulfill({
          status: 409,
          json: { detail: { qa: 'mismatch', move_index: 0, diffs: [{ row: 3, col: 15, expected: 'B', actual: 'empty', reason: 'missing' }] } },
        });
      }
      return route.fulfill({
        json: { ok: true, qa_status: body.override ? 'operator_override' : 'ok', frame_kind: 'after_move', next_guided_move_index: 1 },
      });
    });
    await page.goto('/kiosk/baipu/session/test1');

    await page.getByTestId('baipu-confirm').click(); // move 0 → QA mismatch
    await expect(page.getByTestId('baipu-qa-banner')).toBeVisible();
    await page.getByTestId('baipu-qa-override').click(); // confirm correct → continue
    await expect(page.getByTestId('baipu-next-chip')).toContainText('白');
  });
});
