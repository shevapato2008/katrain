import { expect, test } from '@playwright/test';
import { freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });

/**
 * 屏 19 新文案(P14 / P15)在真浏览器里上屏。三行都排在第 4 行之后,**默认落在列表可视区之外** ——
 * 断言前先滚到那一行,证明「滚得到、念得对」,而不是 jsdom 里拼出来的一句话。
 */
const at = (iso: string) => new Date(iso).toISOString();
const base = {
  user_id: 1, board_size: 19, rules: 'chinese', komi: 7.5, category: 'game', black_rank: null, white_rank: null,
  event: null, round_name: null, game_date: '2026-08-20', updated_at: null, game_type: 'free',
};
const filler = (id: string, hour: number) => ({
  ...base, id, title: null, player_black: '访客', player_white: 'KataGo', result: 'W+R', move_count: 120,
  source: 'play_ai', created_at: at(`2026-08-20T${String(hour).padStart(2, '0')}:00:00`),
});
const GAMES = [
  filler('f1', 15), filler('f2', 14), filler('f3', 13), filler('f4', 12),
  { ...base, id: 'u1', title: null, player_black: '', player_white: '', result: 'B+R', move_count: 96,
    source: 'play_local', created_at: at('2026-08-19T19:20:00') },
  { ...base, id: 'r1', title: '柯洁 vs 申真谞', player_black: null, player_white: null, result: null, move_count: 80,
    source: 'research', game_type: null, created_at: at('2026-08-18T10:00:00') },
  { ...base, id: 'i1', title: '老谱', player_black: null, player_white: null, result: null, move_count: 187,
    source: 'import', game_type: null, created_at: at('2026-08-17T10:00:00') },
];
const row = (page: import('@playwright/test').Page, i: number) =>
  page.locator('[data-testid="review-row"]').nth(i);

test('屏 19:未记名 / 研究存档 / 谱里没写结果 在滚动区里够得着且念得对', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'labels');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({ json: { id: 1, username: '访客', rank: '5段', credits: 0 } }));
  await page.route('**/api/v1/geometry/status', (route) => route.fulfill({
    json: { phase: 'disabled', session_calibrated: false, last_error: null,
      capabilities: { camera_ready: false, led_ready: false, geometry_ready: false, recognition_ready: false } },
  }));
  await page.route('**/api/v1/user-games/*', (route) => route.fulfill({ json: { ...GAMES[0], sgf_content: '(;FF[4]GM[1]SZ[19])' } }));
  await page.route('**/api/v1/user-games**', (route) => route.fulfill({ json: { items: GAMES, total: GAMES.length, page: 1, page_size: 12 } }));
  await page.route('**/api/v1/reports/summary', (route) => route.fulfill({ json: { pending: 0, running: 0, completed: 0, failed: 0 } }));
  await page.route('**/api/v1/reports/', (route) => route.fulfill({ json: [] }));

  await page.goto('/kiosk/report');
  await expect(page.locator('[data-testid="review-row"]')).toHaveCount(7);

  await row(page, 4).scrollIntoViewIfNeeded();
  await expect(row(page, 4)).toBeInViewport();
  await expect(row(page, 4)).toContainText('本地对局 · 未记名');

  await row(page, 5).scrollIntoViewIfNeeded();
  await expect(row(page, 5)).toContainText('研究存档 · 柯洁 vs 申真谞');
  await expect(row(page, 5)).toHaveAttribute('data-state', 'unanalyzed');

  await row(page, 6).scrollIntoViewIfNeeded();
  await expect(row(page, 6)).toBeInViewport();
  await expect(row(page, 6)).toContainText('谱里没写结果 · 187 手');
  await expect(row(page, 6)).not.toContainText('就退出了');
  await expect(row(page, 6)).toHaveAttribute('data-state', 'unanalyzed');

  await page.screenshot({ path: 'test-results/kiosk-review-row-labels.png' });
});
