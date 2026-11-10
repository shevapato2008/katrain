import { expect, test, type Page, type WebSocketRoute } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { kioskMeJson } from './helpers/kioskIdentity';
import { stubBackendStatics } from './helpers/fourup';

test.use({ viewport: { width: 1024, height: 600 } });
const SHOTS = resolve(process.cwd(), '../../../output/playwright/lobby-game-unified');
mkdirSync(SHOTS, { recursive: true });
const seat = (name: string) => ({ player_type: 'player:human', player_subtype: '', name, calculated_rank: null, periods_used: 0, main_time_used: 0 });
const stateFor = (over: Record<string, unknown> = {}) => ({
  game_id: 'lobby-game', game_type: 'pvp_lobby', board_size: [19, 19], komi: 7.5, handicap: 0, ruleset: 'chinese',
  count_min_moves: 100, current_node_id: 0, current_node_index: 0,
  history: [{ node_id: 0, score: null, winrate: null, move: null, player: null }],
  player_to_move: 'B', platform_my_color: 'B', my_color: 'B', stones: [], last_move: null,
  prisoner_count: { B: 0, W: 0 }, analysis: null, commentary: '', is_root: true, is_pass: false,
  end_result: null, children: [], ghost_stones: [], players_info: { B: seat('fan'), W: seat('在线棋友') }, note: '',
  ui_state: { show_children: false, show_dots: false, show_hints: false, show_policy: false,
    show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false }, ...over,
});
async function open(page: Page, state = stateFor()) {
  const runtimeErrors: string[] = [];
  page.on('pageerror', error => runtimeErrors.push(error.message));
  let socket!: WebSocketRoute;
  const requests: string[] = [];
  await page.addInitScript(() => { localStorage.setItem('token', 'lobby-test'); localStorage.setItem('katrain_language', 'cn'); });
  await page.routeWebSocket('**/ws/**', ws => { if (ws.url().includes('/ws/lobby-session')) socket = ws; });
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith('/api/')) return route.continue();
    requests.push(path);
    if (path === '/api/translations') return route.fulfill({ json: { translations: { chinese: '中国' } } });
    if (path === '/api/v1/health') return route.fulfill({ json: { engines: { local: 'reachable' } } });
    if (path === '/api/state') return route.fulfill({ json: { state } });
    if (path === '/api/v1/auth/me') return route.fulfill({ json: kioskMeJson({ username: 'fan' }) });
    if (path === '/api/v1/vision/status') return route.fulfill({ json: { enabled: false, camera_connected: false,
      pose_locked: false, sync_state: 'unbound', recognition_ready: false, led_connected: null, bound_session_id: null } });
    if (path === '/api/v1/geometry/status') return route.fulfill({ status: 404, json: { detail: 'disabled' } });
    if (path === '/api/count/request') return route.fulfill({ json: { status: 'pending' } });
    if (path === '/api/count/respond') return route.fulfill({ json: { accepted: route.request().postDataJSON().accept } });
    if (path === '/api/resign') return route.fulfill({ json: { state: { ...state, end_result: 'W+R' } } });
    return route.fulfill({ json: {} });
  });
  await stubBackendStatics(page);
  await page.route('**/assets/sounds/*', route => route.fulfill({ path: resolve(process.cwd(), '../../sounds', new URL(route.request().url()).pathname.split('/').pop()!) }));
  await page.goto('/kiosk/play/pvp/room/lobby-session');
  await expect(page.locator('.lobby-game__status-head')).toContainText('已连接');
  await page.waitForSelector('[data-testid="game-board"] canvas');
  await page.evaluate(() => document.fonts.ready);
  expect(runtimeErrors).toEqual([]);
  return { requests, send: (data: unknown) => socket.send(JSON.stringify(data)) };
}

test('approved lobby geometry and four actions, honest click-only territory loading/error/retry/result', async ({ page }) => {
  const lobby = await open(page);
  expect(lobby.requests).not.toContain('/api/pvp/territory');
  expect(lobby.requests).not.toContain('/api/analysis/current');
  const geometry = await page.evaluate(() => {
    const rect = (selector: string) => { const r = document.querySelector(selector)!.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; };
    const rail = document.querySelector('.lobby-game') as HTMLElement;
    return { board: rect('[data-testid="game-board"]'), rail: rect('.lobby-game'), header: rect('.lobby-game__head'),
      players: rect('.lobby-game__seats'), status: rect('.lobby-game__status'),
      keys: [...document.querySelectorAll('.lobby-game__actions button,.lobby-game__toggles button:not(.lobby-game__help)')].map(el => { const r = el.getBoundingClientRect(); return [r.width, r.height]; }),
      icons: [...document.querySelectorAll('.lobby-game__key svg')].map(el => { const r = el.getBoundingClientRect(); return [r.width, r.height]; }),
      overflow: rail.scrollHeight - rail.clientHeight, docHeight: document.documentElement.scrollHeight };
  });
  expect(geometry.board).toEqual([16, 70, 516, 516]);
  expect(geometry.rail).toEqual([548, 70, 460, 516]);
  expect(geometry.header[3]).toBe(62); expect(geometry.players[3]).toBe(104); expect(geometry.status[3]).toBe(152);
  expect(geometry.keys).toEqual(Array(6).fill([109, 50]));
  expect(geometry.icons).toEqual(Array(8).fill([22, 22]));
  expect(geometry.overflow).toBeLessThanOrEqual(0); expect(geometry.docHeight).toBeLessThanOrEqual(600);
  await expect(page.locator('[data-testid="game-actions"] button')).toHaveText(['领地', '数子', '停一手', '认输']);
  await expect(page.getByRole('button', { name: '数子', exact: true })).toBeDisabled();
  await page.screenshot({ path: `${SHOTS}/normal-1024x600.png` });
  let calls = 0;
  await page.route('**/api/pvp/territory', async route => {
    calls++;
    if (calls === 1) return route.fulfill({ status: 503, json: { detail: 'temporarily unavailable' } });
    return route.fulfill({ json: { session_id: 'lobby-session', game_id: 'lobby-game', current_node_id: 0,
      move_count: 0, board_size: [19, 19], ownership: Array.from({ length: 361 }, (_, i) => i < 180 ? .8 : -.8),
      black_area: 170, white_area: 165, stale: false } });
  });
  await page.getByRole('button', { name: '领地', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveText('领地未取得，请重试');
  await page.screenshot({ path: `${SHOTS}/territory-error-1024x600.png` });
  await page.getByRole('button', { name: '领地', exact: true }).click();
  await expect(page.getByText('领地参考 · 黑 170.0 · 白 165.0')).toBeVisible();
  await expect(page.getByRole('button', { name: '领地', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.screenshot({ path: `${SHOTS}/territory-result-1024x600.png` });
  expect(calls).toBe(2);
  await page.getByRole('button', { name: '领地', exact: true }).click();
  expect(calls).toBe(2);
  lobby.send({ type: 'game_update', state: stateFor({ current_node_id: 1, current_node_index: 1, player_to_move: 'W' }) });
  await expect(page.getByRole('button', { name: '停一手', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: '领地', exact: true })).toHaveAttribute('aria-pressed', 'false');
  expect(calls).toBe(2);
});

test('formal count request and opponent response keep their actual transports', async ({ page }) => {
  const lobby = await open(page, stateFor({ history: Array(100).fill({ node_id: 0, score: null, winrate: null }) }));
  await page.getByRole('button', { name: '数子', exact: true }).click();
  await expect(page.getByTestId('lobby-count-pending')).toBeVisible();
  await expect(page.getByRole('button', { name: '领地', exact: true })).toBeDisabled();
  expect(lobby.requests).toContain('/api/count/request');
  await page.screenshot({ path: `${SHOTS}/count-pending-1024x600.png` });
  lobby.send({ type: 'count_rejected' });
  await expect(page.getByTestId('lobby-count-notice')).toHaveText('数子请求已被拒绝');
  lobby.send({ type: 'count_request', data: { requester_id: 2, requester_name: '在线棋友' } });
  await expect(page.getByRole('dialog')).toContainText('对方请求数子');
  await page.getByRole('button', { name: '接受数子', exact: true }).click();
  await expect(page.getByRole('dialog')).not.toBeVisible();
  expect(lobby.requests).toContain('/api/count/respond');
});

test('central outage hides the unknown board and preserves the real reconnect action', async ({ page }) => {
  const lobby = await open(page);
  lobby.send({ type: 'error', code: 'CENTRAL_DISCONNECTED' });
  await expect(page.getByTestId('central-room-disconnected')).toBeVisible();
  await expect(page.getByTestId('game-board')).not.toBeVisible();
  await page.screenshot({ path: `${SHOTS}/disconnected-1024x600.png` });
  const before = lobby.requests.filter(path => path === '/api/state').length;
  await page.getByRole('button', { name: '重新连接', exact: true }).click();
  await expect(page.locator('.lobby-game__status-head')).toContainText('已连接');
  expect(lobby.requests.filter(path => path === '/api/state').length).toBe(before + 1);
});
