import { test, type Page } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/22-growth/1024x600');

/**
 * 屏 22 成长(§5 **L1 两栏**)—— 27 屏里**最后一屏**,也是唯一实现侧从零新建的一屏。
 *
 * ## 稿子这一屏有四处说的不成立 —— 全部**不照搬**
 *
 * 稿子中段那一大块 `.empty` 是道歉:「段位的算法是全的,接线断在一个词上 ——
 * 写段位的分支只认 `game_type == "rated"`,而人机升降级写的是 `"ranked"`,
 * 所以打完永远不动段位;真正会改段位的只有在线大厅的定级队列」。
 * **2026-08-25 逐条核过,四处都已经不是这样:**
 *
 *  ① **那条 `rated` 计数早被换掉了。** `server.py:2331-2336` 的注释白纸黑字写着替换理由
 *    (「nothing ever wrote that value for an AI game」)⇒ 现在的闸是
 *    `ai_ladder_repo.has_ladder_rank()`;`count_completed_rated_games` 如今**零调用者**。
 *  ② **升降级对弈真会动段位。** `katrain/core/ladder.py` 有完整 41 档,
 *    `ai_ladder_ranked.py` 有 `PLACEMENT_GAMES = 5` / `ai_ladder_rung` / `net_score`,
 *    `/api/v1/ai-ladder/status` 早就把这些吐出来了,**kiosk 也已经在用**(`useAiLadderStatus`)。
 *    ⇒ 左栏画的是真数据,一行后端都没加。
 *  ③ **「上封 12 段」不存在。** 41 档是 20级…1级 / 准1段…9段 / 职业水平 / 职业顶尖 / 超越人类,
 *    全表没有「12 段」这个词。屏上写的是实际上下界。
 *  ④ **「按对手强度」不用等。** `ai_ladder_game_ledger` 每行带 `opponent_rung` /
 *    `opponent_rank_name`,而 `ck_ai_ladder_ledger_decision` 强制 counted 的行必须有档位 ——
 *    **已计入的局一局都不会漏**。稿子写「还没有战绩」是因为它以为没有这张账本。
 *
 * ⇒ 参考图和实现图在**中段**必然大不一样:稿子那儿是一段道歉,实现那儿是真数字。
 * **这不是未对齐,是稿子过时。** 差异图上那一大块红是预期的。
 *
 * ## 预期差异(都是登记项)
 *
 *  · **能力诊断**是真数据了(2026-09):最近几份已完成报告里**你执的那一方**的手,按
 *    布局 / 中盘 / 官子三段数问题手,构造照国象样稿 14 屏的「段名 + 细条」,底部一句样本量。
 *    稿子那儿是「样本 0 局」空态 + 蓝标「后端已有 · 界面未接」—— 两样都去掉了。
 *  · **左栏多了「近 30 天走势」**(档位折线 + 最高点绿标,Fan 2026-09-21 裁定画档位),
 *    稿子这一屏没画;来源是共享规范 §5 与国象样稿 14 屏的 `.spark`。为了装下它,
 *    「升降的规矩」三行从 44 压到 30(不可点,不受触控下限约束)。
 *  · **胜率那一格的标签是「胜率 · 近 30 天」,不是稿子的「胜率 · 同期」**,底下多一句
 *    「有 N 局没算进胜率」。2026-09 起 `user_games.user_color` 记下了用户坐哪一方,
 *    人机局也算得出胜负;面对面、导入的谱、以及这一列上线之前的非升降级局没有这个事实,
 *    **不进分母** —— 分母比「近 30 天对局」小的时候差额必须说出来。
 *    **口径写进标签**是共享外壳 §5 的硬要求(原话:「一个光秃秃的 58% 谁也不知道是哪来的」)。
 *    (云端没部署这一版时标签退回「升降级胜率」,那一态由 `kiosk-screen-22-growth.spec.ts` 的默认夹具覆盖。)
 *  · 取图机器上没有摄像头 ⇒ 与实体盘有关的东西一律不出现(这一屏本来也没有)。
 */

const LADDER = {
  view_state: 'ready',
  placement_state: {
    phase: 'placed',
    rung: { rung: 18, rank_name: '3级', certification_status: 'certified', availability: 'available', route: 'local' },
  },
  current_opponent: null,
  recent_ranked_results: ['win', 'win', 'loss', 'win', 'loss'],
  net_score: 1,
  pending_settlement: false,
  blocking_game: null,
  provisional_play_allowed: false,
};

/** 打过四档。**没打过的档不在这里** —— 那正是稿子要的「不摆一排 0 胜 0 负」。 */
const SUMMARY = {
  window_days: 30,
  games_in_window: 42,
  ranked_total: 31,
  ranked_wins_in_window: 9,
  ranked_losses_in_window: 5,
  // 42 局里 30 局算得出执色 ⇒ 胜率 17/30,差的 12 局由那句 setnote 说出来。
  decided_games_in_window: 30,
  wins_in_window: 17,
  losses_in_window: 13,
  // 定级之后的档位,一天一个点;中间没下的日子不补点。日期落在冻结时钟(2026-09-22)前 30 天里,
  // 与稿子屏 22 那条示例走势同一组偏移(27/24/23/18/15/11/9/6/3/1 天前)。
  rung_trend: [
    ['08-26', 16], ['08-29', 16], ['08-30', 17], ['09-04', 17], ['09-07', 18],
    ['09-11', 17], ['09-13', 18], ['09-16', 19], ['09-19', 18], ['09-21', 18],
  ].map(([d, rung]) => ({ date: `2026-${d}`, rung, rank_name: `${21 - (rung as number)}级` })),
  by_opponent_rung: [
    { rung: 21, rank_name: '准1段', wins: 1, losses: 4 },
    { rung: 20, rank_name: '1级', wins: 3, losses: 3 },
    { rung: 19, rank_name: '2级', wins: 6, losses: 2 },
    { rung: 18, rank_name: '3级', wins: 8, losses: 4 },
  ],
  authority: 'this_node',
};

/** 六份报告、420 手;中盘那段明显高 ⇒ 标「最弱」。样本够,不出「结论会抖」那句。 */
const DIAGNOSIS = {
  window_days: 90,
  reports: 6,
  skipped_without_color: 0,
  graded_moves: 420,
  phases: [
    { phase: 'opening', graded: 150, bad: 15 },
    { phase: 'midgame', graded: 200, bad: 60 },
    { phase: 'endgame', graded: 70, bad: 7 },
  ],
  authority: 'this_node',
};

/**
 * 近一年练棋日历。**与稿子屏 22 那张示例同一个生成器、同一个种子**(smartbox `go-kiosk.tmpl.html`
 * 末尾那段脚本逐行搬过来)⇒ 两边的格子逐格相同,差异图上剩下的只有结构差异。
 * 稿子的「今天」是 2026-09-22,所以这一屏的时钟也冻在那一天(见 `freezeClock` 那一行)。
 */
const ACTIVITY = (() => {
  const DAY = 86400000;
  const today = Date.UTC(2026, 8, 22);
  const first = today - 364 * DAY;
  const dow = (t: number) => (new Date(t).getUTCDay() + 6) % 7;
  let seed = 20260922;
  const rand = () => {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const days: { date: string; games: number; solved: number }[] = [];
  for (let t = first - dow(first) * DAY; t <= today; t += DAY) {
    if (t < first) continue;
    const d = new Date(t);
    const progress = (t - first) / (today - first);
    let p = 0.28 + 0.5 * progress + (dow(t) >= 5 ? 0.12 : 0);
    const m = d.getUTCMonth() + 1, dd = d.getUTCDate();
    if ((m === 2 && dd >= 14 && dd <= 22) || (m === 5 && dd >= 3 && dd <= 13)) p = 0.06;
    const n = rand() < p ? 1 + Math.floor(Math.pow(rand(), 1.7) * (4 + 10 * progress)) : 0;
    if (n > 0) {
      const games = Math.ceil(n / 3);
      days.push({ date: d.toISOString().slice(0, 10), games, solved: n - games });
    }
  }
  return { window_days: 365, days, authority: 'this_node' };
})();

/** 37 道做过的题,其中 29 道解出来了 —— 「累计已解题」那一格的来源。 */
const PROGRESS = Object.fromEntries(
  Array.from({ length: 37 }, (_, i) => [`p${i}`, { problemId: `p${i}`, completed: i < 29, attempts: 1 }]),
);

const stub = async (page: Page) => {
  await stubBackendStatics(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup-22');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') {
      return route.fulfill({ json: { id: 1, username: '访客', rank: '3级', credits: 0 } });
    }
    if (path === '/api/v1/ai-ladder/status') return route.fulfill({ json: LADDER });
    if (path === '/api/v1/growth/summary') return route.fulfill({ json: SUMMARY });
    if (path === '/api/v1/growth/diagnosis') return route.fulfill({ json: DIAGNOSIS });
    if (path === '/api/v1/growth/activity') return route.fulfill({ json: ACTIVITY });
    if (path === '/api/v1/tsumego/progress') return route.fulfill({ json: PROGRESS });
    if (path === '/api/v1/vision/status') {
      return route.fulfill({ json: { enabled: false, camera_connected: false, pose_locked: false,
        sync_state: 'unbound', recognition_ready: false, led_connected: null, bound_session_id: null } });
    }
    if (path === '/api/v1/geometry/status') return route.fulfill({ status: 404, json: { detail: 'disabled' } });
    // 引擎已就绪 —— 顶栏那条「AI 引擎准备中」(2026-09-17 加的预热提示)只在开机头一两分钟出现,
    // 不是这一屏的常态。不 stub 它的话兜底的 `{}` 会被读成「还在预热」,四图里凭空多一条横幅。
    if (path === '/api/v1/health') return route.fulfill({ json: { engines: { local: 'reachable' } } });
    return route.fulfill({ json: {} });
  });
};

test('四图:成长 ←→ sample-go/shots/22-growth.png', async ({ page }) => {
  // 冻在稿子的「今天」:日历的右端和走势的横轴都从这一天往回数。
  await freezeClock(page, '2026-09-22T16:40:00');
  await stub(page);
  await page.goto('/kiosk/growth');
  // 等的是**打过的档真的画出来了** —— 它是这一屏区别于稿子的那一块。
  await page.waitForSelector('[data-testid="growth-by-rung"] .grung');
  await page.waitForSelector('[data-testid="diag-row"]');
  await page.waitForSelector('[data-testid="growth-trend"]');
  await page.waitForSelector('[data-testid="growth-cal-days"]');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '22-growth.png'),
    outDir: OUT,
    slug: '22-growth',
    referenceCaption:
      '参考:sample-go/shots/22-growth.png(2026-09-22 照实现重画 + 近一年练棋日历)· L1 两栏 · '
      + '左栏段位 / 净胜分 / 走势 / 规矩 / 两格,右栏数据条 + 胜率口径 + 日历 + 诊断 | 按对手强度',
    implementationCaption:
      '实现:/kiosk/growth @1024×600 · 时钟冻 16:40 · '
      + '**稿子这一屏有四处已经不成立,全部没照搬** —— ① 那条只认 game_type=="rated" 的计数'
      + '早被 has_ladder_rank() 换掉了(server.py 的注释写着替换理由),'
      + 'count_completed_rated_games 如今零调用者;② 升降级对弈真会动段位:ladder.py 有完整 41 档、'
      + 'PLACEMENT_GAMES=5、net_score,/api/v1/ai-ladder/status 早就在吐,kiosk 也已经在用 ⇒ '
      + '**左栏画真数据,一行后端都没加**;③ 稿子写的「上封 12 段」在 41 档里根本不存在'
      + '(20级…1级 / 准1段…9段 / 职业水平 / 职业顶尖 / 超越人类)⇒ 屏上写实际上下界;'
      + '④ 「按对手强度」不用等:ai_ladder_game_ledger 每行带 opponent_rung,而 CHECK 约束'
      + '强制 counted 的行必须有档位 ⇒ **已计入的局一局不漏**,打过哪档列哪档 · '
      + '⇒ **中段那一大块红是预期的:稿子那儿是一段道歉,实现那儿是真数字** · '
      + '**胜率那格是「胜率 · 近 30 天」**:user_games 记下了执色,人机局也算得出胜负;'
      + '42 局里 30 局算得出 ⇒ 57%,差的 12 局由底下那句「没算进胜率」说出来 · '
      + '**能力诊断是真数据**:最近 6 份报告里你下的 420 手,按布局/中盘/官子数问题手(小亏·失误·恶手),'
      + '中盘 60/200 明显高 ⇒ 标「最弱」;稿子的「样本 0 局」和蓝标都去掉了 · '
      + '**左栏多了近 30 天档位走势**(Fan 09-21 裁定画档位),最高点走 --good 绿标;'
      + '为装下它「升降的规矩」三行从 44 压到 30 · '
      + '**近一年练棋日历**(Fan 09-22):每格 = 当天下完的对局 + 新解出的题,固定五档;'
      + '格子数据与稿子同一个种子,逐格相同',
  });
  console.log(`[fourup 22-growth] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
