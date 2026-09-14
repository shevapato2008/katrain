import { expect, test, type Page } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = (slug: string) => resolve(process.cwd(),
  `../../../superpowers/tracks/kiosk-go-tsumego/visual/${slug}/1024x600`);

/**
 * 错题页与做题屏错题模式(T1)。**稿子没有单独画这两态** —— 稿子原注写的是「同一副骨架，只换题从哪儿来」,
 * 所以参考图分别拿屏 13 与屏 14:比的是骨架(几何、层级、组件),不是文案。
 * 进度造进 `tsumego_progress:u1`(真存储真格式),`auth/me` 回 id=1。
 */
const PROBLEM = {
  id: 'demo-atari', level: '15k', category: 'capturing', hint: '黑先', boardSize: 19,
  initialBlack: ['co', 'bp', 'eo', 'fp'], initialWhite: ['cp', 'ep'], sgfContent: '',
};
const IDS = Array.from({ length: 45 }, (_, i) => ({ id: i === 3 ? PROBLEM.id : `p${i}` }));
const PROGRESS = {
  p0: { completed: true, attempts: 0, lastDuration: 18 },
  p1: { completed: true, attempts: 1, lastDuration: 40 },
  [PROBLEM.id]: { completed: false, attempts: 1 },
  p8: { completed: false, attempts: 2 },
  p20: { completed: false, attempts: 1 },
  p33: { completed: false, attempts: 3 },
};

const boot = async (page: Page, snapshot: string[] | null) => {
  await freezeClock(page);
  await page.addInitScript(({ progress, snap }) => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
    localStorage.setItem('kiosk_tsumego_physical', 'false');
    localStorage.setItem('tsumego_progress:u1', JSON.stringify(progress));
    // 错题快照按账号存(Task 7),下面 auth/me 回 id=1 ⇒ `:u1`。钥匙写错的话做题屏会静默退回整类,四图照样出图。
    if (snap) sessionStorage.setItem('kiosk_problems_15k_capturing_wrong:u1', JSON.stringify(snap));
  }, { progress: PROGRESS, snap: snapshot });
  await stubBackendStatics(page);
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') {
      return route.fulfill({ json: { id: 1, username: '访客', rank: '5段', credits: 0 } });
    }
    if (path.startsWith('/api/v1/tsumego/problems/')) return route.fulfill({ json: PROBLEM });
    if (path.startsWith('/api/v1/tsumego/levels/') && path.includes('/categories/')) {
      return route.fulfill({ json: IDS });
    }
    return route.fulfill({ json: {} });
  });
};

test('四图:错题页 ←→ sample-go/shots/13-problems.png(同一副骨架)', async ({ page }) => {
  await boot(page, null);
  await page.goto('/kiosk/tsumego/15k/capturing/wrong');
  await page.waitForSelector('.qgrid button:nth-child(4)');
  await page.waitForLoadState('networkidle');
  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '13-problems.png'),
    outDir: OUT('13w-wrong'),
    slug: '13w-wrong',
    referenceCaption: '参考:sample-go/shots/13-problems.png · 稿子没画错题页;原注「同一副骨架，只换题从哪儿来」⇒ 拿屏 13 比骨架',
    implementationCaption:
      '实现:/kiosk/tsumego/15k/capturing/wrong @1024×600 · 时钟冻 16:40 · 题号 45 个与进度(4 道试过没做对)是 fixture · '
      + '数据条换成「现在有几道 / 平均尝试次数 / 这一类已做对」· 格上写整类真题号 · 换一批只剩整级',
  });
  console.log(`[fourup 13w-wrong] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});

test('四图:做题屏错题模式 ←→ sample-go/shots/14-puzzle.png(同一副骨架)', async ({ page }) => {
  await boot(page, [PROBLEM.id, 'p8', 'p20', 'p33']);
  await page.goto(`/kiosk/tsumego/problem/${PROBLEM.id}?set=wrong`);
  await page.waitForSelector('.kiosk-layout-a .dots i:nth-child(4)');
  // 前置:真的在错题模式里。快照钥匙没对上时做题屏退回整类(45 道 ⇒ 点阵照样有第 4 个),上面那句等待拦不住。
  await expect(page.getByTestId('puzzle-pagebar')).toContainText('错题 第 1 / 4 道');
  await page.waitForLoadState('networkidle');
  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '14-puzzle.png'),
    outDir: OUT('14w-puzzle-wrong'),
    slug: '14w-puzzle-wrong',
    referenceCaption: '参考:sample-go/shots/14-puzzle.png · 稿子没画错题模式 ⇒ 拿屏 14 比骨架',
    implementationCaption:
      '实现:/kiosk/tsumego/problem/:id?set=wrong @1024×600 · 时钟冻 16:40 · 题目逐子同屏 14 fixture · '
      + '页控条「错题 第 1 / 4 道」、返回键「错题」、单元块「错题 · 4 道」;其余与屏 14 同',
  });
  console.log(`[fourup 14w-puzzle-wrong] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
