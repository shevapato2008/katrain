import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/18-live/1024x600');

/**
 * 屏 18 直播 · 观战(L2 布局 A:盘 516 + 16 + 右栏 460)。
 *
 * 这一屏**没有动作区** —— 你在看别人下棋,一个能改这盘棋的按钮都不该有。
 *
 * 预期差异,每条都是裁定:
 *  ① **两张玩家卡右端那个「28:14 / 剩余」不画**:三个源客户端返回的字典、`LiveMatchDB`、
 *    `types/live.ts` 三层都没有时间字段。盒子问不出来的数不上屏(同屏 24 环、屏 06 段位列)。
 *  ② 页控条副标的手数是**真的当前手**,而屏上那个胜率只在盒内 KataGo 真算过时才出现 ——
 *    `current_winrate` 在源头被写死(`pandanet.py:125` 无条件 `0.5`,`xingzhen.py:191` 取不到退回
 *    `0.5`),「真的 50%」和「没有这个数」在数据里是同一个值,所以它一个字都不上屏。
 *  ③ 实现比稿子**少三块**:进度条 `PlaybackBar`、胜率曲线 `TrendChart`、AI 推荐列表 `AiAnalysis`。
 *    右栏六块正好摆满 516,能再塞的上限是 101px,而那三块分别要 ~48 / 128 / 214。
 *    能力一件没丢:任意跳手→点着法表(本仓 `.mvrows .mv[role=button]` 早就写好)、
 *    跳到最新→「跟到最新」、手数→折叠头右端、点推荐看后续→**点盘上那个标记**(屏 20 判过的同一条)。
 *  ④ 「跟到最新」做成**按下态**,稿子那一帧把它画成暗的、而视图正停在最新手 —— 自相矛盾。
 */

const MOVES = [
  'Q16', 'D16', 'D4', 'Q4', 'Q10', 'R14', 'C14', 'F17', 'R7', 'Q7', 'E17', 'D10', 'C7', 'H17',
];

const MATCH = {
  id: 'm1', source: 'xingzhen', tournament: '第 29 届三星杯', round_name: '八强',
  date: '2026-08-24', player_black: '申真谞', player_white: '柯洁',
  black_rank: '九段', white_rank: '九段', status: 'live', result: null,
  move_count: MOVES.length, current_winrate: 0.5, current_score: 0.0,
  last_updated: '2026-08-24T08:40:00Z', board_size: 19, komi: 7.5, rules: 'chinese',
  sgf: null, moves: MOVES,
};

test('四图:直播 · 观战 ←→ sample-go/shots/18-live.png', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: '访客', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/v1/live/matches/m1**', (route) => route.fulfill({ json: MATCH }));
  // 盒内 KataGo 对当前这一手算出来了 —— 于是折叠头右端才会出现胜率。
  await page.route('**/api/v1/live/matches/m1/analysis**', (route) => route.fulfill({
    json: {
      analysis: {
        [MOVES.length]: {
          move_number: MOVES.length, winrate: 0.532, score_lead: 1.8,
          top_moves: [
            { move: 'C7', visits: 812, winrate: 0.54, score_lead: 2.1, prior: 0.3, pv: ['C7', 'D7'] },
            { move: 'H17', visits: 402, winrate: 0.51, score_lead: 1.2, prior: 0.2, pv: ['H17'] },
          ],
          ownership: null,
        },
      },
    },
  }));

  await page.goto('/kiosk/live/m1');
  await page.waitForSelector('[data-testid="live-toggles"] button');
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '18-live.png'),
    outDir: OUT,
    slug: '18-live',
    referenceCaption:
      '参考:sample-go/shots/18-live.png · L2 布局 A(盘 516 + 16 + 右栏 460)· '
      + '没有动作区(看别人下棋，不该有能改棋的按钮)· 试下动的是复制出来的盘',
    implementationCaption:
      '实现:/kiosk/live/m1 @1024×600 · 时钟冻 16:40 · '
      + '**两张卡右端那个「28:14 / 剩余」不画**:三个源客户端、数据库、类型三层都没有时间字段 · '
      + '**胜率只认盒内 KataGo 算出来的那个**(并进折叠头右端「第 14 手 · 黑 53.2%」，算不出来时'
      + '后半截整个不出现)——`current_winrate` 在源头被写死 0.5，「真的 50%」和「没有这个数」同值 · '
      + '**比稿子少三块**:进度条 / 胜率曲线 / AI 推荐列表。右栏六块正好摆满 516，'
      + '能再塞的上限 101px，那三块分别要 ~48 / 128 / 214；'
      + '而且那条曲线现实现给没算过的手一律补 50%，本仓已把「不许画贴中线的平线冒充均势」写成规则 · '
      + '**能力一件没丢**:任意跳手→点着法表、跳到最新→「跟到最新」、手数→折叠头右端、'
      + '点推荐看后续→点盘上那个标记(屏 20 判过的同一条) · '
      + '「跟到最新」做成**按下态**:稿子那帧把它画成暗的、而视图正停在最新手，自相矛盾',
  });
  console.log(`[fourup 18-live] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
