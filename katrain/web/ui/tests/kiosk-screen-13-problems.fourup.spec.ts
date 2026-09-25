import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';
import { kioskMeJson } from './helpers/kioskIdentity';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const REFERENCE = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-ui-redesign/artifacts/13-problems-split-preview.png');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-ui-redesign/visual/13-problems/1024x600');

/**
 * 屏 13 双栏题目列表，对照用户已确认的 1024×600 HTML 设计稿。
 *
 * 稿子那一格画的是「做了 3 道、第 4 道是下一道」的中途态,所以这里**得造进度** ——
 * 造的是 `tsumego_progress:u<id>`(真存储,真格式),不是往组件里塞假 props。
 * ⚠️ `attempts` 存的是**失败**的那几次,屏上那句「N 次」= `attempts + (做对了 ? 1 : 0)`:
 * 稿子上的 `1 次 / 1 次 / 3 次` 对应 `attempts: 0 / 0 / 2`。
 */
const IDS = Array.from({ length: 45 }, (_, i) => ({ id: `p${i}` }));

test('四图:双栏题目列表 ←→ 用户确认的 7 英寸设计稿', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
    // 稿子那一屏:前 3 道做对(试了 1 / 1 / 3 次),第 4 道是下一道且一次没试过,
    // 另有一道错过没做对的(第 21 题,给「换一批」那行的「现在有 1 道」当依据)。
    // ⚠️ 钥匙**带 user id**(`progressStorageKey`)—— S1 把做题进度改成分人存之后,
    // 这个 fixture 的钥匙一直没跟着改:整整一天,这一屏的四图里三个数全是「0 / — / —」,
    // 而闸照样绿、三个计数照样打印。**没人重跑四图,所以没人知道。**
    // 这里的 `auth/me` 回的是 id=1 ⇒ `tsumego_progress:u1`。
    localStorage.setItem('tsumego_progress:u1', JSON.stringify({
      p0: { completed: true, attempts: 0, lastDuration: 18 },
      p1: { completed: true, attempts: 0, lastDuration: 21 },
      p2: { completed: true, attempts: 2, lastDuration: 27 },
      p20: { completed: false, attempts: 1 },
    }));
  });
  // 后端没起时 logo 会 502,取出来的图左上角是碎图标 —— 钉在仓里那份真字节上。
  await stubBackendStatics(page);
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') {
      return route.fulfill({ json: kioskMeJson({ username: '访客' }) });
    }
    if (path.startsWith('/api/v1/tsumego/levels/') && path.includes('/categories/')) {
      return route.fulfill({ json: IDS });
    }
    if (path.startsWith('/api/v1/tsumego/problems/')) {
      const id = path.split('/').at(-1);
      return route.fulfill({ json: {
        id, level: '15k', category: 'capturing', hint: '黑先', boardSize: 19,
        initialBlack: ['co', 'bp', 'eo', 'fp'], initialWhite: ['cp', 'ep'], sgfContent: '',
      } });
    }
    if (path === '/api/v1/tsumego/progress') return route.fulfill({ json: {} });
    return route.fulfill({ json: {} });
  });
  await page.goto('/kiosk/tsumego/15k/capturing/1');
  await page.waitForSelector('.qgrid button:nth-child(20)');
  await page.waitForSelector('[data-testid="problem-preview-board"] [data-stone="b"]');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: REFERENCE,
    localReference: true,
    outDir: OUT,
    slug: '13-problems',
    referenceCaption: '参考:已确认的 7 英寸 HTML 设计稿 · 516 棋盘 + 460 右栏 · 第 4 题预览',
    implementationCaption: '实现:真实题目接口的初始棋形 · 20 题 5×4 · 底部进入所选题 · 题目 fixture 与设计稿示意棋形不同',
  });
  console.log(`[fourup 13-problems] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
