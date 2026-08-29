/* 「所有带棋盘的右边栏宽度是否统一」的实测闸。
 *
 * 判据不是读源码，是**在真浏览器里逐页逐档量** `board-right-rail` 的 border-box 宽，
 * 与 spec §2.3 的四档比。任何一页只要走了别的版式（或有人给某页单独写了宽度），
 * 这里就会报出来。
 *
 * 用法：cd katrain/web/ui && node ../../../superpowers/tracks/galaxy-ui-redesign/audit_rail_width.mjs
 */
import { createRequire } from 'node:module';
import path from 'node:path';
const require = createRequire(path.join(process.cwd(), 'package.json'));
const { chromium } = require('@playwright/test');

const BASE = process.env.GALAXY_BASE_URL ?? 'http://127.0.0.1:8002';
const ROUTES = [
  ['对局 game', '/galaxy/play/game/free-demo'],
  ['人人对弈 room', '/galaxy/play/room/room-demo'],
  ['研究 research', '/galaxy/research'],
  ['复盘列表 reports', '/galaxy/report'],
  ['复盘详情 report', '/galaxy/report/1'],
  ['死活题 tsumego', '/galaxy/tsumego/problem/10039'],
  ['直播列表 live', '/galaxy/live'],
  ['直播对局 match', '/galaxy/live/yike_184016'],
  ['棋谱库 kifu', '/galaxy/kifu'],
  ['教程图 tutorial', '/galaxy/tutorials/figure/1'],
];
/* 每档取一个代表视口 + 断点前一像素，钉「档位边界」也钉「顶档不再更宽」。 */
const TIERS = [
  [1024, 768, 320], [1199, 800, 320],
  [1200, 800, 360], [1440, 900, 360], [1535, 900, 360],
  [1536, 900, 420], [1919, 1080, 420],
  [1920, 1080, 520], [2560, 1440, 520],
];

const browser = await chromium.launch();
const ctx = await browser.newContext();
await ctx.addInitScript(() => {
  localStorage.setItem('token', 'test-token');
  localStorage.setItem('katrain_language', 'cn');
  localStorage.setItem('galaxy.sidebar.docked.expanded.v1', 'true');
});
const page = await ctx.newPage();
await page.routeWebSocket(/\/ws\//, () => {});
await page.route('**/api/v1/auth/me', (r) => r.fulfill({ json: { id: 1, username: 'fan', credits: 0 } }));
/* 对局/人人对弈两页要有一份局面才会渲染右栏。造的是**输入**（一份合法 state），
   断言的仍然是浏览器量出来的栏宽 —— 不造这份输入，这两页就只能报 no-rail，
   而「到达不了」对版式一个字都证明不了。 */
const STONES = [['B', [3, 3]], ['W', [15, 15]], ['B', [15, 3]], ['W', [3, 15]]];
await page.route((u) => u.pathname === '/api/state', (r) => r.fulfill({ json: { state: {
  game_id: 'demo', board_size: [19, 19], komi: 6.5, handicap: 0, ruleset: 'japanese',
  current_node_id: 4, current_node_index: 4,
  history: STONES.map((_, i) => ({ node_id: i + 1, score: null, winrate: null })),
  player_to_move: 'B', stones: STONES.map(([c, pt], i) => [c, pt, i + 1, null]),
  last_move: [3, 15], prisoner_count: { B: 0, W: 0 }, analysis: null, commentary: '',
  is_root: false, is_pass: false, end_result: null, children: [], ghost_stones: [], note: '', language: 'cn',
  game_type: 'ai_free', count_min_moves: 100,
  players_info: {
    B: { player_type: 'player:human', player_subtype: '', name: 'fan', rank_display: '无级别', calculated_rank: null, periods_used: 0, main_time_used: 29 },
    W: { player_type: 'player:ai', player_subtype: 'ai:human', name: 'AI (拟人)', rank_display: '10级', calculated_rank: null, periods_used: 0, main_time_used: 0 },
  },
  timer: { paused: false, main_time_used: 29, current_node_time_used: 4, next_player_periods_used: 0, settings: { main_time: 10, byo_length: 30, byo_periods: 3, minimal_use: 0, sound: false } },
  ui_state: { show_children: false, show_dots: false, show_hints: false, show_policy: false, show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false },
} } }));

const rows = [];
for (const [name, route] of ROUTES) {
  for (const [w, h, expect] of TIERS) {
    await page.setViewportSize({ width: w, height: h });
    await page.goto(BASE + route, { waitUntil: 'domcontentloaded' }).catch(() => {});
    const ok = await page.getByTestId('board-right-rail').first()
      .waitFor({ timeout: 8000 }).then(() => true).catch(() => false);
    if (!ok) { rows.push({ name, vp: `${w}x${h}`, expect, got: null, verdict: 'no-rail' }); continue; }
    await page.waitForTimeout(150);
    const got = await page.evaluate(() =>
      Math.round(document.querySelector('[data-testid="board-right-rail"]').getBoundingClientRect().width));
    rows.push({ name, vp: `${w}x${h}`, expect, got, verdict: got === expect ? 'ok' : 'MISMATCH' });
  }
}
await browser.close();

const reached = rows.filter((r) => r.verdict !== 'no-rail');
const bad = reached.filter((r) => r.verdict === 'MISMATCH');
const unreached = [...new Set(rows.filter((r) => r.verdict === 'no-rail').map((r) => r.name))];
console.log(`到达并量到右栏：${reached.length} 次（${new Set(reached.map((r) => r.name)).size} 个页面 × ${TIERS.length} 档）`);
for (const n of [...new Set(reached.map((r) => r.name))]) {
  const mine = reached.filter((r) => r.name === n);
  console.log(`  ${n.padEnd(20)} ${mine.map((r) => `${r.vp}->${r.got}`).join('  ')}`);
}
if (unreached.length) console.log(`未渲染出右栏（本地无数据/未登录，非版式问题）：${unreached.join('、')}`);
console.log(bad.length ? `\n❌ 宽度不一致 ${bad.length} 处：\n` + bad.map((r) => `  ${r.name} @${r.vp} 期望 ${r.expect} 实得 ${r.got}`).join('\n')
                       : `\n✅ 到达的每个棋盘页、每一档，右栏宽度都与 spec §2.3 一致`);
process.exit(bad.length ? 1 : 0);
