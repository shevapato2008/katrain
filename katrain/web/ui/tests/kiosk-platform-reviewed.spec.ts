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
  await page.route('**/api/v1/platforms/golaxy/rooms?*', (route) => route.fulfill({ json: { rooms: [
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
  await page.route('**/api/v1/platforms/golaxy/users?*', (route) => route.fulfill({ json: { users: [
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

test('reviewed platform previews and left aligned login variants', async ({ page, context }) => {
  const out = resolve(process.cwd(), '../../../docs/previews/reviewed-platform');
  const reference = await context.newPage();
  for (const [id, name] of [['platform-login-pw', 'golaxy-login'], ['platform-login-ogs', 'ogs-login']]) {
    await reference.goto(`file://${resolve(process.cwd(), '../../../docs/design/kiosk-current-based-redesign-2026-10-14.html')}#${id}`);
    await reference.locator('#stage').evaluate((el: HTMLElement) => { el.style.transform = 'none'; el.style.width='1024px'; el.style.height='600px'; document.body.replaceChildren(el); document.body.style.margin='0'; el.style.position='relative'; el.style.margin='0'; });
    await reference.locator('#stage').screenshot({ path: resolve(out, `${name}-reference.png`) });
  }
  await reference.close();
  await boot(page, '/kiosk/play/cross-platform/golaxy');
  await expect(page.getByText('当前星阵账号')).toBeVisible();
  await page.screenshot({ path: resolve(out, 'golaxy-lobby-1024x600.png') });
  for (const platform of ['golaxy', 'ogs']) {
    await boot(page, `/kiosk/play/cross-platform/login/${platform}`);
    if (platform === 'golaxy') await page.getByTestId('login-mode-tabs').getByRole('button', { name:'密码', exact:true }).click();
    const input = page.getByTestId('login-field-user');
    await expect(input).toBeVisible();
    expect(await input.evaluate(el => getComputedStyle(el).textAlign)).toBe('left');
    await page.screenshot({ path: resolve(out, `${platform}-login-1024x600.png`) });
    if (platform === 'golaxy') {
      await page.getByTestId('login-mode-tabs').getByRole('button', { name:'验证码', exact:true }).click();
      expect(await page.getByTestId('login-field-password').evaluate(el => getComputedStyle(el).textAlign)).toBe('left');
      await page.getByTestId('login-mode-tabs').getByRole('button', { name:'密码', exact:true }).click();
    }
    await captureFourUp({ page, referencePng: resolve(out, `${platform}-login-reference.png`), localReference:true, outDir:out, slug:`${platform}-login`, referenceCaption:'Approved 2026-10-14 proposal stage', implementationCaption:'Actual React route; credentials and connection handlers preserved' });
  }
});
