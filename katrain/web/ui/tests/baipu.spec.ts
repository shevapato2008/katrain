import { test, expect, type Page } from '@playwright/test';

/**
 * 摆谱(屏 17)那台状态机的 e2e:`guiding → 确认 → (采集 → 待移除 → 已移除) → done`,外加撤回。
 * `/baipu/load` 走 route mock(不需要引擎),SGF 走 localStorage 缓存。
 * **不需要 LED 板或相机** —— 只要 web app + 一个假后端。
 *
 * ⚠️ **2026-08-24 把断言迁到了新把手。** 屏 17 按稿子重画成共享外壳的布局 A 之后,
 * 这几块没了:通栏状态条 `baipu-status-bar`、两张玩家卡 `baipu-player-*`、
 * 下一手那张 `baipu-next-chip`、最近保存那块 `baipu-latest-frame`、
 * 通栏横幅 `baipu-removal-banner`、以及 `baipu-done-back`。
 * **被测的行为一条没变**,变的是它们现在住在哪:
 *   · 「轮到谁、第几手、在哪一格」→ 同一块 `baipu-pcard`(四态互斥,`data-mood` 标身份)
 *   · 「已采集 / 最近保存 / 提子 / 几何」→ 摄像头折叠块那本账 `baipu-cam-fold`
 *   · 「请移除被提的子」→ 不再是横幅,是 pcard 的 `removal` 态(固定 516 里没有横幅的位置)
 *   · 「采集失败」→ 同上,`failed` 态
 *   · 退出 → 页控条返回键 + `.cdlg` 二次确认(那颗独立的「退出」键没了)
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

    // 第 1 手是黑 —— pcard 说的是「放黑子」,而**盘上那个圈必须同时是红的**
    // (规范:屏上高亮色必须和灯同色;黑→红)。
    const pcard = page.getByTestId('baipu-pcard');
    await expect(pcard).toHaveAttribute('data-mood', 'guiding');
    await expect(pcard).toContainText('把黑子放');
    await expect(page.locator('.gob .ghost--b')).toHaveCount(1);

    // 确认第 1 手(这一手不提子)→ 轮到白
    await page.getByRole('button', { name: '确认落子' }).click();
    await expect(pcard).toContainText('把白子放');
    await expect(page.locator('.gob .ghost--w')).toHaveCount(1);

    // 确认第 2 手 → 又轮到黑(这一手会提子)
    await page.getByRole('button', { name: '确认落子' }).click();
    await expect(pcard).toContainText('把黑子放');

    // 确认第 3 手 → 提子:**同一块 pcard 换成 removal 态**,盘上被提的子画红框
    await page.getByRole('button', { name: '确认落子' }).click();
    await expect(pcard).toHaveAttribute('data-mood', 'removal');
    await expect(pcard).toContainText('请拿走被提的 1 子');
    await expect(page.locator('.gob .atari')).toHaveCount(1);
    await page.getByRole('button', { name: '已移除 1 子' }).click();

    // 摆完了:pcard 说完,而「完成」这时才亮
    await expect(pcard).toHaveAttribute('data-mood', 'done');
    await expect(page.getByRole('button', { name: '完成' })).toBeEnabled();
  });

  test('undo steps back one move', async ({ page }) => {
    await setupSession(page);
    await captureDisabled(page);
    await page.goto('/kiosk/baipu/session/test1');

    await page.getByRole('button', { name: '确认落子' }).click();   // 到第 2 手(白)
    await expect(page.getByTestId('baipu-pcard')).toContainText('把白子放');

    await page.getByRole('button', { name: '撤回上一手' }).click();
    await page.getByTestId('baipu-undo-confirm-action').click();
    await expect(page.getByTestId('baipu-pcard')).toContainText('把黑子放');
  });

  // 退出这条路整个换了:独立的「退出」键没了(它和一局按 250 次的「确认落子」同排,
  // 那是这一屏被点名的 Blocker),改成页控条返回 + 二次确认。**确认这一半不许省** ——
  // 它和「移到角上」是配套采纳的。
  test('退出走页控条,并且要再确认一次', async ({ page }) => {
    await setupSession(page);
    await captureDisabled(page);
    await page.goto('/kiosk/baipu/session/test1');
    await expect(page.getByTestId('baipu-pcard')).toBeVisible();

    await page.getByRole('button', { name: /棋谱/ }).click();
    await expect(page.getByTestId('baipu-exit-confirm')).toBeVisible();
    // 取消 = 留在原地,一手都没丢
    await page.getByRole('button', { name: '取消' }).click();
    await expect(page.getByTestId('baipu-exit-confirm')).toHaveCount(0);
    await expect(page.getByTestId('baipu-pcard')).toBeVisible();

    await page.getByRole('button', { name: /棋谱/ }).click();
    await page.getByTestId('baipu-exit-confirm-action').click();
    await expect(page).toHaveURL(/\/kiosk\/baipu$/);
  });

  // 稿子画了四格,实现三格。这一条钉的是**那颗「虚手」不在**:它在重放既有 SGF 的屏上
  // 要么破坏 `frames.length = 1 + 非 pass 落子数`,要么什么都不干。
  test('动作区三格,没有「虚手」;「完成」摆完之前一直灰着', async ({ page }) => {
    await setupSession(page);
    await captureDisabled(page);
    await page.goto('/kiosk/baipu/session/test1');
    await expect(page.getByTestId('baipu-pcard')).toBeVisible();

    await expect(page.getByTestId('baipu-actions').locator('button')).toHaveCount(3);
    await expect(page.getByRole('button', { name: '虚手' })).toHaveCount(0);
    const finish = page.getByRole('button', { name: '完成' });
    await expect(finish).toBeDisabled();
    await expect(finish).toHaveAttribute('title', /还剩 3 手没摆/);
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

    await expect(page.getByTestId('baipu-pagebar')).toContainText('第 1 / 3 手');
    await expect(page.getByTestId('baipu-cam-fold')).toContainText('frame_000.jpg');
    await page.getByRole('button', { name: '确认落子' }).click();
    await expect(page.getByTestId('baipu-pagebar')).toContainText('第 2 / 3 手');
    await expect(page.getByTestId('baipu-cam-fold')).toContainText('frame_049.jpg');
    await expect(page.getByTestId('baipu-pcard')).toContainText('把白子放');
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

    await page.getByRole('button', { name: '确认落子' }).click();

    await expect(page.getByTestId('baipu-pcard')).toHaveAttribute('data-mood', 'failed');
    await expect(page.getByTestId('baipu-pagebar')).toContainText('第 1 / 3 手');
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

    await expect(page.getByTestId('baipu-cam-fold')).toContainText('frame_000.jpg');
    await page.getByRole('button', { name: '确认落子' }).click();

    // 失败不推进:pcard 转 failed、手数不动、上一张成功的文件名还留着 ——
    // 重按「确认落子」就是重试(这一条正是数据契约要的 re-capture 而不是 advance)。
    await expect(page.getByTestId('baipu-pcard')).toHaveAttribute('data-mood', 'failed');
    await expect(page.getByTestId('baipu-pagebar')).toContainText('第 1 / 3 手');
    await expect(page.getByTestId('baipu-cam-fold')).toContainText('frame_000.jpg');
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

    await expect(page.getByTestId('baipu-resume')).toContainText('接着上次摆？');
    expect(bodies).toHaveLength(0);

    await page.getByTestId('baipu-resume-restart').click();
    await expect.poll(() => bodies.length).toBe(1);
    expect(bodies[0]).toEqual(expect.objectContaining({
      move_index: -1,
      overwrite_existing: true,
    }));
    await expect(page.getByTestId('baipu-cam-fold')).toContainText('frame_000.jpg');
  });
});
