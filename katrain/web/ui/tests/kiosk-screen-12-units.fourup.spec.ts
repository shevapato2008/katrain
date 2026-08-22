import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/12-units/1024x600');

/**
 * ⚠️ **屏号是 12 不是 04。** 计划书那个号是 2026-08-20 那份十屏稿的编号;
 * 稿子 2026-08-21 扩到 27 屏之后,单元列表是第 12 屏(`shots/12-units.png`)。
 */

// 稿子画的是 15 级 · 吃子 的九个单元 ⇒ 造 180 道题(9 × 20)。
// 造的是**接口返回的题号**,单元怎么分、每格写什么范围,是页面自己算的。
const IDS = Array.from({ length: 180 }, (_, i) => ({ id: `p${i}` }));

test('四图:单元列表 ←→ sample-go/shots/12-units.png', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
    // 稿子上「本单元已做对」写的是 0 / 20、九个环全是 0% —— 那是**一道没做**的真状态,
    // 所以这一屏**不造进度**:清掉本地进度,画出来的 0% 就是真的 0%。
    localStorage.removeItem('tsumego_progress');
    localStorage.setItem('kiosk_tsumego_autoadvance', 'true');   // 数据条第三格「开」
  });
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') {
      return route.fulfill({ json: { id: 1, username: '访客', rank: '5段', credits: 0 } });
    }
    if (path.startsWith('/api/v1/tsumego/levels/') && path.includes('/categories/')) {
      return route.fulfill({ json: IDS });
    }
    if (path === '/api/v1/tsumego/progress') return route.fulfill({ json: {} });
    return route.fulfill({ json: {} });
  });
  await page.goto('/kiosk/tsumego/15k/capturing');
  // 等到九张单元卡都渲出来 —— 卡是接口回来之后才有的。
  await page.waitForSelector('.kiosk-cards .kiosk-card:nth-child(9)');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '12-units.png'),
    outDir: OUT,
    slug: '12-units',
    referenceCaption:
      '参考:sample-go/shots/12-units.png · 布局 B(无棋盘 ⇒ 页控条通栏 x16)· 稿子上的九个单元是形状示意,真实 15 级·吃子 630 题 = 32 个',
    implementationCaption:
      '实现:/kiosk/tsumego/15k/capturing @1024×600 · 时钟冻 16:40 · 题号 180 个是 fixture(单元怎么分、每格写什么范围由页面算)· **进度没造**:环里那些 0% 是真的一道没做 · 「只做错过的」灰是真的(算得出、没地方去)',
  });
  console.log(`[fourup 12-units] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
