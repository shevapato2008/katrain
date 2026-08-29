import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/19-review/1024x600');

/**
 * 屏 19 复盘(L1 布局 A,**形态 2**:头尾固定,只有中间那条列表滚)。
 *
 * 造的数据逐条对着稿子那张图:六局、第一局已分析、曲线在第 43 手掉下去。
 * 时钟冻在 16:40,所以前两局落「今天 15:12 / 今天 11:40」,第三局「昨天」,后三局「前天 / 07-24」。
 *
 * ⚠️ **差异图上会红的地方,下面这些都是预期**:
 *  ① 稿子的行尾只有一个状态标,实现多了动作键(查看报告 / 继续分析)和一个删除 ——
 *    规范 §11 要求四种分析状态各有各的样子,且「就地干活不跳页」(Fan 2026-07-28);
 *    国象稿子同一处画的就是「状态标 + 药丸键」。**稿子这一屏是漏画,不是简化。**
 *  ② 组标题右端多一个放大镜(搜索开关)。稿子这一屏没画搜索,但**稿子自己的 `.sbox` 注释
 *    把复盘列进了「有搜索的四屏」**,而现状这条搜索是通的 —— 也是漏画。
 *    收起态和稿子逐像素一样,展开才多出那条框。
 *  ③ 第三张卡在稿子上是 `is-soon`「接口还没有 · 即将上线」,实现里是**能用的** ——
 *    两条导入路(本地 SGF / 棋谱库)都在跑,挂「即将上线」等于把有的说成没有。
 *  ④ 三格的数字对不上稿子的 78% / 4 手 / 1 手:稿子那三个是示意值,实现是拿
 *    `report_task_moves` 真算的(算式见 `features/report/reportStats.ts`)。
 *    造的数据让**失误 4 手、妙手 1 手**落在稿子那两个数上,准确率随算式走。
 *  ⑤ 第三行稿子写「在线大厅 · 定级局」,实现按 `source` + `game_type` 拼成
 *    「升降级对弈 · 对手」——「在线大厅」这个说法在库里没有对应的列,不自己编。
 */

const at = (iso: string) => new Date(iso).toISOString();

const GAMES = [
  {
    id: 'g1', title: null, player_black: '访客', player_white: 'KataGo',
    black_rank: null, white_rank: '6 级', result: 'W+R', move_count: 187,
    source: 'play_ai', game_type: 'free', created_at: at('2026-08-20T15:12:00'),
  },
  {
    id: 'g2', title: null, player_black: 'KataGo', player_white: '访客',
    black_rank: '3 级', white_rank: null, result: 'B+6.5', move_count: 241,
    source: 'play_ai', game_type: 'free', created_at: at('2026-08-20T11:40:00'),
  },
  {
    id: 'g3', title: null, player_black: '访客', player_white: '网友',
    black_rank: null, white_rank: '4 级', result: 'W+R', move_count: 154,
    source: 'play_human', game_type: 'ai_ladder_ranked', created_at: at('2026-08-19T20:05:00'),
  },
  {
    id: 'g4', title: null, player_black: '小明', player_white: '小红',
    black_rank: null, white_rank: null, result: 'B+R', move_count: 96,
    source: 'play_local', game_type: 'free', created_at: at('2026-08-18T19:20:00'),
  },
  {
    id: 'g5', title: 'OGS', player_black: 'aphelion', player_white: '访客',
    black_rank: '2d', white_rank: '1d', result: 'W+2.5', move_count: 268,
    source: 'import', game_type: null, created_at: at('2026-07-24T21:00:00'),
  },
  {
    id: 'g6', title: null, player_black: '小明', player_white: '小红',
    black_rank: null, white_rank: null, result: null, move_count: 22,
    source: 'play_local', game_type: 'free', created_at: at('2026-08-18T09:30:00'),
  },
].map((g) => ({
  user_id: 1, board_size: 19, rules: 'chinese', komi: 7.5, category: 'game',
  event: null, round_name: null, game_date: '2026-08-20', updated_at: null, ...g,
}));

/**
 * 187 手的逐手分析。**黑方 4 手失误、1 手妙手** —— 落在稿子那两个数上。
 * 曲线照稿子那条重画:54% 起、第 43 手掉到 25%、后面一路滑到 8%。
 * 上黑下白,所以 `winrate` 就是黑方胜率(cron 那条线固定 `reportAnalysisWinratesAs: "BLACK"`)。
 */
// ⚠️ 必须全是**奇数**:奇数手才是黑走的。写成偶数的话失误会记到白头上,
// 而左栏三格算的是黑 —— 屏上「失误」那格会少两手,却看不出为什么(2026-08-23 踩过)。
const MISTAKES = [43, 97, 121, 155];
const BRILLIANT = 61;

function reportMoves() {
  const wrAt = (n: number): number => {
    if (n <= 42) return 0.54 + Math.sin(n / 7) * 0.02;
    if (n === 43) return 0.25;
    if (n <= 95) return 0.31 - (n - 43) * 0.0006;
    if (n <= 119) return 0.19 - (n - 96) * 0.0004;
    if (n <= 154) return 0.11 - (n - 120) * 0.0005;
    return 0.08;
  };
  const rows = [];
  let prevScore = 0;
  for (let n = 0; n <= 187; n += 1) {
    const player = n === 0 ? null : (n % 2 === 1 ? 'B' : 'W');
    // 目差跟着胜率走(粗略够用):正 = 黑好。
    const score = (wrAt(n) - 0.5) * 24;
    let delta: number | null = null;
    if (player) {
      const raw = player === 'B' ? score - prevScore : prevScore - score;
      delta = MISTAKES.includes(n) ? Math.min(raw, -4.2)
        : n === BRILLIANT ? 2.6
          : Math.max(-0.9, Math.min(0.9, raw));
    }
    rows.push({
      id: n, task_id: 41, move_number: n, status: 'success',
      winrate: wrAt(n), score_lead: score, visits: 500,
      top_moves: null, ownership: null,
      actual_move: player ? 'Q16' : null, actual_player: player,
      delta_score: delta, delta_winrate: null,
    });
    prevScore = score;
  }
  return rows;
}

/**
 * 左栏那块终局盘 —— **逐点抄稿子那张图的 `data-b` / `data-w`**,不是自己摆的:
 *   黑 Q16,Q4,C6,C10,Q10,C15,R17   白 D4,D16,F3,R14,R6,E14,Q6   最后一手 R17
 * 这里换算成 `/baipu/load` 的 canonical 坐标(row 0 在上,col 按 ABCDEFGHJKLMNOPQRST 数)。
 */
const FINAL_BOARD = [
  ['B', 3, 15],  // Q16
  ['W', 15, 3],  // D4
  ['W', 3, 3],   // D16
  ['B', 15, 15], // Q4
  ['B', 13, 2],  // C6
  ['W', 16, 5],  // F3
  ['B', 9, 2],   // C10
  ['W', 5, 16],  // R14
  ['B', 9, 15],  // Q10
  ['W', 13, 16], // R6
  ['B', 4, 2],   // C15
  ['W', 5, 4],   // E14
  ['W', 13, 15], // Q6
  ['B', 2, 16],  // R17 —— 最后一手
] as const;

test('四图:复盘 ←→ sample-go/shots/19-review.png', async ({ page }) => {
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
  await page.route('**/api/v1/user-games/g*', (route) => route.fulfill({
    json: { ...GAMES[0], sgf_content: '(;FF[4]GM[1]SZ[19];B[pd];W[dd])' },
  }));
  await page.route('**/api/v1/user-games**', (route) => route.fulfill({
    json: { items: GAMES, total: GAMES.length, page: 1, page_size: 12 },
  }));
  await page.route('**/api/v1/reports/summary', (route) => route.fulfill({
    json: { pending: 0, running: 0, completed: 1, failed: 0 },
  }));
  await page.route('**/api/v1/reports/41/moves', (route) => route.fulfill({ json: reportMoves() }));
  await page.route('**/api/v1/reports/', (route) => route.fulfill({
    json: [{
      id: 41, user_game_id: 'g1', status: 'completed', report_type: 'normal',
      total_moves: 187, analyzed_moves: 187, requested_visits: 500,
    }],
  }));
  await page.route('**/api/v1/baipu/load', (route) => route.fulfill({
    json: {
      board_size: 19,
      steps: FINAL_BOARD.map(([color, row, col], i) => ({
        kind: 'move', move_index: i, property: color, row, col, color,
        removed: [], board_hash: '',
      })),
      meta: {},
    },
  }));

  await page.goto('/kiosk/report');
  await page.waitForSelector('[data-testid="review-rows"] .kiosk-row:nth-child(3)');
  await page.waitForSelector('[data-testid="review-winrate-plot"][data-state="plotted"]');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '19-review.png'),
    outDir: OUT,
    slug: '19-review',
    referenceCaption:
      '参考:sample-go/shots/19-review.png · L1 布局 A 形态 2(镜像栏 296 + 16 + 右栏 680;'
      + '胜率固定 122 / 历史对局 194 会滚 / 生成报告 102 固定)· 上黑下白 · 行尾只有一个状态标',
    implementationCaption:
      '实现:/kiosk/report @1024×600 · 时钟冻 16:40 · 六局与逐手分析是 fixture · '
      + '**三格是「妙手」不是国象的「漏着」**:围棋的报告是 cron 离线跑的(每手 500/2000 次),'
      + '不受盒子算力限制,且 `reportModel.ts:192` 早有 `delta_score ≥ 2` 这条口径 —— 转判据不转结论 · '
      + '曲线接真数据,稿子那枚「后端已有 · 界面未接」蓝标本轮不成立,已去掉 · '
      + '行尾多出动作键(规范 §11 四态各有各的样子 + 就地干活不跳页,国象稿子同处就是这么画的)· '
      + '组标题右端多一个搜索开关(稿子漏画,它自己的 `.sbox` 注释把复盘算进了有搜索的四屏)· '
      + '第三张卡是能用的,不是「即将上线」· 三格数字随算式走,稿子那三个是示意值 · '
      + 'Dock 七项(2026-08-25 起补了「成长」,围棋独有)',
  });
  console.log(`[fourup 19-review] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
