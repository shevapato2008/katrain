import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/14-puzzle/1024x600');

/**
 * 屏 14 做题屏(L2 布局 A)。
 *
 * 造的题**逐子照着稿子那张图**:黑 C5 B4 E5 F4 / 白 C4 E4(数气就能核的吃子题)。
 * 接口收的是 SGF 坐标(列 `a+x`,行从**上**数 `a+(size-1-y)`),所以 C5=(2,4) → `co`。
 *
 * ⚠️ **题面不是造的,是没有。** 题库那张表根本没有「题面」这一列(`hint` 只有 16 字),
 * 稿子上那段「黑先。白有两颗子……」是画稿时手写的 —— 实现里屏上写的是 `hint` 那一句
 * 加这一屏自己的规则。差异图上那一块会红一片,**这是预期**。
 */
const PROBLEM = {
  id: 'demo-atari',
  level: '15k',
  category: 'capturing',
  hint: '黑先',
  boardSize: 19,
  initialBlack: ['co', 'bp', 'eo', 'fp'],   // C5 B4 E5 F4
  initialWhite: ['cp', 'ep'],               // C4 E4
  sgfContent: '',
};
const IDS = Array.from({ length: 45 }, (_, i) => ({ id: i === 0 ? PROBLEM.id : `p${i}` }));

test('四图:做题屏 ←→ sample-go/shots/14-puzzle.png', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript((seq) => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
    localStorage.removeItem('tsumego_progress');
    localStorage.setItem('kiosk_tsumego_physical', 'false');
    // 屏 12 / 13 走过来时写下的那条顺序表 —— 上/下一题和点阵都靠它。
    sessionStorage.setItem('kiosk_problems_15k_capturing', JSON.stringify(seq));
  }, IDS.map((p) => p.id));
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') {
      return route.fulfill({ json: { id: 1, username: '访客', rank: '5段', credits: 0 } });
    }
    if (path.startsWith('/api/v1/tsumego/problems/')) return route.fulfill({ json: PROBLEM });
    if (path.startsWith('/api/v1/tsumego/levels/') && path.includes('/categories/')) {
      return route.fulfill({ json: IDS });
    }
    if (path === '/api/v1/tsumego/progress') return route.fulfill({ json: {} });
    return route.fulfill({ json: {} });
  });
  await page.goto(`/kiosk/tsumego/problem/${PROBLEM.id}`);
  await page.waitForSelector('.kiosk-layout-a .dots i:nth-child(20)');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '14-puzzle.png'),
    outDir: OUT,
    slug: '14-puzzle',
    referenceCaption:
      '参考:sample-go/shots/14-puzzle.png · 布局 A(盘 516 + 16 + 右栏 460)· 稿子上那段题面和标题「一手叫吃两边」是画稿时手写的,题库里没有这两样',
    implementationCaption:
      '实现:/kiosk/tsumego/problem/:id @1024×600 · 时钟冻 16:40 · 题目逐子照稿子(黑 C5 B4 E5 F4 / 白 C4 E4)是 fixture · '
      + '题面写的是题库真有的 hint「黑先」+ 这一屏的规则,**没编题面**;标签去掉稿子第三个「示意题面」 · '
      + '多出来的一排开关(试下 / 实体棋盘)和第五个动作键(上一题)是稿子没画、而真前端一直有的功能',
  });
  console.log(`[fourup 14-puzzle] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
