import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubShellAssets } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/27-settings/1024x600');

/**
 * 屏 27 设置(L1-B:左栏仍是 296 的 `.kiosk-console`,装的是导航不是盘)。
 *
 * ⚠️ **这一屏和稿子差得最多,而且是裁定不是遗漏**:
 * 稿子摆了七组,这台盒子上**五组没有内容**(棋盘外观、声音与报着、对局默认值、关于整组不存在;
 * 实体棋盘只有标定和读数,没有 LED 开关和帧率滑条)。计划 D10 在三条路里选了
 * **只做有内容的组**:
 *   · 七组全摆、空的挂琥珀「未接后端」—— **用错标**:那五组大部分不是「后端没有」,
 *     是「这个设置项还没做」。两回事,两种颜色。
 *   · 七组全摆、空的做成真功能 —— 五个新 feature,远超一条表现层赛道。
 * ⇒ 导航四项、右边四组,**词一一对应**。差异图上少三组是这条裁定的后果。
 *
 * 其余预期差异:
 *  ① 稿子没有「语言」这一组,实现有 —— 规范 §12 说它该在设置中心,**可设置中心不在本仓**,
 *    搬走等于这台盒子上再没有语言开关。登记为已知偏差。
 *  ② 账号那两行 2026-08-23 从 MUI 卡片重排成了 `.kiosk-row`。
 *    **段位详情那张卡(`AiLadderStatusCard`)还没重画** —— 它只在点开对话框之后才出现。
 *  ③ 平台那一行念的是**真能连的三家**(OGS / 野狐 / 星阵),不是上一版那四张死卡
 *    (99围棋 / 野狐 / 腾讯 / 新浪 —— 和真正能连的对不上)。
 *  ④ Dock 少「成长」(D6)。
 */

test('四图:设置 ←→ sample-go/shots/27-settings.png', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubShellAssets(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: '访客', rank: '5段', credits: 0 },
  }));
  // 这台盒子接着摄像头、标定过了、LED 也在 —— 三格才有真读数可显示。
  await page.route('**/api/v1/geometry/status', (route) => route.fulfill({
    json: {
      phase: 'ready', session_calibrated: true, last_error: null,
      capabilities: { camera_ready: true, led_ready: true, geometry_ready: true, recognition_ready: true },
    },
  }));

  // 段位状态不 mock 的话这一行会显示「加载失败」—— 那是诚实的,但对照台要看的是常态。
  await page.route('**/api/v1/ai-ladder/**', (route) => route.fulfill({
    json: {
      view_state: 'ready',
      placement_state: { phase: 'placed', rung: { rung: 12, rank_name: '9 级', certification_status: 'certified', availability: 'available', route: 'local' } },
      current_opponent: { rung: 12, rank_name: '9 级', certification_status: 'certified', availability: 'available', route: 'local' },
      recent_ranked_results: [], net_score: 2, pending_settlement: false,
    },
  }));

  await page.goto('/kiosk/settings');
  await page.waitForSelector('[data-testid="settings-nav"] button');
  await page.waitForSelector('[data-group="language"]');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '27-settings.png'),
    outDir: OUT,
    slug: '27-settings',
    referenceCaption:
      '参考:sample-go/shots/27-settings.png · L1-B(左栏仍是 296,装导航不是盘)· '
      + '稿子摆了七组:账号与平台 / 实体棋盘 / 棋盘外观 / 落子与提示 / 声音与报着 / 对局默认值 / 关于',
    implementationCaption:
      '实现:/kiosk/settings @1024×600 · 时钟冻 16:40 · 摄像头 / 标定 / LED 三格是 fixture · '
      + '**只做有内容的四组**(计划 D10):那五组大部分不是「后端没有」而是「这个设置项还没做」,'
      + '挂琥珀「未接后端」是用错标;做成真功能是五个新 feature,超出一条表现层赛道 —— **裁定不是遗漏** · '
      + '导航项数 = 分组数、词一一对应;高亮跟着**滚动位置**走,不跟着最后点过哪一项 · '
      + '尾部那段留白不是排版,是让最后一组也能滚到视口顶 —— 不然点第 3 项会被滚动事件弹回第 2 项 · '
      + '多一组「语言」:规范 §12 说它该在设置中心,可设置中心不在本仓,搬走等于这台盒子上再没有语言开关 · '
      + '账号那两行也是 `.kiosk-row`(段位详情那张卡还没重画,它只在点开对话框之后才出现)· '
      + '平台那一行念的是真能连的三家,不是上一版那四张对不上的死卡 · Dock 少「成长」(D6)',
  });
  console.log(`[fourup 27-settings] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
