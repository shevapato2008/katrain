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
  await page.route('**/api/v1/platforms/golaxy/rooms', (route) => route.fulfill({ json: { rooms: [
    ['8799', 0, '甲', '乙', 83],
    ['8895', -1, '丙', '丁', 104],
    ['8843', 0, '戊', '己', 118],
    ['8591', 0, '庚', '辛', 196],
    ['9011', -1, '壬', '癸', 37],
  ].map(([number, handicap, black, white, moveNumber]) => ({
    room_id: `fixture-${number}`, room_number: number, room_type: null, handicap,
    black: { user_id: `black-${number}`, username: `棋手${black}`, rank: null },
    white: { user_id: `white-${number}`, username: `棋手${white}`, rank: null },
    phase: `${moveNumber}手`, spectator_count: null,
  })) } }));
  await page.route('**/api/v1/platforms/golaxy/users', (route) => route.fulfill({ json: { users: [
    { user_id: 'fixture-a', username: '棋友甲', rank: null, status: null },
    { user_id: 'fixture-b', username: '棋友乙', rank: null, status: null },
    { user_id: 'fixture-c', username: '棋友丙', rank: null, status: null },
    { user_id: 'fixture-d', username: '棋友丁', rank: null, status: null },
  ] } }));
  await page.route('**/api/v1/platforms/golaxy/engine/levels', (route) => route.fulfill({ json: { levels: [
    { elo_score: 400, level_name: '第 1 档', name: '星阵 1', goal_difference: 0, timing: '', display_elo: 400, ref_rank: '入门' },
    { elo_score: 1800, level_name: '第 15 档', name: '星阵 15', goal_difference: 0, timing: '', display_elo: 1800, ref_rank: '业余 3 段' },
  ] } }));
  await page.route('**/api/v1/platforms/ogs/active-game', (route) => route.fulfill({ json: { session_id: null } }));
  await page.goto(path);
}

test('四图:星阵大厅 ←→ 已确认的 1024×600 HTML 审核稿', async ({ page }, testInfo) => {
  await boot(page, '/kiosk/play/cross-platform/golaxy');
  await expect(page.getByTestId('golaxy-home-page')).toBeVisible();
  await expect(page.getByText('当前星阵账号')).toBeVisible();
  await expect(page.getByRole('button', { name: /快速匹配/ })).toBeEnabled();
  await expect(page.getByRole('button', { name: /^房间/ })).toBeEnabled();
  await expect(page.getByRole('button', { name: /人机对弈/ })).toBeEnabled();
  await page.waitForLoadState('networkidle');

  const result = await captureFourUp({
    page,
    referencePng: resolve(PREVIEWS, 'golaxy-live-lobby-revised-home-1024x600.png'),
    localReference: true,
    outDir: testInfo.outputPath('fourup'),
    slug: 'golaxy-home',
    referenceCaption: '用户已确认的 HTML 审核稿:星阵大厅 · 1024×600',
    implementationCaption: '正式 React 路由:房间与棋友样本仅来自 API 拦截；匹配/房间进入设置；最终开局与观战尚未接通',
  });
  console.log(`[fourup golaxy-home] both=${result.both} refOnly=${result.refOnly} implOnly=${result.implOnly}`);
});

test('四图:星阵只读观战 ←→ 已确认的 1024×600 HTML 审核稿', async ({ page }, testInfo) => {
  await boot(page, '/kiosk/play/cross-platform/golaxy');
  await page.route('**/api/v1/platforms/golaxy/rooms/fixture-8799/snapshot', (route) => route.fulfill({ json: {
    room_id: 'fixture-8799', room_number: '8799', board_size: 19,
    black: { username: '棋手甲', rank: '7 段' }, white: { username: '棋手乙', rank: '7 段' },
    black_stones: ['D16', 'Q16', 'K10', 'K9'], white_stones: ['D4', 'Q4', 'L10', 'L9'],
    move_number: 48, phase: '进行中', result: null, room_type: '自由战', handicap: 0,
  } }));
  await page.getByRole('button', { name: /8799 房/ }).click();
  await expect(page).toHaveURL(/\/golaxy\/spectate\/fixture-8799$/);
  await expect(page.getByTestId('golaxy-spectator-page')).toBeVisible();
  await expect(page.getByTestId('spectator-board').locator('[data-stone]')).toHaveCount(8);
  expect((await page.getByRole('button', { name: '对战大厅', exact: true }).boundingBox())?.height).toBeGreaterThanOrEqual(44);
  expect((await page.getByRole('button', { name: '返回对战大厅' }).boundingBox())?.height).toBeGreaterThanOrEqual(44);
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: resolve(PREVIEWS, 'golaxy-spectator-runtime-1024x600.png') });
  const result = await captureFourUp({
    page,
    referencePng: resolve(PREVIEWS, 'golaxy-live-lobby-spectate-1024x600.png'),
    localReference: true,
    outDir: testInfo.outputPath('fourup'),
    slug: 'golaxy-spectator',
    referenceCaption: '用户已确认的 HTML 观战审核稿 · 1024×600',
    implementationCaption: 'React 只读观战页；房号、棋手与棋子仅由本条 Playwright API 拦截提供',
  });
  console.log(`[fourup golaxy-spectator] both=${result.both} refOnly=${result.refOnly} implOnly=${result.implOnly}`);
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

for (const state of ['quick', 'room-create', 'room-join', 'ai'] as const) {
  test(`四图:星阵开局设置 ${state} · 1024×600`, async ({ page }, testInfo) => {
    const ai = state === 'ai';
    await boot(page, ai ? '/kiosk/play/cross-platform/engine/golaxy' : `/kiosk/play/cross-platform/golaxy/setup/${state === 'quick' ? 'quick' : 'room'}`);
    if (ai) {
      await expect(page.getByTestId('setup-input')).toBeVisible();
      await expect(page.getByTestId('setup-opponent-plate')).toBeVisible();
    } else {
      await expect(page.getByTestId('golaxy-pregame-page')).toBeVisible();
      if (state === 'room-join') {
        await page.getByRole('tab', { name: '加入房间' }).click();
        await page.getByRole('textbox', { name: '房间号' }).fill('8799');
      }
      await expect(page.getByRole('button', { name: /暂不可用/ })).toBeDisabled();
    }
    await page.waitForLoadState('networkidle');
    const result = await captureFourUp({
      page,
      referencePng: resolve(PREVIEWS, `golaxy-live-lobby-${ai ? 'ai' : state === 'quick' ? 'quick' : 'room'}-1024x600.png`),
      localReference: true,
      outDir: testInfo.outputPath('fourup'),
      slug: `golaxy-setup-${state}`,
      referenceCaption: `用户已确认的 HTML 审核稿:星阵 ${state === 'room-join' ? '房间创建（加入态待补参考图）' : state}`,
      implementationCaption: ai ? '现有星阵 AI 设置；棋力档仅来自 API 拦截' : `正式 React 设置路由:${state}；最终提交等待协议确认`,
    });
    console.log(`[fourup golaxy-${state}] both=${result.both} refOnly=${result.refOnly} implOnly=${result.implOnly}`);
  });
}
