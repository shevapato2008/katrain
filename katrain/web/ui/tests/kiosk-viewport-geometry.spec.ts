import { expect, test, type Page } from '@playwright/test';
import { writeFileSync } from 'node:fs';
import { KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

/**
 * 整棵 kiosk 树的**视口盒子** —— 承重实测(设置赛道 ST6)。
 *
 * 旋转功能 2026-07-08 删了入口,可 `RotationWrapper` 即使在 rotation=0 下也渲染一个
 * `position:fixed; 100vw×100vh; overflow:hidden` 的盒子,它是:
 *  · `.kiosk` 画布的**包含块** —— 画布是 `absolute; top/left:50%` 居中的,居中的原点就是它;
 *  · 登录页的**高度来源** —— `LoginPage` 在 `KioskLayout` 外面,写的是 `height:100%`,
 *    那个 100% 直接取这只盒子的 100vh。少了它登录页会塌成内容高(塌陷类:最空状态下才看得出);
 *  · 整棵树的**裁切边界**。
 * ⇒ 删旋转机器时这只盒子必须原样留下。jsdom 没有布局引擎,这一条只能在真浏览器里量。
 *
 * 判据全是**关系式**(盒子 = 视口、画布居中且落在盒内、文档不溢出、该滚的那一格自己能滚、
 * 登录页 = 视口),具体像素不作判据。两个视口:原生 1024×600(缩放 1)和一个放大的
 * (缩放 ≠ 1 时居中才真的依赖包含块)。
 *
 * `GEOMETRY_DUMP=<path>` 时把量到的数写出来 —— 改前改后各写一份,`diff` 两份就是逐字段比对。
 */

const VIEWPORTS = [KIOSK_VIEWPORT, { width: 1280, height: 800 }] as const;

// 复盘列表造到**两屏以上**:装得下的数据量下「能不能滚」量出来的数不作数。
const GAMES = Array.from({ length: 30 }, (_, i) => ({
  id: `g${i + 1}`, title: null, player_black: '访客', player_white: 'KataGo',
  black_rank: null, white_rank: '6 级', result: 'W+R', move_count: 120 + i,
  source: 'play_ai', game_type: 'free', created_at: new Date(Date.UTC(2026, 7, 20, 12, 0) - i * 3_600_000).toISOString(),
  user_id: 1, board_size: 19, rules: 'chinese', komi: 7.5, category: 'game',
  event: null, round_name: null, game_date: '2026-08-20', updated_at: null,
}));

async function stubCommon(page: Page, signedIn: boolean) {
  await page.addInitScript((token) => {
    localStorage.setItem('katrain_language', 'cn');
    if (token) localStorage.setItem('token', token);
  }, signedIn ? 'geometry' : '');
  await stubBackendStatics(page);
  if (signedIn) {
    await page.route('**/api/v1/auth/me', (route) => route.fulfill({
      json: { id: 1, username: '访客', rank: '5段', credits: 0 },
    }));
  }
  await page.route('**/api/v1/geometry/status', (route) => route.fulfill({
    json: {
      phase: 'ready', session_calibrated: true, last_error: null,
      capabilities: { camera_ready: true, led_ready: true, geometry_ready: true, recognition_ready: true },
    },
  }));
  await page.route('**/api/v1/user-games**', (route) => route.fulfill({
    json: { items: GAMES, total: GAMES.length, page: 1, page_size: GAMES.length },
  }));
  await page.route('**/api/v1/reports/summary', (route) => route.fulfill({
    json: { pending: 0, running: 0, completed: 0, failed: 0 },
  }));
  await page.route('**/api/v1/reports/', (route) => route.fulfill({ json: [] }));
}

type Rect = { x: number; y: number; w: number; h: number };
interface Measured {
  vw: number; vh: number;
  doc: { sw: number; cw: number; sh: number; ch: number };
  box: (Rect & { overflow: string }) | null;
  root: Rect;
  scroll: { sh: number; ch: number; top: number } | null;
}

/** 从 `rootSelector` 往上找**最近的 fixed 祖先** —— 改前是旋转盒子,改后是视口盒子,判据不认名字。 */
async function measure(page: Page, rootSelector: string, scrolls: boolean): Promise<Measured> {
  return page.evaluate(([sel, wantScroll]) => {
    const rect = (el: Element) => {
      const r = el.getBoundingClientRect();
      return { x: r.x, y: r.y, w: r.width, h: r.height };
    };
    const root = document.querySelector(sel as string)!;
    let box = root.parentElement;
    while (box && getComputedStyle(box).position !== 'fixed') box = box.parentElement;
    const doc = document.documentElement;
    let scroll = null;
    if (wantScroll) {
      const zone = document.querySelector('.kiosk-side__scroll') as HTMLElement;
      zone.scrollTop = 1e6;
      scroll = { sh: zone.scrollHeight, ch: zone.clientHeight, top: zone.scrollTop };
    }
    return {
      vw: window.innerWidth, vh: window.innerHeight,
      doc: { sw: doc.scrollWidth, cw: doc.clientWidth, sh: doc.scrollHeight, ch: doc.clientHeight },
      box: box ? { ...rect(box), overflow: getComputedStyle(box).overflow } : null,
      root: rect(root),
      scroll,
    };
  }, [rootSelector, scrolls] as const);
}

function expectViewportBox(m: Measured) {
  expect(m.box, '视口盒子不在了:没有任何 fixed 祖先').not.toBeNull();
  expect(m.box!).toMatchObject({ x: 0, y: 0, w: m.vw, h: m.vh, overflow: 'hidden' });
  expect(m.doc.sw, '文档横向溢出').toBeLessThanOrEqual(m.doc.cw);
  expect(m.doc.sh, '文档纵向溢出').toBeLessThanOrEqual(m.doc.ch);
}

function expectCanvasCentred(m: Measured) {
  expect(Math.abs(m.root.x + m.root.w / 2 - m.vw / 2), '画布水平没居中').toBeLessThan(1);
  expect(Math.abs(m.root.y + m.root.h / 2 - m.vh / 2), '画布垂直没居中').toBeLessThan(1);
  expect(m.root.x).toBeGreaterThanOrEqual(-0.5);
  expect(m.root.y).toBeGreaterThanOrEqual(-0.5);
  expect(m.root.x + m.root.w).toBeLessThanOrEqual(m.vw + 0.5);
  expect(m.root.y + m.root.h).toBeLessThanOrEqual(m.vh + 0.5);
}

function expectScrolls(m: Measured) {
  // 该滚的是右栏那一格自己,不是它的祖先:写一个大 scrollTop 之后读回来要到底。
  expect(m.scroll!.sh, '数据没造到溢出,这一格量了也不作数').toBeGreaterThan(m.scroll!.ch * 2);
  expect(Math.abs(m.scroll!.top - (m.scroll!.sh - m.scroll!.ch))).toBeLessThanOrEqual(1);
}

const dump: Record<string, Measured> = {};

for (const vp of VIEWPORTS) {
  test.describe(`${vp.width}×${vp.height}`, () => {
    test.use({ viewport: vp });

    test('设置屏:盒子 = 视口,画布居中,右栏自己能滚', async ({ page }) => {
      await stubCommon(page, true);
      await page.goto('/kiosk/settings');
      await page.waitForSelector('[data-group="language"]');
      const m = await measure(page, '.kiosk', true);
      dump[`${vp.width}x${vp.height} settings`] = m;
      expectViewportBox(m);
      expectCanvasCentred(m);
      expectScrolls(m);
    });

    test('复盘列表(30 局):同上', async ({ page }) => {
      await stubCommon(page, true);
      await page.goto('/kiosk/report');
      await page.waitForSelector('.kiosk-side__scroll');
      await page.waitForLoadState('networkidle');
      const m = await measure(page, '.kiosk', true);
      dump[`${vp.width}x${vp.height} report`] = m;
      expectViewportBox(m);
      expectCanvasCentred(m);
      expectScrolls(m);
    });

    test('对弈首页(游客):盒子 = 视口,画布居中', async ({ page }) => {
      await stubCommon(page, false);
      await page.goto('/kiosk/play');
      await page.waitForSelector('.kiosk-screen');
      const m = await measure(page, '.kiosk', false);
      dump[`${vp.width}x${vp.height} play`] = m;
      expectViewportBox(m);
      expectCanvasCentred(m);
    });

    // 塌陷类:登录页在 `KioskLayout` 外面,`height:100%` 取的是视口盒子的 100vh。
    test('登录页:高度来自视口盒子,不塌', async ({ page }) => {
      await stubCommon(page, false);
      await page.goto('/kiosk/login');
      await page.waitForSelector('[data-testid="kiosk-login-page"]');
      const m = await measure(page, '[data-testid="kiosk-login-page"]', false);
      dump[`${vp.width}x${vp.height} login`] = m;
      expectViewportBox(m);
      expect(m.root).toMatchObject({ x: 0, y: 0, w: m.vw, h: m.vh });
    });
  });
}

test.afterAll(() => {
  if (process.env.GEOMETRY_DUMP) writeFileSync(process.env.GEOMETRY_DUMP, JSON.stringify(dump, null, 2));
});
