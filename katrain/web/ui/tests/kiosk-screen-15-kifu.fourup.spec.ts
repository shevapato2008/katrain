import { test } from '@playwright/test';
import { freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';
import { kioskMeJson } from './helpers/kioskIdentity';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

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
  event, display_event: event, display_round_name: round, display_player_black: b, display_player_white: w, round_name: round, result, move_count: moves, date_played: date,
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

test('approved archive selection and final-board preview', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
  });
  // 后端没起时 logo 会 502,取出来的图左上角是碎图标 —— 钉在仓里那份真字节上。
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({ json: kioskMeJson({ username: '访客' }) }));
  await page.route('**/api/v1/kifu/albums*', (route) => route.fulfill({
    json: { items: ALBUMS, total: 2318, page: 1, page_size: 6 },
  }));
  await page.route('**/api/v1/kifu/albums/*', route => route.fulfill({ json: { ...ALBUMS[0], sgf_content: '(;SZ[19];B[dd];W[pp])' } }));
  await page.route('**/api/v1/baipu/load', route => route.fulfill({ json: { board_size: 19, steps: [{ kind: 'move', row: 3, col: 3, color: 'B', removed: [] }, { kind: 'move', row: 15, col: 15, color: 'W', removed: [] }], meta: {} } }));
  await page.goto('/kiosk/kifu');
  await page.waitForSelector('.kifu-record.is-selected');
  await page.waitForFunction(() => !(Array.from(document.querySelectorAll('button')).find(button => button.textContent === '查看棋谱') as HTMLButtonElement | undefined)?.disabled);
  await page.screenshot({ path: '/tmp/kiosk-15-reviewed.png' });
  await page.waitForLoadState('networkidle');

});
