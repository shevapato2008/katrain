import { test } from '@playwright/test';
import { freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

/**
 * 屏 20 复盘 · 报告(L2 布局 A:盘 516 + 16 + 右栏 460)。
 *
 * 盘上那 17 手**逐点抄稿子的 `data-b` / `data-w`**,顺序排成一条合法的交替谱,
 * 最后一手落在稿子标出来的 J17 上。
 *
 * ⚠️ **差异图上会红的地方,下面这些都是预期**:
 *  ① 题头第二行稿子写「每手算 2000 次 · 用了 6 分 12 秒」,实现写「每手算 2000 次 · 187 手」——
 *    **耗时接口不给**(`ReportTaskStatus` 不吐 `started_at` / `completed_at`),编一个就是假数据。
 *    已登记,该提上游补字段。
 *  ② 稿子的盘上没有手数、没有地色,可它自己把「领地」和「手数」两个开关画成了亮着的 ——
 *    **稿子那块盘是静态图,不跟自己的开关走**。实现跟着开关走,所以盘上有数字和地色。
 *  ③ 重点手三行的手数和读数是 fixture,和稿子那三行(43/96/120)不一样:稿子那三个是示意值,
 *    实现是拿 `report_task_moves` 真算的(排序按**走子方自己视角**的胜率跌幅)。
 *  ④ 稿子这一屏没有滑块,实现也没有 —— 但把「点曲线跳到那一手」补上了,
 *    并在曲线上多画一条竖游标标出「现在在第几手」。原来那条 `PlaybackBar` 的功能不能跟着控件一起丢。
 */

// 稿子:黑 Q16,Q4,C6,C10,Q10,C15,R17,E3,J17 / 白 D4,D16,F3,R14,R6,E14,Q6,H3;最后一手 J17。
// 排成交替谱(黑 9 手、白 8 手,黑先),SGF 列 a..s 不跳字母、行 a 在上。
const SGF = '(;FF[4]GM[1]SZ[19]'
  + ';B[pd];W[dp];B[pp];W[dd];B[cn];W[fq];B[cj];W[qf];B[pj]'
  + ';W[qn];B[ce];W[ef];B[qc];W[pn];B[eq];W[hq];B[ic])';

const GAME = {
  id: 'g1', user_id: 1, title: null, player_black: '访客', player_white: 'KataGo',
  black_rank: null, white_rank: '6 级', result: 'W+R', board_size: 19, rules: 'chinese',
  komi: 7.5, move_count: 187, source: 'play_ai', category: 'game', game_type: 'free',
  event: null, round_name: null, game_date: '2026-08-20',
  created_at: new Date('2026-08-20T15:12:00').toISOString(), updated_at: null,
  sgf_content: SGF,
};

/**
 * 十七手的逐手分析,曲线照稿子那条重画:黑 54% 起 → 第 5 手掉到 25% → 一路滑到 8%。
 * 三处掉分(第 5 / 11 / 15 手,都是黑走的奇数手)让「重点手」正好列满三行。
 */
const DROPS: Record<number, number> = { 5: 0.29, 11: 0.12, 15: 0.11 };
function reportMoves() {
  const rows = [];
  let wr = 0.54;
  for (let n = 0; n <= 17; n += 1) {
    const player = n === 0 ? null : (n % 2 === 1 ? 'B' : 'W');
    const prev = wr;
    if (n > 0) wr = Math.max(0.08, wr - (DROPS[n] ?? 0.004));
    const ownDrop = player === 'B' ? prev - wr : wr - prev;
    rows.push({
      id: n, task_id: 41, move_number: n, status: 'success',
      winrate: wr, score_lead: (wr - 0.5) * 24, visits: 2000,
      // 「该走 X」取的是**上一行**的首选 —— 所以候选存在每一行上。
      top_moves: [{ move: ['R11', 'C3', 'S8', 'Q17'][n % 4], visits: 1800, winrate: 0.6, score_lead: 3, prior: 0.7, pv: [], psv: 1 }],
      ownership: null,
      actual_move: player ? 'C3' : null,
      actual_player: player,
      delta_score: player ? (DROPS[n] ? -(DROPS[n] * 40) : -0.3) : null,
      delta_winrate: player ? -ownDrop : null,
    });
  }
  return rows;
}

test('四图:复盘 · 报告 ←→ sample-go/shots/20-report.png', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: '访客', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/v1/geometry/status', (route) => route.fulfill({
    json: {
      phase: 'disabled', session_calibrated: false, last_error: null,
      capabilities: { camera_ready: false, led_ready: false, geometry_ready: false, recognition_ready: false },
    },
  }));
  await page.route('**/api/v1/reports/41/moves', (route) => route.fulfill({ json: reportMoves() }));
  await page.route('**/api/v1/reports/41', (route) => route.fulfill({
    json: {
      id: 41, user_game_id: 'g1', status: 'completed', report_type: 'deep',
      total_moves: 187, analyzed_moves: 187, requested_visits: 2000,
      // 稿子这一行写的就是「每手算 2000 次 · 用了 6 分 12 秒」—— 372 秒。
      // 2026-08-23 之前接口不吐这两个章,屏上只能退回「187 手」;补上之后
      // 参照物和实现说的是同一句话,这一处的差因此该消失。
      started_at: '2026-08-23T01:00:00+08:00', completed_at: '2026-08-23T01:06:12+08:00',
    },
  }));
  await page.route('**/api/v1/user-games/g1', (route) => route.fulfill({ json: GAME }));

  await page.goto('/kiosk/report/41');
  await page.waitForSelector('[data-testid="ai-recommend-row"]');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: '/tmp/kiosk-20-reviewed.png' });
  await page.getByRole('button', { name: 'AI吻合度', exact: true }).click();
  await page.screenshot({ path: '/tmp/kiosk-20-last-tab.png' });
});
