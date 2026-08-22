import { expect, test, type Page } from '@playwright/test';

/**
 * 屏 02 · 对局中(§11 **布局 A**)—— 真浏览器 1024×600 实测。
 *
 * 这一条守三样,都是**浏览器算出来的数**,jsdom 一条都作不了证:
 *   ① 骨架:盘 516×516 贴 (16,70)、右栏 460、页控条 460×44@y70、返回键 36。
 *   ② 刻度带的字心 = **屏上那条线的横坐标**。这一屏的盘是 `<canvas>`,
 *      所以线的位置**从像素里读**,不从公式里读 —— 判据是屏上那条线,
 *      不是「字心应该落在 (i+0.5)/N」那个版式规则(拿后者当判据会「数字漂亮、结论全假」)。
 *   ③ 承重:整屏不滚、右栏不滚;折叠块收起后**动作区一动不动**、标题行右端那个结论**还在**。
 *
 * 另外两条是「禁的时候整块不渲染」:升降级局里胜率块和「图表」键**一个都不许出现**,
 * 不许渲成灰的或者一条全 `—` 的空图。
 */

/**
 * ⚠️ **屏号 05 不是 02。** 计划书里这一屏写作「屏 02」,那是十屏稿的编号;
 * 稿子 2026-08-21 扩到 27 屏后,对局中是第 5 屏(参考图 `sample-go/shots/05-game.png`)。
 */

test.use({ viewport: { width: 1024, height: 600 } });

const COLS = 'ABCDEFGHJKLMNOPQRST';
const xy = (c: string): [number, number] => [COLS.indexOf(c[0]), Number(c.slice(1)) - 1];

const BLACK = ['Q16', 'Q4', 'C14', 'C11', 'Q6', 'Q10', 'K17', 'C7', 'C5', 'D8', 'R14', 'M16'];
const WHITE = ['D4', 'D16', 'C16', 'O3', 'L3', 'F17', 'G3', 'D6', 'C4', 'F5', 'N17', 'P17'];

/** 25 手的胜率/目差:第 17 手黑走坏,两条线一起掉(和稿子那张图说的是同一局)。 */
const HISTORY = Array.from({ length: 25 }, (_, i) => ({
  node_id: i,
  winrate: i < 17 ? 0.5 - i * 0.004 : 0.5 - 17 * 0.004 - (i - 16) * 0.012,
  score: i < 17 ? -i * 0.12 : -17 * 0.12 - (i - 16) * 0.55,
}));

// `calculated_rank` 是**内部数值**,不是 `'5k'` 这种字符串:0 → 1 级、−4 → 5 级、1 → 1 段。
// 上一版这里写了 `'5k'`,屏上画出来是「**5 段**」—— `internalToRank` 里那句
// 「Fallback if it's already a rank string like "20k"」**从来没生效过**:
// `parseInt('5k', 10)` = 5,不是 NaN,于是直接走了段位分支。
// 后端给的一直是数值(`base_katrain.py:178` 的 `ai_rank_estimation`),所以那个坑是**休眠**的;
// 但拿字符串造 fixture 会把它叫醒,而叫醒之后错的是**图**,不是代码。已登记,不在本 Task 修。
const seat = (name: string, type: string, rank: number | string) => ({
  player_type: type, player_subtype: '', name, calculated_rank: rank, periods_used: 0, main_time_used: 0,
});

const stateFor = (gameType: string) => ({
  game_id: 'g-02',
  board_size: [19, 19],
  komi: 6.5,
  handicap: 0,
  ruleset: 'chinese',
  game_type: gameType,
  count_min_moves: 100,
  current_node_id: 24,
  current_node_index: 24,
  history: HISTORY,
  player_to_move: 'B',
  stones: [
    ...BLACK.map((c, i) => ['B', xy(c), null, i * 2 + 1]),
    ...WHITE.map((c, i) => ['W', xy(c), null, i * 2 + 2]),
  ],
  last_move: xy('P17'),
  prisoner_count: { B: 0, W: 0 },
  analysis: null,
  commentary: '',
  is_root: false,
  is_pass: false,
  end_result: null,
  children: [],
  ghost_stones: [],
  players_info: {
    B: seat('访客（你）', 'player:human', ''),
    W: seat('KataGo', 'player:ai', -4),
  },
  note: '',
  ui_state: {
    show_children: false, show_dots: false, show_hints: false, show_policy: false,
    show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false,
  },
});

const stub = async (page: Page, gameType = 'free') => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'screen-02');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/state**', (route) => route.fulfill({ json: { state: stateFor(gameType) } }));
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') {
      return route.fulfill({ json: { id: 1, username: '访客', rank: '5段', credits: 0 } });
    }
    // 取图机器上没有摄像头 —— 让实体识别整条关掉,这一屏就退成纯触屏,和硬件无关。
    if (path === '/api/v1/vision/status') {
      return route.fulfill({ json: { enabled: false, camera_connected: false, pose_locked: false,
        sync_state: 'unbound', recognition_ready: false, led_connected: null, bound_session_id: null } });
    }
    if (path === '/api/v1/geometry/status') {
      return route.fulfill({ status: 404, json: { detail: 'geometry disabled' } });
    }
    return route.fulfill({ json: {} });
  });
};

const open = async (page: Page, gameType = 'free', route = '/kiosk/play/ai/game/g-02') => {
  await stub(page, gameType);
  await page.goto(route);
  await page.waitForSelector('[data-testid="game-board"] canvas');
  // 「图表」默认开着,但那块要等 history 到位才画得出线
  await page.waitForLoadState('networkidle');
};

const geometry = (page: Page) => page.evaluate(() => {
  const box = (sel: string) => {
    const n = document.querySelector(sel) as HTMLElement | null;
    if (!n) return null;
    const r = n.getBoundingClientRect();
    return {
      x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
      right: Math.round(r.right), bottom: Math.round(r.bottom),
    };
  };
  const rail = document.querySelector('.kiosk-rail') as HTMLElement;
  return {
    board: box('[data-testid="game-board"]'),
    play: box('[data-testid="game-board"] .kiosk-board__play'),
    canvas: box('[data-testid="game-board"] canvas'),
    rail: box('.kiosk-rail'),
    pagebar: box('[data-testid="game-pagebar"]'),
    back: box('.kiosk-pagebar__back'),
    actions: box('[data-testid="game-actions"]'),
    canvasAttrW: (document.querySelector('[data-testid="game-board"] canvas') as HTMLCanvasElement).width,
    railScrolls: rail.scrollHeight - rail.clientHeight,
    docScrollWidth: document.documentElement.scrollWidth,
    docScrollHeight: document.documentElement.scrollHeight,
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
  };
});

test('布局 A 的外框:516 的盘贴 (16,70),右栏 460,页控条在右栏顶', async ({ page }) => {
  await open(page);
  const g = await geometry(page);
  console.log('[02-game/geometry]', JSON.stringify(g));

  expect(g.board!.w, '盘不是 516 宽').toBe(516);
  expect(g.board!.h, '盘不是 516 高').toBe(516);
  expect(g.board!.x, '盘没有贴 x=16').toBe(16);
  expect(g.board!.y, '盘顶不在 y=70').toBe(70);

  // 落子区 = 516 − 2×28(四条刻度带画在框内,不额外占外部空间)
  expect(g.play!.w, '落子区不是 460').toBe(460);
  expect(g.play!.h, '落子区不是 460').toBe(460);
  expect(g.play!.x - g.board!.x, '左刻度带不是 28 宽').toBe(28);

  expect(g.rail!.w, '右栏不是 460 宽').toBe(460);
  expect(g.rail!.x - g.board!.right, '盘和右栏之间不是 16 的栏距').toBe(16);
  expect(g.rail!.right, '右栏右缘没贴到 1008').toBe(g.innerWidth - 16);

  expect(g.pagebar!.x, '页控条左缘没和右栏对齐 —— 那是布局 B 的做法').toBe(g.rail!.x);
  expect(g.pagebar!.w, '页控条不是 460 宽').toBe(g.rail!.w);
  expect(g.pagebar!.y, '页控条顶不在 70').toBe(70);
  expect(g.pagebar!.h, '页控条不是 44 高').toBe(44);
  expect(g.back!.h, '返回按钮不是 36 高').toBe(36);

  expect(g.docScrollWidth, '页面横向溢出').toBeLessThanOrEqual(g.innerWidth);
  expect(g.docScrollHeight, '页面纵向溢出 —— L3 布局 A 整屏不滚是首选形态').toBeLessThanOrEqual(g.innerHeight);
});

test('刻度带的字心 = 屏上那条线的横坐标(externalRulers 三件事一起成立才有的结果)', async ({ page }) => {
  await open(page);

  const m = await page.evaluate(() => {
    const canvas = document.querySelector('[data-testid="game-board"] canvas') as HTMLCanvasElement;
    const ctx = canvas.getContext('2d')!;
    // 从**像素**里读竖线的位置:横着切一刀(取 40% 高,避开中间那条星位密集带),
    // 找亮度的局部极小 —— 线是深色的 `--gb-line`,画在浅木底上。
    const y = Math.round(canvas.height * 0.4);
    const row = ctx.getImageData(0, y, canvas.width, 1).data;
    const lum = new Float64Array(canvas.width);
    for (let x = 0; x < canvas.width; x += 1) {
      lum[x] = 0.299 * row[x * 4] + 0.587 * row[x * 4 + 1] + 0.114 * row[x * 4 + 2];
    }
    const dips: number[] = [];
    for (let x = 3; x < canvas.width - 3; x += 1) {
      // 比左右各 3px 都暗 8 以上 ⇒ 一条线;连着几个像素时取其中最暗的那个
      if (lum[x] + 8 < lum[x - 3] && lum[x] + 8 < lum[x + 3]
        && lum[x] <= lum[x - 1] && lum[x] <= lum[x + 1]) {
        if (dips.length && x - dips[dips.length - 1] < 6) {
          if (lum[x] < lum[dips[dips.length - 1]]) dips[dips.length - 1] = x;
        } else dips.push(x);
      }
    }
    const cRect = canvas.getBoundingClientRect();
    // canvas 的 CSS 尺寸可能≠位图尺寸,换算回屏幕坐标
    const k = cRect.width / canvas.width;
    const lineCenters = dips.map((x) => cRect.x + (x + 0.5) * k);
    const rulerCenters = Array.from(document.querySelectorAll('[data-testid="game-board"] .kiosk-board__ruler--top span'))
      .map((s) => { const r = s.getBoundingClientRect(); return r.x + r.width / 2; });
    const drift = lineCenters.length === rulerCenters.length
      ? Math.max(...lineCenters.map((c, i) => Math.abs(c - rulerCenters[i])))
      : null;
    return {
      lineCount: lineCenters.length,
      rulerCount: rulerCenters.length,
      maxDriftPx: drift === null ? null : Math.round(drift * 100) / 100,
      // canvas 位图必须**正好等于**落子区:−8 的内边距或 floor 的格距都会在这儿露出来
      canvasBitmapW: canvas.width,
      canvasCssW: Math.round(cRect.width),
      playW: Math.round((document.querySelector('[data-testid="game-board"] .kiosk-board__play') as HTMLElement).getBoundingClientRect().width),
      topFirst: document.querySelector('[data-testid="game-board"] .kiosk-board__ruler--top span')?.textContent,
      topLast: document.querySelector('[data-testid="game-board"] .kiosk-board__ruler--top span:last-child')?.textContent,
      leftFirst: document.querySelector('[data-testid="game-board"] .kiosk-board__ruler--left span')?.textContent,
      leftLast: document.querySelector('[data-testid="game-board"] .kiosk-board__ruler--left span:last-child')?.textContent,
    };
  });
  console.log('[02-game/ruler]', JSON.stringify(m));

  expect(m.canvasBitmapW, 'canvas 位图没有铺满落子区 —— `externalRulers` 的第 ② 件事没生效').toBe(m.playW);
  expect(m.canvasCssW, 'canvas 的 CSS 宽没铺满落子区').toBe(m.playW);

  expect(m.rulerCount, '上刻度不是 19 个字').toBe(19);
  expect(m.topFirst).toBe('A');
  expect(m.topLast, '跳 I 之后 19 路正好到 T').toBe('T');
  expect(m.leftFirst, '行号 1 在最下 ⇒ 从上往下第一个是 19').toBe('19');
  expect(m.leftLast).toBe('1');

  expect(m.lineCount, `从像素里只数出 ${m.lineCount} 条竖线`).toBe(19);
  // 门槛 1.5px:亚像素舍入允许,一个字宽的偏差不允许。
  // margin 从 0.5 改回 1.5 时这个数会跳到 ≈24(整整一格),floor 格距时跳到 ≈2。
  expect(m.maxDriftPx, `字和线最大错开 ${m.maxDriftPx}px`).not.toBeNull();
  expect(m.maxDriftPx!).toBeLessThanOrEqual(1.5);
});

test('承重:右栏不滚;收起胜率块动作区一动不动,标题行右端那个结论还在', async ({ page }) => {
  await open(page);

  const before = await page.evaluate(() => {
    const acts = document.querySelector('[data-testid="game-actions"]')!.getBoundingClientRect();
    const rail = document.querySelector('.kiosk-rail') as HTMLElement;
    return {
      actionsBottom: Math.round(acts.bottom),
      railBottom: Math.round(rail.getBoundingClientRect().bottom),
      railOverflow: rail.scrollHeight - rail.clientHeight,
      foldValue: document.querySelector('.kiosk-fold[data-fold="eval"] .kiosk-fold__head b')?.textContent ?? null,
      graphVisible: !!document.querySelector('.kiosk-fold[data-fold="eval"] [data-eval]'),
      wrLine: !!document.querySelector('.kiosk-eval__plot polyline.wr'),
      slLine: !!document.querySelector('.kiosk-eval__plot polyline.sl'),
    };
  });
  console.log('[02-game/fold-before]', JSON.stringify(before));

  expect(before.railOverflow, '右栏装不下,溢出了').toBeLessThanOrEqual(0);
  expect(before.actionsBottom, '动作区没有贴右栏底').toBe(before.railBottom);
  expect(before.graphVisible, '胜率图没画出来').toBe(true);
  expect(before.wrLine, '绿线(胜率)没画').toBe(true);
  expect(before.slLine, '橙线(目差)没画 —— 围棋这块是双轴,少一条就只剩一半').toBe(true);
  expect(before.foldValue, '标题行右端没有当前值').toBeTruthy();
  expect(before.foldValue, '当前值应当是「黑 xx.x% · 白 +x.x 目」这种结论').toContain('%');

  await page.click('.kiosk-fold[data-fold="eval"] .kiosk-fold__head');

  const after = await page.evaluate(() => {
    const acts = document.querySelector('[data-testid="game-actions"]')!.getBoundingClientRect();
    return {
      open: document.querySelector('.kiosk-fold[data-fold="eval"]')?.getAttribute('data-open'),
      actionsBottom: Math.round(acts.bottom),
      foldValue: document.querySelector('.kiosk-fold[data-fold="eval"] .kiosk-fold__head b')?.textContent ?? null,
      // 明细真的收了:body 的高度归零(`display:none`)
      bodyH: Math.round((document.querySelector('.kiosk-fold[data-fold="eval"] .kiosk-fold__body') as HTMLElement).getBoundingClientRect().height),
      headH: Math.round((document.querySelector('.kiosk-fold[data-fold="eval"] .kiosk-fold__head') as HTMLElement).getBoundingClientRect().height),
      foldH: Math.round((document.querySelector('.kiosk-fold[data-fold="eval"]') as HTMLElement).getBoundingClientRect().height),
    };
  });
  console.log('[02-game/fold-after]', JSON.stringify(after));

  expect(after.open).toBe('false');
  expect(after.bodyH, '收起了但明细还占着高度').toBe(0);
  // 收起后整块 = 标题行 30 + 上下各 1px 描边 = 32。稿子那本账里胜率块记的是 **128**
  // (30 + 96 + 2),不是 126 —— 描边在 `border-box` 下也占地方。
  expect(after.headH, '标题行不是 30 高(--fold-head-h)').toBe(30);
  expect(after.foldH, '收起后整块应当就剩标题行 + 上下描边').toBe(after.headH + 2);
  // §11 第 2 条:**收起的是明细不是结论**
  expect(after.foldValue, '收起之后标题行右端那个当前值也跟着没了').toBe(before.foldValue);
  // §11 第 4 条:腾出的空白落在动作区**上面**,按钮不许跟着上移
  expect(after.actionsBottom, '收个面板就把悔棋/认输挪走了 —— 那是肌肉记忆').toBe(before.actionsBottom);
});

test('认输是这一排里唯一的红:求得出值,且和兄弟键不同色', async ({ page }) => {
  await open(page);

  const colors = await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('[data-testid="game-actions"] button')) as HTMLElement[];
    const resign = btns.find((b) => b.textContent?.includes('认输'))!;
    const pass = btns.find((b) => b.textContent?.includes('停一手'))!;
    const cs = (e: HTMLElement) => {
      const s = getComputedStyle(e);
      return { color: s.color, border: s.borderTopColor, bg: s.backgroundColor };
    };
    return { count: btns.length, resign: cs(resign), pass: cs(pass) };
  });
  console.log('[02-game/danger]', JSON.stringify(colors));

  expect(colors.count, '自由对弈屏应当是七个键').toBe(7);
  // 「求得出值」这一条不是形式:`--bad` 定义在 `.kiosk` 上,一旦这一排渲染到 `.kiosk` 外面
  // (比如 MUI 的 portal 里),`var(--bad)` 会解析成 `rgba(0,0,0,0)` —— **看起来就是没红**。
  expect(colors.resign.color, '认输的字色求不出值').not.toBe('rgba(0, 0, 0, 0)');
  expect(colors.resign.border, '认输的描边求不出值').not.toBe('rgba(0, 0, 0, 0)');
  expect(colors.resign.color, '认输和停一手一个色 —— 那条 danger 规则没生效').not.toBe(colors.pass.color);
  // 描边+字色,**不是实心红**:52 的格子里实心红会把整排的视觉重心拉到最危险那个键上
  expect(colors.resign.bg, '认输被做成了实心红').toBe(colors.pass.bg);

  // 确认框在 MUI 的 portal 里(`.kiosk` 外面)—— 它那颗确认键也要求得出值
  await page.click('[data-testid="game-actions"] button:has-text("认输")');
  await page.waitForSelector('text=确认认输？');
  const confirm = await page.evaluate(() => {
    const dlg = Array.from(document.querySelectorAll('[role="dialog"]'))
      .find((d) => d.textContent?.includes('确认认输？'))!;
    const btn = Array.from(dlg.querySelectorAll('button')).find((b) => b.textContent?.includes('认输'))! as HTMLElement;
    const s = getComputedStyle(btn);
    return { inKiosk: !!btn.closest('.kiosk'), color: s.color };
  });
  console.log('[02-game/danger-confirm]', JSON.stringify(confirm));
  expect(confirm.color, '确认框里那颗认输键的字色求不出值').not.toBe('rgba(0, 0, 0, 0)');
});

test('升降级局:胜率块和「图表」键**一个都不渲染**,不是灰的也不是一条全 — 的空图', async ({ page }) => {
  await open(page, 'ai_ladder_ranked');

  const g = await page.evaluate(() => ({
    hasFold: !!document.querySelector('.kiosk-fold[data-fold="eval"]'),
    hasEval: !!document.querySelector('.kiosk-eval'),
    hasPlot: !!document.querySelector('[data-eval]'),
    labels: Array.from(document.querySelectorAll('[data-testid="game-actions"] button')).map((b) => b.textContent?.trim()),
    actionsBottom: Math.round(document.querySelector('[data-testid="game-actions"]')!.getBoundingClientRect().bottom),
    railBottom: Math.round(document.querySelector('.kiosk-rail')!.getBoundingClientRect().bottom),
    railOverflow: (() => { const r = document.querySelector('.kiosk-rail') as HTMLElement; return r.scrollHeight - r.clientHeight; })(),
    title: document.querySelector('.kiosk-pagebar__title')?.firstChild?.textContent ?? null,
  }));
  console.log('[02-game/ranked]', JSON.stringify(g));

  expect(g.hasFold, '升降级局里胜率折叠块还在').toBe(false);
  expect(g.hasEval, '升降级局里胜率块还在').toBe(false);
  expect(g.hasPlot, '升降级局里那张图还在').toBe(false);
  expect(g.labels, '升降级局里还有「图表」键').not.toContain('图表');
  // 悔棋在升降级局里后端本来就拒(反作弊),界面也不摆
  expect(g.labels, '升降级局里还有「悔棋」键').not.toContain('悔棋');
  expect(g.title, '页控条标题没说这是升降级局').toBe('升降级对弈');
  // 少了一块之后动作区照旧贴底,右栏照旧不滚
  expect(g.actionsBottom).toBe(g.railBottom);
  expect(g.railOverflow).toBeLessThanOrEqual(0);
});

// ── 屏 10 · 星阵人机 —— **同一个 `GamePage`**,`engineMode` 只换右栏 ─────────────────
// 单独量一遍是因为右栏换了内容就换了一本账:三个道具键(52)顶掉了胜率块(128),
// 而「动作区贴底」「右栏不滚」两条对两屏都成立。两屏共用一个组件 ⇒ 改一屏必然动另一屏,
// 只量一屏等于**只证了一半**。
test('星阵人机屏:道具键在、胜率块不在,动作区照旧贴底且不滚', async ({ page }) => {
  await open(page, 'free', '/kiosk/play/cross-platform/engine/game/g-02');

  const g = await page.evaluate(() => ({
    items: Array.from(document.querySelectorAll('.items button')).map((b) => b.lastChild?.textContent?.trim()),
    badges: Array.from(document.querySelectorAll('.items .cnt')).map((b) => b.textContent?.trim()),
    hasEval: !!document.querySelector('.kiosk-fold[data-fold="eval"]'),
    actionLabels: Array.from(document.querySelectorAll('[data-testid="game-actions"] button')).map((b) => b.textContent?.trim()),
    actionsBottom: Math.round(document.querySelector('[data-testid="game-actions"]')!.getBoundingClientRect().bottom),
    railBottom: Math.round(document.querySelector('.kiosk-rail')!.getBoundingClientRect().bottom),
    railOverflow: (() => { const r = document.querySelector('.kiosk-rail') as HTMLElement; return r.scrollHeight - r.clientHeight; })(),
    title: document.querySelector('.kiosk-pagebar__title')?.firstChild?.textContent ?? null,
    docScrollHeight: document.documentElement.scrollHeight,
  }));
  console.log('[10-platform-game]', JSON.stringify(g));

  expect(g.items, '三个道具键(领地/支招/变化图)不全').toEqual(['领地', '支招', '变化图']);
  // `—` = **这一次没取到数**,和 `0`(用完了)不是一回事。取图机器上接口是空桩,所以是 `—`。
  expect(g.badges).toEqual(['—', '—', '—']);
  expect(g.hasEval, '星阵局里不该有胜率块 —— 那一屏没有图表键').toBe(false);
  expect(g.actionLabels, '星阵局的动作区不是四个键').toEqual(['悔棋', '停一手', '数子', '认输']);
  expect(g.actionsBottom, '动作区没贴右栏底').toBe(g.railBottom);
  expect(g.railOverflow, '右栏溢出').toBeLessThanOrEqual(0);
  expect(g.docScrollHeight, '整屏溢出').toBeLessThanOrEqual(600);
  expect(g.title).toBe('星阵围棋 · 人机');
});
