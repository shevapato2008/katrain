import { expect, test, type Locator, type Page, type Route } from '@playwright/test';
import { resolve } from 'node:path';

import { parsePo } from './helpers/po';

const VIEWPORT = { width: 1024, height: 600 };
const SGF = '(;FF[4]GM[1]SZ[19]RU[Chinese]KM[7.5]PB[Alpha]BR[3D]PW[Beta]WR[4D]RE[B+2.5];B[pd];W[dd];B[qp];W[dq];B[fc];W[cf])';

type ReportStatus = 'pending' | 'running' | 'completed' | 'failed';
type ReportType = 'normal' | 'deep';

interface ReportTask {
  id: number;
  user_game_id: string;
  status: ReportStatus;
  report_type: ReportType;
  total_moves: number;
  analyzed_moves: number;
  requested_visits: number;
}

const game = (id: string, overrides: Record<string, unknown> = {}) => ({
  id,
  user_id: 1,
  title: `测试棋局 ${id}`,
  player_black: 'Alpha',
  player_white: 'Beta',
  black_rank: '3D',
  white_rank: '4D',
  result: 'B+2.5',
  board_size: 19,
  rules: 'chinese',
  komi: 7.5,
  move_count: 6,
  source: 'import',
  category: 'review',
  game_type: null,
  event: `测试赛事 ${id}`,
  round_name: '第 1 轮',
  game_date: '2026-07-15',
  created_at: '2026-07-15T08:00:00Z',
  updated_at: '2026-07-15T08:00:00Z',
  ...overrides,
});

/**
 * 七局各占一种行状态 —— `reviewPresentation.rowState` 一共就六种,
 * 加上「同一局两档都跑完」那一档(行尾没有唯一宾语,得拆成两个键)。
 * 少造一种,那一档在真浏览器里就一次都没画过。
 */
const GAMES = [
  game('no-report', { event: '尚未生成复盘' }),                       // unanalyzed
  game('queued', { event: '排队中的棋局' }),                          // running(pending)
  game('running', { event: '正在生成的棋局' }),                       // running
  game('normal', { event: '普通复盘已完成' }),                        // analyzed(一档)
  game('both-tiers', { event: '两档都跑完了' }),                      // analyzed(两档)
  game('failed', { event: '算了一半断掉' }),                          // partial
  game('dead', { event: '一手没算就失败了' }),                        // failed
  game('unfinished', { event: '没下完的棋', result: null }),          // unfinished
  game('long', {
    title: '一段非常非常长、用于验证七英寸屏幕标题不会挤出研究按钮的复盘标题',
    event: '一场元数据同样很长、必须在 1024 像素宽度内正确省略的国际赛事',
    player_black: '黑方棋手名字特别特别长',
    player_white: '白方棋手名字也特别特别长',
  }),
];

const INITIAL_TASKS: ReportTask[] = [
  { id: 101, user_game_id: 'queued', status: 'pending', report_type: 'normal', total_moves: 6, analyzed_moves: 0, requested_visits: 1000 },
  { id: 102, user_game_id: 'running', status: 'running', report_type: 'deep', total_moves: 6, analyzed_moves: 3, requested_visits: 5000 },
  { id: 103, user_game_id: 'normal', status: 'completed', report_type: 'normal', total_moves: 6, analyzed_moves: 6, requested_visits: 1000 },
  { id: 104, user_game_id: 'both-tiers', status: 'completed', report_type: 'normal', total_moves: 6, analyzed_moves: 6, requested_visits: 1000 },
  { id: 107, user_game_id: 'both-tiers', status: 'completed', report_type: 'deep', total_moves: 6, analyzed_moves: 6, requested_visits: 5000 },
  // 后端没有「暂停」：跑一半断掉的落在 failed 上、`analyzed_moves` 还留着 ⇒ 那是「只算到 n/m · 继续分析」。
  { id: 105, user_game_id: 'failed', status: 'failed', report_type: 'normal', total_moves: 6, analyzed_moves: 2, requested_visits: 1000 },
  { id: 108, user_game_id: 'dead', status: 'failed', report_type: 'normal', total_moves: 6, analyzed_moves: 0, requested_visits: 1000 },
  { id: 106, user_game_id: 'long', status: 'completed', report_type: 'deep', total_moves: 6, analyzed_moves: 6, requested_visits: 5000 },
];

/**
 * `/baipu/load` 的 canonical 坐标(row 0 在上,col 按 ABCDEFGHJKLMNOPQRST 数),
 * 对着 `SGF` 那六手:B[pd] W[dd] B[qp] W[dq] B[fc] W[cf]。
 */
const FINAL_BOARD = [
  ['B', 3, 15],   // pd = Q16
  ['W', 3, 3],    // dd = D16
  ['B', 15, 16],  // qp = R4
  ['W', 16, 3],   // dq = D3
  ['B', 2, 5],    // fc = F17
  ['W', 5, 2],    // cf = C14
] as const;

const OWNERSHIP = Array.from({ length: 19 }, (_row, y) =>
  Array.from({ length: 19 }, (_column, x) => ((x + y) % 3 === 0 ? 0.8 : -0.6)),
);

const reportMoves = (taskId: number) => Array.from({ length: 7 }, (_unused, moveNumber) => ({
  id: taskId * 10 + moveNumber,
  task_id: taskId,
  move_number: moveNumber,
  status: 'completed',
  // 第 3 手是黑走的,黑的胜率从 54% 掉到 30% —— `keyMoves` 要**目和胜率同时掉**才收，
  // 只把 `delta_score` 写成负数、胜率却一路上扬,那一手一样进不了「重点手」。
  winrate: moveNumber === 3 ? 0.30 : 0.52 + moveNumber * 0.01,
  score_lead: 1.2 + moveNumber * 0.3,
  visits: 1200,
  top_moves: [
    { move: 'Q10', visits: 700, winrate: 0.64, score_lead: 4.1, prior: 0.3, psv: 0.6, pv: ['Q10', 'C12', 'R6'] },
    { move: 'C12', visits: 350, winrate: 0.61, score_lead: 3.2, prior: 0.2, psv: 0.3, pv: ['C12', 'Q10'] },
    { move: 'R6', visits: 150, winrate: 0.59, score_lead: 2.7, prior: 0.1, psv: 0.1, pv: ['R6', 'D4'] },
  ],
  ownership: OWNERSHIP,
  actual_move: moveNumber === 0 ? null : ['Q16', 'D16', 'Q4', 'D4', 'F17', 'C14'][moveNumber - 1],
  actual_player: moveNumber === 0 ? null : moveNumber % 2 ? 'B' : 'W',
  // 第 3 手黑掉 6.4 目 —— 「重点手」只列掉过三目以上的,一手都不掉时它是空态,
  // 那一块的「看这手」就一次都没画过。
  delta_score: moveNumber === 0 ? null : moveNumber === 3 ? -6.4 : 0.3,
  delta_winrate: moveNumber === 0 ? null : 0.01,
}));

const ALBUM = {
  id: 88,
  player_black: '棋谱库黑方',
  player_white: '棋谱库白方',
  black_rank: '9P',
  white_rank: '9P',
  event: '棋谱库测试赛事',
  result: 'W+R',
  rules: 'chinese',
  date_played: '2026-01-02',
  komi: 7.5,
  handicap: 0,
  board_size: 19,
  round_name: '决赛',
  move_count: 6,
};

/**
 * **喂仓里那份真 PO,不是空表。**
 *
 * 这里原来是 `{}`,理由写的是「这一屏的文案键(`review:*`)在 `katrain/i18n/` 里一个都没有」
 * —— 那句话对 `review:*` 成立,可这条 spec 同时走**导入对话框**,而那一族(`report:*`)
 * 在 PO 里**条条都有**。于是空表让屏上落回代码 fallback,
 * 而当时代码 fallback 和 PO 说的不是同一句话(「导入并生成普通**复盘**」对「…普通**报告**」)
 * ⇒ **这条 e2e 有五处断言的字符串,设备上从来没出现过**。
 * 那是「到达性 fixture 给断路发通行证」的又一例:自己造的输入,自然自己能通过。
 *
 * 2026-08-26 那批 fallback 已经统一到 PO(见 `kiosk-shell-contract.spec.ts` 闸四),
 * 所以现在两边说的是同一句;但**判据不能靠这个巧合** —— 喂真 PO,
 * 将来任何一边再走散,这条 spec 会跟着红。
 */
const TRANSLATIONS: Record<string, string> = parsePo(
  resolve(process.cwd(), '../../i18n/locales/cn/LC_MESSAGES/katrain.po'),
);

interface MockState {
  tasks: ReportTask[];
  createReportBodies: Array<Record<string, unknown>>;
  createGameBodies: Array<Record<string, unknown>>;
  retryIds: number[];
  unhandledRequests: string[];
}

async function fulfillJson(route: Route, json: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(json) });
}

async function setupReportMocks(page: Page): Promise<MockState> {
  const state: MockState = {
    tasks: INITIAL_TASKS.map((task) => ({ ...task })),
    createReportBodies: [],
    createGameBodies: [],
    retryIds: [],
    unhandledRequests: [],
  };
  await page.addInitScript(() => {
    localStorage.setItem('token', 'report-e2e-token');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/translations**', (route) =>
    // 形状照真端点:`server.py:2180` 回的是 `{lang, translations}`,不是 `language`。
    fulfillJson(route, { lang: 'cn', translations: TRANSLATIONS }),
  );
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (path === '/api/v1/auth/me') {
      await fulfillJson(route, { id: 1, username: '触屏测试用户', rank: '1D', credits: 100 });
      return;
    }
    if (path === '/api/v1/tsumego/progress') {
      await fulfillJson(route, {});
      return;
    }
    if (path === '/api/v1/geometry/status') {
      await fulfillJson(route, {
        phase: 'ready',
        session_calibrated: true,
        last_valid: true,
        capabilities: { camera_ready: true, led_ready: true, geometry_ready: true },
      });
      return;
    }
    if (path === '/api/v1/vision/status') {
      await fulfillJson(route, {
        enabled: true,
        camera_connected: true,
        pose_locked: false,
        sync_state: 'synced',
        bound_session_id: null,
        recognition_ready: true,
        led_connected: true,
      });
      return;
    }
    if (path === '/api/v1/live/translations') {
      await fulfillJson(route, { translations: {} });
      return;
    }
    if (path === '/api/v1/reports/summary') {
      await fulfillJson(route, {
        pending: state.tasks.filter(({ status }) => status === 'pending').length,
        running: state.tasks.filter(({ status }) => status === 'running').length,
        completed: state.tasks.filter(({ status }) => status === 'completed').length,
        failed: state.tasks.filter(({ status }) => status === 'failed').length,
      });
      return;
    }
    if (path === '/api/v1/reports/' && method === 'GET') {
      await fulfillJson(route, state.tasks);
      return;
    }
    if (path === '/api/v1/reports/' && method === 'POST') {
      const body = request.postDataJSON() as Record<string, unknown>;
      state.createReportBodies.push(body);
      const created: ReportTask = {
        id: 200 + state.createReportBodies.length,
        user_game_id: String(body.user_game_id),
        status: 'pending',
        report_type: (body.report_type as ReportType | undefined) ?? 'normal',
        total_moves: 6,
        analyzed_moves: 0,
        requested_visits: body.report_type === 'deep' ? 5000 : 1000,
      };
      state.tasks.unshift(created);
      await fulfillJson(route, created, 201);
      return;
    }

    const reportMatch = path.match(/^\/api\/v1\/reports\/(\d+)(?:\/(moves|retry))?$/);
    if (reportMatch) {
      const taskId = Number(reportMatch[1]);
      const action = reportMatch[2];
      const task = state.tasks.find(({ id }) => id === taskId);
      if (!task) {
        await fulfillJson(route, { detail: 'not found' }, 404);
        return;
      }
      if (action === 'moves') {
        await fulfillJson(route, reportMoves(taskId).slice(0, task.analyzed_moves + 1));
        return;
      }
      if (action === 'retry' && method === 'POST') {
        state.retryIds.push(taskId);
        task.status = 'pending';
        task.analyzed_moves = 0;
        await fulfillJson(route, task);
        return;
      }
      await fulfillJson(route, task);
      return;
    }

    if (path === '/api/v1/user-games/' && method === 'GET') {
      const q = (url.searchParams.get('q') || '').toLocaleLowerCase();
      const items = q
        ? GAMES.filter((item) => JSON.stringify(item).toLocaleLowerCase().includes(q))
        : GAMES;
      await fulfillJson(route, { items, total: items.length, page: 1, page_size: 12 });
      return;
    }
    if (path === '/api/v1/user-games/' && method === 'POST') {
      const body = request.postDataJSON() as Record<string, unknown>;
      state.createGameBodies.push(body);
      await fulfillJson(route, {
        ...game(`imported-${state.createGameBodies.length}`, {
          title: body.title ?? '已导入测试棋局',
          source: body.source,
          player_black: body.player_black ?? 'Alpha',
          player_white: body.player_white ?? 'Beta',
        }),
        sgf_content: body.sgf_content ?? SGF,
      }, 201);
      return;
    }
    const userGameMatch = path.match(/^\/api\/v1\/user-games\/([^/]+)$/);
    if (userGameMatch) {
      const item = GAMES.find(({ id }) => id === decodeURIComponent(userGameMatch[1]));
      if (!item) {
        await fulfillJson(route, { detail: 'not found' }, 404);
        return;
      }
      if (method === 'DELETE') {
        await fulfillJson(route, { status: 'deleted' });
        return;
      }
      await fulfillJson(route, { ...item, sgf_content: SGF });
      return;
    }

    // 左栏那块「选中那一局的终局盘」由后端把 SGF 走成局面 —— 前端不自己摆子。
    if (path === '/api/v1/baipu/load' && method === 'POST') {
      await fulfillJson(route, {
        board_size: 19,
        steps: FINAL_BOARD.map(([color, row, col], index) => ({
          kind: 'move', move_index: index, property: color, row, col, color,
          removed: [], board_hash: '',
        })),
        meta: {},
      });
      return;
    }

    if (path === '/api/v1/kifu/albums') {
      await fulfillJson(route, { items: [ALBUM], total: 1, page: 1, page_size: 10 });
      return;
    }
    if (path === `/api/v1/kifu/albums/${ALBUM.id}`) {
      await fulfillJson(route, { ...ALBUM, place: '测试会场', source: 'e2e', sgf_content: SGF });
      return;
    }

    state.unhandledRequests.push(`${method} ${path}`);
    await fulfillJson(route, { detail: `Unhandled deterministic fixture: ${method} ${path}` }, 500);
  });
  return state;
}

async function expectViewportFit(page: Page) {
  expect(page.viewportSize()).toEqual(VIEWPORT);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(VIEWPORT.width);
}

/**
 * **48 只对壳管不着的控件成立。** MUI 的菜单项、对话框按钮、顶栏、Dock 由这份自己负责,
 * 那 48 是这里唯一的判据。
 *
 * 而 §11 那套外壳控件(页控条返回键 36 高、`--btn-pill-h: 26`、走子键、开关条)的几何
 * **是四棋类共用的设计系统**,由 `kiosk-shell-geometry.spec.ts` 逐条钉着。
 * 在这儿对同一个控件再断言一个不一样的数,两条闸就会互相矛盾 ——
 * 而先红的那条多半会被人按现状改小,等于把设计系统调成了「现在长这样」。
 * 所以壳控件在这份里只判 `expectReachable`:**在屏上、没被切掉、点得到**。
 */
async function expectTouchTarget(page: Page, locator: Locator, name: string) {
  await expect(locator, `${name} should be visible`).toBeVisible();
  await expect.poll(async () => (await locator.boundingBox())?.width ?? 0, {
    message: `${name} width should settle at the touch minimum`,
  }).toBeGreaterThanOrEqual(48);
  await expect.poll(async () => (await locator.boundingBox())?.height ?? 0, {
    message: `${name} height should settle at the touch minimum`,
  }).toBeGreaterThanOrEqual(48);
  const box = await locator.boundingBox();
  expect(box, `${name} should have a bounding box`).not.toBeNull();
  expect(box!.width, `${name} width`).toBeGreaterThanOrEqual(48);
  expect(box!.height, `${name} height`).toBeGreaterThanOrEqual(48);
  expect(box!.x, `${name} left edge`).toBeGreaterThanOrEqual(0);
  expect(box!.y, `${name} top edge`).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width, `${name} right edge`).toBeLessThanOrEqual(VIEWPORT.width + 0.5);
  expect(box!.y + box!.height, `${name} bottom edge`).toBeLessThanOrEqual(VIEWPORT.height + 0.5);
}

/** 壳控件:看得见、点得着、整块落在 1024×600 之内。具体尺寸归 `kiosk-shell-geometry.spec.ts`。 */
async function expectReachable(page: Page, locator: Locator, name: string) {
  // 不判 enabled：走子条走到末手时,四个键里有两个**本来就该是灰的**。
  // 该亮的地方由各条用例自己点名。
  await expect(locator, `${name} should be visible`).toBeVisible();
  const box = await locator.boundingBox();
  expect(box, `${name} should have a bounding box`).not.toBeNull();
  expect(box!.width, `${name} width`).toBeGreaterThan(0);
  expect(box!.height, `${name} height`).toBeGreaterThan(0);
  expect(box!.x, `${name} left edge`).toBeGreaterThanOrEqual(0);
  expect(box!.y, `${name} top edge`).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width, `${name} right edge`).toBeLessThanOrEqual(VIEWPORT.width + 0.5);
  expect(box!.y + box!.height, `${name} bottom edge`).toBeLessThanOrEqual(VIEWPORT.height + 0.5);
}

test.use({ viewport: VIEWPORT });

/**
 * 屏 19 复盘列表 / 屏 20 报告详情，**在 1024×600 这块真屏上**。
 *
 * 这份守的是 jsdom 作不了证的三样：控件够不够手指点（≥48）· 有没有横着溢出屏幕 ·
 * 点下去之后真的发了哪一条请求。静止一帧长什么样归四图
 * （`kiosk-screen-19-review.fourup.spec.ts` / `-20-report`），两边互不替代。
 *
 * ⚠️ **2026-08-25 整份重写。** 原来那版打的是 27 屏改造**之前**的 DOM
 * （`report-list-page` / `report-game-card` / 列表上的播放条 / 每张卡自己的菜单），
 * 改造之后四条全部停在第一句 `toBeVisible` 上 —— 断言的对象整个不存在了。
 * 这类失败最会骗人：它红得像「功能坏了」，其实是**闸自己过期了**，
 * 而一旦有人把它标成 skip，这一屏在真浏览器里就再也没人量过。
 */
test.describe('kiosk Report at the exact seven-inch viewport', () => {
  test('列表：装得下、六种状态各说各的话、选中、两档生成、断点续算、打开报告', async ({ page }) => {
    const state = await setupReportMocks(page);
    await page.goto('/kiosk/report');

    await expect(page.getByTestId('review-page')).toBeVisible();
    await expectViewportFit(page);

    const headerActions = page.locator('header').getByRole('button').or(
      page.locator('header').getByRole('link'),
    );
    await expect(headerActions).not.toHaveCount(0);
    for (let index = 0; index < await headerActions.count(); index += 1) {
      await expectTouchTarget(page, headerActions.nth(index), `Header action ${index + 1}`);
    }
    // Dock 有几项由 `KioskDock.test.tsx` 钉着 —— 这里只管**每一项都够手指点**。
    const dockActions = page.locator('nav button');
    await expect(dockActions).not.toHaveCount(0);
    for (let index = 0; index < await dockActions.count(); index += 1) {
      await expectTouchTarget(page, dockActions.nth(index), `Dock action ${index + 1}`);
    }

    // 六种行状态各有各的说法 —— 「算了一半」被糊弄成「已分析」是这一屏最容易犯的错。
    // ⚠️ 行上写的是 `rowTitle` —— `source: 'import'` 画的是「导入的棋谱 · {title}」,
    // `event` 在这一屏**根本不上屏**。拿 event 去找行,找到的是空集合。
    const rows = page.getByTestId('review-row');
    const rowOf = (id: string) => rows.filter({ hasText: `测试棋局 ${id}` });
    for (const [id, kind, tag] of [
      ['no-report', 'unanalyzed', '未分析'],
      ['queued', 'running', '正在分析 0/6'],
      ['running', 'running', '正在分析 3/6'],
      ['normal', 'analyzed', '已分析'],
      ['failed', 'partial', '只算到 2/6'],
      ['dead', 'failed', '分析失败'],
      ['unfinished', 'unfinished', '未终局'],
    ] as const) {
      await expect(rowOf(id), `${id} 行`).toHaveAttribute('data-state', kind);
      await expect(rowOf(id), `${id} 的状态标`).toContainText(tag);
    }

    // 两档都跑完 ⇒ 行尾拆成两个键，各自只有一个宾语；只有一档时才是概括的「查看报告」。
    const bothRow = rowOf('both-tiers');
    await expectReachable(page, bothRow.getByRole('button', { name: '标准' }), '两档 · 标准');
    await expectReachable(page, bothRow.getByRole('button', { name: '精读' }), '两档 · 精读');
    await expect(bothRow.getByRole('button', { name: '查看报告' })).toHaveCount(0);

    // 选中是整块左半，动作在行尾 —— 两个手势分开。
    const pick = rowOf('running').locator('.rvpick');
    await expectReachable(page, pick, 'Row select target');
    await pick.click();
    await expect(rowOf('running')).toHaveAttribute('data-selected', 'true');

    // 没下完的局不给生成报告：判别位是「终局没有」，不是「算不算分」。
    await rowOf('unfinished').locator('.rvpick').click();
    const standard = page.getByTestId('review-cards').getByRole('button', { name: /标准/ });
    const deep = page.getByTestId('review-cards').getByRole('button', { name: /精读/ });
    await expect(standard).toBeDisabled();
    await expect(deep).toBeDisabled();

    await rowOf('no-report').locator('.rvpick').click();
    await expectReachable(page, standard, 'Standard tier card');
    await expectReachable(page, deep, 'Deep tier card');
    await standard.click();
    await expect.poll(() => state.createReportBodies)
      .toContainEqual({ user_game_id: 'no-report', report_type: 'normal' });

    // 断掉的那条重试会**从断点续算**，所以它说的是「继续分析」而不是「重试」。
    const resume = rowOf('failed').getByRole('button', { name: '继续分析' });
    await resume.scrollIntoViewIfNeeded();
    await expectReachable(page, resume, 'Resume partial analysis');
    await resume.click();
    await expect.poll(() => state.retryIds).toContain(105);
    await expectViewportFit(page);

    const open = rowOf('normal').getByRole('button', { name: '查看报告' });
    await open.scrollIntoViewIfNeeded();
    await expectReachable(page, open, 'Open completed report');
    await open.click();
    await expect(page).toHaveURL(/\/kiosk\/report\/103$/);
    await expect(page.getByTestId('report-detail-board')).toBeVisible();
    expect(state.unhandledRequests).toEqual([]);
  });

  test('导入：两条路都点得着，送出去的两份 body 都对', async ({ page }) => {
    const state = await setupReportMocks(page);
    await page.goto('/kiosk/report');
    await expect(page.getByTestId('review-page')).toBeVisible();

    const importCard = page.getByTestId('review-cards').getByRole('button', { name: /导入棋谱复盘/ });
    await expectReachable(page, importCard, 'Import trigger');
    await importCard.click();
    const localMenuItem = page.getByRole('menuitem', { name: '从本地导入 SGF' });
    const libraryMenuItem = page.getByRole('menuitem', { name: '从棋谱库导入' });
    await expectTouchTarget(page, localMenuItem, 'Local import menu action');
    await expectTouchTarget(page, libraryMenuItem, 'Library import menu action');
    await localMenuItem.click();

    const localDialog = page.getByRole('dialog', { name: '从本地导入 SGF' });
    await expect(localDialog).toBeVisible();
    await expectTouchTarget(page, localDialog.getByRole('button', { name: '选择本地文件' }), 'Local file chooser');
    await localDialog.getByLabel('SGF 内容').fill(SGF);
    for (const label of ['取消', '仅导入', '导入并生成普通报告', '导入并生成深度报告']) {
      await expectTouchTarget(page, localDialog.getByRole('button', { name: label }), `Local dialog ${label}`);
    }
    await expectViewportFit(page);
    const keyboardHide = page.locator('.skbd-hide');
    if (await keyboardHide.isVisible()) await keyboardHide.click();
    await localDialog.getByRole('button', { name: '导入并生成普通报告' }).click();
    await expect(localDialog).toBeHidden();
    await expect.poll(() => state.createGameBodies.length).toBe(1);
    // 棋谱自己写着 `RE[B+2.5]`。本地导入这条以前**不读 RE[]**，
    // 于是导进来的每一局在屏上都是「没写胜负」——而屏幕上看不出它本来是有的。
    await expect.poll(() => state.createGameBodies[0]?.result).toBe('B+2.5');
    await expect.poll(() => state.createReportBodies)
      .toContainEqual({ user_game_id: 'imported-1', report_type: 'normal' });

    await importCard.click();
    await page.getByRole('menuitem', { name: '从棋谱库导入' }).click();
    const libraryDialog = page.getByRole('dialog', { name: '从棋谱库导入' });
    await expect(libraryDialog).toBeVisible();
    const librarySearch = libraryDialog.getByRole('textbox', { name: '搜索棋谱库' });
    const librarySearchButton = libraryDialog.getByRole('button', { name: '搜索' });
    await expectTouchTarget(page, librarySearch, 'Library search input');
    await expectTouchTarget(page, librarySearchButton, 'Library search button');
    const album = libraryDialog.getByRole('button', { name: /棋谱库测试赛事/ });
    await expectTouchTarget(page, album, 'Library result');
    for (const label of ['取消', '仅导入', '导入并生成普通报告', '导入并生成深度报告']) {
      await expectTouchTarget(page, libraryDialog.getByRole('button', { name: label }), `Library dialog ${label}`);
    }
    await expectViewportFit(page);
    await libraryDialog.getByRole('button', { name: '导入并生成深度报告' }).click();
    await expect(libraryDialog).toBeHidden();
    await expect.poll(() => state.createGameBodies.length).toBe(2);
    await expect.poll(() => state.createReportBodies)
      .toContainEqual({ user_game_id: 'imported-2', report_type: 'deep' });
    expect(state.unhandledRequests).toEqual([]);
  });

  test('报告详情：长元数据装得下、四个开关、重点手跳手、去研究带得回来', async ({ page }) => {
    const state = await setupReportMocks(page);
    await page.goto('/kiosk/report/106');

    await expect(page.getByTestId('report-detail-board')).toBeVisible();
    await expectViewportFit(page);
    await expectReachable(
      page,
      page.getByTestId('report-detail-pagebar').getByRole('button', { name: '复盘' }),
      'Detail back',
    );
    const research = page.getByRole('button', { name: '去研究' });
    await expectReachable(page, research, 'Open in Research');
    await expectReachable(page, page.getByRole('button', { name: '重算' }), 'Recompute');

    // 造的数据里有 ownership ⇒「领地」可点(那颗键开的就是 ownership 色块)。四个开关的初值写死在页面上，点一下必须翻面。
    const toggles = page.getByTestId('report-detail-toggles');
    for (const [name, pressedAfter] of [
      ['领地', 'false'], ['手数', 'false'], ['AI 推荐', 'true'], ['试下', 'true'],
    ] as const) {
      const toggle = toggles.getByRole('button', { name });
      await expectReachable(page, toggle, `${name} toggle`);
      await toggle.click();
      await expect(toggle).toHaveAttribute('aria-pressed', pressedAfter);
    }

    // 走子的四个键 —— 这一屏没有滑杆，长局靠曲线点，短距离靠这四个。
    const movenav = page.getByTestId('report-detail-movenav');
    for (const label of ['回到开局', '上一手', '下一手', '跳到最后']) {
      await expectReachable(page, movenav.getByRole('button', { name: label }), `Movenav ${label}`);
    }
    // 打开时游标停在**最后一份算完的分析**上,所以「跳到最后」这会儿就是灰的。
    await expect(movenav.getByRole('button', { name: '跳到最后' })).toBeDisabled();
    await movenav.getByRole('button', { name: '回到开局' }).click();
    await expect(movenav.getByRole('button', { name: '回到开局' })).toBeDisabled();
    await expect(movenav.getByRole('button', { name: '下一手' })).toBeEnabled();

    // 「重点手」那块每行一个「看这手」，点了就跳到那一手。
    const keyRow = page.getByTestId('report-detail-key-row').first();
    await keyRow.scrollIntoViewIfNeeded();
    const seeMove = keyRow.getByRole('button', { name: '看这手' });
    await expectReachable(page, seeMove, 'See this move');
    await seeMove.click();
    // 跳到某一手之后就不在开局了 —— 「回到开局」重新亮起来。
    await expect(movenav.getByRole('button', { name: '回到开局' })).toBeEnabled();

    await expectViewportFit(page);
    await research.click();
    // `&from=report&task=` 是屏 21 加的 —— 研究屏靠它才知道返回键该回**这一份报告**
    // (四个入口里,这一条和对局历史那一条的 URL 形状一模一样、反推不出来)。
    await expect(page).toHaveURL(/\/kiosk\/research\?user_game_id=long&from=report&task=\d+$/);
    expect(state.unhandledRequests).toEqual([]);
  });

  test('算了一半的报告：「重算」够手指点，且真的打到共用的那条 API', async ({ page }) => {
    const state = await setupReportMocks(page);
    await page.goto('/kiosk/report/105');

    const retry = page.getByRole('button', { name: '重算' });
    await expectReachable(page, retry, 'Detail retry');
    await retry.click();
    await expect.poll(() => state.retryIds).toContain(105);
    await expectViewportFit(page);
    expect(state.unhandledRequests).toEqual([]);
  });
});
