import { expect, test } from '@playwright/test';
import { resolve } from 'node:path';
import { freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });

test('05a 弃局按钮与确认弹窗预览', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'preview-token');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.routeWebSocket('**/ws/**', () => {});
  await stubBackendStatics(page);
  await page.route('**/api/state**', route => route.fulfill({ json: { state: {
    game_id: 'local-preview', board_size: [19, 19], komi: 7.5, handicap: 0, ruleset: 'chinese',
    game_type: 'pvp_local', count_min_moves: 100, current_node_id: 0, current_node_index: 0,
    history: [], player_to_move: 'B', stones: [], last_move: null,
    prisoner_count: { B: 0, W: 0 }, analysis: null, commentary: '', is_root: true,
    is_pass: false, end_result: null, children: [], ghost_stones: [],
    players_info: {
      B: { player_type: 'player:human', player_subtype: '', name: '黑方', calculated_rank: '', periods_used: 0, main_time_used: 0 },
      W: { player_type: 'player:human', player_subtype: '', name: '白方', calculated_rank: '', periods_used: 0, main_time_used: 0 },
    },
    local_confirmation: { enabled: true, status: 'idle' },
    ui_state: { show_children: false, show_dots: false, show_hints: false, show_policy: false,
      show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false },
  } } }));
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') return route.fulfill({ json: { id: 1, username: 'tester', rank: '20k', credits: 0 } });
    if (path === '/api/v1/health') return route.fulfill({ json: { engines: { local: 'reachable' } } });
    if (path === '/api/v1/vision/status') return route.fulfill({ json: { enabled: false, camera_connected: false,
      pose_locked: false, sync_state: 'unbound', recognition_ready: false, led_connected: null, bound_session_id: null } });
    if (path === '/api/v1/geometry/status') return route.fulfill({ status: 404, json: { detail: 'geometry disabled' } });
    return route.fulfill({ json: {} });
  });
  await page.goto('/kiosk/play/pvp/local/game/local-preview');
  await expect(page.getByTestId('local-confirm-game')).toBeVisible();
  await expect(page.getByRole('button', { name: '弃局' })).toHaveCount(2);
  await page.screenshot({ path: resolve(process.cwd(), '../../../docs/previews/reviewed-pre-growth-2026-10-19/05a-abandon-preview.png') });
  await page.getByRole('button', { name: '弃局' }).first().click();
  await expect(page.getByRole('dialog')).toContainText('不会出现在复盘页面');
  await page.waitForTimeout(250); // wait for the dialog's visual transition before photographing it
  await page.screenshot({ path: resolve(process.cwd(), '../../../docs/previews/reviewed-pre-growth-2026-10-19/05a-abandon-dialog-preview.png') });
});
