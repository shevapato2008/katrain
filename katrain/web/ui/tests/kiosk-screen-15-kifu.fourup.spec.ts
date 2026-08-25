import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/15-kifu/1024x600');

/**
 * 屏 15 棋谱(L1 布局 A,形态 1)。
 *
 * 造的数据逐条对着稿子那张图:三条「最近摆过」的名字、手数、时间,和两场直播。
 * 时钟冻在 16:40,所以第一条 15:40 落在「今天 15:40」上、第二条落「昨天」、第三条落「前天」。
 *
 * ⚠️ **两处稿子上有而实现里没有的**,差异图上会红一片,都是预期:
 *  ① 稿子第五块「棋谱详情 · 后端已有 · 界面未接」—— 那是**说给读稿人听的**进度说明
 *    (块里印着 `PlaceholderPage` 和 `galaxy/pages/KifuLibraryPage.tsx` 两个文件名),
 *    而且它说的事本轮已经不成立:详情屏接上了,就是下一张对照台那一屏。
 */
const ALBUMS = Array.from({ length: 6 }, (_, i) => ({
  id: i + 1,
  player_black: '柯洁', player_white: '申真谞',
  black_rank: '九段', white_rank: '九段',
  event: '第 29 届三星杯', round_name: '半决赛',
  result: 'B+R', move_count: 241,
  date_played: '2026-06-30', board_size: 19, handicap: 0,
  komi: 7.5, rules: 'chinese',
}));

const MATCHES = [
  {
    id: 'm1', source: 'xingzhen', tournament: '第 29 届三星杯', round_name: '八强',
    date: '2026-08-20T06:00:00Z', player_black: '柯洁', player_white: '申真谞',
    black_rank: '九段', white_rank: '九段', status: 'live', result: null, move_count: 118,
    current_winrate: 0.52, current_score: 1.2, last_updated: '',
    board_size: 19, komi: 7.5, rules: 'chinese',
  },
  {
    id: 'm2', source: 'yike', tournament: '名人战挑战赛', round_name: '第三局',
    date: '2026-08-20T06:00:00Z', player_black: '芈昱廷', player_white: '杨鼎新',
    black_rank: '九段', white_rank: '九段', status: 'scheduled', result: null, move_count: 0,
    current_winrate: 0.5, current_score: 0, last_updated: '',
    board_size: 19, komi: 7.5, rules: 'chinese',
  },
];

test('四图:棋谱 ←→ sample-go/shots/15-kifu.png', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
    // 冻住的「现在」是 2026-08-20 16:40。三条最近摆过分别落在 今天 15:40 / 昨天 / 前天。
    const at = (iso: string) => new Date(iso).getTime();
    localStorage.setItem('baipu:recent', JSON.stringify([
      { id: 'kifu_1', name: '第 29 届三星杯 · 半决赛', savedAt: at('2026-08-20T15:40:00') },
      { id: 'kifu_2', name: '名人战 · 第七局', savedAt: at('2026-08-19T20:10:00') },
      { id: 'local_3', name: '本地导入 · game-0731', savedAt: at('2026-08-18T09:30:00') },
    ]));
    const prog = (k: number, total: number) => JSON.stringify({ k, frames: 0, updatedAt: 0, total });
    localStorage.setItem('baipu:progress:kifu_1', prog(47, 241));
    localStorage.setItem('baipu:progress:kifu_2', prog(198, 198));
    localStorage.setItem('baipu:progress:local_3', prog(12, 175));
  });
  // 后端没起时 logo 会 502,取出来的图左上角是碎图标 —— 钉在仓里那份真字节上。
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: '访客', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/v1/kifu/albums*', (route) => route.fulfill({
    json: { items: ALBUMS, total: 1234, page: 1, page_size: 6 },
  }));
  await page.route('**/live/matches*', (route) => route.fulfill({
    json: { matches: MATCHES, live_count: 1, total: 2 },
  }));
  await page.goto('/kiosk/kifu');
  await page.waitForSelector('[data-testid="kifu-recent-rows"] .kiosk-row:nth-child(3)');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '15-kifu.png'),
    outDir: OUT,
    slug: '15-kifu',
    referenceCaption:
      '参考:sample-go/shots/15-kifu.png · L1 布局 A(镜像栏 296 + 16 + 右栏 680)· '
      + '「棋谱 / 摆谱 / 直播」三项收成的那一项 · 稿子第五块「棋谱详情 · 界面未接」是写给读稿人的进度说明',
    implementationCaption:
      '实现:/kiosk/kifu @1024×600 · 时钟冻 16:40 · 最近摆过三条和两场直播是 fixture · '
      + '**没搬**稿子第五块「棋谱详情 · 界面未接」:那是说给读稿人听的,而且详情屏本轮已接上(见屏 16 对照台) · '
      + '组标题右端写真数据(共 1,234 局 / 来源按这批真的来自哪几家算),不是稿子那两句解释 · '
      + '「搜棋谱」是开关不是跳转 —— 收起时和稿子一样,按下去在这一组里展开搜索框和结果行 · '
      + 'Dock 七项(2026-08-25 起补了「成长」,围棋独有)',
  });
  console.log(`[fourup 15-kifu] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
