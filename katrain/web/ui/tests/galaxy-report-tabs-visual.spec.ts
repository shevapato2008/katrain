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

  // AI 推荐表：第五列「N段选择率」。这一段量的是**真浏览器算出来的布局结论**：
  // 五列必须都装得下、表头不能被省略号截断、整行不能横向溢出。
  // 纯 fr 权重下这个表头会被压到 41px 然后截断（量过），所以列宽用的是 minmax()。
  const aiTable = await page.evaluate(() => {
    const header = Array.from(document.querySelectorAll('div')).find(
      (d) => getComputedStyle(d).display === 'grid'
        && getComputedStyle(d).gridTemplateColumns.split(' ').length === 5
        && d.textContent?.includes('选择率'),
    ) as HTMLElement | undefined;
    if (!header) return null;
    const cells = Array.from(header.children) as HTMLElement[];
    return {
      trackCount: getComputedStyle(header).gridTemplateColumns.split(' ').length,
      overflowX: header.scrollWidth - header.clientWidth,
      humanHeaderClipped: cells[2].scrollWidth > cells[2].clientWidth,
      humanHeaderText: cells[2].textContent,
    };
  });
  expect(aiTable).not.toBeNull();
  expect(aiTable!.trackCount).toBe(5);
  expect(aiTable!.overflowX).toBeLessThanOrEqual(0);
  expect(aiTable!.humanHeaderClipped).toBe(false);
  expect(aiTable!.humanHeaderText).toContain('选择率');

  // 三种状态必须都能出现在同一屏：正常值 / 不足 1 人 / 没有数据。
  // 「没有数据」显示成「—」而不是 0 —— 0 在中文里读起来像「绝对没人下」。
  await expect(page.getByText('31人')).toBeVisible();
  await expect(page.getByText('<1人')).toBeVisible();

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

  // 内容闸：改完之后这四屏必须还有东西，空屏截图不算过关。
  await tabs.getByRole('tab').nth(3).click();
  await expect(panel.getByText('最佳')).toBeVisible();
  await tabs.getByRole('tab').nth(4).click();
  await expect(panel.getByText('走中 AI 一选')).toBeVisible();
  await expect(panel.getByText('走进 AI 前三')).toBeVisible();
  await expect(panel.getByText(/分母是能与 AI 比对的手数/)).toBeVisible();
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
        humanColShown: Array.from(header.querySelectorAll('[data-col="human"]')).some(
          (el) => getComputedStyle(el as HTMLElement).display !== 'none',
        ),
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
    // 窄栏（右栏 320px）必须已经退成四列并收掉人类列；宽栏才显示五列。
    if (width < 1200) {
      expect(m!.tracks).toBe(4);
      expect(m!.humanColShown).toBe(false);
    } else {
      expect(m!.tracks).toBe(5);
      expect(m!.humanColShown).toBe(true);
    }
  });
}
