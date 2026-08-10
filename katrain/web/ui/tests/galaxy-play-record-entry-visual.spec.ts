import { expect, test, type Page } from '@playwright/test';
import { resolve } from 'node:path';

const translationFixture = {
  Home: '首页',
  'btn:Play': '对局',
  Research: '研究',
  Tsumego: '死活题',
  'analysis:report': '复盘',
  Live: '直播',
  'kifu:library': '棋谱库',
  Tutorials: '教程',
  Settings: '设置',
  Logout: '退出登录',
  More: '更多',
  'play:choose_mode': '选择游戏模式',
  'play:game_records': '对局记录',
  'play:vs_ai_free': '自由对弈',
  'play:vs_ai_free_desc': '使用完整分析、悔棋和自定义设置练习。',
  'play:rated_ai': '升降级对弈',
  'play:rated_ai_desc': '与拟人 AI 进行计入段位的正式对局。',
  'play:hvh': '对战大厅',
  'play:hvh_desc': '挑战好友或在线匹配对手。',
};

const prepareGalaxyPlay = async (page: Page) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: '棋手', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/translations?lang=cn', (route) => route.fulfill({
    json: { lang: 'cn', translations: translationFixture },
  }));
  await page.route('**/api/v1/live/translations?lang=cn', (route) => route.fulfill({
    json: { players: {}, tournaments: {}, rounds: {}, rules: {} },
  }));
  await page.route('**/api/v1/tsumego/progress', (route) => route.fulfill({ json: {} }));
  await page.route('**/api/v1/user-games**', (route) => route.fulfill({
    json: { items: [], total: 0, page: 1, page_size: 12 },
  }));
  await page.route('**/api/v1/reports**', (route) => route.fulfill({
    json: { items: [], total: 0 },
  }));
  await page.route('**/assets/img/logo-white.png', (route) => route.fulfill({
    path: resolve(process.cwd(), '../../../katrain/img/logo-white.png'),
  }));
};

for (const viewport of [
  { width: 1440, height: 900 },
  { width: 430, height: 880 },
] as const) {
  test(`Galaxy 对局记录入口 ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await prepareGalaxyPlay(page);
    await page.goto('/galaxy/play');

    await expect(page.getByRole('heading', { name: '对局', exact: true })).toBeVisible();
    const recordsButton = page.getByRole('button', { name: '对局记录', exact: true });
    await expect(recordsButton).toBeVisible();
    await expect(page.locator('.MuiCard-root')).toHaveCount(3);
    await expect(page.getByRole('button', { name: /自由对弈/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /升降级对弈/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /对战大厅/ })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);

    const screenshotPath = resolve(
      process.cwd(),
      `../../../superpowers/tracks/galaxy-ai-ladder-journey/visual/play-record-entry/${viewport.width}x${viewport.height}/implementation.png`,
    );
    await page.screenshot({ path: screenshotPath });

    await recordsButton.click();
    await expect(page).toHaveURL(/\/galaxy\/report$/);
  });
}
