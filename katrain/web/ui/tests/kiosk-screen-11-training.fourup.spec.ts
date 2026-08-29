import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/11-training/1024x600');

/**
 * ⚠️ **屏号是 11 不是 03。** 计划书里这一屏写作「屏 03」,那是 2026-08-20 那份**十屏**稿的编号;
 * 稿子 2026-08-21 扩到 27 屏之后,训练营成了第 11 屏(`sample-go/shots/11-training.png`)。
 * 参考图的文件名是唯一不会漂的锚,所以 slug 跟它走 —— 和屏 05 那次同一条口径。
 */

// 稿子那六档(15 级 / 10 级 / 5 级 / 1 级 / 3 段 / 7 段)。题量**不在稿子上**(G8:题库不在仓库里),
// 这里造的是**接口的返回**,页面照它算 —— 画出来的题量是页面自己的逻辑,不是图上写死的字。
const LEVELS = [
  { level: '15k', categories: { 'life-death': 167, tesuji: 139, semeai: 96, capturing: 630, endgame: 74, opening: 58 }, total: 1164 },
  { level: '10k', categories: { 'life-death': 402, tesuji: 265, semeai: 121, capturing: 188 }, total: 976 },
  { level: '5k', categories: { 'life-death': 511, tesuji: 302, semeai: 143, endgame: 96 }, total: 1052 },
  { level: '1k', categories: { 'life-death': 448, tesuji: 271, semeai: 130 }, total: 849 },
  { level: '3d', categories: { 'life-death': 386, tesuji: 194 }, total: 580 },
  { level: '7d', categories: { 'life-death': 233, tesuji: 118 }, total: 351 },
];

test('四图:训练营 ←→ sample-go/shots/11-training.png', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
    // 「接着上次」和两处高亮全是真实数据驱动的:没做过题就**不该**出现。稿子上有,所以造。
    // ⚠️ 标签用的是 `TsumegoProblemPage` 真会写的那个格式(`… · 第 N 题`),
    // **不是稿子上那句「第 1 单元」** —— 后者这套代码永远写不出来,摆上去就是编。
    localStorage.setItem('kiosk_active_practice', JSON.stringify({
      kind: 'practice',
      label: '15 级 · 吃子 · 第 1 题',
      route: '/kiosk/tsumego/problem/fourup-fixture',
      ts: 1_766_000_000_000,
    }));
    localStorage.setItem('kiosk_tsumego_last_level', '15k');
    localStorage.setItem('kiosk_tsumego_last_category', 'capturing');
  });
  // 后端没起时 logo 会 502,取出来的图左上角是碎图标 —— 钉在仓里那份真字节上。
  await stubBackendStatics(page);
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') {
      return route.fulfill({ json: { id: 1, username: '访客', rank: '5段', credits: 0 } });
    }
    if (path === '/api/v1/tsumego/levels') {
      return route.fulfill({ json: LEVELS });
    }
    // 硬件三格 stub 成 ready:取图机器上没有摄像头也没有 LED,不 stub 三格全红/琥珀,
    // **交到人手上会被读成设计**。造的是输入,写进了标签带。
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
  await page.goto('/kiosk/tsumego');
  // 等到卡真的渲出来 —— 六张分类卡是接口回来之后才有的,`.kiosk-screen` 在场不代表数据到了。
  await page.waitForSelector('.kiosk-cards .kiosk-card:nth-child(6)');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '11-training.png'),
    outDir: OUT,
    slug: '11-training',
    referenceCaption:
      '参考:sample-go/shots/11-training.png · 2026-08-22 起稿子上不再有旁注小字(Fan 裁:那些字收进 HTML 注释)',
    implementationCaption:
      '实现:/kiosk/tsumego @1024×600 · 时钟冻 16:40 · 题库六档是 fixture(题量由页面从接口算,不是图上写死)· 接着上次 / 两处高亮 / 硬件三格都是 fixture · 镜像盘压暗=还没接到识别结果 · 环恒「—」是真的:这一层算不出每档进度',
  });
  console.log(`[fourup 11-training] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
