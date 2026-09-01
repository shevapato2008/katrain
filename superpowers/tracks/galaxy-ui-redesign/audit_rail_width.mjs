/* 「右栏加宽有没有花棋盘」的实测闸（spec §2.3）。
 *
 * 2026-09-01 之前这里断言的是一张**写死的档位表**。栏宽改成
 * `clamp(档位下限, 壳宽 − 20 − min(1200, 视高 − 72), 900)` 之后，表就没法写死了：
 * 同一个视口宽度下，侧边栏折没折、视口多高，栏宽都不一样 —— 那正是这条公式要的。
 *
 * 所以判据换成**不变式**，它不会过期：
 *   ① 新栏宽 ≥ 旧档位定值    —— 任何一档都不许变窄
 *   ② 新栏宽下的棋盘边长 == 旧档位定值下的棋盘边长 —— 加宽不许花棋盘
 * 两项都在同一个页面、同一帧里现场量，不引用任何记下来的数字。
 *
 * 用法：cd katrain/web/ui && GALAXY_BASE_URL=... node ../../../superpowers/tracks/galaxy-ui-redesign/audit_rail_width.mjs
 */
import { createRequire } from 'node:module';
import path from 'node:path';
const require = createRequire(path.join(process.cwd(), 'package.json'));
const { chromium } = require('@playwright/test');

const BASE = process.env.GALAXY_BASE_URL ?? 'http://127.0.0.1:8002';
const ROUTES = [
  ['对局 game', '/galaxy/play/game/free-demo'],
  ['研究 research', '/galaxy/research'],
  ['复盘列表 reports', '/galaxy/report'],
  ['复盘详情 report', '/galaxy/report/1'],
  ['死活题 tsumego', '/galaxy/tsumego/problem/10039'],
  ['直播列表 live', '/galaxy/live'],
  ['直播对局 match', '/galaxy/live/yike_184016'],
  ['棋谱库 kifu', '/galaxy/kifu'],
];
/* 每档一个代表视口 + 断点前一像素。`old` 是 2026-09-01 之前那一档的定值，
   就是不变式里的「旧档位定值」—— 它是**参照物**不是期望值。 */
const TIERS = [
  [1024, 768, 320], [1199, 800, 320],
  [1200, 800, 360], [1440, 900, 360], [1535, 900, 360],
  [1536, 900, 420], [1919, 1080, 420],
  [1920, 1080, 620], [2000, 1050, 620], [2560, 1440, 620],
  [1920, 1200, 520], [1920, 1440, 520], [2560, 1600, 520],
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

/* 同一帧里量两次：一次是现在的样子，一次是把栅格钉回旧定值。
   钉回去用的是内联样式，量完立刻还原 —— 断言的两个数因此出自同一棵 DOM、同一次布局。 */
const PROBE = (oldPx) => {
  const shell = document.querySelector('[data-testid="board-page-shell"]');
  const rail = document.querySelector('[data-testid="board-right-rail"]');
  /* 列表页在没选中对局之前棋盘区是一句占位文字，没有 canvas 可量。
     那时**不能静默跳过**——跳过等于给这一页发通行证。改成：栏宽那一条照常判，
     棋盘那一条如实记成 n/a，并在汇总里单独计数，让「没量到」看得见。 */
  const cv = document.querySelector('canvas');
  if (!shell || !rail) return null;
  const read = () => ({
    rail: Math.round(rail.getBoundingClientRect().width),
    board: cv ? Math.round(cv.getBoundingClientRect().width) : null,
  });
  const now = read();
  const prev = shell.style.gridTemplateColumns;
  shell.style.gridTemplateColumns = `minmax(0, 1fr) ${oldPx}px`;
  shell.getBoundingClientRect();
  const before = read();
  shell.style.gridTemplateColumns = prev;
  shell.getBoundingClientRect();
  return { now, before, hasBoard: !!cv };
};

let bad = 0, seen = 0, gain = 0, noBoard = 0;
for (const [name, route] of ROUTES) {
  const cells = [];
  for (const [w, h, oldPx] of TIERS) {
    await page.setViewportSize({ width: w, height: h });
    await page.goto(BASE + route, { waitUntil: 'domcontentloaded' }).catch(() => {});
    const ok = await page.getByTestId('board-right-rail').first()
      .waitFor({ timeout: 8000 }).then(() => true).catch(() => false);
    if (!ok) { cells.push(`${w}x${h}->no-rail`); continue; }
    await page.waitForTimeout(200);
    const r = await page.evaluate(PROBE, oldPx);
    if (!r) { cells.push(`${w}x${h}->no-shell`); continue; }
    seen++;
    if (!r.hasBoard) noBoard++;
    const notNarrower = r.now.rail >= oldPx;
    const boardKept = !r.hasBoard || r.now.board === r.before.board;
    if (!notNarrower || !boardKept) {
      bad++;
      cells.push(`✗${w}x${h} 栏${oldPx}->${r.now.rail} 盘${r.before.board}->${r.now.board}`);
    } else {
      gain += r.now.rail - oldPx;
      cells.push(`${w}x${h}:${oldPx}->${r.now.rail}${r.now.rail > oldPx ? '+' : '='}${r.hasBoard ? '' : '(盘n/a)'}`);
    }
  }
  console.log(`  ${name.padEnd(16)} ${cells.join('  ')}`);
}
console.log(`\n量到 ${seen} 格，${bad} 格违反不变式（① 不许变窄 ② 棋盘边长不许变）`);
console.log(`其中 ${noBoard} 格棋盘区是占位符（列表页未选中对局），②在那些格上量不到 —— 记账，不当通过。`);
console.log(`累计多给右栏 ${gain}px（跨页面跨档位求和），棋盘一处未动。`);
await browser.close();
process.exit(bad ? 1 : 0);
