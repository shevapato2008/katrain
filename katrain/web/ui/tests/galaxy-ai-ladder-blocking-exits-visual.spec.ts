import { expect, test, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * 「未完成对局」面板的六态:取图 + **承重结构实测**。
 *
 * 两件事在这一个文件里,因为它们量的是同一帧而判据不同:
 *   · 取图那半交给人眼看构图对不对(四图关卡);
 *   · 承重那半交给浏览器算 —— jsdom 没有布局引擎,对布局事实无权作证,
 *     而这张卡的外层 `Paper` 带 `overflow: hidden`,右栏一旦比行高长就是**裁切**,
 *     不是滚动。组件测试里那些全绿也照样看不见这件事。
 *
 * 六态从「两扇门 × 各自的倒计时」换成了「一个开新局 × outbox 的四种同步状态」:
 * 接管窗口和放弃窗口连同它们的门槛一起删了(那两条在回答「另一台设备是不是真的死了」,
 * 而站在两台机器之间的是同一个人)。留下的这条倒计时数的不是权限,是 outbox 下一次
 * 真的会发请求的时刻。
 *
 * 量之前先把数据造到会溢出:最长的档位名 + 同步状态行 + 重试按钮 + 一条错误条,
 * 那是这块面板内容最多的一格。装得下的数据量下量出来的数字一概不算。
 */

const VIEWPORT = { width: 1440, height: 900 };
const OUT_DIR = resolve(
  process.cwd(),
  '../../../superpowers/tracks/golaxy-ai-ladder-parity/visual/blocking-exits/simplified-1440x900',
);

const readyStatus = (blocking: Record<string, unknown> | null) => ({
  view_state: 'ready',
  placement_state: {
    phase: 'placed',
    rung: { rung: 30, rank_name: '5段', certification_status: 'certified', availability: 'available', route: 'server' },
  },
  current_opponent: {
    rung: 30, rank_name: '5段', certification_status: 'certified', availability: 'available', route: 'server',
  },
  recent_ranked_results: ['win', 'loss', 'win', 'win', 'loss'],
  net_score: 1,
  pending_settlement: false,
  blocking_game: blocking,
});

const stubShell = async (page: Page) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: 'tester', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/translations?lang=cn', (route) => route.fulfill({
    json: {
      lang: 'cn',
      translations: {
        Home: '首页', 'btn:Play': '对局', Research: '研究', Tsumego: '死活题',
        'analysis:report': '复盘', Live: '直播', 'kifu:library': '棋谱库', Tutorials: '教程',
        Settings: '设置', Logout: '退出登录',
      },
    },
  }));
  await page.route('**/api/v1/live/translations?lang=cn', (route) => route.fulfill({
    json: { players: {}, tournaments: {}, rounds: {}, rules: {} },
  }));
  await page.route('**/assets/img/logo-white.png', (route) => route.fulfill({
    path: resolve(process.cwd(), '../../../katrain/img/logo-white.png'),
  }));
};

/** 右栏(挑战面板)的承重结论,全部由浏览器算,不由测试猜。 */
const measurePanel = (page: Page) => page.evaluate(() => {
  const heading = Array.from(document.querySelectorAll('p, span, div'))
    .find((node) => node.textContent?.trim() === '未完成对局');
  const panel = heading?.parentElement as HTMLElement | undefined;
  if (!panel) throw new Error('找不到「未完成对局」面板 —— 这一格根本没渲染出来');
  const card = panel.parentElement as HTMLElement;
  const style = getComputedStyle(panel);
  return {
    panelClientHeight: panel.clientHeight,
    panelScrollHeight: panel.scrollHeight,
    panelOverflowY: style.overflowY,
    cardClientHeight: card.clientHeight,
    cardScrollHeight: card.scrollHeight,
    cardOverflow: getComputedStyle(card).overflow,
    docScrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    // 动作区能不能**够得着**。下面那条 `panelScrollHeight <= panelClientHeight` 表达不了
    // 这件事 —— 见调用处的说明。
    costLineBottom: (() => {
      const cost = Array.from(panel.querySelectorAll('p'))
        .find((node) => /那一局(会记为本局负|不计入|没能开起来)/.test(node.textContent || ''));
      return cost ? Math.round(cost.getBoundingClientRect().bottom) : null;
    })(),
    innerHeight: window.innerHeight,
  };
});

const CASES: Array<{ slug: string; title: string; blocking: Record<string, unknown> }> = [
  {
    // 2026-08-11 新增。这条 spec 此前**停在契约改动之前** —— 六个案例全是 active/pending,
    // 而 `blocking_game.state` 从那天起多了 `reserved`,代价与另外两格不同(让掉不记成绩)。
    // 假响应的层级本来就是对的,所以真浏览器解得开、几何断言照旧全绿 —— 缺的不是正确性,
    // 是**这一格从没进过真浏览器**。象棋那边同类的缺口是层级过时,这里是取值缺席,
    // 两种都表现为「取图关卡全绿而屏上那一格没人看过」。
    slug: '00-reserved-never-started',
    title: '云端登记了、棋盘没能开起来 —— 让掉不记成绩',
    blocking: {
      game_id: 'g1', state: 'reserved', ownership: 'other_device',
      user_color: 'B', opponent_rank_name: '业余 3 段',
    },
  },
  {
    slug: '01-active-current-resumable',
    title: '局还在下,就在这台机器上',
    blocking: {
      game_id: 'g1', state: 'active', ownership: 'current_device', session_id: 'sess-1',
      user_color: 'B', opponent_rank_name: '业余 3 段',
    },
  },
  {
    slug: '02-active-current-interrupted',
    title: '这台机器重启过,局接不回来',
    blocking: {
      game_id: 'g1', state: 'active', ownership: 'current_device',
      user_color: 'B', opponent_rank_name: '业余 3 段',
    },
  },
  {
    slug: '03-active-other',
    title: '局在另一台设备上',
    blocking: {
      game_id: 'g1', state: 'active', ownership: 'other_device',
      user_color: 'B', opponent_rank_name: '业余 3 段',
    },
  },
  {
    slug: '04-pending-retrying',
    title: '成绩还在送:第 2 次重试,下一次 4:12 后',
    blocking: {
      game_id: 'g1', state: 'pending_settlement', ownership: 'current_device',
      user_color: 'B', opponent_rank_name: '业余 3 段',
      sync: {
        state: 'waiting', attempt: 2, max_attempts: 5, next_attempt_in_seconds: 252,
        last_http_status: null, last_error: 'timeout',
      },
    },
  },
  {
    slug: '05-pending-exhausted',
    title: '五次都没送到:自动重试用尽,仍可手动再试',
    blocking: {
      game_id: 'g1', state: 'pending_settlement', ownership: 'current_device',
      user_color: 'B', opponent_rank_name: '业余 3 段',
      sync: {
        state: 'exhausted', attempt: 5, max_attempts: 5, next_attempt_in_seconds: null,
        last_http_status: null, last_error: 'connection refused',
      },
    },
  },
  {
    slug: '06-pending-refused',
    title: '云端在事实上拒收:不给重试按钮',
    blocking: {
      game_id: 'g1', state: 'pending_settlement', ownership: 'current_device',
      user_color: 'B', opponent_rank_name: '业余 3 段',
      sync: {
        state: 'refused', attempt: 1, max_attempts: 5, next_attempt_in_seconds: null,
        last_http_status: 422, last_error: 'HTTP 422: rung mismatch',
      },
    },
  },
];

test.beforeAll(() => mkdirSync(OUT_DIR, { recursive: true }));

for (const testCase of CASES) {
  test(`未完成对局 ${testCase.slug} — ${testCase.title}`, async ({ page }) => {
    await page.setViewportSize(VIEWPORT);
    await stubShell(page);
    await page.route('**/api/v1/ai-ladder/status', (route) => route.fulfill({
      json: readyStatus(testCase.blocking),
    }));

    await page.goto('/galaxy/play/ai?mode=rated');
    await expect(page.getByText('未完成对局')).toBeVisible();

    const measured = await measurePanel(page);
    // 判据是**关系式**,不是像素。具体数字只记录。
    expect(measured.docScrollWidth, '页面横向出现滚动条').toBeLessThanOrEqual(measured.innerWidth);
    expect(
      measured.panelScrollHeight,
      `右栏内容 ${measured.panelScrollHeight}px 超过了它的可视高度 ${measured.panelClientHeight}px，`
      + `而外层 Paper 是 overflow:${measured.cardOverflow} —— 超出的部分是被**裁掉**的，不是能滚的`,
    ).toBeLessThanOrEqual(measured.panelClientHeight);
    expect(
      measured.cardScrollHeight,
      `卡片自身被裁切:内容 ${measured.cardScrollHeight}px > 可视 ${measured.cardClientHeight}px`,
    ).toBeLessThanOrEqual(measured.cardClientHeight);
    // ⚠️ 上面那两条**表达不了「够不够得着」**。实测:把 `opponent_rank_name` 造到 300 字,
    // 卡片涨到 2370px、代价行跑到 y=2483,而 `panelScrollHeight <= panelClientHeight` 和
    // `cardScrollHeight <= cardClientHeight` **照样通过** —— 因为卡片是跟着内容一起长的,
    // 没有谁被裁,只是整页变得很长。一条永远不会红的守卫比没有守卫更坏,下一个人会信它。
    //
    // 所以补这一条:realistic 数据下,**代价行必须落在首屏内**,不需要滚页才看得到。
    // (galaxy 外层是 `overflowY: auto`,失控档位名那一格退化成「页面很长但滚得到、按钮
    // 够得着」,严重度低于 kiosk 那处真消失 —— 那一格产品方定了行为不动,所以这里不为它
    // 设闸,只守 realistic 这一侧。)
    expect(measured.costLineBottom, '代价行没渲染出来').not.toBeNull();
    expect(
      measured.costLineBottom!,
      `代价行底边 ${measured.costLineBottom}px 掉出首屏 ${measured.innerHeight}px —— `
      + '「按下去会发生什么」要滚页才看得到,而用户按之前不一定会滚',
    ).toBeLessThanOrEqual(measured.innerHeight);
    // eslint-disable-next-line no-console
    console.log(`[measure] ${testCase.slug} ${JSON.stringify(measured)}`);

    await page.screenshot({ path: resolve(OUT_DIR, `${testCase.slug}.png`) });
    // 面板单独再取一张:四图对照要的是同一个东西的两个版本,整页截图里 90% 的像素
    // (侧边栏、段位区)两边都没有,拿它们去做叠加差异只会把真正的差别淹掉。
    const panel = page.locator('text=未完成对局').first().locator('..');
    await panel.screenshot({ path: resolve(OUT_DIR, `${testCase.slug}--panel.png`) });
  });
}

test('内容最多的那一格:同步状态行 + 重试 + 开新局 + 一条错误条 + 最长档位名', async ({ page }) => {
  // 承重那一关的正题。装得下的数据量下量出来的数字一概不算,所以这里把这块面板
  // 能同时出现的东西全堆上:同步状态行、「立即重试」、「开新局」+ 后果行、
  // 「刷新状态」、一条错误条,以及一个够长的档位名。
  await page.setViewportSize(VIEWPORT);
  await stubShell(page);
  await page.route('**/api/v1/ai-ladder/status', (route) => route.fulfill({
    json: readyStatus({
      game_id: 'g1', state: 'pending_settlement', ownership: 'other_device',
      user_color: 'W', opponent_rank_name: '智星职业九段·超一流·测试用超长档位名称',
      sync: {
        state: 'waiting', attempt: 4, max_attempts: 5, next_attempt_in_seconds: 3620,
        last_http_status: 503, last_error: 'HTTP 503: upstream unavailable',
      },
    }),
  }));
  await page.route('**/api/v1/ai-ladder/games/*/end', (route) => route.fulfill({
    status: 500, json: { detail: 'boom' },
  }));

  await page.goto('/galaxy/play/ai?mode=rated');
  await expect(page.getByText('未完成对局')).toBeVisible();

  const measured = await measurePanel(page);
  expect(measured.docScrollWidth).toBeLessThanOrEqual(measured.innerWidth);
  expect(
    measured.panelScrollHeight,
    `内容最多的那一格被裁掉了:${measured.panelScrollHeight}px > ${measured.panelClientHeight}px。`
    + '外层 Paper 是 overflow:hidden,所以超出的不是滚走而是**看不见**,'
    + '而看不见的正好是最下面那条「后果」——用户最需要读的一行。',
  ).toBeLessThanOrEqual(measured.panelClientHeight);
  // eslint-disable-next-line no-console
  console.log(`[measure] overflow-case ${JSON.stringify(measured)}`);

  await page.screenshot({ path: resolve(OUT_DIR, '07-overflow-worst-case.png') });
});
