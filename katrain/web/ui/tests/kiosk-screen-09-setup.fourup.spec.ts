import { expect, test, type Page } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/07-09-platform/1024x600');

/** 屏 09 的 1024×600 预览；旧稿只作为左右栏构图参照。 */

/** 星阵那 39 档,按 `GOLAXY_AI_LEVELS` 的形状造,取第 22 档「星皮猴 · 2 段」对齐稿子那一帧。 */
const GOLAXY_LEVELS = {
  levels: Array.from({ length: 39 }, (_, i) => ({
    elo_score: 100 + i * 10,
    level_name: `第 ${i + 1} 档`,
    name: `星阵 ${i + 1}`,
    goal_difference: 0,
    timing: '',
    display_elo: 400 + i * 50,
    ref_rank: `业余 ${i + 1}`,
  })),
};

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
      platforms: [{
        platform: 'golaxy', connected: false,
        supports_live_play: true, supports_automatch: false,
        supports_rooms: true, supports_seek_graph: false, supports_engine_play: true,
      }],
    },
  }));
  await page.route('**/api/v1/platforms/golaxy/engine/levels', (route) => route.fulfill({ json: GOLAXY_LEVELS }));
  // 稿子那一帧「落子」选中的是实体盘 ⇒ 这台机器标定过摄像头。
  await page.route('**/api/v1/vision/status', (route) => route.fulfill({
    json: {
      enabled: true, camera_connected: true, pose_locked: true, sync_state: 'idle',
      bound_session_id: null, recognition_ready: true, led_connected: true,
    },
  }));
  await page.goto(path);
}

test('四图:跨平台 · 人机开局 ←→ sample-go/shots/09-platform-engine.png', async ({ page }) => {
  await boot(page, '/kiosk/play/cross-platform/engine/golaxy');
  await page.waitForSelector('[data-testid="platform-engine-start"]');
  await expect(page.locator('[data-testid="setup-opponent-plate"] .rung')).toContainText('第 1 / 39 档');
  await page.locator('[data-testid="setup-opponent-plate"]').click();
  await page.locator('[data-testid="level-row"]').nth(21).locator('button').click();
  await expect(page.locator('[data-testid="setup-opponent-plate"] .rung')).toContainText('第 22 / 39 档');
  await page.locator('[data-testid="setup-handicap"]').click();
  await page.locator('[data-testid="setup-handicap-pop"] [data-k="2"]').click();
  await expect(page.locator('[data-testid="setup-komi-value"]')).toContainText('黑贴 2 子');
  await page.locator('[data-testid="setup-handicap"]').evaluate((el: HTMLElement) => el.blur());
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '09-platform-engine.png'),
    outDir: OUT,
    slug: '09-platform-engine',
    referenceCaption: '旧稿:sample-go/shots/09-platform-engine.png · 左盘右栏构图参照',
    implementationCaption: '实现:星阵对手菜单选第 22 档、让 2 子 · 让子和贴目采用自由对弈的设置样式',
  });
  console.log(`[fourup 09-platform-engine] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
