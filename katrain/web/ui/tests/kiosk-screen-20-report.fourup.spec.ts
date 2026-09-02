import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/20-report/1024x600');

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
  // 2026-09-02:等的东西换了。屏 20 默认展开的是**AI 推荐**(逐手的东西),
  // 曲线搬进了「着手评价」折叠块的「走势」tab,默认收着 —— 再等
  // `review-winrate-plot` 会等到超时,而超时会把「版式变了」伪装成「页面坏了」。
  await page.waitForSelector('[data-testid="ai-recommend-row"]');
  // 稿子那一帧画的是**着手评价展开、走势 tab**,所以取图前先点开它 ——
  // AI 推荐那张表和屏 21 是同一个组件,在这儿再拍一遍什么都没多说;
  // 五个 tab 才是这一屏新增的全部内容。左右两半必须停在同一态上。
  await page.click('[data-testid="report-detail-grade"] .kiosk-fold__head');
  await page.waitForSelector('[data-testid="review-winrate-plot"][data-state="plotted"]');
  // 点完要**失焦**:焦点环是取图这个动作留下的痕迹,不是这一屏的默认长相,
  // 留着它差异图上会多出一圈蓝框,而那圈框在真机上根本不存在。
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  // canvas 是图片加载完之后才画的 —— 早一步取到的是一张空白盘。
  await page.waitForFunction(() => {
    const c = document.querySelector('.kiosk-board__play canvas') as HTMLCanvasElement | null;
    if (!c || !c.width) return false;
    const d = c.getContext('2d')!.getImageData(0, Math.floor(c.height / 2), c.width, 1).data;
    for (let i = 0; i < d.length; i += 4) if (d[i] > 40) return true;
    return false;
  });
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '20-report.png'),
    outDir: OUT,
    slug: '20-report',
    referenceCaption:
      'sample-go/shots/20-report.png(2026-09-02 随本次改版重出)。右栏是**单开手风琴**:'
      + '收着的「AI 推荐」头上仍写着结论(黑 25.0%),展开的是「着手评价 · 七档」的**走势** tab。'
      + '两块都展开要 380 而只有 300 —— 「都展开」在这一屏上不是默认值问题、是装不下;'
      + '共享闸 screen-gate.mjs 为此开了 accordions 这个口,核的是「至少开一块」(变异验过)。',
    implementationCaption:
      '实现 /kiosk/report/:taskId @1024×600 · 时钟冻 16:40 · 取图前点开了「着手评价」并失焦。'
      + '五个 tab 走势/妙手/失误/发挥水准/AI吻合度,名字与顺序逐个对上 galaxy 的 TrendChart;'
      + '走势图两条曲线:绿读左轴(胜率,上黑下白)、橙读右轴(目差 ±12),0 目与 50% 都落在正中虚线上;'
      + '显示开关 试下/领地/手数/支招 的顺序与图标逐个对上 galaxy(这一排推翻了「开关不带图标」那条老规矩,理由记在 go-screens.css)。'
      + ' ⚠️ 四处已知差,都不是版式的:'
      + '① 页控条 稿子「自由对弈 · KataGo 6 级 / 你执黑负」,实现「vs KataGo · 6 级 / 你(黑)中盘负」—— 两处措辞早就不一样,不是这次改的;'
      + '② 状态区 稿子「深度复盘」实现「深度报告」—— 设备上 PO 赢,这一对登记在 PO_OVERRIDES_DEFAULT_BASELINE 里;'
      + '③「领地」是灰的:这份 fixture 的逐手行没有 ownership,而按钮 disabled={!ownership};真报告有这份数据,稿子画的是有的那一态;'
      + '④ 盘上有手数、曲线读数是 17 手 fixture 真算的 —— 稿子那块盘是静态图不跟自己的开关走,那条曲线是照 187 手的故事画的示意线。',
  });
  console.log(`[fourup 20-report] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
