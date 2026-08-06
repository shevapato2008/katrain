import { expect, test } from '@playwright/test';
import { resolve } from 'node:path';

const screenshotPath = resolve(
  process.cwd(),
  '../../../superpowers/tracks/galaxy-ai-ladder-journey/visual/setup/1440x900/implementation.png',
);

test('Galaxy 升降级对弈准备页 1440x900', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: 'tester', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/translations?lang=cn', (route) => route.fulfill({ json: {
    lang: 'cn',
    translations: {
      Home: '首页', 'btn:Play': '对局', Research: '研究', Tsumego: '死活题',
      'analysis:report': '复盘', Live: '直播', 'kifu:library': '棋谱库', Tutorials: '教程',
      Settings: '设置', Logout: '退出登录',
    },
  } }));
  await page.route('**/api/v1/live/translations?lang=cn', (route) => route.fulfill({
    json: { players: {}, tournaments: {}, rounds: {}, rules: {} },
  }));
  await page.route('**/assets/img/logo-white.png', (route) => route.fulfill({
    path: resolve(process.cwd(), '../../../katrain/img/logo-white.png'),
  }));
  await page.route('**/api/v1/ai-ladder/status', (route) => route.fulfill({
    json: {
      view_state: 'ready',
      placement_state: {
        phase: 'placed',
        rung: { rung: 30, rank_name: '5段', certification_status: 'certified', availability: 'available', route: 'server' },
      },
      current_opponent: { rung: 30, rank_name: '5段', certification_status: 'certified', availability: 'available', route: 'server' },
      recent_ranked_results: ['win', 'loss', 'win', 'win', 'loss'],
      net_score: 1,
      pending_settlement: false,
    },
  }));

  await page.goto('/galaxy/play/ai?mode=rated');
  await expect(page.getByRole('heading', { name: '升降级对弈' })).toBeVisible();
  await expect(page.getByRole('button', { name: '返回对局' })).toBeVisible();
  await expect(page.getByRole('button', { name: '开始正式对局' })).toBeEnabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: screenshotPath });
});
