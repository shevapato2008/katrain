import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

/**
 * 开局设置 r2 三屏的**四图对比**(参考 / 实现 / 并排 / 差异)。
 *
 * ## 参考图为什么不在 `sample-go/shots/`
 *
 * 那一份画的是**改版前**的开局设置(八组等重的设置、贴目是一条轨)。
 * 这三屏 2026-09-21 重画过,设计源是那天通过的稿子;稿子渲染出的三张图收在
 * `superpowers/tracks/kiosk-go-play-ai/visual/reference/`,跟着这个仓走。
 *
 * 旧的 `kiosk-screen-0{2,3,4}-*.fourup.spec.ts` 因此**已经删掉**:它们比的是一份
 * 不再描述这个产品的参考图,而其中 02 那份还会直接崩(它点的是一颗已经不存在的
 * `＋` 键)。**不是 skip —— skip 掉等于这三屏再也没人量。**
 * 它们留在 `superpowers/tracks/kiosk-go-shell-align/visual/` 下 02–04 那三份旧存档
 * 没有动:那是另一条赛道的档案,这一版只是不再往里写。
 *
 * 文件名保持 `kiosk-screen-*.fourup.spec.ts` 的形状,这样 `npm run fourup` 那条
 * glob 仍然收得到这三屏。
 *
 * ## 这一关管什么、不管什么
 *
 * 四图对比用眼睛看**静止一帧对不对**:构图、间距、层级、字色、图标、文案、状态语义。
 * **它不管可滚性** —— 被 `overflow` 裁掉的东西在截图上根本不存在,差异图无从比。
 * 那一半归 `kiosk-setup-r2-geometry.spec.ts`,用机器量。两关互不替代。
 */

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG

const REF = resolve(process.cwd(), '../../../superpowers/tracks/kiosk-go-play-ai/visual/reference');
const OUT = (slug: string) =>
  resolve(process.cwd(), `../../../superpowers/tracks/kiosk-go-play-ai/visual/${slug}/1024x600`);

async function boot(page: Parameters<typeof freezeClock>[0]) {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (r) => r.fulfill({
    json: { id: 1, username: '访客', rank: '5段', credits: 0 },
  }));
  // 取图机器没有标定过摄像头 —— 稿子那三帧取的也是这一态。
  await page.route('**/api/v1/vision/status', (r) => r.fulfill({
    json: {
      enabled: false, camera_connected: false, pose_locked: false, sync_state: 'idle',
      bound_session_id: null, recognition_ready: false, led_connected: null,
    },
  }));
  await page.route('**/api/v1/geometry/status', (r) => r.fulfill({
    json: {
      phase: 'disabled', session_calibrated: false, last_error: null,
      capabilities: { camera_ready: false, led_ready: false, geometry_ready: false, recognition_ready: false },
    },
  }));
  /* 这份形状照抄 `kiosk-screen-03-setup-ranked.fourup.spec.ts` 里那一份 ——
     第一版我自己编了一个 `placement_state: { phase: 'done' }`,结果屏上是
     「升降级对弈状态加载失败 · 重试」。**桩数据编错了形状,屏上就是诚实的出错态**,
     而四图会把那一帧当成实现拍下来。 */
  await page.route('**/api/v1/ai-ladder/status', (r) => r.fulfill({
    json: {
      view_state: 'ready',
      placement_state: {
        phase: 'placed',
        rung: { rung: 16, rank_name: '5级', certification_status: 'certified', availability: 'available', route: 'server' },
      },
      current_opponent: { rung: 16, rank_name: '5级', certification_status: 'certified', availability: 'available', route: 'server' },
      recent_ranked_results: ['win', 'win'], net_score: 2, pending_settlement: false, blocking_game: null,
    },
  }));
}

test('四图:自由对弈开局设置', async ({ page }) => {
  await boot(page);
  await page.goto('/kiosk/play/ai/setup/free');
  await page.waitForSelector('[data-testid="setup-game-group"]');
  await page.waitForLoadState('networkidle');
  const r = await captureFourUp({
    page, localReference: true,
    referencePng: resolve(REF, '02-setup-free.png'),
    outDir: OUT('02-setup-free'), slug: '02-setup-free',
    referenceCaption: '参考:2026-09-21 通过的稿子 · 两行三格 + 一条推导 · 默认态(19 路 · 中国规则 · 分先)',
    implementationCaption:
      '实现:/kiosk/play/ai/setup/free @1024×600 · 时钟冻 16:40 · 没标定摄像头那一态 · '
      + '**已知差异**:稿子的「怎么坐」那行提示写死了两句,实现按设备状态三选一;'
      + '棋力那条提示实现收短了一档(右栏余量只有 5.5px,折行就溢出)',
  });
  console.log(`[fourup r2 02] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});

test('四图:升降级对弈开局设置', async ({ page }) => {
  await boot(page);
  await page.goto('/kiosk/play/ai/setup/ranked');
  await page.waitForSelector('[data-testid="setup-game-group"]');
  await page.waitForLoadState('networkidle');
  const r = await captureFourUp({
    page, localReference: true,
    referencePng: resolve(REF, '03-setup-ranked.png'),
    outDir: OUT('03-setup-ranked'), slug: '03-setup-ranked',
    referenceCaption: '参考:稿子 · 盘面三格是虚线读数(服务端写死,客户端连发都不许发)· 对手并在同一段里',
    implementationCaption:
      '实现:/kiosk/play/ai/setup/ranked @1024×600 · '
      + '**已知差异**:对手那一格用的是 `KioskAiLadderOpponent`(它要带加载/出错/重试三态,'
      + '稿子画的是已定档那一态的静止帧);稿子那条「全程封分析」提示撤掉了 —— '
      + '页控条副标已经写着,同一件事说两遍,而撤掉它把右栏余量从 2.2px 提到 11.2px。'
      + '合入 develop 只给这一屏加了页控条中间那条「AI 引擎准备中」——它是绝对定位在'
      + '固定画布上的,不占右栏高度,余量没变(实测合并前后实现图只差 bbox 332,11–692,104 那一块)。',
  });
  console.log(`[fourup r2 03] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});

test('四图:本地对局开局设置', async ({ page }) => {
  await boot(page);
  await page.goto('/kiosk/play/pvp/setup');
  await page.waitForSelector('[data-testid="setup-game-group"]');
  await page.waitForLoadState('networkidle');
  const r = await captureFourUp({
    page, localReference: true,
    referencePng: resolve(REF, '04-setup-local.png'),
    outDir: OUT('04-setup-local'), slug: '04-setup-local',
    referenceCaption: '参考:稿子 · 姓名压成一行两格 · 落子提示音并进「怎么坐」· 取的是让 2 子那一帧',
    implementationCaption:
      '实现:/kiosk/play/pvp/setup @1024×600 · '
      + '**已知差异**:① 实现取的是默认态(分先),稿子那一帧是让 2 子 —— 所以左盘空、'
      + '推导条写「黑贴 3¾ 子」;② 底部那句「终局死活两人自己确认」**是过期文案** —— '
      + '本文件的 docstring 自己写着它不成立(数子是引擎估算死活),但改它的那一版'
      + '(kiosk-local-play v2)还没并进这条分支,**不在本次范围内**,记给 Fan',
  });
  console.log(`[fourup r2 04] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
