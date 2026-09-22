import { expect, test, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';
import { kioskMeJson } from './helpers/kioskIdentity';

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
    /* 错题快照按账号存(Task 7),下面 auth/me 回 uuid=u1 ⇒ 真键是 `..._wrong:u1`。
       ⚠️ **它在 localStorage,不在 sessionStorage** —— `readWrongSequence` 走的是
       `getCurrentKioskActivityStorage()`(真用户 ⇒ 带后缀的 localStorage),而**不带
       `_wrong` 的整类顺序表**才是 sessionStorage(`readSequence` 直接读它)。
       同一个文件里两条顺序表分属两种存储,写错一条做题屏会**静默退回整类**、四图照样出图。 */
    if (snap) localStorage.setItem('kiosk_problems_15k_capturing_wrong:u1', JSON.stringify(snap));
  }, { progress: PROGRESS, snap: snapshot });
  await stubBackendStatics(page);
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') {
      return route.fulfill({ json: kioskMeJson({ username: '访客' }) });
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

/**
 * 屏 12 补一张滚到底的实现图(review round 1)。**不是四图**:
 * 屏 12 本尊钉在参考稿的 1024×600,「整级一起做」那一段(N8 新副标 + T1「只做错过的」卡)
 * 在那个高度之外 —— 稿子没画滚到底那一态,没有参考图可比,`captureFourUp` 用不上。
 * 这里只证明:真滚到底之后,这两句话真的在屏上、在视口里,不是写在标签带里的空话。
 */
const UNITS_IDS = Array.from({ length: 180 }, (_, i) => ({ id: `p${i}` }));
const UNITS_PROGRESS = {
  // 做错过、还没做对(`isWrongEntry`)⇒「只做错过的」卡可点、写着真数,不是 disabled 的灰卡。
  p5: { completed: false, attempts: 2 },
};

test('滚到底:屏 12 下半屏(整级一起做 + 只做错过的)真的在视口里', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript((progress) => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
    localStorage.setItem('tsumego_progress:u1', JSON.stringify(progress));
  }, UNITS_PROGRESS);
  await stubBackendStatics(page);
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') {
      return route.fulfill({ json: kioskMeJson({ username: '访客' }) });
    }
    if (path.startsWith('/api/v1/tsumego/levels/') && path.includes('/categories/')) {
      return route.fulfill({ json: UNITS_IDS });
    }
    if (path === '/api/v1/tsumego/progress') return route.fulfill({ json: {} });
    return route.fulfill({ json: {} });
  });
  await page.goto('/kiosk/tsumego/15k/capturing');
  await page.waitForSelector('.kiosk-cards .kiosk-card:nth-child(9)');
  await page.waitForLoadState('networkidle');

  // **真滚轮**,和 `kiosk-tsumego-wrong.spec.ts` 那条承重闸同一手法 —— `scrollTop = n` 证明不了用户能滚到。
  const zone = page.locator('.kiosk-scrollzone').first();
  await page.mouse.move(500, 300);
  await page.mouse.wheel(0, 5000);
  await expect.poll(() => zone.getAttribute('data-at')).toBe('end');

  // 两句都要真的在 1024×600 视口里 —— 不是在 DOM 里、被滚动区裁掉。future 的裁切要在这里当场红,
  // 不能再靠人肉逐张打开四图才发现(round 1 finding 的成因)。
  /* ⚠️ 这一句跟着源码走,别照抄旧稿:develop 的 `4f80ec9e` 把「整级一起做 · 按分类排好，
     不分单元」换成了「综合训练 · 混合当前难度全部题型，每 20 题一单元」
     (`TsumegoUnitsPage.tsx:206-209`)。测试等一句源码里已经没有的话,报的是
     「element(s) not found」—— 看起来像被裁掉了,其实是文案改了。 */
  const wholeLevelSub = page.getByText('混合当前难度全部题型，每 20 题一单元');
  const wrongCard = page.getByText('只做错过的', { exact: true });
  await expect(wholeLevelSub).toBeInViewport();
  await expect(wrongCard).toBeInViewport();

  const outDir = OUT('12s-units-scrolled');
  mkdirSync(outDir, { recursive: true });
  await page.screenshot({
    path: resolve(outDir, '12s-units-scrolled--implementation.png'),
    animations: 'disabled',
  });
});
