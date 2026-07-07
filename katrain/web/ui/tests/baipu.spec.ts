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
    await expect(page.getByTestId('baipu-next-chip')).toContainText(/黑|Black/);
    await expect(page.getByTestId('baipu-player-B')).toHaveAttribute('data-active', 'true');

    // Confirm move 0 (no capture) → advances to white.
    await page.getByTestId('baipu-confirm').click();
    await expect(page.getByTestId('baipu-next-chip')).toContainText(/白|White/);
    await expect(page.getByTestId('baipu-player-W')).toHaveAttribute('data-active', 'true');

    // Confirm move 1 → black again (the capturing move).
    await page.getByTestId('baipu-confirm').click();
    await expect(page.getByTestId('baipu-next-chip')).toContainText(/黑|Black/);

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
    await expect(page.getByTestId('baipu-next-chip')).toContainText(/白|White/);

    await page.getByTestId('baipu-undo').click();
    await page.getByRole('button', { name: '已撤回' }).click();
    await expect(page.getByTestId('baipu-next-chip')).toContainText(/黑|Black/);
  });

  test('operator confirmation captures once and advances without override UI', async ({ page }) => {
    await setupSession(page);
    const bodies: Record<string, unknown>[] = [];
    await page.route('**/api/v1/baipu/capture', async (route) => {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      bodies.push(body);
      const moveIndex = Number(body.move_index);
      const file = moveIndex === -1 ? 'frame_000.jpg' : 'frame_049.jpg';
      return route.fulfill({
        json: {
          ok: true,
          path: `/captures/test1/${file}`,
          qa_status: 'operator_confirmed',
          frame_kind: moveIndex === -1 ? 'initial_led' : 'after_move',
          next_guided_move_index: moveIndex + 1,
        },
      });
    });
    await page.goto('/kiosk/baipu/session/test1');

    await expect(page.getByTestId('baipu-current-move')).toContainText('第 1 手');
    await expect(page.getByTestId('baipu-latest-frame')).toContainText('frame_000.jpg');
    await page.getByTestId('baipu-confirm').click();
    await expect(page.getByTestId('baipu-current-move')).toContainText('第 2 手');
    await expect(page.getByTestId('baipu-latest-frame')).toContainText('frame_049.jpg');
    await expect(page.getByTestId('baipu-next-chip')).toContainText(/白|White/);
    await expect(page.getByTestId('baipu-qa-banner')).toHaveCount(0);
    await expect(page.getByTestId('baipu-qa-override')).toHaveCount(0);
    expect(bodies.filter((body) => body.move_index === 0)).toEqual([
      expect.not.objectContaining({ override: expect.anything() }),
    ]);
  });

  test('legacy mismatch response is an error and never exposes override controls', async ({ page }) => {
    await setupSession(page);
    await page.route('**/api/v1/baipu/capture', async (route) => {
      const body = route.request().postDataJSON();
      if (body.move_index === 0) {
        return route.fulfill({
          status: 409,
          json: { detail: { qa: 'mismatch', move_index: 0, diffs: [{ row: 3, col: 15, expected: 'B', actual: 'empty', reason: 'missing' }] } },
        });
      }
      return route.fulfill({ json: { ok: true, qa_status: 'operator_confirmed' } });
    });
    await page.goto('/kiosk/baipu/session/test1');

    await page.getByTestId('baipu-confirm').click();

    await expect(page.getByTestId('baipu-capture-error')).toBeVisible();
    await expect(page.getByTestId('baipu-progress')).toContainText('1/3');
    await expect(page.getByTestId('baipu-qa-banner')).toHaveCount(0);
    await expect(page.getByTestId('baipu-qa-override')).toHaveCount(0);
  });

  test('capture failure keeps the current move and latest successful filename', async ({ page }) => {
    await setupSession(page);
    await page.route('**/api/v1/baipu/capture', async (route) => {
      const body = route.request().postDataJSON();
      if (body.move_index === -1) {
        return route.fulfill({
          json: { ok: true, path: '/captures/test1/frame_000.jpg', qa_status: 'operator_confirmed' },
        });
      }
      return route.fulfill({ status: 500, json: { detail: 'camera unavailable' } });
    });
    await page.goto('/kiosk/baipu/session/test1');

    await expect(page.getByTestId('baipu-latest-frame')).toContainText('frame_000.jpg');
    await page.getByTestId('baipu-confirm').click();

    await expect(page.getByTestId('baipu-capture-error')).toBeVisible();
    await expect(page.getByTestId('baipu-current-move')).toContainText('第 1 手');
    await expect(page.getByTestId('baipu-latest-frame')).toContainText('frame_000.jpg');
  });

  test('restart uses same directory overwrite mode and waits for operator choice before initial capture', async ({ page }) => {
    await setupSession(page);
    await page.addInitScript(() => {
      localStorage.setItem('baipu:progress:test1', JSON.stringify({ k: 2, frames: 3, updatedAt: 2 }));
    });
    const bodies: Record<string, unknown>[] = [];
    await page.route('**/api/v1/baipu/capture', async (route) => {
      bodies.push(route.request().postDataJSON() as Record<string, unknown>);
      return route.fulfill({
        json: {
          ok: true,
          path: '/captures/test1/frame_000.jpg',
          qa_status: 'operator_confirmed',
          frame_kind: 'initial_led',
          next_guided_move_index: 0,
        },
      });
    });

    await page.goto('/kiosk/baipu/session/test1');

    await expect(page.getByRole('dialog')).toContainText('继续上次会话？');
    expect(bodies).toHaveLength(0);

    await page.getByRole('button', { name: '重新开始' }).click();
    await expect.poll(() => bodies.length).toBe(1);
    expect(bodies[0]).toEqual(expect.objectContaining({
      move_index: -1,
      overwrite_existing: true,
    }));
    await expect(page.getByTestId('baipu-latest-frame')).toContainText('frame_000.jpg');
  });
});
