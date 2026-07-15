import { expect, test, type Locator, type Page, type Route } from '@playwright/test';

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

const GAMES = [
  game('no-report', { event: '尚未生成复盘' }),
  game('queued', { event: '排队中的棋局' }),
  game('running', { event: '正在生成的棋局' }),
  game('normal', { event: '普通复盘已完成' }),
  game('deep', { event: '深度复盘已完成' }),
  game('failed', { event: '失败后可重试' }),
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
  { id: 104, user_game_id: 'deep', status: 'completed', report_type: 'deep', total_moves: 6, analyzed_moves: 6, requested_visits: 5000 },
  { id: 105, user_game_id: 'failed', status: 'failed', report_type: 'normal', total_moves: 6, analyzed_moves: 2, requested_visits: 1000 },
  { id: 106, user_game_id: 'long', status: 'completed', report_type: 'deep', total_moves: 6, analyzed_moves: 6, requested_visits: 5000 },
];

const OWNERSHIP = Array.from({ length: 19 }, (_row, y) =>
  Array.from({ length: 19 }, (_column, x) => ((x + y) % 3 === 0 ? 0.8 : -0.6)),
);

const reportMoves = (taskId: number) => Array.from({ length: 7 }, (_unused, moveNumber) => ({
  id: taskId * 10 + moveNumber,
  task_id: taskId,
  move_number: moveNumber,
  status: 'completed',
  winrate: 0.52 + moveNumber * 0.01,
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
  delta_score: moveNumber === 0 ? null : 0.3,
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

const TRANSLATIONS: Record<string, string> = {
  Settings: '设置',
  'report:normal': '普通报告',
  'report:deep': '深度报告',
  'report:select_game': '选择一局棋谱',
  'report:more_actions': '更多报告操作',
  'report:generate_normal': '生成普通报告',
  'report:generate_deep': '生成深度报告',
  'report:open_normal': '打开普通报告',
  'report:open_deep': '打开深度报告',
  'report:retry_normal': '重试普通报告',
  'report:retry_deep': '重试深度报告',
  'report:import_local': '从本地导入 SGF',
  'report:import_library': '从棋谱库导入',
  'report:import_and_normal': '导入并生成普通报告',
  'report:import_and_deep': '导入并生成深度报告',
  'report:enter_research': '进入研究室',
  'report:territory': '领地',
  'report:suggestions': '建议',
  'live:first_move': '第一手',
  'live:previous': '上一手',
  'live:next': '下一手',
  'live:latest': '最新',
  'live:moves': '手',
};

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
    fulfillJson(route, { language: 'cn', translations: TRANSLATIONS }),
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

async function expectPlaybackTouchTargets(page: Page, playback: Locator, name: string) {
  await expectTouchTarget(page, playback.getByRole('slider'), `${name} slider`);
  for (const control of ['第一手', '上一手', '播放', '下一手', '最新']) {
    await expectTouchTarget(page, playback.getByRole('button', { name: control }), `${name} ${control}`);
  }
}

test.use({ viewport: VIEWPORT });

test.describe('kiosk Report at the exact seven-inch viewport', () => {
  test('list fits, exposes every state, selects games, creates and retries reports', async ({ page }) => {
    const state = await setupReportMocks(page);
    await page.goto('/kiosk/report');

    await expect(page.getByTestId('report-list-page')).toBeVisible();
    await expectViewportFit(page);
    const headerActions = page.locator('header').getByRole('button').or(
      page.locator('header').getByRole('link'),
    );
    await expect(headerActions).not.toHaveCount(0);
    for (let index = 0; index < await headerActions.count(); index += 1) {
      await expectTouchTarget(page, headerActions.nth(index), `Header action ${index + 1}`);
    }
    const dockActions = page.locator('nav button');
    await expect(dockActions).toHaveCount(8);
    for (let index = 0; index < 8; index += 1) {
      await expectTouchTarget(page, dockActions.nth(index), `Dock action ${index + 1}`);
    }
    await expectPlaybackTouchTargets(page, page.getByTestId('report-playback'), 'List playback');
    await expect(page.getByText('普通报告 · 排队中', { exact: true })).toBeVisible();
    await expect(page.getByText('深度报告 · 生成中', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '打开普通报告' })).toBeAttached();
    await expect(page.getByRole('button', { name: '打开深度报告' })).toHaveCount(2);
    await expect(page.getByRole('button', { name: '重试普通报告' })).toBeAttached();

    const runningCard = page.getByRole('button', { name: /选择一局棋谱：正在生成的棋局/ });
    await runningCard.click();
    await expect(runningCard.locator('xpath=ancestor::*[@data-testid="report-game-card"]')).toHaveAttribute('data-selected', 'true');

    const noReportCard = page.getByRole('button', { name: /选择一局棋谱：尚未生成复盘/ })
      .locator('xpath=ancestor::*[@data-testid="report-game-card"]');
    await noReportCard.getByRole('button').nth(1).click();
    const generateNormal = page.getByRole('menuitem', { name: '生成普通报告' });
    await expectTouchTarget(page, generateNormal, 'Generate normal report');
    await generateNormal.click();
    await expect.poll(() => state.createReportBodies).toContainEqual({ user_game_id: 'no-report', report_type: 'normal' });

    const retry = page.getByRole('button', { name: '重试普通报告' });
    await retry.scrollIntoViewIfNeeded();
    await expectTouchTarget(page, retry, 'Failed report retry');
    await retry.click();
    await expect.poll(() => state.retryIds).toContain(105);
    await expectViewportFit(page);

    const openCompleted = page.getByRole('button', { name: '打开普通报告' });
    await openCompleted.scrollIntoViewIfNeeded();
    await expectTouchTarget(page, openCompleted, 'Open completed report');
    await openCompleted.click();
    await expect(page).toHaveURL(/\/kiosk\/report\/103$/);
    await expect(page.getByTestId('report-detail-board')).toBeVisible();
    expect(state.unhandledRequests).toEqual([]);
  });

  test('local and library imports keep all actions visible and send normal/deep requests', async ({ page }) => {
    const state = await setupReportMocks(page);
    await page.goto('/kiosk/report');
    await expect(page.getByTestId('report-list-page')).toBeVisible();

    const importButton = page.getByRole('button', { name: '导入棋谱' });
    await expectTouchTarget(page, importButton, 'Import trigger');
    await importButton.click();
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
    await expect.poll(() => state.createReportBodies).toContainEqual({ user_game_id: 'imported-1', report_type: 'normal' });

    await importButton.click();
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
    await expect.poll(() => state.createReportBodies).toContainEqual({ user_game_id: 'imported-2', report_type: 'deep' });
    expect(state.unhandledRequests).toEqual([]);
  });

  test('completed detail fits long metadata, toggles analysis, previews recommendations and opens Research', async ({ page }) => {
    const state = await setupReportMocks(page);
    await page.goto('/kiosk/report/106');

    await expect(page.getByTestId('report-detail-board')).toBeVisible();
    await expectViewportFit(page);
    await expectTouchTarget(page, page.getByRole('button', { name: '返回', exact: true }), 'Detail back');
    const research = page.getByRole('button', { name: '进入研究室' });
    await expectTouchTarget(page, research, 'Open in Research');

    for (const [name, pressed] of [['试下', 'true'], ['领地', 'true'], ['手数', 'true'], ['建议', 'false']] as const) {
      const toggle = page.getByRole('button', { name });
      await expectTouchTarget(page, toggle, `${name} toggle`);
      await toggle.click();
      await expect(toggle).toHaveAttribute('aria-pressed', pressed);
    }

    const recommendations = ['Q10', 'C12', 'R6'].map((move) => (
      page.getByRole('button', { name: `预览变化 ${move}` })
    ));
    for (const [index, recommendation] of recommendations.entries()) {
      await recommendation.scrollIntoViewIfNeeded();
      await expectTouchTarget(page, recommendation, `AI recommendation ${index + 1}`);
    }
    await recommendations[0].click();
    await expect(page.getByText('变化预览', { exact: false })).toBeVisible();

    await expectPlaybackTouchTargets(page, page.getByTestId('report-detail-playback-fixed'), 'Detail playback');
    await expectViewportFit(page);
    await research.click();
    await expect(page).toHaveURL(/\/kiosk\/research\?user_game_id=long$/);
    expect(state.unhandledRequests).toEqual([]);
  });

  test('failed detail keeps its retry action touch-safe and retries through the shared server API', async ({ page }) => {
    const state = await setupReportMocks(page);
    await page.goto('/kiosk/report/105');

    const retry = page.getByRole('button', { name: '重试复盘' });
    await expectTouchTarget(page, retry, 'Detail retry');
    await retry.click();
    await expect.poll(() => state.retryIds).toContain(105);
    await expectViewportFit(page);
    expect(state.unhandledRequests).toEqual([]);
  });
});
