import { expect, test } from '@playwright/test';
import { resolve } from 'node:path';
import { freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });

test('大厅观战在 1024×600 上保留可读页头和回合对比', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'visual-fixture');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({ json: { id: 1, username: '访客', rank: '20k', credits: 0 } }));
  await page.route('**/api/pvp/spectate/room-a', (route) => route.fulfill({ json: {
    session_id: 'room-a', public_lobby: true, game_ended: false, spectator_count: 3,
    player_b: '黑方棋友', player_w: '白方棋友', player_b_id: 2, player_w_id: 3,
    player_b_rank_label: '业余 2 段', player_w_rank_label: '业余 3 段',
    state: { game_id: 'game-a', board_size: [19, 19],
      stones: [['B', [3, 15], null, 1], ['W', [15, 15], null, 2]],
      last_move: [15, 15], current_node_index: 2, player_to_move: 'B',
      end_result: null, terminal_result: null, awaiting_count: false },
  } }));
  await page.goto('/kiosk/play/pvp/watch/room-a');
  await expect(page.getByTestId('pvp-spectator-page')).toBeVisible();
  await expect(page.getByText('黑方棋友')).toBeVisible();
  await expect(page.getByText('白方棋友')).toBeVisible();
  const sizes = await page.evaluate(() => ({
    back: parseFloat(getComputedStyle(document.querySelector('.pvp-spectator .kiosk-pagebar__back')!).fontSize),
    title: parseFloat(getComputedStyle(document.querySelector('.pvp-spectator .golaxy-spectator__page-title')!).fontSize),
    status: parseFloat(getComputedStyle(document.querySelector('.pvp-spectator .golaxy-spectator__sync')!).fontSize),
  }));
  expect(sizes).toEqual({ back: 22, title: 22, status: 18 });
  await page.screenshot({ path: resolve(process.cwd(), '../../../docs/previews/reviewed-pre-growth-2026-10-19/pvp-spectator.png') });
});
