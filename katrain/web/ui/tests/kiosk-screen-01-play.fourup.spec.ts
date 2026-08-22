import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/01-play/1024x600');

test('四图:对弈首页 ←→ sample-go/shots/01-play.png', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') {
      return route.fulfill({ json: { id: 1, username: '访客', rank: '5段', credits: 0 } });
    }
    // 硬件三格必须 stub 成 ready:取图机器上没有摄像头和 LED,不 stub 三格全是红/琥珀,
    // **交到人手上会被读成设计**。stub 出来的态写进了下面的标签带。
    if (path === '/api/v1/vision/status') {
      return route.fulfill({ json: { enabled: true, camera_connected: true, pose_locked: true,
        sync_state: 'synced', recognition_ready: true, led_connected: true, bound_session_id: null } });
    }
    if (path === '/api/v1/geometry/status') {
      return route.fulfill({ json: { phase: 'ready', session_calibrated: true, last_valid: true,
        capabilities: { camera_ready: true, led_ready: true, geometry_ready: true } } });
    }
    return route.fulfill({ json: {} });
  });
  await page.goto('/kiosk/play');
  await page.waitForSelector('.kiosk-screen');
  // ⚠️ **这里不调 `waitForRealPixels`。** 它等的是镜像栏那块盘的真像素,而 `GoConsoleRail`
  // 现在传的是 `board={null}` —— 识别的盘面还没接进来,那一格如实空着(G8 诚实态)。
  // 没有被等对象的话它就是一条 30 秒超时,把「没有东西要等」报成「等不到」。
  // 真正要等的是跨平台三张卡(接口回来才渲):等滚动区在,再等网络静默。
  await page.waitForSelector('.kiosk-scrollzone', { state: 'attached' });
  await page.waitForLoadState('networkidle');
  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '01-play.png'),
    outDir: OUT,
    slug: '01-play',
    referenceCaption: '参考:sample-go/shots/01-play.png · 稿子上的 .note 旁注不上线(三家都没搬)',
    implementationCaption:
      '实现:/kiosk/play @1024×600 · 时钟冻 16:40 · Dock 六项(成长跳过) · 硬件三格是 stub 的 ready · 内容尚未按稿重画(Task 10)',
  });
  console.log(`[fourup 01-play] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
