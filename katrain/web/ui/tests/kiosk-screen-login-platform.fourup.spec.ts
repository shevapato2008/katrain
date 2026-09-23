import { expect, test, type Page } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/07-09-platform/1024x600');

/**
 * Task 8:登录独立成页(屏 07a 星阵·扫码 / 07b 星阵·密码 / 08 OGS·登录)的四图。
 *
 * 二维码必须是**确定性的** —— 真实 `scan/start` 的 `payload` 带随机 uuid,每次跑出来的
 * 码都不一样,四图会永远判「变了」。这里把 `scan/start` 钉成固定 payload
 * (`golaxy_url&&&FIXTURE-UUID`),`scan/state` 钉成 `waiting`(稿子 07a 画的就是
 * 「等待扫描」那一态)。
 *
 * 同一条预期差异(照 `kiosk-screen-07-09-platform.fourup.spec.ts` 头注的口径):
 * 稿子里那枚琥珀 / 蓝色的 `.wip` 施工标是给读稿人看的进度标注,**不上屏**。
 */

async function boot(page: Page, path: string) {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: '访客', rank: '20k', credits: 0 },
  }));
  await page.route('**/api/v1/platforms/status', (route) => route.fulfill({
    json: {
      platforms: [
        {
          platform: 'ogs', connected: false,
          supports_live_play: true, supports_automatch: true,
          supports_rooms: false, supports_seek_graph: true, supports_engine_play: false,
        },
        {
          platform: 'golaxy', connected: false,
          supports_live_play: true, supports_automatch: false,
          supports_rooms: true, supports_seek_graph: false, supports_engine_play: true,
        },
      ],
    },
  }));
  // 确定性二维码:固定 scan_id / payload,轮询钉在「等待扫描」——稿子 07a 那一态。
  await page.route('**/api/v1/platforms/golaxy/scan/start', (route) => route.fulfill({
    json: { scan_id: 'fixture-scan-id', payload: 'golaxy_url&&&FIXTURE-UUID', expires_at: 9999999999 },
  }));
  await page.route('**/api/v1/platforms/golaxy/scan/state*', (route) => route.fulfill({
    json: { state: 'waiting' },
  }));
  await page.goto(path);
}

test('四图:跨平台 · 登录 · 星阵扫码 ←→ sample-go/shots/07a-platform-login.png', async ({ page }) => {
  await boot(page, '/kiosk/play/cross-platform/login/golaxy');
  await page.waitForSelector('[data-testid="platform-login-page"]');
  await page.waitForSelector('[data-testid="scan-qr"]');
  await expect(page.locator('[data-testid="login-mode-tabs"]')).toBeVisible();
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '07a-platform-login.png'),
    outDir: OUT,
    slug: '07a-platform-login',
    referenceCaption:
      '参考:sample-go/shots/07a-platform-login.png · L2 布局 B · '
      + '扫码是星阵默认标签 · 左栏讲登录之前要知道的',
    implementationCaption:
      '实现:/kiosk/play/cross-platform/login/golaxy @1024×600 · 时钟冻 16:40 · '
      + '二维码内容钉死(`scan_id=fixture-scan-id`,`payload=golaxy_url&&&FIXTURE-UUID`),'
      + '状态钉在「等待扫描」——真实 payload 带随机 uuid,不钉的话四图每次跑都会判「变了」 · '
      + '**稿子那枚 `.wip`「扫码 · 未接后端」不上屏**(施工标是给读稿人看的,屏 07/08/15/19 同例,'
      + '扫码链今天已经接通,标注本身也已过期)',
  });
  console.log(`[fourup 07a-platform-login] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});

test('四图:跨平台 · 登录 · 星阵密码 ←→ sample-go/shots/07b-platform-login-pw.png', async ({ page }) => {
  await boot(page, '/kiosk/play/cross-platform/login/golaxy');
  await page.waitForSelector('[data-testid="platform-login-page"]');
  await page.waitForSelector('[data-testid="login-mode-tabs"]');
  await page.getByRole('button', { name: '密码' }).click();
  await page.waitForSelector('[data-testid="login-field-password"]');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '07b-platform-login-pw.png'),
    outDir: OUT,
    slug: '07b-platform-login-pw',
    referenceCaption:
      '参考:sample-go/shots/07b-platform-login-pw.png · L2 布局 B · '
      + '账号字段是手机号(星阵账号体系本身就是手机号,不是「用户名」)',
    implementationCaption:
      '实现:/kiosk/play/cross-platform/login/golaxy @1024×600 · 时钟冻 16:40 · '
      + '点到「密码」标签后的稳态截图 · 字段标签「手机号」+ `type="tel"` · '
      + '**稿子那枚 `.wip` 不上屏**(同头注)',
  });
  console.log(`[fourup 07b-platform-login-pw] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});

test('四图:跨平台 · 登录 · OGS ←→ sample-go/shots/08-platform-login-ogs.png', async ({ page }) => {
  await boot(page, '/kiosk/play/cross-platform/login/ogs');
  await page.waitForSelector('[data-testid="platform-login-page"]');
  await page.waitForSelector('[data-testid="login-field-user"]');
  await expect(page.locator('[data-testid="login-mode-tabs"]')).toHaveCount(0);
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '08-platform-login-ogs.png'),
    outDir: OUT,
    slug: '08-platform-login-ogs',
    referenceCaption:
      '参考:sample-go/shots/08-platform-login-ogs.png · L2 布局 B · '
      + 'OGS 只有一种登录方式',
    implementationCaption:
      '实现:/kiosk/play/cross-platform/login/ogs @1024×600 · 时钟冻 16:40 · '
      + '**标签栏整条不渲染**(单一选项的分段控件是假的选择,判例同屏 07/08 大厅那条) · '
      + '字段标签「用户名」/「密码」,`type="text"`/`type="password"`',
  });
  console.log(`[fourup 08-platform-login-ogs] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
