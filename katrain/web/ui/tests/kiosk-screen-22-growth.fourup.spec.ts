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
 *  · **能力诊断**那一块照搬稿子的诚实空态:它要拿**已经跑过报告**的对局算,那是另一条链
 *    (复盘屏),这一轮不接。标签用 `.wip.have`(蓝 = 后端已有 · 界面未接),不是琥珀。
 *  · **胜率那一格的标签是「升降级胜率」,不是稿子的「胜率 · 同期」。**
 *    `user_games.result` 存的是**哪一方赢**(`"B+R"`),表里**没有一列记这个用户坐哪一方**
 *    (测试对着 `__table__.columns` 断言过)。只有升降级账本的 `result` 是从用户视角写的。
 *    **口径写进标签**是共享外壳 §5 的硬要求(原话:「一个光秃秃的 58% 谁也不知道是哪来的」)。
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
  by_opponent_rung: [
    { rung: 21, rank_name: '准1段', wins: 1, losses: 4 },
    { rung: 20, rank_name: '1级', wins: 3, losses: 3 },
    { rung: 19, rank_name: '2级', wins: 6, losses: 2 },
    { rung: 18, rank_name: '3级', wins: 8, losses: 4 },
  ],
  authority: 'this_node',
};

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
    if (path === '/api/v1/tsumego/progress') return route.fulfill({ json: PROGRESS });
    if (path === '/api/v1/vision/status') {
      return route.fulfill({ json: { enabled: false, camera_connected: false, pose_locked: false,
        sync_state: 'unbound', recognition_ready: false, led_connected: null, bound_session_id: null } });
    }
    if (path === '/api/v1/geometry/status') return route.fulfill({ status: 404, json: { detail: 'disabled' } });
    return route.fulfill({ json: {} });
  });
};

test('四图:成长 ←→ sample-go/shots/22-growth.png', async ({ page }) => {
  await freezeClock(page);
  await stub(page);
  await page.goto('/kiosk/growth');
  // 等的是**打过的档真的画出来了** —— 它是这一屏区别于稿子的那一块。
  await page.waitForSelector('[data-testid="growth-by-rung"] .grung');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '22-growth.png'),
    outDir: OUT,
    slug: '22-growth',
    referenceCaption:
      '参考:sample-go/shots/22-growth.png · L1 两栏 · 左栏段位 + 升降规矩,'
      + '右栏数据条 + 一大段「接线断在一个词上」+ 两块诊断空态',
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
      + '**胜率那格标签是「升降级胜率」不是「胜率」**:user_games.result 说的是哪一方赢,'
      + '表里没有一列记这个用户坐哪一方,只有升降级账本的 result 是从用户视角写的——'
      + '口径必须写进标签 · **能力诊断**照搬稿子的诚实空态(要拿跑过报告的对局算,那是复盘那条链)',
  });
  console.log(`[fourup 22-growth] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
