import { expect, test, type Page } from '@playwright/test';

/**
 * 屏上不许留下**没替换掉的 `{占位符}`**。
 *
 * ⚠️ **这条闸是被四图对比抓出来的漏洞补的,不是想出来的。** 2026-08-22(Task 13):
 * 单元列表的卡片写成 `t('tsumego:unit', '第 {n} 单元').replace('{n}', …)`,
 * 而 `tsumego:unit` 在 cn PO 里是 **`单元`**(galaxy 三处在用)。翻译表**赢过**默认值 ⇒
 * `.replace('{n}', …)` 找不到东西可换,屏上出现的是「单元」和「第 {start}-{end} 题」。
 *
 * **单测抓不到这一类**:jsdom 里翻译表没加载,`t()` 恒返回我自己写的默认值,
 * 而默认值里的占位符名当然和我的 `.replace` 对得上 —— 断言断的是「我自己和我自己一致」。
 * 判据必须落在**真浏览器 + 真翻译表**上:屏上那段字里还有没有花括号。
 *
 * 扫的是 `innerText`(渲染后的文字),不是源码 —— 所以它连**我没想到要探的那一块**一起管。
 */

test.use({ viewport: { width: 1024, height: 600 } });

const boot = async (page: Page, path: string) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'kiosk-copy-gate');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: 'tester', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/v1/tsumego/levels', (route) => route.fulfill({
    json: [{ level: '15k', categories: { capturing: 45, 'life-death': 20 }, total: 65 }],
  }));
  await page.route('**/api/v1/tsumego/levels/*/categories/*', (route) => route.fulfill({
    json: Array.from({ length: 45 }, (_, i) => ({ id: `q${i}` })),
  }));
  await page.route('**/api/v1/tsumego/problems/*', (route) => route.fulfill({
    json: {
      id: 'q0', level: '15k', category: 'capturing', hint: '黑先', boardSize: 19,
      initialBlack: ['co'], initialWhite: ['cp'], sgfContent: '',
    },
  }));
  await page.goto(path);
  await page.waitForSelector('.kiosk-screen', { state: 'attached' });
  // 翻译表是异步取的 —— 早一步扫到的是默认值,而默认值恰好总是自洽的。
  await page.waitForLoadState('networkidle');
};

/** 只认 `{word}` 这一种写法(项目里的惯例)。CSS/JS 里的花括号不会进 innerText。 */
const PLACEHOLDER = /\{[A-Za-z_]\w*\}/g;

const screens: readonly (readonly [string, string, string])[] = [
  ['对弈首页', '/kiosk/play', '.kiosk-cards .kiosk-card'],
  ['训练营', '/kiosk/tsumego', '.kiosk-cards .kiosk-card'],
  ['单元列表', '/kiosk/tsumego/15k/capturing', '.kiosk-cards .kiosk-card'],
  ['题目列表', '/kiosk/tsumego/15k/capturing/1', '.qgrid button'],
  ['做题屏', '/kiosk/tsumego/problem/q0', '[data-testid="puzzle-actions"] button'],
];

for (const [name, path, ready] of screens) {
  test(`${name}:屏上没有没替换掉的 {占位符}`, async ({ page }) => {
    await boot(page, path);
    // 等到内容真的渲出来 —— 空屏当然没有占位符,那种绿是假的。
    await page.waitForSelector(ready);
    const found = await page.evaluate((re) => {
      const text = (document.querySelector('.kiosk-screen') as HTMLElement).innerText;
      return text.match(new RegExp(re, 'g')) ?? [];
    }, PLACEHOLDER.source);
    expect(found, `${name} 屏上还留着没替换的占位符 —— 多半是拿了一个已有 msgid 却套了新的占位符名`)
      .toEqual([]);
  });
}
