import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubShellAssets } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/10-platform-game/1024x600');

/**
 * 屏 10 星阵围棋 · 对局中(L3 布局 A)。
 *
 * ⚠️ **这一屏是 2026-08-24 收口盘点时才发现漏取图的**,而且我第一次还把它写成了「没实现」——
 * 那是错的。它的实现**跟着屏 05 那一轮一起上了外壳**(同一个 `GamePage`,差一个 `engineMode` prop),
 * 稿子说的四处差别里三处早就在。漏的只是**这份四图**和 scope.md 里的记录。
 * 教训写在 scope.md §27:盘点要 grep**源码里这一屏的特征物**,不是 grep 文档。
 *
 * 稿子 `:1797-1860`。与自由对弈(屏 05)同骨架,差别四处:
 *
 *  ① **三颗会扣次数的星阵道具键**(领地 12 / 支招 5 / 变化图 0)——
 *    `GameControlPanel.tsx:228`。角标三态照实现:数字 = 还剩几次;`0` **用红底不灰掉**
 *    (去星阵 App 充了值马上又能用,灰掉等于说「这个功能没有」);`—` = 这一次没取到数,
 *    和 0 不是一回事。它们既不与动作区并排、也不与「坐标 / 手数」并排 ——
 *    **一个会花钱的按钮和一个纯显示开关长成一样,是这一屏最容易犯的错。**
 *  ② **没有胜率图表**(`evalAllowed = !engineMode && …`)—— 本地局那颗「图表」开关整个不存在。
 *  ③ **悔棋在星阵算招期间禁用**(`disableUndo={isRanked || !!platformPendingMove}`)——
 *    那一手最长要等 ~180 秒,后端本来就 409,灰在这儿比点了被拒好。
 *  ④ 顶上一条**平台条**(哪一家 / 连没连上 / 上一手多少秒)。
 *
 * 预期差异 —— **两处都是早就登记在案的,不是未对齐**
 * (`docs/superpowers/plans/2026-08-20-kiosk-go-shell-align.md` 屏 10 的「没做、已登记」那一节):
 *
 *  · **④ 那条平台条不画**,三个值一个都喂不了:「哪一家」是写死常量且页控条标题已经写了;
 *    **「连没连上」没有来源,而最近的候选会主动撒谎** —— WS `platform_status` 全仓
 *    **无任何 Python 处 emit**,REST `/platforms/status` 的 `connected` 是
 *    `golaxy/adapter.py` 的**登录闩**(置真 4 处全在 `connect()` 里、置假只有 `disconnect()`
 *    一处),平台宕机时恒真,和屏 18 `current_winrate` 写死 `0.5` 同形;
 *    **「上一手 4.2s」全链路没有这个字段**。
 *    掉线由 `engineErrorToast` 说 —— 星阵 genmove 跑在人类落子请求**里面**
 *    (`gateway.py:137/163`),没有不由用户触发的往返。
 *  · **稿子那个「棋谱」折叠块也不画**:`GameState.history` 里只有 `node_id/score/winrate`、
 *    **没有坐标**,而 `stones` 虽有 `moveNumber` 却**不含被提掉的子** —— 拿它拼出来的棋谱会缺手。
 *    ⇒ 等后端补一条着法序列。`.mvrows` 的 CSS 一直留着(屏 16/18 有真消费者),接口一到就能接。
 *    **这也是为什么 engineMode 下右栏中段空着约 148px**(实测:六块 308 + 5×12 = 368 / 516,
 *    `grows: 0`,动作区靠 `margin-top:auto` 贴底)。
 *  · 取图机器上**实体识别关着** ⇒ 页控条右端那个「重置识别」页级图标键不出现。
 *    **它在真盒子上是有的。**
 */

const COLS = 'ABCDEFGHJKLMNOPQRST';
const xy = (c: string): [number, number] => [COLS.indexOf(c[0]), Number(c.slice(1)) - 1];

// 稿子 `:1822` 那一局,逐子照搬 —— 参考图和实现图必须画同一个局面。
const BLACK = ['Q16', 'D4', 'C6', 'Q10', 'R14', 'F17', 'K4', 'C11', 'P3'];
const WHITE = ['D16', 'Q4', 'F3', 'R6', 'O17', 'D9', 'H3', 'R11', 'M17'];

const STATE = {
  game_id: 'fourup-10', board_size: [19, 19], komi: 7.5, handicap: 0, ruleset: 'chinese',
  game_type: 'free', count_min_moves: 100, current_node_id: 18, current_node_index: 18,
  history: Array.from({ length: 19 }, (_, i) => ({ node_id: i, winrate: 0.5, score: 0 })),
  player_to_move: 'W',
  stones: [
    ...BLACK.map((c, i) => ['B', xy(c), null, i * 2 + 1]),
    ...WHITE.map((c, i) => ['W', xy(c), null, i * 2 + 2]),
  ],
  last_move: xy('M17'), prisoner_count: { B: 0, W: 0 },
  analysis: null, commentary: '', is_root: false, is_pass: false, end_result: null,
  children: [], ghost_stones: [],
  // 星阵局两个座位都带 bare "human",引擎方靠 `platform_engine_color` 认(GamePage.tsx:63)。
  platform_engine_color: 'W',
  players_info: {
    B: { player_type: 'player:human', player_subtype: '', name: '访客（你）', calculated_rank: '', periods_used: 0, main_time_used: 0 },
    W: { player_type: 'player:human', player_subtype: '', name: '星皮猴', calculated_rank: '2段', periods_used: 0, main_time_used: 0 },
  },
  note: '',
  ui_state: { show_children: false, show_dots: false, show_hints: false, show_policy: false,
    show_ownership: false, show_move_numbers: true, show_coordinates: false, zen_mode: false },
};

test('四图:星阵围棋 · 对局中 ←→ sample-go/shots/10-platform-game.png', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
    // 这条路由外面套着 `PlayInputGuard` —— 选「屏幕」就不走那道守卫,
    // 否则取图机器(没摄像头、几何 404)会被换成标定台。
    localStorage.setItem('kiosk_play_on_board', 'false');
  });
  await stubShellAssets(page);
  await page.route('**/api/state**', (route) => route.fulfill({ json: { state: STATE } }));
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') {
      return route.fulfill({ json: { id: 1, username: '访客', rank: '5段', credits: 0 } });
    }
    // 稿子那一帧的三个角标:12 / 5 / **0**(第三个是红底那一格,不是灰掉)。
    if (path === '/api/v1/platforms/golaxy/engine/items') {
      return route.fulfill({ json: { area: 12, options: 5, variation: 0 } });
    }
    if (path === '/api/v1/vision/status') {
      return route.fulfill({ json: { enabled: false, camera_connected: false, pose_locked: false,
        sync_state: 'unbound', recognition_ready: false, led_connected: null, bound_session_id: null } });
    }
    if (path === '/api/v1/geometry/status') {
      return route.fulfill({ status: 404, json: { detail: 'geometry disabled' } });
    }
    return route.fulfill({ json: {} });
  });

  await page.goto('/kiosk/play/cross-platform/engine/game/fourup-10');
  // 等的是**三颗道具键真的画出来了** —— 它们是这一屏区别于屏 05 的那一块。
  await page.waitForSelector('.items button:nth-child(3)');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '10-platform-game.png'),
    outDir: OUT,
    slug: '10-platform-game',
    referenceCaption:
      '参考:sample-go/shots/10-platform-game.png · L3 布局 A · 与自由对弈同骨架，'
      + '右栏换成三个**会扣次数**的星阵道具键 · 没有胜率图表',
    implementationCaption:
      '实现:/kiosk/play/cross-platform/engine/game @1024×600 · 时钟冻 16:40 · 局面照搬稿子那一局 · '
      + '**三颗道具键的角标是真接口给的**(12 / 5 / 0)，`0` 用红底**不灰掉**——去星阵 App 充了值'
      + '马上又能用，灰掉等于说「这个功能没有」；`—` 是「这次没取到数」，和 0 不是一回事 · '
      + '**两处与稿子的差都是早就登记在案的,不是未对齐** · '
      + '**平台条不画**:「哪一家」是写死常量且标题已经写了；**「连没连上」没有来源，'
      + '而最近的候选会主动撒谎**——WS platform_status 全仓无 Python emit，REST 那个 connected 是'
      + 'golaxy/adapter.py 的**登录闩**(置真全在 connect() 里、置假只有 disconnect() 一处)，'
      + '平台宕机时恒真，和屏 18 写死 0.5 的 current_winrate 同形；「上一手 4.2s」全链路无字段。'
      + '掉线由 engineErrorToast 说——星阵 genmove 跑在人类落子请求**里面**，没有不由用户触发的往返 · '
      + '**棋谱折叠块不画**:history 只有 node_id/score/winrate 没坐标，stones 有 moveNumber 但'
      + '**不含被提掉的子**，拼出来的棋谱会缺手 ⇒ 等后端补着法序列。'
      + '这也是右栏中段空着约 148px 的原因(实测 308+60=368/516，grows:0) · '
      + '实体识别关着 ⇒ 页控条右端那个「重置识别」键不出现，**它在真盒子上是有的**',
  });
  console.log(`[fourup 10-platform-game] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
