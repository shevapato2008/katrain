import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { freezeClock } from './helpers/fourup';

// Test-only fixture. Every API/WS is intercepted; this file never starts a backend.
test.use({ viewport: { width: 1024, height: 600 } });
const OUT = process.env.TERRITORY_PREVIEW_DIR ?? '/tmp/territory-view-dismissal-20261105';
const moves = ['Q16', 'D4', 'C14', 'D16', 'Q4', 'Q10', 'C11', 'F17', 'Q6', 'L3', 'K17', 'G3', 'C7', 'D6', 'C5', 'C4', 'D8', 'F5', 'R14', 'N17', 'M16', 'P17'];
const xy = (move: string) => ['ABCDEFGHJKLMNOPQRST'.indexOf(move[0]), Number(move.slice(1)) - 1];
const stateFor = (source: 'ranked' | 'star') => ({
  game_id: 'territory-fixture', board_size: [19, 19], komi: 7.5, handicap: 0, ruleset: 'chinese',
  game_type: source === 'ranked' ? 'ai_ladder_ranked' : 'free', count_min_moves: 100,
  current_node_id: moves.length, current_node_index: moves.length,
  history: [{ node_id: 0, score: null, winrate: null, move: null, player: null },
    ...moves.map((move, i) => ({ node_id: i + 1, score: null, winrate: null, move, player: i % 2 ? 'W' : 'B' }))],
  player_to_move: 'B', stones: moves.map((move, i) => [i % 2 ? 'W' : 'B', xy(move), null, i + 1]),
  last_move: xy(moves[moves.length - 1]), prisoner_count: { B: 0, W: 0 },
  analysis: null, commentary: '', is_root: false, is_pass: false, end_result: null, children: [], ghost_stones: [],
  platform_engine_color: source === 'star' ? 'W' : null,
  players_info: {
    B: { player_type: 'player:human', player_subtype: '', name: '你', calculated_rank: '', periods_used: 0, main_time_used: 0 },
    W: { player_type: 'player:ai', player_subtype: '', name: source === 'star' ? '星阵' : 'KataGo', calculated_rank: -4, periods_used: 0, main_time_used: 0 },
  }, note: '',
  ui_state: { show_children: false, show_dots: false, show_hints: false, show_policy: false, show_ownership: false,
    show_move_numbers: false, show_coordinates: true, zen_mode: false },
});
const ownership = Array.from({ length: 361 }, (_, index) => {
  const x = index % 19; const y = Math.floor(index / 19);
  return (x < 7 && y < 8) || (x > 10 && y > 10) ? 0.8
    : (x > 14 && y < 5) || (x < 4 && y > 13) ? -0.8 : 0;
});

async function fixture(page: Page, source: 'ranked' | 'star') {
  page.on('pageerror', (error) => console.error('[fixture pageerror]', error.message));
  let territoryCalls = 0;
  let otherAnalysisCalls = 0;
  const state = stateFor(source);
  await freezeClock(page, '2026-11-05T16:40:00');
  await page.addInitScript(() => {
    localStorage.setItem('token', 'territory-test-fixture');
    localStorage.setItem('katrain_language', 'cn');
    localStorage.setItem('kiosk_play_on_board', 'false');
  });
  await page.routeWebSocket('**/ws/**', () => { /* all game/vision sockets stay local */ });
  await page.route('**/assets/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith('/assets/')) return route.continue();
    const name = path.split('/').pop() ?? '';
    if (!['logo-white.png', 'B_stone.png', 'W_stone.png', 'board.png', 'inner.png', 'topmove.png'].includes(name)) return route.abort();
    // Read only these named Git blobs; no filesystem dependency on backend assets.
    const body = execFileSync('git', ['show', `HEAD:katrain/img/${name}`]);
    return route.fulfill({ body, contentType: 'image/png' });
  });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith('/api/')) return route.continue();
    if (path === '/api/v1/auth/me') return route.fulfill({ json: { id: 1, uuid: 'territory-test', username: '预览棋手', credits: 0 } });
    if (path === '/api/translations') return route.fulfill({ json: { lang: 'cn', translations: { chinese: '中国' } } });
    if (path === '/api/state') return route.fulfill({ json: { state } });
    if (path === '/api/v1/vision/status') return route.fulfill({ json: { enabled: false, camera_connected: false, pose_locked: false,
      sync_state: 'unbound', recognition_ready: false, led_connected: null, bound_session_id: null } });
    if (path === '/api/v1/geometry/status') return route.fulfill({ status: 404, json: { detail: 'fixture: no hardware' } });
    if (path === '/api/ai-ladder/territory') {
      if (route.request().method() === 'GET') return route.fulfill({ json: { remaining: territoryCalls ? 0 : 1, in_flight: false } });
      territoryCalls++;
      return route.fulfill({ json: { remaining: 0, move_count: moves.length, ownership,
        black_area: ownership.filter(n => n > 0.5).length, white_area: ownership.filter(n => n < -0.5).length } });
    }
    if (path === '/api/v1/platforms/golaxy/engine/items') return route.fulfill({ json: { area: territoryCalls ? 11 : 12, options: 5, variation: 0 } });
    if (path === '/api/v1/platforms/golaxy/engine/analysis') {
      const { kind } = route.request().postDataJSON();
      if (kind !== 'area') {
        otherAnalysisCalls++;
        return route.fulfill({ json: { ok: true, kind, data: { candidates: [] } } });
      }
      territoryCalls++;
      return route.fulfill({ json: { ok: true, kind, data: {
        ownership: ownership.map((value, index) => ({ col: index % 19, row: 18 - Math.floor(index / 19), value })), winrate: 0.375, delta: -2.2,
      } } });
    }
    return route.fulfill({ json: {} });
  });
  await page.goto(source === 'ranked' ? '/kiosk/play/ai/game/territory-fixture' : '/kiosk/play/cross-platform/engine/game/territory-fixture');
  await expect(page.locator('[data-testid="game-board"] canvas')).toBeVisible({ timeout: 15_000 });
  await page.evaluate(() => document.fonts.ready);
  return { calls: () => territoryCalls, otherCalls: () => otherAnalysisCalls };
}

// Independent static panel reference over the unchanged runtime board/shell.
// It records the proposed composition; production uses the MUI presentation component.
async function reference(page: Page, source: 'ranked' | 'star', background: Buffer) {
  const referencePage = await page.context().newPage();
  const quota = source === 'ranked' ? '升降级本局剩余 0 次 · 同局面可免费复看' : '星阵账号领地道具剩余 11 次 · 同局面可免费复看';
  const origin = new URL(page.url()).origin;
  const html = `<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="${origin}/src/kiosk-shell/fonts.css?direct"><style>
  *{box-sizing:border-box}body{margin:0;width:1024px;height:600px;background:url(data:image/png;base64,${background.toString('base64')});font-family:"SmartBox Sans","SmartBox Kai",system-ui;color:#eef3f1;font-synthesis:none}
  .shade{position:absolute;top:56px;bottom:0;left:540px;right:0;background:#06100ba8}.wrap{height:600px;display:flex;align-items:center;justify-content:flex-end;padding-right:56px}
  .card{width:380px;max-height:380px;border:2px solid #c486f1;border-radius:15px;background:#26352e;box-shadow:0 0 0 4px #b66cf229,0 18px 38px #000c,0 0 30px #b66cf24d;position:relative}
  h2{font-size:28px;font-family:"SmartBox Serif","SmartBox Kai",Georgia,serif;line-height:1.25;margin:0;padding:14px 16px 4px;font-weight:600}.content{padding:8px 16px}p{font-size:18px;line-height:1.5;margin:0}.source{color:#93a49d;margin-bottom:8px}.lead{font-size:22px;line-height:1.5;font-weight:600;margin-bottom:8px}.win{margin-bottom:8px}.quota{color:#93a49d;margin-top:12px}.note{color:#93a49d;margin-top:8px}.actions{padding:10px 16px 14px}button{font:600 22px/1.75 "SmartBox Sans","SmartBox Kai",system-ui;width:100%;padding:12px 24px;border:0;border-radius:12px;background:#58b57a;color:#0f1416;min-height:44px}
  </style><div class="shade"></div><div class="wrap"><div class="card"><h2>领地判断</h2><div class="content"><p class="source">${source === 'ranked' ? '升降级 · 云端参考' : '星阵 · 账号道具'}</p><p class="lead">${source === 'ranked' ? '暂未取得领先判断' : '预计白领先 2.2 目'}</p>${source === 'ranked' ? '<p>黑方较确定区域 120 点</p><p>白方较确定区域 40 点</p>' : '<p class="win">黑棋胜率 37.5%</p>'}<p class="quota">${quota}</p><p class="note">局中参考，正式胜负以终局数子为准</p></div><div class="actions"><button>关闭领地，继续下棋</button></div></div></div>`;
  writeFileSync(resolve(OUT, `${source}-reference.html`), html);
  const target = `${origin}/territory-design-reference.html`;
  await referencePage.route(target, route => route.fulfill({ body: html, contentType: 'text/html' }));
  await referencePage.goto(target);
  await referencePage.evaluate(() => document.fonts.ready);
  await referencePage.screenshot({ path: resolve(OUT, `${source}-reference.png`), animations: 'disabled' });
  await referencePage.close();
}

for (const source of ['ranked', 'star'] as const) {
  test(`${source}: territory opens, closes Canvas and reopens without another query`, async ({ page }) => {
    mkdirSync(OUT, { recursive: true });
    const meter = await fixture(page, source);
    const board = page.locator('[data-testid="game-board"] canvas');
    const boardPixels = () => board.evaluate((canvas: HTMLCanvasElement) => canvas.toDataURL());
    const initialPixels = await boardPixels();
    const territory = () => page.getByRole('button', { name: source === 'ranked' ? /^领地\s*\d/ : /^\d+\s*领地/, includeHidden: true });
    await expect(territory()).toBeEnabled();
    await territory().click();
    const dialog = page.getByRole('dialog', { name: '领地判断' });
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText(source === 'ranked' ? '暂未取得领先判断' : '预计白领先 2.2 目');
    await expect.poll(boardPixels).not.toBe(initialPixels);
    await expect(dialog).toContainText(source === 'ranked' ? '本局剩余 0 次' : '道具剩余 11 次');
    const geometry = await page.evaluate(() => {
      const rect = (selector: string) => { const r = document.querySelector(selector)!.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height, right: r.right, bottom: r.bottom }; };
      const rail = document.querySelector('.kiosk-rail')!;
      const container = document.querySelector('.kiosk-game-side-dialog .MuiDialog-container')!;
      return { dialog: rect('[role="dialog"]'), close: rect('[role="dialog"] .MuiDialogActions-root button:last-child'), board: rect('[data-testid="game-board"]'), railOverflow: rail.scrollHeight - rail.clientHeight,
        backdropColor: getComputedStyle(document.querySelector('.kiosk-game-side-dialog .MuiBackdrop-root')!).backgroundColor,
        rightRailScrimLeft: parseFloat(getComputedStyle(container, '::before').left),
        documentWidth: document.documentElement.scrollWidth, documentHeight: document.documentElement.scrollHeight };
    });
    expect(geometry.dialog.width).toBe(380);
    expect(geometry.board.right).toBeLessThanOrEqual(geometry.dialog.x);
    expect(geometry.backdropColor).toBe('rgba(0, 0, 0, 0)');
    expect(geometry.rightRailScrimLeft).toBeGreaterThanOrEqual(geometry.board.right);
    expect(geometry.close.height).toBeGreaterThanOrEqual(42);
    expect(geometry.close.bottom).toBeLessThanOrEqual(600);
    expect(geometry.railOverflow).toBeLessThanOrEqual(0);
    expect(geometry.documentWidth).toBe(1024);
    expect(geometry.documentHeight).toBe(600);
    writeFileSync(resolve(OUT, `${source}-geometry.json`), JSON.stringify(geometry, null, 2));
    // The reference borrows only the unchanged game shell and Canvas backdrop.
    await page.getByTestId('territory-dialog').evaluate((el) => { el.style.visibility = 'hidden'; });
    const background = await page.screenshot({ animations: 'disabled' });
    await page.getByTestId('territory-dialog').evaluate((el) => { el.style.visibility = ''; });
    await reference(page, source, background);
    await page.screenshot({ path: resolve(OUT, `${source}-implementation.png`), animations: 'disabled' });
    await page.getByRole('button', { name: '关闭领地，继续下棋' }).click();
    await expect(dialog).toBeHidden();
    await expect.poll(boardPixels).toBe(initialPixels);
    await territory().click();
    await expect(dialog).toBeVisible();
    expect(meter.calls()).toBe(1);
    if (source === 'ranked') await expect(territory()).toHaveAttribute('aria-pressed', 'true');
    else {
      await page.getByRole('button', { name: '关闭领地，继续下棋' }).click();
      await page.getByRole('button', { name: /支招$/ }).click();
      await expect.poll(meter.otherCalls).toBe(1);
      await territory().click();
      await expect(dialog).toBeVisible();
      expect(meter.calls()).toBe(1);
    }
    // Comparison images are generated in the test browser, without an imaging dependency.
    const compared = await page.evaluate(async ({ ref, impl }) => {
      const load = (src: string) => new Promise<HTMLImageElement>((resolve) => { const i = new Image(); i.onload = () => resolve(i); i.src = src; });
      const [a, b] = await Promise.all([load(ref), load(impl)]);
      const side = document.createElement('canvas'); side.width = 2048; side.height = 600;
      const s = side.getContext('2d')!; s.drawImage(a, 0, 0); s.drawImage(b, 1024, 0);
      const overlay = document.createElement('canvas'); overlay.width = 1024; overlay.height = 600;
      const o = overlay.getContext('2d')!; o.drawImage(a, 0, 0); o.globalAlpha = 0.5; o.drawImage(b, 0, 0);
      return { side: side.toDataURL().split(',')[1], overlay: overlay.toDataURL().split(',')[1] };
    }, { ref: `data:image/png;base64,${readFileSync(resolve(OUT, `${source}-reference.png`)).toString('base64')}`,
      impl: `data:image/png;base64,${readFileSync(resolve(OUT, `${source}-implementation.png`)).toString('base64')}` });
    writeFileSync(resolve(OUT, `${source}-side-by-side.png`), Buffer.from(compared.side, 'base64'));
    writeFileSync(resolve(OUT, `${source}-overlay.png`), Buffer.from(compared.overlay, 'base64'));
  });
}
