import { test, expect } from '@playwright/test';
import { stubBackendStatics } from './helpers/fourup';

test.use({ viewport: { width: 1024, height: 600 } });
const sgf = '(;SZ[19]PB[黑棋手]PW[白棋手];B[pd];W[dd];B[qp];W[dq])';
const top_moves = Array.from({ length: 10 }, (_, i) => ({ move: ['Q10', 'D10', 'C3', 'R6', 'K10', 'S3', 'A4', 'B4', 'E10', 'F10'][i], visits: 100, winrate: .64, score_lead: 4.1, prior: .1, psv: 1, pv: ['Q10', 'D10'] }));
const rows = Array.from({ length: 5 }, (_, n) => ({
  id: n, task_id: 42, move_number: n, status: 'success', winrate: .62, score_lead: 3.2, visits: 1000,
  top_moves, ownership: null, actual_move: n ? 'D4' : null, actual_player: n ? (n % 2 ? 'B' : 'W') : null,
  delta_score: 0, delta_winrate: 0, grade: 'best', points_lost: 0, is_top_move: true,
}));
const game = {
  id: 'g1', user_id: 1, title: '真实报告', player_black: '黑棋手', player_white: '白棋手', black_rank: '9p', white_rank: '8p',
  board_size: 19, rules: 'chinese', komi: 7.5, move_count: 4, source: 'import', category: 'all', event: '赛事甲',
  round_name: '决赛', game_date: '2026-10-01', result: 'W+R', game_type: null, created_at: null, updated_at: null, sgf_content: sgf,
};

for (const professional of [false, true]) {
  test(`${professional ? '职业' : '个人'}报告：460×516、五行44px、弹层和坐标几何`, async ({ page }) => {
    await page.addInitScript(() => { localStorage.setItem('token', 'test'); localStorage.setItem('katrain_language', 'cn'); });
    await stubBackendStatics(page);
    let failRefresh = false;
    await page.route('**/api/v1/**', async (route) => {
      const path = new URL(route.request().url()).pathname;
      let json: unknown = {};
      if (path.endsWith('/auth/me')) json = { id: 1, username: '黑棋手', rank: '9p', credits: 100 };
      else if (path.endsWith('/geometry/status')) json = { phase: 'disabled', capabilities: {} };
      else if (path.endsWith('/vision/status')) json = { enabled: false };
      else if (path === '/api/v1/reports/42/moves') json = rows;
      else if (path === '/api/v1/reports/42') {
        if (failRefresh) { await route.fulfill({ status: 503, json: { detail: 'offline' } }); return; }
        json = { id: 42, user_game_id: 'g1', status: 'completed', report_type: 'deep', total_moves: 4, analyzed_moves: 4, requested_visits: 1000 };
      } else if (path === '/api/v1/user-games/g1') json = game;
      else if (path === '/api/v1/kifu/albums/7/analysis') json = { album_id: 7, canonical_album_id: 7, status: 'completed', total_moves: 4, analyzed_moves: 4, requested_visits: 2000, moves: rows };
      else if (path === '/api/v1/kifu/albums/7') json = { ...game, id: 7, date_played: game.game_date, place: '上海', handicap: 0 };
      await route.fulfill({ json });
    });
    await page.goto(professional ? '/kiosk/kifu/7' : '/kiosk/report/42');
    const rail = page.locator('.report-analysis-rail');
    await expect(rail).toBeVisible();
    await expect(page.getByTestId('ai-recommend-row')).toHaveCount(5);
    const rect = await rail.boundingBox();
    expect(rect?.width).toBe(460); expect(rect?.height).toBe(516);
    expect(await rail.evaluate((el) => el.scrollHeight)).toBeLessThanOrEqual(516);
    for (const row of await page.getByTestId('ai-recommend-row').all()) expect((await row.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    const board = page.locator('.kiosk-board');
    const before = await board.boundingBox();
    await page.getByRole('button', { name: '坐标', exact: true }).click();
    await expect(board).toHaveAttribute('data-coordinates', 'false');
    expect(await board.boundingBox()).toEqual(before);
    expect(await page.locator('.kiosk-board__ruler span').first().evaluate((el) => getComputedStyle(el).visibility)).toBe('hidden');
    await page.getByRole('button', { name: '坐标', exact: true }).click();
    await page.screenshot({ path: `/private/tmp/kiosk-${professional ? 'professional' : 'personal'}-report.png` });
    await page.getByTestId(professional ? 'kifu-report-grade' : 'report-detail-grade').click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    const size = await dialog.boundingBox();
    expect(size?.width).toBe(460); expect(size?.height).toBe(480);
    for (const tab of ['走势', '妙手', '失误', '发挥水准', 'AI吻合度']) await expect(dialog.getByRole('button', { name: tab, exact: true })).toBeVisible();
    await page.screenshot({ path: `/private/tmp/kiosk-${professional ? 'professional' : 'personal'}-analysis.png` });
    await dialog.getByRole('button', { name: '关闭', exact: true }).click();
    await page.getByRole('button', { name: '对局详情', exact: true }).click();
    await expect(dialog).toContainText('赛事甲');
    await expect(dialog).toContainText('2026-10-01');
    await page.keyboard.press('Escape');
    await expect(dialog).not.toBeVisible();
    if (!professional) {
      failRefresh = true;
      await page.getByRole('button', { name: '重算', exact: true }).click();
      await expect(page.getByTestId('report-detail-alert')).toBeVisible();
      const retry = page.getByRole('button', { name: '重试加载', exact: true });
      await retry.scrollIntoViewIfNeeded(); await expect(retry).toBeInViewport();
      const nav = page.getByRole('button', { name: '上一手', exact: true });
      await nav.scrollIntoViewIfNeeded(); await expect(nav).toBeInViewport();
      expect((await nav.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    }
  });
}
