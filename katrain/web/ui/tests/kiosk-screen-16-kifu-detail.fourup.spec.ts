import { test } from '@playwright/test';
import { freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

/**
 * 屏 16 棋谱详情(L2 布局 A)。
 *
 * 造的谱**逐手照着稿子那张图**的前七手:
 *   1 Q16 D16 / 2 D4 Q4 / 3 Q10 R14 / 4 C14 F17 / 5 R7 Q7 / 6 E17 D10 / 7 C7
 * 走到第 13 手(= C7),和稿子上「第 13 / 241 手」对上。
 * 接口收的是 canonical 坐标(row=0 在**上**),所以 Q16 = (row 3, col 15)。
 *
 * ⚠️ 三处预期差异:
 *  ① 稿子题头右上那枚 `界面未接` 蓝标 —— 说给读稿人听的,而且接上了就不成立。
 *  ② 稿子第三个动作键「送去复盘」**没有**:`POST /api/v1/reports/` 收 `user_game_id`,
 *    服务端拿它去 `UserGame` 表里查这一局是不是你下的,名局棋谱没有这一行;
 *    galaxy 的棋谱库也只有「在研究中打开」一个出口。画一个按下去必然报错的键更坏。
 *  ③ 题头补了段位(`black_rank` / `white_rank` 是库里真有的列)。
 *  另外这一屏总手数写的是**这份 fixture 真有的手数**,不是稿子那个 241 ——
 *  造一份 241 手的假谱只为了让角标好看,那就是拿假数据充门面。
 */
const COORDS: [string, number, number][] = [
  ['Q16', 3, 15], ['D16', 3, 3],
  ['D4', 15, 3], ['Q4', 15, 15],
  ['Q10', 9, 15], ['R14', 5, 16],
  ['C14', 5, 2], ['F17', 2, 5],
  ['R7', 12, 16], ['Q7', 12, 15],
  ['E17', 2, 4], ['D10', 9, 3],
  ['C7', 12, 2],
];

const STEPS = COORDS.map(([, row, col], i) => ({
  kind: 'move', move_index: i, property: i % 2 === 0 ? 'B' : 'W',
  row, col, color: i % 2 === 0 ? 'B' : 'W', removed: [], board_hash: '',
}));

const ALBUM = {
  id: 7,
  player_black: '申真谞', player_white: '柯洁',
  black_rank: '九段', white_rank: '九段',
  event: '第 29 届三星杯', round_name: '半决赛',
  result: 'B+R', move_count: STEPS.length,
  date_played: '2026-06-30', board_size: 19, handicap: 0,
  komi: 7.5, rules: 'chinese', place: null, source: null,
  sgf_content: '(;FF[4]GM[1]SZ[19];B[pd])',
};

test('四图:棋谱详情 ←→ sample-go/shots/16-kifu-detail.png', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
  });
  // 后端没起时 logo 会 502,取出来的图左上角是碎图标 —— 钉在仓里那份真字节上。
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: '访客', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/v1/kifu/albums/*', (route) => route.fulfill({ json: ALBUM }));
  await page.route('**/api/v1/baipu/load', (route) => route.fulfill({
    json: { board_size: 19, steps: STEPS, meta: {} },
  }));
  await page.goto('/kiosk/kifu/7/replay');
  await page.waitForSelector('[data-testid="kifu-detail-actions"] button');
  // 稿子停在第 13 手(C7),这里走到最后一手 —— 正好也是第 13 手。
  await page.getByRole('button', { name: '上一手', exact: true }).click();
  await page.getByRole('button', { name: '跳到最后', exact: true }).click();
  await page.waitForSelector('.kifu-replay-move-grid button[aria-pressed="true"]');
  await page.waitForLoadState('networkidle');

  await page.screenshot({ path: '/tmp/kiosk-16-replay.png' });
});
