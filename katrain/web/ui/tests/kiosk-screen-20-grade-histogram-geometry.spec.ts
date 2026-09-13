import { expect, test, type Page } from '@playwright/test';
import { freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });

/**
 * 屏 20「发挥水准」直方图的**承重结构**闸。
 *
 * 2026-09-13 板上实测到的缺陷：14 根柱子全在、数字全对、**高度全是 0** —— 图是空的。
 * 根因是柱子的百分比高度挂在 `.hb` 上，而 `.hb` 的高度是内容撑出来的（只有那个 `<u>`
 * 标签），百分比对着 auto 高度的父元素解析成 auto ⇒ `<b>` 没有内容 ⇒ 恒 0。
 *
 * **这条闸只能建在真浏览器上。** jsdom 没有布局引擎：缺陷在位时，
 * `src/kiosk/__tests__` 下与屏 20 相关的单测**一条都没红**，因为它们能看见的只有
 * style 属性里那串 `height: 5.88%`，而那串字符串在坏掉的版本里同样存在。
 * 判据一句：把这条断言原样搬进真浏览器，还有可能失败吗？—— 能，所以它该在这里。
 *
 * 断言写成**关系式**（柱高之比 ≈ 手数之比、最高柱填满轨道），具体像素只记录不作判据。
 *
 * ⚠️ **塌陷类要在最空状态下量。** 内容一多，柱子自己就把 `.hb` 撑起来了，
 * 缺陷会被掩住 —— 所以下面第二个用例只喂**一手**。
 *
 * 变异记录（两条都真跑过）：
 *   ① `go-screens.css` 把 `.hbars { align-items: stretch }` 改回 `flex-end`
 *      → 两个用例同时红（所有柱高变 0）。还原即绿。
 *   ② 把 `MoveGradePanel` 里的 `<span className="hbt">` 去掉、`<b>` 直接挂回 `.hb`
 *      → 同样两个用例全红。还原即绿。
 */

const SGF = '(;FF[4]GM[1]SZ[19]'
  + ';B[pd];W[dp];B[pp];W[dd];B[cn];W[fq];B[cj];W[qf];B[pj]'
  + ';W[qn];B[ce];W[ef];B[qc];W[pn];B[eq];W[hq];B[ic])';

const GAME = {
  id: 'g1', user_id: 1, title: null, player_black: '访客', player_white: 'KataGo',
  black_rank: null, white_rank: '6 级', result: 'W+R', board_size: 19, rules: 'chinese',
  komi: 7.5, move_count: 17, source: 'play_ai', category: 'game', game_type: 'free',
  event: null, round_name: null, game_date: '2026-08-20',
  created_at: '2026-08-20T15:12:00.000Z', updated_at: null, sgf_content: SGF,
};

function row(n: number, grade: string | null) {
  const player = n % 2 === 1 ? 'B' : 'W';
  return {
    id: n, task_id: 41, move_number: n, status: 'success',
    winrate: 0.5, score_lead: 0, visits: 2000, root_visits: 2000,
    top_moves: [{ move: 'R11', visits: 1800, winrate: 0.6, score_lead: 3, prior: 0.7, pv: [], psv: 1 }],
    ownership: null, actual_move: 'C3', actual_player: player,
    delta_score: -0.3, delta_winrate: -0.01, grade,
  };
}

async function mount(page: Page, moves: ReturnType<typeof row>[]) {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'geom');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (r) => r.fulfill({
    json: { id: 1, username: '访客', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/v1/geometry/status', (r) => r.fulfill({
    json: {
      phase: 'disabled', session_calibrated: false, last_error: null,
      capabilities: { camera_ready: false, led_ready: false, geometry_ready: false, recognition_ready: false },
    },
  }));
  await page.route('**/api/v1/reports/41/moves', (r) => r.fulfill({ json: moves }));
  await page.route('**/api/v1/reports/41', (r) => r.fulfill({
    json: {
      id: 41, user_game_id: 'g1', status: 'completed', report_type: 'normal',
      total_moves: 17, analyzed_moves: 17, requested_visits: 500,
      started_at: '2026-08-23T01:00:00+08:00', completed_at: '2026-08-23T01:02:00+08:00',
    },
  }));
  await page.route('**/api/v1/user-games/g1', (r) => r.fulfill({ json: GAME }));

  await page.goto('/kiosk/report/41');
  await page.waitForSelector('[data-testid="ai-recommend-row"]');
  await page.click('[data-testid="report-detail-grade"] .kiosk-fold__head');
  await page.click('[data-testid="report-detail-grade"] .gseg5 button:nth-child(4)');  // 发挥水准
  await page.waitForSelector('[data-testid="grade-histogram"]');
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
}

/** 浏览器算出来的柱子几何 —— 断言只用这里回来的数。 */
function measure(page: Page) {
  return page.evaluate(() => {
    const groups = [...document.querySelectorAll('.hg')].map((g) => ({
      tier: (g.querySelector('em') as HTMLElement).innerText,
      // 顺序就是[黑, 白] —— 颜色要记下来：柱高按的是**各自颜色的占比**，
      // 不是原始手数，而黑白两边的分母可以不一样。
      bars: [...g.querySelectorAll('.hb')].map((hb, i) => ({
        color: i === 0 ? 'B' : 'W',
        n: Number((hb.querySelector('u') as HTMLElement).innerText),
        h: (hb.querySelector('b') as HTMLElement).getBoundingClientRect().height,
      })),
    }));
    const track = document.querySelector('.hbt') as HTMLElement;
    const body = document.querySelector('[data-testid="report-detail-grade"] .kiosk-fold__body') as HTMLElement;
    return {
      groups,
      trackH: track.getBoundingClientRect().height,
      overflow: body.scrollHeight - body.clientHeight,
    };
  });
}

test('柱高与手数成比例，最高的那根填满轨道', async ({ page }) => {
  // 17 手铺开到多个档位：最佳 6 / 很好 4 / 小亏 4 / 恶手 2 / 妙手 1。
  const grades = ['best', 'best', 'best', 'best', 'best', 'best',
    'very_good', 'very_good', 'very_good', 'very_good',
    'inaccuracy', 'inaccuracy', 'inaccuracy', 'inaccuracy',
    'blunder', 'blunder', 'brilliant'];
  await mount(page, grades.map((g, i) => row(i + 1, g)));
  const { groups, trackH, overflow } = await measure(page);

  const bars = groups.flatMap((g) => g.bars);
  expect(bars).toHaveLength(14);                       // 七档 × 黑白

  // ① 缺陷本身：有手数的柱子必须画得出来。
  const drawn = bars.filter((b) => b.n > 0);
  expect(drawn.length).toBeGreaterThan(0);
  for (const b of drawn) expect(b.h).toBeGreaterThan(0);

  // ② 没手数的柱子必须是 0 —— 否则「有」和「没有」长得一样。
  for (const b of bars.filter((b) => b.n === 0)) expect(b.h).toBe(0);

  // ③ 关系式：柱高 ∝ **该颜色自己的占比**（不是原始手数），最高的那根填满轨道。
  //   黑白分母不同（本用例里黑 9 手 / 白 8 手），所以跨颜色比手数是错的 ——
  //   第一版就这么写的，真浏览器当场报了 8/9=0.889。
  const totals = {
    B: bars.filter((b) => b.color === 'B').reduce((s, b) => s + b.n, 0),
    W: bars.filter((b) => b.color === 'W').reduce((s, b) => s + b.n, 0),
  };
  const rateOf = (b: { color: string; n: number }) => b.n / totals[b.color as 'B' | 'W'];
  const maxRate = Math.max(...drawn.map(rateOf));

  const tallest = drawn.reduce((a, b) => (b.h > a.h ? b : a));
  expect(tallest.h).toBeCloseTo(trackH, 0);
  expect(rateOf(tallest)).toBeCloseTo(maxRate, 5);     // 最高的就是占比最大的
  for (const b of drawn) {
    if (b.h <= 2.5) continue;                          // 地板段不参与比例判定
    expect(b.h / trackH).toBeCloseTo(rateOf(b) / maxRate, 1);
  }

  // ④ 画出来了也不能把折叠体撑破。
  expect(overflow).toBe(0);
});

test('最空状态：只有一手时那根柱子照样在，且不溢出', async ({ page }) => {
  // 塌陷类的判据在最空处 —— 内容一多，柱子自己会把父元素撑起来，缺陷就被掩住了。
  await mount(page, [row(1, 'best'), ...Array.from({ length: 16 }, (_, i) => row(i + 2, null))]);
  const { groups, trackH, overflow } = await measure(page);

  const bars = groups.flatMap((g) => g.bars);
  const drawn = bars.filter((b) => b.n > 0);
  expect(drawn).toHaveLength(1);                       // 就那一手
  expect(drawn[0].h).toBeCloseTo(trackH, 0);           // 它就是 100%，该填满轨道
  expect(trackH).toBeGreaterThan(10);                  // 轨道自己也不能塌
  expect(overflow).toBe(0);
});
