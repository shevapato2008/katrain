import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/13-problems/1024x600');

/**
 * 屏 13 题目列表。**原稿少画的那一层**(2026-08-21 补的),计划书里没有对应的 Task。
 *
 * 稿子那一格画的是「做了 3 道、第 4 道是下一道」的中途态,所以这里**得造进度** ——
 * 造的是 `tsumego_progress`(真存储,真格式),不是往组件里塞假 props。
 * ⚠️ `attempts` 存的是**失败**的那几次,屏上那句「N 次」= `attempts + (做对了 ? 1 : 0)`:
 * 稿子上的 `1 次 / 1 次 / 3 次` 对应 `attempts: 0 / 0 / 2`。
 */
const IDS = Array.from({ length: 45 }, (_, i) => ({ id: `p${i}` }));

test('四图:题目列表 ←→ sample-go/shots/13-problems.png', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
    // 稿子那一屏:前 3 道做对(试了 1 / 1 / 3 次),第 4 道是下一道且一次没试过,
    // 另有一道错过没做对的(第 21 题,给「换一批」那行的「现在有 1 道」当依据)。
    localStorage.setItem('tsumego_progress', JSON.stringify({
      p0: { completed: true, attempts: 0, lastDuration: 18 },
      p1: { completed: true, attempts: 0, lastDuration: 21 },
      p2: { completed: true, attempts: 2, lastDuration: 27 },
      p20: { completed: false, attempts: 1 },
    }));
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
  await page.goto('/kiosk/tsumego/15k/capturing/1');
  await page.waitForSelector('.qgrid button:nth-child(20)');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '13-problems.png'),
    outDir: OUT,
    slug: '13-problems',
    referenceCaption:
      '参考:sample-go/shots/13-problems.png · 布局 B(无棋盘 ⇒ 页控条通栏 x16)· 稿子这一层 2026-08-21 才补上,原稿从单元卡直接跳做题屏',
    implementationCaption:
      '实现:/kiosk/tsumego/15k/capturing/1 @1024×600 · 时钟冻 16:40 · 题号 45 个是 fixture,进度造进 tsumego_progress(真存储真格式)· '
      + '三处按 Fan「别写那么多小字」改了:两条组标题右端的说明去掉、数据条标签去掉「· 当前单元」、错题那行点名「这一类」 · '
      + '「只做错过的」不摆按不动的「开始」,只挂 §14 琥珀标',
  });
  console.log(`[fourup 13-problems] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
