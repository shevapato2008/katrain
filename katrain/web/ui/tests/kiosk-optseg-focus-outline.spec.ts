import { expect, test, type Page } from '@playwright/test';
import { freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });

/**
 * Task 8b 第二轮:`.kiosk-optseg` 按钮的焦点描边。
 *
 * 根因是 `src/index.css`(Vite 脚手架遗留)原来的 `button:focus, button:focus-visible
 * { outline: 4px auto -webkit-focus-ring-color }` —— 加载顺序在 `theme.css`/`global.css`
 * 之后,`:focus-visible` 那一半和 `global.css` 里同 specificity 的 `button:focus-visible`
 * 打平,按加载顺序它赢,把浏览器默认蓝圈盖回了全站每一个按钮(包括 kiosk 侧那十几条
 * 专门写的 `:focus-visible` 覆盖 —— 它们 specificity 更高,理应赢,但这条闸最早只测了
 * 「颜色变了没」,没有测「点击路径下到底有没有描边」)。
 *
 * 修法(`src/index.css`):只删 `:focus` 那一半,只留 `:focus-visible`。这条闸测的是
 * 两条路径各自的结果:
 *   · 鼠标/触屏点击 → 不该有可见描边(和设计稿一致,`:focus-visible` 的鼠标/触屏启发式
 *     不命中原生 `:focus-visible` 语义时不应该显示,但 Chromium 对已经获得过 `:focus`
 *     的元素在测试环境里的判定可能因路径而异 —— 这条闸不猜启发式怎么判,只认最终结果:
 *     颜色不能是离色板的浏览器默认蓝)。
 *   · 键盘 Tab → 必须有可见描边,且颜色落在 `--accent` 色板内(可达性)。
 *
 * 变异判据:把 `src/index.css` 的 `:focus` 那一半加回去,第一条必须红。
 */

async function boot(page: Page) {
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
          platform: 'golaxy', connected: false,
          supports_live_play: true, supports_automatch: false,
          supports_rooms: true, supports_seek_graph: false, supports_engine_play: true,
        },
      ],
    },
  }));
  await page.goto('/kiosk/play/cross-platform/login/golaxy');
  await page.waitForSelector('[data-testid="login-mode-tabs"]');
}

/** 浏览器默认焦点圈的颜色族 —— Chromium 的 `-webkit-focus-ring-color` 渲染成蓝色系,
 * 和这套深绿毡设计系统的 `--accent`(墨绿/暖色系)不可能撞色,拿它当「离色板」的判据。 */
function isBlueUaRing(rgb: string): boolean {
  const m = rgb.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  if (!m) return false;
  const [, r, g, b] = m.map(Number) as unknown as [number, number, number, number];
  return b > r && b > g && b > 120;
}

test('鼠标/触屏点击标签:焦点描边不是离色板的浏览器默认蓝', async ({ page }) => {
  await boot(page);
  const tab = page.getByRole('button', { name: '密码' });
  await tab.click();
  const outlineColor = await tab.evaluate((el) => getComputedStyle(el).outlineColor);
  expect(isBlueUaRing(outlineColor)).toBe(false);
});

// ⚠️ 名字只说断言真的量了的那两件事。这条**没有**验「颜色正好是 `--accent`」——
// 断言写的是「有描边」+「不是离色板的蓝」,别照名字以为在色板内已经被守住了。
// (真实发生过的缺陷就是那圈蓝,这条闸对准的是它;要验确切色值得先做色值归一化,
// 与它挡住的缺陷不相称,故不做 —— 但名字不许替它宣称。)
test('键盘 Tab 到标签:有可见的焦点圈,且不是浏览器默认蓝', async ({ page }) => {
  await boot(page);
  // 从标签栏本身开始,连续按 Tab 越过「扫码」「验证码」落到「密码」——三个都是普通
  // <button>,顺序遍历,不依赖具体第几下。
  const tabs = page.locator('[data-testid="login-mode-tabs"] button');
  await tabs.first().focus();
  await page.keyboard.press('Tab');
  await page.keyboard.press('Tab');
  const target = page.getByRole('button', { name: '密码' });
  await expect(target).toBeFocused();

  const style = await target.evaluate((el) => {
    const cs = getComputedStyle(el);
    return { outlineStyle: cs.outlineStyle, outlineColor: cs.outlineColor };
  });
  expect(style.outlineStyle).not.toBe('none');
  expect(isBlueUaRing(style.outlineColor)).toBe(false);
});
