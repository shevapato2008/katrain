import { expect, test, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * 对弈·AI/升降级赛道(superpowers/tracks/kiosk-go-play-ai)的真浏览器实测,1024×600,打构建产物。
 * 只放 jsdom 作不了证的东西:时钟真的在走、右栏承重链(Task 9 追加)。
 * 不改 kiosk-screen-05-game.spec.ts —— 那个文件跨平台赛道也在改。
 */
test.use({ viewport: { width: 1024, height: 600 } });

const SHOTS = resolve(process.cwd(), '../../../superpowers/tracks/kiosk-go-play-ai/visual');
mkdirSync(SHOTS, { recursive: true });

const seat = (name: string, type: string, over: Record<string, number> = {}) => ({
  player_type: type, player_subtype: '', name, calculated_rank: -4, periods_used: 0, main_time_used: 0, ...over,
});

const baseState = (over: Record<string, unknown> = {}) => ({
  game_id: 'play-ai', board_size: [19, 19], komi: 7.5, handicap: 0, ruleset: 'chinese',
  game_type: 'free', count_min_moves: 100, current_node_id: 0, current_node_index: 0,
  history: [{ node_id: 0, score: null, winrate: null, move: null, player: null }],
  player_to_move: 'B', stones: [], last_move: null, prisoner_count: { B: 0, W: 0 },
  analysis: null, commentary: '', is_root: true, is_pass: false, end_result: null, children: [], ghost_stones: [],
  players_info: { B: seat('访客（你）', 'player:human'), W: seat('KataGo', 'player:ai') },
  note: '',
  ui_state: {
    show_children: false, show_dots: false, show_hints: false, show_policy: false,
    show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false,
  },
  ...over,
});

const open = async (page: Page, state: Record<string, unknown>) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'play-ai');
    localStorage.setItem('katrain_language', 'cn');
  });
  // 造的 token 是假的,不接住 WS 屏上会盖一条「实时连接被拒绝」(那一态归 kiosk-screen-05-game.spec.ts 量)
  await page.routeWebSocket('**/ws/**', () => { /* 连上就行,不推任何东西 */ });
  await page.route('**/api/state**', (route) => route.fulfill({ json: { state } }));
  await page.route('**/api/analysis/current', (route) => route.fulfill({ json: { state } }));
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') return route.fulfill({ json: { id: 1, username: '访客', rank: '5段', credits: 0 } });
    if (path === '/api/v1/vision/status') {
      return route.fulfill({ json: { enabled: false, camera_connected: false, pose_locked: false,
        sync_state: 'unbound', recognition_ready: false, led_connected: null, bound_session_id: null } });
    }
    if (path === '/api/v1/geometry/status') return route.fulfill({ status: 404, json: { detail: 'geometry disabled' } });
    return route.fulfill({ json: {} });
  });
  await page.goto('/kiosk/play/ai/game/play-ai');
  await page.waitForSelector('[data-testid="game-board"] canvas');
};

test('A18 计时局:轮到的一方时钟真的在走,另一方停着,时钟格没被玩家卡裁掉', async ({ page }) => {
  await open(page, baseState({
    timer: {
      paused: false, main_time_used: 12, current_node_time_used: 0, next_player_periods_used: 0, configured: true,
      settings: { main_time: 5, byo_length: 30, byo_periods: 3, minimal_use: 0, sound: false },
    },
    players_info: {
      B: seat('访客（你）', 'player:human', { main_time_used: 12 }),
      W: seat('KataGo', 'player:ai', { main_time_used: 30 }),
    },
  }));
  const clock = (c: 'B' | 'W') => page.locator(`[data-testid="player-card-${c}"] .clock b`);
  await expect(page.locator('[data-testid="player-card-B"] .clock span')).toHaveText('剩余');
  const b0 = await clock('B').textContent();
  const w0 = await clock('W').textContent();
  await expect.poll(() => clock('B').textContent(), { timeout: 3000, message: '轮到的一方时钟没在走' }).not.toBe(b0);
  expect(await clock('W').textContent(), '没轮到的一方时钟在走').toBe(w0);

  const g = await page.evaluate(() => {
    const card = document.querySelector('[data-testid="player-card-B"]')!.getBoundingClientRect();
    const c = document.querySelector('[data-testid="player-card-B"] .clock')!.getBoundingClientRect();
    return { cardRight: Math.round(card.right), clockRight: Math.round(c.right) };
  });
  expect(g.clockRight, '时钟格溢出了玩家卡').toBeLessThanOrEqual(g.cardRight);
  await page.screenshot({ path: `${SHOTS}/a18-timed-game-1024x600.png` });
});
