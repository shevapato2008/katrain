/* 右栏加宽（spec §2.3，2026-08-30）的取图脚本。
 *
 * 取的是**对局中**那一屏（Fan 截图的那一屏：自由对弈、双方计时、四宫格工具、走势图、
 * 显示开关、离开对局），因为右栏内容最满、最能看出加宽之后内部排版够不够用。
 * 所有 API 都是 route mock，不连后端也不连引擎——这里要的是版式，不是数据。
 *
 * 用法（先 `npm run build`，再起 :8002 或任意 baseURL）：
 *   cd katrain/web/ui && node ../../../superpowers/tracks/galaxy-ui-redesign/capture_rail_widths.mjs <标签>
 */
import { createRequire } from 'node:module';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';

const require = createRequire(path.join(process.cwd(), 'package.json'));
const { chromium } = require('@playwright/test');

const label = process.argv[2] ?? 'implementation';
/* `legacy` = 用 CSS 覆盖把右栏压回加宽之前的三档（320/340/380），拿来做同一次构建下的
   before 图。之所以不 checkout 旧代码重新构建：本仓多 worktree 共用一条 stash 栈，
   而且工作区里还有没提交的活，`git checkout HEAD -- <file>` 会把它们冲掉。 */
const legacy = process.env.RAIL_LEGACY === '1';
const baseUrl = process.env.GALAXY_BASE_URL ?? 'http://127.0.0.1:8002';
const outRoot = path.resolve(process.cwd(), '../../../superpowers/tracks/galaxy-ui-redesign/visual/rail-width');
const imgRoot = path.resolve(process.cwd(), '../../../katrain/img');

/* 1280×800 与 1536×960 是**棋盘会掉像素**的两档（各 −20 / −32），必须取进来 ——
   只取不掉像素的视口，等于把这次的代价从证据里排除掉。 */
const VIEWPORTS = [[1280, 800], [1440, 900], [1536, 900], [1536, 960], [1920, 1080], [2000, 1050], [2560, 1440]];

const stones = [
  ['B', [3, 3]], ['W', [15, 15]], ['B', [15, 3]], ['W', [3, 15]],
  ['B', [9, 9]], ['W', [10, 9]], ['B', [9, 10]], ['W', [10, 10]],
  ['B', [4, 4]], ['W', [14, 14]], ['B', [14, 4]], ['W', [4, 14]],
  ['B', [6, 2]], ['W', [12, 2]], ['B', [2, 6]], ['W', [16, 6]],
];

const TRANSLATIONS = {
  Home: '首页', 'btn:Play': '对局', Research: '研究', Tsumego: '死活题',
  'analysis:report': '复盘', Live: '直播', 'kifu:library': '棋谱库', Tutorials: '教程',
  Settings: '设置', Logout: '退出登录', Territory: '领地', Advice: '支招', Graph: '图表',
  Undo: '悔棋', PASS: '停一手', RESIGN: '认输', COUNT: '数子', Coordinates: '坐标',
  'Move Numbers': '手数', Captures: '提子', Komi: '贴目', Rules: '规则', japanese: '日本',
  'live:black_winrate': '黑棋胜率', 'live:black_lead': '黑棋领先', 'live:points_unit': '目',
  'play:vs_ai_free': '自由对弈', 'game:leave': '离开对局',
};

async function mock(page) {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token');
    localStorage.setItem('katrain_language', 'cn');
    localStorage.setItem('galaxy.sidebar.docked.expanded.v1', 'true');
  });
  /* `/ws/{session_id}` 是**鉴权**的，假 token 会被服务端 1008 拒掉，页面随即换成
     「实时连接被拒绝」而根本不渲染 `board-page-shell`。这里把 WS 整条接管掉：
     不连真服务器，保持连接开着即可 —— 这一屏要的是版式，棋局数据全从 /api/state 来。 */
  await page.routeWebSocket(/\/ws\//, () => {});
  await page.route('**/api/v1/auth/me', (r) => r.fulfill({ json: { id: 1, username: 'fan', rank: null, credits: 0 } }));
  await page.route('**/api/translations?lang=cn', (r) => r.fulfill({ json: { lang: 'cn', translations: TRANSLATIONS } }));
  await page.route('**/api/v1/live/translations?lang=cn', (r) => r.fulfill({ json: { players: {}, tournaments: {}, rounds: {}, rules: {} } }));
  await page.route('**/api/v1/users/following', (r) => r.fulfill({ json: [] }));
  await page.route('**/api/v1/ai-ladder/status', (r) => r.fulfill({ json: {
    view_state: 'ready', placement_state: { phase: 'unplaced' }, current_opponent: null,
    recent_ranked_results: [], net_score: 0, pending_settlement: false,
  } }));
  await page.route((u) => u.pathname === '/api/state', (r) => r.fulfill({ json: { state: {
    game_id: 'free-demo', board_size: [19, 19], komi: 6.5, handicap: 0, ruleset: 'japanese',
    current_node_id: stones.length, current_node_index: stones.length,
    history: stones.map((_, i) => ({ node_id: i + 1, score: (i % 5) - 2, winrate: 0.45 + (i % 7) * 0.015 })),
    player_to_move: 'B', stones: stones.map(([c, p], i) => [c, p, i + 1, null]),
    last_move: [16, 6], prisoner_count: { B: 0, W: 0 }, analysis: null, commentary: '',
    is_root: false, is_pass: false, end_result: null, children: [], ghost_stones: [], note: '', language: 'cn',
    game_type: 'ai_free', count_min_moves: 100,
    players_info: {
      B: { player_type: 'player:human', player_subtype: '', name: 'fan', rank_display: '无级别', calculated_rank: null, periods_used: 0, main_time_used: 29 },
      W: { player_type: 'player:ai', player_subtype: 'ai:human', name: 'AI (拟人)', rank_display: '10级', calculated_rank: null, periods_used: 0, main_time_used: 0 },
    },
    timer: { paused: false, main_time_used: 29, current_node_time_used: 4, next_player_periods_used: 0, settings: { main_time: 10, byo_length: 30, byo_periods: 3, minimal_use: 0, sound: false } },
    ui_state: { show_children: false, show_dots: false, show_hints: false, show_policy: false, show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false },
  } } }));
  for (const name of ['logo-white.png', 'board.png', 'B_stone.png', 'W_stone.png', 'inner.png', 'topmove.png']) {
    await page.route(`**/assets/img/${name}`, (r) => r.fulfill({ path: path.join(imgRoot, name) }));
  }
}

const browser = await chromium.launch();
const rows = [];
for (const [w, h] of VIEWPORTS) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await mock(page);
  page.on('pageerror', (e) => console.error('[pageerror]', String(e).slice(0, 400)));
  await page.goto(`${baseUrl}/galaxy/play/game/free-demo`, { waitUntil: 'domcontentloaded' });
  try {
    await page.getByTestId('board-page-shell').waitFor({ timeout: 15000 });
  } catch (e) {
    console.error('[body]', (await page.locator('body').innerText()).slice(0, 500));
    throw e;
  }
  await page.getByTestId('board-stage').locator('canvas').waitFor({ timeout: 30000 });
  if (legacy) {
    await page.addStyleTag({ content: `
      @media (min-width:900px)  { [data-testid="board-page-shell"] { grid-template-columns: minmax(0,1fr) 320px !important; } }
      @media (min-width:1200px) { [data-testid="board-page-shell"] { grid-template-columns: minmax(0,1fr) 340px !important; } }
      @media (min-width:1536px) { [data-testid="board-page-shell"] { grid-template-columns: minmax(0,1fr) 380px !important; } }
    ` });
  }
  await page.waitForTimeout(900);
  const dir = path.join(outRoot, `${w}x${h}`);
  await mkdir(dir, { recursive: true });
  await page.screenshot({ path: path.join(dir, `${label}.png`) });
  await page.getByTestId('board-right-rail').screenshot({ path: path.join(dir, `${label}-rail.png`) });
  rows.push(await page.evaluate(() => {
    const b = (s) => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height) }; };
    const rail = document.querySelector('[data-testid="board-right-rail"]');
    const scroll = document.querySelector('[data-testid="board-rail-scroll"]');
    return {
      vp: `${innerWidth}x${innerHeight}`, rail: b('[data-testid="board-right-rail"]'),
      stage: b('[data-testid="board-stage"]'), canvas: b('[data-testid="board-stage"] canvas'),
      railOverflow: scroll ? scroll.scrollHeight - scroll.clientHeight : null,
      hScroll: document.documentElement.scrollWidth > innerWidth,
      railClipped: rail ? rail.scrollWidth > rail.clientWidth : null,
    };
  }));
  await ctx.close();
}
await browser.close();
console.log(JSON.stringify(rows, null, 2));
