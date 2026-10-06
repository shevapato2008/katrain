import { resolve } from 'node:path';
import { stubBackendStatics } from './helpers/fourup';
import { test, expect, type Page } from '@playwright/test';

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
  'live:moves': '手',
  'live:ai_recommendations': 'AI 推荐',
  'live:after_move': '第',
  'live:suggested_move': '着点',
  'live:recommendation': '推荐度',
  'live:lead_pts': '领先',
  'live:winrate': '胜率',
  'live:territory': '领地',
  'live:move_numbers': '手数',
  'live:try': '试下',
  'live:clear': '清空',
  'Advice': '支招',
  'Coordinates': '坐标',
  'report:enter_research': '进入研究',
  'review:recompute': '重算',
  'report:chinese_rules': '中国规则',
  'result:white_win': '白胜',
  'result:time': '超时',
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


const rows = buildMoves();
// Store the next actual move below the top five to exercise the bounded sixth row.
const beforeFinal = rows[MOVES - 1];
const actualCandidate = beforeFinal.top_moves.find(move => move.move === gtpPoint(MOVES))!;
beforeFinal.top_moves = [...beforeFinal.top_moves.filter(move => move.move !== actualCandidate.move), actualCandidate];
const game = { id: 'g1', user_id: 1, title: '2026世界围棋团体赛', player_black: '王星昊', player_white: '杨鼎新',
  black_rank: '9p', white_rank: '9p', result: 'W+T', board_size: 19, rules: 'chinese', komi: 6.5,
  move_count: MOVES, source: 'import', category: 'game', event: '2026世界围棋团体赛', round_name: '决赛',
  game_date: '2026-10-01', date_played: '2026-10-01', sgf_content: sgf(), handicap: 0 };
const parameters = { version: 1, verified: true, rules: 'japanese', komi: 6.5, sgf_sha256: 'test-sgf', parameter_sha256: 'test-parameters', provenance: {} };
async function prepare(page: Page, unresolved = false, realAudio = false) {
  await stubBackendStatics(page);
  await page.route('**/assets/sounds/stone1.wav', route => route.fulfill({ path: resolve(process.cwd(), '../../sounds/stone1.wav'), contentType: 'audio/wav' }));
  await page.addInitScript(({ realAudio }) => {
    localStorage.setItem('token', 'test'); localStorage.setItem('katrain_language', 'cn');
    (window as any).__stonePlays = 0;
    const nativePlay = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function () {
      const playing = realAudio ? nativePlay.call(this) : Promise.resolve();
      return playing.then(() => { if (this.src.endsWith('/stone1.wav')) (window as any).__stonePlays++; });
    };
  }, { realAudio });
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const path = new URL(route.request().url()).pathname;
    let json: unknown = {};
    if (path.endsWith('/auth/me')) json = { id: 1, username: '棋手', rank: '5d', credits: 100 };
    else if (path === '/api/translations') json = { lang: 'cn', translations: translationFixture };
    else if (path.endsWith('/live/translations')) json = { players: {}, tournaments: {}, rounds: {}, rules: {} };
    else if (path.endsWith('/geometry/status')) json = { phase: 'disabled', capabilities: {} };
    else if (path.endsWith('/vision/status')) json = { enabled: false };
    else if (path.endsWith('/reports/42/moves')) json = rows;
    else if (path.endsWith('/reports/42')) json = { id: 42, user_game_id: 'g1', status: 'completed', report_type: 'deep', total_moves: MOVES, analyzed_moves: MOVES, requested_visits: 2000 };
    else if (path.endsWith('/user-games/g1')) json = game;
    else if (path.endsWith('/kifu/albums/7/analysis')) json = { album_id: 7, canonical_album_id: 7, status: unresolved ? 'rules_unresolved' : 'completed', total_moves: MOVES, analyzed_moves: unresolved ? 0 : MOVES, requested_visits: 2000, moves: unresolved ? [] : rows,
      analysis_parameters: unresolved ? null : parameters, parameters_verified: !unresolved, parameter_error: unresolved ? { code: 'rules_missing', message: 'SGF has no RU' } : null };
    else if (path.endsWith('/kifu/albums/7')) json = { ...game, id: 7, rules: unresolved ? null : game.rules, sgf_content: unresolved ? sgf().replace('RU[chinese]', '') : sgf() };
    await route.fulfill({ json });
  });
}

for (const viewport of [{ width: 1440, height: 900 }, { width: 2048, height: 1080 }, { width: 1024, height: 600 }]) {
  for (const professional of [false, true]) {
    const kiosk = viewport.width === 1024;
    test(`${kiosk ? 'kiosk' : 'Galaxy'} ${viewport.width} ${professional ? 'professional' : 'personal'}`, async ({ page }) => {
      await page.setViewportSize(viewport); await prepare(page);
      await page.goto(kiosk ? professional ? '/kiosk/kifu/7' : '/kiosk/report/42' : professional ? '/galaxy/kifu/7/report' : '/galaxy/report/42');
      const rail = page.getByTestId(kiosk ? professional ? 'kifu-report-detail-shell' : 'report-detail-shell' : 'report-analysis-layout');
      await expect(page.getByTestId('report-candidate-list')).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      expect(await page.evaluate(() => (window as any).__stonePlays)).toBe(0);
      const board = page.locator(kiosk ? '.kiosk-board' : '[data-testid="board-stage"]');
      const before = await board.boundingBox();
      await page.getByRole('button', { name: kiosk ? '上一手' : 'live:previous', exact: true }).click();
      expect(await page.evaluate(() => (window as any).__stonePlays)).toBe(1);
      const tag = `${kiosk ? 'kiosk' : 'galaxy'}-${viewport.width}-${professional ? 'pro' : 'personal'}`;
      if (kiosk) {
        const prefix = professional ? 'kifu-report' : 'report-detail';
        const actions = page.getByTestId(`${prefix}-actions`).getByRole('button');
        const toggles = page.getByTestId(`${prefix}-toggles`).getByRole('button');
        await expect(actions).toHaveText(['试下', '领地', '支招', '分析']);
        await expect(toggles).toHaveText(['手数', '坐标', '清空', '详情']);
        expect(await actions.first().evaluate(el => el.getBoundingClientRect().width))
          .toBe(await toggles.first().evaluate(el => el.getBoundingClientRect().width));
        await expect(page.getByTestId(`${prefix}-metadata`)).toContainText(professional ? '日本规则 · 分析贴目 6.5' : '中国规则 · 贴目 6.5');
        await expect(page.locator('.report-analysis-rail__players .kifu-record__stone--black')).toHaveCSS('background-color', 'rgb(21, 23, 22)');
        await expect(page.locator('.report-analysis-rail__players .kifu-record__stone--white')).toHaveCSS('background-color', 'rgb(232, 228, 223)');
      }
      await page.screenshot({ path: `/tmp/report-v2-playwright/${tag}-main.png` });
      const candidates = page.getByTestId('report-candidate-list');
      await expect(candidates.locator(':scope > *')).toHaveCount(6);
      const actual = candidates.locator('[data-actual="true"]');
      await expect(actual).toContainText('T1');
      await actual.scrollIntoViewIfNeeded();
      await expect(actual).toBeInViewport();
      expect(await candidates.evaluate(el => el.scrollTop)).toBeGreaterThan(0);
      expect(await rail.evaluate(el => el.scrollTop)).toBe(0);
      await page.screenshot({ path: `/tmp/report-v2-playwright/${tag}-actual-sixth.png` });
      if (kiosk) await page.getByRole('button', { name: '着手评价 · 七档' }).click();
      const root = kiosk ? page.getByRole('dialog') : page.getByTestId('report-analysis-tabs');
      for (const label of ['走势', '妙手', '失误', '发挥水准', 'AI吻合度']) {
        await root.getByRole(kiosk ? 'button' : 'tab', { name: label, exact: true }).click();
        await page.waitForTimeout(100);
        await page.screenshot({ path: `/tmp/report-v2-playwright/${tag}-${label}.png` });
        expect(await rail.evaluate(el => el.scrollHeight <= el.clientHeight + 1)).toBe(true);
        expect(await root.evaluate(el => el.scrollHeight <= el.clientHeight + 1)).toBe(true);
      }
      await page.getByRole('button', { name: 'AI吻合度 · 说明' }).click();
      const help = page.getByRole('dialog', { name: 'AI吻合度 · 说明' });
      await expect(help).toContainText('不能单独当作棋力或作弊的证据');
      await help.getByRole('button', { name: '关闭' }).click();
      await root.getByRole(kiosk ? 'button' : 'radio', { name: '分布', exact: true }).click();
      await page.screenshot({ path: `/tmp/report-v2-playwright/${tag}-distribution.png` });
      expect(await board.boundingBox()).toEqual(before);
      expect(await page.evaluate(() => (window as any).__stonePlays)).toBe(1);
    });
  }
}

test('unresolved report exposes raw SGF komi and keeps the WenKai dialog font', async ({ page }) => {
  await prepare(page, true); await page.goto('/galaxy/kifu/7/report');
  await expect(page.getByTestId('report-meta-panel')).toContainText('规则待核验');
  await expect(page.getByTestId('report-meta-panel')).not.toContainText('50.0%');
  await page.getByRole('button', { name: '对局详情' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText('SGF 贴目'); await expect(dialog).toContainText('6.5');
  expect(await dialog.evaluate(el => getComputedStyle(el).fontFamily)).toContain('LXGW WenKai');
});

for (const kiosk of [false, true]) test(`professional ${kiosk ? 'kiosk' : 'Galaxy'} plays the real stone wave after a gesture and respects mute`, async ({ page }) => {
  await page.setViewportSize(kiosk ? { width: 1024, height: 600 } : { width: 1440, height: 900 });
  await prepare(page, false, true);
  await page.goto(kiosk ? '/kiosk/kifu/7' : '/galaxy/kifu/7/report');
  await expect(page.getByTestId('report-candidate-list')).toBeVisible();
  expect(await page.evaluate(() => (window as any).__stonePlays)).toBe(0);
  const previous = page.getByRole('button', { name: kiosk ? '上一手' : 'live:previous', exact: true });
  await previous.click();
  await expect.poll(() => page.evaluate(() => (window as any).__stonePlays)).toBe(1);
  await page.evaluate(() => localStorage.setItem('kiosk_audio_sfx', 'false'));
  await previous.click();
  await page.mouse.move(100, 100);
  await page.getByRole('tooltip').waitFor({ state: 'hidden' });
  await page.getByRole('button', { name: '手数', exact: true }).click();
  expect(await page.evaluate(() => (window as any).__stonePlays)).toBe(1);
});
