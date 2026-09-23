import { expect, test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';
import { scopedKey, kioskMeJson } from './helpers/kioskIdentity';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = (slug: string) => resolve(process.cwd(),
  `../../../superpowers/tracks/kiosk-go-shell-align/visual/${slug}/1024x600`);

/**
 * 屏 17 摆谱 · 进行中(L2 布局 A:盘 516 + 16 + 右栏 460),五帧:
 *  17 摄像头在看(等下一手)/ 17a 放错了、把盘面摆对 / 17b 试下 / 17c AI 支招 / 17d 摄像头用不了(手动兜底)。
 *
 * 2026-09-23 Fan:「不要每走一步都要按屏幕上的确认键……应该使用摄像头确认」。摄像头态的五帧都**不点确认键**:
 * `/ws/vision` 由 `page.routeWebSocket` 接管,每一手发一条 `move_confirmed` —— 和人在实体盘上摆一颗、
 * 摄像头认到是同一个事件。`setup-mode` 的 POST 回一条 `setup_complete`(盘面对上了);17a 那一帧不回。
 * **采集态不取四图**(只在 `--baipu-collect` 起的采集机上出现)。
 *
 * 预期差异(不是没对齐):
 *  · 顶栏「访客」—— 稿子的占位用户名;这里 `/me` 也给了「访客」,但顶栏样式随登录态走。
 *  · 支招键写「AI支招」(无空格)—— 与对弈页同一个 key `Hints`,Fan 要的是「和对弈页对齐」;稿子写成「AI 支招」。
 *  · 玩家卡两张删了 —— 摆谱**没有人在下棋**,名字进页控条标题(2026-08-24 裁定,稿子同)。
 */

/** 稿子那 12 手,换成后端 `steps[]`(row 从上往下数)。 */
const MOVES: [number, number, 'B' | 'W'][] = [
  [3, 15, 'B'], [3, 3, 'W'],      // Q16 D16
  [15, 3, 'B'], [15, 15, 'W'],    // D4  Q4
  [9, 15, 'B'], [5, 16, 'W'],     // Q10 R14
  [5, 2, 'B'], [2, 5, 'W'],       // C14 F17
  [12, 16, 'B'], [12, 15, 'W'],   // R7  Q7
  [2, 4, 'B'], [9, 3, 'W'],       // E17 D10
];

const STEPS = {
  board_size: 19,
  meta: { player_black: '申真谞', player_white: '柯洁', handicap: 0, komi: 6.5, ruleset: 'chinese' },
  steps: [
    ...MOVES.map(([row, col, color], i) => ({
      kind: 'move', move_index: i, property: color, row, col, color, removed: [], board_hash: `h${i}`,
    })),
    // 第 13 手 = 稿子那个待摆点 C7(row 12, col 2)
    { kind: 'move', move_index: 12, property: 'B', row: 12, col: 2, color: 'B', removed: [], board_hash: 'h12' },
    // 后面再补一批,好让「共 241」那类分母不是 13(这一屏的分母要真)
    ...Array.from({ length: 228 }, (_, i) => ({
      kind: 'move', move_index: 13 + i, property: i % 2 === 0 ? 'W' : 'B',
      row: 7 + (i % 5), col: 7 + Math.floor(i / 5) % 5, color: i % 2 === 0 ? 'W' : 'B',
      removed: [], board_hash: `t${i}`,
    })),
  ],
};

/** 摄像头那一头:谁连上了 `/ws/vision`、识别层现在布没布臂、setup 要不要自动对上。 */
interface Vision {
  send: (type: string, data?: Record<string, unknown>) => void;
  /** 最近一次 `move-detection` 的 armed —— 等到 true 才算进了「等下一手」,那之前发的落子会被丢掉。 */
  armed: boolean;
  /** `setup-mode` 之后自动回 `setup_complete`(盘面对上了)。17a 关掉它。 */
  autoComplete: boolean;
}

/**
 * `camera`:视觉服务就绪与否。`geometry`:几何这次开机确认过没有 —— 摄像头态要两个都真;
 * 17d 取「视觉在、几何没确认」那一种,正是稿子画的「棋盘还没标定」。
 */
const boot = async (
  page: import('@playwright/test').Page,
  { camera, geometry = camera ? 'ready' : 'disabled' }: { camera: boolean; geometry?: 'ready' | 'disabled' | 'required' },
): Promise<Vision> => {
  await freezeClock(page);
  // 种子键带身份后缀 + `/me` 给同一个 uuid,缺一不可 —— 见 helpers/kioskIdentity.ts。
  await page.addInitScript((sgfKey: string) => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
    localStorage.setItem(sgfKey, JSON.stringify({
      id: 's1', name: '摆谱 · 三星杯半决赛', sgf: '(;SZ[19];B[pd])', savedAt: 1,
    }));
  }, scopedKey('baipu:sgf:s1'));
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({ json: kioskMeJson({ username: '访客' }) }));
  // ⚠️ 几何和视觉状态**两条都要钉** —— 这一屏走哪一路(摄像头 / 手动兜底)就由这两条决定,
  // 不钉就随 :8001 在不在而变:四图跑的 vite dev server 把 `/api` 代理到 :8001,而视觉这一套不起后端。
  // (2026-08-26 撞过一次:几何接口连不上时 phase 停在 `required`,整屏停在「正在检查棋盘状态」。)
  // 判据和 `stubBackendStatics` 是同一条:**一张随后端在不在而变的实现图,不是这一屏的实现图。**
  await page.route('**/api/v1/geometry/status', (route) => route.fulfill({
    json: {
      phase: geometry, session_calibrated: geometry === 'ready', last_error: null,
      capabilities: {
        camera_ready: camera, led_ready: camera, geometry_ready: geometry === 'ready', recognition_ready: camera,
      },
    },
  }));
  const vision: Vision = { send: () => {}, armed: false, autoComplete: true };
  const sockets = new Set<import('@playwright/test').WebSocketRoute>();
  await page.routeWebSocket('**/ws/vision', (ws) => {
    sockets.add(ws);
    ws.onClose(() => { sockets.delete(ws); });
  });
  vision.send = (type, data = {}) => { for (const ws of sockets) ws.send(JSON.stringify({ type, data })); };
  await page.route('**/api/v1/vision/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/vision/status')) {
      return route.fulfill({
        json: {
          enabled: camera, camera_connected: camera, pose_locked: camera, sync_state: 'idle',
          bound_session_id: null, recognition_ready: camera, led_connected: true,
        },
      });
    }
    if (path.endsWith('/vision/move-detection')) vision.armed = !!route.request().postDataJSON()?.armed;
    await route.fulfill({ json: { ok: true } });
    if (path.endsWith('/vision/setup-mode') && vision.autoComplete) {
      setTimeout(() => vision.send('setup_complete'), 30);
    }
  });
  await page.route('**/api/v1/baipu/load', (route) => route.fulfill({ json: STEPS }));
  await page.route('**/api/v1/led/**', (route) => route.fulfill({
    json: { ok: true, connected: true, shown_at: null, errors: [] },
  }));
  // 取的是**上线态**(盒子默认)。钉死 `collect:false`:不让这张图随 :8001 上起的是不是采集机而变。
  await page.route('**/api/v1/baipu/mode', (route) => route.fulfill({ json: { collect: false } }));
  // 同一个判据:引擎在不在不属于这一屏 —— 不钉的话 :8001 没起时顶栏多一条「AI 引擎准备中」。
  await page.route('**/api/v1/health', (route) => route.fulfill({ json: { engines: { local: 'reachable' } } }));
  await page.goto('/kiosk/baipu/session/s1');
  await page.waitForSelector('[data-testid="baipu-pcard"]');
  return vision;
};

const pagebarShows = (page: import('@playwright/test').Page, n: number) => page.waitForFunction((i) => {
  const el = document.querySelector('[data-testid="baipu-pagebar"]');
  return !!el && el.textContent!.includes(`第 ${i} / 241 手`);
}, n);

/** 摄像头态摆到第 13 手:每一手等识别层布好臂,再发一条 `move_confirmed` —— 和人在盘上摆一颗一样。 */
const placeByCamera = async (page: import('@playwright/test').Page, vision: Vision) => {
  for (let i = 0; i < 12; i += 1) {
    await expect.poll(() => vision.armed, { timeout: 5_000 }).toBe(true);
    const [row, col, color] = MOVES[i];
    vision.armed = false;
    vision.send('move_confirmed', { row, col, color: color === 'B' ? 1 : 2 });
    await pagebarShows(page, i + 2);
  }
  await expect.poll(() => vision.armed, { timeout: 5_000 }).toBe(true);
};

const settle = async (page: import('@playwright/test').Page) => {
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  // 不等 networkidle:17a / 17c 有闪烁的灯(蓝 / 白),每 450 ms 发一次 LED,网络永远不会静。
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
};

const LAYOUT = 'L2 布局 A(盘 516 + 16 + 右栏 460)';

test('四图:摆谱 · 摄像头在看 ←→ sample-go/shots/17-baipu.png', async ({ page }) => {
  const vision = await boot(page, { camera: true });
  await placeByCamera(page, vision);
  await settle(page);
  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '17-baipu.png'),
    outDir: OUT('17-baipu'),
    slug: '17-baipu',
    referenceCaption: `参考:sample-go/shots/17-baipu.png · ${LAYOUT} · 摄像头认到就自动下一手，没有确认键`,
    implementationCaption:
      '实现:/kiosk/baipu/session/s1 @1024×600 · 时钟冻 16:40 · 上线态 collect=false · 视觉/几何钉成就绪 · '
      + '前 12 手由 /ws/vision 逐手 move_confirmed 推进(不点任何键)· 动作区 撤回 / 试下 / AI支招 · '
      + '支招键「AI支招」无空格 = 对弈页同一个 key',
  });
  console.log(`[fourup 17-baipu] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});

test('四图:摆谱 · 放错了 ←→ sample-go/shots/17a-baipu-restore.png', async ({ page }) => {
  const vision = await boot(page, { camera: true });
  await placeByCamera(page, vision);
  // 第 13 手该在 C7,人放到了 C6:识别层报 C6 → 进「把盘面摆对」,这次 setup 不自动对上。
  vision.autoComplete = false;
  vision.send('move_confirmed', { row: 13, col: 2, color: 1 });
  await expect(page.getByTestId('baipu-pcard')).toHaveAttribute('data-mood', 'setup');
  vision.send('setup_progress', { matched: 12, total: 12, missing: [], extra: [[13, 2, 1]] });
  await expect(page.locator('.gob .remove')).toHaveCount(1);
  await settle(page);
  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '17a-baipu-restore.png'),
    outDir: OUT('17a-baipu-restore'),
    slug: '17a-baipu-restore',
    referenceCaption: `参考:sample-go/shots/17a-baipu-restore.png · ${LAYOUT} · 放错 / 提子 / 撤回 / 试下结束都进这一态`,
    implementationCaption:
      '实现:摆到第 13 手后 /ws/vision 报 C6(黑)→ 放错 → setup 目标仍是第 12 手之后的局面 · '
      + 'setup_progress 报多出 C6 → 盘上蓝圈 + 蓝灯闪 · C7 只画屏上的圈、**不点灯**(子压在亮着的红灯上会被认成 led_red)',
  });
  console.log(`[fourup 17a-baipu-restore] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});

test('四图:摆谱 · 试下 ←→ sample-go/shots/17b-baipu-try.png', async ({ page }) => {
  const vision = await boot(page, { camera: true });
  await placeByCamera(page, vision);
  await page.getByRole('button', { name: '试下' }).click();
  await expect(page.getByTestId('baipu-pcard')).toHaveAttribute('data-mood', 'trying');
  await settle(page);
  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '17b-baipu-try.png'),
    outDir: OUT('17b-baipu-try'),
    slug: '17b-baipu-try',
    referenceCaption: `参考:sample-go/shots/17b-baipu-try.png · ${LAYOUT} · 试下是开关,识别暂停、灯全灭`,
    implementationCaption:
      '实现:摄像头摆到第 13 手后按「试下」· 识别层撤臂 + 暂停 · 撤回 / AI支招 灰着(悬停说原因)· 盘上不画下一手的圈',
  });
  console.log(`[fourup 17b-baipu-try] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});

test('四图:摆谱 · AI 支招 ←→ sample-go/shots/17c-baipu-hint.png', async ({ page }) => {
  // 黑方视角(后端口径);第 13 手轮黑,不翻转。
  await page.route('**/api/v1/analysis/quick-analyze', (route) => route.fulfill({
    json: {
      moveInfos: [
        { move: 'C7', winrate: 0.524, scoreLead: 0.9, visits: 90 },
        { move: 'C9', winrate: 0.518, scoreLead: 0.6, visits: 60 },
        { move: 'R3', winrate: 0.506, scoreLead: 0.2, visits: 40 },
      ],
    },
  }));
  const vision = await boot(page, { camera: true });
  await placeByCamera(page, vision);
  await page.getByRole('button', { name: 'AI支招' }).click();
  await expect(page.getByTestId('baipu-hint-fold')).toContainText('3 · R3');
  await settle(page);
  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '17c-baipu-hint.png'),
    outDir: OUT('17c-baipu-hint'),
    slug: '17c-baipu-hint',
    referenceCaption: `参考:sample-go/shots/17c-baipu-hint.png · ${LAYOUT} · 候选点白灯,图例那块临时换成候选`,
    implementationCaption:
      '实现:摄像头摆到第 13 手后按「AI支招」· quick-analyze 钉成三手(C7 / C9 / R3)· 分析的是**谱上**这一手的局面 · '
      + '识别暂停 · 30 秒自动收起、换一手也收起',
  });
  console.log(`[fourup 17c-baipu-hint] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});

test('四图:摆谱 · 摄像头用不了 ←→ sample-go/shots/17d-baipu-manual.png', async ({ page }) => {
  // 视觉在、几何这次开机还没确认(盒子重启后的常态)⇒ 手动兜底,原因「棋盘还没标定」。
  await boot(page, { camera: true, geometry: 'required' });
  // 手动兜底:临时露出「确认落子」,前 12 手逐手按。
  for (let i = 0; i < 12; i += 1) {
    await page.getByRole('button', { name: '确认落子' }).click();
    await pagebarShows(page, i + 2);
  }
  await page.waitForLoadState('networkidle');
  await settle(page);
  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '17d-baipu-manual.png'),
    outDir: OUT('17d-baipu-manual'),
    slug: '17d-baipu-manual',
    referenceCaption: `参考:sample-go/shots/17d-baipu-manual.png · ${LAYOUT} · 摄像头用不了才临时露出确认键,写明原因`,
    implementationCaption:
      '实现:视觉就绪、几何 required(本次开机没确认过)⇒ 手动兜底,原因「棋盘还没标定」+ 去「设置」标定 · '
      + '前 12 手按「确认落子」· 试下灰着说「摄像头没在识别」· 恢复后这颗键自己收起',
  });
  console.log(`[fourup 17d-baipu-manual] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
