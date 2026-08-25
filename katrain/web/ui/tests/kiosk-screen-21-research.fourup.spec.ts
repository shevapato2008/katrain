import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubShellAssets } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/21-research/1024x600');

/**
 * 屏 21 研究(L2 布局 A:盘 516 + 16 + 右栏 460)。
 *
 * 稿子那一帧:5 黑(Q16,D4,Q10,C14,R7)+ 4 白(D16,Q4,R14,F17),`data-last="R7"`,
 * 三个绿点 R11 / C7 / Q6,标题「研究 · 第 9 手」。这里逐子照搬。
 *
 * 预期差异,每条都是裁定:
 *
 *  ① **副标题跟着入口走,不是稿子写死的那一句。** 稿子的返回键是「← 棋谱」、副标写
 *    「来自复盘:自由对弈 · 今天 15:12」。可这一屏有**三个**入口(棋谱详情 / 复盘报告 /
 *    刚下完那局),回去的地方各不相同,而前两条的 URL 形状完全一样
 *    (都带 `?user_game_id=`)、反推不出来 ⇒ 由 `?from=` 说了算。这一帧取 `from=report`。
 *    (2026-08-25:原来那一帧取的是 `from=history`,而对局历史那一屏是 27 屏改造之前的东西、
 *     从 UI 上走不到,已随本轮删掉 ⇒ 入口从四个变三个。)
 *    **拿不到出处就整行不渲染** —— 不编。
 *
 *  ② **稿子那句 `.kiosk-opthint` 换掉了。** 原句「这四种互斥 —— 同一根手指点在盘上只能是
 *    其中一个意思,所以是分段不是开关」是讲给读稿人的设计理由,而规范给这一行的定义是
 *    **「写当前选中项」**;Fan 2026-08-22 也说过「不要写那么多解释文字,还都是小字,
 *    7 英寸屏看起来非常费劲」。腾出来的这一行拿去说**规则 / 贴目** ——
 *    那三个控件(规则 / 贴目 / 让子)这一版删了(三个入口都自带这些值),
 *    但**删控件不等于可以不说值**:用户得知道 AI 是按什么规则算的。
 *
 *  ③ **实现比稿子多一颗:页控条右端的「领地」。** 这是本轮**唯一**超出稿子的增加,
 *    已登记。理由:形势图对**手搭的局面**没有任何替代路径(屏 18/20 只覆盖真实对局),
 *    而它连一次请求都不多发 —— ownership 和候选着法在同一个 `quickAnalyze` 响应里。
 *    位置是规范 §11 给的那**一个**页级图标键槽。
 *
 *  ④ **`移动` / `手数` / `建议` 三颗不在了。** `移动` 是**坏的**不是「用得少」:
 *    选中态存在一个 `useRef` 里,ref 不触发重渲染 ⇒ 点第一下屏上零反馈、第二下那颗子瞬移。
 *    `手数` 在摆出来的局面上画的是「你点击的顺序」而不是棋理。
 *    `建议` 被**常亮的推荐点**取代 —— 那正是稿子画的(`data-ghost` 没有任何开关管它)。
 *
 *  ⑤ **表里的数按走子方视角,不按稿子那几个数。** 稿子这一帧自相矛盾:黑 5 子白 4 子
 *    ⇒ 第 9 手之后**轮到白走**,可折叠头写「黑 54.2%」而首行 R11 的胜率也是 54.2% ——
 *    若表是走子方视角,两个数不可能同时成立。实现里早有定论(KataGo 给的是黑方视角,
 *    上屏按走子方翻转),直播和复盘两屏都在用这一套。⇒ 这一帧显示的是**白方**的数。
 *
 *  ⑥ **「全局分析」按稿子降到第 5 颗等重,但补了一层确认。** 它是几分钟、期间盘面锁死的
 *    重操作,而上一版把它做成右栏底部钉住的大 CTA(占 60px,表要少 2 行)。
 *    代价信息(每手 500 次)进确认弹层 —— 比按钮副标题更早也更清楚。
 *    同一轮把倒置的轻重扳回来:**「清空」补确认**(上一版一点就擦掉整盘、毫无确认),
 *    **「停一手」去确认**(上一版这个上一手就能撤销的动作反倒弹框)。
 */

/** 稿子那一帧的九手。交替,最后一手 R7 是黑 ⇒ 轮白走。 */
const SGF = '(;GM[1]FF[4]SZ[19]PB[柯洁]PW[申真谞]KM[7.5]RU[chinese]'
  + ';B[qd];W[dd];B[dp];W[pp];B[pj];W[rf];B[cf];W[fc];B[rm])';

/** 稿子表里那 10 行。`scoreLead`/`winrate` 按**黑方视角**给(后端就是这么给的), */
/*  上屏时页面按走子方(这一帧是白)翻转 —— 见预期差异 ⑤。 */
const MOVE_INFOS = [
  { move: 'R11', visits: 610, winrate: 0.458, scoreLead: -1.8 },
  { move: 'C7', visits: 180, winrate: 0.484, scoreLead: -0.4 },
  { move: 'Q6', visits: 110, winrate: 0.509, scoreLead: 0.9 },
  { move: 'D10', visits: 60, winrate: 0.542, scoreLead: 2.4 },
  { move: 'S8', visits: 40, winrate: 0.570, scoreLead: 3.7 },
  { move: 'T4', visits: 30, winrate: 0.578, scoreLead: 4.1 },
  { move: 'B15', visits: 20, winrate: 0.602, scoreLead: 5.6 },
  { move: 'F16', visits: 20, winrate: 0.609, scoreLead: 6.0 },
  { move: 'K3', visits: 10, winrate: 0.635, scoreLead: 7.4 },
  { move: 'D17', visits: 10, winrate: 0.660, scoreLead: 8.8 },
];

test('四图:研究 ←→ sample-go/shots/21-research.png', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubShellAssets(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: '访客', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/v1/analysis/quick-analyze', (route) => route.fulfill({
    json: { turnInfos: [{ moveInfos: MOVE_INFOS, ownership: null }] },
  }));
  // 出处那一行要真数据 —— 这一帧走「复盘报告 → 去研究」那条入口。
  await page.route('**/api/v1/user-games/hist-1**', (route) => route.fulfill({
    json: {
      id: 'hist-1', user_id: 1, title: '自由对弈', player_black: '柯洁', player_white: '申真谞',
      black_rank: null, white_rank: null, result: null, board_size: 19, rules: 'chinese',
      komi: 7.5, move_count: 9, source: 'kiosk', category: 'ai', game_type: 'free',
      event: null, round_name: null, game_date: '2026-08-24T07:12:00Z',
      created_at: '2026-08-24T07:12:00Z', updated_at: null, sgf_content: SGF,
    },
  }));

  // **不带 `analyze=1`** —— 带了会直接跑去扫描态,而稿子这一帧画的是编辑态。
  await page.goto('/kiosk/research?user_game_id=hist-1&from=report');
  await page.waitForSelector('.aitab .best');
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '21-research.png'),
    outDir: OUT,
    slug: '21-research',
    referenceCaption:
      '参考:sample-go/shots/21-research.png · L2 布局 A(盘 516 + 16 + 右栏 460)· '
      + '编辑工具互斥所以用分段，不是开关 · 折叠块 253，AI 表体 221 只露得出表头 + 8 行(稿子给了 10 行，'
      + 'K3 那行被横切) —— 装不下是设计里就有的',
    implementationCaption:
      '实现:/kiosk/research?user_game_id=hist-1&from=report @1024×600 · 时钟冻 16:40 · '
      + '**副标题跟着入口走**:三个入口(棋谱详情/复盘报告/刚下完那局)回去的地方各不相同，'
      + '而前两条 URL 形状一样、反推不出来 ⇒ 由 `?from=` 说了算；拿不到出处就整行不渲染，不编 · '
      + '**提示行换成「当前工具 · 规则 · 贴目」**:规范给这一行的定义是「写当前选中项」，'
      + '稿子那句讲设计理由的话收进代码注释(Fan 2026-08-22:小字太费劲)；'
      + '规则/贴目/让子三个控件删了(三个入口都自带这些值)，但**删控件不等于可以不说值** · '
      + '**多一颗「领地」在页控条**(本轮唯一超出稿子的增加，已登记):形势图对手搭的局面没有替代路径，'
      + '而它连一次请求都不多发——ownership 和候选着法在同一个响应里 · '
      + '**少三颗**:`移动` 是坏的不是用得少(选中态存在 useRef 里，屏上零反馈、第二下瞬移)、'
      + '`手数` 在摆出来的局面上画的是点击顺序不是棋理、`建议` 被常亮的推荐点取代(那正是稿子画的) · '
      + '**表里是白方视角**:稿子那帧自相矛盾——黑 5 子白 4 子 ⇒ 轮白走，'
      + '可折叠头写「黑 54.2%」而首行胜率也是 54.2%，两者不可能同时成立 · '
      + '**「全局分析」降到第 5 颗等重但补了确认**(每手 500 次写进弹层，不写「大概几分钟」——'
      + '开跑前没有校准过的速率，那个数只能编)；同轮把倒置的轻重扳回来:清空补确认、停一手去确认',
  });
  console.log(`[fourup 21-research] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
