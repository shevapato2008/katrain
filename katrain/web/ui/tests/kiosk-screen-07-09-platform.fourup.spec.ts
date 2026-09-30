import { expect, test, type Page } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });

// These are the React runtime screenshots approved at the 1024×600 visual gate.
// The old sample-go platform selector and lobby shots describe removed screens.
const PREVIEWS = resolve(process.cwd(), '../../../docs/previews');

async function boot(page: Page, path: string) {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
    localStorage.setItem('kiosk_play_on_board', 'true');
  });
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, uuid: 'fourup', username: '访客', rank: '20k', credits: 0 },
  }));
  await page.route('**/api/v1/platforms/status', (route) => route.fulfill({
    json: { platforms: [
      { platform: 'golaxy', connected: true, saved_username: '当前星阵账号', supports_engine_play: true },
      { platform: 'ogs', connected: true, saved_username: 'my_ogs_account', supports_live_play: true },
    ] },
  }));
  await page.route('**/api/v1/vision/status', (route) => route.fulfill({
    json: {
      enabled: true, camera_connected: true, pose_locked: true, sync_state: 'idle',
      bound_session_id: null, recognition_ready: true, led_connected: true,
    },
  }));
  // Only the screenshot test supplies these rows; the production page reads the API.
  await page.route('**/api/v1/platforms/ogs/challenges', (route) => route.fulfill({
    json: { challenges: [
      { platform: 'ogs', challenge_id: 'sample-1', from_user: { platform: 'ogs', user_id: '1', username: 'stone_walker', rank: '4d', rank_numeric: 34, status: 'idle' }, board_size: 19, time_control: { system: 'byoyomi', main_time: 600, period_time: 30, periods: 5 }, rules: 'chinese', ranked: true, handicap: 0, komi: null },
      { platform: 'ogs', challenge_id: 'sample-2', from_user: { platform: 'ogs', user_id: '2', username: 'kosumi', rank: '8k', rank_numeric: 22, status: 'idle' }, board_size: 19, time_control: { system: 'byoyomi', main_time: 1200, period_time: 30, periods: 5 }, rules: 'chinese', ranked: false, handicap: -1, komi: null },
      { platform: 'ogs', challenge_id: 'sample-3', from_user: { platform: 'ogs', user_id: '3', username: 'tenuki_now', rank: '2d', rank_numeric: 32, status: 'idle' }, board_size: 13, time_control: { system: 'absolute', main_time: 180 }, rules: 'chinese', ranked: false, handicap: 0, komi: null },
    ] },
  }));
  await page.route('**/api/v1/platforms/ogs/active-game', (route) => route.fulfill({ json: { session_id: null } }));
  await page.goto(path);
}

test('四图:星阵专页 ←→ 已确认的 1024×600 React 运行时', async ({ page }, testInfo) => {
  await boot(page, '/kiosk/play/cross-platform/golaxy');
  await expect(page.getByTestId('golaxy-home-page')).toBeVisible();
  await expect(page.getByText('当前星阵账号')).toBeVisible();
  await expect(page.getByRole('button', { name: /快速匹配/ })).toBeDisabled();
  await expect(page.getByRole('button', { name: /房间/ })).toBeDisabled();
  await expect(page.getByRole('button', { name: /人机对弈/ })).toBeEnabled();
  await page.waitForLoadState('networkidle');

  const result = await captureFourUp({
    page,
    referencePng: resolve(PREVIEWS, 'golaxy-runtime-1024x600.png'),
    localReference: true,
    outDir: testInfo.outputPath('fourup'),
    slug: 'golaxy-home',
    referenceCaption: '用户已确认的 React 运行时:星阵专页 · 1024×600',
    implementationCaption: '正式 React 路由:真实连接状态；人人对弈未接通，匹配和房间不可点；棋友不使用假数据',
  });
  console.log(`[fourup golaxy-home] both=${result.both} refOnly=${result.refOnly} implOnly=${result.implOnly}`);
});

test('四图:OGS 专页 ←→ 已确认的 1024×600 React 运行时', async ({ page }, testInfo) => {
  await boot(page, '/kiosk/play/cross-platform/ogs');
  await expect(page.getByTestId('platform-lobby-page')).toBeVisible();
  await expect(page.getByText('my_ogs_account')).toBeVisible();
  await expect(page.getByRole('button', { name: /快速匹配/ })).toBeDisabled();
  await expect(page.getByRole('button', { name: /发起挑战/ })).toBeDisabled();
  await expect(page.getByRole('button', { name: /找人下/ })).toBeEnabled();
  await page.waitForLoadState('networkidle');

  const result = await captureFourUp({
    page,
    referencePng: resolve(PREVIEWS, 'ogs-runtime-fixture-1024x600.png'),
    localReference: true,
    outDir: testInfo.outputPath('fourup'),
    slug: 'ogs-home',
    referenceCaption: '用户已确认的 React 运行时:OGS 专页 · 1024×600；挑战行来自隔离预览 Fixture',
    implementationCaption: '正式 React 路由:连接状态来自 API；挑战行仅由这条截图测试的 API Stub 提供',
  });
  console.log(`[fourup ogs-home] both=${result.both} refOnly=${result.refOnly} implOnly=${result.implOnly}`);
});
