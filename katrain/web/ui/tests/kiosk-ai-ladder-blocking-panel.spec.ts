import { expect, test, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * kiosk 挡局面板的六态:取图 + **承重结构实测**,固定 1024×600。
 *
 * 两件事在一个文件里,因为它们量的是同一帧而判据不同:
 *   · 取图那半交给人眼看构图对不对(四图关卡,由 -fourup 那条 spec 合成后两张);
 *   · 承重那半交给浏览器算 —— jsdom 没有布局引擎,对布局事实无权作证,
 *     而这块面板长在 kiosk 设置页那个 `overflow: hidden` 的右栏里:装不下的默认后果
 *     是**裁切**,而被裁掉的永远是最下面那一段,也就是按钮和代价行。
 *
 * 这块屏的取舍与 galaxy 那块(1440×900,要求整块面板一个像素都不许溢出)**不同**,
 * 所以判据也不同,三条关系式:
 *   1. 页面横向不许出现滚动条;
 *   2. **动作区必须整块落在视口内** —— 能改变什么的东西一个都不许被裁、不许要滚才看得见;
 *   3. 叙述区(状态说明 + 同步行 + 错误条)**溢出时必须真的能滚**,而不是被裁掉:
 *      `overflow-y` 算出来得是 auto/scroll,而且 `scrollTop` 真的推得动。
 *
 * 「能不能滚」永远归这一关。量之前先把数据造到会溢出 —— 装得下的数据量下量出来的
 * 数字一概不算,所以最后那条 case 把最长档位名、五行同步文案和错误 Alert 同时摆上。
 */

// 📏 **余量,以及变异该造多大** —— 两条一起用,单独用哪一条都会骗人。
//
// 量的是 `emptyGapPx`:**动作区顶边 − 它之前最后一个真的渲染出来的元素的底边**,也就是
// 空的那一段。旧口径(动作区顶边 − 裁切框底边)是个假指标:那个差里会站进**条件渲染**的
// 元素(错误条只在失败时出现),于是加了内容之后这个数纹丝不动 —— 一个在最该报警时不动的
// 指标。实测差别:压力那一格旧口径说 **+23**(还有余量),新口径说 **−35**(已经越界)。
//
// 实测(2026-08-11,1024×600,改完主标题/预览/披露之后重打的):
//
//   01-reserved 271 / 02-active-current 215 / 03-interrupted 271 / 04-active-other 271
//   05-pending-retrying 177 / 06-pending-refused 233 / runaway-rank-name 130
//   **10-error-state(真实文案,错误条在场)119**
//   overflow-worst-case(压力:12 倍长译文 + 16 倍错误条)**−60**
//
// **真实文案里最紧的是错误态的 119px**,不是没有错误时的 177 —— 错误条 + 代价行 + 两个
// 按钮同时在场那一帧才是这块屏最挤的样子,而它**只在失败时存在,顺路取图永远拍不到**。
// 01–04 那四格可滚区是空的(描述已升为标题、代价在按钮下面),口径回落到头部底边。
// `actionsSlackPx` 恒为 16,那是右栏的 padding,**不是可以拿来用的余量**。
//
// 变异量**必须大于闸的余量**,而「闸的余量」比上面任何一个 emptyGap 都小 —— 量出来的一对:
//   · 动作区 +40px ⇒ **12 条全绿**(错误态 alertSlack 从 119 掉到 71,还没够到任何判据);
//   · 动作区 +70px ⇒ **红**,而红的是**压力那一格的 sync 行**(它离裁切线只有 57px:
//     clipBottom 450 − syncLineBottom 393),不是错误态那一格。
//   ⇒ **最紧的那个数是 57,而它不在上面那张表里** —— 表报的是各格自己的空段,闸卡的是
//     最紧的那一条必需信息离裁切线还有多远。加文案的人要看的是前者,做变异的人要用后者。
// 这是「0 红」的第四种长相:探测点对、被测对象对、闸也真在守,只是变异被系统里的一段弹性
// (叙述区的 `flex:1`)整段吸收了 —— 而报告上和「闸真的挡住了」逐字相同。
// 直觉是反的:**变异造得越温和,越容易撞上它。**
//
// ⚠️ **变异必须证明自己到达了被测物,这一步我栽过一次。**
// 做装配层那次变异时我把 `npm run build` 的输出屏蔽了,而 `tsc -b` 因为
// 「`handleEndGame` 声明了没人用」失败 ⇒ **vite 根本没跑,旧产物原地不动**,
// playwright 跑的是**未变异的代码**,结果是「2 passed」—— 和「闸挡住了」逐字相同。
// 三条一起用(见 scratchpad 里的 mutate.sh):锚点唯一(`count == 1`,而裸的
// `minHeight: 0` 在那个文件里有 **4** 处,拿它当锚点必错)、构建输出不许屏蔽、
// 产物文件名必须变。本文件里所有红/绿都是按这条重跑过的。
//
// 变异量**必须大于余量**,这是量出来的一对:
//   · 给动作区加 8px(+8px 的 Stack 间距 = 16,< 23)⇒ **9 条全绿**;
//   · 加 16px(合计 24,> 23)或 40px ⇒ 当场红。
// 这是「0 红」的第四种长相:探测点对、被测对象对、闸也真在守,只是变异被系统里的一段弹性
// (这里是叙述区的 `flex:1`)整段吸收了 —— 而报告上和「闸真的挡住了」逐字相同。
// 直觉是反的:**变异造得越温和,越容易撞上它。**
//
// ⚠️ `reserved`(`blocking_game.state`)和 `released`(`AiLadderGameLifecycle`)是 2026-08-11
// **加法式**引入的两个取值。加法不会让任何既有 fixture 编译失败、也不会让任何既有断言变红 ——
// galaxy 那条 spec 的六个案例一个新取值都不覆盖,而且全绿。**编译器不管这两格,靠这里管。**
// 删掉下面 01 那个案例之前先想清楚:没有任何自动机制会提醒下一个人它不见了。
const VIEWPORT = { width: 1024, height: 600 };
const OUT_DIR = resolve(
  process.cwd(),
  '../../../superpowers/tracks/golaxy-ai-ladder-parity/visual/kiosk-blocking/1024x600',
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

const stubShell = async (page: Page, translations: Record<string, string> = {}) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'kiosk-ladder-e2e-token');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: 'tester', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/translations?lang=cn', (route) => route.fulfill({
    json: { lang: 'cn', translations },
  }));
};

/** 承重结论全部由浏览器算,不由测试猜。 */
const measure = (page: Page) => page.evaluate(() => {
  const panel = document.querySelector('[data-testid="kiosk-ladder-blocking-panel"]') as HTMLElement | null;
  const header = document.querySelector('[data-testid="kiosk-ladder-blocking-header"]') as HTMLElement | null;
  const body = document.querySelector('[data-testid="kiosk-ladder-blocking-body"]') as HTMLElement | null;
  const actions = document.querySelector('[data-testid="kiosk-ladder-blocking-actions"]') as HTMLElement | null;
  const column = document.querySelector('[data-testid="ranked-settings-panel"]') as HTMLElement | null;
  const name = document.querySelector('[data-testid="kiosk-ladder-blocking-name"]') as HTMLElement | null;
  if (!panel || !header || !body || !actions || !column || !name) throw new Error('挡局面板没渲染出来 —— 这一格根本不在');

  // ① **先读静止那一帧**。量之前必须确认没人滚过 —— 滚过之后量到的是别的一帧,
  //    而用户做决定看的就是这一帧。
  const restingScrollTop = body.scrollTop;

  // 静止帧里哪些东西**完整**落在裁切框内。判据是关系式:元素底边 ≤ 裁切框底边。
  // `toBeVisible()` 在这里没有证据力 —— 被滚动裁掉的元素在 Playwright 眼里仍然 visible,
  // 它只证明「没有 display:none」。
  const clipBottom = body.getBoundingClientRect().bottom;
  // 在**整块面板**里找,不是只在可滚区里找 —— 「这是哪一局 / 为什么挡着」那句现在是标题,
  // 住在不参与滚动的头部。必需信息从可滚区搬进固定区是**加强**,但探测点不跟着走的话,
  // 它会读成 null,而 `null <= number` 会以一个看不懂的方式红。
  const bottomOf = (selector: string) => {
    const node = panel.querySelector(selector) as HTMLElement | null;
    return node ? node.getBoundingClientRect().bottom : null;
  };
  const stateLineBottom = bottomOf('[data-testid="kiosk-ladder-state-line"]');
  const syncLineBottom = bottomOf('[data-testid="kiosk-ladder-sync-line"]');
  // 重设计之后,「重试几次」那个**数**搬进了固定的事实格(`__facts`),而那句解释它的散文
  // 留在可滚区。判据跟着搬:必需的是**数**,不是那句话。
  const syncFactBottom = bottomOf('[data-testid="kiosk-ladder-sync-fact"]');
  const alertBottom = bottomOf('[role="alert"]');

  // ② 再推一下,验「能不能滚」。`overflow-y: auto` 只是**声明**,要看 scrollTop 动不动。
  const before = body.scrollTop;
  body.scrollTop = body.scrollHeight;
  const scrolledTo = body.scrollTop;
  body.scrollTop = before;

  const actionsRect = actions.getBoundingClientRect();
  // ③ **余量**:文案再长多少就开始裁人。「过」和「过多少」是两回事,所以过与不过都打出来。
  const required = [stateLineBottom, syncFactBottom].filter((value): value is number => value !== null);
  const narrativeSlackPx = required.length ? Math.round(clipBottom - Math.max(...required)) : null;
  const alertSlackPx = alertBottom === null ? null : Math.round(clipBottom - alertBottom);
  const actionsSlackPx = Math.round(window.innerHeight - actionsRect.bottom);
  // **余量的正口径:量空的那一段。** 动作区顶边 − 它前面**最后一个真的渲染出来的**元素的底边。
  //
  // 旧口径(动作区顶边 − 裁切框底边)在这里是个假指标:那个差里**会站进条件渲染的元素**
  // (错误条只在失败时出现),于是加了内容之后这个数**纹丝不动** —— 一个在最该报警时不动的
  // 指标。所以取的是最后一个**已渲染**子元素,错误条一出现,这个数当场就缩。
  // 可滚区是**空的**时(01–04 那四格:描述已升为标题、代价在按钮下面,叙述区里什么都没有),
  // 「主键之前最后一个元素」就是头部本身 —— 空的那一段是整个叙述区。回落到它,
  // 这样每一格都报得出一个数,而不是一个看不懂的 null。
  // 事实格已经搬到可滚区外面,所以「主键之前最后一个元素」是它,不再是可滚区里的最后一项。
  const facts = panel.querySelector('[data-testid="kiosk-ladder-blocking-facts"]') as HTMLElement | null;
  const lastBefore = facts ?? (body.lastElementChild as HTMLElement | null) ?? header;
  const emptyGapPx = Math.round(actionsRect.top - lastBefore.getBoundingClientRect().bottom);
  return {
    columnClientHeight: column.clientHeight,
    columnClientWidth: column.clientWidth,
    headerHeight: Math.round(header.getBoundingClientRect().height),
    headerScrollHeight: header.scrollHeight,
    nameClientWidth: name.clientWidth,
    nameScrollWidth: name.scrollWidth,
    nameClientHeight: name.clientHeight,
    nameScrollHeight: name.scrollHeight,
    nameRight: Math.round(name.getBoundingClientRect().right),
    columnOverflow: getComputedStyle(column).overflow,
    panelClientHeight: panel.clientHeight,
    panelScrollHeight: panel.scrollHeight,
    bodyClientHeight: body.clientHeight,
    bodyScrollHeight: body.scrollHeight,
    bodyOverflowY: getComputedStyle(body).overflowY,
    bodyScrolledTo: scrolledTo,
    restingScrollTop,
    clipBottom: Math.round(clipBottom),
    stateLineBottom: stateLineBottom === null ? null : Math.round(stateLineBottom),
    syncLineBottom: syncLineBottom === null ? null : Math.round(syncLineBottom),
    syncFactBottom: syncFactBottom === null ? null : Math.round(syncFactBottom),
    alertBottom: alertBottom === null ? null : Math.round(alertBottom),
    narrativeSlackPx,
    alertSlackPx,
    actionsSlackPx,
    emptyGapPx,
    lastBeforeActionsTestId: lastBefore?.getAttribute('data-testid') ?? lastBefore?.getAttribute('role') ?? null,
    actionsTop: Math.round(actionsRect.top),
    actionsBottom: Math.round(actionsRect.bottom),
    actionsHeight: Math.round(actionsRect.height),
    innerHeight: window.innerHeight,
    innerWidth: window.innerWidth,
    docScrollWidth: document.documentElement.scrollWidth,
    docScrollHeight: document.documentElement.scrollHeight,
  };
});

type Measured = Awaited<ReturnType<typeof measure>>;

/** 三条关系式,每一条都写死了才去读数;具体像素只记录,不作判据。 */
const assertLoadBearing = (m: Measured, label: string) => {
  expect(m.docScrollWidth, `${label}:页面横向出现滚动条`).toBeLessThanOrEqual(m.innerWidth);
  expect(m.docScrollHeight, `${label}:整页纵向滚了 —— kiosk 是固定视口`).toBeLessThanOrEqual(m.innerHeight);
  // 面板自己不许把外层那个 overflow:hidden 的右栏撑破。
  expect(
    m.panelScrollHeight,
    `${label}:面板 ${m.panelScrollHeight}px 撑破了右栏可视高度 ${m.panelClientHeight}px，`
    + `而右栏是 overflow:${m.columnOverflow} —— 超出的部分是被裁掉的`,
  ).toBeLessThanOrEqual(m.panelClientHeight);
  // 动作区整块在视口内。被裁掉的动作等于没有动作。
  expect(m.actionsHeight, `${label}:动作区高度为 0 —— 按钮没渲染`).toBeGreaterThan(0);
  expect(
    m.actionsBottom,
    `${label}:动作区底边 ${m.actionsBottom}px 掉出了视口 ${m.innerHeight}px —— `
    + '被裁掉的正是代价行和确认按钮，而那是用户最需要读、也是唯一能推进事情的东西',
  ).toBeLessThanOrEqual(m.innerHeight);
  expect(m.actionsTop, `${label}:动作区顶边掉出视口上方`).toBeGreaterThanOrEqual(0);

  // —— 静止那一帧里到底有什么 ——
  //
  // 「元素存在」「元素 visible」「元素这一帧在屏上」是三件事,前两件都不蕴含第三件。
  // 上面那条 `bodyScrolledTo` 量的是**能不能滚**,由它推不出**静止帧够用** ——
  // 而用户决定按不按那个掉分按钮,看的就是静止那一帧。
  //
  // 失败长什么样:钉住的「认输那一局」和「会记为本局负」都在,而**说明是哪一局、
  // 为什么挡着的那句话在折线以下**。按钮和代价都在,语境没了。
  // **「这块屏能不能滚」本身要钉一条。** 我为错误条选的是「放进可滚区」那条路,而那条路
  // 成立的前提就是这里真的可滚;哪天有人把它改成 `hidden`,这个取舍就退化成「根本没有
  // 可滚区」—— 装不下的东西不是晚半秒看到,是没了,而屏上什么都不会说。
  expect(
    ['auto', 'scroll'],
    `${label}:叙述区的 overflow-y 是 ${m.bodyOverflowY} —— 错误条「放进可滚区」那个取舍的前提没了`,
  ).toContain(m.bodyOverflowY);
  expect(m.restingScrollTop, `${label}:量之前这块区域已经被滚过,那量的是别的一帧`).toBe(0);
  // ⚠️ **判据的比较对象跟着盒子链走。** 重设计之后必需信息都搬出了可滚区(标题在头部、
  // 那几个数在事实格,两者都 `flex: none`),所以它们该比的是**视口**,不是可滚区的裁切框 ——
  // 裁切框现在只圈着那条会变长的状态条。拿旧的比较对象去比,九格会一起红在一个不存在的
  // 缺陷上(实测过:facts 搬出去之后 clipBottom 跑到了 facts 上面,九条全红)。
  expect(
    m.stateLineBottom,
    `${label}:「这是哪一局 / 为什么挡着」那句话掉出视口了`,
  ).toBeLessThanOrEqual(m.innerHeight);
  if (m.syncFactBottom !== null) {
    // **判据从散文搬到了数上。** 重设计之后 outbox 的「重试 2/5」进了固定的事实格,
    // 而解释它的那句话留在可滚区 —— 用户据以决定「要不要先去重试」的是那个数,
    // 散文长到装不下时滚下去是设计好的降级,把散文也算成必需就等于要求
    // 「任何长度的译文都必须一屏装完」,那个要求没有任何布局能满足。
    expect(
      m.syncFactBottom,
      `${label}:outbox 的重试次数在静止帧里被裁掉了 —— `
      + '而「先去重试」这句话能不能据以决定,全靠那个数',
    ).toBeLessThanOrEqual(m.innerHeight);
  }
};

const CASES: Array<{ slug: string; title: string; blocking: Record<string, unknown> }> = [
  {
    slug: '01-reserved-never-started',
    title: '云端登记了、棋盘没开起来 —— 让掉不记成绩',
    blocking: {
      game_id: 'g1', state: 'reserved', ownership: 'other_device',
      user_color: 'B', opponent_rank_name: '业余 3 段',
      // 从没 activate ⇒ 一次心跳都没有、也没进 pending。缺席是 null,不是 0。
      heartbeat_age_seconds: null, pending_since_seconds: null,
    },
  },
  {
    slug: '02-active-current-resumable',
    title: '局还在下,就在这台机器上',
    blocking: {
      game_id: 'g1', state: 'active', ownership: 'current_device', session_id: 'sess-1',
      user_color: 'B', opponent_rank_name: '业余 3 段',
      heartbeat_age_seconds: 8, pending_since_seconds: null,
    },
  },
  {
    slug: '03-active-current-interrupted',
    title: '这台机器重启过,局接不回来',
    blocking: {
      game_id: 'g1', state: 'active', ownership: 'current_device',
      user_color: 'B', opponent_rank_name: '业余 3 段',
      // 本机重启过,进程没了 ⇒ 心跳停在重启那一刻。
      heartbeat_age_seconds: 214, pending_since_seconds: null,
    },
  },
  {
    slug: '04-active-other',
    title: '局在另一台设备上',
    blocking: {
      game_id: 'g1', state: 'active', ownership: 'other_device',
      user_color: 'W', opponent_rank_name: '业余 3 段',
      // 42 秒 —— 和象棋参考屏同一个数,方便并排看骨架时对得上。
      heartbeat_age_seconds: 42, pending_since_seconds: null,
    },
  },
  {
    slug: '05-pending-retrying',
    title: '成绩还在送:第 2 次重试,4:12 后 —— 守卫 2 那一格',
    blocking: {
      game_id: 'g1', state: 'pending_settlement', ownership: 'current_device',
      user_color: 'B', opponent_rank_name: '业余 3 段',
      heartbeat_age_seconds: 11, pending_since_seconds: 486,
      sync: {
        state: 'waiting', attempt: 2, max_attempts: 5, next_attempt_in_seconds: 252,
        last_http_status: null, last_error: 'timeout',
      },
    },
  },
  {
    slug: '06-pending-refused',
    title: '云端在事实上拒收:不给重试按钮',
    blocking: {
      game_id: 'g1', state: 'pending_settlement', ownership: 'current_device',
      user_color: 'B', opponent_rank_name: '业余 3 段',
      heartbeat_age_seconds: 96, pending_since_seconds: 5400,
      sync: {
        state: 'refused', attempt: 1, max_attempts: 5, next_attempt_in_seconds: null,
        last_http_status: 422, last_error: 'HTTP 422: rung mismatch',
      },
    },
  },
];

test.beforeAll(() => mkdirSync(OUT_DIR, { recursive: true }));

for (const testCase of CASES) {
  test(`kiosk 挡局 ${testCase.slug} — ${testCase.title}`, async ({ page }) => {
    await page.setViewportSize(VIEWPORT);
    await stubShell(page);
    await page.route('**/api/v1/ai-ladder/status', (route) => route.fulfill({
      json: readyStatus(testCase.blocking),
    }));

    await page.goto('/kiosk/play/ai/setup/ranked');
    await expect(page.getByTestId('kiosk-ladder-blocking-panel')).toBeVisible();

    const measured = await measure(page);
    assertLoadBearing(measured, testCase.slug);
    // eslint-disable-next-line no-console
    console.log(`[measure] ${testCase.slug} ${JSON.stringify(measured)}`);

    // **事实格里的每一格,都必须是标题读完之后还不知道的事。**
    // 两条一起钉:①不许复读标题;②诊断数真的填上了(加法式字段没有任何东西会红 ——
    // 上一版那两格一直显示「未收到过 / 不适用」,是看图才发现的,不是测试)。
    const facts = await page.getByTestId('kiosk-ladder-blocking-facts').innerText();
    const title = await page.getByTestId('kiosk-ladder-state-line').innerText();
    expect(facts, `${testCase.slug}:事实格复读了标题`).not.toContain(title);
    const blocking = testCase.blocking as { heartbeat_age_seconds?: number | null };
    if (typeof blocking.heartbeat_age_seconds === 'number') {
      expect(facts, `${testCase.slug}:心跳那一格没填上数,fixture 或组件掉了这个字段`)
        .toMatch(/\d+\s*(秒|分钟|小时)前/);
    }

    await page.screenshot({ path: resolve(OUT_DIR, `${testCase.slug}.png`) });
    await page.getByTestId('kiosk-ladder-blocking-panel')
      .screenshot({ path: resolve(OUT_DIR, `${testCase.slug}--panel.png`) });
  });
}

test('内容最多的那一格:叙述装不下时必须真的能滚，而按钮一格都不许被裁', async ({ page }) => {
  // 承重那一关的正题,而「造到会溢出」这一步走了三轮才走对:
  //
  //   · 26 字的档位名在 26px 字号、690px 可用宽度下**正好一行装得下**(实测
  //     nameScrollWidth 690)——「装得下的数据量下量出来的数字一概不算」,那一轮白量;
  //   · 加到 150 字,头部涨到 248px、叙述区被挤到 42px,滚动第一次真的接管(scrollTop 推到 6);
  //   · 加到 300 字,头部涨到 427px —— 头部是 flexShrink:0,于是**动作区被整个推到
  //     y=578..722,底边掉出 600px 视口**,再被右栏的 overflow:hidden 裁掉:屏上只剩一个
  //     读不完的名字,两个按钮一个都不在。这是这条链上的**第二个断点**,量出来才发现的,
  //     修法是把档位名钳成两行(见组件)。
  //
  // 钳住之后档位名再也撑不动头部(实测 78/150/300 字都停在 128px),叙述区也就再没有机会
  // 溢出。所以这里改用**另一条真实的加长途径**把它逼出来:文案全部走 `i18n.t(key, 中文)`,
  // 而 `/api/translations` 是服务端发的 —— 换一门语言,同一句话可以长好几倍。
  // 假的是输入(一份超长译文),读出来的结论仍然是浏览器算的。
  // 12 遍,不是刚好够的那个遍数。**这个数字被改过两次**:6 遍原本刚好溢出 5px,
  // 后来把按钮从 54px 改回骨架的 48px、动作区矮了 10px,叙述区就多出 10px —— 6 遍当场
  // 变成「装得下」,这条测试自己红了(红得对:它量的是「装得下」,数字一概不算)。
  // 所以留足冗余:压力用例**不该**卡在判据边上,否则下一次任何一个几像素的调整都会把它
  // 悄悄变成一个什么都不证明的绿。
  // **这个数字被改过三次**,每次都是布局动了之后压力用例自己失效:
  //   6 遍 → 按钮 54→48px 让叙述区多出 10px ⇒ 变成「装得下」;
  //   12 遍 → 状态描述升为标题、搬出可滚区 ⇒ 又变成「装得下」(可滚区只剩 sync + 错误条)。
  // 两次都是这条测试自己红的(红得对)。所以现在把加长压在**仍然住在可滚区里**的那条
  // 文案上(sync 那一行),并留足冗余 —— 压力用例不该卡在判据边上。
  const longCopy = '这一局已经下完，成绩还没送到云端。'.repeat(12);
  await page.setViewportSize(VIEWPORT);
  await stubShell(page, {
    'ladder:blocking_body_undelivered': longCopy,
    // sync 那一行只加到 4 遍(两行,仍然装得下)—— 它是**必需信息**,把它本身撑到比可视区
    // 还高,就没有任何布局能让它「完整落在静止帧里」,那时红的是构造不是实现。
    'ladder:sync_exhausted': '连试 {max} 次都没送到。恢复联网后会自动继续送。'.repeat(10),
    // 溢出改压在**错误条**上:它是这块可滚区里唯一的非必需元素,而「必需信息留在静止帧、
    // 回执可以滚下去」正是这块屏设计好的降级方式。这样造出来的溢出走的是真实的那条路。
    'Could not end that game, please retry': '结束对局失败，请重试。'.repeat(28),
  });
  await page.route('**/api/v1/ai-ladder/status', (route) => route.fulfill({
    json: readyStatus({
      game_id: 'g1', state: 'pending_settlement', ownership: 'current_device',
      user_color: 'W',
      opponent_rank_name: '智星职业九段·超一流·测试用超长档位名称与更长的后缀·再加一段确保它必须折行'
        + '·还要更长一点才够把头部撑到两行以上·就是这么长',
      sync: {
        state: 'exhausted', attempt: 5, max_attempts: 5, next_attempt_in_seconds: null,
        last_http_status: 503, last_error: 'HTTP 503: upstream unavailable',
      },
    }),
  }));
  await page.route('**/api/v1/ai-ladder/games/*/end', (route) => route.fulfill({
    status: 500, json: { detail: 'boom' },
  }));

  await page.goto('/kiosk/play/ai/setup/ranked');
  await expect(page.getByTestId('kiosk-ladder-blocking-panel')).toBeVisible();

  // 再把错误条造出来:按一次认输并确认,让 500 落到面板上。
  await page.getByRole('button', { name: '认输那一局，在这里开新局' }).click();
  await page.getByRole('button', { name: '确认认输' }).click();
  await expect(page.getByRole('alert')).toBeVisible();

  const measured = await measure(page);
  // eslint-disable-next-line no-console
  console.log(`[measure] overflow-worst-case ${JSON.stringify(measured)}`);
  assertLoadBearing(measured, 'overflow-worst-case');

  expect(
    measured.bodyScrollHeight,
    '这一格没有造出溢出 —— 那量的是「装得下」，数字一概不算，得再加内容',
  ).toBeGreaterThan(measured.bodyClientHeight);
  expect(['auto', 'scroll']).toContain(measured.bodyOverflowY);
  expect(
    measured.bodyScrolledTo,
    '声明了 overflow-y:auto，但 scrollTop 推不动 —— 那就是裁切，不是滚动',
  ).toBeGreaterThan(0);

  await page.screenshot({ path: resolve(OUT_DIR, '07-overflow-worst-case.png') });
  await page.getByTestId('kiosk-ladder-blocking-panel')
    .screenshot({ path: resolve(OUT_DIR, '07-overflow-worst-case--panel.png') });
});

test('只在出错时才出现的那一格:真实文案 + 错误条,专门造出来量', async ({ page }) => {
  // **凡是「只在出错时出现」的界面,取图和承重都必须专门造。** 它最容易漏(走顺利那条路
  // 永远撞不到),又往往最紧 —— 错误提示总是加在一块已经排满的屏上。
  //
  // 上面那条最坏格用的是 12 倍长译文,量的是压力;这一条用**真实文案**,量的是这块屏在
  // 生产里真会遇到的那个错误态。两条都要:一条问「极端下会不会塌」,一条问「常态下够不够」。
  await page.setViewportSize(VIEWPORT);
  await stubShell(page);
  await page.route('**/api/v1/ai-ladder/status', (route) => route.fulfill({
    json: readyStatus({
      game_id: 'g1', state: 'pending_settlement', ownership: 'current_device',
      user_color: 'B', opponent_rank_name: '业余 3 段',
      heartbeat_age_seconds: 34, pending_since_seconds: 1260,
      sync: {
        state: 'exhausted', attempt: 5, max_attempts: 5, next_attempt_in_seconds: null,
        last_http_status: null, last_error: 'connection refused',
      },
    }),
  }));
  await page.route('**/api/v1/ai-ladder/games/*/end', (route) => route.fulfill({
    status: 500, json: { detail: 'boom' },
  }));

  await page.goto('/kiosk/play/ai/setup/ranked');
  await expect(page.getByTestId('kiosk-ladder-blocking-panel')).toBeVisible();
  await page.getByRole('button', { name: '认输那一局，在这里开新局' }).click();
  await page.getByRole('button', { name: '确认认输' }).click();
  await expect(page.getByRole('alert')).toBeVisible();

  const measured = await measure(page);
  // eslint-disable-next-line no-console
  console.log(`[measure] error-state-realistic ${JSON.stringify(measured)}`);
  assertLoadBearing(measured, 'error-state-realistic');
  // 真实文案下错误条必须**整条**落在静止帧里 —— 这一格没有「压力」可以拿来解释。
  expect(
    measured.alertSlackPx,
    `真实文案下错误条底边就已经越过裁切线(${measured.alertSlackPx}px) —— `
    + '这不是压力测试,这是生产里按一次认输失败就会看到的那一帧',
  ).toBeGreaterThanOrEqual(0);
  // 两条出路仍然都在,且都按得下(守卫 2 的边界:失败不许把出口一起关掉)。
  await expect(page.getByRole('button', { name: '立即重试' })).toBeEnabled();
  await expect(page.getByRole('button', { name: '认输那一局，在这里开新局' })).toBeEnabled();

  await page.screenshot({ path: resolve(OUT_DIR, '10-error-state-realistic.png') });
  await page.getByTestId('kiosk-ladder-blocking-panel')
    .screenshot({ path: resolve(OUT_DIR, '10-error-state-realistic--panel.png') });
});

test('档位名再长,按钮也不许被挤出视口 —— 头部两行封顶', async ({ page }) => {
  // 上面那条修出来的不变式,单独钉一颗钉子:`opponent_rank_name` 是服务端发下来的字符串,
  // 前端不设界。目录里的名字都很短(「5级」「准3段」),但**界不该由数据来守** ——
  // 那正是「同一条链上可以有不止一处断点」的样子:叙述区那处已经通了,头部这处还没有。
  await page.setViewportSize(VIEWPORT);
  await stubShell(page);
  await page.route('**/api/v1/ai-ladder/status', (route) => route.fulfill({
    json: readyStatus({
      game_id: 'g1', state: 'pending_settlement', ownership: 'current_device',
      user_color: 'W', opponent_rank_name: '智'.repeat(300),
      sync: {
        state: 'exhausted', attempt: 5, max_attempts: 5, next_attempt_in_seconds: null,
        last_http_status: 503, last_error: 'x',
      },
    }),
  }));

  await page.goto('/kiosk/play/ai/setup/ranked');
  await expect(page.getByTestId('kiosk-ladder-blocking-panel')).toBeVisible();

  const measured = await measure(page);
  // eslint-disable-next-line no-console
  console.log(`[measure] runaway-rank-name ${JSON.stringify(measured)}`);
  assertLoadBearing(measured, 'runaway-rank-name');
  // 名字**自己被裁**,而不是让它去裁掉按钮。重设计之后裁的轴变了:从前它是标题、
  // 两行封顶(纵向裁),现在它是事实格里的一行值、`text-overflow: ellipsis`(横向裁)。
  // 判据跟着轴走 —— 实测 `nameScrollWidth 3900` vs `nameClientWidth 302`。
  // (这一条是 `min-width: 0` 修好之后才成立的:grid 子项默认 `min-width: auto`,
  //  格子拒绝收缩到内容宽度以下,省略号永远没机会生效,那时两个数都是 3900。)
  expect(
    measured.nameScrollWidth,
    '档位名没有被省略号截断 —— 格子被它撑开了,`min-width: 0` 没生效',
  ).toBeGreaterThan(measured.nameClientWidth);
  expect(measured.nameClientWidth).toBeLessThanOrEqual(measured.columnClientWidth);
  expect(measured.headerHeight).toBeLessThan(measured.panelClientHeight / 2);

  await page.screenshot({ path: resolve(OUT_DIR, '09-runaway-rank-name.png') });
});

test.describe('装配层:从页面按下去,真的有一次请求打出去', () => {
  // **守卫要写在装配层,判据是「真的有一次请求打出去了」,不是「回调被调用了」。**
  //
  // 象棋踩的是比「吞了错误」更靠外一层的洞:那个按钮**根本没接线** —— 装配层从来没把回调
  // 传给屏,可选调用静默什么都不做,前五层全绿。**屏级测试看不见这一层**,因为它自己传了
  // 一个 mock 进去,于是「按钮会调回调」永远是绿的。
  //
  // 这里在真浏览器里从 `/kiosk/play/ai/setup/ranked` 出发,拦网络看请求。回调被没被调用
  // 一概不问 —— 问的是网线上有没有那一条 POST。
  for (const [slug, label, confirm, state] of [
    ['reserved', '让掉它，在这里开新局', '确认让掉', 'reserved'],
    ['active', '认输那一局，在这里开新局', '确认认输', 'active'],
  ] as const) {
    test(`装配层 ${slug}:按下去 → 确认 → POST /end 真的发出去`, async ({ page }) => {
      await page.setViewportSize(VIEWPORT);
      await stubShell(page);
      await page.route('**/api/v1/ai-ladder/status', (route) => route.fulfill({
        json: readyStatus({
          game_id: 'assembly-game', state, ownership: 'other_device',
          user_color: 'B', opponent_rank_name: '业余 3 段',
        }),
      }));
      const sent: string[] = [];
      await page.route('**/api/v1/ai-ladder/games/*/end', async (route, request) => {
        sent.push(`${request.method()} ${new URL(request.url()).pathname} ${request.postData() ?? ''}`);
        await route.fulfill({
          json: state === 'reserved'
            ? { state: 'released', game_id: 'assembly-game', counted: false }
            : { state: 'settled', game_id: 'assembly-game', receipt: { counted: true, reason: null } },
        });
      });

      await page.goto('/kiosk/play/ai/setup/ranked');
      await page.getByRole('button', { name: label }).click();
      await page.getByRole('button', { name: confirm }).click();
      await expect.poll(() => sent.length, { timeout: 5_000 }).toBe(1);

      expect(sent[0]).toBe(
        'POST /api/v1/ai-ladder/games/assembly-game/end {"reason":"user_resigned"}',
      );
    });
  }
});

test('让掉那一格的二次确认:标题、正文、确认按钮里一个「记为本局负」都没有', async ({ page }) => {
  // 组件测试已经断言过同一件事,这里再量一遍是因为**弹窗是另一层盒子**:
  // MUI 的 Dialog 挂在 body 上,不在那条 overflow:hidden 的链里,1024×600 上它自己
  // 会不会顶出视口、按钮会不会被裁,只有真浏览器答得了。
  await page.setViewportSize(VIEWPORT);
  await stubShell(page);
  await page.route('**/api/v1/ai-ladder/status', (route) => route.fulfill({
    json: readyStatus({
      game_id: 'g1', state: 'reserved', ownership: 'other_device',
      user_color: 'B', opponent_rank_name: '智星职业九段·超一流·测试用超长档位名称与更长的后缀',
    }),
  }));

  await page.goto('/kiosk/play/ai/setup/ranked');
  await page.getByRole('button', { name: '让掉它，在这里开新局' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();

  const dialogBox = await dialog.evaluate((node) => {
    const rect = node.getBoundingClientRect();
    const confirm = Array.from(node.querySelectorAll('button'))
      .find((button) => button.textContent?.includes('确认让掉'))!;
    const confirmRect = confirm.getBoundingClientRect();
    return {
      top: Math.round(rect.top),
      bottom: Math.round(rect.bottom),
      confirmBottom: Math.round(confirmRect.bottom),
      confirmHeight: Math.round(confirmRect.height),
      innerHeight: window.innerHeight,
      text: document.body.innerText,
    };
  });

  expect(dialogBox.top).toBeGreaterThanOrEqual(0);
  expect(dialogBox.confirmBottom).toBeLessThanOrEqual(dialogBox.innerHeight);
  // 触屏最小可点尺寸。按不准的确认按钮在 7 寸屏上等于没有。
  expect(dialogBox.confirmHeight).toBeGreaterThanOrEqual(40);
  expect(dialogBox.text).not.toMatch(/记为本局负|计为本局负|计入升降级/);
  // eslint-disable-next-line no-console
  console.log(`[measure] release-dialog ${JSON.stringify({ ...dialogBox, text: undefined })}`);

  await page.screenshot({ path: resolve(OUT_DIR, '08-release-dialog.png') });
});
