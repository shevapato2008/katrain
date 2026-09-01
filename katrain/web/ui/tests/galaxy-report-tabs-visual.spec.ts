import { expect, test, type Page } from '@playwright/test';

/**
 * Galaxy 复盘详情页右栏四个统计 tab 的取图 spec。
 *
 * 这一页此前**没有任何 e2e**（tests/ 下带 report 的 spec 全是 kiosk 的），
 * 所以「妙手 / 失误 / 发挥水准 / AI一致率」改完不会红 ≠ 改对了 —— 这个 spec 存在
 * 就是为了让它们能被真浏览器量一次、并出四图对比里的实现图。
 *
 * 数据全部走 route mock：棋谱是**互不相邻**的 100 手（每隔一路一子），保证不会有
 * 提子/自杀，棋盘怎么解析都不会炸。评价档位和候选表是按手号定死的，跑多少次都一样。
 *
 * 承重结构那一段的**变异记录**（两条分支都跑过）：
 *   把 ReportDetailPage 的 `<Box data-testid="report-trend-region" sx={{ flex: 'none' }}>`
 *   改成 `flex: 1, minHeight: 0` —— 也就是它自己注释里警告的「中段里再套一个中段」——
 *   本 spec 当场报红：能滚的祖先从 1 个变 0 个，右栏内容整段够不到。还原即绿。
 *   （反例：只在 TrendChart **内部**加一个 overflow:auto 的盒子不会红，因为断言走的是
 *   祖先链不是后代 —— 要防后代方向得另写一条。）
 *
 * tab 条可达性那一段的**变异记录**：把 Tabs 上的 `variant="scrollable" scrollButtons="auto"`
 *   去掉（= MUI 默认 standard），本 spec 当场报红 —— 五个 tab 内容宽 500px、右栏 349px，
 *   溢出被 overflow-x:hidden 切掉且滚动按钮 0 个，第 5 个 tab 用户够不到。加回即绿。
 */

const OUT = process.env.REPORT_SHOT_DIR ?? 'test-results/report-tabs';

const translationFixture: Record<string, string> = {
  'analysis:report': '复盘',
  Home: '首页',
  'btn:Play': '对局',
  Research: '研究',
  Live: '直播',
  Settings: '设置',
  'live:trend_chart': '走势',
  'live:brilliant': '妙手',
  'live:mistakes': '失误',
  'live:move_number': '第',
  'live:points': '目',
  'live:points_unit': '目',
  'live:black': '黑',
  'live:white': '白',
  'live:black_winrate': '黑棋胜率',
  'live:black_lead': '黑棋领先',
  'grade:performance': '发挥水准',
  'grade:match_rate': 'AI吻合度',
  'grade:brilliant': '妙手',
  'grade:best': '最佳',
  'grade:very_good': '很好',
  'grade:playable': '尚可',
  'grade:inaccuracy': '小亏',
  'grade:mistake': '失误',
  'grade:blunder': '恶手',
  'grade:brilliance': '妙度',
  'grade:unrated': '未评级',
  'grade:phase_all': '全盘',
  'grade:phase_opening': '布局',
  'grade:phase_midgame': '中盘',
  'grade:phase_endgame': '官子',
  'grade:player_both': '双方',
  'grade:player_B': '黑方',
  'grade:player_W': '白方',
  'grade:histogram_footer': '黑 {b} 手 / 白 {w} 手已评级',
  'grade:unrated_count': '{n} 手未评级',
  'grade:truncated_note': '另有 {n} 处未列出，可切换阶段或棋手查看',
  'grade:view_stats': '统计',
  'grade:view_distribution': '分布',
  'grade:filter_phase': '阶段',
  'grade:filter_player': '棋手',
  'grade:filter_match_view': '视图',
  'grade:count_note': '本阶段共 {n} 处',
  'grade:def_points_lt': '目损 < {n} 目',
  'grade:def_blunder': '目损 ≥ {n} 目',
  'grade:match_top1': '走中 AI 一选',
  'grade:match_top3': '走进 AI 前三',
  'grade:match_offbook': '不在 AI 前十选',
  'grade:match_footer': '分母是能与 AI 比对的手数：黑 {b} 手 / 白 {w} 手',
  'grade:match_undecidable': '{n} 手无法比对',
  'grade:match_caveat': '一致率高低取决于局面难度，不能单独当作棋力或作弊的证据。',
  'grade:match_no_data': '本阶段还没有可比对的着手',
  'grade:no_rated_moves': '本阶段没有已评级的着手',
};

const MOVES = 100;
const LETTERS = 'abcdefghijklmnopqrs';

/** 第 n 手（1 基）的坐标。每隔一路落一子 ⇒ 任意两子都不相邻 ⇒ 不会有提子。 */
const sgfPoint = (n: number) => {
  const i = n - 1;
  return `${LETTERS[(i % 10) * 2]}${LETTERS[Math.floor(i / 10) * 2]}`;
};
const gtpPoint = (n: number) => {
  const i = n - 1;
  const col = 'ABCDEFGHJKLMNOPQRST'[(i % 10) * 2];
  return `${col}${19 - Math.floor(i / 10) * 2}`;
};

const sgf = () => {
  let out = `(;GM[1]FF[4]SZ[19]KM[6.5]RU[chinese]PB[王星昊]PW[杨鼎新]RE[W+T]`;
  for (let n = 1; n <= MOVES; n++) out += `;${n % 2 === 1 ? 'B' : 'W'}[${sgfPoint(n)}]`;
  return `${out})`;
};

/** 手号 → 档位。定死的分布，覆盖七档 + 未评级，两方都有。 */
const gradeOf = (n: number): string => {
  if (n % 47 === 0) return 'brilliant';
  if (n % 29 === 0) return 'blunder';
  if (n % 17 === 0) return 'mistake';
  if (n % 11 === 0) return 'inaccuracy';
  if (n % 7 === 0) return 'playable';
  if (n % 3 === 0) return 'very_good';
  if (n % 13 === 0) return 'unrated';
  return 'best';
};

const buildMoves = () =>
  Array.from({ length: MOVES + 1 }, (_, n) => {
    const grade = n === 0 ? null : gradeOf(n);
    const isTop = grade === 'best' || grade === 'brilliant';
    // 下一手的实战点在本行候选表里的名次：0 = 一选，1/2 = 前三，-1 = 不在表里。
    const nextRank = grade === null ? 0 : n % 9 === 4 ? -1 : n % 5 === 2 ? 2 : isTop ? 0 : 1;
    const candidates: string[] = [];
    for (let k = 0; k < 6; k++) candidates.push(gtpPoint(((n * 7 + k * 13) % MOVES) + 1));
    if (nextRank >= 0) candidates[nextRank] = gtpPoint(n + 1);
    else candidates.forEach((_, k) => {
      if (candidates[k] === gtpPoint(n + 1)) candidates[k] = gtpPoint(((n + 41) % MOVES) + 1);
    });
    return {
      id: n + 1,
      task_id: 1,
      move_number: n,
      status: 'done',
      winrate: 0.5 + 0.28 * Math.sin(n / 9),
      score_lead: 8 * Math.sin(n / 7),
      visits: 500,
      top_moves: candidates.map((move, k) => ({
        move,
        visits: 500 - k * 60,
        winrate: 0.5,
        score_lead: 1 - k * 0.4,
        prior: 0.4 - k * 0.05,
        pv: [move],
        psv: 500 - k * 60,
        // 人类倾向三种状态都要出现在同一屏：正常值 / 不足 1 人 / 引擎没给（null）。
        human_prior: k === 1 ? 0.002 : k === 2 ? null : 0.31 - k * 0.06,
        human_profile: k === 2 ? null : 'rank_5d',
      })),
      ownership: null,
      actual_move: n === 0 ? null : gtpPoint(n),
      actual_player: n === 0 ? null : n % 2 === 1 ? 'B' : 'W',
      delta_score: 0,
      delta_winrate: 0,
      grade,
      points_lost:
        grade === 'blunder' ? 9.4 : grade === 'mistake' ? 4.6 : grade === 'inaccuracy' ? 2.1 : 0.2,
      points_lost_source: 'in_search',
      is_top_move: grade === null || grade === 'unrated' ? null : isTop,
      top_prior: 0.02 + (n % 7) * 0.01,
      brilliance: grade === 'brilliant' ? ((n / 47) | 0) + 3 : null,
      root_visits: 500,
    };
  });

const prepare = async (page: Page) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({ json: { id: 1, username: '棋手', rank: '5段', credits: 0 } }),
  );
  await page.route('**/api/translations?lang=cn', (route) =>
    route.fulfill({ json: { lang: 'cn', translations: translationFixture } }),
  );
  await page.route('**/api/v1/live/translations**', (route) =>
    route.fulfill({ json: { players: {}, tournaments: {}, rounds: {}, rules: {} } }),
  );
  await page.route('**/api/v1/reports/1/moves', (route) => route.fulfill({ json: buildMoves() }));
  await page.route('**/api/v1/reports/1', (route) =>
    route.fulfill({
      json: {
        id: 1,
        user_game_id: 'game-1',
        status: 'completed',
        report_type: 'deep',
        total_moves: MOVES,
        analyzed_moves: MOVES,
        requested_visits: 500,
        started_at: '2026-01-29T10:00:00Z',
        completed_at: '2026-01-29T10:12:00Z',
      },
    }),
  );
  await page.route('**/api/v1/user-games/game-1', (route) =>
    route.fulfill({
      json: {
        id: 'game-1',
        user_id: 1,
        title: '2026世界围棋团体赛热身赛',
        player_black: '王星昊',
        player_white: '杨鼎新',
        black_rank: '9段',
        white_rank: '9段',
        result: 'W+T',
        board_size: 19,
        rules: 'chinese',
        komi: 6.5,
        move_count: MOVES,
        source: 'upload',
        category: 'pro',
        game_type: null,
        event: null,
        round_name: null,
        game_date: '2026-01-29',
        created_at: '2026-01-29T09:00:00Z',
        updated_at: '2026-01-29T10:12:00Z',
        sgf_content: sgf(),
      },
    }),
  );
};

const TABS = [
  { index: 1, name: '妙手', file: '01-brilliant' },
  { index: 2, name: '失误', file: '02-mistakes' },
  { index: 3, name: '发挥水准', file: '03-performance' },
  { index: 4, name: 'AI吻合度', file: '04-match-rate' },
] as const;

test('Galaxy 复盘右栏四个统计 tab', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await prepare(page);
  await page.goto('/galaxy/report/1');

  const tabs = page.locator('.MuiTabs-root').first();
  await expect(tabs).toBeVisible({ timeout: 15000 });
  // 第 5 个 tab 必须在**末尾**：tab 是位置索引，插中间会静默改掉后面所有 tab === N。
  await expect(tabs.getByRole('tab')).toHaveCount(5);
  await expect(tabs.getByRole('tab').nth(4)).toHaveText(/AI吻合度/);

  const panel = tabs.locator('..');

  // AI 推荐表：四列（着点 / 推荐度 / 领先 / 胜率），不横向溢出、表头不被截断。
  //
  // 2026-09-01：这里原本断言的是**五列**，第五列是「N段选择率」（人类倾向）。
  // Fan 当日裁定那一列先不上（「规则不统一，没有很好的产品价值」），
  // `ReportDetailPage` 不再传 `showHumanTendency`。所以断言的对象不是坏了、是**没有了** ——
  // 按「闸也会过期」的口径改写成当下的事实，而不是把这条测试 skip 掉：
  // skip 掉等于这张表从此没人量。`AiAnalysis` 里五列那条分支仍有单测覆盖。
  const aiTable = await page.evaluate(() => {
    const header = document.querySelector('[data-testid="ai-table-header"]') as HTMLElement | null;
    if (!header) return null;
    const cells = Array.from(header.children) as HTMLElement[];
    return {
      trackCount: getComputedStyle(header).gridTemplateColumns.split(' ').length,
      overflowX: header.scrollWidth - header.clientWidth,
      humanCells: header.querySelectorAll('[data-col="human"]').length,
      clippedCells: cells.filter((c) => c.scrollWidth > c.clientWidth).length,
    };
  });
  expect(aiTable).not.toBeNull();
  expect(aiTable!.trackCount).toBe(4);
  expect(aiTable!.overflowX).toBeLessThanOrEqual(0);
  // 那一列必须**一个格子都不渲染**，不是渲染了再用 display:none 藏起来。
  expect(aiTable!.humanCells).toBe(0);
  expect(aiTable!.clippedCells).toBe(0);

  const aiRegion = page.locator('[data-testid="report-trend-region"]').locator('xpath=preceding-sibling::div[1]');
  if (await aiRegion.count()) await aiRegion.screenshot({ path: `${OUT}/00-ai-table.png` });

  for (const tab of TABS) {
    await tabs.getByRole('tab').nth(tab.index).click();
    await expect(panel).toBeVisible();
    await page.waitForTimeout(150);
    await panel.screenshot({ path: `${OUT}/${tab.file}.png` });
  }

  // 承重结构：**真浏览器量出来的那条链**，不是注释上写的那条。
  // 实测（1440x900，失误 tab）：TrendChart 自己的 height:100% 没有确定高度的父级可依，
  // 塌成内容高 1116px，它内部那层 overflow:auto 于是**从未生效**（scrollHeight == clientHeight）；
  // 真正在滚的是右栏外壳（h 684 / scrollHeight 1787 / overflow-y:auto）。
  // 加了棒棒糖图只是往这条已经在滚的壳里塞高度，链没有变 —— 但这句话只有量过才算数。
  await tabs.getByRole('tab').nth(2).click();
  await page.waitForTimeout(80);
  const chain = await panel.evaluate((el) => {
    const out: { h: number; sh: number; ch: number; canScroll: boolean }[] = [];
    let n: HTMLElement | null = el as HTMLElement;
    while (n && n !== document.documentElement) {
      const cs = getComputedStyle(n);
      out.push({
        h: Math.round(n.getBoundingClientRect().height),
        sh: n.scrollHeight,
        ch: n.clientHeight,
        canScroll: n.scrollHeight > n.clientHeight && /auto|scroll/.test(cs.overflowY),
      });
      n = n.parentElement;
    }
    return out;
  });
  // 关系式先写死：链上**必须有且只有一处**真正能滚的祖先，且它比自己的内容矮。
  const scrollers = chain.filter((c) => c.canScroll);
  expect(scrollers).toHaveLength(1);
  expect(scrollers[0].sh).toBeGreaterThan(scrollers[0].ch);

  // 而且要真的滚得动（能不能滚永远归真浏览器，不归 jsdom）。
  const moved = await panel.evaluate((el) => {
    let n = el.parentElement as HTMLElement | null;
    while (n && !(n.scrollHeight > n.clientHeight && /auto|scroll/.test(getComputedStyle(n).overflowY))) {
      n = n.parentElement;
    }
    if (!n) return -1;
    n.scrollTop = 9999;
    return n.scrollTop;
  });
  expect(moved).toBeGreaterThan(0);

  // 页面本身既不纵滚也不横滚。
  const docOverflow = await page.evaluate(() => ({
    y: document.documentElement.scrollHeight - document.documentElement.clientHeight,
    x: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  }));
  expect(docOverflow.y).toBeLessThanOrEqual(0);
  expect(docOverflow.x).toBeLessThanOrEqual(0);

  // 内容闸：改完之后这几屏必须还有东西，空屏截图不算过关。
  //
  // 2026-09-01：发挥水准那条原来写的是 `panel.getByText('最佳')`，现在会命中 4 个元素
  // （两个柱子的悬停 `<title>`、横轴标签、定义带里的那一条）。**是断言变歧义了，不是
  // 功能坏了** —— 那一屏比以前信息更多。所以把判据钉到具体位置，而不是给它加
  // `.first()` 蒙混过去：`.first()` 会让「轴标签没了但 tooltip 还在」这种缺陷照样绿。
  await tabs.getByRole('tab').nth(3).click();
  const histogram = page.getByTestId('trend-histogram-chart');
  await expect(histogram).toBeVisible();
  // 七档的横轴标签一个都不能少 —— 少一档就是少一根柱子。
  for (const tier of ['妙手', '最佳', '很好', '尚可', '小亏', '失误', '恶手']) {
    await expect(histogram.getByText(tier, { exact: true })).toBeVisible();
  }
  // 定义带常驻（Fan 要求「定义剪短写在图表下方」）。阈值来自 GRADE_LADDER_POINTS。
  await expect(panel.getByText('目损 < 0.5 目')).toBeVisible();

  await tabs.getByRole('tab').nth(4).click();
  await expect(panel.getByText('走中 AI 一选')).toBeVisible();
  await expect(panel.getByText('走进 AI 前三')).toBeVisible();
  await expect(panel.getByText(/分母是能与 AI 比对的手数/)).toBeVisible();
  // 分布视图是这次新增的，切过去必须真的换图。
  await panel.getByRole('radio', { name: '分布' }).click();
  await expect(page.getByTestId('trend-match-timeline')).toBeVisible();
  // 免责声明在两个视图里都得在 —— 这条是硬性的。
  await expect(panel.getByText(/不能单独当作棋力或作弊的证据/)).toBeVisible();
});

/**
 * AI 推荐表在**窄右栏**下的承重。加第五列之前这张表是四等分 fr，怎么挤都不会溢出；
 * 加了带 minmax() 下限的第五列之后，下限之和是一条**硬地板**，右栏比它窄就会溢出，
 * 而裁切祖先 [data-testid=board-rail-scroll] 在 ≥900px 是 overflowX:hidden ——
 * 溢出的部分不是「可以滚过去看」，是**直接看不到**。
 *
 * 右栏宽度分档在 BoardPageShell.tsx:73/79：900-1199px 给 320px，≥1200px 才给 360px。
 * 原来的 spec 只跑 1440，正好落在不会红的那一档。
 */
for (const width of [1024, 1180, 1440]) {
  test(`AI 推荐表在 ${width}px 下不溢出右栏`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await prepare(page);
    await page.goto('/galaxy/report/1');
    await expect(page.locator('.MuiTabs-root').first()).toBeVisible({ timeout: 15000 });

    const m = await page.evaluate(() => {
      const header = document.querySelector('[data-testid="ai-table-header"]') as HTMLElement | null;
      if (!header) return null;
      const last = header.children[header.children.length - 1] as HTMLElement;
      const rail = document.querySelector('[data-testid="board-rail-scroll"]') as HTMLElement | null;
      return {
        tracks: getComputedStyle(header).gridTemplateColumns.split(' ').length,
        hasHumanCol: !!header.querySelector('[data-col="human"]'),
        clientW: header.clientWidth,
        scrollW: header.scrollWidth,
        lastRight: Math.round(last.getBoundingClientRect().right),
        railRight: rail ? Math.round(rail.getBoundingClientRect().right) : null,
      };
    });
    expect(m).not.toBeNull();
    // eslint-disable-next-line no-console
    console.log('RAIL', width, JSON.stringify(m));
    // 无论宽窄，都不许溢出、不许越过右栏右边缘（祖先是 overflowX:hidden，溢出=看不到）。
    expect(m!.scrollW).toBeLessThanOrEqual(m!.clientW);
    if (m!.railRight !== null) expect(m!.lastRight).toBeLessThanOrEqual(m!.railRight + 1);
    // 四列，**每一档都一样**。2026-09-01 撤掉人类倾向列之后不再有「宽栏五列」那一支；
    // 这条循环留着的价值是：栏宽档位一改（正在做的加宽），四列会不会溢出仍然有人量。
    expect(m!.tracks).toBe(4);
    expect(m!.hasHumanCol).toBe(false);
  });
}

/**
 * 图表宽度跟随右栏 —— 规范 §2.5「已知未解」那一条的验收。
 *
 * **改造前的事实**：四张矢量图都写死 `viewBox="0 0 420 H"` + `xMidYMid meet`。
 * 于是无论右栏多宽，viewBox 宽恒为 420：右栏窄于 420 时整张图被等比缩小
 * （连轴标文字一起缩），宽于 420 时图**不再变大**、多出来的宽度变成图框内死区。
 *
 * **改造后要成立的关系式**（写关系不写像素，像素只记录）：
 *   1. `viewBox.width === round(svg 的 CSS 宽)` —— 缩放比恒为 1，字号才等于写下的数值；
 *   2. 两个不同视口下 svg 的 CSS 宽**必须不同** —— 证明它真的跟着右栏走。
 *      这一条就是对旧行为的变异：旧代码在任何视口下 viewBox 都是 420，第 1 条必红。
 *
 * jsdom 对这两条都无权作证（没有布局引擎，且 `test/setup.ts` 里的 ResizeObserver
 * 是空实现，单测里量到的永远是兜底值 420）。所以判据只能在这里。
 */
const CHART_TABS = [
  { index: 0, name: '走势', testid: 'trend-dual-chart' },
  { index: 2, name: '失误', testid: 'trend-lollipop-chart' },
];

for (const chart of CHART_TABS) {
  test(`${chart.name}图的 viewBox 宽跟随右栏实宽`, async ({ page }) => {
    const seen: Record<number, { css: number; viewBox: number; fontPx: number | null }> = {};

    for (const width of [1024, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await prepare(page);
      await page.goto('/galaxy/report/1');
      await expect(page.locator('.MuiTabs-root').first()).toBeVisible({ timeout: 15000 });
      await page.locator('.MuiTabs-root').first().getByRole('tab').nth(chart.index).click();
      await page.waitForTimeout(200);

      // 选择器必须钉在图表自己的 testid 上。第一版写的是
      // `[data-testid="report-trend-region"] svg`，命中的是 tab 条上那个 MUI 滚动按钮
      // 图标（23px 宽）—— 而且关系式 1 在那个错元素上**照样通过**（23 vs 24 差 1px）。
      // 抓住它的是下面关系式 2。判据要挂在稳定标识上，不能挂在「区域里第一个 svg」这种结构巧合上。
      const m = await page.evaluate((testid: string) => {
        const svg = document.querySelector(`[data-testid="${testid}"]`) as SVGSVGElement | null;
        if (!svg) return null;
        const text = svg.querySelector('text');
        return {
          css: Math.round(svg.getBoundingClientRect().width),
          viewBox: Math.round(svg.viewBox.baseVal.width),
          // 屏上真实字号 = 标称字号 × 缩放比。缩放比为 1 时两者相等。
          fontPx: text
            ? Math.round(parseFloat(getComputedStyle(text).fontSize) * 10) / 10
            : null,
        };
      }, chart.testid);
      expect(m, `${chart.name} 图在 ${width} 下没找到 svg`).not.toBeNull();
      seen[width] = m!;
      // eslint-disable-next-line no-console
      console.log('CHARTW', chart.name, width, JSON.stringify(m));

      // 关系式 1：缩放比恒为 1。容许 1px 的取整误差。
      expect(Math.abs(m!.viewBox - m!.css)).toBeLessThanOrEqual(1);
    }

    // 关系式 2：右栏在这两档分别是 320 / 360，图必须跟着变宽。
    // 旧代码（写死 420）在这里必红 —— 这一条就是它的变异守卫。
    expect(seen[1440].css).toBeGreaterThan(seen[1024].css);
    expect(seen[1440].viewBox).toBeGreaterThan(seen[1024].viewBox);
  });
}
