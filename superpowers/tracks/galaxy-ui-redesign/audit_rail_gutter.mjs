/* 「右栏左右内边距是不是全栏、全页面同一个值」的实测闸。
 *
 * 判据不是读源码，是在真浏览器里量**每一段的第一个可见内容**相对右栏左边框的偏移：
 * 模块牌的标题、滚动区的第一件东西、动作区的第一件东西，三者都必须等于
 * `RAIL_GUTTER`。改之前这三个数是 0 / 12 / 16 —— 标题贴着左框就是那个 0。
 *
 * 用法：cd katrain/web/ui && GALAXY_BASE_URL=... node ../../../superpowers/tracks/galaxy-ui-redesign/audit_rail_gutter.mjs
 */
import { createRequire } from 'node:module';
import path from 'node:path';
const require = createRequire(path.join(process.cwd(), 'package.json'));
const { chromium } = require('@playwright/test');

const BASE = process.env.GALAXY_BASE_URL ?? 'http://127.0.0.1:8002';
const GUTTER = 20;
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
/* 两个视口：一个窄档一个宽档。水槽是同一个值，两档都得对上。 */
const VIEWPORTS = [[1440, 900], [2000, 1050]];

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

/* 量的是**可见文字**的左边缘，不是包装盒的：满宽的分隔条、满宽的按钮组本来就顶到
   水槽边，量它们等于什么都没量。

   三段的期望值不一样，而且**其中一个是算出来的不是写死的**：
   - `module`：有返回键时标题本来就该缩到返回键右边（`20 + 40 + 12`），
     所以期望值取「返回键右边缘 + 间距」而不是 20。没有返回键就是 20。
   - `scroll`：一律 20。搜索框、卡片、区段标题都在这一段，Fan 报的
     「标题和卡片对不齐」就是拿这一段和 module 比出来的。
   - `actions`：一律 ≥20。这一段常放居中的播放条和满宽按钮，居中不是缺陷，
     所以只钉「不许比水槽还靠左」，不钉等于。 */
const PROBE = (gutter) => {
  const rail = document.querySelector('[data-testid="board-right-rail"]');
  if (!rail) return null;
  const R = rail.getBoundingClientRect();
  const out = [];
  for (const seg of ['board-rail-module', 'board-rail-scroll', 'board-rail-actions']) {
    const box = rail.querySelector(`[data-testid="${seg}"]`);
    if (!box) continue;
    const leaves = [...box.querySelectorAll('*')].filter((el) => {
      if (el.children.length) return false;
      if (!(el.textContent || '').trim()) return false;
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && r.width < R.width * 0.98;
    });
    if (!leaves.length) continue;
    const sample = leaves.reduce((a, b) =>
      a.getBoundingClientRect().left <= b.getBoundingClientRect().left ? a : b);
    const left = Math.round(sample.getBoundingClientRect().left - R.left);

    let want = gutter, why = '';
    if (seg === 'board-rail-module') {
      const back = box.querySelector('button[aria-label]');
      if (back) {
        const br = back.getBoundingClientRect();
        if (br.width > 0) { want = Math.round(br.right - R.left + 12); why = '返回键右侧'; }
      }
    }
    const ok = seg === 'board-rail-actions' ? left >= gutter : left === want;
    out.push({ seg, left, want, why, ok, txt: (sample.textContent || '').trim().slice(0, 14) });
  }
  return { railW: Math.round(R.width), segs: out };
};

let bad = 0, seen = 0;
for (const [name, route] of ROUTES) {
  for (const [w, h] of VIEWPORTS) {
    await page.setViewportSize({ width: w, height: h });
    await page.goto(BASE + route, { waitUntil: 'domcontentloaded' }).catch(() => {});
    const ok = await page.getByTestId('board-right-rail').first()
      .waitFor({ timeout: 8000 }).then(() => true).catch(() => false);
    if (!ok) { console.log(`  ${name.padEnd(18)} ${w}x${h}  no-rail（本地无数据/未登录，非版式问题）`); continue; }
    await page.waitForTimeout(250);
    const got = await page.evaluate(PROBE, GUTTER);
    if (!got) continue;
    for (const s of got.segs) {
      seen++;
      if (!s.ok) bad++;
      const want = s.seg === 'board-rail-actions' ? `≥${GUTTER}` : `${s.want}${s.why ? '（' + s.why + '）' : ''}`;
      console.log(`  ${s.ok ? '✓' : '✗'} ${name.padEnd(18)} ${String(w).padStart(4)}x${h} 栏${String(got.railW).padStart(4)}  ${s.seg.replace('board-rail-', '').padEnd(8)} 左${String(s.left).padStart(3)} 应${String(want).padStart(4)}  「${s.txt}」`);
    }
  }
}
console.log(`\n量到 ${seen} 段，${bad} 段不合格（水槽 ${GUTTER}px）`);
await browser.close();
process.exit(bad ? 1 : 0);
