import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

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
    // 「继续上一局」是真实数据驱动的:localStorage 里没有在下的局它就**不该**出现。
    // 稿子上有这一条,所以取图时造一条 —— 造的是**输入**,画出来的还是页面自己的逻辑。
    // 标签带里写明了它是 fixture,别让下一个人指着这张图说「板上真有一局在下」。
    localStorage.setItem('kiosk_active_game', JSON.stringify({
      kind: 'game',
      label: '自由对弈 · KataGo 5 级 · 第 24 手 · 你执黑',
      route: '/kiosk/play/ai/game/fourup-fixture',
      ts: 1_766_000_000_000,
    }));
  });
  // 后端没起时 logo 会 502,取出来的图左上角是碎图标 —— 钉在仓里那份真字节上。
  await stubBackendStatics(page);
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
    // 平台状态也造:取图机器上一个平台都没登录,而稿子画的是「OGS 已连接」——
    // 不造的话三张卡全是「点击登录」,`.dot`(那颗绿点)和「已连接 · 走大厅」这条分支
    // 在图上一次都不出现,四图就核不到它们。造的是**输入**,标签带里写明了。
    if (path === '/api/v1/platforms/status' || path.endsWith('/platforms')) {
      return route.fulfill({ json: { platforms: [
        { platform: 'ogs', connected: true, supports_live_play: true, supports_automatch: true,
          supports_rooms: true, supports_seek_graph: true, supports_engine_play: false },
      ] } });
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
      '实现:/kiosk/play @1024×600 · 时钟冻 16:40 · Dock 七项(2026-08-25 起补了「成长」,围棋独有) · 硬件三格 / 继续上一局 / OGS 已连接 都是 fixture · 镜像盘压暗=还没接到识别结果',
  });
  console.log(`[fourup 01-play] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
