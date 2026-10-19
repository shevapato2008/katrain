import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/26-calib/1024x600');

/**
 * 屏 26 棋盘标定(**布局 B**:页控条通栏,内容区 992×460 内部切 516 | 16 | 460)。
 *
 * 取的是稿子那一帧的**同一时刻**:正在定位星位、已经点亮 4 角 + 8 星。
 *
 * 预期差异,每条都是裁定:
 *
 *  ① 五步含真实的曝光收敛和锁定阶段；旧参考图仍是四步。
 *    当前星位定位显示「第 4 / 5 步」。每个锚点的熄灯参考帧没有独立阶段，仍不单列。
 *
 *  ② **摄像头画面里此刻画不出网格。** 稿子这一帧画了完整的四边形 + 插值出来的 19×19 网格,
 *    可这一刻**单应矩阵还不存在** —— 它是 13 个锚点全部定位之后 `fit_geometry_from_anchors`
 *    才算出来的。标定进行中能诚实画出来的只有**已经找到的那些点**。
 *    稿子那张网格是「标定完成之后」的样子,被画到了「标定进行中」这一帧上。
 *
 *  ③ **叠加层是 `<canvas>` 不是 SVG** ⇒ 稿子的 `.camview .quad/.g/.cor/.star` 四条 CSS
 *    落不到它身上。调色板仍然留在 CSS(用 `--cam-*` 四个自定义属性),画的时候读回来 ——
 *    顺手把原来硬编码的三个色号(`#55e68a/#ff4d4f/#ffd166`,一个都不是围棋 token)换掉。
 *    锚点也不再按**LED 灯色**上色(那三种颜色屏上没有一个字解释,而且没有任何消费者),
 *    改成照稿:四角绿、星位琥珀。
 *
 *  ④ **稿子那两颗键在这一刻一颗都不成立** ⇒ 运行中整行换成一颗满宽的「取消标定」。
 *    「沿用上次标定」要 `phase ∈ {required,failed,cancelled}`(否则服务端 `ValueError`;
 *    2026-09-20 起 `_REUSABLE_PHASES` 加了 `cancelled`,V2 之后过期的是「只有 required/failed」这句),
 *    「重新开始标定」会撞 `CalibrationBusy` → 409。照画就是两颗按不动的键。
 *    而一次标定要逐个点亮 13 个 LED、每个 clear→拍→点亮→拍,是分钟级的 ——
 *    **没有退出路径的分钟级流程,在 7 寸触摸屏上就是卡死。**
 *
 *  ⑤ **多一个视图分段和三格状态的真值。** 分段照稿画在页控条右端(原始画面 / 俯视矫正,
 *    两段常驻都能按 —— 切到俯视而还没标定时那一块自己会说「完成 LED 标定后生成俯视画面」)。
 *    三格的值跟着真状态走,而**还没读到状态时一律「—」且不给 tone**:
 *    `DEFAULT_STATUS` 三个 capability 全是 false,照画会在还没问过的时候说「未连接」。
 *
 *  ⑥ 右栏中段可滚，新增曝光步骤和失败诊断都在中段；头(三格 56)尾(按钮 44)固定。
 */

/** 4 角 + 8 星 = 12 个已定位锚点。稿子那一帧写的正是「九星 8 / 9」。 */
const CORNERS = [[0, 0], [0, 18], [18, 18], [18, 0]];
const STARS = [[3, 3], [3, 9], [3, 15], [9, 3], [9, 9], [9, 15], [15, 3], [15, 9]];
const ANCHORS = [...CORNERS, ...STARS].map(([row, col], i) => ({
  row, col,
  x: 120 + col * 17 + (i % 3) * 2,
  y: 110 + row * 15 + (i % 2) * 2,
  color: 'green',
}));

const STATUS = {
  phase: 'verifying',
  session_calibrated: false,
  last_valid: false,
  error: null,
  progress: { current: 12, total: 13 },
  detected_anchors: ANCHORS,
  capabilities: { camera_ready: true, led_ready: true, geometry_ready: false, recognition_ready: false },
};

/**
 * 一张 640×480 的**深色** PNG。不用 1×1 的那张 —— 它被拉满整块之后是一片荧光绿,
 * 四图上看起来像出了故障。这里只是给 `<img>` 一个真能 load 的东西
 * (叠加层要靠 `onImageLoad` 拿帧尺寸)。
 */
const DARK_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAoAAAAHgCAIAAAC6s0uzAAAF+UlEQVR42u3VoQ0AAAgEsfco2H9YtgDTpBOcudQ0AHAsEgCAAQOAAQMABgwABgwAGDAAGDAAYMAAYMAAgAEDgAEDgAEDAAYMAAYMABgwABgwAGDAAGDAAIABA4ABA4ABAwAGDAAGDAAYMAAYMABgwABgwACAAQOAAQOAAQMABgwABgwAGDAAGDAAYMAAYMAAgAEDgAEDgAEDAAYMAAYMABgwABgwAGDAAGDAAIABA4ABA4ABAwAGDAAGDAAYMAAYMABgwABgwACAAQOAAQOAAQMABgwABgwAGDAAGDAAYMAAYMAAgAEDgAEDgAEDAAYMAAYMABgwABgwAGDAAGDAAIABA4ABA4ABAwAGDAAGDAAYMAAYMABgwABgwACAAQOAAQOAAasAAAYMAAYMABgwABgwAGDAAGDAAIABA4ABAwAGDAAGDAAGDAAYMAAYMABgwABgwACAAQOAAQMABgwABgwABgwAGDAAGDAAYMAAYMAAgAEDgAEDAAYMAAYMAAYMABgwABgwAGDAAGDAAIABA4ABAwAGDAAGDAAGDAAYMAAYMABgwABgwACAAQOAAQMABgwABgwABgwAGDAAGDAAYMAAYMAAgAEDgAEDAAYMAAYMAAYMABgwABgwAGDAAGDAAIABA4ABAwAGDAAGDAAGDAAYMAAYMABgwABgwACAAQOAAQMABgwABgwABgwAGDAAGDAAYMAAYMAAgAEDgAEDAAYMAAYMAAasAgAYMAAYMABgwABgwACAAQOAAQMABgwABgwAGDAAGDAAGDAAYMAAYMAAgAEDgAEDAAYMAAYMABgwABgwABgwAGDAAGDAAIABA4ABAwAGDAAGDAAYMAAYMAAYMABgwABgwACAAQOAAQMABgwABgwAGDAAGDAAGDAAYMAAYMAAgAEDgAEDAAYMAAYMABgwABgwABgwAGDAAGDAAIABA4ABAwAGDAAGDAAYMAAYMAAYMABgwABgwACAAQOAAQMABgwABgwAGDAAGDAAGDAAYMAAYMAAgAEDgAEDAAYMAAYMABgwABgwABgwAGDAAGDAAIABA4ABAwAGDAAGDAAYMAAYMAAYMABgwABgwACAAQOAAQMABgwABgwAGDAAGDAAGLAEAGDAAGDAAIABA4ABAwAGDAAGDAAYMAAYMABgwABgwABgwACAAQOAAQMABgwABgwAGDAAGDAAYMAAYMAAYMAAgAEDgAEDAAYMAAYMABgwABgwAGDAAGDAAGDAAIABA4ABAwAGDAAGDAAYMAAYMABgwABgwABgwACAAQOAAQMABgwABgwAGDAAGDAAYMAAYMAAYMAAgAEDgAEDAAYMAAYMABgwABgwAGDAAGDAAGDAAIABA4ABAwAGDAAGDAAYMAAYMABgwABgwABgwACAAQOAAQMABgwABgwAGDAAGDAAYMAAYMAAYMAAgAEDgAEDAAYMAAYMABgwABgwAGDAAGDAAGDAKgCAAQOAAQMABgwABgwAGDAAGDAAYMAAYMAAgAEDgAEDgAEDAAYMAAYMABgwABgwAGDAAGDAAIABA4ABA4ABAwAGDAAGDAAYMAAYMABgwABgwACAAQOAAQOAAQMABgwABgwAGDAAGDAAYMAAYMAAgAEDgAEDgAEDAAYMAAYMABgwABgwAGDAAGDAAIABA4ABA4ABAwAGDAAGDAAYMAAYMABgwABgwACAAQOAAQOAAQMABgwABgwAGDAAGDAAYMAAYMAAgAEDgAEDgAEDAAYMAAYMABgwABgwAGDAAGDAAIABA4ABA4ABAwAGDAAGDAAYMAAYMABgwABgwACAAQOAAQOAAasAAAYMAAYMABgwABgwAGDAAGDAAIABA4ABAwAGDAAGDAAGDAAYMAAYMABgwABgwACAAQOAAQMABgwABgwABgwAGDAAGDAAYMAAYMAAgAEDgAEDAAYMAAYMAAYMABgwABgwAGDAAGDAAIABA4ABAwAGDAAGDAAGDAAYMAAYMABgwABgwACAAQOAAQMABgwABgwABgwAGDAAGDAAYMAAYMAAgAEDgAEDAAYMAP8WscKsmt98AsgAAAAASUVORK5CYII=',
  'base64',
);

test('四图:棋盘标定 ←→ sample-go/shots/26-calib.png', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: '访客', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/v1/geometry/status', (route) => route.fulfill({ json: STATUS }));
  // 标定进行中没有几何可读 —— 409 正是后端此刻的答复。
  await page.route('**/api/v1/geometry/layout', (route) => route.fulfill({ status: 409, json: { detail: 'not calibrated' } }));
  await page.route('**/api/v1/geometry/stream*', (route) => route.fulfill({
    status: 200, contentType: 'image/png', body: DARK_PNG,
  }));

  await page.goto('/kiosk/vision/setup');
  await page.waitForSelector('[data-testid="calib-step"][data-state="now"]');
  // ⚠️ **不能等 `networkidle`**:标定进行中 `GeometryProvider` 每 300ms 轮询一次
  // `/status`(`ACTIVE` 相位下的间隔),网络永远闲不下来 —— 那是一条 30 秒超时,不是慢。
  await page.waitForSelector('[data-testid="calib-cap"]');
  await page.waitForFunction(() =>
    (document.querySelector('.kiosk-status__cell')?.textContent ?? '').includes('已连接'));
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '26-calib.png'),
    outDir: OUT,
    slug: '26-calib',
    referenceCaption:
      '参考:sample-go/shots/26-calib.png · L2 布局 B(页控条通栏)· 左边是摄像头画面不是棋盘 · '
      + 'LED 只在按下之后才亮，不会自己亮 · 失败时给诊断不给「重试」',
    implementationCaption:
      '实现:/kiosk/vision/setup @1024×600 · 时钟冻 16:40 · 正在定位星位(4 角 + 8 星已点亮)· '
      + '**五步**:新增真实的「曝光收敛并锁定」，星位现在是第 4 / 5 步；旧参考图仍为四步 · '
      + '**此刻画不出网格**:单应矩阵要 13 个点全部定位之后才算得出来，'
      + '标定进行中能诚实画的只有已经找到的那些点；稿子那张网格是「标定完成之后」的样子 · '
      + '**运行中整行只有一颗「取消标定」**:稿子那两颗此刻一颗都不成立('
      + '沿用要 phase∈{required,failed,cancelled} 否则服务端 ValueError，重新开始会撞 409)，'
      + '而分钟级流程没有退出路径在 7 寸触屏上就是卡死 · '
      + '**多一个视图分段**(原始画面/俯视矫正，两段常驻都能按，切过去没标定时那块自己说人话) · '
      + '**三格状态跟真值走**，还没读到时一律「—」不给 tone(DEFAULT_STATUS 三个 capability 全 false，'
      + '照画会在还没问过的时候说「未连接」) · '
      + '**右栏中段可滚**:失败时要多一张诊断卡、旁注也比稿子多两行，放不下 · '
      + '**LED 那格写「串口已连接」**（只说串口通了，视觉赛道 V4），稿子那格是「已连接」(左栏的说法)',
  });
  console.log(`[fourup 26-calib] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
