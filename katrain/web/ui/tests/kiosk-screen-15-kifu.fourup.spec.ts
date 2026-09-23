import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';
import { scopedKey, kioskMeJson } from './helpers/kioskIdentity';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/15-kifu/1024x600');

/**
 * 屏 15 棋谱(L1 布局 A,形态 1)。
 *
 * 造的数据逐条对着稿子那张图:三条「最近摆过」的名字、手数、时间。
 * 时钟冻在 16:40,所以第一条 15:40 落在「今天 15:40」上、第二条落「昨天」、第三条落「前天」。
 *
 * 稿子 2026-09-23 按 Fan 改判重画过(smartbox `feat/kiosk-go-kifu-list-design-2026-09-23`):
 * 名局列表一进来就摊开(搜索框 + 导入 SGF 一行、一页六局、翻页),没有直播那一组、
 * 也没有「棋谱详情 · 界面未接」那块进度说明。名局六行与「共 2,318 局」照稿子造。
 */
// 名局六行对着稿子那六局(棋手、赛事、轮次、日期、手数、结果)—— 差异图上剩下的才是实现与稿子真不一样的地方。
const game = (id: number, b: string, w: string, event: string, round: string, date: string,
  moves: number, result: string, rules = 'chinese') => ({
  id, player_black: b, player_white: w, black_rank: '九段', white_rank: '九段',
  event, round_name: round, result, move_count: moves, date_played: date,
  board_size: 19, handicap: 0, komi: 7.5, rules,
});
const ALBUMS = [
  game(1, '申真谞', '柯洁', '第 29 届三星杯', '半决赛', '2026-06-30', 241, 'B+R'),
  game(2, '朴廷桓', '丁浩', 'LG 杯', '决赛第二局', '2026-02-12', 186, 'W+R'),
  game(3, '一力辽', '芝野虎丸', '名人战', '第七局', '2025-11-06', 312, 'B+1.5', 'japanese'),
  game(4, '杨鼎新', '卞相壹', '春兰杯', '八强', '2025-10-18', 207, 'W+R'),
  game(5, '辜梓豪', '申旻埈', '梦百合杯', '四强', '2025-09-02', 268, 'B+0.5', 'korean'),
  game(6, '许家元', '李轩豪', '应氏杯', '十六强', '2025-07-21', 159, 'W+R'),
];

test('四图:棋谱 ←→ sample-go/shots/15-kifu.png', async ({ page }) => {
  await freezeClock(page);
  // 种子键带身份后缀 + `/me` 给同一个 uuid,缺一不可 —— 见 helpers/kioskIdentity.ts。
  // (少了它这一屏的「最近摆过」三行根本不出现,而这张四图的全部意义就是那三行。)
  await page.addInitScript((k: { recent: string; p1: string; p2: string; p3: string }) => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
    // 冻住的「现在」是 2026-08-20 16:40。三条最近摆过分别落在 今天 15:40 / 昨天 / 前天。
    const at = (iso: string) => new Date(iso).getTime();
    localStorage.setItem(k.recent, JSON.stringify([
      { id: 'kifu_1', name: '第 29 届三星杯 · 半决赛', savedAt: at('2026-08-20T15:40:00') },
      { id: 'kifu_2', name: '名人战 · 第七局', savedAt: at('2026-08-19T20:10:00') },
      { id: 'local_3', name: '本地导入 · game-0731', savedAt: at('2026-08-18T09:30:00') },
    ]));
    const prog = (n: number, total: number) => JSON.stringify({ k: n, frames: 0, updatedAt: 0, total });
    localStorage.setItem(k.p1, prog(47, 241));
    localStorage.setItem(k.p2, prog(198, 198));
    localStorage.setItem(k.p3, prog(12, 175));
  }, {
    recent: scopedKey('baipu:recent'),
    p1: scopedKey('baipu:progress:kifu_1'),
    p2: scopedKey('baipu:progress:kifu_2'),
    p3: scopedKey('baipu:progress:local_3'),
  });
  // 后端没起时 logo 会 502,取出来的图左上角是碎图标 —— 钉在仓里那份真字节上。
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({ json: kioskMeJson({ username: '访客' }) }));
  await page.route('**/api/v1/kifu/albums*', (route) => route.fulfill({
    json: { items: ALBUMS, total: 2318, page: 1, page_size: 6 },
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
      '参考:sample-go/shots/15-kifu.png(2026-09-23 改稿)· L1 布局 A(镜像栏 296 + 16 + 右栏 680)· '
      + '名局列表一进来就摊开 · 没有直播',
    implementationCaption:
      '实现:/kiosk/kifu @1024×600 · 时钟冻 16:40 · 名局六行与最近摆过三条是照稿子造的 fixture · '
      + '名局列表一进来就摊开:搜索框常驻、「导入 SGF」贴在右边(Fan 2026-09-23)· '
      + '没有直播:Fan 2026-09-22 裁定 kiosk 端删掉直播,只在 galaxy 保留 · '
      + '组标题右端写真数据(共 N 局)· '
      + 'Dock 七项(2026-08-25 起补了「成长」,围棋独有)',
  });
  console.log(`[fourup 15-kifu] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
