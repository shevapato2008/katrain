import { expect, test, type Page } from '@playwright/test';
import { resolve } from 'node:path';
import { freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';
import { kioskMeJson, scopedKey } from './helpers/kioskIdentity';

/**
 * 直播列表屏(稿外屏,`/kiosk/live`)与棋谱屏入口行的**承重实测**。jsdom 没有布局引擎,
 * 对「列表能不能滚、会不会被裁、页控条会不会被顶走」无权作证 —— 这里在真浏览器里量。
 *
 * 数据先造到会溢出:50 场直播 + 30 场已结束 + 20 场赛程(一屏 52+8 的行摆不下 8 行)。
 * 数据是**输入**,可以造;下面每个断言的对象都是浏览器算出来的**结论**。
 * 每条造完输入先断言前置状态真的成立,造不出来当场红。
 *
 * 这些桩数据只活在这个 spec 里(`page.route` 拦截),不进产品代码;随 spec 一起存在。
 */
test.use({ viewport: KIOSK_VIEWPORT });

const OUT = resolve(process.cwd(), '../../../superpowers/tracks/kiosk-go-live/visual/live-list');

const match = (i: number, status: 'live' | 'finished') => ({
  id: `${status}-${i}`, source: i % 3 === 0 ? 'yike' : 'xingzhen',
  tournament: `第 ${i + 20} 届三星杯`, round_name: '半决赛',
  date: '2026-08-19T06:00:00Z', player_black: '申真谞', player_white: '柯洁',
  black_rank: '九段', white_rank: '九段', status,
  result: status === 'finished' ? 'W+2.5' : null,
  move_count: 100 + i * 3,                           // 到 247:三位数手数塞进 46px 的行首格
  current_winrate: 0.5, current_score: 0, last_updated: '2026-08-20T08:00:00Z',
  board_size: 19, komi: 7.5, rules: 'chinese',
});
const upcoming = (i: number) => ({
  id: `u${i}`, tournament: `第 ${i + 1} 届春兰杯`, round_name: '第 1 轮',
  scheduled_time: `2026-08-${String(21 + (i % 5)).padStart(2, '0')}T03:00:00Z`,
  player_black: i % 4 === 0 ? null : '朴廷桓', player_white: i % 4 === 0 ? null : '芈昱廷',
  source: 'foxwq', source_url: 'https://example.com/x',
});

const boot = async (page: Page) => {
  await freezeClock(page);                            // 2026-08-20 16:40
  await page.addInitScript(() => {
    localStorage.setItem('token', 'kiosk-live-list');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (r) => r.fulfill({ json: kioskMeJson({ username: '访客' }) }));
  await page.route('**/live/matches*', (r) => r.fulfill({
    json: {
      matches: [...Array(50)].map((_, i) => match(i, 'live')).concat([...Array(30)].map((_, i) => match(i, 'finished'))),
      total: 80, live_count: 50,
    },
  }));
  await page.route('**/live/upcoming*', (r) => r.fulfill({ json: { matches: [...Array(20)].map((_, i) => upcoming(i)) } }));
};

/** 该滚的是这一个:`KioskScrollZone` 形态 1 的 `.kiosk-side__scroll`,不是它的祖先。 */
const zoneOf = (page: Page) => page.locator('[data-testid="live-page"] .kiosk-side__scroll');

test('直播列表:列表自己滚、手指拨得动、滚到底不被裁、整页不溢出、切分段页控条不动且回到顶', async ({ page }) => {
  await boot(page);
  await page.goto('/kiosk/live');
  await expect(page.getByTestId('live-row')).toHaveCount(50);

  const zone = zoneOf(page);
  const m0 = await zone.evaluate((el) => ({ sh: el.scrollHeight, ch: el.clientHeight }));
  // token 定义在外壳根上不在 `:root` 上 ⇒ 从行自己的计算样式里读(继承下来的就是它生效的那个值)。
  const [rowH, rowHToken] = await page.getByTestId('live-row').first().evaluate((el) =>
    [el.getBoundingClientRect().height, parseFloat(getComputedStyle(el).getPropertyValue('--row-h'))]);
  console.log(`[live-list] zone sh=${m0.sh} ch=${m0.ch} rowH=${rowH} token=${rowHToken}`);

  // 前置:真的溢出了,而且溢出量与造进去的 50 行成比例(不是被压扁之后的「刚好多几像素」)。
  expect(m0.sh).toBeGreaterThan(m0.ch);
  expect(rowH).toBe(rowHToken);                                   // 行没被 flex 压扁
  expect(m0.sh).toBeGreaterThanOrEqual(50 * rowHToken);

  // 整页不滚、不横向溢出 —— 只有列表滚。
  const doc = await page.evaluate(() => ({
    sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,
    sh: document.documentElement.scrollHeight, ch: document.documentElement.clientHeight,
  }));
  expect(doc.sw).toBeLessThanOrEqual(doc.cw);
  expect(doc.sh).toBeLessThanOrEqual(doc.ch);

  // 行首格装得下三位数手数(46px 等宽格;「247 手」溢出就会压到标题上)。
  const leadOverflow = await page.locator('[data-testid="live-row"] .kiosk-row__lead').evaluateAll(
    (els) => els.filter((el) => el.scrollWidth > el.clientWidth).length);
  expect(leadOverflow).toBe(0);

  // 手指拨得动:真滚轮(Chromium 不认未受信任的合成 WheelEvent)。
  const box = (await zone.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.wheel(0, 600);
  await expect.poll(() => zone.evaluate((el) => el.scrollTop)).toBeGreaterThan(0);

  // 滚到底:scrollTop 读回的是「到底」那个数,最后一行完整落在滚动框里,滚动框完整落在 600 里。
  const end = await zone.evaluate((el) => {
    el.scrollTop = 1e6;
    const z = el.getBoundingClientRect();
    const rows = el.querySelectorAll('[data-testid="live-row"]');
    const last = rows[rows.length - 1].getBoundingClientRect();
    return { st: el.scrollTop, max: el.scrollHeight - el.clientHeight, zTop: z.top, zBottom: z.bottom, lastTop: last.top, lastBottom: last.bottom };
  });
  console.log(`[live-list] end ${JSON.stringify(end)}`);
  expect(end.st).toBeGreaterThanOrEqual(end.max - 1);
  expect(end.lastBottom).toBeLessThanOrEqual(end.zBottom + 0.5);
  expect(end.lastTop).toBeGreaterThanOrEqual(end.zTop - 0.5);
  expect(end.zBottom).toBeLessThanOrEqual(KIOSK_VIEWPORT.height);

  // 切分段:页控条原地不动,列表回到顶(同一个滚动节点,不归零就停在上一段滚到的位置)。
  const pb0 = (await page.getByTestId('live-list-pagebar').boundingBox())!;
  await page.getByRole('radio', { name: '已结束' }).click();
  await expect(page.getByTestId('live-row')).toHaveCount(30);
  await expect.poll(() => zone.evaluate((el) => el.scrollTop)).toBe(0);
  const pb1 = (await page.getByTestId('live-list-pagebar').boundingBox())!;
  expect(pb1.y).toBe(pb0.y);
  expect(pb1.height).toBe(pb0.height);

  await page.getByRole('radio', { name: '即将开始' }).click();
  await expect(page.getByTestId('upcoming-row')).toHaveCount(20);
  const pb2 = (await page.getByTestId('live-list-pagebar').boundingBox())!;
  expect(pb2.y).toBe(pb0.y);
  // 赛程行尾是时刻标签,行里任何一格都不许把行撑出横向溢出。
  const rowOverflow = await page.getByTestId('upcoming-row').evaluateAll(
    (els) => els.filter((el) => el.scrollWidth > el.clientWidth).length);
  expect(rowOverflow).toBe(0);
  const upZone = await zone.evaluate((el) => ({ sh: el.scrollHeight, ch: el.clientHeight }));
  expect(upZone.sh).toBeGreaterThan(upZone.ch);
});

test('棋谱屏:直播那一组末行入口滚得到、完整可见,点下去进 /kiosk/live', async ({ page }) => {
  await boot(page);
  // 「最近摆过」造三条,让棋谱屏的滚动区确实溢出(入口行在最底下,装得下的数据量不作数)。
  await page.addInitScript((k: { recent: string }) => {
    const at = (iso: string) => new Date(iso).getTime();
    localStorage.setItem(k.recent, JSON.stringify([
      { id: 'kifu_1', name: '第 29 届三星杯 · 半决赛', savedAt: at('2026-08-20T15:40:00') },
      { id: 'kifu_2', name: '名人战 · 第七局', savedAt: at('2026-08-19T20:10:00') },
      { id: 'local_3', name: '本地导入 · game-0731', savedAt: at('2026-08-18T09:30:00') },
    ]));
  }, { recent: scopedKey('baipu:recent') });
  await page.route('**/api/v1/kifu/albums*', (r) => r.fulfill({ json: { items: [], total: 0, page: 1, page_size: 6 } }));
  await page.goto('/kiosk/kifu');
  const more = page.getByTestId('kifu-live-more');
  await expect(more).toBeAttached();
  await expect(page.locator('[data-testid="kifu-live"] .kiosk-row')).toHaveCount(5);   // 4 场 + 入口

  const zone = page.locator('.kiosk-side__scroll').first();
  const pre = await zone.evaluate((el) => ({ sh: el.scrollHeight, ch: el.clientHeight }));
  expect(pre.sh).toBeGreaterThan(pre.ch);                          // 前置:确实溢出

  const end = await zone.evaluate((el) => {
    el.scrollTop = 1e6;
    const z = el.getBoundingClientRect();
    const m = el.querySelector('[data-testid="kifu-live-more"]')!.getBoundingClientRect();
    return { zTop: z.top, zBottom: z.bottom, mTop: m.top, mBottom: m.bottom };
  });
  console.log(`[kifu-live-more] ${JSON.stringify(end)}`);
  expect(end.mTop).toBeGreaterThanOrEqual(end.zTop - 0.5);
  expect(end.mBottom).toBeLessThanOrEqual(end.zBottom + 0.5);

  await page.screenshot({ path: resolve(OUT, 'kifu-bottom--implementation.png') });
  await more.click();
  await expect(page).toHaveURL(/\/kiosk\/live$/);
  await expect(page.getByTestId('live-list-pagebar')).toBeVisible();
});

test('取实现图:直播中 / 已结束 / 即将开始 三段各一帧', async ({ page }) => {
  await boot(page);
  await page.goto('/kiosk/live');
  await expect(page.getByTestId('live-row')).toHaveCount(50);
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: resolve(OUT, 'live-list-live--implementation.png') });
  await page.getByRole('radio', { name: '已结束' }).click();
  await expect(page.getByTestId('live-row')).toHaveCount(30);
  await page.screenshot({ path: resolve(OUT, 'live-list-finished--implementation.png') });
  await page.getByRole('radio', { name: '即将开始' }).click();
  await expect(page.getByTestId('upcoming-row')).toHaveCount(20);
  await page.screenshot({ path: resolve(OUT, 'live-list-upcoming--implementation.png') });
});
