import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubShellAssets } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/02-setup-free/1024x600');

/**
 * 屏 02 自由对弈 · 开局设置(L2 布局 A,右栏整栏滚)。
 *
 * 稿子取的那一帧是 **让子 2 子** 的状态 —— 那正是贴目那一组换成一整段说明的那一态。
 * 这份对照因此也把让子推到 2:两边说的是同一件事,才比得出版式。
 *
 * 预期差异,四条,每条都是**实现对、稿子那一处不成立**:
 *
 *  ① **「落子」不是设置项。** 稿子把它画成「屏幕 / 实体盘」两段可选;实现里
 *    `isVisionEnabled` 由后端 `/api/v1/vision/status` 给(`context/VisionContext.tsx`),
 *    **全仓没有任何地方能让用户切它**。照画就是摆一个戳不动的旋钮。
 *    ⇒ 改成 `.igfix` 读数(虚线边 = 读数不是控件),说这一局会落在哪儿。
 *    这一帧取的是**没标定过摄像头**那一态(取图机器上就是),所以写「屏幕」。
 *
 *  ② **「我执」两项,不是稿子那三项。** 第三项「随机」是搬象棋骨架带来的:
 *    象棋 ranked 写死开局随机执棋,而围棋这边 kiosk(本屏)和 galaxy
 *    (`components/aiLadder/AiLadderRatedSetup.tsx`)**两处都只给黑白**。
 *    在四家里只有围棋多一条路,那不是对齐是分叉。
 *
 *  ③ **AI 策略那一行说明只有「拟人」有。** 稿子只写了这一条;另外四条说的是引擎
 *    干什么,是**对产品行为的断言**,仓里没有任何一处证明,编不得。
 *    `.kiosk-opthint` 定高,留空不会让下面的组跳。
 *
 *  ④ **贴目档是 15 档不是三档。** 稿子那句「会变回可选的贴目档(6.5 / 7.5 / 0)」写在
 *    一段说明里,不是控件规格;实现的贴目是 0.5 – 7.5 半目一档共 15 档,
 *    把它收成三档是删功能不是重画。屏 04 的贴目稿子画的正是一条档位轨,两屏因此同一种控件。
 *
 *  另外 Dock 少「成长」:围棋没有 growth 路由/页面/后端(D6)。
 */

test('四图:自由对弈开局设置 ←→ sample-go/shots/02-setup-free.png', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubShellAssets(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: '访客', rank: '5段', credits: 0 },
  }));
  // 没标定过摄像头 —— 「落子」那一格因此读「屏幕」。
  await page.route('**/api/v1/vision/status', (route) => route.fulfill({
    json: {
      enabled: false, camera_connected: false, pose_locked: false, sync_state: 'idle',
      bound_session_id: null, recognition_ready: false, led_connected: null,
    },
  }));
  await page.route('**/api/v1/geometry/status', (route) => route.fulfill({
    json: {
      phase: 'disabled', session_calibrated: false, last_error: null,
      capabilities: { camera_ready: false, led_ready: false, geometry_ready: false, recognition_ready: false },
    },
  }));

  await page.goto('/kiosk/play/ai/setup/free');
  await page.waitForSelector('[data-testid="setup-clock"]');

  // 稿子那一帧是让子 2 子 —— 把它推到同一态,否则比的是两个不同的屏。
  const more = page.locator('[data-testid="setup-handicap"] button[aria-label="多让一子"]');
  await more.click();
  await more.click();
  await page.waitForSelector('[data-testid="setup-komi-explain"]');

  // 点过键之后有两样东西会污染这一帧,**两样都不是产品缺陷,是取图没收拾干净**:
  //   ① 浏览器把刚点的键滚进了视野 —— 右栏于是停在「我执」而不是顶上那一组;
  //   ② 那颗键还留着 `:focus-visible` 的高亮圈。
  // 稿子画的是刚进这一屏的样子,所以这里滚回顶部并把焦点摘掉。
  await page.evaluate(() => {
    (document.activeElement as HTMLElement | null)?.blur();
    document.querySelector('.kiosk-side__scroll')?.scrollTo(0, 0);
  });
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '02-setup-free.png'),
    outDir: OUT,
    slug: '02-setup-free',
    referenceCaption:
      '参考:sample-go/shots/02-setup-free.png · L2 布局 A(盘 516 + 16 + 右栏 460,右栏整栏滚)· '
      + '取的是**让子 2 子**那一帧 —— 贴目那一组因此是一整段说明',
    implementationCaption:
      '实现:/kiosk/play/ai/setup/free @1024×600 · 时钟冻 16:40 · 让子已推到 2 子,和稿子同一态 · '
      + '**「落子」是读数不是控件**(虚线边):`isVisionEnabled` 由后端给,全仓没有任何地方能让用户切它,'
      + '照稿子画成两段可选就是摆一个戳不动的旋钮;这台机器没标定过摄像头,所以读「屏幕」 · '
      + '**「我执」两项不是三项**:第三项「随机」是搬象棋骨架带来的,围棋 kiosk 和 galaxy 两处都只给黑白 · '
      + '**AI 策略只有「拟人」那一条说明**:另外四条是对引擎行为的断言,仓里没有出处,不编 · '
      + '**贴目 15 档**(0.5 – 7.5 半目一档),稿子那句「(6.5 / 7.5 / 0)」写在说明里不是控件规格,'
      + '收成三档是删功能不是重画 · Dock 少「成长」(D6)',
  });
  console.log(`[fourup 02-setup-free] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
