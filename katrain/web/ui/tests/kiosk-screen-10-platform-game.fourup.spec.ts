import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

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
 *    和 0 不是一回事。它们与四颗动作键组成连续的等尺寸点击区；「坐标 / 手数」
 *    单独组成滑动开关区。
 *  ② **没有胜率图表**(`evalAllowed = !engineMode && …`)—— 本地局那颗「图表」开关整个不存在。
 *  ③ **动作区有悔棋 / 停一手 / 数子 / 认输**。机器人隧道没有悔棋调用，因此按平台
 *    原界面保留灰色；后三颗可用。数子只查看当前形势，不结束对局。
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
 *  · **「棋谱」折叠块 —— 2026-08-25 补上了,右栏中段那 148px 的空没了。**
 *    卡住它的是数据:`history` 只有 `node_id/score/winrate`(**没有坐标**),而 `stones` 虽有
 *    `moveNumber` 却**不含被提掉的子** —— 拿它拼出来的棋谱会缺手。
 *    ⇒ 后端在 `interface.py` 那个**本来就在遍历主线 GameNode** 的循环里加了两个键
 *    (`move` = `Move.gtp()`,`player`),坐标就在 `node.move` 上,顺手写进去。
 *    断言在 `tests/platforms/test_state_history_moves.py` —— 其中一条专门造了个提子,
 *    证明那一手在 `history` 里还在、在 `stones` 里已经没了(**这条就是这次改动的全部理由**)。
 *    前端在 `GameControlPanel` 里叠行:**按后端给的 `player` 分黑白,不按手数奇偶**
 *    (让子局第一手就是白,连着几手同色也真会出现)。
 *    「装不下时滚的是它自己 / 一手没下时空态说话」在 `kiosk-screen-05-game.spec.ts` 里
 *    用真浏览器量 —— 被 `overflow` 裁掉的行在截图上根本不存在,四图对比无从证起。
 *  · **悔棋:2026-09-16 按最新视觉确认恢复为「在、但灰」。** 星阵在线房间虽有 backmove，
 *    机器人使用的无状态 genmove 隧道没有悔棋协议；因此按钮整局保持禁用，且不随 pending 状态重排。
 *  · **停一手 / 数子:2026-09-16 补齐机器人对局。** 已提交的真实校准结果确认
 *    PASS=-1、RESIGN=-3；数子复用已有免费 judge 隧道，右端说明它不会结束对局。
 *  · **两张玩家卡:稿子那一帧自相矛盾。** `.turn`(青玉描边)给了写着「已落子」的访客卡,
 *    而正在算的是星皮猴 —— `go-screens.css` 那行注释白纸黑字「`.turn` 是**轮到谁**」。
 *    实现把手数计只挂在轮到的那张卡上也是对的:kiosk 不计时、`main_time_used` 不累加,
 *    唯一为真的量「第几手」是**局面的**量不是某一方的量。「最长 180s」是隧道超时不是时限,**不上屏**。
 *  · **两个显示开关的状态两边不同,而稿子那一帧自己也不自洽。** 稿子画的是「坐标关 / 手数开」,
 *    可它盘上的子**一个手数都没写**;实现的默认是「坐标开 / 手数关」,盘上也没有手数 —— 自洽。
 *    这两个是**用户开关**,不是这一屏的属性,四图比的是默认态 ⇒ **不改**,登记在此。
 *  · 取图机器上**实体识别关着** ⇒ 页控条右端那个「重置识别」页级图标键不出现。
 *    **它在真盒子上是有的。**
 */

const COLS = 'ABCDEFGHJKLMNOPQRST';
const xy = (c: string): [number, number] => [COLS.indexOf(c[0]), Number(c.slice(1)) - 1];

/**
 * 稿子 `:1822` 那一局,逐子照搬 —— 参考图和实现图必须画同一个局面。
 *
 * 这里存的是**落子顺序**,不是两串「盘上有哪些子」:稿子的棋谱块画出了第 11–18 手
 * (`6 K4/H3`、`7 P3/R11`、`8 F17/O17`、`9 Q10/M17`),顺序是它自己写死的,和把黑白各自
 * 排成一列的那种写法对不上。⇒ **盘上的子和棋谱从同一个数组导出**,两者不可能互相说谎。
 * 前十手稿子里滚出去了(它默认停在当前手),照常规布局补,不影响那两张图要比的东西。
 */
const ORDER: [string, 'B' | 'W'][] = [
  ['Q16', 'B'], ['D16', 'W'], ['D4', 'B'], ['Q4', 'W'], ['C6', 'B'],
  ['F3', 'W'], ['R14', 'B'], ['R6', 'W'], ['C11', 'B'], ['D9', 'W'],
  // ↓ 稿子棋谱块上看得见的那四行
  ['K4', 'B'], ['H3', 'W'], ['P3', 'B'], ['R11', 'W'],
  ['F17', 'B'], ['O17', 'W'], ['Q10', 'B'], ['M17', 'W'],
];

const STATE = {
  game_id: 'fourup-10', board_size: [19, 19], komi: 7.5, handicap: 0, ruleset: 'chinese',
  game_type: 'free', count_min_moves: 100, current_node_id: 18, current_node_index: 18,
  // `history[0]` 是根节点 —— 没有着法。第 n 手落在 `history[n]`,和 `current_node_index` 同一套下标。
  history: [
    { node_id: 0, winrate: 0.5, score: 0, move: null, player: null },
    ...ORDER.map(([move, player], i) => ({ node_id: i + 1, winrate: 0.5, score: 0, move, player })),
  ],
  player_to_move: 'W',
  stones: ORDER.map(([c, p], i) => [p, xy(c), null, i + 1]),
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
  await stubBackendStatics(page);
  // 实时连接**接上但不推**。不接的话 `useGameSession` 那条掉线红条会盖在题头上,
  // 而稿子那一帧当然没有它 —— 屏 05 同一处 2026-08-25 已经判过一次(`7b048605`)。
  // 判据同 `stubBackendStatics`:**一张随「另一个进程在不在」而变的实现图,不是这一屏的实现图。**
  await page.routeWebSocket('**/ws/**', () => { /* 连上就行,不推任何东西 */ });
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

  // 局面由上面的 `/api/state` stub 提供；旧 WS pending 桩只影响已撤掉的悔棋键。

  await page.goto('/kiosk/play/cross-platform/engine/game/fourup-10');
  // 等的是**三颗道具键真的画出来了** —— 它们是这一屏区别于屏 05 的那一块。
  await page.waitForSelector('.items button:nth-child(3)');
  /** 动作区从第一帧固定显示悔棋 / 停一手 / 数子 / 认输。 */
  await page.waitForFunction(() =>
    document.querySelectorAll('[data-testid="game-actions"] button').length === 4);
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
      + '**棋谱折叠块补上了**(2026-08-25)，右栏中段那 148px 的空没了。'
      + '卡住它的是数据:history 只有 node_id/score/winrate **没坐标**，stones 有 moveNumber 但'
      + '**不含被提掉的子**，拼出来的谱会缺手 ⇒ 后端在**本来就在遍历主线的那个循环**里'
      + '加了 move(GTP)/player 两个键。叠行**按 player 不按手数奇偶**(让子局第一手就是白) · '
      + '**「AI 思考中…」药丸居中在棋盘上**(2026-08-25 改)——上一版 left:50% 相对的是 992 宽的'
      + '定位祖先，落在视口 512 而盘右沿是 532，药丸横跨盘/栏接缝压住第一张玩家卡 · '
      + '**悔棋按平台原界面保留为灰色**:在线房间有 backmove 接口，但机器人走无状态 genmove 隧道，'
      + '当前没有可调用的机器人悔棋协议 · '
      + '**七颗点击按钮连续摆放且统一为 110×52**；坐标 / 手数单独放在上方的滑动开关区 · '
      + '**停一手 / 数子已恢复**:PASS 使用已校准的 -1 哨兵；数子调用免费的 judge 隧道，'
      + '右端写「数子只查看当前形势，不结束对局」 · '
      + '**两张玩家卡稿子自相矛盾**:.turn 给了写着「已落子」的访客卡而正在算的是星皮猴 · '
      + '实体识别关着 ⇒ 页控条右端那个「重置识别」键不出现，**它在真盒子上是有的**',
  });
  console.log(`[fourup 10-platform-game] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
