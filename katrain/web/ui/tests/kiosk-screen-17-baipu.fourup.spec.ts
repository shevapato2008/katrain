import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';
import { scopedKey, kioskMeJson } from './helpers/kioskIdentity';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/17-baipu/1024x600');

/**
 * 屏 17 摆谱 · 进行中(L2 布局 A:盘 516 + 16 + 右栏 460)。
 *
 * 2026-09-23 稿子改画上线态(Fan:逐手拍照只为采 YOLO 训练数据,RK3562 上用户只用亮灯摆谱),
 * 原先这里记的三处稿子错误里有两处随之修掉 —— 稿子现在也是「灯 · 颜色对照」三句真图例
 * (红=放黑子 / 绿=放白子 / 蓝=该拿走,`constants/ledColors.ts`)、C7 待摆圈是红的、
 * 页控条不写帧数、确认键画 hand-pointing。**采集态不取四图**(只在 `--baipu-collect` 起的采集机上出现)。
 *
 * ⚠️ 稿子里还剩一处是错的,不是我没对齐(2026-08-24 裁定,已回报稿子作者):
 *  · 稿子动作区四格,多一颗**虚手**。这一屏是在重放一份既有 SGF,而这条 track 的数据契约
 *    把 pass 定义成「无物理动作」(不产帧、`frames.length = 1 + 非 pass 落子数`)——
 *    一颗人能按的虚手要么破坏那条等式,要么什么都不干。⇒ 三格:确认落子 / 撤回上一手 / 完成。
 *
 * 其余预期差异:
 *  · 玩家卡两张删了 —— 摆谱**没有人在下棋**,一局早已结束的谱,屏前只有一个操作员;
 *    `data-active` 挂在申真谞那张卡上等于屏上写着「轮到申真谞了」。名字进页控条标题。
 *  · 通栏状态条(落子黑 / 手数 / 已采集 / 两颗健康点)整块删:前三样稿子本来就有落点,
 *    LED 那颗**由页控条右上角那颗「重新点灯」兼任**(它本来就是这个故障的补救动作),
 *    相机那颗**删** —— 唯一现成的数据源 `vision/status` 在摆谱专用部署(有相机、有采集、
 *    无 vision 模型)下恒返回 `camera_connected:false`,挂上去就是在好机器上画红点。
 *  · 「完成」常驻但摆完之前灰着 + 写明还剩几手(常驻是为了那颗按 250 次的键位置不跳)。
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

const boot = async (page: import('@playwright/test').Page) => {
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
  // ⚠️ **这条不是装饰,是这一屏的四图能不能自己站住的前提。**
  // (2026-09-14 起只有采集态套守卫,但**上线态同样离不开这条桩**:上线态要等棋盘状态读到过才挂摆谱屏
  //  —— 不桩就停在「正在检查棋盘状态」,`baipu-pcard` 照样永远不出现。)
  // `baipu/session/:source` 外面套着 `PhysicalBoardGuard`,它读 `GeometryContext`;
  // 而 `GeometryProvider` 只在**接口 404** 时才落到 `disabled`(那是「这台盒子没摄像头」
  // 这个**读到了的结论**),接口连不上时 phase 停在 `required` ⇒ 整屏被换成标定台,
  // `baipu-pcard` 永远不出现 ⇒ 30 秒超时。四图跑的 vite dev server 把 `/api` 代理到
  // :8001,而视觉这一套**不起后端** —— 也就是说这一屏原来「后端起着就绿、一停就红」。
  // 2026-08-26 撞上:整批 27 屏重跑时只有这一屏红,而它上一次绿是因为那天 :8001 正好开着。
  // 判据和 `stubBackendStatics` 是同一条:**一张随后端在不在而变的实现图,不是这一屏的实现图。**
  await page.route('**/api/v1/geometry/status', (route) => route.fulfill({
    json: {
      phase: 'disabled', session_calibrated: false, last_error: null,
      capabilities: { camera_ready: false, led_ready: false, geometry_ready: false, recognition_ready: false },
    },
  }));
  await page.route('**/api/v1/baipu/load', (route) => route.fulfill({ json: STEPS }));
  await page.route('**/api/v1/led/**', (route) => route.fulfill({
    json: { ok: true, connected: true, shown_at: null, errors: [] },
  }));
  // 取的是**上线态**(盒子默认)。钉死 `collect:false`:不让这张图随 :8001 上起的是不是采集机而变 ——
  // 与上面 `geometry/status` 那条同一个判据(一张随后端在不在而变的实现图,不是这一屏的实现图)。
  await page.route('**/api/v1/baipu/mode', (route) => route.fulfill({ json: { collect: false } }));
  // 同一个判据:引擎在不在不属于这一屏 —— 不钉的话 :8001 没起时顶栏多一条「AI 引擎准备中」。
  await page.route('**/api/v1/health', (route) => route.fulfill({ json: { engines: { local: 'reachable' } } }));
  await page.goto('/kiosk/baipu/session/s1');
  await page.waitForSelector('[data-testid="baipu-pcard"]');
};

test('四图:摆谱 · 进行中 ←→ sample-go/shots/17-baipu.png', async ({ page }) => {
  await boot(page);
  // 摆到第 13 手(稿子那一帧)—— 前 12 手逐手确认,和真人做的事一样。
  for (let i = 0; i < 12; i += 1) {
    await page.getByRole('button', { name: '确认落子' }).click();
    await page.waitForFunction((n) => {
      const el = document.querySelector('[data-testid="baipu-pagebar"]');
      return !!el && el.textContent!.includes(`第 ${n} / 241 手`);
    }, i + 2);
  }
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '17-baipu.png'),
    outDir: OUT,
    slug: '17-baipu',
    referenceCaption:
      '参考:sample-go/shots/17-baipu.png · L2 布局 A(盘 516 + 16 + 右栏 460)· '
      + '主角在盘上不在屏上:灯指下一手，人摆好按确认 · 上线态(不拍照)',
    implementationCaption:
      '实现:/kiosk/baipu/session/s1 @1024×600 · 时钟冻 16:40 · 摆到第 13 手 · 上线态 collect=false · '
      + '**动作区三格不是四格**:稿子多的那颗「虚手」不做——这一屏在重放既有 SGF，'
      + '而 pass 按数据契约不产帧，一颗能按的虚手要么破坏 frames 等式要么什么都不干 · '
      + '**玩家卡两张删了**:摆谱没有人在下棋，名字进页控条标题 · '
      + '**通栏状态条删了**:LED 那颗健康点由右上角「重新点灯」兼任(它就是这个故障的补救)，'
      + '相机那颗删——唯一数据源在摆谱专用部署下恒报 false，挂上去就是在好机器上画红点 · '
      + '「完成」常驻但摆完前灰着(常驻是为了那颗按 250 次的键位置不跳)',
  });
  console.log(`[fourup 17-baipu] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
