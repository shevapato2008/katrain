import { expect, test } from '@playwright/test';
import { resolve } from 'node:path';

const screenshotPath = resolve(
  process.cwd(),
  '../../../superpowers/tracks/galaxy-ai-ladder-journey/visual/game/1440x900/implementation.png',
);

const stones = [
  ['B', [3, 3]], ['W', [15, 15]], ['B', [15, 3]], ['W', [3, 15]],
  ['B', [9, 9]], ['W', [10, 9]], ['B', [9, 10]], ['W', [10, 10]],
  ['B', [4, 4]], ['W', [14, 14]], ['B', [14, 4]], ['W', [4, 14]],
] as const;

test('Galaxy 升降级对弈棋盘页 1440x900', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: '棋手', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/translations?lang=cn', (route) => route.fulfill({ json: {
    lang: 'cn',
    translations: {
      Home: '首页', 'btn:Play': '对局', Research: '研究', Tsumego: '死活题',
      'analysis:report': '复盘', Live: '直播', 'kifu:library': '棋谱库', Tutorials: '教程',
      Settings: '设置', Logout: '退出登录', Territory: '领地', Advice: '支招', Graph: '走势',
      Undo: '悔棋', PASS: '停一手', RESIGN: '认输', COUNT: '数子', Coordinates: '坐标',
      'Move Numbers': '手数', Captures: '提子', Komi: '贴目', Rules: '规则', japanese: '日本',
      items_disabled_rated: '升降级对弈进行中，分析与悔棋不可用',
      rated_mode_active: '升降级模式进行中', rated_mode_desc: '本局结果计入段位进度',
    },
  } }));
  await page.route('**/api/v1/live/translations?lang=cn', (route) => route.fulfill({
    json: { players: {}, tournaments: {}, rounds: {}, rules: {} },
  }));
  await page.route('**/api/v1/users/following', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/v1/ai-ladder/status', (route) => route.fulfill({
    json: {
      view_state: 'in_progress',
      placement_state: { phase: 'placed', rung: { rung: 30, rank_name: '5段' } },
      current_opponent: { rung: 30, rank_name: '5段' }, recent_ranked_results: [], net_score: 1,
      pending_settlement: false,
    },
  }));
  await page.route('**/api/state?session_id=ranked-demo', (route) => route.fulfill({ json: { state: {
    game_id: 'ranked-demo', board_size: [19, 19], komi: 7.5, handicap: 0, ruleset: 'japanese',
    current_node_id: 12, current_node_index: 12,
    history: stones.map((_, index) => ({ node_id: index + 1, score: null, winrate: null })),
    player_to_move: 'B', stones: stones.map(([color, point], index) => [color, point, index + 1, null]),
    last_move: [4, 14], prisoner_count: { B: 0, W: 0 }, analysis: null, commentary: '',
    is_root: false, is_pass: false, end_result: null, children: [], ghost_stones: [], note: '', language: 'cn',
    game_type: 'ai_ladder_ranked', count_min_moves: 100,
    players_info: {
      B: { player_type: 'player:human', player_subtype: '', name: '棋手', rank_display: '5段', calculated_rank: null, periods_used: 0, main_time_used: 82 },
      W: { player_type: 'player:ai', player_subtype: 'ai:ladder', name: '智星棋手', rank_display: '5段', calculated_rank: null, periods_used: 0, main_time_used: 64 },
    },
    timer: { paused: true, main_time_used: 82, current_node_time_used: 4, next_player_periods_used: 0, settings: { main_time: 10, byo_length: 30, byo_periods: 3, minimal_use: 0, sound: false } },
    ui_state: { show_children: false, show_dots: false, show_hints: false, show_policy: false, show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false },
  } } }));
  for (const name of ['logo-white.png', 'board.png', 'B_stone.png', 'W_stone.png', 'inner.png', 'topmove.png']) {
    await page.route(`**/assets/img/${name}`, (route) => route.fulfill({
      path: resolve(process.cwd(), `../../../katrain/img/${name}`),
    }));
  }

  await page.goto('/galaxy/play/game/ranked-demo?mode=rated');
  await expect(page.getByTestId('board-page-shell')).toBeVisible();
  await expect(page.getByRole('heading', { name: '升降级对弈' })).toBeVisible();
  await expect(page.getByRole('button', { name: '返回升降级' })).toBeVisible();
  await expect(page.getByTestId('board-stage').locator('canvas')).toBeVisible();
  expect(await page.getByTestId('board-stage').locator('h1,h2,h3,h4,h5,h6,button').count()).toBe(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: screenshotPath });
});
